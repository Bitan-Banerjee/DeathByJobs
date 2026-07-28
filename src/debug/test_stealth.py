import os
import json
import time
from playwright.sync_api import sync_playwright

# Check if playwright_stealth is available
try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
TARGET_URL = "https://www.naukri.com/job-listings-python-application-data-engineer-vichara-technologies-hyderabad-pune-delhi-ncr-5-to-10-years-290426017813"

def debug_stealth():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        if HAS_STEALTH:
            stealth_sync(page)
            print("🕵️ Stealth mode activated.")
        
        if os.path.exists(SESSION_FILE):
            print(f"🔑 Loading session: {SESSION_FILE}")
            with open(SESSION_FILE, 'r') as f:
                context.add_cookies(json.load(f))
        
        print(f"Navigating to: {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        time.sleep(10)

        apply_btn = page.locator("#apply-button, .apply-button").first
        if apply_btn.count() > 0:
            print("Clicking Apply with mouse...")
            apply_btn.scroll_into_view_if_needed()
            box = apply_btn.bounding_box()
            page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
            page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
            
            print("Waiting for drawer...")
            time.sleep(10)
            
            drawer = page.locator(".chatbot_DrawerContentWrapper").first
            if drawer.count() > 0 and drawer.is_visible():
                print("✅ Success! Drawer opened with stealth.")
            else:
                print("❌ Drawer still NOT visible.")
        
        browser.close()

if __name__ == "__main__":
    debug_stealth()
