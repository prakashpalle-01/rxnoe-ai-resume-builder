export type ResumeTemplateId =
  | "genai-model"
  | "ats-classic"
  | "tech-compact"
  | "executive-clean"
  | "engineer-dense"
  | "data-modern"
  | "cloud-systems"
  | "frontend-sharp"
  | "minimal-two-page"
  | "recruiter-scan";

export type ResumeTemplate = {
  id: ResumeTemplateId;
  name: string;
  description: string;
  className: string;
};

export const resumeTemplates: ResumeTemplate[] = [
  {
    id: "genai-model",
    name: "GenAI Model",
    description: "Matches the uploaded model: dense two-page AI/ML layout.",
    className: "template-genai"
  },
  {
    id: "ats-classic",
    name: "ATS Classic",
    description: "Simple single-column recruiter standard.",
    className: "template-classic"
  },
  {
    id: "tech-compact",
    name: "Tech Compact",
    description: "Compact spacing for technical resumes.",
    className: "template-compact"
  },
  {
    id: "executive-clean",
    name: "Executive Clean",
    description: "Polished senior-level spacing and headings.",
    className: "template-executive"
  },
  {
    id: "engineer-dense",
    name: "Engineer Dense",
    description: "More bullets and technical keywords per page.",
    className: "template-engineer"
  },
  {
    id: "data-modern",
    name: "Data Modern",
    description: "Clean skills emphasis for data and AI roles.",
    className: "template-data"
  },
  {
    id: "cloud-systems",
    name: "Cloud Systems",
    description: "Infrastructure and DevOps friendly layout.",
    className: "template-cloud"
  },
  {
    id: "frontend-sharp",
    name: "Frontend Sharp",
    description: "Readable frontend/product engineering style.",
    className: "template-frontend"
  },
  {
    id: "minimal-two-page",
    name: "Minimal Two Page",
    description: "Designed to breathe across two pages.",
    className: "template-minimal"
  },
  {
    id: "recruiter-scan",
    name: "Recruiter Scan",
    description: "Fast 6-second scan with strong section clarity.",
    className: "template-scan"
  }
];

export const defaultTemplateId: ResumeTemplateId = "genai-model";
