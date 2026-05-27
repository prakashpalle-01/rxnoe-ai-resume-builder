export type ResumeJson = {
  personal_info: {
    name: string;
    email: string;
    phone: string;
    location: string;
    linkedin: string;
    github: string;
    portfolio: string;
  };
  target_title?: string;
  summary: string;
  skills: {
    [key: string]: string[];
    ai_ml_core: string[];
    deep_learning: string[];
    genai_llm_systems: string[];
    frameworks_libraries: string[];
    mlops_engineering: string[];
    cloud_infrastructure: string[];
    databases_vector_stores: string[];
    messaging_streaming: string[];
    programming: string[];
    monitoring_observability: string[];
    ai_safety_compliance: string[];
    developer_tools: string[];
    technical: string[];
    tools: string[];
    cloud: string[];
    databases: string[];
    soft_skills: string[];
  };
  experience: Array<{
    company: string;
    title: string;
    location: string;
    start_date: string;
    end_date: string;
    bullets: string[];
  }>;
  projects: Array<{
    name: string;
    url?: string;
    technologies: string[];
    bullets: string[];
  }>;
  target_keywords?: string[];
  unverified_job_keywords?: string[];
  suggested_projects?: Array<{
    name: string;
    url?: string;
    technologies: string[];
    bullets: string[];
    requires_confirmation?: boolean;
  }>;
  education: string[];
  certifications: string[];
};

export type ResumeRecord = {
  id: number;
  title: string;
  filename: string;
  raw_text: string;
  parsed_json: ResumeJson;
  created_at: string;
};

export type ResumeVersion = {
  id: number;
  resume_id: number;
  version_name: string;
  resume_json: ResumeJson;
  change_summary: string;
  created_at: string;
};

export type AtsScore = {
  overall_score: number;
  keyword_match_score: number;
  skills_match_score: number;
  experience_match_score: number;
  title_relevance_score: number;
  project_relevance_score: number;
  formatting_score: number;
  readability_score: number;
  recruiter_realism_score?: number;
  missing_keywords: string[];
  matched_keywords: string[];
  confirm_before_adding?: string[];
  metric_prompts?: string[];
  project_suggestions?: string[];
  recruiter_decision?: {
    status: string;
    reason: string;
  };
  warnings: string[];
  recruiter_view: string[];
};
