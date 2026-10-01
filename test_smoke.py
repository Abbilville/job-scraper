"""Smoke and unit tests for Job Alert Bot."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from config import Config
from dedup import JobDeduplicator
from discord_notifier import DiscordNotifier, build_job_embed


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = Config()
        self.assertEqual(cfg.search_term, "Frontend Developer")
        self.assertEqual(cfg.location, "Indonesia")
        self.assertEqual(cfg.hours_old, 24)
        self.assertEqual(cfg.results_wanted, 15)
        self.assertFalse(cfg.is_remote)
        self.assertTrue(cfg.enable_indeed_fallback)
        self.assertIn("linkedin", cfg.site_names)


class TestDeduplication(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = os.path.join(self.temp_dir.name, "seen_test.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dedup_lifecycle(self):
        dedup = JobDeduplicator(filepath=self.temp_file, max_history=5)
        self.assertEqual(len(dedup.seen_data), 0)

        job1 = {
            "id": "li-12345",
            "title": "Frontend Engineer",
            "company": "Acme Corp",
            "job_url": "https://linkedin.com/jobs/view/12345",
            "date_posted": "2026-10-01",
            "site": "linkedin",
        }
        job2 = {
            "id": "li-67890",
            "title": "React Developer",
            "company": "Beta Inc",
            "job_url": "https://linkedin.com/jobs/view/67890",
            "date_posted": "2026-10-01",
            "site": "linkedin",
        }

        self.assertFalse(dedup.is_seen(job1))
        dedup.mark_seen(job1)
        self.assertTrue(dedup.is_seen(job1))
        self.assertFalse(dedup.is_seen(job2))

        # Test filter_unseen
        unseen = dedup.filter_unseen([job1, job2])
        self.assertEqual(len(unseen), 1)
        self.assertEqual(unseen[0]["id"], "li-67890")

        # Save and reload
        dedup.save()
        self.assertTrue(os.path.exists(self.temp_file))

        dedup2 = JobDeduplicator(filepath=self.temp_file, max_history=5)
        self.assertTrue(dedup2.is_seen("li-12345"))
        self.assertFalse(dedup2.is_seen("li-67890"))

    def test_dedup_pruning(self):
        dedup = JobDeduplicator(filepath=self.temp_file, max_history=3)
        for i in range(5):
            dedup.mark_seen({"id": f"job-{i}", "title": f"Job {i}"})

        dedup.save()
        dedup_reloaded = JobDeduplicator(filepath=self.temp_file, max_history=3)
        self.assertLessEqual(len(dedup_reloaded.seen_data), 3)


class TestDiscordNotifier(unittest.TestCase):
    def test_build_embed_basic(self):
        job = {
            "title": "Senior Frontend Developer",
            "company": "Tech Nusantara",
            "location": "Jakarta, Indonesia",
            "is_remote": True,
            "site": "linkedin",
            "date_posted": "2026-09-30",
            "job_url": "https://www.linkedin.com/jobs/view/123",
            "min_amount": 15000000,
            "max_amount": 25000000,
            "currency": "IDR",
            "interval": "monthly",
            "job_type": "full_time",
        }
        embed = build_job_embed(job)
        self.assertEqual(embed["title"], "Senior Frontend Developer")
        self.assertEqual(embed["url"], "https://www.linkedin.com/jobs/view/123")
        self.assertEqual(embed["color"], 0x0A66C2)  # LinkedIn blue

        # Verify fields
        field_dict = {f["name"]: f["value"] for f in embed["fields"]}
        self.assertIn("🏢 Perusahaan", field_dict)
        self.assertEqual(field_dict["🏢 Perusahaan"], "Tech Nusantara")
        self.assertIn("Jakarta, Indonesia (Remote)", field_dict["📍 Lokasi"])
        self.assertIn("IDR", field_dict["💰 Estimasi Gaji"])

    def test_build_embed_indeed_color(self):
        job = {
            "title": "Frontend Engineer",
            "site": "indeed",
            "job_url": "https://indeed.com/viewjob?jk=abc",
        }
        embed = build_job_embed(job)
        self.assertEqual(embed["color"], 0x2164F3)  # Indeed blue

    @patch("requests.post")
    def test_notifier_send(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")
        success = notifier.send_single_job({"title": "Test Job", "job_url": "https://example.com"})
        self.assertTrue(success)
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
