import os
import json
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')

def save_session():
    with sync_playwright() as p:
        # Launch non-headless so user can log in
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("🚀 Opening Naukri Login...")
        page.goto("https://www.naukri.com/nlogin/login")
        
        print("⏳ PLEASE LOG IN MANUALLY IN THE BROWSER WINDOW.")
        print("Once you see your profile or dashboard, come back here and press ENTER.")
        
        input("Press Enter after you have logged in...")
        
        # Save cookies
        cookies = context.cookies()
        with open(SESSION_FILE, 'w') as f:
            json.dump(cookies, f, indent=4)
        
        print(f"✅ Session saved to {SESSION_FILE}")
        browser.close()

if __name__ == "__main__":
    save_session()
