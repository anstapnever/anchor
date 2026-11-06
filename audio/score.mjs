// ANCHOR (90 s anime short): the whole score and sound design, all synthesized (no samples, no voices).
//   node audio/score.mjs out/music.wav        (from the project root)
// Writes out/music.wav (48 kHz stereo 24-bit, 92.0 s = 90 s of picture + a 2 s tail) and audio/cues.md.
// The tempo grid is 150 bpm (8th = 0.2 s), so every shot boundary in BIBLE.md falls on an 8th note.
//   part1.mjs  Act 1 (0-14) the hopeful theme; Act 2 (14-28) the storm
//   part2.mjs  Act 3 (28-42) the pin shears, the chain bursts out, the city lurches; Act 4 (42-55) the mech wakes
//   part3.mjs  Act 5 (55-70) the chase; Act 6 (70-82) the hold; Act 7 (82-92) the clouds open
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { A } from './lib.mjs';
import * as S from './sfx.mjs';
import { CUES, cue, curve } from './common.mjs';
import { act1, act2 } from './part1.mjs';
import { act3, act4 } from './part2.mjs';
import { act5, act6, act7 } from './part3.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(process.argv.slice(2).find((a) => a.endsWith('.wav')) || path.join(HERE, '..', 'out', 'music.wav'));
const DUR = 92.0;

A.init({ duration: DUR, bpm: 150, seed: 7 });

// ---- buses (created in this order, which is also the order of the report's columns) ------------------------------------------
A.bus('str', { gain: -5, hp: 30 }); // string sections, ostinati, solo violin / cello lines
A.bus('solo', { gain: -6, hp: 90 }); // flute, solo horn
A.bus('brass', { gain: -8, hp: 40 }); // horns + trumpets
A.bus('choir', { gain: -6, hp: 110 }); // wordless formant choir pads
A.bus('keys', { gain: -8, hp: 60 }); // harp, piano, glockenspiel, bells
A.bus('perc', { gain: -9, hp: 28 }); // timpani, taiko, gran cassa, cymbals, tam-tam
A.bus('low', { gain: -10, hp: 25 }); // sub drones, low synths
A.bus('sfx', { gain: -8, hp: 25 }); // impacts, metal, water, machines
A.bus('foley', { gain: -10, hp: 150 }); // gulls, chicks, wings
A.bus('amb', { gain: -9, hp: 35, duck: [{ from: 'hit', depth: 0.4, attack: 0.004, release: 0.3 }] }); // wind, roar, sea beds
A.bus('fx', { gain: -8 }); // toolkit fx voices that only write here (sparkles)

// Under water (11.2-14.0) the score is heard through the water.
for (const b of ['str', 'solo', 'brass', 'choir', 'keys', 'perc', 'low']) A.automate(b, 'lp', [[0, 19000], [11.15, 19000], [11.55, 1500], [13.85, 1500], [14.0, 19000]]);

// ---- ambience beds --------------------------------------------------------------------------------------------------------------
// Act 1: high airy wind over the sky city, a rush down the chain (4.6-7.4), a breeze over the port, nothing under water.
S.wind(0, 11.35, curve([[0, 0.25], [0.8, 0.5], [3.0, 0.5], [4.6, 0.6], [6.4, 1.0], [7.3, 0.9], [7.7, 0.35], [9.6, 0.28], [11.1, 0.25], [11.35, 0]]),
  { base: 650, whistle: 0.35, whistleF: 1500, vel: 0.55 });
// The storm wind from the city rim (14.0) to the clouds opening (82.0); muffled under water (28.0-33.2); a hush on the visor (47.4).
S.wind(13.9, DUR, curve([[13.9, 0], [14.2, 0.4], [16.4, 0.55], [18.4, 0.75], [20.0, 0.7], [22.0, 0.8], [24.4, 0.85], [27.9, 0.8], [28.05, 0.06], [33.15, 0.06], [33.3, 0.8],
  [37.4, 0.6], [39.0, 0.8], [47.3, 0.8], [47.5, 0.45], [49.0, 0.7], [55.0, 0.85], [63.4, 0.6], [65.4, 0.85], [76.0, 0.9], [78.6, 1.0], [80.6, 0.9], [82.0, 0.4], [83.2, 0.14], [DUR, 0.12]]),
  { base: 420, whistle: 0.7, whistleF: 1050, gust: 0.2, vel: 0.7 });
// The waterspout's roar: forms at 22.0, nearest when the city reaches it (59.0) and when it passes (78.6-80.6, left to right).
S.roar(22.0, 83.4, curve([[22.0, 0], [22.8, 0.35], [24.4, 0.45], [27.9, 0.4], [28.05, 0.04], [33.15, 0.04], [33.3, 0.35], [39.0, 0.55], [42.0, 0.5], [47.3, 0.45], [47.5, 0.2],
  [49.0, 0.4], [57.4, 0.45], [59.0, 0.85], [61.0, 0.5], [63.4, 0.45], [63.6, 0.25], [65.2, 0.25], [65.4, 0.5], [70.0, 0.55], [73.6, 0.75], [76.0, 0.6], [78.6, 1.5], [80.6, 1.3],
  [81.6, 0.3], [82.4, 0.08], [83.4, 0]]), { pan: curve([[22, -0.6], [39, -0.4], [59, -0.15], [73.6, 0.25], [78.4, -0.85], [80.8, 0.85], [83.4, 0.7]]) });
S.lap(82.4, DUR, { vel: 0.3 }); // calm harbour water after the storm
cue(0.0, 'sfx', 'Ambience: high airy wind over the sky city 0-11.35, swelling into a rush down the chain 4.6-7.4, a light breeze over the port');
cue(13.9, 'sfx', 'Storm wind bed from 14.0, rising through acts 2-6 (muffled under water 28.0-33.2, a hush on the visor 47.4-49.0), dropping as the clouds open at 82.0');
cue(82.4, 'sfx', 'Calm harbour water lapping 82.4-92.0; a soft breeze');
// distant thunder rolling through the storm, between the scripted strikes
[[17.9, 0.15, 0.6], [21.4, 0.2, -0.4], [36.6, 0.15, -0.6], [53.8, 0.2, -0.5], [67.0, 0.25, 0.5], [71.2, 0.2, -0.6], [77.4, 0.2, 0.5]]
  .forEach(([t, close, pan]) => S.thunder(t, { close, pan, vel: 0.35 }));
cue(17.9, 'sfx', 'Distant thunder rolls (no crack) between the scripted strikes: 17.9 / 21.4 / 36.6 / 53.8 / 67.0 / 71.2 / 77.4');

// ---- the acts -------------------------------------------------------------------------------------------------------------------
const tw = Date.now();
act1(); act2(); act3(); act4(); act5(); act6(); act7();
console.log(`voices written in ${((Date.now() - tw) / 1000).toFixed(1)} s`);

// ---- fader rides: dB curves applied to what the voices wrote (dry and reverb / delay sends alike) -------------------------------
const ALL = ['str', 'solo', 'brass', 'choir', 'keys', 'perc', 'low', 'sfx', 'foley', 'amb', 'fx'];
function ride(names, pts) {
  const g = curve(pts); const n = Math.ceil(DUR * A.SR); const k = new Float32Array(n);
  for (let i = 0; i < n; i++) k[i] = Math.pow(10, g(i / A.SR) / 20);
  for (const name of names) {
    const b = A.bus(name);
    for (const ch of [b.L, b.R, b.VL, b.VR, b.DL, b.DR]) if (ch) for (let i = 0; i < Math.min(n, ch.length); i++) ch[i] *= k[i];
  }
}
// the dawn is gentle, under water further away, the storm full, the clouds opening warm but below the climax (78.6)
ride(ALL, [[0, -2.5], [11.15, -2.5], [11.3, -3.5], [13.95, -3.5], [14.0, 0],
  [22.8, 0], [23.4, -1.5], [24.38, -1.5], [24.4, 0], [24.9, 0], [25.6, -1.5], [27.6, -1.5], [28.0, 0], // lightning: dip before, punch, pull back
  [52.9, 0], [53.3, -1.5], [54.8, -1.5], [55.0, 0], // a breath after the first step, the chase starts full
  [73.4, 0], [76.0, 0.5], [78.5, 1.5], [80.6, 1.5], [80.7, 0], // the hold, then the build to the climax (78.6)
  [81.95, 0], [82.0, -3], [DUR, -3]]);
// a breath before the biggest hits: the tonal buses stop for ~0.11 s while the reverse cymbals on 'perc' swell into the hit
for (const t of [24.4, 42.0, 52.4, 69.3, 78.6]) A.gap(t - 0.12, t - 0.012, { buses: ['str', 'solo', 'brass', 'choir', 'keys', 'low'], fade: 0.01 });
cue(24.28, 'music', 'Breaths: strings, brass, choir and keys stop for ~0.11 s right before the hits at 24.4 / 42.0 / 52.4 / 69.3 / 78.6 while the reverse cymbals keep swelling into them');
// the silence after the pin shears: only the ring and the deep groans, low
ride(['sfx'], [[30.25, 0], [30.4, -6], [31.45, -6], [31.58, 0]]);

const SECTIONS = { act1: [0, 14], act2: [14, 28], act3: [28, 42], act4: [42, 55], act5: [55, 70], act6: [70, 82], act7: [82, 90], tail: [90, 92], 'gap 30.3': [30.35, 31.55], 'leap 63.4': [63.5, 65.3] };
if (process.env.ANCHOR_STEMS) stemReport();
/** Debug (ANCHOR_STEMS=1): K-weighted loudness of each bus per section (ungated, bus gain included, before inserts). */
function stemReport() {
  const bq = (b, a) => { let x1 = 0; let x2 = 0; let y1 = 0; let y2 = 0; return (x) => { const y = b[0] * x + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2; x2 = x1; x1 = x; y2 = y1; y1 = y; return y; }; };
  const kw = () => { const f1 = bq([1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]); const f2 = bq([1, -2, 1], [1, -1.99004745483398, 0.99007225036621]); return (x) => f2(f1(x)); };
  const names = [...ALL]; const rows = {};
  for (const name of names) {
    const b = A.bus(name); const g = Math.pow(10, (b.opts.gain ?? 0) / 10); const fl = kw(); const fr = kw();
    const L = new Float64Array(b.L.length); for (let i = 0; i < L.length; i++) { const l = fl(b.L[i]); const r = fr(b.R[i]); L[i] = l * l + r * r; }
    for (const [sec, [t0, t1]] of Object.entries(SECTIONS)) {
      const i0 = Math.floor(t0 * A.SR); const i1 = Math.min(L.length, Math.floor(t1 * A.SR)); let sum = 0; for (let i = i0; i < i1; i++) sum += L[i];
      const ms = (sum / Math.max(1, i1 - i0)) * g; (rows[sec] ||= []).push(ms > 1e-12 ? (-0.691 + 10 * Math.log10(ms)).toFixed(1).padStart(7) : '      -');
    }
  }
  console.log(`K-weighted LUFS per bus (pre-master):
${''.padEnd(11)}${names.map((n) => n.padStart(7)).join('')}`);
  for (const [sec, cells] of Object.entries(rows)) console.log(`${sec.padEnd(11)}${cells.join('')}`);
}

const res = A.render(OUT, {
  lufs: -17, truePeak: -1.6, reverb: { room: 0.86, damp: 0.35, width: 1, predelay: 0.02 }, glue: 0.2, monoBass: 100, fadeOut: 0.6, report: true,
  sections: SECTIONS,
});

// ---- measure with ffmpeg (EBU R128 / BS.1770, the delivery check) and write the cue sheet ---------------------------------------
let meas = null;
const ff = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', OUT, '-af', 'loudnorm=print_format=summary', '-f', 'null', '-'], { encoding: 'utf8' });
if (ff.status === 0) {
  const g = (k) => { const m = new RegExp(`Input ${k}:\\s*([-+0-9.]+)`).exec(ff.stderr); return m ? Number(m[1]) : null; };
  meas = { I: g('Integrated'), TP: g('True Peak'), LRA: g('LRA') };
  console.log(`ffmpeg loudnorm: ${meas.I} LUFS integrated, true peak ${meas.TP} dBTP, LRA ${meas.LRA} LU`);
}
const SHOTS = [0, 3, 4.6, 7.4, 9.6, 11.2, 14, 16.4, 18.4, 20, 22, 24.4, 25.8, 28, 30, 31.6, 33.2, 35.2, 37.4, 39, 42, 44, 45.6, 47.4, 49, 52.4, 55, 57.4, 59, 61, 63.4, 65.4,
  67.2, 70, 72, 73.6, 76, 78.6, 80.6, 82, 84.4, 86.4, 88.2];
const shotAt = (t) => (t >= 90 ? 'tail' : String(SHOTS.reduce((a, s, i) => (s <= t + 1e-6 ? i + 1 : a), 1)).padStart(2, '0'));
const ORDER = { HIT: 0, music: 1, sfx: 2 };
const rows = [...CUES].sort((a, b) => a[0] - b[0] || ORDER[a[1]] - ORDER[b[1]]);
const hits = rows.filter((r) => r[1] === 'HIT');
const md = [
  '# ANCHOR: score cue sheet',
  '',
  `Rendered by \`node audio/score.mjs out/music.wav\` from the project root. All synthesized (no samples, no voices or speech). ${DUR.toFixed(1)} s, 48 kHz stereo 24-bit: 90 s of picture + a 2 s tail.`,
  meas ? `Measured with ffmpeg loudnorm: **${meas.I} LUFS integrated, true peak ${meas.TP} dBTP, LRA ${meas.LRA} LU**.` : `Toolkit master: ${res.I.toFixed(1)} LUFS integrated, true peak ${res.tp.toFixed(2)} dBTP.`,
  '',
  'Tempo grid: 150 bpm, 8th note = 0.2 s, so every shot boundary in BIBLE.md falls on the grid. Act 5 (the chase) is in 12/8 with a dotted quarter = 0.6 s = one footfall; Act 6 (the hold) is a heavy 3/4, bar = 1.2 s.',
  '',
  `**HIT** = hard sync point, the transient lands exactly on the listed time (${hits.length} of them): ${hits.map((r) => r[0].toFixed(1)).join(', ')}. **music** = score event, **sfx** = sound effect.`,
  '',
  '| time (s) | shot | kind | what |',
  '|---:|:---:|:---|:---|',
  ...rows.map(([t, k, w]) => `| ${t.toFixed(2)} | ${shotAt(t)} | ${k === 'HIT' ? '**HIT**' : k} | ${w.replace(/\|/g, '/')} |`),
  '',
];
fs.writeFileSync(path.join(HERE, 'cues.md'), md.join('\n'));
console.log(`wrote audio/cues.md (${rows.length} cues, ${hits.length} hard hits)`);
