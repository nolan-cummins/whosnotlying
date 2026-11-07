#!/usr/bin/env node
/**
 * Validate topic packs (v2 schema, see sources/CONVERTING.md).
 *
 *   node scripts/lint_packs.ts packs/*.json                   # errors exit 1, warnings are printed
 *   node scripts/lint_packs.ts --quiet packs/*.json           # errors only
 *   node scripts/lint_packs.ts --check-archive packs/*.json   # also: every offline copy exists in $ARCHIVE_DIR
 *   npm run lint:packs                                        # the repository's own packs
 *
 * Errors: broken schema, duplicate ids / titles / statements, missing or oversized facts.
 * Warnings are heuristics for a human pass: a title word that only one side mentions, length
 * mismatch between truth and lie, a number on one side only.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { basename, join } from "node:path";
import { fileURLToPath } from "node:url";

const ARCHIVE = process.env.ARCHIVE_DIR || "/mnt/hdd2/liars-archive";

const STOP = new Set(
  `a an the of and or to in on at by for with from into over under vs about after before
their his her its was were is are be been this that these those who what when where why how one
first last most more than`.split(/\s+/),
);
const TRUTH_FACTS: [number, number] = [3, 5];
const LIE_FACTS: [number, number] = [2, 4];
const MAX_FACT_WORDS = 14;
const JOURNAL_FACT_WORDS = 20;
// Hedges ("legend says...") on one side only tell guessers which statement is which.
const HEDGE = /\b(legend(?:s|arily)?|reportedly|allegedly|according to|claim\w*|said to|rumou?r\w*|myth\w*|supposedly)\b/i;

interface Side {
  text?: string;
  facts?: string[];
  venues?: unknown;
}
interface Source {
  doi?: string;
  journal?: string;
  institution?: string;
  year?: number | string;
  publisher?: string;
  quote?: string;
  url?: string;
  archive?: string;
  also?: Source[];
}
interface Topic {
  id?: string;
  topic?: string;
  category?: string;
  tags?: unknown;
  group?: string | null;
  source?: Source | null;
  truth?: Side | null;
  lies?: Side[] | null;
  used?: unknown;
  used_as?: unknown;
}
interface Pack {
  id?: string;
  /** A rewrite of another pack with the same topic ids (PhD Mode: Simple): titles may repeat between the two. */
  derived_from?: string;
  topics?: Topic[];
}

export interface LintResult {
  errors: string[];
  warnings: string[];
}

const words = (s: string): string[] => s.toLowerCase().match(/[a-z0-9']+/g) ?? [];
const stem = (w: string): string => w.slice(0, 5); // crude: "pirates"/"piracy" -> "pirat"
const isObj = (v: unknown): v is Record<string, unknown> => Boolean(v) && typeof v === "object" && !Array.isArray(v);

function readPack(path: string): Pack | string {
  try {
    return JSON.parse(readFileSync(path, "utf-8")) as Pack;
  } catch (e) {
    return e instanceof Error ? e.message : String(e);
  }
}

export function lint(paths: string[], checkArchive = false): LintResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const titles = new Map<string, { where: string; pack: string; family: string }>();
  const texts = new Map<string, string>();
  for (const path of paths) {
    const pack = readPack(path);
    if (typeof pack === "string") {
      errors.push(`${path}: unreadable (${pack})`);
      continue;
    }
    if (!pack.id || !Array.isArray(pack.topics)) {
      errors.push(`${path}: needs 'id' and a 'topics' list`);
      continue;
    }
    const ids = new Set<string>();
    const papers = pack.topics.some((t) => Boolean(t.source?.doi)); // a PhD-style pack: invented lies name journals to bluff with
    const family = pack.derived_from || pack.id; // a derived pack shares titles (not statements) with its parent
    const simple = Boolean(pack.derived_from); // the Simple rules: short plain statements, at most one number, facts are findings
    for (const t of pack.topics) {
      const where = `${pack.id}:${t.id}`;
      const err = (m: string) => errors.push(`${where}: ${m}`);
      const warn = (m: string) => warnings.push(`${where}: ${m}`);
      if (!t.id || ids.has(t.id)) err("missing or duplicate id");
      ids.add(String(t.id));
      if ("used" in t || "used_as" in t) err("'used' flags don't belong in packs (history is tracked separately)");
      const src = t.source;
      const paper = isObj(src) && Boolean(src.doi);
      if ((t.group || paper) && !(paper && src?.journal && t.group)) err("paper-based topics need 'group' and source.journal/doi (see sources/phd/GUIDE.md)");
      if (paper && !(src?.institution && src?.year)) err("paper source needs 'institution' (where the authors were) and 'year'");
      if (src && !paper && !(isObj(src) && src.publisher && src.quote)) err("web source needs 'publisher' and the supporting 'quote' (see sources/absurd/GUIDE.md)");
      for (const s of (isObj(src) ? [src as Source, ...((src as Source).also ?? [])] : []) as Source[]) {
        if (!(String(s.url ?? "").startsWith("https://") && s.archive)) err("every source needs an https 'url' and an offline 'archive' copy");
        else if (checkArchive && !existsSync(join(ARCHIVE, s.archive))) err(`offline copy missing: ${ARCHIVE}/${s.archive}`);
      }
      if (t.tags !== undefined && t.tags !== null && !(Array.isArray(t.tags) && t.tags.every((x) => typeof x === "string" && x))) err("'tags' must be a list of strings");
      const title = t.topic ?? "";
      const truth: Side = t.truth ?? {};
      const lies: Side[] = t.lies ?? [];
      if (!title || !t.category) err("needs 'topic' (title) and 'category'");
      // Items may be one-sided (PhD pack: real truths and separately invented lies); paired ones get the pairing checks.
      if (!(truth.text || lies.length) || !lies.every((l) => l.text)) {
        err("needs truth.text and/or lies with text");
        continue;
      }
      if (src && !truth.text) err("a source/DOI belongs only on a truth");
      const tl = title.toLowerCase();
      const prev = titles.get(tl);
      if (prev && (prev.pack === pack.id || prev.family !== family)) err(`title '${title}' already used by ${prev.where}`);
      if (!prev) titles.set(tl, { where, pack: pack.id, family });
      if (simple) {
        for (const txt of [truth.text, ...lies.map((l) => l.text)]) {
          if (!txt) continue;
          const n = words(txt).length;
          if (n > 30) warn(`statement is ${n} words (Simple pack: keep it under 30): ${txt.slice(0, 50)}`);
          const nums = txt.match(/\d[\d,.]*%?/g) ?? [];
          if (nums.length > 1) warn(`statement carries ${nums.length} numbers (Simple pack: at most one): ${txt.slice(0, 50)}`);
        }
        for (const f of [...(truth.facts ?? []), ...lies.flatMap((l) => l.facts ?? [])]) {
          if (/^(some|others|critics|skeptics|many|proponents)\b.*\b(argue|say|claim|believe|suggest|contend)/i.test(f) || /^(some argue|others argue|critics)/i.test(f)) warn(`fact reads as an argument, not a finding: ${f}`);
        }
      }
      for (const s of [...(truth.text ? [truth.text] : []), ...lies.map((l) => l.text as string)]) {
        if (texts.has(s)) err(`statement duplicated in ${texts.get(s)}: ${s.slice(0, 50)}`);
        texts.set(s, where);
      }
      const tf = truth.facts ?? [];
      if (truth.text && !(TRUTH_FACTS[0] <= tf.length && tf.length <= TRUTH_FACTS[1])) err(`truth has ${tf.length} facts (want ${TRUTH_FACTS[0]}-${TRUTH_FACTS[1]})`);
      lies.forEach((l, i) => {
        const facts = l.facts ?? [];
        const jl = facts.filter((f) => f.startsWith("Journals like "));
        const venues = Array.isArray(l.venues) ? l.venues : null;
        if (l.venues !== undefined && !(venues && venues.length >= 2 && venues.length <= 3 && venues.every((v) => typeof v === "string" && v.trim() && v.length <= 80))) err(`lie ${i} 'venues' must list 2-3 journal names`);
        if (papers && !truth.text && (venues ? jl.length !== 0 : jl.length !== 1)) err(`lie ${i} needs either 'venues' (2-3 journals) or exactly one 'Journals like X and Y publish papers on ...' fact in a paper pack`);
        const n = facts.length - jl.length; // the journals line doesn't count toward the fact budget
        if (!(LIE_FACTS[0] <= n && n <= LIE_FACTS[1])) err(`lie ${i} has ${n} facts (want ${LIE_FACTS[0]}-${LIE_FACTS[1]})`);
      });
      for (const f of [...tf, ...lies.flatMap((l) => l.facts ?? [])]) {
        if (words(f).length > (f.startsWith("Journals like ") ? JOURNAL_FACT_WORDS : MAX_FACT_WORDS)) err(`fact over ${MAX_FACT_WORDS} words: ${f}`);
        if (/^[•\-*]/.test(f.trimStart())) err(`fact has a bullet character (the UI adds it): ${f}`);
      }
      if (!(truth.text && lies.length)) continue;
      const tw = words(truth.text).length;
      const titleStems = new Set(words(title).filter((w) => !STOP.has(w) && w.length > 2).map(stem));
      const truthStems = new Set(words(truth.text).map(stem));
      lies.forEach((l, i) => {
        const lt = l.text as string;
        const lw = words(lt).length;
        const ratio = lw / Math.max(tw, 1);
        if (!(ratio >= 0.6 && ratio <= 1.6)) warn(`lie ${i} is ${lw} words vs truth ${tw}`);
        if (/\d/.test(truth.text as string) !== /\d/.test(lt)) warn(`a number/date appears on only one side (lie ${i})`);
        if (HEDGE.test(truth.text as string) !== HEDGE.test(lt)) warn(`hedging word ('legend', 'claimed'...) on only one side (lie ${i})`);
        const lieStems = new Set(words(lt).map(stem));
        for (const s of titleStems) {
          if (truthStems.has(s) !== lieStems.has(s)) warn(`title word '${s}..' appears only in the ${truthStems.has(s) ? "truth" : `lie ${i}`}: '${title}'`);
        }
      });
    }
  }
  // A lie's background facts shouldn't name the subject of another topic's truth
  // (a liar would be holding a spoiler for someone else's statement).
  const names = (s: string): Set<string> => new Set(s.match(/\b[A-Z][a-z]{3,}(?:\s[A-Z][a-z]+)+\b/g) ?? []);
  const truthNames = new Map<string, string | undefined>();
  const loaded = paths.map(readPack).filter((p): p is Pack => typeof p !== "string");
  for (const pack of loaded) {
    for (const t of pack.topics ?? []) for (const n of names(t.truth?.text ?? "")) if (!truthNames.has(n)) truthNames.set(n, t.id);
  }
  for (const pack of loaded) {
    for (const t of pack.topics ?? []) {
      for (const l of t.lies ?? []) {
        for (const f of l.facts ?? []) {
          for (const n of names(f)) {
            const owner = truthNames.get(n);
            if (owner !== undefined && owner !== t.id) warnings.push(`${pack.id}:${t.id}: lie fact names '${n}', the subject of ${owner}'s truth`);
          }
        }
      }
    }
  }
  return { errors, warnings };
}

export function repoPacks(): string[] {
  const dir = join(fileURLToPath(new URL(".", import.meta.url)), "..", "packs");
  return readdirSync(dir)
    .filter((n) => n.endsWith(".json") && !n.startsWith("_"))
    .sort()
    .map((n) => join(dir, n));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  let args = process.argv.slice(2).filter((a) => !a.startsWith("--"));
  if (!args.length) args = repoPacks(); // no paths given (CI): lint the repository's own packs
  if (!args.length) {
    process.stderr.write("no packs found\n");
    process.exit(2);
  }
  const { errors, warnings } = lint(args, process.argv.includes("--check-archive"));
  if (!process.argv.includes("--quiet")) for (const w of warnings) console.log("WARN ", w);
  for (const e of errors) console.log("ERROR", e);
  console.log(`${errors.length} error(s), ${warnings.length} warning(s)`);
  process.exit(errors.length ? 1 : 0);
}
