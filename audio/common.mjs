// ANCHOR score: shared musical helpers (theme, phrases, harp, ostinati, brass chords, orchestral hits) and the cue
// sheet that audio/score.mjs writes to audio/cues.md.
import { A, M, strings, spic, line, piano, timp, taiko, bassDrum, tamtam } from './lib.mjs';

export const CUES = [];
/** The score's buses (silenced together by gaps); the effects live on 'sfx', 'foley', 'amb'. */
export const MUSIC = ['str', 'solo', 'brass', 'choir', 'keys', 'perc', 'low'];
/** Log a sync point (seconds) for audio/cues.md. kind: 'HIT' (hard sync), 'sfx', 'music'. */
export const cue = (t, kind, what) => CUES.push([t, kind, what]);

/** Piecewise-linear curve through [[t, v], ...] (held flat outside). */
export const curve = (pts) => (t) => {
  if (t <= pts[0][0]) return pts[0][1];
  for (let i = 1; i < pts.length; i++) if (t <= pts[i][0]) { const [a, va] = pts[i - 1]; const [b, vb] = pts[i]; return va + ((vb - va) * (t - a)) / Math.max(1e-9, b - a); }
  return pts[pts.length - 1][1];
};

// The theme in quarter notes: phrase A rises and asks (half cadence), phrase B answers (full cadence).
export const THEME_A = [['F#4', 1], ['A4', 1], ['D5', 2], ['C#5', 1.5], ['B4', 0.5], ['A4', 2], ['G4', 1], ['B4', 1], ['E5', 1.5], ['D5', 0.5], ['C#5', 4]];
export const THEME_B = [['F#4', 1], ['A4', 1], ['D5', 2], ['E5', 1.5], ['F#5', 0.5], ['G5', 2], ['F#5', 1], ['E5', 1], ['D5', 1], ['C#5', 1], ['D5', 4]];

/** [[name, quarters], ...] from t0, q seconds a quarter → a line() list. tr: semitones; v: loudness or fn(i); last: length of the last note (s). */
export function phrase(t0, q, notes, { tr = 0, v = 0.8, slur = 0.03, last } = {}) {
  let t = t0; const out = [];
  notes.forEach(([n, len], i) => {
    const d = len * q;
    out.push({ t, d: i === notes.length - 1 && last ? last : d + slur, n: M(n) + tr, v: typeof v === 'function' ? v(i) : v });
    t += d;
  });
  return out;
}
/** [[t, d, note, v], ...] → a line() list. */
export const notes = (rows) => rows.map(([t, d, n, v = 0.8]) => ({ t, d, n, v }));

/** Harp notes `step` s apart from t0. */
export function harp(t0, step, ns, { vel = 0.4, dur = 1.8, pan = -0.35, bright = 0.55, verb = 0.4 } = {}) {
  ns.forEach((n, i) => { if (n != null) A.pluck(t0 + i * step, n, { type: 'harp', dur, vel: typeof vel === 'function' ? vel(i) : vel, pan, bright, bus: 'keys', verb }); });
}
/** Harp glissando through a scale from a to b over [t0, t1]. */
export function gliss(t0, t1, a, b, { key = 'D', mode = 'major', vel = 0.35, pan = -0.35 } = {}) {
  const sc = A.scale(key, mode); const lo = Math.min(M(a), M(b)); const hi = Math.max(M(a), M(b)); const ns = [];
  for (let m = lo; m <= hi; m++) if (sc.steps.includes((((m - sc.root) % 12) + 12) % 12)) ns.push(m);
  if (M(a) > M(b)) ns.reverse();
  const step = (t1 - t0) / ns.length;
  ns.forEach((m, i) => A.pluck(t0 + i * step, m, { type: 'harp', dur: 1.3, vel: vel * (0.85 + 0.15 * Math.sin(i * 1.7)), pan, bright: 0.6, bus: 'keys', verb: 0.45 }));
}
/** Arpeggio: chord tones cycled by `pattern` (indices into the chord) every `step` s over [t0, t1]; voice 'harp' | 'piano'. */
export function arpeggio(t0, t1, step, chord, { pattern = [0, 1, 2, 3, 4, 3, 2, 1], voice = 'harp', vel = 0.35, pan = -0.3, dur = 1.6 } = {}) {
  const cs = chord.map(M);
  for (let i = 0, t = t0; t < t1 - 1e-6; i++, t = t0 + i * step) {
    const n = cs[pattern[i % pattern.length] % cs.length]; const v = (typeof vel === 'function' ? vel(i, t) : vel) * (i % 4 === 0 ? 1 : 0.82);
    if (voice === 'piano') piano(t, n, { vel: v, dur: step * 1.6 });
    else A.pluck(t, n, { type: 'harp', dur, vel: v, pan, bright: 0.5, bus: 'keys', verb: 0.4 });
  }
}

/** Ostinato of short string notes over [t0, t1] every `step` s: nf(i, t) → note or null; vf(i, t) → loudness. */
export function ostinato(t0, t1, step, nf, { vf = () => 0.5, dur, bright = 0.5, sub = 0.6, pan = 0, verb = 0.2 } = {}) {
  for (let i = 0, t = t0; t < t1 - 1e-6; i++, t = t0 + i * step) {
    const n = nf(i, t); if (n == null) continue;
    spic(t, n, { dur: dur ?? step * 0.9, vel: vf(i, t), bright, sub, pan, bus: 'str', verb });
  }
}

/** Sustained brass chord: horns below C4, trumpets above, each a legato line; o.dyn(T) shapes swells. */
export function brassChord(t, dur, ns, o = {}) {
  const ms = ns.map(M);
  ms.forEach((n, i) => line([{ t, d: dur, n, v: o.v ?? 0.8 }], { type: n >= 60 ? 'brass' : 'horn', bus: 'brass', vel: (o.vel ?? 0.4) / Math.sqrt(ms.length),
    pan: ms.length > 1 ? (i / (ms.length - 1) - 0.5) * 0.6 : 0, dyn: o.dyn, att: o.att, rel: o.rel ?? 0.35, verb: o.verb ?? 0.35 }));
}

/** Strings swelling from a → b (0..1.3) over the note. */
export const swellStr = (t, dur, ns, a, b, o = {}) => strings(t, dur, ns, { ...o, dyn: (u) => a + (b - a) * Math.pow(u, o.pow ?? 1.4) });

/** Orchestral hit: brass + strings stab, timpani, gran cassa, cymbal, taiko (optional tam-tam). */
export function tutti(t, ns, { vel = 1, tn, cym = 0.5, tam = 0, tk = 0.7, len = 0.45, strVel = 0.7, brassVel = 0.7, rel = 0.6 } = {}) {
  const ms = ns.map(M);
  brassChord(t, len, ms, { vel: brassVel * vel, v: 1.15, att: 0.02, rel: 0.3 });
  strings(t, len, ms, { att: 0.012, rel, bright: 0.9, vel: strVel * vel, voices: 3, verb: 0.4 });
  let tp = tn != null ? M(tn) : ms[0]; while (tp > 50) tp -= 12; while (tp < 38) tp += 12;
  timp(t, tp, 1.0 * vel);
  bassDrum(t, { vel: 1.1 * vel });
  if (tk) taiko(t, { vel: tk * vel, f: 58 });
  if (cym) A.crash(t, { vel: cym * vel, bus: 'perc', dur: 2.8, verb: 0.35 });
  if (tam) tamtam(t, { vel: tam * vel, dur: 5 });
}
