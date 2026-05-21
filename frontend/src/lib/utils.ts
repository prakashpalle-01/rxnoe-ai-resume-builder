import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { ResumeJson } from "../types/resume";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function scoreLabel(score: number) {
  if (score >= 90) return "Excellent match";
  if (score >= 75) return "Strong match";
  if (score >= 60) return "Needs improvement";
  return "Weak match";
}

export function resumeDownloadName(resume: ResumeJson | null | undefined, extension: "pdf" | "docx") {
  const nameParts = (resume?.personal_info?.name || "").trim().split(/\s+/).filter(Boolean);
  const first = nameParts[0] || "FirstName";
  const last = nameParts.length > 1 ? nameParts[nameParts.length - 1] : "LastName";
  const role = resume?.target_title || resume?.experience?.[0]?.title || "Resume";
  const date = new Date().toISOString().slice(0, 10);
  return [first, last, role, date].map(filenamePart).join("_") + `.${extension}`;
}

function filenamePart(value: string) {
  return value.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "Resume";
}
