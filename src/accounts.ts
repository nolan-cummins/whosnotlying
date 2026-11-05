/**
 * Player accounts and topic history, kept outside the pack files (packs are read-only content).
 *
 * DATA_DIR/accounts.json  {name_lower: {id, name, pw_hash, salt, score_total, rounds, created}}
 * DATA_DIR/history.json   {"global": [key], "users": {account_id: [key]}, "settings": {...}}
 *
 * A statement key is "pack:topic_id:t" (the truth) or "pack:topic_id:f<N>" (lie N), so text edits
 * don't break the record. Seeing either side of a topic spoils the whole topic, so blocking
 * works on the "pack:topic_id" prefix. Legacy marks without a known side use the suffix "?".
 *
 * The file formats (and the PBKDF2 password hashes) are the same as the Python version's, so a
 * data directory written by it keeps working.
 */
import { pbkdf2Sync, randomBytes, timingSafeEqual } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));

export const cfg = {
  dataDir: process.env.DATA_DIR || join(here, "..", "data"),
};

export function setDataDir(dir: string): void {
  cfg.dataDir = dir;
}

export type MatchMode = "off" | "tags" | "expertise";

export interface Settings {
  use_global: boolean;
  use_user: boolean;
  lying_facts: boolean;
  hide_facts: boolean;
  fair_roles: boolean;
  match_mode: MatchMode;
  idle_minutes: number;
  [k: string]: boolean | number | string;
}

export const DEFAULT_SETTINGS: Settings = {
  use_global: true,
  use_user: true,
  lying_facts: false,
  hide_facts: false,
  fair_roles: false,
  match_mode: "off",
  idle_minutes: 60,
};
const CHOICES: Record<string, readonly string[]> = { match_mode: ["off", "tags", "expertise"] }; // non-bool settings: allowed values
const RANGES: Record<string, readonly [number, number]> = { idle_minutes: [5, 1440] }; // integer settings: inclusive bounds

export interface Account {
  id: string;
  name: string;
  pw_hash: string;
  salt: string;
  score_total: number;
  rounds: number;
  created: number;
  games?: number;
  wins?: number;
  tags?: string[];
  expertise?: string;
  reset_requested?: number | null;
  must_change?: boolean;
}

export interface AccountRow {
  id: string;
  name: string;
  score_total: number;
  rounds: number;
  wins: number;
  games: number;
  reset_requested: boolean;
  must_change: boolean;
  seen: number;
}

export interface LeaderboardRow {
  name: string;
  points: number;
  wins: number;
  games: number;
  rounds: number;
}

export interface Review {
  ts: number;
  game_id: number;
  round: number;
  topic_id: string | null;
  pack: string | null;
  topic: string | null;
  side: "truth" | "lie";
  statement: string | null;
  facts: string[] | string | null;
  score: number;
  text: string;
  player_name: string;
  account_id: string | null;
}

export interface UsedStatement {
  type: "true" | "false";
  game: number;
  round: number;
  player_id: string;
  player_name: string;
  topic: string;
  category: string | null;
  statement: string;
  detailed_description?: string | null;
}

interface History {
  global: string[];
  users: Record<string, string[]>;
  settings: Settings;
}

type Accounts = Record<string, Account>;

function path(name: string): string {
  return join(cfg.dataDir, name);
}

function read<T>(name: string, fallback: T): T {
  try {
    return JSON.parse(readFileSync(path(name), "utf-8")) as T;
  } catch {
    return fallback;
  }
}

function write(name: string, data: unknown): void {
  mkdirSync(cfg.dataDir, { recursive: true });
  const tmp = path(name) + ".tmp";
  writeFileSync(tmp, JSON.stringify(data, null, 1), "utf-8");
  renameSync(tmp, path(name));
}

/** Append one statement review to reviews.jsonl (feedback on generated content; read back when improving packs). */
export function addReview(entry: Review): void {
  mkdirSync(cfg.dataDir, { recursive: true });
  appendFileSync(path("reviews.jsonl"), JSON.stringify(entry) + "\n", "utf-8");
}

/** All reviews, newest first. */
export function reviews(): Review[] {
  let rows: Review[];
  try {
    rows = readFileSync(path("reviews.jsonl"), "utf-8")
      .split("\n")
      .filter((l) => l.trim())
      .map((l) => JSON.parse(l) as Review);
  } catch {
    return [];
  }
  return rows.reverse();
}

export function topicOf(key: string): string {
  const i = key.lastIndexOf(":");
  return i < 0 ? key : key.slice(0, i);
}

// ---------- passwords ----------

export function hashPassword(password: string, salt?: string): [string, string] {
  const s = salt || randomBytes(16).toString("hex");
  const h = pbkdf2Sync(Buffer.from(password, "utf-8"), Buffer.from(s, "hex"), 200_000, 32, "sha256").toString("hex");
  return [h, s];
}

export function checkPassword(password: string | null | undefined, pwHash: string | null | undefined, salt: string | null | undefined): boolean {
  if (!pwHash || !salt) return false;
  const a = Buffer.from(hashPassword(password || "", salt)[0]);
  const b = Buffer.from(pwHash);
  return a.length === b.length && timingSafeEqual(a, b);
}

// ---------- accounts ----------

export function getAccount(name: string): Account | null {
  return read<Accounts>("accounts.json", {})[name.trim().toLowerCase()] ?? null;
}

export function accountById(acctId: string): Account | null {
  return Object.values(read<Accounts>("accounts.json", {})).find((a) => a.id === acctId) ?? null;
}

export function createAccount(name: string, password: string): Account {
  const accts = read<Accounts>("accounts.json", {});
  const [h, salt] = hashPassword(password);
  const acct: Account = { id: "a_" + randomBytes(6).toString("hex"), name: name.trim(), pw_hash: h, salt, score_total: 0, rounds: 0, created: Math.floor(Date.now() / 1000) };
  accts[name.trim().toLowerCase()] = acct;
  write("accounts.json", accts);
  return acct;
}

/** Interests follow a permanent account into every future game. */
export function setProfile(acctId: string, tags: string[], expertise: string): void {
  const accts = read<Accounts>("accounts.json", {});
  for (const a of Object.values(accts)) {
    if (a.id === acctId) {
      a.tags = tags;
      a.expertise = expertise;
      write("accounts.json", accts);
      return;
    }
  }
}

function update(acctId: string, fields: Partial<Account>): boolean {
  const accts = read<Accounts>("accounts.json", {});
  for (const a of Object.values(accts)) {
    if (a.id === acctId) {
      Object.assign(a, fields);
      write("accounts.json", accts);
      return true;
    }
  }
  return false;
}

/** "Forgot password" on the join page: flags the account for the admin. No secret is involved. */
export function requestReset(name: string): boolean {
  const acct = getAccount(name || "");
  return Boolean(acct) && update(acct!.id, { reset_requested: Math.floor(Date.now() / 1000) });
}

/** Admin hands out a one-time password; the player must replace it at their next login. */
export function resetPassword(acctId: string): string | null {
  const temp = [0, 1, 2].map(() => randomBytes(2).toString("hex")).join("-"); // e.g. 3fa1-09bc-7d2e: easy to read out loud
  const [h, salt] = hashPassword(temp);
  return update(acctId, { pw_hash: h, salt, must_change: true, reset_requested: null }) ? temp : null;
}

export function setPassword(acctId: string, password: string): boolean {
  const [h, salt] = hashPassword(password);
  return update(acctId, { pw_hash: h, salt, must_change: false });
}

/** A finished game: everyone listed played it, the top scorers (ties included) won it. */
export function recordGame(accountIds: Iterable<string>, winnerIds: Iterable<string>): void {
  const played = new Set(accountIds);
  const won = new Set(winnerIds);
  const accts = read<Accounts>("accounts.json", {});
  for (const a of Object.values(accts)) {
    if (played.has(a.id)) {
      a.games = (a.games ?? 0) + 1;
      a.wins = (a.wins ?? 0) + (won.has(a.id) ? 1 : 0);
    }
  }
  write("accounts.json", accts);
}

/** Public: saved accounts ranked by games won, then total points. */
export function leaderboard(): LeaderboardRow[] {
  const rows = Object.values(read<Accounts>("accounts.json", {})).map((a) => ({
    name: a.name,
    points: a.score_total ?? 0,
    wins: a.wins ?? 0,
    games: a.games ?? 0,
    rounds: a.rounds ?? 0,
  }));
  return rows.sort((x, y) => y.wins - x.wins || y.points - x.points || x.name.toLowerCase().localeCompare(y.name.toLowerCase()));
}

export function listAccounts(): AccountRow[] {
  const users = read<Partial<History>>("history.json", {}).users ?? {};
  return Object.values(read<Accounts>("accounts.json", {})).map((a) => ({
    id: a.id,
    name: a.name,
    score_total: a.score_total ?? 0,
    rounds: a.rounds ?? 0,
    wins: a.wins ?? 0,
    games: a.games ?? 0,
    reset_requested: Boolean(a.reset_requested),
    must_change: Boolean(a.must_change),
    seen: new Set((users[a.id] ?? []).map(topicOf)).size,
  }));
}

export function deleteAccount(acctId: string): boolean {
  const accts = read<Accounts>("accounts.json", {});
  const keep: Accounts = {};
  for (const [k, a] of Object.entries(accts)) if (a.id !== acctId) keep[k] = a;
  if (Object.keys(keep).length === Object.keys(accts).length) return false;
  write("accounts.json", keep);
  clearUserHistory(acctId);
  return true;
}

export function addRoundScore(acctId: string, pts: number): void {
  const accts = read<Accounts>("accounts.json", {});
  for (const a of Object.values(accts)) {
    if (a.id === acctId) {
      a.score_total = (a.score_total ?? 0) + pts;
      a.rounds = (a.rounds ?? 0) + 1;
      write("accounts.json", accts);
      return;
    }
  }
}

// ---------- history ----------

function history(): History {
  const h = read<Partial<History>>("history.json", {});
  return { global: h.global ?? [], users: h.users ?? {}, settings: { ...DEFAULT_SETTINGS, ...(h.settings ?? {}) } };
}

export function hasHistoryFile(): boolean {
  return existsSync(path("history.json"));
}

/** Create history.json once, seeded with legacy 'used' marks migrated out of the packs. */
export function initHistory(legacyKeys: string[]): void {
  if (!hasHistoryFile()) {
    const h = history();
    h.global = [...new Set(legacyKeys)];
    write("history.json", h);
  }
}

export function settings(): Settings {
  return history().settings;
}

export function setSetting(name: string, value: unknown): boolean {
  if (!(name in DEFAULT_SETTINGS)) return false;
  const h = history();
  if (name in CHOICES) {
    if (typeof value !== "string" || !CHOICES[name]!.includes(value)) return false;
    h.settings[name] = value;
  } else if (name in RANGES) {
    const v = typeof value === "number" ? Math.trunc(value) : typeof value === "string" && /^\s*-?\d+\s*$/.test(value) ? parseInt(value, 10) : NaN;
    if (!Number.isFinite(v)) return false;
    const [lo, hi] = RANGES[name]!;
    if (v < lo || v > hi) return false;
    h.settings[name] = v;
  } else {
    h.settings[name] = Boolean(value);
  }
  write("history.json", h);
  return true;
}

/** Append statement keys to the global history and to each listed account's history. */
export function record(keys: Iterable<string>, accountIds: Iterable<string>): void {
  const ks = [...keys].filter(Boolean);
  if (!ks.length) return;
  const h = history();
  const targets = [h.global, ...[...accountIds].map((a) => (h.users[a] ??= []))];
  let changed = false;
  for (const lst of targets) {
    const have = new Set(lst);
    for (const k of ks) {
      if (!have.has(k)) {
        lst.push(k);
        have.add(k);
        changed = true;
      }
    }
  }
  if (changed) write("history.json", h);
}

export function globalKeys(): string[] {
  return [...history().global];
}

/** Topic ids ("pack:topic") to avoid, honoring the global / per-player toggles. */
export function blockedTopics(accountIds: Iterable<string>): Set<string> {
  const h = history();
  let keys = h.settings.use_global ? [...h.global] : [];
  if (h.settings.use_user) for (const a of accountIds) keys = keys.concat(h.users[a] ?? []);
  return new Set(keys.map(topicOf));
}

export function resetGlobal(): void {
  const h = history();
  h.global = [];
  write("history.json", h);
}

export function clearUserHistory(acctId: string): void {
  const h = history();
  if (acctId in h.users) {
    delete h.users[acctId];
    write("history.json", h);
  }
}

// ---------- "View Used" archive (statements per round, survives restarts) ----------

export const ARCHIVE_MAX = 1000;

export function loadArchive(): UsedStatement[] {
  return read<UsedStatement[]>("archive.json", []);
}

export function saveArchive(entries: UsedStatement[]): void {
  write("archive.json", entries.slice(-ARCHIVE_MAX));
}
