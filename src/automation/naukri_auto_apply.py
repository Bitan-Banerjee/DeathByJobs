import os
import json
import time
import random
import re
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright
try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

# Add auth helper
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils'))
try:
    from auth_helper import ensure_naukri_session
except ImportError:
    def ensure_naukri_session(page, context): return True

try:
    from linkedin_auto_apply import get_batch_answers_from_gemini
except ImportError:
    def get_batch_answers_from_gemini(questions, registry):
        # Fallback if import fails
        return {}

# Identify project root (DeathByJobs/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'naukri_matched_jobs.json')
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
REGISTRY_PATH = os.path.join(BASE_DIR, 'data', 'job_qa_registry.json')


def get_registry():
    if not os.path.exists(REGISTRY_PATH): return {}
    with open(REGISTRY_PATH, 'r') as f: return json.load(f)


def save_registry(registry):
    with open(REGISTRY_PATH, 'w') as f: json.dump(registry, f, indent=4)


def is_login_page(page):
    """Detect if we have been redirected to login or are in a logged-out state."""
    current_url = page.url
    if "login" in current_url.lower() or "register" in current_url.lower():
        return True
    
    # Check for login buttons or headers
    login_indicators = [
        "button:has-text('Login')",
        "a:has-text('Login')",
        "input[placeholder*='username' i]",
        "input[placeholder*='password' i]"
    ]
    for ind in login_indicators:
        if page.locator(ind).count() > 0:
            if page.locator(ind).first.is_visible(timeout=2000):
                return True
    return False


def check_for_errors(page):
    """Detect common Naukri error messages or blocks."""
    error_keys = [
        "there was some error processing that request",
        "something went wrong",
        "please try again later",
        "unable to process",
        "access denied",
        "blocked"
    ]
    try:
        # Check for visible error toasts or dialogs
        body_text = page.evaluate("() => document.body.innerText.toLowerCase()")
        for key in error_keys:
            if key in body_text:
                print(f"    🚨 ERROR DETECTED: {key}")
                return True
        return False
    except:
        return False


def detect_form_panel(page):
    """Refined detection for Naukri's drawer or chatbot form."""
    selectors = [
        ".chatbot_DrawerContentWrapper",
        ".chatbot_Drawer",
        ".chatbot_MessageContainer",
        "[class*='applyModal' i]",
        "[class*='questionnaire' i]",
        "[role='dialog']"
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                is_vis = loc.is_visible()
                print(f"    DEBUG: Found {sel}, visible: {is_vis}")
                if is_vis:
                    return True
        except: continue
    
    # Check for specific chatbot elements as fallback
    try:
        fallback_loc = page.locator(".botMsg, .ssrc__radio-btn-container, .chatbot_ListItem")
        if fallback_loc.count() > 0:
            if fallback_loc.first.is_visible():
                return True
    except: pass

    return False


def extract_questions(page):
    """Refined extraction logic for Naukri Chatbots and standard forms."""
    return page.evaluate("""() => {
        const questions = [];
        const drawer = document.querySelector('.chatbot_DrawerContentWrapper') || 
                       document.querySelector('.chatbot_MessageContainer') || 
                       document.querySelector('[role="dialog"]');
        if (!drawer) return [];

        // 1. CHATBOT MESSAGE EXTRACTION
        const messageEls = Array.from(drawer.querySelectorAll('.chatbot_ListItem, .msg, .chipMsg, p, span'));
        let chatbotQuestion = "";
        for (let i = messageEls.length - 1; i >= 0; i--) {
            const text = messageEls[i].innerText.trim();
            if (text.length > 10 && !text.includes('logo') && !text.includes('Naukri') && !text.includes('Save')) {
                chatbotQuestion = text;
                break;
            }
        }

        // 2. PILLS/OPTIONS / CHECKBOXES
        const allItems = Array.from(drawer.querySelectorAll('.chatbot_ListItem, .chatbot_MessageContainer > div'));
        const lastFewItems = allItems.slice(-5); 
        let options = [];
        let type = 'styled_radio';

        // Check for explicit checkboxes in the last few items
        lastFewItems.forEach(item => {
            const checkboxes = item.querySelectorAll('input[type="checkbox"], .mcc__checkbox, .ssrc__checkbox');
            if (checkboxes.length > 0) type = 'styled_checkbox';

            const found = Array.from(item.querySelectorAll('.chipMsg, .pill, .option, [class*="chip" i], [class*="pill" i], label, .ssrc__label, .optionVal, .chatbot_Chip'))
                .map(o => o.innerText.trim())
                .filter(t => t.length > 0 && t.length < 50 && t !== chatbotQuestion && !t.includes('Save') && !t.includes('Type here'));
            found.forEach(f => { if(!options.includes(f)) options.push(f); });
        });

        if (chatbotQuestion && options.length > 0) {
            questions.push({
                question: chatbotQuestion,
                type: type,
                options: options.map(o => ({ value: o, text: o })),
                index: 0
            });
        }

        // 3. INPUTS
        if (questions.length === 0 && chatbotQuestion) {
            const chatInput = drawer.querySelector('.textArea, [contenteditable="true"], input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]), textarea');
            if (chatInput) {
                questions.push({
                    question: chatbotQuestion,
                    type: chatInput.tagName === 'INPUT' || chatInput.tagName === 'TEXTAREA' ? 'text' : 'contenteditable',
                    options: [],
                    index: 0
                });
            }
        }

        // 4. FALLBACK: Standard Modal
        if (questions.length === 0) {
            const containers = Array.from(drawer.querySelectorAll('[class*="question" i], [class*="formItem" i], [class*="field" i]'));
            containers.forEach((container, idx) => {
                const labelEl = container.querySelector('label, [class*="label" i], p');
                const label = labelEl ? labelEl.innerText.trim() : container.innerText.split('\\n')[0].trim();
                if (label.length < 5) return;
                const hasInput = container.querySelector('input, textarea');
                if (hasInput) questions.push({ question: label, type: 'text', options: [], index: idx });
            });
        }
        return questions;
    }""")


def answer_questions(page, questions, registry):
    """Answer questions with aggressive click logic and modern event dispatching."""
    for q in questions:
        q_text = q['question']
        options = [o['text'] for o in q.get('options', [])]
        full_key = f"{q_text} (Options: {', '.join(options)})" if options else q_text
        print(f"    ❓ Question: {q_text[:80]}")

        if full_key not in registry:
            try:
                new_ans = get_batch_answers_from_gemini([full_key], registry)
                if new_ans: registry.update(new_ans); save_registry(registry)
            except: pass
        
        ans = str(registry.get(full_key, "")).strip()
        if not ans and options: ans = options[0]
        print(f"    💡 Answer: {ans}")

        if q['type'] in ('text', 'contenteditable'):
            input_locator = page.locator('.textArea, [contenteditable="true"], .chatbot_Drawer input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]), .chatbot_Drawer textarea').first
            if input_locator.count() > 0 and input_locator.first.is_visible():
                input_locator.first.click()
                time.sleep(0.5)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(ans, delay=50)
                time.sleep(0.5)
                page.evaluate("""([ans]) => {
                    const input = document.querySelector('.textArea, [contenteditable="true"], .chatbot_Drawer input, .chatbot_Drawer textarea');
                    if (input) {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""", [ans])
        elif q['type'] in ('styled_radio', 'styled_checkbox'):
            # AGGRESSIVE CLICKING LOGIC FOR RADIOS AND CHECKBOXES (NATIVE PLAYWRIGHT)
            answers = ans.split(',') if q['type'] == 'styled_checkbox' else [ans]
            for a in answers:
                target = a.strip()
                try:
                    # Native playwright click
                    loc = page.locator(f"label:text-is('{target}')").first
                    if not loc.is_visible():
                        loc = page.locator(f"label:has-text('{target}')").first
                    
                    if not loc.is_visible():
                        loc = page.locator(f"text='{target}'").locator("..").first # Sometimes it's a span inside a div

                    if loc.is_visible():
                        loc.scroll_into_view_if_needed()
                        for_id = loc.get_attribute("for")
                        is_checked = False
                        if for_id:
                            is_checked = page.evaluate(f"document.getElementById('{for_id}')?.checked")
                        
                        if not is_checked:
                            loc.click(force=True)
                            print(f"      🔘 Clicked: {target}")
                        else:
                            print(f"      🔘 Already checked: {target}")
                    else:
                        # JS Fallback
                        page.evaluate("""(t) => {
                            const selectors = ['.mcc__label', '.ssrc__label', '.chipMsg', '.pill', '.chatbot_Chip', '.optionVal'];
                            const targets = Array.from(document.querySelectorAll(selectors.join(',')));
                            const match = targets.find(el => el.innerText.trim().toLowerCase() === t.toLowerCase());
                            if (match) match.click();
                        }""", target)
                except Exception as e:
                    print(f"      ⚠️ Click error for {target}: {e}")

            # Enable the save button explicitly
            page.evaluate("""() => {
                const saveBtn = document.querySelector('.sendMsgbtn_container .send') || document.querySelector('.chatBot-ic-send');
                if (saveBtn) { saveBtn.classList.remove('disabled'); saveBtn.removeAttribute('disabled'); }
            }""")
        time.sleep(3)


def submit_form(page):
    """Submit current step with enhanced state checking."""
    try:
        save_btn = page.locator(".sendMsgbtn_container .send, button:has-text('Save'), button:has-text('Submit'), button:has-text('Next'), button:has-text('Apply'), .chatBot-ic-send").last
        if not save_btn.is_visible(timeout=3000):
            print("    ℹ️ No Save button visible.")
            return True

        is_disabled = page.evaluate("""(el) => {
            if (!el) return false;
            return el.classList.contains('disabled') || el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';
        }""", save_btn.element_handle())
        
        if not is_disabled:
            save_btn.click(force=True)
            print("    📨 Clicked Save/Submit")
            time.sleep(4)
            return True
        else:
            print("    ⚠️ Save button DISABLED. Forcing click.")
            page.evaluate("(el) => { el.classList.remove('disabled'); el.click(); }", save_btn.element_handle())
            time.sleep(4)
            return True
    except: return False


def check_success(page):
    """Comprehensive success verification with specific button and text checks."""
    try:
        # 1. Check for the green 'Applied' button which is the most reliable indicator
        applied_btn = page.locator("button:has-text('Applied'), [class*='applied' i], .applied-btn, .applied").first
        if applied_btn.count() > 0:
            if applied_btn.is_visible(timeout=2000):
                return True

        # 2. Check for success text in the body or chatbot drawer
        success_keys = [
            "successfully applied", 
            "application submitted", 
            "already applied", 
            "applied on", 
            "applied today", 
            "thank you for applying", 
            "interest has been sent",
            "your application has been sent",
            "successfully sent"
        ]
        
        # Check specific containers first (drawer, bot messages)
        containers = [".chatbot_Drawer", ".chatbot_MessageContainer", ".success-message", ".apply-message"]
        for sel in containers:
            container = page.locator(sel).first
            if container.count() > 0 and container.is_visible(timeout=1000):
                text = container.inner_text().lower()
                if any(k in text for k in success_keys):
                    return True

        # Global body check as fallback
        body_text = page.evaluate("() => document.body.innerText.toLowerCase()")
        if any(k in body_text for k in success_keys):
            return True
            
        return False
    except:
        return False


def is_expired(page):
    """Check if the job posting has expired."""
    title = page.title().lower()
    if "jobs in india" in title and "job vacancies" in title: return True
    expired_keys = ["this job has expired", "job is no longer available", "post is no longer available", "deactivated", "closed"]
    body = page.evaluate("() => document.body.innerText.toLowerCase()")
    if any(k in body for k in expired_keys): return True
    return page.locator(".expired-job, [class*='expired' i]").count() > 0


COMPANY_BEHAVIOR_FILE = os.path.join(BASE_DIR, 'data', 'naukri_company_behavior.json')


def get_behavior():
    if not os.path.exists(COMPANY_BEHAVIOR_FILE): return {}
    with open(COMPANY_BEHAVIOR_FILE, 'r') as f: return json.load(f)


def save_behavior(behavior):
    with open(COMPANY_BEHAVIOR_FILE, 'w') as f: json.dump(behavior, f, indent=4)


def naukri_apply(matched_path=MATCHED_PATH):
    if not os.path.exists(matched_path): 
        print(f"❌ Matched path not found: {matched_path}")
        return
    with open(matched_path, 'r') as f: jobs = json.load(f).get("approved_jobs", [])
    if not jobs: return

    registry = get_registry()
    behavior = get_behavior()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            java_script_enabled=True
        )
        if os.path.exists(SESSION_FILE):
            print(f"🔑 Loading session: {SESSION_FILE}")
            with open(SESSION_FILE, 'r') as f: context.add_cookies(json.load(f))
        
        page = context.new_page()
        if HAS_STEALTH:
            stealth_sync(page)
            print("🕵️ Stealth mode activated.")
        page.set_default_timeout(60000)

        # --- SESSION VALIDATION ---
        if not ensure_naukri_session(page, context):
            print("🛑 Could not establish valid Naukri session. Exiting.")
            browser.close()
            return
        # --------------------------

        for job in jobs:
            if job.get('status') == 'applied': continue
            
            company_name = job.get('company', 'Unknown')
            print(f"\n🚀 Processing: {company_name}")
            try:
                page.goto(job['url'], wait_until="domcontentloaded")
                time.sleep(10) # Heavy page, wait for scripts

                # --- SESSION CHECK ---
                if is_login_page(page):
                    print("⚠️ Detected login redirect inside loop. Attempting auto-refresh...")
                    if not ensure_naukri_session(page, context):
                        print("🛑 Session expired and auto-login failed. Skipping rest of Naukri jobs.")
                        break
                    else:
                        print("🔄 Session refreshed. Returning to job...")
                        page.goto(job['url'], wait_until="domcontentloaded")
                        time.sleep(10)
                # ---------------------

                if check_success(page):
                    print("  ✅ Already applied."); job['status'] = 'applied'
                else:
                    apply_btn = page.locator("#apply-button, .apply-button").first
                    if not apply_btn.is_visible(timeout=5000):
                        if is_expired(page):
                            print("  ⚠️ Job has expired."); job['status'] = 'expired'
                        else:
                            print("  ❌ Apply button missing."); job['status'] = 'skipped_no_apply_btn'
                    else:
                        print("  🔘 Clicking Apply...")
                        try:
                            apply_btn.scroll_into_view_if_needed()
                            # Move mouse to button and click like a human
                            box = apply_btn.bounding_box()
                            if box:
                                page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                time.sleep(random.uniform(0.2, 0.5))
                                page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                            else:
                                apply_btn.click(force=True)
                            print(f"    DEBUG: Clicked button. Current URL: {page.url}")
                        except Exception as click_err:
                            print(f"    ⚠️ Direct click failed, trying JS click: {click_err}")
                            page.evaluate("(el) => { if(el) el.click(); }", apply_btn.element_handle())
                        
                        # --- IMPROVED TIMING & ERROR CHECK ---
                        print("    ⏳ Waiting 5s for response...")
                        time.sleep(5)
                        
                        if check_for_errors(page):
                            print("    ❌ Application blocked by system error.")
                            job['status'] = 'failed_system_error'
                            continue

                        # Wait the remaining time for animations/redirects
                        time.sleep(5)
                        # -------------------------------------
                        
                        # 2. Check for current page redirect to external site
                        if "naukri.com" not in page.url:
                            print(f"  🌐 Redirected to external portal (same tab): {page.url}")
                            job['status'] = 'skipped_external_portal'
                            if company_name not in behavior: behavior[company_name] = {"internal": 0, "external": 0}
                            behavior[company_name]["external"] += 1
                            save_behavior(behavior)
                            continue
                        
                        # 3. Detect if drawer/form opened
                        if not detect_form_panel(page):
                            # Check if we succeeded without a form (One-click)
                            if check_success(page):
                                print("  ✅ Success (One-Click)!"); job['status'] = 'applied'
                                if company_name not in behavior: behavior[company_name] = {"internal": 0, "external": 0}
                                behavior[company_name]["internal"] += 1
                                save_behavior(behavior)
                                continue
                            else:
                                print("  ⚠️ Drawer didn't open. Retrying click...")
                                try:
                                    page.evaluate("(el) => { if(el) el.click(); }", apply_btn.element_handle())
                                except: pass
                                time.sleep(8)
                                
                                # Final check after retry
                                if not detect_form_panel(page):
                                    if check_success(page):
                                        print("  ✅ Success (One-Click)!"); job['status'] = 'applied'
                                        if company_name not in behavior: behavior[company_name] = {"internal": 0, "external": 0}
                                        behavior[company_name]["internal"] += 1
                                        save_behavior(behavior)
                                        continue
                                    else:
                                        # One more attempt: Check for green 'Applied' button specifically
                                        if check_success(page): # redundant check but safe
                                             print("  ✅ Success!"); job['status'] = 'applied'
                                        else:
                                            print("  ❌ Failed: Drawer didn't open and success not detected.")
                                            job['status'] = 'failed_no_drawer'
                                            continue

                        last_question = ""
                        stuck_count = 0
                        
                        for round_num in range(10): # Overall limit
                            # Periodic success check
                            if check_success(page):
                                print("  ✅ Success!"); job['status'] = 'applied'; break
                            
                            if not detect_form_panel(page):
                                # Panel vanished - verify if it was success or failure
                                time.sleep(4)
                                if check_success(page):
                                    print("  ✅ Success (Form Completed)!"); job['status'] = 'applied'
                                    if company_name not in behavior: behavior[company_name] = {"internal": 0, "external": 0}
                                    behavior[company_name]["internal"] += 1
                                    save_behavior(behavior)
                                else:
                                    print("  ❌ Form vanished but success NOT confirmed."); job['status'] = 'failed_vanished'
                                break

                            questions = extract_questions(page)
                            if not questions:
                                # Might be a loading state or a different type of screen
                                time.sleep(4); questions = extract_questions(page)
                                if not questions:
                                    if check_success(page):
                                        print("  ✅ Success!"); job['status'] = 'applied'; break
                                    else:
                                        print("  ⚠️ Form present but no questions extracted."); job['status'] = 'failed_no_questions'
                                        break

                            current_q = questions[0]['question']
                            if current_q == last_question:
                                stuck_count += 1
                                if stuck_count >= 3:
                                    print(f"  🛑 Stuck on same question for 3 rounds: {current_q[:50]}...")
                                    job['status'] = 'failed_stuck'
                                    break
                            else:
                                last_question = current_q
                                stuck_count = 0

                            print(f"    📝 Step {round_num+1}: Found {len(questions)} question(s)")
                            
                            answer_questions(page, questions, registry)
                            submit_form(page)
                            
                            # Brief pause after submit to let UI settle
                            time.sleep(2)
                        else:
                            print("  ⚠️ Max rounds (10) reached. Likely stuck."); job['status'] = 'skipped_too_many_rounds'

            except Exception as e:
                print(f"  ⚠️ Error: {str(e).split('\\n')[0]}")
                job['status'] = 'error'

            # Save progress after each job
            with open(matched_path, 'w') as f: json.dump({"approved_jobs": jobs}, f, indent=4)
            time.sleep(1)

        browser.close()


if __name__ == "__main__":
    naukri_apply()
