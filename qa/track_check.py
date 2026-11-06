"""numeric checks of the baked chain track (out/track/chain.npy): events for FX, jitter, sag of the held span, solids.
usage: python qa/track_check.py            -> prints a report and writes out/track/events.json"""
import sys, os, math, json
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'shots'))
import story as S

C = np.load(os.path.join(ROOT, 'out', 'track', 'chain.npy'))      # (2161, 81, 3), index = frame
NF = C.shape[0] - 1
t_of = lambda f: (f - 1) / 24.0
f_of = lambda t: int(round(t * 24)) + 1
E = C[:, -1]
ev = {}

# 1) the end bursts out of the sea after the release
rel = f_of(31.1)
fs = [f for f in range(rel, f_of(40)) if E[f, 2] > 0.0 and E[f - 1, 2] <= 0.0]
if fs:
    f = fs[0]; ev['burst'] = dict(frame=f, t=round(t_of(f), 3), pos=[round(float(v), 2) for v in E[f]],
                                  vel=[round(float(v), 2) for v in (E[f + 1] - E[f - 1]) * 12.0])
pk = max(range(rel, f_of(40)), key=lambda f: E[f, 2])
ev['end_apex'] = dict(frame=pk, t=round(t_of(pk), 3), pos=[round(float(v), 2) for v in E[pk]])
# every node that crosses the surface going up in 31..40 (the chain tears out of the sea: spray column)
ups = []
for f in range(rel, f_of(40)):
    m = np.where((C[f, :, 2] > 0.0) & (C[f - 1, :, 2] <= 0.0))[0]
    for i in m: ups.append((f, int(i)))
ev['surface_exits'] = len(ups)
if ups:
    ev['surface_exit_first'] = dict(frame=ups[0][0], t=round(t_of(ups[0][0]), 3), node=ups[0][1])
    ev['surface_exit_last'] = dict(frame=ups[-1][0], t=round(t_of(ups[-1][0]), 3), node=ups[-1][1])

# 2) the end's touch-downs on the sea 35..69.3 (skips): local minima of its height below 1.6 m = a splash each
skips = []
for f in range(f_of(35.0), f_of(69.3)):
    if E[f, 2] < 1.6 and E[f, 2] <= E[f - 1, 2] and E[f, 2] < E[f + 1, 2]:
        v = (E[f + 1] - E[f - 1]) * 12.0
        skips.append(dict(frame=f, t=round(t_of(f), 3), pos=[round(float(x), 1) for x in E[f]], speed=round(float(np.linalg.norm(v)), 1)))
ev['skips'] = skips
ev['n_skips'] = len(skips)
ev['grab'] = dict(frame=f_of(S.T['grab']), t=S.T['grab'], pos=[round(float(v), 2) for v in E[f_of(S.T['grab'])]])
fl = f_of(35.4); ev['landing'] = dict(frame=fl, t=35.4, pos=[round(float(v), 2) for v in E[fl]])

# 3) crane hit: closest approach of the end to CRANE_HIT
fc = min(range(f_of(41), f_of(44)), key=lambda f: np.linalg.norm(E[f] - S.CRANE_HIT))
ev['crane_hit'] = dict(frame=fc, t=round(t_of(fc), 3), pos=[round(float(v), 2) for v in E[fc]],
                       dist=round(float(np.linalg.norm(E[fc] - S.CRANE_HIT)), 2),
                       vel=[round(float(v), 1) for v in (E[fc + 1] - E[fc - 1]) * 12.0])

# 4) jitter: frame-to-frame acceleration of every node (m/s^2), report the worst outside the release kick
acc = np.zeros(C.shape[:2])
acc[2:-1] = np.linalg.norm(C[3:] - 2 * C[2:-1] + C[1:-2], axis=2) * 576.0
spans = [(1, 740), (740, f_of(31.0)), (f_of(31.4), f_of(35.5)), (f_of(35.5), f_of(41)), (f_of(41), f_of(46)),
         (f_of(46), f_of(65)), (f_of(65), f_of(69.2)), (f_of(69.3), f_of(76)), (f_of(76), NF - 1)]
jit = []
for a, b in spans:
    blk = acc[a:b]
    i = np.unravel_index(np.argmax(blk), blk.shape)
    # sign flips of the end's acceleration in consecutive frames = visible shake
    ae = C[a + 1:b + 1, -1] - 2 * C[a:b, -1] + C[a - 1:b - 1, -1]
    flips = int(np.sum(np.sum(ae[1:] * ae[:-1], axis=1) < 0))
    jit.append(dict(t0=round(t_of(a), 2), t1=round(t_of(b), 2), max_acc=round(float(blk.max()), 1),
                    at_t=round(t_of(a + i[0]), 3), node=int(i[1]), p95=round(float(np.percentile(blk, 95)), 1),
                    end_flip_frac=round(flips / max(1, b - a), 2)))
ev['jitter'] = jit

# 5) held span during the wrap: free length vs chord, max sag off the chord
held = []
for t in (76.0, 76.5, 77.0, 77.5, 78.0, 78.4, 79.0, 79.4, 80.0, 80.6, 81.0, 82.0, 84.0, 86.0, 88.0, 90.0):
    f = min(f_of(t), NF); P = C[f]
    d = np.hypot(P[:, 0] - S.LIGHTHOUSE[0], P[:, 1] - S.LIGHTHOUSE[1])
    tch = np.where(d < S.WRAP_R + 0.8)[0]
    if not len(tch): continue
    k1 = int(tch[0]); ch = P[k1] - P[0]; L = k1 * S.PITCH; c = np.linalg.norm(ch); u = ch / c
    off = P[:k1 + 1] - P[0]; perp = off - np.outer(off @ u, u); sag = float(np.max(np.linalg.norm(perp, axis=1)))
    held.append(dict(t=t, k1=k1, free_len=round(L, 1), chord=round(float(c), 1), ratio=round(L / c, 4), sag=round(sag, 1),
                     min_z=round(float(P[:, 2].min()), 2), wrapped_nodes=int(len(tch))))
ev['held_span'] = held

# 6) analytic solids: drum below the band, the breakwater head cap, seabed
pen = []
for f in range(1, NF + 1):
    P = C[f]; t = t_of(f)
    d = np.hypot(P[:, 0] - S.LIGHTHOUSE[0], P[:, 1] - S.LIGHTHOUSE[1])
    inside = (d < S.LH_R - 0.05) & (P[:, 2] > 5.0) & (P[:, 2] < S.LH_TOP + 8)
    head = (d < S.HEAD_R) & (P[:, 2] < S.CAP_Z - 0.3)
    bed = P[:, 2] < np.array([S.bed(x, y) for x, y in P[:, :2]]) - 0.3 if t < 31.5 else np.zeros(len(P), bool)
    for name, m in (('drum', inside), ('head_cap', head), ('seabed', bed)):
        if m.any(): pen.append((name, round(t, 3), int(np.where(m)[0][0]), int(m.sum())))
ev['penetrations'] = pen[:40]; ev['n_penetrations'] = len(pen)

# 7) where the chain is over the quay / dock land (y > 400) close to the ground: needs PORT geometry to judge
land = []
for f in range(f_of(38), f_of(50)):
    P = C[f]; m = (P[:, 1] > 400.0) & (P[:, 2] < 12.0) & (P[:, 0] > -560) & (P[:, 0] < -300)
    if m.any(): land.append((round(t_of(f), 3), int(m.sum()), round(float(P[m, 2].min()), 1), round(float(P[m, 1].max()), 1)))
ev['low_over_land'] = land[:30]; ev['n_low_over_land'] = len(land)

json.dump(ev, open(os.path.join(ROOT, "out", "track", "events.json"), "w"), indent=1, default=float)
for k, v in ev.items():
    if isinstance(v, list) and v and isinstance(v[0], dict):
        print(k); [print('   ', x) for x in v]
    else:
        print(k, v)
