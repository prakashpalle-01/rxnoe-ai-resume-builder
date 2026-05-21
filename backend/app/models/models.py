from datetime import date, datetime
from typing import Optional
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resumes: Mapped[list["UploadedResume"]] = relationship(back_populates="user")


class UploadedResume(Base):
    __tablename__ = "uploaded_resumes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255), default="Untitled Resume")
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(Text, default="")
    parsed_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    user: Mapped[User] = relationship(back_populates="resumes")
    versions: Mapped[list["ResumeVersion"]] = relationship(back_populates="resume")


class ParsedResume(Base):
    __tablename__ = "parsed_resumes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("uploaded_resumes.id"))
    structured_json: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[dict] = mapped_column(JSON, default=dict)


class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("uploaded_resumes.id"))
    job_description_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_descriptions.id"), nullable=True)
    version_name: Mapped[str] = mapped_column(String(255), default="Optimized Version")
    resume_json: Mapped[dict] = mapped_column(JSON)
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resume: Mapped[UploadedResume] = relationship(back_populates="versions")


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    raw_text: Mapped[str] = mapped_column(Text)
    analysis_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AtsScore(Base):
    __tablename__ = "ats_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("uploaded_resumes.id"))
    job_description_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_descriptions.id"), nullable=True)
    score_json: Mapped[dict] = mapped_column(JSON)
    overall_score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KeywordAnalysis(Base):
    __tablename__ = "keyword_analysis"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("uploaded_resumes.id"))
    matched_keywords: Mapped[dict] = mapped_column(JSON, default=list)
    missing_keywords: Mapped[dict] = mapped_column(JSON, default=list)


class ResumeTemplate(Base):
    __tablename__ = "resume_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(255))
    template_json: Mapped[dict] = mapped_column(JSON, default=dict)


class CoverLetter(Base):
    __tablename__ = "cover_letters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    resume_id: Mapped[Optional[int]] = mapped_column(ForeignKey("uploaded_resumes.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    questions_json: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ApplicationTracker(Base):
    __tablename__ = "applications_tracker"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    company: Mapped[str] = mapped_column(String(255))
    job_title: Mapped[str] = mapped_column(String(255))
    job_link: Mapped[str] = mapped_column(String(1000), default="")
    resume_version_used: Mapped[str] = mapped_column(String(255), default="")
    application_date: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[str] = mapped_column(String(50), default="Saved")
    notes: Mapped[str] = mapped_column(Text, default="")
    follow_up_reminder: Mapped[str] = mapped_column(String(255), default="")
