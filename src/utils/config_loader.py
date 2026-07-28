"""Unified config loader for candidate profile and LLM providers.

Keeps personal profile data and provider settings in local files under
config/ so any candidate can use the tool for their own job search.
"""

import os
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
PROFILE_PATH = CONFIG_DIR / "profile.json"
PROVIDERS_PATH = CONFIG_DIR / "providers.json"

# Migration map for old flat profile.json schema
DEFAULT_PROFILE = {
    "candidate": {"name": "", "email": ""},
    "target_profile": {
        "role": "Data Engineer",
        "experience_years": 4,
        "experience_range": "0 to 5 years",
        "notice_period": "30 days",
        "serving_notice": False,
        "core_skills": ["Python", "SQL", "PySpark", "AWS"],
    },
    "search": {
        "linkedin_keyword": "Data Engineer",
        "naukri_keyword": "Data Engineer",
        "location": "India",
    },
    "filters": {
        "match_variance": "moderate",
        "title": {
            "red_flags": [
                "director", "manager", "vp", "lead", "head", "principal",
                "frontend", "front-end", "ui", "ux", "ios", "android", "mobile",
                "react", "angular", "full stack", "full-stack", "qa", "test", "support"
            ],
            "green_flags": [
                "data", "etl", "elt", "aws", "cloud", "backend", "back-end",
                "pipeline", "spark", "pyspark", "analytics", "infrastructure",
                "platform", "python", "sql", "database", "glue", "lambda",
                "redshift", "rds", "warehouse", "airflow", "big data", "bigdata"
            ],
        },
        "company": {"excluded": ["Turing"], "current_employer": ""},
        "applicants": {"max": 100},
        "dealbreakers": [
            "DB1: Job strictly requires MORE than 5 years of experience.",
            "DB2: Job requires designing/training AI/ML models or advanced Statistical/Mathematical modeling.",
            "DB3: Job requires Azure or GCP, but does NOT mention AWS.",
            "DB4: The hiring company is the candidate's current employer.",
            "DB5: The hiring company is in the explicit excluded-companies list."
        ],
    },
    "application": {
        "experience_years": 4,
        "availability": {
            "morning": "Before 11:00 AM",
            "afternoon": "2:00 PM - 4:30 PM",
            "evening": "After 7:00 PM",
        },
        "analogous_skills": {
            "Azure": "AWS",
            "GCP": "AWS",
            "Databricks": "Glue",
            "Snowflake": "Redshift",
            "Informatica": "ETL/ELT",
        },
    },
    "resume": {
        "generic_docx": "resume.docx",
        "derived_md": "base_resume.md",
    },
}

DEFAULT_PROVIDERS = {
    "active_provider": "gemini",
    "providers": {
        "gemini": {
            "enabled": True,
            "api_key_env": "GEMINI_API_KEY",
            "models": ["gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"],
            "rpm_limit": 5,
            "delay_between_batches_seconds": 15,
        },
        "openai": {
            "enabled": False,
            "api_key_env": "OPENAI_API_KEY",
            "models": ["gpt-4o-mini", "gpt-4o"],
            "rpm_limit": 10,
        },
        "anthropic": {
            "enabled": False,
            "api_key_env": "ANTHROPIC_API_KEY",
            "models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
            "rpm_limit": 10,
        },
        "local": {
            "enabled": False,
            "api_key_env": "LOCAL_API_KEY",
            "base_url": "http://localhost:11434/v1",
            "models": ["llama3.2", "gemma2"],
            "rpm_limit": 1000,
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _migrate_old_profile(old: dict) -> dict:
    """Convert legacy flat profile.json into the new nested schema."""
    migrated = json.loads(json.dumps(DEFAULT_PROFILE))
    migrated["target_profile"]["role"] = old.get("target_role", migrated["target_profile"]["role"])
    migrated["target_profile"]["candidate_experience"] = old.get("candidate_experience", "")
    migrated["target_profile"]["notice_period"] = old.get("notice_period", migrated["target_profile"]["notice_period"])
    migrated["target_profile"]["serving_notice"] = str(old.get("serving_notice_period", "No")).lower() in ("yes", "true")
    migrated["target_profile"]["core_skills"] = old.get("core_skills", migrated["target_profile"]["core_skills"])
    migrated["filters"]["dealbreakers"] = old.get("dealbreakers", migrated["filters"]["dealbreakers"])

    # Try to infer search keyword from role
    role = migrated["target_profile"]["role"]
    migrated["search"]["linkedin_keyword"] = role
    migrated["search"]["naukri_keyword"] = role

    return migrated


def load_json(path: Path, default: dict) -> dict:
    """Load JSON or return default if missing/invalid."""
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def load_profile() -> dict:
    """Load candidate profile with defaults and migration."""
    raw = load_json(PROFILE_PATH, {})
    if raw.get("target_role") and "target_profile" not in raw:
        raw = _migrate_old_profile(raw)
    return _deep_merge(DEFAULT_PROFILE, raw)


def load_providers() -> dict:
    """Load LLM provider configuration with defaults."""
    return _deep_merge(DEFAULT_PROVIDERS, load_json(PROVIDERS_PATH, {}))


def save_profile(profile: dict) -> None:
    """Persist candidate profile."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def save_providers(providers: dict) -> None:
    """Persist provider configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROVIDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(providers, f, indent=2)


def profile_exists() -> bool:
    return PROFILE_PATH.exists()


def providers_exists() -> bool:
    return PROVIDERS_PATH.exists()


def get_search_keywords(profile: dict | None = None) -> tuple[str, str, str]:
    """Return (linkedin_keyword, naukri_keyword, location)."""
    p = profile or load_profile()
    search = p.get("search", {})
    return (
        search.get("linkedin_keyword", "Data Engineer"),
        search.get("naukri_keyword", "Data Engineer"),
        search.get("location", "India"),
    )


def get_excluded_companies(profile: dict | None = None) -> list[str]:
    """Return merged excluded companies (explicit + current employer)."""
    p = profile or load_profile()
    company_cfg = p.get("filters", {}).get("company", {})
    excluded = list(company_cfg.get("excluded", []))
    current = str(company_cfg.get("current_employer", "")).strip()
    if current and current.lower() not in [e.lower() for e in excluded]:
        excluded.append(current)
    return [e.strip() for e in excluded if e.strip()]


def is_configured() -> bool:
    """Return True if both config files exist."""
    return profile_exists() and providers_exists()


def get_resume_paths(profile: dict | None = None) -> tuple[Path, Path]:
    """Return (generic_docx_path, derived_md_path)."""
    p = profile or load_profile()
    resume_cfg = p.get("resume", {})
    generic = Path(resume_cfg.get("generic_docx", "resume.docx"))
    derived = Path(resume_cfg.get("derived_md", "base_resume.md"))
    if not generic.is_absolute():
        generic = BASE_DIR / generic
    if not derived.is_absolute():
        derived = BASE_DIR / derived
    return generic, derived


def get_env_key_name() -> str:
    """Return the env variable name for the active provider's API key."""
    providers = load_providers()
    active = providers.get("active_provider", "gemini")
    provider_cfg = providers.get("providers", {}).get(active, {})
    return provider_cfg.get("api_key_env", "GEMINI_API_KEY")


def get_api_key() -> str | None:
    """Read API key from environment (loaded from .env elsewhere)."""
    return os.getenv(get_env_key_name(), "")


def get_active_provider_config() -> dict[str, Any]:
    """Return the active provider's config dict."""
    providers = load_providers()
    active = providers.get("active_provider", "gemini")
    return providers.get("providers", {}).get(active, DEFAULT_PROVIDERS["providers"]["gemini"])


if __name__ == "__main__":
    print(json.dumps(load_profile(), indent=2))
    print(json.dumps(load_providers(), indent=2))
