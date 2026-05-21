import { FileText, Gauge, Target, Trash2, UploadCloud } from "lucide-react";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Badge, Button, Card, ProgressBar } from "../components/ui";
import { useAppStore } from "../store/app-store";

export function DashboardPage() {
  const { resumes, setResumes } = useAppStore();
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    api.get("/resumes").then((response) => setResumes(response.data)).catch(() => setResumes([]));
  }, [setResumes]);

  async function deleteResume(id: number) {
    setDeletingId(id);
    setDeleteError("");
    try {
      await api.delete(`/resumes/${id}`);
      setResumes(resumes.filter((resume) => resume.id !== id));
    } catch (err: any) {
      setDeleteError(err.response?.data?.detail ?? "Could not delete this resume.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col justify-between gap-4 rounded-lg border border-rx-line bg-white p-6 shadow-panel md:flex-row md:items-center">
        <div>
          <Badge tone="green">Focused resume generator</Badge>
          <h1 className="mt-3 text-3xl font-bold tracking-normal">Upload resume. Paste job description. Generate the strongest ATS-friendly version.</h1>
          <p className="mt-2 max-w-2xl text-rx-muted">RxNoe optimizes for the highest truthful match, recruiter readability, clean formatting, and interview chances.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link to="/upload-resume"><Button><UploadCloud size={18} /> Upload resume</Button></Link>
          <Link to="/paste-job-description/latest"><Button className="bg-rx-green hover:bg-emerald-700"><Target size={18} /> Generate resume</Button></Link>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-4">
        <Metric icon={FileText} label="Uploaded resumes" value={resumes.length} />
        <Metric icon={Gauge} label="Optimized versions" value={resumes.length} />
        <Metric icon={Target} label="Best match mode" value="On" />
        <Metric icon={UploadCloud} label="Exports" value="PDF/DOCX" />
      </div>

      <Card title="Recent Resumes">
        <div className="space-y-3">
          {deleteError && <p className="rounded-md bg-red-50 p-3 text-sm text-red-600">{deleteError}</p>}
          {resumes.length === 0 && <p className="text-sm text-rx-muted">No resumes yet. Upload a PDF or DOCX to start.</p>}
          {resumes.map((resume) => (
            <div key={resume.id} className="flex flex-col gap-3 rounded-md border border-rx-line p-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="font-semibold">{resume.title}</p>
                <p className="text-sm text-rx-muted">{resume.filename}</p>
              </div>
              <div className="w-full md:w-52">
                <ProgressBar value={resume.parsed_json?.summary ? 76 : 42} />
                <p className="mt-1 text-xs text-rx-muted">Parsing confidence preview</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to={`/paste-job-description/${resume.id}`}><Button><Target size={16} /> Generate</Button></Link>
                <button className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-red-200 bg-white px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60" disabled={deletingId === resume.id} onClick={() => deleteResume(resume.id)}>
                  <Trash2 size={16} /> {deletingId === resume.id ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof FileText; label: string; value: string | number }) {
  return (
    <Card>
      <Icon className="mb-3 text-rx-blue" size={22} />
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-sm text-rx-muted">{label}</p>
    </Card>
  );
}
