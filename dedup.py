"""Deduplication manager using seen_jobs.json to prevent duplicate alerts."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("job_alerts.dedup")


class JobDeduplicator:
    """Manages history of seen job postings to prevent duplicate alerts."""

    def __init__(self, filepath: str = "seen_jobs.json", max_history: int = 1000):
        self.filepath = filepath
        self.max_history = max_history
        self.seen_data: Dict[str, Dict[str, Any]] = {}
        self.load()

    def _normalize_key(self, job_or_id: Any) -> str:
        if isinstance(job_or_id, dict):
            # Prefer id, fallback to job_url or job_url_direct
            key = job_or_id.get("id") or job_or_id.get("job_url") or job_or_id.get("job_url_direct")
        else:
            key = str(job_or_id) if job_or_id is not None else ""
        return str(key).strip()

    def load(self) -> None:
        """Load seen jobs from JSON file."""
        if not os.path.exists(self.filepath):
            logger.info("File '%s' belum ada. Riwayat seen jobs kosong.", self.filepath)
            self.seen_data = {}
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)

            if isinstance(raw, dict):
                # Standard format with metadata: {"jobs": {...}}
                if "jobs" in raw and isinstance(raw["jobs"], dict):
                    self.seen_data = raw["jobs"]
                else:
                    # Simple dict format: {"id": ...}
                    self.seen_data = {
                        str(k): (v if isinstance(v, dict) else {"first_seen": None})
                        for k, v in raw.items()
                    }
            elif isinstance(raw, list):
                # List format: ["id1", "id2"]
                self.seen_data = {str(item): {"first_seen": None} for item in raw}
            else:
                self.seen_data = {}

            logger.info("Berhasil memuat %d riwayat lowongan dari '%s'.", len(self.seen_data), self.filepath)
        except Exception as exc:
            logger.warning("Gagal membaca '%s' (%s). Memulai dengan riwayat kosong.", self.filepath, exc)
            self.seen_data = {}

    def is_seen(self, job_or_id: Any) -> bool:
        """Check if a job has already been seen."""
        key = self._normalize_key(job_or_id)
        if not key:
            return False

        if key in self.seen_data:
            return True

        # Secondary check by URL if key was an ID or vice versa
        if isinstance(job_or_id, dict):
            url = job_or_id.get("job_url") or job_or_id.get("job_url_direct")
            if url and str(url).strip() in self.seen_data:
                return True

        return False

    def mark_seen(self, job: Dict[str, Any]) -> None:
        """Mark a single job as seen with metadata."""
        key = self._normalize_key(job)
        if not key:
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        self.seen_data[key] = {
            "title": job.get("title"),
            "company": job.get("company"),
            "site": job.get("site"),
            "job_url": job.get("job_url") or job.get("job_url_direct"),
            "date_posted": job.get("date_posted"),
            "first_seen": now_iso,
        }

    def filter_unseen(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out already seen jobs from a list."""
        unseen = [job for job in jobs if not self.is_seen(job)]
        logger.info(
            "Deduplikasi selesai: %d dari %d lowongan adalah lowongan baru.",
            len(unseen),
            len(jobs),
        )
        return unseen

    def _prune(self) -> None:
        """Prune oldest entries if history exceeds max_history."""
        if len(self.seen_data) <= self.max_history:
            return

        # Sort by first_seen or keep recent items
        overflow = len(self.seen_data) - self.max_history
        keys_to_remove = list(self.seen_data.keys())[:overflow]
        for k in keys_to_remove:
            del self.seen_data[k]
        logger.info("Memangkas %d riwayat seen jobs lama agar file tetap optimal.", overflow)

    def save(self) -> None:
        """Save seen jobs to JSON file with atomic write."""
        self._prune()
        payload = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_seen": len(self.seen_data),
            "jobs": self.seen_data,
        }

        temp_filepath = f"{self.filepath}.tmp"
        try:
            with open(temp_filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(temp_filepath, self.filepath)
            logger.info("Riwayat lowongan berhasil disimpan ke '%s' (total: %d).", self.filepath, len(self.seen_data))
        except Exception as exc:
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except OSError:
                    pass
            logger.error("Gagal menyimpan riwayat seen jobs ke '%s': %s", self.filepath, exc)
            raise
