import os
import sys
import csv
import json
import subprocess
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError
from apscheduler import events as aps_events
import atexit

# --- PATH SETUP ---
BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(BRIDGE_DIR)) # Adjusted to be project root
SRC_DIR = os.path.join(BASE_DIR, "src")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, SRC_DIR)
# Correctly locate the script directory
SCRIPTS_DIR = os.path.join(BASE_DIR, "src", "automation")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# --- Config / onboarding helpers ------------------------------------------------
from utils.config_loader import (
    load_profile,
    load_providers,
    save_profile,
    save_providers,
    profile_exists,
    providers_exists,
    is_configured,
    get_env_key_name,
    get_resume_paths,
    DEFAULT_PROFILE,
    DEFAULT_PROVIDERS,
)
from utils.resume_parser import derive_base_resume


app = FastAPI(title="AI Job Pipeline API")

# Serve UI
UI_DIR = os.path.join(BRIDGE_DIR, "ui")
if os.path.exists(UI_DIR):
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

active_process = None
scheduler = BackgroundScheduler(timezone="Asia/Kolkata", job_defaults={"misfire_grace_time": 3600})

# ── Models ────────────────────────────────────────────────────────────────────

class PipelineParams(BaseModel):
    jobs: int = 25
    target: int = 50
    max_loops: int = 4
    mode: str = "quota"  # "quota" | "single_test" | "resume"

class CronUpdate(BaseModel):
    job_id: str          # job_id from schedule.json
    enabled: bool | None = None
    hour: int | None = None
    minute: int | None = None

class OnboardingPayload(BaseModel):
    candidate_name: str
    candidate_email: str
    target_role: str
    experience_years: int
    experience_range: str
    notice_period: str
    serving_notice: bool
    core_skills: list[str]
    linkedin_keyword: str
    naukri_keyword: str
    location: str
    match_variance: str
    title_red_flags: list[str]
    excluded_companies: list[str]
    current_employer: str
    provider: str
    api_key: str
    linkedin_email: str = ""
    linkedin_password: str = ""
    naukri_email: str = ""
    naukri_password: str = ""
    analogous_skills: dict | None = None

# ── Scheduled Job Functions ───────────────────────────────────────────────────

def _launch_pipeline(cmd: list[str]) -> dict:
    """Shared launch helper for both manual Start and scheduled runs.
    Writes to logs/api_run.log so dashboard/status/logs stay consistent."""
    global active_process
    if active_process is not None and active_process.poll() is None:
        return {"status": "already_running", "pid": active_process.pid}
    if _pipeline_is_running_from_lock():
        pid = _get_lock_pid()
        return {"status": "already_running", "pid": pid}

    log_path = os.path.join(BASE_DIR, "logs", "api_run.log")
    log_file = open(log_path, "w")
    active_process = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT)
    return {"status": "started", "pid": active_process.pid}


def run_main_pipeline():
    """Runs the main job application pipeline (scheduled or manual)."""
    print("Scheduler: Kicking off main pipeline run.")
    main_script_path = os.path.join(BASE_DIR, "src", "automation", "main.py")
    cmd = [
        sys.executable, "-u", main_script_path,
        "--target", "50", "--max-loops", "4", "--jobs", "25"
    ]
    _launch_pipeline(cmd)


def _job_listener(event):
    """APScheduler event listener for debugging missed/executed jobs."""
    if hasattr(event, 'exception') and event.exception:
        print(f"Scheduler: Job '{event.job_id}' crashed: {event.exception}")
    else:
        code = getattr(event, 'code', None)
        if code == aps_events.EVENT_JOB_EXECUTED:
            print(f"Scheduler: Job '{event.job_id}' executed successfully.")
        elif code == aps_events.EVENT_JOB_ERROR:
            print(f"Scheduler: Job '{event.job_id}' errored.")
        elif code == aps_events.EVENT_JOB_MISSED:
            print(f"Scheduler: Job '{event.job_id}' MISSED at {event.scheduled_run_time}.")
        elif code == aps_events.EVENT_JOB_SUBMITTED:
            print(f"Scheduler: Job '{event.job_id}' submitted.")

scheduler.add_listener(_job_listener, aps_events.EVENT_ALL)


def _check_scheduled_jobs():
    """Watchdog: fires any job whose scheduled minute has arrived.
    This guards against APScheduler cron misses when the process is launched
    by the native app or the machine sleeps/wakes."""
    if get_process_status() == "running":
        return

    now = datetime.now(scheduler.timezone)
    current_key = (now.hour, now.minute)

    with open(SCHEDULE_FILE, 'r') as f:
        config = json.load(f)

    for job_info in config.get("jobs", []):
        if not job_info.get("enabled"):
            continue
        if (job_info["hour"], job_info["minute"]) != current_key:
            continue
        job_id = job_info["id"]
        last_key = _last_fired_minute.get(job_id)
        if last_key == current_key:
            continue
        func_name = job_info["func"].rsplit(':', 1)[1]
        func = globals().get(func_name)
        if func:
            print(f"Scheduler watchdog: Firing '{job_id}' at {now.strftime('%H:%M:%S')}.")
            func()
            _last_fired_minute[job_id] = current_key


_last_fired_minute: dict[str, tuple[int, int]] = {}


def run_naukri_update():
    """Runs the daily Naukri resume update."""
    print("Scheduler: Kicking off Naukri resume update.")
    cmd = [sys.executable, "-u", os.path.join(BASE_DIR, "src", "utils", "naukri_resume_uploader.py")]
    log_path = os.path.join(BASE_DIR, "logs", "daily_naukri_update.log")
    with open(log_path, "w") as log_file:
        subprocess.Popen(cmd, cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT)


# ── Scheduler Management ──────────────────────────────────────────────────────

SCHEDULE_FILE = os.path.join(BASE_DIR, "data", "schedule.json")

def load_schedule():
    """Loads schedule from JSON file and configures the scheduler."""
    if not os.path.exists(SCHEDULE_FILE):
        return
    with open(SCHEDULE_FILE, 'r') as f:
        config = json.load(f)

    for job_info in config.get("jobs", []):
        if job_info.get("enabled"):
            trigger = CronTrigger(hour=job_info["hour"], minute=job_info["minute"], timezone=scheduler.timezone)
            
            # Dynamically get the function from its path string
            module_path, func_name = job_info["func"].rsplit(':', 1)
            
            # This is a simple way; for robustness, you might import the module
            # but given our context, we know the functions are in this file.
            func = globals().get(func_name)

            if func:
                scheduler.add_job(
                    func,
                    trigger=trigger,
                    id=job_info["id"],
                    name=job_info["name"],
                    replace_existing=True
                )
                print(f"Scheduler: Loaded '{job_info['id']}' for {job_info['hour']:02d}:{job_info['minute']:02d} IST")

@app.on_event("startup")
def startup_event():
    load_schedule()
    scheduler.start()
    scheduler.add_job(_check_scheduled_jobs, "interval", minutes=1, id="scheduler_watchdog", replace_existing=True)
    atexit.register(lambda: scheduler.shutdown())

LOCK_FILE = os.path.join(BASE_DIR, "app.lock")

def _pipeline_is_running_from_lock():
    """Detect if src/automation/main.py is already running via its lock file."""
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, "r") as f:
            pid = int(f.read().strip())
        # Check if the process is actually alive
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, ProcessLookupError):
        # Stale lock
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass
        return False

def get_process_status():
    # If the API itself started a process, trust that first.
    if active_process is not None:
        if active_process.poll() is None:
            return "running"
        return "finished"
    # Otherwise, check for a pre-existing pipeline session.
    if _pipeline_is_running_from_lock():
        return "running"
    return "idle"

# ── Pipeline endpoints ────────────────────────────────────────────────────────

@app.get("/")
async def root():
    index = os.path.join(UI_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "AI Pipeline API running. UI not found."}

def _get_lock_pid():
    if not os.path.exists(LOCK_FILE):
        return None
    try:
        with open(LOCK_FILE, "r") as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None

@app.get("/status")
async def status():
    status = get_process_status()
    pid = active_process.pid if active_process else _get_lock_pid()
    return {"status": status, "pid": pid}


@app.post("/start_job")
async def start_job_simple():
    """Starts the pipeline with default parameters."""
    return await start_pipeline(PipelineParams())


@app.post("/start")
async def start_pipeline(params: PipelineParams):
    if get_process_status() == "running":
        raise HTTPException(status_code=400, detail="Pipeline already running.")

    main_script_path = os.path.join(BASE_DIR, "src", "automation", "main.py")
    cmd = [sys.executable, "-u", main_script_path]
    if params.mode == "quota":
        cmd.extend(["--target", str(params.target), "--max-loops", str(params.max_loops), "--jobs", str(params.jobs)])
    elif params.mode == "single_test":
        cmd.extend(["--jobs", str(params.jobs), "--max-loops", "1"])
    elif params.mode == "resume":
        cmd.append("--resume")

    result = _launch_pipeline(cmd)
    return {"status": result["status"], "pid": result["pid"]}

def _kill_orphan_browsers():
    """Best-effort cleanup of lingering Chromium/Playwright processes."""
    try:
        subprocess.run(
            ["pkill", "-f", "Chromium"],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass

@app.post("/stop")
async def stop_pipeline():
    global active_process
    if active_process and active_process.poll() is None:
        active_process.terminate()
        try:
            active_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            active_process.kill()
            active_process.wait()
        active_process = None
        _kill_orphan_browsers()
        return {"status": "stopped"}
    raise HTTPException(status_code=400, detail="No active pipeline to stop.")

def _latest_log_path():
    """Pick the best available log file for the current or last pipeline run."""
    # 1. API-launched run log
    api_log = os.path.join(BASE_DIR, "logs", "api_run.log")
    if os.path.exists(api_log) and os.path.getsize(api_log) > 0:
        return api_log

    # 2. Mirror of the running pipeline's output
    latest_md = os.path.join(BASE_DIR, "latest_run.md")
    if os.path.exists(latest_md) and os.path.getsize(latest_md) > 0:
        return latest_md

    # 3. Most recent timestamped log under logs/YYYY/MM/DD/
    log_root = os.path.join(BASE_DIR, "logs")
    candidates = []
    for root, _, files in os.walk(log_root):
        for f in files:
            if f.startswith("run_") and f.endswith(".log"):
                candidates.append(os.path.join(root, f))
    if candidates:
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    return None

@app.get("/logs")
async def get_logs(lines: int = 100):
    log_path = _latest_log_path()
    if not log_path or not os.path.exists(log_path):
        return {"lines": []}
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    # Strip markdown code-fence markers that may appear in latest_run.md
    cleaned = []
    for line in all_lines:
        stripped = line.rstrip()
        if stripped in ("```text", "```"):
            continue
        cleaned.append(stripped)
    return {"lines": cleaned[-lines:]}

# ── Report endpoint ───────────────────────────────────────────────────────────

@app.get("/report")
async def get_report():
    data = {
        "linkedin": {"scraped": 0, "matched": 0, "applied": 0, "failed": 0},
        "naukri":   {"scraped": 0, "matched": 0, "applied": 0, "failed": 0},
    }

    # Prefer the persistent last-run snapshot written by export_tracker.py.
    # This ensures the dashboard shows only the metrics from the most recent pipeline run.
    last_run_report = os.path.join(BASE_DIR, "data", "last_run_report.json")
    if os.path.exists(last_run_report):
        try:
            with open(last_run_report, 'r') as f:
                report = json.load(f)
            for platform in ["linkedin", "naukri"]:
                if platform in report:
                    data[platform] = report[platform]
            return {"linkedin": data["linkedin"], "naukri": data["naukri"]}
        except Exception:
            pass

    # Fallback: read ephemeral intermediate JSON files from the latest run.
    for platform in ["linkedin", "naukri"]:
        p = os.path.join(BASE_DIR, "data", f"{platform}_jobs.json")
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                data[platform]["scraped"] = len(d) if isinstance(d, list) else len(d.get("jobs", []))
            except: pass

    for platform in ["linkedin", "naukri"]:
        p = os.path.join(BASE_DIR, "data", f"{platform}_matched_jobs.json")
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                approved = d.get("approved_jobs", []) if isinstance(d, dict) else []
                data[platform]["matched"] = len(approved)
                applied = sum(1 for j in approved if j.get("status") == "applied")
                skipped = sum(1 for j in approved if j.get("status") == "skipped_low_score")
                data[platform]["applied"] = applied
                data[platform]["failed"] = len(approved) - applied - skipped
            except: pass

    return {"linkedin": data["linkedin"], "naukri": data["naukri"]}


# ── Cron endpoints ────────────────────────────────────────────────────────────

@app.get("/cron")
async def list_cron_jobs():
    """Returns the schedule from the JSON file merged with live scheduler next run times."""
    if not os.path.exists(SCHEDULE_FILE):
        return {"jobs": []}
    with open(SCHEDULE_FILE, 'r') as f:
        config = json.load(f)

    live_jobs = {job.id: job for job in scheduler.get_jobs()}
    for job_info in config.get("jobs", []):
        live = live_jobs.get(job_info["id"])
        if live and live.next_run_time:
            job_info["next_run"] = live.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        else:
            job_info.pop("next_run", None)
    return config

@app.patch("/cron")
async def update_cron_job(update: CronUpdate):
    """Updates a job in the schedule JSON and in the live scheduler."""
    if not os.path.exists(SCHEDULE_FILE):
        raise HTTPException(status_code=404, detail="Schedule file not found.")

    with open(SCHEDULE_FILE, 'r') as f:
        config = json.load(f)

    job_found = False
    for job_info in config.get("jobs", []):
        if job_info["id"] == update.job_id:
            # Update the dictionary with new values
            if update.enabled is not None:
                job_info["enabled"] = update.enabled
            if update.hour is not None:
                job_info["hour"] = update.hour
            if update.minute is not None:
                job_info["minute"] = update.minute
            
            job_found = True
            
            # Now, update the live scheduler
            existing_job = scheduler.get_job(job_info["id"])
            now = datetime.now(scheduler.timezone)
            scheduled_today = now.replace(hour=job_info["hour"], minute=job_info["minute"], second=0, microsecond=0)
            run_now = False
            func = None
            
            if job_info["enabled"]:
                trigger = CronTrigger(hour=job_info["hour"], minute=job_info["minute"], timezone=scheduler.timezone)
                func_path = job_info["func"]
                func_name = func_path.rsplit(':', 1)[1]
                func = globals().get(func_name)
                
                if existing_job:
                    scheduler.reschedule_job(job_info["id"], trigger=trigger)
                    updated_job = scheduler.get_job(job_info["id"])
                    print(f"Scheduler: Rescheduled '{job_info['id']}' to {job_info['hour']:02d}:{job_info['minute']:02d} IST (next: {updated_job.next_run_time})")
                else:
                    if func:
                        scheduler.add_job(
                            func,
                            trigger=trigger,
                            id=job_info["id"],
                            name=job_info["name"],
                            replace_existing=True
                        )
                        print(f"Scheduler: Added '{job_info['id']}' at {job_info['hour']:02d}:{job_info['minute']:02d} IST")
                    else:
                        print(f"Scheduler: Could not add '{job_info['id']}' — function '{func_path}' not found.")
                        raise HTTPException(status_code=500, detail=f"Function '{func_path}' not found.")
                
                # If the saved time has already passed today, run it once now so the user
                # does not have to wait until tomorrow.
                if scheduled_today <= now:
                    run_now = True
            elif existing_job:
                scheduler.remove_job(job_info["id"])
                print(f"Scheduler: Disabled '{job_info['id']}'")

            break
    
    if not job_found:
        raise HTTPException(status_code=404, detail=f"Job with id '{update.job_id}' not found.")

    # Write changes back to the file
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Fire once if the scheduled time was already passed when the user saved it.
    if run_now and func:
        print(f"Scheduler: Saved time {job_info['hour']:02d}:{job_info['minute']:02d} already passed today; running '{job_info['id']}' now.")
        scheduler.add_job(func, trigger='date', run_date=datetime.now(scheduler.timezone), id=f"{job_info['id']}_catchup", replace_existing=True)
        
    # Find the updated job to return
    updated_job_to_return = next((job for job in config["jobs"] if job["id"] == update.job_id), None)

    return {"status": "updated", "job": updated_job_to_return}


@app.get("/scheduler")
async def scheduler_status():
    """Return the list of scheduled jobs and their next run time."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return {"jobs": jobs, "timezone": str(scheduler.timezone), "running": scheduler.running}


@app.post("/scheduler/reload")
async def scheduler_reload():
    """Reload the schedule from the JSON file without restarting the backend.
    If a job's scheduled time has already passed today, it runs immediately."""
    for job in scheduler.get_jobs():
        job.remove()
    load_schedule()

    now = datetime.now(timezone.utc).astimezone()
    triggered = []
    for job in scheduler.get_jobs():
        if job.next_run_time and job.next_run_time < now:
            print(f"Scheduler: {job.name} was scheduled for {job.next_run_time} (already passed). Running now.")
            scheduler.modify_job(job.id, next_run_time=now)
            triggered.append(job.id)

    return {"status": "reloaded", "jobs": len(scheduler.get_jobs()), "triggered_immediately": triggered}


@app.post("/scheduler/trigger")
async def scheduler_trigger():
    """Immediately trigger the main pipeline run."""
    run_main_pipeline()
    return {"status": "triggered"}


# ── Onboarding / Config endpoints ─────────────────────────────────────────────

@app.get("/onboarding/status")
async def onboarding_status():
    """Return whether the tool has been configured for this user."""
    return {
        "configured": is_configured(),
        "profile_exists": profile_exists(),
        "providers_exists": providers_exists(),
    }


@app.get("/config")
async def get_config():
    """Return current profile and provider config (without API keys)."""
    profile = load_profile()
    providers = load_providers()
    # Sanitize keys from returned providers
    safe_providers = json.loads(json.dumps(providers))
    for cfg in safe_providers.get("providers", {}).values():
        cfg.pop("api_key_env", None)
        cfg.pop("api_key", None)
    return {
        "profile": profile,
        "providers": safe_providers,
        "resume_path": str(get_resume_paths()[0]),
        "base_resume_path": str(get_resume_paths()[1]),
        "linkedin_email": os.getenv("LINKEDIN_EMAIL", ""),
        "naukri_email": os.getenv("NAUKRI_EMAIL", ""),
    }


@app.post("/onboarding")
async def save_onboarding(payload: OnboardingPayload):
    """Save candidate profile, provider choice, and API key."""
    excluded = list(payload.excluded_companies)
    if payload.current_employer and payload.current_employer.strip():
        current = payload.current_employer.strip()
        if current not in excluded:
            excluded.append(current)

    # Build analogous skills map if not provided, based on variance choice
    analogous = payload.analogous_skills or {
        "Azure": "AWS",
        "GCP": "AWS",
        "Databricks": "Glue",
        "Snowflake": "Redshift",
        "Informatica": "ETL/ELT",
    }

    custom_flags = [f.strip().lower() for f in payload.title_red_flags if f.strip()]
    default_flags = DEFAULT_PROFILE["filters"]["title"]["red_flags"]
    merged_red_flags = list(dict.fromkeys(default_flags + custom_flags))

    profile = {
        "candidate": {
            "name": payload.candidate_name,
            "email": payload.candidate_email,
        },
        "target_profile": {
            "role": payload.target_role,
            "experience_years": payload.experience_years,
            "experience_range": payload.experience_range,
            "notice_period": payload.notice_period,
            "serving_notice": payload.serving_notice,
            "core_skills": payload.core_skills,
        },
        "search": {
            "linkedin_keyword": payload.linkedin_keyword,
            "naukri_keyword": payload.naukri_keyword,
            "location": payload.location,
        },
        "filters": {
            "match_variance": payload.match_variance,
            "title": {
                **DEFAULT_PROFILE["filters"]["title"],
                "red_flags": merged_red_flags,
            },
            "company": {
                "excluded": excluded,
                "current_employer": payload.current_employer.strip(),
            },
            "applicants": {"max": 100},
            "dealbreakers": [
                f"DB1: Job strictly requires MORE than {payload.experience_years} years of experience.",
                "DB2: Job requires designing/training AI/ML models or advanced Statistical/Mathematical modeling. (NOTE: Building data pipelines, cleaning data, or writing ETL workflows to support AI teams is a PERFECT match and should NOT be rejected).",
                "DB3: Job requires a cloud platform or tool the candidate does not have and does not list as analogous.",
                "DB4: The hiring company is the candidate's current employer.",
                "DB5: The hiring company is in the explicit excluded-companies list.",
            ],
        },
        "application": {
            "experience_years": payload.experience_years,
            "availability": DEFAULT_PROFILE["application"]["availability"],
            "analogous_skills": analogous,
        },
        "resume": DEFAULT_PROFILE["resume"],
    }

    providers = json.loads(json.dumps(DEFAULT_PROVIDERS))
    providers["active_provider"] = payload.provider
    for name, cfg in providers["providers"].items():
        cfg["enabled"] = (name == payload.provider)

    save_profile(profile)
    save_providers(providers)

    # Persist API key to .env using the correct env var name for the provider.
    # If the submitted key is empty (e.g. settings page left it blank), keep
    # the existing key instead of overwriting it with an empty value.
    env_key = providers["providers"][payload.provider].get("api_key_env", f"{payload.provider.upper()}_API_KEY")
    if payload.api_key.strip():
        _write_env_key(env_key, payload.api_key)
        # Also inject into the current process so resume derivation can use it immediately
        # without requiring a backend restart.
        os.environ[env_key] = payload.api_key

    # Persist platform credentials to .env
    if payload.linkedin_email.strip():
        _write_env_key("LINKEDIN_EMAIL", payload.linkedin_email)
    if payload.linkedin_password.strip():
        _write_env_key("LINKEDIN_PASSWORD", payload.linkedin_password)
    if payload.naukri_email.strip():
        _write_env_key("NAUKRI_EMAIL", payload.naukri_email)
    if payload.naukri_password.strip():
        _write_env_key("NAUKRI_PASSWORD", payload.naukri_password)

    return {"status": "saved", "provider": payload.provider, "env_key": env_key}


def _write_env_key(key_name: str, key_value: str) -> None:
    """Write or update a single key in the project .env file."""
    env_path = os.path.join(BASE_DIR, ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key_name}="):
            lines[i] = f"{key_name}={key_value}\n"
            updated = True
            break

    if not updated:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"{key_name}={key_value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


@app.post("/upload-resume")
async def upload_resume_file(payload: dict):
    """Accept a resume.docx upload as base64 from the onboarding UI."""
    import base64
    b64_data = payload.get("data", "")
    filename = payload.get("filename", "resume.docx")
    if not b64_data:
        raise HTTPException(status_code=400, detail="No file data provided.")

    resume_path, _ = get_resume_paths()
    with open(resume_path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return {"status": "saved", "path": str(resume_path), "filename": filename}


@app.post("/derive-resume")
async def derive_resume():
    """Derive base_resume.md from the uploaded resume.docx."""
    result = derive_base_resume(force=True)
    if result is None:
        raise HTTPException(status_code=400, detail="resume.docx not found; upload first.")
    return {"status": "derived", "path": str(result)}
