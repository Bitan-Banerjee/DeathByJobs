import os
import json
import time
import urllib.parse
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'linkedin_session.json')
LOGS_DIR = os.path.join(BASE_DIR, 'logs', 'debug_loop')

def run_linkedin_filter_test():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)

    with sync_playwright() as p:
        print("🚀 Launching browser for LinkedIn filtering test...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        
        # Simple URL to ensure results
        url = "https://www.linkedin.com/jobs/search/?keywords=Data%20Engineer"
        
        print(f"🌐 Navigating to: {url}")
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(8) 
        
        # 1. Initial State
        card_selectors = [".job-card-container", ".jobs-search-results-list__item", ".base-card", ".base-search-card", ".jobs-search-results__list-item"]
        initial_count = 0
        active_selector = ".job-card-container" # Default
        
        for selector in card_selectors:
            count = page.locator(selector).count()
            if count > 0:
                initial_count = count
                active_selector = selector
                break
                
        print(f"📊 Initial job cards found: {initial_count} using selector '{active_selector}'")
        if initial_count == 0:
            print("DEBUG: No cards found. Page title:", page.title())
            page.screenshot(path=os.path.join(LOGS_DIR, "li_error_no_cards.png"))
        
        page.screenshot(path=os.path.join(LOGS_DIR, "li_filter_1_initial.png"))

        # 2. Identify filters
        filters = ["Senior", "Lead", "Manager", "Director", "VP", "Principal"]
        print(f"🪄 Applying LinkedIn browser-level filters: {filters}")
        
        results = page.evaluate("""(args) => {
            const filterList = args.filters;
            const selector = args.selector;
            const cards = document.querySelectorAll(selector);
            let stats = {
                total: cards.length,
                removed: 0,
                removed_titles: [],
                details: {}
            };
            
            filterList.forEach(f => stats.details[f] = 0);
            stats.details["Applied"] = 0;
            
            cards.forEach(card => {
                const titleEl = card.querySelector('.job-card-list__title, .base-card__full-link, h3');
                if (!titleEl) return;
                
                const title = titleEl.innerText;
                const text = card.innerText;
                let shouldRemove = false;
                let reason = "";
                
                for (const f of filterList) {
                    const regex = new RegExp('\\\\b' + f + '\\\\b', 'i');
                    if (regex.test(title)) {
                        shouldRemove = true;
                        reason = f;
                        break;
                    }
                }
                
                if (text.includes('Applied') || text.includes('Applied ')) {
                    shouldRemove = true;
                    reason = "Applied";
                }
                
                if (shouldRemove) {
                    card.style.border = "3px solid orange";
                    card.style.opacity = "0.5";
                    card.setAttribute('data-filter-reason', reason);
                    stats.removed++;
                    stats.removed_titles.push(`${title.split('\\n')[0].trim()} (${reason})`);
                    if (stats.details[reason] !== undefined) stats.details[reason]++;
                }
            });
            return stats;
        }""", {"filters": filters, "selector": active_selector})
        
        print(f"✅ Filter identification complete:")
        print(json.dumps(results, indent=2))
        
        page.screenshot(path=os.path.join(LOGS_DIR, "li_filter_2_identified.png"))
        
        # 3. Physical Removal
        print(f"🗑️ Removing filtered cards using selector {active_selector}...")
        final_count = page.evaluate(f"""(sel) => {{
            document.querySelectorAll(sel + '[data-filter-reason]').forEach(el => el.remove());
            return document.querySelectorAll(sel).length;
        }}""", active_selector)
        
        print(f"📊 Final LinkedIn job cards remaining: {final_count}")
        page.screenshot(path=os.path.join(LOGS_DIR, "li_filter_3_final.png"))
        
        browser.close()

if __name__ == "__main__":
    run_linkedin_filter_test()
