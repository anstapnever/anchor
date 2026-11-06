// ANCHOR score: the orchestra. String sections, spiccato, legato solo lines (flute, horn, brass, cello, violin),
// a wordless choir-like pad, piano, glockenspiel, timpani, taiko, gran cassa, tam-tam, built on the nap synth core
// (offline, 48 kHz, deterministic). Every voice writes into a named bus through A.writer; the mixer is A.render.
import * as A from './synth/index.mjs';

export { A };
const { SR, TAU, writer, at, noise, rand, svf, saw, clamp, panLR, drive } = A;
export const M = (n) => (typeof n === 'number' ? n : A.note(n));
export const F = (n) => A.mtof(M(n));
const SEMI = Math.LN2 / 12;
const smooth = (x) => x * x * (3 - 2 * x);
const relEnv = (x) => (x <= 0 ? 1 : x >= 1 ? 0 : Math.exp(-3 * x) * (1 - x));

/** Smooth random wobble in [-1, 1] (three slow sines with random rates and phases). */
export function wob(rate = 0.2) {
  const p = [rand(), rand(), rand()];
  const f = [rate * (0.6 + 0.5 * rand()), rate * (1.4 + rand()), rate * (2.6 + rand())];
  return (t) => 0.5 * Math.sin(TAU * (f[0] * t + p[0])) + 0.3 * Math.sin(TAU * (f[1] * t + p[1])) + 0.2 * Math.sin(TAU * (f[2] * t + p[2]));
}

/**
 * String section chord: per note `voices` detuned saws, each with its own drift and vibrato, a dynamic low-pass and a
 * little bite at 2.4 kHz. o: vel, att, rel, bus ('str'), verb, pan, spread, width, detune, voices, bright (0..1),
 * dyn(u) (u = 0..1 across the note → loudness, shapes crescendi), trem (bow strokes per second), vib (semitones),
 * bend(s) (semitones, glissandi).
 */
export function strings(t, dur, notes, o = {}) {
  const ns = notes.map(M); const nv = o.voices ?? 4; const att = o.att ?? 0.3; const rel = o.rel ?? 0.7;
  const w = writer(o.bus || 'str', { verb: o.verb ?? 0.35, gain: o.vel ?? 0.5 });
  const vs = [];
  ns.forEach((m, ni) => {
    const np = ns.length > 1 ? (ni / (ns.length - 1) - 0.5) * (o.spread ?? 0.8) : 0;
    for (let j = 0; j < nv; j++) {
      const x = nv > 1 ? (j / (nv - 1)) * 2 - 1 : 0;
      vs.push({ o: saw(), f: A.mtof(m), det: x * (o.detune ?? 0.1) + (rand() - 0.5) * 0.03, vr: 4.8 + rand() * 1.4, vp: rand() * TAU,
        dr: wob(0.25), tp: rand(), r: 1, a: 1, p: panLR(clamp((o.pan ?? 0) + np + x * (o.width ?? 0.35), -1, 1)) });
    }
  });
  const fl = svf(); const fr = svf(); const hl = svf(); const hr = svf();
  const el = A.biquad('peak', 2400, 2, 0.8); const er = A.biquad('peak', 2400, 2, 0.8);
  const hpF = Math.max(28, A.mtof(Math.min(...ns)) * 0.55);
  const norm = 0.55 / Math.sqrt(vs.length);
  const i0 = at(t); const n = Math.floor((dur + rel) * SR);
  const bright = o.bright ?? 0.5; const vib = o.vib ?? 0.09; const trem = o.trem ?? 0;
  let d = 1; let cut = 2000;
  for (let k = 0; k < n; k++) {
    const s = k / SR;
    if ((k & 31) === 0) {
      d = o.dyn ? o.dyn(clamp(s / dur)) : 1;
      const va = vib * clamp((s - 0.2) / 0.5); const bs = o.bend ? o.bend(s) : 0;
      for (const v of vs) {
        v.r = Math.exp((v.det + v.dr(t + s) * 0.04 + va * Math.sin(TAU * v.vr * s + v.vp) + bs) * SEMI);
        if (trem) v.a = 0.3 + 0.7 * Math.abs(Math.sin(Math.PI * (trem * s + v.tp)));
      }
      cut = 700 + 6000 * bright * (0.35 + 0.65 * Math.min(1.2, d));
    }
    const env = (s < att ? Math.sin((s / att) * Math.PI / 2) : 1) * relEnv((s - dur) / rel);
    let l = 0; let r = 0;
    for (const v of vs) { const x = v.o(v.f * v.r) * v.a; l += x * v.p[0]; r += x * v.p[1]; }
    const g = env * d * norm;
    w(i0 + k, el(hl(fl(l, cut, 0.6).lp, hpF, 0.7).hp) * g, er(hr(fr(r, cut, 0.6).lp, hpF, 0.7).hp) * g);
  }
}

/** Short bowed note (spiccato / marcato) for ostinati. o: dur (0.16), vel, bus ('str'), pan, bright, sub (octave-below sine 0..1), verb. */
export function spic(t, n, o = {}) {
  const f = F(n); const dur = o.dur ?? 0.16;
  const w = writer(o.bus || 'str', { pan: o.pan ?? 0, verb: o.verb ?? 0.25, gain: o.vel ?? 0.5 });
  const os = [saw(), saw(), saw()]; const fl = svf(); const nb = svf(); const sub = A.sine();
  const i0 = at(t); const len = Math.floor((dur + 0.15) * SR); const br = o.bright ?? 0.5; const sb = o.sub ?? 0;
  for (let k = 0; k < len; k++) {
    const s = k / SR;
    const env = (s < 0.006 ? s / 0.006 : 1) * Math.exp(-s / (dur * 1.1)) * (s < dur ? 1 : Math.exp(-(s - dur) / 0.035));
    const x = (os[0](f * 1.004) + os[1](f * 0.996) + os[2](f)) / 3;
    const c = 400 + f * 2 + (1000 + 5000 * br) * Math.exp(-s / 0.07);
    const chiff = nb(noise(), 2400, 0.8).bp * Math.exp(-s / 0.008) * 0.25;
    w(i0 + k, (fl(x, c, 0.8).lp + sub(f / 2) * sb * 0.6 + chiff) * env);
  }
}

const LINE = {
  flute: { att: 0.05, rel: 0.2, vib: 0.1, vr: 5.0, glide: 0.05, uni: 1 },
  horn: { att: 0.07, rel: 0.3, vib: 0.05, vr: 4.8, glide: 0.07, uni: 2 },
  brass: { att: 0.03, rel: 0.22, vib: 0.06, vr: 5.2, glide: 0.05, uni: 3 },
  cello: { att: 0.09, rel: 0.35, vib: 0.16, vr: 5.4, glide: 0.09, uni: 2 },
  violin: { att: 0.07, rel: 0.3, vib: 0.14, vr: 5.8, glide: 0.07, uni: 3 },
};
/**
 * Legato monophonic line (a solo, or a section in unison). list: [{ t, d, n, v }] (v loudness 0..1.2): overlapping or
 * touching notes slur with a glide, separated notes re-attack. o.type: flute | horn | brass | cello | violin; vel, bus
 * ('solo'), pan, verb, delay, glide, att, rel, vib (semitones), detune, uni (unison voices), dyn(T) (loudness
 * multiplier over absolute time: swells and fades).
 */
export function line(list, o = {}) {
  const type = o.type || 'horn'; const P = LINE[type];
  const ns = list.map((x) => ({ t: x.t, d: x.d, f: F(x.n), v: x.v ?? 0.8 })).sort((a, z) => a.t - z.t);
  const att = o.att ?? P.att; const rel = o.rel ?? P.rel; const glide = o.glide ?? P.glide; const vibD = o.vib ?? P.vib;
  const w = writer(o.bus || 'solo', { pan: o.pan ?? 0, verb: o.verb ?? 0.35, delay: o.delay, gain: o.vel ?? 0.5 });
  const uni = o.uni ?? P.uni;
  const os = Array.from({ length: uni }, (_, j) => ({ o: saw(), d: uni > 1 ? Math.exp(((j / (uni - 1)) * 2 - 1) * (o.detune ?? 0.07) * SEMI) : 1 }));
  const s1 = A.sine(); const s2 = A.sine(); const s3 = A.sine();
  const lp = svf(); const bn = svf(); const hn = svf(); const dc = A.dcBlock();
  const T0 = ns[0].t; const last = ns[ns.length - 1];
  const n = Math.floor((last.t + last.d + rel * 1.5 + 0.05 - T0) * SR); const i0 = at(T0);
  const aA = Math.exp(-1 / (att * SR)); const aR = Math.exp(-1 / ((rel / 3) * SR));
  let idx = 0; let fFrom = ns[0].f; let fNow = ns[0].f; let amp = 0; let legato = false; let start = T0;
  for (let k = 0; k < n; k++) {
    const T = T0 + k / SR;
    while (idx + 1 < ns.length && ns[idx + 1].t <= T) {
      const p = ns[idx]; idx++; legato = p.t + p.d >= ns[idx].t - 0.02 && amp > 0.05; fFrom = fNow; start = ns[idx].t;
    }
    const nt = ns[idx]; const s = T - start;
    const vib = vibD * clamp((s - 0.18) / 0.35) * Math.sin(TAU * P.vr * T);
    const scoop = legato ? 0 : -0.3 * Math.exp(-s / 0.04);
    fNow = legato ? fFrom * Math.pow(nt.f / fFrom, smooth(clamp(s / glide))) : nt.f;
    const f = fNow * Math.exp((vib + scoop) * SEMI);
    const tgt = (T < nt.t + nt.d ? nt.v : 0) * (o.dyn ? o.dyn(T) : 1);
    amp = tgt > amp ? tgt + (amp - tgt) * aA : tgt + (amp - tgt) * aR;
    const acc = 1 + 0.35 * Math.exp(-s / 0.07) * (legato ? 0.4 : 1);
    let x;
    if (type === 'flute') {
      const dy = Math.min(1, amp);
      x = s1(f) + (0.1 + 0.25 * dy) * s2(f * 2) + (0.03 + 0.1 * dy) * s3(f * 3);
      x += bn(noise(), f * 2, 1.2).bp * (0.12 + 0.3 * Math.exp(-s / 0.05) * (legato ? 0.3 : 1)) + hn(noise(), 7000, 0.7).hp * 0.02;
      x *= 0.92 + 0.08 * Math.sin(TAU * P.vr * T + 1);
    } else {
      let sw = 0; for (const v of os) sw += v.o(f * v.d); sw /= Math.sqrt(uni);
      const dy = Math.min(1.2, amp) * acc;
      if (type === 'horn') x = drive(lp(sw, clamp(f * (1.6 + 3.2 * dy), 250, 2600), 0.7).lp + s1(f) * 0.35, 1.4);
      else if (type === 'brass') x = drive(lp(sw, clamp(f * (2.5 + 7 * dy), 400, 7000), 0.9).lp, 1.9);
      else x = lp(sw, clamp(f * (4 + 5 * dy), 600, 6500), 0.6).lp + bn(noise(), 3000, 0.7).bp * 0.015;
    }
    w(i0 + k, dc(x) * amp);
  }
}

const VOW = {
  a: [[800, 1], [1150, 0.45], [2800, 0.2], [3500, 0.1]], o: [[450, 1], [800, 0.4], [2830, 0.1], [3500, 0.05]],
  u: [[325, 1], [700, 0.25], [2530, 0.05], [3500, 0.02]], e: [[400, 1], [1600, 0.35], [2700, 0.2], [3300, 0.1]],
};
/** Wordless choir-like pad ('ah' / 'oo' formants on detuned saws, no words). o: vowel, toVowel, vel, bus ('choir'), att, rel, dyn(u), voices, verb, breath. */
export function choir(t, dur, notes, o = {}) {
  const ns = notes.map(M); const nv = o.voices ?? 4; const att = o.att ?? 0.8; const rel = o.rel ?? 1.2;
  const w = writer(o.bus || 'choir', { verb: o.verb ?? 0.55, gain: o.vel ?? 0.5 });
  const vs = [];
  ns.forEach((m, ni) => {
    for (let j = 0; j < nv; j++) {
      const x = nv > 1 ? (j / (nv - 1)) * 2 - 1 : 0;
      vs.push({ o: saw(), f: A.mtof(m), det: x * 0.12 + (rand() - 0.5) * 0.05, vr: 4.6 + rand() * 1.2, vp: rand() * TAU, dr: wob(0.3), r: 1,
        p: panLR(clamp(x * 0.7 + (ni % 2 ? 0.15 : -0.15), -1, 1)) });
    }
  });
  const A0 = VOW[o.vowel || 'a']; const Z0 = VOW[o.toVowel || o.vowel || 'a'];
  const fL = A0.map(() => svf()); const fR = A0.map(() => svf()); const pl = svf(); const pr = svf();
  const norm = 0.6 / Math.sqrt(vs.length); const i0 = at(t); const n = Math.floor((dur + rel) * SR);
  let d = 1; let fm = A0.map((x) => x[0]); let gm = A0.map((x) => x[1]);
  for (let k = 0; k < n; k++) {
    const s = k / SR;
    if ((k & 31) === 0) {
      const u = clamp(s / dur); d = o.dyn ? o.dyn(u) : 1;
      for (const v of vs) v.r = Math.exp((v.det + v.dr(t + s) * 0.05 + 0.1 * clamp((s - 0.3) / 0.6) * Math.sin(TAU * v.vr * s + v.vp)) * SEMI);
      fm = A0.map((x, j) => x[0] + (Z0[j][0] - x[0]) * u); gm = A0.map((x, j) => x[1] + (Z0[j][1] - x[1]) * u);
    }
    const env = (s < att ? Math.sin((s / att) * Math.PI / 2) : 1) * relEnv((s - dur) / rel);
    let l = 0; let r = 0;
    for (const v of vs) { const x = v.o(v.f * v.r); l += x * v.p[0]; r += x * v.p[1]; }
    const br = noise() * (o.breath ?? 0.06);
    l = pl(l, 3600, 0.5).lp + br; r = pr(r, 3600, 0.5).lp + br;
    let yl = 0; let yr = 0;
    for (let j = 0; j < fL.length; j++) { yl += fL[j](l, fm[j], 6).bp * gm[j] * 0.5; yr += fR[j](r, fm[j], 6).bp * gm[j] * 0.5; }
    const g = env * d * norm;
    w(i0 + k, yl * g, yr * g);
  }
}

/** Piano note: stretched partials on two slightly detuned strings, hammer thump, damper at o.dur. o: vel, dur, bus ('keys'), pan, verb. */
export function piano(t, n, o = {}) {
  const m = M(n); const f = A.mtof(m); const vel = o.vel ?? 0.6; const dur = o.dur ?? 1.5;
  const w = writer(o.bus || 'keys', { pan: o.pan ?? clamp((m - 62) / 30, -0.6, 0.6), verb: o.verb ?? 0.35, gain: vel });
  const t1 = clamp(7 * Math.pow(2, -(m - 45) / 14), 0.6, 9);
  const H = Math.max(2, Math.min(10, Math.floor(12000 / f)));
  const ps = [];
  for (let h = 1; h <= H; h++) for (const dt of [-1, 1]) {
    const wk = (TAU * f * h * Math.sqrt(1 + 0.00035 * h * h) * (1 + dt * 0.0004)) / SR;
    const tau = (t1 / (1 + 0.7 * (h - 1))) * (dt > 0 ? 1 : 0.55); const ph = rand() * TAU;
    ps.push({ c: Math.cos(wk), s: Math.sin(wk), x: Math.cos(ph), y: Math.sin(ph), a: Math.pow(h, -(1.6 - 0.6 * Math.min(1, vel))) * 0.5, d: Math.exp(-1 / (tau * SR)) });
  }
  const norm = 0.55; const hn = svf(); const i0 = at(t); const n1 = Math.floor((dur + 0.5) * SR); const damp = Math.exp(-1 / (0.1 * SR));
  let dg = 1;
  for (let k = 0; k < n1; k++) {
    const s = k / SR; let v = 0;
    for (const p of ps) { const x = p.x * p.c - p.y * p.s; p.y = p.x * p.s + p.y * p.c; p.x = x; p.a *= p.d; v += p.y * p.a; }
    if (s > dur) dg *= damp;
    const ham = hn(noise(), 1500 + 2500 * vel, 0.7).lp * Math.exp(-s / 0.005) * 0.2;
    w(i0 + k, (v * norm + ham) * dg * (k < 48 ? k / 48 : 1) * (k > n1 - 480 ? (n1 - k) / 480 : 1));
  }
}

/**
 * Modal resonator bank (two-pole resonators, a slightly detuned copy per channel) struck by hits [{ t, v, w }] (w =
 * mallet width in s: short = hard and bright). modes [[Hz, amp, tau]]. o: mallet, noisy, len (s after the last hit),
 * bus, pan, verb, vel, spread. The base of timpani, bells, chimes, chains, plates, containers, tiles.
 */
export function modal(hits, modes, o = {}) {
  const hs = (Array.isArray(hits) ? hits : [hits]).map((h) => (typeof h === 'number' ? { t: h, v: 1 } : h)).sort((a, z) => a.t - z.t);
  const T0 = hs[0].t; const len = o.len ?? Math.min(12, Math.max(...modes.map((m) => m[2])) * 5);
  const n = Math.floor((hs[hs.length - 1].t - T0 + len) * SR); const i0 = at(T0);
  const exc = new Float64Array(n);
  for (const h of hs) {
    const mw = Math.max(1, Math.floor((h.w ?? o.mallet ?? 0.002) * SR)); const j0 = Math.floor((h.t - T0) * SR); const g = (h.v * Math.PI) / (2 * mw);
    for (let j = 0; j < mw && j0 + j < n; j++) exc[j0 + j] += g * Math.sin((Math.PI * (j + 0.5)) / mw) * (o.noisy ? noise() * 1.6 : 1);
  }
  const sp = o.spread ?? 0.0015;
  const mk = (fq, a, tau) => { const wk = (TAU * fq) / SR; const r = Math.exp(-1 / (tau * SR)); return { b1: 2 * r * Math.cos(wk), b2: r * r, g: a * Math.sin(wk), y1: 0, y2: 0 }; };
  const rs = modes.filter((m) => m[0] > 15 && m[0] < SR * 0.45).map(([fq, a, tau]) => [mk(fq * (1 - sp * rand()), a, tau), mk(fq * (1 + sp * rand()), a, tau)]);
  const w = writer(o.bus || 'perc', { pan: o.pan ?? 0, verb: o.verb ?? 0.3, gain: o.vel ?? 1 });
  const fade = Math.floor(0.05 * SR);
  for (let k = 0; k < n; k++) {
    const x = exc[k]; let l = 0; let r = 0;
    for (const [a, b] of rs) {
      const ya = a.b1 * a.y1 - a.b2 * a.y2 + x * a.g; a.y2 = a.y1; a.y1 = ya; l += ya;
      const yb = b.b1 * b.y1 - b.b2 * b.y2 + x * b.g; b.y2 = b.y1; b.y1 = yb; r += yb;
    }
    const e = k > n - fade ? (n - k) / fade : 1;
    w(i0 + k, l * e, r * e);
  }
}

/** Glockenspiel (soft 0) … celesta (soft 1): free-bar modes. o: vel, dur, bus ('keys'), pan, verb, soft. */
export function glock(t, n, o = {}) {
  const f = F(n); const d = o.dur ?? 1.6; const sf = o.soft ?? 0.5;
  modal([{ t, v: 1, w: 0.00012 + sf * 0.00025 }],[[f, 1, d * 0.4], [f * 2.756, 0.3 * (1 - 0.7 * sf), d * 0.1], [f * 5.404, 0.1 * (1 - sf), d * 0.04], [f * 4, 0.12 * sf, d * 0.08]],
    { bus: o.bus || 'keys', pan: o.pan ?? 0.2, verb: o.verb ?? 0.45, vel: (o.vel ?? 0.4) * 0.6, len: d * 2.2 });
}

const TIMP = [[1, 1, 1.6], [1.504, 0.55, 1.0], [1.742, 0.32, 0.7], [2.0, 0.3, 0.75], [2.245, 0.18, 0.5], [2.494, 0.14, 0.45], [2.8, 0.09, 0.3], [3.15, 0.05, 0.22], [0.6, 0.7, 0.06]];
/** Timpani stroke at t, or a roll t → o.t1 from velocity v to o.to (o.rate strokes per second, o.curve). n: pitch. */
export function timp(t, n, v = 0.8, o = {}) {
  const f = F(n); let hits;
  if (o.t1) {
    hits = []; let tt = t; let i = 0; const rate = o.rate ?? 16;
    while (tt < o.t1) {
      const p = (tt - t) / (o.t1 - t); const vv = (v + ((o.to ?? v) - v) * Math.pow(p, o.curve ?? 1.6)) * (i % 2 ? 0.85 : 1) * (0.9 + 0.2 * rand());
      hits.push({ t: tt, v: vv, w: 0.007 - 0.003 * Math.min(1, vv) }); tt += (1 / rate) * (0.88 + 0.24 * rand()); i++;
    }
  } else hits = [{ t, v, w: 0.0065 - 0.0035 * Math.min(1, v) }];
  modal(hits, TIMP.map(([r, a, tau]) => [f * r, a, tau * (o.decay ?? 1)]), { bus: o.bus || 'perc', pan: o.pan ?? -0.2, verb: o.verb ?? 0.3, vel: (o.vel ?? 1) * (o.t1 ? 0.2 : 0.34), len: 3 });
}

/** Taiko / big drum: pitched skin with a pitch drop, slap and body. o: f (Hz), vel, decay, slap, slapF, pan, bus ('perc'), verb. */
export function taiko(t, o = {}) {
  const f0 = o.f ?? 62; const dec = o.decay ?? 0.45;
  const w = writer(o.bus || 'perc', { pan: o.pan ?? 0, verb: o.verb ?? 0.35, gain: o.vel ?? 0.8 });
  const sl = svf(); const lo = svf(); const i0 = at(t); const n = Math.floor((dec * 5 + 0.05) * SR);
  let p1 = 0; let p2 = 0;
  for (let k = 0; k < n; k++) {
    const s = k / SR; const fr = f0 * (1 + 0.55 * Math.exp(-s / 0.03));
    p1 += (TAU * fr) / SR; p2 += (TAU * fr * 1.58) / SR;
    const body = Math.sin(p1) * Math.exp(-s / dec) + Math.sin(p2) * 0.35 * Math.exp(-s / (dec * 0.4));
    const slap = sl(noise(), o.slapF ?? 900, 0.9).bp * Math.exp(-s / 0.012) * (o.slap ?? 0.7);
    const thump = lo(noise(), 180, 0.7).lp * Math.exp(-s / 0.03) * 0.8;
    w(i0 + k, drive((body + slap + thump) * (s < 0.0015 ? s / 0.0015 : 1), 1.5) * (k > n - 480 ? (n - k) / 480 : 1));
  }
}
/** Gran cassa (orchestral bass drum). */
export const bassDrum = (t, o = {}) => taiko(t, { f: 41, decay: 1.0, slap: 0.25, slapF: 350, verb: 0.4, ...o });

/** Tam-tam: dense inharmonic shimmer. o: vel, dur, pan, bus. */
export function tamtam(t, o = {}) {
  const modes = [];
  for (let i = 0; i < 64; i++) { const fq = 70 * Math.pow(60, rand()); modes.push([fq, 0.15 + 0.85 * rand() * rand(), (o.dur ?? 5) * (0.25 + 0.75 * rand()) * Math.pow(400 / Math.max(400, fq), 0.35)]); }
  const hits = Array.from({ length: 6 }, (_, j) => ({ t: t + j * 0.004, v: 1 - j * 0.12, w: 0.006 }));
  modal(hits, modes, { bus: o.bus || 'perc', pan: o.pan ?? 0.25, verb: 0.5, vel: (o.vel ?? 0.5) * 0.18, len: o.dur ?? 5, spread: 0.004 });
}
