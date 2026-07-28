import os
import json
import time
from playwright.sync_api import sync_playwright
import sys

# Project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'linkedin_session.json')

def debug_linkedin(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        print(f"Navigating to: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        
        # Screenshot before click
        page.screenshot(path=os.path.join(BASE_DIR, 'logs', 'linkedin_pre_click.png'))
        
        # Try to find and click Easy Apply
        btn = page.locator("button:has-text('Easy Apply')").first
        if btn.count() > 0:
            print(f"Found Easy Apply. Visible: {btn.is_visible()}")
            btn.click()
            print("Clicked. Waiting for modal...")
            time.sleep(10)
            page.screenshot(path=os.path.join(BASE_DIR, 'logs', 'linkedin_post_click.png'))
            
            modal = page.locator(".artdeco-modal").first
            if modal.count() > 0 and modal.is_visible():
                print("✅ Modal is visible!")
            else:
                print("❌ Modal NOT visible.")
                with open(os.path.join(BASE_DIR, 'logs', 'linkedin_failed_dom.html'), 'w') as f:
                    f.write(page.content())
        else:
            print("❌ Easy Apply button not found.")
            with open(os.path.join(BASE_DIR, 'logs', 'linkedin_no_btn_dom.html'), 'w') as f:
                f.write(page.content())

        browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_linkedin(sys.argv[1])
    else:
        debug_linkedin("https://www.linkedin.com/jobs/view/4407307697/")
