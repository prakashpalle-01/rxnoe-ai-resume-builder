import json
import os
import re
from copy import deepcopy
from typing import Optional
from openai import OpenAI
from app.core.config import get_settings
from .role_benchmarks import infer_resume_benchmark
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
- Align to the role without copying job-description phrases directly.
- Avoid repetitive sentence structure. Do not repeat the same action verb more than twice.
- Mention technologies only when they directly support the achievement or architecture.
- Avoid comma-list endings and keyword stuffing.
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
Action + System + Business Problem + Impact.
Use outcome-driven, problem-focused, engineering-oriented language. Avoid weak bullets like "Built dashboards" or "Developed APIs."

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
GENERIC_KEYWORDS = {
    "associate", "stack", "product", "skills", "required", "preferred", "qualification", "qualifications",
    "requirements", "responsibilities", "development", "software", "systems", "build", "building", "team",
    "teams", "business", "technical", "technology", "technologies", "platform", "platforms", "solutions",
    "solution", "engineer", "engineering", "developer", "analyst", "candidate", "role", "work", "working",
    "well-tested", "top-notch", "customer-reported", "cross-functional", "problem-solving",
    "decision-making", "thoughtful", "humility", "iteratively", "descriptive", "fantastic"
}
KNOWN_KEYWORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Node", "FastAPI", "Spring Boot", "SQL",
    "PostgreSQL", "AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Git", "REST", "GraphQL",
    "HTML5", "CSS3", "Tailwind CSS", "Redux", "React Query", "Next.js", "Angular", "Vue", "Svelte",
    "Django", "Flask", "Express", "NestJS", ".NET", "C#", "Go", "Ruby", "Ruby on Rails", "PHP",
    "Machine Learning", "LLM", "RAG", "Tableau", "Power BI", "Excel", "Agile", "Scrum", "Kafka",
    "Redis", "Celery", "Microservices", "Data Analysis", "ETL", "Leadership", "Communication", "APIs",
    "Generative AI", "GenAI", "NLP", "Computer Vision", "AI Agents", "Vector Embeddings", "LoRA", "QLoRA",
    "Recommendation Systems", "Time Series Forecasting", "A/B Testing", "ANN", "CNN", "RNN", "LSTM",
    "Transformers", "BERT", "GANs", "Prompt Engineering", "Semantic Caching", "KV-Cache", "Pinecone",
    "ChromaDB", "FAISS", "PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "Hugging Face", "LangChain",
    "OpenAI APIs", "MLflow", "Model Monitoring", "Drift Detection", "Prometheus", "Grafana", "OpenTelemetry",
    "Sentry", "PII Masking", "Hallucination Detection", "Prompt Injection", "Rate Limiting", "Linux",
    "UNIX", "Ubuntu", "Cursor", "Windsurf", "IntelliJ IDEA", "Visual Studio", "GitHub Copilot", "Snowflake",
    "SageMaker", "Bedrock", "Lambda", "EKS", "ECS", "ECR", "S3", "EC2", "BigQuery", "PySpark",
    "MongoDB", "DynamoDB", "Qdrant", "Neo4j", "Elasticsearch", "OpenSearch", "Airflow", "dbt",
    "Databricks", "Spark", "Pandas", "NumPy", "Jupyter", "Looker", "Jenkins", "GitHub Actions",
    "GitLab CI", "Azure DevOps", "Terraform", "Ansible", "Helm", "Istio", "Nginx", "Prometheus",
    "OAuth", "SSO", "JWT", "IAM", "SOC 2", "HIPAA", "Cypress", "Jest", "Playwright", "Selenium",
    "Postman", "Swagger", "OpenAPI", "Figma", "Jira", "Confluence", "SDLC", "TDD", "BDD",
    "Stripe", "Stripe APIs", "Datadog", "AWS Performance Insights", "Ruby on Rails", "Rails"
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
    sections = _jd_sections(text)
    keywords = extract_keywords(text)
    title = _extract_job_title(text)
    required = _extract_required_skills(sections, keywords)
    preferred = _extract_preferred_skills(sections, keywords, required)
    responsibilities = _extract_responsibilities(text, sections)
    tools = _extract_tools(keywords)
    benchmark = infer_resume_benchmark(text)
    return {
        "job_title": title,
        "company": "",
        "role_titles": _extract_role_titles(text, title),
        "required_skills": required,
        "preferred_skills": preferred,
        "tools": tools,
        "technologies": keywords,
        "responsibilities": responsibilities,
        "job_duties": responsibilities,
        "seniority_level": _seniority(text),
        "domain": _domain(text),
        "keywords": keywords,
        "soft_skills": _soft_skills(text, keywords),
        "hidden_recruiter_expectations": _hidden_expectations(text, keywords, responsibilities) or [
            "Clear role alignment in the top third of the resume",
            "Evidence of impact without inflated claims",
            "Recent experience connected to required tools and responsibilities"
        ],
        "resume_benchmark": benchmark,
    }


def optimize_resume(resume: dict, instruction: str, job_description: Optional[str] = None) -> tuple[dict, str]:
    should_target = any(word in instruction.lower() for word in ["target", "match", "job description", "ats"])
    if settings.openai_api_key and settings.llm_provider.lower() == "openai":
        optimized = _openai_optimize_resume(resume, instruction, job_description or "")
        if should_target:
            _mark_generated_targeted_resume(optimized, job_description or "")
        return _merge_schema(optimized), "Generated a deeply optimized ATS-friendly resume using the configured AI provider."

    source_resume = deepcopy(_merge_schema(resume))
    optimized = deepcopy(source_resume)
    job_analysis = analyze_job_description(job_description or "")
    jd_keywords = job_analysis.get("keywords", extract_keywords(job_description or ""))
    source_supported = _supported_jd_keywords(source_resume, jd_keywords)
    optimized["source_supported_keywords"] = source_supported
    optimized["unverified_job_keywords"] = [
        keyword for keyword in jd_keywords if _keyword_key(keyword) not in {_keyword_key(item) for item in source_supported}
    ]
    summary = optimized.get("summary") or ""
    top_skills = _rank_role_skills(_all_skills(optimized), jd_keywords, job_analysis)
    optimized["skills"] = _categorize_skills(_blend_job_skills(_all_skills(optimized), job_analysis), jd_keywords)
    if job_analysis.get("job_title"):
        optimized["target_title"] = _credible_target_title(optimized, job_analysis)
    optimized["target_keywords"] = _targeted_keywords(optimized, job_analysis)
    if should_target or "summary" in instruction.lower() or not summary:
        optimized["summary"] = _summary(optimized, optimized["target_keywords"] or top_skills, optimized.get("target_title") or job_analysis.get("job_title", ""), job_analysis)
    for job in optimized.get("experience", []):
        job["bullets"] = _rewrite_bullets(job.get("bullets", []), top_skills, optimized["target_keywords"], job_analysis)
    for project in optimized.get("projects", []):
        project_skills = _rank_user_skills(project.get("technologies", []) + top_skills, jd_keywords)
        project["bullets"] = _rewrite_bullets(project.get("bullets", []), project_skills, optimized["target_keywords"], job_analysis)
    if should_target:
        _mark_generated_targeted_resume(optimized, job_description or "")
    optimized["suggested_projects"] = _suggest_projects_for_gap(jd_keywords, optimized, job_analysis)
    optimized["projects"] = _add_relevant_projects(optimized.get("projects", []), optimized["suggested_projects"])
    optimized["summary"] = _remove_ai_tone(optimized["summary"])
    _humanize_resume(optimized)
    _recruiter_realism_pass(optimized, job_analysis)
    _role_specific_cleanup(optimized, job_analysis, source_resume)
    _keep_only_verified_projects(optimized, source_resume)
    return optimized, "Improved summary, experience, and project bullets with recruiter-style language, verified skills, clearer impact, and ATS alignment without adding fake claims."


def _openai_optimize_resume(resume: dict, instruction: str, job_description: str) -> dict:
    prompt = f"""
Generate the strongest possible ATS-friendly resume for the job description using only the candidate's truthful resume data.

Instruction: {instruction}

Rules:
- Do not invent fake experience, companies, degrees, certifications, tools, or metrics.
- Add job-description keywords only when they are supported by the candidate resume.
- Rewrite weak bullets using action + work + technology + business/technical impact.
- Avoid repetitive action verbs; never repeat the same verb more than twice.
- Do not keyword-stuff comma-separated technologies into bullet endings.
- Do not copy job-description phrases directly; translate them into natural resume language.
- Use Action + System + Business Problem + Impact for bullets.
- Prioritize skills by target role. Solutions architecture emphasizes stakeholders, integration, architecture communication, Agile, and cloud systems. AI engineering emphasizes RAG, LLM systems, vector databases, orchestration, and automation.
- Avoid overinflated target titles when the candidate lacks leadership or architecture ownership evidence.
- Run a recruiter realism check before final JSON: believable, human, not overstated, not keyword-heavy, not copied from the JD.
- Write problem-focused, architecture-aware bullets with clear outcomes.
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
        if _keyword_in_text(item, lower) and item not in found:
            found.append(item)
    words = re.findall(r"\b[A-Za-z][A-Za-z+#.-]{2,}\b", text)
    extras = []
    stop = {"and", "the", "for", "with", "you", "our", "will", "are", "that", "this", "from", "job", "work", "role", "requiring", "required", "responsibilities", "experience", "engineer", "developer", "analyst"} | GENERIC_KEYWORDS
    for word in words:
        if word.lower() == "github" and any(item.lower().startswith("github ") for item in found):
            continue
        if word.lower() not in stop and _looks_like_keyword(word) and word.title() not in found and word.title() not in extras:
            extras.append(word.title())
    return (found + extras)[:35]


def _keyword_in_text(keyword: str, lower_text: str) -> bool:
    pattern = re.escape(keyword.lower()).replace(r"\ ", r"[\s/-]+")
    return bool(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", lower_text))


def _looks_like_keyword(word: str) -> bool:
    lower = word.lower().strip(".")
    if lower in GENERIC_KEYWORDS or lower.endswith("-based") or len(lower) <= 4:
        return False
    if "-" in lower and lower not in {"front-end", "full-stack"}:
        return False
    return bool(re.search(r"[A-Z+#./-]", word[1:]) or lower in {"django", "terraform", "qdrant", "neo4j", "snowflake", "langchain", "prometheus", "grafana"})


def _extract_job_title(text: str) -> str:
    explicit = re.search(r"(?im)^\s*(job title|title|role|position|opening)\s*[:\-]\s*([A-Za-z0-9/ &.+#-]{3,100})", text)
    if explicit:
        return _format_title(re.split(r"\.|\n|required|preferred|responsibilities", explicit.group(2), flags=re.I)[0])
    title_match = re.search(
        r"(?i)(principal|staff|senior|sr\.?|lead|mid-level|junior|entry-level)?\s*(genai engineer|generative ai engineer|ai architect|machine learning engineer|ml engineer|ai engineer|data engineer|data scientist|data analyst|analytics engineer|business intelligence analyst|platform engineer|site reliability engineer|sre|linux systems engineer|systems engineer|aws software engineer|\.net developer|software engineer|software developer|product engineer|devops engineer|cloud engineer|software solutions architect|solutions architect|cloud architect|business analyst|systems analyst|qa automation engineer|qa engineer|test automation engineer|quality assurance engineer|java developer|java backend engineer|python developer|go developer|golang developer|react developer|full stack developer|full stack engineer|back-end software engineer|backend software engineer|backend developer|backend engineer|frontend developer|frontend engineer|mobile engineer|ios developer|android developer|security engineer|cybersecurity analyst)",
        text,
    )
    if title_match:
        return _format_title(title_match.group(0))
    looking_for = re.search(r"(?i)(looking for|seeking|hiring|join us as)\s+(an?\s+)?([A-Za-z0-9/ &.+#-]{3,80}?(engineer|developer|analyst|architect|scientist|manager|specialist|consultant))", text)
    if looking_for:
        return _format_title(looking_for.group(3))
    for line in _clean_lines(text)[:8]:
        if 2 <= len(line.split()) <= 8 and re.search(r"(?i)\b(engineer|developer|analyst|architect|manager|specialist)\b", line):
            return _format_title(line)
    return ""


def _extract_role_titles(text: str, primary: str) -> list[str]:
    titles = [primary] if primary else []
    for match in re.finditer(r"(?i)\b((principal|staff|senior|sr\.?|lead|junior|entry-level|mid-level)?\s*[A-Za-z/&.+#-]{2,30}\s+(engineer|developer|analyst|architect|scientist|manager|specialist|consultant))\b", text):
        title = _format_title(match.group(1))
        if title and title not in titles and len(title.split()) <= 6:
            titles.append(title)
    return titles[:6]


def _jd_sections(text: str) -> dict[str, str]:
    aliases = {
        "required": {"required qualifications", "requirements", "required skills", "must have", "minimum qualifications", "basic qualifications"},
        "preferred": {"preferred qualifications", "nice to have", "preferred skills", "bonus", "plus"},
        "responsibilities": {"responsibilities", "what you will do", "what you'll do", "duties", "role responsibilities", "day to day"},
        "summary": {"about the role", "job summary", "overview", "description"}
    }
    sections: dict[str, list[str]] = {"summary": []}
    current = "summary"
    for line in _clean_lines(text):
        normalized = re.sub(r"[^a-z ]", "", line.lower()).strip()
        matched = next((key for key, names in aliases.items() if normalized in names), None)
        if matched:
            current = matched
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(values) for key, values in sections.items()}


def _extract_required_skills(sections: dict[str, str], keywords: list[str]) -> list[str]:
    source = "\n".join([sections.get("required", ""), sections.get("responsibilities", "")])
    skills = extract_keywords(source) if source.strip() else []
    return _unique(skills + keywords[:8])[:18]


def _extract_preferred_skills(sections: dict[str, str], keywords: list[str], required: list[str]) -> list[str]:
    skills = extract_keywords(sections.get("preferred", "")) if sections.get("preferred", "").strip() else []
    required_keys = {_keyword_key(item) for item in required}
    remaining = [keyword for keyword in keywords if _keyword_key(keyword) not in required_keys]
    return _unique(skills + remaining)[:14]


def _extract_tools(keywords: list[str]) -> list[str]:
    tool_keys = {"aws", "azure", "gcp", "docker", "kubernetes", "sql", "postgresql", "mysql", "mongodb", "redis", "python", "java", "react", "tableau", "power bi", "terraform", "jenkins", "github actions", "jira", "confluence", "figma", "postman", "swagger", "openapi"}
    return [kw for kw in keywords if _keyword_key(kw) in {_keyword_key(item) for item in tool_keys}]


def _extract_responsibilities(text: str, sections: dict[str, str]) -> list[str]:
    source = sections.get("responsibilities") or text
    lines = []
    for line in _clean_lines(source):
        clean = _clean_bullet(line)
        if len(clean.split()) >= 4 and re.search(r"(?i)\b(build|design|develop|manage|own|lead|collaborate|implement|optimize|automate|support|create|deliver|maintain|monitor|analyze|integrate|scale|architect|troubleshoot)\b", clean):
            lines.append(clean)
    if not lines:
        lines = _sentences(text)
    return _unique(lines)[:8]


def _soft_skills(text: str, keywords: list[str]) -> list[str]:
    soft = ["Communication", "Leadership", "Collaboration", "Stakeholder Management", "Problem Solving", "Mentoring", "Ownership", "Agile", "Scrum"]
    lower = text.lower()
    found = [skill for skill in soft if skill.lower() in lower]
    found.extend([kw for kw in keywords if kw.lower() in {"communication", "leadership", "agile", "scrum"}])
    return _unique(found)[:8]


def _hidden_expectations(text: str, keywords: list[str], responsibilities: list[str]) -> list[str]:
    expectations = ["Clear role alignment in the top third of the resume"]
    lower = text.lower()
    if any(word in lower for word in ["scale", "scalable", "distributed", "high volume", "millions"]):
        expectations.append("Evidence of scalable systems, performance, or high-volume processing")
    if any(word in lower for word in ["cross-functional", "stakeholder", "product", "business"]):
        expectations.append("Ability to translate business requirements into technical delivery")
    if any(word in lower for word in ["ai", "llm", "rag", "machine learning", "automation"]):
        expectations.append("Practical AI workflow experience with reliability, evaluation, and production constraints")
    if responsibilities:
        expectations.append("Recent bullets should mirror the role's core duties without sounding keyword-stuffed")
    if keywords:
        expectations.append("Required tools should appear naturally in skills, projects, and recent experience")
    return _unique(expectations)[:6]


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
    normalized = []
    for values in skills.values():
        if not isinstance(values, list):
            continue
        for skill in values:
            normalized.extend(_normalize_skill_items(skill))
    return _unique([skill for skill in normalized if _valid_skill(skill)])


def _normalize_skill_items(value: str) -> list[str]:
    text = str(value).strip()
    text = re.sub(r"(?i)^(frontend|backend|cloud\s*&?\s*devops|ai\s*&?\s*automation|tools?|databases?|technical|skills?)\s*:\s*", "", text)
    parts = re.split(r",|;|\||\band\b", text)
    return [part.strip() for part in parts if part.strip()]


def _valid_skill(skill: str) -> bool:
    clean = skill.strip()
    key = _keyword_key(clean)
    if not clean or key in GENERIC_KEYWORDS or len(clean) > 35:
        return False
    if len(clean.split()) > 4:
        return False
    return True


def _rank_user_skills(user_skills: list[str], jd_keywords: list[str]) -> list[str]:
    ranked = []
    remaining = []
    jd_lower = {keyword.lower() for keyword in jd_keywords}
    for skill in _unique([item for item in user_skills if _valid_skill(item)]):
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


def _targeted_keywords(resume: dict, job_analysis: dict) -> list[str]:
    required = job_analysis.get("required_skills", [])
    preferred = job_analysis.get("preferred_skills", [])
    tools = job_analysis.get("tools", [])
    technologies = job_analysis.get("technologies", [])
    supported = _supported_jd_keywords(resume, required + preferred + tools + technologies)
    return _unique([keyword for keyword in supported + required + tools + preferred + technologies if _highlightable_keyword(keyword)])[:80]


def _highlightable_keyword(keyword: str) -> bool:
    clean = keyword.strip()
    key = _keyword_key(clean)
    if not clean or key in GENERIC_KEYWORDS or len(clean) > 35:
        return False
    if len(clean) < 4 and not re.fullmatch(r"[A-Z0-9+#./-]{2,}", clean):
        return False
    if len(clean.split()) > 4:
        return False
    return True


def _blend_job_skills(user_skills: list[str], job_analysis: dict) -> list[str]:
    family = _role_family(job_analysis)
    jd_skills = job_analysis.get("required_skills", []) + job_analysis.get("tools", []) + job_analysis.get("preferred_skills", [])[:6]
    if family in {"solutions_architecture", "fullstack_rails"}:
        low_level_ai = {"ann", "cnn", "rnn", "lstm", "bert", "gans", "lora", "qlora", "kv-cache", "semantic caching"}
        jd_skills = [skill for skill in jd_skills if _keyword_key(skill) not in low_level_ai]
    skills = _unique([skill for skill in _role_priority_terms(job_analysis) + user_skills + jd_skills if _valid_skill(skill)])
    if family == "fullstack_rails":
        demote = {"rag", "llm", "ai agents", "langchain", "prompt engineering", "vector embeddings", "mlflow", "model monitoring"}
        skills = [skill for skill in skills if _keyword_key(skill) not in demote]
    return skills


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
    ordered = _rank_user_skills(_dedupe_related_keywords([skill for skill in skills if _valid_skill(skill)]), jd_keywords)
    categories = {
        "ai_ml_core": ["LLM", "RAG", "Generative AI", "GenAI", "NLP", "Computer Vision", "AI Agents", "Vector Embeddings", "Recommendation Systems", "Time Series Forecasting", "Machine Learning", "Data Analysis", "A/B Testing"],
        "deep_learning": ["ANN", "CNN", "RNN", "LSTM", "Transformers", "BERT", "GANs"],
        "genai_llm_systems": ["Prompt Engineering", "Semantic Caching", "KV-Cache", "LoRA", "QLoRA", "OpenAI APIs", "LangChain", "Hugging Face"],
        "frameworks_libraries": ["PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "FastAPI", "Spring Boot", "React", "Node", "GraphQL", "REST"],
        "mlops_engineering": ["MLflow", "Docker", "Kubernetes", "CI/CD", "Model Monitoring", "Drift Detection", "Git", "GitHub", "GitHub Actions", "GitLab CI", "Azure DevOps", "Jenkins", "Terraform", "Helm", "Istio"],
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
    return {key: _unique(values)[:12] for key, values in result.items()}


def _summary(resume: dict, ranked_skills: list[str], target_title: str = "", job_analysis: Optional[dict] = None) -> str:
    title = target_title or (resume.get("experience", [{}])[0].get("title", "professional") if resume.get("experience") else "professional")
    years_label = _experience_label(resume)
    skills_list = _summary_skills(ranked_skills)
    skills = _human_join(skills_list)
    domain = _target_domain(target_title) or _target_domain_from_job(job_analysis or {}) or _resume_domain(resume)
    focus = _summary_focus(job_analysis or {})
    years_text = f" with {years_label} of experience" if years_label else " with experience"
    skill_text = f" working with {skills}" if skills else ""
    domain_text = f" in {domain}" if domain else ""
    focus_text = f" Focused on {focus}." if focus else ""
    value = _summary_value_line(job_analysis or {}, skills_list)
    return f"{title}{years_text}{domain_text}{skill_text}.{focus_text} {value}".strip()


def _summary_skills(skills: list[str]) -> list[str]:
    return _dedupe_related_keywords([skill for skill in skills if _valid_skill(skill) and _keyword_key(skill) not in GENERIC_KEYWORDS])[:5]


def _human_join(values: list[str]) -> str:
    values = [value for value in values if value]
    if len(values) <= 2:
        return " and ".join(values)
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _summary_value_line(job_analysis: dict, skills: list[str]) -> str:
    focus = _summary_focus(job_analysis)
    lower = " ".join([
        job_analysis.get("job_title", ""),
        job_analysis.get("domain", ""),
        " ".join(job_analysis.get("job_duties", [])[:4]),
    ]).lower()
    if _contains_phrase(lower, ["solution architect", "solutions architect", "solutions engineer"]):
        return "Brings a practical architecture style that connects stakeholder needs, integration decisions, cloud constraints, and delivery tradeoffs."
    if _contains_phrase(lower, ["ruby on rails", "rails", "stripe", "donor", "giving", "donation"]):
        return "Brings a product engineering style focused on maintainable features, secure customer data, thoughtful UX, small pull requests, and production reliability."
    if _contains_phrase(lower, ["healthcare", "claim", "reimbursement", "clinical", "revenue cycle"]):
        return "Brings a practical engineering style to healthcare workflows, balancing clean APIs, reliable data handling, and readable systems that operations teams can trust."
    if _contains_phrase(lower, ["platform", "devops", "kubernetes", "terraform", "sre", "observability"]):
        return "Brings a practical engineering style to platform work, balancing automation, reliability, observability, and clear delivery habits."
    if _contains_phrase(lower, ["analytics", "dashboard", "bi", "report", "kpi", "data analyst"]):
        return "Brings a practical analytics style that turns messy requirements into clean data workflows, readable dashboards, and decisions teams can act on."
    if _contains_phrase(lower, ["frontend", "react", "component", "ui", "user experience"]):
        return "Brings a practical product mindset to frontend work, connecting clean interfaces with dependable APIs and user workflows."
    if _contains_phrase(lower, ["ai", "ml", "llm", "rag", "machine learning", "model"]):
        return "Brings a practical AI engineering style, connecting model workflows, APIs, data quality, and production reliability."
    if focus:
        return f"Brings a practical engineering style to {focus}, with emphasis on clear implementation and dependable delivery."
    if skills:
        return f"Brings a practical engineering style with emphasis on {skills[0]}, clean implementation, and dependable delivery."
    return "Brings a practical engineering style with emphasis on clear implementation, dependable delivery, and recruiter-readable impact."


def _target_domain_from_job(job_analysis: dict) -> str:
    domain = job_analysis.get("domain", "")
    return "" if domain == "General Technology" else domain


def _summary_focus(job_analysis: dict) -> str:
    duties = job_analysis.get("job_duties") or job_analysis.get("responsibilities") or []
    text = " ".join([
        job_analysis.get("job_title", ""),
        job_analysis.get("domain", ""),
        " ".join(job_analysis.get("keywords", [])),
        " ".join(duties[:4]),
    ]).lower()
    if _contains_phrase(text, ["developer platform", "terraform", "kubernetes", "ci/cd", "observability", "incident", "aws software engineer", "devops"]):
        return "AWS services, infrastructure automation, container delivery, observability, and reliable CI/CD"
    if _contains_phrase(text, ["ruby on rails", "rails", "stripe", "donor", "giving", "donation"]):
        return "Rails and React product features, donation workflows, admin reporting, customer bug fixes, and secure delivery"
    if _contains_phrase(text, ["stakeholder", "requirements", "solution architect", "solutions architect", "integration", "architecture"]):
        return "requirements discovery, system integration, architecture communication, and delivery tradeoffs"
    if _contains_phrase(text, ["dashboard", "kpi", "report", "stakeholder", "insight", "analytics"]):
        return "analytics workflows, KPI reporting, stakeholder visibility, and data-backed decisions"
    if _contains_phrase(text, ["model", "ml", "pipeline", "drift", "monitor", "sagemaker"]):
        return "production ML workflows, model reliability, monitoring, and deployment readiness"
    if _contains_phrase(text, ["api", "backend", "microservice", "distributed"]):
        return "API design, backend workflows, and scalable service delivery"
    if _contains_phrase(text, ["frontend", "react", "user", "component", "interface"]):
        return "user-facing product workflows, reusable frontend systems, and clean API integration"
    if duties:
        return _plain_focus_phrase(duties[0])
    benchmark = job_analysis.get("resume_benchmark", {})
    if benchmark.get("resume_focus"):
        return benchmark["resume_focus"]
    return ""


def _plain_focus_phrase(value: str) -> str:
    clean = _clean_bullet(value).strip(".")
    clean = re.sub(r"(?i)^responsibilities?\s*:\s*", "", clean).strip()
    clean = re.sub(r"(?i)^(build|design|develop|manage|own|lead|collaborate|implement|optimize|automate|support|create|deliver|maintain|monitor|analyze|integrate|scale|architect|partner|improve)\s+", "", clean)
    if not clean:
        return ""
    if clean[:2].isupper() or "/" in clean[:6]:
        return clean
    return clean[0].lower() + clean[1:]


def _contains_phrase(text: str, phrases: list[str]) -> bool:
    lower = text.lower()
    for phrase in phrases:
        pattern = re.escape(phrase.lower()).replace(r"\ ", r"[\s/-]+")
        if re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", lower):
            return True
    return False


def _target_domain(target_title: str) -> str:
    title = target_title.lower()
    if "full stack" in title or "full-stack" in title:
        return "full-stack product engineering"
    if "solution" in title and "architect" in title:
        return "solutions architecture"
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


def _role_family(job_analysis: dict) -> str:
    text = " ".join([
        job_analysis.get("job_title", ""),
        job_analysis.get("domain", ""),
        " ".join(job_analysis.get("keywords", [])),
        " ".join(job_analysis.get("job_duties", []) or job_analysis.get("responsibilities", [])),
    ]).lower()
    has_rails = _contains_phrase(text, ["ruby on rails", "rails"])
    giving_rails = _contains_phrase(text, ["stripe", "donor", "giving", "donation"]) or (
        has_rails and _contains_phrase(text, ["react"])
    )
    if giving_rails:
        return "fullstack_rails"
    if _contains_phrase(text, ["solutions architect", "solution architect", "solutions engineer", "pre-sales", "presales"]):
        return "solutions_architecture"
    if _contains_phrase(text, ["ai engineer", "genai", "generative ai", "llm", "rag", "machine learning"]):
        return "ai_engineering"
    if _contains_phrase(text, ["platform engineer", "sre", "site reliability", "devops", "kubernetes", "terraform"]):
        return "platform_engineering"
    benchmark = job_analysis.get("resume_benchmark", {}).get("key", "")
    if has_rails:
        return "rails_backend"
    if benchmark == "dotnet_cloud":
        return "dotnet_engineering"
    if benchmark == "java_backend" or _contains_phrase(text, ["java backend", "spring boot", "j2ee"]):
        return "java_backend"
    if benchmark == "data_etl" or _contains_phrase(text, ["data engineer", "etl", "data warehouse", "airflow"]):
        return "data_engineering"
    target_title = job_analysis.get("job_title", "").lower()
    if _contains_phrase(target_title, ["backend", "back-end", "go developer", "golang developer"]) or _contains_phrase(text, ["node.js backend", "node backend", "golang"]):
        return "backend_engineering"
    if benchmark == "web_frontend" or _contains_phrase(text, ["frontend", "front end", "react", "product engineer", "ui", "component", "vue", "next.js", "nextjs"]):
        return "product_frontend"
    if benchmark == "business_analysis" or _contains_phrase(text, ["business analyst", "user stories", "requirements gathering"]):
        return "business_analysis"
    if benchmark == "quality_assurance" or _contains_phrase(text, ["quality assurance", "qa automation", "test automation", "selenium", "cypress"]):
        return "quality_assurance"
    if benchmark == "business_intelligence" or _contains_phrase(text, ["data analyst", "business intelligence", "analytics", "dashboard", "kpi"]):
        return "analytics"
    return "software_engineering"


def _role_priority_terms(job_analysis: dict) -> list[str]:
    family = _role_family(job_analysis)
    priorities = {
        "fullstack_rails": ["Ruby on Rails", "React", "Stripe APIs", "PostgreSQL", "TypeScript", "JavaScript", "REST", "APIs", "AWS", "GitHub", "Datadog"],
        "rails_backend": ["Ruby on Rails", "Ruby", "REST", "APIs", "PostgreSQL", "SQL", "AWS", "Docker", "Git"],
        "solutions_architecture": ["Stakeholder Management", "Requirements Gathering", "System Integration", "Architecture", "Cloud", "AWS", "Agile", "APIs", "Communication", "Leadership"],
        "ai_engineering": ["RAG", "LLM", "Generative AI", "Vector Embeddings", "AI Agents", "LangChain", "OpenAI APIs", "FastAPI", "Python", "PostgreSQL"],
        "platform_engineering": ["Kubernetes", "Docker", "Terraform", "CI/CD", "AWS", "GitHub Actions", "Prometheus", "Grafana", "OpenTelemetry", "Linux"],
        "dotnet_engineering": [".NET", "C#", "SQL", "REST", "APIs", "AWS", "Docker", "CI/CD", "Git"],
        "java_backend": ["Java", "Spring Boot", "REST", "APIs", "Microservices", "PostgreSQL", "Docker", "AWS", "Git"],
        "data_engineering": ["Python", "SQL", "PostgreSQL", "Snowflake", "ETL", "AWS", "Docker", "Data Analysis"],
        "backend_engineering": ["Go", "Python", "Node", "TypeScript", "JavaScript", "REST", "APIs", "PostgreSQL", "SQL", "AWS", "Docker", "Git"],
        "product_frontend": ["React", "TypeScript", "JavaScript", "APIs", "React Query", "Redux", "HTML5", "CSS3", "Figma", "Accessibility"],
        "analytics": ["SQL", "PostgreSQL", "Power BI", "Tableau", "Excel", "Python", "Data Analysis", "ETL", "Snowflake", "KPI Reporting"],
        "business_analysis": ["SQL", "Agile", "Requirements Gathering", "Process Mapping", "Documentation", "APIs"],
        "quality_assurance": ["Selenium", "Cypress", "Playwright", "API Testing", "CI/CD", "Git", "Postman"],
        "software_engineering": ["Python", "Java", "TypeScript", "FastAPI", "Spring Boot", "APIs", "Microservices", "PostgreSQL", "AWS", "Docker"],
    }
    return priorities.get(family, priorities["software_engineering"])


def _rank_role_skills(user_skills: list[str], jd_keywords: list[str], job_analysis: dict) -> list[str]:
    priority = _role_priority_terms(job_analysis)
    ranked_source = _unique(priority + jd_keywords + user_skills)
    supported = [skill for skill in ranked_source if _valid_skill(skill)]
    return _rank_user_skills(supported, jd_keywords)


def _credible_target_title(resume: dict, job_analysis: dict) -> str:
    title = job_analysis.get("job_title", "")
    if not title:
        return ""
    lower = title.lower()
    if "solution" in lower and "architect" in lower and not _has_architect_evidence(resume):
        if _years_experience(resume) < 5:
            return "Software Engineer - Solutions Architecture"
        return "Solutions Engineer"
    if re.search(r"\b(principal|staff|lead)\b", lower) and not _has_leadership_evidence(resume):
        return re.sub(r"(?i)\b(principal|staff|lead)\s+", "Senior ", title).strip()
    return title


def _has_architect_evidence(resume: dict) -> bool:
    pieces = []
    for job in resume.get("experience", []):
        pieces.extend([job.get("title", ""), job.get("company", "")])
        pieces.extend(job.get("bullets", []))
    for project in resume.get("projects", []):
        pieces.append(project.get("name", ""))
        pieces.extend(project.get("bullets", []))
    text = " ".join(str(piece) for piece in pieces if piece).lower()
    return _contains_phrase(text, ["architecture", "stakeholder", "integration", "requirements", "roadmap", "governance", "solution design"])


def _has_leadership_evidence(resume: dict) -> bool:
    pieces = []
    for job in resume.get("experience", []):
        pieces.extend([job.get("title", ""), job.get("company", "")])
        pieces.extend(job.get("bullets", []))
    text = " ".join(str(piece) for piece in pieces if piece).lower()
    return _contains_phrase(text, ["led", "mentored", "owned", "architecture", "roadmap", "stakeholder", "cross-functional"])


def _rewrite_bullets(
    bullets: list[str],
    skills: list[str],
    target_keywords: Optional[list[str]] = None,
    job_analysis: Optional[dict] = None,
) -> list[str]:
    verbs = ["Architected", "Engineered", "Designed", "Optimized", "Automated", "Integrated", "Delivered", "Scaled", "Orchestrated", "Streamlined"]
    rewritten = []
    target_keywords = target_keywords or []
    aligned_skills = _rank_user_skills(_dedupe_related_keywords(skills + target_keywords), target_keywords)
    for index, bullet in enumerate(bullets):
        rewritten.append(_rewrite_bullet(bullet, aligned_skills, verbs[index % len(verbs)], job_analysis, index))
    return _enforce_verb_variety(rewritten)


def _rewrite_bullet(
    bullet: str,
    skills: list[str],
    fallback_verb: str,
    job_analysis: Optional[dict] = None,
    index: int = 0,
) -> str:
    clean = _upgrade_action_opening(_normalize_weak_opening(_remove_ai_tone(bullet.rstrip("."))))
    tech = next((item for item in skills if _valid_skill(item) and item.lower() in clean.lower()), None)
    context = _job_alignment_context(job_analysis or {}, index)
    if len(clean.split()) < 6:
        tool_text = f" with {tech}" if tech and _keyword_key(tech) not in clean.lower() else ""
        impact = _role_impact_phrase(job_analysis or {}, index)
        if _starts_with_action(clean):
            clean = f"{_capitalize(clean)}{tool_text} for {context}, improving {impact}"
        else:
            clean = f"{fallback_verb} {clean.lower()}{tool_text} for {context}, improving {impact}"
    elif not _starts_with_action(clean):
        clean = f"{fallback_verb} {clean[0].lower() + clean[1:]}"
    clean = _attach_job_context(clean, job_analysis or {}, index)
    return _clean_generated_sentence(_restore_acronyms(clean)) + "."


def _job_alignment_context(job_analysis: dict, index: int = 0) -> str:
    duties = _translated_role_contexts(job_analysis) or _duty_fragments(job_analysis)
    focus = _summary_focus(job_analysis)
    if duties:
        duty = _plain_focus_phrase(duties[index % len(duties)]).strip(".")
        if duty:
            return duty
    if focus:
        return focus
    title = job_analysis.get("job_title") or "role"
    return f"{title.lower()} delivery, reliability, and business workflows"


def _role_impact_phrase(job_analysis: dict, index: int = 0) -> str:
    family = _role_family(job_analysis)
    impact = {
        "fullstack_rails": ["feature maintainability", "donor workflow clarity", "admin reporting quality", "secure delivery"],
        "rails_backend": ["service reliability", "API clarity", "data integrity", "production maintainability"],
        "solutions_architecture": ["implementation clarity", "technical handoff quality", "integration planning", "delivery tradeoff visibility"],
        "ai_engineering": ["retrieval quality", "automation reliability", "model workflow visibility", "production readiness"],
        "platform_engineering": ["release reliability", "operational visibility", "deployment consistency", "incident response"],
        "dotnet_engineering": ["service reliability", "secure delivery", "database integrity", "release confidence"],
        "java_backend": ["service reliability", "API maintainability", "integration quality", "deployment readiness"],
        "data_engineering": ["pipeline reliability", "data quality", "processing visibility", "reporting readiness"],
        "backend_engineering": ["service reliability", "API maintainability", "production support", "secure delivery"],
        "product_frontend": ["user flow clarity", "interface reliability", "product delivery speed", "API-backed usability"],
        "analytics": ["reporting accuracy", "decision visibility", "data quality", "stakeholder confidence"],
        "business_analysis": ["requirements clarity", "delivery alignment", "process visibility", "acceptance quality"],
        "quality_assurance": ["release confidence", "defect prevention", "test coverage", "regression visibility"],
        "software_engineering": ["service reliability", "delivery quality", "operational visibility", "maintainability"],
    }
    options = impact.get(family, impact["software_engineering"])
    return options[index % len(options)]


def _translated_role_contexts(job_analysis: dict) -> list[str]:
    text = " ".join([
        job_analysis.get("job_title", ""),
        job_analysis.get("domain", ""),
        " ".join(job_analysis.get("job_duties", []) or job_analysis.get("responsibilities", [])),
        " ".join(job_analysis.get("keywords", [])),
    ]).lower()
    contexts: list[str] = []
    if _contains_phrase(text, ["ruby on rails", "rails", "stripe", "donor", "giving", "donation"]):
        contexts.extend(["Rails and React product features", "donor experience workflows", "admin reporting", "customer bug fixes", "secure payment workflows", "pull request review"])
    if _contains_phrase(text, ["solutions architect", "solution architect", "stakeholder", "requirements", "integration"]):
        contexts.extend(["solution discovery workflows", "system integration planning", "technical implementation plans", "cross-functional delivery planning"])
    if _contains_phrase(text, ["healthcare", "claim", "claims", "reimbursement", "revenue cycle"]):
        contexts.extend(["healthcare operations workflows", "claims review visibility", "reimbursement process quality", "traceable operational decisions"])
    if _contains_phrase(text, ["platform", "sre", "terraform", "kubernetes", "observability", "ci/cd"]):
        contexts.extend(["developer platform services", "release automation", "Kubernetes workload reliability", "observability and incident response"])
    if _contains_phrase(text, ["analytics", "dashboard", "bi", "reporting", "kpi"]):
        contexts.extend(["KPI reporting workflows", "data quality review", "operational dashboard visibility", "analytics decision support"])
    if _contains_phrase(text, ["ai", "ml", "llm", "rag", "model"]):
        contexts.extend(["AI workflow delivery", "retrieval quality review", "model-backed automation", "production AI operations"])
    if _contains_phrase(text, ["frontend", "react", "component", "ui"]):
        contexts.extend(["user-facing product workflows", "component reuse", "API-backed interface behavior", "frontend delivery quality"])
    return _unique(contexts)[:8]


def _duty_fragments(job_analysis: dict) -> list[str]:
    source = job_analysis.get("job_duties") or job_analysis.get("responsibilities") or []
    fragments: list[str] = []
    for item in source:
        pieces = re.split(r";|\n|(?<=[.])\s+|,\s+(?=(build|design|develop|manage|own|lead|collaborate|implement|optimize|automate|support|create|deliver|maintain|monitor|analyze|integrate|scale|architect|partner|improve)\b)", item, flags=re.I)
        for piece in pieces:
            if not piece or re.fullmatch(r"(?i)(build|design|develop|manage|own|lead|collaborate|implement|optimize|automate|support|create|deliver|maintain|monitor|analyze|integrate|scale|architect|partner|improve)", piece.strip()):
                continue
            clean = re.sub(r"(?i)^responsibilities?\s*:\s*", "", _clean_bullet(piece).strip(" .")).strip()
            if re.match(r"(?i)^(required|preferred|minimum|basic)\s+(skills|qualifications|requirements)\s*:", clean):
                continue
            if re.search(r"(?i)\b(engineer|developer|analyst|architect)\b", clean) and len(clean.split()) <= 4:
                continue
            if 3 <= len(clean.split()) <= 18:
                fragments.append(_restore_acronyms(clean))
    if fragments:
        return _unique(fragments)[:8]
    lower = " ".join(source + [job_analysis.get("job_title", ""), job_analysis.get("domain", "")]).lower()
    role_contexts = []
    if _contains_phrase(lower, ["platform", "sre", "terraform", "kubernetes", "observability", "ci/cd"]):
        role_contexts.extend(["developer platform services", "CI/CD automation", "Kubernetes workload reliability", "observability and incident response"])
    if _contains_phrase(lower, ["analytics", "dashboard", "bi", "reporting", "kpi"]):
        role_contexts.extend(["KPI reporting workflows", "data quality review", "operational dashboard visibility", "analytics decision support"])
    if _contains_phrase(lower, ["ai", "ml", "llm", "rag", "model"]):
        role_contexts.extend(["AI workflow delivery", "model reliability review", "retrieval quality", "production AI operations"])
    if _contains_phrase(lower, ["frontend", "react", "component", "ui"]):
        role_contexts.extend(["user-facing product workflows", "component reuse", "API-backed interface behavior", "frontend delivery quality"])
    if _contains_phrase(lower, ["healthcare", "claim", "reimbursement", "revenue cycle"]):
        role_contexts.extend(["healthcare operations workflows", "claims review visibility", "reimbursement process quality", "traceable operational decisions"])
    return _unique(role_contexts)[:8]


def _attach_job_context(text: str, job_analysis: dict, index: int = 0) -> str:
    if not job_analysis or len(text.split()) > 24:
        return text
    context = _job_alignment_context(job_analysis, index)
    lower = text.lower()
    if context and not any(word in lower for word in context.lower().split()[:3]):
        impact = _role_impact_phrase(job_analysis, index)
        endings = [
            f" for {context}, improving {impact}",
            f" supporting {context} and clearer {impact}",
            f" aligned with {context} and practical {impact}",
        ]
        return text.rstrip(".") + endings[index % len(endings)]
    return text


def _enforce_verb_variety(bullets: list[str]) -> list[str]:
    replacements = ["Architected", "Engineered", "Designed", "Optimized", "Automated", "Integrated", "Delivered", "Scaled", "Orchestrated", "Streamlined"]
    counts: dict[str, int] = {}
    result = []
    for bullet in bullets:
        match = re.match(r"^([A-Za-z]+)\b", bullet)
        verb = match.group(1) if match else ""
        if verb:
            counts[verb.lower()] = counts.get(verb.lower(), 0) + 1
            if counts[verb.lower()] > 2:
                replacement = next((item for item in replacements if counts.get(item.lower(), 0) < 2), "Delivered")
                bullet = re.sub(r"^[A-Za-z]+\b", replacement, bullet, count=1)
                counts[replacement.lower()] = counts.get(replacement.lower(), 0) + 1
        result.append(bullet)
    return result


def _clean_generated_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?i)\bAutomated automation\b", "Automated operational", text)
    text = re.sub(r"(?i)\bBuilt APIs\b", "Architected APIs", text)
    text = re.sub(r"\b(using|with emphasis on)\s+([A-Za-z]+,\s*){2,}[A-Za-z]+$", "", text).strip()
    text = re.sub(r"\b(Associate|Stack|Product|Skills|Build|System)\b,?\s*", "", text).strip()
    text = _trim_technology_stuffing(text)
    return text.rstrip(" ,")


def _upgrade_action_opening(text: str) -> str:
    rules = [
        (r"(?i)^built\s+(automation|automated|pipeline|pipelines)", "Automated"),
        (r"(?i)^built\s+(scalable|distributed|backend|api-driven|healthcare)", "Engineered"),
        (r"(?i)^built\s+(responsive|frontend|product|user)", "Designed"),
        (r"(?i)^developed\s+(scalable|distributed|backend|api-driven|healthcare)", "Engineered"),
        (r"(?i)^implemented\s+(monitoring|observability|integration|integrations)", "Integrated"),
        (r"(?i)^improved\s+", "Optimized "),
    ]
    for pattern, replacement in rules:
        if re.search(pattern, text):
            return re.sub(r"^[A-Za-z]+\b", replacement, text, count=1)
    return text


def _trim_technology_stuffing(text: str) -> str:
    match = re.search(r"\busing\s+([^.;]+)", text, re.I)
    if not match:
        return text
    techs = [item.strip() for item in match.group(1).split(",") if item.strip()]
    if len(techs) <= 3:
        return text
    keep = ", ".join(techs[:3])
    return text[:match.start(1)] + keep + text[match.end(1):]


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


def _experience_label(resume: dict) -> str:
    summary = resume.get("summary", "")
    explicit = re.search(r"\b(\d+\+?\s*years?)\b", summary, re.I)
    if explicit:
        value = re.search(r"\d+\+?", explicit.group(1))
        return f"{value.group(0)} years" if value else explicit.group(1)
    years = _years_experience(resume)
    return f"{years}+ years" if years else ""


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
        "ml": "ML",
        "qa": "QA",
        "aws": "AWS",
        "sre": "SRE",
        "sql": "SQL",
        ".net": ".NET",
        "api": "API",
        "devops": "DevOps",
        "frontend": "Frontend",
        "backend": "Backend",
        "full": "Full",
        "stack": "Stack",
    }
    clean = re.sub(r"[^A-Za-z0-9/ &.+#-]", " ", title)
    words = clean.lower().split()
    return " ".join(replacements.get(word, word.capitalize()) for word in words).strip()


def _mark_generated_targeted_resume(resume: dict, job_description: str) -> None:
    analysis = analyze_job_description(job_description)
    resume["optimization_status"] = "generated_targeted"
    resume.pop("score_target", None)
    if analysis.get("job_title") and not resume.get("target_title"):
        resume["target_title"] = analysis["job_title"]


def _starts_with_action(text: str) -> bool:
    return bool(re.match(r"(?i)^(architected|engineered|built|created|developed|improved|designed|implemented|optimized|integrated|orchestrated|streamlined|scaled|analyzed|managed|automated|delivered|supported|owned|led|reduced|organized|modeled|containerized|documented|exposed)", text))


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _restore_acronyms(text: str) -> str:
    replacements = {
        "apis": "APIs",
        "api": "API",
        "sql": "SQL",
        "aws": "AWS",
        "ui": "UI",
        "etl": "ETL",
        "llm": "LLM",
        "rag": "RAG",
        "ai": "AI",
        "ci/cd": "CI/CD",
        "kubernetes": "Kubernetes",
        "docker": "Docker",
        "fastapi": "FastAPI",
        "postgresql": "PostgreSQL",
        "terraform": "Terraform",
        "rails": "Rails",
    }
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


def _suggest_projects_for_gap(jd_keywords: list[str], resume: dict, job_analysis: Optional[dict] = None) -> list[dict]:
    job_analysis = job_analysis or {}
    resume_text = _resume_keyword_text(resume)
    missing = [keyword for keyword in jd_keywords if _keyword_key(keyword) not in resume_text]
    title = job_analysis.get("job_title", "")
    duties = job_analysis.get("job_duties") or job_analysis.get("responsibilities") or []
    domain = job_analysis.get("domain", "")
    text = " ".join(missing + jd_keywords + [title, domain] + duties).lower()
    suggestions = []
    if _contains_phrase(text, ["ruby on rails", "rails", "stripe", "donor", "giving", "donation"]):
        suggestions.append({
            "name": "Stripe-Powered Donor Giving Experience",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"ruby on rails", "rails", "react", "stripe", "stripe apis", "postgresql", "aws"}],
            "bullets": [
                "Built a donor-facing giving workflow with Rails APIs, React forms, validation states, and secure payment handoff patterns.",
                "Modeled donation records, admin review states, and reporting views so support and finance teams could trace giving activity."
            ]
        })
        suggestions.append({
            "name": "Donation Migration & Admin Reporting Tool",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"ruby on rails", "rails", "react", "postgresql", "datadog", "aws performance insights"}],
            "bullets": [
                "Designed a migration review workflow for imported donor records, exception handling, and admin-side reporting.",
                "Added production-readiness notes for error monitoring, performance review, and small well-tested pull requests."
            ]
        })
    if _contains_phrase(text, ["solutions architect", "solution architect", "solutions engineer", "stakeholder", "requirements", "integration"]):
        suggestions.append({
            "name": "Enterprise Integration Readiness Platform",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"aws", "apis", "rest", "sql", "postgresql", "docker", "openapi", "swagger"}],
            "bullets": [
                "Designed a solution assessment workflow that connects stakeholder requirements, API dependencies, and implementation risks into a clear delivery plan.",
                "Modeled integration touchpoints and cloud constraints so engineering teams could compare tradeoffs before build decisions.",
                "Created architecture notes, API documentation, and rollout assumptions to improve handoff quality across technical and business teams."
            ]
        })
    if _contains_phrase(text, ["healthcare", "claim", "claims", "reimbursement", "clinical", "revenue cycle", "payer"]):
        suggestions.append({
            "name": "AI-Driven Revenue Cycle Optimization Platform",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"python", "fastapi", "postgresql", "sql", "aws", "llm", "rag", "apis"}],
            "bullets": [
                "Designed reimbursement workflow services that organize claim records, validation logic, and exception review into a clear API-driven process.",
                "Built document and data handling paths that support cleaner operational review, traceable decisions, and healthcare workflow visibility.",
                "Mapped job-specific requirements into resume-ready architecture notes covering APIs, data quality, automation, and reliability."
            ]
        })
    if _contains_phrase(text, ["platform", "sre", "terraform", "kubernetes", "observability", "incident", "infrastructure"]):
        suggestions.append({
            "name": "Cloud-Native Developer Platform Automation",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"aws", "docker", "kubernetes", "terraform", "ci/cd", "github actions", "prometheus", "grafana"}],
            "bullets": [
                "Engineered deployment workflows with environment configuration, health checks, and rollback documentation for reliable service releases.",
                "Integrated observability checks and release notes to make platform behavior easier to troubleshoot and support.",
                "Organized infrastructure and CI/CD requirements into a clean project narrative aligned with developer platform responsibilities."
            ]
        })
    if _contains_phrase(text, ["machine learning", "ml", "model", "drift", "sagemaker", "feature", "training pipeline"]):
        suggestions.append({
            "name": "Production ML Monitoring & Retrieval Intelligence System",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"python", "mlflow", "sagemaker", "aws", "postgresql", "prometheus", "grafana", "rag", "llm"}],
            "bullets": [
                "Designed model monitoring workflows for prediction quality, drift review, and production readiness across ML-backed services.",
                "Built API-accessible evaluation outputs so engineering teams can inspect model behavior and operational risk.",
                "Documented reliability, data quality, and deployment considerations that match production ML engineering expectations."
            ]
        })
    if _contains_phrase(text, ["business intelligence", "bi", "dashboard", "analytics", "kpi", "reporting", "stakeholder"]):
        suggestions.append({
            "name": "Revenue Operations Analytics Intelligence Platform",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"sql", "postgresql", "python", "tableau", "power bi", "excel", "snowflake"}],
            "bullets": [
                "Created KPI datasets, SQL queries, and dashboard views that translate operational requirements into clear reporting outputs.",
                "Analyzed data quality issues and documented business assumptions so stakeholders can trust the reporting flow.",
                "Organized analytics deliverables around role-specific needs including metrics definitions, trends, and decision support."
            ]
        })
    if any(word in text for word in ["react", "typescript", "frontend"]):
        suggestions.append({
            "name": "AI-Assisted Product Workflow Dashboard",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"react", "typescript", "javascript", "api", "apis"}],
            "bullets": [
                "Built responsive product workflows with reusable React components, API integration, filtering, loading states, and error handling.",
                "Documented component architecture, state management, and accessibility decisions for user-facing workflows."
            ]
        })
    if any(word in text for word in ["aws", "docker", "kubernetes", "cloud", "ci/cd"]):
        suggestions.append({
            "name": "Enterprise CI/CD Deployment Orchestrator",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"aws", "docker", "kubernetes", "ci/cd"}],
            "bullets": [
                "Containerize backend services and deploy them with environment configuration, health checks, and rollback documentation.",
                "Add CI/CD workflows and monitoring notes to demonstrate production-ready release operations."
            ]
        })
    if any(word in text for word in ["llm", "rag", "ai", "machine learning"]):
        suggestions.append({
            "name": "Multimodal Healthcare Document Intelligence Engine",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"llm", "rag", "python", "fastapi", "postgresql"}],
            "bullets": [
                "Built a document intelligence workflow with chunking, retrieval, prompt templates, and response evaluation for operational review.",
                "Exposed retrieval workflows through APIs and documented quality, latency, and failure handling for production review."
            ]
        })
    if any(word in text for word in ["sql", "postgresql", "data", "analytics", "tableau", "power bi", "forecasting"]):
        suggestions.append({
            "name": "Operational Analytics & Decision Intelligence Platform",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"sql", "postgresql", "python", "tableau", "power bi", "excel"}],
            "bullets": [
                "Create cleaned datasets, KPI queries, and dashboard views that answer operational business questions.",
                "Document assumptions, data quality checks, and recommendations to show analytical judgment and decision support."
            ]
        })
    if any(word in text for word in ["java", "spring boot", "microservices", "kafka"]):
        suggestions.append({
            "name": "Enterprise Event-Driven Claims Processing Service",
            "technologies": [keyword for keyword in jd_keywords if keyword.lower() in {"java", "spring boot", "postgresql", "kafka", "docker"}],
            "bullets": [
                "Build a REST service with validation, persistence, event publishing, tests, and API documentation.",
                "Show service boundaries, failure handling, and database design decisions for scalable claims-processing workflows."
            ]
        })
    return suggestions[:5]


def _add_relevant_projects(existing: list[dict], suggestions: list[dict]) -> list[dict]:
    projects = [project for project in existing or [] if project.get("name") or project.get("bullets")]
    seen = {_keyword_key(project.get("name", "")) for project in projects}
    for suggestion in suggestions:
        key = _keyword_key(suggestion.get("name", ""))
        if key and key not in seen:
            projects.append(_resume_ready_project(suggestion))
            seen.add(key)
        if len(projects) >= 5:
            break
    return projects


def _resume_ready_project(project: dict) -> dict:
    return {
        "name": project.get("name", "Relevant Technical Project"),
        "technologies": project.get("technologies", []),
        "bullets": _enforce_verb_variety([_project_bullet_to_resume_style(bullet) for bullet in project.get("bullets", [])[:3]]),
    }


def _project_bullet_to_resume_style(bullet: str) -> str:
    text = bullet.strip().rstrip(".")
    text = re.sub(r"(?i)\band deploy them\b", "and deployed them", text)
    replacements = {
        r"(?i)^build\s+": "Built ",
        r"(?i)^create\s+": "Created ",
        r"(?i)^containerize\s+": "Containerized ",
        r"(?i)^add\s+": "Added ",
        r"(?i)^document\s+": "Documented ",
        r"(?i)^expose\s+": "Exposed ",
        r"(?i)^show\s+": "Showed ",
        r"(?i)^model\s+": "Modeled ",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    if not _starts_with_action(text):
        text = f"Engineered {text[0].lower() + text[1:]}" if text else "Engineered a role-relevant technical project"
    return _clean_generated_sentence(_restore_acronyms(text)) + "."


def _humanize_resume(resume: dict) -> None:
    all_bullets: list[tuple[dict, int, str]] = []
    for job in resume.get("experience", []):
        cleaned = []
        for bullet in job.get("bullets", []):
            cleaned.append(_remove_ai_tone(_clean_generated_sentence(_upgrade_action_opening(bullet.rstrip(".")))) + ".")
        job["bullets"] = cleaned
        all_bullets.extend((job, index, bullet) for index, bullet in enumerate(cleaned))
    for project in resume.get("projects", []):
        project["name"] = _brand_project_name(project.get("name", "Technical Project"))
        project["technologies"] = _dedupe_related_keywords([tech for tech in project.get("technologies", []) if _valid_skill(tech)])[:8]
        cleaned = [_remove_ai_tone(_clean_generated_sentence(_upgrade_action_opening(bullet.rstrip(".")))) + "." for bullet in project.get("bullets", [])]
        project["bullets"] = cleaned
        all_bullets.extend((project, index, bullet) for index, bullet in enumerate(cleaned))
    varied = _enforce_verb_variety([bullet for _, _, bullet in all_bullets])
    for (owner, index, _), bullet in zip(all_bullets, varied):
        owner["bullets"][index] = bullet
    resume["skills"] = _categorize_skills(_all_skills(resume), resume.get("target_keywords", []))


def _recruiter_realism_pass(resume: dict, job_analysis: dict) -> None:
    bullet_index = 0
    for job in resume.get("experience", []):
        cleaned = []
        for bullet in job.get("bullets", []):
            cleaned.append(_recruiter_safe_sentence(bullet, job_analysis, bullet_index))
            bullet_index += 1
        job["bullets"] = cleaned
    for project in resume.get("projects", []):
        project["name"] = _business_project_name(project.get("name", ""), job_analysis)
        cleaned = []
        for bullet in project.get("bullets", []):
            cleaned.append(_recruiter_safe_sentence(bullet, job_analysis, bullet_index))
            bullet_index += 1
        project["bullets"] = cleaned
    resume["projects"] = _dedupe_projects_by_name(resume.get("projects", []))
    _reduce_project_redundancy(resume, job_analysis)
    _remove_repetitive_sentence_shapes(resume, job_analysis)


def _recruiter_safe_sentence(text: str, job_analysis: dict, index: int) -> str:
    clean = _remove_ai_tone(_clean_generated_sentence(text.rstrip(".")))
    clean = re.sub(r"(?i)^built app\b", "Built role-aligned workflow application", clean)
    clean = re.sub(r"(?i)^(architected|engineered|designed|optimized|automated|delivered)\s+app\b", lambda m: f"{m.group(1).capitalize()} role-aligned workflow application", clean)
    clean = re.sub(r"(?i)^built dashboards\b", "Built operational dashboards", clean)
    clean = re.sub(r"(?i)^built deployments\b", "Managed deployment workflows", clean)
    clean = re.sub(r"(?i)^(Architected|Engineered|Designed|Optimized|Automated|Delivered)\s+added\s+", "Added ", clean)
    clean = _fix_action_collisions(clean)
    clean = re.sub(r"(?i)\busing\s+([A-Za-z0-9+#./ -]+,\s*){2,}[A-Za-z0-9+#./ -]+", "with role-relevant tooling", clean)
    clean = re.sub(r"(?i)\b(millions|thousands|40%|50%|100%)\b", "high-volume" if index % 2 else "measurable", clean)
    copied = _copied_jd_fragments(clean, job_analysis)
    for fragment in copied:
        clean = clean.replace(fragment, _job_alignment_context(job_analysis, index))
    if len(clean.split()) < 8:
        clean = f"{clean} for {_job_alignment_context(job_analysis, index)}, improving {_role_impact_phrase(job_analysis, index)}"
    clean = _add_impact_number(clean, job_analysis, index)
    return _restore_acronyms(clean).rstrip(" .") + "."


def _fix_action_collisions(text: str) -> str:
    text = re.sub(r"(?i)^(Architected|Engineered|Designed|Optimized|Automated|Integrated|Delivered|Scaled|Orchestrated|Streamlined)\s+used\s+", r"\1 ", text)
    text = re.sub(r"(?i)^(Architected|Engineered|Designed|Optimized|Automated|Integrated|Delivered|Scaled|Orchestrated|Streamlined)\s+(collaborated|partnered|worked)\b", lambda m: m.group(2).capitalize(), text)
    text = re.sub(r"(?i)^(Architected|Engineered|Designed|Optimized|Automated|Integrated|Delivered|Scaled|Orchestrated|Streamlined)\s+(managed|owned|supported|led)\b", lambda m: m.group(2).capitalize(), text)
    text = re.sub(r"(?i)^(Architected|Engineered|Designed|Optimized|Automated|Integrated|Delivered|Scaled|Orchestrated|Streamlined)\s+(translated|shipped|strengthened|diagnosed|reviewed|investigated|improved|built)\b", lambda m: m.group(2).capitalize(), text)
    return text


def _add_impact_number(text: str, job_analysis: dict, index: int) -> str:
    if re.search(r"\b\d+[%x]?\b|\$|hours?|minutes?|seconds?|days?|weeks?", text, re.I):
        return text
    base = text.rstrip(" .")
    if index % 4 == 2:
        return f"{base}; {_concrete_scale_phrase(job_analysis, index)}"
    if _planning_or_collaboration_bullet(base):
        return f"{base}; {_non_numeric_outcome_phrase(job_analysis, index)}"
    if index % 4 == 0:
        return f"{base}; {_impact_outcome_phrase(job_analysis, index)}"
    return f"{base}; {_non_numeric_outcome_phrase(job_analysis, index)}"


def _planning_or_collaboration_bullet(text: str) -> bool:
    return bool(re.search(r"(?i)\b(collaborated|partnered|coordinated|aligned|planned|planning|requirements|discovery|handoff|communication|tradeoff|stakeholder)\b", text))


def _impact_outcome_phrase(job_analysis: dict, index: int) -> str:
    family = _role_family(job_analysis)
    metrics = {
        "fullstack_rails": [
            "reduced donor workflow friction by 25%",
            "improved admin reporting review speed by 30%",
            "cut customer bug investigation time by 20%",
            "improved feature delivery consistency by 25%",
        ],
        "solutions_architecture": [
            "reduced implementation ambiguity by 30%",
            "shortened technical discovery cycles by 25%",
            "reduced integration rework by 20%",
            "cut release-planning rework by 25%",
        ],
        "ai_engineering": [
            "reduced manual review effort by 35%",
            "improved retrieval review speed by 30%",
            "cut repetitive analysis time by 40%",
            "increased workflow traceability by 25%",
        ],
        "platform_engineering": [
            "reduced deployment friction by 30%",
            "improved release consistency by 35%",
            "cut troubleshooting time by 25%",
            "increased operational visibility by 40%",
        ],
        "product_frontend": [
            "reduced user workflow friction by 25%",
            "improved task completion speed by 30%",
            "increased interface consistency by 35%",
            "cut API handoff issues by 20%",
        ],
        "analytics": [
            "reduced manual reporting effort by 40%",
            "improved data review speed by 30%",
            "increased KPI visibility by 35%",
            "cut recurring analysis time by 25%",
        ],
        "software_engineering": [
            "reduced manual support effort by 30%",
            "improved service reliability by 25%",
            "cut operational review time by 35%",
            "increased delivery visibility by 30%",
        ],
    }
    options = metrics.get(family, metrics["software_engineering"])
    return options[index % len(options)]


def _concrete_scale_phrase(job_analysis: dict, index: int) -> str:
    family = _role_family(job_analysis)
    scales = {
        "fullstack_rails": [
            "structured 8+ Rails API and React UI flows for giving workflows",
            "organized 10+ admin reporting states for operational review",
            "documented 6+ payment and data validation paths for release readiness",
        ],
        "solutions_architecture": [
            "mapped 10+ integration touchpoints across API and cloud workflows",
            "organized 8+ implementation assumptions into clear delivery notes",
            "documented 12+ API and data-flow considerations for release planning",
        ],
        "ai_engineering": [
            "structured 1,000+ document chunks for retrieval review",
            "evaluated 20+ prompt and retrieval scenarios for quality checks",
            "organized 5+ AI workflow stages for traceable review",
        ],
        "platform_engineering": [
            "tracked 50+ deployment and observability signals across services",
            "supported 10+ release workflow checks across cloud environments",
            "organized 6+ service health checks for operational review",
        ],
        "product_frontend": [
            "supported 10+ reusable UI workflows across API-backed screens",
            "standardized 15+ component states for repeated product flows",
            "organized 8+ user workflow paths for cleaner delivery review",
        ],
        "analytics": [
            "modeled 12+ KPI definitions for recurring operational reporting",
            "organized 20+ SQL checks for data quality review",
            "supported 5+ dashboard views for recurring business decisions",
        ],
        "software_engineering": [
            "designed 8+ API workflows for operational use cases",
            "supported 10+ backend validation paths across service workflows",
            "organized 6+ reliability checks for deployment review",
        ],
    }
    options = scales.get(family, scales["software_engineering"])
    return options[index % len(options)]


def _non_numeric_outcome_phrase(job_analysis: dict, index: int) -> str:
    family = _role_family(job_analysis)
    outcomes = {
        "fullstack_rails": ["improved donor experience clarity", "made admin reporting easier to review", "strengthened secure customer-data handling", "reduced ambiguity during pull request review"],
        "solutions_architecture": ["accelerated requirement validation cycles", "reduced integration friction during release planning", "improved coordination between engineering and operations"],
        "ai_engineering": ["streamlined AI workflow validation and exception handling", "improved model-output review for operational teams", "strengthened traceability across AI-assisted decisions"],
        "platform_engineering": ["improved deployment reliability across cloud environments", "centralized monitoring signals for faster debugging", "strengthened release coordination across services"],
        "product_frontend": ["improved user workflow clarity across API-backed screens", "reduced friction in repeated product tasks", "strengthened component reuse across delivery work"],
        "analytics": ["improved reporting visibility for recurring decisions", "streamlined operational data review", "reduced ambiguity in KPI definitions"],
        "software_engineering": ["improved engineering coordination and service ownership", "streamlined operational validation and exception handling", "strengthened reliability across backend workflows"],
    }
    options = outcomes.get(family, outcomes["software_engineering"])
    return options[index % len(options)]


def _copied_jd_fragments(text: str, job_analysis: dict) -> list[str]:
    copied = []
    lower = text.lower()
    for duty in job_analysis.get("job_duties", []) or job_analysis.get("responsibilities", []):
        words = re.findall(r"[A-Za-z0-9+#./-]+", duty)
        for size in range(7, 3, -1):
            for index in range(0, max(len(words) - size + 1, 0)):
                phrase = " ".join(words[index:index + size])
                if len(phrase) > 20 and phrase.lower() in lower:
                    copied.append(phrase)
    return _unique(copied)[:4]


def _reduce_project_redundancy(resume: dict, job_analysis: dict) -> None:
    global_fingerprints: list[set[str]] = []
    for project_index, project in enumerate(resume.get("projects", [])):
        kept: list[str] = []
        fingerprints: list[set[str]] = []
        for bullet in project.get("bullets", []):
            fingerprint = _project_bullet_fingerprint(bullet)
            if any(_fingerprint_overlap(fingerprint, existing) >= 0.55 for existing in fingerprints):
                continue
            if any(_fingerprint_overlap(fingerprint, existing) >= 0.65 for existing in global_fingerprints):
                continue
            if _project_bullet_angle(bullet) in [_project_bullet_angle(item) for item in kept]:
                continue
            kept.append(bullet)
            fingerprints.append(fingerprint)
            global_fingerprints.append(fingerprint)
            if len(kept) >= 2:
                break
        while len(kept) < min(2, len(project.get("bullets", [])) or 2):
            candidate = _project_angle_bullet(project, job_analysis, project_index + len(kept))
            fingerprint = _project_bullet_fingerprint(candidate)
            if not any(_fingerprint_overlap(fingerprint, existing) >= 0.5 for existing in fingerprints + global_fingerprints):
                kept.append(candidate)
                fingerprints.append(fingerprint)
                global_fingerprints.append(fingerprint)
            else:
                break
        project["bullets"] = kept[:2]
    limit = 2 if _role_family(job_analysis) == "fullstack_rails" else 3
    resume["projects"] = _rank_projects_for_role(resume.get("projects", []), job_analysis)[:limit]


def _project_bullet_fingerprint(text: str) -> set[str]:
    stop = {
        "the", "and", "for", "with", "into", "that", "using", "through", "across", "from",
        "improving", "improved", "support", "supported", "supporting", "created", "built",
        "designed", "engineered", "organized", "documented", "workflow", "workflows", "system",
        "systems", "project", "platform", "service", "services"
    }
    return {word for word in re.findall(r"[a-z0-9+#./-]+", text.lower()) if len(word) > 3 and word not in stop}


def _fingerprint_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0
    return len(left & right) / max(len(left), len(right))


def _project_bullet_angle(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ["deploy", "release", "rollback", "ci/cd", "environment"]):
        return "delivery"
    if any(word in lower for word in ["observability", "monitor", "health", "debug", "troubleshoot"]):
        return "observability"
    if any(word in lower for word in ["data", "sql", "kpi", "dashboard", "report"]):
        return "analytics"
    if any(word in lower for word in ["api", "integration", "documentation", "openapi"]):
        return "integration"
    if any(word in lower for word in ["rag", "retrieval", "prompt", "model", "ai", "llm"]):
        return "ai"
    return "architecture"


def _project_angle_bullet(project: dict, job_analysis: dict, index: int) -> str:
    family = _role_family(job_analysis)
    tech = _human_join(project.get("technologies", [])[:3]) if project.get("technologies") else "role-relevant tooling"
    if family == "ai_engineering":
        options = [
            f"Implemented retrieval evaluation checkpoints with {tech} to compare response quality before release.",
            f"Added traceable AI workflow stages so document processing behavior could be reviewed and improved.",
        ]
    elif family == "platform_engineering":
        options = [
            f"Added deployment health checks and rollback notes with {tech} to support cleaner production releases.",
            f"Connected service monitoring signals to release review so operational issues were easier to isolate.",
        ]
    elif family == "analytics":
        options = [
            f"Modeled KPI definitions and data-quality checks with {tech} to make reporting assumptions easier to audit.",
            f"Built dashboard-ready query outputs so recurring business questions could be reviewed without manual cleanup.",
        ]
    elif family == "solutions_architecture":
        options = [
            f"Mapped API dependencies and rollout assumptions with {tech} to reduce ambiguity before implementation.",
            f"Created integration notes that helped engineering teams compare delivery risks and system tradeoffs.",
        ]
    else:
        options = [
            f"Structured API and validation paths with {tech} to make operational behavior easier to maintain.",
            f"Documented service boundaries and failure-handling assumptions to improve production-readiness review.",
        ]
    return options[index % len(options)]


def _remove_repetitive_sentence_shapes(resume: dict, job_analysis: Optional[dict] = None) -> None:
    bullets = []
    owners = []
    for job in resume.get("experience", []):
        for index, bullet in enumerate(job.get("bullets", [])):
            owners.append((job, index))
            bullets.append(bullet)
    for project in resume.get("projects", []):
        for index, bullet in enumerate(project.get("bullets", [])):
            owners.append((project, index))
            bullets.append(bullet)
    varied = _enforce_verb_variety(bullets)
    used_endings: set[str] = set()
    used_percentages: set[str] = set()
    used_stems: set[str] = set()
    for global_index, ((owner, index), bullet) in enumerate(zip(owners, varied)):
        bullet = _avoid_repeated_ending(bullet, job_analysis or {}, global_index, used_endings, used_percentages, used_stems)
        owner["bullets"][index] = bullet


def _avoid_repeated_ending(
    bullet: str,
    job_analysis: dict,
    index: int,
    used_endings: set[str],
    used_percentages: set[str],
    used_stems: set[str],
) -> str:
    base = bullet.rstrip(".")
    base = _avoid_repeated_stem(base, job_analysis, index, used_stems)
    ending = base.split(";")[-1].strip().lower() if ";" in base else ""
    percent = re.search(r"\b\d+%\b", base)
    repeated_percent = bool(percent and percent.group(0) in used_percentages)
    if ending and ending in used_endings or repeated_percent:
        replacement = _replacement_outcome(job_analysis, index, used_endings)
        base = re.sub(r";\s*[^.;]+$", f"; {replacement}", base) if ";" in base else f"{base}; {replacement}"
        ending = replacement.lower()
    if ending:
        used_endings.add(ending)
    percent = re.search(r"\b\d+%\b", base)
    if percent:
        used_percentages.add(percent.group(0))
    return _restore_acronyms(base.rstrip(" .")) + "."


def _rank_projects_for_role(projects: list[dict], job_analysis: dict) -> list[dict]:
    family = _role_family(job_analysis)
    priority_terms = {
        "fullstack_rails": ["giving", "donor", "donation", "stripe", "rails", "react", "admin", "reporting", "payment"],
        "platform_engineering": ["deployment", "ci/cd", "cloud", "kubernetes", "observability", "platform", "orchestration"],
        "ai_engineering": ["ai", "rag", "llm", "document", "retrieval", "model", "intelligence"],
        "solutions_architecture": ["integration", "readiness", "architecture", "api", "cloud", "implementation"],
        "analytics": ["analytics", "kpi", "data", "dashboard", "reporting", "intelligence"],
        "product_frontend": ["product", "workflow", "dashboard", "react", "frontend", "user"],
        "software_engineering": ["api", "service", "automation", "backend", "microservice", "platform"],
    }.get(family, ["api", "service", "automation"])
    negative_name_terms = {
        "fullstack_rails": ["rag", "ai-assisted", "document intelligence", "developer platform", "ci/cd deployment", "model monitoring"],
        "platform_engineering": ["analytics", "kpi", "dashboard", "reporting", "business intelligence"],
        "ai_engineering": ["ci/cd", "deployment orchestrator", "analytics kpi"],
        "solutions_architecture": ["kpi", "dashboard", "model monitoring"],
        "analytics": ["ci/cd", "deployment", "kubernetes"],
        "product_frontend": ["ci/cd", "model monitoring"],
    }.get(family, [])
    def score(project: dict) -> int:
        name = project.get("name", "").lower()
        text = " ".join([
            project.get("name", ""),
            " ".join(project.get("technologies", [])),
            " ".join(project.get("bullets", [])),
        ]).lower()
        value = sum(4 for term in priority_terms if term in name) + sum(2 for term in priority_terms if term in text) + min(len(project.get("bullets", [])), 2)
        if any(term in name for term in negative_name_terms):
            value -= 10
        return value
    ranked = sorted(projects, key=score, reverse=True)
    positive = [project for project in ranked if score(project) > 1]
    return positive or ranked


def _avoid_repeated_stem(base: str, job_analysis: dict, index: int, used_stems: set[str]) -> str:
    stem = base.split(";")[0].strip()
    stem_key = _stem_key(stem)
    if stem_key and stem_key in used_stems:
        context = _fresh_context(job_analysis, index, used_stems)
        impact = _role_impact_phrase(job_analysis, index + 3)
        if re.search(r"\b(for|supporting|aligned with)\s+[^,;]+,\s+improving\s+[^;]+", stem, re.I):
            stem = re.sub(r"\b(for|supporting|aligned with)\s+[^,;]+,\s+improving\s+[^;]+", f"for {context}, improving {impact}", stem, flags=re.I)
        else:
            stem = f"{stem} for {context}"
        base = stem + (";" + ";".join(base.split(";")[1:]) if ";" in base else "")
        stem_key = _stem_key(stem)
    if stem_key:
        used_stems.add(stem_key)
    return base


def _stem_key(stem: str) -> str:
    context = re.search(r"\b(?:for|supporting|aligned with)\s+([^,;]+),\s+improving\s+([^;]+)", stem, re.I)
    if context:
        return f"{context.group(1)}|{context.group(2)}".lower()
    stem_key = re.sub(r"^[A-Za-z]+\s+", "", stem.lower())
    stem_key = re.sub(r"\b(api|apis|dashboard|dashboards|workflow|workflows|application|applications|deployment|deployments|services?)\b", "", stem_key)
    return re.sub(r"\s+", " ", stem_key).strip()


def _fresh_context(job_analysis: dict, index: int, used_stems: set[str]) -> str:
    raw_candidates = _translated_role_contexts(job_analysis) + _duty_fragments(job_analysis)
    candidates = [
        _short_context_phrase(_plain_focus_phrase(candidate))
        for candidate in raw_candidates
        if candidate and not re.match(r"(?i)^(required|preferred|minimum|basic)\s+(skills|qualifications|requirements)\s*:", candidate)
    ] + [
        "implementation planning",
        "operational review",
        "release readiness",
        "service ownership",
        "cross-functional delivery",
        "production support workflows",
    ]
    for offset in range(len(candidates) + 1):
        candidate = candidates[(index + offset) % len(candidates)] if candidates else "technical delivery"
        if candidate.lower() not in " ".join(used_stems):
            return candidate
    return candidates[index % len(candidates)] if candidates else "technical delivery"


def _short_context_phrase(value: str) -> str:
    clean = re.split(r",|;|\band\b", value)[0].strip()
    return clean or value


def _replacement_outcome(job_analysis: dict, index: int, used_endings: set[str]) -> str:
    candidates = (
        [_concrete_scale_phrase(job_analysis, index + 5), _non_numeric_outcome_phrase(job_analysis, index + 7)]
        + [_concrete_scale_phrase(job_analysis, index + offset) for offset in range(1, 12)]
        + [_non_numeric_outcome_phrase(job_analysis, index + offset) for offset in range(1, 12)]
        + _fallback_unique_outcomes(job_analysis)
    )
    return next((item for item in candidates if item.lower() not in used_endings), candidates[0])


def _fallback_unique_outcomes(job_analysis: dict) -> list[str]:
    family = _role_family(job_analysis)
    common = [
        "improved release review quality without adding process overhead",
        "created clearer ownership across implementation steps",
        "reduced avoidable follow-up during delivery review",
        "made operational risks easier to identify before release",
        "improved handoff quality between build and support work",
        "created a cleaner path from requirements to implementation",
        "reduced ambiguity in service behavior and operational review",
        "made recurring delivery work easier to validate",
        "strengthened production-readiness review before deployment",
        "improved traceability across system changes",
    ]
    role_specific = {
        "platform_engineering": [
            "made deployment behavior easier to compare across environments",
            "improved service health review before production changes",
            "reduced uncertainty during release troubleshooting",
            "created cleaner operational checks for cloud workloads",
        ],
        "solutions_architecture": [
            "made integration assumptions easier to validate with engineering teams",
            "reduced ambiguity around API ownership and rollout needs",
            "created clearer architecture notes for implementation planning",
            "improved alignment between requirements and technical delivery",
        ],
        "ai_engineering": [
            "made retrieval behavior easier to evaluate before release",
            "improved review quality for AI-assisted workflow decisions",
            "created clearer checkpoints for model and data workflow behavior",
            "reduced ambiguity in AI output validation",
        ],
        "analytics": [
            "made recurring reporting logic easier to audit",
            "improved confidence in operational metric definitions",
            "reduced ambiguity across dashboard inputs and outputs",
            "created clearer review paths for data quality issues",
        ],
        "product_frontend": [
            "made user workflow behavior easier to test and review",
            "improved consistency across repeated interface states",
            "reduced ambiguity between API behavior and screen behavior",
            "created cleaner handoffs between product and engineering review",
        ],
    }
    return role_specific.get(family, []) + common


def _business_project_name(name: str, job_analysis: dict) -> str:
    branded = _brand_project_name(name)
    if branded != name:
        return branded
    family = _role_family(job_analysis)
    lower = name.lower()
    if any(generic in lower for generic in ["todo", "crud", "dashboard app", "job tracker", "technical project"]):
        replacements = {
            "solutions_architecture": "Enterprise Integration Readiness Platform",
            "ai_engineering": "AI-Powered Operations Intelligence Platform",
            "platform_engineering": "Enterprise Deployment Orchestration Platform",
            "product_frontend": "Product Workflow Intelligence Dashboard",
            "analytics": "Operational Analytics Intelligence System",
            "software_engineering": "API-Driven Operations Automation Platform",
        }
        return replacements.get(family, "API-Driven Operations Automation Platform")
    return branded


def _dedupe_projects_by_name(projects: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for project in projects:
        key = _keyword_key(project.get("name", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(project)
    return result[:5]


def _brand_project_name(name: str) -> str:
    mapping = {
        "Frontend Job Tracker Dashboard": "AI-Assisted Hiring Intelligence Dashboard",
        "Cloud Deployment Pipeline": "Enterprise CI/CD Deployment Orchestrator",
        "RAG Document Assistant": "Multimodal Healthcare Document Intelligence Engine",
        "Analytics KPI Dashboard": "Operational Analytics & Decision Intelligence Platform",
        "Spring Boot Event-Driven Service": "Enterprise Event-Driven Claims Processing Service",
    }
    return mapping.get(name, name)


def _remove_ai_tone(text: str) -> str:
    for word in BAD_AI_WORDS:
        text = re.sub(rf"\b{word}\b", "used", text, flags=re.I)
    return text


def _role_specific_cleanup(resume: dict, job_analysis: dict, source_resume: Optional[dict] = None) -> None:
    family = _role_family(job_analysis)
    source_resume = source_resume or resume
    if family == "fullstack_rails" and not _source_supports_any(source_resume, ["Ruby on Rails", "Rails"]):
        _generic_target_cleanup(resume, job_analysis, source_resume)
        return
    if family == "platform_engineering":
        _platform_engineering_cleanup(resume, job_analysis, source_resume)
        return
    if family == "product_frontend":
        if not _source_supports_any(source_resume, ["React", "TypeScript", "JavaScript"]):
            _generic_target_cleanup(resume, job_analysis, source_resume)
            return
        _product_frontend_cleanup(resume, job_analysis, source_resume)
        return
    if family == "ai_engineering":
        if not _source_supports_any(source_resume, ["Python", "FastAPI", "RAG", "LLM", "Generative AI"]):
            _generic_target_cleanup(resume, job_analysis, source_resume)
            return
        _ai_engineering_cleanup(resume, job_analysis, source_resume)
        return
    if family == "java_backend":
        if not _source_supports_any(source_resume, ["Java", "Spring Boot"]):
            _generic_target_cleanup(resume, job_analysis, source_resume)
            return
        _profile_cleanup(resume, job_analysis, source_resume, _java_profile())
        return
    if family == "data_engineering":
        if not _source_supports_any(source_resume, ["Python", "SQL"]):
            _generic_target_cleanup(resume, job_analysis, source_resume)
            return
        _profile_cleanup(resume, job_analysis, source_resume, _data_profile())
        return
    if family == "backend_engineering":
        _profile_cleanup(resume, job_analysis, source_resume, _backend_profile(job_analysis, source_resume))
        return
    if family == "analytics":
        _profile_cleanup(resume, job_analysis, source_resume, _analytics_profile())
        return
    if family == "business_analysis":
        _profile_cleanup(resume, job_analysis, source_resume, _business_analysis_profile())
        return
    if family == "quality_assurance":
        _profile_cleanup(resume, job_analysis, source_resume, _qa_profile())
        return
    if family == "rails_backend":
        if not _source_supports_any(source_resume, ["Ruby on Rails", "Rails"]):
            _generic_target_cleanup(resume, job_analysis, source_resume)
            return
        _profile_cleanup(resume, job_analysis, source_resume, _rails_backend_profile())
        return
    if family == "dotnet_engineering":
        _profile_cleanup(resume, job_analysis, source_resume, _dotnet_profile())
        return
    if family == "solutions_architecture":
        _profile_cleanup(resume, job_analysis, source_resume, _solutions_profile())
        return
    if family != "fullstack_rails":
        _generic_target_cleanup(resume, job_analysis, source_resume)
        return
    resume["target_title"] = "Full Stack Engineer"
    resume["summary"] = _fullstack_rails_summary(resume)
    allowed = {
        "ruby on rails", "ruby", "rails", "react", "typescript", "javascript", "postgresql",
        "aws", "github", "git", "rest", "apis", "stripe", "stripe apis", "datadog",
        "aws performance insights", "react query", "redux"
    }
    skills = [skill for skill in _all_skills(resume) if _keyword_key(skill) in allowed]
    skills = _dedupe_fullstack_skills(_unique(["Ruby on Rails", "React", "PostgreSQL", "JavaScript", "TypeScript", "Stripe APIs", "GitHub"] + skills))
    resume["skills"] = _fullstack_rails_skills(skills)
    _rewrite_fullstack_rails_experience(resume, job_analysis)
    _force_fullstack_rails_projects(resume)


def _source_supports_any(source_resume: dict, keywords: list[str]) -> bool:
    content = _resume_keyword_text(source_resume)
    return any(_keyword_key(keyword) in content for keyword in keywords)


def _keep_only_verified_projects(resume: dict, source_resume: dict) -> None:
    original = deepcopy(source_resume.get("projects", []))
    generated = resume.get("projects", [])
    suggestions = deepcopy(resume.get("suggested_projects", []))
    original_names = {_keyword_key(project.get("name", "")) for project in original}
    for project in generated:
        key = _keyword_key(project.get("name", ""))
        if key and key not in original_names:
            suggestions.append({**project, "requires_confirmation": True})
    resume["projects"] = original
    resume["suggested_projects"] = _dedupe_projects_by_name(suggestions)


def _platform_engineering_cleanup(resume: dict, job_analysis: dict, source_resume: dict) -> None:
    title = job_analysis.get("job_title") or "AWS Software Engineer"
    jd_text = " ".join(job_analysis.get("keywords", []) + job_analysis.get("job_duties", [])).lower()
    resume["target_title"] = title if "engineer" in title.lower() else ("AWS Software Engineer" if "aws" in jd_text else "Cloud Software Engineer")
    resume["summary"] = _platform_engineering_summary(resume, source_resume)
    allowed = {
        "aws", "docker", "kubernetes", "terraform", "ci/cd", "git", "github", "github actions",
        "sql", "postgresql", "prometheus", "grafana", "opentelemetry", "linux", "apis", "rest",
        ".net", "c#"
    }
    evidence = " ".join(
        [bullet for job in source_resume.get("experience", []) for bullet in job.get("bullets", [])]
        + [bullet for project in source_resume.get("projects", []) for bullet in project.get("bullets", [])]
    ).lower()
    original_skills = [
        skill for skill in _all_skills(source_resume)
        if _keyword_key(skill) in allowed
        and (_keyword_key(skill) not in {"net", "c#"} or _keyword_key(skill) in _keyword_key(evidence))
    ]
    resume["skills"] = _platform_engineering_skills(_unique(original_skills))
    _rewrite_platform_experience(resume)
    _force_platform_projects(resume)


def _platform_engineering_summary(resume: dict, source_resume: dict) -> str:
    years = _experience_label(resume)
    years_text = f" with {years} of experience" if years else " with experience"
    visible = _all_skills(source_resume)
    featured = [skill for skill in ["AWS", "Terraform", "Docker", "Kubernetes", "CI/CD", "SQL"] if skill in visible]
    stack = _human_join(featured[:5]) or "AWS services and deployment automation"
    return (
        f"AWS Software Engineer{years_text} delivering backend services, deployment workflows, and cloud operations with {stack}. "
        "Experienced supporting reliable releases, diagnosing production issues, and improving service visibility through practical automation and monitoring. "
        "Focused on maintainable software, secure delivery, and dependable operational outcomes."
    )


def _generic_target_cleanup(resume: dict, job_analysis: dict, source_resume: dict) -> None:
    target = job_analysis.get("job_title") or "Software Engineer"
    years = _experience_label(source_resume)
    years_text = f" with {years} of experience" if years else " with experience"
    benchmark = job_analysis.get("resume_benchmark", {})
    focus = benchmark.get("resume_focus") or "maintainable software, clear implementation, and dependable delivery"
    skills = _summary_skills(_supported_jd_keywords(source_resume, job_analysis.get("keywords", [])))
    skill_text = f" Supported experience includes {_human_join(skills)}." if skills else ""
    resume["target_title"] = target
    resume["summary"] = f"{target}{years_text} delivering software and technical workflows aligned to {focus}.{skill_text} Focused on truthful, maintainable implementation and production-ready outcomes."
    resume["projects"] = deepcopy(source_resume.get("projects", []))


def _profile_cleanup(resume: dict, job_analysis: dict, source_resume: dict, profile: dict) -> None:
    resume["target_title"] = job_analysis.get("job_title") or profile["title"]
    years = _experience_label(resume)
    years_text = f" with {years} of experience" if years else " with experience"
    resume["summary"] = (
        f"{resume['target_title']}{years_text} {profile['summary_work']}. "
        f"Experienced in {profile['summary_value']}. "
        f"Focused on {profile['summary_focus']}."
    )
    supported = _supported_profile_skills(source_resume, profile["allowed"])
    resume["skills"] = _profile_skills(supported, profile["groups"])
    for index, job in enumerate(resume.get("experience", [])):
        _normalize_platform_job_header(job)
        job["bullets"] = profile["bullet_sets"][min(index, len(profile["bullet_sets"]) - 1)]
    resume["projects"] = profile["projects"]


def _supported_profile_skills(source_resume: dict, allowed: set[str]) -> list[str]:
    return _unique([skill for skill in _all_skills(source_resume) if _keyword_key(skill) in allowed])


def _profile_skills(skills: list[str], groups: dict[str, set[str]]) -> dict:
    result = {
        "programming": [], "frameworks_libraries": [], "cloud_infrastructure": [],
        "mlops_engineering": [], "databases_vector_stores": [], "monitoring_observability": [],
        "developer_tools": [], "technical": [], "ai_ml_core": [], "deep_learning": [],
        "genai_llm_systems": [], "ai_safety_compliance": [], "tools": [], "cloud": [],
        "databases": [], "soft_skills": [],
    }
    for skill in skills:
        key = _keyword_key(skill)
        group = next((name for name, values in groups.items() if key in values), "technical")
        result[group].append(skill)
    return result


def _java_profile() -> dict:
    return {
        "title": "Java Backend Engineer",
        "summary_work": "building backend services and API-driven applications with Java, Spring Boot, PostgreSQL, and AWS",
        "summary_value": "service design, data persistence, integration workflows, and maintainable delivery",
        "summary_focus": "reliable APIs, clear system behavior, and production-ready backend engineering",
        "allowed": {"java", "spring boot", "rest", "apis", "microservices", "postgresql", "sql", "aws", "docker", "git", "github"},
        "groups": {
            "programming": {"java", "apis", "sql"}, "frameworks_libraries": {"spring boot", "rest", "microservices"},
            "databases_vector_stores": {"postgresql"}, "cloud_infrastructure": {"aws"},
            "mlops_engineering": {"docker"}, "developer_tools": {"git", "github"},
        },
        "bullet_sets": [
            ["Developed Java and Spring Boot service workflows with REST API boundaries and PostgreSQL-backed persistence for maintainable backend delivery.",
             "Designed validation and processing flows that kept operational behavior traceable across API and data-layer changes.",
             "Applied Docker and AWS delivery practices to support dependable application releases and production review."],
            ["Built backend and data integrations for API-driven applications, emphasizing clear service behavior and maintainable implementation.",
             "Improved SQL-backed workflow logic and troubleshooting practices for reliable operational processing.",
             "Collaborated on testing, code review, and deployment decisions across service-oriented delivery."],
            ["Supported application services and production issue investigation across backend workflows.",
             "Documented implementation and release considerations for dependable software delivery."],
        ],
        "projects": [
            {"name": "Service-Oriented Workflow API", "technologies": ["Java", "Spring Boot", "PostgreSQL", "REST"], "bullets": ["Designed REST service boundaries, request validation, persistence flows, and failure handling for a maintainable backend workflow.", "Documented API behavior and testing scenarios for implementation and release review."]},
            {"name": "Cloud-Ready Backend Delivery Pipeline", "technologies": ["Java", "Docker", "AWS"], "bullets": ["Structured container-based delivery practices for a backend service with environment configuration and health-check planning.", "Outlined deployment validation and operational review steps for reliable service releases."]},
        ],
    }


def _backend_profile(job_analysis: dict, source_resume: dict) -> dict:
    supported = _supported_jd_keywords(source_resume, job_analysis.get("keywords", []))
    text = " ".join(supported).lower()
    technologies = []
    for skill in ["Go", "Python", "Node", "TypeScript", "JavaScript", "PostgreSQL", "SQL", "AWS", "Docker"]:
        if _keyword_key(skill) in _keyword_key(text):
            technologies.append(skill)
    stack = _human_join(technologies[:4]) or "APIs, databases, and cloud delivery practices"
    return {
        "title": "Backend Software Engineer",
        "summary_work": f"building API-driven services and production application workflows with {stack}",
        "summary_value": "service implementation, data handling, debugging, and reliable software delivery",
        "summary_focus": "maintainable backend systems, secure application behavior, and production reliability",
        "allowed": {"go", "python", "node", "typescript", "javascript", "rest", "apis", "postgresql", "sql", "aws", "docker", "git", "github", "redis", "microservices"},
        "groups": {"programming": {"go", "python", "typescript", "javascript", "sql", "apis"}, "frameworks_libraries": {"node", "rest", "microservices"}, "databases_vector_stores": {"postgresql", "redis"}, "cloud_infrastructure": {"aws"}, "mlops_engineering": {"docker"}, "developer_tools": {"git", "github"}},
        "bullet_sets": [
            ["Developed API-backed application workflows with clear service behavior, validation, and maintainable data handling.",
             "Designed backend processing and error-handling paths that supported reliable production operation and practical troubleshooting.",
             "Applied cloud and deployment practices to improve release readiness and operational support."],
            ["Built service and data workflow enhancements for production applications, emphasizing readable implementation and dependable behavior.",
             "Investigated application issues through logs, data checks, and reproducible technical context.",
             "Collaborated on testing, code review, and production delivery for backend changes."],
            ["Supported backend service reliability and technical issue resolution across application workflows.",
             "Documented service behavior and release considerations for maintainable delivery."],
        ],
        "projects": [
            {"name": "Production Service Workflow API", "technologies": technologies[:4] or ["REST APIs", "SQL"], "bullets": ["Designed API operations, validation rules, persistence behavior, and failure handling for a maintainable backend service.", "Documented test scenarios and deployment considerations for reliable production review."]},
            {"name": "Service Reliability Operations Toolkit", "technologies": [skill for skill in technologies if skill in {"AWS", "Docker", "PostgreSQL", "SQL"}] or ["Git"], "bullets": ["Structured operational review around service errors, data checks, and release verification practices.", "Created clear troubleshooting and implementation notes for repeatable backend support."]},
        ],
    }


def _rails_backend_profile() -> dict:
    return {
        "title": "Back-end Software Engineer",
        "summary_work": "building maintainable web services, API workflows, and data-backed application behavior with Ruby on Rails and PostgreSQL",
        "summary_value": "backend implementation, validation, production troubleshooting, and dependable software delivery",
        "summary_focus": "readable Rails services, secure application behavior, and useful customer outcomes",
        "allowed": {"ruby on rails", "ruby", "rest", "apis", "postgresql", "sql", "aws", "docker", "git", "github", "graphql"},
        "groups": {"programming": {"ruby", "sql", "apis"}, "frameworks_libraries": {"ruby on rails", "rest", "graphql"}, "databases_vector_stores": {"postgresql"}, "cloud_infrastructure": {"aws"}, "mlops_engineering": {"docker"}, "developer_tools": {"git", "github"}},
        "bullet_sets": [
            ["Developed backend application workflows with clear API behavior, database validation, and maintainable service boundaries.",
             "Implemented data-backed processing and exception handling practices to improve operational reliability and support review.",
             "Investigated production application issues through observable behavior and practical debugging steps."],
            ["Built service and data workflow improvements for API-backed applications with attention to maintainable implementation.",
             "Supported testable changes, technical review, and dependable production delivery across backend work.",
             "Collaborated on issue resolution and workflow improvements tied to user-facing application behavior."],
            ["Supported backend workflow reliability and production investigation across software delivery work.",
             "Documented implementation and release considerations for maintainable application changes."],
        ],
        "projects": [
            {"name": "API-Driven Content Delivery Service", "technologies": ["Ruby on Rails", "PostgreSQL", "REST APIs"], "bullets": ["Designed API endpoints, validation behavior, persistence flows, and failure handling for a maintainable web service.", "Documented test scenarios and release considerations for dependable backend delivery."]},
            {"name": "Application Reliability Review Toolkit", "technologies": ["Ruby on Rails", "PostgreSQL", "Git"], "bullets": ["Structured application issue review around data checks, error behavior, and clear remediation notes.", "Organized change-review practices for readable implementation and production support."]},
        ],
    }


def _dotnet_profile() -> dict:
    return {
        "title": ".NET Software Engineer",
        "summary_work": "developing backend services and software delivery workflows for secure, dependable application systems",
        "summary_value": "API design, database-backed processing, testing considerations, and production support",
        "summary_focus": "maintainable implementation, service reliability, and clear operational outcomes",
        "allowed": {"net", "c#", "sql", "postgresql", "rest", "apis", "aws", "azure", "docker", "ci/cd", "git", "github"},
        "groups": {"programming": {"c#", "sql", "apis"}, "frameworks_libraries": {"net", "rest"}, "databases_vector_stores": {"postgresql"}, "cloud_infrastructure": {"aws", "azure"}, "mlops_engineering": {"docker", "ci/cd"}, "developer_tools": {"git", "github"}},
        "bullet_sets": [
            ["Developed backend application workflows with API validation, data handling, and reliable production delivery practices.",
             "Applied database-backed processing and troubleshooting methods to keep service behavior clear and supportable.",
             "Contributed to tested implementation and deployment review for dependable software changes."],
            ["Built service workflow improvements focused on maintainable code, operational clarity, and release readiness.",
             "Investigated application issues through data behavior and error context, supporting practical remediation.",
             "Collaborated on implementation review and reliable software delivery."],
            ["Supported backend application delivery, issue resolution, and clear technical documentation."],
        ],
        "projects": [
            {"name": "Secure Service Workflow API", "technologies": ["SQL", "REST APIs", "Git"], "bullets": ["Designed service validation and data-flow patterns for a secure, maintainable API-backed application.", "Documented release checks and failure-handling behavior for implementation review."]},
        ],
    }


def _solutions_profile() -> dict:
    return {
        "title": "Software Solutions Architect",
        "summary_work": "connecting application workflows, cloud delivery, and technical implementation decisions across software initiatives",
        "summary_value": "solution analysis, API and integration thinking, delivery planning, and production-minded engineering",
        "summary_focus": "credible architecture communication, clear tradeoffs, and maintainable delivery",
        "allowed": {"aws", "apis", "rest", "sql", "postgresql", "javascript", "typescript", "docker", "git", "github", "microservices"},
        "groups": {"programming": {"javascript", "typescript", "sql", "apis"}, "frameworks_libraries": {"rest", "microservices"}, "databases_vector_stores": {"postgresql"}, "cloud_infrastructure": {"aws"}, "mlops_engineering": {"docker"}, "developer_tools": {"git", "github"}},
        "bullet_sets": [
            ["Translated operational and product needs into clear technical workflows, service boundaries, and implementation considerations.",
             "Designed API and data-flow approaches that balanced maintainability, delivery constraints, and production support needs.",
             "Communicated solution decisions through practical documentation, reviewable changes, and operational context."],
            ["Built service-backed workflow improvements and contributed technical guidance across application delivery work.",
             "Analyzed integration and data behavior to clarify dependencies, risks, and implementation paths.",
             "Collaborated with engineering partners on reviewable, maintainable production changes."],
            ["Supported system delivery and technical investigation across software workflows.",
             "Documented solution behavior and operational review considerations."],
        ],
        "projects": [
            {"name": "Enterprise Integration Readiness Platform", "technologies": ["REST APIs", "PostgreSQL", "AWS"], "bullets": ["Mapped system touchpoints, API behaviors, data constraints, and rollout considerations for a reviewable integration plan.", "Documented tradeoffs and validation steps so implementation choices could be evaluated clearly."]},
            {"name": "Cloud Solution Delivery Blueprint", "technologies": ["AWS", "Docker", "Git"], "bullets": ["Structured deployment and service reliability considerations for a cloud-hosted application workflow.", "Created technical review notes connecting architecture decisions to operational support and delivery risks."]},
        ],
    }


def _data_profile() -> dict:
    return {
        "title": "Data Engineer",
        "summary_work": "developing data pipelines, backend processing workflows, and cloud-based data services with Python, SQL, PostgreSQL, Snowflake, and AWS",
        "summary_value": "data validation, reliable processing, reporting support, and operational troubleshooting",
        "summary_focus": "trustworthy datasets, maintainable pipelines, and decision-ready data delivery",
        "allowed": {"python", "sql", "postgresql", "snowflake", "aws", "docker", "git", "github", "etl"},
        "groups": {"programming": {"python", "sql"}, "databases_vector_stores": {"postgresql", "snowflake"}, "cloud_infrastructure": {"aws"}, "mlops_engineering": {"docker"}, "developer_tools": {"git", "github"}, "technical": {"etl"}},
        "bullet_sets": [
            ["Developed Python and SQL processing workflows for operational data handling, validation, and reporting-ready outputs.",
             "Designed PostgreSQL-backed data paths with clear exception handling and traceable transformations for reliable review.",
             "Applied AWS and Docker delivery practices to support repeatable deployment of data-oriented services."],
            ["Built data workflow and API improvements that made processing behavior easier to inspect and maintain.",
             "Investigated data-quality and operational issues through structured checks and technical troubleshooting.",
             "Collaborated on implementation, testing, and release considerations for production data delivery."],
            ["Supported reliable data processing and production investigation across service-backed workflows.",
             "Documented validation assumptions and operational review practices for maintainable delivery."],
        ],
        "projects": [
            {"name": "Operational Data Quality Pipeline", "technologies": ["Python", "SQL", "PostgreSQL", "AWS"], "bullets": ["Designed ingestion, validation, and exception-review stages for a reporting-ready data workflow.", "Structured data-quality checks and traceable processing outputs for operational review."]},
            {"name": "Cloud Analytics Processing Service", "technologies": ["Python", "Snowflake", "AWS", "Docker"], "bullets": ["Built a cloud-oriented data processing concept focused on cleaned outputs, scheduled execution, and reproducible deployment.", "Documented reliability and monitoring considerations for production data workflows."]},
        ],
    }


def _analytics_profile() -> dict:
    return {
        "title": "Business Intelligence Analyst",
        "summary_work": "turning operational data into clear reporting and business insights with SQL, PostgreSQL, and analytics workflows",
        "summary_value": "data validation, reporting logic, stakeholder-facing analysis, and actionable interpretation",
        "summary_focus": "accurate metrics, readable reporting, and decisions grounded in reliable data",
        "allowed": {"sql", "postgresql", "python", "snowflake", "excel", "tableau", "power bi", "data analysis"},
        "groups": {"programming": {"sql", "python"}, "databases_vector_stores": {"postgresql", "snowflake"}, "developer_tools": {"excel", "tableau", "power bi"}, "technical": {"data analysis"}},
        "bullet_sets": [
            ["Analyzed operational workflow data and reporting needs, translating business questions into structured query and validation logic.",
             "Created reporting-ready outputs and exception-review approaches to improve confidence in recurring operational analysis.",
             "Communicated technical findings in clear terms suited to business review and practical decision-making."],
            ["Developed SQL-backed reporting workflows that improved visibility into operational trends and data-quality issues.",
             "Reviewed data behavior and reporting assumptions to support consistent analysis across recurring requests.",
             "Collaborated on clear delivery of analytics findings and implementation considerations."],
            ["Supported structured reporting and operational review through dependable data handling practices.",
             "Documented analysis assumptions and validation steps for repeatable business reporting."],
        ],
        "projects": [
            {"name": "Operational Metrics & Reporting Workspace", "technologies": ["SQL", "PostgreSQL"], "bullets": ["Designed KPI definitions, validation checks, and reporting outputs for recurring operational review.", "Documented metric assumptions and exception paths to improve confidence in reported findings."]},
            {"name": "Decision Support Analytics Dashboard", "technologies": ["SQL", "Python"], "bullets": ["Structured analysis-ready datasets and summary views around practical business questions.", "Translated trends and data-quality observations into clear review notes and recommendations."]},
        ],
    }


def _business_analysis_profile() -> dict:
    return {
        "title": "Business Analyst",
        "summary_work": "connecting operational needs, technical workflows, and delivery decisions across software and data-driven initiatives",
        "summary_value": "requirements clarification, process analysis, validation thinking, and cross-functional implementation support",
        "summary_focus": "clear requirements, practical solutions, and measurable operational value",
        "allowed": {"sql", "agile", "scrum", "apis", "jira", "confluence", "excel", "data analysis"},
        "groups": {"programming": {"sql", "apis"}, "developer_tools": {"jira", "confluence", "excel"}, "technical": {"agile", "scrum", "data analysis"}},
        "bullet_sets": [
            ["Translated operational workflow needs into clear functional requirements, validation rules, and implementation-ready decisions.",
             "Mapped process issues and system behavior to improve clarity between product goals and technical delivery.",
             "Collaborated with engineering and operational partners on acceptance expectations, workflow review, and release readiness."],
            ["Analyzed data-backed workflow issues and documented practical recommendations for implementation and review.",
             "Supported cross-functional delivery by clarifying process assumptions, technical dependencies, and business outcomes.",
             "Organized reviewable requirements and validation considerations for maintainable software changes."],
            ["Supported operational process improvement through structured analysis and clear documentation.",
             "Contributed to implementation review and issue resolution across technical workflows."],
        ],
        "projects": [
            {"name": "Operational Workflow Requirements Hub", "technologies": ["SQL", "APIs"], "bullets": ["Mapped user needs, system touchpoints, validation rules, and acceptance scenarios for an operational workflow.", "Created implementation-ready requirements notes connecting process outcomes to technical behavior."]},
            {"name": "Business Process Insight Workspace", "technologies": ["SQL"], "bullets": ["Organized process observations and data checks into a clear improvement analysis.", "Documented assumptions, risks, and review criteria for cross-functional delivery decisions."]},
        ],
    }


def _qa_profile() -> dict:
    return {
        "title": "QA Automation Engineer",
        "summary_work": "supporting quality engineering, production reliability, and API-backed application delivery",
        "summary_value": "defect investigation, validation thinking, release review, and dependable technical workflows",
        "summary_focus": "clear test coverage, actionable defect reporting, and release confidence",
        "allowed": {"playwright", "cypress", "selenium", "ci/cd", "git", "github", "apis", "rest", "postman"},
        "groups": {"frameworks_libraries": {"apis", "rest"}, "mlops_engineering": {"ci/cd"}, "developer_tools": {"playwright", "cypress", "selenium", "git", "github", "postman"}},
        "bullet_sets": [
            ["Defined validation scenarios and error-handling checks for API-backed product workflows and production-ready changes.",
             "Investigated application issues through reproducible steps, expected behavior, and clear defect context for engineering review.",
             "Supported release quality through structured test thinking, implementation review, and operational follow-up."],
            ["Reviewed workflow behavior and service outputs to identify issues before release and clarify expected results.",
             "Collaborated with engineering teammates on testability, failure handling, and reliable implementation delivery.",
             "Documented defect findings and validation outcomes for practical release decisions."],
            ["Supported software quality and production troubleshooting through clear issue analysis and validation notes.",
             "Contributed to release review practices for maintainable application changes."],
        ],
        "projects": [
            {"name": "API Workflow Test Automation Suite", "technologies": ["REST APIs", "Git"], "bullets": ["Designed reusable validation scenarios for success, failure, and edge-case behaviors across API-backed workflows.", "Documented expected results and defect reporting patterns for consistent engineering review."]},
            {"name": "Release Readiness Validation Console", "technologies": ["CI/CD", "Git"], "bullets": ["Organized regression checks, release verification notes, and issue-triage context into a focused quality workflow.", "Structured review outputs to improve traceability from defect discovery to resolved release behavior."]},
        ],
    }


def _product_frontend_cleanup(resume: dict, job_analysis: dict, source_resume: dict) -> None:
    resume["target_title"] = job_analysis.get("job_title") or "Frontend Engineer"
    years = _experience_label(resume)
    years_text = f" with {years} of experience" if years else " with experience"
    resume["summary"] = (
        f"Frontend Engineer{years_text} building responsive, API-connected product experiences with React, TypeScript, and JavaScript. "
        "Experienced translating workflow requirements into clear UI states, reusable components, validation, and reliable client-side behavior. "
        "Focused on accessible interfaces, maintainable implementation, and user-facing quality."
    )
    supported = _all_skills(source_resume)
    chosen = _unique([skill for skill in supported if _keyword_key(skill) in {
        "react", "typescript", "javascript", "html5", "css3", "rest", "apis", "react query",
        "redux", "jest", "playwright", "git", "github", "figma", "aws"
    }])
    resume["skills"] = {
        "programming": [skill for skill in chosen if _keyword_key(skill) in {"typescript", "javascript", "html5", "css3"}],
        "frameworks_libraries": [skill for skill in chosen if _keyword_key(skill) in {"react", "react query", "redux", "rest", "apis"}],
        "developer_tools": [skill for skill in chosen if _keyword_key(skill) in {"git", "github", "figma", "jest", "playwright"}],
        "cloud_infrastructure": [skill for skill in chosen if _keyword_key(skill) == "aws"],
        "technical": [],
        "ai_ml_core": [], "deep_learning": [], "genai_llm_systems": [], "mlops_engineering": [],
        "databases_vector_stores": [], "monitoring_observability": [], "ai_safety_compliance": [],
        "tools": [], "cloud": [], "databases": [], "soft_skills": [],
    }
    bullet_sets = [
        [
            "Designed React-based product workflows with reusable UI components, validation states, and API integration for clearer user interactions.",
            "Implemented responsive interface behavior and error handling patterns that made key user flows easier to complete and maintain.",
            "Translated product requirements into testable frontend changes, collaborating on UX details and implementation quality.",
            "Improved component reuse and screen-state consistency across API-backed experiences, reducing repeated front-end maintenance work.",
        ],
        [
            "Developed user-facing React features connected to backend APIs, with attention to loading, error, and empty-state behavior.",
            "Applied TypeScript and structured component patterns to improve readability, maintainability, and change confidence.",
            "Reviewed workflow behavior with teammates and refined UI implementation around usability, validation, and production support.",
            "Supported release-ready frontend delivery through clear Git changes, debugging, and practical test coverage.",
        ],
        [
            "Built maintainable interface workflows for web applications, connecting user requirements to consistent front-end implementation.",
            "Investigated UI defects and API interaction issues, improving reliability across customer-facing screens.",
            "Contributed to clean implementation and release practices for production web features.",
        ],
    ]
    for index, job in enumerate(resume.get("experience", [])):
        _normalize_platform_job_header(job)
        job["bullets"] = bullet_sets[min(index, len(bullet_sets) - 1)]
    resume["projects"] = [
        {
            "name": "Customer Workflow Experience Dashboard",
            "technologies": ["React", "TypeScript", "REST APIs"],
            "bullets": [
                "Built reusable interface views for filtering, form validation, loading states, and error recovery across API-backed workflows.",
                "Structured components and client-side state for a readable, responsive product experience suitable for iterative delivery.",
            ],
        },
        {
            "name": "Accessible Frontend Component System",
            "technologies": ["React", "TypeScript", "HTML5", "CSS3"],
            "bullets": [
                "Designed reusable form and navigation patterns with accessible structure, predictable interactions, and clear visual hierarchy.",
                "Documented component behavior and test scenarios to support consistent product implementation and review.",
            ],
        },
    ]


def _ai_engineering_cleanup(resume: dict, job_analysis: dict, source_resume: dict) -> None:
    resume["target_title"] = job_analysis.get("job_title") or "AI Engineer"
    years = _experience_label(resume)
    years_text = f" with {years} of experience" if years else " with experience"
    resume["summary"] = (
        f"AI Engineer{years_text} developing intelligent document and workflow systems with Python, FastAPI, PostgreSQL, and AWS. "
        "Experienced connecting retrieval, API services, data validation, and evaluation practices into maintainable applications. "
        "Focused on useful AI behavior, traceable outputs, and reliable production delivery."
    )
    supported = _all_skills(source_resume)
    chosen = _unique([skill for skill in supported if _keyword_key(skill) in {
        "python", "fastapi", "postgresql", "aws", "docker", "llm", "rag", "langchain",
        "vector embeddings", "openai apis", "hugging face", "mlflow", "git", "github"
    }])
    resume["skills"] = {
        "programming": [skill for skill in chosen if _keyword_key(skill) in {"python", "apis"}],
        "frameworks_libraries": [skill for skill in chosen if _keyword_key(skill) in {"fastapi"}],
        "ai_ml_core": [skill for skill in chosen if _keyword_key(skill) in {"llm", "rag", "vector embeddings"}],
        "genai_llm_systems": [skill for skill in chosen if _keyword_key(skill) in {"langchain", "openai apis", "hugging face"}],
        "databases_vector_stores": [skill for skill in chosen if _keyword_key(skill) == "postgresql"],
        "cloud_infrastructure": [skill for skill in chosen if _keyword_key(skill) in {"aws"}],
        "mlops_engineering": [skill for skill in chosen if _keyword_key(skill) in {"docker", "mlflow", "git", "github"}],
        "technical": [], "deep_learning": [], "monitoring_observability": [], "ai_safety_compliance": [],
        "developer_tools": [], "tools": [], "cloud": [], "databases": [], "soft_skills": [],
    }
    bullet_sets = [
        [
            "Designed AI-enabled workflow services with Python and FastAPI, connecting data handling, application logic, and reliable API behavior.",
            "Developed document-processing and retrieval-oriented flows with attention to traceability, validation, and practical user outcomes.",
            "Integrated PostgreSQL-backed data operations and cloud delivery practices to support maintainable production workflows.",
            "Reviewed AI-assisted functionality for clear failure handling, readable outputs, and dependable operational use.",
        ],
        [
            "Built backend services and data workflows that support automation, reporting, and reliable production processing.",
            "Applied API and database design practices to keep processing behavior testable and operationally understandable.",
            "Diagnosed workflow issues through logs and reviewable application signals, strengthening production support.",
            "Collaborated on feature delivery, testing, and implementation decisions across data-driven application work.",
        ],
        [
            "Delivered service-oriented application workflows with attention to reliability, validation, and maintainable implementation.",
            "Supported production troubleshooting and iterative improvements across API-backed systems.",
            "Documented implementation behavior and release considerations for technical review.",
        ],
    ]
    for index, job in enumerate(resume.get("experience", [])):
        _normalize_platform_job_header(job)
        job["bullets"] = bullet_sets[min(index, len(bullet_sets) - 1)]
    resume["projects"] = [
        {
            "name": "Document Retrieval & Evaluation Workspace",
            "technologies": ["Python", "FastAPI", "PostgreSQL", "RAG"],
            "bullets": [
                "Developed document ingestion, retrieval, and response-review workflows with structured API endpoints and traceable evaluation steps.",
                "Designed validation and failure-handling paths so retrieval behavior could be examined before production use.",
            ],
        },
        {
            "name": "AI Workflow Operations Console",
            "technologies": ["Python", "FastAPI", "AWS", "Docker"],
            "bullets": [
                "Built an API-backed operations view for reviewing AI workflow requests, outputs, exceptions, and processing status.",
                "Documented deployment and quality-check practices to support reliable delivery of AI-assisted application features.",
            ],
        },
    ]


def _platform_engineering_skills(skills: list[str]) -> dict:
    keys = {_keyword_key(skill): skill for skill in skills}

    def present(*values: str) -> list[str]:
        return [keys[_keyword_key(value)] for value in values if _keyword_key(value) in keys]

    return {
        "programming": present("C#", "SQL", "APIs"),
        "frameworks_libraries": present(".NET", "REST"),
        "cloud_infrastructure": present("AWS"),
        "mlops_engineering": present("Terraform", "Docker", "Kubernetes", "CI/CD", "GitHub Actions"),
        "databases_vector_stores": present("PostgreSQL"),
        "monitoring_observability": present("Prometheus", "Grafana", "OpenTelemetry"),
        "developer_tools": present("Git", "GitHub", "Linux"),
        "technical": [],
        "ai_ml_core": [],
        "deep_learning": [],
        "genai_llm_systems": [],
        "ai_safety_compliance": [],
        "tools": [],
        "cloud": [],
        "databases": [],
        "soft_skills": [],
    }


def _rewrite_platform_experience(resume: dict) -> None:
    bullet_sets = [
        [
            "Engineered backend and cloud delivery workflows with AWS, Docker, and CI/CD practices to support repeatable releases and clearer operational ownership.",
            "Automated infrastructure and environment configuration patterns with Terraform, reducing manual setup steps across deployment workflows.",
            "Implemented container deployment checks and service health review practices for Kubernetes-based workloads and production readiness.",
            "Diagnosed production issues through logs and monitoring signals, improving the path from reported incident to actionable fix.",
        ],
        [
            "Developed service and data workflow improvements backed by SQL and PostgreSQL, keeping operational behavior traceable during release review.",
            "Integrated CI/CD checks with Git-based delivery practices to improve build validation and make deployment changes easier to review.",
            "Improved monitoring visibility across application and infrastructure behavior using operational metrics and structured troubleshooting notes.",
            "Collaborated with engineering teammates on maintainable implementation details, testing expectations, and reliable production delivery.",
        ],
        [
            "Supported backend service delivery and production troubleshooting across cloud-hosted workflows, with attention to security and reliability.",
            "Applied Docker and deployment automation practices to standardize application packaging and reduce environment drift.",
            "Reviewed service performance signals and query behavior to identify practical improvements in cloud application operation.",
            "Maintained clear Git-based change history and release documentation for repeatable support and delivery work.",
        ],
    ]
    for index, job in enumerate(resume.get("experience", [])):
        _normalize_platform_job_header(job)
        job["bullets"] = bullet_sets[min(index, len(bullet_sets) - 1)]


def _normalize_platform_job_header(job: dict) -> None:
    title = job.get("title", "") or "Software Engineer"
    company = job.get("company", "") or ""
    if not company and "," in title:
        title_part, company_part = [part.strip() for part in title.rsplit(",", 1)]
        if company_part and len(company_part.split()) <= 4:
            title, company = title_part, company_part
    if _invalid_job_heading(title):
        title = "Software Engineer"
    if _looks_like_parsed_fragment(company) or _invalid_company_heading(company):
        company = ""
    job["title"] = re.sub(r"\bFull Stack Product Engineer\b", "Software Engineer", title, flags=re.I)
    job["company"] = company


def _force_platform_projects(resume: dict) -> None:
    resume["projects"] = [
        {
            "name": "Cloud-Native Deployment Automation Platform",
            "technologies": ["AWS", "Terraform", "Docker", "Kubernetes", "CI/CD"],
            "bullets": [
                "Designed infrastructure-as-code and container delivery workflows for repeatable environment provisioning and service deployment.",
                "Added health-check, rollback, and deployment validation steps to make production releases easier to review and troubleshoot.",
            ],
        },
        {
            "name": "AWS Service Reliability & Monitoring Toolkit",
            "technologies": ["AWS", "SQL", "Prometheus", "Grafana", "Git"],
            "bullets": [
                "Organized application health signals, deployment observations, and SQL-backed operational checks into a focused troubleshooting workflow.",
                "Documented incident review and release verification steps to support maintainable, reliable cloud software delivery.",
            ],
        },
    ]


def _fullstack_rails_summary(resume: dict) -> str:
    years = _experience_label(resume)
    years_text = f" with {years} of experience" if years else " with experience"
    return (
        f"Full Stack Engineer{years_text} building customer-facing product workflows, backend APIs, and reporting tools with React, Ruby on Rails, PostgreSQL, and AWS. "
        "Experienced turning product requirements into small, reviewable changes, improving front-end UX, debugging production issues, and protecting customer data. "
        "Brings a practical product engineering style suited to donor experiences, admin reporting, payment workflows, and reliable delivery."
    )


def _fullstack_bullet_cleanup(text: str) -> str:
    text = re.sub(r"(?i)\bAI-assisted development workflows\b", "developer productivity workflows", text)
    text = re.sub(r"(?i)\bAI-enabled systems\b", "product systems", text)
    text = re.sub(r"(?i)\bRAG pipelines?,?\s*", "", text)
    text = re.sub(r"(?i)\bvector search,?\s*", "", text)
    text = re.sub(r"(?i)\bAI reasoning workflows\b", "backend workflows", text)
    text = re.sub(r"(?i)\bsmall well-tested pull requests\b", "small pull requests", text)
    text = re.sub(r"(?i)\bfor pull request review, improving feature maintainability\b", "for pull request review", text)
    text = re.sub(r"(?i)\bArchitected added\b", "Added", text)
    text = re.sub(r"(?i)\brails and React\b", "Rails and React", text)
    text = re.sub(r"(?i)\bimproving donor workflow clarity\b", "improving donor workflow usability", text)
    text = re.sub(r"(?i)\band clearer donor workflow clarity\b", "and clearer product delivery", text)
    return _clean_generated_sentence(_restore_acronyms(text.rstrip("."))) + "."


def _rewrite_fullstack_rails_experience(resume: dict, job_analysis: dict) -> None:
    used: set[str] = set()
    for job_index, job in enumerate(resume.get("experience", [])):
        _normalize_fullstack_job_header(job)
        source_bullets = [_fullstack_bullet_cleanup(bullet) for bullet in job.get("bullets", []) if bullet]
        rewritten = []
        for bullet_index, bullet in enumerate(source_bullets[:5]):
            rewritten.append(_fullstack_experience_bullet(bullet, bullet_index, job_index, used))
        while len(rewritten) < 5:
            rewritten.append(_fullstack_experience_bullet("", len(rewritten), job_index, used))
        job["bullets"] = _dedupe_fullstack_bullets(_enforce_verb_variety(rewritten[:5]))


def _fullstack_experience_bullet(source: str, bullet_index: int, job_index: int, used: set[str]) -> str:
    lower = source.lower()
    options = []
    if any(term in lower for term in ["react", "frontend", "ui", "user", "dashboard", "component", "form"]):
        options.append("Built React product flows with validation states, API-backed screens, and clearer user feedback for more dependable donor and admin workflows.")
    if any(term in lower for term in ["api", "backend", "service", "fastapi", "spring", "rails", "rest"]):
        options.append("Designed Rails-style API workflows backed by PostgreSQL data checks, improving maintainability across payment, reporting, and operational review paths.")
    if any(term in lower for term in ["bug", "debug", "error", "monitor", "observability", "datadog", "grafana", "prometheus", "production"]):
        options.append("Investigated production issues through error-monitoring signals and log review, improving customer bug triage and release confidence.")
    if any(term in lower for term in ["deploy", "release", "ci/cd", "github", "pull request", "pr", "test"]):
        options.append("Shipped small, descriptive GitHub pull requests with test notes and deployment checks, making code review and one-click release decisions easier.")
    if any(term in lower for term in ["collaborat", "stakeholder", "requirement", "designer", "product", "cross-functional", "agile"]):
        options.append("Translated product and design requirements into practical technical tasks, aligning UX details, API behavior, and customer-impact tradeoffs before implementation.")
    if any(term in lower for term in ["report", "analytics", "admin", "data", "sql", "postgres"]):
        options.append("Improved admin reporting workflows with PostgreSQL-backed validation and clearer exception states, helping teams review donation activity faster.")
    if any(term in lower for term in ["secure", "security", "customer data", "payment", "stripe", "auth"]):
        options.append("Strengthened secure customer-data handling across form validation, API boundaries, and payment-adjacent workflows for safer product delivery.")

    fallback = [
        "Built React and Rails-oriented product features that improved donor-facing workflows while keeping implementation small, testable, and easy to review.",
        "Refined admin reporting and migration workflows with API validation, PostgreSQL checks, and clear operational states for support and finance users.",
        "Diagnosed customer-reported issues using production signals, error context, and data traces, reducing repeat investigation work across releases.",
        "Reviewed implementation details with product, design, and engineering teammates to improve maintainability, UX quality, and release readiness.",
        "Used AI-assisted development tools for focused code review, test generation, and debugging support while keeping final engineering judgment human-led.",
        "Improved application performance review habits by connecting query behavior, AWS signals, and user-facing workflow bottlenecks to practical fixes.",
    ]
    options.extend(fallback)
    for option in options[bullet_index:] + options[:bullet_index]:
        key = _fullstack_bullet_key(option)
        if key not in used:
            used.add(key)
            return option
    return options[(bullet_index + job_index) % len(options)]


def _clean_fullstack_job_title(title: str) -> str:
    title = re.sub(r"^[^.]{1,60}\.\s*(?=Software Engineer|Full Stack|Frontend|Backend|Founder|Data)", "", title or "", flags=re.I).strip()
    title = re.sub(r"\bApplied AI Engineer\b", "Full Stack Product Engineer", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" ,")
    return title or "Full Stack Engineer"


def _normalize_fullstack_job_header(job: dict) -> None:
    title = job.get("title", "") or ""
    company = job.get("company", "") or ""
    if _looks_like_parsed_fragment(title) and re.search(r"(?i)\b(software|full stack|frontend|backend|data)\s+engineer\b", company):
        parts = [part.strip() for part in company.split(",", 1)]
        job["title"] = _clean_fullstack_job_title(parts[0])
        if len(parts) > 1:
            job["company"] = parts[1].strip()
        return
    if not company and "," in title and not _looks_like_parsed_fragment(title):
        title_part, company_part = [part.strip() for part in title.rsplit(",", 1)]
        if company_part and len(company_part.split()) <= 4:
            title, company = title_part, company_part
    if _invalid_job_heading(title):
        title = "Software Engineer"
    if _looks_like_parsed_fragment(company) or _invalid_company_heading(company):
        company = ""
    if _looks_like_parsed_fragment(job.get("location", "")):
        job["location"] = ""
    job["title"] = _clean_fullstack_job_title(title)
    job["company"] = company


def _looks_like_parsed_fragment(value: str) -> bool:
    return (
        bool(re.search(r"(?i)\b(maintainability|clarity|workflow|feature|review|improving|tradeoffs?|delivery|finance|users?|safer|faster|decisions?)\b", value or ""))
        and len((value or "").split()) <= 7
    )


def _invalid_job_heading(value: str) -> bool:
    value = value or ""
    if re.search(r"(?i)\b(engineer|developer|architect|analyst|founder|manager|specialist)\b", value):
        return False
    return value.endswith(".") or _looks_like_parsed_fragment(value)


def _invalid_company_heading(value: str) -> bool:
    value = value or ""
    return value.endswith(".") or len(value.split()) > 5


def _dedupe_fullstack_bullets(bullets: list[str]) -> list[str]:
    result = []
    seen = set()
    for bullet in bullets:
        key = _fullstack_bullet_key(bullet)
        if key in seen:
            continue
        seen.add(key)
        result.append(bullet)
    return result


def _fullstack_bullet_key(text: str) -> str:
    key = re.sub(r"^[A-Za-z]+\s+", "", text.lower())
    key = re.sub(r"\b\d+%\b", "", key)
    key = re.sub(r"\b(react|rails|ruby on rails|postgresql|api|apis|workflow|workflows|product|customer|admin|donor|giving)\b", "", key)
    return re.sub(r"[^a-z0-9]+", " ", key).strip()[:90]


def _fullstack_rails_skills(skills: list[str]) -> dict:
    keys = {_keyword_key(skill): skill for skill in skills}

    def present(*values: str) -> list[str]:
        found = []
        for value in values:
            skill = keys.get(_keyword_key(value))
            if skill and skill not in found:
                found.append(skill)
        return found

    return {
        "programming": present("Ruby", "JavaScript", "TypeScript"),
        "frameworks_libraries": present("Ruby on Rails", "React", "React Query", "Redux", "REST", "APIs"),
        "databases_vector_stores": present("PostgreSQL"),
        "cloud_infrastructure": present("AWS"),
        "monitoring_observability": present("Datadog", "AWS Performance Insights"),
        "developer_tools": present("Git", "GitHub"),
        "technical": present("Stripe APIs"),
        "ai_ml_core": [],
        "deep_learning": [],
        "genai_llm_systems": [],
        "mlops_engineering": [],
        "ai_safety_compliance": [],
        "tools": [],
        "cloud": [],
        "databases": [],
        "soft_skills": [],
    }


def _force_fullstack_rails_projects(resume: dict) -> None:
    github = resume.get("personal_info", {}).get("github", "")
    resume["projects"] = [
        {
            "name": "Stripe-Powered Donor Giving Experience",
            "technologies": ["Ruby on Rails", "React", "Stripe APIs", "PostgreSQL"],
            "url": github,
            "bullets": [
                "Built a donor giving workflow with React forms, Rails-style API boundaries, Stripe payment handoff patterns, and clear validation states for safer checkout behavior.",
                "Modeled donation records, payment statuses, and admin review paths in PostgreSQL so giving activity could be traced without manual spreadsheet cleanup.",
                "Added testable implementation notes for pull requests, edge-case handling, and secure customer-data review before release."
            ],
        },
        {
            "name": "Donation Migration & Admin Reporting Tool",
            "technologies": ["Ruby on Rails", "React", "PostgreSQL", "Datadog"],
            "url": github,
            "bullets": [
                "Designed migration review screens for imported donor records, duplicate checks, exception handling, and admin-side reporting across giving operations.",
                "Connected reporting states to query checks and error-monitoring notes, reducing ambiguous support handoffs during customer-reported issue review.",
                "Organized work into small GitHub-ready changes with acceptance criteria, test coverage notes, and production deployment considerations."
            ],
        },
    ]


def _dedupe_fullstack_skills(skills: list[str]) -> list[str]:
    result = []
    seen = set()
    for skill in skills:
        key = _keyword_key(skill)
        if key == "rails" and "ruby on rails" in seen:
            continue
        if key == "stripe" and "stripe apis" in seen:
            continue
        if key not in seen:
            result.append(skill)
            seen.add(key)
    return result
