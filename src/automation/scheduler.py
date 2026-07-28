from apscheduler.schedulers.background import BackgroundScheduler
import time
import json
import os
from src.automation.naukri_auto_apply import naukri_apply

# Identify project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'profile.json')

def get_config():
    """Reads the configuration file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def is_scheduler_enabled():
    """Checks if the scheduler is enabled in the config."""
    config = get_config()
    return config.get('scheduler', {}).get('enabled', False)

def run_naukri_job():
    """Wrapper function to run the Naukri auto-apply job."""
    print("Scheduler is running naukri_apply job...")
    try:
        naukri_apply()
        print("naukri_apply job finished.")
    except Exception as e:
        print(f"Error running naukri_apply job: {e}")

def main():
    """
    Initializes and runs the scheduler.
    The scheduler will run in the background and execute jobs as per the schedule.
    """
    if not is_scheduler_enabled():
        print("Scheduler is disabled in the configuration. Exiting.")
        return

    scheduler = BackgroundScheduler()
    
    # Schedule the naukri_apply job to run once a day.
    # You can change the trigger to suit your needs (e.g., interval, cron).
    scheduler.add_job(run_naukri_job, 'interval', days=1)
    
    scheduler.start()
    
    print("Scheduler started. Press Ctrl+C to exit.")
    
    try:
        # Keep the main thread alive.
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    main()
