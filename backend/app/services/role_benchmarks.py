import re


# Category-level benchmarks inspired by public IT resume categories. This stores
# no third-party resume content or candidate personal information.
ROLE_BENCHMARKS = [
    {
        "key": "dotnet_cloud",
        "label": ".NET / Cloud Software Engineering",
        "source_category": ".NET Developers/Architects",
        "patterns": [r"\.net", r"\bc#\b", r"\basp\.net\b", r"\bazure\b"],
        "core_skills": [".NET", "C#", "AWS", "SQL", "Docker", "Terraform", "CI/CD", "Git"],
        "resume_focus": "backend services, cloud delivery, secure software, deployment automation, and production reliability",
    },
    {
        "key": "platform_release",
        "label": "Cloud / Platform & Release Engineering",
        "source_category": "Network and Systems Administrators",
        "patterns": [r"\bdevops\b", r"\bkubernetes\b", r"\bterraform\b", r"\bci/cd\b", r"\brelease engineer\b", r"\bsre\b"],
        "core_skills": ["AWS", "Terraform", "Docker", "Kubernetes", "CI/CD", "Git", "Monitoring"],
        "resume_focus": "infrastructure automation, container delivery, observability, incident response, and repeatable releases",
    },
    {
        "key": "web_frontend",
        "label": "Web / Frontend Engineering",
        "source_category": "Web Developer",
        "patterns": [r"\bfront[\s-]?end\b", r"\bui developer\b", r"\breact\b", r"\btypescript\b", r"\bweb developer\b"],
        "core_skills": ["React", "TypeScript", "JavaScript", "HTML5", "CSS3", "APIs", "Testing"],
        "resume_focus": "user-facing features, reusable UI systems, accessibility, API integration, and product quality",
    },
    {
        "key": "java_backend",
        "label": "Java Backend Engineering",
        "source_category": "Java Developers/Architects",
        "patterns": [r"\bjava\b", r"\bspring boot\b", r"\bj2ee\b", r"\bkafka\b"],
        "core_skills": ["Java", "Spring Boot", "REST", "SQL", "Microservices", "Kafka", "AWS"],
        "resume_focus": "backend services, integration patterns, reliable APIs, distributed workflows, and system performance",
    },
    {
        "key": "data_etl",
        "label": "Data / ETL Engineering",
        "source_category": "Datawarehousing, ETL, Informatica",
        "patterns": [r"\betl\b", r"\binformatica\b", r"\bdata warehouse\b", r"\bdata engineer\b", r"\bairflow\b"],
        "core_skills": ["SQL", "ETL", "Python", "Data Warehousing", "Airflow", "Cloud", "Data Quality"],
        "resume_focus": "data pipelines, data quality, scalable processing, trustworthy datasets, and operational reporting",
    },
    {
        "key": "business_intelligence",
        "label": "Business Intelligence / Analytics",
        "source_category": "Business Intelligence, Business Object",
        "patterns": [r"\bbusiness intelligence\b", r"\bpower bi\b", r"\btableau\b", r"\bkpi\b", r"\banalytics\b"],
        "core_skills": ["SQL", "Power BI", "Tableau", "Excel", "Data Analysis", "Reporting", "Stakeholder Communication"],
        "resume_focus": "decision-ready reporting, KPI clarity, data validation, dashboard adoption, and business outcomes",
    },
    {
        "key": "business_analysis",
        "label": "Business Analysis",
        "source_category": "Business Analyst (BA)",
        "patterns": [r"\bbusiness analyst\b", r"\brequirements gathering\b", r"\buser stories\b"],
        "core_skills": ["Requirements", "Process Mapping", "Agile", "SQL", "Documentation", "Stakeholder Management"],
        "resume_focus": "requirements clarity, process improvement, cross-functional delivery, validation, and measurable outcomes",
    },
    {
        "key": "quality_assurance",
        "label": "Quality Assurance / Test Automation",
        "source_category": "Quality Assurance (QA)",
        "patterns": [r"\bquality assurance\b", r"\bqa\b", r"\btest automation\b", r"\bselenium\b", r"\bcypress\b"],
        "core_skills": ["Test Automation", "Selenium", "Cypress", "API Testing", "CI/CD", "Defect Tracking"],
        "resume_focus": "test coverage, release confidence, defect prevention, automation, and product reliability",
    },
    {
        "key": "sql_data",
        "label": "SQL / Database Engineering",
        "source_category": "SQL Developers",
        "patterns": [r"\bsql developer\b", r"\bdatabase developer\b", r"\bpostgresql\b", r"\bsql server\b"],
        "core_skills": ["SQL", "PostgreSQL", "Database Design", "Performance Tuning", "ETL", "Reporting"],
        "resume_focus": "data modeling, query performance, reliable reporting, data integrity, and scalable database workflows",
    },
]


def infer_resume_benchmark(text: str) -> dict:
    lower = text.lower()
    best = None
    best_score = 0
    for profile in ROLE_BENCHMARKS:
        score = sum(1 for pattern in profile["patterns"] if re.search(pattern, lower))
        if score > best_score:
            best = profile
            best_score = score
    if not best:
        return {
            "key": "software_engineering",
            "label": "Software Engineering",
            "source_category": "Other Resumes",
            "core_skills": [],
            "resume_focus": "maintainable software, tested implementation, production reliability, and clear impact",
        }
    return {key: value for key, value in best.items() if key != "patterns"}
