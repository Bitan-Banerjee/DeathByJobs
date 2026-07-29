import os
import json
import re
import argparse
import sys

# Add path for internal imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, SRC_DIR)

from linkedin_auto_apply import linkedin_apply as auto_apply
from naukri_auto_apply import naukri_apply
from utils.export_tracker import export_to_excel

BASE_DIR = os.path.dirname(SRC_DIR)
FAILED_PATH = os.path.join(BASE_DIR, 'data', 'failed_applications.json')
MAX_RETRIES = 999 

def load_safe_json(path):
    """Read JSON safely."""
    if not os.path.exists(path): return {}
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    try:
        # First attempt: simple json.loads
        return json.loads(content, strict=False)
    except Exception:
        try:
            # Second attempt: strip comments
            clean_content = re.sub(r'(?<!:)//.*', '', content)
            return json.loads(clean_content, strict=False)
        except:
            # Third attempt: strip markdown code fences if Gemini returned them
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
                return json.loads(content, strict=False)
            return None

def retry_failed_jobs(linkedin_only=False, naukri_only=False):
    if not os.path.exists(FAILED_PATH):
        print("✅ No failed applications found.")
        return

    data = load_safe_json(FAILED_PATH)
    if not data: return
    
    failed_jobs = data.get('failed_jobs', [])
    if not failed_jobs:
        print("✅ Failed applications list is empty.")
        return

    linkedin_jobs = [j for j in failed_jobs if 'linkedin.com' in j.get('url', '')]
    naukri_jobs = [j for j in failed_jobs if 'naukri.com' in j.get('url', '')]

    # Filter based on flags
    if linkedin_only:
        print("🎯 Platform filter: LinkedIn Only")
        naukri_jobs = []
    elif naukri_only:
        print("🎯 Platform filter: Naukri Only")
        linkedin_jobs = []

    if not linkedin_jobs and not naukri_jobs:
        print("✅ No jobs to retry based on current filters.")
        return

    print(f"🔄 Retrying {len(linkedin_jobs)} LinkedIn and {len(naukri_jobs)} Naukri jobs.")
    
    # We will reconstruct the failed list after processing
    # Start with the jobs we are NOT retrying this time
    still_failed = [j for j in failed_jobs if j not in linkedin_jobs and j not in naukri_jobs]

    if linkedin_jobs:
        temp_path = os.path.join(BASE_DIR, 'data', 'linkedin_matched_jobs.json')
        with open(temp_path, 'w') as f: json.dump({"approved_jobs": linkedin_jobs}, f, indent=4)
        print("\n🚀 Retrying LinkedIn Jobs...")
        auto_apply(matched_path=temp_path)
        export_to_excel(matched_path=temp_path)
        
        try:
            with open(temp_path, 'r') as f: processed = json.load(f).get("approved_jobs", [])
            for j in processed:
                status = j.get('status')
                if status not in ['applied', 'skipped_low_score', 'expired']:
                    j['retry_count'] = j.get('retry_count', 0) + 1
                    still_failed.append(j)
                elif status == 'expired':
                    print(f"  🗑️ Removed expired LinkedIn job: {j.get('company')}")
            if os.path.exists(temp_path): os.remove(temp_path)
        except Exception: pass
        
    if naukri_jobs:
        temp_path = os.path.join(BASE_DIR, 'data', 'naukri_matched_jobs.json')
        with open(temp_path, 'w') as f: json.dump({"approved_jobs": naukri_jobs}, f, indent=4)
        print("\n🚀 Retrying Naukri Jobs...")
        naukri_apply(matched_path=temp_path)
        export_to_excel(matched_path=temp_path)
        
        try:
            with open(temp_path, 'r') as f: processed = json.load(f).get("approved_jobs", [])
            for j in processed:
                status = j.get('status')
                if status not in ['applied', 'skipped_low_score', 'expired']:
                    j['retry_count'] = j.get('retry_count', 0) + 1
                    still_failed.append(j)
                elif status == 'expired':
                    print(f"  🗑️ Removed expired Naukri job: {j.get('company')}")
            if os.path.exists(temp_path): os.remove(temp_path)
        except Exception: pass
        
    # Final check: Update failed_applications.json
    with open(FAILED_PATH, 'w') as f: json.dump({"failed_jobs": still_failed}, f, indent=4)
    
    recovered = len(failed_jobs) - len(still_failed)
    print(f"\n🎉 Retry complete! Recovered/Cleaned {recovered} applications. {len(still_failed)} still in failed list.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retry failed job applications.")
    parser.add_argument("--linkedin-only", action="store_true", help="Retry only LinkedIn jobs.")
    parser.add_argument("--naukri-only", action="store_true", help="Retry only Naukri jobs.")
    args = parser.parse_args()
    
    retry_failed_jobs(linkedin_only=args.linkedin_only, 
                      naukri_only=args.naukri_only)
