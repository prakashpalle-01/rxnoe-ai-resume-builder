import { Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
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
    if (!id) return;
    const response = await api.get(`/resumes/${id}/export/${type}`, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = `rxnoe-resume-${id}.${type}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function chooseTemplate(value: ResumeTemplateId) {
    setTemplateId(value);
    localStorage.setItem("rxnoe_template", value);
  }

  if (!resume) return <p className="text-rx-muted">Loading download page...</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
      <Card title="Download Resume">
        <div className="space-y-3">
          <p className="text-sm text-rx-muted">Export an ATS-safe, selectable-text resume. Use DOCX when you need to edit after download.</p>
          <select className="h-10 w-full rounded-md border border-rx-line bg-white px-3 text-sm" value={templateId} onChange={(event) => chooseTemplate(event.target.value as ResumeTemplateId)}>
            {resumeTemplates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
          </select>
          <Button className="w-full" onClick={() => exportFile("pdf")}><Download size={17} /> Download PDF</Button>
          <SecondaryButton className="w-full" onClick={() => exportFile("docx")}><FileText size={17} /> Download DOCX</SecondaryButton>
          <Link to={`/resume-editor/${id}`}><SecondaryButton className="w-full">Back to editor</SecondaryButton></Link>
        </div>
      </Card>
      <Card title="Final Preview">
        <ResumePreview resume={resume.parsed_json} templateId={templateId} />
      </Card>
    </div>
  );
}
