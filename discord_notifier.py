"""Discord Webhook Notifier with Modern Minimalist 3-Column Card and batch-level role mentions."""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import requests

from config import Config

logger = logging.getLogger("job_alerts.discord")

# Aesthetics & Brand Colors (Modern Palette)
COLOR_TOP_TIER = 0xE5B842        # Champagne Gold: Top Tier / Big 4
COLOR_STREAM_TECH = 0x3B82F6      # Modern Blue: Tech & Engineering
COLOR_STREAM_DATA = 0x8B5CF6      # Indigo/Purple: Data & AI
COLOR_STREAM_PRODUCT = 0xF59E0B   # Warm Amber: Product & Business Analysis
COLOR_LINKEDIN = 0x0A66C2        # LinkedIn Blue
COLOR_INDEED = 0x2164F3          # Indeed Blue
COLOR_DEFAULT = 0x64748B         # Slate Gray (Neutral)

PORTAL_LOGOS = {
    "linkedin": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/linkedin.png",
    "indeed": "https://www.google.com/s2/favicons?domain=indeed.com&sz=128",
}

# Known Top Company Domain Mapping for Instant High-Res PNG Logos
TOP_COMPANY_DOMAINS = {
    "goto": "gojek.com",
    "gojek": "gojek.com",
    "tokopedia": "tokopedia.com",
    "traveloka": "traveloka.com",
    "shopee": "shopee.co.id",
    "grab": "grab.com",
    "tiket": "tiket.com",
    "blibli": "blibli.com",
    "bukalapak": "bukalapak.com",
    "dana": "dana.id",
    "xendit": "xendit.co",
    "kredivo": "kredivo.id",
    "efishery": "efishery.com",
    "ajaib": "ajaib.co.id",
    "bibit": "bibit.id",
    "stockbit": "stockbit.com",
    "dkatalis": "dkatalis.com",
    "sirclo": "sirclo.com",
    "komerce": "komerce.id",
    "ruangguru": "ruangguru.com",
    "google": "google.com",
    "microsoft": "microsoft.com",
    "amazon": "amazon.com",
    "aws": "aws.amazon.com",
    "bytedance": "bytedance.com",
    "tiktok": "tiktok.com",
    "meta": "meta.com",
    "pwc": "pwc.com",
    "deloitte": "deloitte.com",
    "ey": "ey.com",
    "kpmg": "kpmg.com",
    "mckinsey": "mckinsey.com",
    "bcg": "bcg.com",
    "bain": "bain.com",
    "accenture": "accenture.com",
    "bca": "bca.co.id",
    "mandiri": "bankmandiri.co.id",
    "bri": "bri.co.id",
    "bni": "bni.co.id",
    "dbs": "dbs.com",
    "cimb": "cimbniaga.co.id",
    "ocbc": "ocbc.id",
    "jenius": "jenius.com",
    "telkom": "telkom.co.id",
    "telkomsel": "telkomsel.com",
    "astra": "astra.co.id",
    "unilever": "unilever.co.id",
    "nestle": "nestle.co.id",
    "kalbe": "kalbe.co.id",
    "mayora": "mayoraindah.co.id",
    "wings": "wingscorp.com",
    "pertamina": "pertamina.com",
}


def _resolve_thumbnail_url(job: Dict[str, Any]) -> str:
    """Resolve a guaranteed raster PNG/JPEG thumbnail for Discord embed.
    Discord does NOT support SVG format for embed thumbnails.
    """
    # 1. Scraped logo (if valid raster image, not SVG)
    logo = job.get("company_logo")
    if logo and isinstance(logo, str) and logo.startswith("http") and not logo.lower().endswith(".svg"):
        return logo

    # 2. Known company logo via Google Favicon PNG
    company_name = str(job.get("company") or "")
    for keyword, domain in TOP_COMPANY_DOMAINS.items():
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, company_name, re.IGNORECASE):
            return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    # 3. Fallback to Job Portal Official PNG Logo
    site_key = str(job.get("site") or "linkedin").lower()
    return PORTAL_LOGOS.get(site_key, PORTAL_LOGOS["linkedin"])


def _format_salary(job: Dict[str, Any]) -> Optional[str]:
    """Format salary information cleanly if available."""
    min_amt = job.get("min_amount")
    max_amt = job.get("max_amount")
    currency = job.get("currency") or "IDR"
    interval = job.get("interval") or "bln"
    if interval.lower() in ("monthly", "month"):
        interval = "bulan"
    elif interval.lower() in ("yearly", "year", "annually", "annual"):
        interval = "tahun"

    if min_amt is not None and max_amt is not None:
        try:
            return f"{currency} {float(min_amt):,.0f} - {float(max_amt):,.0f} / {interval}".strip()
        except (ValueError, TypeError):
            return f"{currency} {min_amt} - {max_amt} / {interval}".strip()
    elif min_amt is not None:
        try:
            return f"{currency} ≥ {float(min_amt):,.0f} / {interval}".strip()
        except (ValueError, TypeError):
            return f"{currency} ≥ {min_amt} / {interval}".strip()
    elif max_amt is not None:
        try:
            return f"{currency} ≤ {float(max_amt):,.0f} / {interval}".strip()
        except (ValueError, TypeError):
            return f"{currency} ≤ {max_amt} / {interval}".strip()

    compensation = job.get("compensation")
    if compensation and isinstance(compensation, str) and compensation.strip():
        return compensation.strip()

    return None


def _get_embed_color(job: Dict[str, Any], is_top_tier: bool = False) -> int:
    """Select appropriate brand color:
    1. Champagne Gold for Top Tier / Big 4.
    2. Stream-specific color (Blue for Tech, Purple for Data, Amber for Product).
    3. Fallback to site/default color.
    """
    if is_top_tier:
        return COLOR_TOP_TIER

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
    """Build a clean Modern Minimalist Discord Embed with 3-column glanceable grid."""
    title = str(job.get("title") or "Lowongan Pekerjaan").strip()[:250]
    company = str(job.get("company") or "Perusahaan").strip()
    raw_location = str(job.get("location") or "").strip()
    is_remote = job.get("is_remote")

    # Format location with remote tag
    if is_remote and raw_location:
        location = f"{raw_location} (Remote)"
    elif is_remote:
        location = "Remote Friendly"
    else:
        location = raw_location or "Indonesia"

    url = job.get("job_url") or job.get("job_url_direct") or ""
    site = str(job.get("site") or "LinkedIn").capitalize()
    date_posted = job.get("date_posted") or "Baru saja"
    job_type = job.get("job_type")

    # Top company classification
    company_match = job.get("company_match")
    is_top_tier = company_match is not None

    # Extracted insights
    insights = job.get("insights")
    salary = _format_salary(job)

    # Sub-header description: Company • Location • Optional Top Tier badge + full-width divider
    header_parts = [f"**{company}**", location]
    if is_top_tier and company_match:
        header_parts.append(company_match.badge)
    divider = "─" * 58
    description_text = " • ".join(header_parts) + f"\n{divider}"
    fields = []

    # 1. 3-Column Modern Grid (Tipe Kerja, Pengalaman, Level)
    formatted_type = str(job_type).replace("_", " ").title() if job_type else "Full-time"
    formatted_yoe = insights.yoe if (insights and insights.yoe) else "Tidak Disebutkan"
    formatted_level = insights.seniority if (insights and insights.seniority and insights.seniority != "Not Specified") else "Semua Level"

    fields.append({"name": "💼 Tipe Kerja", "value": formatted_type, "inline": True})
    fields.append({"name": "⏳ Pengalaman", "value": formatted_yoe, "inline": True})
    fields.append({"name": "🎓 Level", "value": formatted_level, "inline": True})

    # 2. Salary Callout (if available)
    if salary:
        fields.append({
            "name": "💰 Estimasi Kompensasi",
            "value": f"**{salary}**",
            "inline": False,
        })

    # 3. Key Tech Stack & Tools (clean code pills)
    if insights and insights.skills:
        skills_formatted = "  ".join([f"`{s}`" for s in insights.skills[:8]])
        fields.append({
            "name": "🛠️ Tech Stack & Tools",
            "value": skills_formatted[:1000],
            "inline": False,
        })

    # 4. Optional brief summary/notes
    if insights and insights.summary:
        fields.append({
            "name": "📌 Catatan Posisi",
            "value": str(insights.summary)[:1000],
            "inline": False,
        })

    # 5. Clean external link CTA
    if url:
        fields.append({
            "name": "\u200b",
            "value": f"👉 **[Lamar Sekarang di {site} ↗]({url})**",
            "inline": False,
        })

    # Clean, human footer with timestamp
    footer_text = f"{site} • Diposting {date_posted}"

    embed: Dict[str, Any] = {
        "title": title,
        "description": description_text,
        "color": _get_embed_color(job, is_top_tier=is_top_tier),
        "fields": fields,
        "footer": {
            "text": footer_text,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if url:
        embed["url"] = url

    # Thumbnail: Guaranteed raster PNG (Company Logo or Portal Fallback)
    thumbnail_url = _resolve_thumbnail_url(job)
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}
    return embed


class DiscordNotifier:
    """Handles dispatching job alert embeds to Discord Webhooks with stream routing and batch-level mentions."""

    def __init__(
        self,
        default_webhook_url: str = "",
        config: Optional[Config] = None,
        delay: float = 1.0,
    ):
        self.default_webhook_url = default_webhook_url.strip()
        self.config = config
        self.delay = max(0.2, delay)
        # Track streams that have already pinged in this execution batch
        self.pinged_streams: Set[str] = set()

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

    def send_single_job(
        self,
        job: Dict[str, Any],
        mention_role: bool = False,
        max_retries: int = 3,
    ) -> bool:
        """Send one job alert embed to the appropriate stream webhook with optional role mention."""
        target_webhook = self.get_webhook_for_job(job)
        if not target_webhook or not target_webhook.startswith("https://discord.com/api/webhooks/"):
            logger.warning(
                "Tidak ada webhook URL yang valid untuk stream '%s' (job: '%s'). Melewati pengiriman.",
                job.get("stream_key"),
                job.get("title"),
            )
            return False

        embed = build_job_embed(job)
        stream_key = job.get("stream_key", "")
        stream_name = job.get("stream_name", "")
        bot_username = f"Jobville • {stream_name}" if stream_name else "Jobville"

        payload: Dict[str, Any] = {
            "username": bot_username,
            "embeds": [embed],
        }

        # Role mention / member tag ONLY on batch trigger
        if mention_role:
            role_id = job.get("role_id")
            if not role_id and self.config:
                streams = self.config.discord_routing.get("streams", {})
                role_id = streams.get(stream_key, {}).get("role_id")

            if role_id:
                payload["content"] = f"<@&{role_id}>"
                payload["allowed_mentions"] = {"roles": [str(role_id)]}

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(target_webhook, json=payload, timeout=15)

                if response.status_code in (200, 204):
                    logger.info(
                        "Berhasil mengirim alert [%s]: '%s' (%s) (Mention: %s)",
                        job.get("stream_name", "General"),
                        job.get("title"),
                        job.get("company"),
                        mention_role,
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
        """Send alerts for a list of jobs routed to their respective channel streams.
        Mentions the stream role ONLY ONCE per batch/run.
        """
        if not jobs:
            logger.info("Tidak ada lowongan baru untuk dikirim ke Discord.")
            return []

        if not self.has_any_webhook():
            logger.warning("Tidak ada webhook Discord yang dikonfigurasi. Mode dry-run/preview aktif.")
            return []

        successful: List[Dict[str, Any]] = []
        logger.info("Mengirim %d lowongan baru ke Discord multi-channel streams...", len(jobs))

        for idx, job in enumerate(jobs, 1):
            stream_key = job.get("stream_key", "default")
            # Mention role ONLY for the first job of each stream in this batch
            mention_role = stream_key not in self.pinged_streams

            ok = self.send_single_job(job, mention_role=mention_role)
            if ok:
                successful.append(job)
                self.pinged_streams.add(stream_key)

            if idx < len(jobs):
                time.sleep(self.delay)

        logger.info("Selesai mengirim alerts: %d/%d berhasil terkirim.", len(successful), len(jobs))
        return successful
