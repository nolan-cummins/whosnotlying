/** The pages carry their JavaScript inline; parse every script block with `node --check`. */
import { strict as assert } from "node:assert";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as templates from "../src/templates.ts";

const PAGES: Record<string, () => string> = {
  admin: () => templates.getAdminHtml(5050, "127.0.0.1"),
  qr: () => templates.getQrHtml(5050, "127.0.0.1"),
  join: () => templates.getJoinHtml(5050),
  display: () => templates.getDisplayHtml(5050),
  control: () => templates.getStageControlHtml(5050),
  login: () => templates.getAdminLoginHtml(),
};

for (const [page, render] of Object.entries(PAGES)) {
  test(`inline scripts parse: ${page}`, () => {
    const dir = mkdtempSync(join(tmpdir(), "tpl-"));
    try {
      const scripts = [...render().matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1] as string);
      scripts.forEach((js, i) => {
        const f = join(dir, `${page}${i}.js`);
        writeFileSync(f, js);
        const r = spawnSync(process.execPath, ["--check", f], { encoding: "utf-8" });
        assert.equal(r.status, 0, r.stderr);
      });
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
}

test("placeholders are all filled in", () => {
  for (const render of Object.values(PAGES)) assert.ok(!/\{\{[a-z_]+\}\}/.test(render()));
  assert.ok(templates.getAdminHtml(5050, "10.0.0.2").includes("http://10.0.0.2:5050/join"));
  assert.ok(templates.getAdminHtml(5050, "10.0.0.2", "https://game.example.com/").includes("https://game.example.com/join"));
  const qr = templates.getQrHtml(5050, "10.0.0.2", "https://game.example.com");
  assert.ok(qr.includes("https://game.example.com/join") && qr.includes("http://10.0.0.2:5050/join") && qr.includes("http://127.0.0.1:5050/join"));
});
