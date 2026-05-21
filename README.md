# RxNoe AI Resume Builder

Focused AI resume optimization app. Users upload a PDF/DOCX resume, paste a job description, get ATS scoring, keyword gaps, honest resume optimization, recruiter-view warnings, and PDF/DOCX export.

## Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn-style local UI primitives, React Hook Form, Zustand
- Backend: FastAPI, SQLAlchemy, JWT auth, PyMuPDF, python-docx, OpenAI-ready LLM service
- Jobs: Redis and Celery scaffold
- Database: SQLite by default, PostgreSQL-ready

## Run Locally

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Product Workflow

1. Upload a PDF or DOCX resume.
2. Extract resume text.
3. Parse into structured sections.
4. Paste a job description.
5. Analyze JD requirements and ATS keywords.
6. Compare resume vs JD.
7. Review ATS score, keyword gaps, rejection risks, weak bullets, formatting issues, and recruiter readability.
8. Generate an optimized resume version.
9. Compare before and after.
10. Preview and download PDF or DOCX.

## Chat-Style Resume Editor

The resume editor includes a ChatGPT-style editing panel with a local-first command engine. Common requests such as grammar cleanup, shortening, weak verb replacement, AI-tone removal, skill formatting, ATS validation, keyword checks, duplicate detection, and bullet formatting run in the browser without API calls.

AI calls are only triggered by explicit buttons such as `AI Optimize` and `Deep Rewrite`. These actions are batched at the resume level, cached in the browser for repeated requests, and labeled as credit-using edits in the UI.

## Main Pages

- `/login` and `/signup`
- `/dashboard`
- `/upload-resume`
- `/paste-job-description/:resumeId`
- `/ats-score/:resumeId`
- `/resume-editor/:id`
- `/resume-preview/:id`
- `/download/:id`

## OpenAI

The app works without OpenAI by using local parsing/scoring heuristics. To use OpenAI:

```env
OPENAI_API_KEY=your-key
LLM_PROVIDER=openai
```

## Security

- JWT authentication
- File type validation for PDF/DOCX
- 5MB upload limit
- Password-protected PDF rejection
- Image-only resume rejection
- Extracted text sanitization
- API keys loaded from environment variables

## Resume Templates

The product supports five ATS-safe single-column template roles:

1. Software Engineer
2. Data Analyst
3. AI Engineer
4. Cloud/DevOps Engineer
5. Business Analyst

## MVP Phases

Phase 1 is implemented: auth, resume upload, text extraction, parsing, editor.

Phase 2 is implemented: job analyzer, ATS score, keyword gaps, resume optimization.

Phase 3 is implemented: PDF export, DOCX export, version history, preview.

Phase 4 is intentionally removed from the frontend to keep the app focused on one workflow: upload resume, paste job description, generate best-match resume, export.

## Deployment

Use PostgreSQL and Redis in production:

```bash
docker compose up -d postgres redis
```

Backend production command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend production build:

```bash
npm run build
```

Serve `frontend/dist` from a static host and point API traffic to the FastAPI service.
