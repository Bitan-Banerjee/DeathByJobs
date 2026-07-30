# AI Context & Progress Log

## 🚀 Status Summary (2026-05-01)
- **Obj:** Fix Naukri loops, integrate pipeline, resume/process apps.
- **State:** Queue processed. Pipeline complete via `main.py`.
- **Fix:** "Relocation" + `styled_checkbox`/`styled_radio` loops resolved. Use Playwright native `click()` on labels. Abandon JS `.click()` (failed framework updates).
- **Fix (Pipeline):** `playwright_stealth` import error resolved. Use `stealth_sync`.

## 🛠️ Technical Progress
### 1. Checkbox & Radio Button Fix
- **Cause:** Naukri React/SPA needs native label events. JS `element.click()` / `input.checked = true` skip state updates.
- **Solution:** 
  - Native Playwright locators: `page.locator(f"label:text-is('{target}')").first.click(force=True)`.
  - Fallback: `page.locator(f"label:has-text('{target}')").first`.
  - Check `input.checked` via label `for` attr.
  - Stuck detection: 3x same question → `failed_stuck`.

### 2. Main Pipeline
- Verified stealth via `from playwright_stealth import stealth_sync`.
- Resume: `python3 DeathByJobs/scripts/main.py --naukri-only --resume`.
- Successful: CGI, Pylon, TCS, Kazhuga. Gemini API batch logic OK.

### 3. Deep Cleanup & Optimization
- **Relocation:** Moved `GEMINI.md` and `AI_CONTEXT.md` to `DeathByJobs/context/` for a cleaner root directory.
- **Script Renaming:** Renamed `auto_apply.py` to `linkedin_auto_apply.py` and its main function to `linkedin_apply` for consistency. Updated all internal imports and references.
- **Deduplication Logic:** Removed the (Company, Title) "Role Pair" check from `naukri_scraper.py` and `linkedin_scraper.py`. The bot now only deduplicates based on the unique normalized URL, allowing multiple applications to identical roles if they are posted via different URLs/IDs.
- **Folder Cleanup:** Removed redundant `DeathByJobs/scripts/logs/` and merged logging to root `logs/`.
- **Duplicate Removal:** Deleted duplicate `Job_Applications_Tracker.csv` from `scripts/` (Root version is authoritative).
- **Redundant Scripts:** Purged obsolete session debuggers (`auto_save_session.py`, `continuous_save.py`, `reset_applied.py`, `test_session.py`).
- **File System:** Removed `.DS_Store` noise and deleted original markdown backups (`.original.md`) to minimize context.
- **Cache:** Cleared all `__pycache__` and `.pyc` files.
- **Current Data:** `data/failed_applications.json` is confirmed empty.


## 🧠 Future Considerations
- **Missing Apply Buttons:** TCS-style external ATS/inactive posts. Skipped/logged.
- **Performance:** Ensure visibility. Use `.scroll_into_view_if_needed()` or `force=True`.

## 🚨 Latest Run Result
```text
[STAGE 3/4] 🤖 Deploying Naukri Auto-Apply Bot...
...
🚀 Processing: TO THE NEW
  🔘 Clicking Apply...
    DEBUG: Clicked button. Current URL: ...
    📝 Step 1: Found 1 question(s)
    ❓ Question: Are you currently residing in Noida or willing to relocate to Noida?
    💡 Answer: Yes
      🔘 Clicked: Yes
    📨 Clicked Save/Submit
  ✅ Success!
[STAGE 3/4] ✅ Auto-Applying complete.

[STAGE 4/4] 📊 Exporting daily applications to Excel tracker...
[STAGE 4/4] ✅ Export complete.
```
