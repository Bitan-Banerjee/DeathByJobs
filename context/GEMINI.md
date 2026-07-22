# AI Assistant Context & Developer Journal

> **⚠️ SYSTEM INSTRUCTION:**
> Update `context/AI_CONTEXT.md` every 5 prompts. Log decisions, problems, solutions, details. No context loss.

## 🧑‍💻 Developer Profile & Preferences
- **Workflow:** Iterative. Plan first, code second. Wait for approval.
- **Eval:** Optimize for **Recall**. Catch all potential jobs.
- **Infra:** Local open-source (Llama 3.2, Gemma 2). Cloud APIs (Gemini) batched. (Gemini Free Tier: 5 RPM, 20 RPD).
- **HW:** Apple Silicon Mac. Parallel 9B+ = bottleneck. Small/batched = OK.

## 🐛 Debugging Philosophy
- **Diagnose First:** No assumptions on UI failures.
- **Evidence:** `page.screenshot()`, `page.content()`. Analyze before fix.
- **LinkedIn:** `auto_apply.py` auto-saves screenshots on failure to `logs/screenshots/`.
- **Debugging Loop (Naukri Chatbot):**
  1. Standalone `debug_<platform>.py` in `scripts/debug/`.
  2. Aggressive element dump/logging.
  3. Integrate Gemini for end-to-end verification.
  4. **Proof Mandate:** 5 successful apps + verified states before merge. "Form vanished" != success without evidence.
  5. **State Integrity:** Must update failed list + tracker. Task complete only when job removed from failed list.
  6. Autonomous "Fix -> Run -> Evidence -> Fix" cycle.

## 🧠 Job Matching Evolution
### 8. Naukri Chatbot Integration
- **Problem:** Dynamic single-question chatbots using `contenteditable` DIVs + binary "pills". Seen as "ghost panels".
- **Solution:** 
  - Target `.chatbot_MessageContainer`.
  - Priority: pill-clicking over text input for binary.
  - Dispatch `change`, `click` events for state updates.
  - Success indicator: green "Applied" button.

## 📱 Social Media
- **X:** 2 hashtags (#BuildInPublic, #AIAutomation).
- **LinkedIn:** 3-5 hashtags. Suggest @mentions.
- **Opt:** Professional, engaging. No generic tags.

## 🚀 Project Overview
End-to-end job automation:
1. **Sourcing:** `linkedin_scraper.py`.
2. **Filtering:** Match vs Profile/Dealbreakers.
3. **Tailoring:** `tailor_resume.py`.
4. **Applying:** `auto_apply.py`.

## 🧠 Job Matching Evolution
Iterated for Speed, Accuracy, Cost.

### 1-6. Local & Cloud Iterations
- **Llama 3.2 (3B):** Hallucinations, logic failures.
- **Gemma 2 (9B):** Accurate but slow.
- **Gemini Batch:** Fast but "lazy" (needs reasoning).
- **Hybrid Llama:** Multi-agent, CoT. 3B models lack synthesis.
- **Apple Silicon Opt:** Prompt-level batching, prefix caching, MLX framework, quantization (Q4_K_M).
- **MLX Issues:** OOM on 8GB RAM → use `gemma-2-2b-it-4bit` for stability.

### 7. Local Optimizations
- Regex pre-filtering.
- Early exit for non-borderline jobs.
- Async I/O for disk writes.

## 🎯 Next Steps
1. **Direct ATS Scraper:** Greenhouse/Lever (zero-token).
2. **Deep Research:** Pre-interview prep.

## 📈 Recent Upgrades
1. **Profile Decoupling:** `config/profile.json`.
2. **Token-Efficient Scoring:** 0-100 in Gemini filtering.
3. **Playwright PDF Engine:** `tailor_resume.py` rewrite MD -> HTML -> PDF.
4. **Sourcing:** Phrase match, relevance gate, applicant cap (<100).
5. **Orchestrator:** `main.py` loop until 50 apps.
6. **Quarantine:** `failed_applications.json`.
7. **Cleanup:** Root at `/AiAutomation/`.
8. **Naukri Integration:** `naukri_scraper.py`, `naukri_auto_apply.py`.
9. **Multi-Key Router:** Gemini API key fallback.
10. **Static Logger:** `latest_run.md`.
11. Early Rejection: Reject score < 80 in Stage 2.
12. Freelance Exclusion: Explicitly skip 'Turing' (pre-filter and DB5) as it is freelance-only.

## 📜 Core Mandates
- **Approval:** technical strategy + user approval before ANY file changes.
- **Reporting:** Tabular Pipeline Status Report after run. Scan logs for accuracy.

### 📊 Pipeline Status Report (YYYY-MM-DD)
[Table structure preserved]

## 🚨 Latest Run Logs
[Log content preserved]
