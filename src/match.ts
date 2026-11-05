/**
 * Per-player topic matching. The admin picks one mode (settings.match_mode):
 *   tags       overlap between a player's chosen tags and a topic's tags
 *   expertise  cosine similarity between the player's free-text expertise and the topic,
 *              both embedded by a local Ollama model (vectors cached in DATA_DIR/embeddings.json)
 * Scores only weight the deal: deal() adds Gumbel noise and assigns greedily, so the
 * best-aligned player usually wins a contested topic, and nobody is ever locked to their field.
 * If Ollama is unreachable, expertise matching quietly degrades to random.
 */
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import * as accounts from "./accounts.ts";
import type { Topic } from "./packs.ts";
import { rng, type Rng } from "./rng.ts";

export interface Profile {
  id: string;
  tags?: string[];
  expertise?: string;
}

/** The bits of a topic that matching reads; the engine passes full topics. */
export interface Matchable {
  id: string;
  topic?: string;
  category?: string;
  tags?: string[];
  group?: string | null;
  summary?: string | null;
  true_statement?: string;
  true_description?: string;
}

export type Vec = number[];

export interface Status {
  state: "idle" | "working" | "ready" | "offline";
  error: string;
  model: string;
  cached: number;
}

export const cfg = {
  ollamaUrl: (process.env.OLLAMA_URL || "").replace(/\/+$/, ""), // empty: matching by expertise and résumé parsing are off
  model: process.env.EMBED_MODEL || "qwen3-embedding:0.6b",
};
const BETA: Record<string, number> = { tags: 1.5, expertise: 1.0 }; // match strength vs. the Gumbel noise (scale 1)

/** Module state, exported so tests can stub the vector cache (the Python tests monkeypatched the same names). */
export const state = {
  vecs: new Map<string, Vec>(),
  cos: new Map<string, Map<string, number | null>>(), // player text key -> topic key -> cosine
  loaded: false,
  status: { state: "idle", error: "" } as { state: Status["state"]; error: string },
  worker: null as Promise<void> | null,
  draining: false, // true while the worker is still picking up `pending`
  pending: [] as string[],
  rankMemo: new Map<string, string[]>(),
};

/** Tests start from an empty cache and never reach a real embedding server. */
export function resetForTests(): void {
  cfg.ollamaUrl = "http://127.0.0.1:9";
  state.vecs = new Map();
  state.cos = new Map();
  state.loaded = true;
  state.status = { state: "idle", error: "" };
  state.worker = null;
  state.draining = false;
  state.pending = [];
  state.rankMemo = new Map();
  embedFn = embed;
}

export function key(text: string): string {
  return createHash("sha1").update(cfg.model + "\n" + text, "utf-8").digest("hex");
}

function cacheFile(): string {
  return join(accounts.cfg.dataDir, "embeddings.json");
}

function load(): void {
  if (state.loaded) return;
  state.loaded = true;
  try {
    const raw = JSON.parse(readFileSync(cacheFile(), "utf-8")) as Record<string, Vec>;
    for (const [k, v] of Object.entries(raw)) state.vecs.set(k, v);
  } catch {
    /* no cache yet */
  }
}

function save(): void {
  mkdirSync(accounts.cfg.dataDir, { recursive: true });
  const tmp = cacheFile() + ".tmp";
  writeFileSync(tmp, JSON.stringify(Object.fromEntries(state.vecs)), "utf-8");
  renameSync(tmp, cacheFile());
}

/** Unit-length embeddings from Ollama. Rejects on any failure. */
export async function embed(texts: string[], timeoutMs = 30_000): Promise<Vec[]> {
  const res = await fetch(`${cfg.ollamaUrl}/api/embed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: cfg.model, input: texts }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) throw new Error(`embed: HTTP ${res.status}`);
  const vecs = ((await res.json()) as { embeddings: Vec[] }).embeddings;
  return vecs.map((v) => {
    const n = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1.0;
    return v.map((x) => Math.round((x / n) * 1e5) / 1e5);
  });
}

/** The embedding call in use; tests swap it for a stub. */
export let embedFn: typeof embed = embed;
export function setEmbed(fn: typeof embed): void {
  embedFn = fn;
}

export function topicText(t: Matchable): string {
  return t.summary || [t.topic ?? "", t.category ?? "", t.true_statement ?? "", (t.true_description ?? "").replaceAll("•", "")].join(" ");
}

/** Player side of the match; Qwen3 embeddings retrieve better with a task instruction on the query. */
export function queryText(expertise: string | null | undefined): string {
  const e = (expertise ?? "").trim();
  return e && "Instruct: Given a description of a person's expertise and interests, retrieve trivia topics they could confidently talk about\nQuery: " + e;
}

/** Tags are embedded as short phrases, so "army" lands near "Military History" and "War". */
export function tagText(tag: string): string {
  return "Topic: " + tag;
}

const dot = (a: Vec, b: Vec): number => {
  let s = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) s += (a[i] as number) * (b[i] as number);
  return s;
};

/** Mean over a topic's tags of the best cosine to any of the player's tags; null if not embedded yet. */
function tagScores(mine: string[], topics: Matchable[]): (number | null)[] | null {
  load();
  const pv = mine.map((x) => state.vecs.get(key(tagText(x)))).filter((v): v is Vec => Boolean(v));
  if (!pv.length) return null;
  const memoKey = "tags:" + [...mine].sort().join("|");
  let memo = state.cos.get(memoKey); // one pass per distinct tag (~50), not per topic
  if (!memo) {
    memo = new Map();
    state.cos.set(memoKey, memo);
  }
  const out: (number | null)[] = [];
  for (const t of topics) {
    const best: number[] = [];
    for (const tag of t.tags ?? []) {
      if (!memo.has(tag)) {
        const tv = state.vecs.get(key(tagText(tag)));
        memo.set(tag, tv ? Math.max(...pv.map((v) => dot(tv, v))) : null);
      }
      const m = memo.get(tag);
      if (m !== null && m !== undefined) best.push(m);
    }
    out.push(best.length ? best.reduce((a, b) => a + b, 0) / best.length : null);
  }
  return out;
}

function zscore(vals: (number | null | undefined)[]): number[] | null {
  const known = vals.filter((c): c is number => c !== null && c !== undefined);
  if (known.length < 2) return null;
  const mean = known.reduce((a, b) => a + b, 0) / known.length;
  const sd = Math.sqrt(known.reduce((a, c) => a + (c - mean) ** 2, 0) / known.length) || 1.0;
  return vals.map((c) => (c === null || c === undefined ? 0.0 : (c - mean) / sd)); // same strength whatever the model's cosine baseline
}

export function status(): Status {
  return { ...state.status, model: cfg.model, cached: state.vecs.size };
}

/** Embed any texts not cached yet, in the background. Safe to call often. */
export function warm(texts: string[]): void {
  load();
  const missing = [...new Set(texts.filter((x) => x && !state.vecs.has(key(x))))];
  if (!missing.length) {
    if (state.status.state === "idle" || state.status.state === "working") state.status.state = "ready";
    return;
  }
  if (state.draining) {
    state.pending.push(...missing); // the running worker picks these up when its current list is done
    return;
  }
  state.status.state = "working";
  state.draining = true;
  const run = async () => {
    let todo = missing;
    try {
      while (todo.length) {
        for (let i = 0; i < todo.length; i += 32) {
          const batch = todo.slice(i, i + 32);
          const vecs = await embedFn(batch, 120_000);
          batch.forEach((text, j) => state.vecs.set(key(text), vecs[j] as Vec));
        }
        // stop draining only once the queue has been swept, so nothing queued is dropped
        todo = [...new Set(state.pending)].filter((x) => !state.vecs.has(key(x)));
        state.pending.length = 0;
        state.draining = todo.length > 0;
      }
      save();
      state.status = { state: "ready", error: "" };
    } catch (e) {
      state.draining = false;
      state.status = { state: "offline", error: String(e instanceof Error ? e.message : e).slice(0, 200) };
    }
  };
  state.worker = run();
}

/** Resolves when the background embedding worker (if any) is done. */
export async function idle(): Promise<void> {
  while (state.worker) {
    const w = state.worker;
    await w;
    if (state.worker === w) state.worker = null;
  }
}

/** One score per topic (higher = better fit), or null when this player has nothing to match on. */
export function scores(player: Profile, topics: Matchable[], mode: string): number[] | null {
  if (mode === "tags") {
    const mine = player.tags ?? [];
    if (!mine.length) return null;
    const sem = tagScores(mine, topics);
    if (sem !== null) return zscore(sem);
    const low = new Set(mine.map((x) => x.toLowerCase())); // Ollama offline / not embedded yet: exact overlap
    return topics.map((t) => {
      const tags = t.tags ?? [];
      return tags.filter((x) => low.has(x.toLowerCase())).length / Math.max(1, tags.length);
    });
  }
  if (mode === "expertise") {
    load();
    const pk = key(queryText(player.expertise));
    const pv = state.vecs.get(pk);
    if (!pv) return null;
    let memo = state.cos.get(pk); // compute each pair once
    if (!memo) {
      memo = new Map();
      state.cos.set(pk, memo);
    }
    const cos: (number | null | undefined)[] = [];
    for (const t of topics) {
      const tk = key(topicText(t));
      if (!memo.has(tk) && state.vecs.has(tk)) memo.set(tk, dot(pv, state.vecs.get(tk)!));
      cos.push(memo.get(tk));
    }
    return zscore(cos);
  }
  return null;
}

/** Give each player a distinct topic. Weighted by match score; never two topics from one paper (group). */
export function deal<T extends Matchable>(players: Profile[], topics: T[], mode: string, r: Rng = rng): Map<string, T> {
  const beta = BETA[mode] ?? 0.0;
  const pairs: [number, string, number][] = [];
  for (const p of players) {
    const s = beta ? scores(p, topics, mode) : null;
    for (let i = 0; i < topics.length; i++) {
      pairs.push([(s ? beta * (s[i] as number) : 0.0) - Math.log(-Math.log(r.random() || 1e-12)), p.id, i]);
    }
  }
  pairs.sort((a, b) => b[0] - a[0] || (a[1] < b[1] ? 1 : a[1] > b[1] ? -1 : 0) || b[2] - a[2]);
  // greedy over Gumbel-perturbed scores, not an optimal assignment; fine at party sizes.
  const out = new Map<string, T>();
  const used = new Set<number>();
  const groups = new Set<string>();
  for (const [, pid, i] of pairs) {
    const t = topics[i] as T;
    if (out.has(pid) || used.has(i) || (t.group && groups.has(t.group))) continue;
    out.set(pid, t);
    used.add(i);
    if (t.group) groups.add(t.group);
    if (out.size === players.length) break;
  }
  return out;
}

/** How well a dealt topic fits this player: the share of the pool (0-100) it beats. null if unscorable. */
export function percent(player: Profile, topic: Matchable, pool: Matchable[], mode: string): number | null {
  const ids = pool.map((t) => t.id);
  const at = ids.indexOf(topic.id);
  if (at < 0) return null;
  const s = scores(player, pool, mode);
  if (!s || s.length < 2) return null;
  const mine = s[at] as number;
  return Math.round((100 * s.filter((x) => x < mine).length) / (s.length - 1));
}

/** Embed missing texts right now (small sets only, e.g. ~50 tags); false if Ollama is unreachable. */
async function ensure(texts: string[], timeoutMs = 8_000): Promise<boolean> {
  load();
  const missing = [...new Set(texts)].filter((x) => x && !state.vecs.has(key(x)));
  if (!missing.length) return true;
  let vecs: Vec[];
  try {
    vecs = await embedFn(missing, timeoutMs);
  } catch {
    return false;
  }
  missing.forEach((text, i) => state.vecs.set(key(text), vecs[i] as Vec));
  save();
  return true;
}

/** The existing tag closest in meaning to `tag`, if it's close enough; exact (case-insensitive) match wins. */
export async function nearestTag(tag: string, options: string[], threshold = 0.78): Promise<string | null> {
  const exact = options.find((o) => o.toLowerCase() === tag.toLowerCase()) ?? null;
  if (exact || !options.length || !(await ensure([tagText(tag), ...options.map(tagText)], 20_000))) return exact;
  const tv = state.vecs.get(key(tagText(tag)))!;
  let best = options[0] as string;
  let bestCos = -Infinity;
  for (const o of options) {
    const c = dot(tv, state.vecs.get(key(tagText(o)))!);
    if (c > bestCos) {
      bestCos = c;
      best = o;
    }
  }
  return bestCos >= threshold ? best : null;
}

/** Cosine of each tag to a player's expertise text; null if Ollama is unreachable. */
export async function tagRelevance(expertise: string, tags: string[]): Promise<number[] | null> {
  const q = queryText(expertise);
  if (!q || !(await ensure([q, ...tags.map(tagText)], 20_000))) return null;
  const qv = state.vecs.get(key(q))!;
  return tags.map((t) => dot(qv, state.vecs.get(key(tagText(t)))!));
}

const az = (a: string, b: string): number => (a.toLowerCase() < b.toLowerCase() ? -1 : a.toLowerCase() > b.toLowerCase() ? 1 : 0);

/**
 * Phone "Relevance" order: your tags A-Z, then the rest by closeness in meaning to your tags and expertise
 * (A-Z when there's nothing to compare with, or until the embeddings are ready: state polls never block on Ollama).
 */
export function rankTags(mine: string[], tags: string[], expertise = ""): string[] {
  const have = new Set(mine.map((t) => t.toLowerCase()));
  const rest = tags.filter((t) => !have.has(t.toLowerCase())).sort(az);
  const anchors = [...mine.map(tagText), ...((expertise ?? "").trim() ? [queryText(expertise)] : [])];
  const memoKey = anchors.join("\n") + "\0" + rest.join("\n");
  const hit = state.rankMemo.get(memoKey);
  if (hit) return hit;
  const texts = [...anchors, ...rest.map(tagText)];
  if (anchors.length && !texts.every((x) => state.vecs.has(key(x)))) {
    warm(texts);
  } else if (anchors.length) {
    const av = anchors.map((a) => state.vecs.get(key(a))!);
    const score = new Map(rest.map((t) => [t, Math.max(...av.map((v) => dot(state.vecs.get(key(tagText(t)))!, v)))]));
    rest.sort((a, b) => (score.get(b) as number) - (score.get(a) as number));
    if (state.rankMemo.size > 256) state.rankMemo.clear();
    const out = [...mine].sort(az).concat(rest);
    state.rankMemo.set(memoKey, out);
    return out;
  }
  return [...mine].sort(az).concat(rest);
}
