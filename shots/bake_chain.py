# ANCHOR — bakes the chain for the whole film (frames 1..2160). Pure numpy (system Python).
#   0 .. 30.0 s : position-based simulation, top joint pinned to the city's collar, the last joint pinned to the anchor
#                 (both ends fixed: smooth, the chain sags and sways in the gale); blended into the kinematic chain over 29.5..30.0
#   30.0 .. 90  : kinematic: the analytic catenary from the collar to the chain's end, which rides story.end_guide (pin shear,
#                 whip, burst, skips, crane hit, trail, the skips away from the hand) and from the grab (69.3) the mech's palm;
#                 then the wrap round the lighthouse drum (story.wrap_geom: free span + drum arc + tail, exactly CHAIN_LEN long).
#                 Travelling waves for the events (pin shear, release, burst, lurch, crane hit, catch), a slow sway while it is
#                 dragged, the snap's ring, a hum while it holds, a shudder at the release; constraint projection (lengths,
#                 bend limit, drum, band, seabed). (A simulated free end was chaotic - folds, teleports - and was removed.)
#   python shots/bake_chain.py [--palm palm.npy] [--recoil R] [--until T]   -> out/track/chain.npy (2161 x 81 x 3), report
import sys, os, math, time, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import story as S

N = S.CHAIN_N + 1
SEG = S.PITCH
NF = 2160
KIN_T0 = 30.0           # kinematic from here (the simulated chain blends into it over BLEND seconds before)
BLEND = 0.5
RECOIL = 0.0            # optional kick along the chain at the release (m/s at the end); the designed end path does the whip
OUT = os.path.join(ROOT, 'out', 'track'); os.makedirs(OUT, exist_ok=True)


def collar(t):
    return S.collar(t)


def bed_full(x, y):
    """seabed + the west breakwater (cap z 5 on the trunk |x+700| < 12 and the head disc r < 45) as a floor for the chain."""
    z = S.bed(x, y)
    trunk = (np.abs(x + 700.0) < 12.0) & (y > -123.0) & (y < 400.0)
    head = np.hypot(x - S.LIGHTHOUSE[0], y - S.LIGHTHOUSE[1]) < S.HEAD_R
    return np.where(trunk | head, S.CAP_Z, z)


def fabrik(P, top, bot, iters=40):
    P = np.array(P, float); n = len(P)
    def fwd():
        P[0] = top; last = np.array((0.0, 0.0, -1.0))
        for i in range(1, n):
            d = P[i] - P[i - 1]; ln = np.linalg.norm(d)
            if ln < 1e-4: d = last; ln = 1.0
            d = d / ln
            if i >= 2 and np.dot(d, last) < 0.0: d = last      # never fold back on the previous segment
            last = d; P[i] = P[i - 1] + d * SEG
    if bot is None:          # free end: one pass from the pinned top gives exact lengths
        fwd(); return P
    for _ in range(iters):
        fwd()
        P[-1] = bot; last = np.array((0.0, 0.0, 1.0))
        for i in range(n - 2, -1, -1):
            d = P[i] - P[i + 1]; ln = np.linalg.norm(d)
            if ln < 1e-4: d = last; ln = 1.0
            d = d / ln
            if i <= n - 3 and np.dot(d, last) < 0.0: d = last
            last = d; P[i] = P[i + 1] + d * SEG
        if np.linalg.norm(P[0] - top) < 1e-3: break
    return P


def bends(P):
    a = P[1:-1] - P[:-2]; b = P[2:] - P[1:-1]
    cs = np.sum(a * b, axis=1) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-9)
    return np.degrees(np.arccos(np.clip(cs, -1.0, 1.0)))


def bridge(p0, p1, m):
    """m interior nodes so that p0, x1..xm, p1 is a hanging circular arc of length (m+1)*SEG (no folds by construction)."""
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float); L = (m + 1) * SEG
    ch = p1 - p0; D = np.linalg.norm(ch)
    if D < 1e-6: ch = np.array((0, 0, -1e-3)); D = 1e-3
    u = ch / D
    if D >= L * 0.999:
        return [p0 + ch * (k + 1) / (m + 1) for k in range(m)]
    lo, hi = 1e-6, 2 * math.pi - 1e-6           # L/D = th / (2 sin(th/2))
    for _ in range(80):
        th = 0.5 * (lo + hi)
        if th / (2 * math.sin(th / 2)) < L / D: lo = th
        else: hi = th
    th = 0.5 * (lo + hi); r = L / th
    down = np.array((0.0, 0.0, -1.0)) - u * u[2]
    if np.linalg.norm(down) < 1e-3: down = np.cross(u, (1.0, 0, 0))
    down /= np.linalg.norm(down)
    mid = (p0 + p1) * 0.5; ctr = mid - down * r * math.cos(th / 2)    # the arc's lowest point is ctr + down * r
    out = []
    for k in range(m):
        psi = -th / 2 + th * (k + 1) / (m + 1)
        out.append(ctr + r * (math.sin(psi) * u + math.cos(psi) * down))
    return out


def unfold(P, top, bot, lim=22.0):
    """replace any kinked stretch (Z-folds, sharp bends) by a hanging arc of the same chain length, then exact lengths."""
    n = len(P); P = np.array(P, float)
    hi_free = n - 2 if bot is not None else n - 1
    for _ in range(6):
        bd = bends(P); bad = np.where(bd > lim)[0] + 1
        if len(bad) == 0: break
        i = int(bad[0]); j = int(bad[-1]) if bad[-1] - bad[0] < 14 else i
        a_ = max(1, i - 4); b_ = min(hi_free, j + 4)
        if b_ == n - 1:          # free end inside the window: hang it straight on from a_-1 along the chain direction
            d = P[a_ - 1] - P[a_ - 2] if a_ >= 2 else np.array((0, 0, -1.0))
            d = d / max(np.linalg.norm(d), 1e-9)
            for k in range(a_, n): P[k] = P[a_ - 1] + d * SEG * (k - a_ + 1)
        else:
            P[a_:b_ + 1] = np.array(bridge(P[a_ - 1], P[b_ + 1], b_ - a_ + 1))
        P = fabrik(P, top, bot, 30)
    return P


def _relax(P, top, bot, max_bend, iters):
    n = len(P); cb = math.cos(math.radians(max_bend))
    for _ in range(iters):
        a = P[1:-1] - P[:-2]; b = P[2:] - P[1:-1]
        cs = np.sum(a * b, axis=1) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-9)
        bad = np.where(cs < cb)[0]
        if len(bad) == 0: break
        for k in bad:
            i = k + 1
            if 0 < i < n - 1: P[i] += ((P[i - 1] + P[i + 1]) * 0.5 - P[i]) * 0.5
        z = bed_full(P[:, 0], P[:, 1]) + 2.6; P[:, 2] = np.maximum(P[:, 2], z)
        P = fabrik(P, top, bot, 8)
    return P


def smooth_bends(P, top, bot, max_bend=19.0, iters=60):
    """exact lengths and no joint bent more than max_bend (the links interlock cleanly up to 25 deg), above the seabed.
    Only a true fold (> 60 deg) is cut out and re-hung as an arc."""
    P = _relax(fabrik(P, top, bot), top, bot, max_bend, iters)
    if bends(P).max() > 60.0:
        P = _relax(unfold(P, top, bot, lim=60.0), top, bot, max_bend, iters)
    return fabrik(P, top, bot)


class Sim:
    def __init__(s, P):
        s.P = np.array(P, float); s.prev = s.P.copy(); s.max_bend = math.radians(20.0); s.calm = False
        n = len(s.P); s.dmask = np.ones((n, 1)); s.dmask[-8:, 0] = np.linspace(1.0, 0.985, 8)
        s.guide_fn = lambda t: None; s.wdrag = 1.8; s.sub = 12

    def kick(s, v):
        s.prev = s.P - v * (1.0 / 24 / s.sub)

    def step(s, t, dt, iters=18):
        sub = s.sub; h = dt / sub
        for k in range(sub):
            tt = t + h * (k + 1)
            V = s.P - s.prev
            wet = s.P[:, 2] < 0.0
            damp = np.where(wet, math.exp(-s.wdrag * h), math.exp(-0.25 * h))[:, None] * s.dmask
            acc = np.zeros_like(s.P); acc[:, 2] -= 9.8 * np.where(wet, 0.87, 1.0)
            if not s.calm: acc += s.wind(tt) * (~wet)[:, None]
            g = s.guide_fn(tt)
            s.soft = None
            if g is not None:     # art-directed free end: a soft position pin toward the designed path
                tgt, alpha = g
                if alpha > 0: s.soft = (tgt, alpha)
            s.prev = s.P.copy()
            s.P = s.P + V * damp + acc * h * h
            pins = s.pin_fn(tt)
            for _ in range(iters):
                s._pin(pins); s._lengths(pins); s._bend(pins); s._collide(); s._pin(pins)
                if s.soft is not None: s.P[-1] += s.soft[1] * (s.soft[0] - s.P[-1])
            for _ in range(6): s._lengths(pins); s._pin(pins)
        pins = s.pin_fn(t + dt)
        Q = smooth_bends(s.P, pins[0], pins.get(len(s.P) - 1))
        s.prev += Q - s.P; s.P = Q

    def wind(s, t):
        n = len(s.P); u = np.linspace(0, 1, n)
        w = np.zeros((n, 3))
        w[:, 0] += 0.25 * math.sin(t * 0.37) + 0.12 * math.sin(t * 1.1 + 2.0)
        w[:, 1] += 0.18 * math.cos(t * 0.29 + 1.0)
        st = S.storm(t)
        if st > 0: w[:, 0] += 1.4 * st * (0.6 + 0.4 * math.sin(t * 0.8)); w[:, 1] += 0.6 * st * math.sin(t * 0.53)
        if 20.0 < t < S.RELEASE:  # the taut chain hums in the gale
            k = S.sstep(S.rng(t, 20.0, 22.0))
            w[:, 0] += k * 3.0 * np.sin(t * 21.0 + u * 9.0); w[:, 1] += k * 2.2 * np.sin(t * 17.0 + u * 7.0 + 1.0)
        return w

    def _pin(s, pins):
        for i, p in pins.items(): s.P[i] = p

    def _lengths(s, pins):
        P = s.P; n = len(P); w = np.ones(n)
        if getattr(s, 'soft', None) is not None: w[-1] = 0.3
        for i in pins: w[i] = 0.0
        for par in (0, 1):
            i = np.arange(par, n - 1, 2)
            d = P[i + 1] - P[i]; ln = np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
            corr = (ln - SEG) / ln * d
            wi = w[i][:, None]; wj = w[i + 1][:, None]; ws = np.maximum(wi + wj, 1e-9)
            P[i] += corr * wi / ws; P[i + 1] -= corr * wj / ws

    def _bend(s, pins):
        P = s.P
        a = P[1:-1] - P[:-2]; b = P[2:] - P[1:-1]
        c = np.sum(a * b, axis=1) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-9)
        for k in np.where(c < math.cos(s.max_bend))[0]:
            i = k + 1
            if i in pins: continue
            P[i] += ((P[i - 1] + P[i + 1]) * 0.5 - P[i]) * 0.4

    def _collide(s):
        P = s.P
        z = bed_full(P[:, 0], P[:, 1]) + 2.6
        m = P[:, 2] < z; P[m, 2] = z[m]


# ------------------------------------------------------------------------------------------------------------------- kinematic
def catenary2(p0, p1, L, n=400):
    """n points along a hanging chain of length L from p0 to p1 (analytic catenary in their vertical plane); + shortfall."""
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float); d = p1 - p0
    h = math.hypot(d[0], d[1]); v = d[2]; chord = math.hypot(h, v)
    if L <= chord + 1e-6 or h < 1e-3: return np.linspace(p0, p1, n), max(0.0, chord - L)
    target = math.sqrt(L * L - v * v)
    lo, hi = 1e-3 * h, 1e7 * h
    for _ in range(200):
        a = math.sqrt(lo * hi)
        if 2 * a * math.sinh(min(h / (2 * a), 700.0)) > target: lo = a
        else: hi = a
    a = math.sqrt(lo * hi); m = math.atanh(max(-0.999999, min(0.999999, v / L))); x0 = h / 2 - a * m
    xs = np.linspace(0, h, n); zs = a * np.cosh((xs - x0) / a) - a * math.cosh(-x0 / a)
    u = np.array((d[0] / h, d[1] / h, 0.0))
    return p0 + np.outer(xs, u) + np.outer(zs, (0, 0, 1.0)), 0.0


def resample(poly, n, seg):
    poly = np.asarray(poly, float); dl = np.linalg.norm(np.diff(poly, axis=0), axis=1); cum = np.concatenate(([0], np.cumsum(dl)))
    out = []
    for k in range(n):
        s_ = min(k * seg, cum[-1]); i = min(max(int(np.searchsorted(cum, s_, side='right')) - 1, 0), len(dl) - 1)
        u = (s_ - cum[i]) / max(dl[i], 1e-9); out.append(poly[i] + (poly[i + 1] - poly[i]) * u)
    return np.array(out)


def _direct(t, pal):
    poly, short = catenary2(collar(t), pal, S.CHAIN_LEN + S.end_cut(t))     # the last joint stops end_cut short of the palm
    return resample(poly, N, SEG), short


FILLET = S.FILLET       # links over which the free span lifts out of the groove (the bend is shared, no kink at the lip)


def _wrapped(t, pal, g):
    c = S.LIGHTHOUSE[:2]; R = S.WRAP_R
    na = max(2, int(g['arc'] / 2.0) + 1)
    ang = np.radians(np.linspace(g['T1'], g['T2'], na)); zz = np.linspace(S.WRAP_Z[0], S.WRAP_Z[1], na)
    arcpts = np.stack((c[0] + R * np.cos(ang), c[1] + R * np.sin(ang), zz), 1)
    tail = np.linspace(arcpts[-1], pal, 12)
    a1 = math.radians(g['T1']); tcw = np.array((math.sin(a1), -math.cos(a1), 0.0))     # leaves the drum clockwise, toward the city
    poly, short = _lift(collar(t), arcpts[0], tcw, g['L_free'])
    return resample(np.vstack((poly, arcpts[1:], tail[1:])), N, SEG), short


def _lift(col, q0, plan_dir, L):
    """from q0 the chain lifts over FILLET links (elevation shared out) and hangs to the collar; returns the poly collar -> q0."""
    free0, _ = catenary2(col, q0, L)
    d0 = free0[-6] - free0[-1]; phi0 = max(0.0, math.atan2(d0[2], math.hypot(d0[0], d0[1])))
    fil = [np.asarray(q0, float)]
    for k in range(1, FILLET + 1):
        e = phi0 * k / (FILLET + 1)
        fil.append(fil[-1] + SEG * (plan_dir * math.cos(e) + np.array((0.0, 0.0, math.sin(e)))))
    free, short = catenary2(col, fil[-1], L - FILLET * SEG)
    return np.vstack((free, np.array(fil[::-1][1:]))), short


def _grip(t, pal, g):
    col = collar(t); d = col - pal; dh = np.array((d[0], d[1], 0.0)); u = dh / max(np.linalg.norm(dh), 1e-9)
    q0 = pal + u * g['L_grip'] + np.array((0.0, 0.0, g.get('dz_grip', 0.0)))     # down to the wrap's height (the fist is higher)
    poly, short = _lift(col, q0, u, S.CHAIN_LEN + S.end_cut(t) - float(np.linalg.norm(q0 - pal)))
    return resample(np.vstack((poly, np.linspace(q0, pal, 12)[1:])), N, SEG), short


T_ON = None             # when the chain first touches the drum (set in main)


def kin_chain(t, pal):
    if t < S.T['grab'] + 0.2:       # free / just caught: the plain hanging chain to the end (no wrap geometry yet)
        Pd, short = _direct(t, pal)
        return Pd, short, {'arc': 0.0}
    g = S.wrap_geom(t, collar(t), pal)
    if g['arc'] <= 0.0 or T_ON is None or t < T_ON:
        Pd, short = _direct(t, pal)
        wg = g.get('w_grip', 0.0)
        if wg <= 0.0: return Pd, short, g
        Pg, short = _grip(t, pal, g)
        return (Pd * (1 - wg) + Pg * wg) if wg < 1.0 else Pg, short, g
    Pw, short = _wrapped(t, pal, g)
    return Pw, short, g


def vibrate(P, t):
    """the held span: the snap at 70.0 rings out, a strain hum while it is dragged and hauled, a hum while it holds the city,
    a shudder when the spout lets go (80.6). Low frequencies only (>= 6 frames a cycle)."""
    P = np.array(P, float)
    amp = 0.0; f1, f2 = 2.2, 3.7
    tt = S.T['taut']; ts = S.T['slack']
    if t >= tt: amp += 2.4 * math.exp(-(t - tt) * 3.0) * S.sstep(S.rng(t, tt, tt + 0.12))
    amp += 0.22 * S.sstep(S.rng(t, tt, tt + 0.6)) * (1.0 - S.sstep(S.rng(t, 75.6, 76.4)))
    amp += 0.5 * S.sstep(S.rng(t, 77.8, 78.4)) * (1.0 - S.sstep(S.rng(t, ts, ts + 1.2)))
    if t >= ts: amp += 2.6 * math.exp(-(t - ts) * 2.2) * S.sstep(S.rng(t, ts, ts + 0.15))
    if amp <= 1e-4: return P
    d = np.hypot(P[:, 0] - S.LIGHTHOUSE[0], P[:, 1] - S.LIGHTHOUSE[1]); touch = np.where(d < S.WRAP_R + 0.8)[0]
    k1 = int(touch[0]) if len(touch) else len(P) - 1
    if k1 < 4: return P
    span = P[k1] - P[0]; u = span / np.linalg.norm(span)
    side = np.cross(u, (0, 0, 1.0)); side /= max(np.linalg.norm(side), 1e-9); up = np.cross(side, u)
    for i in range(1, k1):
        s_ = i / k1
        w = math.sin(math.pi * s_) * math.sin(t * 2 * math.pi * f1 + s_ * 2.0) + 0.4 * math.sin(2 * math.pi * s_) * math.sin(t * 2 * math.pi * f2)
        P[i] += (side * 0.8 + up * 0.6) * amp * w
    return P


# (t0, amplitude m, runs from 'end' | 'top', speed m/s, pulse width m, decay 1/s)
EVENTS = [
    (S.T['pin_shear'], 1.4, 'end', 170.0, 45.0, 1.4),     # the pin shears: a jolt runs up the chain
    (S.RELEASE, 5.5, 'end', 150.0, 60.0, 0.8),            # the link rips free: the whip wave runs up to the city
    (S.T['burst'], 3.0, 'end', 170.0, 50.0, 1.0),         # it tears out of the sea
    (S.T['lurch'], 4.5, 'top', 170.0, 70.0, 0.9),         # the city lurches: a wave runs down from the collar
    (S.T['crane_hit'], 5.0, 'end', 150.0, 55.0, 0.8),     # the end smashes crane A
    (S.T['grab'], 2.2, 'end', 190.0, 45.0, 1.8),          # caught
]


def waves(P, t):
    """event pulses travelling along the chain + a slow sway while it hangs free (30 .. 70), on a frame perpendicular to the
    span (zero at both pinned ends). Small offsets (a few metres on 420 m): the projection after it only trims lengths."""
    if t < S.T['pin_shear'] - 0.01 or t > S.T['taut'] + 3.0: return P
    P = np.array(P, float); n = len(P)
    sp = P[-1] - P[0]; L = np.linalg.norm(sp)
    if L < 1e-3: return P
    u = sp / L
    side = np.cross(u, (0.0, 0.0, 1.0)); ns = np.linalg.norm(side)
    side = side / ns if ns > 1e-3 else np.array((1.0, 0.0, 0.0))
    up = np.cross(side, u)
    s_ = np.arange(n) * SEG; Ls = s_[-1]
    env = np.sin(np.pi * s_ / Ls) ** 0.5
    off_s = np.zeros(n); off_u = np.zeros(n)
    for (t0, A, frm, v, w, dk) in EVENTS:
        if t < t0: continue
        dt = t - t0
        a = A * math.exp(-dk * dt) * S.sstep(S.rng(t, t0, t0 + 0.12))
        if a < 1e-3: continue
        c = Ls - v * dt if frm == 'end' else v * dt
        g = np.exp(-((s_ - c) / w) ** 2)
        off_s += a * g; off_u += 0.45 * a * g * np.sin((s_ - c) / w * 2.2)
    # slow sway of the hanging chain (fundamental + second mode), only between the release and the snap
    k = S.sstep(S.rng(t, S.RELEASE, S.RELEASE + 1.5)) * (1.0 - S.sstep(S.rng(t, S.T['grab'], S.T['taut'])))
    if k > 0:
        x = s_ / Ls
        off_s += k * (2.6 * np.sin(np.pi * x) * math.sin(2 * math.pi * 0.31 * t + 0.4)
                      + 0.9 * np.sin(2 * np.pi * x) * math.sin(2 * math.pi * 0.53 * t + 1.7))
        off_u += k * 1.2 * np.sin(np.pi * x) * math.sin(2 * math.pi * 0.23 * t + 2.2)
    P += env[:, None] * (off_s[:, None] * side + off_u[:, None] * up)
    return P


def _on_arc(P, g, r):
    """the joints lying on the drum: inside the wrap's angular range (T1 .. T2 counter-clockwise, 1 deg either side) and on the
    wrap radius. The joints of the tail and of the span past the tangent points are free (a band clamp there kinks the chain)."""
    if g is None or g.get('arc', 0.0) <= 0.0 or 'T1' not in g: return np.zeros(len(P), bool)
    c = S.LIGHTHOUSE[:2]; th = np.degrees(np.arctan2(P[:, 1] - c[1], P[:, 0] - c[0]))
    d = (th - g['T1'] + 1.0) % 360.0
    return (d <= g['arc'] + 2.0) & (r < S.WRAP_R + 0.25) & (P[:, 2] < S.LH_TOP + 3.0)


def relax_wrap(P, top, bot, iters=60, max_bend=19.0, g=None):
    """constraint projection: bend limit, the drum (nothing inside the chain's wrap radius below the bastion top), the band
    for the links lying on the drum (story.wrap_geom's arc `g`), exact lengths."""
    P = np.array(P, float); n = len(P); c = S.LIGHTHOUSE[:2]; cb = math.cos(math.radians(max_bend))
    for _ in range(iters):
        a = P[1:-1] - P[:-2]; b = P[2:] - P[1:-1]
        cs = np.sum(a * b, axis=1) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-9)
        for k in np.where(cs < cb)[0]:
            i = k + 1
            if 0 < i < n - 1: P[i] += ((P[i - 1] + P[i + 1]) * 0.5 - P[i]) * 0.5
        d = P[:, :2] - c; r = np.linalg.norm(d, axis=1)
        m = (r < S.WRAP_R) & (P[:, 2] < S.LH_TOP + 3.0)
        if m.any(): P[m, :2] = c + d[m] / np.maximum(r[m, None], 1e-9) * S.WRAP_R
        on = _on_arc(P, g, np.linalg.norm(P[:, :2] - c, axis=1))
        if on.any(): P[on, 2] = np.clip(P[on, 2], S.GROOVE[0], S.GROOVE[1])
        z = bed_full(P[:, 0], P[:, 1]) + 2.6; P[:, 2] = np.maximum(P[:, 2], z)
        P = fabrik(P, top, bot, 6)
    return P


# ------------------------------------------------------------------------------------------------------------------- driver
RELEASE = S.RELEASE     # the end link rips out of the sheared shackle; from here the chain is free (recoil kick)


def guide_tau(t):
    """time constant (s) with which the free end follows story.end_guide (None = free)."""
    if t < RELEASE: return None
    if t < RELEASE + 0.3: return 0.12 / max(1e-3, S.sstep(S.rng(t, RELEASE, RELEASE + 0.3))) ** 2
    if t < 35.4: return 0.12
    if t < 37.1: return 0.12 + 0.13 * S.sstep(S.rng(t, 35.4, 37.1))
    if t < 40.5: return 0.25
    if t < 42.0: return 0.25 - 0.21 * S.sstep(S.rng(t, 40.5, 42.0))
    if t < 43.1: return 0.04
    if t < 45.5: return 0.04 + 0.21 * S.sstep(S.rng(t, 43.1, 45.5))
    if t < 65.0: return 0.25
    return 0.25 - 0.22 * S.sstep(S.rng(t, 65.0, 68.8))


def guide(t):
    return None              # the end is pinned to story.end_guide (see bottom); kept for experiments
    if t < RELEASE or t > S.T['grab']: return None
    tau = guide_tau(t)
    if tau is None: return None
    per_frame = min(0.95, 1.0 / (24.0 * tau))
    alpha = 1.0 - (1.0 - per_frame) ** (1.0 / (12 * 18))
    return S.end_guide(t), alpha


def palm_at(t, palm=None):
    if palm is not None:
        f = int(round(t * 24)) + 1
        return palm[min(max(f, 0), len(palm) - 1)]
    return S.palm_path(t)


def bottom(t, palm=None):
    if t < S.T['pin_shear']: return S.ANCHOR.copy()
    if t <= S.T['grab']: return S.end_guide(t)
    return palm_at(t, palm)


def rest_catenary(p0, p1):
    poly, _ = catenary2(p0, p1, S.CHAIN_LEN)
    P = resample(poly, N, SEG)
    z = bed_full(P[:, 0], P[:, 1]) + 2.6; P[:, 2] = np.maximum(P[:, 2], z)
    return fabrik(P, p0, p1)


def project(P, top, bot, iters=40):
    P = fabrik(P, top, bot)
    P = _relax(P, top, bot, 19.0, iters)
    return fabrik(P, top, bot)


LAST = [NF]
OUTNAME = 'chain'        # --out NAME: write NAME.npy / NAME_report.json (default chain.npy / chain_report.json)


def temporal_filter(out, f0, f1, palm=None, sigma=1.0):
    """Gaussian in time over the free / dragged stretch, then exact lengths and bends again (top on the collar, the end on the
    palm once it is caught)."""
    rad = int(math.ceil(3 * sigma)); ker = np.exp(-0.5 * (np.arange(-rad, rad + 1) / sigma) ** 2)
    src = out.copy()
    for f in range(f0, f1 + 1):
        lo = max(1, f - rad); hi = min(f1 + rad, NF, f + rad, LAST[0])
        w = ker[lo - f + rad: hi - f + rad + 1]; w = w / w.sum()
        P = np.tensordot(w, src[lo:hi + 1], axes=(0, 0))
        t = (f - 1) / 24.0
        bot = palm_at(t, palm) if t > S.T['grab'] else P[-1].copy()     # the free end keeps its filtered (smooth) path
        out[f] = project(P, collar(t), bot)
    return out


def sim_run(palm, recoil, until):
    sim = Sim(rest_catenary(collar(0.0), S.ANCHOR))
    def pins(t):
        b = bottom(t, palm)
        return {0: collar(t)} if b is None else {0: collar(t), N - 1: b}
    sim.pin_fn = pins
    sim.guide_fn = guide
    sim.calm = True
    for _ in range(120): sim.step(0.0, 1.0 / 24); sim.prev = sim.P.copy()   # settle without wind, kill velocity
    sim.calm = False
    fN = min(NF, int(round(until * 24)) + 1)
    out = np.zeros((NF + 1, N, 3))
    for f in range(1, fN + 1):
        t = (f - 1) / 24.0
        if f > 1:
            sim.wdrag = 0.45 if RELEASE <= t < RELEASE + 2.9 else 1.8
            sim.step(t - 1.0 / 24, 1.0 / 24)
            if recoil > 0 and (t - 1.0 / 24) < RELEASE <= t:   # optional recoil kick toward the city
                P = sim.P; dirs = np.zeros_like(P); dirs[1:] = P[:-1] - P[1:]
                dirs /= np.maximum(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-9)
                u = np.linspace(0.0, 1.0, len(P))[:, None]
                sim.kick(dirs * recoil * u ** 1.6 + np.array((0.0, 0.0, 6.0)) * u)
        out[f] = sim.P
    return out, fN


def burst_time(out, fN):
    E = out[:, -1]; f0 = int(round(RELEASE * 24)) + 1
    for f in range(f0, fN + 1):
        if E[f, 2] > 0.0 and E[f - 1, 2] <= 0.0: return (f - 1) / 24.0
    return None


def main():
    global T_ON
    args = sys.argv[1:]
    palm = None; recoil = RECOIL
    if '--palm' in args: palm = np.load(args[args.index('--palm') + 1])
    global OUTNAME
    if '--out' in args: OUTNAME = args[args.index('--out') + 1]
    t0 = time.time()
    out, fN = sim_run(palm, recoil, KIN_T0 + 0.05)
    np.save(os.path.join(OUT, 'chain_pbd_raw.npy'), out[:fN + 1].astype(np.float32))
    fb = int(round((KIN_T0 - BLEND) * 24)) + 1
    def end_at(t):
        return bottom(t, palm)
    # the wrap onset: first time the palm's line to the city crosses the drum
    for f in range(int(round(75.0 * 24)) + 1, NF + 1):
        t = (f - 1) / 24.0
        if S.wrap_geom(t, collar(t), palm_at(t, palm))['arc'] > 0.0: T_ON = t; break
    shorts = []
    for f in range(fb, NF + 1):
        t = (f - 1) / 24.0; e = end_at(t)
        P, short, g = kin_chain(t, e)
        if S.end_cut(t) > 0.0: e = P[-1].copy()      # the cut end (end_cut back along the chain from the palm) is the pin
        if short > 0.05: shorts.append((f, round(short, 2)))
        P = relax_wrap(vibrate(waves(P, t), t), collar(t), e, max_bend=21.0 if t < S.T['grab'] + 1.0 else 19.0, g=g)
        if t < KIN_T0:       # the simulated taut chain (pinned at both ends) hands over to the kinematic one
            u = S.sstep(S.rng(t, KIN_T0 - BLEND, KIN_T0))
            P = project(out[f] * (1 - u) + P * u, collar(t), e)
        out[f] = P
    out[0] = out[1]
    rep = []
    for f in range(1, NF + 1):
        P = out[f]; seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        rep.append((f, round(float(np.abs(seg - SEG).max()), 3), round(float(bends(P).max()), 1)))
    np.save(os.path.join(OUT, OUTNAME + '.npy'), out.astype(np.float32))
    bad_len = [r for r in rep if r[1] > 0.05]
    bad_bend = [r for r in rep if r[2] > 22.0]
    bt = None
    for f in range(int(round(S.RELEASE * 24)) + 1, NF):
        if out[f, -1, 2] > 0.0 and out[f - 1, -1, 2] <= 0.0: bt = (f - 1) / 24.0; break
    R = dict(frames=len(rep), burst=bt, wrap_onset=T_ON, len_err_frames=len(bad_len), len_examples=bad_len[:10],
             bend_over22=len(bad_bend), bend_examples=bad_bend[:10], max_bend=max(r[2] for r in rep),
             max_len_err=max(r[1] for r in rep), wrap_short=shorts[:10], n_short=len(shorts), secs=round(time.time() - t0, 1))
    json.dump(R, open(os.path.join(OUT, OUTNAME + '_report.json'), 'w'), indent=1)
    print(json.dumps(R))


if __name__ == '__main__':
    main()
