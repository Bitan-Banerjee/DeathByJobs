import os
import json
import random
import time
import argparse
import sys
from dotenv import load_dotenv
import re
import urllib.parse
from playwright.sync_api import sync_playwright
from datetime import datetime

# Path setup
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

from utils.config_loader import load_profile, get_excluded_companies

EMAIL = os.getenv("LINKEDIN_EMAIL")
PASSWORD = os.getenv("LINKEDIN_PASSWORD")
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'linkedin_session.json')
JOBS_FILE = os.path.join(BASE_DIR, 'data', 'jobs.json')
SEEN_JOBS_FILE = os.path.join(BASE_DIR, 'data', 'seen_jobs.json')

_profile = load_profile()
_filters = _profile.get("filters", {})
_title_cfg = _filters.get("title", {})
_applicants_cfg = _filters.get("applicants", {})

def is_title_relevant(title, profile=None):
    if profile is None:
        profile = _profile
    filters = profile.get("filters", {})
    title_cfg = filters.get("title", {})
    title_lower = title.lower()

    red_flags = title_cfg.get("red_flags", _title_cfg.get("red_flags", []))
    for flag in red_flags:
        if flag.lower() in title_lower.split() or re.search(r'\b' + re.escape(flag.lower()) + r'\b', title_lower):
            return False

    green_flags = title_cfg.get("green_flags", _title_cfg.get("green_flags", []))
    if any(flag.lower() in title_lower for flag in green_flags):
        return True

    return False

def human_delay(min_sec=1.5, max_sec=4.5):
    time.sleep(random.uniform(min_sec, max_sec))

def safe_goto(page, url, timeout=60000):
    """Attempt to go to a URL with a longer timeout and a single retry."""
    try:
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
    except Exception as e:
        print(f"  ⚠️ Timeout on {url}. Retrying once...")
        time.sleep(5)
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")

def dismiss_login_popup(page):
    try:
        page.keyboard.press("Escape")
        dismiss_btn = page.query_selector("button[aria-label='Dismiss']")
        if dismiss_btn: dismiss_btn.click(timeout=1000)
    except: pass

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}

def slow_scroll(page, scrolls=10):
    try:
        page.wait_for_selector(".jobs-search-results-list", timeout=5000)
    except:
        pass
        
    for i in range(scrolls):
        dismiss_login_popup(page)
        page.evaluate("""() => {
            const container = document.querySelector('.jobs-search-results-list') || document.documentElement;
            if (container) container.scrollBy(0, 800);
            
            const cards = document.querySelectorAll('.job-card-container');
            if (cards.length > 0) cards[cards.length - 1].scrollIntoView();
        }""")
        time.sleep(random.uniform(1.5, 2.5))

def scrape_linkedin_jobs(keyword, location, max_pages, max_jobs, output_file=JOBS_FILE):
    seen_jobs = load_seen_jobs()

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900}, # Force desktop layout
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        # Set a global default timeout of 60s instead of 30s
        page.set_default_timeout(60000)

        print("🌐 Opening LinkedIn...")
        safe_goto(page, "https://www.linkedin.com/login")
        
        if page.query_selector("#username"):
            print("🔐 Session expired. Logging in...")
            page.fill("#username", EMAIL)
            page.fill("#password", PASSWORD)
            page.click('[type="submit"]')
            page.wait_for_timeout(5000)
            with open(SESSION_FILE, "w") as f:
                json.dump(context.cookies(), f)

        all_jobs = []
        for page_num in range(max_pages):
            if len(all_jobs) >= max_jobs: break
            
            start = page_num * 25
            encoded_keyword = urllib.parse.quote(f'"{keyword}"')
            url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_keyword}&location={location}&f_AL=true&f_TPR=r259200&sortBy=DD&start={start}"
            print(f"📄 Scraping Page {page_num + 1}...")
            
            safe_goto(page, url)
            human_delay(3, 5)
            slow_scroll(page)
            
            # --- BROWSER LEVEL FILTERING ---
            excluded_companies = get_excluded_companies(_profile)
            browser_filters = ["Senior", "Lead", "Manager", "Director", "VP", "Principal"]
            filters_json = json.dumps(browser_filters)
            excluded_json = json.dumps(excluded_companies)
            print("🪄 Applying browser-level filters (DOM removal)...")
            script = """
            () => {
                const filters = %s;
                const excludedCompanies = %s;
                const selectors = [".job-card-container", ".jobs-search-results-list__item", ".base-card", ".base-search-card", ".jobs-search-results__list-item"];

                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(card => {
                        const text = card.innerText;
                        const hasFlag = filters.some(f => {
                            const regex = new RegExp('\\b' + f + '\\b', 'i');
                            return regex.test(text);
                        });

                        const isExcludedCompany = excludedCompanies.some(c => {
                            const regex = new RegExp('\\b' + c + '\\b', 'i');
                            return regex.test(text);
                        });

                        if (hasFlag || isExcludedCompany || text.includes('Applied') || text.includes('Applied ')) {
                            card.remove();
                        }
                    });
                });
            }
            """ % (filters_json, excluded_json)
            page.evaluate(script)
            # -------------------------------

            cards = page.locator(".job-card-container")
            card_count = cards.count()
            print(f"    🔍 Found {card_count} job cards on this page.")
            
            if card_count == 0:
                print("  ⚠️ No more jobs found. Stopping pagination.")
                break
            
            for i in range(card_count):
                if len(all_jobs) >= max_jobs: break
                try:
                    card = cards.nth(i)
                    
                    title_el = card.locator(".job-card-list__title--link").first
                    if not title_el.is_visible(): continue
                    title = title_el.inner_text().split('\n')[0].strip()
                    
                    if not is_title_relevant(title):
                        print(f"  ⏭️ Skipped (Irrelevant Title): {title}")
                        continue
                        
                    subtitle = card.locator(".artdeco-entity-lockup__subtitle").first
                    company = subtitle.inner_text().split('\n')[0].strip() if subtitle.is_visible() else "Unknown"
                    
                    excluded_companies = get_excluded_companies(_profile)
                    if any(excluded.lower() == company.lower() for excluded in excluded_companies):
                        print(f"  ⏭️ Skipped (Excluded Company): {company}")
                        continue
                    
                    href = title_el.get_attribute("href")
                    if not href: continue
                    job_url = "https://www.linkedin.com" + href.split("?")[0]

                    if job_url in seen_jobs:
                        print(f"  ⏭️ Skipped: Already seen {title} at {company}")
                        continue
                    
                    card.scroll_into_view_if_needed()
                    card.click()
                    human_delay(2, 4)
                    
                    # Wait specifically for the description to appear
                    desc_locator = page.locator(".jobs-description")
                    desc_locator.wait_for(timeout=10000)
                    description = desc_locator.inner_text().strip()
                    
                    # Extract applicant count safely
                    applicants = "Unknown"
                    try:
                        app_locator = page.get_by_text(re.compile(r'(?:over\s+)?[\d,]+\s*applicants?', re.IGNORECASE)).first
                        if app_locator.is_visible(timeout=2000):
                            applicants = app_locator.inner_text().strip()
                    except: pass
                    
                    # Drop job if > configured max applicants
                    max_applicants = _applicants_cfg.get("max", 100)
                    skip_job = False
                    if applicants != "Unknown":
                        if "over 100" in applicants.lower():
                            skip_job = True
                        else:
                            num_match = re.search(r'\d+', applicants.replace(',', ''))
                            if num_match and int(num_match.group()) > max_applicants:
                                skip_job = True
                    if skip_job:
                        print(f"  ⏭️ Skipped: Too many applicants ({applicants}, max {max_applicants})")
                        continue

                    all_jobs.append({
                        "title": title, 
                        "company": company, 
                        "url": job_url, 
                        "applicants": applicants,
                        "description": description[:1200]
                    })
                    
                    seen_jobs[job_url] = {"title": title, "company": company, "seen_at": datetime.now().isoformat()}
                    print(f"  ✅ Scraped: {title} at {company}")
                except Exception as e:
                    error_msg = str(e).split('\n')[0]
                    print(f"  ⚠️ Error scraping card {i}: {error_msg}")
                    continue

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            json.dump({"jobs": all_jobs}, f, indent=2)
        with open(SEEN_JOBS_FILE, "w") as f:
            json.dump(seen_jobs, f, indent=2)
        browser.close()
        print(f"💾 Done! Scraped {len(all_jobs)} jobs.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape LinkedIn job postings.")
    parser.add_argument("--pages", type=int, default=1, help="Number of search result pages to scrape.")
    parser.add_argument("--max", type=int, default=10, help="Maximum number of jobs to scrape in total.")
    parser.add_argument("--keyword", type=str, default=None, help="Override search keyword.")
    parser.add_argument("--location", type=str, default=None, help="Override search location.")
    args = parser.parse_args()

    keyword, naukri_keyword, location = load_profile().get("search", {}).values()
    keyword = args.keyword or keyword
    location = args.location or location

    scrape_linkedin_jobs(keyword=keyword, location=location, max_pages=args.pages, max_jobs=args.max)
