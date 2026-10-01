"""Company classification and matching module driven by config.json."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("job_alerts.company_filter")


@dataclass
class CompanyMatch:
    canonical_name: str
    category: str
    badge: str


class CompanyMatcher:
    """Matches employer names against top company catalog loaded from config.json."""

    def __init__(
        self,
        top_companies_dict: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        custom_companies: Optional[List[str]] = None,
    ):
        self._compiled_patterns: List[tuple] = []
        self._build_patterns(top_companies_dict or {}, custom_companies or [])

    def _build_patterns(
        self,
        top_companies: Dict[str, List[Dict[str, Any]]],
        custom_companies: List[str],
    ) -> None:
        self._compiled_patterns.clear()

        # 1. Process categorized companies from config.json
        for category, companies in top_companies.items():
            if not isinstance(companies, list):
                continue

            for co in companies:
                if not isinstance(co, dict):
                    continue

                canonical = co.get("name", "").strip()
                badge = co.get("badge", f"⭐ {category}").strip()
                aliases = co.get("aliases", [canonical.lower()])

                if not canonical:
                    continue

                self._add_pattern(canonical, category, badge, aliases)

        # 2. Process custom companies
        for custom_name in custom_companies:
            clean = str(custom_name).strip()
            if clean:
                self._add_pattern(clean, "Custom Top Company", "⭐ Top Employer", [clean.lower()])

    def _add_pattern(self, canonical: str, category: str, badge: str, aliases: List[str]) -> None:
        sub_patterns = []
        for alias in aliases:
            if not alias or not str(alias).strip():
                continue
            escaped = re.escape(str(alias).strip())
            sub_patterns.append(rf"(?:\b{escaped}\b)")

        if not sub_patterns:
            return

        combined = "|".join(sub_patterns)
        try:
            regex = re.compile(combined, re.IGNORECASE)
            self._compiled_patterns.append((canonical, category, badge, regex))
        except re.error as err:
            logger.warning("Regex error for company '%s': %s", canonical, err)

    def match(self, company_name: Optional[str]) -> Optional[CompanyMatch]:
        """Check if company_name matches any known top tier employer."""
        if not company_name:
            return None

        clean_name = str(company_name).strip()
        if not clean_name:
            return None

        for canonical, category, badge, regex in self._compiled_patterns:
            if regex.search(clean_name):
                return CompanyMatch(canonical_name=canonical, category=category, badge=badge)

        return None
