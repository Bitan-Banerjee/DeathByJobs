import os
import json
import time
import random
import re
import argparse
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright

# Path setup
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

# Add auth helper
try:
    from utils.auth_helper import ensure_naukri_session
except ImportError:
    def ensure_naukri_session(page, context): return True

try:
    from automation.linkedin_scraper import is_title_relevant, human_delay, safe_goto
except ImportError:
    pass

from utils.config_loader import load_profile, get_excluded_companies

JOBS_FILE = os.path.join(BASE_DIR, 'data', 'jobs.json')
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
SEEN_JOBS_FILE = os.path.join(BASE_DIR, 'data', 'naukri_seen_jobs.json')
COMPANY_BEHAVIOR_FILE = os.path.join(BASE_DIR, 'data', 'naukri_company_behavior.json')
STATE_FILE = os.path.join(BASE_DIR, 'data', 'naukri_state.json')

_profile = load_profile()
_excluded_companies = get_excluded_companies(_profile)

def scrape_naukri_jobs(keyword="Data Engineer", location="India", max_jobs=25, output_file=JOBS_FILE):
    # Load memory to prevent duplicates
    seen_jobs = {}
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            seen_jobs = json.load(f)

    company_behavior = {}

    if os.path.exists(COMPANY_BEHAVIOR_FILE):
        with open(COMPANY_BEHAVIOR_FILE, "r") as f:
            company_behavior = json.load(f)
    
    # Load last page state
    state = {"last_page": 0}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        except: pass
    
    start_page = state.get("last_page", 0) + 1
    print(f"🌐 Booting up Naukri Scraper for '{keyword}' (Resuming from Page {start_page})...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                context.add_cookies(json.load(f))
                
        page = context.new_page()
        page.set_default_timeout(60000)
        
        # --- SESSION VALIDATION ---
        if not ensure_naukri_session(page, context):
            print("🛑 Could not establish valid Naukri session. Scraping will continue but may fail to extract descriptions.")
        # --------------------------

        formatted_keyword = keyword.lower().replace(' ', '-')
        formatted_location = location.lower().replace(' ', '-')
        all_jobs = []
        max_pages_to_scrape = (max_jobs // 20) + 2
        
        last_successful_page = state.get("last_page", 0)
        
        for page_num in range(start_page, start_page + max_pages_to_scrape):
            if len(all_jobs) >= max_jobs: break
            
            # Build URL: e.g., https://www.naukri.com/data-engineer-jobs-in-india-2?jobAge=3&sort=r
            page_suffix = f"-{page_num}" if page_num > 1 else ""
            url = f"https://www.naukri.com/{formatted_keyword}-jobs-in-{formatted_location}{page_suffix}?jobAge=3&sort=r"
            
            print(f"📄 Scraping Naukri Page {page_num}...")
            safe_goto(page, url)
            human_delay(3, 5)
            
            # --- BROWSER LEVEL FILTERING ---
            browser_filters = ["Applied", "Walk-in", "Sponsored", "Premium", "Lead", "Manager", "Director"]
            filters_json = json.dumps(browser_filters)
            excluded_json = json.dumps(_excluded_companies)
            print("🪄 Applying browser-level filters (DOM removal)...")
            script = """
            () => {
                const filters = %s;
                const excludedCompanies = %s;
                const cards = document.querySelectorAll('.srp-jobtuple-wrapper');
                cards.forEach(card => {
                    const text = card.innerText;
                    const hasFlag = filters.some(f => text.includes(f));
                    const isExcluded = excludedCompanies.some(c => {
                        const regex = new RegExp('\\b' + c + '\\b', 'i');
                        return regex.test(text);
                    });
                    if (hasFlag || isExcluded) {
                        card.remove();
                    }
                });
            }
            """ % (filters_json, excluded_json)
            page.evaluate(script)
            # -------------------------------

            cards = page.locator(".srp-jobtuple-wrapper")
            card_count = cards.count()
            print(f"    🔍 Found {card_count} job cards on this page.")
            
            if card_count == 0:
                print("  ⚠️ No more jobs found. Resetting page state for next run.")
                last_successful_page = 0 
                break
            
            last_successful_page = page_num
                
            # Step 1: Extract URLs to avoid stale elements
            job_links = []
            for i in range(card_count):
                card = cards.nth(i)
                title_el = card.locator("a.title").first
                if not title_el.is_visible(): continue
                
                title = title_el.inner_text().strip()
                if not is_title_relevant(title):
                    print(f"  ⏭️ Skipped (Irrelevant Title): {title}")
                    continue
                    
                company_el = card.locator("a.comp-name").first
                company = company_el.inner_text().strip() if company_el.is_visible() else "Unknown"

                if any(excluded.lower() == company.lower() for excluded in _excluded_companies):
                    print(f"  ⏭️ Skipped (Excluded Company): {company}")
                    continue

                # Check Company Behavior Matrix to skip known external-only spammers
                # Only skip if internal_apply count is 0 and external_apply count is significantly high (e.g., >= 5)
                stats = company_behavior.get(company, {"internal": 0, "external": 0})
                if stats["internal"] == 0 and stats["external"] >= 5:
                    print(f"  ⏭️ Skipped: '{company}' strictly uses external portals.")
                    continue
                
                href = title_el.get_attribute("href")
                if not href: continue
                
                job_url = href.split("?")[0]
                if job_url in seen_jobs:
                    print(f"  ⏭️ Skipped: Already seen {title} at {company}")
                    continue
                    
                job_links.append({"title": title, "company": company, "url": job_url})
                
            # Step 2: Visit each URL to grab the description
            for job_info in job_links:
                if len(all_jobs) >= max_jobs: break
                try:
                    safe_goto(page, job_info['url'])
                    human_delay(2, 3)
                    
                    company_name = job_info['company']
                    if company_name not in company_behavior:
                        company_behavior[company_name] = {"internal": 0, "external": 0}
                    
                    # Broad wildcard locator to catch standard and premium company pages
                    desc_locator = page.locator(".job-desc, .dang-inner-html, div[class*='job-desc'], section[class*='job-desc']").first
                    desc_locator.wait_for(timeout=5000)
                    
                    # Filter out jobs that have already been applied to
                    if page.locator("text='Already Applied', button:has-text('Already Applied'), button:has-text('Applied')").is_visible():
                        print(f"  ⏭️ Skipped: Already applied to {job_info['title']}")
                        continue

                    # Filter out jobs that redirect to external company portals and update behavior matrix
                    apply_btn = page.locator("button:has-text('Apply'), a:has-text('Apply')").first
                    if apply_btn.is_visible(timeout=2000):
                        btn_text = apply_btn.inner_text().lower()
                        if "company site" in btn_text or "employer site" in btn_text:
                            company_behavior[company_name]["external"] += 1
                            print(f"  ⏭️ Skipped: External application portal for {job_info['title']}")
                            continue
                        else:
                            company_behavior[company_name]["internal"] += 1
                            
                    description = desc_locator.inner_text().strip()
                    
                    all_jobs.append({
                        "title": job_info['title'], "company": job_info['company'], 
                        "url": job_info['url'], "applicants": "Unknown", "description": description[:1200]
                    })
                    
                    seen_jobs[job_info['url']] = {"title": job_info['title'], "company": job_info['company'], "seen_at": datetime.now().isoformat()}
                    print(f"  ✅ Scraped: {job_info['title']} at {job_info['company']}")
                except Exception as e:
                    error_msg = str(e).split('\n')[0]
                    print(f"  ⚠️ Failed to extract description for {job_info['title']}. Reason: {error_msg}")
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            json.dump({"jobs": all_jobs}, f, indent=2)
        with open(SEEN_JOBS_FILE, "w") as f:
            json.dump(seen_jobs, f, indent=2)
        with open(COMPANY_BEHAVIOR_FILE, "w") as f:
            json.dump(company_behavior, f, indent=2)
            
        # Update page state for next loop
        with open(STATE_FILE, "w") as f:
            json.dump({"last_page": last_successful_page, "last_run": datetime.now().isoformat()}, f)
            
        browser.close()
        print(f"💾 Done! Scraped {len(all_jobs)} jobs from Naukri (Current Page: {last_successful_page}).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Naukri job postings.")
    parser.add_argument("--max", type=int, default=10, help="Maximum number of jobs to scrape.")
    parser.add_argument("--keyword", type=str, default=None, help="Override search keyword.")
    parser.add_argument("--location", type=str, default=None, help="Override search location.")
    args = parser.parse_args()

    search_cfg = load_profile().get("search", {})
    keyword = args.keyword or search_cfg.get("naukri_keyword", "Data Engineer")
    location = args.location or search_cfg.get("location", "India")

    scrape_naukri_jobs(keyword=keyword, location=location, max_jobs=args.max)