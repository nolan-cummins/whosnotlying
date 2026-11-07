/**
 * Topic packs: every *.json file in PACKS_DIR is a read-only pack, picked up automatically.
 *
 * v2 schema: {"id", "name", "version": 2, "topics": [{id, category, topic,
 *   "truth": {"text", "facts": [..]}, "lies": [{"text", "facts": [..]}]}]}
 * v1 topics (true_statement / true_description / false_statements) are still accepted.
 * Loaded topics carry both shapes, so game code can read true_statement / false_statements.
 * The set of enabled packs lives in _settings.json; play history lives in accounts.ts.
 */
import { existsSync, readdirSync, readFileSync, renameSync, statSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";
import { fileURLToPath } from "node:url";
import { choice } from "./rng.ts";

export interface Side {
  text: string;
  facts: string[];
  /** Lies in a paper pack: journals the liar may claim the study appeared in. */
  venues?: string[];
}

export interface Source {
  [k: string]: unknown;
}

/** A topic as the game sees it: v2 fields plus the v1 projections. */
export interface Topic {
  id: string;
  category: string;
  topic: string;
  truth: Side;
  lies: Side[];
  true_statement: string;
  true_description: string;
  false_statements: string[];
  tags: string[];
  group: string | null;
  summary: string | null;
  source: Source | null;
}

/** A topic of an enabled pack: the id is namespaced "pack:topic". */
export interface LibraryTopic extends Topic {
  pack: string;
}

export interface Pack {
  id: string;
  name: string;
  _raw: RawPack;
  topics: Topic[];
}

export interface RawTopic {
  id?: string | number;
  category?: string;
  topic?: string;
  tags?: unknown[];
  truth?: { text?: string; facts?: string[] } | null;
  lies?: { text?: string; facts?: string[]; venues?: string[] }[] | null;
  true_statement?: string;
  true_description?: string;
  false_statements?: string[];
  false_statement?: string;
  group?: string | null;
  summary?: string | null;
  source?: Source | null;
  used?: boolean;
  used_as?: string;
  [k: string]: unknown;
}

export interface RawPack {
  id?: string;
  name?: string;
  version?: number;
  description?: string;
  default_off?: boolean;
  topics?: RawTopic[];
  [k: string]: unknown;
}

export type Need = "truth" | "lie" | null | undefined;

export interface PackSummary {
  id: string;
  name: string;
  total: number;
  used: number;
  selected: boolean;
}

const here = fileURLToPath(new URL(".", import.meta.url));
const SETTINGS = "_settings.json"; // leading underscore: never loaded as a pack

export const cfg = {
  packsDir: process.env.PACKS_DIR || join(here, "..", "packs"),
};

const cache = new Map<string, { mtime: bigint; pack: Pack }>(); // path -> (mtime, pack)

/** Tests point the loader at an isolated copy of the packs. */
export function setPacksDir(dir: string): void {
  cfg.packsDir = dir;
  cache.clear();
}

export function clearCache(): void {
  cache.clear();
}

function writeJson(path: string, data: unknown): void {
  const tmp = path + ".tmp";
  writeFileSync(tmp, JSON.stringify(data, null, 1), "utf-8");
  renameSync(tmp, path);
}

function bullets(desc: string | null | undefined): string[] {
  return (desc ?? "")
    .split(/\r?\n/)
    .map((ln) => ln.trim())
    .filter(Boolean)
    .map((ln) => ln.replace(/^•+/, "").trim());
}

/** Return a topic with both the v2 (truth/lies) and the v1 (true_statement/...) fields. */
export function normalize(t: RawTopic): Topic {
  const truth: Side = t.truth
    ? { text: t.truth.text ?? "", facts: (t.truth.facts ?? []).map(String) }
    : { text: t.true_statement ?? "", facts: bullets(t.true_description) };
  let lies: Side[];
  if (t.lies && t.lies.length) {
    lies = t.lies.map((l) => {
      const side: Side = { text: l.text ?? "", facts: (l.facts ?? []).map(String) };
      if (Array.isArray(l.venues) && l.venues.length) side.venues = l.venues.map(String);
      return side;
    });
  } else {
    const old = t.false_statements ?? (t.false_statement ? [t.false_statement] : []);
    lies = old.map((s) => ({ text: s, facts: [] }));
  }
  return {
    id: String(t.id),
    category: t.category ?? "",
    topic: t.topic ?? "",
    truth,
    lies,
    true_statement: truth.text,
    true_description: truth.facts.map((f) => "• " + f).join("\n"),
    false_statements: lies.map((l) => l.text),
    // optional: matching tags; the PhD pack also has group (paper DOI), summary (for embeddings), source
    tags: (t.tags ?? []).map((x) => String(x)),
    group: t.group ?? null,
    summary: t.summary ?? null,
    source: t.source ?? null,
  };
}

/** id -> pack, rescanning the directory (cheap: files reload only when the mtime changes). */
function packs(): Map<string, Pack> {
  const seen = new Map<string, Pack>();
  let names: string[] = [];
  try {
    if (existsSync(cfg.packsDir) && statSync(cfg.packsDir).isDirectory()) {
      names = readdirSync(cfg.packsDir)
        .filter((n) => n.endsWith(".json") && !n.startsWith("_"))
        .sort();
    }
  } catch {
    names = [];
  }
  for (const n of names) {
    const path = join(cfg.packsDir, n);
    try {
      const mt = statSync(path, { bigint: true }).mtimeNs;
      const hit = cache.get(path);
      if (!hit || hit.mtime !== mt) {
        const raw = JSON.parse(readFileSync(path, "utf-8")) as RawPack;
        const pid = String(raw.id || n.slice(0, -5));
        const pack: Pack = { id: pid, name: raw.name ?? pid, _raw: raw, topics: (raw.topics ?? []).map(normalize) };
        cache.set(path, { mtime: mt, pack });
      }
      const pack = cache.get(path)!.pack;
      seen.set(pack.id, pack);
    } catch {
      continue; // unreadable / malformed pack: skip it
    }
  }
  for (const p of [...cache.keys()]) if (!names.includes(basename(p))) cache.delete(p);
  return seen;
}

function selectedIds(all: Map<string, Pack>): string[] {
  let sel: string[] = [];
  try {
    const raw = JSON.parse(readFileSync(join(cfg.packsDir, SETTINGS), "utf-8")) as { selected?: unknown };
    sel = (Array.isArray(raw.selected) ? raw.selected : []).filter((i): i is string => typeof i === "string" && all.has(i));
  } catch {
    sel = [];
  }
  // default / nothing valid selected: every pack except opt-in ones ("default_off", e.g. PhD Mode)
  if (sel.length) return sel;
  const defaults = [...all.values()].filter((p) => !p._raw.default_off).map((p) => p.id);
  return defaults.length ? defaults : [...all.keys()];
}

/** Topics of the enabled packs; ids are namespaced "pack:topic". */
export function library(): LibraryTopic[] {
  const all = packs();
  const out: LibraryTopic[] = [];
  for (const pid of selectedIds(all)) {
    for (const t of all.get(pid)!.topics) out.push({ ...t, id: `${pid}:${t.id}`, pack: pid });
  }
  return out;
}

/** Can this topic serve a truth teller ("truth") or a liar ("lie")? Packs may hold one-sided items. */
export function hasSide(t: Topic, need: Need): boolean {
  if (!need) return true;
  return need === "truth" ? Boolean(t.true_statement) : t.false_statements.length > 0;
}

/** Every tag used by the enabled packs: the list players pick their interests from. */
export function allTags(): string[] {
  return [...new Set(library().flatMap((t) => t.tags))].sort();
}

/** History keys of every statement a (namespaced) topic holds: its truth and each lie. */
export function statementKeys(t: Topic): string[] {
  const out = t.true_statement ? [t.id + ":t"] : [];
  for (let i = 0; i < t.false_statements.length; i++) out.push(`${t.id}:f${i}`);
  return out;
}

/** `usedKeys`: statement keys in the history. Counts are statements (truths + lies), not topics. */
export function packSummaries(usedKeys: ReadonlySet<string> = new Set()): PackSummary[] {
  const all = packs();
  const sel = new Set(selectedIds(all));
  const out: PackSummary[] = [];
  for (const [pid, p] of all) {
    const keys = p.topics.flatMap((t) => statementKeys({ ...t, id: `${pid}:${t.id}` }));
    out.push({ id: pid, name: p.name, total: keys.length, used: keys.filter((k) => usedKeys.has(k)).length, selected: sel.has(pid) });
  }
  return out;
}

export function setSelected(ids: string[]): boolean {
  const all = packs();
  const valid = ids.filter((i) => all.has(i));
  if (!valid.length) return false;
  writeJson(join(cfg.packsDir, SETTINGS), { selected: valid });
  return true;
}

/** "pack:topic:t" for the truth, "pack:topic:f<N>" for lie N, null if the text isn't in the topic. */
export function statementKey(topic: Topic, statement: string | null | undefined): string | null {
  if (!statement) return null;
  if (statement === topic.true_statement) return topic.id + ":t";
  const i = topic.false_statements.indexOf(statement);
  return i >= 0 ? `${topic.id}:f${i}` : null;
}

export function lieInfo(topic: Topic | null | undefined, statement: string | null | undefined): Side | null {
  return topic?.lies.find((l) => l.text === statement) ?? null;
}

/** The liar's background facts; in a paper pack the journals they may claim come last as one more line. */
export function lieFacts(topic: Topic | null | undefined, statement: string | null | undefined): string[] {
  const lie = lieInfo(topic, statement);
  if (!lie) return [];
  return lie.venues?.length ? [...lie.facts, `Journals that publish this kind of work: ${lie.venues.join(", ")}`] : lie.facts;
}

/**
 * One-time migration: v1 packs carried 'used'/'used_as' flags; return them as history keys.
 * Read-only: the loader ignores those fields, and leaving the file untouched lets a newer
 * seeded copy replace it (cp -u compares mtimes).
 */
export function legacyUsedKeys(): string[] {
  const keys: string[] = [];
  for (const [pid, p] of packs()) {
    for (const t of p._raw.topics ?? []) {
      if (t.used) {
        const side = t.used_as;
        keys.push(`${pid}:${t.id}:` + (side === "true" ? "t" : side === "false" ? "f0" : "?"));
      }
    }
  }
  return keys;
}

export function getRandomFalseStatement(topic: Topic): string {
  if (topic.false_statements.length) return choice(topic.false_statements);
  return "";
}
