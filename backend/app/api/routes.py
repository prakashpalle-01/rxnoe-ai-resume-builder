from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.models import ApplicationTracker, AtsScore, CoverLetter, InterviewQuestion, JobDescription, KeywordAnalysis, ParsedResume, ResumeVersion, UploadedResume, User
from app.schemas.schemas import ApplicationCreate, ApplicationOut, AtsScoreRequest, AuthRequest, CoverLetterRequest, InterviewRequest, JobAnalyzeRequest, JobRankRequest, OptimizeRequest, ResumeOut, ResumeUpdate, ResumeVersionOut, TokenResponse
from app.services.ai_service import analyze_job_description, generate_cover_letter, generate_interview_questions, optimize_resume, parse_resume
from app.services.export_service import build_docx, build_pdf
from app.services.file_service import extract_text, remove_file, save_upload
from app.services.scoring_service import score_resume

router = APIRouter()


@router.post("/auth/signup", response_model=TokenResponse)
def signup(payload: AuthRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")
    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: AuthRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/resumes/upload", response_model=ResumeOut)
def upload_resume(file: UploadFile, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    path = save_upload(file, user.id)
    raw_text = extract_text(path)
    resume = UploadedResume(user_id=user.id, title=(file.filename or "Resume").rsplit(".", 1)[0], filename=file.filename or "resume", file_path=path, raw_text=raw_text, parsed_json={})
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes", response_model=list[ResumeOut])
def list_resumes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(UploadedResume).where(UploadedResume.user_id == user.id).order_by(UploadedResume.created_at.desc())).all()


@router.get("/resumes/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _resume_or_404(resume_id, user.id, db)


@router.put("/resumes/{resume_id}", response_model=ResumeOut)
def update_resume(resume_id: int, payload: ResumeUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(resume_id, user.id, db)
    resume.parsed_json = payload.parsed_json
    db.add(ResumeVersion(resume_id=resume.id, resume_json=payload.parsed_json, version_name="Manual Edit", change_summary="User edited structured resume JSON."))
    db.commit()
    db.refresh(resume)
    return resume


@router.delete("/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(resume_id, user.id, db)
    file_path = resume.file_path
    _delete_resume_dependents(resume.id, db)
    db.delete(resume)
    db.commit()
    still_used = db.scalar(select(UploadedResume.id).where(UploadedResume.file_path == file_path, UploadedResume.user_id == user.id))
    if not still_used:
        remove_file(file_path)
    return {"ok": True}


@router.post("/resumes/{resume_id}/parse", response_model=ResumeOut)
def parse_uploaded_resume(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(resume_id, user.id, db)
    parsed, confidence = parse_resume(resume.raw_text)
    resume.parsed_json = parsed
    resume.confidence = confidence
    db.add(ParsedResume(resume_id=resume.id, structured_json=parsed, confidence=confidence))
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/optimize", response_model=ResumeOut)
def optimize_uploaded_resume(resume_id: int, payload: OptimizeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(resume_id, user.id, db)
    optimized, summary = optimize_resume(resume.parsed_json, payload.instruction, payload.job_description)
    if _is_targeted_generation(payload):
        analysis = analyze_job_description(payload.job_description or "")
        target_title = analysis.get("job_title") or "Targeted Role"
        targeted = UploadedResume(
            user_id=user.id,
            title=f"{resume.title} - Targeted for {target_title}",
            filename=f"targeted-{resume.filename}",
            file_path=resume.file_path,
            raw_text=resume.raw_text,
            parsed_json=optimized,
            confidence=resume.confidence,
        )
        db.add(targeted)
        db.commit()
        db.refresh(targeted)
        db.add(ResumeVersion(resume_id=targeted.id, resume_json=resume.parsed_json, version_name="Before Optimization", change_summary="Original resume before job-description targeting."))
        db.add(ResumeVersion(resume_id=targeted.id, resume_json=optimized, version_name=payload.instruction, change_summary=summary))
        db.commit()
        db.refresh(targeted)
        return targeted
    db.add(ResumeVersion(resume_id=resume.id, resume_json=resume.parsed_json, version_name="Before Optimization", change_summary="Snapshot before AI edits."))
    resume.parsed_json = optimized
    db.add(ResumeVersion(resume_id=resume.id, resume_json=optimized, version_name=payload.instruction, change_summary=summary))
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes/{resume_id}/versions", response_model=list[ResumeVersionOut])
def resume_versions(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _resume_or_404(resume_id, user.id, db)
    return db.scalars(select(ResumeVersion).where(ResumeVersion.resume_id == resume_id).order_by(ResumeVersion.created_at.desc(), ResumeVersion.id.desc())).all()


@router.get("/resumes/{resume_id}/export/pdf")
@router.post("/resumes/{resume_id}/export/pdf")
def export_pdf(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(resume_id, user.id, db)
    return Response(content=build_pdf(resume.parsed_json), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="rxnoe-resume-{resume.id}.pdf"'})


@router.get("/resumes/{resume_id}/export/docx")
@router.post("/resumes/{resume_id}/export/docx")
def export_docx(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(resume_id, user.id, db)
    return Response(content=build_docx(resume.parsed_json), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="rxnoe-resume-{resume.id}.docx"'})


@router.post("/jobs/analyze")
def analyze_job(payload: JobAnalyzeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    analysis = analyze_job_description(payload.job_description)
    record = JobDescription(user_id=user.id, raw_text=payload.job_description, analysis_json=analysis)
    db.add(record)
    db.commit()
    return analysis


@router.post("/ats/score")
def ats_score(payload: AtsScoreRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(payload.resume_id, user.id, db)
    result = score_resume(resume.parsed_json, resume.raw_text, payload.job_description)
    db.add(AtsScore(resume_id=resume.id, score_json=result, overall_score=result["overall_score"]))
    db.commit()
    return result


@router.post("/jobs/rank")
def rank_jobs(payload: JobRankRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(payload.resume_id, user.id, db)
    posts = [post.strip() for post in payload.job_posts.split("\n---") if post.strip()]
    ranked = []
    for index, post in enumerate(posts[:20], start=1):
        first_line = next((line.strip() for line in post.splitlines() if line.strip()), f"Job {index}")
        result = score_resume(resume.parsed_json, resume.raw_text, post)
        ranked.append({
            "title": first_line[:120],
            "score": result["overall_score"],
            "matched_keywords": result["matched_keywords"][:10],
            "missing_keywords": result["missing_keywords"][:10],
            "recommendation": _job_recommendation(result["overall_score"])
        })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {
        "ranked_jobs": ranked,
        "search_links": _search_links(resume.parsed_json)
    }


@router.post("/cover-letter/generate")
def cover_letter(payload: CoverLetterRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resume = _resume_or_404(payload.resume_id, user.id, db) if payload.resume_id else None
    content = generate_cover_letter(resume.parsed_json if resume else {}, payload.job_description, payload.company, payload.tone)
    db.add(CoverLetter(user_id=user.id, resume_id=payload.resume_id, content=content))
    db.commit()
    return {"content": content}


@router.post("/interview/generate")
def interview(payload: InterviewRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    questions = generate_interview_questions(payload.job_description)
    db.add(InterviewQuestion(user_id=user.id, questions_json=questions))
    db.commit()
    return {"questions": questions}


@router.post("/applications", response_model=ApplicationOut)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ApplicationTracker(user_id=user.id, **payload.model_dump(exclude_none=True))
    if item.application_date is None:
        item.application_date = date.today()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/applications", response_model=list[ApplicationOut])
def applications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(ApplicationTracker).where(ApplicationTracker.user_id == user.id).order_by(ApplicationTracker.id.desc())).all()


def _resume_or_404(resume_id: int, user_id: int, db: Session) -> UploadedResume:
    resume = db.scalar(select(UploadedResume).where(UploadedResume.id == resume_id, UploadedResume.user_id == user_id))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return resume


def _delete_resume_dependents(resume_id: int, db: Session) -> None:
    for model in (ParsedResume, ResumeVersion, AtsScore, KeywordAnalysis, CoverLetter):
        db.execute(delete(model).where(model.resume_id == resume_id))


def _is_targeted_generation(payload: OptimizeRequest) -> bool:
    instruction = payload.instruction.lower()
    return bool(payload.job_description and ("targeted resume" in instruction or "job description" in instruction))


def _job_recommendation(score: int) -> str:
    if score >= 90:
        return "Excellent target. Apply with a tailored resume."
    if score >= 75:
        return "Strong target. Optimize keywords and apply."
    if score >= 60:
        return "Possible target. Close missing skill gaps first."
    return "Low fit. Use as a learning/project target before applying."


def _search_links(resume_json: dict) -> list[dict]:
    skills = []
    for values in resume_json.get("skills", {}).values():
        if isinstance(values, list):
            skills.extend(values)
    title = resume_json.get("experience", [{}])[0].get("title", "Software Engineer") if resume_json.get("experience") else "Software Engineer"
    query = "+".join([title] + skills[:4])
    return [
        {"label": "LinkedIn search", "url": f"https://www.linkedin.com/jobs/search/?keywords={query}"},
        {"label": "Indeed search", "url": f"https://www.indeed.com/jobs?q={query}"},
        {"label": "Google jobs search", "url": f"https://www.google.com/search?q={query}+jobs"}
    ]
