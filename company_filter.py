"""Company classification and matching module for top employers (Big 4, Top Tech, Banking, FMCG)."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
logger = logging.getLogger("job_alerts.company_filter")


@dataclass
class CompanyMatch:
    canonical_name: str
    category: str
    badge: str


# Curated catalog of top employers targetting top university students (UI, ITB, UGM, etc.)
DEFAULT_TOP_COMPANIES: Dict[str, Dict[str, Any]] = {
    # --------------------------------------------------------------------------
    # 1. Big 4 Accounting, Strategy & Top Management Consulting
    # --------------------------------------------------------------------------
    "PwC": {
        "category": "Big 4 Consulting",
        "badge": "🏆 Big 4 Consulting",
        "aliases": ["pwc", "pricewaterhousecoopers", "price waterhouse cooper"],
    },
    "Deloitte": {
        "category": "Big 4 Consulting",
        "badge": "🏆 Big 4 Consulting",
        "aliases": ["deloitte", "deloitte consulting", "deloitte indonesia"],
    },
    "EY (Ernst & Young)": {
        "category": "Big 4 Consulting",
        "badge": "🏆 Big 4 Consulting",
        "aliases": ["ey", "ernst & young", "ernst and young", "ernst young"],
    },
    "KPMG": {
        "category": "Big 4 Consulting",
        "badge": "🏆 Big 4 Consulting",
        "aliases": ["kpmg", "kpmg indonesia", "siddharta widjaja"],
    },
    "McKinsey & Company": {
        "category": "Top Strategy Consulting",
        "badge": "💎 Top Strategy Consulting",
        "aliases": ["mckinsey", "mckinsey & company", "mckinsey company"],
    },
    "Boston Consulting Group (BCG)": {
        "category": "Top Strategy Consulting",
        "badge": "💎 Top Strategy Consulting",
        "aliases": ["bcg", "boston consulting group"],
    },
    "Bain & Company": {
        "category": "Top Strategy Consulting",
        "badge": "💎 Top Strategy Consulting",
        "aliases": ["bain", "bain & company", "bain and company"],
    },
    "Accenture": {
        "category": "Top Consulting & Tech Services",
        "badge": "🏆 Top Consulting",
        "aliases": ["accenture"],
    },

    # --------------------------------------------------------------------------
    # 2. Top Tech Giants, Unicorns & Decacorns
    # --------------------------------------------------------------------------
    "GoTo (Gojek & Tokopedia)": {
        "category": "Top Tech Giant",
        "badge": "🚀 Top Tech Giant",
        "aliases": ["goto", "gojek", "tokopedia", "goto financial", "midtrans", "moka"],
    },
    "Traveloka": {
        "category": "Top Tech Unicorn",
        "badge": "🚀 Top Tech Unicorn",
        "aliases": ["traveloka"],
    },
    "Shopee / Sea Group": {
        "category": "Top Tech Giant",
        "badge": "🚀 Top Tech Giant",
        "aliases": ["shopee", "sea group", "garena", "seabank", "shopeepay"],
    },
    "Grab": {
        "category": "Top Tech Giant",
        "badge": "🚀 Top Tech Giant",
        "aliases": ["grab", "grab indonesia", "ovo"],
    },
    "Blibli / GDP Venture": {
        "category": "Top Tech Unicorn",
        "badge": "🚀 Top Tech Unicorn",
        "aliases": ["blibli", "pt global digital niaga", "gdp venture", "tiket.com"],
    },
    "Bukalapak": {
        "category": "Top Tech Unicorn",
        "badge": "🚀 Top Tech Unicorn",
        "aliases": ["bukalapak"],
    },
    "DANA Indonesia": {
        "category": "Top FinTech Unicorn",
        "badge": "🚀 Top FinTech Unicorn",
        "aliases": ["dana", "dana indonesia", "pt espay debit indonesia koe"],
    },
    "Xendit": {
        "category": "Top FinTech Unicorn",
        "badge": "🚀 Top FinTech Unicorn",
        "aliases": ["xendit"],
    },
    "Kredivo": {
        "category": "Top FinTech Unicorn",
        "badge": "🚀 Top FinTech Unicorn",
        "aliases": ["kredivo", "finaccel"],
    },
    "eFishery": {
        "category": "Top Tech Unicorn",
        "badge": "🚀 Top Tech Unicorn",
        "aliases": ["efishery"],
    },
    "Ajaib": {
        "category": "Top FinTech Unicorn",
        "badge": "🚀 Top FinTech Unicorn",
        "aliases": ["ajaib", "ajaib sekuritas"],
    },
    "Bibit / Stockbit": {
        "category": "Top FinTech",
        "badge": "🚀 Top FinTech",
        "aliases": ["bibit", "stockbit"],
    },
    "Ruangguru": {
        "category": "Top EdTech",
        "badge": "🚀 Top EdTech",
        "aliases": ["ruangguru"],
    },
    "Google": {
        "category": "Global Tech Giant",
        "badge": "🌐 Global Tech Giant",
        "aliases": ["google", "google indonesia", "alphabet"],
    },
    "Microsoft": {
        "category": "Global Tech Giant",
        "badge": "🌐 Global Tech Giant",
        "aliases": ["microsoft", "microsoft indonesia"],
    },
    "Amazon / AWS": {
        "category": "Global Tech Giant",
        "badge": "🌐 Global Tech Giant",
        "aliases": ["amazon", "aws", "amazon web services"],
    },
    "ByteDance / TikTok": {
        "category": "Global Tech Giant",
        "badge": "🌐 Global Tech Giant",
        "aliases": ["bytedance", "tiktok"],
    },
    "Meta": {
        "category": "Global Tech Giant",
        "badge": "🌐 Global Tech Giant",
        "aliases": ["meta", "facebook"],
    },

    # --------------------------------------------------------------------------
    # 3. Top Tier Banking & Financial Institutions
    # --------------------------------------------------------------------------
    "Bank Central Asia (BCA)": {
        "category": "Top Tier Banking",
        "badge": "🏛️ Top Tier Banking",
        "aliases": ["bca", "bank central asia", "pt bank central asia"],
    },
    "Bank Mandiri": {
        "category": "Top Tier Banking",
        "badge": "🏛️ Top Tier Banking",
        "aliases": ["bank mandiri", "mandiri", "pt bank mandiri"],
    },
    "Bank Rakyat Indonesia (BRI)": {
        "category": "Top Tier Banking",
        "badge": "🏛️ Top Tier Banking",
        "aliases": ["bri", "bank rakyat indonesia", "pt bank rakyat indonesia"],
    },
    "Bank Negara Indonesia (BNI)": {
        "category": "Top Tier Banking",
        "badge": "🏛️ Top Tier Banking",
        "aliases": ["bni", "bank negara indonesia", "pt bank negara indonesia"],
    },
    "Bank Indonesia (BI)": {
        "category": "Central Bank",
        "badge": "🏛️ Central Bank",
        "aliases": ["bank indonesia"],
    },
    "DBS Bank": {
        "category": "Top Tier Banking",
        "badge": "🏛️ Top Tier Banking",
        "aliases": ["dbs", "bank dbs", "dbs indonesia"],
    },
    "CIMB Niaga": {
        "category": "Top Tier Banking",
        "badge": "🏛️ Top Tier Banking",
        "aliases": ["cimb", "cimb niaga", "bank cimb niaga"],
    },
    "OCBC": {
        "category": "Top Tier Banking",
        "badge": "🏛️ Top Tier Banking",
        "aliases": ["ocbc", "ocbc nisp", "bank ocbc"],
    },
    "Bank BTPN / Jenius": {
        "category": "Top Tier Banking",
        "badge": "🏛️ Top Tier Banking",
        "aliases": ["btpn", "jenius", "bank btpn"],
    },

    # --------------------------------------------------------------------------
    # 4. Top Conglomerates, Telco & FMCG
    # --------------------------------------------------------------------------
    "Telkom / Telkomsel": {
        "category": "Top Telco & Digital",
        "badge": "📡 Top Telco & Digital",
        "aliases": ["telkom", "telkomsel", "pt telkom indonesia", "pt telekomunikasi indonesia"],
    },
    "Astra International": {
        "category": "Top Conglomerate",
        "badge": "🏢 Top Conglomerate",
        "aliases": ["astra", "astra international", "pt astra international"],
    },
    "Unilever": {
        "category": "Top FMCG",
        "badge": "🌟 Top FMCG",
        "aliases": ["unilever", "unilever indonesia", "pt unilever"],
    },
    "Nestlé": {
        "category": "Top FMCG",
        "badge": "🌟 Top FMCG",
        "aliases": ["nestle", "nestlé", "pt nestle indonesia"],
    },
    "Procter & Gamble (P&G)": {
        "category": "Top FMCG",
        "badge": "🌟 Top FMCG",
        "aliases": ["p&g", "procter & gamble", "procter and gamble"],
    },
    "Danone": {
        "category": "Top FMCG",
        "badge": "🌟 Top FMCG",
        "aliases": ["danone", "danone aqua", "sarihusada"],
    },
    "Paragon Technology (Wardah)": {
        "category": "Top FMCG & Beauty",
        "badge": "🌟 Top FMCG",
        "aliases": ["paragon", "paragon technology and innovation", "wardah", "make over", "kahf"],
    },
    "Indofood": {
        "category": "Top FMCG",
        "badge": "🌟 Top FMCG",
        "aliases": ["indofood", "indofood cbp", "pt indofood"],
    },
    "Djarum": {
        "category": "Top Conglomerate",
        "badge": "🏢 Top Conglomerate",
        "aliases": ["djarum", "pt djarum"],
    },
    "Pertamina": {
        "category": "National Energy Giant",
        "badge": "⚡ National Energy Giant",
        "aliases": ["pertamina", "pt pertamina"],
    },
}


class CompanyMatcher:
    """Matches employer names against top company catalog with regex token boundaries."""

    def __init__(self, custom_companies: Optional[List[str]] = None):
        self.catalog = dict(DEFAULT_TOP_COMPANIES)
        self._compiled_patterns: List[tuple] = []
        self._init_custom_companies(custom_companies)
        self._compile_regexes()

    def _init_custom_companies(self, custom_companies: Optional[List[str]]) -> None:
        if not custom_companies:
            return

        for item in custom_companies:
            item_clean = item.strip()
            if not item_clean:
                continue

            self.catalog[item_clean] = {
                "category": "Custom Top Company",
                "badge": "⭐ Top Employer",
                "aliases": [item_clean.lower()],
            }

    def _compile_regexes(self) -> None:
        self._compiled_patterns.clear()
        for canonical, info in self.catalog.items():
            category = info.get("category", "Top Tier Company")
            badge = info.get("badge", "⭐ Top Company")
            aliases = info.get("aliases", [canonical.lower()])

            # Build regex matching word boundaries
            # Handle special characters (e.g., &, +, .)
            sub_patterns = []
            for alias in aliases:
                escaped = re.escape(alias)
                # If alias is alphanumeric word, use \b boundary
                sub_patterns.append(rf"(?:\b{escaped}\b)")

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
