import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(BASE_DIR, 'data', 'job_qa_registry.json')

def initialize_registry():
    # Updated defaults based on your specific requirements
    default_qa = {
        "notice_period_days": "90",
        "current_location": "Bengaluru",
        "willing_to_relocate": "Yes",
        "preferred_work_mode": "Work from Office, Hybrid and remote",
        "expected_ctc_lpa": "NA",
        "current_ctc_lpa": "9.5 fixed and 1lpa variable",
        "work_authorization_india": "Yes",
        "sponsorship_required": "No",
        "years_experience_spark": "4",
        "years_experience_aws": "4",
        "years_experience_glue": "4",
        "years_experience_python": "4",
        "years_experience_sql": "4"
    }

    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, 'r') as f:
            try:
                existing = json.load(f)
                default_qa.update(existing)
            except:
                pass

    print("📋 Current Preferences Registry (Press Enter to keep default):")
    for k, v in default_qa.items():
        user_input = input(f"  {k} [{v}]: ").strip()
        if user_input:
            default_qa[k] = user_input

    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(default_qa, f, indent=2)
    print(f"✅ Registry updated at {REGISTRY_PATH}")

if __name__ == "__main__":
    initialize_registry()
