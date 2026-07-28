import json
import csv
import os
from datetime import datetime

# Points to the root folder (two levels up from scripts/utils/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
OUTPUT_FILE = os.path.join(BASE_DIR, 'Job_Applications_Tracker.csv')
LAST_RUN_REPORT = os.path.join(BASE_DIR, 'data', 'last_run_report.json')

def _derive_platform(matched_path):
    basename = os.path.basename(matched_path).lower()
    if 'linkedin' in basename:
        return 'linkedin'
    if 'naukri' in basename:
        return 'naukri'
    return 'unknown'

def _count_from_jobs_json(platform):
    jobs_path = os.path.join(BASE_DIR, 'data', f'{platform}_jobs.json')
    if not os.path.exists(jobs_path):
        return 0
    try:
        with open(jobs_path, 'r') as f:
            d = json.load(f)
        if isinstance(d, list):
            return len(d)
        return len(d.get('jobs', []))
    except Exception:
        return 0

def _update_last_run_report(platform, approved_jobs):
    """Write a snapshot of the last run's metrics so the dashboard can show only that run."""
    applied = sum(1 for j in approved_jobs if j.get('status') == 'applied')
    skipped = sum(1 for j in approved_jobs if j.get('status') == 'skipped_low_score')
    failed = len(approved_jobs) - applied - skipped

    report = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'linkedin': {'scraped': 0, 'matched': 0, 'applied': 0, 'failed': 0},
        'naukri': {'scraped': 0, 'matched': 0, 'applied': 0, 'failed': 0},
    }

    if os.path.exists(LAST_RUN_REPORT):
        try:
            with open(LAST_RUN_REPORT, 'r') as f:
                existing = json.load(f)
            for key in ['linkedin', 'naukri']:
                if key in existing:
                    report[key] = existing[key]
        except Exception:
            pass

    report[platform] = {
        'scraped': _count_from_jobs_json(platform),
        'matched': len(approved_jobs),
        'applied': applied,
        'failed': failed,
    }

    os.makedirs(os.path.dirname(LAST_RUN_REPORT), exist_ok=True)
    with open(LAST_RUN_REPORT, 'w') as f:
        json.dump(report, f, indent=2)

def export_to_excel(matched_path=MATCHED_PATH):
    if not os.path.exists(matched_path):
        print(f"❌ Missing {matched_path}. No jobs to export.")
        return

    with open(matched_path, 'r') as f:
        data = json.load(f)
        approved_jobs = data.get('approved_jobs', [])

    # Snapshot last-run report before filtering (so matched/failed are accurate)
    platform = _derive_platform(matched_path)
    _update_last_run_report(platform, approved_jobs)

    # Only export jobs that were actually successfully applied
    jobs = [j for j in approved_jobs if j.get('status') == 'applied']

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
