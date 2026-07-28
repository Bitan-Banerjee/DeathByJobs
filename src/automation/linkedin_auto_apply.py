import os
import json
import time
import random
import re
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

from utils.config_loader import load_profile
from utils.llm_client import generate_json, LLMError

# Legacy alias used by debug scripts and naukri_auto_apply
def get_batch_answers_from_gemini(questions_list, registry):
    return get_batch_answers(questions_list, registry)

SESSION_FILE = os.path.join(BASE_DIR, 'data', 'linkedin_session.json')
MATCHED_PATH = os.path.join(BASE_DIR, 'data', 'matched_jobs.json')
REGISTRY_PATH = os.path.join(BASE_DIR, 'data', 'job_qa_registry.json')

_profile = load_profile()
_application_cfg = _profile.get("application", {})
_analogous_skills = _application_cfg.get("analogous_skills", {})
_availability = _application_cfg.get("availability", {})
_experience_years = _application_cfg.get("experience_years", 4)
_core_skills = _profile.get("target_profile", {}).get("core_skills", [])


def _build_analogous_skills_text(skills_map: dict) -> str:
    if not skills_map:
        return "No analogous skill mappings configured."
    lines = []
    for required, candidate_equivalent in skills_map.items():
        lines.append(f"- If asked for {required}, treat it as {candidate_equivalent} experience.")
    return "\n".join(lines)


def get_batch_answers(questions_list, registry):
    if not questions_list: return {}

    print(f"    🧠 Batching {len(questions_list)} new questions to LLM...")

    profile = load_profile()
    app_cfg = profile.get("application", {})
    experience_years = app_cfg.get("experience_years", _experience_years)
    availability = app_cfg.get("availability", _availability)
    analogous_map = app_cfg.get("analogous_skills", _analogous_skills)
    core_skills = profile.get("target_profile", {}).get("core_skills", _core_skills)

    prompt = f"""You are filling out a job application.

User Profile: {json.dumps(profile)}
Registry (previously answered questions): {json.dumps(registry)}

Answer the following list of questions:
{json.dumps(questions_list)}

RULES:
1. You MUST return ONLY a valid JSON dictionary.
2. Keys MUST be the EXACT question strings provided.

**YEARS OF EXPERIENCE RULE**:
- The candidate has **{experience_years} years** of experience in {', '.join(core_skills)}.
- **ANALOGOUS SKILLS**:
{_build_analogous_skills_text(analogous_map)}
- Example: "Years of experience in Azure?" -> Answer: "{experience_years}".
- NEVER output "0" for these technical skills.

**INTERVIEW AVAILABILITY**:
- The candidate is available at:
    1. Morning: {availability.get('morning', 'Before 11:00 AM')}.
    2. Afternoon: {availability.get('afternoon', '2:00 PM - 4:30 PM')}.
    3. Evening: {availability.get('evening', 'After 7:00 PM')}.
- If asked for a preferred time slot or checkbox, pick the option that BEST fits one of these windows.

**FORMATTING RULES**:
- If the question asks for years/months and expects a number (or is a numeric field), return ONLY the integer (e.g., "{experience_years}" not "{experience_years} years").
- If the question is "Yes/No", return "Yes".

**MULTIPLE CHOICE**:
- If a question includes "(Options: ...)", the value MUST be the exact text of one of those options. Choose the most positive/experienced option.

3. Be consistent with the Registry.
"""

    try:
        return generate_json(prompt, temperature=0.2)
    except LLMError as e:
        print(f"    ⚠️ LLM Q&A failed: {e}")
        raise

def handle_questions(page, registry):
    questions_to_ask = []
    
    # --- PHASE 1: SCRAPE & BATCH ---
    for field in page.query_selector_all(".artdeco-modal input[type='text'], .artdeco-modal input[type='number'], .artdeco-modal textarea"):
        if not field.input_value(): 
            label = page.query_selector(f"label[for='{field.get_attribute('id')}']")
            q_text = label.inner_text().strip() if label else ""
            if q_text and q_text not in registry: questions_to_ask.append(q_text)

    for dropdown in page.query_selector_all(".artdeco-modal select"):
        label = page.query_selector(f"label[for='{dropdown.get_attribute('id')}']")
        q_text = label.inner_text().strip() if label else ""
        options = [opt.inner_text().strip() for opt in dropdown.query_selector_all("option") if "Select" not in opt.inner_text() and opt.inner_text().strip()]
        if options:
            full_q = f"{q_text} (Options: {', '.join(options)})"
            if full_q not in registry: questions_to_ask.append(full_q)

    for fieldset in page.query_selector_all(".artdeco-modal fieldset"):
        if not fieldset.query_selector("input:checked"): 
            legend = fieldset.query_selector("legend")
            q_text = legend.inner_text().strip() if legend else ""
            labels = fieldset.query_selector_all("label")
            options = [l.inner_text().strip() for l in labels if l.inner_text().strip()]
            if options:
                full_q = f"{q_text} (Options: {', '.join(options)})"
                if full_q not in registry: questions_to_ask.append(full_q)

    # --- PHASE 2: ASK AI & SAVE ---
    if questions_to_ask:
        new_answers = get_batch_answers_from_gemini(questions_to_ask, registry)
        if new_answers:
            registry.update(new_answers)
            try:
                with open(REGISTRY_PATH, 'w') as f: json.dump(registry, f, indent=4)
                print(f"    💾 Batch saved {len(new_answers)} new answers to registry.")
            except: pass

    # --- PHASE 3: FILL THE PAGE ---
    for field in page.query_selector_all(".artdeco-modal input[type='text'], .artdeco-modal input[type='number'], .artdeco-modal textarea"):
        label = page.query_selector(f"label[for='{field.get_attribute('id')}']")
        q_text = label.inner_text().strip() if label else ""
        if q_text in registry:
            ans = str(registry[q_text])
            
            # Numeric intent detection based on label or input type
            is_numeric = (field.get_attribute('type') == 'number' or 
                         any(term in q_text.lower() for term in ["years", "ctc", "exp", "notice", "days", "months"]))
            
            if is_numeric:
                clean_ans = re.sub(r'[^\d.]', '', ans)
                # If cleaning makes it empty or just a dot, or we have "10.5 LPA" -> "10.5"
                if not clean_ans or clean_ans == ".":
                    clean_ans = "4"
                
                # Special case: float validation (larger than 0.0)
                try:
                    if float(clean_ans) <= 0:
                        clean_ans = "4"
                except:
                    clean_ans = "4"
                
                ans = clean_ans

            print(f"    📝 Filling: '{q_text}' -> '{ans}'")
            field.click() # Focus
            page.keyboard.press("Control+A") # Select all
            page.keyboard.press("Backspace") # Clear
            field.fill(ans)
            time.sleep(0.5)
            # Attempt to click autocomplete suggestions (Mandatory for LinkedIn Location fields)
            try:
                dropdown_opt = page.locator(".search-typeahead-v2__hit, .basic-typeahead__result, .artdeco-typeahead__result").first
                if dropdown_opt.is_visible(timeout=500):
                    dropdown_opt.click()
                    time.sleep(0.5)
            except: pass

    for dropdown in page.query_selector_all(".artdeco-modal select"):
        label = page.query_selector(f"label[for='{dropdown.get_attribute('id')}']")
        q_text = label.inner_text().strip() if label else ""
        options = [opt.inner_text().strip() for opt in dropdown.query_selector_all("option") if "Select" not in opt.inner_text() and opt.inner_text().strip()]
        if options:
            full_q = f"{q_text} (Options: {', '.join(options)})"
            if full_q in registry:
                try: dropdown.select_option(label=str(registry[full_q]))
                except: dropdown.select_option(index=1) 

    for fieldset in page.query_selector_all(".artdeco-modal fieldset"):
        if not fieldset.query_selector("input:checked"):
            legend = fieldset.query_selector("legend")
            q_text = legend.inner_text().strip() if legend else ""
            labels = fieldset.query_selector_all("label")
            options = [l.inner_text().strip() for l in labels if l.inner_text().strip()]
            if options:
                full_q = f"{q_text} (Options: {', '.join(options)})"
                if full_q in registry:
                    ans = str(registry[full_q]).lower()
                    for lbl in labels:
                        if ans == lbl.inner_text().strip().lower():
                            lbl.click()
                            break

def take_screenshot(page, company_name, error_type, debug_mode=False):
    """Saves a timestamped screenshot and DOM to logs/screenshots/ for debugging."""
    try:
        now = datetime.now()
        ss_dir = os.path.join(BASE_DIR, 'logs', 'screenshots', now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
        os.makedirs(ss_dir, exist_ok=True)
        
        safe_company = re.sub(r'[^\w\s-]', '', company_name).strip().replace(' ', '_')
        timestamp = now.strftime('%H-%M-%S')
        
        # Save Screenshot
        png_filename = f"{timestamp}_linkedin_{safe_company}_{error_type}.png"
        png_path = os.path.join(ss_dir, png_filename)
        page.screenshot(path=png_path)
        
        # Save DOM
        html_filename = f"{timestamp}_linkedin_{safe_company}_{error_type}.html"
        html_path = os.path.join(ss_dir, html_filename)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
            
        print(f"    📸 Evidence saved: {png_filename} and {html_filename}")
        return png_path, html_path
    except Exception as e:
        print(f"    ⚠️ Failed to take screenshot: {e}")
        return None, None

def linkedin_apply(matched_path=MATCHED_PATH, debug_mode=False):
    if not os.path.exists(REGISTRY_PATH): return
    with open(REGISTRY_PATH, 'r') as f: registry = json.load(f)
    if not os.path.exists(matched_path): return
    with open(matched_path, 'r') as f: jobs = json.load(f).get("approved_jobs", [])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f: context.add_cookies(json.load(f))
        
        page = context.new_page()
        page.set_default_timeout(60000)

        for job in jobs:
            company_name = job.get('company', 'Unknown')
            score = job.get('ai_score', 0)
            print(f"\n🚀 Processing: {company_name} (Score: {score})")
            if score < 80:
                print(f"  ⏭️  Skipping: AI Score is below the 80 threshold.")
                job['status'] = 'skipped_low_score'
                continue

            try:
                page.goto(job['url'], wait_until="domcontentloaded")
            except Exception as e:
                print(f"  ⚠️ Navigation failed: {e}")
                if debug_mode: take_screenshot(page, company_name, "navigation_failed", debug_mode)
                continue
            
            time.sleep(random.uniform(2, 4))
            page.mouse.wheel(0, 500)
            time.sleep(2)

            try:
                if page.locator("button:has-text('Applied')").is_visible(timeout=2000):
                    print(f"  ✅ Already applied to {company_name}. Skipping.")
                    continue
            except: pass

            try:
                # Close the messaging drawer if it's open and blocking UI
                if page.locator(".msg-overlay-bubble-header__control--close-btn").is_visible(timeout=1000):
                    page.locator(".msg-overlay-bubble-header__control--close-btn").click()
            except: pass

            button_clicked = False
            print("  🕵️ Hunting for the Easy Apply button...")

            if not button_clicked:
                try:
                    btn = page.get_by_role("button", name=re.compile("Easy Apply", re.IGNORECASE)).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        print("    🔘 Clicked Easy Apply via ARIA Role")
                        button_clicked = True
                except: pass

            if not button_clicked:
                try:
                    btn = page.locator("button:has-text('Easy Apply')").first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        print("    🔘 Clicked Easy Apply via Text Locator")
                        button_clicked = True
                except: pass

            if not button_clicked:
                try:
                    clicked = page.evaluate("""() => {
                        const elements = Array.from(document.querySelectorAll('button, a, div[role="button"]')).filter(el => el.offsetWidth > 0 && el.offsetHeight > 0);
                        const target = elements.find(el => el.innerText && el.innerText.trim().includes('Easy Apply'));
                        if (target) { target.click(); return true; }
                        return false;
                    }""")
                    if clicked: 
                        print("    🔘 Clicked Easy Apply via JavaScript Injection")
                        button_clicked = True
                except: pass

            if not button_clicked:
                print(f"  ❌ Easy Apply button genuinely not found. Moving on.")
                if debug_mode: 
                    png, html = take_screenshot(page, company_name, "no_apply_button", debug_mode)
                    job['debug_screenshot'] = png
                    job['debug_dom'] = html
                continue

            # Wait for the modal to actually appear before starting the interaction loop
            try:
                page.locator(".artdeco-modal").first.wait_for(state="visible", timeout=12000)
            except Exception:
                print("  ⚠️ Modal did not appear (might be an external redirect or slow connection). Skipping.")
                if debug_mode: 
                    png, html = take_screenshot(page, company_name, "modal_timeout", debug_mode)
                    job['debug_screenshot'] = png
                    job['debug_dom'] = html
                continue

            for loop_count in range(10):
                time.sleep(2)
                
                modal = page.locator(".artdeco-modal")
                if not modal.is_visible():
                    if loop_count > 0:
                        print("  ⚠️ Modal closed unexpectedly.")
                        if debug_mode: take_screenshot(page, company_name, "modal_closed_early", debug_mode)
                    break
                    
                handle_questions(page, registry)
                
                file_input = modal.locator("input[type='file']")
                if file_input.count() > 0:
                    target_resume = job.get('tailored_resume_path', '')
                    if os.path.exists(target_resume):
                        try:
                            file_input.first.set_input_files(target_resume)
                            print(f"    📄 Attached {os.path.basename(target_resume)}.")
                        except Exception as e: 
                            pass
                
                errors = modal.locator(".artdeco-inline-feedback--error")
                if errors.count() > 0:
                    error_text = errors.first.inner_text().strip()
                    print(f"  ⚠️ Form validation error detected: {error_text}")
                    
                    # Attempt a surgical fix for the most common numeric error
                    if "numeric" in error_text.lower() or "number" in error_text.lower():
                        error_field = page.locator(".artdeco-inline-feedback--error").locator("xpath=./preceding-sibling::*[self::input or self::textarea]").last
                        if error_field.count() > 0:
                            current_val = error_field.input_value()
                            clean_val = re.sub(r'[^\d.]', '', current_val)
                            if clean_val and clean_val != current_val:
                                print(f"    🔧 Attempting to fix numeric field: {current_val} -> {clean_val}")
                                error_field.fill(clean_val)
                                time.sleep(1)
                                if modal.locator(".artdeco-inline-feedback--error").count() == 0:
                                    print("    ✅ Error cleared after numeric fix.")
                                    continue # Retry the loop for this step

                    print("  ⚠️ Form validation failing. Skipping job to avoid infinite loop.")
                    if debug_mode: 
                        png, html = take_screenshot(page, company_name, "form_validation_error", debug_mode)
                        job['debug_screenshot'] = png
                        job['debug_dom'] = html
                    break

                # Scroll down the modal content to ensure Next/Submit buttons are visible
                try:
                    page.evaluate("""() => {
                        const modalContent = document.querySelector('.artdeco-modal__content');
                        if (modalContent) modalContent.scrollTo(0, modalContent.scrollHeight);
                    }""")
                    time.sleep(0.5)
                except: pass
                
                print("    ⏳ Holding form for 3 seconds for visual review...")
                time.sleep(3)

                # Back to the explicit text-based button matching that worked!
                next_btn = modal.locator("button:has-text('Next')").first
                review_btn = modal.locator("button:has-text('Review')").first
                submit_btn = modal.locator("button:has-text('Submit application')").first

                if submit_btn.is_visible():
                    print(f"  🏁 Finalizing application for {company_name}...")
                    submit_btn.click(force=True)
                    time.sleep(3)
                    print(f"  ✅ SUCCESS! Application fully submitted.")
                    job['status'] = 'applied'
                    with open(matched_path, 'w') as f:
                        json.dump({"approved_jobs": jobs}, f, indent=4)
                    break
                elif review_btn.is_visible():
                    review_btn.click(force=True)
                    print("    ➡️ Clicked 'Review'")
                elif next_btn.is_visible():
                    next_btn.click(force=True)
                    print("    ➡️ Clicked 'Next'")
                else:
                    print("  ⚠️ Could not find Next/Review/Submit buttons. Exiting modal.")
                    if debug_mode: 
                        png, html = take_screenshot(page, company_name, "no_modal_buttons", debug_mode)
                        job['debug_screenshot'] = png
                        job['debug_dom'] = html
                    break

        browser.close()

if __name__ == "__main__":
    linkedin_apply()
