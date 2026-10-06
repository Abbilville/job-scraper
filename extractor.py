"""Information extraction module for job skills, YoE, and seniority with AI fallback."""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger("job_alerts.extractor")


@dataclass
class JobInsights:
    skills: List[str] = field(default_factory=list)
    yoe: Optional[str] = None
    seniority: str = "Not Specified"
    level_code: str = "mid_senior"  # 'internship', 'entry_level', 'associate', 'mid_senior', 'senior', 'lead'
    summary: Optional[str] = None
    source: str = "rule-based"  # 'rule-based' or 'ai'


def clean_job_text(text: str) -> str:
    """Normalize markdown escapes, non-breaking spaces, and typography for reliable regex parsing."""
    if not text:
        return ""
    # Unescape markdown-escaped punctuation (e.g. 5\+ -> 5+, 3\-5 -> 3-5, C\+\+ -> C++)
    cleaned = re.sub(r"\\([+\-*_#&\\./()\[\]])", r"\1", text)
    cleaned = cleaned.replace("’", "'").replace("‘", "'").replace("`", "'")
    cleaned = cleaned.replace("\u00a0", " ").replace("\xa0", " ").replace("\u200b", " ")
    return cleaned


# Curated CS, SI, Tech & Product Skills dictionary mapped to canonical display names
SKILLS_DICTIONARY: Dict[str, str] = {
    # Programming Languages
    r"\bpython\b": "Python",
    r"\btypescript\b": "TypeScript",
    r"\bjavascript\b": "JavaScript",
    r"\bgolang\b|\bgo\s*(?:language|programming|lang)?\b": "Go",
    r"\bjava\b": "Java",
    r"\bkotlin\b": "Kotlin",
    r"\bswift\b": "Swift",
    r"\brust\b": "Rust",
    r"\bc\+\+(?!\w)": "C++",
    r"\bc#(?!\w)": "C#",
    r"(?:(?<!\w)\.net\b|\bdotnet\b)": ".NET",
    r"\bphp\b": "PHP",
    r"\bruby\b": "Ruby",
    r"\bsql\b": "SQL",
    r"\br\s+programming\b|\br\s+lang\b": "R",

    # Frontend Technologies
    r"\breact\b|\breact\.js\b|\breactjs\b": "React",
    r"\bnext\.?js\b": "Next.js",
    r"\bvue\b|\bvue\.js\b|\bvuejs\b": "Vue.js",
    r"\bnuxt\.?js\b": "Nuxt.js",
    r"\bangular\b": "Angular",
    r"\bsvelte\b": "Svelte",
    r"\btailwind\b|\btailwindcss\b": "Tailwind CSS",
    r"\bhtml5?\b|\bcss3?\b": "HTML/CSS",
    r"\bredux\b": "Redux",

    # Backend & API Frameworks
    r"\bnode\.?js\b|\bnodejs\b": "Node.js",
    r"\bexpress\.?js\b|\bexpress\b": "Express.js",
    r"\bnest\.?js\b|\bnestjs\b": "NestJS",
    r"\bfastapi\b": "FastAPI",
    r"\bdjango\b": "Django",
    r"\bflask\b": "Flask",
    r"\bspring\s*boot\b": "Spring Boot",
    r"\blaravel\b": "Laravel",
    r"\bgraphql\b": "GraphQL",
    r"\brest\s*api\b|\brestful\b": "REST API",
    r"\bgrpc\b": "gRPC",

    # Mobile Development
    r"\bflutter\b": "Flutter",
    r"\breact\s*native\b": "React Native",
    r"\bandroid\b": "Android",
    r"\bios\b": "iOS",

    # Product Management & Agile / Scrum
    r"\bjira\b": "Jira",
    r"\bconfluence\b": "Confluence",
    r"\bfigma\b": "Figma",
    r"\bwireframing\b|\bwireframe\b": "Wireframing",
    r"\bprd\b|\bproduct\s*requirements?\s*doc(?:ument)?\b": "PRD",
    r"\bproduct\s*roadmap\b": "Product Roadmap",
    r"\buser\s*stories\b": "User Stories",
    r"\ba/b\s*test(?:ing)?\b": "A/B Testing",
    r"\bmixpanel\b": "Mixpanel",
    r"\bamplitude\b": "Amplitude",
    r"\bproduct\s*lifecycle\b": "Product Lifecycle",
    r"\bagile\b|\bscrum\b": "Agile/Scrum",

    # Business Analysis & Systems (SI)
    r"\bbpmn\b": "BPMN",
    r"\buml\b": "UML",
    r"\bflowchart\b|\bdata\s*flow\s*diagram\b|\bdfd\b": "Flowchart/DFD",
    r"\bbrd\b|\bbusiness\s*requirements?\b": "BRD",
    r"\bfsd\b|\bfunctional\s*specifications?\b": "FSD",
    r"\bgap\s*analysis\b": "Gap Analysis",
    r"\bstakeholder\s*management\b": "Stakeholder Management",
    r"\bdata\s*modeling\b": "Data Modeling",

    # Business Intelligence & Analytics
    r"\bpower\s*bi\b": "Power BI",
    r"\btableau\b": "Tableau",
    r"\blooker\b|\blooker\s*studio\b": "Looker",
    r"\bmetabase\b": "Metabase",
    r"\bdax\b": "DAX",
    r"\bexcel\b|\badvanced\s*excel\b": "Excel",
    r"\bdata\s*warehouse\b|\bdwh\b": "Data Warehouse",
    r"\betl\b|\belt\b": "ETL",
    r"\bdbt\b": "dbt",
    r"\bsnowflake\b": "Snowflake",
    r"\bbigquery\b": "BigQuery",

    # Databases & Caching
    r"\bpostgresql\b|\bpostgres\b": "PostgreSQL",
    r"\bmysql\b": "MySQL",
    r"\bmongodb\b|\bmongo\b": "MongoDB",
    r"\bredis\b": "Redis",
    r"\belasticsearch\b": "Elasticsearch",

    # Cloud, DevOps & Infrastructure
    r"\bdocker\b": "Docker",
    r"\bkubernetes\b|\bk8s\b": "Kubernetes",
    r"\baws\b|\bamazon\s*web\s*services\b": "AWS",
    r"\bgcp\b|\bgoogle\s*cloud\b": "GCP",
    r"\bazure\b": "Azure",
    r"\bterraform\b": "Terraform",
    r"\bci[/-]cd\b": "CI/CD",
    r"\blinux\b": "Linux",
    r"\bgit\b": "Git",
    r"\bkafka\b": "Apache Kafka",
    r"\brabbitmq\b": "RabbitMQ",

    # Data Engineering, AI & Machine Learning
    r"\bpytorch\b": "PyTorch",
    r"\btensorflow\b": "TensorFlow",
    r"\bscikit[/-]learn\b": "Scikit-Learn",
    r"\bpandas\b": "Pandas",
    r"\bnumpy\b": "NumPy",
    r"\bspark\b|\bpyspark\b": "Apache Spark",
    r"\bairflow\b": "Apache Airflow",
    r"\bllm\b|\blarge\s+language\s+models?\b": "LLM",
    r"\blangchain\b": "LangChain",
    r"\brag\b|\bretrieval[- ]augmented\b": "RAG",
    r"\bnlp\b|\bnatural\s+language\b": "NLP",
    r"\bcomputer\s*vision\b|\bopencv\b": "Computer Vision",

    # Architecture & Practices
    r"\bmicroservices\b": "Microservices",
    r"\bsystem\s*design\b": "System Design",
    r"\bclean\s*architecture\b": "Clean Architecture",
    r"\bunit\s*test(?:ing)?\b|\btdd\b": "Testing / TDD",
}

COMPILED_SKILLS = [
    (re.compile(pattern, re.IGNORECASE), name)
    for pattern, name in SKILLS_DICTIONARY.items()
]


def extract_skills_rule_based(text: str, max_skills: int = 12) -> List[str]:
    """Grep and extract matched technical skills from text using regex patterns."""
    if not text:
        return []

    cleaned = clean_job_text(text)
    found = []
    seen = set()
    for regex, skill_name in COMPILED_SKILLS:
        if regex.search(cleaned):
            if skill_name not in seen:
                seen.add(skill_name)
                found.append(skill_name)
                if len(found) >= max_skills:
                    break

    return found


def extract_yoe_rule_based(text: str, experience_range: Optional[str] = None) -> Optional[str]:
    """Extract required Years of Experience (YoE) using regex patterns and JobPost schema."""
    # 1. Parse from structured experience_range schema if present (e.g. Naukri or job boards)
    if experience_range and str(experience_range).strip():
        exp_str = clean_job_text(str(experience_range)).strip()
        m_range = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)", exp_str, re.IGNORECASE)
        if m_range:
            return f"{m_range.group(1)}-{m_range.group(2)} tahun"
        m_min = re.search(r"(\d+)\+?", exp_str)
        if m_min:
            return f"Min. {m_min.group(1)} tahun"

    if not text:
        return None

    cleaned = clean_job_text(text)

    # Pattern 1: Range (e.g. 0-2 years, 3 - 5 yrs, 2 to 4 years, 1-3 tahun, 2 s/d 4 tahun)
    m = re.search(
        r"\b([0-9]|1[0-9]|20)\s*(?:-|to|sampai|hingga|s/?d|s\.d\.)\s*([0-9]|1[0-9]|20)\+?\s*(?:years?|yrs?|thn|tahun)\b",
        cleaned,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)}-{m.group(2)} tahun"

    # Pattern 1b: Range with 'pengalaman' prefix (e.g. pengalaman 2 - 4 tahun)
    m = re.search(
        r"\b(?:pengalaman|experience)\s*(?:kerja)?\s*([0-9]|1[0-9]|20)\s*(?:-|to|sampai|hingga|s/?d|s\.d\.)\s*([0-9]|1[0-9]|20)\+?\s*(?:years?|yrs?|thn|tahun)\b",
        cleaned,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)}-{m.group(2)} tahun"

    # Pattern 2: Minimum / At least notation (e.g. at least 3 years, minimum 2 years, min. 5 tahun, minimal 1 tahun)
    m = re.search(
        r"\b(?:at least|minimum|min\.?|minimal|sekurang-kurangnya|lebih dari|more than|over)\s*(?:of\s*)?([1-9]|1[0-9]|20)\+?\s*(?:years?|yrs?|thn|tahun)\b",
        cleaned,
        re.IGNORECASE,
    )
    if m:
        return f"Min. {m.group(1)} tahun"

    # Pattern 3: Plus notation (e.g. 5+ years, 3+ yrs, 2+ tahun, 4 + years, 3+ thn)
    m = re.search(
        r"\b([1-9]|1[0-9]|20)\s*\+\s*(?:years?|yrs?|thn|tahun)\b",
        cleaned,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)}+ tahun"

    # Pattern 4: General "X years of experience" / "X years in [field]" / "X tahun pengalaman"
    m = re.search(
        r"\b([1-9]|1[0-9]|20)\s*(?:years?|yrs?|thn|tahun)(?:'s|'|\s+of|\s+in)?\s*(?:working\s+|hands-on\s+|professional\s+|relevant\s+|proven\s+|related\s+)?(?:experience|experiences|pengalaman|software|engineering|development|industry)\b",
        cleaned,
        re.IGNORECASE,
    )
    if m:
        return f"Min. {m.group(1)} tahun"

    # Pattern 4b: Indonesian "pengalaman [kerja] X tahun"
    m = re.search(
        r"\b(?:memiliki\s+|punya\s+)?(?:pengalaman|pengalaman kerja|berpengalaman)\s*(?:selama\s+|minimal\s+|min\.?\s*)?([1-9]|1[0-9]|20)\s*(?:tahun|thn)\b",
        cleaned,
        re.IGNORECASE,
    )
    if m:
        return f"Min. {m.group(1)} tahun"

    # Pattern 5: Fresh Graduate indicator
    if re.search(
        r"\b(?:fresh\s*graduates?|freshgrad|lulusan\s*baru|entry\s*level|entry-level|tanpa\s*pengalaman|no\s*experience\s*required)\b",
        cleaned,
        re.IGNORECASE,
    ):
        return "Fresh Graduate (0-1 tahun)"

    # Pattern 6: Internship indicator
    if re.search(r"\b(?:internship|magang|intern|praktik\s*kerja\s*lapangan|pkl)\b", cleaned, re.IGNORECASE):
        return "Internship / Mahasiswa"

    # Pattern 7: Qualitative experience indicator in requirements (no specific years stated)
    if re.search(
        r"(?:required\s+experience|kualifikasi\s+pengalaman|persyaratan\s+pengalaman|syarat\s+pengalaman)\s*:?[\s\S]{0,120}\b(?:prior\s+experience|previous\s+experience|proven\s+experience|hands-on\s+experience|berpengalaman|pengalaman\s+kerja)\b",
        cleaned,
        re.IGNORECASE,
    ) or re.search(
        r"\b(?:prior\s+experience|previous\s+experience|proven\s+experience\s+as|berpengalaman\s+di\s+bidang|memiliki\s+pengalaman\s+kerja\s+di\s+bidang)\b",
        cleaned,
        re.IGNORECASE,
    ):
        return "Berpengalaman"

    return None


def extract_seniority_rule_based(
    title: str,
    text: str = "",
    job_level: Optional[str] = None,
    yoe: Optional[str] = None,
) -> tuple[str, str]:
    """Determine seniority level and normalized level_code prioritizing job title, followed by LinkedIn job_level,
    description keywords, and inferred YoE.
    Returns: (display_name, level_code)
    """
    title_lower = (title or "").lower()
    full_str = clean_job_text(f"{title} {text}").lower()
    norm_job_level = (job_level or "").strip().lower()

    # 1. Title check (most explicit & authoritative)
    if any(k in title_lower for k in ["intern", "internship", "magang"]):
        return "Internship", "internship"
    if any(k in title_lower for k in ["lead", "principal", "staff engineer", "head", "architect", "tech lead", "director", "vp "]):
        return "Lead / Principal", "lead"
    if any(k in title_lower for k in ["senior", "sr.", "sr ", "expert", "specialist"]):
        return "Senior", "senior"
    if any(k in title_lower for k in ["junior", "jr.", "jr ", "entry", "associate", "fresh grad"]):
        return "Junior / Associate", "associate"
    if any(k in title_lower for k in ["mid", "intermediate"]):
        return "Mid-Level", "mid_senior"

    # 2. LinkedIn job_level metadata (if provided and valid)
    if norm_job_level and norm_job_level != "not applicable":
        if "intern" in norm_job_level:
            return "Internship", "internship"
        if "entry" in norm_job_level:
            return "Entry Level", "entry_level"
        if "associate" in norm_job_level:
            return "Junior / Associate", "associate"
        if "mid-senior" in norm_job_level or "mid_senior" in norm_job_level:
            return "Mid-Senior Level", "mid_senior"
        if "director" in norm_job_level or "executive" in norm_job_level:
            return "Director / Lead", "lead"

    # 3. Description keywords (prioritize entry/junior to avoid false exclusion)
    if any(k in full_str for k in ["internship", "magang"]):
        return "Internship", "internship"
    if any(k in full_str for k in ["fresh graduate", "fresh grad", "lulusan baru", "entry level", "entry-level", "tanpa pengalaman"]):
        return "Fresh Graduate / Entry", "entry_level"
    if any(k in full_str for k in ["junior developer", "junior engineer", "junior analyst", "junior position", "junior role"]):
        return "Junior / Associate", "associate"
    if re.search(r"\b(?:senior\s+(?:level|position|role|developer|engineer|analyst)|minimum\s+[5-9]\s*tahun|\b[5-9]\+\s*(?:years?|tahun))\b", full_str):
        return "Senior", "senior"

    # 4. Inference from YoE if available
    if yoe:
        yoe_lower = yoe.lower()
        if "fresh graduate" in yoe_lower or "0-1" in yoe_lower or "intern" in yoe_lower:
            return "Fresh Graduate / Entry", "entry_level"
        if any(f"{y}+" in yoe_lower or f"min. {y}" in yoe_lower for y in range(8, 21)):
            return "Lead / Principal", "lead"
        if any(f"{y}+" in yoe_lower or f"min. {y}" in yoe_lower for y in range(5, 21)):
            return "Senior", "senior"
        if any(k in yoe_lower for k in ["0-2", "1-2", "1-3"]):
            return "Junior / Associate", "associate"

    return "Mid-Level / General", "mid_senior"

def extract_with_ai(
    title: str,
    company: str,
    description: str,
    api_url: str,
    api_key: Optional[str] = None,
    timeout: float = 8.0,
) -> Optional[JobInsights]:
    """Call external AI extraction endpoint (VPS microservice/LLM API)."""
    if not api_url or not api_url.strip():
        return None

    headers = {"Content-Type": "application/json"}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    payload = {
        "title": title,
        "company": company,
        "description": description[:4000] if description else "",
    }

    try:
        response = requests.post(api_url.strip(), json=payload, headers=headers, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            skills = data.get("skills", [])
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(",") if s.strip()]

            seniority_display = data.get("seniority", "Not Specified")
            # Map seniority to level_code
            sen_lower = str(seniority_display).lower()
            if "intern" in sen_lower:
                lvl_code = "internship"
            elif "entry" in sen_lower or "fresh" in sen_lower:
                lvl_code = "entry_level"
            elif "junior" in sen_lower or "associate" in sen_lower:
                lvl_code = "associate"
            elif "senior" in sen_lower:
                lvl_code = "senior"
            elif "lead" in sen_lower or "principal" in sen_lower:
                lvl_code = "lead"
            else:
                lvl_code = "mid_senior"

            return JobInsights(
                skills=skills[:8] if isinstance(skills, list) else [],
                yoe=data.get("yoe"),
                seniority=seniority_display,
                level_code=lvl_code,
                summary=data.get("summary"),
                source="ai",
            )
        else:
            logger.warning("AI endpoint mengembalikan HTTP %d: %s", response.status_code, response.text[:200])
    except Exception as exc:
        logger.info("AI service tidak merespon (%s). Menggunakan rule-based extractor lokal.", exc)

    return None


def extract_job_insights(
    job: Dict[str, Any],
    ai_api_url: Optional[str] = None,
    ai_api_key: Optional[str] = None,
) -> JobInsights:
    """Extract job insights using AI service if available, otherwise rule-based extractor."""
    title = str(job.get("title") or "")
    company = str(job.get("company") or "")
    description = str(job.get("description") or "")
    job_level = job.get("job_level")
    experience_range = job.get("experience_range")
    job_type = job.get("job_type")
    raw_skills = job.get("skills")
    combined_text = f"{title}\n{description}"

    # Try AI endpoint if configured
    if ai_api_url:
        ai_insights = extract_with_ai(
            title=title,
            company=company,
            description=description,
            api_url=ai_api_url,
            api_key=ai_api_key,
        )
        if ai_insights:
            # If AI didn't catch skills, augment with rule-based
            if not ai_insights.skills:
                ai_insights.skills = extract_skills_rule_based(combined_text)
            if not ai_insights.yoe:
                ai_insights.yoe = extract_yoe_rule_based(combined_text, experience_range=experience_range)
            if not ai_insights.seniority or ai_insights.seniority == "Not Specified":
                ai_insights.seniority, ai_insights.level_code = extract_seniority_rule_based(
                    title=title,
                    text=combined_text,
                    job_level=job_level,
                    yoe=ai_insights.yoe,
                )
            return ai_insights

    # Local Rule-Based Extraction
    skills = extract_skills_rule_based(combined_text)
    # Merge pre-parsed skills from schema (e.g. Naukri or direct data)
    if raw_skills:
        if isinstance(raw_skills, str):
            extra_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        elif isinstance(raw_skills, list):
            extra_skills = [str(s).strip() for s in raw_skills if str(s).strip()]
        else:
            extra_skills = []
        for s in extra_skills:
            if s not in skills and len(skills) < 12:
                skills.append(s)

    yoe = extract_yoe_rule_based(combined_text, experience_range=experience_range)
    # If still None, check job_type or job_level for internship/entry indicators
    if not yoe:
        norm_lvl = str(job_level or "").lower().strip()
        norm_type = str(job_type or "").lower().strip()
        if "intern" in norm_lvl or "intern" in norm_type:
            yoe = "Internship / Mahasiswa"
        elif "entry" in norm_lvl:
            yoe = "Entry Level (0-1 tahun)"

    seniority, level_code = extract_seniority_rule_based(
        title=title,
        text=combined_text,
        job_level=job_level,
        yoe=yoe,
    )

    return JobInsights(
        skills=skills,
        yoe=yoe,
        seniority=seniority,
        level_code=level_code,
        summary=None,
        source="rule-based",
    )
