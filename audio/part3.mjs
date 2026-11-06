// ANCHOR score, part 3. Act 5 (55-70 s): the chase in 12/8 (a footfall every 0.6 s), the heroic brass theme, boats
// between its legs, the leap (silence but a high string and the wind), the landing, the climb to the grab at 69.3.
// Act 6 (70-82 s): the hold: a grinding 3/4 ostinato, steam, cracks, the rising choir while it winds the chain round
// the lighthouse, the waterspout passing, the release. Act 7 (82-92 s): the clouds open, the whole theme, the gull, the
// visor dims, the last chord rings.
import { A, M, strings, line, choir, piano, glock, timp, taiko } from './lib.mjs';
import * as S from './sfx.mjs';
import { cue, notes, gliss, arpeggio, ostinato, brassChord, swellStr, tutti } from './common.mjs';

const pick = (H, t) => H.reduce((a, h) => (h[0] <= t + 1e-9 ? h : a), H[0]);

export function act5() {
  // ---- the chase: 12/8, dotted quarter = 0.6 s = one footfall --------------------------------------------------------------
  const H5 = [[55.0, 'B1', ['B2', 'D3', 'F#3', 'B3', 'D4']], [56.2, 'G1', ['G2', 'D3', 'G3', 'B3', 'D4']], [57.4, 'D2', ['D3', 'F#3', 'A3', 'D4', 'F#4']], [58.6, 'B1', ['B2', 'F#3', 'B3', 'D4', 'F#4']],
    [59.8, 'G1', ['G2', 'D3', 'G3', 'B3', 'E4']], [61.0, 'A1', ['A2', 'E3', 'A3', 'C#4', 'E4']], [62.2, 'G1', ['G2', 'D3', 'G3', 'B3', 'D4']], [62.8, 'A1', ['A2', 'E3', 'A3', 'C#4', 'E4']]];
  ostinato(55.0, 63.4, 0.2, (i, t) => M(pick(H5, t)[1]) + [0, 12, 7][i % 3], { vf: (i, t) => (i % 3 === 0 ? 0.72 : 0.52) + (0.12 * (t - 55)) / 8.4, bright: 0.55, sub: 0.7, dur: 0.17 });
  H5.forEach(([t, r, ch], i) => {
    const d = (i + 1 < H5.length ? H5[i + 1][0] : 63.4) - t;
    swellStr(t, d - 0.02, ch, 0.55 + 0.05 * i, 0.7 + 0.05 * i, { att: 0.06, rel: 0.1, trem: 13, bright: 0.55, vel: 0.42 });
    brassChord(t, d - 0.05, [M(r) + 12, M(ch[1]) - 12 < 40 ? M(ch[1]) : M(ch[1]) - 12, M(ch[2]) - 12], { vel: 0.3, rel: 0.1, dyn: (T) => 0.7 + (0.3 * (T - t)) / d });
    let tp = M(r); while (tp < 38) tp += 12; timp(t, tp, 0.6 + 0.04 * i);
  });
  for (let n = 0; n < 14; n++) {
    const t = 55.0 + 0.6 * n;
    taiko(t, { vel: 0.85 + (n % 2 ? 0 : 0.1), f: 56 });
    A.tom(t + 0.2, 'D3', { vel: 0.22, bus: 'perc', verb: 0.25 }); A.tom(t + 0.4, n % 4 === 3 ? 'E3' : 'A2', { vel: 0.3, bus: 'perc', verb: 0.25 });
  }
  A.crash(57.4, { vel: 0.45, bus: 'perc', dur: 2.4 }); A.crash(61.0, { vel: 0.4, bus: 'perc', dur: 2.0 });
  A.roll(62.2, 63.4, (t, v) => A.snare(t, { type: 'tight', vel: v * 0.3, bus: 'perc', verb: 0.3 }), { from: 1 / 4, to: 1 / 16, vel0: 0.3, vel1: 1 });
  A.riser(62.2, 63.4, { vel: 0.12, bus: 'sfx', type: 'noise' });
  const callH = notes([[55.0, 0.42, 'B3', 0.9], [55.4, 0.22, 'D4', 0.85], [55.6, 0.62, 'F#4', 1.0], [56.2, 0.42, 'G4', 0.95], [56.6, 0.22, 'F#4', 0.85], [56.8, 0.6, 'D4', 0.9]]);
  line(callH, { type: 'horn', bus: 'brass', vel: 0.5, pan: -0.2, rel: 0.1 });
  line(callH.map((x) => ({ ...x, n: M(x.n) - 12 })), { type: 'cello', bus: 'str', vel: 0.3, pan: 0.1, rel: 0.1 });
  cue(55.0, 'music', 'Act 5, the chase: 12/8 gallop at a dotted quarter = 0.6 s; taiko on every footfall, toms on the off-8ths, string ostinato B-G-D-B-G-A-G-A; horn call B3 D4 F#4 / G4 F#4 D4 (55.0-57.4) with cellos');
  const her = notes([[57.4, 0.62, 'F#4', 0.95], [58.0, 0.62, 'A4', 1.0], [58.6, 1.22, 'D5', 1.1], [59.8, 0.62, 'E5', 1.0], [60.4, 0.42, 'F#5', 1.05], [60.8, 0.22, 'G5', 1.05], [61.0, 1.22, 'A5', 1.15], [62.2, 0.62, 'B5', 1.1], [62.8, 0.6, 'C#6', 1.15]]);
  line(her, { type: 'brass', bus: 'brass', vel: 0.42, pan: 0.1, rel: 0.12 });
  line(her.map((x) => ({ ...x, n: M(x.n) - 12 })), { type: 'horn', bus: 'brass', vel: 0.5, pan: -0.15, rel: 0.12 });
  line(her.filter((x) => x.t >= 59.8).map((x) => ({ ...x, n: M(x.n) + 12 })), { type: 'violin', bus: 'str', vel: 0.24, pan: 0.25, rel: 0.1 });
  cue(57.4, 'music', 'Heroic brass theme over the gallop: trumpets + horns (F#4 A4 D5 | E5 F#5 G5 A5 | B5 C#6), violins join at 59.8');
  // ---- footfalls: water, then off screen, then the breakwater; the push-off -------------------------------------------------------
  for (let n = 0; n < 14; n++) {
    const t = 55.0 + 0.6 * n; const pan = n % 2 ? 0.15 : -0.15;
    if (t < 59.0) { S.boom(t, { f: 36, decay: 0.6, dur: 1.6, vel: 0.5, crunch: 0.25, pan }); S.splash(t + 0.02, { size: 1.1, dur: 1.4, vel: 0.36, pan, rain: 0.7 }); }
    else if (t < 61.0) { S.boom(t, { f: 38, decay: 0.5, dur: 1.2, vel: 0.22, crunch: 0.1 }); S.splash(t + 0.02, { size: 0.8, vel: 0.12, rain: 0.4 }); }
    else { S.boom(t, { f: 40, decay: 0.45, dur: t > 62.5 ? 0.9 : 1.4, vel: 0.55, crunch: 0.9, crunchF: 1100, pan }); S.rubble(t + 0.01, 0.5, { vel: 0.3, pan }); }
    S.clank(t + 0.03, { size: 2.2, ring: 0.25, vel: 0.12, thud: 0, pan });
  }
  S.boom(63.4, { f: 38, decay: 0.4, dur: 0.9, vel: 0.65, crunch: 1.0, crunchF: 1000 }); S.rubble(63.41, 0.7, { vel: 0.45 }); S.clank(63.42, { size: 1.8, ring: 0.3, vel: 0.3, thud: 0.3 });
  cue(55.0, 'HIT', 'Footfalls every 0.6 s: 55.0 55.6 56.2 56.8 57.4 58.0 58.6 (shallows: boom + splash), 59.2 59.8 60.4 (off screen, distant), 61.0 61.6 62.2 62.8 (breakwater: boom + concrete crunch); push-off at 63.4');
  S.engine(57.3, 59.2, { rate: 11, pan: [0.7, -0.7], pass: 0.45, vel: 0.2 }); S.engine(57.6, 59.2, { rate: 9, pan: [0.8, -0.5], pass: 0.6, vel: 0.15 });
  S.toot(57.8, 0.3, { f: 247, dop: 0.05, pan: 0.2, vel: 0.12 }); S.toot(58.2, 0.45, { f: 247, dop: 0.05, pan: -0.1, vel: 0.12 });
  cue(57.4, 'sfx', 'Boats pass between its legs the other way: two diesels right to left, horn toots 57.8 / 58.2');
  [59.1, 59.5, 59.9, 60.3, 60.7].forEach((t, i) => A.whoosh(t, 0.45, { f0: 300, f1: 2200, q: 1, pan: i % 2 ? [0.8, -0.8] : [-0.8, 0.8], vel: 0.18, bus: 'sfx' }));
  [59.3, 59.9, 60.5].forEach((t, i) => { S.splash(t, { size: 0.7, vel: 0.26, pan: -0.3 + 0.3 * i, rain: 0.5 }); S.clank(t, { size: 1.3, ring: 0.3, vel: 0.14, thud: 0.1 }); });
  S.thunder(60.2, { close: 0.45, pan: -0.5, vel: 0.5 });
  cue(59.0, 'sfx', 'City near the waterspout: the roar swells, debris whooshes circle 59.1-60.7, the chain end skips 59.3 / 59.9 / 60.5');
  // ---- 63.4 the leap: only a high string note and the wind ----------------------------------------------------------------------
  A.gap(63.4, 65.4, { buses: ['solo', 'brass', 'choir', 'keys', 'perc', 'low'], fade: 0.04 });
  strings(63.4, 2.05, ['F#5', 'F#6'], { att: 0.12, rel: 0.4, bright: 0.45, vel: 0.3, vib: 0.07, voices: 4 });
  S.wind(63.3, 65.6, (T) => 0.3 + 0.7 * Math.sin(Math.PI * Math.min(1, Math.max(0, (T - 63.3) / 2.3))), { base: 900, whistle: 0.9, whistleF: 1300, vel: 0.9, bus: 'sfx' });
  A.whoosh(63.45, 1.9, { f0: 300, f1: 1100, q: 0.6, pan: [-0.3, 0.3], vel: 0.25, bus: 'sfx' });
  cue(63.4, 'HIT', 'The leap: everything drops out 63.4-65.4 except a held high violin F#5/F#6 and the rushing wind');
  // ---- 65.4 the landing; the climb to the grab ------------------------------------------------------------------------------------
  tutti(65.4, ['B1', 'F#2', 'B2', 'D3', 'F#3', 'B3', 'D4'], { vel: 1.1, tn: 'B1', cym: 0.8, tam: 0.6, tk: 1.0, len: 0.6 });
  S.boom(65.4, { f: 30, decay: 1.3, vel: 1.0, crunch: 0.4 });
  S.splash(65.42, { size: 2.6, dur: 3.0, vel: 0.9 });
  A.whoosh(65.6, 1.6, { f0: 1500, f1: 300, q: 0.6, shape: 'out', pan: [0, -0.95], vel: 0.25, bus: 'sfx' });
  A.whoosh(65.6, 1.6, { f0: 1400, f1: 280, q: 0.6, shape: 'out', pan: [0, 0.95], vel: 0.25, bus: 'sfx' });
  S.waveCrash(66.2, { build: 0.4, dur: 2.0, vel: 0.4 });
  cue(65.4, 'HIT', 'Landing waist-deep: boom + huge splash, ring wave spreading left and right, tutti B minor');
  const H6 = [[65.4, 'B1', ['B2', 'F#3', 'B3', 'D4', 'F#4']], [66.6, 'C2', ['C3', 'G3', 'C4', 'E4', 'G4']], [67.6, 'C#2', ['C#3', 'G3', 'Bb3', 'E4', 'G4']], [68.2, 'D2', ['D3', 'A3', 'D4', 'F#4', 'A4']], [68.8, 'E2', ['E3', 'G#3', 'B3', 'D4', 'G#4']]];
  ostinato(65.6, 69.3, 0.1, (i, t) => M(pick(H6, t)[1]) + [0, 12, 0, 12][i % 4], { vf: (i, t) => 0.5 + (0.35 * (t - 65.6)) / 3.7 + (i % 4 === 0 ? 0.1 : 0), bright: 0.6, sub: 0.6, dur: 0.09 });
  H6.forEach(([t, r, ch], i) => {
    const d = (i + 1 < H6.length ? H6[i + 1][0] : 69.3) - t;
    swellStr(t + (i ? 0 : 0.3), d + (i ? 0.02 : -0.28), ch, 0.6 + 0.1 * i, 0.8 + 0.12 * i, { att: 0.08, rel: 0.12, trem: 14 + i, bright: 0.55 + 0.05 * i, vel: 0.48 });
    brassChord(t, d, [M(r) + 12, M(ch[1]) - 12, M(ch[2]) - 12], { vel: 0.42, rel: 0.1, dyn: (T) => 0.4 + (0.6 * (T - t)) / d });
  });
  line(notes([[65.6, 1.02, 'F#5', 0.8], [66.6, 1.02, 'G5', 0.85], [67.6, 0.62, 'Bb5', 0.9], [68.2, 0.62, 'A5', 0.95], [68.8, 0.5, 'B5', 1.0]]), { type: 'violin', bus: 'str', vel: 0.3, pan: 0.2, rel: 0.1 });
  timp(68.2, 'A2', 0.15, { t1: 69.3, to: 1.0, curve: 1.5 });
  A.roll(68.2, 69.3, (t, v) => A.snare(t, { type: 'tight', vel: v * 0.3, bus: 'perc', verb: 0.3 }), { from: 1 / 4, to: 1 / 16, vel0: 0.2, vel1: 1 });
  A.reverseCymbal(69.3, 1.1, { vel: 0.45, bus: 'perc' }); A.riser(67.8, 69.3, { vel: 0.12, bus: 'sfx', type: 'noise' });
  for (let t = 66.0; t < 69.3 - 1e-6; t += 0.3) taiko(t, { vel: 0.4 + (t - 66) * 0.12, f: 60 });
  [[67.5, 0.3], [68.1, 0.4], [68.65, 0.5]].forEach(([t, p]) => { S.splash(t, { size: 0.5, vel: 0.24, pan: p, rain: 0.5 }); S.clank(t, { size: 1.4, ring: 0.35, vel: 0.2, thud: 0.1, pan: p }); });
  S.servo(67.2, 1.2, { f0: 220, f1: 650, vel: 0.28 }); S.servo(68.4, 0.9, { f0: 300, f1: 800, vel: 0.26, pan: 0.2 });
  cue(67.2, 'sfx', 'The hand reaches: servo whines 67.2 / 68.4; the last link skips away 67.5 / 68.1 / 68.65; chromatic climb B-C-C#-D-E into the grab');
  // ---- 69.3 the grab ------------------------------------------------------------------------------------------------------------
  tutti(69.3, ['A1', 'E2', 'A2', 'C#3', 'E3', 'A3', 'C#4', 'E4'], { vel: 1.15, tn: 'A1', cym: 0.85, tam: 0.7, tk: 1.0, len: 0.55 });
  S.clank(69.3, { size: 2.2, ring: 1.4, vel: 1.0, thud: 0.8 });
  S.boom(69.3, { f: 40, decay: 0.8, vel: 0.7, crunch: 0.7, crunchF: 800, dur: 2 });
  S.splash(69.32, { size: 0.9, vel: 0.3 });
  swellStr(69.45, 0.6, ['A2', 'E3', 'A3', 'C#4', 'E4', 'A4'], 0.7, 0.5, { att: 0.05, rel: 0.1, trem: 12, bright: 0.5, vel: 0.36 });
  cue(69.3, 'HIT', 'The hand closes on the last link: metal-on-metal clang + tutti A major (hard sync)');
}

export function act6() {
  // ---- 70.0 the chain snaps taut; the grinding 3/4 hold (bar = 1.2 s) ---------------------------------------------------------
  ostinato(70.0, 76.0, 0.2, (i) => M(['D2', 'D2', 'Eb2', 'D2', 'C#2', 'D2'][i % 6]), { vf: (i, t) => (i % 6 === 0 ? 0.75 : 0.5) + (0.1 * (t - 70)) / 6, bright: 0.45, sub: 0.9, dur: 0.18 });
  for (let k = 0, t = 70.0; t < 76.0 - 1e-6; k++, t = 70.0 + k * 0.4) brassChord(t, 0.3, ['D2', 'A2'], { vel: 0.3, att: 0.02, rel: 0.15, v: k % 3 === 0 ? 1.1 : 0.75 });
  A.reese(70.0, 6.0, 'D1', { vel: 0.22, bus: 'low', cut: 300, env: 200, move: 120, wobble: 0.8, subLevel: 0.4, drive: 1.8 });
  [[70.0, ['D3', 'F3', 'A3', 'Eb4']], [71.2, ['D3', 'F3', 'Bb3', 'D4']], [72.4, ['D3', 'G3', 'Bb3', 'D4']], [73.6, ['D3', 'F3', 'Bb3', 'F4']], [74.8, ['D3', 'E3', 'A3', 'C#4']]]
    .forEach(([t, ch], k) => swellStr(t, 1.22, ch, 0.5 + 0.08 * k, 0.65 + 0.08 * k, { att: 0.1, rel: 0.2, trem: 11, bright: 0.45, vel: 0.38 }));
  for (let k = 0; k < 5; k++) {
    const t = 70.0 + k * 1.2;
    timp(t, 'D2', 0.75 + k * 0.05); taiko(t, { vel: 0.7, f: 55 }); taiko(t + 0.6, { vel: 0.45, f: 70 });
    S.clank(t + 0.8, { size: 0.5, ring: 0.3, vel: 0.12, thud: 0, bus: 'perc' });
  }
  cue(70.0, 'music', 'Act 6, the hold: heavy 3/4 grinding ostinato D-D-Eb-D-C#-D (bar 1.2 s), low brass on every beat, distorted low synth, anvil clank on beat 3');
  S.rattle(70.0, 70.35, { rate: 40, size: 1.4, vel: 0.6, ring: 0.5 });
  S.clank(70.0, { size: 2.6, ring: 1.6, vel: 0.9, thud: 0.7 });
  S.splash(70.05, { size: 1.5, vel: 0.5, rain: 1.5 });
  S.groan(70.1, 2.2, { f: 40, vel: 0.55, drop: 0.1 });
  S.boom(70.2, { f: 28, decay: 2, vel: 0.35, crunch: 0.3, dur: 2.5 });
  S.rubble(70.2, 1.8, { vel: 0.35 });
  A.noiseHit(70.2, 1.8, { lp: 300, attack: 0.2, decay: 1.5, vel: 0.35, bus: 'sfx' });
  cue(70.0, 'HIT', 'The chain snaps taut: links bang into line, a huge clank, water thrown off; feet plough the seabed 70.2-72.0');
  S.steam(72.0, 1.0, { pan: -0.4, vel: 0.45 }); S.steam(72.4, 0.8, { pan: 0.5, vel: 0.35, whistle: 4200 }); S.steam(73.0, 0.9, { pan: -0.1, vel: 0.3 });
  [72.25, 72.95].forEach((t) => { S.clank(t, { size: 0.5, ring: 0.2, vel: 0.5, thud: 0.3 }); A.noiseHit(t, 0.08, { hp: 1500, decay: 60, vel: 0.4, bus: 'sfx' }); });
  S.flicker(73.0, 0.5, { vel: 0.22 });
  cue(72.0, 'sfx', 'Strain: steam hisses 72.0 / 72.4 / 73.0, armour cracks 72.25 / 72.95, visor flicker buzz 73.0-73.5');
  swellStr(73.6, 2.4, ['D5', 'F5', 'A5', 'D6'], 0.4, 0.9, { att: 0.4, trem: 13, bright: 0.5, vel: 0.28, rel: 0.2 });
  brassChord(73.6, 2.4, ['D2', 'A2', 'D3'], { vel: 0.35, dyn: (T) => 0.3 + (0.7 * (T - 73.6)) / 2.4, rel: 0.15 });
  S.creak(74.0, 1.4, { f: 200, q: 16, vel: 0.3 }); S.groan(74.2, 1.6, { f: 52, vel: 0.35 }); S.thunder(74.6, { close: 0.3, pan: -0.5, vel: 0.45 });
  cue(73.6, 'music', 'Looking up at the city like a stone sky: high strings swell over the grind, the waterspout roar grows');
  // ---- 76.0 winding the chain round the lighthouse: the rising choir -------------------------------------------------------------
  const climb = [[76.0, ['D4', 'F4', 'A4'], 'D2'], [76.6, ['Eb4', 'G4', 'Bb4'], 'Eb2'], [77.2, ['F4', 'A4', 'C5'], 'F2'], [77.8, ['G4', 'B4', 'D5'], 'G2'], [78.2, ['A4', 'C#5', 'E5'], 'A2']];
  climb.forEach(([t, ch, r], i) => {
    const d = (i + 1 < climb.length ? climb[i + 1][0] : 78.6) - t + 0.05;
    choir(t, d, ch, { vowel: 'a', att: 0.12, rel: 0.2, vel: 0.42 + i * 0.07 });
    choir(t, d, ch.map((n) => M(n) - 12), { vowel: 'o', att: 0.12, rel: 0.2, vel: 0.34 + i * 0.05, voices: 3 });
    strings(t, d, [r, ...ch.map((n) => M(n) - 12)], { att: 0.08, rel: 0.15, trem: 14, bright: 0.55 + i * 0.05, vel: 0.44 + i * 0.05 });
    brassChord(t, d, [M(r) + 12, M(ch[0]) - 12, M(ch[2]) - 12], { vel: 0.42 + i * 0.06, rel: 0.12 });
  });
  ostinato(76.0, 78.6, 0.2, (i, t) => M(pick(climb, t)[2]) + [0, 12][i % 2], { vf: (i) => 0.58 + i * 0.015, bright: 0.55, sub: 0.8, dur: 0.17 });
  timp(77.2, 'A2', 0.15, { t1: 78.6, to: 1.0 }); A.reverseCymbal(78.6, 1.2, { vel: 0.45, bus: 'perc' });
  cue(76.0, 'music', 'Winding the chain: rising choir-like chords Dm-Eb-F-G-A (76.0 / 76.6 / 77.2 / 77.8 / 78.2) with strings and brass, timpani roll');
  S.rattle(76.0, 78.6, { rate: 16, size: 1.3, vel: 0.36, ring: 0.35, shape: (u) => 0.6 + 0.4 * Math.sin(Math.PI * u) });
  S.screech(76.3, 1.6, { f: 500, vel: 0.22 });
  S.groan(76.4, 2.0, { f: 70, drop: 0.1, vel: 0.42, pan: 0.3 }); S.creak(76.8, 1.4, { f: 360, q: 12, pan: 0.35, vel: 0.32 });
  S.rubble(77.4, 0.8, { vel: 0.3, pan: 0.3 });
  S.clank(78.2, { size: 1.5, ring: 0.8, vel: 0.5, thud: 0.6, pan: 0.3 }); S.boom(78.2, { f: 34, decay: 0.8, vel: 0.35, crunch: 0.6, dur: 2 });
  cue(76.0, 'sfx', 'Winding: continuous chain rattle and scrape on stone, the lighthouse groans and creaks, masonry crumbles 77.4, it bends and holds with a crack at 78.2');
  // ---- 78.6 the waterspout passes by metres: the climax ---------------------------------------------------------------------------
  tutti(78.6, ['Bb1', 'F2', 'Bb2', 'D3', 'F3', 'Bb3', 'D4', 'F4'], { vel: 1.1, tn: 'Bb1', cym: 0.85, tam: 0.8, tk: 1.0, len: 0.4 });
  const CL = [[78.6, 1.0, ['Bb3', 'D4', 'F4', 'Bb4', 'D5', 'F5'], ['Bb1', 'Bb2', 'F3', 'Bb3', 'D4', 'F4', 'Bb4', 'D5'], ['Bb2', 'F3', 'Bb3', 'D4', 'F4']],
    [79.6, 0.4, ['G3', 'Bb3', 'D4', 'G4', 'Bb4', 'D5'], ['G1', 'G2', 'D3', 'G3', 'Bb3', 'D4', 'G4', 'Bb4'], ['G2', 'D3', 'G3', 'Bb3', 'D4']],
    [80.0, 0.6, ['A3', 'C#4', 'E4', 'A4', 'C#5', 'E5'], ['A1', 'A2', 'E3', 'A3', 'C#4', 'E4', 'A4', 'C#5'], ['A2', 'E3', 'A3', 'C#4', 'E4']]];
  CL.forEach(([t, d, ch, st, br], i) => {
    choir(t, d + 0.02, ch, { vowel: 'a', att: 0.06, rel: 0.12, vel: 0.72 + 0.03 * i });
    strings(t, d + 0.02, st, { att: 0.03, rel: 0.1, trem: 16, bright: 0.75, vel: 0.58 });
    brassChord(t, d, br, { vel: 0.66, rel: 0.1, dyn: i === 2 ? (T) => 0.8 + (0.4 * (T - t)) / d : undefined });
  });
  const top = notes([[78.6, 0.42, 'D5', 1.1], [79.0, 0.42, 'F5', 1.1], [79.4, 0.22, 'Bb5', 1.15], [79.6, 0.42, 'Bb5', 1.1], [80.0, 0.6, 'A5', 1.2]]);
  line(top, { type: 'brass', bus: 'brass', vel: 0.5, pan: 0.1, rel: 0.08 });
  line(top.map((x) => ({ ...x, n: M(x.n) - 12 })), { type: 'horn', bus: 'brass', vel: 0.55, pan: -0.15, rel: 0.08 });
  line(top.map((x) => ({ ...x, n: M(x.n) + 12 })), { type: 'violin', bus: 'str', vel: 0.25, pan: 0.25, rel: 0.08 });
  A.whoosh(78.45, 2.4, { f0: 150, f1: 900, q: 0.5, shape: 'swell', pan: [-0.95, 0.95], vel: 0.5, bus: 'sfx' });
  A.noiseHit(78.6, 2.0, { lp: 220, attack: 0.7, decay: 0.6, vel: 0.45, bus: 'sfx' });
  timp(79.6, 'G2', 0.8); timp(80.0, 'A2', 0.3, { t1: 80.6, to: 1.0 });
  [79.6, 80.0, 80.2, 80.4].forEach((t, i) => taiko(t, { vel: 0.6 + 0.1 * i, f: 58 }));
  S.screech(79.1, 0.4, { f: 1200, vel: 0.22, pan: -0.2 }); S.clank(79.15, { size: 0.6, ring: 0.3, vel: 0.28, thud: 0.2, pan: -0.2 });
  A.whoosh(79.3, 0.6, { f0: 300, f1: 2500, pan: [0.3, -0.8], vel: 0.22, bus: 'sfx' }); A.whoosh(79.7, 0.5, { f0: 300, f1: 2500, pan: [-0.2, 0.9], vel: 0.2, bus: 'sfx' });
  S.thunder(79.0, { close: 0.6, vel: 0.5, pan: 0.3 });
  cue(78.6, 'HIT', 'The waterspout passes the city by metres: climax Bb major (choir, brass, strings, tam-tam), trumpets + horns sing D5 F5 Bb5 | Bb5 | A5 -> Gm 79.6 -> A 80.0; the roar sweeps left to right 78.6-80.8; windmill sails ripped off 79.1');
  // ---- 80.6 the release ----------------------------------------------------------------------------------------------------------
  S.rattle(80.6, 81.7, { rate: 18, size: 1.2, vel: 0.35, ring: 0.35, shape: (u) => Math.pow(1 - u, 2) });
  S.groan(80.6, 1.4, { f: 60, drop: 0.3, peak: 0.1, vel: 0.4 });
  A.downlifter(80.6, 1.4, { vel: 0.3, bus: 'sfx' });
  S.creak(81.0, 0.8, { f: 300, q: 12, vel: 0.22 }); A.thud(81.6, { f0: 70, vel: 0.2, bus: 'sfx' });
  strings(80.75, 0.8, ['A2', 'E3', 'A3', 'D4', 'G4'], { att: 0.35, rel: 0.3, bright: 0.3, vel: 0.3 });
  strings(81.5, 0.55, ['A2', 'E3', 'A3', 'C#4', 'G4'], { att: 0.2, rel: 0.3, bright: 0.32, vel: 0.3 });
  line(notes([[80.8, 0.75, 'D4', 0.6], [81.55, 0.5, 'C#4', 0.6]]), { type: 'horn', vel: 0.4 });
  gliss(81.4, 81.98, 'A3', 'A5', { vel: 0.25 });
  timp(81.2, 'A2', 0.05, { t1: 82.0, to: 0.3 });
  cue(80.6, 'HIT', 'Release: the climax cuts off, the chain shudders and slackens (rattle dying away), downlifter, an A7sus4 pianissimo breath; the city stops');
}

export function act7() {
  // ---- 82.0 the clouds open: the whole theme, warm (bars 82.0 / 83.6 / 85.2 / 86.8, the final chord at 88.2) ------------------
  A.reverseCymbal(82.0, 1.0, { vel: 0.2, bus: 'perc' }); A.crash(82.0, { vel: 0.18, bus: 'perc', dur: 3, verb: 0.5 });
  A.whoosh(81.6, 1.4, { f0: 800, f1: 3000, vel: 0.08, bus: 'sfx' });
  timp(82.0, 'D2', 0.4);
  const fin = notes([[82.0, 0.43, 'F#4', 0.85], [82.4, 0.43, 'A4', 0.9], [82.8, 0.83, 'D5', 1.0], [83.6, 0.63, 'C#5', 0.95], [84.2, 0.23, 'B4', 0.85], [84.4, 0.83, 'A4', 0.85],
    [85.2, 0.43, 'G4', 0.85], [85.6, 0.43, 'B4', 0.9], [86.0, 0.63, 'E5', 1.0], [86.6, 0.23, 'D5', 0.9], [86.8, 0.63, 'D5', 0.95], [87.4, 0.82, 'C#5', 0.9], [88.2, 2.6, 'D5', 0.85]]);
  line(fin, { type: 'horn', vel: 0.55, verb: 0.45, pan: -0.1 });
  line(fin.map((x) => ({ ...x, n: M(x.n) + 12 })), { type: 'violin', bus: 'str', vel: 0.28, pan: 0.2 });
  line(fin.map((x) => ({ ...x, n: M(x.n) + 12 })), { type: 'flute', vel: 0.24, pan: 0.15 });
  cue(82.0, 'music', 'Act 7, the clouds open: the whole theme, warm and major, horn + violins + flute (F#4 A4 D5 | C#5 B4 A4 | G4 B4 E5 D5 | D5 C#5 | D5), bass D-C#-B-A');
  swellStr(82.0, 1.62, ['D2', 'A2', 'D3', 'F#3', 'A3', 'D4', 'F#4'], 0.55, 0.85, { att: 0.5, rel: 0.5, bright: 0.55, vel: 0.5 });
  strings(83.6, 1.62, ['C#2', 'A2', 'E3', 'A3', 'C#4', 'E4'], { att: 0.25, rel: 0.5, bright: 0.55, vel: 0.5 });
  strings(85.2, 1.62, ['B1', 'B2', 'G3', 'D4', 'E4', 'G4'], { att: 0.25, rel: 0.5, bright: 0.55, vel: 0.5 });
  strings(86.8, 0.62, ['A1', 'A2', 'E3', 'G3', 'D4'], { att: 0.2, rel: 0.4, bright: 0.5, vel: 0.48 });
  strings(87.4, 0.82, ['A1', 'A2', 'E3', 'G3', 'C#4'], { att: 0.15, rel: 0.5, bright: 0.5, vel: 0.48 });
  strings(88.2, 2.4, ['D2', 'A2', 'D3', 'F#3', 'A3', 'D4', 'E4', 'F#4', 'A4'], { att: 0.3, rel: 1.4, bright: 0.45, vel: 0.5, dyn: (u) => 1 - 0.45 * u });
  brassChord(82.0, 1.6, ['D3', 'F#3', 'A3'], { vel: 0.22, dyn: (T) => 0.5 + 0.5 * Math.min(1, (T - 82) / 0.8) });
  brassChord(88.2, 2.4, ['D3', 'F#3', 'A3'], { vel: 0.2, rel: 1.0, dyn: (T) => 1 - 0.5 * Math.min(1, (T - 88.2) / 2.4) });
  arpeggio(82.0, 83.6, 0.2, ['D3', 'A3', 'D4', 'F#4', 'A4'], { vel: 0.3 });
  arpeggio(83.6, 85.2, 0.2, ['C#3', 'A3', 'C#4', 'E4', 'A4'], { vel: 0.3 });
  arpeggio(85.2, 86.8, 0.2, ['B2', 'G3', 'B3', 'D4', 'E4'], { vel: 0.3 });
  arpeggio(86.8, 88.2, 0.2, ['A2', 'E3', 'G3', 'C#4', 'E4'], { vel: 0.28 });
  ['D2', 'A2', 'D3', 'F#3', 'A3', 'D4', 'F#4', 'A4', 'D5'].forEach((n, i) => A.pluck(88.2 + i * 0.06, n, { type: 'harp', dur: 3.2, vel: 0.32, pan: -0.3, bright: 0.5, bus: 'keys', verb: 0.5 }));
  [[82.0, ['D3', 'A3', 'F#4']], [83.6, ['C#3', 'A3', 'E4']], [85.2, ['B2', 'G3', 'E4']], [86.8, ['A2', 'G3', 'D4']], [87.4, ['A2', 'G3', 'C#4']], [88.25, ['D3', 'A3', 'F#4', 'D5']]]
    .forEach(([t, ch]) => ch.forEach((n) => piano(t, n, { vel: 0.3, dur: t > 88 ? 3 : 1.5 })));
  choir(82.0, 5.4, ['D4', 'F#4', 'A4'], { vowel: 'o', att: 1.5, rel: 0.3, vel: 0.22 });
  choir(87.4, 0.82, ['C#4', 'E4', 'A4'], { vowel: 'o', att: 0.2, rel: 0.2, vel: 0.22 });
  choir(88.2, 2.6, ['D4', 'F#4', 'A4'], { vowel: 'o', att: 0.3, rel: 1.2, vel: 0.24 });
  line(notes([[82.0, 1.63, 'D2'], [83.6, 1.63, 'C#2'], [85.2, 1.63, 'B1'], [86.8, 1.42, 'A1'], [88.2, 2.6, 'D2']]), { type: 'cello', bus: 'str', vel: 0.3, rel: 1.0 });
  A.sub(88.2, 2.6, 'D1', { vel: 0.16, bus: 'low', attack: 0.3, release: 1.2 });
  [['A6', 82.05], ['D7', 82.25]].forEach(([n, t]) => glock(t, n, { vel: 0.16, soft: 0.8 }));
  // ---- the gull, the visor ----------------------------------------------------------------------------------------------------
  S.gull(83.2, { calls: 2, f: 900, dist: 0.85, pan: -0.6, vel: 0.1 });
  S.gull(86.4, { calls: 3, f: 880, dist: 0.2, pan: 0.2, vel: 0.36, first: 0.28 });
  // the wings on the picture (mechanim.gull_home, s42): downstrokes 86.55 / 86.88 coming in, the braking beats 87.10 / 87.34 over
  // the nest (the loudest), the fold after the touchdown at 87.45 a soft rustle. ph0 0 at rate 5: each whump peaks 0.1 s in.
  [[86.55, 0.24, 0.5], [86.88, 0.17, 0.35], [87.1, 0.34, 0.2], [87.34, 0.36, 0.12]].forEach(([tt, v, p]) => S.flaps(tt - 0.1, 0.2, { rate: 5, ph0: 0, pan: [p, p], vel: v }));
  S.flaps(87.5, 0.36, { rate: 9, ph0: 0.5, pan: [0.1, 0.1], vel: 0.07 });
  S.chick(87.0, { n: 4, vel: 0.12, pan: 0.1 }); S.chick(87.55, { n: 2, vel: 0.1, pan: 0.1 });
  cue(86.4, 'sfx', 'The gull returns to the nest: call at 86.4, wingbeats on the picture 86.55 / 86.88, braking beats 87.1 / 87.34, touchdown 87.45 and the fold, chick peeps 87.0 / 87.55');
  S.powerDown(88.2, 1.8, { from: 'A5', to: 'D5', vel: 0.16 });
  [['D7', 88.45], ['A6', 88.75], ['F#6', 89.05]].forEach(([n, t]) => glock(t, n, { vel: 0.2, soft: 0.8 }));
  S.gull(90.2, { calls: 2, f: 920, dist: 0.9, pan: -0.5, vel: 0.08 });
  cue(88.2, 'HIT', 'The visor dims: soft descending tone A5 -> D5, the boot chime reversed (D7 A6 F#6 at 88.45 / 88.75 / 89.05); the final D(add9) chord rings into the tail to 92.0');
}
