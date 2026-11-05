/**
 * "Upload resume": PDF -> text (pdftotext) -> a local Ollama chat model drafts the player's expertise and tags.
 * Nothing is stored: the PDF lives in a temp file for the length of one request.
 */
import { execFile } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import * as match from "./match.ts";

const run = promisify(execFile);

export const cfg = {
  model: process.env.RESUME_MODEL || "qwen3-vl:4b",
};
export const MAX_PDF = 5 * 1024 * 1024;

export interface Draft {
  expertise: string;
  tags: string[];
}

export async function pdfText(data: Buffer): Promise<string> {
  if (!data.subarray(0, 4).equals(Buffer.from("%PDF"))) throw new RangeError("That file isn't a PDF.");
  const dir = mkdtempSync(join(tmpdir(), "resume-"));
  let out = "";
  try {
    const file = join(dir, "resume.pdf");
    writeFileSync(file, data);
    out = (await run("pdftotext", ["-q", "-layout", file, "-"], { timeout: 30_000, maxBuffer: 64 * 1024 * 1024 })).stdout;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  const text = out.split(/\s+/).filter(Boolean).join(" ");
  if (text.length < 100) throw new RangeError("Couldn't read any text in that PDF (is it a scanned image?).");
  return text.slice(0, 12000);
}

async function chat(prompt: string): Promise<Record<string, unknown>> {
  const body = { model: cfg.model, stream: false, format: "json", think: false, options: { temperature: 0.2 }, messages: [{ role: "user", content: prompt }] };
  const res = await fetch(`${match.cfg.ollamaUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(180_000),
  });
  if (!res.ok) throw new Error(`chat: HTTP ${res.status}`);
  const msg = ((await res.json()) as { message: { content?: string; thinking?: string } }).message;
  // With think=false, Ollama returns qwen3-vl's answer in "thinking" rather than "content"; take either.
  return JSON.parse(msg.content || msg.thinking || "{}") as Record<string, unknown>;
}

/** Tags for a player's expertise text: existing game tags where one means the same thing, else short custom tags. */
export async function suggestTags(expertise: string, vocabulary: string[]): Promise<string[]> {
  const out = await chat(
    "For a trivia party game, pick 6-12 short topic tags for what this person could confidently talk about.\n" +
      'Return JSON only: {"tags": ["..."]}. Use tags from this list whenever one fits, ' +
      "and only invent a short new tag (1-3 words) for something the list doesn't cover. " +
      'Tags are subjects ("Robotics", "Military History"), never roles or traits ("Hobbyist", "Expert"): ' +
      vocabulary.join(", ") +
      "\n\nEXPERTISE:\n" +
      expertise.slice(0, 2000),
  );
  const picked: string[] = [];
  for (const raw of Array.isArray(out.tags) ? out.tags : []) {
    let t = String(raw).split(/\s+/).filter(Boolean).join(" ").slice(0, 32);
    t = t ? (await match.nearestTag(t, vocabulary)) || t : ""; // 0.78: WWII History -> Military History, Cooking -> Food & Drink; Plastics stays custom
    if (t && !picked.some((x) => x.toLowerCase() === t.toLowerCase())) picked.push(t);
  }
  // The model sometimes grabs a list tag on a word clash ("Plants" for factory plants): drop picks far less related
  // to the expertise than the best pick (calibrated: engineer -> Plants 0.24 vs CNC 0.48; chef -> Sports 0.25 vs Food 0.32).
  const rel = picked.length ? await match.tagRelevance(expertise, picked) : null;
  let kept = picked;
  if (rel) {
    const top = Math.max(...rel);
    kept = picked.filter((_, i) => (rel[i] as number) >= 0.6 * top);
  }
  const known = new Set(vocabulary.map((v) => v.toLowerCase()));
  return kept
    .map((t, i) => ({ t, i, custom: known.has(t.toLowerCase()) ? 0 : 1 }))
    .sort((a, b) => a.custom - b.custom || a.i - b.i) // existing tags first
    .map((x) => x.t)
    .slice(0, 12);
}

/** Ask the model for {"expertise": str, "tags": [str]}; tags prefer the game's existing vocabulary. */
export async function draftProfile(text: string, vocabulary: string[]): Promise<Draft> {
  const prompt =
    "Below is a resume. For a trivia party game, describe what this person could confidently talk about.\n" +
    'Return JSON only: {"expertise": "5-8 short bullet lines starting with \'- \', under 550 characters: ' +
    'their field, specialties, tools, hobbies", "tags": ["6-12 short topic tags"]}.\n' +
    "Prefer tags from this list when they fit: " +
    vocabulary.join(", ") +
    "\n\nRESUME:\n" +
    text;
  const out = await chat(prompt);
  const exp = Array.isArray(out.expertise) ? out.expertise.join("\n") : String(out.expertise ?? "");
  const tags = (Array.isArray(out.tags) ? out.tags : []).map(String).filter((t) => t.trim());
  return { expertise: exp.trim().slice(0, 600), tags: tags.slice(0, 12) };
}
