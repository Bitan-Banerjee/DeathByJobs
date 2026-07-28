import os
import json
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAUKRI_SESSION = os.path.join(BASE_DIR, 'data', 'naukri_session.json')

def test_browser_filter():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        if os.path.exists(NAUKRI_SESSION):
            with open(NAUKRI_SESSION, "r") as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        print("🌐 Opening Naukri search...")
        page.goto("https://www.naukri.com/data-engineer-jobs-in-india?jobAge=30", wait_until="domcontentloaded")
        time.sleep(5) # Wait for cards
        
        # Count before
        before_count = page.locator(".srp-jobtuple-wrapper").count()
        applied_before = page.locator(".srp-jobtuple-wrapper:has-text('Applied')").count()
        print(f"📊 Before Filter: {before_count} total cards, {applied_before} marked 'Applied'.")
        
        page.screenshot(path="logs/debug_filter_before.png")

        print("🪄 Injecting physical filter (JS)...")
        page.evaluate("""() => {
            const cards = document.querySelectorAll('.srp-jobtuple-wrapper');
            let hidden = 0;
            cards.forEach(card => {
                // Naukri specific: "Applied" text or status
                if (card.innerText.includes('Applied')) {
                    card.style.border = '5px solid red'; // Visual debug
                    card.style.opacity = '0.3';
                    // card.remove(); // This would be the physical removal
                    hidden++;
                }
            });
            console.log('Hidden ' + hidden + ' cards');
        }""")
        
        time.sleep(2)
        page.screenshot(path="logs/debug_filter_after.png")
        
        # Physical removal test
        print("🗑️ Physically removing 'Applied' cards...")
        page.evaluate("""() => {
            document.querySelectorAll('.srp-jobtuple-wrapper').forEach(card => {
                if (card.innerText.includes('Applied')) card.remove();
            });
        }""")
        
        after_count = page.locator(".srp-jobtuple-wrapper").count()
        print(f"📊 After Physical Filter: {after_count} total cards.")
        
        browser.close()

if __name__ == "__main__":
    if not os.path.exists("logs"): os.makedirs("logs")
    test_browser_filter()
