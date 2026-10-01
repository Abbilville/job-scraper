"""Scraper module utilizing python-jobspy with multi-search and fallback support."""

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
    search_term: str,
    location: str,
    cfg: Config,
    results_wanted: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Scrape a single job site with error handling."""
    target_results = results_wanted or cfg.results_wanted
    logger.info(
        "Memulai scraping dari '%s' (Search: '%s', Lokasi: '%s', Limit: %d, Hours: %d, Remote: %s)...",
        site,
        search_term,
        location,
        target_results,
        cfg.hours_old,
        cfg.is_remote,
    )

    try:
        df = scrape_jobs(
            site_name=[site],
            search_term=search_term,
            location=location,
            results_wanted=target_results,
            hours_old=cfg.hours_old,
            is_remote=cfg.is_remote,
            country_indeed=cfg.country_indeed,
            verbose=0,
        )

        if df is None or df.empty:
            logger.info("Scraping '%s' untuk '%s' di '%s': 0 lowongan.", site, search_term, location)
            return []

        records = [clean_job_record(r, default_site=site) for r in df.to_dict("records")]
        logger.info("Scraping '%s' untuk '%s' di '%s': %d lowongan ditemukan.", site, search_term, location, len(records))
        return records

    except Exception as exc:
        logger.warning(
            "Peringatan: Gagal scraping '%s' untuk '%s' (%s): %s",
            site,
            search_term,
            location,
            exc,
            exc_info=False,
        )
        return []


def fetch_jobs(cfg: Config) -> List[Dict[str, Any]]:
    """Fetch jobs across all configured search terms, locations, and job sites with fallback."""
    all_jobs: List[Dict[str, Any]] = []
    seen_keys = set()

    search_terms = cfg.search_terms if cfg.search_terms else [cfg.search_term]
    locations = cfg.locations if cfg.locations else [cfg.location]
    sites_to_query = list(cfg.site_names)

    total_combinations = len(search_terms) * len(locations)
    logger.info(
        "Menjalankan pencarian untuk %d kombinasi (%d kata kunci x %d lokasi) pada situs: %s",
        total_combinations,
        len(search_terms),
        len(locations),
        ", ".join(sites_to_query),
    )

    for term in search_terms:
        for loc in locations:
            linkedin_results_count = 0
            linkedin_attempted = False

            for site in sites_to_query:
                if site == "linkedin":
                    linkedin_attempted = True

                site_jobs = scrape_site_safely(
                    site=site,
                    search_term=term,
                    location=loc,
                    cfg=cfg,
                )

                if site == "linkedin":
                    linkedin_results_count = len(site_jobs)

                for job in site_jobs:
                    key = str(job.get("id") or job.get("job_url"))
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        # Record matched query context
                        job["matched_query"] = f"{term} @ {loc}"
                        all_jobs.append(job)

            # Check Indeed fallback condition per query
            if (
                cfg.enable_indeed_fallback
                and linkedin_attempted
                and linkedin_results_count == 0
                and "indeed" not in sites_to_query
            ):
                logger.info(
                    "LinkedIn 0 hasil untuk '%s' di '%s'. Menjalankan fallback Indeed...",
                    term,
                    loc,
                )
                indeed_jobs = scrape_site_safely(
                    site="indeed",
                    search_term=term,
                    location=loc,
                    cfg=cfg,
                )
                for job in indeed_jobs:
                    key = str(job.get("id") or job.get("job_url"))
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        job["matched_query"] = f"{term} @ {loc}"
                        all_jobs.append(job)

    logger.info("Total lowongan unik hasil scraping semua kombinasi: %d", len(all_jobs))
    return all_jobs
