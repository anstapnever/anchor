// ANCHOR score, part 1. Act 1 (0-14 s): High Harbor at sunrise, the theme (flute, then horn), harp, strings, gulls,
// wind chimes, the dive down the chain, the port, the sleeping mech, the anchor under water.
// Act 2 (14-30 s): the storm builds: D-minor ostinato, the theme in minor on horns, the bell alarm, the collar,
// the waterspout forms, lightning on the chain, the discharge running down, the shackle boiling.
import { A, M, strings, spic, line, piano, glock, timp, taiko } from './lib.mjs';
import * as S from './sfx.mjs';
import { cue, phrase, notes, gliss, arpeggio, ostinato, brassChord, swellStr, tutti, THEME_A, THEME_B } from './common.mjs';

export function act1() {
  // ---- intro bloom and phrase A (bars 1.0 / 2.6 / 4.2 / 5.8, quarter = 0.4 s) --------------------------------------------
  swellStr(0.0, 2.6, ['D3', 'A3', 'E4', 'F#4', 'A4'], 0.25, 0.75, { att: 1.0, rel: 0.8, bright: 0.35, vel: 0.42 });
  gliss(0.05, 0.95, 'D3', 'A5', { vel: 0.3 });
  cue(0.0, 'music', 'Act 1: strings bloom on D(add9), harp glissando up, wind and wind chimes over the city');
  line(phrase(1.0, 0.4, THEME_A, { tr: 12, v: (i) => [0.7, 0.75, 0.85, 0.8, 0.7, 0.75, 0.7, 0.75, 0.9, 0.8, 0.85][i], last: 1.75 }), { type: 'flute', vel: 0.42, pan: 0.1, verb: 0.45 });
  cue(1.0, 'music', 'Theme, phrase A, solo flute (F#5 A5 D6 | C#6 B5 A5 | G5 B5 E6 D6 | C#6), harp arpeggios');
  strings(2.6, 1.65, ['C#3', 'A3', 'E4', 'A4'], { att: 0.4, rel: 0.6, bright: 0.4, vel: 0.4 });
  strings(4.2, 1.65, ['B2', 'G3', 'D4', 'E4'], { att: 0.4, rel: 0.6, bright: 0.42, vel: 0.42 });
  swellStr(5.8, 0.85, ['A2', 'E3', 'A3', 'D4'], 0.7, 0.9, { att: 0.3, rel: 0.4, bright: 0.45, vel: 0.44 });
  swellStr(6.6, 0.85, ['A2', 'E3', 'A3', 'C#4', 'E4'], 0.85, 1.2, { att: 0.2, rel: 0.6, bright: 0.55, vel: 0.46 });
  line(notes([[0.3, 2.33, 'D2', 0.55], [2.6, 1.63, 'C#2', 0.6], [4.2, 1.63, 'B1', 0.62], [5.8, 1.62, 'A1', 0.7]]), { type: 'cello', bus: 'str', vel: 0.32, verb: 0.3, glide: 0.12 });
  arpeggio(1.0, 2.6, 0.2, ['D3', 'A3', 'D4', 'F#4', 'A4'], { vel: 0.3 });
  arpeggio(2.6, 4.2, 0.2, ['C#3', 'A3', 'C#4', 'E4', 'A4'], { vel: 0.3 });
  arpeggio(4.2, 5.8, 0.2, ['B2', 'G3', 'B3', 'D4', 'E4'], { vel: 0.3 });
  gliss(5.8, 7.3, 'A6', 'A2', { vel: 0.32, pan: -0.2 });
  // ---- phrase B on the horn: the port at dawn (bars 7.4 / 9.0 / 10.6 / 12.2) ------------------------------------------------
  line(phrase(7.4, 0.4, THEME_B.slice(0, 10), { v: (i) => [0.75, 0.8, 0.9, 0.85, 0.8, 0.9, 0.8, 0.75, 0.75, 0.7][i] }).concat(notes([[12.2, 1.1, 'D5', 0.7]])),
    { type: 'horn', vel: 0.5, pan: -0.1, verb: 0.4 });
  cue(7.4, 'music', 'Port wide: theme phrase B on solo horn over full strings and piano arpeggios (F#4 A4 D5 | E5 F#5 G5 | F#5 E5 D5 C#5)');
  strings(7.4, 1.65, ['B2', 'F#3', 'A3', 'D4', 'F#4'], { att: 0.25, rel: 0.6, bright: 0.55, vel: 0.5 });
  strings(9.0, 1.65, ['G2', 'D3', 'B3', 'F#4', 'A4'], { att: 0.3, rel: 0.6, bright: 0.55, vel: 0.5 });
  strings(10.6, 0.82, ['E3', 'B3', 'D4', 'G4'], { att: 0.3, rel: 0.4, bright: 0.5, vel: 0.46 });
  strings(11.4, 0.42, ['A2', 'E3', 'G3', 'D4'], { att: 0.15, rel: 0.3, bright: 0.45, vel: 0.44 });
  strings(11.8, 0.42, ['A2', 'E3', 'G3', 'C#4'], { att: 0.1, rel: 0.4, bright: 0.45, vel: 0.44 });
  swellStr(12.2, 1.2, ['Bb2', 'F3', 'A3', 'D4'], 0.8, 0.6, { att: 0.25, rel: 0.5, bright: 0.35, vel: 0.46 });
  swellStr(13.4, 0.62, ['A2', 'E3', 'G3', 'C#4', 'Bb4'], 0.5, 1.1, { att: 0.2, rel: 0.25, bright: 0.45, vel: 0.44, trem: 12 });
  line(notes([[7.4, 1.63, 'B1', 0.7], [9.0, 1.63, 'G1', 0.7], [10.6, 0.83, 'E2', 0.65], [11.4, 0.83, 'A1', 0.65], [12.2, 1.23, 'Bb1', 0.7], [13.4, 0.62, 'A1', 0.75]]),
    { type: 'cello', bus: 'str', vel: 0.34, verb: 0.3, glide: 0.1 });
  [[7.4, 1.6, 'B1'], [9.0, 1.6, 'G1'], [10.6, 0.8, 'E2'], [11.4, 0.8, 'A1'], [12.2, 1.2, 'Bb1'], [13.4, 0.6, 'A1']].forEach(([t, d, n]) => A.sub(t, d, n, { vel: 0.16, bus: 'low', attack: 0.15, release: 0.25 }));
  const pa = (t0, t1, ch) => { for (let i = 0, t = t0; t < t1 - 1e-6; i++, t = t0 + i * 0.2) piano(t, ch[[0, 1, 2, 3, 4, 3, 2, 1][i % 8] % ch.length], { vel: 0.3 * (i % 4 === 0 ? 1 : 0.8), dur: 0.5 }); };
  pa(7.4, 9.0, ['B2', 'F#3', 'A3', 'D4', 'F#4']); pa(9.0, 10.6, ['G2', 'D3', 'B3', 'F#4', 'A4']); pa(10.6, 11.4, ['E2', 'B2', 'E3', 'G3', 'D4']); pa(11.4, 12.2, ['A2', 'E3', 'G3', 'C#4', 'D4']);
  [['Bb1', 12.2], ['F2', 12.5], ['D3', 12.8], ['A3', 13.1], ['A1', 13.4], ['E2', 13.6], ['Bb2', 13.8]].forEach(([n, t]) => piano(t, n, { vel: 0.35, dur: 1.2 }));
  [['F#6', 9.6], ['A6', 9.8], ['D7', 10.0]].forEach(([n, t]) => glock(t, n, { vel: 0.22, soft: 0.8, pan: 0.25 }));
  timp(13.2, 'A2', 0.08, { t1: 14.0, to: 0.5 });
  cue(11.2, 'music', 'Under water: score low-passed 11.2-14.0; deceptive cadence Bbmaj7 at 12.2, A7(b9) at 13.4, timpani roll into act 2');

  // ---- sound: the sky, the street, the dive, the port, the head, the anchor -------------------------------------------------
  S.chimes(0.3, 4.5, { gap: 0.42, vel: 0.12 });
  S.chimes(3.0, 4.6, { gap: 0.3, vel: 0.14, notes: ['A5', 'B5', 'D6', 'E6', 'F#6'] });
  S.gull(1.3, { calls: 3, f: 820, pan: 0.6, dist: 0.55, vel: 0.22 });
  S.gull(2.35, { calls: 2, f: 900, pan: -0.55, dist: 0.65, vel: 0.16 });
  [3.0, 3.45, 3.9, 4.35].forEach((t) => A.whoosh(t, 0.4, { f0: 300, f1: 1400, q: 0.9, pan: [0.7, -0.7], vel: 0.18, bus: 'foley', verb: 0.1 }));
  S.flaps(3.0, 1.6, { rate: 9, pan: [0.35, 0.15], vel: 0.18 });
  S.churchBell([3.3], 'D4', { vel: 0.07, pan: -0.45 });
  cue(3.0, 'sfx', 'Street: windmill sails sweep past (whooshes 3.0 / 3.45 / 3.9 / 4.35), laundry flapping, distant bell toll at 3.3');
  for (let t = 4.6, gap = 0.36; t < 7.25; t += gap, gap *= 0.9) A.whoosh(t, 0.28, { f0: 200, f1: 1800, q: 1.1, pan: [-0.3, 0.3], vel: 0.15 + (t - 4.6) * 0.03, bus: 'sfx', verb: 0.1 });
  A.whoosh(4.6, 2.8, { f0: 250, f1: 2500, q: 0.6, shape: 'in', pan: [0, 0], vel: 0.25, bus: 'sfx' });
  cue(4.6, 'sfx', 'Dive along the chain: link pass-bys accelerating 4.6 -> 7.3, air rush building, cut clean at 7.4; harp glissando down 5.8-7.3');
  S.lap(7.3, 11.4, { vel: 0.35 });
  S.gull(7.9, { calls: 4, f: 860, pan: -0.35, dist: 0.45, vel: 0.24 });
  S.gull(8.9, { calls: 2, f: 940, pan: 0.55, dist: 0.7, vel: 0.14 });
  S.engine(7.5, 11.0, { rate: 7, pan: [0.6, 0.35], pass: 0.95, vel: 0.06 });
  S.gull(9.75, { calls: 1, first: 0.34, f: 780, pan: 0.1, dist: 0.1, vel: 0.22 });
  S.chick(10.15, { n: 3, pan: 0.15, vel: 0.12 }); S.chick(10.7, { n: 2, pan: 0.1, vel: 0.1 });
  cue(9.6, 'sfx', "Mech head macro: the nesting gull calls 9.75, chick peeps 10.15 / 10.7; music-box glock F#6-A6-D7 9.6 / 9.8 / 10.0 (the later 'boot' motif)");
  S.underBed(11.2, 14.05, { vel: 0.55, bubbles: 7 });
  S.groan(12.3, 1.6, { f: 64, vel: 0.12, pan: -0.2, peak: 0.5 });
}

// harmony of the act-2 ostinato: [root, quality] by time
const ROOT = (t) => (t < 17.2 ? ['D2', 'm'] : t < 18.8 ? ['A1', 'M'] : t < 20.4 ? ['E2', 'h'] : t < 22.0 ? ['A1', 'M'] : t < 23.6 ? ['D2', 'm'] : ['A1', 'M']);
const PAT = { m: [0, 12, 0, 12, 0, 15, 0, 14], M: [0, 12, 0, 12, 0, 16, 0, 14], h: [0, 12, 0, 12, 0, 15, 0, 13] };

export function act2() {
  // ---- the ostinato: 8ths, then 16ths from the waterspout on ---------------------------------------------------------------
  ostinato(14.0, 22.0, 0.2, (i, t) => { const [r, q] = ROOT(t); return M(r) + PAT[q][i % 8]; },
    { vf: (i, t) => (0.32 + (0.25 * (t - 14)) / 8) * (i % 8 === 0 ? 1.25 : i % 2 ? 0.8 : 1), bright: 0.45, sub: 0.5 });
  ostinato(22.0, 24.4, 0.1, (i, t) => { const [r, q] = ROOT(t); return M(r) + [0, 12, 0, 12, 0, q === 'm' ? 15 : 16, 0, 12][i % 8]; },
    { vf: (i) => 0.5 + (i % 4 === 0 ? 0.15 : 0), bright: 0.6, sub: 0.6, dur: 0.09 });
  ostinato(24.6, 28.0, 0.1, (i) => M('D2') + [0, 12, 0, 12, 0, 13, 0, 12][i % 8], { vf: (i, t) => 0.45 + (0.15 * (t - 24.6)) / 3.4 + (i % 4 === 0 ? 0.1 : 0), bright: 0.6, sub: 0.6, dur: 0.09 });
  ostinato(28.0, 30.0, 0.2, (i) => (i % 2 ? M('Eb2') : M('D2')), { vf: (i, t) => 0.35 + (0.3 * (t - 28)) / 2, bright: 0.3, sub: 0.8 });
  cue(14.0, 'music', 'Act 2: D-minor string ostinato in 8ths (16ths from 22.0), tremolo strings, timpani; the storm wall');
  swellStr(14.0, 1.65, ['D3', 'A3', 'D4', 'F4'], 0.2, 0.6, { att: 0.6, trem: 10, bright: 0.4, vel: 0.36 });
  swellStr(15.6, 1.65, ['D3', 'F3', 'A3', 'D4'], 0.5, 0.7, { trem: 10, bright: 0.45, vel: 0.36 });
  swellStr(17.2, 1.65, ['A2', 'E3', 'G3', 'C#4', 'Bb4'], 0.6, 0.8, { trem: 11, bright: 0.5, vel: 0.38 });
  swellStr(18.8, 1.65, ['E3', 'G3', 'Bb3', 'D4'], 0.65, 0.85, { trem: 11, bright: 0.5, vel: 0.4 });
  swellStr(20.4, 1.65, ['A2', 'E3', 'A3', 'C#4', 'E4'], 0.7, 1.1, { trem: 13, bright: 0.55, vel: 0.42 });
  swellStr(22.0, 1.62, ['D3', 'A3', 'D4', 'F4', 'A4'], 0.9, 1.1, { trem: 14, bright: 0.65, vel: 0.45 });
  swellStr(23.6, 0.82, ['A2', 'G3', 'C#4', 'E4', 'A4'], 1.0, 1.25, { trem: 15, bright: 0.7, vel: 0.46, rel: 0.1 });
  // ---- the theme turns minor: low horns + cellos (15.6), then trumpets + violins (22.0), broken by the lightning ------------
  const lo = notes([[15.6, 0.43, 'F3', 0.75], [16.0, 0.43, 'A3', 0.8], [16.4, 0.83, 'D4', 0.9], [17.2, 0.63, 'C#4', 0.85], [17.8, 0.23, 'Bb3', 0.8], [18.0, 0.83, 'A3', 0.85],
    [18.8, 0.43, 'G3', 0.8], [19.2, 0.43, 'Bb3', 0.85], [19.6, 0.63, 'E4', 0.95], [20.2, 0.23, 'D4', 0.9], [20.4, 1.6, 'C#4', 1.0]]);
  line(lo, { type: 'horn', bus: 'brass', vel: 0.55, pan: -0.15 });
  line(lo.map((x) => ({ ...x, n: M(x.n) - 12 })), { type: 'cello', bus: 'str', vel: 0.3, pan: -0.25 });
  cue(15.6, 'music', 'The theme in D minor on low horns and cellos (F3 A3 D4 | C#4 Bb3 A3 | G3 Bb3 E4 D4 | C#4)');
  const hi = notes([[22.0, 0.43, 'F4', 0.95], [22.4, 0.43, 'A4', 1.0], [22.8, 0.83, 'D5', 1.1], [23.6, 0.43, 'C#5', 1.05], [24.0, 0.42, 'Bb4', 1.1]]);
  line(hi, { type: 'brass', bus: 'brass', vel: 0.42, pan: 0.1 });
  line(hi.map((x) => ({ ...x, n: M(x.n) + 12 })), { type: 'violin', bus: 'str', vel: 0.3, pan: 0.2 });
  line(hi.map((x) => ({ ...x, n: M(x.n) - 12 })), { type: 'horn', bus: 'brass', vel: 0.38, pan: -0.2 });
  tutti(24.4, ['D2', 'Eb3', 'G3', 'Bb3', 'Eb4', 'G4'], { vel: 1, tn: 'D2', cym: 0.6, tam: 0.5, tk: 0.8, len: 0.55 });
  swellStr(24.5, 1.3, ['D3', 'Eb3', 'G3', 'Bb3', 'Eb4'], 1.0, 0.5, { att: 0.05, trem: 16, bright: 0.6, vel: 0.4 });
  cue(24.4, 'HIT', 'Lightning strikes the chain at the collar: close thunder crack, electric crackle 24.4-25.8, tutti hit on Eb/D, tam-tam');
  brassChord(25.2, 2.8, ['D2', 'A2', 'D3'], { vel: 0.4, dyn: (T) => 0.4 + (0.6 * (T - 25.2)) / 2.8 });
  ['D6', 'C#6', 'C6', 'B5', 'Bb5', 'A5', 'Ab5', 'G5', 'F#5', 'F5', 'E5'].forEach((n, i) => {
    const t = 25.8 + i * 0.2;
    spic(t, n, { dur: 0.18, vel: 0.35 + i * 0.02, bright: 0.8, pan: 0.3 - i * 0.05 });
    spic(t, M(n) - 12, { dur: 0.18, vel: 0.3 + i * 0.02, bright: 0.7, pan: 0.2 - i * 0.04 });
    piano(t, M(n) - 36, { vel: 0.45, dur: 0.3 });
  });
  swellStr(28.0, 2.0, ['Eb5', 'D6', 'Eb6'], 0.3, 1.2, { att: 0.1, trem: 16, bright: 0.6, vel: 0.33, rel: 0.12 });
  swellStr(28.0, 2.0, ['D2', 'Eb2', 'A2'], 0.3, 1.1, { att: 0.3, trem: 12, bright: 0.4, vel: 0.4, rel: 0.12 });
  brassChord(28.0, 2.0, ['D2', 'Eb2', 'A2'], { vel: 0.4, dyn: (T) => 0.3 + 0.8 * Math.pow((T - 28) / 2, 2), rel: 0.1 });
  A.sub(28.0, 2.0, 'D1', { vel: 0.3, bus: 'low', attack: 0.6, release: 0.08 });
  // ---- percussion ------------------------------------------------------------------------------------------------------------
  timp(14.0, 'D2', 0.75); timp(14.05, 'D2', 0.06, { t1: 15.6, to: 0.35 });
  timp(15.6, 'D2', 0.6); timp(17.2, 'A2', 0.6); timp(18.8, 'E2', 0.6); timp(20.4, 'A2', 0.7); timp(21.2, 'A2', 0.15, { t1: 22.0, to: 0.6 }); timp(22.0, 'D2', 0.9);
  timp(26.6, 'D2', 0.12, { t1: 28.0, to: 0.7 }); timp(28.0, 'D2', 0.1, { t1: 30.0, to: 0.9, curve: 2 });
  [17.2, 18.8].forEach((t) => taiko(t, { vel: 0.55, f: 60 }));
  for (let t = 20.4; t < 22.0 - 1e-6; t += 0.4) taiko(t, { vel: 0.45 + (t - 20.4) * 0.15, f: 62 });
  for (let i = 0; i < 12; i++) { const c = 'X.x.X.xxX.xx'[i]; if (c !== '.') taiko(22.0 + i * 0.2, { vel: c === 'X' ? 0.8 : 0.5, f: c === 'X' ? 58 : 75 }); }
  for (let i = 0; i < 8; i++) A.tom(23.6 + i * 0.1, ['A2', 'A2', 'F2', 'F2', 'D2', 'D2', 'A1', 'A1'][i], { vel: 0.35 + i * 0.05, bus: 'perc', verb: 0.3 });
  for (let t = 25.2; t < 28.0 - 1e-6; t += 0.4) taiko(t, { vel: 0.4 + (t - 25.2) * 0.12, f: 60 });
  A.roll(26.4, 28.0, (t, v) => A.snare(t, { type: 'tight', vel: v * 0.3, bus: 'perc', verb: 0.3 }), { from: 1 / 4, to: 1 / 16, vel0: 0.2, vel1: 0.9 });
  A.reverseCymbal(24.4, 1.4, { vel: 0.35, bus: 'perc' });
  A.reverseCymbal(30.0, 1.6, { vel: 0.4, bus: 'perc' });
  A.riser(28.6, 30.0, { vel: 0.1, bus: 'sfx', type: 'noise' });

  // ---- sound: the storm wall, the boats, the alarm, the collar, the waterspout, the lightning, the discharge, the boil -------
  S.thunder(14.6, { close: 0.1, dur: 4.5, pan: -0.7, vel: 0.45 }); S.thunder(15.9, { close: 0.15, dur: 4, pan: -0.6, vel: 0.4 });
  S.creak(14.3, 0.55, { f: 1300, q: 16, rate: [28, 12], pan: 0.45, vel: 0.12 }); S.creak(15.1, 0.45, { f: 1150, q: 16, rate: [24, 10], pan: 0.3, vel: 0.1 });
  cue(14.6, 'sfx', 'Storm wall: distant thunder 14.6 and 15.9 (left, the west); weather vanes squeak 14.3 / 15.1');
  S.engine(16.4, 18.6, { rate: 12, pan: [-0.8, 0.7], pass: 0.5, vel: 0.22 }); S.engine(16.8, 18.6, { rate: 10, pan: [-0.9, 0.4], pass: 0.7, vel: 0.16 });
  S.splash(16.95, { size: 0.45, vel: 0.22, pan: -0.2 }); S.splash(17.85, { size: 0.55, vel: 0.24, pan: 0.3 });
  S.waveCrash(17.5, { build: 0.7, dur: 1.6, vel: 0.28, pan: 0.1 });
  cue(16.4, 'sfx', 'Boats race home: two diesel pass-bys left to right, spray 16.95 / 17.85, a wave breaks at 17.5');
  for (let t = 18.4; t < 20.0; t += 0.17) A.whoosh(t, 0.22, { f0: 400, f1: 2000, q: 1, pan: [0.5, -0.5], vel: 0.08, bus: 'foley', verb: 0.05 });
  S.churchBell([18.45, 18.85, 19.25, 19.65, 20.05], 'D5', { v: [1, 0.9, 1, 0.85, 0.7], vel: 0.16, pan: 0.25 });
  S.tear(18.9, 0.45, { rips: 2, vel: 0.25, pan: 0.3 }); S.flaps(19.0, 1.0, { rate: 13, pan: [0.3, -0.9], vel: 0.25 });
  cue(18.4, 'sfx', 'City alarm: the swinging bell tolls 18.45 / 18.85 / 19.25 / 19.65 / 20.05, windmills whirl, laundry torn away 18.9');
  S.groan(20.0, 2.1, { f: 46, drop: 0.08, vel: 0.5, pan: 0.1, peak: 0.3 });
  S.creak(20.15, 1.6, { f: 260, q: 14, rate: [32, 8], vel: 0.3, pan: -0.15 });
  [20.5, 20.8, 21.05, 21.3, 21.6].forEach((t, i) => {
    S.clank(t, { size: 0.12, ring: 0.25, vel: 0.35, thud: 0, pan: -0.4 + i * 0.2, mallet: 0.0002 });
    A.toneSweep(t + 0.01, 0.25, { wave: 'sine', from: { hz: 3200 }, to: { hz: 1900 }, vel: 0.06, bus: 'sfx', pan: -0.4 + i * 0.2 });
  });
  S.rubble(20.5, 1.3, { vel: 0.14 });
  cue(20.0, 'sfx', 'Collar: the chain goes taut (groan + creak from 20.0), rivets pop 20.5 / 20.8 / 21.05 / 21.3 / 21.6, rust dust');
  A.whoosh(22.0, 2.4, { f0: 80, f1: 400, q: 0.7, pan: [-0.8, -0.5], vel: 0.25, bus: 'sfx' }); S.thunder(22.7, { close: 0.3, pan: -0.6, vel: 0.5 });
  cue(22.0, 'sfx', 'The waterspout forms: a deep vortex swell from the left, its roar starts and stays under the score until 83.0');
  S.thunder(24.4, { close: 1, dur: 4.5, vel: 0.95, pan: 0.1 });
  S.crackle(24.42, 25.8, { density: 420, vel: 0.45, shape: (u) => Math.pow(1 - u, 1.2) });
  A.zap(24.4, { vel: 0.25, bus: 'sfx' });
  S.clank(24.42, { size: 1.6, ring: 1.4, vel: 0.35, thud: 0, pan: 0.1 });
  for (let i = 0; i < 11; i++) {
    const t = 25.8 + i * 0.2; const p = 0.4 - i * 0.07;
    S.crackle(t, t + 0.16, { density: 900, vel: 0.3, hum: 0.5, pan: p, shape: (u) => 1 - u });
    S.clank(t + 0.01, { size: 1.0 + 0.04 * i, ring: 0.3, vel: 0.22, thud: 0.15, pan: p, mallet: 0.0004 });
  }
  S.steam(27.85, 1.4, { vel: 0.4, whistle: 2600 }); S.splash(27.9, { size: 0.6, vel: 0.3 });
  cue(25.8, 'sfx', 'Discharge runs down the chain link by link: 11 spark + clank ticks every 0.2 s (25.8 ... 27.8) on a descending chromatic string run; sizzle into the sea 27.85');
  S.underBed(28.0, 33.25, { vel: 0.6, bubbles: 10 });
  S.bubbles(28.0, 30.05, { rate: 260, f: [180, 1100], vel: 0.38, lp: 2200, shape: (u) => 0.15 + 0.85 * Math.pow(u, 1.5) });
  for (let i = 0; i < 9; i++) S.clank(28.15 + i * 0.2 + 0.08 * A.rand(), { size: 0.07, ring: 0.06, vel: 0.12, thud: 0, mallet: 0.0002, pan: (A.rand() - 0.5) * 0.8 });
  A.whoosh(28.45, 0.35, { f0: 150, f1: 700, q: 0.8, pan: [-0.2, -0.9], vel: 0.15, bus: 'sfx' }); A.whoosh(28.8, 0.3, { f0: 150, f1: 650, q: 0.8, pan: [0.2, 0.9], vel: 0.12, bus: 'sfx' });
  cue(28.0, 'sfx', 'Under water: the shackle glows, the water boils (bubbles thicken), heat pings, fish dart away 28.45 / 28.8; tremolo cluster D-Eb + timpani roll crescendo into 30.0');
}
