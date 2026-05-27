import type { ResumeJson } from "../types/resume";

export type EditTarget = {
  label: string;
  path: string;
  value: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  message: string;
  editType: "local" | "ai";
  targetSection: string;
  before?: string;
  after?: string;
  accepted?: boolean;
};

export type LocalEditResult = {
  handled: boolean;
  editType: "local" | "ai";
  message: string;
  before: string;
  after: string;
  targetSection: string;
  resume: ResumeJson;
  suggestions: string[];
};

const weakVerbRules: Array<[RegExp, string]> = [
  [/\bworked on\b/gi, "engineered"],
  [/\bhelped with\b/gi, "supported"],
  [/\bresponsible for\b/gi, "owned"],
  [/\binvolved in\b/gi, "contributed to"],
  [/\bparticipated in\b/gi, "contributed to"],
  [/\bmade\b/gi, "designed"],
  [/\bused\b/gi, "applied"]
];

const buzzwordRules: Array<[RegExp, string]> = [
  [/\bleveraged\b/gi, "used"],
  [/\bspearheaded\b/gi, "led"],
  [/\bcutting-edge\b/gi, "modern"],
  [/\brobust\b/gi, "reliable"],
  [/\bseamless\b/gi, "smooth"],
  [/\bdynamic\b/gi, "flexible"],
  [/\binnovative\b/gi, "practical"],
  [/\btransformative\b/gi, "useful"]
];

const knownSkills = {
  cloud: ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "CI/CD"],
  databases: ["SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "DynamoDB"],
  tools: ["Git", "Jira", "Excel", "Tableau", "Power BI", "Postman", "Figma"],
  soft_skills: ["Communication", "Leadership", "Collaboration", "Problem Solving"],
  technical: ["Java", "Python", "JavaScript", "TypeScript", "React", "Node", "FastAPI", "Spring Boot", "REST", "GraphQL", "Kafka", "LLM", "RAG", "Machine Learning"]
};

export function getEditableTargets(resume: ResumeJson): EditTarget[] {
  const targets: EditTarget[] = [
    { label: "Professional Summary", path: "summary", value: resume.summary ?? "" },
    { label: "Technical Skills", path: "skills", value: skillsToText(resume.skills) }
  ];

  resume.experience?.forEach((job, jobIndex) => {
    job.bullets?.forEach((bullet, bulletIndex) => {
      targets.push({
        label: `${job.title || "Experience"} bullet ${bulletIndex + 1}`,
        path: `experience.${jobIndex}.bullets.${bulletIndex}`,
        value: bullet
      });
    });
  });

  resume.projects?.forEach((project, projectIndex) => {
    project.bullets?.forEach((bullet, bulletIndex) => {
      targets.push({
        label: `${project.name || "Project"} bullet ${bulletIndex + 1}`,
        path: `projects.${projectIndex}.bullets.${bulletIndex}`,
        value: bullet
      });
    });
  });

  return targets;
}

export function applyLocalCommand(resume: ResumeJson, instruction: string, target: EditTarget, selectedText = "", jobDescription = ""): LocalEditResult {
  const lower = instruction.toLowerCase();
  const before = selectedText || target.value;
  let after = before;
  let suggestions: string[] = [];
  let handled = true;

  if (matches(lower, ["fix grammar", "grammar", "clean"])) after = fixGrammar(after);
  else if (matches(lower, ["shorten", "concise", "make concise"])) after = shortenText(after);
  else if (matches(lower, ["action verb", "weak verb", "better bullet", "bullet better"])) after = improveActionVerbs(after);
  else if (matches(lower, ["remove ai tone", "human", "buzzword"])) after = removeAIBuzzwords(after);
  else if (matches(lower, ["format skills", "reorder skills", "duplicate skills", "clean skills"])) after = skillsToText(cleanSkills(resume.skills, jobDescription));
  else if (matches(lower, ["bullet formatting", "fix bullet"])) after = fixBulletFormatting(after);
  else if (matches(lower, ["paragraph to bullets", "convert to bullets"])) after = paragraphToBullets(after);
  else if (matches(lower, ["ats", "ats friendly", "formatting validator"])) suggestions = validateATS(resume);
  else if (matches(lower, ["repeated words", "duplicate words"])) suggestions = detectRepeatedWords(before);
  else if (matches(lower, ["weak bullets", "weak verbs"])) suggestions = detectWeakBullets(resume);
  else if (matches(lower, ["duplicate sections"])) suggestions = detectDuplicateSections(resume);
  else if (matches(lower, ["score", "keyword", "match"])) suggestions = generateSuggestions(resume, jobDescription);
  else handled = false;

  const editedResume = suggestions.length > 0 && after === before ? resume : updateResumeAtPath(resume, target.path, selectedText ? target.value.replace(selectedText, after) : after);

  return {
    handled,
    editType: handled ? "local" : "ai",
    message: handled ? "Free local edit ready. Review the before/after and accept it if it looks right." : "This looks like a deep rewrite. Use AI Optimize to batch the request.",
    before,
    after,
    targetSection: target.label,
    resume: editedResume,
    suggestions,
  };
}

export function detectWeakBullets(resume: ResumeJson): string[] {
  const weak = ["worked on", "helped with", "responsible for", "involved in", "participated in"];
  const bullets = [
    ...(resume.experience ?? []).flatMap((job) => job.bullets ?? []),
    ...(resume.projects ?? []).flatMap((project) => project.bullets ?? [])
  ];
  return bullets
    .filter((bullet) => weak.some((phrase) => bullet.toLowerCase().includes(phrase)))
    .map((bullet) => `Weak bullet: ${bullet}`);
}

export function replaceWeakVerbs(text: string) {
  return weakVerbRules.reduce((value, [pattern, replacement]) => value.replace(pattern, replacement), text);
}

export function removeAIBuzzwords(text: string) {
  return buzzwordRules.reduce((value, [pattern, replacement]) => value.replace(pattern, replacement), text);
}

export function validateATS(resume: ResumeJson): string[] {
  const warnings: string[] = [];
  if (!resume.summary?.trim()) warnings.push("Missing professional summary.");
  if (!Object.values(resume.skills ?? {}).some((group) => group.length > 0)) warnings.push("Missing technical skills section.");
  if (!resume.education?.length) warnings.push("Missing education section.");
  if ((resume.summary ?? "").split(/\s+/).length > 90) warnings.push("Summary is too long for recruiter scanning.");
  const bullets = (resume.experience ?? []).flatMap((job) => job.bullets ?? []);
  if (bullets.some((bullet) => bullet.length > 210)) warnings.push("One or more bullets are too long.");
  if (detectDuplicateSections(resume).length) warnings.push("Duplicate section content detected.");
  if (detectWeakBullets(resume).length) warnings.push("Weak verbs found in bullets.");
  return warnings.length ? warnings : ["ATS formatting looks clean: single-column sections, skills, bullets, and readable structure."];
}

export function cleanSkills(skills: ResumeJson["skills"], jobDescription = ""): ResumeJson["skills"] {
  const all = Object.values(skills ?? {}).flat().filter(Boolean);
  const deduped = unique(all);
  const jd = jobDescription.toLowerCase();
  const grouped: ResumeJson["skills"] = emptySkills();

  for (const skill of deduped) {
    const group = Object.entries(knownSkills).find(([, values]) => values.some((value) => value.toLowerCase() === skill.toLowerCase()))?.[0] as keyof ResumeJson["skills"] | undefined;
    grouped[group ?? "technical"].push(skill);
  }

  for (const key of Object.keys(grouped) as Array<keyof ResumeJson["skills"]>) {
    grouped[key] = grouped[key].sort((a, b) => Number(jd.includes(b.toLowerCase())) - Number(jd.includes(a.toLowerCase())));
  }

  return grouped;
}

export function scoreResumeLocally(resume: ResumeJson, jobDescription = "") {
  const suggestions = generateSuggestions(resume, jobDescription);
  const keywordScore = keywordMatch(resume, jobDescription).score;
  const sectionScore = ["summary", "experience", "education"].filter((key) => Boolean((resume as any)[key]?.length)).length * 20 + (Object.values(resume.skills).some((items) => items.length) ? 20 : 0);
  const bulletScore = Math.max(20, 100 - detectWeakBullets(resume).length * 15);
  const formattingScore = validateATS(resume).length <= 1 ? 92 : 70;
  const readabilityScore = suggestions.some((item) => item.includes("too long")) ? 72 : 88;
  return {
    keywordScore,
    sectionCompleteness: Math.min(100, sectionScore),
    bulletQuality: bulletScore,
    formattingScore,
    readabilityScore,
    overall: Math.round((keywordScore + Math.min(100, sectionScore) + bulletScore + formattingScore + readabilityScore) / 5)
  };
}

export function generateSuggestions(resume: ResumeJson, jobDescription = ""): string[] {
  const suggestions = [...validateATS(resume)];
  const { missing } = keywordMatch(resume, jobDescription);
  suggestions.push(...missing.slice(0, 8).map((keyword) => `Missing ${keyword} keyword. Add only if truthful.`));
  if ((resume.summary ?? "").split(/\s+/).length > 80) suggestions.push("Summary too long. Keep it to 3-5 concise lines.");
  detectWeakBullets(resume).slice(0, 5).forEach((item) => suggestions.push(item));
  const duplicateSkills = findDuplicates(Object.values(resume.skills ?? {}).flat());
  duplicateSkills.forEach((skill) => suggestions.push(`Duplicate skill found: ${skill}`));
  if (!resume.projects?.length) suggestions.push("Add a project section if projects are relevant to the target role.");
  return unique(suggestions);
}

export function skillsToText(skills: ResumeJson["skills"]) {
  return Object.entries(skills ?? {})
    .filter(([, values]) => values.length > 0)
    .map(([group, values]) => `${label(group)}: ${values.join(", ")}`)
    .join("\n");
}

export function textToSkills(text: string): ResumeJson["skills"] {
  const grouped: ResumeJson["skills"] = emptySkills();
  text.split("\n").forEach((line) => {
    const [rawGroup, rawValues] = line.split(":");
    const key = (rawGroup || "technical").toLowerCase().replace(/\s+/g, "_") as keyof ResumeJson["skills"];
    const values = (rawValues ?? line).split(",").map((item) => item.trim()).filter(Boolean);
    if (key in grouped) grouped[key] = unique([...(grouped[key] ?? []), ...values]);
    else grouped.technical = unique([...grouped.technical, ...values]);
  });
  return cleanSkills(grouped);
}

function updateResumeAtPath(resume: ResumeJson, path: string, value: string): ResumeJson {
  const next = structuredClone(resume);
  if (path === "summary") next.summary = value;
  else if (path === "skills") next.skills = textToSkills(value);
  else {
    const parts = path.split(".");
    let pointer: any = next;
    for (let index = 0; index < parts.length - 1; index += 1) pointer = pointer[parts[index] as any];
    pointer[parts[parts.length - 1]] = value;
  }
  return next;
}

function fixGrammar(text: string) {
  return text
    .replace(/\s+/g, " ")
    .replace(/\s+([,.])/g, "$1")
    .replace(/\bi\b/g, "I")
    .replace(/(^|[.!?]\s+)([a-z])/g, (_, prefix, letter) => `${prefix}${letter.toUpperCase()}`)
    .trim();
}

function shortenText(text: string) {
  const words = text.split(/\s+/);
  if (words.length <= 22) return text;
  return words.filter((word) => !["very", "really", "successfully", "various", "multiple", "different"].includes(word.toLowerCase())).slice(0, 26).join(" ").replace(/[,;:]$/, "") + ".";
}

function improveActionVerbs(text: string) {
  return restoreAcronyms(fixGrammar(replaceWeakVerbs(text)));
}

function fixBulletFormatting(text: string) {
  return text.split("\n").map((line) => line.trim().replace(/^[-•*]\s*/, "")).filter(Boolean).map((line) => `- ${fixGrammar(line)}`).join("\n");
}

function paragraphToBullets(text: string) {
  return text.split(/(?<=[.!?])\s+/).filter(Boolean).map((sentence) => `- ${fixGrammar(sentence)}`).join("\n");
}

function detectRepeatedWords(text: string) {
  const words = text.toLowerCase().match(/\b[a-z]{3,}\b/g) ?? [];
  return findDuplicates(words).map((word) => `Repeated word: ${word}`);
}

function detectDuplicateSections(resume: ResumeJson) {
  const sections = [resume.summary, skillsToText(resume.skills), ...(resume.education ?? []), ...(resume.certifications ?? [])].filter(Boolean);
  return findDuplicates(sections).map((section) => `Duplicate section/content detected: ${section.slice(0, 80)}`);
}

function keywordMatch(resume: ResumeJson, jobDescription = "") {
  const keywords = unique((jobDescription.match(/\b[A-Za-z][A-Za-z+#./-]{2,}\b/g) ?? []).filter((word) => word.length > 3)).slice(0, 40);
  const text = JSON.stringify(resume).toLowerCase();
  const matched = keywords.filter((keyword) => text.includes(keyword.toLowerCase()));
  const missing = keywords.filter((keyword) => !text.includes(keyword.toLowerCase()));
  return { matched, missing, score: keywords.length ? Math.round((matched.length / keywords.length) * 100) : 75 };
}

function restoreAcronyms(text: string) {
  return text.replace(/\bapis\b/gi, "APIs").replace(/\bsql\b/gi, "SQL").replace(/\baws\b/gi, "AWS").replace(/\bui\b/gi, "UI");
}

function matches(value: string, terms: string[]) {
  return terms.some((term) => value.includes(term));
}

function unique(values: string[]) {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = value.trim().toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function findDuplicates(values: string[]) {
  const counts = new Map<string, number>();
  values.forEach((value) => counts.set(value.toLowerCase(), (counts.get(value.toLowerCase()) ?? 0) + 1));
  return [...counts.entries()].filter(([, count]) => count > 1).map(([value]) => value);
}

function label(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function emptySkills(): ResumeJson["skills"] {
  return {
    ai_ml_core: [],
    deep_learning: [],
    genai_llm_systems: [],
    frameworks_libraries: [],
    mlops_engineering: [],
    cloud_infrastructure: [],
    databases_vector_stores: [],
    messaging_streaming: [],
    programming: [],
    monitoring_observability: [],
    ai_safety_compliance: [],
    developer_tools: [],
    technical: [],
    tools: [],
    cloud: [],
    databases: [],
    soft_skills: []
  };
}
