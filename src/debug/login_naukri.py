import os
import json
import time
import sys
from playwright.sync_api import sync_playwright

# Identify project root (AiAutomation/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')

def autonomous_login(username, password):
    with sync_playwright() as p:
        # Use a real-looking browser context
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(45000)
        
        print("🚀 Navigating to Naukri...")
        page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded")
        
        try:
            print(f"👤 Entering credentials for {username}...")
            page.fill("#usernameField", username)
            page.fill("#passwordField", password)
            page.click("button[type='submit']")
        except Exception as e:
            print(f"❌ Initial form fill failed: {e}")
            browser.close()
            return False

        print("⏳ Waiting for login confirmation...")
        success = False
        for i in range(30): # 60 seconds
            curr_url = page.url
            print(f"📍 [{i*2}s] {curr_url}")
            
            # Check for success indicators
            is_logged_in = page.evaluate("""() => {
                const url = window.location.href;
                if (url.includes("mnjuser/profile") || url.includes("mnjuser/homepage") || url.includes("ni/ninja/homepage") || url.includes("mnjuser/homepage")) return true;
                if (document.querySelector('a[href*="nlogin/logout"]') || document.querySelector('.nI-gNb-header__logged-in')) return true;
                return false;
            }""")
            
            if is_logged_in:
                print("✅ Login detected! Saving cookies immediately...")
                time.sleep(3)
                cookies = context.cookies()
                with open(SESSION_FILE, 'w') as f:
                    json.dump(cookies, f, indent=4)
                print(f"💾 Session saved: {SESSION_FILE}")
                
                # Optional verify
                try:
                    print("🏁 Verifying profile access...")
                    page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=10000)
                    if "profile" in page.url:
                        print("✨ Profile verified.")
                except:
                    print("⚠️ Verification navigation timed out, but session was already saved.")
                
                success = True
                break
            
            if "otp" in curr_url.lower():
                print("⚠️ OTP REQUIRED. Waiting 30s...")
                time.sleep(30)
                continue

            time.sleep(2)
            
        browser.close()
        return success

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python login_naukri.py <user> <pass>")
    else:
        autonomous_login(sys.argv[1], sys.argv[2])
