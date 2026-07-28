import os
import json
import time
from playwright.sync_api import sync_playwright

import sys

# Correct project root (AiAutomation/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')

# Get URL from argument or fallback to default
if len(sys.argv) > 1:
    TARGET_URL = sys.argv[1]
else:
    TARGET_URL = "https://www.naukri.com/job-listings-data-engineer-lance-labs-noida-5-to-8-years-300426023693"

def debug_apply():
    # Ensure logs directory exists
    logs_dir = os.path.join(BASE_DIR, 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f:
                context.add_cookies(json.load(f))
        
        page = context.new_page()
        print(f"Navigating to: {TARGET_URL}")
        try:
            # Using domcontentloaded as networkidle often timeouts on Naukri
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(10) # Heavy page, wait for scripts

            # 1. Capture state before click
            pre_click_ss = os.path.join(logs_dir, "debug_pre_click.png")
            page.screenshot(path=pre_click_ss)
            print(f"Captured pre-click screenshot: {pre_click_ss}")
            
            # 2. Find and click apply
            # Improved selector list
            apply_selectors = [
                "button:has-text('Apply')",
                ".applyBtn",
                ".apply-button",
                "#apply-button",
                "[class*='apply' i] button",
                "button.apply"
            ]
            
            apply_btn = None
            for sel in apply_selectors:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    apply_btn = loc
                    break
            
            if apply_btn:
                print(f"Apply button found with selector. Text: {apply_btn.inner_text()}")
                print("Clicking...")
                apply_btn.click(force=True)
                print("Click dispatched. Waiting 10s for drawer...")
                time.sleep(10) 
                
                # 3. Capture state after click
                post_click_ss = os.path.join(logs_dir, "debug_post_click.png")
                page.screenshot(path=post_click_ss)
                print(f"Captured post-click screenshot: {post_click_ss}")
                
                dom_path = os.path.join(logs_dir, "debug_naukri_full_dom.html")
                with open(dom_path, "w") as f:
                    f.write(page.content())
                print(f"Dumped DOM to: {dom_path}")
                
                # Check for drawer
                drawer_selectors = [".chatbot_DrawerContentWrapper", ".chatbot_Drawer", ".chatbot_MessageContainer", "[role='dialog']", ".chatbot_MessageContainer"]
                found_drawer = False
                for d_sel in drawer_selectors:
                    drawer = page.locator(d_sel).first
                    if drawer.count() > 0 and drawer.is_visible():
                        print(f"✅ Drawer is visible (Selector: {d_sel})!")
                        found_drawer = True
                        break
                
                if not found_drawer:
                    print("❌ Drawer NOT visible after 10s.")
            else:
                print("❌ Apply button not found or not visible.")
                # Dump DOM anyway to see what's there
                dom_path = os.path.join(logs_dir, "debug_naukri_no_btn.html")
                with open(dom_path, "w") as f:
                    f.write(page.content())
                print(f"Dumped DOM to: {dom_path}")

        except Exception as e:
            print(f"🛑 Error during execution: {e}")

        browser.close()

if __name__ == "__main__":
    debug_apply()
