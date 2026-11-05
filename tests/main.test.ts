import { strict as assert } from "node:assert";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { main } from "../src/main.ts";
import type { GameManager } from "../src/game.ts";
import { ROOT, isolate } from "./helpers.ts";

isolate();

test("main --help runs cleanly", () => {
  const r = spawnSync(process.execPath, [join(ROOT, "src", "main.ts"), "--help"], { encoding: "utf-8" });
  assert.equal(r.status, 0, r.stderr);
  assert.ok(r.stdout.includes("One of These People Is Not Lying"));
});

test("main initialises an empty lobby and passes the arguments through", async () => {
  let got: { port?: number; gameManager?: GameManager } | null = null;
  let tabs = 0;
  const fake = { close: (cb?: () => void) => cb?.() } as unknown as import("node:http").Server;
  const running = await main(["--no-browser", "--port", "5055"], {
    createServer: async (opts = {}) => {
      got = opts;
      return { server: fake, port: opts.port ?? 0, lanIp: "127.0.0.1" };
    },
    openBrowserTabsDelayed: () => {
      tabs++;
    },
  });
  assert.ok(running);
  assert.equal(got!.port, 5055);
  const gm = got!.gameManager!;
  assert.equal(gm.players.length, 0);
  assert.deepEqual(gm.guesserIds, []);
  assert.deepEqual(gm.truthTellerIds, []);
  assert.equal(tabs, 0);
});
