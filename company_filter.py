"""Company classification and matching module driven by config.json."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple

logger = logging.getLogger("job_alerts.company_filter")

# Legal-form / filler tokens dropped before comparing a company name against `exact_aliases`,
# so "PT Bank Mandiri (Persero) Tbk." normalizes to "bank mandiri" and "DANA Indonesia" to "dana".
_LEGAL_NOISE_TOKENS = frozenset({
    "pt", "tbk", "persero", "indonesia", "inc", "ltd", "limited", "corp", "corporation", "co", "llc", "plc",
})


@dataclass
class CompanyMatch:
    canonical_name: str
    category: str
    badge: str
    domain: Optional[str] = None


def normalize_company_name(name: str) -> str:
    """Lowercase, drop brackets/commas and legal-form tokens; keeps dots inside tokens (e.g. tiket.com)."""
    tokens = re.sub(r"[(),]", " ", name.lower()).split()
    kept = [t.strip(".") for t in tokens]
    return " ".join(t for t in kept if t and t not in _LEGAL_NOISE_TOKENS)


class CompanyMatcher:
    """Matches employer names against the top company catalog loaded from config.json.

    Each catalog entry supports:
      - `aliases`: distinctive names matched anywhere in the employer name (whole words).
      - `exact_aliases`: ambiguous/common words (e.g. "mandiri", "sea", "dana", "wings") that only match when
        they are the whole employer name after legal-form normalization, so "PT Mandiri Utama Finance" or
        "Wings Air" do not inherit the badge.
    """

    def __init__(
        self,
        top_companies_dict: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        custom_companies: Optional[List[str]] = None,
    ):
        self._entries: List[Tuple[CompanyMatch, Optional[Pattern[str]], Set[str]]] = []
        self._build_entries(top_companies_dict or {}, custom_companies or [])

    def _build_entries(
        self,
        top_companies: Dict[str, List[Dict[str, Any]]],
        custom_companies: List[str],
    ) -> None:
        for category, companies in top_companies.items():
            if not isinstance(companies, list):
                continue

            for co in companies:
                if not isinstance(co, dict):
                    continue

                canonical = str(co.get("name", "")).strip()
                if not canonical:
                    continue

                badge = str(co.get("badge", f"⭐ {category}")).strip()
                domain = str(co.get("domain") or "").strip() or None
                aliases = co.get("aliases", [canonical.lower()])
                exact_aliases = co.get("exact_aliases", [])
                self._add_entry(CompanyMatch(canonical, category, badge, domain), aliases, exact_aliases)

        for custom_name in custom_companies:
            clean = str(custom_name).strip()
            if clean:
                self._add_entry(CompanyMatch(clean, "Custom Top Company", "⭐ Top Employer"), [clean.lower()], [])

    def _add_entry(self, match: CompanyMatch, aliases: List[Any], exact_aliases: List[Any]) -> None:
        sub_patterns = [
            rf"\b{re.escape(str(alias).strip())}\b" for alias in aliases if alias and str(alias).strip()
        ]
        exact = {normalize_company_name(str(a)) for a in exact_aliases if a and str(a).strip()}
        exact.discard("")

        if not sub_patterns and not exact:
            return

        regex = None
        if sub_patterns:
            try:
                regex = re.compile("|".join(sub_patterns), re.IGNORECASE)
            except re.error as err:
                logger.warning("Regex error for company '%s': %s", match.canonical_name, err)
                return

        self._entries.append((match, regex, exact))

    def match(self, company_name: Optional[str]) -> Optional[CompanyMatch]:
        """Return the catalog entry for company_name, or None if it is not a known top tier employer."""
        if not company_name:
            return None

        clean_name = str(company_name).strip()
        if not clean_name:
            return None

        normalized = normalize_company_name(clean_name)
        for match, regex, exact in self._entries:
            if normalized in exact or (regex is not None and regex.search(clean_name)):
                return match

        return None
