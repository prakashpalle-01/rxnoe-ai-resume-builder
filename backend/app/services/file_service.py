import os
import re
import shutil
from pathlib import Path
import fitz
from docx import Document
from fastapi import HTTPException, UploadFile
from app.core.config import get_settings

settings = get_settings()
ALLOWED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx"
}


def sanitize_text(text: str) -> str:
    text = re.sub(r"\x00", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def save_upload(file: UploadFile, user_id: int) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED and suffix not in [".pdf", ".docx"]:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX resumes are supported.")

    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    path = upload_root / f"user-{user_id}-{Path(file.filename or 'resume').name}"
    size = 0
    with path.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_mb * 1024 * 1024:
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="File is over 5MB.")
            buffer.write(chunk)
    return str(path)


def extract_text(path: str) -> str:
    suffix = Path(path).suffix.lower()
    try:
        if suffix == ".pdf":
            return sanitize_text(extract_pdf(path))
        if suffix == ".docx":
            return sanitize_text(extract_docx(path))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The file appears corrupted or unreadable.") from exc
    raise HTTPException(status_code=400, detail="Unsupported file type.")


def extract_pdf(path: str) -> str:
    with fitz.open(path) as doc:
        if doc.needs_pass:
            raise RuntimeError("Password-protected PDFs are not supported.")
        text = "\n".join(page.get_text("text") for page in doc)
    if len(text.strip()) < 40:
        raise RuntimeError("This looks like an image-only resume. Upload a selectable-text PDF or DOCX.")
    return text


def extract_docx(path: str) -> str:
    doc = Document(path)
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    if len(text.strip()) < 40:
        raise RuntimeError("This DOCX does not contain enough readable text.")
    return text


def remove_file(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
