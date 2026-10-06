"""Comprehensive smoke and unit tests for Job Alert Bot (SI & Multi-Stream Edition)."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from company_filter import CompanyMatch, CompanyMatcher
from config import Config, load_config
from dedup import JobDeduplicator
from discord_notifier import (
    COLOR_STREAM_DATA,
    COLOR_STREAM_PRODUCT,
    COLOR_STREAM_TECH,
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
from main import classify_stream, is_location_allowed, is_title_excluded


class TestConfigAndCompanyMatcher(unittest.TestCase):
    def test_config_json_loaded(self):
        cfg = load_config("config.json")
        self.assertIn("Product Manager", cfg.search_terms)
        self.assertIn("Associate Product Manager", cfg.search_terms)
        self.assertIn("Business Analyst", cfg.search_terms)
        self.assertIn("BI Analyst", cfg.search_terms)
        self.assertIn("Data Scientist", cfg.search_terms)
        self.assertIn("Software Engineer", cfg.search_terms)
        self.assertIn("Senior", cfg.exclude_title_keywords)
        self.assertIn("Product Marketing", cfg.exclude_title_keywords)
        self.assertIn("tech_engineering", cfg.discord_routing.get("streams", {}))
        self.assertIn("data_and_ai", cfg.discord_routing.get("streams", {}))
        self.assertIn("product_and_analysis", cfg.discord_routing.get("streams", {}))

    def test_new_companies_matcher(self):
        cfg = load_config("config.json")
        matcher = CompanyMatcher(top_companies_dict=cfg.top_companies)

        # SI / Tech additions
        m_tiket = matcher.match("PT Global Tiket Network (tiket.com)")
        self.assertIsNotNone(m_tiket)

        m_sirclo = matcher.match("PT Sirclo Teknologi Indonesia")
        self.assertIsNotNone(m_sirclo)

        m_dkatalis = matcher.match("DKATALIS Digital Lab")
        self.assertIsNotNone(m_dkatalis)

        m_komerce = matcher.match("Komerce Indonesia")
        self.assertIsNotNone(m_komerce)

        # FMCG & Healthcare additions
        m_mayora = matcher.match("PT Mayora Indah Tbk")
        self.assertIsNotNone(m_mayora)

        m_wings = matcher.match("Wings Group Indonesia")
        self.assertIsNotNone(m_wings)

        m_kalbe = matcher.match("PT Kalbe Farma Tbk")
        self.assertIsNotNone(m_kalbe)

    def test_sea_and_traveloka_company_match(self):
        cfg = load_config("config.json")
        matcher = CompanyMatcher(top_companies_dict=cfg.top_companies)
        m_sea = matcher.match("Sea")
        self.assertIsNotNone(m_sea)
        self.assertEqual(m_sea.canonical_name, "Shopee / Sea Group")


class TestExclusionAndStreamRouting(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config("config.json")

    def test_negative_title_exclusion(self):
        exclude_kw = self.cfg.exclude_title_keywords

        # Forbidden titles
        is_ex, reason = is_title_excluded("Senior Product Manager", exclude_kw)
        self.assertTrue(is_ex)
        self.assertEqual(reason, "Senior")

        is_ex, reason = is_title_excluded("VP of Engineering", exclude_kw)
        self.assertTrue(is_ex)
        self.assertEqual(reason, "VP")

        is_ex, reason = is_title_excluded("Medical Representative", exclude_kw)
        self.assertTrue(is_ex)

        is_ex, reason = is_title_excluded("Product Marketing Lead", exclude_kw)
        self.assertTrue(is_ex)

        # Allowed titles
        is_ex, reason = is_title_excluded("Associate Product Manager", exclude_kw)
        self.assertFalse(is_ex)

        is_ex, reason = is_title_excluded("Junior Business Analyst", exclude_kw)
        self.assertFalse(is_ex)

        is_ex, reason = is_title_excluded("Software Engineer", exclude_kw)
        self.assertFalse(is_ex)

    def test_stream_classification(self):
        routing = self.cfg.discord_routing

        # Product & Analysis stream
        self.assertEqual(
            classify_stream({"title": "Associate Product Manager", "matched_query": ""}, routing),
            "product_and_analysis",
        )
        self.assertEqual(
            classify_stream({"title": "IT Business Analyst", "matched_query": ""}, routing),
            "product_and_analysis",
        )
        self.assertEqual(
            classify_stream({"title": "Product Owner", "matched_query": ""}, routing),
            "product_and_analysis",
        )

        # Data & AI stream
        self.assertEqual(
            classify_stream({"title": "Data Scientist", "matched_query": ""}, routing),
            "data_and_ai",
        )
        self.assertEqual(
            classify_stream({"title": "BI Analyst", "matched_query": ""}, routing),
            "data_and_ai",
        )
        self.assertEqual(
            classify_stream({"title": "Machine Learning Engineer", "matched_query": ""}, routing),
            "data_and_ai",
        )

        # Tech & Engineering stream
        self.assertEqual(
            classify_stream({"title": "Backend Developer", "matched_query": ""}, routing),
            "tech_engineering",
        )
        self.assertEqual(
            classify_stream({"title": "DevOps Engineer", "matched_query": ""}, routing),
            "tech_engineering",
        )

    def test_location_filtering(self):
        allowed_locations = ["Indonesia", "Jakarta"]

        # Allowed locations
        self.assertTrue(is_location_allowed({"location": "Jakarta, Indonesia"}, allowed_locations))
        self.assertTrue(is_location_allowed({"location": "Bandung, Jawa Barat"}, allowed_locations))
        self.assertTrue(is_location_allowed({"location": "Batam, Kepulauan Riau"}, allowed_locations))
        self.assertTrue(is_location_allowed({"location": "Remote Friendly", "is_remote": True}, allowed_locations))
        self.assertTrue(is_location_allowed({"location": "Worldwide", "is_remote": True}, allowed_locations))
        self.assertTrue(is_location_allowed({"location": ""}, allowed_locations))

        # Rejected foreign locations
        self.assertFalse(is_location_allowed({"location": "Paris, France"}, allowed_locations))
        self.assertFalse(is_location_allowed({"location": "London, United Kingdom"}, allowed_locations))
        self.assertFalse(is_location_allowed({"location": "Munich, Germany"}, allowed_locations))
        self.assertFalse(is_location_allowed({"location": "Houston, TX"}, allowed_locations))
        self.assertFalse(is_location_allowed({"location": "São Paulo, Brazil"}, allowed_locations))


class TestExtractorSIAndTech(unittest.TestCase):
    def test_si_and_product_skills_extraction(self):
        desc = (
            "Responsibilities: Gather business requirements and create BRD, FSD, and BPMN diagrams. "
            "Manage user stories in Jira and Confluence. Collaborate with UI/UX using Figma. "
            "Strong SQL and Power BI dashboarding skills are required."
        )
        skills = extract_skills_rule_based(desc)
        self.assertIn("Jira", skills)
        self.assertIn("Confluence", skills)
        self.assertIn("Figma", skills)
        self.assertIn("BPMN", skills)
        self.assertIn("BRD", skills)
        self.assertIn("FSD", skills)
        self.assertIn("Power BI", skills)
        self.assertIn("SQL", skills)

    def test_level_code_normalization(self):
        _, lvl_intern = extract_seniority_rule_based("Product Intern", "")
        self.assertEqual(lvl_intern, "internship")

        _, lvl_junior = extract_seniority_rule_based("Junior Business Analyst", "")
        self.assertEqual(lvl_junior, "associate")

        _, lvl_senior = extract_seniority_rule_based("Senior BI Developer", "")
        self.assertEqual(lvl_senior, "senior")

    def test_seniority_fallback_not_false_positive_senior(self):
        # Mentions senior manager in description but role is Junior / General
        desc_with_senior_mgr = "Responsibilities: Report to Senior Engineering Manager. Work on frontend."
        _, lvl = extract_seniority_rule_based("Software Developer", desc_with_senior_mgr)
        self.assertNotEqual(lvl, "senior")
        self.assertEqual(lvl, "mid_senior")

        # Fresh graduate mentioning senior mentor
        desc_fresh_with_senior = "Open for fresh graduates. You will be mentored by senior engineers."
        _, lvl_fresh = extract_seniority_rule_based("Software Engineer", desc_fresh_with_senior)
        self.assertEqual(lvl_fresh, "entry_level")

    def test_markdown_unescaping_and_yoe_extraction(self):
        # Test escaped hyphens and pluses from jobspy markdown descriptions
        self.assertEqual(extract_yoe_rule_based("Qualifications: 3\\-5 years of working experience in software"), "3-5 tahun")
        self.assertEqual(extract_yoe_rule_based("* 5\\+ years of DevOps experience"), "5+ tahun")
        self.assertEqual(extract_yoe_rule_based("* 0\\-2 years of relevant work experience"), "0-2 tahun")
        self.assertEqual(extract_yoe_rule_based("with at least 10 years of professional experience"), "Min. 10 tahun")
        self.assertEqual(extract_yoe_rule_based("3\\+ years in software development (SQL, Power BI, Azure)"), "3+ tahun")
        self.assertEqual(extract_yoe_rule_based("You should have 15 years experiences."), "Min. 15 tahun")
        self.assertEqual(extract_yoe_rule_based("Pengalaman minimal 3 tahun di bidang backend"), "Min. 3 tahun")
        self.assertEqual(extract_yoe_rule_based("Minimal 2 tahun pengalaman kerja"), "Min. 2 tahun")
        self.assertEqual(extract_yoe_rule_based("Memiliki pengalaman 3 tahun dengan Python"), "Min. 3 tahun")
        self.assertEqual(extract_yoe_rule_based("Pengalaman kerja 2 - 4 tahun"), "2-4 tahun")

    def test_schema_experience_range_and_job_insights(self):
        # Test Naukri / JobPost schema experience_range field
        self.assertEqual(extract_yoe_rule_based("", experience_range="2-4 Yrs"), "2-4 tahun")
        self.assertEqual(extract_yoe_rule_based("", experience_range="3+ years"), "Min. 3 tahun")

        # Test extract_job_insights using schema fields
        job_post = {
            "title": "Data Analyst",
            "company": "Tech Corp",
            "description": "SQL and Tableau reporting.",
            "job_level": "entry level",
            "experience_range": "1-3 Yrs",
            "skills": ["SQL", "Tableau", "Python"],
        }
        insights = extract_job_insights(job_post)
        self.assertEqual(insights.yoe, "1-3 tahun")
        self.assertEqual(insights.seniority, "Entry Level")
        self.assertEqual(insights.level_code, "entry_level")
        self.assertIn("Python", insights.skills)
        self.assertIn("Tableau", insights.skills)

    def test_linkedin_job_level_seniority(self):
        # When title has no seniority, LinkedIn job_level takes precedence
        sen_entry, code_entry = extract_seniority_rule_based("Software Engineer", "", job_level="entry level")
        self.assertEqual(code_entry, "entry_level")
        self.assertEqual(sen_entry, "Entry Level")

        sen_assoc, code_assoc = extract_seniority_rule_based("Software Engineer", "", job_level="associate")
        self.assertEqual(code_assoc, "associate")
        self.assertEqual(sen_assoc, "Junior / Associate")

        sen_mid, code_mid = extract_seniority_rule_based("Software Engineer", "", job_level="mid-senior level")
        self.assertEqual(code_mid, "mid_senior")
        self.assertEqual(sen_mid, "Mid-Senior Level")

        sen_dir, code_dir = extract_seniority_rule_based("Software Engineer", "", job_level="director")
        self.assertEqual(code_dir, "lead")
        self.assertEqual(sen_dir, "Director / Lead")

        # When title explicitly has Senior, title overrides inaccurate LinkedIn job_level
        sen_sr, code_sr = extract_seniority_rule_based("Senior Software Engineer", "", job_level="associate")
        self.assertEqual(code_sr, "senior")
        self.assertEqual(sen_sr, "Senior")

    def test_inferred_seniority_from_yoe(self):
        _, code_sr = extract_seniority_rule_based("DevOps Engineer", "", yoe="Min. 5 tahun")
        self.assertEqual(code_sr, "senior")

        _, code_lead = extract_seniority_rule_based("Cloud Engineer", "", yoe="Min. 10 tahun")
        self.assertEqual(code_lead, "lead")

        _, code_jr = extract_seniority_rule_based("Backend Engineer", "", yoe="0-2 tahun")
        self.assertEqual(code_jr, "associate")

    def test_qualitative_experience_and_special_skills(self):
        desc_qual = (
            "**Required Experience:**\n"
            "* Prior experience in configuring network and security infrastructures.\n"
            "* Experience with C\\+\\+, C#, and .NET frameworks."
        )
        self.assertEqual(extract_yoe_rule_based(desc_qual), "Berpengalaman")
        skills = extract_skills_rule_based(desc_qual)
        self.assertIn("C++", skills)
        self.assertIn("C#", skills)
        self.assertIn(".NET", skills)

    def test_clean_job_record_with_list_fields(self):
        from scraper import clean_job_record
        raw_record = {
            "id": "12345",
            "title": "DevOps Engineer",
            "skills": ["Docker", "Kubernetes"],
            "description": "Great job",
        }
        cleaned = clean_job_record(raw_record, default_site="linkedin")
        self.assertEqual(cleaned["skills"], ["Docker", "Kubernetes"])
        self.assertEqual(cleaned["site"], "linkedin")


class TestDiscordNotifierStreamRouting(unittest.TestCase):
    def test_embed_color_by_stream(self):
        # Product job
        product_job = {
            "title": "Associate Product Manager",
            "company": "Sirclo",
            "stream_key": "product_and_analysis",
            "stream_name": "Product & Business Analysis",
        }
        embed_prod = build_job_embed(product_job)
        self.assertEqual(embed_prod["color"], COLOR_STREAM_PRODUCT)

        # Data job
        data_job = {
            "title": "Data Analyst",
            "company": "Komerce",
            "stream_key": "data_and_ai",
            "stream_name": "Data & AI",
        }
        embed_data = build_job_embed(data_job)
        self.assertEqual(embed_data["color"], COLOR_STREAM_DATA)

        # Tech job
        tech_job = {
            "title": "Software Engineer",
            "company": "Startup",
            "stream_key": "tech_engineering",
            "stream_name": "Tech & Engineering",
        }
        embed_tech = build_job_embed(tech_job)
        self.assertEqual(embed_tech["color"], COLOR_STREAM_TECH)

        # Top Tier priority (overrides stream color to Gold)
        top_job = {
            "title": "Software Engineer",
            "company": "Shopee",
            "stream_key": "tech_engineering",
            "stream_name": "Tech & Engineering",
            "company_match": CompanyMatch("Shopee", "Top Tech", "🚀 Top Tech"),
        }
        embed_top = build_job_embed(top_job)
        self.assertEqual(embed_top["color"], COLOR_TOP_TIER)

    def test_webhook_resolution_fallback(self):
        cfg = Config(
            discord_webhook_url="https://discord.com/api/webhooks/default/123",
            discord_webhook_tech="https://discord.com/api/webhooks/tech/456",
        )
        notifier = DiscordNotifier(default_webhook_url=cfg.discord_webhook_url, config=cfg)

        # Tech job resolves to tech webhook
        tech_job = {"stream_key": "tech_engineering"}
        self.assertEqual(notifier.get_webhook_for_job(tech_job), "https://discord.com/api/webhooks/tech/456")

        # Product job (not set) falls back to default webhook
        prod_job = {"stream_key": "product_and_analysis"}
        self.assertEqual(notifier.get_webhook_for_job(prod_job), "https://discord.com/api/webhooks/default/123")

    def test_embed_cta_and_clean_fallbacks(self):
        from discord_notifier import _resolve_thumbnail_url

        # Test CTA button name is non-empty (\u200b)
        job_with_url = {
            "title": "Backend Developer",
            "company": "Tech Corp",
            "job_url": "https://linkedin.com/jobs/view/12345",
            "site": "LinkedIn",
        }
        embed = build_job_embed(job_with_url)
        cta_field = [f for f in embed["fields"] if "Lamar Sekarang" in f.get("value", "")][0]
        self.assertEqual(cta_field["name"], "\u200b")

        # Test clean fallbacks
        yoe_field = [f for f in embed["fields"] if "Pengalaman" in f.get("name", "")][0]
        level_field = [f for f in embed["fields"] if "Level" in f.get("name", "")][0]
        self.assertEqual(yoe_field["value"], "Tidak Disebutkan")
        self.assertEqual(level_field["value"], "Semua Level")

        # Test word-boundary domain matching (super.money should NOT match ey.com)
        logo_supermoney = _resolve_thumbnail_url({"company": "super.money"})
        self.assertNotIn("ey.com", logo_supermoney)

        logo_ey = _resolve_thumbnail_url({"company": "EY Indonesia"})
        self.assertIn("ey.com", logo_ey)


if __name__ == "__main__":
    unittest.main()
