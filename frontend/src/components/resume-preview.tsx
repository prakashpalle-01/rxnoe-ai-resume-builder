import type { ResumeJson } from "../types/resume";
import { cn } from "../lib/utils";
import { defaultTemplateId, resumeTemplates, type ResumeTemplateId } from "../lib/resume-templates";

export function ResumePreview({ resume, templateId = defaultTemplateId }: { resume: ResumeJson; templateId?: ResumeTemplateId }) {
  const p = resume.personal_info;
  const headline = resume.target_title || resume.experience?.[0]?.title;
  const template = resumeTemplates.find((item) => item.id === templateId) ?? resumeTemplates[0];
  return (
    <article className={cn("resume-paper mx-auto min-h-[1050px] max-w-[780px] bg-white p-10 text-[13px] leading-5 text-slate-900", template.className)}>
      <header className="border-b border-slate-300 pb-3 text-center">
        <h1 className="text-2xl font-bold tracking-normal">{p.name || "Your Name"}</h1>
        {headline && <p className="mt-1 text-sm font-semibold text-slate-700">{headline}</p>}
        <p className="mt-1 text-xs text-slate-600">
          {[p.email, p.phone, p.location, p.linkedin, p.github, p.portfolio].filter(Boolean).join(" | ")}
        </p>
      </header>
      <ResumeSection title="Summary">
        <p>{resume.summary || "A concise, role-targeted summary will appear here."}</p>
      </ResumeSection>
      <ResumeSection title="Technical Skills">
        <div className="space-y-1 skill-lines">
          {orderedSkillEntries(resume.skills).map(([group, values]) => (
            <p key={group}><strong>{label(group)}:</strong> {values.join(", ")}</p>
          ))}
        </div>
      </ResumeSection>
      <ResumeSection title="Experience">
        {resume.experience.map((job, index) => (
          <div key={`${job.company}-${index}`} className="mb-3">
            <div className="flex justify-between gap-4">
              <strong>{job.title || "Role"}{job.company ? `, ${job.company}` : ""}</strong>
              <span className="text-xs text-slate-600">{[job.start_date, job.end_date].filter(Boolean).join(" - ")}</span>
            </div>
            <ul className="mt-1 list-disc pl-5">
              {job.bullets.map((bullet, bulletIndex) => <li key={bulletIndex}>{highlightKeywords(bullet, resume.target_keywords)}</li>)}
            </ul>
          </div>
        ))}
      </ResumeSection>
      {resume.projects.length > 0 && (
        <ResumeSection title="Projects">
          {resume.projects.map((project, index) => (
            <div key={`${project.name}-${index}`} className="mb-3 break-inside-avoid">
              <strong>{project.name || "Project"}</strong>
              {project.technologies.length > 0 && <span className="text-xs text-slate-600"> | {highlightKeywords(project.technologies.join(", "), resume.target_keywords)}</span>}
              {project.url && <span className="text-xs text-slate-600"> | {project.url}</span>}
              <ul className="mt-1 list-disc pl-5">
                {project.bullets.map((bullet, bulletIndex) => <li key={bulletIndex}>{highlightKeywords(bullet, resume.target_keywords)}</li>)}
              </ul>
            </div>
          ))}
        </ResumeSection>
      )}
      {resume.education.length > 0 && <ResumeSection title="Education"><p>{resume.education.join(" | ")}</p></ResumeSection>}
      {resume.certifications.length > 0 && <ResumeSection title="Certifications"><p>{resume.certifications.join(" | ")}</p></ResumeSection>}
    </article>
  );
}

function ResumeSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-4">
      <h2 className="mb-2 border-b border-slate-200 pb-1 text-sm font-bold uppercase tracking-normal">{title}</h2>
      {children}
    </section>
  );
}

function label(value: string) {
  const labels: Record<string, string> = {
    ai_ml_core: "AI / ML Core",
    deep_learning: "Deep Learning",
    genai_llm_systems: "GenAI & Advanced LLM Systems",
    frameworks_libraries: "Frameworks & Libraries",
    mlops_engineering: "MLOps & ML Engineering",
    cloud_infrastructure: "Cloud & Infrastructure",
    databases_vector_stores: "Databases & Vector Stores",
    programming: "Programming",
    monitoring_observability: "Monitoring & Observability",
    ai_safety_compliance: "AI Safety, Privacy & Compliance",
    developer_tools: "Developer & Productivity Tools",
    technical: "Additional Technical Skills",
    tools: "Tools",
    cloud: "Cloud",
    databases: "Databases",
    soft_skills: "Professional Skills"
  };
  return labels[value] ?? value.replace(/_/g, " ").replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function orderedSkillEntries(skills: ResumeJson["skills"]) {
  const order = [
    "ai_ml_core",
    "deep_learning",
    "genai_llm_systems",
    "frameworks_libraries",
    "mlops_engineering",
    "cloud_infrastructure",
    "databases_vector_stores",
    "programming",
    "monitoring_observability",
    "ai_safety_compliance",
    "developer_tools",
    "technical",
    "tools",
    "cloud",
    "databases",
    "soft_skills"
  ];
  return order
    .map((key) => [key, skills[key] ?? []] as [string, string[]])
    .filter(([, values]) => values.length > 0);
}

function highlightKeywords(text: string, keywords: string[] = []) {
  const important = keywordHighlights(keywords);
  if (!important.length) return text;
  const pattern = new RegExp(`(^|[^A-Za-z0-9+#./-])(${important.map(escapeRegExp).join("|")})(?=$|[^A-Za-z0-9+#./-])`, "gi");
  return text.split(pattern).map((part, index) =>
    important.some((keyword) => keyword.toLowerCase() === part.toLowerCase())
      ? <strong key={`${part}-${index}`}>{part}</strong>
      : part
  );
}

function keywordHighlights(keywords: string[] = []) {
  const blocked = new Set([
    "associate",
    "stack",
    "product",
    "skills",
    "required",
    "preferred",
    "qualification",
    "qualifications",
    "requirements",
    "responsibilities",
    "development",
    "software",
    "systems",
    "build",
    "building",
    "team",
    "teams",
    "business",
    "technical",
    "technology",
    "technologies",
    "platform",
    "platforms",
    "solutions",
    "solution",
    "engineer",
    "engineering",
    "developer",
    "analyst",
    "candidate",
    "role",
    "work",
    "working"
  ]);
  const seen = new Set<string>();
  return keywords
    .map((keyword) => keyword.trim())
    .filter((keyword) => {
      const key = keyword.toLowerCase();
      if (!keyword || seen.has(key) || blocked.has(key)) return false;
      seen.add(key);
      const isAcronym = /^[A-Z0-9+#./-]{2,}$/.test(keyword);
      const isUsefulPhrase = keyword.includes(" ") && keyword.length >= 5;
      return isAcronym || isUsefulPhrase || keyword.length >= 4;
    })
    .sort((a, b) => b.length - a.length)
    .slice(0, 80);
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
