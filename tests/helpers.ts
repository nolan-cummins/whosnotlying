/**
 * Shared fixtures: every test gets an isolated data directory and an isolated copy of the packs
 * (the game writes _settings.json next to them), a fresh embedding cache that never reaches a real
 * Ollama server, and a quiet HTTP server on a random port when it needs one.
 */
import { afterEach, beforeEach } from "node:test";
import { cpSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import * as accounts from "../src/accounts.ts";
import * as game from "../src/game.ts";
import type { GameManager, Player } from "../src/game.ts";
import * as match from "../src/match.ts";
import * as packs from "../src/packs.ts";
import * as rng from "../src/rng.ts";
import * as server from "../src/server.ts";

export const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
export const REAL_PACKS = join(ROOT, "packs");

export interface Sandbox {
  dir: string;
  packsDir: string;
  dataDir: string;
}

export const sandbox: Sandbox = { dir: "", packsDir: "", dataDir: "" };

/** Register the per-test isolation hooks for this file (call once at the top level). */
export function isolate(): Sandbox {
  beforeEach(() => {
    sandbox.dir = mkdtempSync(join(tmpdir(), "wnl-"));
    sandbox.packsDir = join(sandbox.dir, "packs");
    sandbox.dataDir = join(sandbox.dir, "data");
    cpSync(REAL_PACKS, sandbox.packsDir, { recursive: true });
    rmSync(join(sandbox.packsDir, "_settings.json"), { force: true });
    game.setPlayersFile(join(sandbox.dir, "players.json"));
    packs.setPacksDir(sandbox.packsDir);
    accounts.setDataDir(sandbox.dataDir);
    match.resetForTests();
    server.resetAdminSecret();
    server.cfg.loginDelayMs = 0;
    server.cfg.logRequests = false;
    rng.seed();
  });
  afterEach(() => {
    rmSync(sandbox.dir, { recursive: true, force: true });
    packs.clearCache();
  });
  return sandbox;
}

/** Session token for a player (tests skip the join flow). */
export function tok(gm: GameManager, pid: string): string {
  const p = gm.players.find((x) => x.id === pid) as Player;
  p.token ??= "tok_" + pid;
  return p.token;
}

export interface Reply {
  status: number;
  headers: Headers;
  text: string;
  json: Record<string, any>;
}

export interface TestServer {
  base: string;
  port: number;
  gm: GameManager;
  get(path: string, opts?: { admin?: boolean }): Promise<Reply>;
  post(path: string, body: string | Record<string, unknown>, opts?: { admin?: boolean; form?: boolean }): Promise<Reply>;
  /** POST /api/action as JSON. */
  action(payload: Record<string, unknown>, opts?: { admin?: boolean }): Promise<Reply>;
  close(): Promise<void>;
}

/** An HTTP server for one test on a free port; requests carry the admin cookie unless `admin: false`. */
export async function startServer(gm: GameManager, lanIp = "192.168.0.100"): Promise<TestServer> {
  const running = await server.createServer({ host: "127.0.0.1", port: 0, gameManager: gm });
  // createServer reports the real LAN address; tests want a fixed one in the pages
  const ctxServer = running.server;
  ctxServer.removeAllListeners("request");
  ctxServer.on("request", server.createHandler({ gm, port: running.port, lanIp }));
  const base = `http://127.0.0.1:${running.port}`;
  const send = async (method: string, path: string, body?: string, headers: Record<string, string> = {}, admin = true): Promise<Reply> => {
    if (admin) headers["Cookie"] = "liars_admin=" + server.makeAdminCookie();
    const res = await fetch(base + path, { method, headers, body, redirect: "manual" });
    const text = await res.text();
    let json: Record<string, any> = {};
    try {
      json = JSON.parse(text);
    } catch {
      /* not JSON */
    }
    return { status: res.status, headers: res.headers, text, json };
  };
  return {
    base,
    port: running.port,
    gm,
    get: (path, opts = {}) => send("GET", path, undefined, {}, opts.admin ?? true),
    post: (path, body, opts = {}) =>
      send("POST", path, typeof body === "string" ? body : JSON.stringify(body), { "Content-Type": opts.form ? "application/x-www-form-urlencoded" : "application/json" }, opts.admin ?? true),
    action: (payload, opts = {}) => send("POST", "/api/action", JSON.stringify(payload), { "Content-Type": "application/json" }, opts.admin ?? true),
    close: () => new Promise((resolve) => ctxServer.close(() => resolve())),
  };
}
