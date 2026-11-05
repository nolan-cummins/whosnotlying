import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import * as accounts from "../src/accounts.ts";
import { GameManager, findTopicData } from "../src/game.ts";
import * as packs from "../src/packs.ts";
import { isolate, sandbox } from "./helpers.ts";

isolate();

function addPack(pid: string, n = 3): void {
  const topics = Array.from({ length: n }, (_, i) => ({
    id: `t${i}`, category: "c", topic: `${pid} topic ${i}`, true_statement: `${pid} true ${i}`, true_description: "- d", false_statements: [`${pid} false ${i}`],
  }));
  writeFileSync(join(sandbox.packsDir, `${pid}.json`), JSON.stringify({ id: pid, name: pid, topics }));
}

test("a new pack autoloads, can be selected, and history resets", () => {
  const gm = new GameManager({ seedSamples: true });
  const shipped = new Set(packs.packSummaries().map((p) => p.id));
  assert.ok(shipped.has("ai-hallucinations-1"));
  addPack("extra");
  assert.deepEqual(new Set(packs.packSummaries().map((p) => p.id)), new Set([...shipped, "extra"]));

  assert.ok(gm.setPacks(["extra"]));
  assert.ok(!gm.setPacks(["nope"])); // invalid selection is rejected, previous one kept
  assert.deepEqual(new Set(packs.library().map((t) => t.pack)), new Set(["extra"]));

  gm.assignRoundRoles();
  assert.ok(gm.players.filter((p) => p.topic).every((p) => findTopicData(p.topic)!.pack === "extra"));
  gm.setPhase("questioning", true);
  const used = Object.fromEntries(packs.packSummaries(new Set(accounts.globalKeys())).map((p) => [p.id, p.used]));
  assert.equal(used["extra"], 3);

  gm.clearTopicHistory();
  assert.deepEqual(accounts.globalKeys(), []);
});

test("v1 used flags migrate into the history file", () => {
  const path = join(sandbox.packsDir, "ai-hallucinations-1.json");
  const raw = JSON.parse(readFileSync(path, "utf-8"));
  for (const t of raw.topics.slice(0, 2)) t.true_statement = "truth" in t ? t.truth.text : t.true_statement;
  Object.assign(raw.topics[0], { used: true, used_as: "true" });
  Object.assign(raw.topics[1], { used: true });
  writeFileSync(path, JSON.stringify(raw));
  new GameManager();
  const [tid0, tid1] = [raw.topics[0].id, raw.topics[1].id];
  assert.deepEqual(accounts.globalKeys(), [`ai-hallucinations-1:${tid0}:t`, `ai-hallucinations-1:${tid1}:?`]);
  assert.ok(!("used" in packs.library()[0]!)); // flags in the file are ignored by the loader
});

test("statement keys and the v2 schema", () => {
  writeFileSync(
    join(sandbox.packsDir, "v2.json"),
    JSON.stringify({ id: "v2", topics: [{ id: "a", category: "c", topic: "T", truth: { text: "true one", facts: ["f1"] }, lies: [{ text: "lie one", facts: ["g1"] }, { text: "lie two", facts: [] }] }] }),
  );
  const t = packs.library().find((x) => x.pack === "v2")!;
  assert.equal(t.true_description, "• f1");
  assert.deepEqual(t.false_statements, ["lie one", "lie two"]);
  assert.equal(packs.statementKey(t, "true one"), "v2:a:t");
  assert.equal(packs.statementKey(t, "lie two"), "v2:a:f1");
  assert.deepEqual(packs.lieFacts(t, "lie one"), ["g1"]);
});
