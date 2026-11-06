// ANCHOR score, part 2. Act 3 (30-42 s): the pin shears (hit + silence), metal groans, the chain whips up and bursts
// out of the bay, the city lurches, the crystals shimmer, the city drifts toward the waterspout.
// Act 4 (42-55 s): the crane smash, water over the mech, the gull flees, lightning on the antenna, the visor boots, the
// rise, the first step into the sea, the look up at the city.
import { A, M, strings, spic, line, choir, glock, timp, taiko, bassDrum } from './lib.mjs';
import * as S from './sfx.mjs';
import { cue, notes, ostinato, brassChord, swellStr, tutti, MUSIC } from './common.mjs';

const smooth = (x) => x * x * (3 - 2 * x);

export function act3() {
  // ---- 30.0 the pin shears: hit, then silence -------------------------------------------------------------------------------
  tutti(30.0, ['D2', 'A2', 'D3', 'Eb3', 'A3', 'D4', 'Eb4'], { vel: 1.05, tn: 'D2', cym: 0.5, tam: 0, tk: 0.9, len: 0.3 });
  S.clank(30.0, { size: 0.35, ring: 2.2, vel: 0.9, thud: 0.6, mallet: 0.0002 });
  A.noiseHit(30.0, 0.09, { hp: 1800, decay: 40, vel: 0.5, bus: 'sfx' });
  S.screech(30.02, 0.22, { f: 1600, vel: 0.3 });
  S.boom(30.0, { f: 32, decay: 0.7, dur: 1.2, vel: 0.6, crunch: 0.2, crunchF: 400 });
  S.silt(30.05, 1.4, { vel: 0.55 });
  A.gap(30.3, 31.58, { buses: MUSIC, fade: 0.06 });
  cue(30.0, 'HIT', 'The shackle pin shears: metal snap with a long ring, tutti stab, then a SILENCE GAP in the score 30.3-31.58 (only the ring, the silt burst and the groans)');
  S.groan(30.6, 1.3, { f: 42, drop: 0.15, vel: 0.55, peak: 0.7 }); S.groan(30.9, 1.0, { f: 61, drop: 0.1, vel: 0.4, peak: 0.8, pan: 0.2 });
  S.creak(31.0, 0.6, { f: 180, q: 18, rate: [20, 45], vel: 0.25 });
  cue(30.6, 'sfx', 'Deep metal stress groans build through the gap, 30.6-31.6');
  // ---- 31.6 the chain whips free (under water) ------------------------------------------------------------------------------
  S.boom(31.6, { f: 30, decay: 1.4, vel: 1.0, crunch: 0.4, crunchF: 400 });
  A.whoosh(31.6, 1.6, { f0: 90, f1: 1800, q: 0.8, shape: 'in', pan: [-0.4, 0.4], vel: 0.55, bus: 'sfx' });
  S.rattle(31.7, 33.1, { rate: 10, size: 1.2, vel: 0.22, shape: (u) => 0.4 + 0.6 * u, ring: 0.3 });
  A.braam(31.6, 1.2, { note: 'D2', vel: 0.5, bus: 'brass' });
  timp(31.6, 'D2', 1.0); bassDrum(31.6, { vel: 0.9 }); taiko(31.6, { vel: 0.8, f: 55 });
  strings(31.6, 1.6, ['D3', 'A3', 'D4'], { bend: (s) => 12 * Math.pow(s / 1.6, 1.5), trem: 14, dyn: (u) => 0.5 + 0.7 * u, att: 0.05, rel: 0.1, bright: 0.6, vel: 0.42 });
  brassChord(31.65, 1.55, ['D3', 'A3', 'D4'], { vel: 0.4, dyn: (T) => 0.35 + (0.75 * (T - 31.65)) / 1.55, rel: 0.1 });
  cue(31.6, 'HIT', 'Huge underwater impact as the chain whips free: sub boom, braam, timpani + gran cassa; whip whoosh and an octave string glissando rising into 33.2');
  // ---- 33.2 it bursts out of the bay ------------------------------------------------------------------------------------------
  S.splash(33.2, { size: 3, dur: 3.6, vel: 0.85, rain: 1.4 });
  S.boom(33.2, { f: 40, decay: 0.8, vel: 0.65, crunch: 0.5, crunchF: 900 });
  S.rattle(33.2, 34.8, { rate: 14, size: 1.3, vel: 0.35, shape: (u) => Math.pow(1 - u, 1.5), ring: 0.45 });
  A.whoosh(33.05, 1.3, { f0: 500, f1: 6000, q: 0.7, shape: 'out', pan: [-0.5, 0.6], vel: 0.35, bus: 'sfx' });
  tutti(33.2, ['Bb1', 'F2', 'Bb2', 'D3', 'F3', 'Bb3', 'D4', 'F4'], { vel: 1.0, tn: 'Bb1', cym: 0.75, tam: 0.6, tk: 0.9, len: 0.6 });
  swellStr(33.4, 1.8, ['Bb2', 'F3', 'Bb3', 'D4', 'F4'], 0.9, 0.45, { att: 0.08, trem: 15, bright: 0.6, vel: 0.42, rel: 0.4 });
  line(notes([[33.2, 0.43, 'Bb4', 1.0], [33.6, 0.43, 'A4', 0.95], [34.0, 0.43, 'G4', 0.9], [34.4, 0.43, 'F4', 0.85], [34.8, 0.42, 'E4', 0.8]]), { type: 'horn', bus: 'brass', vel: 0.5 });
  cue(33.2, 'HIT', 'The chain bursts out of the bay: wall of spray, boom, chain clatter, tutti Bb/D with tam-tam; horns fall Bb-A-G-F-E with the spray');
  // ---- 35.2 the city lurches; the crystals --------------------------------------------------------------------------------------
  S.groan(35.2, 2.2, { f: 38, drop: 0.2, vel: 0.6, peak: 0.25 });
  S.creak(35.3, 1.8, { f: 520, q: 9, rate: [35, 9], vel: 0.3, pan: -0.3 });
  S.creak(35.6, 1.4, { f: 340, q: 12, rate: [28, 7], vel: 0.28, pan: 0.4 });
  S.boom(35.2, { f: 28, decay: 1.6, vel: 0.45, crunch: 0.2, crunchF: 300 });
  S.tiles(35.5, 37.4, { rate: 16, vel: 0.24, shape: (u) => Math.sin(Math.PI * Math.min(1, u * 1.2)) });
  S.wind(35.3, 37.8, (T) => Math.sin(Math.PI * Math.min(1, (T - 35.3) / 2.5)) * 0.5, { base: 1600, whistle: 0, vel: 0.5, bus: 'sfx' });
  strings(35.2, 1.6, ['D3', 'F3', 'A3', 'D4', 'F4'], { bend: (s) => -smooth(Math.min(1, s / 0.9)), trem: 10, dyn: (u) => 0.9 - 0.4 * u, att: 0.04, rel: 0.5, bright: 0.5, vel: 0.42 });
  timp(35.2, 'D2', 0.85); bassDrum(35.2, { vel: 0.6 });
  line(notes([[35.2, 0.55, 'D3', 0.9], [35.7, 0.9, 'C#3', 0.8]]), { type: 'horn', bus: 'brass', vel: 0.4, glide: 0.4 });
  cue(35.2, 'HIT', 'The city lurches: rock groan, wooden creaks, houses shudder, roof tiles rain 35.5-37.4, a waterfall bends; strings slide down a semitone');
  choir(35.2, 3.8, ['G3', 'B3', 'D4', 'F#4', 'A4', 'C#5'], { vowel: 'u', toVowel: 'a', att: 2.0, rel: 1.4, dyn: (u) => 0.25 + 0.75 * Math.min(1, u / 0.58), vel: 0.42 });
  A.pad(36.2, 2.8, ['G4', 'B4', 'D5', 'F#5', 'A5', 'C#6'].map(M), { type: 'glass', vel: 0.32, bus: 'keys', attack: 1.0, release: 1.2 });
  A.reverseCymbal(37.4, 1.2, { vel: 0.22, bus: 'perc' });
  A.whoosh(37.35, 0.9, { f0: 2000, f1: 9000, q: 0.8, shape: 'out', pan: [-0.3, 0.3], vel: 0.12, bus: 'sfx' });
  for (let i = 0, t = 37.45; t < 39.0; i++, t += 0.11 + 0.05 * A.rand()) glock(t, ['C#6', 'D6', 'F#6', 'A6', 'B6', 'C#7', 'E7'][Math.floor(A.rand() * 7)], { vel: 0.18, soft: 0.6, pan: (A.rand() - 0.5) * 1.2 });
  strings(37.4, 1.6, ['A5', 'C#6', 'F#6'], { att: 0.4, rel: 1.0, bright: 0.3, vel: 0.22, vib: 0.04 });
  cue(35.2, 'music', 'Levitation crystals: shimmering choir-like pad Gmaj9(#11) from 35.2, flaring at 37.4 (reverse swell, glass pad, glockenspiel glints) until 39.0');
  // ---- 39.0 the city drifts toward the waterspout -------------------------------------------------------------------------------
  const R3 = (t) => (t < 40.6 ? 'D2' : t < 41.4 ? 'Bb1' : 'A1');
  ostinato(39.0, 40.6, 0.2, (i, t) => M(R3(t)) + [0, 12, 0, 12, 0, 15, 0, 14][i % 8], { vf: (i) => (i % 8 === 0 ? 0.6 : 0.45), bright: 0.5, sub: 0.6 });
  ostinato(40.6, 42.0, 0.1, (i, t) => M(R3(t)) + [0, 12, 0, 12][i % 4], { vf: (i, t) => 0.45 + 0.2 * (t - 40.6) / 1.4 + (i % 4 === 0 ? 0.1 : 0), bright: 0.6, sub: 0.6, dur: 0.09 });
  const mot = notes([[39.0, 0.43, 'F3', 0.8], [39.4, 0.43, 'A3', 0.85], [39.8, 0.83, 'D4', 0.95], [40.6, 0.43, 'F3', 0.85], [41.0, 0.43, 'Bb3', 0.9], [41.4, 0.6, 'C#4', 1.05]]);
  line(mot, { type: 'horn', bus: 'brass', vel: 0.55, pan: -0.1 });
  line(mot.map((x) => ({ ...x, n: M(x.n) - 12 })), { type: 'cello', bus: 'str', vel: 0.3, pan: -0.25 });
  swellStr(39.0, 1.62, ['D3', 'A3', 'D4', 'F4'], 0.5, 0.8, { trem: 12, bright: 0.5, vel: 0.4 });
  swellStr(40.6, 0.82, ['Bb2', 'F3', 'Bb3', 'D4'], 0.8, 0.95, { trem: 14, bright: 0.55, vel: 0.42 });
  swellStr(41.4, 0.6, ['A2', 'E3', 'A3', 'C#4', 'E4'], 0.9, 1.25, { trem: 16, bright: 0.65, vel: 0.44, rel: 0.1 });
  timp(39.0, 'D2', 0.7); timp(40.6, 'Bb2', 0.7); timp(41.0, 'A2', 0.15, { t1: 42.0, to: 0.9 });
  [39.0, 39.8, 40.6, 41.0, 41.4, 41.6, 41.8].forEach((t, i) => taiko(t, { vel: 0.45 + i * 0.06, f: 60 }));
  A.reverseCymbal(42.0, 1.2, { vel: 0.4, bus: 'perc' }); A.riser(40.5, 42.0, { vel: 0.12, bus: 'sfx', type: 'noise' });
  S.wind(39.0, 42.1, () => 0.35, { base: 3200, whistle: 0, vel: 0.35, bus: 'sfx', gust: 0.4 });
  [39.4, 40.1, 40.7, 41.3].forEach((t, i) => S.splash(t, { size: 0.6, vel: 0.22, pan: -0.5 + i * 0.25, rain: 0.6 }));
  S.thunder(40.2, { close: 0.25, pan: -0.6, vel: 0.45 });
  cue(39.0, 'music', 'The city drifts toward the waterspout: ostinato returns, minor motif on horns + cellos, crescendo, reverse cymbal into 42.0; the chain end skips 39.4 / 40.1 / 40.7 / 41.3');
}

export function act4() {
  // ---- 42.0 the crane --------------------------------------------------------------------------------------------------------
  tutti(42.0, ['D2', 'A2', 'D3', 'F3', 'A3', 'D4', 'F4'], { vel: 1.05, tn: 'D2', cym: 0.7, tam: 0.7, tk: 0.9, len: 0.5 });
  S.boom(42.0, { f: 36, decay: 1.0, vel: 0.85, crunch: 0.9, crunchF: 900 });
  S.screech(42.0, 1.1, { f: 700, vel: 0.45, pan: 0.2 });
  S.clank(42.0, { size: 2.5, ring: 1.5, vel: 0.75, thud: 0.6, pan: 0.15 });
  [[42.35, -0.4], [42.7, 0.5], [43.0, -0.2], [43.45, 0.35], [43.9, -0.5]].forEach(([t, p], i) => S.clank(t, { size: 1.6 + 0.3 * (i % 2), f: 120, ring: 0.9, vel: 0.5 - i * 0.05, thud: 0.7, pan: p }));
  S.rattle(42.1, 43.3, { rate: 12, size: 0.6, vel: 0.2, shape: (u) => 1 - u, ring: 0.3 });
  S.rubble(42.1, 1.2, { vel: 0.3, pan: 0.1 });
  S.waveCrash(43.2, { build: 0.7, dur: 2.2, vel: 0.6, pan: -0.1 }); S.splash(43.25, { size: 1.5, vel: 0.5 });
  cue(42.0, 'HIT', 'The chain end smashes crane A: metal tearing, impact, tutti D minor + tam-tam; containers clang 42.35 / 42.7 / 43.0 / 43.45 / 43.9; the wave hits the dock 43.2');
  swellStr(42.5, 3.1, ['D2', 'A2', 'D3'], 0.5, 0.35, { att: 0.5, trem: 9, bright: 0.3, vel: 0.36, rel: 0.2 });
  A.sub(42.4, 3.2, 'D1', { vel: 0.28, bus: 'low', attack: 0.4, release: 0.2 });
  timp(44.0, 'D2', 0.35); timp(44.8, 'D2', 0.4);
  S.waveCrash(44.0, { build: 0.3, dur: 1.8, vel: 0.5, pan: 0.2 }); S.splash(44.05, { size: 1.2, vel: 0.4 });
  S.rattle(44.1, 45.0, { rate: 10, size: 0.5, vel: 0.16, ring: 0.25 });
  S.gull(44.5, { calls: 4, f: 960, gap: 0.05, dist: 0.1, pan: 0.2, vel: 0.4 }); S.flaps(44.45, 1.0, { rate: 7, pan: [0.1, 0.9], vel: 0.45 }); S.chick(44.95, { n: 4, gap: 0.12, vel: 0.12 });
  cue(44.0, 'sfx', 'Water and debris crash over the sleeping mech 44.0; the gull flees with alarm calls from 44.5, wing flaps, chick peeps 44.95; heartbeat timpani 44.0 / 44.8');
  // ---- 45.6 lightning on the antenna -----------------------------------------------------------------------------------------
  S.thunder(45.6, { close: 1, dur: 4, vel: 1.0 });
  S.crackle(45.6, 47.3, { density: 500, vel: 0.5, shape: (u) => Math.pow(1 - u, 0.8) });
  A.zap(45.6, { vel: 0.35, bus: 'sfx' }); S.clank(45.62, { size: 0.4, ring: 1.0, vel: 0.35, thud: 0 });
  tutti(45.6, ['D2', 'Ab2', 'D3', 'Ab3', 'D4'], { vel: 0.8, tn: 'D2', cym: 0.6, tam: 0, tk: 0.6, len: 0.35, strVel: 0.4 });
  strings(45.9, 1.5, ['A6'], { att: 0.4, rel: 0.3, bright: 0.25, vel: 0.15, vib: 0.03, voices: 3 });
  cue(45.6, 'HIT', 'Lightning strikes the mech antenna: close thunder, electric crackle 45.6-47.3, tritone stab D/Ab; a high violin A6 hangs');
  // ---- 47.4 the visor: relay, swell, the boot chord at 48.2 -----------------------------------------------------------------------
  S.clank(47.4, { size: 0.3, ring: 0.15, vel: 0.4, thud: 0.8 });
  S.powerUp(47.4, 48.2, { f0: 50, f1: 900, vel: 0.55 });
  A.supersaw(47.4, 0.8, ['D3', 'A3', 'D4', 'E4'].map(M), { cutFn: (T) => 250 * Math.pow(24, Math.min(1, Math.max(0, (T - 47.4) / 0.8))), attack: 0.6, release: 0.15, vel: 0.7, bus: 'brass', verb: 0.3 });
  A.supersaw(48.2, 1.0, ['D3', 'A3', 'D4', 'F#4', 'A4'].map(M), { attack: 0.005, release: 0.9, cutHi: 6000, cutLo: 1400, fdec: 2.5, vel: 0.85, bus: 'brass', verb: 0.4 });
  brassChord(48.2, 0.75, ['D3', 'A3', 'D4', 'F#4'], { vel: 0.45, att: 0.01, rel: 0.4, v: 1.0 });
  strings(48.2, 0.75, ['D2', 'A2', 'D3', 'F#3', 'A3', 'D4'], { att: 0.01, rel: 0.5, bright: 0.6, vel: 0.4 });
  timp(48.2, 'D2', 0.7);
  S.clank(48.2, { size: 0.22, ring: 0.12, vel: 0.35, thud: 0.4 });
  [['F#6', 48.2], ['A6', 48.33], ['D7', 48.46]].forEach(([n, t]) => A.bell(t, n, { ratio: 3.5, index: 1.2, idec: 7, dur: 1.6, vel: 0.3, bus: 'keys' }));
  A.sub(48.2, 0.8, 'D1', { vel: 0.4, bus: 'low', attack: 0.01, release: 0.4 });
  cue(47.4, 'HIT', 'Visor power-on: relay clunk + rising synth swell 47.4-48.2 (eyes should reach full brightness at 48.2)');
  cue(48.2, 'HIT', "Mechanical 'boot' chord, D major, with the F#-A-D chime (the theme's opening motif)");
  // ---- 49.0 the rise ------------------------------------------------------------------------------------------------------------
  const call = notes([[49.0, 0.43, 'F#4', 0.85], [49.4, 0.43, 'A4', 0.9], [49.8, 0.83, 'D5', 1.0], [50.6, 0.43, 'E5', 0.95], [51.0, 0.43, 'F#5', 1.0], [51.4, 0.43, 'G5', 1.05], [51.8, 0.6, 'A5', 1.15]]);
  line(call, { type: 'horn', bus: 'brass', vel: 0.55, pan: 0.1 });
  line(call.map((x) => ({ ...x, n: M(x.n) - 12 })), { type: 'horn', bus: 'brass', vel: 0.4, pan: -0.2 });
  ['D4', 'E4', 'F#4', 'G4', 'A4', 'B4', 'C#5', 'D5', 'E5', 'F#5', 'G5', 'A5', 'B5', 'C#6', 'D6', 'E6', 'F#6'].forEach((n, i) => spic(49.0 + i * 0.2, n, { dur: 0.19, vel: 0.3 + i * 0.015, bright: 0.5 + i * 0.02, pan: 0.25 }));
  [[49.0, 0.82, ['D3', 'A3', 'D4', 'F#4']], [49.8, 0.82, ['B2', 'F#3', 'B3', 'D4']], [50.6, 0.82, ['G2', 'D3', 'G3', 'B3', 'D4']], [51.4, 0.42, ['E3', 'G3', 'B3', 'D4']], [51.8, 0.6, ['A2', 'E3', 'A3', 'C#4', 'E4']]]
    .forEach(([t, d, ns], i) => swellStr(t, d, ns, 0.55 + i * 0.12, 0.65 + i * 0.14, { att: 0.15, rel: 0.25, bright: 0.5 + i * 0.05, vel: 0.42 }));
  line(notes([[49.0, 0.82, 'D2'], [49.8, 0.82, 'B1'], [50.6, 0.82, 'G1'], [51.4, 0.42, 'E2'], [51.8, 0.6, 'A1']]), { type: 'cello', bus: 'str', vel: 0.36 });
  timp(50.6, 'A2', 0.1, { t1: 52.4, to: 1.0, curve: 1.8 });
  A.roll(51.2, 52.4, (t, v) => A.snare(t, { type: 'tight', vel: v * 0.3, bus: 'perc', verb: 0.3 }), { from: 1 / 4, to: 1 / 16, vel0: 0.2, vel1: 1 });
  A.reverseCymbal(52.4, 1.4, { vel: 0.45, bus: 'perc' });
  [49.0, 49.8, 50.6, 51.4, 51.8, 52.0, 52.2].forEach((t, i) => taiko(t, { vel: 0.45 + i * 0.07, f: 60 }));
  cue(49.0, 'music', 'The rise: horn calls climb (F#4 A4 D5 | E5 F#5 G5 A5), strings run up the D-major scale in 8ths, timpani + snare roll, reverse cymbal into 52.4');
  S.servo(49.0, 1.4, { f0: 150, f1: 420, pan: -0.3, vel: 0.32 }); S.servo(49.9, 1.3, { f0: 200, f1: 600, pan: 0.4, vel: 0.28 });
  S.servo(50.9, 1.4, { f0: 120, f1: 380, pan: -0.1, vel: 0.3 }); S.servo(51.6, 0.9, { f0: 260, f1: 700, pan: 0.3, vel: 0.25 });
  S.groan(49.1, 2.6, { f: 47, drop: -0.08, vel: 0.45, peak: 0.6 });
  S.creak(49.4, 1.2, { f: 230, q: 14, vel: 0.3, pan: 0.2 }); S.creak(50.8, 1.2, { f: 300, q: 12, vel: 0.28, pan: -0.3 });
  [[49.3, 0.7, -0.4], [50.0, 0.8, 0.5], [50.7, 0.6, -0.2], [51.5, 0.7, 0.3]].forEach(([t, d, p]) => S.tear(t, d, { vel: 0.45, pan: p }));
  [50.3, 50.9, 51.4, 51.9].forEach((t, i) => A.thud(t, { f0: 110 + i * 10, vel: 0.12, bus: 'foley' }));
  S.rubble(50.2, 0.8, { vel: 0.14, pan: 0.2 });
  S.gull(49.5, { calls: 3, f: 900, pan: -0.6, dist: 0.3, vel: 0.33 }); S.gull(49.9, { calls: 2, f: 1050, pan: 0.5, dist: 0.4, vel: 0.28 });
  S.gull(50.4, { calls: 4, f: 800, pan: -0.2, dist: 0.5, vel: 0.26 }); S.gull(50.9, { calls: 2, f: 980, pan: 0.7, dist: 0.6, vel: 0.22 });
  S.flaps(49.4, 1.6, { rate: 8, pan: [-0.2, -0.9], vel: 0.4 }); S.flaps(49.8, 1.4, { rate: 7, pan: [0.2, 0.9], vel: 0.35 });
  cue(49.0, 'sfx', 'The rise: servo whines 49.0 / 49.9 / 50.9 / 51.6, steel groans, vines tear 49.3 / 50.0 / 50.7 / 51.5, moss thuds, gulls scatter 49.5-51.2 with wing flaps');
  // ---- 52.4 the first step; it looks up --------------------------------------------------------------------------------------------
  tutti(52.4, ['D2', 'A2', 'D3', 'F#3', 'A3', 'D4', 'F#4', 'A4'], { vel: 1.1, tn: 'D2', cym: 0.8, tam: 0.6, tk: 1.0, len: 0.7 });
  S.boom(52.4, { f: 30, decay: 1.5, vel: 1.0, crunch: 0.5 });
  S.splash(52.42, { size: 3, dur: 3.2, vel: 0.95 });
  S.waveCrash(53.4, { build: 0.4, dur: 1.6, vel: 0.35 });
  S.clank(52.4, { size: 3, ring: 0.8, vel: 0.4, thud: 0.5 });
  cue(52.4, 'HIT', 'The first step into the sea: colossal footfall boom + splash, tutti D major (the first major-key hit)');
  swellStr(52.9, 0.92, ['D3', 'A3', 'D4', 'F#4', 'A4'], 0.6, 0.7, { att: 0.5, rel: 0.35, bright: 0.45, vel: 0.42 });
  swellStr(53.8, 0.82, ['B2', 'F#3', 'B3', 'D4', 'F#4'], 0.65, 0.75, { att: 0.2, rel: 0.35, bright: 0.45, vel: 0.42 });
  swellStr(54.6, 0.42, ['G2', 'D3', 'G3', 'B3', 'D4'], 0.7, 0.9, { att: 0.1, rel: 0.2, bright: 0.5, vel: 0.42 });
  line(notes([[53.0, 0.43, 'F#4', 0.8], [53.4, 0.43, 'A4', 0.85], [53.8, 0.83, 'D5', 0.95], [54.6, 0.42, 'E5', 0.85]]), { type: 'horn', vel: 0.5, verb: 0.45 });
  line(notes([[52.9, 0.92, 'D2'], [53.8, 0.82, 'B1'], [54.6, 0.42, 'G1']]), { type: 'cello', bus: 'str', vel: 0.32 });
  [54.4, 54.6, 54.8].forEach((t, i) => taiko(t, { vel: 0.45 + i * 0.12, f: 66 }));
  cue(53.0, 'music', 'It looks up at the drifting city: the opening motif on solo horn (F#4 A4 D5 E5); taiko pickup 54.4 / 54.6 / 54.8 into the chase');
}
