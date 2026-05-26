import { FileText, LayoutTemplate, UploadCloud } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Button, Card, Input, SecondaryButton, Textarea } from "../components/ui";

export function UploadResumePage() {
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<"file" | "paste">(searchParams.get("mode") === "paste" ? "paste" : "file");
  const [file, setFile] = useState<File | null>(null);
  const [pastedText, setPastedText] = useState("");
  const [pastedTitle, setPastedTitle] = useState("Pasted Resume");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function upload() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append("file", file);
      const response = await api.post("/resumes/upload", data);
      await api.post(`/resumes/${response.data.id}/parse`);
      navigate(`/paste-job-description/${response.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Upload failed. Check the file and try again.");
    } finally {
      setBusy(false);
    }
  }

  async function generateFromText() {
    if (pastedText.trim().length < 40) {
      setError("Paste at least a few lines of your resume before generating a template.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await api.post("/resumes/paste", { text: pastedText, title: pastedTitle });
      navigate(`/download/${response.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Could not create a resume from the pasted text.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-normal">Create a resume</h1>
        <p className="mt-2 text-sm text-rx-muted">Upload a document for job targeting, or paste resume text to instantly generate a downloadable design.</p>
      </div>
      <div className="inline-flex rounded-md border border-rx-line bg-white p-1">
        <button className={`inline-flex min-h-10 items-center gap-2 rounded-md px-4 text-sm font-semibold ${mode === "file" ? "bg-rx-blue text-white" : "text-slate-700"}`} onClick={() => { setMode("file"); setError(""); }}>
          <UploadCloud size={17} /> Upload file
        </button>
        <button className={`inline-flex min-h-10 items-center gap-2 rounded-md px-4 text-sm font-semibold ${mode === "paste" ? "bg-rx-blue text-white" : "text-slate-700"}`} onClick={() => { setMode("paste"); setError(""); }}>
          <FileText size={17} /> Paste resume text
        </button>
      </div>
      {mode === "file" ? (
        <Card title="Upload Resume">
          <div className="rounded-lg border-2 border-dashed border-rx-line bg-slate-50 p-10 text-center">
            <UploadCloud className="mx-auto text-rx-blue" size={38} />
            <h2 className="mt-4 text-2xl font-bold">Upload your existing resume</h2>
            <p className="mt-2 text-sm text-rx-muted">PDF or DOCX, up to 5MB. Images, locked files, and corrupted documents are rejected.</p>
            <input
              className="mt-6 w-full max-w-sm rounded-md border border-rx-line bg-white p-2 text-sm"
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            {file && <p className="mt-3 text-sm font-medium">{file.name}</p>}
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            <Button className="mt-6" disabled={!file || busy} onClick={upload}>
              {busy ? "Extracting and parsing..." : "Upload and continue"}
            </Button>
          </div>
        </Card>
      ) : (
        <Card title="Paste Resume And Generate Template">
          <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_230px]">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Resume text</label>
              <Textarea className="min-h-[390px]" placeholder={"Paste your resume here, including contact details, summary, skills, experience, projects, and education."} value={pastedText} onChange={(event) => setPastedText(event.target.value)} />
              {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            </div>
            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Resume name</label>
                <Input value={pastedTitle} onChange={(event) => setPastedTitle(event.target.value)} placeholder="Pasted Resume" />
              </div>
              <div className="rounded-md border border-rx-line bg-slate-50 p-4 text-sm text-slate-700">
                <LayoutTemplate className="mb-3 text-rx-blue" size={22} />
                <p className="font-semibold">Next step</p>
                <p className="mt-2 text-rx-muted">The app parses your text and opens 10 ATS-friendly resume designs with PDF and DOCX download.</p>
              </div>
              <Button className="w-full" disabled={pastedText.trim().length < 40 || busy} onClick={generateFromText}>
                <LayoutTemplate size={17} /> {busy ? "Generating..." : "Generate Templates"}
              </Button>
              <SecondaryButton className="w-full" onClick={() => setPastedText("")} disabled={!pastedText || busy}>Clear text</SecondaryButton>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
