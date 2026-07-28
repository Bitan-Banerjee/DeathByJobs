import os
import sys
import json
import time
import random
from playwright.sync_api import sync_playwright

# Add scripts dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from linkedin_auto_apply import get_batch_answers_from_gemini

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
REGISTRY_PATH = os.path.join(BASE_DIR, 'data', 'job_qa_registry.json')

def debug_interview_checkboxes(url):
    print(f"🌐 Debugging Interview Slots on: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f: context.add_cookies(json.load(f))
            
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            # Check Login
            print("🌐 Checking Naukri session...")
            page.goto("https://www.naukri.com/nlogin/login")
            time.sleep(3)
            
            if page.locator("#usernameField").is_visible():
                print("🔐 Session expired. Please log in manually. Waiting 120s...")
                page.wait_for_url("**/mnjuser/**", timeout=120000)
                print("✅ Login detected! Saving session...")
                with open(SESSION_FILE, "w") as f:
                    json.dump(context.cookies(), f)

            page.goto(url, wait_until="domcontentloaded")
            time.sleep(5)

            apply_btn = page.locator("button:has-text('Apply'), [class*='applyBtn' i]").first
            if apply_btn.is_visible(timeout=5000):
                apply_btn.click()
                print("  🔘 Clicked Apply.")
                time.sleep(8)
            else:
                print("  ❌ Apply button missing.")
                return

            # Simulate the question handling loop
            for round_num in range(10):
                time.sleep(3)
                
                # Dynamic element extraction (same as naukri_auto_apply.py)
                questions = page.evaluate("""() => {
                    const drawer = document.querySelector('.chatbot_DrawerContentWrapper') || 
                                   document.querySelector('.chatbot_MessageContainer') || 
                                   document.querySelector('[role="dialog"]');
                    if (!drawer) return [];

                    const messageEls = Array.from(drawer.querySelectorAll('.chatbot_ListItem, .msg, .chipMsg, p, span'));
                    let qText = "";
                    for (let i = messageEls.length - 1; i >= 0; i--) {
                        const t = messageEls[i].innerText.trim();
                        if (t.length > 10 && !t.includes('logo') && !t.includes('Naukri') && !t.includes('Save')) {
                            qText = t; break;
                        }
                    }

                    const options = Array.from(drawer.querySelectorAll('.chipMsg, .pill, .option, [class*="chip" i], [class*="pill" i], label'))
                        .map(o => o.innerText.trim())
                        .filter(t => t.length > 0 && t.length < 50 && t !== qText);

                    return [{ question: qText, options: options }];
                }""")

                if not questions or not questions[0]['question']:
                    print("    ⚠️ No question found.")
                    continue

                q = questions[0]
                print(f"    ❓ Round {round_num+1}: {q['question']}")
                print(f"    📋 Options: {q['options']}")

                # Get answer from Gemini (with our new availability rules)
                registry = {}
                if os.path.exists(REGISTRY_PATH):
                    with open(REGISTRY_PATH, 'r') as f: registry = json.load(f)

                full_key = f"{q['question']} (Options: {', '.join(q['options'])})" if q['options'] else q['question']
                
                print("    🧠 Asking Gemini for valid slot...")
                new_ans = get_batch_answers_from_gemini([full_key], registry)
                ans = new_ans.get(full_key, "")
                print(f"    💡 Answer: {ans}")

                # TEST NEW CLICK LOGIC
                page.evaluate("""([ans]) => {
                    const val = ans.toLowerCase().trim();
                    // Try inputs
                    const inputs = Array.from(document.querySelectorAll('input[type="radio"], input[type="checkbox"]'));
                    for (const r of inputs) {
                        const lbl = document.querySelector(`label[for="${r.id}"]`) || r.parentElement;
                        if (lbl && lbl.innerText.toLowerCase().includes(val)) {
                            r.click(); // Click label or radio
                            return true;
                        }
                    }
                    // Try pills
                    const targets = Array.from(document.querySelectorAll('.chatbot_Drawer .chipMsg, .pill, label, .option, button, span'));
                    const match = targets.find(t => t.innerText.trim().toLowerCase().includes(val));
                    if (match) { match.click(); return true; }
                }""", [ans])

                time.sleep(2)
                # Click Save/Send
                page.locator(".sendMsg, .sendMsgbtn_container, button:has-text('Save'), button:has-text('Submit'), button:has-text('Next')").last.click(force=True)
                print("    📨 Sent answer.")

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            print("🏁 Debug run finished. Keeping browser open for 10s...")
            time.sleep(10)
            browser.close()

if __name__ == "__main__":
    exl_url = "https://www.naukri.com/job-listings-data-engineer-exl-gurugram-bengaluru-2-to-5-years-210426000116"
    debug_interview_checkboxes(exl_url)
