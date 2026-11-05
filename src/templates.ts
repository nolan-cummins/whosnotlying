/**
 * The six pages, each a self-contained HTML document in src/templates/ (its own CSS and inline
 * JavaScript, no build step). A handful of {{placeholders}} are filled in per request:
 * - Admin console (/admin, login required)
 * - Lobby QR code tab (/qr or /lobby)
 * - Player phone page (/join)
 * - Public display (/display)
 * - Stage controller (/admin/control)
 * - Admin login (/admin/login)
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = join(fileURLToPath(new URL(".", import.meta.url)), "templates");
const cache = new Map<string, string>();

function page(name: string, vars: Record<string, string | number> = {}): string {
  let html = cache.get(name);
  if (html === undefined) {
    html = readFileSync(join(dir, name + ".html"), "utf-8");
    cache.set(name, html);
  }
  for (const [k, v] of Object.entries(vars)) html = html.replaceAll(`{{${k}}}`, String(v));
  return html;
}

const joinUrl = (port: number, lanIp: string, baseUrl?: string | null): string => (baseUrl ? `${baseUrl.replace(/\/+$/, "")}/join` : `http://${lanIp}:${port}/join`);

export function getAdminHtml(port: number, lanIp: string, baseUrl?: string | null): string {
  return page("admin", { port, join_url: joinUrl(port, lanIp, baseUrl) });
}

export function getQrHtml(port: number, lanIp: string, baseUrl?: string | null): string {
  return page("qr", {
    primary_join_url: joinUrl(port, lanIp, baseUrl),
    join_url_lan: `http://${lanIp}:${port}/join`,
    join_url_local: `http://127.0.0.1:${port}/join`,
    lan_ip: lanIp,
  });
}

export function getJoinHtml(_port: number): string {
  return page("join");
}

export function getDisplayHtml(_port: number): string {
  return page("display");
}

export function getStageControlHtml(_port: number): string {
  return page("control");
}

export function getAdminLoginHtml(): string {
  return page("login");
}
