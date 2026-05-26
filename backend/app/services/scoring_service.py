import re
from .ai_service import analyze_job_description


def score_resume(resume: dict, raw_text: str, job_description: str) -> dict:
    analysis = analyze_job_description(job_description)
    keywords = analysis["keywords"]
    resume_text = _resume_content_text(resume)
    matched = [word for word in keywords if word.lower() in resume_text]
    missing = [word for word in keywords if word.lower() not in resume_text]
    if _is_generated_targeted(resume):
        unverified = resume.get("unverified_job_keywords", [])
        unverified_keys = {item.lower() for item in unverified}
        matched = [word for word in matched if word.lower() not in unverified_keys]
        missing = _unique_words(missing + [word for word in keywords if word.lower() in unverified_keys])
    keyword_score = _percent(len(matched), max(len(keywords), 1))
    skills_score = _clamp(keyword_score + 10 if _skills_count(resume) >= 8 else keyword_score - 10)
    experience_score = _experience_score(resume)
    title_score = _title_score(resume, analysis.get("job_title", ""))
    project_score = 80 if resume.get("projects") else 45
    formatting_score, formatting_warnings = _formatting_score(resume_text, resume)
    readability_score = _readability_score(resume_text)
    realism_score, realism_warnings = _recruiter_realism_score(resume, analysis, job_description)
    overall = round((keyword_score * 0.25) + (skills_score * 0.18) + (experience_score * 0.18) + (title_score * 0.12) + (project_score * 0.1) + (formatting_score * 0.1) + (readability_score * 0.07))
    warnings = formatting_warnings + _quality_warnings(resume, missing, overall) + realism_warnings
    result = {
        "overall_score": overall,
        "keyword_match_score": _clamp(keyword_score),
        "skills_match_score": skills_score,
        "experience_match_score": experience_score,
        "title_relevance_score": title_score,
        "project_relevance_score": project_score,
        "formatting_score": formatting_score,
        "readability_score": readability_score,
        "recruiter_realism_score": realism_score,
        "missing_keywords": missing[:15],
        "matched_keywords": matched[:20],
        "confirm_before_adding": _confirm_before_adding(missing, resume),
        "metric_prompts": _metric_prompts(resume),
        "project_suggestions": _project_suggestions(missing, analysis),
        "warnings": warnings,
        "recruiter_view": _recruiter_view(resume, matched, missing),
        "recruiter_decision": _recruiter_decision(overall, missing),
    }
    if _is_generated_targeted(resume):
        return _generated_targeted_score(result, missing)
    return result


def _percent(value: int, total: int) -> int:
    return int(round((value / total) * 100))


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def _unique_words(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _is_generated_targeted(resume: dict) -> bool:
    return resume.get("optimization_status") == "generated_targeted" or resume.get("score_target") == 100


def _generated_targeted_score(result: dict, unsupported: list[str]) -> dict:
    if not unsupported:
        result.update({
            "overall_score": 100,
            "keyword_match_score": 100,
            "skills_match_score": 100,
            "title_relevance_score": 100,
            "project_relevance_score": 100,
            "formatting_score": 100,
            "readability_score": 100,
        })
        result["warnings"] = [
            "100 ATS alignment means all extracted requirements are represented in the confirmed resume content; it does not guarantee recruiter selection or an interview."
        ]
        result["recruiter_decision"] = _recruiter_decision(100, [])
        return result
    note = "Generated resume is formatted and targeted for this role; the score remains evidence-based."
    note += " Confirm missing skills before adding them."
    result["warnings"] = [note] + result.get("warnings", [])
    result["recruiter_decision"] = _recruiter_decision(result.get("overall_score", 0), unsupported)
    return result


def _recruiter_decision(score: int, missing: list[str]) -> dict:
    if not missing and score >= 85:
        return {
            "status": "Ready for recruiter review",
            "reason": "The resume is strongly aligned and no major extracted skill gaps remain. Verify every project and metric before applying.",
        }
    if score >= 75:
        gap_text = ", ".join(missing[:4]) if missing else "remaining role-specific evidence"
        return {
            "status": "Competitive with gaps",
            "reason": f"The resume is readable and targeted, but a recruiter may screen for evidence of {gap_text}. Add only truthful proof.",
        }
    gap_text = ", ".join(missing[:5]) if missing else "core role evidence"
    return {
        "status": "Not ready for this role",
        "reason": f"The job requires evidence not clearly supported by the resume: {gap_text}. Tailoring wording alone cannot solve this gap.",
    }


def _skills_count(resume: dict) -> int:
    skills = resume.get("skills", {})
    return sum(len(values) for values in skills.values() if isinstance(values, list))


def _resume_content_text(resume: dict) -> str:
    parts = [resume.get("target_title", ""), resume.get("summary", "")]
    skills = resume.get("skills", {})
    for values in skills.values():
        if isinstance(values, list):
            parts.extend(values)
    for job in resume.get("experience", []):
        parts.extend([job.get("title", ""), job.get("company", ""), job.get("location", "")])
        parts.extend(job.get("bullets", []))
    for project in resume.get("projects", []):
        parts.extend([project.get("name", ""), project.get("url", "")])
        parts.extend(project.get("technologies", []))
        parts.extend(project.get("bullets", []))
    parts.extend(resume.get("education", []))
    parts.extend(resume.get("certifications", []))
    return " ".join(str(part) for part in parts if part).lower()


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
    return max(20, score), warnings


def _readability_score(raw_text: str) -> int:
    sentences = re.split(r"[.!?]", raw_text)
    avg = sum(len(sentence.split()) for sentence in sentences) / max(len(sentences), 1)
    if avg <= 18:
        return 88
    if avg <= 26:
        return 74
    return 58


def _recruiter_realism_score(resume: dict, analysis: dict, job_description: str) -> tuple[int, list[str]]:
    warnings = []
    score = 94
    bullets = [bullet for job in resume.get("experience", []) for bullet in job.get("bullets", [])]
    bullets.extend([bullet for project in resume.get("projects", []) for bullet in project.get("bullets", [])])
    verbs = [re.match(r"^([A-Za-z]+)\b", bullet).group(1).lower() for bullet in bullets if re.match(r"^([A-Za-z]+)\b", bullet)]
    repeated = {verb for verb in verbs if verbs.count(verb) > 2}
    if repeated:
        score -= 10
        warnings.append(f"Recruiter realism: repeated action verbs detected ({', '.join(sorted(repeated)[:3])}).")
    if _keyword_stuffing_ratio(resume) > 0.22:
        score -= 12
        warnings.append("Recruiter realism: resume may feel keyword-heavy. Keep technologies tied to work and impact.")
    copied = _copied_job_phrases(resume, job_description)
    if copied:
        score -= 14
        warnings.append("Recruiter realism: some wording appears copied from the job description. Paraphrase it into your own engineering impact.")
    if _overstated_title(resume, analysis):
        score -= 12
        warnings.append("Recruiter realism: target title may overstate architecture or leadership scope for the visible experience.")
    if bullets and not any(re.search(r"\b(reduced|improved|automated|supported|enabled|increased|accelerated|simplified|stabilized|saved)\b", bullet, re.I) for bullet in bullets):
        score -= 8
        warnings.append("Recruiter realism: bullets need clearer business or operational impact.")
    return _clamp(score), warnings[:5]


def _keyword_stuffing_ratio(resume: dict) -> float:
    text = _resume_content_text(resume)
    words = re.findall(r"\b[A-Za-z][A-Za-z+#./-]*\b", text)
    if not words:
        return 0
    techish = [word for word in words if re.search(r"[A-Z+#./-]", word) or word.lower() in {"python", "react", "docker", "kubernetes", "terraform", "postgresql", "fastapi", "aws", "sql"}]
    return len(techish) / len(words)


def _copied_job_phrases(resume: dict, job_description: str) -> list[str]:
    resume_text = _resume_content_text(resume)
    jd_words = re.findall(r"[A-Za-z0-9+#./-]+", job_description.lower())
    copied = []
    for size in range(8, 4, -1):
        for index in range(0, max(len(jd_words) - size + 1, 0)):
            phrase = " ".join(jd_words[index:index + size])
            if len(phrase) > 24 and phrase in resume_text:
                copied.append(phrase)
                if len(copied) >= 3:
                    return copied
    return copied


def _overstated_title(resume: dict, analysis: dict) -> bool:
    title = (resume.get("target_title") or analysis.get("job_title") or "").lower()
    if not re.search(r"\b(principal|staff|lead|architect)\b", title):
        return False
    text = _resume_content_text(resume)
    return not re.search(r"\b(led|owned|architected|stakeholder|roadmap|mentored|governance|architecture|integration)\b", text)


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
