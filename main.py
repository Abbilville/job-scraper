"""Main entry point for Job Alert Bot with multi-stream routing and negative keyword filtering."""

import argparse
import logging
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from company_filter import CompanyMatcher
from config import Config, load_config
from dedup import JobDeduplicator
from discord_notifier import DiscordNotifier
from extractor import extract_job_insights
from scraper import fetch_jobs

logger = logging.getLogger("job_alerts.main")


def setup_logging(verbose: bool = False) -> None:
    """Configure console logging with clean formatting."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


INDONESIAN_REGION_KEYWORDS = (
    "indonesia", "jakarta", "bandung", "surabaya", "yogyakarta", "jogja",
    "semarang", "medan", "tangerang", "depok", "bogor", "bekasi", "batam",
    "bali", "denpasar", "malang", "solo", "surakarta", "banten", "jawa",
    "sumatera", "kalimantan", "sulawesi",
)


def is_location_allowed(job: Dict[str, Any], allowed_locations: List[str]) -> bool:
    """Check if job location matches allowed locations or remote."""
    if not allowed_locations:
        return True

    loc = str(job.get("location") or "").strip().lower()
    is_remote = bool(job.get("is_remote"))

    # Remote jobs or explicit WFH are always allowed
    if is_remote or any(k in loc for k in ("remote", "wfh", "telecommute", "work from home", "anywhere")):
        return True

    # If location is not provided by scraper, allow it to prevent over-filtering
    if not loc:
        return True

    allowed_set = {a.strip().lower() for a in allowed_locations if a.strip()}

    # Check direct match with any configured allowed location
    for allowed in allowed_set:
        if allowed in loc:
            return True

    # If "indonesia" is in allowed locations, also accept major Indonesian cities/provinces
    if "indonesia" in allowed_set:
        for keyword in INDONESIAN_REGION_KEYWORDS:
            if re.search(rf"\b{re.escape(keyword)}\b", loc):
                return True

    return False


def is_title_excluded(title: str, exclude_keywords: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if job title contains any forbidden exclusion keyword."""
    title_clean = title.strip()
    for kw in exclude_keywords:
        clean_kw = kw.strip()
        if not clean_kw:
            continue
        if re.search(rf"\b{re.escape(clean_kw)}\b", title_clean, re.IGNORECASE):
            return True, clean_kw
    return False, None


def _match_stream_keywords(text: str, streams: Dict[str, Any]) -> Optional[str]:
    """Return the first stream in `streams` whose keyword matches `text` as a whole word/phrase."""
    if not text:
        return None
    for stream_key, meta in streams.items():
        if not isinstance(meta, dict):
            continue
        for kw in meta.get("keywords", []):
            clean = str(kw).strip()
            if clean and re.search(rf"\b{re.escape(clean)}\b", text, re.IGNORECASE):
                return stream_key
    return None


def classify_stream(job: Dict[str, Any], routing_cfg: Dict[str, Any]) -> str:
    """Classify job into a configured stream.

    Matches the job title first across `routing_cfg['streams']` in config order, and only falls back to
    `matched_query` when the title matches nothing—so a "Backend Developer" returned by a "Business Analyst"
    search still goes to the engineering channel.
    """
    streams = routing_cfg.get("streams") or {}
    fallback = routing_cfg.get("fallback_stream")
    if not fallback:
        fallback = next(reversed(streams), "tech_engineering")

    title = str(job.get("title") or "").strip()
    matched_query = str(job.get("matched_query") or "").strip()
    return (
        _match_stream_keywords(title, streams)
        or _match_stream_keywords(matched_query, streams)
        or fallback
    )


def filter_by_location(jobs: List[Dict[str, Any]], allowed_locations: List[str]) -> List[Dict[str, Any]]:
    """Drop jobs whose location falls outside `allowed_locations`."""
    kept: List[Dict[str, Any]] = []
    for job in jobs:
        if is_location_allowed(job, allowed_locations):
            kept.append(job)
        else:
            logger.debug("Exclude lowongan '%s' karena lokasi '%s' di luar target", job.get("title"), job.get("location"))

    dropped = len(jobs) - len(kept)
    if dropped > 0:
        logger.info("Filter lokasi: Mengabaikan %d lowongan di luar target wilayah (tersisa %d).", dropped, len(kept))
    return kept


def filter_by_title(jobs: List[Dict[str, Any]], exclude_keywords: List[str]) -> List[Dict[str, Any]]:
    """Drop jobs whose title matches any negative exclusion keyword."""
    kept: List[Dict[str, Any]] = []
    for job in jobs:
        is_ex, reason = is_title_excluded(job.get("title", ""), exclude_keywords)
        if is_ex:
            logger.debug("Exclude lowongan '%s' karena mengandung '%s'", job.get("title"), reason)
        else:
            kept.append(job)

    dropped = len(jobs) - len(kept)
    if dropped > 0:
        logger.info("Filter kata kunci negatif: Mengabaikan %d lowongan tidak relevan (tersisa %d).", dropped, len(kept))
    return kept


def enrich_jobs(jobs: List[Dict[str, Any]], matcher: CompanyMatcher, cfg: Config) -> None:
    """Attach `company_match` and `insights` in place, tripping a circuit breaker if the AI endpoint fails once."""
    logger.info(
        "Mengekstrak keterampilan (skills), pengalaman (YoE), dan level jabatan untuk %d lowongan baru...",
        len(jobs),
    )
    active_ai_url: Optional[str] = cfg.ai_api_url or None
    for job in jobs:
        job["company_match"] = matcher.match(job.get("company"))
        insights = extract_job_insights(
            job=job,
            ai_api_url=active_ai_url,
            ai_api_key=cfg.ai_api_key,
        )
        if active_ai_url and insights.source != "ai":
            logger.warning(
                "AI endpoint gagal merespon; menonaktifkan AI untuk sisa %d lowongan di run ini.",
                len(jobs),
            )
            active_ai_url = None
        job["insights"] = insights


def split_by_level(
    jobs: List[Dict[str, Any]],
    allowed_levels: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Partition jobs into (kept, rejected) by `allowed_experience_levels`."""
    if not allowed_levels:
        return list(jobs), []

    allowed_set = {lvl.lower().strip() for lvl in allowed_levels if lvl.strip()}
    kept: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for job in jobs:
        lvl_code = getattr(job.get("insights"), "level_code", "mid_senior")
        if lvl_code in allowed_set:
            kept.append(job)
        else:
            rejected.append(job)
            logger.debug("Exclude lowongan '%s' karena level '%s' tidak diizinkan", job.get("title"), lvl_code)

    if rejected:
        logger.info(
            "Filter level pengalaman: Mengabaikan %d lowongan level senior/lead (tersisa %d).",
            len(rejected),
            len(kept),
        )
    return kept, rejected


def split_by_company_mode(
    jobs: List[Dict[str, Any]],
    filter_mode: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Partition jobs into (eligible, rejected) according to `filter_mode` ('only_top' / 'highlight' / 'all')."""
    if filter_mode == "only_top":
        eligible = [j for j in jobs if j.get("company_match")]
        rejected = [j for j in jobs if not j.get("company_match")]
        logger.info(
            "Filter 'only_top': Menyaring %d lowongan dari perusahaan Top Tier (dari total %d).",
            len(eligible),
            len(jobs),
        )
        return eligible, rejected

    eligible = list(jobs)
    if filter_mode == "highlight":
        eligible.sort(key=lambda j: 0 if j.get("company_match") else 1)
    return eligible, []


def assign_streams(jobs: List[Dict[str, Any]], routing_cfg: Dict[str, Any]) -> None:
    """Populate `stream_key`, `stream_name`, and `role_id` on each job."""
    streams = routing_cfg.get("streams", {})
    for job in jobs:
        stream_key = classify_stream(job, routing_cfg)
        stream_meta = streams.get(stream_key, {})
        job["stream_key"] = stream_key
        job["stream_name"] = stream_meta.get("name", stream_key)
        job["role_id"] = stream_meta.get("role_id")


def log_job_preview(jobs: List[Dict[str, Any]]) -> None:
    """Log a one-line preview per job (used by both --dry-run and the no-webhook fallback)."""
    for i, job in enumerate(jobs, 1):
        badge = f"[{job['company_match'].badge}] " if job.get("company_match") else ""
        stream_tag = f"[{job.get('stream_name')}] "
        ins = job.get("insights")
        skills_str = f" | Skills: {', '.join(ins.skills[:5])}" if ins and ins.skills else ""
        yoe_str = f" | YoE: {ins.yoe}" if ins and ins.yoe else ""
        lvl_str = f" | Level: {ins.seniority}" if ins and ins.seniority else ""
        logger.info(
            "[%d] %s%s%s | %s%s%s%s | %s",
            i,
            stream_tag,
            badge,
            job.get("title"),
            job.get("company"),
            lvl_str,
            yoe_str,
            skills_str,
            job.get("job_url"),
        )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Job Alert Bot - Scrapes jobs and sends alerts to Discord.")
    parser.add_argument("--config-file", type=str, default=None, help="Path to custom config.json")
    parser.add_argument("--search-terms", type=str, default=None, help="Comma-separated search terms")
    parser.add_argument("--locations", type=str, default=None, help="Comma-separated job locations")
    parser.add_argument("--hours-old", type=int, default=None, help="Max age of job postings in hours")
    parser.add_argument("--results-wanted", type=int, default=None, help="Number of results desired per site/query")
    parser.add_argument("--sites", type=str, default=None, help="Comma-separated sites (e.g. linkedin,indeed)")
    parser.add_argument("--filter-mode", type=str, choices=["highlight", "only_top", "all"], default=None,
                        help="Company filter mode: highlight (default), only_top, all")
    parser.add_argument("--custom-companies", type=str, default=None,
                        help="Comma-separated additional top companies to recognize")
    parser.add_argument("--remote", action="store_true", default=None, help="Filter for remote jobs only")
    parser.add_argument("--dry-run", action="store_true", default=None, help="Scrape without sending to Discord or saving")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


def build_config_from_args(args: argparse.Namespace) -> Config:
    """Load config.json and merge with CLI arguments."""
    cfg = load_config(args.config_file) if args.config_file else load_config()

    if args.search_terms is not None:
        cfg.search_terms = [s.strip() for s in args.search_terms.split(",") if s.strip()]

    if args.locations is not None:
        cfg.locations = [s.strip() for s in args.locations.split(",") if s.strip()]

    if args.hours_old is not None:
        cfg.hours_old = args.hours_old

    if args.results_wanted is not None:
        cfg.results_wanted = args.results_wanted

    if args.remote is not None:
        cfg.is_remote = args.remote

    if args.filter_mode is not None:
        cfg.filter_mode = args.filter_mode

    if args.sites is not None:
        cfg.site_names = [s.strip().lower() for s in args.sites.split(",") if s.strip()]

    if args.custom_companies is not None:
        extra = [c.strip() for c in args.custom_companies.split(",") if c.strip()]
        cfg.custom_companies.extend(extra)

    if args.dry_run is not None:
        cfg.dry_run = args.dry_run

    return cfg


def run_job_alerts(cfg: Config) -> int:
    """Execute the job alert pipeline with exclusion filtering and stream routing."""
    logger.info("=" * 65)
    logger.info("🚀 Menjalankan Job Alert Bot (SI & Tech Edition)")
    logger.info("  • Kata Kunci      : %d role (%s...)", len(cfg.search_terms), ", ".join(cfg.search_terms[:4]))
    logger.info("  • Lokasi          : %s (Remote: %s)", ", ".join(cfg.locations), cfg.is_remote)
    logger.info("  • Rentang Waktu   : %d jam terakhir", cfg.hours_old)
    logger.info("  • Target Hasil    : %d per query/situs", cfg.results_wanted)
    logger.info("  • Mode Filter     : %s (only_top / highlight / all)", cfg.filter_mode)
    if cfg.exclude_title_keywords:
        logger.info("  • Negative Exclude: %d kata kunci (%s...)", len(cfg.exclude_title_keywords), ", ".join(cfg.exclude_title_keywords[:5]))
    logger.info("  • Stream Routing  : %s", "Aktif (Multi-Channel)" if cfg.discord_routing.get("enable_stream_routing", True) else "Single Channel")
    logger.info("  • AI Extractor    : %s", "Aktif (URL terpasang)" if cfg.ai_api_url else "Offline (Rule-based Regex)")
    logger.info("  • Mode Dry Run    : %s", cfg.dry_run)
    logger.info("=" * 65)

    dedup = JobDeduplicator(filepath=cfg.seen_jobs_file, max_history=cfg.max_seen_history)
    matcher = CompanyMatcher(top_companies_dict=cfg.top_companies, custom_companies=cfg.custom_companies)

    scraped_jobs = fetch_jobs(cfg)
    if not scraped_jobs:
        logger.info("Tidak ada lowongan ditemukan pada pencarian kali ini.")
        return 0

    filtered_by_location = filter_by_location(scraped_jobs, cfg.locations)
    if not filtered_by_location:
        logger.info("Semua lowongan hasil scraping tereliminasi oleh filter lokasi.")
        return 0

    filtered_by_title = filter_by_title(filtered_by_location, cfg.exclude_title_keywords)
    if not filtered_by_title:
        logger.info("Semua lowongan hasil scraping tereliminasi oleh filter kata kunci negatif.")
        return 0

    new_jobs = dedup.filter_unseen(filtered_by_title)
    if not new_jobs:
        logger.info("Semua lowongan (%d) sudah ada di riwayat seen_jobs. Tidak ada alert baru.", len(filtered_by_title))
        return 0

    enrich_jobs(new_jobs, matcher, cfg)
    filtered_by_level, rejected_by_level = split_by_level(new_jobs, cfg.allowed_experience_levels)
    eligible_jobs, rejected_by_company = split_by_company_mode(filtered_by_level, cfg.filter_mode)
    rejected_jobs = rejected_by_level + rejected_by_company
    assign_streams(eligible_jobs, cfg.discord_routing)

    if cfg.dry_run:
        logger.info("--- [MODE DRY RUN AKTIF - PREVIEW LOWONGAN & ROUTING STREAM] ---")
        log_job_preview(eligible_jobs)
        logger.info("Dry run selesai. Tidak ada pesan dikirim dan seen_jobs.json tidak diubah.")
        return 0

    notifier = DiscordNotifier(
        default_webhook_url=cfg.discord_webhook_url,
        config=cfg,
        delay=cfg.delay_between_alerts,
    )

    if not notifier.has_any_webhook():
        if eligible_jobs:
            logger.warning(
                "DISCORD_WEBHOOK_URL belum disetel! Menampilkan preview %d lowongan baru di konsol:",
                len(eligible_jobs),
            )
            log_job_preview(eligible_jobs)
            logger.info("Tips: Setel DISCORD_WEBHOOK_URL atau webhook per stream untuk mengirim otomatis ke Discord.")
        else:
            logger.info("Tidak ada lowongan yang sesuai dengan filter level atau perusahaan.")
        return 0

    # Real run: record post-extraction rejections too so future runs don't re-extract them,
    # and always flush seen_jobs.json in `finally` even if a later send raises.
    try:
        for job in rejected_jobs:
            dedup.mark_seen(job, status="rejected")

        if not eligible_jobs:
            if not filtered_by_level:
                logger.info("Tidak ada lowongan yang sesuai dengan level pengalaman yang diizinkan.")
            else:
                logger.info("Tidak ada lowongan yang memenuhi kriteria filter perusahaan.")
            return 0

        top_count = sum(1 for j in eligible_jobs if j.get("company_match"))
        logger.info("Ditemukan %d lowongan baru (%d dari Top Tier/Big 4/Tech Giants)!", len(eligible_jobs), top_count)

        sent_jobs = notifier.notify_jobs(eligible_jobs, on_sent=dedup.mark_seen)
        if not sent_jobs:
            logger.warning("Tidak ada alert yang berhasil terkirim ke Discord.")
        return 0
    finally:
        if dedup.dirty:
            dedup.save()


def main() -> None:
    args = parse_arguments()
    setup_logging(verbose=args.verbose)
    cfg = build_config_from_args(args)
    exit_code = run_job_alerts(cfg)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
