import { create } from "zustand";
import type { AtsScore, ResumeRecord } from "../types/resume";

type AppState = {
  userEmail: string | null;
  resumes: ResumeRecord[];
  currentResume: ResumeRecord | null;
  atsScore: AtsScore | null;
  jobDescription: string;
  setUserEmail: (email: string | null) => void;
  setResumes: (resumes: ResumeRecord[]) => void;
  setCurrentResume: (resume: ResumeRecord | null) => void;
  setAtsScore: (score: AtsScore | null) => void;
  setJobDescription: (value: string) => void;
};

export const useAppStore = create<AppState>((set) => ({
  userEmail: localStorage.getItem("rxnoe_email"),
  resumes: [],
  currentResume: null,
  atsScore: null,
  jobDescription: "",
  setUserEmail: (email) => set({ userEmail: email }),
  setResumes: (resumes) => set({ resumes }),
  setCurrentResume: (resume) => set({ currentResume: resume }),
  setAtsScore: (score) => set({ atsScore: score }),
  setJobDescription: (value) => set({ jobDescription: value })
}));
