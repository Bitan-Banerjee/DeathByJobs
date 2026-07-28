import os
import sys
import csv
import json
import subprocess
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
    cmd = [sys.executable, "-u", os.path.join(BASE_DIR, "src", "automation", "main.py"), "--ci"]
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

def get_process_status():
    if active_process is None:
        return "idle"
    if active_process.poll() is None:
        return "running"
    return "finished"

# ── Pipeline endpoints ────────────────────────────────────────────────────────

@app.get("/")
async def root():
    index = os.path.join(UI_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "AI Pipeline API running. UI not found."}

@app.get("/status")
async def status():
    return {"status": get_process_status(), "pid": active_process.pid if active_process else None}


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
    active_process = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=open(log_path, "w"), stderr=subprocess.STDOUT)
    return {"status": "started", "pid": active_process.pid}

@app.post("/stop")
async def stop_pipeline():
    global active_process
    if active_process and active_process.poll() is None:
        active_process.terminate()
        active_process.wait()
        active_process = None
        return {"status": "stopped"}
    raise HTTPException(status_code=400, detail="No active pipeline to stop.")

@app.get("/logs")
async def get_logs(lines: int = 100):
    log_path = os.path.join(BASE_DIR, "logs", "api_run.log")
    if not os.path.exists(log_path):
        return {"lines": []}
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"lines": [l.rstrip() for l in all_lines[-lines:]]}

# ── Report endpoint ───────────────────────────────────────────────────────────

@app.get("/report")
async def get_report():
    data = {
        "linkedin": {"scraped": 0, "matched": 0, "applied": 0, "failed": 0},
        "naukri":   {"scraped": 0, "matched": 0, "applied": 0, "failed": 0},
    }

    # Scraped counts from intermediate JSON
    for platform in ["linkedin", "naukri"]:
        p = os.path.join(BASE_DIR, "data", f"{platform}_jobs.json")
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                data[platform]["scraped"] = len(d) if isinstance(d, list) else len(d.get("jobs", []))
            except: pass

    # Applied + failed from tracker CSV
    tracker = os.path.join(BASE_DIR, "Job_Applications_Tracker.csv")
    if os.path.exists(tracker):
        try:
            with open(tracker, encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url    = row.get("Job URL", "")
                    status = row.get("Status", "")
                    platform = "linkedin" if "linkedin.com" in url else "naukri" if "naukri.com" in url else None
                    if not platform: continue
                    if "Applied" in status: data[platform]["applied"] += 1
                    elif "Failed" in status: data[platform]["failed"] += 1
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
