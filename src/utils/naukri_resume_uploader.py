import os
import json
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
RESUME_PATH = os.path.join(BASE_DIR, 'resume.docx')
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"

def upload_resume():
    if not os.path.exists(RESUME_PATH):
        print(f"❌ Resume not found at: {RESUME_PATH}")
        return False

    with sync_playwright() as p:
        # Launching headful for verification, can be switched to headless=True
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        
        if os.path.exists(SESSION_FILE):
            print("🔑 Loading session cookies...")
            with open(SESSION_FILE, 'r') as f:
                context.add_cookies(json.load(f))
        else:
            print("❌ Session file missing. Cannot upload without login.")
            browser.close()
            return False

        page = context.new_page()
        print(f"🚀 Navigating to profile: {PROFILE_URL}")
        page.goto(PROFILE_URL)
        time.sleep(5)

        # Check if we are actually on the profile page (auth check)
        if "login" in page.url.lower():
            print("❌ Redirected to login. Session expired.")
            browser.close()
            return False

        try:
            print("📤 Locating resume upload input...")
            # Naukri uses an invisible input[type="file"] triggered by a "Update" or "Upload Resume" button
            # Selector for the actual file input
            file_input = page.locator("input[type='file'][id='attachCV']")
            
            if file_input.count() == 0:
                # Fallback to any visible file input if the specific ID changed
                file_input = page.locator("input[type='file']").first

            if file_input.is_visible(timeout=5000) or file_input.count() > 0:
                print(f"📄 Uploading: {RESUME_PATH}")
                file_input.set_input_files(RESUME_PATH)
                
                # Wait for upload completion indicators
                print("⏳ Waiting for upload to complete...")
                time.sleep(10)
                
                # Capture evidence
                ss_path = os.path.join(BASE_DIR, 'logs', 'screenshots', 'naukri_resume_upload_result.png')
                os.makedirs(os.path.dirname(ss_path), exist_ok=True)
                page.screenshot(path=ss_path)
                print(f"📸 Result screenshot saved: {ss_path}")
                
                # Check for success message or updated date
                success_keywords = ["successfully", "updated", "just now", "today"]
                body_text = page.evaluate("() => document.body.innerText.toLowerCase()")
                if any(k in body_text for k in success_keywords):
                    print("✅ Resume uploaded successfully!")
                    return True
                else:
                    print("⚠️ Upload finished but success message not detected. Check screenshot.")
                    return True
            else:
                print("❌ Could not find resume upload input.")
                return False

        except Exception as e:
            print(f"❌ Error during upload: {e}")
            return False
        finally:
            time.sleep(2)
            browser.close()

if __name__ == "__main__":
    upload_resume()
