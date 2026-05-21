from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ResumeUpdate(BaseModel):
    parsed_json: dict


class ResumeOut(BaseModel):
    id: int
    title: str
    filename: str
    raw_text: str
    parsed_json: dict
    confidence: dict
    created_at: datetime

    class Config:
        from_attributes = True


class ResumeVersionOut(BaseModel):
    id: int
    resume_id: int
    version_name: str
    resume_json: dict
    change_summary: str
    created_at: datetime

    class Config:
        from_attributes = True


class OptimizeRequest(BaseModel):
    instruction: str = "Match this job"
    job_description: Optional[str] = None


class JobAnalyzeRequest(BaseModel):
    job_description: str


class AtsScoreRequest(BaseModel):
    resume_id: int
    job_description: str


class JobRankRequest(BaseModel):
    resume_id: int
    job_posts: str


class CoverLetterRequest(BaseModel):
    resume_id: Optional[int] = None
    job_description: str
    company: str = ""
    tone: str = "professional"


class InterviewRequest(BaseModel):
    resume_id: Optional[int] = None
    job_description: str


class ApplicationCreate(BaseModel):
    company: str
    job_title: str
    job_link: str = ""
    resume_version_used: str = ""
    application_date: Optional[date] = None
    status: str = "Saved"
    notes: str = ""
    follow_up_reminder: str = ""


class ApplicationOut(ApplicationCreate):
    id: int
    application_date: date

    class Config:
        from_attributes = True
