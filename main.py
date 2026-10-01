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
    "sumatera", "kalimantan", "sulawesi", "id"
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
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, loc):
                return True

    return False


def is_title_excluded(title: str, exclude_keywords: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if job title contains any forbidden exclusion keyword."""
    title_clean = title.strip()
    for kw in exclude_keywords:
        clean_kw = kw.strip()
        if not clean_kw:
            continue
        # Use word boundary search
        pattern = rf"\b{re.escape(clean_kw)}\b"
        if re.search(pattern, title_clean, re.IGNORECASE):
            return True, clean_kw
    return False, None


def classify_stream(job: Dict[str, Any], routing_cfg: Dict[str, Any]) -> str:
    """Classify job into stream: product_and_analysis, data_and_ai, or tech_engineering."""
    title = str(job.get("title") or "")
    matched_query = str(job.get("matched_query") or "")
    combined = f"{title} {matched_query}".lower()

    streams = routing_cfg.get("streams", {})

    # Priority 1: Product & Analysis
    product_keywords = streams.get("product_and_analysis", {}).get("keywords", [])
    for kw in product_keywords:
        pattern = rf"\b{re.escape(kw.lower().strip())}\b"
        if re.search(pattern, combined):
            return "product_and_analysis"

    # Priority 2: Data & AI
    data_keywords = streams.get("data_and_ai", {}).get("keywords", [])
    for kw in data_keywords:
        pattern = rf"\b{re.escape(kw.lower().strip())}\b"
        if re.search(pattern, combined):
            return "data_and_ai"

    # Priority 3: Tech & Engineering
    tech_keywords = streams.get("tech_engineering", {}).get("keywords", [])
    for kw in tech_keywords:
        pattern = rf"\b{re.escape(kw.lower().strip())}\b"
        if re.search(pattern, combined):
            return "tech_engineering"

    return "tech_engineering"


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
    json_path = args.config_file or "config.json"
    cfg = load_config(json_path)

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
    logger = logging.getLogger("job_alerts.main")

    logger.info("=" * 65)
    logger.info("🚀 Menjalankan Job Alert Bot (SI & Tech Edition)")
    logger.info("  • Kata Kunci      : %d role (%s...)", len(cfg.search_terms), ", ".join(cfg.search_terms[:4]))
    logger.info("  • Lokasi          : %s (Remote: %s)", ", ".join(cfg.locations), cfg.is_remote)
    logger.info("  • Rentang Waktu   : %d jam terakhir", cfg.hours_old)
    logger.info("  • Target Hasil    : %d per query/situs", cfg.results_wanted)
    logger.info("  • Mode Filter     : %s (only_top / highlight / all)", cfg.filter_mode)
    if cfg.exclude_title_keywords:
        logger.info("  • Negative Exclude: %d kata kunci (%s...)", len(cfg.exclude_title_keywords), ", ".join(cfg.exclude_title_keywords[:5]))
    logger.info("  • Stream Routing  : %s", "Aktif (Multi-Channel)" if cfg.discord_routing.get("enable_stream_routing") else "Single Channel")
    logger.info("  • AI Extractor    : %s", "Aktif (URL terpasang)" if cfg.ai_api_url else "Offline (Rule-based Regex)")
    logger.info("  • Mode Dry Run    : %s", cfg.dry_run)
    logger.info("=" * 65)

    # 1. Initialize Deduplicator & Company Matcher
    dedup = JobDeduplicator(filepath=cfg.seen_jobs_file, max_history=cfg.max_seen_history)
    matcher = CompanyMatcher(
        top_companies_dict=cfg.top_companies,
        custom_companies=cfg.custom_companies,
    )

    # 2. Scrape Jobs across terms & locations
    scraped_jobs = fetch_jobs(cfg)
    if not scraped_jobs:
        logger.info("Tidak ada lowongan ditemukan pada pencarian kali ini.")
        return 0

    # 3. Apply Post-Scrape Location Filter (Anti-Foreign Leakage)
    filtered_by_location = []
    loc_excluded_count = 0
    for job in scraped_jobs:
        if is_location_allowed(job, cfg.locations):
            filtered_by_location.append(job)
        else:
            loc_excluded_count += 1
            logger.debug("Exclude lowongan '%s' karena lokasi '%s' di luar target", job.get("title"), job.get("location"))

    if loc_excluded_count > 0:
        logger.info(
            "Filter lokasi: Mengabaikan %d lowongan di luar target wilayah (tersisa %d).",
            loc_excluded_count,
            len(filtered_by_location),
        )

    if not filtered_by_location:
        logger.info("Semua lowongan hasil scraping tereliminasi oleh filter lokasi.")
        return 0

    # 4. Apply Negative Title Exclusion Filter
    filtered_by_title = []
    excluded_count = 0
    for job in filtered_by_location:
        is_ex, reason = is_title_excluded(job.get("title", ""), cfg.exclude_title_keywords)
        if is_ex:
            excluded_count += 1
            logger.debug("Exclude lowongan '%s' karena mengandung '%s'", job.get("title"), reason)
        else:
            filtered_by_title.append(job)

    if excluded_count > 0:
        logger.info("Filter kata kunci negatif: Mengabaikan %d lowongan tidak relevan (tersisa %d).", excluded_count, len(filtered_by_title))

    if not filtered_by_title:
        logger.info("Semua lowongan hasil scraping tereliminasi oleh filter kata kunci negatif.")
        return 0

    # 5. Early Deduplication against seen_jobs.json (avoid running expensive extraction on seen jobs)
    new_jobs = dedup.filter_unseen(filtered_by_title)
    if not new_jobs:
        logger.info("Semua lowongan (%d) sudah ada di riwayat seen_jobs. Tidak ada alert baru.", len(filtered_by_title))
        return 0

    # 6. Extract Insights (Skills, YoE, Seniority, Level Code) ONLY for unseen jobs
    logger.info("Mengekstrak keterampilan (skills), pengalaman (YoE), dan level jabatan untuk %d lowongan baru...", len(new_jobs))
    for job in new_jobs:
        job["company_match"] = matcher.match(job.get("company"))
        job["insights"] = extract_job_insights(
            job=job,
            ai_api_url=cfg.ai_api_url,
            ai_api_key=cfg.ai_api_key,
        )

    # 7. Apply Seniority Level Filtering (if configured)
    filtered_by_level = []
    if cfg.allowed_experience_levels:
        allowed_set = {lvl.lower().strip() for lvl in cfg.allowed_experience_levels if lvl.strip()}
        level_excluded = 0
        for job in new_jobs:
            lvl_code = getattr(job["insights"], "level_code", "mid_senior")
            if lvl_code in allowed_set:
                filtered_by_level.append(job)
            else:
                level_excluded += 1
                logger.debug("Exclude lowongan '%s' karena level '%s' tidak diizinkan", job.get("title"), lvl_code)

        if level_excluded > 0:
            logger.info("Filter level pengalaman: Mengabaikan %d lowongan level senior/lead (tersisa %d).", level_excluded, len(filtered_by_level))
    else:
        filtered_by_level = new_jobs

    if not filtered_by_level:
        logger.info("Tidak ada lowongan yang sesuai dengan level pengalaman yang diizinkan.")
        return 0

    # 8. Apply Company Filter Mode
    eligible_jobs = []
    if cfg.filter_mode == "only_top":
        for job in filtered_by_level:
            if job.get("company_match"):
                eligible_jobs.append(job)
        logger.info(
            "Filter 'only_top': Menyaring %d lowongan dari perusahaan Top Tier (dari total %d).",
            len(eligible_jobs),
            len(filtered_by_level),
        )
    else:
        eligible_jobs = filtered_by_level
        # In 'highlight' mode, prioritize Top Tier companies first
        if cfg.filter_mode == "highlight":
            eligible_jobs.sort(key=lambda j: 0 if j.get("company_match") else 1)

    if not eligible_jobs:
        logger.info("Tidak ada lowongan yang memenuhi kriteria filter perusahaan.")
        return 0

    # 9. Classify stream for each job
    routing_cfg = cfg.discord_routing
    for job in eligible_jobs:
        stream_key = classify_stream(job, routing_cfg)
        job["stream_key"] = stream_key
        stream_meta = routing_cfg.get("streams", {}).get(stream_key, {})
        job["stream_name"] = stream_meta.get("name", stream_key)
        job["stream_color"] = stream_meta.get("color")
        job["role_id"] = stream_meta.get("role_id")

    top_count = sum(1 for j in eligible_jobs if j.get("company_match"))
    logger.info("Ditemukan %d lowongan baru (%d dari Top Tier/Big 4/Tech Giants)!", len(eligible_jobs), top_count)
    # 10. Preview / Dry-run check
    if cfg.dry_run:
        logger.info("--- [MODE DRY RUN AKTIF - PREVIEW LOWONGAN & ROUTING STREAM] ---")
        for i, job in enumerate(eligible_jobs, 1):
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
        logger.info("Dry run selesai. Tidak ada pesan dikirim dan seen_jobs.json tidak diubah.")
        return 0

    # 11. Send alerts to Discord with stream-based routing
    notifier = DiscordNotifier(
        default_webhook_url=cfg.discord_webhook_url,
        config=cfg,
        delay=cfg.delay_between_alerts,
    )

    if not notifier.has_any_webhook():
        logger.warning(
            "DISCORD_WEBHOOK_URL belum disetel! Menampilkan preview %d lowongan baru di konsol:",
            len(eligible_jobs),
        )
        for i, job in enumerate(eligible_jobs, 1):
            badge = f"[{job['company_match'].badge}] " if job.get("company_match") else ""
            stream_tag = f"[{job.get('stream_name')}] "
            ins = job.get("insights")
            skills_str = f" | Skills: {', '.join(ins.skills[:5])}" if ins and ins.skills else ""
            logger.info(
                "[%d] %s%s%s | %s%s | %s",
                i,
                stream_tag,
                badge,
                job.get("title"),
                job.get("company"),
                skills_str,
                job.get("job_url"),
            )
        logger.info("Tips: Setel DISCORD_WEBHOOK_URL atau webhook per stream untuk mengirim otomatis ke Discord.")
        return 0

    # 12. Dispatch and mark seen
    sent_jobs = notifier.notify_jobs(eligible_jobs)
    for job in sent_jobs:
        dedup.mark_seen(job)

    # 13. Persist seen jobs
    if sent_jobs:
        dedup.save()
        logger.info("Berhasil menyimpan %d lowongan baru ke '%s'.", len(sent_jobs), cfg.seen_jobs_file)
    else:
        logger.warning("Tidak ada alert yang berhasil terkirim ke Discord.")

    return 0


def main() -> None:
    args = parse_arguments()
    setup_logging(verbose=args.verbose)
    cfg = build_config_from_args(args)
    exit_code = run_job_alerts(cfg)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
