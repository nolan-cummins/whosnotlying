import { strict as assert } from "node:assert";
import { test } from "node:test";
import { lint, repoPacks } from "../scripts/lint_packs.ts";

test("shipped packs have no lint errors", () => {
  const { errors } = lint(repoPacks());
  assert.deepEqual(errors, []);
});
