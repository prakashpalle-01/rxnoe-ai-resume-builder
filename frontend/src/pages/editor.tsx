import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Bot, Check, Download, RefreshCw, RotateCcw, Save, Search, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { resumeDownloadName } from "../lib/utils";
import { applyLocalCommand, generateSuggestions, getEditableTargets, scoreResumeLocally, textToSkills, type ChatMessage, type LocalEditResult } from "../lib/local-resume-engine";
import { Button, Card, SecondaryButton, Textarea, Badge, ProgressBar } from "../components/ui";
import { ResumePreview } from "../components/resume-preview";
import { defaultTemplateId, resumeTemplates, type ResumeTemplateId } from "../lib/resume-templates";
import { useAppStore } from "../store/app-store";
import type { ResumeJson, ResumeVersion } from "../types/resume";

const quickCommands = ["fix grammar", "shorten", "improve action verbs", "remove AI tone", "format skills", "check ATS formatting", "detect weak bullets"];

export function ResumeEditorPage() {
  const { id } = useParams();
  const { currentResume, setCurrentResume } = useAppStore();
  const [draftResume, setDraftResume] = useState<ResumeJson | null>(null);
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [selectedPath, setSelectedPath] = useState("summary");
  const [instruction, setInstruction] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState<LocalEditResult | null>(null);
  const [undoStack, setUndoStack] = useState<ResumeJson[]>([]);
  const [busy, setBusy] = useState("");
  const [templateId, setTemplateId] = useState<ResumeTemplateId>((localStorage.getItem("rxnoe_template") as ResumeTemplateId) || defaultTemplateId);
  const aiCache = useRef(new Map<string, ResumeJson>());

  useEffect(() => {
    if (!id) return;
    api.get(`/resumes/${id}`).then((response) => {
      setCurrentResume(response.data);
      setDraftResume(response.data.parsed_json);
    });
    refreshVersions();
  }, [id, setCurrentResume]);

  const targets = useMemo(() => draftResume ? getEditableTargets(draftResume) : [], [draftResume]);
  const selectedTarget = targets.find((target) => target.path === selectedPath) ?? targets[0];
  const previewResume = pending?.resume ?? draftResume;
  const localScore = draftResume ? scoreResumeLocally(draftResume, jobDescription) : null;

  const editor = useEditor({
    extensions: [StarterKit],
    content: textToHtml(selectedTarget?.value ?? ""),
    editorProps: {
      attributes: {
        class: "min-h-[260px] rounded-md border border-rx-line bg-white p-4 text-sm leading-6 outline-none focus:ring-4 focus:ring-rx-blue/10"
      }
    },
    onUpdate({ editor }) {
      if (!draftResume || !selectedTarget) return;
      const value = editor.getText({ blockSeparator: "\n" });
      setDraftResume(updateResumeAtPath(draftResume, selectedTarget.path, value));
    }
  });

  useEffect(() => {
    if (editor && selectedTarget) editor.commands.setContent(textToHtml(selectedTarget.value), { emitUpdate: false });
  }, [editor, selectedPath]);

  function refreshVersions() {
    if (!id) return;
    api.get(`/resumes/${id}/versions`).then((response) => setVersions(response.data)).catch(() => setVersions([]));
  }

  async function save() {
    if (!id || !draftResume) return;
    setBusy("save");
    const response = await api.put(`/resumes/${id}`, { parsed_json: draftResume });
    setCurrentResume(response.data);
    setDraftResume(response.data.parsed_json);
    refreshVersions();
    setBusy("");
  }

  async function reparse() {
    if (!id) return;
    setBusy("reparse");
    const response = await api.post(`/resumes/${id}/parse`);
    setCurrentResume(response.data);
    setDraftResume(response.data.parsed_json);
    refreshVersions();
    setBusy("");
  }

  async function runChatCommand(command = instruction) {
    if (!draftResume || !selectedTarget || !command.trim()) return;
    const selectedText = getSelectedEditorText();
    const result = applyLocalCommand(draftResume, command, selectedTarget, selectedText, jobDescription);
    const userMessage = newMessage("user", command, "local", selectedTarget.label);
    const assistantMessage = newMessage("assistant", result.message, result.editType, selectedTarget.label, result.before, result.after);
    setMessages((items) => [...items, userMessage, assistantMessage]);
    setInstruction("");
    if (result.handled) setPending(result);
  }

  async function runAiOptimize(label = "AI Optimize") {
    if (!id || !draftResume) return;
    if (!window.confirm("This uses AI credits. Continue?")) return;
    const cacheKey = `${id}:${label}:${jobDescription}:${JSON.stringify(draftResume).slice(0, 2000)}`;
    const cached = aiCache.current.get(cacheKey);
    if (cached) {
      setUndoStack((items) => [draftResume, ...items]);
      setDraftResume(cached);
      setMessages((items) => [...items, newMessage("assistant", "Loaded cached AI result. No new API call used.", "ai", "Full resume")]);
      return;
    }
    setBusy(label);
    await api.put(`/resumes/${id}`, { parsed_json: draftResume });
    const response = await api.post(`/resumes/${id}/optimize`, {
      instruction: label === "Deep Rewrite" ? "Deep resume rewrite" : "AI optimize resume",
      job_description: jobDescription || undefined
    });
    aiCache.current.set(cacheKey, response.data.parsed_json);
    setUndoStack((items) => [draftResume, ...items]);
    setDraftResume(response.data.parsed_json);
    setCurrentResume(response.data);
    setMessages((items) => [...items, newMessage("assistant", `${label} complete. Review the preview and save/export when ready.`, "ai", "Full resume")]);
    refreshVersions();
    setBusy("");
  }

  function acceptPending() {
    if (!pending || !draftResume) return;
    setUndoStack((items) => [draftResume, ...items]);
    setDraftResume(pending.resume);
    if (editor) editor.commands.setContent(textToHtml(pending.after), { emitUpdate: false });
    setMessages((items) => items.map((message) => message.before === pending.before && message.after === pending.after ? { ...message, accepted: true } : message));
    setPending(null);
  }

  function rejectPending() {
    setPending(null);
  }

  function undo() {
    const [previous, ...rest] = undoStack;
    if (!previous) return;
    setDraftResume(previous);
    const target = getEditableTargets(previous).find((item) => item.path === selectedPath);
    if (editor && target) editor.commands.setContent(textToHtml(target.value), { emitUpdate: false });
    setUndoStack(rest);
  }

  async function exportFile(type: "pdf" | "docx") {
    if (!id || !draftResume) return;
    await save();
    const response = await api.get(`/resumes/${id}/export/${type}`, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = resumeDownloadName(draftResume, type);
    link.click();
    URL.revokeObjectURL(url);
  }

  function getSelectedEditorText() {
    if (!editor) return "";
    const { from, to } = editor.state.selection;
    return from === to ? "" : editor.state.doc.textBetween(from, to, " ");
  }

  if (!currentResume || !draftResume || !previewResume) return <p className="text-rx-muted">Loading resume...</p>;

  function chooseTemplate(value: ResumeTemplateId) {
    setTemplateId(value);
    localStorage.setItem("rxnoe_template", value);
  }

  return (
    <div className="grid gap-5 2xl:grid-cols-[360px_minmax(420px,0.9fr)_minmax(520px,1fr)]">
      <div className="space-y-4">
        <Card title="Resume Chat" action={<Badge tone="green">Free local edit</Badge>}>
          <div className="mb-3 max-h-[300px] space-y-3 overflow-auto rounded-md border border-rx-line bg-slate-50 p-3">
            {messages.length === 0 && <p className="text-sm text-rx-muted">Ask for local edits like “fix grammar,” “shorten,” “remove AI tone,” or “make this bullet better.” Select text in the editor to target only that text.</p>}
            {messages.map((message) => (
              <div key={message.id} className={message.role === "user" ? "text-right" : "text-left"}>
                <div className={`inline-block max-w-[92%] rounded-md px-3 py-2 text-sm ${message.role === "user" ? "bg-rx-blue text-white" : "bg-white text-slate-800"}`}>
                  <p>{message.message}</p>
                  <p className="mt-1 text-[11px] opacity-75">{message.editType === "local" ? "Free local edit" : "AI edit uses credits"}</p>
                </div>
              </div>
            ))}
          </div>
          <Textarea className="min-h-24" placeholder="Type: improve my summary, shorten this bullet, check ATS formatting..." value={instruction} onChange={(event) => setInstruction(event.target.value)} />
          <Button className="mt-3 w-full" onClick={() => runChatCommand()} disabled={!instruction.trim()}><Bot size={17} /> Send</Button>
          <div className="mt-3 flex flex-wrap gap-2">
            {quickCommands.map((command) => <SecondaryButton key={command} className="min-h-8 px-2 py-1 text-xs" onClick={() => runChatCommand(command)}>{command}</SecondaryButton>)}
          </div>
        </Card>

        <Card title="AI Controls" action={<Badge tone="amber">AI edit uses credits</Badge>}>
          <Textarea className="mb-3 min-h-28" placeholder="Optional: paste job description here for AI Optimize or local keyword checks." value={jobDescription} onChange={(event) => setJobDescription(event.target.value)} />
          <div className="grid gap-2">
            <Button disabled={Boolean(busy)} onClick={() => runAiOptimize("AI Optimize")}><Sparkles size={17} /> {busy === "AI Optimize" ? "Optimizing..." : "AI Optimize"}</Button>
            <SecondaryButton disabled={Boolean(busy)} onClick={() => runAiOptimize("Deep Rewrite")}><Sparkles size={17} /> Deep Rewrite</SecondaryButton>
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card
          title="Editable Resume Sections"
          action={
            <div className="flex flex-wrap gap-2">
              <SecondaryButton onClick={undo} disabled={undoStack.length === 0}><RotateCcw size={16} /> Undo</SecondaryButton>
              <SecondaryButton onClick={reparse} disabled={Boolean(busy)}><RefreshCw size={16} /> Re-parse</SecondaryButton>
              <SecondaryButton onClick={save} disabled={busy === "save"}><Save size={16} /> Save</SecondaryButton>
              <Link to={`/job-match/${id}`}><Button><Search size={16} /> Match job</Button></Link>
            </div>
          }
        >
          <select className="mb-3 h-10 w-full rounded-md border border-rx-line bg-white px-3 text-sm" value={selectedPath} onChange={(event) => setSelectedPath(event.target.value)}>
            {targets.map((target) => <option key={target.path} value={target.path}>{target.label}</option>)}
          </select>
          <EditorContent editor={editor} />
          <p className="mt-2 text-xs text-rx-muted">Tip: highlight text inside this editor, then ask the chat to edit only the selected text.</p>
        </Card>

        {pending && (
          <Card title="Before / After Diff" action={<div className="flex gap-2"><Button onClick={acceptPending}><Check size={16} /> Accept</Button><SecondaryButton onClick={rejectPending}><X size={16} /> Reject</SecondaryButton></div>}>
            <div className="grid gap-3 md:grid-cols-2">
              <DiffPanel title="Before" text={pending.before} />
              <DiffPanel title="After" text={pending.after} />
            </div>
            {pending.suggestions.length > 0 && <ul className="mt-3 list-disc pl-5 text-sm text-rx-muted">{pending.suggestions.map((item) => <li key={item}>{item}</li>)}</ul>}
          </Card>
        )}

        <Card title="Local ATS Checks">
          {localScore && (
            <div className="space-y-3">
              <ScoreRow label="Overall" value={localScore.overall} />
              <ScoreRow label="Keyword match" value={localScore.keywordScore} />
              <ScoreRow label="Sections" value={localScore.sectionCompleteness} />
              <ScoreRow label="Bullet quality" value={localScore.bulletQuality} />
              <div className="space-y-2 pt-2">
                {generateSuggestions(draftResume, jobDescription).slice(0, 8).map((item) => <p className="rounded-md bg-slate-50 p-2 text-sm text-slate-700" key={item}>{item}</p>)}
              </div>
            </div>
          )}
        </Card>

        <Card title="Version History">
          <div className="space-y-3">
            {versions.length === 0 && <p className="text-sm text-rx-muted">No saved versions yet. Save or generate an optimized resume to create history.</p>}
            {versions.map((version) => (
              <button key={version.id} className="w-full rounded-md border border-rx-line p-3 text-left hover:bg-slate-50" onClick={() => {
                setDraftResume(version.resume_json);
                const target = getEditableTargets(version.resume_json).find((item) => item.path === selectedPath);
                if (editor && target) editor.commands.setContent(textToHtml(target.value), { emitUpdate: false });
              }}>
                <p className="text-sm font-semibold">{version.version_name}</p>
                <p className="text-xs text-rx-muted">{version.change_summary || "Saved resume version"}</p>
              </button>
            ))}
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card title="Live Resume Preview" action={<div className="flex flex-wrap gap-2"><Link to={`/download/${id}`}><SecondaryButton><Download size={16} /> Download page</SecondaryButton></Link><Button onClick={() => exportFile("pdf")}><Download size={16} /> PDF</Button><SecondaryButton onClick={() => exportFile("docx")}>DOCX</SecondaryButton></div>}>
          <select className="mb-3 h-10 w-full rounded-md border border-rx-line bg-white px-3 text-sm" value={templateId} onChange={(event) => chooseTemplate(event.target.value as ResumeTemplateId)}>
            {resumeTemplates.map((template) => <option key={template.id} value={template.id}>{template.name} - {template.description}</option>)}
          </select>
          <ResumePreview resume={previewResume} templateId={templateId} />
        </Card>
      </div>
    </div>
  );
}

function DiffPanel({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-md border border-rx-line bg-white p-3">
      <p className="mb-2 text-sm font-semibold">{title}</p>
      <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{text || "No content"}</p>
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm"><span>{label}</span><strong>{value}</strong></div>
      <ProgressBar value={value} />
    </div>
  );
}

function newMessage(role: "user" | "assistant", message: string, editType: "local" | "ai", targetSection: string, before?: string, after?: string): ChatMessage {
  return { id: crypto.randomUUID(), role, message, editType, targetSection, before, after, accepted: false };
}

function textToHtml(text: string) {
  const lines = text.split("\n").filter(Boolean);
  if (lines.length === 0) return "<p></p>";
  return lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("");
}

function escapeHtml(value: string) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function updateResumeAtPath(resume: ResumeJson, path: string, value: string): ResumeJson {
  const next = structuredClone(resume);
  if (path === "summary") next.summary = value;
  else if (path === "skills") {
    next.skills = textToSkills(value);
  } else {
    const parts = path.split(".");
    let pointer: any = next;
    for (let index = 0; index < parts.length - 1; index += 1) pointer = pointer[parts[index] as any];
    pointer[parts[parts.length - 1]] = value;
  }
  return next;
}
