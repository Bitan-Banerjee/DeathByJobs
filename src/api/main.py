import os
import sys
import csv
import json
import subprocess
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

# --- PATH SETUP ---
BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(BRIDGE_DIR)) # Adjusted to be project root
sys.path.insert(0, BASE_DIR)
# Correctly locate the script directory
SCRIPTS_DIR = os.path.join(BASE_DIR, "src", "automation")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


app = FastAPI(title="AI Job Pipeline API")

# Serve UI
UI_DIR = os.path.join(BRIDGE_DIR, "ui")
if os.path.exists(UI_DIR):
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

active_process = None
scheduler = BackgroundScheduler()

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

# ── Scheduled Job Functions ───────────────────────────────────────────────────

def run_main_pipeline():
    """Runs the main job application pipeline."""
    print("Scheduler: Kicking off main pipeline run.")
    main_script_path = os.path.join(BASE_DIR, "src", "automation", "main.py")
    cmd = [
        sys.executable, "-u", main_script_path,
        "--target", "50", "--max-loops", "4", "--jobs", "25"
    ]
    log_path = os.path.join(BASE_DIR, "logs", "daily_run.log")
    with open(log_path, "w") as log_file:
        subprocess.Popen(cmd, cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT)

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
            trigger = CronTrigger(hour=job_info["hour"], minute=job_info["minute"])
            
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

@app.on_event("startup")
def startup_event():
    load_schedule()
    scheduler.start()
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
    global active_process
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

    log_path = os.path.join(BASE_DIR, "logs", "api_run.log")
    log_file = open(log_path, "w")
    active_process = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT)
    return {"status": "started", "pid": active_process.pid}

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
    """Returns the schedule from the JSON file, not the live scheduler state."""
    if not os.path.exists(SCHEDULE_FILE):
        return {"jobs": []}
    with open(SCHEDULE_FILE, 'r') as f:
        config = json.load(f)
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
            
            if job_info["enabled"]:
                trigger = CronTrigger(hour=job_info["hour"], minute=job_info["minute"])
                func = globals().get(job_info["func"].split(':')[1])
                if existing_job:
                    scheduler.reschedule_job(job_info["id"], trigger=trigger)
                else:
                    if func:
                        scheduler.add_job(
                            func,
                            trigger=trigger,
                            id=job_info["id"],
                            name=job_info["name"],
                            replace_existing=True
                        )
            elif existing_job:
                scheduler.remove_job(job_info["id"])

            break
    
    if not job_found:
        raise HTTPException(status_code=404, detail=f"Job with id '{update.job_id}' not found.")

    # Write changes back to the file
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(config, f, indent=2)
        
    # Find the updated job to return
    updated_job_to_return = next((job for job in config["jobs"] if job["id"] == update.job_id), None)

    return {"status": "updated", "job": updated_job_to_return}
