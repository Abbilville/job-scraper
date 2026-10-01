"""Comprehensive smoke and unit tests for Job Alert Bot."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from company_filter import CompanyMatch, CompanyMatcher
from config import load_config
from dedup import JobDeduplicator
from discord_notifier import (
    COLOR_DEFAULT,
    COLOR_LINKEDIN,
    COLOR_TOP_TIER,
    DiscordNotifier,
    build_job_embed,
)
from extractor import (
    JobInsights,
    extract_job_insights,
    extract_seniority_rule_based,
    extract_skills_rule_based,
    extract_with_ai,
    extract_yoe_rule_based,
)


class TestConfigAndCompanyMatcher(unittest.TestCase):
    def test_config_json_loaded(self):
        cfg = load_config("config.json")
        self.assertIn("Frontend Developer", cfg.search_terms)
        self.assertIn("AI Engineer", cfg.search_terms)
        self.assertIn("Forward Deployed Engineer", cfg.search_terms)
        self.assertIn("Indonesia", cfg.locations)
        self.assertEqual(cfg.filter_mode, "highlight")
        self.assertIn("Big 4 & Strategy Consulting", cfg.top_companies)

    def test_company_matcher_from_config(self):
        cfg = load_config("config.json")
        matcher = CompanyMatcher(
            top_companies_dict=cfg.top_companies,
            custom_companies=["Keluarga Mahasiswa UI"],
        )

        # Big 4
        m_pwc = matcher.match("PricewaterhouseCoopers Indonesia")
        self.assertIsNotNone(m_pwc)
        self.assertEqual(m_pwc.canonical_name, "PwC")

        # Top Tech
        m_goto = matcher.match("PT Tokopedia")
        self.assertIsNotNone(m_goto)

        m_grab = matcher.match("Grab Holdings")
        self.assertIsNotNone(m_grab)

        # Banking
        m_bca = matcher.match("PT Bank Central Asia Tbk")
        self.assertIsNotNone(m_bca)

        # Custom
        m_custom = matcher.match("Keluarga Mahasiswa UI")
        self.assertIsNotNone(m_custom)
        self.assertEqual(m_custom.canonical_name, "Keluarga Mahasiswa UI")

        # Unknown
        m_unknown = matcher.match("PT Warung Kopi Sederhana")
        self.assertIsNone(m_unknown)


class TestExtractor(unittest.TestCase):
    def test_skills_extraction(self):
        desc = (
            "We are looking for an AI Engineer proficient in Python, PyTorch, and Docker. "
            "Experience with LangChain, Next.js, and PostgreSQL is highly desired."
        )
        skills = extract_skills_rule_based(desc)
        self.assertIn("Python", skills)
        self.assertIn("PyTorch", skills)
        self.assertIn("Docker", skills)
        self.assertIn("LangChain", skills)
        self.assertIn("Next.js", skills)
        self.assertIn("PostgreSQL", skills)

    def test_yoe_extraction(self):
        self.assertEqual(extract_yoe_rule_based("Requires 2-4 years of experience"), "2-4 tahun")
        self.assertEqual(extract_yoe_rule_based("Minimal 3 tahun pengalaman kerja"), "Min. 3 tahun")
        self.assertEqual(extract_yoe_rule_based("5+ years of software development"), "5+ tahun")
        self.assertEqual(extract_yoe_rule_based("Fresh graduates are welcome to apply"), "Fresh Graduate (0-1 tahun)")
        self.assertEqual(extract_yoe_rule_based("Summer Internship Program"), "Internship / Mahasiswa")

    def test_seniority_extraction(self):
        self.assertEqual(extract_seniority_rule_based("Lead Software Engineer", ""), "Lead / Principal")
        self.assertEqual(extract_seniority_rule_based("Senior Frontend Developer", ""), "Senior")
        self.assertEqual(extract_seniority_rule_based("Junior Backend Engineer", ""), "Junior / Associate")
        self.assertEqual(extract_seniority_rule_based("Frontend Engineering Intern", ""), "Internship")

    @patch("requests.post")
    def test_ai_extraction_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "skills": ["Python", "FastAPI"],
                "yoe": "1-2 tahun",
                "seniority": "Junior",
                "summary": "Membangun microservices dengan FastAPI",
            },
        )
        insights = extract_with_ai(
            title="Backend Engineer",
            company="Startup",
            description="Sample text",
            api_url="https://ai.example.com/extract",
            api_key="secret",
        )
        self.assertIsNotNone(insights)
        self.assertEqual(insights.source, "ai")
        self.assertIn("FastAPI", insights.skills)
        self.assertEqual(insights.yoe, "1-2 tahun")


class TestDeduplication(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = os.path.join(self.temp_dir.name, "seen_test.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dedup_lifecycle(self):
        dedup = JobDeduplicator(filepath=self.temp_file, max_history=5)
        job1 = {"id": "li-12345", "title": "Frontend Engineer", "company": "PwC"}
        job2 = {"id": "li-67890", "title": "AI Engineer", "company": "Gojek"}

        self.assertFalse(dedup.is_seen(job1))
        dedup.mark_seen(job1)
        self.assertTrue(dedup.is_seen(job1))

        unseen = dedup.filter_unseen([job1, job2])
        self.assertEqual(len(unseen), 1)
        self.assertEqual(unseen[0]["id"], "li-67890")

        dedup.save()
        dedup_reloaded = JobDeduplicator(filepath=self.temp_file, max_history=5)
        self.assertTrue(dedup_reloaded.is_seen("li-12345"))


class TestDiscordNotifier(unittest.TestCase):
    def test_build_embed_with_insights(self):
        job = {
            "title": "AI Engineer",
            "company": "Shopee",
            "site": "linkedin",
            "job_url": "https://linkedin.com/jobs/view/111",
            "company_match": CompanyMatch(
                canonical_name="Shopee / Sea Group",
                category="Top Tech Giants & Unicorns",
                badge="🚀 Top Tech Giant",
            ),
            "insights": JobInsights(
                skills=["Python", "PyTorch", "Docker"],
                yoe="1-3 tahun",
                seniority="Junior / Associate",
                summary="Fokus pada computer vision model",
                source="ai",
            ),
        }
        embed = build_job_embed(job)
        self.assertEqual(embed["color"], COLOR_TOP_TIER)
        field_dict = {f["name"]: f["value"] for f in embed["fields"]}
        self.assertIn("⭐ PERUSAHAAN UNGGULAN (TOP TIER)", field_dict)
        self.assertIn("🛠️ Keahlian / Tech Stack", field_dict)
        self.assertIn("`Python`", field_dict["🛠️ Keahlian / Tech Stack"])
        self.assertIn("🎓 Level", field_dict)
        self.assertEqual(field_dict["🎓 Level"], "Junior / Associate")
        self.assertIn("🤖 AI Analyzed", embed["footer"]["text"])


if __name__ == "__main__":
    unittest.main()
