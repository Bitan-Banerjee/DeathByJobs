import os
import json
import time
from dotenv import load_dotenv
from google import genai

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

api_keys = []
for key_name in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"]:
    if os.getenv(key_name):
        api_keys.append(os.getenv(key_name).strip())

SCRAPED_PATH = os.path.join(BASE_DIR, 'data', 'jobs.json')
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
PROFILE_PATH = os.path.join(BASE_DIR, 'config', 'profile.json')

BATCH_SIZE = 10  # Balanced for Gemini Flash to handle reasoning tokens safely
DELAY_BETWEEN_BATCHES = 15  # 15 seconds delay to stay safely under the 5 RPM limit

def passes_basic_filter(title, company):
    title_lower = title.lower()
    company_lower = company.lower()
    
    if 'turing' in company_lower:
        return False

    red_flags = ['director', 'manager', 'vp', 'lead', 'head']
    for flag in red_flags:
        if flag in title_lower.split():
            return False
    return True

def evaluate_job_batch(batch_jobs, profile_data):
    if not api_keys:
        raise Exception("No Gemini API keys found in .env file.")
        
    # Create a compact payload for the AI to read
    jobs_payload = []
    for i, job in enumerate(batch_jobs):
        jobs_payload.append({
            "id": str(i),
            "title": job.get('title'),
            "company": job.get('company'),
            "description": job.get('description', '')
        })

    dealbreakers_text = "\n    ".join(profile_data.get('dealbreakers', []))
    skills_text = ", ".join(profile_data.get('core_skills', []))

    prompt = f"""
    You are an expert technical recruiter. 
    
    Candidate Profile:
    Target Role: {profile_data.get('target_role')}
    Candidate Experience: {profile_data.get('candidate_experience')}
    Core Skills: {skills_text}
    
    CRITICAL DEALBREAKERS (Reject if ANY are true):
    {dealbreakers_text}

    SKILL FLEXIBILITY RULES:
    1. Cloud Platforms: AWS, Azure, and GCP are considered analogous. If a job requires Azure but the candidate has AWS, it is a "potential" match.
    2. Data Tools: Glue and Databricks are considered analogous. 
    3. Experience: Years of experience are strict dealbreakers if specified in dealbreakers.

    Evaluate the following batch of jobs. 
    Return ONLY a valid JSON object mapping the "id" to an object containing:
    - "reasoning": Step-by-step reasoning.
    - "score": 0-100 based on skill alignment.
    - "match": boolean (true/false).
    - "match_type": "direct" (strong alignment) or "potential" (analogous skills like AWS vs Azure).

    Format exactly like this:
    {{
      "0": {{"reasoning": "...", "score": 85, "match": true, "match_type": "direct"}},
      "1": {{"reasoning": "...", "score": 75, "match": true, "match_type": "potential"}}
    }}

    Jobs to evaluate:
    '''
    {json.dumps(jobs_payload)}
    '''
    """
    
    fallback_models = ['gemini-flash-latest', 'gemini-2.5-flash', 'gemini-flash-lite-latest']
    
    for key_idx, api_key in enumerate(api_keys):
        client = genai.Client(api_key=api_key)
        for model_name in fallback_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                text = response.text.strip()
                if text.startswith("```json"): text = text[7:-3].strip()
                elif text.startswith("```"): text = text[3:-3].strip()
                return json.loads(text)
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    print(f"  ⚠️ 429 Rate Limit hit on {model_name} (Key {key_idx + 1}). Switching...")
                    continue
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    print(f"  ⚠️ Model {model_name} not found. Switching...")
                    continue
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    print(f"  ⚠️ 503 Service Unavailable on {model_name} (Key {key_idx + 1}). Switching...")
                    continue
                else:
                    print(f"  ⚠️ API Error on batch with {model_name} (Key {key_idx + 1}): {error_str}")
                    continue
                    
    raise Exception("Gemini API limits exhausted across all available keys. Halting to prevent data loss.")

def match_jobs_batched(scraped_path=SCRAPED_PATH, matched_path=MATCHED_PATH):
    start_time = time.time()
    if not os.path.exists(scraped_path):
        print(f"❌ Missing {scraped_path}.")
        return
        
    if not os.path.exists(PROFILE_PATH):
        print(f"❌ Missing {PROFILE_PATH}. Please create profile.json in the root directory.")
        return
        
    try:
        with open(PROFILE_PATH, 'r') as f:
            profile_data = json.load(f)
    except json.JSONDecodeError:
        print(f"❌ Error: {PROFILE_PATH} is empty or contains invalid JSON.")
        return
        
    try:
        with open(scraped_path, 'r') as f:
            jobs = json.load(f).get('jobs', [])
    except json.JSONDecodeError:
        print(f"❌ Error: {scraped_path} is empty or contains invalid JSON.")
        return
        
    # Pre-filter to save API calls
    valid_jobs = [j for j in jobs if passes_basic_filter(j.get('title', ''), j.get('company', ''))]
    
    print(f"🔍 Evaluating {len(valid_jobs)} jobs using Gemini Batched API (Batch Size: {BATCH_SIZE})...")
    approved_jobs = []
    
    for i in range(0, len(valid_jobs), BATCH_SIZE):
        batch = valid_jobs[i:i + BATCH_SIZE]
        print(f"\n📦 Sending Batch {i//BATCH_SIZE + 1} ({len(batch)} jobs) to Gemini...")
        
        results = evaluate_job_batch(batch, profile_data)
        
        for job_idx_str, data in results.items():
            idx = int(job_idx_str)
            if idx < len(batch):
                company = batch[idx].get('company', 'Unknown')
                title = batch[idx].get('title', 'Unknown')
                
                # Extract boolean and reasoning safely
                if isinstance(data, dict):
                    is_match = str(data.get("match", "false")).lower() == "true"
                    reason = data.get("reasoning", "No reasoning provided.")
                    score = data.get("score", 0)
                    match_type = data.get("match_type", "direct")
                else:
                    is_match = str(data).lower() == "true"
                    reason = "No reasoning provided."
                    score = 0
                    match_type = "direct"
                
                if is_match:
                    if score >= 70: # Lowered threshold slightly for potential matches
                        print(f"  ✅ MATCHED ({match_type.upper()}, Score: {score}): {company} - {title}")
                        print(f"     └ 📝 {reason}")
                        batch[idx]['ai_score'] = score
                        batch[idx]['match_type'] = match_type
                        approved_jobs.append(batch[idx])
                    else:
                        print(f"  ❌ REJECTED (Low Score: {score}): {company} - {title}")
                        print(f"     └ 📝 {reason}")
                else:
                    print(f"  ❌ REJECTED (Score: {score}): {company} - {title}")
                    print(f"     └ 📝 {reason}")
        
        # Respect the 5 RPM rate limit (if there are more batches to process)
        if i + BATCH_SIZE < len(valid_jobs):
            print(f"  ⏳ Sleeping for {DELAY_BETWEEN_BATCHES}s to respect API rate limits...")
            time.sleep(DELAY_BETWEEN_BATCHES)
            
    os.makedirs(os.path.dirname(matched_path), exist_ok=True)
    with open(matched_path, 'w') as f:
        json.dump({"approved_jobs": approved_jobs}, f, indent=4)
        
    print(f"\n🎉 Done! Approved {len(approved_jobs)} jobs. Saved to {matched_path}")
    print(f"⏱️ Total runtime: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    match_jobs_batched()