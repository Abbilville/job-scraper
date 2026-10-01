"""Smoke and unit tests for Job Alert Bot with multi-search and company filter tests."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from company_filter import CompanyMatch, CompanyMatcher
from config import Config
from dedup import JobDeduplicator
from discord_notifier import COLOR_TOP_TIER, COLOR_LINKEDIN, DiscordNotifier, build_job_embed


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = Config()
        self.assertIn("Frontend Developer", cfg.search_terms)
        self.assertIn("Indonesia", cfg.locations)
        self.assertEqual(cfg.hours_old, 24)
        self.assertEqual(cfg.results_wanted, 15)
        self.assertFalse(cfg.is_remote)
        self.assertTrue(cfg.enable_indeed_fallback)
        self.assertEqual(cfg.filter_mode, "highlight")
        self.assertIn("linkedin", cfg.site_names)


class TestCompanyMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = CompanyMatcher(custom_companies=["Special UI Startup"])

    def test_big4_matching(self):
        match_pwc = self.matcher.match("PwC Indonesia")
        self.assertIsNotNone(match_pwc)
        self.assertEqual(match_pwc.canonical_name, "PwC")
        self.assertEqual(match_pwc.category, "Big 4 Consulting")

        match_ey = self.matcher.match("Ernst & Young Advisory")
        self.assertIsNotNone(match_ey)
        self.assertEqual(match_ey.canonical_name, "EY (Ernst & Young)")

    def test_top_tech_matching(self):
        match_goto = self.matcher.match("PT Tokopedia")
        self.assertIsNotNone(match_goto)
        self.assertEqual(match_goto.canonical_name, "GoTo (Gojek & Tokopedia)")

        match_shopee = self.matcher.match("Shopee International Indonesia")
        self.assertIsNotNone(match_shopee)

        match_traveloka = self.matcher.match("Traveloka Indonesia")
        self.assertIsNotNone(match_traveloka)

    def test_banking_and_fmcg_matching(self):
        match_bca = self.matcher.match("PT Bank Central Asia Tbk")
        self.assertIsNotNone(match_bca)
        self.assertEqual(match_bca.canonical_name, "Bank Central Asia (BCA)")

        match_unilever = self.matcher.match("PT Unilever Indonesia Tbk")
        self.assertIsNotNone(match_unilever)

    def test_custom_company_matching(self):
        match_custom = self.matcher.match("Special UI Startup")
        self.assertIsNotNone(match_custom)
        self.assertEqual(match_custom.canonical_name, "Special UI Startup")

    def test_unmatched_company(self):
        match = self.matcher.match("Toko Kelontong Sejahtera")
        self.assertIsNone(match)


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
            "company": "PwC Indonesia",
            "job_url": "https://linkedin.com/jobs/view/12345",
            "date_posted": "2026-10-01",
            "site": "linkedin",
        }
        job2 = {
            "id": "li-67890",
            "title": "React Developer",
            "company": "PT Tokopedia",
            "job_url": "https://linkedin.com/jobs/view/67890",
            "date_posted": "2026-10-01",
            "site": "linkedin",
        }

        self.assertFalse(dedup.is_seen(job1))
        dedup.mark_seen(job1)
        self.assertTrue(dedup.is_seen(job1))
        self.assertFalse(dedup.is_seen(job2))

        unseen = dedup.filter_unseen([job1, job2])
        self.assertEqual(len(unseen), 1)
        self.assertEqual(unseen[0]["id"], "li-67890")

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
    def test_build_embed_standard(self):
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
        self.assertEqual(embed["color"], COLOR_LINKEDIN)

    def test_build_embed_top_tier_highlight(self):
        job = {
            "title": "Frontend Engineer",
            "company": "PwC Indonesia",
            "site": "linkedin",
            "job_url": "https://linkedin.com/jobs/view/999",
            "company_match": CompanyMatch(
                canonical_name="PwC",
                category="Big 4 Consulting",
                badge="🏆 Big 4 Consulting",
            ),
        }
        embed = build_job_embed(job)
        self.assertEqual(embed["color"], COLOR_TOP_TIER)
        # Verify highlight field
        field_names = [f["name"] for f in embed["fields"]]
        self.assertIn("⭐ PERUSAHAAN UNGGULAN (TOP TIER)", field_names)
        self.assertIn("Big 4 Consulting", embed["footer"]["text"])

    @patch("requests.post")
    def test_notifier_send(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")
        success = notifier.send_single_job({"title": "Test Job", "job_url": "https://example.com"})
        self.assertTrue(success)
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
