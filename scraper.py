"""Scraper module utilizing python-jobspy with fallback support."""

import datetime
import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from jobspy import scrape_jobs

from config import Config

logger = logging.getLogger("job_alerts.scraper")


def clean_job_record(record: Dict[str, Any], default_site: str = "") -> Dict[str, Any]:
    """Clean pandas record by replacing NaN with None and converting dates to string."""
    cleaned: Dict[str, Any] = {}
    for k, v in record.items():
        if pd.isna(v):
            cleaned[k] = None
        elif isinstance(v, (datetime.date, datetime.datetime)):
            cleaned[k] = v.isoformat()
        else:
            cleaned[k] = v

    # Ensure site identifier exists
    if not cleaned.get("site") and default_site:
        cleaned["site"] = default_site

    # Ensure a stable identifier key exists
    job_id = cleaned.get("id")
    job_url = cleaned.get("job_url") or cleaned.get("job_url_direct")
    if not job_id and job_url:
        cleaned["id"] = str(job_url)

    return cleaned


def scrape_site_safely(
    site: str,
    cfg: Config,
    results_wanted: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Scrape a single job site with error handling."""
    target_results = results_wanted or cfg.results_wanted
    logger.info(
        "Memulai scraping dari '%s' (Search: '%s', Lokasi: '%s', Limit: %d, Hours: %d, Remote: %s)...",
        site,
        cfg.search_term,
        cfg.location,
        target_results,
        cfg.hours_old,
        cfg.is_remote,
    )

    try:
        df = scrape_jobs(
            site_name=[site],
            search_term=cfg.search_term,
            location=cfg.location,
            results_wanted=target_results,
            hours_old=cfg.hours_old,
            is_remote=cfg.is_remote,
            country_indeed=cfg.country_indeed,
            verbose=0,
        )

        if df is None or df.empty:
            logger.info("Scraping '%s' selesai: 0 lowongan ditemukan.", site)
            return []

        records = [clean_job_record(r, default_site=site) for r in df.to_dict("records")]
        logger.info("Scraping '%s' berhasil: %d lowongan ditemukan.", site, len(records))
        return records

    except Exception as exc:
        logger.warning("Peringatan: Gagal melakukan scraping pada '%s': %s", site, exc, exc_info=False)
        return []


def fetch_jobs(cfg: Config) -> List[Dict[str, Any]]:
    """Fetch jobs according to configuration, with automatic Indeed fallback for LinkedIn."""
    all_jobs: List[Dict[str, Any]] = []
    seen_keys = set()

    sites_to_query = list(cfg.site_names)
    primary_site = sites_to_query[0] if sites_to_query else "linkedin"

    linkedin_results_count = 0
    linkedin_attempted = False

    for site in sites_to_query:
        if site == "linkedin":
            linkedin_attempted = True

        site_jobs = scrape_site_safely(site, cfg)
        if site == "linkedin":
            linkedin_results_count = len(site_jobs)

        for job in site_jobs:
            key = str(job.get("id") or job.get("job_url"))
            if key and key not in seen_keys:
                seen_keys.add(key)
                all_jobs.append(job)

    # Check Indeed fallback condition:
    # If LinkedIn was attempted and returned 0 results or failed, and Indeed was not in sites_to_query
    if (
        cfg.enable_indeed_fallback
        and linkedin_attempted
        and linkedin_results_count == 0
        and "indeed" not in sites_to_query
    ):
        logger.info("LinkedIn tidak menghasilkan lowongan atau gagal. Menjalankan fallback Indeed...")
        indeed_jobs = scrape_site_safely("indeed", cfg)
        for job in indeed_jobs:
            key = str(job.get("id") or job.get("job_url"))
            if key and key not in seen_keys:
                seen_keys.add(key)
                all_jobs.append(job)

    logger.info("Total lowongan baru hasil scraping (sebelum deduplikasi riwayat): %d", len(all_jobs))
    return all_jobs
