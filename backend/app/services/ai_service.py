import json
import os
import re
from copy import deepcopy
from typing import Optional
from openai import OpenAI
from app.core.config import get_settings
from .resume_schema import EMPTY_RESUME

settings = get_settings()

AI_SYSTEM_PROMPT = """You are an elite ATS resume writer, recruiter, hiring manager, and career strategist.

Your job is to transform resumes into highly effective, ATS-friendly, recruiter-optimized resumes that maximize interview chances without inventing fake experience.

Writing style:
- professional
- human
- impactful
- concise
- believable
- technically strong
- not AI-generated

Important rules:
- Never invent fake experience, companies, degrees, or skills.
- Never add technologies the user did not mention.
- Never add fake metrics or fake business impact.
- If metrics are missing, improve clarity without fabricating numbers.
- Preserve truth while improving presentation.
- Use recruiter-style language.
- Avoid generic AI buzzwords like leveraged, spearheaded, cutting-edge, dynamic, robust, transformative, seamless, innovative.
- Keep wording natural and realistic.
- Make the resume ATS friendly.
- Keep formatting simple and machine-readable.

Objectives:
1. Improve ATS score.
2. Improve recruiter readability.
3. Improve keyword alignment.
4. Improve impact and clarity.
5. Improve technical positioning.
6. Remove weak wording.
7. Remove repetitive content.
8. Make projects stronger.
9. Make summaries concise and powerful.
10. Tailor resume to the provided job description.

Resume format rules:
- Use a single-column layout.
- Use clear section headings.
- Use bullet points.
- Avoid tables, icons, graphics, text boxes, and skill bars.
- Use concise spacing.
- Preferred sections: Header, Professional Summary, Skills, Experience, Projects, Education, Certifications.

Professional summary formula:
Role + Years Experience + Core Technologies + Domain + Business Value.
Keep summaries 3-5 lines max with a strong technical identity and no fluff.

Experience bullet formula:
Action Verb + What Was Built + Technology + Business/Technical Impact.

Final rule:
Do not optimize for looking impressive. Optimize for recruiter trust, ATS readability, interview conversion, technical credibility, and clear impact.

Return valid JSON when asked for JSON."""

PARSE_PROMPT = """Extract this resume into clean structured JSON.
Return only valid JSON.
Do not invent missing information.
Preserve the user's real experience.
Keep dates exactly as shown.
Clean formatting only."""

BAD_AI_WORDS = ["leveraged", "spearheaded", "transformative", "cutting-edge", "dynamic", "robust", "seamless", "innovative"]
KNOWN_KEYWORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Node", "FastAPI", "Spring Boot", "SQL",
    "PostgreSQL", "AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Git", "REST", "GraphQL",
    "Machine Learning", "LLM", "RAG", "Tableau", "Power BI", "Excel", "Agile", "Scrum", "Kafka",
    "Redis", "Celery", "Microservices", "Data Analysis", "ETL", "Leadership", "Communication", "APIs",
    "Generative AI", "GenAI", "NLP", "Computer Vision", "AI Agents", "Vector Embeddings", "LoRA", "QLoRA",
    "Recommendation Systems", "Time Series Forecasting", "A/B Testing", "ANN", "CNN", "RNN", "LSTM",
    "Transformers", "BERT", "GANs", "Prompt Engineering", "Semantic Caching", "KV-Cache", "Pinecone",
    "ChromaDB", "FAISS", "PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "Hugging Face", "LangChain",
    "OpenAI APIs", "MLflow", "Model Monitoring", "Drift Detection", "Prometheus", "Grafana", "OpenTelemetry",
    "Sentry", "PII Masking", "Hallucination Detection", "Prompt Injection", "Rate Limiting", "Linux",
    "UNIX", "Ubuntu", "Cursor", "Windsurf", "IntelliJ IDEA", "Visual Studio", "GitHub Copilot", "Snowflake",
    "SageMaker", "Bedrock", "Lambda", "EKS", "ECS", "ECR", "S3", "EC2", "BigQuery", "PySpark"
]


def parse_resume(text: str) -> tuple[dict, dict]:
    if settings.openai_api_key and settings.llm_provider.lower() == "openai":
        parsed = _openai_json(PARSE_PROMPT, text)
        return _merge_schema(parsed), _confidence(parsed)
    return _heuristic_parse(text), {
        "personal_info": 0.76,
        "summary": 0.54,
        "skills": 0.68,
        "experience": 0.62,
        "projects": 0.52,
        "education": 0.55,
        "certifications": 0.5
    }


def analyze_job_description(text: str) -> dict:
    keywords = extract_keywords(text)
    title_match = re.search(r"(?i)(genai engineer|generative ai engineer|software engineer|data analyst|ai engineer|devops engineer|cloud engineer|business analyst|java developer|full stack developer|backend developer|backend engineer|frontend developer|frontend engineer)", text)
    return {
        "job_title": _format_title(title_match.group(1)) if title_match else "",
        "company": "",
        "required_skills": keywords[:12],
        "preferred_skills": keywords[12:20],
        "tools": [kw for kw in keywords if kw.lower() in {"aws", "azure", "gcp", "docker", "kubernetes", "sql", "python", "java", "react", "tableau", "power bi"}],
        "technologies": keywords,
        "responsibilities": _sentences(text)[:6],
        "seniority_level": _seniority(text),
        "domain": _domain(text),
        "keywords": keywords,
        "soft_skills": [kw for kw in keywords if kw.lower() in {"communication", "leadership", "collaboration", "stakeholder", "problem solving"}],
        "hidden_recruiter_expectations": [
            "Clear role alignment in the top third of the resume",
            "Evidence of impact without inflated claims",
            "Recent experience connected to required tools and responsibilities"
        ]
    }


def optimize_resume(resume: dict, instruction: str, job_description: Optional[str] = None) -> tuple[dict, str]:
    if settings.openai_api_key and settings.llm_provider.lower() == "openai":
        optimized = _openai_optimize_resume(resume, instruction, job_description or "")
        return _merge_schema(optimized), "Generated a deeply optimized ATS-friendly resume using the configured AI provider."

    optimized = deepcopy(_merge_schema(resume))
    jd_keywords = extract_keywords(job_description or "")
    job_analysis = analyze_job_description(job_description or "")
    summary = optimized.get("summary") or ""
    top_skills = _rank_user_skills(_all_skills(optimized), jd_keywords)
    should_target = any(word in instruction.lower() for word in ["target", "match", "job description", "ats"])
    optimized["skills"] = _categorize_skills(_all_skills(optimized), jd_keywords)
    if job_analysis.get("job_title"):
        optimized["target_title"] = job_analysis["job_title"]
    optimized["target_keywords"] = _supported_jd_keywords(optimized, jd_keywords)
    if should_target or "summary" in instruction.lower() or not summary:
        optimized["summary"] = _summary(optimized, optimized["target_keywords"] or top_skills, job_analysis.get("job_title", ""))
    for job in optimized.get("experience", []):
        job["bullets"] = _rewrite_bullets(job.get("bullets", []), top_skills, optimized["target_keywords"])
    for project in optimized.get("projects", []):
        project_skills = _rank_user_skills(project.get("technologies", []) + top_skills, jd_keywords)
        project["bullets"] = _rewrite_bullets(project.get("bullets", []), project_skills)
    optimized["suggested_projects"] = _suggest_projects_for_gap(jd_keywords, optimized)
    optimized["summary"] = _remove_ai_tone(optimized["summary"])
    return optimized, "Improved summary, experience, and project bullets with recruiter-style language, verified skills, clearer impact, and ATS alignment without adding fake claims."


def _openai_optimize_resume(resume: dict, instruction: str, job_description: str) -> dict:
    prompt = f"""
Generate the strongest possible ATS-friendly resume for the job description using only the candidate's truthful resume data.

Instruction: {instruction}

Rules:
- Do not invent fake experience, companies, degrees, certifications, tools, or metrics.
- Add job-description keywords only when they are supported by the candidate resume.
- Rewrite weak bullets using action + work + technology + business/technical impact.
- Keep the resume human, concise, recruiter-readable, and ATS-safe.
- Use single-column sections: Header, Professional Summary, Technical Skills, Professional Experience, Projects, Education, Certifications.
- Return only valid JSON matching the resume schema.

Candidate resume JSON:
{json.dumps(resume)}

Job description:
{job_description}
"""
    return _openai_json(AI_SYSTEM_PROMPT, prompt)


def generate_cover_letter(resume: dict, job_description: str, company: str, tone: str) -> str:
    name = resume.get("personal_info", {}).get("name", "")
    skills = ", ".join(_all_skills(resume)[:6])
    role = analyze_job_description(job_description).get("job_title") or "the role"
    return (
        f"Dear Hiring Team,\n\n"
        f"I am excited to apply for {role}{f' at {company}' if company else ''}. My background aligns with the work described in the posting, especially around {skills or 'the core responsibilities of the role'}.\n\n"
        "I would bring clear communication, practical execution, and a strong focus on measurable outcomes. I am especially interested in this opportunity because it matches the kind of work I have been building toward.\n\n"
        f"Thank you for your time and consideration.\n\n{name or 'Sincerely'}"
    )


def generate_interview_questions(job_description: str) -> list[str]:
    analysis = analyze_job_description(job_description)
    skills = analysis["keywords"][:5] or ["your core technical skills"]
    return [
        f"Technical: How have you used {skill} in a real project or work setting?" for skill in skills[:3]
    ] + [
        "Behavioral: Tell me about a time you had to clarify ambiguous requirements.",
        "Project: Walk me through the strongest project on your resume and the decisions you made.",
        "Resume-based: Which bullet on your resume best proves you can succeed in this role?",
        "STAR: Describe a challenge, the action you took, and the measurable result."
    ]


def extract_keywords(text: str) -> list[str]:
    found = []
    lower = text.lower()
    for item in KNOWN_KEYWORDS:
        if item.lower() in lower and item not in found:
            found.append(item)
    words = re.findall(r"\b[A-Za-z][A-Za-z+#.-]{2,}\b", text)
    extras = []
    stop = {"and", "the", "for", "with", "you", "our", "will", "are", "that", "this", "from", "job", "work", "role", "requiring", "required", "responsibilities", "experience", "engineer", "developer", "analyst"}
    for word in words:
        if word.lower() not in stop and len(word) > 4 and word.title() not in found and word.title() not in extras:
            extras.append(word.title())
    return (found + extras)[:35]


def _heuristic_parse(text: str) -> dict:
    resume = deepcopy(EMPTY_RESUME)
    lines = _clean_lines(text)
    sections = _split_sections(lines)
    header_lines = _header_lines(lines)
    if header_lines:
        resume["personal_info"]["name"] = _guess_name(header_lines)
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone = re.search(r"(\+?\d[\d\s().-]{8,}\d)", text)
    linkedin = re.search(r"(linkedin\.com/[^\s]+)", text, re.I)
    github = re.search(r"(github\.com/[^\s]+)", text, re.I)
    portfolio = re.search(r"(https?://(?!.*linkedin)(?!.*github)[^\s]+)", text, re.I)
    if email:
        resume["personal_info"]["email"] = email.group(0)
    if phone:
        resume["personal_info"]["phone"] = phone.group(0)
    if linkedin:
        resume["personal_info"]["linkedin"] = linkedin.group(0)
    if github:
        resume["personal_info"]["github"] = github.group(0)
    if portfolio:
        resume["personal_info"]["portfolio"] = portfolio.group(0)
    resume["personal_info"]["location"] = _guess_location(header_lines)

    summary_lines = _section(sections, "summary", "profile", "professional summary", "objective")
    resume["summary"] = " ".join(summary_lines).strip()[:650]

    keywords = extract_keywords(text)
    skills_lines = _section(sections, "skills", "technical skills", "core skills", "technologies")
    parsed_skills = _parse_skills(skills_lines)
    resume["skills"] = _categorize_skills(_unique(parsed_skills + [keyword for keyword in keywords if keyword in KNOWN_KEYWORDS]))

    exp_lines = _section(sections, "experience", "work experience", "professional experience", "employment")
    resume["experience"] = _parse_experience(exp_lines)

    project_lines = _section(sections, "projects", "project experience", "personal projects")
    resume["projects"] = _parse_projects(project_lines, keywords)

    resume["education"] = _section(sections, "education")
    resume["certifications"] = _section(sections, "certifications", "certification", "licenses")

    if not resume["summary"]:
        resume["summary"] = _fallback_summary(lines, resume["skills"]["technical"])
    if not resume["experience"]:
        bullets = _bullet_like(lines)
        resume["experience"] = [{
            "company": "",
            "title": "",
            "location": "",
            "start_date": "",
            "end_date": "",
            "bullets": bullets[:5]
        }] if bullets else []
    return resume


SECTION_ALIASES = {
    "summary": {"summary", "professional summary", "profile", "objective", "about"},
    "skills": {"skills", "technical skills", "core skills", "technologies", "tools"},
    "experience": {"experience", "work experience", "professional experience", "employment", "employment history"},
    "projects": {"projects", "project experience", "personal projects", "academic projects"},
    "education": {"education", "academic background"},
    "certifications": {"certifications", "certification", "licenses", "licenses & certifications"}
}


def _clean_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line.strip()).strip() for line in text.splitlines() if line.strip()]


def _canonical_section(line: str) -> Optional[str]:
    normalized = re.sub(r"[^a-z& ]", "", line.lower()).strip()
    if len(normalized.split()) > 4:
        return None
    for canonical, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "header"
    sections[current] = []
    for line in lines:
        section = _canonical_section(line)
        if section:
            current = section
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _section(sections: dict[str, list[str]], *names: str) -> list[str]:
    result: list[str] = []
    canonicals = []
    for name in set(names):
        canonical = next((key for key, aliases in SECTION_ALIASES.items() if name == key or name in aliases), name)
        if canonical not in canonicals:
            canonicals.append(canonical)
    for canonical in canonicals:
        result.extend(sections.get(canonical, []))
    return result


def _header_lines(lines: list[str]) -> list[str]:
    header = []
    for line in lines[:12]:
        if _canonical_section(line):
            break
        header.append(line)
    return header


def _guess_name(lines: list[str]) -> str:
    for line in lines[:5]:
        if "@" not in line and not re.search(r"\d{3}", line) and len(line.split()) <= 5:
            return line[:80]
    return lines[0][:80] if lines else ""


def _guess_location(lines: list[str]) -> str:
    for line in lines[:8]:
        city_state = re.search(r"\b[A-Z][a-zA-Z .'-]+,\s*[A-Z]{2}\b", line)
        if city_state:
            return city_state.group(0)
        remote = re.search(r"\b(Remote|United States|USA)\b", line, re.I)
        if remote:
            return remote.group(0)
    return ""


def _parse_skills(lines: list[str]) -> list[str]:
    joined = ", ".join(lines)
    parts = re.split(r"[,|;•●\n]", joined)
    skills = []
    for part in parts:
        part = re.sub(r"^(languages|frameworks|tools|databases|cloud|technical|skills):", "", part.strip(), flags=re.I).strip()
        if 1 <= len(part.split()) <= 4 and len(part) <= 40:
            skills.append(part)
    return _unique(skills)


def _parse_experience(lines: list[str]) -> list[dict]:
    jobs = []
    current = None
    pending_header = []
    date_pattern = r"((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4})\s*[-–—]\s*((Present|Current)|((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})|\d{1,2}/\d{4}|\d{4})"
    for line in lines:
        is_bullet = _is_bullet(line)
        date_match = re.search(date_pattern, line, re.I)
        if date_match and not is_bullet:
            if current:
                jobs.append(current)
            title, company, location = _parse_job_header(" | ".join(pending_header + [line]), date_match.group(0))
            current = {
                "company": company,
                "title": title,
                "location": location,
                "start_date": date_match.group(1),
                "end_date": date_match.group(3),
                "bullets": []
            }
            pending_header = []
        elif is_bullet and current:
            current["bullets"].append(_clean_bullet(line))
        elif current and len(line.split()) >= 5:
            current["bullets"].append(_clean_bullet(line))
        else:
            pending_header.append(line)
    if current:
        jobs.append(current)
    return [job for job in jobs if job["title"] or job["company"] or job["bullets"]]


def _parse_job_header(header: str, date_text: str) -> tuple[str, str, str]:
    clean = header.replace(date_text, "")
    parts = [part.strip(" |,-") for part in re.split(r"\s+\|\s+| - | – | — |\n", clean) if part.strip(" |,-")]
    title = parts[0] if parts else ""
    company = parts[1] if len(parts) > 1 else ""
    location = parts[2] if len(parts) > 2 else ""
    return title[:120], company[:120], location[:120]


def _parse_projects(lines: list[str], keywords: list[str]) -> list[dict]:
    projects = []
    current = None
    for line in lines:
        if _is_bullet(line) and current:
            current["bullets"].append(_clean_bullet(line))
        elif len(line.split()) <= 10:
            if current:
                projects.append(current)
            tech = [kw for kw in keywords if kw.lower() in line.lower()]
            current = {"name": re.sub(r"\s*\|.*$", "", line), "technologies": tech, "bullets": []}
        elif current:
            current["bullets"].append(_clean_bullet(line))
    if current:
        projects.append(current)
    return projects


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^[-•●▪▫*]", line.strip())) or bool(re.match(r"^(built|created|developed|improved|designed|implemented|analyzed|managed|automated|delivered|worked|led|owned|supported)\b", line, re.I))


def _clean_bullet(line: str) -> str:
    return line.strip(" -•●▪▫*\t")


def _bullet_like(lines: list[str]) -> list[str]:
    return [_clean_bullet(line) for line in lines if _is_bullet(line) or len(line.split()) >= 8][:8]


def _fallback_summary(lines: list[str], skills: list[str]) -> str:
    useful = [line for line in lines[1:8] if len(line.split()) >= 6 and "@" not in line]
    if useful:
        return " ".join(useful[:2])[:450]
    if skills:
        return f"Professional with experience in {', '.join(skills[:5])}."
    return ""


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        clean = value.strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _openai_json(prompt: str, text: str) -> dict:
    client = OpenAI(api_key=settings.openai_api_key or os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "system", "content": AI_SYSTEM_PROMPT}, {"role": "user", "content": f"{prompt}\n\n{text}"}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content or "{}")


def _merge_schema(parsed: dict) -> dict:
    merged = deepcopy(EMPTY_RESUME)
    for key, value in (parsed or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return _sanitize_resume(merged)


def _sanitize_resume(resume: dict) -> dict:
    resume["education"] = _remove_keyword_dump(resume.get("education", []))
    resume["certifications"] = _remove_keyword_dump(resume.get("certifications", []))
    return resume


def _remove_keyword_dump(lines: list[str]) -> list[str]:
    cleaned = []
    skip_after_marker = False
    for line in lines or []:
        text = str(line).strip()
        lower = text.lower()
        if "ats keyword" in lower or lower in {"keywords", "ats"}:
            skip_after_marker = True
            continue
        looks_like_dump = text.count(",") >= 8 and not re.search(r"(?i)\b(university|college|school|degree|master|bachelor|certified|certification)\b", text)
        if skip_after_marker and looks_like_dump:
            continue
        cleaned.append(text)
        skip_after_marker = False
    return cleaned


def _confidence(parsed: dict) -> dict:
    return {key: 0.85 if parsed.get(key) else 0.35 for key in EMPTY_RESUME}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[.\n]", text) if len(part.strip()) > 30]


def _seniority(text: str) -> str:
    lower = text.lower()
    if "senior" in lower or "lead" in lower:
        return "Senior"
    if "junior" in lower or "entry" in lower:
        return "Entry"
    return "Mid"


def _domain(text: str) -> str:
    lower = text.lower()
    if "health" in lower:
        return "Healthcare"
    if "finance" in lower or "bank" in lower:
        return "Finance"
    if "data" in lower:
        return "Data"
    return "General Technology"


def _all_skills(resume: dict) -> list[str]:
    skills = resume.get("skills", {})
    return [skill for values in skills.values() if isinstance(values, list) for skill in values]


def _rank_user_skills(user_skills: list[str], jd_keywords: list[str]) -> list[str]:
    ranked = []
    remaining = []
    jd_lower = {keyword.lower() for keyword in jd_keywords}
    for skill in _unique(user_skills):
        if _keyword_key(skill) in {_keyword_key(keyword) for keyword in jd_keywords}:
            ranked.append(skill)
        else:
            remaining.append(skill)
    return ranked + remaining


def _supported_jd_keywords(resume: dict, jd_keywords: list[str]) -> list[str]:
    resume_text = _resume_keyword_text(resume)
    supported = []
    seen = set()
    for keyword in jd_keywords:
        key = _keyword_key(keyword)
        if key and key in resume_text and key not in seen:
            seen.add(key)
            supported.append(keyword)
    return supported[:18]


def _resume_keyword_text(resume: dict) -> str:
    parts = [
        resume.get("target_title", ""),
        resume.get("summary", ""),
    ]
    parts.extend(_all_skills(resume))
    for job in resume.get("experience", []):
        parts.extend([
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
        ])
        parts.extend(job.get("bullets", []))
    for project in resume.get("projects", []):
        parts.extend([project.get("name", "")])
        parts.extend(project.get("technologies", []))
        parts.extend(project.get("bullets", []))
    parts.extend(resume.get("education", []))
    parts.extend(resume.get("certifications", []))
    raw = " ".join(str(part) for part in parts if part).lower()
    normalized = _keyword_key(raw)
    return f"{raw} {normalized}"


def _categorize_skills(skills: list[str], jd_keywords: Optional[list[str]] = None) -> dict:
    jd_keywords = jd_keywords or []
    ordered = _rank_user_skills(_dedupe_related_keywords(skills), jd_keywords)
    categories = {
        "ai_ml_core": ["LLM", "RAG", "Generative AI", "GenAI", "NLP", "Computer Vision", "AI Agents", "Vector Embeddings", "Recommendation Systems", "Time Series Forecasting", "Machine Learning", "Data Analysis", "A/B Testing"],
        "deep_learning": ["ANN", "CNN", "RNN", "LSTM", "Transformers", "BERT", "GANs"],
        "genai_llm_systems": ["Prompt Engineering", "Semantic Caching", "KV-Cache", "LoRA", "QLoRA", "OpenAI APIs", "LangChain", "Hugging Face"],
        "frameworks_libraries": ["PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "FastAPI", "Spring Boot", "React", "Node", "GraphQL", "REST"],
        "mlops_engineering": ["MLflow", "Docker", "Kubernetes", "CI/CD", "Model Monitoring", "Drift Detection", "Git", "GitHub"],
        "cloud_infrastructure": ["AWS", "Azure", "GCP", "S3", "EC2", "EKS", "ECS", "ECR", "Lambda", "Bedrock", "SageMaker", "BigQuery", "Snowflake"],
        "databases_vector_stores": ["SQL", "PostgreSQL", "MySQL", "NoSQL", "Redis", "Pinecone", "ChromaDB", "FAISS"],
        "programming": ["Python", "Java", "JavaScript", "TypeScript", "R", "PySpark", "APIs", "Microservices"],
        "monitoring_observability": ["Prometheus", "Grafana", "OpenTelemetry", "Sentry"],
        "ai_safety_compliance": ["PII Masking", "Hallucination Detection", "Prompt Injection", "Rate Limiting"],
        "developer_tools": ["Linux", "UNIX", "Ubuntu", "Cursor", "Windsurf", "IntelliJ IDEA", "Visual Studio", "GitHub Copilot", "Tableau", "Power BI", "Excel"]
    }
    result = {key: [] for key in categories}
    result.update({"technical": [], "tools": [], "cloud": [], "databases": [], "soft_skills": []})
    for skill in ordered:
        placed = False
        for group, group_skills in categories.items():
            if any(_keyword_key(skill) == _keyword_key(item) for item in group_skills):
                result[group].append(skill)
                placed = True
                break
        if not placed:
            result["technical"].append(skill)
    return {key: _unique(values)[:18] for key, values in result.items()}


def _summary(resume: dict, ranked_skills: list[str], target_title: str = "") -> str:
    title = target_title or (resume.get("experience", [{}])[0].get("title", "professional") if resume.get("experience") else "professional")
    years = _years_experience(resume)
    skills = ", ".join(_dedupe_related_keywords(ranked_skills)[:6])
    domain = _target_domain(target_title) or _resume_domain(resume)
    years_text = f" with {years}+ years of experience" if years else " with experience"
    skill_text = f" using {skills}" if skills else ""
    domain_text = f" in {domain}" if domain else ""
    return f"{title}{years_text}{domain_text}{skill_text}. Experienced in building practical systems, APIs, automation workflows, and data-driven features that improve reliability, delivery quality, and business operations."


def _target_domain(target_title: str) -> str:
    title = target_title.lower()
    if "frontend" in title:
        return "frontend engineering"
    if "backend" in title or "software" in title:
        return "backend systems"
    if "ai" in title:
        return "AI and automation"
    if "cloud" in title or "devops" in title:
        return "cloud and DevOps"
    if "data" in title:
        return "data and analytics"
    return ""


def _rewrite_bullets(bullets: list[str], skills: list[str], target_keywords: Optional[list[str]] = None) -> list[str]:
    verbs = ["Developed", "Built", "Improved", "Implemented", "Designed", "Automated", "Analyzed", "Delivered"]
    rewritten = []
    target_keywords = target_keywords or []
    for index, bullet in enumerate(bullets):
        rewritten.append(_add_supported_keyword_context(_rewrite_bullet(bullet, skills, verbs[index % len(verbs)]), target_keywords, index))
    return rewritten


def _rewrite_bullet(bullet: str, skills: list[str], fallback_verb: str) -> str:
    clean = _normalize_weak_opening(_remove_ai_tone(bullet.rstrip(".")))
    tech = next((item for item in skills if item.lower() in clean.lower()), None)
    if len(clean.split()) < 6:
        tool_text = f" using {tech}" if tech and _keyword_key(tech) not in clean.lower() else ""
        if _starts_with_action(clean):
            clean = f"{_capitalize(clean)}{tool_text} to improve clarity, reliability, or delivery"
        else:
            clean = f"{fallback_verb} {clean.lower()}{tool_text} to improve clarity, reliability, or delivery"
    elif not _starts_with_action(clean):
        clean = f"{fallback_verb} {clean[0].lower() + clean[1:]}"
    return _restore_acronyms(clean) + "."


def _years_experience(resume: dict) -> int:
    years = []
    for job in resume.get("experience", []):
        start = re.search(r"\d{4}", job.get("start_date", ""))
        end = re.search(r"\d{4}", job.get("end_date", ""))
        if start:
            start_year = int(start.group(0))
            end_year = int(end.group(0)) if end else 2026
            if end_year >= start_year:
                years.append(end_year - start_year)
    return sum(years)


def _resume_domain(resume: dict) -> str:
    text = " ".join(
        _all_skills(resume)
        + [job.get("title", "") for job in resume.get("experience", [])]
        + [bullet for job in resume.get("experience", []) for bullet in job.get("bullets", [])]
        + [project.get("name", "") for project in resume.get("projects", [])]
    ).lower()
    if re.search(r"\b(ai|machine learning|llm|rag)\b", text):
        return "AI and automation"
    if any(word in text for word in ["cloud", "aws", "azure", "gcp", "kubernetes", "docker"]):
        return "cloud and backend systems"
    if any(word in text for word in ["data", "sql", "analytics", "dashboard"]):
        return "data and analytics"
    return ""


def _normalize_weak_opening(text: str) -> str:
    replacements = {
        r"(?i)^worked on\s+": "built ",
        r"(?i)^worked with\s+": "supported ",
        r"(?i)^helped with\s+": "supported ",
        r"(?i)^handled\s+": "managed ",
        r"(?i)^responsible for\s+": "owned "
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text).strip()
    return text


def _add_supported_keyword_context(bullet: str, target_keywords: list[str], index: int) -> str:
    if not target_keywords:
        return bullet
    chunk = _dedupe_related_keywords(target_keywords[index * 3:index * 3 + 3])
    missing = [keyword for keyword in chunk if _keyword_key(keyword) not in bullet.lower()]
    if not missing:
        return bullet
    base = bullet.rstrip(".")
    connector = " with emphasis on" if " using " in base.lower() else " using"
    return f"{base}{connector} {', '.join(missing)}."


def _format_title(title: str) -> str:
    replacements = {
        "genai": "GenAI",
        "ai": "AI",
        "devops": "DevOps"
    }
    words = title.lower().split()
    return " ".join(replacements.get(word, word.capitalize()) for word in words)


def _starts_with_action(text: str) -> bool:
    return bool(re.match(r"(?i)^(built|created|developed|improved|designed|implemented|analyzed|managed|automated|delivered|supported|owned|led)", text))


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _restore_acronyms(text: str) -> str:
    replacements = {"apis": "APIs", "api": "API", "sql": "SQL", "aws": "AWS", "ui": "UI", "etl": "ETL", "llm": "LLM", "rag": "RAG"}
    for source, target in replacements.items():
        text = re.sub(rf"\b{source}\b", target, text, flags=re.I)
    return text


def _keyword_key(value: str) -> str:
    key = value.lower().replace("/", "").replace("-", "").replace(".", "").strip()
    if key == "api":
        return "apis"
    return key


def _dedupe_related_keywords(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        key = _keyword_key(value)
        if key and key not in seen:
            seen.add(key)
            result.append("APIs" if key == "apis" else value)
    return result


def _suggest_projects_for_gap(jd_keywords: list[str], resume: dict) -> list[dict]:
    resume_text = _resume_keyword_text(resume)
    missing = [keyword for keyword in jd_keywords if _keyword_key(keyword) not in resume_text]
    text = " ".join(missing + jd_keywords).lower()
    suggestions = []
    if any(word in text for word in ["react", "typescript", "frontend"]):
        suggestions.append({
            "name": "Frontend Job Tracker Dashboard",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"react", "typescript", "javascript", "api", "apis"}],
            "bullets": [
                "Build a responsive dashboard with reusable components, API integration, filtering, loading states, and error handling.",
                "Document component structure, state management, and accessibility decisions."
            ]
        })
    if any(word in text for word in ["aws", "docker", "kubernetes", "cloud", "ci/cd"]):
        suggestions.append({
            "name": "Cloud Deployment Pipeline",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"aws", "docker", "kubernetes", "ci/cd"}],
            "bullets": [
                "Containerize an API and deploy it with environment configuration, health checks, and rollback notes.",
                "Add CI/CD steps and monitoring documentation to show production readiness."
            ]
        })
    if any(word in text for word in ["llm", "rag", "ai", "machine learning"]):
        suggestions.append({
            "name": "RAG Document Assistant",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"llm", "rag", "python", "fastapi", "postgresql"}],
            "bullets": [
                "Build a document question-answering workflow with chunking, retrieval, prompt templates, and response evaluation.",
                "Expose the workflow through an API and document retrieval quality, latency, and failure cases."
            ]
        })
    if any(word in text for word in ["sql", "postgresql", "data", "analytics", "tableau", "power bi", "forecasting"]):
        suggestions.append({
            "name": "Analytics KPI Dashboard",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"sql", "postgresql", "python", "tableau", "power bi", "excel"}],
            "bullets": [
                "Create cleaned datasets, KPI queries, and dashboard views that answer role-specific business questions.",
                "Document assumptions, data quality checks, and recommendations so recruiters can see analytical judgment."
            ]
        })
    if any(word in text for word in ["java", "spring boot", "microservices", "kafka"]):
        suggestions.append({
            "name": "Spring Boot Event-Driven Service",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"java", "spring boot", "postgresql", "kafka", "docker"}],
            "bullets": [
                "Build a REST service with validation, persistence, event publishing, tests, and API documentation.",
                "Show service boundaries, failure handling, and database design decisions in the project README."
            ]
        })
    return suggestions[:5]


def _remove_ai_tone(text: str) -> str:
    for word in BAD_AI_WORDS:
        text = re.sub(rf"\b{word}\b", "used", text, flags=re.I)
    return text
