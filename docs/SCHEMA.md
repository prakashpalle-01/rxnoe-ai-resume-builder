# Database Schema

The backend creates these SQLAlchemy tables:

- `users`
- `uploaded_resumes`
- `parsed_resumes`
- `resume_versions`
- `job_descriptions`
- `ats_scores`
- `keyword_analysis`
- `resume_templates`
- `cover_letters`
- `interview_questions`
- `applications_tracker`

Local development defaults to SQLite. Production should use PostgreSQL:

```env
DATABASE_URL=postgresql+psycopg2://rxnoe:rxnoe@localhost:5432/rxnoe
```

For production migrations, add Alembic before launch. The current MVP auto-creates tables at API startup for fast local development.
