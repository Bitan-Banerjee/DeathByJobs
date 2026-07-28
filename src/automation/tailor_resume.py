import os
import json
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

api_keys = []
for key_name in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"]:
    if os.getenv(key_name):
        api_keys.append(os.getenv(key_name).strip())

MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
BASE_RESUME_PATH = os.path.join(BASE_DIR, 'base_resume.md')
GENERIC_RESUME_PATH = os.path.join(BASE_DIR, 'resume.docx')
TEMPLATE_PATH = os.path.join(BASE_DIR, 'templates', 'cv-template.html')
OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs', 'resumes')

def generate_tailored_html(job_title, job_desc, base_resume):
    if not api_keys:
        raise Exception("No Gemini API keys found in .env file.")
        
    prompt = f"""
    You are an expert executive resume writer. 
    
    BASE RESUME (Markdown):
    {base_resume}
    
    JOB TARGET: {job_title}
    JOB DESCRIPTION:
    {job_desc}
    
    INSTRUCTIONS:
    1. Read the Base Resume and the Job Description.
    2. Tailor the "Professional Summary" and "Experience" bullet points to subtly highlight the skills and keywords most relevant to the Job Target.
    3. STRICT RULE: You MUST preserve the exact Company Names, Job Titles, Employment Dates, Education, and Certifications. Do NOT omit or change them.
    4. STRICT RULE: Do NOT invent new experience, fake metrics, or hallucinate skills the candidate does not have. Only rephrase existing points to highlight relevant keywords.
    5. Keep the output clean, professional, and concise. Ensure ALL sections from the Base Resume (including Education and Certifications) are included in the final output.
    6. Convert the final tailored resume directly into clean HTML tags (e.g., <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>).
    7. Do NOT include <html>, <head>, <style>, or <body> tags. Output ONLY the inner HTML content to be injected.
    8. Do NOT wrap the output in ```html codeblocks. Return raw text.
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
                text = text.replace("```html", "").replace("```", "").strip()
                
                # Safely extract inner body if the AI hallucinated the full HTML wrapper
                body_match = re.search(r"<body[^>]*>(.*?)</body>", text, re.IGNORECASE | re.DOTALL)
                if body_match:
                    text = body_match.group(1)
                    
                return text.strip()
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    print(f"  ⚠️ Rate Limit hit on {model_name} (Key {key_idx + 1}). Switching...")
                    continue
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    print(f"  ⚠️ Model {model_name} not found. Switching...")
                    continue
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    print(f"  ⚠️ 503 Unavailable on {model_name} (Key {key_idx + 1}). Switching...")
                    continue
                else:
                    print(f"  ⚠️ API Error on {model_name} (Key {key_idx + 1}): {error_str}")
                    continue
                    
    raise Exception("Gemini API limits exhausted during tailoring across all available keys. Halting.")

def create_pdf_from_html(html_content, output_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        page.emulate_media(media="screen")
        page.wait_for_timeout(1000)  # Give the DOM 1 second to physically paint
        page.pdf(path=output_path, format="A4", print_background=True)
        browser.close()

def tailor_resumes(matched_path=MATCHED_PATH):
    missing = []
    if not os.path.exists(matched_path): missing.append(f"matched_jobs.json\n    Expected at: {matched_path}")
    if not os.path.exists(BASE_RESUME_PATH): missing.append(f"base_resume.md\n    Expected at: {BASE_RESUME_PATH}")
    if not os.path.exists(TEMPLATE_PATH): missing.append(f"cv-template.html\n    Expected at: {TEMPLATE_PATH}")
    
    if missing:
        print("❌ Missing required files:")
        for m in missing: print(f"  - {m}")
        return

    now = datetime.now()
    daily_output_dir = os.path.join(OUTPUT_DIR, now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
    os.makedirs(daily_output_dir, exist_ok=True)

    with open(matched_path, 'r') as f: jobs = json.load(f).get('approved_jobs', [])
    with open(BASE_RESUME_PATH, 'r') as f: base_resume = f.read()
    with open(TEMPLATE_PATH, 'r') as f: html_template = f.read()

    if "{{content}}" not in html_template:
        print(f"❌ FATAL: {TEMPLATE_PATH} is empty or missing the '{{content}}' placeholder tag!")
        return

    print(f"📄 Found {len(jobs)} approved jobs. Processing resumes...")
    
    for i, job in enumerate(jobs):
        company = job.get('company', 'Unknown')
        match_type = job.get('match_type', 'direct')
        score = job.get('ai_score', 0)
        
        if match_type == 'potential':
            print(f"\n  ℹ️ Potential match ({score}) for {company}. Using generic resume.")
            if os.path.exists(GENERIC_RESUME_PATH):
                job['tailored_resume_path'] = GENERIC_RESUME_PATH
            else:
                print(f"  ⚠️ Generic resume not found at {GENERIC_RESUME_PATH}!")
            continue

        if score < 80:
            print(f"\n  ⏭️ Skipping tailoring for {company}: Score ({score}) is below 80 and match_type is '{match_type}'.")
            continue
            
        safe_company = "".join(c if c.isalnum() else "_" for c in company).strip("_")
        pdf_path = os.path.join(daily_output_dir, f"Resume_{safe_company}.pdf")
        
        print(f"\n  ✍️  Tailoring for {company} (Direct Match, Score: {score})...")
        tailored_html = generate_tailored_html(job.get('title'), job.get('description'), base_resume)
        
        if tailored_html:
            print(f"    🔎 AI Output Preview: {tailored_html[:60].replace(chr(10), ' ')}...")
            full_html = html_template.replace("{{content}}", tailored_html)
            
            # Save a debug HTML file so we can see exactly what the AI generated
            html_debug_path = pdf_path.replace('.pdf', '.html')
            with open(html_debug_path, 'w') as f: f.write(full_html)
            
            create_pdf_from_html(full_html, pdf_path)
            print(f"  ✅ Saved Resume_{safe_company}.pdf")
            job['tailored_resume_path'] = pdf_path  # Save the path so auto_apply can find it later
            
        if i < len(jobs) - 1: time.sleep(15)  # Pace API requests to respect limits
            
    with open(matched_path, 'w') as f:
        json.dump({"approved_jobs": jobs}, f, indent=4)
    print(f"\n🎉 Resume processing complete!")

if __name__ == "__main__":
    tailor_resumes()