import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { VERSION } from "../src/version.ts";
import { ROOT } from "./helpers.ts";

test("version matches package.json", () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf-8")) as { version: string };
  assert.equal(VERSION, pkg.version);
});
