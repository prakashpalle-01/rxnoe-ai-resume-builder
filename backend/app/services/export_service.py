from io import BytesIO
from html import escape
import re
from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_pdf(resume: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, rightMargin=48, leftMargin=48, topMargin=34, bottomMargin=34)
    styles = _pdf_styles()
    story = []
    p = resume.get("personal_info", {})
    story.append(Paragraph(f"<b>{_safe(p.get('name') or 'Resume')}</b>", styles["ResumeName"]))
    if resume.get("target_title"):
        story.append(Paragraph(f"<b>{_safe(resume.get('target_title'))}</b>", styles["ResumeTitle"]))
    contact = " | ".join(filter(None, [p.get("email"), p.get("phone"), p.get("location"), p.get("linkedin"), p.get("github"), p.get("portfolio")]))
    story.append(Paragraph(_safe(contact), styles["Contact"]))
    story.append(Spacer(1, 7))

    _pdf_section(story, styles, "Summary")
    story.append(Paragraph(_safe(resume.get("summary", "")), styles["Body"]))

    skill_lines = _skill_lines(resume)
    if skill_lines:
        _pdf_section(story, styles, "Technical Skills")
        for label, values in skill_lines:
            story.append(Paragraph(f"<b>{_safe(label)}:</b> {_safe(', '.join(values))}", styles["SkillLine"]))

    if resume.get("experience"):
        _pdf_section(story, styles, "Experience")
        bullet_counter = 0
        for job in resume.get("experience", []):
            title = job.get("title") or "Role"
            company = job.get("company", "")
            dates = " - ".join(filter(None, [job.get("start_date"), job.get("end_date")]))
            header = f"<b>{_safe(title)}{', ' if company else ''}{_safe(company)}</b>"
            if dates:
                header += f" <font color='#475569'>{_safe(dates)}</font>"
            story.append(Paragraph(header, styles["ItemHeader"]))
            for bullet in job.get("bullets", []):
                story.append(Paragraph(_bullet_html(bullet, resume, bullet_counter), styles["ResumeBullet"], bulletText="•"))
                bullet_counter += 1
            story.append(Spacer(1, 3))

    if resume.get("projects"):
        _pdf_section(story, styles, "Projects")
        bullet_counter = 0
        for project in resume.get("projects", []):
            detail = " | ".join(filter(None, [", ".join(project.get("technologies", [])), project.get("url", "")]))
            header = f"<b>{_safe(project.get('name') or 'Project')}</b>"
            if detail:
                header += f" <font color='#475569'>{_safe(detail)}</font>"
            story.append(Paragraph(header, styles["ItemHeader"]))
            for bullet in project.get("bullets", []):
                story.append(Paragraph(_bullet_html(bullet, resume, bullet_counter, project=True), styles["ResumeBullet"], bulletText="•"))
                bullet_counter += 1
            story.append(Spacer(1, 3))

    _pdf_simple_list(story, styles, "Education", resume.get("education", []))
    _pdf_simple_list(story, styles, "Certifications", resume.get("certifications", []))
    doc.build(story)
    return buffer.getvalue()


def build_docx(resume: dict) -> bytes:
    doc = Document()
    for section in doc.sections:
        section.top_margin = Pt(36)
        section.bottom_margin = Pt(36)
        section.left_margin = Pt(54)
        section.right_margin = Pt(54)
    styles = doc.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(10)
    p = resume.get("personal_info", {})
    doc.add_heading(p.get("name") or "Resume", level=0)
    if resume.get("target_title"):
        role = doc.add_paragraph()
        role.add_run(resume.get("target_title")).bold = True
    doc.add_paragraph(" | ".join(filter(None, [p.get("email"), p.get("phone"), p.get("location"), p.get("linkedin"), p.get("github"), p.get("portfolio")])))
    _docx_section(doc, "Summary", [resume.get("summary", "")])
    skills = [f"{label}: {', '.join(values)}" for label, values in _skill_lines(resume)]
    _docx_section(doc, "Skills", skills)
    if resume.get("experience"):
        doc.add_heading("Experience", level=1)
    for job in resume.get("experience", []):
        doc.add_paragraph(f"{job.get('title', '')}, {job.get('company', '')} {job.get('start_date', '')} - {job.get('end_date', '')}")
        for bullet in job.get("bullets", []):
            doc.add_paragraph(bullet, style="List Bullet")
    if resume.get("projects"):
        doc.add_heading("Projects", level=1)
    for project in resume.get("projects", []):
        detail = " | ".join(filter(None, [", ".join(project.get("technologies", [])), project.get("url", "")]))
        doc.add_paragraph(f"{project.get('name', '')} | {detail}")
        for bullet in project.get("bullets", []):
            doc.add_paragraph(bullet, style="List Bullet")
    _docx_section(doc, "Education", resume.get("education", []))
    _docx_section(doc, "Certifications", resume.get("certifications", []))
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _pdf_styles() -> dict:
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name="ResumeName",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        alignment=TA_CENTER,
        spaceAfter=2,
        textColor=colors.HexColor("#0f172a"),
    ))
    base.add(ParagraphStyle(
        name="ResumeTitle",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#334155"),
        spaceAfter=2,
    ))
    base.add(ParagraphStyle(
        name="Contact",
        parent=base["Normal"],
        fontSize=8.6,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
    ))
    base.add(ParagraphStyle(
        name="SectionHeading",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.4,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        borderColor=colors.HexColor("#cbd5e1"),
        spaceBefore=7,
        spaceAfter=4,
        borderWidth=0.25,
        borderPadding=1,
    ))
    base.add(ParagraphStyle(name="Body", parent=base["Normal"], fontSize=9.3, leading=12.2, spaceAfter=3))
    base.add(ParagraphStyle(name="SkillLine", parent=base["Normal"], fontSize=9, leading=11.5, spaceAfter=1.6))
    base.add(ParagraphStyle(name="ItemHeader", parent=base["Normal"], fontSize=9.4, leading=11.8, spaceBefore=2.5, spaceAfter=1.5))
    base.add(ParagraphStyle(
        name="ResumeBullet",
        parent=base["Normal"],
        fontSize=9,
        leading=11.4,
        leftIndent=13,
        firstLineIndent=-7,
        bulletIndent=2,
        spaceAfter=1.8,
    ))
    return base


def _pdf_section(story, styles, title: str) -> None:
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>{_safe(title.upper())}</b>", styles["SectionHeading"]))


def _pdf_simple_list(story, styles, title: str, lines: list[str]) -> None:
    lines = [line for line in lines if line]
    if not lines:
        return
    _pdf_section(story, styles, title)
    for line in lines:
        story.append(Paragraph(_safe(line), styles["Body"]))


def _skill_lines(resume: dict) -> list[tuple[str, list[str]]]:
    ordered = []
    for group, values in resume.get("skills", {}).items():
        clean_values = [value for value in values if value]
        if clean_values:
            ordered.append((_skill_label(group), clean_values))
    return ordered


def _safe(value: str) -> str:
    return escape(str(value or ""), quote=False)


def _rich_safe(value: str) -> str:
    parts = re.split(r"(\*\*[^*]+\*\*)", str(value or ""))
    rendered = []
    for part in parts:
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            rendered.append(f"<b>{escape(part[2:-2], quote=False)}</b>")
        else:
            rendered.append(escape(part, quote=False))
    return "".join(rendered)


def _bullet_html(value: str, resume: dict, index: int, project: bool = False) -> str:
    text = str(value or "")
    if "**" in text:
        return _rich_safe(text)
    phrase = _metric_phrase(text)
    if not phrase and (index % 2 == 0 or project):
        phrase = _keyword_phrase(text, resume.get("target_keywords", []))
    if not phrase:
        return _safe(text)
    location = text.lower().find(phrase.lower())
    if location < 0:
        return _safe(text)
    return "".join([
        _safe(text[:location]),
        f"<b>{_safe(text[location:location + len(phrase)])}</b>",
        _safe(text[location + len(phrase):]),
    ])


def _metric_phrase(text: str) -> str:
    match = re.search(r"\b(?:reduced|improved|increased|cut|shortened|accelerated|processed|saved|lowered|raised)[^.;,]*?\b\d+%|\b\d+[%x]\b", text, re.I)
    return match.group(0) if match else ""


def _keyword_phrase(text: str, keywords: list[str]) -> str:
    blocked = {
        "associate", "stack", "product", "skills", "required", "preferred", "development",
        "software", "systems", "team", "business", "technical", "technology", "platform",
        "solution", "engineer", "engineering", "developer", "role", "work", "working",
        "collaboration", "communication", "stakeholder",
    }
    priority = [
        "Ruby on Rails", "React", "Stripe APIs", "Stripe", "PostgreSQL", "Datadog",
        "AWS Performance Insights", "AWS", "GitHub", "customer-data", "admin reporting",
        "donor", "donation", "payment", "Rails",
    ]
    candidates = priority + [keyword for keyword in keywords if keyword]
    seen = set()
    for keyword in sorted(candidates, key=len, reverse=True):
        clean = keyword.strip()
        key = clean.lower()
        if not clean or key in seen or key in blocked or len(clean) < 4:
            continue
        seen.add(key)
        pattern = re.compile(rf"(?<![A-Za-z0-9+#./-]){re.escape(clean)}(?![A-Za-z0-9+#./-])", re.I)
        match = pattern.search(text)
        if match:
            return text[match.start():match.end()]
    return ""


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
