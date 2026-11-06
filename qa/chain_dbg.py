import sys, os, math
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shots'))
import bake_chain as B, story as S

F_STOP = int(sys.argv[1]) if len(sys.argv) > 1 else 790
sim = B.Sim(B.rest_catenary(B.collar(0.0), S.ANCHOR))
def pins(t):
    b = B.bottom(t, None)
    return {0: B.collar(t)} if b is None else {0: B.collar(t), B.N - 1: b}
sim.pin_fn = pins; sim.guide_fn = B.guide
sim.calm = True
for _ in range(120): sim.step(0.0, 1.0 / 24); sim.prev = sim.P.copy()
sim.calm = False
orig_smooth = B.smooth_bends
log = []
def traced(P, top, bot, **kw):
    b0 = B.bends(P).max()
    Q = orig_smooth(P, top, bot, **kw)
    b1 = B.bends(Q).max()
    if b1 > 60: np.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fold_case.npy'), np.vstack((P, [top], [bot if bot is not None else (np.nan, np.nan, np.nan)])))
    log.append((b0, b1))
    return Q
B.smooth_bends = traced
for f in range(2, F_STOP + 1):
    t = (f - 1) / 24.0
    sim.wdrag = 0.45 if B.RELEASE <= t < 34.5 else 1.8
    log.clear()
    sim.step(t - 1.0 / 24, 1.0 / 24)
    if (t - 1.0 / 24) < B.RELEASE <= t:
        P = sim.P; dirs = np.zeros_like(P); dirs[1:] = P[:-1] - P[1:]
        dirs /= np.maximum(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-9)
        u = np.linspace(0.0, 1.0, len(P))[:, None]
        sim.kick(dirs * B.RECOIL * u ** 1.6 + np.array((0.0, 0.0, 6.0)) * u)
    bd = B.bends(sim.P).max()
    if bd > 22 or f >= F_STOP - 2:
        print(f, round(t, 3), 'pre-smooth %.1f post-smooth %.1f final %.1f' % (log[-1][0], log[-1][1], bd))
