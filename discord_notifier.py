"""Discord Webhook Notifier with rich embed formatting and top employer highlights."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from config import Config

logger = logging.getLogger("job_alerts.discord")

# Color constants (decimal representation for Discord API)
COLOR_TOP_TIER = 0xF1C40F   # Gold / Featured Employer
COLOR_LINKEDIN = 0x0A66C2   # LinkedIn Blue
COLOR_INDEED = 0x2164F3     # Indeed Blue
COLOR_DEFAULT = 0x5865F2    # Discord Blurple


def _format_salary(job: Dict[str, Any]) -> Optional[str]:
    """Format salary information if available."""
    min_amt = job.get("min_amount")
    max_amt = job.get("max_amount")
    currency = job.get("currency") or ""
    interval = job.get("interval") or ""

    if min_amt is not None and max_amt is not None:
        try:
            return f"{currency} {float(min_amt):,.0f} - {float(max_amt):,.0f} / {interval}".strip()
        except (ValueError, TypeError):
            return f"{currency} {min_amt} - {max_amt} / {interval}".strip()
    elif min_amt is not None:
        try:
            return f"{currency} >= {float(min_amt):,.0f} / {interval}".strip()
        except (ValueError, TypeError):
            return f"{currency} >= {min_amt} / {interval}".strip()
    elif max_amt is not None:
        try:
            return f"{currency} <= {float(max_amt):,.0f} / {interval}".strip()
        except (ValueError, TypeError):
            return f"{currency} <= {max_amt} / {interval}".strip()

    compensation = job.get("compensation")
    if compensation and isinstance(compensation, str) and compensation.strip():
        return compensation.strip()

    return None


def _get_embed_color(site: Optional[str], is_top_tier: bool = False) -> int:
    """Select appropriate brand color based on top tier status and job board."""
    if is_top_tier:
        return COLOR_TOP_TIER

    if not site:
        return COLOR_DEFAULT
    site_lower = str(site).lower()
    if "linkedin" in site_lower:
        return COLOR_LINKEDIN
    if "indeed" in site_lower:
        return COLOR_INDEED
    return COLOR_DEFAULT


def build_job_embed(job: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Discord Embed dictionary from a job record with optional top employer highlight."""
    raw_title = str(job.get("title") or "Lowongan Pekerjaan Baru")
    company = str(job.get("company") or "Perusahaan Tidak Disebutkan")
    raw_location = str(job.get("location") or "Lokasi Tidak Tersedia")
    is_remote = job.get("is_remote")
    location = f"{raw_location} (Remote)" if is_remote else raw_location

    url = job.get("job_url") or job.get("job_url_direct") or ""
    site = str(job.get("site") or "Web").capitalize()
    date_posted = job.get("date_posted") or "Baru saja"
    job_type = job.get("job_type")

    # Check top company classification
    company_match = job.get("company_match")
    is_top_tier = company_match is not None

    fields = []

    # If top tier, prepend a prominent highlight banner field
    if is_top_tier:
        fields.append({
            "name": "⭐ PERUSAHAAN UNGGULAN (TOP TIER)",
            "value": f"**{company_match.badge}** • {company_match.canonical_name}",
            "inline": False,
        })

    fields.extend([
        {"name": "🏢 Perusahaan", "value": company[:1000], "inline": True},
        {"name": "📍 Lokasi", "value": location[:1000], "inline": True},
        {"name": "🌐 Sumber", "value": site[:1000], "inline": True},
        {"name": "📅 Diposting", "value": str(date_posted)[:1000], "inline": True},
    ])

    if job_type:
        fields.append({"name": "💼 Tipe", "value": str(job_type).replace("_", " ").title()[:1000], "inline": True})

    matched_query = job.get("matched_query")
    if matched_query:
        fields.append({"name": "🎯 Pencarian", "value": str(matched_query)[:1000], "inline": True})

    salary = _format_salary(job)
    if salary:
        fields.append({"name": "💰 Estimasi Gaji", "value": salary[:1000], "inline": True})

    # Add quick link call to action
    if url:
        fields.append({"name": "🔗 Link Lamaran", "value": f"[Klik di sini untuk melamar]({url})", "inline": False})

    footer_text = f"Job Alert Bot • {company_match.category}" if is_top_tier else "Job Alert Bot • Powered by JobSpy"

    embed: Dict[str, Any] = {
        "title": raw_title[:250],
        "color": _get_embed_color(job.get("site"), is_top_tier=is_top_tier),
        "fields": fields,
        "footer": {
            "text": footer_text,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if url:
        embed["url"] = url

    # Optional company logo as thumbnail
    logo_url = job.get("company_logo")
    if logo_url and isinstance(logo_url, str) and logo_url.startswith("http"):
        embed["thumbnail"] = {"url": logo_url}

    return embed


class DiscordNotifier:
    """Handles dispatching job alert embeds to Discord Webhooks."""

    def __init__(self, webhook_url: str, delay: float = 1.0):
        self.webhook_url = webhook_url.strip()
        self.delay = max(0.2, delay)

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("https://discord.com/api/webhooks/"))

    def send_single_job(self, job: Dict[str, Any], max_retries: int = 3) -> bool:
        """Send one job alert embed to Discord webhook with retry logic."""
        if not self.is_configured():
            logger.warning("DISCORD_WEBHOOK_URL tidak dikonfigurasi atau tidak valid. Melewati pengiriman.")
            return False

        embed = build_job_embed(job)
        payload = {
            "username": "Job Alert Bot",
            "embeds": [embed],
        }

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(self.webhook_url, json=payload, timeout=15)

                if response.status_code in (200, 204):
                    logger.info("Berhasil mengirim alert: '%s' (%s)", job.get("title"), job.get("company"))
                    return True

                if response.status_code == 429:
                    # Rate limited: wait specified time in response
                    retry_after = 2.0
                    try:
                        retry_after = float(response.json().get("retry_after", 2.0))
                    except Exception:
                        pass
                    logger.warning("Discord Rate Limit tercapai. Menunggu %.2f detik (attempt %d/%d)...", retry_after, attempt, max_retries)
                    time.sleep(retry_after)
                    continue

                logger.error("Gagal mengirim webhook. HTTP %d: %s", response.status_code, response.text)

            except requests.RequestException as exc:
                logger.error("Kesalahan jaringan saat mengirim webhook (attempt %d/%d): %s", attempt, max_retries, exc)
                time.sleep(1.0)

        return False

    def notify_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Send alerts for a list of jobs. Returns the list of successfully sent jobs."""
        if not jobs:
            logger.info("Tidak ada lowongan baru untuk dikirim ke Discord.")
            return []

        if not self.is_configured():
            logger.warning("DISCORD_WEBHOOK_URL kosong. Mode dry-run/preview aktif (tidak ada pesan dikirim ke Discord).")
            return []

        successful: List[Dict[str, Any]] = []
        logger.info("Mengirim %d lowongan baru ke Discord...", len(jobs))

        for idx, job in enumerate(jobs, 1):
            ok = self.send_single_job(job)
            if ok:
                successful.append(job)

            if idx < len(jobs):
                time.sleep(self.delay)

        logger.info("Selesai mengirim alerts: %d/%d berhasil terkirim.", len(successful), len(jobs))
        return successful
