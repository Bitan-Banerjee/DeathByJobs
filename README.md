# AI Job Application Pipeline

An end-to-end, fully autonomous AI agent that scrapes, filters, tailors, and applies to jobs on LinkedIn and Naukri.

Built with **Python**, **Playwright**, and a provider-agnostic LLM layer, this pipeline doesn't just "spray and pray." It acts as a highly discerning personal recruiter: it evaluates jobs against your strict dealbreakers, scores them, rewrites your resume for each specific role, and handles dynamic application forms—all while respecting API rate limits and running completely hands-free.

The tool is **profile-first**: any candidate can configure their target role, skills, dealbreakers, preferred LLM provider, and resume, and the pipeline adapts automatically.

---

## Key Features

- **Goal-Oriented Looping Agent:** Tell it to get 50 applications today, and it will continuously scrape, filter, and apply until it hits the target.
- **Zero-Token Sourcing Gatekeepers:** Smart Python regex filters instantly drop junk roles (e.g., Senior, QA, Frontend) and saturated jobs (>100 applicants) *before* wasting AI tokens.
- **A-F AI Scoring System:** Evaluates job descriptions against your `profile.json` dealbreakers and assigns a 0-100 match score.
- **Profile-First Configuration:** All role, skill, company, and matching rules live in `config/profile.json`. Switching from Data Engineer to Frontend, ML, or any other role only requires changing config.
- **Provider-Agnostic LLM Layer:** Use Google Gemini (default and free-tier friendly), OpenAI, Anthropic Claude, or a local Ollama server. The app asks for your preferred provider and API key during onboarding.
- **Playwright PDF Engine:** Bypasses clunky `.docx` manipulation. Uses your chosen LLM to rewrite your `base_resume.md` summary and bullets, injects them into an HTML/CSS template, and prints a pixel-perfect, ATS-optimized PDF for *every single job*.
- **Dynamic Form Solver:** Uses the LLM to read unseen LinkedIn "Easy Apply" questions, answers them on the fly, and saves the answers to a local memory bank (`job_qa_registry.json`) for future use.
- **Smart Checkpointing:** Network dropped? Run with `--resume` and it automatically detects where it left off based on local files.
- **macOS SwiftUI App:** A vintage-styled native app auto-starts the backend, shows live logs, schedules cron jobs, and walks new users through onboarding.

---

## Prerequisites & Installation

You will need Python 3.10+ and an API key from at least one supported LLM provider.

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/AiAutomation.git
cd AiAutomation
```

### 2. Install Dependencies
```bash
pip3 install -r requirements.txt
playwright install chromium
```

---

## Configuration

### macOS App (Recommended)
Open `AiAutomation.app`. It will auto-start the backend and, if no profile exists, open an onboarding form asking for:
- Your target role, experience, location, and skills
- Excluded / current companies
- Skill-match variance (strict / moderate / loose)
- Preferred LLM provider and API key
- Your `resume.docx` file

The app will upload the resume, derive `base_resume.md` automatically, and write all config files.

### Manual Setup
If you prefer not to use the app:

1. Copy `config/profile.example.json` to `config/profile.json` and edit it.
2. Copy `config/providers.example.json` to `config/providers.json` and edit it.
3. Copy `.env.example` to `.env` and add your API key and LinkedIn credentials.
4. Place your `resume.docx` in the project root.
5. Run `python3 -c "from src.utils.resume_parser import derive_base_resume; derive_base_resume()"` to create `base_resume.md`.

*(Note: Do not delete `templates/cv-template.html`, as it provides the CSS styling for your PDFs!)*

---

## Usage

The entire pipeline is orchestrated by `main.py`.

### Standard Run (Goal-Oriented)
To start the agent and have it loop until it successfully applies to 50 jobs today:
```bash
python3 src/automation/main.py --target 50
```

### Quick Test Run
To run a single, small batch without looping:
```bash
python3 src/automation/main.py --jobs 25 --max-loops 1
```

### Resume from Interruption
If the script crashes or your internet drops, don't start over! Use the resume flag to automatically detect local files and pick up exactly where it left off:
```bash
python3 src/automation/main.py --resume
```

### Run via the macOS App
Double-click `AiAutomation.app`. The app auto-starts the FastAPI backend on `127.0.0.1:8000` and opens the dashboard.

### Automating with Cron (macOS/Linux)
To run the bot completely hands-free every morning at 9:00 AM, add this to your `crontab -e`:
```bash
0 9 * * * cd /path/to/AiAutomation && /usr/local/bin/python3 scripts/main.py --target 50
```

---

## How It Works (The 5 Stages)

### [STAGE 1] Sourcing (`linkedin_scraper.py`)
*   Logs into LinkedIn and searches for your target role using exact phrase matching (e.g., `"%22Data Engineer%22"`).
*   Filters for roles posted in the last 72 hours.
*   Applies a fast Python "Title Gatekeeper" to instantly drop frontend, QA, or senior management roles.
*   Drops jobs with >100 applicants to ensure high-probability targets.
*   Saves raw data to `data/jobs.json`.

### [STAGE 2] Filtering (`match_job_gemini.py`)
*   Batches 10 jobs at a time and sends them to the Gemini API.
*   Uses a robust **Fallback Router** (`gemini-flash-latest` -> `gemini-2.5-flash` -> `gemini-flash-lite-latest`) to completely bypass free-tier rate limits and 503 server errors.
*   Evaluates the jobs against your `profile.json` dealbreakers.
*   Approves valid jobs, scores them (0-100), and saves to `data/matched_jobs.json`.

### [STAGE 3] Tailoring (`tailor_resume.py`)
*   Reads your `base_resume.md`.
*   Asks Gemini to rephrase your summary and bullet points to highlight the exact keywords found in the specific job description (without hallucinating new experience).
*   Outputs raw HTML, injects it into `templates/cv-template.html`, and uses Playwright to print an ATS-friendly PDF.
*   Saves the PDF to a time-stamped archive (e.g., `outputs/resumes/2026/04/18/Resume_Company.pdf`).

### [STAGE 4] Applying (`auto_apply.py`)
*   Playwright navigates to the approved jobs scoring >80.
*   Clicks "Easy Apply" and uploads the *specific* tailored PDF for that company.
*   If it encounters a form question it hasn't seen before, it batches the questions, asks Gemini for the answers based on your profile, and saves them to `data/job_qa_registry.json`.
*   Submits the application.

### [STAGE 5] Logging (`export_tracker.py` & `TeeLogger`)
*   Appends the successfully applied jobs to a master database at `Job_Applications_Tracker.csv`.
*   Includes the Date, Company, Title, URL, AI Score, and the absolute path to the PDF used.
*   Throughout the entire process, console output is simultaneously written to `logs/YYYY/MM/DD/run.log` for easy debugging.

---

## Directory Structure

```text
AiAutomation/
├── context/                    # AI Memory (GEMINI.md, AI_CONTEXT.md, Troubleshooting)
├── scripts/
│   ├── main.py                 # Master Orchestrator & Looping Agent
│   ├── linkedin_scraper.py     # Playwright Sourcing
│   ├── match_job_gemini.py     # AI Dealbreaker Filtering
│   ├── tailor_resume.py        # PDF Generation
│   ├── linkedin_auto_apply.py  # Playwright Application Submitter
│   ├── export_tracker.py       # CSV Database Writer
│   └── update_registry.py      # Setup script for QA memory
├── config/
│   └── profile.json            # Target role and AI dealbreakers
├── templates/
│   └── cv-template.html        # CSS styling for generated PDFs
├── data/                       # Ephemeral short-term memory (Gitignored)
│   ├── jobs.json
│   ├── matched_jobs.json
│   ├── job_qa_registry.json
│   └── linkedin_session.json
├── outputs/                    # Time-stamped PDF cold storage (Gitignored)
├── logs/                       # Time-stamped terminal logs (Gitignored)
├── .env                        # Credentials (Gitignored)
├── base_resume.md              # Master CV (Source of Truth)
└── Job_Applications_Tracker.csv# Master application database
```

---

## Disclaimer
This tool automates interactions with LinkedIn. Please use responsibly and ensure you comply with LinkedIn's Terms of Service. The AI generates application answers and resumes on your behalf; you should routinely audit `job_qa_registry.json` and the generated PDFs to ensure absolute accuracy.