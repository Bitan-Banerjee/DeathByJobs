import os
import json
import time
import sys
from playwright.sync_api import sync_playwright

# Project structure
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
SESSION_FILE = os.path.join(BASE_DIR, 'data', 'naukri_session.json')
REGISTRY_PATH = os.path.join(BASE_DIR, 'data', 'job_qa_registry.json')

sys.path.append(os.path.dirname(SCRIPT_DIR))
try:
    from linkedin_auto_apply import get_batch_answers_from_gemini
except ImportError:
    def get_batch_answers_from_gemini(q, r): return {}

def get_registry():
    if not os.path.exists(REGISTRY_PATH): return {}
    with open(REGISTRY_PATH, 'r') as f: return json.load(f)

def save_registry(registry):
    with open(REGISTRY_PATH, 'w') as f: json.dump(registry, f, indent=4)

def extract_questions_chatbot(page):
    return page.evaluate("""() => {
        const drawer = document.querySelector('.chatbot_DrawerContentWrapper');
        if (!drawer) return null;
        
        // Find the LAST bot message (the current question)
        const botMsgs = Array.from(drawer.querySelectorAll('.botMsg span'));
        if (botMsgs.length === 0) return null;
        const lastMsg = botMsgs[botMsgs.length - 1].innerText.trim();
        
        // Check for pills/options/checkboxes
        const pills = Array.from(drawer.querySelectorAll('.chipMsg, .pill, .optionVal, .chatbot_Chip, .ssrc__label, .mcc__label'))
            .map(p => p.innerText.trim())
            .filter(t => t.length > 0);
            
        return { question: lastMsg, pills: pills };
    }""")

def apply_job(url):
    print(f"\n🚀 APPLYING: {url}")
    registry = get_registry()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'r') as f: context.add_cookies(json.load(f))
        
        page = context.new_page()
        # CAPTURE CONSOLE
        page.on("console", lambda msg: print(f"  🖥️ CONSOLE: {msg.text}"))
        
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(5)

        # Remove Overlays
        page.evaluate("""() => {
            const selectors = ['.styles_recom-container', '#ni-gnb-header-section', '.styles_gnb-container', '.img-overlay', '.secondary-header'];
            selectors.forEach(s => document.querySelector(s)?.remove());
        }""")
        
        # Click Apply
        apply_btn = page.locator("#apply-button, .apply-button").first
        if apply_btn.count() == 0:
            print("❌ Apply button not found (Already applied?)")
            browser.close(); return
            
        apply_btn.click(force=True)
        print("🔘 Clicked Apply.")
        time.sleep(5)
        
        # Chatbot Loop
        for round in range(10):
            # Check success
            success_info = page.evaluate("""() => {
                const text = document.body.innerText.toLowerCase();
                const hasIframe = Array.from(document.querySelectorAll('iframe')).some(f => f.src.includes('saveApply') && f.src.includes('%3A200'));
                return text.includes('successfully applied') || text.includes('already applied') || hasIframe;
            }""")
            if success_info:
                print("✅ SUCCESS!")
                browser.close(); return True

            # Dump HTML for debugging
            drawer_html = page.evaluate("""() => document.querySelector('.chatbot_DrawerContentWrapper')?.outerHTML || "MISSING" """)
            with open(os.path.join(BASE_DIR, 'logs', f"debug_drawer_round_{round+1}.html"), "w") as f:
                f.write(drawer_html)
                
            data = extract_questions_chatbot(page)
            if not data:
                print("🏁 No more questions (Drawer closed or vanished).")
                break
                
            print(f"❓ Q: {data['question']}")
            key = f"{data['question']} (Options: {', '.join(data['pills'])})" if data['pills'] else data['question']
            
            if key not in registry:
                print("🧠 Fetching answer from Gemini...")
                ans_map = get_batch_answers_from_gemini([key], registry)
                if ans_map: registry.update(ans_map); save_registry(registry)
            
            ans = str(registry.get(key, data['pills'][0] if data['pills'] else "Yes")).strip()
            print(f"💡 A: {ans}")
            
            # Answer input
            if data['pills']:
                # Click the pill/checkbox
                page.evaluate("""(ans) => {
                    const selectors = ['.chipMsg', '.pill', '.optionVal', '.chatbot_Chip', '.ssrc__label', '.mcc__label', '.ssrc__radio', '.mcc__checkbox'];
                    const targets = Array.from(document.querySelectorAll(selectors.join(',')));
                    const match = targets.find(t => t.innerText.trim().toLowerCase() === ans.toLowerCase() || 
                                               t.getAttribute('value')?.toLowerCase() === ans.toLowerCase());
                    
                    if (match) {
                        match.scrollIntoView({behavior: 'instant', block: 'center'});
                        
                        // Check if already selected
                        let input = (match.tagName === 'INPUT') ? match : match.querySelector('input');
                        if (!input) {
                            const forId = match.getAttribute('for');
                            if (forId) input = document.getElementById(forId);
                        }
                        if (!input) input = match.parentElement.querySelector('input');
                        
                        if (input && input.checked) return;

                        // THE FIX: Click the INPUT if possible, otherwise the label, 
                        // but use a sequence that triggers frameworks.
                        const clickTarget = input || match;

                        clickTarget.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                        clickTarget.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
                        clickTarget.click();
                        
                        if (input && !input.checked) {
                            input.checked = true;
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }
                }""", ans)
            else:
                # Type in textArea
                page.evaluate("""(ans) => {
                    const el = document.querySelector('.textArea, [contenteditable="true"]');
                    if (el) {
                        el.focus();
                        el.innerHTML = ans;
                        el.innerText = ans;
                        // Trigger multiple events to satisfy different frameworks
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter' }));
                        el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
                        
                        console.log(`INPUT SET TO: ${el.innerText}`);
                        
                        // Enable Save Button Manually
                        const saveBtn = document.querySelector('.sendMsgbtn_container .send');
                        if (saveBtn) {
                            saveBtn.classList.remove('disabled');
                            saveBtn.removeAttribute('disabled');
                        }
                    }
                }""", ans)
                
            # Click Save/Send
            time.sleep(2)
            # DIAGNOSTIC: Print Save button state
            page.evaluate("""() => {
                const saveBtn = document.querySelector('.sendMsgbtn_container .send');
                if (saveBtn) {
                    console.log(`SAVE BTN: class='${saveBtn.className}', disabled=${saveBtn.hasAttribute('disabled')}`);
                } else {
                    console.log("SAVE BTN NOT FOUND");
                }
            }""")
            save_btn = page.locator(".sendMsgbtn_container .send, button:has-text('Save'), .chatBot-ic-send").last
            if save_btn.is_visible(timeout=3000):
                save_btn.click(force=True)
                print("📨 Sent.")
                
            time.sleep(4)
            
        browser.close()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.naukri.com/job-listings-senior-data-engineer-cgi-information-systems-and-management-consultants-pvt-ltd-chennai-bengaluru-5-to-8-years-290426021671"
    apply_job(url)
