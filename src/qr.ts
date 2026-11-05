/**
 * QR Code generator (ISO/IEC 18004): a pure encoder for levels L/M, versions 1-5, plus the SVG writer.
 * generateQrSvg() prefers the `qrcode` package (any version, level H when a logo is drawn) and falls
 * back to the pure encoder when the package is missing.
 */
import type { QRCode as QrcodeCode } from "qrcode";

// GF(256) tables with primitive polynomial 0x11D (x^8 + x^4 + x^3 + x^2 + 1)
const EXP_TABLE = new Array<number>(512).fill(0);
const LOG_TABLE = new Array<number>(256).fill(0);
{
  let val = 1;
  for (let i = 0; i < 255; i++) {
    EXP_TABLE[i] = val;
    EXP_TABLE[i + 255] = val;
    LOG_TABLE[val] = i;
    val = (val << 1) ^ (val & 0x80 ? 0x11d : 0);
  }
}

export function gfMul(x: number, y: number): number {
  if (x === 0 || y === 0) return 0;
  return EXP_TABLE[(LOG_TABLE[x] as number) + (LOG_TABLE[y] as number)] as number;
}

/** Reed-Solomon generator polynomial g(x) = prod_{i=0}^{n-1} (x - alpha^i), high-to-low degree order. */
export function rsGeneratorPoly(ecCount: number): number[] {
  let g = [1];
  for (let i = 0; i < ecCount; i++) {
    const next = new Array<number>(g.length + 1).fill(0);
    g.forEach((coeff, j) => {
      next[j] ^= coeff;
      next[j + 1] ^= gfMul(coeff, EXP_TABLE[i] as number);
    });
    g = next;
  }
  return g;
}

/** Error correction codewords via polynomial division over GF(256). */
export function rsEncode(data: number[], ecCount: number): number[] {
  const gen = rsGeneratorPoly(ecCount);
  let res = new Array<number>(ecCount).fill(0);
  for (const byte of data) {
    const factor = byte ^ (res[0] as number);
    res = [...res.slice(1), 0];
    if (factor !== 0) for (let j = 0; j < ecCount; j++) res[j] = (res[j] as number) ^ gfMul(gen[j + 1] as number, factor);
  }
  return res;
}

type EcLevel = "L" | "M";

// Version specs: [total_codewords, data_codewords, ec_codewords, alignment_coords]
const VERSION_SPECS: Record<string, [number, number, number, number[]]> = {
  "1L": [26, 19, 7, []],
  "1M": [26, 16, 10, []],
  "2L": [44, 34, 10, [18]],
  "2M": [44, 28, 16, [18]],
  "3L": [70, 55, 15, [22]],
  "3M": [70, 44, 26, [22]],
  "4L": [100, 80, 20, [26]],
  "4M": [100, 64, 36, [26]],
  "5L": [134, 108, 26, [30]],
  "5M": [134, 86, 48, [30]],
};

// Standard 15-bit format info values for error correction L and M (masked with 0x5412)
const FORMAT_INFO: Record<string, number> = {
  L0: 0x77c4, L1: 0x72f3, L2: 0x7daa, L3: 0x789d, L4: 0x662f, L5: 0x6318, L6: 0x6c41, L7: 0x6976,
  M0: 0x5412, M1: 0x5125, M2: 0x5e7c, M3: 0x5b4b, M4: 0x45f9, M5: 0x40ce, M6: 0x4f97, M7: 0x4aa0,
};

export class QRCode {
  rawData: Uint8Array;
  ecLevel: EcLevel;
  version: number;
  size: number;
  modules: boolean[][];
  isFunction: boolean[][];

  constructor(data: string, ecLevel: EcLevel = "M") {
    this.rawData = new TextEncoder().encode(data);
    this.ecLevel = ecLevel;
    this.version = this.chooseVersion(this.rawData.length, ecLevel);
    this.size = 17 + 4 * this.version;
    this.modules = Array.from({ length: this.size }, () => new Array<boolean>(this.size).fill(false));
    this.isFunction = Array.from({ length: this.size }, () => new Array<boolean>(this.size).fill(false));
    this.build();
  }

  private chooseVersion(dataLen: number, ec: EcLevel): number {
    for (let v = 1; v <= 5; v++) {
      const spec = VERSION_SPECS[`${v}${ec}`];
      // Byte mode overhead: 4 bits mode + 8 bits count = 12 bits -> ~2 bytes
      if (spec && dataLen + 2 <= spec[1]) return v;
    }
    return 5;
  }

  private build(): void {
    this.placeFinderPatterns();
    this.placeSeparators();
    this.placeAlignmentPatterns();
    this.placeTimingPatterns();
    this.placeDarkModule();
    this.reserveFormatAreas();

    const dataBytes = this.generateDataCodewords();
    const ecBytes = rsEncode(dataBytes, VERSION_SPECS[`${this.version}${this.ecLevel}`]![2]);
    const all = [...dataBytes, ...ecBytes];

    const bits: number[] = [];
    for (const b of all) for (let shift = 7; shift >= 0; shift--) bits.push((b >> shift) & 1);

    this.placeDataBits(bits);
    this.selectBestMask();
  }

  private setModule(r: number, c: number, val: boolean, isFunc = false): void {
    if (r >= 0 && r < this.size && c >= 0 && c < this.size) {
      this.modules[r]![c] = val;
      if (isFunc) this.isFunction[r]![c] = true;
    }
  }

  private placeFinder(top: number, left: number): void {
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        const black = r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4);
        this.setModule(top + r, left + c, black, true);
      }
    }
  }

  private placeFinderPatterns(): void {
    this.placeFinder(0, 0);
    this.placeFinder(0, this.size - 7);
    this.placeFinder(this.size - 7, 0);
  }

  private placeSeparators(): void {
    for (let i = 0; i < 8; i++) {
      this.setModule(7, i, false, true);
      this.setModule(i, 7, false, true);
      this.setModule(7, this.size - 8 + i, false, true);
      this.setModule(i, this.size - 8, false, true);
      this.setModule(this.size - 8, i, false, true);
      this.setModule(this.size - 8 + i, 7, false, true);
    }
  }

  private placeAlignmentPatterns(): void {
    const coords = VERSION_SPECS[`${this.version}${this.ecLevel}`]?.[3] ?? [];
    for (const r of coords) {
      for (const c of coords) {
        if (this.isFunction[r]![c]) continue;
        for (let dr = -2; dr <= 2; dr++) {
          for (let dc = -2; dc <= 2; dc++) {
            const black = Math.abs(dr) === 2 || Math.abs(dc) === 2 || (dr === 0 && dc === 0);
            this.setModule(r + dr, c + dc, black, true);
          }
        }
      }
    }
  }

  private placeTimingPatterns(): void {
    for (let i = 8; i < this.size - 8; i++) {
      const color = i % 2 === 0;
      if (!this.isFunction[6]![i]) this.setModule(6, i, color, true);
      if (!this.isFunction[i]![6]) this.setModule(i, 6, color, true);
    }
  }

  private placeDarkModule(): void {
    this.setModule(4 * this.version + 9, 8, true, true);
  }

  private reserveFormatAreas(): void {
    for (let i = 0; i < 9; i++) {
      this.isFunction[8]![i] = true;
      this.isFunction[i]![8] = true;
    }
    for (let i = this.size - 8; i < this.size; i++) {
      this.isFunction[8]![i] = true;
      this.isFunction[i]![8] = true;
    }
  }

  private generateDataCodewords(): number[] {
    const maxData = VERSION_SPECS[`${this.version}${this.ecLevel}`]![1];
    const dataLen = this.rawData.length;
    let bitBuf = 0;
    let bitLen = 0;
    const out: number[] = [];
    const push = (value: number, count: number) => {
      bitBuf = ((bitBuf << count) | value) >>> 0;
      bitLen += count;
      while (bitLen >= 8) {
        bitLen -= 8;
        out.push((bitBuf >>> bitLen) & 0xff);
      }
      bitBuf &= (1 << bitLen) - 1;
    };
    push(0b0100, 4); // byte mode
    push(dataLen, 8); // character count
    for (const b of this.rawData) push(b, 8);
    const terminator = Math.min(4, maxData * 8 - (out.length * 8 + bitLen)); // terminator up to 4 bits
    if (terminator > 0) push(0, terminator);
    if (bitLen > 0) push(0, 8 - bitLen); // pad to byte boundary
    const pads = [0xec, 0x11];
    let padIdx = 0;
    while (out.length < maxData) {
      out.push(pads[padIdx] as number);
      padIdx ^= 1;
    }
    return out;
  }

  private placeDataBits(bits: number[]): void {
    let bitIdx = 0;
    let row = this.size - 1;
    let col = this.size - 1;
    let dirUp = true;
    while (col > 0) {
      if (col === 6) col -= 1;
      for (let off = 0; off < 2; off++) {
        const c = col - off;
        if (!this.isFunction[row]![c]) {
          if (bitIdx < bits.length) {
            this.modules[row]![c] = Boolean(bits[bitIdx]);
            bitIdx++;
          } else {
            this.modules[row]![c] = false;
          }
        }
      }
      if (dirUp) {
        if (row === 0) {
          dirUp = false;
          col -= 2;
        } else row -= 1;
      } else if (row === this.size - 1) {
        dirUp = true;
        col -= 2;
      } else row += 1;
    }
  }

  private static maskCondition(mask: number, r: number, c: number): boolean {
    switch (mask) {
      case 0: return (r + c) % 2 === 0;
      case 1: return r % 2 === 0;
      case 2: return c % 3 === 0;
      case 3: return (r + c) % 3 === 0;
      case 4: return (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0;
      case 5: return ((r * c) % 2) + ((r * c) % 3) === 0;
      case 6: return (((r * c) % 2) + ((r * c) % 3)) % 2 === 0;
      case 7: return (((r * c) % 3) + ((r + c) % 2)) % 2 === 0;
      default: return false;
    }
  }

  private applyMask(mask: number): void {
    for (let r = 0; r < this.size; r++) {
      for (let c = 0; c < this.size; c++) {
        if (!this.isFunction[r]![c] && QRCode.maskCondition(mask, r, c)) this.modules[r]![c] = !this.modules[r]![c];
      }
    }
  }

  private penaltyScore(): number {
    const size = this.size;
    const m = this.modules;
    let penalty = 0;
    // Feature 1: runs of 5+ consecutive same-coloured modules
    const runs = (get: (i: number, j: number) => boolean) => {
      for (let i = 0; i < size; i++) {
        let run = 0;
        let prev: boolean | null = null;
        for (let j = 0; j < size; j++) {
          const v = get(i, j);
          if (v === prev) run += 1;
          else {
            if (run >= 5) penalty += 3 + (run - 5);
            run = 1;
            prev = v;
          }
        }
        if (run >= 5) penalty += 3 + (run - 5);
      }
    };
    runs((r, c) => m[r]![c] as boolean);
    runs((c, r) => m[r]![c] as boolean);
    // Feature 2: 2x2 blocks of one colour
    for (let r = 0; r < size - 1; r++) {
      for (let c = 0; c < size - 1; c++) {
        const v = m[r]![c];
        if (v === m[r]![c + 1] && v === m[r + 1]![c] && v === m[r + 1]![c + 1]) penalty += 3;
      }
    }
    // Feature 3: finder-like patterns 1:1:3:1:1
    const pat1 = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0];
    const pat2 = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1];
    const matches = (get: (k: number) => boolean) => {
      let a = true;
      let b = true;
      for (let k = 0; k < 11; k++) {
        const v = get(k) ? 1 : 0;
        if (v !== pat1[k]) a = false;
        if (v !== pat2[k]) b = false;
      }
      return a || b;
    };
    for (let r = 0; r < size; r++) for (let c = 0; c < size - 10; c++) if (matches((k) => m[r]![c + k] as boolean)) penalty += 40;
    for (let c = 0; c < size; c++) for (let r = 0; r < size - 10; r++) if (matches((k) => m[r + k]![c] as boolean)) penalty += 40;
    // Feature 4: proportion of dark modules
    let dark = 0;
    for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) if (m[r]![c]) dark++;
    const ratio = Math.floor((dark * 100) / (size * size));
    penalty += Math.floor(Math.abs(ratio - 50) / 5) * 10;
    return penalty;
  }

  private selectBestMask(): number {
    let bestMask = 0;
    let bestScore = Infinity;
    const orig = this.modules.map((row) => row.slice());
    for (let mask = 0; mask < 8; mask++) {
      this.modules = orig.map((row) => row.slice());
      this.applyMask(mask);
      this.placeFormatInfo(mask);
      const score = this.penaltyScore();
      if (score < bestScore) {
        bestScore = score;
        bestMask = mask;
      }
    }
    this.modules = orig.map((row) => row.slice());
    this.applyMask(bestMask);
    this.placeFormatInfo(bestMask);
    return bestMask;
  }

  /** Places the 15 format bits in the exact ISO/IEC 18004 sequence. */
  private placeFormatInfo(mask: number): void {
    const fmt = FORMAT_INFO[`${this.ecLevel}${mask}`] ?? 0x77c4;
    const n = this.size;
    const topLeft: [number, number][] = [[8, 0], [8, 1], [8, 2], [8, 3], [8, 4], [8, 5], [8, 7], [8, 8], [7, 8], [5, 8], [4, 8], [3, 8], [2, 8], [1, 8], [0, 8]];
    const split: [number, number][] = [
      [n - 1, 8], [n - 2, 8], [n - 3, 8], [n - 4, 8], [n - 5, 8], [n - 6, 8], [n - 7, 8],
      [8, n - 8], [8, n - 7], [8, n - 6], [8, n - 5], [8, n - 4], [8, n - 3], [8, n - 2], [8, n - 1],
    ];
    for (let i = 0; i < 15; i++) {
      const bit = Boolean((fmt >> (14 - i)) & 1);
      const [r1, c1] = topLeft[i]!;
      this.modules[r1]![c1] = bit;
      const [r2, c2] = split[i]!;
      this.modules[r2]![c2] = bit;
    }
  }

  /** Standard SVG with the mandatory 4-module quiet zone for phone cameras. */
  toSvg(boxSize = 12, border = 4, fill = "#000000", bg = "#ffffff"): string {
    const dim = (this.size + border * 2) * boxSize;
    const path: string[] = [];
    for (let r = 0; r < this.size; r++) {
      for (let c = 0; c < this.size; c++) {
        if (this.modules[r]![c]) path.push(`M${(c + border) * boxSize},${(r + border) * boxSize}h${boxSize}v${boxSize}h-${boxSize}z`);
      }
    }
    return (
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${dim} ${dim}" width="${dim}" height="${dim}" shape-rendering="crispEdges">\n` +
      `  <rect width="100%" height="100%" fill="${bg}"/>\n` +
      `  <path d="${path.join(" ")}" fill="${fill}"/>\n` +
      `</svg>`
    );
  }
}

/** Detective hat + glasses (the homepage's liars.svg), 24x24 stroke icon. */
export const LOGO_24 = '<path d="M3 10h18"/><path d="M6 10l2-6h8l2 6"/><circle cx="8" cy="15" r="3"/><circle cx="16" cy="15" r="3"/><path d="M11 15h2"/>';

export interface QrOptions {
  boxSize?: number;
  border?: number;
  fill?: string;
  /** "" leaves the background transparent. */
  bg?: string;
  /** 24x24 stroke-icon markup drawn in a cleared centre square (needs the `qrcode` package: level H). */
  logo?: string;
}

type Create = (text: string, opts: { errorCorrectionLevel: "M" | "H" }) => QrcodeCode;
let packageCreate: Create | null | undefined;

async function loadPackage(): Promise<Create | null> {
  if (packageCreate !== undefined) return packageCreate;
  try {
    const mod = (await import("qrcode")) as unknown as { default?: { create?: Create }; create?: Create };
    packageCreate = mod.default?.create ?? mod.create ?? null;
  } catch {
    packageCreate = null;
  }
  return packageCreate;
}

/** Warm the optional encoder so the first /api/qr.svg request is synchronous. */
export const ready: Promise<void> = loadPackage().then(() => undefined);

/**
 * Generates a standard-compliant QR Code SVG. Uses the `qrcode` package when available with error
 * correction M (~15% redundancy) for reliable scanning on iPhone and Android cameras. A `logo` is
 * drawn in a cleared centre square; that switches to level H (~30%) so the hidden modules are
 * recoverable. The pure fallback encoder is level M only, so the logo is dropped there.
 */
export function generateQrSvg(content: string, opts: QrOptions = {}): string {
  const boxSize = opts.boxSize ?? 12;
  const border = opts.border ?? 4;
  const fill = opts.fill ?? "#000000";
  const bg = opts.bg ?? "#ffffff";
  let logo = opts.logo ?? "";

  let matrix: (r: number, c: number) => boolean;
  let size: number;
  const create = packageCreate ?? null;
  if (create) {
    const code = create(content, { errorCorrectionLevel: logo ? "H" : "M" });
    size = code.modules.size;
    const data = code.modules.data as Uint8Array;
    matrix = (r, c) => Boolean(data[r * size + c]);
  } else {
    const qr = new QRCode(content, "M");
    size = qr.size;
    matrix = (r, c) => qr.modules[r]![c] as boolean;
    logo = ""; // fallback encoder is level M only: not enough redundancy to cover modules
  }

  let hole: [number, number] = [0, 0];
  if (logo) {
    const n = Math.floor(size * 0.26) | 1; // odd, so it centres on a module (~7% of modules hidden)
    const lo = Math.floor((size - n) / 2);
    hole = [lo, lo + n];
  }
  const inHole = (i: number) => i >= hole[0] && i < hole[1];
  const dim = (size + border * 2) * boxSize;
  const path: string[] = [];
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (matrix(r, c) && !(inHole(r) && inHole(c))) path.push(`M${(c + border) * boxSize},${(r + border) * boxSize}h${boxSize}v${boxSize}h-${boxSize}z`);
    }
  }
  let mark = "";
  if (logo) {
    const side = (hole[1] - hole[0] - 1) * boxSize; // half a module of clearance on each side
    const at = (hole[0] + border) * boxSize + boxSize / 2;
    mark = `  <g transform="translate(${at},${at}) scale(${side / 24})" fill="none" stroke="${fill}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" shape-rendering="geometricPrecision">${logo}</g>\n`;
  }
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${dim} ${dim}" width="${dim}" height="${dim}" shape-rendering="crispEdges">\n` +
    (bg ? `  <rect width="100%" height="100%" fill="${bg}"/>\n` : "") +
    `  <path d="${path.join(" ")}" fill="${fill}"/>\n` +
    mark +
    `</svg>`
  );
}
