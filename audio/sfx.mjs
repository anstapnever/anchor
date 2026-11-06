// ANCHOR score: sound effects, all synthesized (no samples, no voices): wind, gulls, chimes, bells, thunder, electric
// crackle, metal groans and creaks, clanks and chain rattles, splashes, waves, bubbles, steam, servos, tearing vines,
// wing flaps, colossal booms, the waterspout roar, tiles, boat engines, horns, power up / down.
import { A, F, wob, modal } from './lib.mjs';

const { SR, TAU, writer, at, noise, rand, svf, saw, clamp, panLR, drive, lerp } = A;
const smooth = (x) => x * x * (3 - 2 * x);

/** Wind bed: two pink-noise band-passes with gusts and a whistle. level(t) → 0..1. o: base (Hz), whistle (0..1), whistleF, gust (Hz), vel, bus ('amb'). */
export function wind(t0, t1, level, o = {}) {
  const w = writer(o.bus || 'amb', { verb: o.verb ?? 0.1, gain: o.vel ?? 1 });
  const nL = A.pink(); const nR = A.pink(); const bl = svf(); const br = svf(); const wl = svf(); const wr = svf(); const ll = svf(); const lr = svf();
  const gust = wob(o.gust ?? 0.12); const gust2 = wob(0.33); const wh = wob(0.08);
  const base = o.base ?? 500; const whis = o.whistle ?? 0.3;
  const i0 = at(t0); const n = Math.floor((t1 - t0) * SR);
  let lv = 0; let g = 0; let fc = base; let fw = 900;
  for (let k = 0; k < n; k++) {
    const T = t0 + k / SR;
    if ((k & 63) === 0) { lv = level(T); g = clamp(0.55 + 0.45 * gust(T) + 0.2 * gust2(T), 0, 1.3); fc = base * (0.6 + 0.8 * g); fw = (o.whistleF ?? 900) * (1 + 0.35 * wh(T)); }
    const a = nL(); const b = nR();
    const amp = lv * (0.35 + 0.65 * g) * Math.min(1, k / 2400, (n - k) / 2400);
    const l = bl(a, fc, 0.6).bp * 1.2 + ll(a, 250, 0.7).lp * 0.25 + wl(a, fw, 14).bp * whis * g * g * 0.08;
    const r = br(b, fc * 1.07, 0.6).bp * 1.2 + lr(b, 250, 0.7).lp * 0.25 + wr(b, fw * 1.05, 14).bp * whis * g * g * 0.08;
    w(i0 + k, l * amp, r * amp);
  }
}

/** Herring-gull call ('kee-ow' then shorter 'kyow's): a rough saw through two formants. o: f, calls, first, gap, pan, dist (0..1), vel, bus ('foley'). */
export function gull(t, o = {}) {
  const f0 = o.f ?? 850; const w = writer(o.bus || 'foley', { pan: o.pan ?? 0, verb: o.verb ?? 0.35, gain: o.vel ?? 0.5 });
  const lp = svf(); const f1 = svf(); const f2 = svf(); const osc = saw();
  const segs = []; let tt = 0;
  for (let c = 0; c < (o.calls ?? 3); c++) {
    const d = c === 0 ? (o.first ?? 0.3) : 0.15 + 0.06 * rand();
    segs.push([tt, d, f0 * (c === 0 ? 1.08 : 1) * (0.94 + 0.12 * rand())]); tt += d + (o.gap ?? 0.09) + 0.05 * rand();
  }
  const n = Math.floor((tt + 0.1) * SR); const i0 = at(t); const dist = o.dist ?? 0.3;
  for (let k = 0; k < n; k++) {
    const s = k / SR; let amp = 0; let f = f0;
    for (const [s0, d, fb] of segs) {
      if (s >= s0 && s < s0 + d) { const u = (s - s0) / d; f = fb * (u < 0.25 ? 0.8 + (0.6 * u) / 0.25 : 1.4 - (0.65 * (u - 0.25)) / 0.75); amp = Math.min(1, (s - s0) / 0.015, (s0 + d - s) / 0.04); }
    }
    const rough = 1 + 0.35 * Math.sin(TAU * 31 * s) * Math.sin(TAU * 7 * s);
    const x = osc(f * (1 + 0.01 * noise())) * amp * rough;
    w(i0 + k, lp(f1(x, 1700, 3).bp * 0.6 + f2(x, 3100, 3).bp * 0.35 + x * 0.1, 6500 - 4500 * dist, 0.7).lp);
  }
}

/** Gull chick peeps. o: n, gap, f, pan, vel. */
export function chick(t, o = {}) {
  const w = writer(o.bus || 'foley', { pan: o.pan ?? 0, verb: o.verb ?? 0.25, gain: o.vel ?? 0.3 }); const i0 = at(t);
  for (let c = 0; c < (o.n ?? 3); c++) {
    const off = Math.floor((c * (o.gap ?? 0.16) + 0.03 * rand()) * SR); const f0 = (o.f ?? 3900) * (0.9 + 0.2 * rand()); const d = 0.07 + 0.03 * rand(); let ph = 0;
    for (let k = 0; k < d * SR; k++) { const s = k / SR; ph += (TAU * f0 * (1.15 - (0.3 * s) / d)) / SR; w(i0 + off + k, (Math.sin(ph) + 0.2 * Math.sin(2 * ph)) * Math.sin((Math.PI * s) / d)); }
  }
}

/** Wind chimes: random strikes on tuned tubes (free-bar modes). o: notes, gap (mean s between strikes), vel. */
export function chimes(t0, t1, o = {}) {
  const fs = (o.notes ?? ['D6', 'E6', 'F#6', 'A6', 'B6']).map(F); const hits = fs.map(() => []);
  for (let t = t0; t < t1; t += (o.gap ?? 0.35) * (0.3 + 1.4 * rand())) hits[Math.floor(rand() * fs.length)].push({ t, v: 0.4 + 0.6 * rand(), w: 0.0002 });
  fs.forEach((f, j) => {
    if (hits[j].length) modal(hits[j], [[f, 1, 2.2], [f * 2.756, 0.4, 0.9], [f * 5.404, 0.15, 0.35], [f * 8.933, 0.06, 0.15]],
      { bus: o.bus || 'foley', pan: -0.6 + (1.2 * j) / (fs.length - 1), verb: 0.5, vel: o.vel ?? 0.15, len: 4 });
  });
}

/** Church bell (hum, prime, minor-third tierce, quint, nominal...). times: strike times; o.v: velocity or list. */
export function churchBell(times, n, o = {}) {
  const f = F(n);
  modal(times.map((t, i) => ({ t, v: Array.isArray(o.v) ? o.v[i] : o.v ?? 1, w: 0.0006 })),
    [[f * 0.5, 0.6, 6], [f, 0.8, 4], [f * 1.2, 0.6, 3.5], [f * 1.5, 0.35, 2.5], [f * 2, 0.7, 2.6], [f * 2.5, 0.25, 1.4], [f * 3, 0.2, 1.1], [f * 4.2, 0.1, 0.6]],
    { bus: o.bus || 'foley', pan: o.pan ?? 0.3, verb: o.verb ?? 0.5, vel: o.vel ?? 0.2, len: 5 });
}

/** Thunder: a ripping crack (close), a sub boom and a rolling rumble of random bumps. o: close (0..1), dur, vel, pan, bus ('sfx'). */
export function thunder(t, o = {}) {
  const close = o.close ?? 0.5; const dur = o.dur ?? 4;
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.3, gain: o.vel ?? 0.8 });
  const i0 = at(t); const n = Math.floor(dur * SR);
  const cr = svf(); const lL = svf(); const lR = svf(); const mL = svf(); const mR = svf(); const sub = A.sine();
  const bumps = Array.from({ length: 5 + Math.floor(rand() * 4) }, (_, j) => ({ c: j === 0 ? 0.05 : rand() * dur * 0.7, wd: 0.2 + rand() * 0.6, a: j === 0 ? 1 : 0.3 + 0.6 * rand() }));
  const ck = Math.max(0, (close - 0.35) / 0.65); // distance filters the crack away: only near strikes rip
  const cracks = new Map(); for (let ct = 0; ct < 0.25 * ck; ct += 0.002 + 0.02 * rand() * (ct / 0.25 + 0.2)) cracks.set(Math.floor(ct * SR), 0.5 + rand());
  for (let k = 0; k < n; k++) {
    const s = k / SR;
    let env = 0; for (const b of bumps) env += b.a * Math.exp(-Math.pow((s - b.c) / b.wd, 2));
    env *= Math.exp(-s / (dur * 0.45)) * Math.min(1, s / (0.01 + 0.25 * (1 - close)));
    const a = noise(); const b = noise();
    const imp = cracks.has(k) ? cracks.get(k) * noise() * 4 : 0;
    const crack = cr(imp + noise() * 0.15 * Math.exp(-s / 0.05) * ck, 2500, 0.5).hp * ck * 2 * Math.exp(-s / 0.18);
    const boom = sub(38) * Math.exp(-s / 0.5) * close * 0.6 * Math.min(1, s / 0.01);
    const fade = k > n - 2400 ? (n - k) / 2400 : 1;
    const l = lL(a, 90 + 140 * close, 0.7).lp * 2.2 + mL(a, 300 + 400 * close, 0.6).bp * 0.5 * close;
    const r = lR(b, 90 + 140 * close, 0.7).lp * 2.2 + mR(b, 320 + 400 * close, 0.6).bp * 0.5 * close;
    w(i0 + k, drive(l * env + crack + boom, 1.3) * fade, drive(r * env + crack + boom, 1.3) * fade);
  }
}

/** Electric crackle: random sparks, a 100 Hz arc buzz and hiss, drifting in the stereo field. o: density (sparks/s), shape(u), hum, vel. */
export function crackle(t0, t1, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.2, gain: o.vel ?? 0.4 });
  const hp = svf(); const hp2 = svf(); const bz = svf(); const i0 = at(t0); const n = Math.floor((t1 - t0) * SR); const dens = o.density ?? 250; let ph = 0;
  for (let k = 0; k < n; k++) {
    const u = k / n; const lv = o.shape ? o.shape(u) : Math.pow(1 - u, 1.5); const p = (dens / SR) * lv;
    const imp = (rand() < p ? (rand() * 2 - 1) * (0.5 + rand()) : 0) + (rand() < p * 0.3 ? noise() * 3 : 0);
    ph += (TAU * 100) / SR;
    const x = hp(imp, 1500, 0.7).hp + hp2(noise(), 5000, 0.7).hp * 0.08 * lv + bz(Math.sign(Math.sin(ph)) * 0.05 * (o.hum ?? 1) * lv, 1200, 0.8).lp;
    const pn = Math.sin((TAU * 0.7 * k) / SR) * 0.4; const xx = x * 0.4;
    w(i0 + k, xx * (1 - pn) * Math.min(1, (n - k) / 480), xx * (1 + pn) * Math.min(1, (n - k) / 480));
  }
}

/** Deep metal stress groan: stick-slip pulses ringing low resonances that sag in pitch. o: f (Hz), drop, rate, peak (0..1), vel, pan. */
export function groan(t, dur, o = {}) {
  const f0 = o.f ?? 55; const drop = o.drop ?? 0.12; const pk = o.peak ?? 0.35;
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.35, gain: o.vel ?? 0.5 });
  const R = [1, 1.62, 2.31, 3.17, 4.43]; const G = [1, 0.7, 0.5, 0.35, 0.25]; const fs = R.map(() => svf()); const lo = svf(); const wb = wob(0.6); const wb2 = wob(2.2);
  const i0 = at(t); const n = Math.floor(dur * SR); let ph = 0; let rate = 38; let fq = R.map((r) => f0 * r);
  for (let k = 0; k < n; k++) {
    const s = k / SR; const u = s / dur;
    if ((k & 31) === 0) { rate = (o.rate ?? 38) * (1 + 0.35 * wb(t + s) + 0.15 * wb2(t + s)); fq = R.map((r, j) => f0 * r * (1 - drop * u) * (1 + 0.015 * wb2(t + s + j))); }
    const env = u < pk ? smooth(u / pk) : Math.pow(1 - (u - pk) / (1 - pk), 1.5);
    ph += rate / SR; let x = lo(noise(), 300, 0.7).lp * 0.5; if (ph >= 1) { ph -= 1; x += 4 * (0.6 + 0.8 * rand()); }
    let y = 0; for (let j = 0; j < 5; j++) y += (fs[j](x, fq[j], 16).bp / 16) * G[j] * 4;
    w(i0 + k, drive(y * env * 8, 1.6));
  }
}

/** Creak: stick-slip pulses through a resonance (wood ~500 Hz, big steel ~200 Hz). o: f, q, rate [r0, r1], vel, pan. */
export function creak(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.3, gain: o.vel ?? 0.4 });
  const f1 = svf(); const f2 = svf(); const f3 = svf(); const fq = o.f ?? 420; const q = o.q ?? 10; const [r0, r1] = o.rate ?? [40, 14];
  const i0 = at(t); const n = Math.floor(dur * SR); let ph = 0; let next = 1;
  for (let k = 0; k < n; k++) {
    const u = k / n; const rate = r0 * Math.pow(r1 / r0, u) * (1 + 0.3 * Math.sin((TAU * 3.1 * k) / SR));
    ph += rate / SR; let x = 0; if (ph >= next) { ph = 0; next = 0.7 + 0.6 * rand(); x = 1 + rand(); }
    const y = f1(x, fq, q).bp + f2(x, fq * 2.3, q * 0.8).bp * 0.5 + f3(x, fq * 3.9, 6).bp * 0.25;
    w(i0 + k, y * Math.pow(Math.sin(Math.PI * u), 0.7) * 6);
  }
}

/** Heavy metal hit (chain link, container wall, crane steel): inharmonic modes + a thud. o: size, f, ring (s), vel, pan, thud, mallet. */
export function clank(t, o = {}) {
  const sz = o.size ?? 1; const f0 = ((o.f ?? 160) / sz) * (0.94 + 0.12 * rand()); const ring = o.ring ?? 0.6;
  const R = [1, 1.52, 2.27, 2.79, 3.61, 4.47, 5.39, 6.83];
  const modes = R.map((r, j) => [f0 * r * (1 + 0.02 * (rand() - 0.5)), (j === 0 ? 1 : 0.7 / Math.sqrt(j)) * (0.6 + 0.6 * rand()), ring * sz * Math.pow(1 / r, 0.4) * (0.7 + 0.6 * rand())]);
  modal([{ t, v: 1, w: o.mallet ?? 0.0006 }], modes, { bus: o.bus || 'sfx', pan: o.pan ?? 0, verb: o.verb ?? 0.3, vel: (o.vel ?? 0.5) * 0.5, len: ring * sz * 4 + 0.1 });
  if (o.thud !== 0) A.thud(t, { f0: 70 / Math.sqrt(sz), vel: (o.vel ?? 0.5) * (o.thud ?? 0.5), bus: o.bus || 'sfx' });
}

/** Chain rattle / clatter: clanks at `rate` per second. o: size, vel, shape(u), pan, ring, thud, f. */
export function rattle(t0, t1, o = {}) {
  for (let t = t0; t < t1; t += (1 / (o.rate ?? 12)) * (0.4 + 1.2 * rand())) {
    const u = (t - t0) / (t1 - t0);
    clank(t, { size: (o.size ?? 0.7) * (0.8 + 0.4 * rand()), vel: (o.vel ?? 0.3) * (o.shape ? o.shape(u) : 1) * (0.5 + 0.7 * rand()), pan: (o.pan ?? 0) + (rand() - 0.5) * 0.6, ring: o.ring ?? 0.35, thud: o.thud ?? 0.2, bus: o.bus, f: o.f });
  }
}

/** Water splash: the slap, a falling-back hiss and droplet chirps; big ones get a low whump. o: size (0.3 … 3), dur, rain, vel, pan. */
export function splash(t, o = {}) {
  const sz = o.size ?? 1; const dur = o.dur ?? 0.8 + 1.2 * sz;
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.25, gain: o.vel ?? 0.5 });
  const i0 = at(t); const n = Math.floor(dur * SR); const fl = svf(); const fr = svf(); const cl = svf(); const cr = svf(); const hl = svf(); const hr = svf(); const sub = A.sine();
  const drops = Array.from({ length: Math.floor(30 * sz + 10) }, () => ({ k: Math.floor((0.08 + Math.pow(rand(), 0.7) * (dur - 0.2)) * SR), f: 900 + 2600 * rand(), a: 0.2 + 0.5 * rand(), p: rand() * 2 - 1 })).sort((a, z) => a.k - z.k);
  let di = 0; const act = [];
  for (let k = 0; k < n; k++) {
    const s = k / SR; const a = noise(); const b = noise();
    const body = Math.exp(-s / (0.12 * sz + 0.08)) * Math.min(1, s / 0.004); const cut = 300 + 5000 * Math.exp(-s / (0.15 * sz + 0.05));
    const rain = Math.pow(Math.sin(Math.PI * clamp((s - 0.05) / (dur - 0.05))), 2) * 0.35 * (o.rain ?? 1);
    let l = fl(a, cut, 0.7).lp * body * 1.4 + cl(a, 1600, 0.8).bp * body * 0.8 + hl(a, 2500, 0.7).hp * rain;
    let r = fr(b, cut * 1.05, 0.7).lp * body * 1.4 + cr(b, 1700, 0.8).bp * body * 0.8 + hr(b, 2600, 0.7).hp * rain;
    while (di < drops.length && drops[di].k <= k) act.push({ ...drops[di++], s: 0, ph: 0 });
    for (let j = act.length - 1; j >= 0; j--) {
      const d = act[j]; d.s += 1 / SR; if (d.s > 0.03) { act.splice(j, 1); continue; }
      d.ph += (TAU * d.f * (1 + 8 * d.s)) / SR; const v = Math.sin(d.ph) * d.a * Math.exp(-d.s / 0.008) * 0.35; l += v * (1 - d.p); r += v * (1 + d.p);
    }
    const wh = sz > 0.8 ? sub(55 / Math.sqrt(sz)) * Math.exp(-s / 0.15) * Math.min(1, s / 0.005) * 0.6 : 0;
    const fade = k > n - 2400 ? (n - k) / 2400 : 1;
    w(i0 + k, (l + wh) * fade, (r + wh) * fade);
  }
}

/** Wave: a swell building for `build` s before t, the crash at t, then the wash and fizz. o: build, dur, vel, pan. */
export function waveCrash(t, o = {}) {
  const build = o.build ?? 0.6; const dur = o.dur ?? 2.5;
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.3, gain: o.vel ?? 0.5 });
  const i0 = at(t - build); const n = Math.floor((build + dur) * SR); const fl = svf(); const fr = svf(); const hl = svf(); const hr = svf(); const lo = svf();
  for (let k = 0; k < n; k++) {
    const s = k / SR - build; let env; let cut;
    if (s < 0) { const u = 1 + s / build; env = u * u * 0.6; cut = 300 + 1500 * u; } else { env = (0.4 + 0.6 * Math.exp(-s / 0.25)) * Math.exp(-s / (dur * 0.5)); cut = 600 + 5000 * Math.exp(-s / (dur * 0.3)); }
    const a = noise(); const b = noise(); const fz = s > 0 ? 0.3 * (0.5 + 0.5 * Math.sin(TAU * 9 * s * (1 + 0.3 * Math.sin(s * 3)))) : 0;
    const low = s > 0 ? lo(a, 120, 0.7).lp * Math.exp(-s / 0.4) * 1.5 : 0;
    const fade = k > n - 4800 ? (n - k) / 4800 : 1;
    w(i0 + k, (fl(a, cut, 0.6).lp * 1.5 + hl(a, 4000, 0.7).hp * fz + low) * env * fade, (fr(b, cut * 1.08, 0.6).lp * 1.5 + hr(b, 4200, 0.7).hp * fz + low) * env * fade);
  }
}

/** Bubbles (Minnaert chirps). o: rate (per s), f [lo, hi], shape(u), lp (Hz), vel, bus. */
export function bubbles(t0, t1, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.2, gain: o.vel ?? 0.3 });
  const [fa, fb] = o.f ?? [300, 1400]; const i0 = at(t0); const n = Math.floor((t1 - t0 + 0.25) * SR); const nOn = (t1 - t0) * SR; const lp = svf(); const lp2 = svf(); const act = [];
  for (let k = 0; k < n; k++) {
    if (k < nOn && rand() < ((o.rate ?? 30) * (o.shape ? o.shape(k / nOn) : 1)) / SR) {
      const f0 = fa * Math.pow(fb / fa, rand()); act.push({ f0, d: 0.043 * f0 + 0.0014 * Math.pow(f0, 1.5), s: 0, ph: 0, a: 0.3 + 0.7 * rand(), p: rand() * 2 - 1 });
    }
    let l = 0; let r = 0;
    for (let j = act.length - 1; j >= 0; j--) {
      const b = act[j]; b.s += 1 / SR; const e = Math.exp(-b.d * b.s); if (e < 0.002) { act.splice(j, 1); continue; }
      b.ph += (TAU * b.f0 * (1 + 0.1 * b.d * b.s)) / SR; const v = Math.sin(b.ph) * e * b.a * Math.min(1, b.s / 0.0008); l += v * (1 - 0.5 * b.p); r += v * (1 + 0.5 * b.p);
    }
    w(i0 + k, lp(l, o.lp ?? 3000, 0.7).lp * 0.4, lp2(r, o.lp ?? 3000, 0.7).lp * 0.4);
  }
}

/** Steam hiss with pressure flutter and a faint whistle. o: whistle (Hz), vel, pan. */
export function steam(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.2, gain: o.vel ?? 0.3 });
  const hl = svf(); const hr = svf(); const bl = svf(); const br = svf(); const ws = svf(); const i0 = at(t); const n = Math.floor(dur * SR); const fl = wob(6);
  for (let k = 0; k < n; k++) {
    const s = k / SR; const env = Math.min(1, s / 0.03) * Math.pow(1 - s / dur, 1.3) * (1 + 0.15 * fl(t + s));
    const a = noise(); const b = noise(); const wh = ws(a, o.whistle ?? 3300, 25).bp * 0.012;
    w(i0 + k, (hl(a, 2500, 0.7).hp * 0.6 + bl(a, 6500, 1).bp * 0.5 + wh) * env, (hr(b, 2600, 0.7).hp * 0.6 + br(b, 6800, 1).bp * 0.5 + wh) * env);
  }
}

/** Servo / hydraulic motor whine rising f0 → f1, with gear harmonics and hiss. o: f0, f1, vel, pan. */
export function servo(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.25, gain: o.vel ?? 0.3 });
  const f0 = o.f0 ?? 180; const f1 = o.f1 ?? 520; const os = saw(); const lp = svf(); const hs = svf(); const i0 = at(t); const n = Math.floor(dur * SR); let p2 = 0; let p7 = 0;
  for (let k = 0; k < n; k++) {
    const s = k / SR; const u = s / dur; const g = u < 0.6 ? smooth(u / 0.6) : 1 - 0.35 * smooth((u - 0.6) / 0.4); const f = f0 * Math.pow(f1 / f0, g);
    p2 += (TAU * f * 2) / SR; p7 += (TAU * f * 7.5) / SR;
    const x = lp(os(f), f * 4, 1.2).lp * 0.5 + Math.sin(p2) * 0.25 + Math.sin(p7) * 0.08 + hs(noise(), 5000, 0.7).hp * 0.06;
    w(i0 + k, drive(x, 1.3) * Math.min(1, s / 0.08, (dur - s) / 0.15));
  }
}

/** Vines / roots tearing: bursts of fibre crackle with a low rip. o: rips, vel, pan. */
export function tear(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.2, gain: o.vel ?? 0.4 });
  const bp = svf(); const lo = svf(); const bp2 = svf(); const i0 = at(t); const n = Math.floor(dur * SR);
  const rips = Array.from({ length: o.rips ?? 3 }, () => ({ c: 0.1 + rand() * 0.8, w: 0.05 + rand() * 0.12, a: 0.5 + rand() * 0.5 }));
  for (let k = 0; k < n; k++) {
    const u = k / n; let e = 0; for (const r of rips) e += r.a * Math.exp(-Math.pow(((u - r.c) * dur) / r.w, 2)); e = Math.min(1.3, e + 0.15 * Math.sin(Math.PI * u));
    const imp = rand() < (300 + 2500 * e) / SR ? noise() * (0.5 + rand()) * 2 : 0;
    w(i0 + k, (bp(imp, 2200, 1.2).bp + bp2(imp, 900, 1).bp * 0.6 + lo(noise(), 500, 0.7).lp * e * 0.25) * Math.min(1, e));
  }
}

/** Wing flaps, fading away while panning p0 → p1. o: rate, pan [p0, p1], vel. */
export function flaps(t, dur, o = {}) {
  const w = writer(o.bus || 'foley', { verb: o.verb ?? 0.25, gain: o.vel ?? 0.3 });
  const bp = svf(); const i0 = at(t); const n = Math.floor(dur * SR); let ph = o.ph0 ?? rand(); const [p0, p1] = o.pan ?? [0, 0];
  for (let k = 0; k < n; k++) {
    const s = k / SR; const u = s / dur; ph += ((o.rate ?? 6) * (1 + 0.1 * Math.sin(s * 7))) / SR; if (ph >= 1) ph -= 1;
    const x = bp(noise(), 650 + 500 * Math.sin(Math.PI * ph), 0.9).bp * Math.pow(Math.sin(Math.PI * ph), 6) * (1 - 0.7 * u);
    const [gl, gr] = panLR(lerp(p0, p1, u)); w(i0 + k, x * gl * 3, x * gr * 3);
  }
}

/** Colossal impact / footfall: a sub with a pitch drop, a thump, a crunch and a rumbling tail; ducks the music ('hit'). o: f, decay, dur, crunch, crunchF, vel, pan, duck. */
export function boom(t, o = {}) {
  A.trigger('hit', t, o.duck ?? 1);
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.25, gain: o.vel ?? 0.8 });
  const f0 = o.f ?? 34; const n = Math.floor((o.dur ?? 3) * SR); const i0 = at(t); const th = svf(); const md = svf(); const rl = svf(); const rr = svf(); let ph = 0;
  for (let k = 0; k < n; k++) {
    const s = k / SR; ph += (TAU * f0 * (1 + 1.4 * Math.exp(-s / 0.05))) / SR;
    const a = noise(); const b = noise();
    const c = drive(Math.sin(ph) * Math.exp(-s / (o.decay ?? 0.9)) * Math.min(1, s / 0.004) + th(a, 220, 0.8).lp * Math.exp(-s / 0.06) * 1.6 + md(a, o.crunchF ?? 700, 0.8).bp * Math.exp(-s / 0.12) * (o.crunch ?? 0.6), 1.4);
    const fade = k > n - 4800 ? (n - k) / 4800 : 1;
    w(i0 + k, (c + rl(a, 140, 0.7).lp * Math.exp(-s / 1.2) * 0.9) * fade, (c + rr(b, 150, 0.7).lp * Math.exp(-s / 1.2) * 0.9) * fade);
  }
}

/** Waterspout roar bed: rumble, roar, a vortex whistle and spray hiss. level(t), o.pan(t). */
export function roar(t0, t1, level, o = {}) {
  const w = writer(o.bus || 'amb', { verb: o.verb ?? 0.1, gain: o.vel ?? 1 });
  const loL = svf(); const loR = svf(); const mdL = svf(); const mdR = svf(); const vxL = svf(); const vxR = svf(); const hiL = svf(); const hiR = svf();
  const m1 = wob(0.9); const m2 = wob(0.35); const m3 = wob(0.15); const pl = A.pink(); const pr = A.pink();
  const i0 = at(t0); const n = Math.floor((t1 - t0) * SR); let lv = 0; let gl = 1; let gr = 1; let fv = 400; let mm = 1; let fm = 520;
  for (let k = 0; k < n; k++) {
    const T = t0 + k / SR;
    if ((k & 63) === 0) { lv = level(T) * Math.min(1, k / 4800, (n - k) / 4800); [gl, gr] = panLR(o.pan ? o.pan(T) : 0); fv = 280 * (1 + 0.5 * m2(T)); mm = 0.75 + 0.25 * m1(T); fm = 520 * (1 + 0.2 * m3(T)); }
    const a = pl(); const b = pr();
    const l = loL(a, 160, 0.7).lp * 3 * mm + mdL(a, fm, 0.7).bp * 1.2 + vxL(a, fv, 9).bp * 0.25 + hiL(a, 3500, 0.7).hp * 0.15;
    const r = loR(b, 160, 0.7).lp * 3 * mm + mdR(b, fm * 1.05, 0.7).bp * 1.2 + vxR(b, fv * 1.06, 9).bp * 0.25 + hiR(b, 3600, 0.7).hp * 0.15;
    w(i0 + k, l * lv * gl * 0.16, r * lv * gr * 0.16);
  }
}

/** Falling roof tiles: ceramic clinks, some shattering. o: rate, vel, shape(u). */
export function tiles(t0, t1, o = {}) {
  for (let t = t0; t < t1; t += (1 / (o.rate ?? 14)) * (0.3 + 1.4 * rand())) {
    const f = 1800 + 2800 * rand(); const v = (o.vel ?? 0.2) * (0.4 + 0.6 * rand()) * (o.shape ? o.shape((t - t0) / (t1 - t0)) : 1);
    modal([{ t, v: 1, w: 0.00015 }], [[f, 1, 0.07 + 0.08 * rand()], [f * 2.31, 0.5, 0.05], [f * 3.9, 0.3, 0.03], [f * 0.62, 0.4, 0.04]], { bus: o.bus || 'foley', pan: (rand() - 0.5) * 1.4, verb: 0.3, vel: v, len: 0.4 });
    if (rand() < 0.25) A.noiseHit(t + 0.01, 0.12, { bp: 3500, q: 0.8, decay: 30, vel: v * 0.5, bus: o.bus || 'foley', pan: rand() - 0.5 });
  }
}

/** Boat diesel passing by (putt-putt with a little Doppler). o: rate (Hz), pan [p0, p1], pass (0..1 closest point), vel. */
export function engine(t0, t1, o = {}) {
  const w = writer(o.bus || 'foley', { verb: o.verb ?? 0.15, gain: o.vel ?? 0.3 });
  const lp = svf(); const bp = svf(); const i0 = at(t0); const n = Math.floor((t1 - t0) * SR); const [p0, p1] = o.pan ?? [-0.8, 0.8]; const tc = o.pass ?? 0.5; let ph = 0; let pd = 0;
  for (let k = 0; k < n; k++) {
    const u = k / n; const dist = Math.abs(u - tc) * 2; const g = 1 / (1 + 6 * dist * dist); const dop = 1 + 0.05 * Math.tanh((tc - u) * 6);
    ph += ((o.rate ?? 9) * dop) / SR; let imp = 0; if (ph >= 1) { ph -= 1; imp = 1; }
    pd += (TAU * 55 * dop) / SR;
    const x = (bp(imp * 3 + noise() * 0.05, 140 * dop, 2).bp + lp(noise(), 400, 0.7).lp * 0.08 + Math.sin(pd) * 0.05) * 10;
    const [gl, gr] = panLR(lerp(p0, p1, u)); const fade = Math.min(1, k / 2400, (n - k) / 2400);
    w(i0 + k, x * g * gl * fade, x * g * gr * fade);
  }
}

/** Boat horn toot (two saws a major third apart). o: f, dop (Doppler drop 0..0.06), vel, pan. */
export function toot(t, dur, o = {}) {
  const f = o.f ?? 220; const w = writer(o.bus || 'foley', { pan: o.pan ?? 0, verb: o.verb ?? 0.4, gain: o.vel ?? 0.2 });
  const a = saw(); const b = saw(); const lp = svf(); const i0 = at(t); const n = Math.floor((dur + 0.2) * SR);
  for (let k = 0; k < n; k++) {
    const s = k / SR; const dop = 1 + (o.dop ?? 0) * (0.5 - Math.min(1, s / dur));
    w(i0 + k, lp(a(f * dop) + b(f * 1.26 * dop) * 0.8, 900, 1).lp * Math.min(1, s / 0.05) * (s < dur ? 1 : Math.max(0, 1 - (s - dur) / 0.2)) * 0.5);
  }
}

/** Metal tearing / screeching: an erratic friction tone through metal resonances, with grit. o: f, vel, pan. */
export function screech(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.35, gain: o.vel ?? 0.35 });
  const os = saw(); const os2 = saw(); const r1 = svf(); const r2 = svf(); const r3 = svf(); const hp = svf(); const i0 = at(t); const n = Math.floor(dur * SR); const wb = wob(3); const wb2 = wob(11);
  let f = o.f ?? 900;
  for (let k = 0; k < n; k++) {
    const s = k / SR; const u = s / dur;
    if ((k & 15) === 0) f = (o.f ?? 900) * (1 + 0.45 * wb(t + s) + 0.12 * wb2(t + s)) * (1 - 0.3 * u);
    const x = os(f) + os2(f * 1.51) * 0.5 + noise() * 0.3;
    const y = r1(x, f * 2.1, 8).bp * 0.25 + r2(x, 2700, 6).bp * 0.2 + r3(x, f, 5).bp * 0.3 + hp(noise(), 3000, 0.7).hp * (rand() < 0.3 ? 0.2 : 0.04);
    w(i0 + k, drive(y * Math.min(1, s / 0.02) * Math.pow(1 - u, 0.8) * (0.7 + 0.3 * Math.sin(TAU * 13 * s)), 2));
  }
}

/** Power-up whine: a rising tone and opening filter with a fading mains hum. o: f0, f1, vel. */
export function powerUp(t0, t1, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.35, gain: o.vel ?? 0.35 });
  const os = saw(); const lp = svf(); const i0 = at(t0); const dur = t1 - t0; const n = Math.floor((dur + 0.3) * SR); let p1 = 0; let p2 = 0;
  const f0 = o.f0 ?? 55; const f1 = o.f1 ?? 1100;
  for (let k = 0; k < n; k++) {
    const s = k / SR; const u = Math.min(1, s / dur); const f = f0 * Math.pow(f1 / f0, Math.pow(u, 1.4));
    p1 += (TAU * f * 2) / SR; p2 += (TAU * 100) / SR;
    const env = Math.pow(u, 1.2) * (s > dur ? Math.max(0, 1 - (s - dur) / 0.3) : 1);
    w(i0 + k, (lp(os(f), 300 + 5000 * u, 1.5).lp * 0.5 + Math.sin(p1) * 0.25 + Math.sign(Math.sin(p2)) * 0.03 * (1 - u)) * env);
  }
}

/** Soft descending power-down tone with a faint whir. o: from, to (notes), vel. */
export function powerDown(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.5, gain: o.vel ?? 0.2 });
  const i0 = at(t); const n = Math.floor(dur * SR); let p = 0; const f0 = F(o.from ?? 'A5'); const f1 = F(o.to ?? 'D4'); const os = saw(); const lp = svf();
  for (let k = 0; k < n; k++) {
    const s = k / SR; const u = s / dur; const f = f0 * Math.pow(f1 / f0, Math.pow(u, 0.7)); p += (TAU * f) / SR;
    w(i0 + k, (Math.sin(p) + 0.18 * Math.sin(2 * p) + 0.06 * Math.sin(3 * p) + lp(os(f * 0.25), 600, 0.7).lp * 0.15) * Math.min(1, s / 0.02) * Math.pow(1 - u, 1.6) * 0.5);
  }
}

/** Electrical flicker: a 120 Hz buzz switching on and off. o: vel, pan. */
export function flicker(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.2, gain: o.vel ?? 0.2 });
  const lp = svf(); const i0 = at(t); const n = Math.floor(dur * SR); let on = 1; let g = 0; let cnt = 0; let p = 0;
  for (let k = 0; k < n; k++) {
    if (cnt-- <= 0) { on = rand() < 0.55 ? 1 : 0; cnt = Math.floor((0.015 + 0.06 * rand()) * SR); }
    g += (on - g) * 0.02; p += (TAU * 120) / SR;
    w(i0 + k, lp(Math.sign(Math.sin(p)) + noise() * 0.2, 2200, 0.8).lp * g * 0.4 * Math.min(1, (n - k) / 200));
  }
}

/** Underwater burst (silt explosion): a muffled whoomp with a bubble cloud. o: vel, pan. */
export function silt(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.2, gain: o.vel ?? 0.5 });
  const l1 = svf(); const l2 = svf(); const i0 = at(t); const n = Math.floor(dur * SR); let p = 0;
  for (let k = 0; k < n; k++) {
    const s = k / SR; const cut = 150 + 600 * Math.exp(-s / 0.3); p += (TAU * (40 + 30 * Math.exp(-s / 0.1))) / SR;
    const env = Math.min(1, s / 0.03) * Math.exp(-s / (dur * 0.35)) * Math.min(1, (n - k) / 2400);
    w(i0 + k, (l1(noise(), cut, 0.7).lp * 2 + Math.sin(p) * 0.5) * env, (l2(noise(), cut * 1.1, 0.7).lp * 2 + Math.sin(p) * 0.5) * env);
  }
  bubbles(t + 0.05, t + dur * 0.8, { rate: 60, f: [150, 700], vel: (o.vel ?? 0.5) * 0.5, lp: 1200, bus: o.bus || 'sfx', shape: (u) => Math.exp(-u * 3) });
}

/** Concrete crunch / rubble trickle. o: vel, pan. */
export function rubble(t, dur, o = {}) {
  const w = writer(o.bus || 'sfx', { pan: o.pan ?? 0, verb: o.verb ?? 0.2, gain: o.vel ?? 0.4 });
  const bp = svf(); const bp2 = svf(); const i0 = at(t); const n = Math.floor(dur * SR);
  for (let k = 0; k < n; k++) {
    const u = k / n; const imp = rand() < (3000 * Math.exp(-u * 4) + 200) / SR ? noise() * (0.3 + rand()) * 2 : 0;
    w(i0 + k, (bp(imp, 2200, 1.4).bp + bp2(imp, 500, 1).bp * 0.6) * Math.pow(1 - u, 1.2));
  }
}

/** Underwater bed: a low pressure rumble and stray bubbles. */
export function underBed(t0, t1, o = {}) {
  const w = writer(o.bus || 'amb', { verb: 0.15, gain: o.vel ?? 0.6 });
  const l1 = svf(); const l2 = svf(); const m = wob(0.25); const i0 = at(t0); const n = Math.floor((t1 - t0) * SR);
  for (let k = 0; k < n; k++) {
    const g = (0.7 + 0.3 * m(t0 + k / SR)) * Math.min(1, k / 9600, (n - k) / 9600);
    w(i0 + k, l1(noise(), 220, 0.7).lp * 2 * g, l2(noise(), 240, 0.7).lp * 2 * g);
  }
  bubbles(t0, t1, { rate: o.bubbles ?? 6, f: [250, 900], vel: 0.25, lp: 1500, bus: o.bus || 'amb' });
}

/** Harbour water lapping on stone. o: vel. */
export function lap(t0, t1, o = {}) {
  const w = writer(o.bus || 'amb', { verb: 0.1, gain: o.vel ?? 0.5 });
  const l1 = svf(); const l2 = svf(); const b1 = svf(); const i0 = at(t0); const n = Math.floor((t1 - t0) * SR); const m1 = wob(0.3); const m2 = wob(0.45);
  let a = 0; let b = 0;
  for (let k = 0; k < n; k++) {
    const T = t0 + k / SR; if ((k & 63) === 0) { a = Math.max(0, 0.5 + 0.6 * m1(T)); b = Math.max(0, 0.5 + 0.6 * m2(T)); }
    const fade = Math.min(1, k / 9600, (n - k) / 9600); const sl = b1(noise(), 1300, 1).bp * a * a * a * a * 0.4;
    w(i0 + k, (l1(noise(), 500 + 400 * a, 0.7).lp * a + sl) * fade, (l2(noise(), 520 + 400 * b, 0.7).lp * b + sl * 0.8) * fade);
  }
}
