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
    summary: Optional[str] = None
    source: str = "rule-based"  # 'rule-based' or 'ai'


# Curated CS & Tech Skills dictionary mapped to canonical display names
SKILLS_DICTIONARY: Dict[str, str] = {
    # Programming Languages
    r"\bpython\b": "Python",
    r"\btypescript\b": "TypeScript",
    r"\bjavascript\b": "JavaScript",
    r"\bgolang\b|\bgo\s+language\b": "Go",
    r"\bjava\b": "Java",
    r"\bkotlin\b": "Kotlin",
    r"\bswift\b": "Swift",
    r"\brust\b": "Rust",
    r"\bc\+\+\b": "C++",
    r"\bc#\b": "C#",
    r"\bphp\b": "PHP",
    r"\bruby\b": "Ruby",
    r"\bsql\b": "SQL",

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
    r"\btableau\b": "Tableau",
    r"\bpower\s*bi\b": "Power BI",

    # Architecture & Practices
    r"\bmicroservices\b": "Microservices",
    r"\bsystem\s*design\b": "System Design",
    r"\bagile\b|\bscrum\b": "Agile/Scrum",
    r"\bclean\s*architecture\b": "Clean Architecture",
    r"\bunit\s*test(?:ing)?\b|\btdd\b": "Testing / TDD",
}

COMPILED_SKILLS = [
    (re.compile(pattern, re.IGNORECASE), name)
    for pattern, name in SKILLS_DICTIONARY.items()
]


def extract_skills_rule_based(text: str, max_skills: int = 8) -> List[str]:
    """Grep and extract matched technical skills from text using regex patterns."""
    if not text:
        return []

    found = []
    seen = set()
    for regex, skill_name in COMPILED_SKILLS:
        if regex.search(text):
            if skill_name not in seen:
                seen.add(skill_name)
                found.append(skill_name)
                if len(found) >= max_skills:
                    break

    return found


def extract_yoe_rule_based(text: str) -> Optional[str]:
    """Extract required Years of Experience (YoE) using regex patterns."""
    if not text:
        return None

    # Pattern 1: Range (e.g. 2-4 years, 1 - 3 tahun)
    m = re.search(r"\b(\d+)\s*(?:-|to|sampai|hingga)\s*(\d+)\s*(?:years?|yrs?|thn|tahun)\b", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-{m.group(2)} tahun"

    # Pattern 2: Minimum (e.g. min 2 years, minimal 3 tahun, at least 1 year)
    m = re.search(r"\b(?:at least|minimum|min\.?|minimal|pengalaman)\s*(\d+)\+?\s*(?:years?|yrs?|thn|tahun)\b", text, re.IGNORECASE)
    if m:
        return f"Min. {m.group(1)} tahun"

    # Pattern 3: Plus notation (e.g. 3+ years experience, 2+ tahun)
    m = re.search(r"\b(\d+)\+\s*(?:years?|yrs?|thn|tahun)\b", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}+ tahun"

    # Pattern 4: Fresh Graduate indicator
    if re.search(r"\b(?:fresh\s*graduates?|lulusan\s*baru|entry\s*level|tanpa\s*pengalaman)\b", text, re.IGNORECASE):
        return "Fresh Graduate (0-1 tahun)"

    # Pattern 5: Internship indicator
    if re.search(r"\b(?:internship|magang|intern)\b", text, re.IGNORECASE):
        return "Internship / Mahasiswa"

    return None


def extract_seniority_rule_based(title: str, text: str) -> str:
    """Determine seniority level prioritizing job title followed by description."""
    full_str = f"{title} {text}".lower()
    title_lower = (title or "").lower()

    # Title check (most accurate)
    if any(k in title_lower for k in ["intern", "internship", "magang"]):
        return "Internship"
    if any(k in title_lower for k in ["lead", "principal", "staff engineer", "head", "architect", "tech lead"]):
        return "Lead / Principal"
    if any(k in title_lower for k in ["senior", "sr.", "sr "]):
        return "Senior"
    if any(k in title_lower for k in ["junior", "jr.", "jr ", "entry", "associate", "fresh grad"]):
        return "Junior / Associate"
    if any(k in title_lower for k in ["mid", "intermediate"]):
        return "Mid-Level"

    # Fallback to description keywords
    if "senior" in full_str:
        return "Senior"
    if any(k in full_str for k in ["junior", "associate", "fresh graduate"]):
        return "Junior / Associate"
    if any(k in full_str for k in ["intern", "magang"]):
        return "Internship"

    return "Mid-Level / General"


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

            return JobInsights(
                skills=skills[:8] if isinstance(skills, list) else [],
                yoe=data.get("yoe"),
                seniority=data.get("seniority", "Not Specified"),
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
            return ai_insights

    # Local Rule-Based Extraction
    skills = extract_skills_rule_based(combined_text)
    yoe = extract_yoe_rule_based(combined_text)
    seniority = extract_seniority_rule_based(title, combined_text)

    return JobInsights(
        skills=skills,
        yoe=yoe,
        seniority=seniority,
        summary=None,
        source="rule-based",
    )
