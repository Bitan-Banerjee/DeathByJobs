import os
import json
import time
import sys
import re

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

from utils.config_loader import load_profile, get_excluded_companies
from utils.llm_client import generate_json, LLMError, get_batch_delay_seconds

SCRAPED_PATH = os.path.join(BASE_DIR, 'data', 'jobs.json')
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')

_profile = load_profile()
_filters = _profile.get("filters", {})
_title_cfg = _filters.get("title", {})
BATCH_SIZE = 10
DELAY_BETWEEN_BATCHES = get_batch_delay_seconds()

def passes_basic_filter(title, company, profile=None):
    if profile is None:
        profile = _profile
    title_lower = title.lower()
    company_lower = company.lower()

    excluded_companies = get_excluded_companies(profile)
    if any(excluded.lower() in company_lower for excluded in excluded_companies):
        return False

    title_cfg = profile.get("filters", {}).get("title", _title_cfg)
    red_flags = title_cfg.get("red_flags", _title_cfg.get("red_flags", []))
    for flag in red_flags:
        if flag.lower() in title_lower.split() or re.search(r'\b' + re.escape(flag.lower()) + r'\b', title_lower):
            return False
    return True

def evaluate_job_batch(batch_jobs, profile_data):
    # Create a compact payload for the AI to read
    jobs_payload = []
    for i, job in enumerate(batch_jobs):
        jobs_payload.append({
            "id": str(i),
            "title": job.get('title'),
            "company": job.get('company'),
            "description": job.get('description', '')
        })

    dealbreakers_text = "\n    ".join(profile_data.get('filters', {}).get('dealbreakers', []))
    skills_text = ", ".join(profile_data.get('target_profile', {}).get('core_skills', []))
    target_role = profile_data.get('target_profile', {}).get('role', 'Unknown')
    experience = profile_data.get('target_profile', {}).get('experience_range', 'Not specified')
    variance = profile_data.get('filters', {}).get('match_variance', 'moderate')

    # Build skill-flexibility wording based on user-selected variance.
    variance_rules = {
        "strict": (
            "Tool requirements are STRICT. Only consider a job a match if it explicitly mentions "
            "the candidate's core skills. Do not infer analogous tools."
        ),
        "moderate": (
            "Analogous skills are acceptable when a direct skill is not present. "
            "Example: AWS, Azure, and GCP are considered analogous cloud platforms. "
            "Glue and Databricks are considered analogous data tools."
        ),
        "loose": (
            "Use broad domain matching. Any role in the same field (data engineering, cloud, backend data infrastructure) "
            "can be a match if the description aligns with the candidate's overall background."
        ),
    }
    variance_rule = variance_rules.get(variance, variance_rules["moderate"])

    prompt = f"""You are an expert technical recruiter.

Candidate Profile:
Target Role: {target_role}
Candidate Experience: {experience}
Core Skills: {skills_text}
Match Variance Level: {variance}

CRITICAL DEALBREAKERS (Reject if ANY are true):
{dealbreakers_text}

SKILL FLEXIBILITY RULES:
{variance_rule}

Evaluate the following batch of jobs.
Return ONLY a valid JSON object mapping the "id" to an object containing:
- "reasoning": Step-by-step reasoning.
- "score": 0-100 based on skill alignment.
- "match": boolean (true/false).
- "match_type": "direct" (strong alignment) or "potential" (analogous skills).

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

    try:
        return generate_json(prompt, temperature=0.2)
    except LLMError as e:
        print(f"  ⚠️ LLM failed for batch: {e}")
        raise

def match_jobs_batched(scraped_path=SCRAPED_PATH, matched_path=MATCHED_PATH):
    start_time = time.time()
    if not os.path.exists(scraped_path):
        print(f"❌ Missing {scraped_path}.")
        return

    profile_data = load_profile()
    if not profile_data:
        print("❌ Missing or invalid profile.json. Please create it in the config/ directory.")
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