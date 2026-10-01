"""Configuration module for the Job Alert Bot."""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


def _str_to_bool(val: str, default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "y", "on")


@dataclass
class Config:
    # Search parameters
    search_term: str = os.getenv("SEARCH_TERM", "Frontend Developer")
    location: str = os.getenv("LOCATION", "Indonesia")
    hours_old: int = int(os.getenv("HOURS_OLD", "24"))
    results_wanted: int = int(os.getenv("RESULTS_WANTED", "15"))
    is_remote: bool = _str_to_bool(os.getenv("IS_REMOTE", "false"))
    country_indeed: str = os.getenv("COUNTRY_INDEED", "indonesia")

    # Scraper sites configuration
    # Options: linkedin, indeed (comma-separated, e.g. "linkedin,indeed" or "linkedin")
    site_names: List[str] = field(default_factory=lambda: [
        s.strip().lower()
        for s in os.getenv("SITE_NAMES", "linkedin,indeed").split(",")
        if s.strip()
    ])

    # Fallback to Indeed if LinkedIn fails or returns 0 results
    enable_indeed_fallback: bool = _str_to_bool(os.getenv("ENABLE_INDEED_FALLBACK", "true"), default=True)

    # Discord Webhook
    discord_webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    # Deduplication storage
    seen_jobs_file: str = os.getenv("SEEN_JOBS_FILE", "seen_jobs.json")
    max_seen_history: int = int(os.getenv("MAX_SEEN_HISTORY", "1000"))

    # Operational settings
    delay_between_alerts: float = float(os.getenv("DELAY_BETWEEN_ALERTS", "1.0"))
    dry_run: bool = _str_to_bool(os.getenv("DRY_RUN", "false"))


config = Config()
