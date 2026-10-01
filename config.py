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


def _parse_list(env_val: str, fallback: List[str]) -> List[str]:
    if not env_val or not env_val.strip():
        return fallback
    # Support both comma-separated and newline-separated
    items = []
    for line in env_val.replace("\r", "").split("\n"):
        for part in line.split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in items:
                items.append(cleaned)
    return items if items else fallback


@dataclass
class Config:
    # Search parameters (Supports single or multiple values)
    search_term: str = os.getenv("SEARCH_TERM", "Frontend Developer")
    search_terms: List[str] = field(default_factory=lambda: _parse_list(
        os.getenv("SEARCH_TERMS", os.getenv("SEARCH_TERM", "Frontend Developer")),
        ["Frontend Developer"],
    ))

    location: str = os.getenv("LOCATION", "Indonesia")
    locations: List[str] = field(default_factory=lambda: _parse_list(
        os.getenv("LOCATIONS", os.getenv("LOCATION", "Indonesia")),
        ["Indonesia"],
    ))

    hours_old: int = int(os.getenv("HOURS_OLD", "24"))
    results_wanted: int = int(os.getenv("RESULTS_WANTED", "15"))
    is_remote: bool = _str_to_bool(os.getenv("IS_REMOTE", "false"))
    country_indeed: str = os.getenv("COUNTRY_INDEED", "indonesia")

    # Company Filter Mode:
    # - "highlight": kirim semua, beri badge & warna khusus pada Top Tier (Big 4, Top Tech, Bank, FMCG)
    # - "only_top": hanya kirim lowongan yang perusahaannya termasuk Top Tier
    # - "all": kirim semua tanpa pembedaan
    filter_mode: str = os.getenv("FILTER_MODE", "highlight").strip().lower()

    # Additional custom top companies (comma-separated, e.g. "Acme Corp, MyStartup")
    custom_companies: List[str] = field(default_factory=lambda: _parse_list(
        os.getenv("CUSTOM_TOP_COMPANIES", ""),
        [],
    ))

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

    def __post_init__(self):
        # Sync search_terms and locations if single fields were changed
        if self.search_term and self.search_term not in self.search_terms:
            self.search_terms.insert(0, self.search_term)
        if self.location and self.location not in self.locations:
            self.locations.insert(0, self.location)


config = Config()
