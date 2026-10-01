"""Test script to verify Discord webhook delivery and role tagging for each stream."""

import argparse
import logging
import sys
import time
from typing import Any, Dict, List

from company_filter import CompanyMatch, CompanyMatcher
from config import load_config
from discord_notifier import DiscordNotifier
from extractor import JobInsights

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_alert")


def get_sample_test_jobs() -> List[Dict[str, Any]]:
    """Return 1 realistic test job for each stream with rich insights."""
    return [
        {
            "stream_key": "tech_engineering",
            "stream_name": "Tech & Engineering",
            "role_id": "1555093143299432550",
            "title": "Software Engineer (Fullstack)",
            "company": "GoTo (Gojek & Tokopedia)",
            "location": "Jakarta, Indonesia",
            "is_remote": True,
            "site": "LinkedIn",
            "date_posted": "Baru saja",
            "job_type": "full_time",
            "job_url": "https://www.linkedin.com/jobs/view/sample-swe-goto",
            "min_amount": 15000000,
            "max_amount": 22000000,
            "currency": "IDR",
            "interval": "monthly",
            "company_match": CompanyMatch(
                canonical_name="GoTo (Gojek & Tokopedia)",
                category="Top Tech Giants & Unicorns",
                badge="🚀 Top Tech Giant",
            ),
            "insights": JobInsights(
                skills=["React", "TypeScript", "Go", "PostgreSQL", "Docker", "Git"],
                yoe="1-2 tahun",
                seniority="Junior / Associate",
                summary="Membangun sistem microservices dan web frontend skala besar.",
            ),
        },
        {
            "stream_key": "data_and_ai",
            "stream_name": "Data & AI",
            "role_id": "1555092804307521546",
            "title": "Data Analyst & Business Intelligence",
            "company": "Bank Central Asia (BCA)",
            "location": "Jakarta, Indonesia",
            "is_remote": False,
            "site": "LinkedIn",
            "date_posted": "Baru saja",
            "job_type": "full_time",
            "min_amount": 12000000,
            "max_amount": 18000000,
            "currency": "IDR",
            "interval": "monthly",
            "company_match": CompanyMatch(
                canonical_name="Bank Central Asia (BCA)",
                category="Top Tier Banking & FinTech",
                badge="🏛️ Top Tier Banking",
            ),
            "insights": JobInsights(
                skills=["SQL", "Python", "Tableau", "Power BI", "Excel", "Data Warehouse"],
                yoe="Min. 1 tahun",
                seniority="Associate",
                summary="Analisis data transaksi nasabah dan visualisasi dashboard eksekutif.",
            ),
        },
        {
            "stream_key": "product_and_analysis",
            "stream_name": "Product & Business Analysis",
            "role_id": "1555093143597088848",
            "title": "Associate Product Manager (APM)",
            "company": "tiket.com",
            "location": "Jakarta, Indonesia",
            "is_remote": True,
            "site": "LinkedIn",
            "date_posted": "Baru saja",
            "min_amount": 14000000,
            "max_amount": 20000000,
            "currency": "IDR",
            "interval": "monthly",
            "company_match": CompanyMatch(
                canonical_name="tiket.com",
                category="Top Tech Giants & Unicorns",
                badge="🚀 Top Tech Unicorn",
            ),
            "insights": JobInsights(
                skills=["Jira", "Figma", "PRD", "User Stories", "A/B Testing", "Scrum"],
                yoe="1-2 tahun",
                seniority="Junior / Associate",
                summary="Memimpin siklus pengembangan fitur booking dan riset pengguna.",
            ),
        },
    ]


def run_test(cfg_file: str = "config.json") -> int:
    cfg = load_config(cfg_file)
    notifier = DiscordNotifier(
        default_webhook_url=cfg.discord_webhook_url,
        config=cfg,
        delay=1.0,
    )

    if not notifier.has_any_webhook():
        logger.error(
            "Tidak ada webhook Discord yang disetel! Harap setel DISCORD_WEBHOOK_URL atau webhook per stream di .env atau GitHub Secrets."
        )
        return 1

    jobs = get_sample_test_jobs()
    logger.info("=" * 60)
    logger.info("🧪 Memulai Test Pengiriman 1 Job per Stream ke Discord")
    logger.info("=" * 60)

    success_count = 0
    for job in jobs:
        stream_key = job["stream_key"]
        stream_name = job["stream_name"]
        role_id = job.get("role_id")
        target_webhook = notifier.get_webhook_for_job(job)

        logger.info("Mengirim test alert untuk stream [%s]...", stream_name)
        logger.info("  • Target Webhook : %s", target_webhook[:35] + "..." if target_webhook else "KOSONG")
        logger.info("  • Tag Role ID    : %s (<@&%s>)", role_id, role_id)

        ok = notifier.send_single_job(job, mention_role=True)
        if ok:
            logger.info("  ✓ Berhasil terkirim ke Discord!\n")
            success_count += 1
        else:
            logger.warning("  ✗ Gagal mengirim ke Discord.\n")

        time.sleep(1.0)

    logger.info("Hasil Test: %d/%d stream berhasil dikirim ke Discord.", success_count, len(jobs))
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Discord Webhook for each stream")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    args = parser.parse_args()
    sys.exit(run_test(args.config))
