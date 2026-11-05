/** Unit tests for the QR code generator. */
import { strict as assert } from "node:assert";
import { test } from "node:test";
import { QRCode, generateQrSvg, ready, rsEncode } from "../src/qr.ts";

test("qr generation", async () => {
  await ready;
  const url = "http://192.168.0.136:5050/join";
  const qr = new QRCode(url);
  assert.ok(qr.size > 20);
  assert.equal(qr.modules[0]![0], true); // top-left finder pattern corner

  const svg = generateQrSvg(url);
  assert.ok(svg.includes("<svg"));
  assert.ok(svg.includes("</svg>"));
  assert.ok(svg.includes('xmlns="http://www.w3.org/2000/svg"'));
  assert.ok(svg.includes('shape-rendering="crispEdges"'));
});

test("qr versions", () => {
  assert.ok(new QRCode("hello").version <= 2); // short text -> version 1 or 2
  assert.ok([2, 3, 4].includes(new QRCode("http://192.168.1.100:5050/join").version)); // medium URL
});

test("reed-solomon standard equivalence", () => {
  const data = [65, 230, 135, 71, 71, 3, 162, 242, 243, 19, 147, 34, 227, 19, 99, 130, 227, 2, 227, 19, 51, 99, 163, 83, 3, 83, 2, 246, 166, 246, 150, 224, 236, 17];
  assert.deepEqual(rsEncode(data, 10), [68, 67, 223, 140, 251, 8, 119, 118, 223, 132]);
});

test("logo is drawn in a cleared centre square with the package encoder", async () => {
  await ready;
  const svg = generateQrSvg("http://192.168.0.136:5050/join", { bg: "", logo: '<path d="M3 10h18"/>' });
  assert.ok(svg.includes("<g transform="));
  assert.ok(!svg.includes("<rect")); // transparent background
});
