"""Discord Webhook Notifier with stream routing and color coding."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from config import Config

logger = logging.getLogger("job_alerts.discord")

# Color constants (decimal representation for Discord API)
COLOR_TOP_TIER = 0xF1C40F       # Gold / Featured Employer
COLOR_STREAM_TECH = 0x3498DB     # Blue: Tech & Engineering
COLOR_STREAM_DATA = 0x9B59B6     # Purple: Data & AI
COLOR_STREAM_PRODUCT = 0xE67E22  # Orange: Product & Business Analysis
COLOR_LINKEDIN = 0x0A66C2       # LinkedIn Blue
COLOR_INDEED = 0x2164F3         # Indeed Blue
COLOR_DEFAULT = 0x5865F2        # Discord Blurple


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


def _get_embed_color(job: Dict[str, Any], is_top_tier: bool = False) -> int:
    """Select appropriate brand color:
    1. Gold for Top Tier / Big 4.
    2. Stream-specific color (Blue for Tech, Purple for Data/AI, Orange for Product).
    3. Fallback to site color.
    """
    if is_top_tier:
        return COLOR_TOP_TIER

    stream_color = job.get("stream_color")
    if stream_color:
        try:
            return int(stream_color)
        except (ValueError, TypeError):
            pass

    stream_key = job.get("stream_key")
    if stream_key == "tech_engineering":
        return COLOR_STREAM_TECH
    elif stream_key == "data_and_ai":
        return COLOR_STREAM_DATA
    elif stream_key == "product_and_analysis":
        return COLOR_STREAM_PRODUCT

    site = str(job.get("site") or "").lower()
    if "linkedin" in site:
        return COLOR_LINKEDIN
    if "indeed" in site:
        return COLOR_INDEED

    return COLOR_DEFAULT


def build_job_embed(job: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Discord Embed dictionary from a job record with stream routing, top employer highlight, and insights."""
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

    # Check extracted insights (Skills, YoE, Seniority)
    insights = job.get("insights")
    stream_name = job.get("stream_name", "General Tech")

    fields = []

    # 1. If top tier, prepend a prominent highlight banner field
    if is_top_tier:
        fields.append({
            "name": "⭐ PERUSAHAAN UNGGULAN (TOP TIER)",
            "value": f"**{company_match.badge}** • {company_match.canonical_name}",
            "inline": False,
        })

    # 2. Main metadata fields
    fields.extend([
        {"name": "📁 Stream", "value": f"**{stream_name}**", "inline": True},
        {"name": "🏢 Perusahaan", "value": company[:1000], "inline": True},
        {"name": "📍 Lokasi", "value": location[:1000], "inline": True},
    ])

    fields.extend([
        {"name": "🌐 Sumber", "value": site[:1000], "inline": True},
        {"name": "📅 Diposting", "value": str(date_posted)[:1000], "inline": True},
    ])

    # 3. Insights: Level & YoE
    if insights:
        if insights.seniority and insights.seniority != "Not Specified":
            fields.append({"name": "🎓 Level", "value": insights.seniority[:1000], "inline": True})
        if insights.yoe:
            fields.append({"name": "⏳ Pengalaman (YoE)", "value": insights.yoe[:1000], "inline": True})

    # 4. Job type
    if job_type:
        fields.append({"name": "💼 Tipe", "value": str(job_type).replace("_", " ").title()[:1000], "inline": True})

    # 5. Salary if available
    salary = _format_salary(job)
    if salary:
        fields.append({"name": "💰 Estimasi Gaji", "value": salary[:1000], "inline": True})

    # 6. Insights: Technical & SI Skills (Badges)
    if insights and insights.skills:
        skills_formatted = " ".join([f"`{s}`" for s in insights.skills[:10]])
        fields.append({
            "name": "🛠️ Keahlian / Tech Stack",
            "value": skills_formatted[:1000],
            "inline": False,
        })

    # 7. AI summary if available
    if insights and insights.summary:
        fields.append({
            "name": "💡 Ringkasan Posisi",
            "value": str(insights.summary)[:1000],
            "inline": False,
        })

    # 8. Query context
    matched_query = job.get("matched_query")
    if matched_query:
        fields.append({"name": "🎯 Pencarian Asal", "value": str(matched_query)[:1000], "inline": True})

    # 9. Link to apply
    if url:
        fields.append({"name": "🔗 Link Lamaran", "value": f"[Klik di sini untuk melamar]({url})", "inline": False})

    # Footer source indicator
    ai_tag = "🤖 AI Analyzed" if (insights and insights.source == "ai") else "⚡ Rule-Based"
    footer_text = f"Job Alert Bot • {stream_name} • {ai_tag}"
    if is_top_tier:
        footer_text = f"Job Alert Bot • {company_match.category} • {stream_name} • {ai_tag}"

    embed: Dict[str, Any] = {
        "title": raw_title[:250],
        "color": _get_embed_color(job, is_top_tier=is_top_tier),
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
    """Handles dispatching job alert embeds to Discord Webhooks with multi-stream channel routing."""

    def __init__(
        self,
        default_webhook_url: str = "",
        config: Optional[Config] = None,
        delay: float = 1.0,
    ):
        self.default_webhook_url = default_webhook_url.strip()
        self.config = config
        self.delay = max(0.2, delay)

    def has_any_webhook(self) -> bool:
        """Check if at least one webhook URL is configured."""
        if self.default_webhook_url and self.default_webhook_url.startswith("https://discord.com/api/webhooks/"):
            return True

        if self.config:
            for stream_key in ["tech_engineering", "data_and_ai", "product_and_analysis"]:
                url = self.config.get_webhook_for_stream(stream_key)
                if url and url.startswith("https://discord.com/api/webhooks/"):
                    return True

        return False

    def get_webhook_for_job(self, job: Dict[str, Any]) -> str:
        """Resolve specific target webhook URL for the job's stream, falling back to default webhook."""
        if self.config:
            stream_key = job.get("stream_key")
            url = self.config.get_webhook_for_stream(stream_key)
            if url and url.startswith("https://discord.com/api/webhooks/"):
                return url

        return self.default_webhook_url

    def send_single_job(self, job: Dict[str, Any], max_retries: int = 3) -> bool:
        """Send one job alert embed to the appropriate stream webhook with retry logic."""
        target_webhook = self.get_webhook_for_job(job)
        if not target_webhook or not target_webhook.startswith("https://discord.com/api/webhooks/"):
            logger.warning(
                "Tidak ada webhook URL yang valid untuk stream '%s' (job: '%s'). Melewati pengiriman.",
                job.get("stream_key"),
                job.get("title"),
            )
            return False

        embed = build_job_embed(job)
        payload = {
            "username": f"Job Alert Bot [{job.get('stream_name', 'Jobs')}]",
            "embeds": [embed],
        }

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(target_webhook, json=payload, timeout=15)

                if response.status_code in (200, 204):
                    logger.info(
                        "Berhasil mengirim alert [%s]: '%s' (%s)",
                        job.get("stream_name"),
                        job.get("title"),
                        job.get("company"),
                    )
                    return True

                if response.status_code == 429:
                    retry_after = 2.0
                    try:
                        retry_after = float(response.json().get("retry_after", 2.0))
                    except Exception:
                        pass
                    logger.warning(
                        "Discord Rate Limit tercapai. Menunggu %.2f detik (attempt %d/%d)...",
                        retry_after,
                        attempt,
                        max_retries,
                    )
                    time.sleep(retry_after)
                    continue

                logger.error("Gagal mengirim webhook. HTTP %d: %s", response.status_code, response.text)

            except requests.RequestException as exc:
                logger.error("Kesalahan jaringan saat mengirim webhook (attempt %d/%d): %s", attempt, max_retries, exc)
                time.sleep(1.0)

        return False

    def notify_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Send alerts for a list of jobs routed to their respective channel streams."""
        if not jobs:
            logger.info("Tidak ada lowongan baru untuk dikirim ke Discord.")
            return []

        if not self.has_any_webhook():
            logger.warning("Tidak ada webhook Discord yang dikonfigurasi. Mode dry-run/preview aktif.")
            return []

        successful: List[Dict[str, Any]] = []
        logger.info("Mengirim %d lowongan baru ke Discord multi-channel streams...", len(jobs))

        for idx, job in enumerate(jobs, 1):
            ok = self.send_single_job(job)
            if ok:
                successful.append(job)

            if idx < len(jobs):
                time.sleep(self.delay)

        logger.info("Selesai mengirim alerts: %d/%d berhasil terkirim.", len(successful), len(jobs))
        return successful
