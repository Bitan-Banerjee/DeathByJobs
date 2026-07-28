import os
import json
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')

def test_session_stealth():
    with sync_playwright() as p:
        # Using a more standard Chrome UA
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        if os.path.exists(SESSION_FILE):
            print(f"🔑 Loading cookies from {SESSION_FILE}")
            with open(SESSION_FILE, 'r') as f:
                cookies = json.load(f)
                context.add_cookies(cookies)
        
        page = context.new_page()
        
        # Add some random behavior before navigating
        print("🚀 Navigating to profile with stealth-ish UA...")
        page.goto("https://www.naukri.com/mnjuser/profile", wait_until="networkidle")
        time.sleep(5)
        
        print(f"📍 Final URL: {page.url}")
        
        if "login" in page.url.lower():
            print("❌ STILL EXPIRED or BLOCKED.")
        else:
            print("✅ LOGGED IN!")
            
        browser.close()

if __name__ == "__main__":
    test_session_stealth()
