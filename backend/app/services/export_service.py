from io import BytesIO
from docx import Document
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_pdf(resume: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=54, leftMargin=54, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    story = []
    p = resume.get("personal_info", {})
    story.append(Paragraph(f"<b>{p.get('name') or 'Resume'}</b>", styles["Title"]))
    if resume.get("target_title"):
        story.append(Paragraph(f"<b>{resume.get('target_title')}</b>", styles["Normal"]))
    contact = " | ".join(filter(None, [p.get("email"), p.get("phone"), p.get("location"), p.get("linkedin"), p.get("github"), p.get("portfolio")]))
    story.append(Paragraph(contact, styles["Normal"]))
    _section(story, styles, "Summary", [resume.get("summary", "")])
    skills = []
    for group, values in resume.get("skills", {}).items():
        if values:
            skills.append(f"<b>{_skill_label(group)}:</b> {', '.join(values)}")
    _section(story, styles, "Skills", skills)
    for job in resume.get("experience", []):
        header = f"<b>{job.get('title', '')}{', ' if job.get('title') and job.get('company') else ''}{job.get('company', '')}</b> {job.get('start_date', '')} - {job.get('end_date', '')}"
        _section(story, styles, "Experience", [header] + [f"- {bullet}" for bullet in job.get("bullets", [])])
    for project in resume.get("projects", []):
        detail = " | ".join(filter(None, [", ".join(project.get("technologies", [])), project.get("url", "")]))
        header = f"<b>{project.get('name', '')}</b> {detail}"
        _section(story, styles, "Projects", [header] + [f"- {bullet}" for bullet in project.get("bullets", [])])
    _section(story, styles, "Education", resume.get("education", []))
    _section(story, styles, "Certifications", resume.get("certifications", []))
    doc.build(story)
    return buffer.getvalue()


def build_docx(resume: dict) -> bytes:
    doc = Document()
    p = resume.get("personal_info", {})
    doc.add_heading(p.get("name") or "Resume", level=0)
    if resume.get("target_title"):
        doc.add_paragraph(resume.get("target_title"))
    doc.add_paragraph(" | ".join(filter(None, [p.get("email"), p.get("phone"), p.get("location"), p.get("linkedin"), p.get("github"), p.get("portfolio")])))
    _docx_section(doc, "Summary", [resume.get("summary", "")])
    skills = [f"{_skill_label(group)}: {', '.join(values)}" for group, values in resume.get("skills", {}).items() if values]
    _docx_section(doc, "Skills", skills)
    for job in resume.get("experience", []):
        doc.add_heading("Experience", level=1)
        doc.add_paragraph(f"{job.get('title', '')}, {job.get('company', '')} {job.get('start_date', '')} - {job.get('end_date', '')}")
        for bullet in job.get("bullets", []):
            doc.add_paragraph(bullet, style="List Bullet")
    for project in resume.get("projects", []):
        doc.add_heading("Projects", level=1)
        detail = " | ".join(filter(None, [", ".join(project.get("technologies", [])), project.get("url", "")]))
        doc.add_paragraph(f"{project.get('name', '')} | {detail}")
        for bullet in project.get("bullets", []):
            doc.add_paragraph(bullet, style="List Bullet")
    _docx_section(doc, "Education", resume.get("education", []))
    _docx_section(doc, "Certifications", resume.get("certifications", []))
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _section(story, styles, title: str, lines: list[str]) -> None:
    lines = [line for line in lines if line]
    if not lines:
        return
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>{title.upper()}</b>", styles["Heading2"]))
    for line in lines:
        story.append(Paragraph(line, styles["Normal"]))


def _docx_section(doc: Document, title: str, lines: list[str]) -> None:
    lines = [line for line in lines if line]
    if not lines:
        return
    doc.add_heading(title, level=1)
    for line in lines:
        doc.add_paragraph(line)


def _skill_label(value: str) -> str:
    labels = {
        "ai_ml_core": "AI / ML Core",
        "deep_learning": "Deep Learning",
        "genai_llm_systems": "GenAI & Advanced LLM Systems",
        "frameworks_libraries": "Frameworks & Libraries",
        "mlops_engineering": "MLOps & ML Engineering",
        "cloud_infrastructure": "Cloud & Infrastructure",
        "databases_vector_stores": "Databases & Vector Stores",
        "programming": "Programming",
        "monitoring_observability": "Monitoring & Observability",
        "ai_safety_compliance": "AI Safety, Privacy & Compliance",
        "developer_tools": "Developer & Productivity Tools",
        "technical": "Additional Technical Skills",
        "tools": "Tools",
        "cloud": "Cloud",
        "databases": "Databases",
        "soft_skills": "Professional Skills",
    }
    return labels.get(value, value.replace("_", " ").title())
