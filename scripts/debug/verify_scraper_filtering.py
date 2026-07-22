import os
import sys

# Add scripts to path
scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(scripts_dir)

try:
    from linkedin_scraper import load_seen_jobs as load_li_seen
    from naukri_scraper import load_seen_jobs as load_nk_seen
    
    print("--- Testing LinkedIn Filter ---")
    li_seen = load_li_seen()
    li_test_url = "https://www.linkedin.com/jobs/view/4409922356/" # TCS job from tracker
    if li_test_url in li_seen:
        print(f"✅ SUCCESS: LinkedIn filter caught applied job: {li_test_url}")
    else:
        print(f"❌ FAILURE: LinkedIn filter missed applied job.")

    print("\n--- Testing Naukri Filter ---")
    nk_seen = load_nk_seen()
    nk_test_url = "https://www.naukri.com/job-listings-data-engineer-vipsa-talent-solutions-private-limited-bengaluru-3-to-6-years-060526927029"
    if nk_test_url in nk_seen:
        print(f"✅ SUCCESS: Naukri filter caught applied job: {nk_test_url}")
    else:
        print(f"❌ FAILURE: Naukri filter missed applied job.")
        
except Exception as e:
    print(f"Error during verification: {e}")
