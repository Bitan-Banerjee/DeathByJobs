import os
import csv
import json

def get_already_applied_urls():
    """Load all URLs from tracker CSV and seen_jobs JSONs."""
    applied_urls = set()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 1. Tracker CSV
    tracker_path = os.path.join(base_dir, 'Job_Applications_Tracker.csv')
    if os.path.exists(tracker_path):
        try:
            with open(tracker_path, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None) # Skip header
                for row in reader:
                    if len(row) > 3: # URL is usually index 3
                        applied_urls.add(row[3].strip())
        except Exception as e:
            print(f"Error reading tracker: {e}")

    # 2. Seen Jobs JSONs
    seen_files = [
        os.path.join(base_dir, 'data', 'seen_jobs.json'),
        os.path.join(base_dir, 'data', 'naukri_seen_jobs.json')
    ]
    for sf in seen_files:
        if os.path.exists(sf):
            try:
                with open(sf, 'r') as f:
                    data = json.load(f)
                    # Handle both dict {url: timestamp} and list of URLs
                    if isinstance(data, dict):
                        applied_urls.update(data.keys())
                    elif isinstance(data, list):
                        applied_urls.update(data)
            except Exception as e:
                print(f"Error reading {sf}: {e}")

    return applied_urls

if __name__ == "__main__":
    urls = get_already_applied_urls()
    print(f"Found {len(urls)} already applied/seen URLs.")
    # Show first 5 for verification
    for u in list(urls)[:5]:
        print(f"  - {u}")
