import os
import json
import time
from dotenv import load_dotenv

# Base paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
load_dotenv(os.path.join(BASE_DIR, '.env'))

SESSION_FILE_NAUKRI = os.path.join(BASE_DIR, 'data', 'naukri_session.json')

def login_naukri(page, context, username, password):
    """Performs an automated login to Naukri within an existing context/page."""
    print(f"👤 Attempting automated login for {username}...")
    try:
        page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded")
        time.sleep(5)
        
        page.fill("#usernameField", username)
        page.fill("#passwordField", password)
        page.click("button[type='submit']")
        
        # Wait for login confirmation
        for i in range(15): # 30 seconds
            curr_url = page.url
            is_logged_in = page.evaluate("""() => {
                const url = window.location.href;
                if (url.includes("mnjuser/profile") || url.includes("mnjuser/homepage") || url.includes("ni/ninja/homepage")) return true;
                if (document.querySelector('a[href*="nlogin/logout"]') || document.querySelector('.nI-gNb-header__logged-in')) return true;
                return false;
            }""")
            
            if is_logged_in:
                print("✅ Login successful! Saving session...")
                time.sleep(2)
                cookies = context.cookies()
                with open(SESSION_FILE_NAUKRI, 'w') as f:
                    json.dump(cookies, f, indent=4)
                return True
            
            if "otp" in curr_url.lower():
                print("⚠️ OTP REQUIRED. Automated login cannot proceed.")
                return False
                
            time.sleep(2)
        
        print("❌ Login timed out.")
        return False
    except Exception as e:
        print(f"❌ Automated login failed: {e}")
        return False

def ensure_naukri_session(page, context):
    """Checks if current Naukri session is valid, attempts re-login if expired."""
    print("🔍 Validating Naukri session...")
    try:
        # Check if we are already on a login page before navigating
        if "login" in page.url.lower():
            email = os.getenv("NAUKRI_EMAIL")
            password = os.getenv("NAUKRI_PASSWORD")
            if email and password:
                return login_naukri(page, context, email, password)

        page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded")
        time.sleep(5)
        
        if "login" in page.url.lower():
            print("❌ Session expired.")
            email = os.getenv("NAUKRI_EMAIL")
            password = os.getenv("NAUKRI_PASSWORD")
            
            if email and password:
                return login_naukri(page, context, email, password)
            else:
                print("⚠️ NAUKRI_EMAIL and NAUKRI_PASSWORD not found in .env. Automated re-login skipped.")
                return False
        
        print("✅ Session active.")
        return True
    except Exception as e:
        print(f"⚠️ Session validation failed: {e}")
        return False
