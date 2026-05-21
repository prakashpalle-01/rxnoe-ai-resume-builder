import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function scoreLabel(score: number) {
  if (score >= 90) return "Excellent match";
  if (score >= 75) return "Strong match";
  if (score >= 60) return "Needs improvement";
  return "Weak match";
}
