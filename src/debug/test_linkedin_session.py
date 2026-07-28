import os
import json
import time
from playwright.sync_api import sync_playwright

# Project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'linkedin_session.json')

def test_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        print(f"Navigating to LinkedIn feed...")
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        
        final_url = page.url
        print(f"📍 Final URL: {final_url}")
        
        if "login" in final_url or "checkpoint" in final_url:
            print("❌ LinkedIn Session EXPIRED or BLOCKED.")
        else:
            print("✅ LinkedIn Session is ACTIVE!")

        browser.close()

if __name__ == "__main__":
    test_session()
