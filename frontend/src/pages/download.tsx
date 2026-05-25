import { Download, Edit3, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { resumeDownloadName } from "../lib/utils";
import { Button, Card, SecondaryButton } from "../components/ui";
import { ResumePreview } from "../components/resume-preview";
import type { ResumeRecord } from "../types/resume";
import { defaultTemplateId, resumeTemplates, type ResumeTemplateId } from "../lib/resume-templates";

export function DownloadPage() {
  const { id } = useParams();
  const [resume, setResume] = useState<ResumeRecord | null>(null);
  const [templateId, setTemplateId] = useState<ResumeTemplateId>((localStorage.getItem("rxnoe_template") as ResumeTemplateId) || defaultTemplateId);

  useEffect(() => {
    if (id) api.get(`/resumes/${id}`).then((response) => setResume(response.data));
  }, [id]);

  async function exportFile(type: "pdf" | "docx") {
    if (!id || !resume) return;
    const response = await api.get(`/resumes/${id}/export/${type}`, { params: { template: templateId }, responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = resumeDownloadName(resume.parsed_json, type);
    link.click();
    URL.revokeObjectURL(url);
  }

  function chooseTemplate(value: ResumeTemplateId) {
    setTemplateId(value);
    localStorage.setItem("rxnoe_template", value);
  }

  if (!resume) return <p className="text-rx-muted">Loading download page...</p>;

  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-4 rounded-lg border border-rx-line bg-white p-5 shadow-panel lg:flex-row lg:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-normal">Edit, choose a design, then download</h1>
          <p className="mt-2 text-sm text-rx-muted">Pick one of 10 ATS-friendly templates. Your selected design and spacing will be used in the downloaded PDF or DOCX.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link to={`/resume-editor/${id}`}><Button><Edit3 size={17} /> Edit Resume</Button></Link>
          <Button onClick={() => exportFile("pdf")}><Download size={17} /> Download PDF</Button>
          <SecondaryButton onClick={() => exportFile("docx")}><FileText size={17} /> Download DOCX</SecondaryButton>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <Card title="10 Resume Design Templates">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            {resumeTemplates.map((template, index) => (
              <button
                key={template.id}
                className={`rounded-md border p-3 text-left transition ${templateId === template.id ? "border-rx-blue bg-blue-50 ring-2 ring-blue-100" : "border-rx-line bg-white hover:bg-slate-50"}`}
                onClick={() => chooseTemplate(template.id)}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold">{index + 1}. {template.name}</p>
                  {templateId === template.id && <span className="rounded-md bg-rx-blue px-2 py-1 text-xs font-semibold text-white">Selected</span>}
                </div>
                <p className="mt-1 text-sm text-rx-muted">{template.description}</p>
              </button>
            ))}
          </div>
        </Card>
        <Card title={`Final Preview - ${resumeTemplates.find((template) => template.id === templateId)?.name ?? "Selected Template"}`}>
          <ResumePreview resume={resume.parsed_json} templateId={templateId} />
        </Card>
      </div>
    </div>
  );
}
