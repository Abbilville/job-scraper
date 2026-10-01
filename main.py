"""Main entry point for Job Alert Bot with multi-search, company intelligence, and AI-assisted extraction."""

import argparse
import logging
import sys
from typing import List

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
    """Execute the job alert pipeline."""
    logger = logging.getLogger("job_alerts.main")

    logger.info("=" * 65)
    logger.info("🚀 Menjalankan Job Alert Bot")
    logger.info("  • Kata Kunci      : %s", ", ".join(cfg.search_terms))
    logger.info("  • Lokasi          : %s (Remote: %s)", ", ".join(cfg.locations), cfg.is_remote)
    logger.info("  • Rentang Waktu   : %d jam terakhir", cfg.hours_old)
    logger.info("  • Target Hasil    : %d per query/situs", cfg.results_wanted)
    logger.info("  • Situs           : %s (Fallback Indeed: %s)", ", ".join(cfg.site_names), cfg.enable_indeed_fallback)
    logger.info("  • Mode Filter     : %s (only_top / highlight / all)", cfg.filter_mode)
    logger.info("  • AI Extractor    : %s", "Aktif (URL terpasang)" if cfg.ai_api_url else "Offline (Rule-based Regex)")
    logger.info("  • Discord Webhook : %s", "Tersedia" if cfg.discord_webhook_url else "KOSONG (Dry Run)")
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

    # 3. Classify and match companies
    for job in scraped_jobs:
        job["company_match"] = matcher.match(job.get("company"))

    # 4. Apply Company Filter Mode
    eligible_jobs = []
    if cfg.filter_mode == "only_top":
        for job in scraped_jobs:
            if job.get("company_match"):
                eligible_jobs.append(job)
        logger.info(
            "Filter 'only_top': Menyaring %d lowongan dari perusahaan Top Tier (dari total %d).",
            len(eligible_jobs),
            len(scraped_jobs),
        )
    else:
        # For 'highlight' or 'all', keep all scraped jobs
        eligible_jobs = scraped_jobs

        # In 'highlight' mode, prioritize Top Tier companies first
        if cfg.filter_mode == "highlight":
            eligible_jobs.sort(key=lambda j: 0 if j.get("company_match") else 1)

    if not eligible_jobs:
        logger.info("Tidak ada lowongan yang memenuhi kriteria filter perusahaan.")
        return 0

    # 5. Filter Duplicates against seen_jobs.json
    new_jobs = dedup.filter_unseen(eligible_jobs)
    if not new_jobs:
        logger.info("Semua lowongan (%d) sudah ada di riwayat seen_jobs. Tidak ada alert baru.", len(eligible_jobs))
        return 0

    top_count = sum(1 for j in new_jobs if j.get("company_match"))
    logger.info("Ditemukan %d lowongan baru (%d dari Top Tier/Big 4/Tech Giants)!", len(new_jobs), top_count)

    # 6. Extract Skills, YoE & Seniority Insights
    logger.info("Mengekstrak keterampilan (skills), pengalaman (YoE), dan level jabatan...")
    for job in new_jobs:
        job["insights"] = extract_job_insights(
            job=job,
            ai_api_url=cfg.ai_api_url,
            ai_api_key=cfg.ai_api_key,
        )

    # 7. Preview / Dry-run check
    if cfg.dry_run:
        logger.info("--- [MODE DRY RUN AKTIF - PREVIEW LOWONGAN & INSIGHTS] ---")
        for i, job in enumerate(new_jobs, 1):
            badge = f"[{job['company_match'].badge}] " if job.get("company_match") else ""
            ins = job.get("insights")
            skills_str = f" | Skills: {', '.join(ins.skills[:5])}" if ins and ins.skills else ""
            yoe_str = f" | YoE: {ins.yoe}" if ins and ins.yoe else ""
            lvl_str = f" | Level: {ins.seniority}" if ins and ins.seniority else ""
            logger.info(
                "[%d] %s%s | %s%s%s%s | %s",
                i,
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

    # 8. Send alerts to Discord
    notifier = DiscordNotifier(webhook_url=cfg.discord_webhook_url, delay=cfg.delay_between_alerts)

    if not notifier.is_configured():
        logger.warning(
            "DISCORD_WEBHOOK_URL belum disetel! Menampilkan preview %d lowongan baru di konsol:",
            len(new_jobs),
        )
        for i, job in enumerate(new_jobs, 1):
            badge = f"[{job['company_match'].badge}] " if job.get("company_match") else ""
            ins = job.get("insights")
            skills_str = f" | Skills: {', '.join(ins.skills[:5])}" if ins and ins.skills else ""
            yoe_str = f" | YoE: {ins.yoe}" if ins and ins.yoe else ""
            logger.info(
                "[%d] %s%s | %s%s%s | %s",
                i,
                badge,
                job.get("title"),
                job.get("company"),
                yoe_str,
                skills_str,
                job.get("job_url"),
            )
        logger.info(
            "Tips: Setel environment variable DISCORD_WEBHOOK_URL untuk mengirim otomatis ke Discord."
        )
        return 0

    # 9. Dispatch and mark seen
    sent_jobs = notifier.notify_jobs(new_jobs)
    for job in sent_jobs:
        dedup.mark_seen(job)

    # 10. Persist seen jobs
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
