"""Configuration loader prioritizing config.json with robust environment variable overrides."""

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
    s = str(val).strip().lower()
    if not s:
        return default
    return s in ("true", "1", "yes", "y", "on")


def _parse_int(val: Any, fallback: int) -> int:
    if val is None:
        return fallback
    s = str(val).strip()
    if not s:
        return fallback
    try:
        return int(s)
    except (ValueError, TypeError):
        return fallback


def _parse_float(val: Any, fallback: float) -> float:
    if val is None:
        return fallback
    s = str(val).strip()
    if not s:
        return fallback
    try:
        return float(s)
    except (ValueError, TypeError):
        return fallback


def _parse_str(val: Any, fallback: str) -> str:
    if val is None:
        return fallback
    s = str(val).strip()
    return s if s else fallback


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
    linkedin_fetch_description: bool = True
    # 2. Company & Filtering Settings
    filter_mode: str = "highlight"
    exclude_title_keywords: List[str] = field(default_factory=list)
    allowed_experience_levels: List[str] = field(default_factory=list)
    top_companies: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    custom_companies: List[str] = field(default_factory=list)

    # 3. Discord Routing & Webhooks
    discord_routing: Dict[str, Any] = field(default_factory=dict)
    discord_webhook_url: str = ""
    discord_webhook_tech: str = ""
    discord_webhook_data: str = ""
    discord_webhook_product: str = ""

    # 4. AI Service (Optional)
    ai_api_url: str = ""
    ai_api_key: str = ""

    # 5. Storage & Operational Settings
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

    def get_webhook_for_stream(self, stream_key: Optional[str]) -> str:
        """Resolve webhook URL for a specific stream with fallback to default webhook."""
        if not stream_key:
            return self.discord_webhook_url

        streams = self.discord_routing.get("streams", {})
        stream_info = streams.get(stream_key, {})
        env_var_name = stream_info.get("channel_webhook_env")

        if env_var_name:
            val = os.getenv(env_var_name, "").strip()
            if val:
                return val

        # Direct attribute fallbacks
        if stream_key == "tech_engineering" and self.discord_webhook_tech:
            return self.discord_webhook_tech
        if stream_key == "data_and_ai" and self.discord_webhook_data:
            return self.discord_webhook_data
        if stream_key == "product_and_analysis" and self.discord_webhook_product:
            return self.discord_webhook_product

        return self.discord_webhook_url


def load_config(json_path: str = CONFIG_JSON_PATH) -> Config:
    """Load configuration from config.json and overlay environment variable overrides safely."""
    data = _load_json_file(json_path)

    search_cfg = data.get("search_settings", {})
    filter_cfg = data.get("filtering", {})
    top_co = data.get("top_companies", {})
    routing_cfg = data.get("discord_routing", {})

    # Priority: Env override if set, else config.json, else default
    env_terms = os.getenv("SEARCH_TERMS", os.getenv("SEARCH_TERM"))
    search_terms = _parse_list(env_terms, search_cfg.get("search_terms", ["Frontend Developer"]))

    env_locs = os.getenv("LOCATIONS", os.getenv("LOCATION"))
    locations = _parse_list(env_locs, search_cfg.get("locations", ["Indonesia"]))

    env_sites = os.getenv("SITE_NAMES")
    site_names = _parse_list(env_sites, search_cfg.get("sites", ["linkedin", "indeed"]))

    hours_old = _parse_int(os.getenv("HOURS_OLD"), int(search_cfg.get("hours_old", 24)))
    results_wanted = _parse_int(os.getenv("RESULTS_WANTED"), int(search_cfg.get("results_wanted", 15)))

    env_remote = os.getenv("IS_REMOTE")
    is_remote = _str_to_bool(env_remote, bool(search_cfg.get("is_remote", False))) if env_remote and env_remote.strip() else bool(search_cfg.get("is_remote", False))

    country_indeed = _parse_str(os.getenv("COUNTRY_INDEED"), str(search_cfg.get("country_indeed", "indonesia")))

    env_fallback = os.getenv("ENABLE_INDEED_FALLBACK")
    enable_indeed_fallback = _str_to_bool(env_fallback, bool(search_cfg.get("enable_indeed_fallback", True))) if env_fallback and env_fallback.strip() else bool(search_cfg.get("enable_indeed_fallback", True))

    env_li_desc = os.getenv("LINKEDIN_FETCH_DESCRIPTION")
    linkedin_fetch_description = _str_to_bool(env_li_desc, bool(search_cfg.get("linkedin_fetch_description", True))) if env_li_desc and env_li_desc.strip() else bool(search_cfg.get("linkedin_fetch_description", True))
    filter_mode = _parse_str(os.getenv("FILTER_MODE"), str(filter_cfg.get("filter_mode", "highlight"))).lower()
    exclude_title = _parse_list(os.getenv("EXCLUDE_TITLE_KEYWORDS"), filter_cfg.get("exclude_title_keywords", []))
    allowed_exp = _parse_list(os.getenv("ALLOWED_EXPERIENCE_LEVELS"), filter_cfg.get("allowed_experience_levels", []))
    custom_co = _parse_list(os.getenv("CUSTOM_TOP_COMPANIES", ""), top_co.get("Custom Companies", []))

    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    discord_webhook_tech = os.getenv("DISCORD_WEBHOOK_TECH", "").strip()
    discord_webhook_data = os.getenv("DISCORD_WEBHOOK_DATA", "").strip()
    discord_webhook_product = os.getenv("DISCORD_WEBHOOK_PRODUCT", "").strip()

    ai_api_url = os.getenv("AI_API_URL", "").strip()
    ai_api_key = os.getenv("AI_API_KEY", "").strip()

    seen_jobs_file = _parse_str(os.getenv("SEEN_JOBS_FILE"), "seen_jobs.json")
    max_seen_history = _parse_int(os.getenv("MAX_SEEN_HISTORY"), 1000)
    delay_between_alerts = _parse_float(os.getenv("DELAY_BETWEEN_ALERTS"), 1.0)
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
        linkedin_fetch_description=linkedin_fetch_description,
        exclude_title_keywords=exclude_title,
        allowed_experience_levels=allowed_exp,
        top_companies=top_co,
        custom_companies=custom_co,
        discord_routing=routing_cfg,
        discord_webhook_url=discord_webhook_url,
        discord_webhook_tech=discord_webhook_tech,
        discord_webhook_data=discord_webhook_data,
        discord_webhook_product=discord_webhook_product,
        ai_api_url=ai_api_url,
        ai_api_key=ai_api_key,
        seen_jobs_file=seen_jobs_file,
        max_seen_history=max_seen_history,
        delay_between_alerts=delay_between_alerts,
        dry_run=dry_run,
    )
    return cfg


config = load_config()
