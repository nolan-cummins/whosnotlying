import { strict as assert } from "node:assert";
import { test } from "node:test";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { GameManager } from "../src/game.ts";
import * as match from "../src/match.ts";
import { mulberry32 } from "../src/rng.ts";
import { isolate, sandbox } from "./helpers.ts";

isolate();

const topics = (n = 40) => {
  const tags = ["Physics", "Art", "Sports", "Medicine"];
  return Array.from({ length: n }, (_, i) => ({ id: `t${i}`, topic: `T${i}`, tags: [tags[i % 4] as string], group: null }));
};
const count = (xs: string[]) => {
  const c = new Map<string, number>();
  for (const x of xs) c.set(x, (c.get(x) ?? 0) + 1);
  return c;
};

test("tags bias but do not lock", () => {
  const ts = topics();
  const rng = mulberry32(1);
  const hits = new Map<string, number>();
  for (let i = 0; i < 500; i++) {
    const got = match.deal([{ id: "a", tags: ["Physics"] }, { id: "b" }], ts, "tags", rng);
    const tag = got.get("a")!.tags[0]!;
    hits.set(tag, (hits.get(tag) ?? 0) + 1);
    assert.notEqual(got.get("a"), got.get("b"));
  }
  const total = [...hits.values()].reduce((a, b) => a + b, 0);
  assert.ok((hits.get("Physics") ?? 0) > 250 && total - (hits.get("Physics") ?? 0) > 25, JSON.stringify([...hits])); // chance would be 125
});

test("no profile is uniform", () => {
  const ts = topics();
  const rng = mulberry32(2);
  const hits = count(Array.from({ length: 2000 }, () => match.deal([{ id: "a" }], ts, "tags", rng).get("a")!.tags[0]!));
  assert.ok([...hits.values()].every((n) => n > 400 && n < 600), JSON.stringify([...hits]));
});

test("one topic per paper group", () => {
  const ts = Array.from({ length: 9 }, (_, i) => ({ id: `t${i}`, topic: `T${i}`, tags: [], group: `doi${Math.floor(i / 3)}` }));
  for (let seed = 0; seed < 200; seed++) {
    const got = match.deal([{ id: "a" }, { id: "b" }, { id: "c" }], ts, "off", mulberry32(seed));
    assert.equal(new Set([...got.values()].map((t) => t.group)).size, 3);
  }
});

test("expertise prefers the nearest topics", () => {
  const ts = Array.from({ length: 30 }, (_, i) => ({ id: `t${i}`, topic: `T${i}`, summary: `s${i}`, tags: [] }));
  const vec = (i: number) => (i < 10 ? [1.0, 0.0] : [0.0, 1.0]);
  match.state.vecs = new Map([...ts.map((t, i) => [match.key(`s${i}`), vec(i)] as [string, number[]]), [match.key(match.queryText("cats")), [1.0, 0.0]]]);
  match.state.cos = new Map();
  match.state.loaded = true;
  const rng = mulberry32(3);
  let near = 0;
  for (let i = 0; i < 500; i++) if (parseInt(match.deal([{ id: "a", expertise: "cats" }], ts, "expertise", rng).get("a")!.id.slice(1), 10) < 10) near++;
  assert.ok(near > 250, String(near)); // chance would be ~167
});

test("one-sided items go to the right role", () => {
  // Packs may hold truth-only and lie-only items; truth tellers and liars must each get their kind.
  const items: Record<string, unknown>[] = Array.from({ length: 6 }, (_, i) => ({ id: `t${i}`, category: "C", topic: `Truth ${i}`, truth: { text: `real ${i}`, facts: ["a", "b", "c"] } }));
  for (let i = 0; i < 12; i++) items.push({ id: `l${i}`, category: "C", topic: `Lie ${i}`, lies: [{ text: `fake ${i}`, facts: ["a", "b"] }] });
  writeFileSync(join(sandbox.packsDir, "split.json"), JSON.stringify({ id: "split", name: "Split", version: 2, topics: items }));
  const gm = new GameManager();
  assert.ok(gm.setPacks(["split"]));
  for (let n = 0; n < 5; n++) gm.addPlayer(`P${n}`);
  for (let i = 0; i < 20; i++) {
    gm.randomizeRoles();
    for (const p of gm.players) {
      if (p.role === "truth_teller") assert.ok(p.topic!.startsWith("Truth") && p.statement!.startsWith("real"));
      else if (p.role === "liar") assert.ok(p.topic!.startsWith("Lie") && p.statement!.startsWith("fake"));
    }
  }
  const liar = gm.players.find((p) => p.role === "liar")!;
  gm.setPlayerRole(liar.id, "truth_teller"); // a role swap re-deals from the truth pool
  assert.ok(liar.topic!.startsWith("Truth") && liar.statement!.startsWith("real"));
});

test("tags match by meaning", () => {
  // A custom tag ("army") pulls topics tagged with a different but related tag ("Military History").
  const ts = Array.from({ length: 30 }, (_, i) => ({ id: `t${i}`, topic: `T${i}`, tags: [i < 10 ? "Military History" : "Cooking"] }));
  const vec: Record<string, number[]> = { army: [0.9, 0.1], "Military History": [1.0, 0.0], Cooking: [0.0, 1.0] };
  match.state.vecs = new Map(Object.entries(vec).map(([k, v]) => [match.key(match.tagText(k)), v]));
  match.state.cos = new Map();
  match.state.loaded = true;
  const rng = mulberry32(4);
  let mil = 0;
  for (let i = 0; i < 500; i++) if (match.deal([{ id: "a", tags: ["army"] }], ts, "tags", rng).get("a")!.tags[0] === "Military History") mil++;
  assert.ok(mil > 250, String(mil)); // chance would be ~167
});

test("percent ranks a topic within the pool", () => {
  const ts = Array.from({ length: 11 }, (_, i) => ({ id: `t${i}`, topic: `T${i}`, tags: [i === 0 ? "Physics" : i < 5 ? "Art" : "Sports"] }));
  const p = { id: "p", tags: ["Physics"] };
  assert.equal(match.percent(p, ts[0]!, ts, "tags"), 100);
  assert.equal(match.percent(p, ts[10]!, ts, "tags"), 0);
  assert.equal(match.percent({ id: "q" }, ts[0]!, ts, "tags"), null);
});

test("rankTags puts mine first then alphabetical without embeddings", () => {
  assert.deepEqual(match.rankTags(["Zoo"], ["Art", "Zoo", "Bees"]), ["Zoo", "Art", "Bees"]);
});

test("rankTags relevance: mine A-Z, then by meaning", async () => {
  // Stub embeddings: 2-d unit vectors; "Robots" and the robot-ish expertise point along x, "Cooking" along y.
  const vec: Record<string, number[]> = { Zoo: [0, 1], Robots: [1, 0], Engineering: [0.9, 0.436], Cooking: [0, 1], Art: [0.6, 0.8] };
  match.setEmbed(async (texts) => texts.map((t) => (t.startsWith("Topic: ") ? vec[t.split(": ", 2)[1]!]! : [1, 0])));
  const tags = ["Art", "Cooking", "Engineering", "Robots", "Zoo"];
  assert.deepEqual(match.rankTags(["Zoo", "Robots"], tags), ["Robots", "Zoo", "Art", "Cooking", "Engineering"]); // not embedded yet: A-Z
  match.warm([...tags.map(match.tagText), match.queryText("I build industrial robots")]);
  await match.idle();
  assert.deepEqual(match.rankTags(["Zoo", "Robots"], tags), ["Robots", "Zoo", "Cooking", "Engineering", "Art"]);
  // Expertise alone (no tags selected) still ranks by meaning, not A-Z
  assert.deepEqual(match.rankTags([], tags, "I build industrial robots"), ["Robots", "Engineering", "Art", "Cooking", "Zoo"]);
  assert.equal(await match.nearestTag("robots", ["Robots", "Cooking"]), "Robots"); // exact, case-insensitive
  assert.equal(await match.nearestTag("Engineering", ["Art", "Robots"]), "Robots"); // 0.9 cosine: an existing tag wins
  assert.equal(await match.nearestTag("Cooking", ["Robots"]), null); // unrelated: stays a custom tag
});

test("a warm queued during the drain is not dropped", async () => {
  // A text queued while the worker is finishing must still get embedded (the draining handoff).
  match.setEmbed(async (texts) => {
    const out: number[][] = [];
    for (const _ of texts) {
      await new Promise((r) => setTimeout(r, 20));
      out.push([1, 0]);
    }
    return out;
  });
  match.warm(["Topic: First"]); // worker starts on "First"
  await new Promise((r) => setTimeout(r, 10)); // ...and is mid-embed, so this call queues instead of starting a worker
  match.warm(["Topic: Second"]);
  for (let i = 0; i < 200; i++) {
    if (match.state.vecs.has(match.key("Topic: Second"))) break;
    await new Promise((r) => setTimeout(r, 10));
  }
  assert.ok(match.state.vecs.has(match.key("Topic: Second")));
});
