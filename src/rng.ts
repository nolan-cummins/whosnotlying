/**
 * Randomness for the engine, behind one seam so tests can make a run deterministic
 * (the fairness test seeds it, like `random.seed(7)` did in the Python version).
 */
export interface Rng {
  random(): number;
}

/** Small, fast, seedable PRNG (mulberry32). Good enough for shuffles and weighted picks. */
export function mulberry32(seed: number): Rng {
  let a = seed >>> 0;
  return {
    random() {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    },
  };
}

export const systemRng: Rng = { random: () => Math.random() };

let current: Rng = systemRng;

/** `seed(n)` makes every pick reproducible; `seed()` goes back to Math.random. */
export function seed(n?: number): void {
  current = n === undefined ? systemRng : mulberry32(n);
}

export const rng: Rng = { random: () => current.random() };

export function random(): number {
  return current.random();
}

export function choice<T>(xs: readonly T[], r: Rng = rng): T {
  if (!xs.length) throw new Error("choice from an empty list");
  return xs[Math.floor(r.random() * xs.length)] as T;
}

/** In place, like Python's random.shuffle. */
export function shuffle<T>(xs: T[], r: Rng = rng): T[] {
  for (let i = xs.length - 1; i > 0; i--) {
    const j = Math.floor(r.random() * (i + 1));
    [xs[i], xs[j]] = [xs[j] as T, xs[i] as T];
  }
  return xs;
}

/** One weighted pick, like random.choices(xs, weights)[0]. */
export function weightedChoice<T>(xs: readonly T[], weights: readonly number[], r: Rng = rng): T {
  const total = weights.reduce((a, b) => a + b, 0);
  if (!xs.length || !(total > 0)) return choice(xs, r);
  let x = r.random() * total;
  for (let i = 0; i < xs.length; i++) {
    x -= weights[i] as number;
    if (x <= 0) return xs[i] as T;
  }
  return xs[xs.length - 1] as T;
}

export function randint(lo: number, hi: number, r: Rng = rng): number {
  return lo + Math.floor(r.random() * (hi - lo + 1));
}
