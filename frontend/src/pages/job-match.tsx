import { AlertTriangle, CheckCircle2, Download, FileText, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { scoreLabel } from "../lib/utils";
import { Badge, Button, Card, ProgressBar, SecondaryButton, Textarea } from "../components/ui";
import { useAppStore } from "../store/app-store";
import { ResumePreview } from "../components/resume-preview";
import type { AtsScore, ResumeRecord } from "../types/resume";
import { defaultTemplateId, resumeTemplates, type ResumeTemplateId } from "../lib/resume-templates";

type JobAnalysis = {
  job_title: string;
  role_titles?: string[];
  company: string;
  required_skills: string[];
  preferred_skills: string[];
  tools?: string[];
  technologies?: string[];
  responsibilities: string[];
  job_duties?: string[];
  seniority_level: string;
  domain: string;
  hidden_recruiter_expectations: string[];
};

export function JobMatchPage() {
  const { resumeId } = useParams();
  const { jobDescription, setJobDescription, atsScore, setAtsScore, resumes, setResumes } = useAppStore();
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [success, setSuccess] = useState("");
  const [beforeResume, setBeforeResume] = useState<ResumeRecord | null>(null);
  const [generatedResume, setGeneratedResume] = useState<ResumeRecord | null>(null);
  const [beforeScore, setBeforeScore] = useState<AtsScore | null>(null);
  const [afterScore, setAfterScore] = useState<AtsScore | null>(null);
  const [jobAnalysis, setJobAnalysis] = useState<JobAnalysis | null>(null);
  const [templateId, setTemplateId] = useState<ResumeTemplateId>((localStorage.getItem("rxnoe_template") as ResumeTemplateId) || defaultTemplateId);
  const selectedResume = useMemo(() => resumes.find((resume) => String(resume.id) === selectedResumeId), [resumes, selectedResumeId]);
  const activeScore = afterScore ?? beforeScore ?? atsScore;
  const currentBeforeResume = beforeResume ?? selectedResume ?? null;

  useEffect(() => {
    api.get("/resumes").then((response) => {
      setResumes(response.data);
      const routeId = resumeId && resumeId !== "latest" ? resumeId : "";
      const fallbackId = response.data[0]?.id ? String(response.data[0].id) : "";
      setSelectedResumeId((current) => current || routeId || fallbackId);
    }).catch(() => setError("Could not load resumes. Please sign in again."));
  }, [resumeId, setResumes]);

  async function analyze() {
    if (!selectedResumeId) {
      setError("Upload a resume first, then run ATS analysis.");
      return;
    }
    if (!jobDescription.trim()) {
      setError("Paste the job description first.");
      return;
    }
    setBusy("analyze");
    setError("");
    try {
      const [analysis, response] = await Promise.all([
        api.post("/jobs/analyze", { job_description: jobDescription }),
        api.post("/ats/score", { resume_id: Number(selectedResumeId), job_description: jobDescription })
      ]);
      setJobAnalysis(analysis.data);
      setBeforeScore(response.data);
      setAfterScore(null);
      setAtsScore(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Could not analyze this job description.");
    } finally {
      setBusy("");
    }
  }

  async function generateTargetedResume() {
    if (!selectedResumeId || !jobDescription.trim()) {
      setError("Select a resume and paste a job description first.");
      return;
    }
    setBusy("generate");
    setError("");
    setSuccess("");
    try {
      const [analysis, before] = await Promise.all([
        api.post("/jobs/analyze", { job_description: jobDescription }),
        api.post("/ats/score", { resume_id: Number(selectedResumeId), job_description: jobDescription })
      ]);
      const optimized = await api.post(`/resumes/${selectedResumeId}/optimize`, {
        instruction: "Generate best-match ATS resume from job description",
        job_description: jobDescription
      });
      const response = await api.post("/ats/score", { resume_id: Number(optimized.data.id), job_description: jobDescription });
      setJobAnalysis(analysis.data);
      setBeforeScore(before.data);
      setAfterScore(response.data);
      setBeforeResume(selectedResume ?? null);
      setGeneratedResume(optimized.data);
      setResumes([optimized.data, ...resumes.filter((resume) => resume.id !== optimized.data.id)]);
      setAtsScore(response.data);
      setSuccess(`Targeted resume generated: ${optimized.data.title}`);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Could not generate targeted resume.");
    } finally {
      setBusy("");
    }
  }

  function chooseTemplate(value: ResumeTemplateId) {
    setTemplateId(value);
    localStorage.setItem("rxnoe_template", value);
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-rx-line bg-white p-5 shadow-panel">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <Badge tone="green">Guided optimizer</Badge>
            <h1 className="mt-3 text-2xl font-bold tracking-normal">Paste a job description, understand the role, then generate a targeted resume.</h1>
            <p className="mt-2 max-w-3xl text-sm text-rx-muted">RxNoe summarizes the role, shows required skills, scores your current resume, rewrites the title/summary/bullets, and shows the before/after resume side by side.</p>
          </div>
          <div className="grid gap-2 text-sm sm:grid-cols-3 lg:min-w-[520px]">
            <StepBadge active={Boolean(selectedResumeId)} label="1. Resume" detail={selectedResume ? selectedResume.filename : "Select or upload"} />
            <StepBadge active={Boolean(jobAnalysis)} label="2. Role Brief" detail={jobAnalysis?.job_title || "Analyze JD"} />
            <StepBadge active={Boolean(generatedResume)} label="3. Targeted Resume" detail={generatedResume ? "Ready to download" : "Generate"} />
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(360px,0.7fr)]">
        <Card title="1. Paste Job Description">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="block text-sm font-medium">
              Resume
              <select className="mt-1 h-10 w-full rounded-md border border-rx-line bg-white px-3 text-sm" value={selectedResumeId} onChange={(event) => setSelectedResumeId(event.target.value)}>
                <option value="">Select a resume</option>
                {resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.title}</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium">
              Resume design
              <select className="mt-1 h-10 w-full rounded-md border border-rx-line bg-white px-3 text-sm" value={templateId} onChange={(event) => chooseTemplate(event.target.value as ResumeTemplateId)}>
                {resumeTemplates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
              </select>
            </label>
          </div>
          <Textarea className="mt-4 min-h-[330px]" placeholder="Paste the full job description here. First click Analyze Role to see the role summary and required skills, then Generate Optimized Resume." value={jobDescription} onChange={(event) => setJobDescription(event.target.value)} />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button disabled={!jobDescription.trim() || !selectedResumeId || Boolean(busy)} onClick={analyze}><Search size={17} /> {busy === "analyze" ? "Analyzing..." : "Analyze Role"}</Button>
            <Button className="bg-rx-green hover:bg-emerald-700" disabled={!jobDescription.trim() || !selectedResumeId || Boolean(busy)} onClick={generateTargetedResume}>
              <Sparkles size={17} /> {busy === "generate" ? "Generating..." : "Generate Optimized Resume"}
            </Button>
            <Link to="/upload-resume"><SecondaryButton>Upload resume</SecondaryButton></Link>
          </div>
          {success && <p className="mt-3 text-sm text-rx-green">{success}</p>}
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        </Card>

        <Card title="2. Role Summary & Skills">
          {!jobAnalysis && <p className="text-sm text-rx-muted">Click Analyze Role to see what this job is asking for before generating the new resume.</p>}
          {jobAnalysis && (
            <div className="space-y-4">
              <div className="rounded-md bg-blue-50 p-3">
                <p className="text-xs font-medium uppercase text-blue-700">Target resume title</p>
                <p className="mt-1 text-lg font-bold text-rx-ink">{jobAnalysis.job_title || "Role title not detected"}</p>
                <p className="mt-1 text-sm text-slate-700">{roleSummary(jobAnalysis)}</p>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold">Skills Needed</h3>
                <div className="flex flex-wrap gap-2">{neededSkills(jobAnalysis).map((skill) => <Badge key={skill}>{skill}</Badge>)}</div>
              </div>
              {Boolean(jobAnalysis.tools?.length) && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Tools & Platforms</h3>
                  <div className="flex flex-wrap gap-2">{jobAnalysis.tools?.slice(0, 14).map((tool) => <Badge key={tool} tone="slate">{tool}</Badge>)}</div>
                </div>
              )}
              <div>
                <h3 className="mb-2 text-sm font-semibold">Job Duties To Match</h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  {(jobAnalysis.job_duties ?? jobAnalysis.responsibilities).slice(0, 6).map((item) => <li className="rounded-md bg-slate-50 p-2" key={item}>{item}</li>)}
                </ul>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold">Recruiter Expectations</h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  {jobAnalysis.hidden_recruiter_expectations.map((item) => <li className="flex gap-2" key={item}><CheckCircle2 className="mt-0.5 shrink-0 text-rx-green" size={16} />{item}</li>)}
                </ul>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.75fr)_minmax(0,1fr)]">
      <Card title="3. ATS Score Before / After">
        {!activeScore && <p className="text-sm text-rx-muted">Paste a job description to see the current match score, blockers, keyword gaps, and recruiter rejection risks.</p>}
        {activeScore && (
          <div className="space-y-5">
            {(beforeScore || afterScore) && (
              <div className="grid gap-3 sm:grid-cols-2">
                {beforeScore && <ScoreCard label="Before ATS" score={beforeScore.overall_score} />}
                {afterScore && <ScoreCard label="After ATS" score={afterScore.overall_score} />}
              </div>
            )}
            <div>
              <div className="flex items-end justify-between">
                <p className="text-5xl font-bold">{activeScore.overall_score}</p>
                <Badge tone={activeScore.overall_score >= 75 ? "green" : "amber"}>{scoreLabel(activeScore.overall_score)}</Badge>
              </div>
              <ProgressBar value={activeScore.overall_score} />
            </div>
            {[
              ["Keyword match", activeScore.keyword_match_score],
              ["Skills match", activeScore.skills_match_score],
              ["Experience match", activeScore.experience_match_score],
              ["Title relevance", activeScore.title_relevance_score],
              ["Projects", activeScore.project_relevance_score],
              ["Formatting", activeScore.formatting_score],
              ["Readability", activeScore.readability_score]
            ].map(([label, value]) => (
              <div key={label as string}>
                <div className="mb-1 flex justify-between text-sm"><span>{label}</span><strong>{value}</strong></div>
                <ProgressBar value={Number(value)} />
              </div>
            ))}
            <div>
              <h3 className="mb-2 font-semibold">Missing Keywords</h3>
              <div className="flex flex-wrap gap-2">{activeScore.missing_keywords.map((word) => <Badge key={word} tone="red">{word}</Badge>)}</div>
            </div>
            {Boolean(activeScore.confirm_before_adding?.length) && (
              <div>
                <h3 className="mb-2 font-semibold">Confirm Before Adding</h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  {activeScore.confirm_before_adding?.map((item) => <li className="rounded-md bg-blue-50 p-2" key={item}>{item}</li>)}
                </ul>
              </div>
            )}
            {Boolean(activeScore.metric_prompts?.length) && (
              <div>
                <h3 className="mb-2 font-semibold">Metric Questions</h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  {activeScore.metric_prompts?.map((item) => <li className="rounded-md bg-emerald-50 p-2" key={item}>{item}</li>)}
                </ul>
              </div>
            )}
            {Boolean(activeScore.project_suggestions?.length) && (
              <div>
                <h3 className="mb-2 font-semibold">Projects To Close The Gap</h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  {activeScore.project_suggestions?.map((item) => <li className="rounded-md bg-slate-50 p-2" key={item}>{item}</li>)}
                </ul>
              </div>
            )}
            <div>
              <h3 className="mb-2 font-semibold">Recruiter View</h3>
              <ul className="space-y-2 text-sm">
                {activeScore.recruiter_view.map((item) => <li className="flex gap-2" key={item}><CheckCircle2 className="mt-0.5 shrink-0 text-rx-green" size={16} />{item}</li>)}
                {activeScore.warnings.map((item) => <li className="flex gap-2" key={item}><AlertTriangle className="mt-0.5 shrink-0 text-amber-600" size={16} />{item}</li>)}
              </ul>
            </div>
          </div>
        )}
      </Card>

      <Card title="4. Why The New Resume Matches">
        {!generatedResume && <p className="text-sm text-rx-muted">After generation, this panel explains exactly what changed: title, skills, keywords, formatting, and role alignment.</p>}
        {generatedResume && (
          <div className="space-y-4">
            <ul className="space-y-2 text-sm">
              {matchReasons(generatedResume, afterScore, beforeScore).map((reason) => <li className="flex gap-2" key={reason}><CheckCircle2 className="mt-0.5 shrink-0 text-rx-green" size={16} />{reason}</li>)}
            </ul>
            <div className="flex flex-wrap gap-3">
              <Link to={`/resume-editor/${generatedResume.id}`}><Button><FileText size={16} /> Edit Generated Resume</Button></Link>
              <Link to={`/download/${generatedResume.id}`}><SecondaryButton><Download size={16} /> Download</SecondaryButton></Link>
            </div>
          </div>
        )}
      </Card>
      </div>

      <Card title="5. Resume Before / After">
        {!currentBeforeResume && <p className="text-sm text-rx-muted">Upload or select a resume to preview it here.</p>}
        {currentBeforeResume && (
          <div className="grid gap-5 xl:grid-cols-2">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold">Before</p>
                {beforeScore && <Badge tone={beforeScore.overall_score >= 75 ? "green" : "amber"}>{beforeScore.overall_score} ATS</Badge>}
              </div>
              <ResumePreview resume={currentBeforeResume.parsed_json} templateId={templateId} />
            </div>
            <div>
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold">After</p>
                {afterScore && <Badge tone="green">{afterScore.overall_score} ATS</Badge>}
              </div>
              {generatedResume ? (
                <ResumePreview resume={generatedResume.parsed_json} templateId={templateId} />
              ) : (
                <div className="flex min-h-[520px] items-center justify-center rounded-lg border border-dashed border-rx-line bg-white p-8 text-center text-sm text-rx-muted">
                  The optimized resume appears here after you click Generate Optimized Resume.
                </div>
              )}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function StepBadge({ active, label, detail }: { active: boolean; label: string; detail: string }) {
  return (
    <div className={`rounded-md p-3 ${active ? "bg-emerald-50 text-emerald-800" : "bg-slate-50 text-slate-600"}`}>
      <strong className="block text-rx-ink">{label}</strong>
      <span className="line-clamp-1">{detail}</span>
    </div>
  );
}

function ScoreCard({ label, score }: { label: string; score: number }) {
  return (
    <div className="rounded-md border border-rx-line p-3">
      <p className="text-xs font-medium text-rx-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold">{score}</p>
      <ProgressBar value={score} />
    </div>
  );
}

function matchReasons(resume: ResumeRecord | null, after: AtsScore | null, before: AtsScore | null) {
  const reasons = [
    "The headline and summary are aligned to the detected job title while preserving the original work history.",
    "Important supported keywords are moved into summary, skills, experience, and projects instead of being dumped after education.",
    "The format remains single-column, ATS-safe, and readable across all 10 resume templates.",
  ];
  if (after && before) reasons.unshift(`ATS score improved from ${before.overall_score} to ${after.overall_score}.`);
  if (after?.matched_keywords?.length) reasons.push(`Matched keywords now visible: ${after.matched_keywords.slice(0, 8).join(", ")}.`);
  if (resume?.parsed_json?.suggested_projects?.length) reasons.push("Relevant GitHub project ideas are shown separately so you can build them before adding them as completed projects.");
  return reasons;
}

function neededSkills(analysis: JobAnalysis) {
  return [...analysis.required_skills, ...analysis.preferred_skills].filter((skill, index, list) => skill && list.indexOf(skill) === index).slice(0, 18);
}

function roleSummary(analysis: JobAnalysis) {
  const title = analysis.job_title || analysis.role_titles?.[0] || "This role";
  const level = analysis.seniority_level ? `${analysis.seniority_level.toLowerCase()} ` : "";
  const domain = analysis.domain && analysis.domain !== "General Technology" ? ` in ${analysis.domain.toLowerCase()}` : "";
  const skills = neededSkills(analysis).slice(0, 5).join(", ");
  const duty = (analysis.job_duties ?? analysis.responsibilities)[0] || "delivering role-specific technical work";
  return `${title} is a ${level}role${domain} focused on ${duty}. The resume should emphasize ${skills || "the required tools, responsibilities, and business impact"}.`;
}
