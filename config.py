"""Configuration loader prioritizing config.json with environment variable overrides."""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("job_alerts.config")

CONFIG_JSON_PATH = os.getenv("CONFIG_JSON_PATH", "config.json")


def _str_to_bool(val: Any, default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "y", "on")


def _load_json_file(filepath: str) -> Dict[str, Any]:
    if not os.path.exists(filepath):
        logger.warning("File '%s' tidak ditemukan. Menggunakan konfigurasi default kosong.", filepath)
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Gagal membaca '%s': %s", filepath, exc)
        return {}


def _parse_list(val: Any, fallback: List[str]) -> List[str]:
    if not val:
        return fallback
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    items = []
    for line in str(val).replace("\r", "").split("\n"):
        for part in line.split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in items:
                items.append(cleaned)
    return items if items else fallback


@dataclass
class Config:
    # 1. Search Settings
    search_terms: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    site_names: List[str] = field(default_factory=list)
    hours_old: int = 24
    results_wanted: int = 15
    is_remote: bool = False
    country_indeed: str = "indonesia"
    enable_indeed_fallback: bool = True

    # 2. Company & Filtering Settings
    filter_mode: str = "highlight"
    top_companies: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    custom_companies: List[str] = field(default_factory=list)

    # 3. Discord Webhook & AI Service (Loaded via Env for Security)
    discord_webhook_url: str = ""
    ai_api_url: str = ""
    ai_api_key: str = ""

    # 4. Storage & Operational Settings
    seen_jobs_file: str = "seen_jobs.json"
    max_seen_history: int = 1000
    delay_between_alerts: float = 1.0
    dry_run: bool = False

    # Backwards-compatible singular fields
    search_term: str = ""
    location: str = ""

    def __post_init__(self):
        # Sync singular and plural fields
        if not self.search_term and self.search_terms:
            self.search_term = self.search_terms[0]
        elif self.search_term and self.search_term not in self.search_terms:
            self.search_terms.insert(0, self.search_term)

        if not self.location and self.locations:
            self.location = self.locations[0]
        elif self.location and self.location not in self.locations:
            self.locations.insert(0, self.location)


def load_config(json_path: str = CONFIG_JSON_PATH) -> Config:
    """Load configuration from config.json and overlay environment variable overrides."""
    data = _load_json_file(json_path)

    search_cfg = data.get("search_settings", {})
    filter_cfg = data.get("filtering", {})
    top_co = data.get("top_companies", {})

    # Priority: Env override if set, else config.json, else default
    env_terms = os.getenv("SEARCH_TERMS", os.getenv("SEARCH_TERM"))
    search_terms = _parse_list(env_terms, search_cfg.get("search_terms", ["Frontend Developer"]))

    env_locs = os.getenv("LOCATIONS", os.getenv("LOCATION"))
    locations = _parse_list(env_locs, search_cfg.get("locations", ["Indonesia"]))

    env_sites = os.getenv("SITE_NAMES")
    site_names = _parse_list(env_sites, search_cfg.get("sites", ["linkedin", "indeed"]))

    hours_old = int(os.getenv("HOURS_OLD", str(search_cfg.get("hours_old", 24))))
    results_wanted = int(os.getenv("RESULTS_WANTED", str(search_cfg.get("results_wanted", 15))))
    is_remote = _str_to_bool(os.getenv("IS_REMOTE", search_cfg.get("is_remote", False)))
    country_indeed = os.getenv("COUNTRY_INDEED", search_cfg.get("country_indeed", "indonesia"))
    enable_indeed_fallback = _str_to_bool(
        os.getenv("ENABLE_INDEED_FALLBACK", search_cfg.get("enable_indeed_fallback", True))
    )

    filter_mode = os.getenv("FILTER_MODE", filter_cfg.get("filter_mode", "highlight")).strip().lower()
    custom_co = _parse_list(os.getenv("CUSTOM_TOP_COMPANIES", ""), top_co.get("Custom Companies", []))

    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    ai_api_url = os.getenv("AI_API_URL", "").strip()
    ai_api_key = os.getenv("AI_API_KEY", "").strip()

    seen_jobs_file = os.getenv("SEEN_JOBS_FILE", "seen_jobs.json")
    max_seen_history = int(os.getenv("MAX_SEEN_HISTORY", "1000"))
    delay_between_alerts = float(os.getenv("DELAY_BETWEEN_ALERTS", "1.0"))
    dry_run = _str_to_bool(os.getenv("DRY_RUN", "false"))

    cfg = Config(
        search_terms=search_terms,
        locations=locations,
        site_names=site_names,
        hours_old=hours_old,
        results_wanted=results_wanted,
        is_remote=is_remote,
        country_indeed=country_indeed,
        enable_indeed_fallback=enable_indeed_fallback,
        filter_mode=filter_mode,
        top_companies=top_co,
        custom_companies=custom_co,
        discord_webhook_url=discord_webhook_url,
        ai_api_url=ai_api_url,
        ai_api_key=ai_api_key,
        seen_jobs_file=seen_jobs_file,
        max_seen_history=max_seen_history,
        delay_between_alerts=delay_between_alerts,
        dry_run=dry_run,
    )
    return cfg


config = load_config()
