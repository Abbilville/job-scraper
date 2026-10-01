"""Main entry point for Job Alert Bot."""

import argparse
import logging
import sys
from typing import List

from config import Config, config as default_config
from dedup import JobDeduplicator
from discord_notifier import DiscordNotifier
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
    parser.add_argument("--search-term", type=str, default=None, help="Job title / keyword search term")
    parser.add_argument("--location", type=str, default=None, help="Job location (e.g. Indonesia, Remote)")
    parser.add_argument("--hours-old", type=int, default=None, help="Max age of job postings in hours")
    parser.add_argument("--results-wanted", type=int, default=None, help="Number of results desired per site")
    parser.add_argument("--sites", type=str, default=None, help="Comma-separated sites (e.g. linkedin,indeed)")
    parser.add_argument("--remote", action="store_true", default=None, help="Filter for remote jobs only")
    parser.add_argument("--dry-run", action="store_true", default=None, help="Scrape without sending to Discord or saving")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


def build_config_from_args(args: argparse.Namespace) -> Config:
    """Merge CLI arguments with default configuration."""
    cfg = Config(
        search_term=args.search_term if args.search_term is not None else default_config.search_term,
        location=args.location if args.location is not None else default_config.location,
        hours_old=args.hours_old if args.hours_old is not None else default_config.hours_old,
        results_wanted=args.results_wanted if args.results_wanted is not None else default_config.results_wanted,
        is_remote=args.remote if args.remote is not None else default_config.is_remote,
        country_indeed=default_config.country_indeed,
        enable_indeed_fallback=default_config.enable_indeed_fallback,
        discord_webhook_url=default_config.discord_webhook_url,
        seen_jobs_file=default_config.seen_jobs_file,
        max_seen_history=default_config.max_seen_history,
        delay_between_alerts=default_config.delay_between_alerts,
        dry_run=args.dry_run if args.dry_run is not None else default_config.dry_run,
    )

    if args.sites is not None:
        cfg.site_names = [s.strip().lower() for s in args.sites.split(",") if s.strip()]

    return cfg


def run_job_alerts(cfg: Config) -> int:
    """Execute the job alert pipeline."""
    logger = logging.getLogger("job_alerts.main")

    logger.info("=" * 60)
    logger.info("🚀 Menjalankan Job Alert Bot")
    logger.info("  • Search Term     : %s", cfg.search_term)
    logger.info("  • Lokasi          : %s (Remote: %s)", cfg.location, cfg.is_remote)
    logger.info("  • Rentang Waktu   : %d jam terakhir", cfg.hours_old)
    logger.info("  • Target Hasil    : %d per situs", cfg.results_wanted)
    logger.info("  • Situs           : %s (Fallback Indeed: %s)", ", ".join(cfg.site_names), cfg.enable_indeed_fallback)
    logger.info("  • Discord Webhook : %s", "Tersedia" if cfg.discord_webhook_url else "KOSONG (Dry Run)")
    logger.info("  • Mode Dry Run    : %s", cfg.dry_run)
    logger.info("=" * 60)

    # 1. Initialize Deduplicator
    dedup = JobDeduplicator(filepath=cfg.seen_jobs_file, max_history=cfg.max_seen_history)

    # 2. Scrape Jobs
    scraped_jobs = fetch_jobs(cfg)
    if not scraped_jobs:
        logger.info("Tidak ada lowongan ditemukan pada pencarian ini.")
        return 0

    # 3. Filter Duplicates
    new_jobs = dedup.filter_unseen(scraped_jobs)
    if not new_jobs:
        logger.info("Semua lowongan (%d) sudah ada di riwayat seen_jobs. Tidak ada alert baru.", len(scraped_jobs))
        return 0

    logger.info("Ditemukan %d lowongan baru yang belum pernah dikirim!", len(new_jobs))

    # 4. Preview / Dry-run check
    if cfg.dry_run:
        logger.info("--- [MODE DRY RUN AKTIF - PREVIEW LOWONGAN] ---")
        for i, job in enumerate(new_jobs, 1):
            logger.info(
                "[%d] %s | %s | %s | %s",
                i,
                job.get("title"),
                job.get("company"),
                job.get("location"),
                job.get("job_url"),
            )
        logger.info("Dry run selesai. Tidak ada pesan dikirim dan seen_jobs.json tidak diubah.")
        return 0

    # 5. Send alerts to Discord
    notifier = DiscordNotifier(webhook_url=cfg.discord_webhook_url, delay=cfg.delay_between_alerts)

    if not notifier.is_configured():
        logger.warning(
            "DISCORD_WEBHOOK_URL belum disetel! Menampilkan preview %d lowongan baru di konsol:",
            len(new_jobs),
        )
        for i, job in enumerate(new_jobs, 1):
            logger.info(
                "[%d] %s | %s | %s | %s",
                i,
                job.get("title"),
                job.get("company"),
                job.get("location"),
                job.get("job_url"),
            )
        logger.info(
            "Tips: Setel environment variable DISCORD_WEBHOOK_URL untuk mengirim otomatis ke Discord."
        )
        return 0

    # 6. Dispatch and mark seen
    sent_jobs = notifier.notify_jobs(new_jobs)
    for job in sent_jobs:
        dedup.mark_seen(job)

    # 7. Persist seen jobs
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
