import os
import json
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
LOGS_DIR = os.path.join(BASE_DIR, 'logs', 'debug_loop')

def run_browser_filter_test():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)

    with sync_playwright() as p:
        print("🚀 Launching browser for filtering test...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        
        # Test URL with Data Engineer jobs
        url = "https://www.naukri.com/data-engineer-jobs-in-india?jobAge=30"
        print(f"🌐 Navigating to: {url}")
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(5) # Wait for cards to load fully
        
        # 1. Initial State
        initial_cards = page.locator(".srp-jobtuple-wrapper")
        initial_count = initial_cards.count()
        print(f"📊 Initial job cards found: {initial_count}")
        if initial_count > 0:
            print(f"DEBUG: First card text snippet: {initial_cards.first.inner_text()[:200]}...")
        page.screenshot(path=os.path.join(LOGS_DIR, "filter_1_initial.png"))

        # 2. Identify filters
        filters = ["Applied", "Walk-in", "Sponsored", "Premium", "Lead", "Manager", "Director"]
        
        print(f"🪄 Applying browser-level filters: {filters}")
        
        # We use page.evaluate to perform surgical DOM removal which is faster and cleaner
        results = page.evaluate("""(filterList) => {
            const cards = document.querySelectorAll('.srp-jobtuple-wrapper');
            let stats = {
                total: cards.length,
                removed: 0,
                removed_titles: [],
                details: {}
            };
            
            filterList.forEach(f => stats.details[f] = 0);
            
            cards.forEach(card => {
                const titleEl = card.querySelector('a.title');
                if (!titleEl) return;
                
                const title = titleEl.innerText;
                const text = card.innerText;
                let shouldRemove = false;
                let reason = "";
                
                for (const f of filterList) {
                    // Title check is more precise for Lead/Manager
                    if (title.includes(f) || text.includes(f)) {
                        shouldRemove = true;
                        reason = f;
                        break;
                    }
                }
                
                if (shouldRemove) {
                    card.style.border = "2px solid red";
                    card.style.backgroundColor = "rgba(255, 0, 0, 0.1)";
                    card.setAttribute('data-filter-reason', reason);
                    stats.removed++;
                    stats.removed_titles.push(`${title} (${reason})`);
                    stats.details[reason]++;
                }
            });
            return stats;
        }""", filters)
        
        print(f"✅ Filter identification complete:")
        print(json.dumps(results, indent=2))
        
        page.screenshot(path=os.path.join(LOGS_DIR, "filter_2_identified.png"))
        
        # 3. Physical Removal
        print("🗑️ Physically removing identified cards from DOM...")
        final_count = page.evaluate("""() => {
            document.querySelectorAll('.srp-jobtuple-wrapper[data-filter-reason]').forEach(el => el.remove());
            return document.querySelectorAll('.srp-jobtuple-wrapper').length;
        }""")
        
        print(f"📊 Final job cards remaining: {final_count}")
        page.screenshot(path=os.path.join(LOGS_DIR, "filter_3_final.png"))
        
        if initial_count > final_count:
            print(f"✨ SUCCESS: Successfully filtered out {initial_count - final_count} jobs at the browser level.")
        else:
            print("ℹ️ No jobs matched the filter criteria in this view.")
            
        browser.close()

if __name__ == "__main__":
    run_browser_filter_test()
