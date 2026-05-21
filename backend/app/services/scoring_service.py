import re
from .ai_service import analyze_job_description


def score_resume(resume: dict, raw_text: str, job_description: str) -> dict:
    analysis = analyze_job_description(job_description)
    keywords = analysis["keywords"]
    resume_text = " ".join([raw_text, str(resume)]).lower()
    matched = [word for word in keywords if word.lower() in resume_text]
    missing = [word for word in keywords if word.lower() not in resume_text]
    keyword_score = _percent(len(matched), max(len(keywords), 1))
    skills_score = _clamp(keyword_score + 10 if _skills_count(resume) >= 8 else keyword_score - 10)
    experience_score = _experience_score(resume)
    title_score = _title_score(resume, analysis.get("job_title", ""))
    project_score = 80 if resume.get("projects") else 45
    formatting_score, formatting_warnings = _formatting_score(raw_text, resume)
    readability_score = _readability_score(raw_text)
    overall = round((keyword_score * 0.25) + (skills_score * 0.18) + (experience_score * 0.18) + (title_score * 0.12) + (project_score * 0.1) + (formatting_score * 0.1) + (readability_score * 0.07))
    warnings = formatting_warnings + _quality_warnings(resume, missing, overall)
    return {
        "overall_score": overall,
        "keyword_match_score": _clamp(keyword_score),
        "skills_match_score": skills_score,
        "experience_match_score": experience_score,
        "title_relevance_score": title_score,
        "project_relevance_score": project_score,
        "formatting_score": formatting_score,
        "readability_score": readability_score,
        "missing_keywords": missing[:15],
        "matched_keywords": matched[:20],
        "confirm_before_adding": _confirm_before_adding(missing, resume),
        "metric_prompts": _metric_prompts(resume),
        "project_suggestions": _project_suggestions(missing, analysis),
        "warnings": warnings,
        "recruiter_view": _recruiter_view(resume, matched, missing)
    }


def _percent(value: int, total: int) -> int:
    return int(round((value / total) * 100))


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def _skills_count(resume: dict) -> int:
    skills = resume.get("skills", {})
    return sum(len(values) for values in skills.values() if isinstance(values, list))


def _experience_score(resume: dict) -> int:
    bullets = [bullet for job in resume.get("experience", []) for bullet in job.get("bullets", [])]
    if not bullets:
        return 35
    strong = sum(1 for bullet in bullets if len(bullet.split()) >= 8 and re.search(r"\b(built|developed|improved|created|designed|implemented|analyzed|automated|reduced|increased)\b", bullet, re.I))
    return min(95, 45 + strong * 10)


def _title_score(resume: dict, job_title: str) -> int:
    if not job_title:
        return 70
    titles = " ".join([resume.get("target_title", "")] + [job.get("title", "") for job in resume.get("experience", [])]).lower()
    overlap = set(job_title.lower().split()) & set(titles.split())
    return min(95, 45 + len(overlap) * 20)


def _formatting_score(raw_text: str, resume: dict) -> tuple[int, list[str]]:
    warnings = []
    score = 92
    required = ["summary", "skills", "experience"]
    for section in required:
        if not resume.get(section):
            score -= 14
            warnings.append(f"Your resume is missing a clear {section} section.")
    if "|" in raw_text and raw_text.count("|") > 20:
        score -= 12
        warnings.append("Your resume may use tables or columns that can confuse ATS systems.")
    if len(raw_text.split()) > 1100:
        score -= 8
        warnings.append("Your resume may be too long for a fast recruiter scan.")
    if len(raw_text.split("\n\n")) < 3:
        score -= 6
        warnings.append("Your section spacing may be hard to scan.")
    return max(20, score), warnings


def _readability_score(raw_text: str) -> int:
    sentences = re.split(r"[.!?]", raw_text)
    avg = sum(len(sentence.split()) for sentence in sentences) / max(len(sentences), 1)
    if avg <= 18:
        return 88
    if avg <= 26:
        return 74
    return 58


def _quality_warnings(resume: dict, missing: list[str], overall: int) -> list[str]:
    warnings = []
    summary = resume.get("summary", "")
    if len(summary.split()) < 18:
        warnings.append("Your summary is too generic or too short.")
    bullets = [bullet for job in resume.get("experience", []) for bullet in job.get("bullets", [])]
    if bullets and not any(re.search(r"\d|%|\$|reduced|increased|improved", bullet, re.I) for bullet in bullets):
        warnings.append("Your bullets lack measurable impact. Add real metrics where you know them.")
    if _skills_count(resume) > 35:
        warnings.append("Your skills section has too many unrelated skills.")
    if len(missing) > 8:
        warnings.append("Your resume does not match this job description closely enough yet.")
    if not resume.get("projects"):
        warnings.append("Your project section is weak for this role.")
    if overall < 60:
        warnings.append("Your resume may fail ATS because of missing keywords or formatting issues.")
    return warnings


def _recruiter_view(resume: dict, matched: list[str], missing: list[str]) -> list[str]:
    latest = resume.get("experience", [{}])[0] if resume.get("experience") else {}
    headline = resume.get("target_title") or latest.get("title") or "Add a clear target title near the top."
    return [
        f"Job title clarity: {headline}",
        f"Top skills visible: {', '.join(matched[:6]) if matched else 'Add role-specific skills.'}",
        f"Recent experience: {latest.get('company') or 'Make your most recent company and role easy to scan.'}",
        "Measurable impact: add real numbers where you can prove them.",
        f"Red flags: {', '.join(missing[:4]) if missing else 'No major keyword gaps found.'}"
    ]


def _confirm_before_adding(missing: list[str], resume: dict) -> list[str]:
    if not missing:
        return []
    return [
        f"Can you honestly claim {keyword}? If yes, add where you used it: job, project, coursework, certification, or personal build."
        for keyword in missing[:10]
    ]


def _metric_prompts(resume: dict) -> list[str]:
    prompts = []
    for job in resume.get("experience", [])[:3]:
        label = job.get("title") or job.get("company") or "this role"
        for bullet in job.get("bullets", [])[:2]:
            if not re.search(r"\d|%|\$|reduced|increased|improved|faster|hours|minutes", bullet, re.I):
                prompts.append(f"For {label}: what changed after this work? Time saved, users supported, defects reduced, reports automated, latency improved, or manual steps removed?")
    return prompts[:6]


def _project_suggestions(missing: list[str], analysis: dict) -> list[str]:
    text = " ".join(missing + analysis.get("keywords", [])).lower()
    suggestions = []
    if any(word in text for word in ["llm", "rag", "machine learning", "ai"]):
        suggestions.append("AI Engineer project: build a RAG document assistant with chunking, embeddings, retrieval, evaluation notes, and a clean API.")
    if any(word in text for word in ["react", "typescript", "frontend"]):
        suggestions.append("Frontend project: build a TypeScript React dashboard that consumes APIs, handles loading/error states, and includes reusable components.")
    if any(word in text for word in ["aws", "docker", "kubernetes", "ci/cd", "cloud"]):
        suggestions.append("Cloud/DevOps project: containerize an API, add CI/CD, deploy to cloud, and document monitoring, rollback, and environment configuration.")
    if any(word in text for word in ["sql", "postgresql", "data", "analytics", "tableau", "power bi"]):
        suggestions.append("Data project: create a SQL analytics workflow with cleaned datasets, KPI queries, dashboard visuals, and business recommendations.")
    if any(word in text for word in ["java", "spring boot", "microservices", "kafka"]):
        suggestions.append("Backend project: build a Spring Boot microservice with PostgreSQL, Kafka/event flow, tests, and API documentation.")
    return suggestions[:5]
