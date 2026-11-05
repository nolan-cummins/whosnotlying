/**
 * HTTP server and API router: the six pages, the static files, the polling API
 * (GET /api/state, POST /api/action) and the admin login cookie.
 */
import { execFileSync } from "node:child_process";
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { createServer as createHttpServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { createServer as createNetServer } from "node:net";
import { networkInterfaces } from "node:os";
import { extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";
import * as accounts from "./accounts.ts";
import { GameManager, NEED_NEW_PASSWORD, type GameState, type Player } from "./game.ts";
import * as packs from "./packs.ts";
import { LOGO_24, generateQrSvg, ready as qrReady } from "./qr.ts";
import * as resume from "./resume.ts";
import { getAdminHtml, getAdminLoginHtml, getDisplayHtml, getJoinHtml, getQrHtml, getStageControlHtml } from "./templates.ts";

const here = fileURLToPath(new URL(".", import.meta.url));

export const cfg = {
  adminUser: process.env.ADMIN_USER || "admin",
  adminPass: process.env.ADMIN_PASS || "notthepassword",
  staticDir: join(here, "static"),
  // Offline copies of truth sources (PDFs, saved web pages) plus the pdf.js viewer that shows PDFs on any phone.
  archiveDir: process.env.ARCHIVE_DIR || "/app/archive",
  /** Delay after a failed admin login (slows down guessing); tests set 0. */
  loginDelayMs: 1000,
  /** Print one line per request to stdout. */
  logRequests: true,
};

const STATIC_TYPES: Record<string, string> = {
  ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".png": "image/png", ".ico": "image/x-icon",
};
const ARCHIVE_TYPES: Record<string, string> = {
  ".pdf": "application/pdf", ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
  ".mjs": "text/javascript", ".json": "application/json", ".ftl": "text/plain; charset=utf-8",
  ".bcmap": "application/octet-stream", ".pfb": "application/octet-stream", ".wasm": "application/wasm",
  ".ttf": "font/ttf", ".icc": "application/vnd.iccprofile", ".map": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8",
};
// Actions any browser may send; everything else needs the admin cookie.
const PLAYER_ACTIONS = new Set(["join", "cast_vote", "guesser_advance", "toggle_ready", "set_profile", "request_reset", "parse_resume", "auto_tags", "review"]);
const TOKEN_ACTIONS = new Set(["cast_vote", "guesser_advance", "toggle_ready", "set_profile", "parse_resume", "auto_tags", "review"]);

let secret: Buffer | null = null;

/** HMAC key for admin cookies, generated once into DATA_DIR so sessions survive restarts. */
function adminSecret(): Buffer {
  if (secret === null) {
    const path = join(accounts.cfg.dataDir, "secret.key");
    try {
      secret = readFileSync(path);
    } catch {
      secret = randomBytes(32);
      mkdirSync(accounts.cfg.dataDir, { recursive: true });
      writeFileSync(path, secret);
    }
  }
  return secret;
}

/** Tests that move DATA_DIR want a fresh key. */
export function resetAdminSecret(): void {
  secret = null;
}

export function makeAdminCookie(): string {
  const exp = String(Math.floor(Date.now() / 1000) + 30 * 86400);
  const sig = createHmac("sha256", adminSecret()).update(exp).digest("hex");
  return `${exp}.${sig}`;
}

export function validAdminCookie(value: string | undefined): boolean {
  const [exp = "", sig = ""] = (value || "").split(".", 2);
  const good = createHmac("sha256", adminSecret()).update(exp).digest("hex");
  const a = Buffer.from(sig);
  const b = Buffer.from(good);
  return /^\d+$/.test(exp) && Number(exp) > Date.now() / 1000 && a.length === b.length && timingSafeEqual(a, b);
}

// ANSI terminal colours for live monitoring
export const COLOR_RESET = "\x1b[0m";
export const COLOR_BOLD = "\x1b[1m";
export const COLOR_DIM = "\x1b[2m";
export const COLOR_GREEN = "\x1b[32m";
export const COLOR_YELLOW = "\x1b[33m";
export const COLOR_BLUE = "\x1b[34m";
export const COLOR_MAGENTA = "\x1b[35m";
export const COLOR_CYAN = "\x1b[36m";
export const COLOR_RED = "\x1b[31m";

const stamp = (): string => new Date().toTimeString().slice(0, 8);

/** The machine's Wi-Fi / LAN address, for the QR code. */
export function getLanIp(): string {
  const ifaces = networkInterfaces();
  const preferred = ["en0", "en1", "en2", "eth0", "wlan0", "wlp2s0"];
  const pick = (name: string) => ifaces[name]?.find((a) => a.family === "IPv4" && !a.internal)?.address;
  for (const n of preferred) {
    const ip = pick(n);
    if (ip) return ip;
  }
  for (const n of Object.keys(ifaces)) {
    const ip = pick(n);
    if (ip) return ip;
  }
  return "127.0.0.1";
}

export interface ServerContext {
  gm: GameManager;
  port: number;
  lanIp: string;
}

type Json = Record<string, unknown>;

function parseCookies(header: string | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of (header || "").split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
  }
  return out;
}

const NO_CACHE = { "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0", Pragma: "no-cache", Expires: "0", "Access-Control-Allow-Origin": "*" };

function send(res: ServerResponse, status: number, type: string, body: string | Buffer, extra: Record<string, string> = {}): void {
  const buf = typeof body === "string" ? Buffer.from(body, "utf-8") : body;
  res.writeHead(status, { "Content-Type": type, "Content-Length": String(buf.length), ...extra });
  res.end(buf);
}

const sendJson = (res: ServerResponse, data: unknown, status = 200) => send(res, status, "application/json; charset=utf-8", JSON.stringify(data, null, 2), NO_CACHE);
const sendHtml = (res: ServerResponse, html: string, status = 200) => send(res, status, "text/html; charset=utf-8", html, NO_CACHE);
const sendSvg = (res: ServerResponse, svg: string, status = 200) => send(res, status, "image/svg+xml; charset=utf-8", svg, NO_CACHE);
const notFound = (res: ServerResponse) => send(res, 404, "text/plain; charset=utf-8", "Not Found");

function redirect(res: ServerResponse, location: string, cookie?: string): void {
  const headers: Record<string, string> = { Location: location, "Content-Length": "0" };
  if (cookie) headers["Set-Cookie"] = cookie;
  res.writeHead(302, headers);
  res.end();
}

function sendStatic(res: ServerResponse, rel: string, root: string, types: Record<string, string>): void {
  let decoded: string;
  try {
    decoded = decodeURIComponent(rel);
  } catch {
    return notFound(res);
  }
  const path = normalize(join(root, decoded));
  const ext = extname(path).toLowerCase();
  if (!path.startsWith(root + sep) || !(ext in types) || !existsSync(path) || !statSync(path).isFile()) return notFound(res);
  send(res, 200, types[ext] as string, readFileSync(path), { "Cache-Control": "public, max-age=3600" });
}

function readBody(req: IncomingMessage, limit: number): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size = 0;
    req.on("data", (c: Buffer) => {
      size += c.length;
      if (size <= limit) chunks.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

export function createHandler(ctx: ServerContext): (req: IncomingMessage, res: ServerResponse) => Promise<void> {
  const isAdmin = (req: IncomingMessage) => validAdminCookie(parseCookies(req.headers.cookie)["liars_admin"]);
  const cookieAttrs = (req: IncomingMessage) => `Path=/; HttpOnly; SameSite=Lax${req.headers["x-forwarded-proto"] === "https" ? "; Secure" : ""}`;

  const baseUrl = (req: IncomingMessage): string => {
    // 1. Explicit environment variable override
    const env = process.env.PUBLIC_URL || process.env.BASE_URL;
    if (env) return env.replace(/\/+$/, "");
    // 2. Derive from Host and reverse-proxy headers
    const host = req.headers.host;
    if (host) {
      const proto = (req.headers["x-forwarded-proto"] as string | undefined) || (req.headers["x-forwarded-ssl"] === "on" ? "https" : "http");
      return `${proto}://${host}`.replace(/\/+$/, "");
    }
    // 3. Fallback to the detected LAN address
    return `http://${ctx.lanIp}:${ctx.port}`;
  };

  const logLine = (req: IncomingMessage, res: ServerResponse) => {
    const code = String(res.statusCode);
    const line = `${req.method} ${req.url} HTTP/${req.httpVersion}`;
    if (cfg.logRequests) {
      const color = code.startsWith("2") ? COLOR_GREEN : code.startsWith("3") ? COLOR_YELLOW : COLOR_RED;
      process.stdout.write(`${COLOR_DIM}[${stamp()}]${COLOR_RESET} ${COLOR_CYAN}[HTTP]${COLOR_RESET} ${line} -> ${color}${code}${COLOR_RESET}\n`);
    }
    logRequest(ctx.gm, line, code);
  };

  const doGet = (req: IncomingMessage, res: ServerResponse) => {
    const url = new URL(req.url || "/", "http://x");
    const path = url.pathname;
    const q = url.searchParams;
    if (path === "/") redirect(res, "/join");
    else if (["/game", "/control", "/stages", "/stage-control"].includes(path)) redirect(res, path !== "/game" ? "/admin/control" : "/admin");
    else if (path === "/admin/login") sendHtml(res, getAdminLoginHtml());
    else if (["/admin", "/admin/", "/admin/control"].includes(path)) {
      if (!isAdmin(req)) redirect(res, "/admin/login?next=" + path);
      else if (path === "/admin/control") sendHtml(res, getStageControlHtml(ctx.port));
      else sendHtml(res, getAdminHtml(ctx.port, ctx.lanIp, baseUrl(req)));
    } else if (path.startsWith("/static/")) sendStatic(res, path.slice("/static/".length), cfg.staticDir, STATIC_TYPES);
    else if (path.startsWith("/archive/")) sendStatic(res, path.slice("/archive/".length), cfg.archiveDir, ARCHIVE_TYPES);
    else if (["/qr", "/lobby", "/lobby-qr"].includes(path)) sendHtml(res, getQrHtml(ctx.port, ctx.lanIp, baseUrl(req)));
    else if (["/join", "/play"].includes(path)) sendHtml(res, getJoinHtml(ctx.port));
    else if (["/display", "/player"].includes(path)) sendHtml(res, getDisplayHtml(ctx.port));
    else if (path === "/api/qr.svg") sendSvg(res, generateQrSvg(q.get("url") || `${baseUrl(req)}/join`, { bg: "", logo: LOGO_24 }));
    else if (path === "/api/state") {
      const admin = q.get("role") === "admin";
      if (admin && !isAdmin(req)) return sendJson(res, { error: "Admin login required." }, 401);
      sendJson(res, ctx.gm.getState({ isAdmin: admin, playerId: q.get("player_id"), token: q.get("token") }));
    } else if (path === "/api/reviews") {
      if (!isAdmin(req)) return sendJson(res, { error: "Admin only" }, 403);
      sendJson(res, { reviews: accounts.reviews() });
    } else if (path === "/api/leaderboard") sendJson(res, { leaderboard: accounts.leaderboard() });
    else if (path === "/health") sendJson(res, { status: "ok", game: "one-of-these-people-is-not-lying", lan_ip: ctx.lanIp, port: ctx.port });
    else notFound(res);
  };

  const doPost = async (req: IncomingMessage, res: ServerResponse) => {
    const path = new URL(req.url || "/", "http://x").pathname;
    if (path === "/api/admin/logout") {
      redirect(res, "/admin/login", `liars_admin=; Max-Age=0; ${cookieAttrs(req)}`);
    } else if (path === "/api/admin/login") {
      const form = new URLSearchParams((await readBody(req, 4096)).toString("utf-8"));
      const user = form.get("username") || "";
      const pw = form.get("password") || "";
      let next = form.get("next") || "/admin";
      next = next === "/admin" || next === "/admin/control" ? next : "/admin";
      const same = (a: string, b: string) => {
        const x = Buffer.from(a);
        const y = Buffer.from(b);
        return x.length === y.length && timingSafeEqual(x, y);
      };
      if (same(user, cfg.adminUser) && same(pw, cfg.adminPass)) {
        redirect(res, next, `liars_admin=${makeAdminCookie()}; Max-Age=${30 * 86400}; ${cookieAttrs(req)}`);
      } else {
        if (cfg.loginDelayMs > 0) await new Promise((r) => setTimeout(r, cfg.loginDelayMs)); // slow down guessing
        redirect(res, `/admin/login?error=1&next=${next}`);
      }
    } else if (path === "/api/action") {
      const length = parseInt(req.headers["content-length"] || "0", 10) || 0;
      if (length === 0) return sendJson(res, { error: "Missing request body" }, 400);
      if (length > 8_000_000) return sendJson(res, { error: "Request too large." }, 413); // a 5 MB resume PDF, base64-encoded
      const raw = await readBody(req, 8_000_000);
      let payload: Json;
      try {
        const parsed: unknown = JSON.parse(raw.toString("utf-8"));
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("not an object");
        payload = parsed as Json;
      } catch (e) {
        return sendJson(res, { error: `Invalid JSON: ${e instanceof Error ? e.message : String(e)}` }, 400);
      }
      await handleAction(ctx, req, res, String(payload.action ?? ""), payload);
    } else notFound(res);
  };

  return async (req, res) => {
    res.on("finish", () => logLine(req, res));
    try {
      if (req.method === "OPTIONS") {
        res.writeHead(204, { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" });
        res.end();
      } else if (req.method === "GET" || req.method === "HEAD") doGet(req, res);
      else if (req.method === "POST") await doPost(req, res);
      else send(res, 405, "text/plain; charset=utf-8", "Method Not Allowed");
    } catch (e) {
      if (!res.headersSent) sendJson(res, { error: `Server error: ${e instanceof Error ? e.message : String(e)}` }, 500);
      else res.end();
    }
  };
}

/** Notable HTTP events go into the game log for live monitoring (state polling and the QR image are left out). */
export function logRequest(gm: GameManager, line: string, code: string): void {
  if (line.includes("/api/state") || line.includes("/api/qr.svg")) return;
  gm.log(`HTTP: ${line} -> ${code}`, code.startsWith("4") || code.startsWith("5") ? "WARN" : "INFO");
}

const str = (v: unknown, fallback = ""): string => (v === undefined || v === null ? fallback : String(v));
const strList = (v: unknown): string[] => (Array.isArray(v) ? v.map(String) : []);

async function handleAction(ctx: ServerContext, req: IncomingMessage, res: ServerResponse, action: string, payload: Json): Promise<void> {
  const game = ctx.gm;
  if (cfg.logRequests) process.stdout.write(`${COLOR_DIM}[${stamp()}]${COLOR_RESET} ${COLOR_MAGENTA}[ACTION]${COLOR_RESET} ${COLOR_BOLD}${action}${COLOR_RESET}\n`);

  let addedPlayer: Player | null = null;
  const admin = validAdminCookie(parseCookies(req.headers.cookie)["liars_admin"]);
  if (!PLAYER_ACTIONS.has(action) && !admin) return sendJson(res, { error: "Admin login required." }, 401);
  let token = payload.token === undefined || payload.token === null ? null : String(payload.token);
  if (TOKEN_ACTIONS.has(action) && !admin) {
    const pid = str(payload[action === "cast_vote" ? "voter_id" : "player_id"]);
    if (!game.playerForToken(pid, token)) return sendJson(res, { error: "Your session expired. Log back in from the join page." }, 403);
  }

  game.touch();
  const extra: Json = {};
  const fail = (error: string, status: number, more: Json = {}) => sendJson(res, { error, ...more }, status);
  const roleError = (msg: string | null, counts: unknown) => fail(msg || "Role requirements not met.", 400, { role_counts: counts });

  switch (action) {
    case "join": {
      const { player, error } = game.join(str(payload.name), str(payload.password), Boolean(payload.permanent), str(payload.token), str(payload.new_password));
      if (error) return sendJson(res, { error, need_new_password: error === NEED_NEW_PASSWORD }, 403);
      addedPlayer = player;
      token = player!.token ?? null;
      break;
    }
    case "request_reset":
      if (accounts.requestReset(str(payload.name))) game.log(`Password reset requested: ${str(payload.name)}`, "ACTION");
      return sendJson(res, { ok: true }); // same answer either way: don't reveal which names have accounts
    case "reset_password": {
      const temp = accounts.resetPassword(str(payload.account_id));
      if (!temp) return fail("Unknown account.", 400);
      game.log("Admin reset a player's password.", "ACTION");
      extra.temp_password = temp;
      break;
    }
    case "parse_resume": {
      try {
        const b64 = str(payload.pdf);
        if (!/^[A-Za-z0-9+/]*={0,2}$/.test(b64) || b64.length % 4 !== 0) throw new RangeError("That file isn't a PDF.");
        const data = Buffer.from(b64, "base64");
        if (data.length > resume.MAX_PDF) throw new RangeError("That PDF is over 5 MB.");
        extra.draft = await resume.draftProfile(await resume.pdfText(data), packs.allTags());
      } catch (e) {
        if (e instanceof RangeError) return fail(e.message || "That file isn't a PDF.", 400);
        game.log(`Resume parsing failed: ${e instanceof Error ? e.message : String(e)}`, "WARN");
        return fail("The resume reader is offline right now. Try again later.", 503);
      }
      break;
    }
    case "review": {
      const p = game.playerForToken(str(payload.player_id), token) ?? {};
      const err = game.addReview(p, payload.score, payload.text);
      if (err) return fail(err, 400);
      break;
    }
    case "auto_tags": {
      const p = game.playerForToken(str(payload.player_id), token);
      const text = str(payload.expertise || p?.expertise).trim();
      if (!text) return fail("Write a few lines about your expertise first.", 400);
      try {
        extra.tags = await resume.suggestTags(text.slice(0, 600), packs.allTags());
      } catch (e) {
        game.log(`Auto tags failed: ${e instanceof Error ? e.message : String(e)}`, "WARN");
        return fail("The tag helper is offline right now. Try again later.", 503);
      }
      break;
    }
    case "new_topics":
      game.newTopics(Boolean(payload.record_old));
      break;
    case "end_game":
      game.endGame();
      break;
    case "set_setting": {
      const name = str(payload.name);
      if (!accounts.setSetting(name, payload.value)) return fail("Unknown setting.", 400);
      game.log(`Setting ${name} = ${String(accounts.settings()[name])}`, "ACTION");
      break;
    }
    case "delete_account":
      accounts.deleteAccount(str(payload.account_id));
      break;
    case "clear_account_history":
      accounts.clearUserHistory(str(payload.account_id));
      break;
    case "set_phase": {
      const target = str(payload.phase, "lobby");
      if (game.phase === "reveal" && ["setup", "questioning", "voting"].includes(target)) {
        return fail(`Round ${game.roundNumber} has completed. Cannot return to ${target}. Please start a new round or terminate game and return to lobby.`, 400);
      }
      if (game.phase === "lobby" && ["setup", "questioning", "voting", "reveal"].includes(target)) {
        const [valid, err, counts] = game.checkRoleRequirements();
        if (!valid) return roleError(err, counts);
      }
      const ok = game.setPhase(target);
      if (!ok && target !== game.phase) {
        const [, err, counts] = game.checkRoleRequirements();
        return fail(err || `Failed to switch stage to ${target}`, 400, { role_counts: counts });
      }
      break;
    }
    case "next_phase": {
      if (game.phase === "reveal") return fail("Round has completed. Advance is disabled. Please start a new round or terminate game and return to lobby.", 400);
      if (game.phase === "lobby") {
        const [valid, err, counts] = game.checkRoleRequirements();
        if (!valid) return roleError(err, counts);
      }
      game.nextPhase();
      if (game.phase === "lobby") {
        const [valid, err, counts] = game.checkRoleRequirements();
        if (!valid) return roleError(err, counts);
      }
      break;
    }
    case "add_player":
      addedPlayer = game.addPlayer(str(payload.name), payload.player_id === undefined || payload.player_id === null ? null : str(payload.player_id));
      break;
    case "sync_player":
      addedPlayer = game.syncPlayer(str(payload.player_id), str(payload.name));
      break;
    case "remove_player":
      game.removePlayer(str(payload.player_id));
      break;
    case "set_role":
      game.setPlayerRole(str(payload.player_id), str(payload.role, "liar"), payload.is_voter as boolean | null | undefined);
      break;
    case "set_guesser": {
      const ids = payload.player_ids;
      if (Array.isArray(ids) && ids.length) game.setGuessers(ids.map(String), payload.voter_id === undefined ? null : str(payload.voter_id));
      else game.setPlayerRole(str(payload.player_id), "guesser", payload.is_voter === undefined ? true : (payload.is_voter as boolean | null));
      break;
    }
    case "set_guessers":
      game.setGuessers(strList(payload.player_ids), payload.voter_id === undefined ? null : str(payload.voter_id));
      break;
    case "set_truth_teller": {
      const ids = payload.player_ids;
      if (Array.isArray(ids) && ids.length) game.setTruthTellers(ids.map(String));
      else game.setPlayerRole(str(payload.player_id), "truth_teller");
      break;
    }
    case "set_truth_tellers":
      game.setTruthTellers(strList(payload.player_ids));
      break;
    case "set_role_counts":
      game.setRoleCounts(payload.guesser_count ?? 1, payload.truth_teller_count ?? 1, payload.apply_now === undefined ? true : Boolean(payload.apply_now));
      break;
    case "set_role_mode":
      if (!game.setRoleMode(str(payload.mode))) return fail("Unknown role mode.", 400);
      break;
    case "set_profile": {
      const tags = payload.tags;
      if (!Array.isArray(tags) || !game.setProfile(str(payload.player_id), tags, str(payload.expertise))) return fail("Could not save your interests.", 400);
      break;
    }
    case "toggle_ready":
      if (!game.toggleReady(str(payload.player_id))) return fail("Not ready to start yet.", 400);
      break;
    case "set_voting_guesser":
      game.setVotingGuesser(str(payload.player_id));
      break;
    case "randomize_roles":
      game.randomizeRoles();
      break;
    case "set_packs":
      if (!game.setPacks(strList(payload.pack_ids))) return fail("Select at least one existing pack.", 400);
      break;
    case "clear_topic_history":
      game.clearTopicHistory();
      break;
    case "cast_vote": {
      const target = payload.target_id as string | string[] | null | undefined;
      const targets = payload.target_ids as string | string[] | null | undefined;
      if (!game.castVote(str(payload.voter_id), target, targets)) return fail("Only the designated voting guesser can cast a vote for valid suspect(s)!", 403);
      break;
    }
    case "guesser_advance":
      if (!game.guesserAdvance(str(payload.player_id))) return fail("Only the Guesser can advance the game stages!", 403);
      break;
    case "reveal":
      game.revealAndScore();
      break;
    case "next_round": {
      const [valid, err, counts] = game.checkRoleRequirements();
      if (!valid) return roleError(err, counts);
      game.nextRound();
      break;
    }
    case "reset_game":
      game.resetGame();
      break;
    case "clear_logs":
      game.clearLogs();
      break;
    case "adjust_score":
      game.adjustScore(str(payload.player_id), Number(payload.delta ?? 0));
      break;
    default:
      return fail(`Unknown action: ${action}`, 400);
  }

  const me = addedPlayer ? addedPlayer.id : str(payload.voter_id || payload.player_id) || null;
  const state: GameState = game.getState({ isAdmin: admin, playerId: me, token });
  if (addedPlayer) {
    state.joined_player_id = addedPlayer.id;
    state.joined_player_name = addedPlayer.name;
    state.token = addedPlayer.token;
  }
  sendJson(res, { ...state, ...extra });
}

/** Is something already listening on the port? */
export function isPortInUse(port: number, host = "0.0.0.0"): Promise<boolean> {
  return new Promise((resolve) => {
    const probe = createNetServer();
    probe.once("error", () => resolve(true));
    probe.listen(port, host, () => probe.close(() => resolve(false)));
  });
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function pidsOnPort(port: number): Set<number> {
  const pids = new Set<number>();
  const collect = (out: string) => {
    for (const tok of out.split(/\s+/)) {
      const pid = parseInt(tok, 10);
      if (Number.isInteger(pid) && pid > 0 && pid !== process.pid) pids.add(pid);
    }
  };
  for (const [cmd, args] of [["lsof", ["-ti", `:${port}`]], ["/usr/sbin/lsof", ["-ti", `:${port}`]]] as const) {
    try {
      collect(execFileSync(cmd, [...args], { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] }));
      if (pids.size) break;
    } catch {
      /* try the next one */
    }
  }
  if (!pids.size) {
    try {
      collect(execFileSync("fuser", [`${port}/tcp`], { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] }));
    } catch {
      /* not installed or nothing found */
    }
  }
  return pids;
}

/** Find any process listening on the port and terminate it so the port is free again. */
export async function killProcessOnPort(port: number, maxWaitSeconds = 3.0): Promise<boolean> {
  const pids = pidsOnPort(port);
  if (!pids.size) return false;
  for (const pid of pids) {
    process.stdout.write(`${COLOR_DIM}[${stamp()}]${COLOR_RESET} ${COLOR_YELLOW}[SERVER] Port ${port} is occupied by previous session (PID ${pid}). Terminating old session to start new one...${COLOR_RESET}\n`);
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      /* already gone */
    }
  }
  let deadline = Date.now() + maxWaitSeconds * 1000;
  while (Date.now() < deadline) {
    if (!(await isPortInUse(port))) return true;
    await sleep(100);
  }
  for (const pid of pids) {
    try {
      process.kill(pid, "SIGKILL");
    } catch {
      /* already gone */
    }
  }
  deadline = Date.now() + 1500;
  while (Date.now() < deadline) {
    if (!(await isPortInUse(port))) return true;
    await sleep(100);
  }
  return !(await isPortInUse(port));
}

/** Ensure the port is available by terminating any stale session occupying it. */
export async function findFreePort(startPort = 5050): Promise<number> {
  if (await isPortInUse(startPort)) await killProcessOnPort(startPort);
  return startPort;
}

export interface Running {
  server: Server;
  port: number;
  lanIp: string;
}

export interface CreateServerOptions {
  host?: string;
  port?: number;
  gameManager?: GameManager;
  /** Port 0 picks a free port (tests); the game then reports the one it got. */
}

function listen(server: Server, port: number, host: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const onError = (e: Error) => reject(e);
    server.once("error", onError);
    server.listen(port, host, () => {
      server.off("error", onError);
      const addr = server.address();
      resolve(typeof addr === "object" && addr ? addr.port : port);
    });
  });
}

export async function createServer({ host = "0.0.0.0", port = 5050, gameManager }: CreateServerOptions = {}): Promise<Running> {
  const gm = gameManager ?? new GameManager();
  const lanIp = getLanIp();
  await qrReady;

  // The port must not change: if it is in use, terminate the previous session and take over.
  if (port !== 0 && (await isPortInUse(port, host))) await killProcessOnPort(port);

  const ctx: ServerContext = { gm, port, lanIp };
  const server = createHttpServer(createHandler(ctx));
  try {
    ctx.port = await listen(server, port, host);
  } catch (e) {
    // Still busy: one aggressive kill attempt and a retry
    process.stdout.write(`${COLOR_DIM}[${stamp()}]${COLOR_RESET} ${COLOR_RED}[SERVER] Port ${port} still busy (${String(e)}). Force terminating lingering sessions on port ${port}...${COLOR_RESET}\n`);
    await killProcessOnPort(port, 2.0);
    await sleep(200);
    ctx.port = await listen(server, port, host);
  }
  gm.log(`HTTP Server listening on port ${ctx.port} (LAN IP: ${lanIp})`, "INFO");
  return { server, port: ctx.port, lanIp };
}
