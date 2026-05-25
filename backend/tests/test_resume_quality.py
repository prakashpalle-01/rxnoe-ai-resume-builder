import re
import unittest

from app.services.ai_service import _role_family, analyze_job_description, optimize_resume
from app.services.export_service import build_pdf
from app.services.scoring_service import score_resume


BASE_RESUME = {
    "personal_info": {"name": "Candidate Name", "email": "candidate@example.com", "phone": "", "location": "", "linkedin": "", "github": "", "portfolio": ""},
    "summary": "Software Engineer with 4+ years of experience building production applications and cloud workflows.",
    "skills": {
        "technical": ["Python", "Java", "Spring Boot", "React", "TypeScript", "JavaScript", "SQL", "PostgreSQL", "AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Git"],
    },
    "experience": [
        {
            "company": "Example Company",
            "title": "Software Engineer",
            "location": "",
            "start_date": "2022",
            "end_date": "Present",
            "bullets": ["Developed customer-facing application workflows and backend services.", "Improved deployment and production troubleshooting practices."],
        }
    ],
    "projects": [],
    "education": ["BS Computer Science"],
    "certifications": [],
}


ROLE_CASES = {
    "rails_giving": ("Full Stack Engineer Ruby on Rails React Stripe donor giving admin reporting", "fullstack_rails"),
    "ruby_backend": ("Back-end Software Engineer Ruby on Rails GraphQL PostgreSQL API", "rails_backend"),
    "aws_dotnet": ("AWS Software Engineer AWS .NET C# Terraform CI/CD Docker Kubernetes SQL Git", "platform_engineering"),
    "frontend": ("Frontend Engineer React TypeScript Next.js Tailwind accessibility", "product_frontend"),
    "ai": ("AI Engineer Python FastAPI RAG LLM vector embeddings AWS", "ai_engineering"),
    "java": ("Java Backend Engineer Java Spring Boot REST Microservices Kafka PostgreSQL", "java_backend"),
    "data": ("Data Engineer Python SQL ETL Airflow Snowflake AWS", "data_engineering"),
    "analytics": ("Business Intelligence Analyst SQL Power BI Tableau dashboards KPI", "analytics"),
    "ba": ("Business Analyst requirements gathering user stories Agile SQL", "business_analysis"),
    "qa": ("QA Automation Engineer Selenium Cypress API Testing CI/CD", "quality_assurance"),
    "platform": ("Senior Platform Engineer SRE AWS Kubernetes Terraform CI/CD", "platform_engineering"),
    "go_backend": ("Backend Software Engineer Go Python REST APIs AWS", "backend_engineering"),
    "node_backend": ("Backend Software Engineer TypeScript Node.js SQL AWS security", "backend_engineering"),
    "solutions": ("Principal Software Solutions Architect JavaScript AWS APIs", "solutions_architecture"),
    "dotnet": (".NET Developer SQL REST APIs", "dotnet_engineering"),
    "linux_systems": ("Linux Systems Engineer Terraform Docker AWS", "platform_engineering"),
}


class ResumeQualityTests(unittest.TestCase):
    def test_job_families_route_to_correct_writer(self):
        for label, (description, expected) in ROLE_CASES.items():
            with self.subTest(label=label):
                self.assertEqual(_role_family(analyze_job_description(description)), expected)

    def test_react_alone_does_not_generate_rails_or_giving_content(self):
        result, _ = optimize_resume(BASE_RESUME, "Generate best-match ATS resume from job description", ROLE_CASES["frontend"][0])
        content = _resume_text(result).lower()
        self.assertNotIn("ruby on rails", content)
        self.assertNotIn("donor", content)
        self.assertNotIn("stripe", content)

    def test_generated_projects_require_confirmation_and_are_not_exported_as_work(self):
        result, _ = optimize_resume(BASE_RESUME, "Generate best-match ATS resume from job description", ROLE_CASES["aws_dotnet"][0])
        self.assertEqual(result["projects"], [])
        self.assertTrue(result.get("suggested_projects"))

    def test_unsupported_job_skills_remain_gaps(self):
        result, _ = optimize_resume(BASE_RESUME, "Generate best-match ATS resume from job description", ROLE_CASES["aws_dotnet"][0])
        score = score_resume(result, "", ROLE_CASES["aws_dotnet"][0])
        self.assertIn(".NET", score["missing_keywords"])
        self.assertIn("C#", score["missing_keywords"])
        self.assertLess(score["overall_score"], 100)

    def test_generated_language_has_no_action_collisions(self):
        invalid = re.compile(r"(?i)\b(?:architected|engineered|designed|optimized|automated|integrated|delivered)\s+(?:translated|shipped|refined|strengthened|diagnosed|reviewed|investigated|improved|built)\b")
        for label, (description, _) in ROLE_CASES.items():
            with self.subTest(label=label):
                result, _ = optimize_resume(BASE_RESUME, "Generate best-match ATS resume from job description", description)
                self.assertIsNone(invalid.search(_resume_text(result)))

    def test_acronyms_are_rendered_professionally_in_titles(self):
        expected = {
            "AWS Software Engineer AWS Terraform Docker": "AWS Software Engineer",
            "QA Automation Engineer Selenium Cypress": "QA Automation Engineer",
            "AI Architect Python RAG": "AI Architect",
            ".NET Developer SQL REST APIs": ".NET Developer",
        }
        for description, title in expected.items():
            with self.subTest(description=description):
                self.assertEqual(analyze_job_description(description)["job_title"], title)

    def test_pdf_export_is_selectable_two_page_safe_content(self):
        result, _ = optimize_resume(BASE_RESUME, "Generate best-match ATS resume from job description", ROLE_CASES["frontend"][0])
        pdf = build_pdf(result, "recruiter-scan")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)


def _resume_text(resume: dict) -> str:
    parts = [resume.get("target_title", ""), resume.get("summary", "")]
    parts.extend([bullet for job in resume.get("experience", []) for bullet in job.get("bullets", [])])
    parts.extend([project.get("name", "") for project in resume.get("projects", [])])
    parts.extend([bullet for project in resume.get("projects", []) for bullet in project.get("bullets", [])])
    return " ".join(parts)


if __name__ == "__main__":
    unittest.main()
