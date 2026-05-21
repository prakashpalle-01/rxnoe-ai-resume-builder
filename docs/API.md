# RxNoe API

Base URL: `http://localhost:8000/api`

Authentication uses JWT bearer tokens.

## Auth

- `POST /auth/signup`
- `POST /auth/login`

Body:

```json
{ "email": "user@example.com", "password": "password123" }
```

## Resumes

- `POST /resumes/upload` multipart form file, PDF or DOCX only, max 5MB
- `GET /resumes`
- `GET /resumes/{id}`
- `PUT /resumes/{id}`
- `DELETE /resumes/{id}`
- `POST /resumes/{id}/parse`
- `POST /resumes/{id}/optimize`
- `GET /resumes/{id}/versions`
- `GET|POST /resumes/{id}/export/pdf`
- `GET|POST /resumes/{id}/export/docx`

## Job and ATS

- `POST /jobs/analyze`
- `POST /ats/score`

ATS returns 0-100 scoring for keyword match, skills match, experience match, title relevance, project relevance, formatting, readability, missing keywords, warnings, and recruiter view.

The frontend intentionally exposes only the focused resume optimization workflow.
