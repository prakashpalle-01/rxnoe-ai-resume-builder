import { UploadCloud } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Button, Card } from "../components/ui";

export function UploadResumePage() {
  const [file, setFile] = useState<File | null>(null);
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

  return (
    <div className="mx-auto max-w-3xl">
      <Card title="Upload Resume">
        <div className="rounded-lg border-2 border-dashed border-rx-line bg-slate-50 p-10 text-center">
          <UploadCloud className="mx-auto text-rx-blue" size={38} />
          <h1 className="mt-4 text-2xl font-bold">Upload your existing resume</h1>
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
    </div>
  );
}
