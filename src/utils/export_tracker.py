import json
import csv
import os
from datetime import datetime

# Points to the root folder (two levels up from scripts/utils/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
OUTPUT_FILE = os.path.join(BASE_DIR, 'Job_Applications_Tracker.csv')

def export_to_excel(matched_path=MATCHED_PATH):
    if not os.path.exists(matched_path):
        print(f"❌ Missing {matched_path}. No jobs to export.")
        return
        
    with open(matched_path, 'r') as f:
        data = json.load(f)
        jobs = data.get('approved_jobs', [])
        
    # Only export jobs that were actually successfully applied
    jobs = [j for j in jobs if j.get('status') == 'applied']
        
    if not jobs:
        print("  ⚠️ No approved jobs found for today. Skipping export.")
        return

    file_exists = os.path.isfile(OUTPUT_FILE)
    date_str = datetime.now().strftime("%Y-%m-%d")

    with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write headers if this is the very first time running it
        if not file_exists:
            writer.writerow(["Date Applied", "Company", "Job Title", "Job URL", "Status", "AI Score", "Resume File"])
            
        for job in jobs:
            writer.writerow([
                date_str,
                job.get('company', 'Unknown'),
                job.get('title', 'Unknown'),
                job.get('url', 'Unknown'),
                "Applied via AI",
                job.get('ai_score', 'N/A'),
                job.get('tailored_resume_path', 'N/A')
            ])

if __name__ == "__main__":
    export_to_excel()