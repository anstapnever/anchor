# ANCHOR — unit 07's choreography as numbers (pure numpy, no bpy): where the mech is, where each foot is planted, how each swing
# clears the set, when it splashes. The ground is out/track/ground.npz (bake_ground.py: the real PORT + UNDER set, ray-cast), so a
# planted sole sits exactly on what renders. Used by mechanim.py (Blender: poses + IK per frame), by the FX keying and by the shots.
#   root_at(t) -> np.array((x, y, z, yaw))   z = the floor under the pelvis (mechanim adds the pose's hips offset); yaw 0 = facing -Y
#                                            facing = (sin yaw, -cos yaw), the mech's LEFT = (cos yaw, sin yaw)  (rig: left = +X)
#   foot_at(t, 'L'|'R') -> dict(p, yaw, pitch, roll, planted, lift) or None (in the air, the pose drives the leg)  pitch + = toes down
#   PLANTS [dict(t, lift, side, p, yaw, pitch, roll, gap, kind, A)]   SPLASHES [(t, (x, y, z_water), size, kind, side)]
#   ground_z / ground_hi / water_z / fit_plant / hand_local(t) (the left palm in the root frame while it holds the chain)
# Story (left hand on the chain from the grab): sleep -> rise 49.0 -> first step 52.4 -> run 54.6..63.4 (out of dock 3 over the caisson,
# through the shallows, along the west breakwater, round the WEST side of the lighthouse drum) -> two-footed leap 63.4 -> lands waist-deep
# 65.4 well west of the chain -> wades, reaches 67.2, grabs 69.3 (facing S, the end at its left front) -> yanked 70.0, dragged 18 m with
# both hands on the chain -> pivots clockwise round the hand 72.0..72.8 (the chain stays outside its body) -> hauls north, climbs the
# head's mound -> crouches into the counter-clockwise wind round the drum 76.0..78.2 (drum on its left) -> holds -> kneels after the slack.
import math, os
import numpy as np
import story as S

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
_GD = np.load(os.path.join(ROOT, 'out', 'track', 'ground.npz'))
GX0, GY0, GRES = float(_GD['x0']), float(_GD['y0']), float(_GD['res'])
GH = _GD['H'].astype(np.float64); GNY, GNX = GH.shape
LH = S.LIGHTHOUSE[:2].astype(float)


def ss(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
def lerp(a, b, u): return a + (b - a) * u
def wrap180(a): return (a + 180.0) % 360.0 - 180.0
def rot2(yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw)); return np.array(((c, -s), (s, c)))
def to_world(root, yaw, lxy): return np.asarray(root[:2], float) + rot2(yaw) @ np.asarray(lxy, float)
def to_local(root, yaw, wxy): return rot2(yaw).T @ (np.asarray(wxy[:2], float) - np.asarray(root[:2], float))
def facing(yaw): return np.array((math.sin(math.radians(yaw)), -math.cos(math.radians(yaw))))
def yaw_of(d): return math.degrees(math.atan2(d[0], -d[1]))


def catmull_keys(keys, t):
    """Catmull-Rom through (t, value-tuple) keys with non-uniform times; clamps outside."""
    ts = [k[0] for k in keys]
    if t <= ts[0]: return np.array(keys[0][1], float)
    if t >= ts[-1]: return np.array(keys[-1][1], float)
    i = max(0, min(len(ts) - 2, int(np.searchsorted(ts, t, side='right')) - 1))
    p1 = np.array(keys[i][1], float); p2 = np.array(keys[i + 1][1], float); t1, t2 = ts[i], ts[i + 1]
    p0 = np.array(keys[i - 1][1], float) if i > 0 else p1 - (p2 - p1); t0 = ts[i - 1] if i > 0 else t1 - (t2 - t1)
    p3 = np.array(keys[i + 2][1], float) if i + 2 < len(ts) else p2 + (p2 - p1); t3 = ts[i + 2] if i + 2 < len(ts) else t2 + (t2 - t1)
    m1 = (p2 - p0) / (t2 - t0) * (t2 - t1); m2 = (p3 - p1) / (t3 - t1) * (t2 - t1)
    u = (t - t1) / (t2 - t1); u2 = u * u; u3 = u2 * u
    return (2 * u3 - 3 * u2 + 1) * p1 + (u3 - 2 * u2 + u) * m1 + (-2 * u3 + 3 * u2) * p2 + (u3 - u2) * m2


def pchip_keys(keys, t):
    """monotone cubic through (t, value-tuple) keys: no overshoot between equal or turning keys."""
    ts = np.array([k[0] for k in keys], float); V = np.array([k[1] for k in keys], float)
    if t <= ts[0]: return V[0].copy()
    if t >= ts[-1]: return V[-1].copy()
    h = np.diff(ts); dl = np.diff(V, axis=0) / h[:, None]
    m = np.zeros_like(V)
    for c in range(V.shape[1]):
        for i in range(1, len(ts) - 1):
            a, b = dl[i - 1, c], dl[i, c]
            if a * b > 0:
                w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]; m[i, c] = (w1 + w2) / (w1 / a + w2 / b)
    i = max(0, min(len(ts) - 2, int(np.searchsorted(ts, t, side='right')) - 1))
    u = (t - ts[i]) / h[i]; u2 = u * u; u3 = u2 * u
    return (2 * u3 - 3 * u2 + 1) * V[i] + (u3 - 2 * u2 + u) * h[i] * m[i] + (-2 * u3 + 3 * u2) * V[i + 1] + (u3 - u2) * h[i] * m[i + 1]


# ================================================================================================================= ground + water
def _cells(x, y):
    fx = (np.asarray(x, float) - GX0) / GRES; fy = (np.asarray(y, float) - GY0) / GRES
    i = np.clip(np.floor(fx).astype(int), 0, GNX - 2); j = np.clip(np.floor(fy).astype(int), 0, GNY - 2)
    return fx, fy, i, j


def ground_z(x, y):
    fx, fy, i, j = _cells(x, y); u = np.clip(fx - i, 0, 1); v = np.clip(fy - j, 0, 1)
    z = GH[j, i] * (1 - u) * (1 - v) + GH[j, i + 1] * u * (1 - v) + GH[j + 1, i] * (1 - u) * v + GH[j + 1, i + 1] * u * v
    return float(z) if np.ndim(z) == 0 else z


def _ssv(x): x = np.clip(x, 0.0, 1.0); return x * x * (3 - 2 * x)


def virtual_z(x, y):
    """under the opaque sea the set's mound toes are cliffs onto the analytic seabed (-27 .. -37); the mech walks up invisible
    ramps there instead (they only ever RAISE the floor, so a sole never enters real geometry; never above -0.6 m)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    r = np.hypot(x - LH[0], y - LH[1])
    head = np.where(r < 64.0, -0.6 - 8.4 * _ssv((r - 50.0) / 14.0), -9.0 - 27.0 * _ssv((r - 64.0) / 21.0))
    dx = np.abs(x + 700.0)
    trunk = np.where((y > -130.0) & (y < 400.0), -10.0 - 22.0 * _ssv((dx - 34.0) / 55.0), -99.0)
    # the haul up the head (72.8 .. 75.3): a long ramp up its southern flank to just under the waterline at the cap's foot (r 50),
    # inside the bearing sector of the path (the real flank is ~45 deg: a striding mech can't climb it; under the sea it's unseen)
    ang = np.degrees(np.arctan2(y - LH[1], x - LH[0]))
    wsec = _ssv((ang + 125.0) / 10.0) * _ssv((-25.0 - ang) / 10.0)
    climb = -99.0 + (-0.6 - 35.4 * _ssv((r - 50.0) / 85.0) + 99.0) * wsec
    return np.maximum(np.maximum(head, trunk), climb)


# thin furniture the 1 m ray grid can miss (port.py: breakwater edge bollards every 25 m, lamp posts every 50 m with the lamp arm
# over the harbour side, crown-wall lamps, the crown railing): (x, y, radius incl. margin, top z)
FURN = ([(-688.22, 386.0 - 25.0 * k, 1.0, 6.1) for k in range(21)] + [(-688.0, 374.0 - 50.0 * k, 1.6, 13.8) for k in range(10)]
        + [(-713.5, 394.0 - 50.0 * k, 1.0, 14.8) for k in range(10)])
FURN_A = np.array(FURN)
RAIL = (-714.7, -117.8, 400.0, 0.8, 8.95)          # x, y0, y1, half width incl. margin, top (y0: the crown wall's end, port.py r 52, + 1 m - 1 m)


def furniture_z(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float); z = np.full(np.shape(x), -99.0)
    for (fx, fy, r, top) in FURN:
        z = np.where((x - fx) ** 2 + (y - fy) ** 2 < r * r, np.maximum(z, top), z)
    z = np.where((np.abs(x - RAIL[0]) < RAIL[3]) & (y > RAIL[1]) & (y < RAIL[2]), np.maximum(z, RAIL[4]), z)
    return z


def ground_hi(x, y):
    """conservative height: the highest of the four cells round (x, y) (a sole must clear a wall's edge, not its bilinear ramp),
    raised to the invisible underwater ramps and to the thin furniture."""
    fx, fy, i, j = _cells(x, y)
    z = np.maximum(np.maximum(GH[j, i], GH[j, i + 1]), np.maximum(GH[j + 1, i], GH[j + 1, i + 1]))
    z = np.maximum(np.maximum(z, virtual_z(x, y)), furniture_z(x, y))
    return float(z) if np.ndim(z) == 0 else z


DOCK_IN = (-510.0, -410.0, 405.5, 600.0)        # dry dock 3's basin behind the caisson (floor -14)
DOCK_WATER = -6.0                               # flooded by the wave
FLOOD = (43.2, 44.4)


def in_dock(x, y): return DOCK_IN[0] < x < DOCK_IN[1] and DOCK_IN[2] < y < DOCK_IN[3]


def water_z(x, y, t):
    if in_dock(x, y): return -14.0 + (DOCK_WATER + 14.0) * ss((t - FLOOD[0]) / (FLOOD[1] - FLOOD[0]))
    return 0.0


# ================================================================================================================= feet
FOOT_FWD, FOOT_BACK, FOOT_HW = 9.0, 9.6, 4.45   # the sole round its contact point (MECH_sole): toes 9.0 m ahead, heel 9.6 behind
HIP_X, SOLE_Y = 8.6, -3.0                      # standing: sole contacts at local (+-8.6, -3)


def foot_grid(x, y, yaw, margin=0.4, step=1.0):
    us = np.arange(-FOOT_FWD - margin, FOOT_BACK + margin + 1e-6, step)
    nv = max(3, int(round(2 * (FOOT_HW + margin) / step)) + 1)
    vs = np.linspace(-FOOT_HW - margin, FOOT_HW + margin, nv)
    U, V = np.meshgrid(us, vs); U = U.ravel(); V = V.ravel()
    R = rot2(yaw); X = x + R[0, 0] * V + R[0, 1] * U; Y = y + R[1, 0] * V + R[1, 1] * U
    return U, V, X, Y


def sole_dz(U, V, pitch, roll):
    """height of the sole point (local x = V, local y = U) above the contact for a foot pitched / rolled as mech.leg_ik does."""
    p, r = math.radians(pitch), math.radians(roll)
    return -V * math.sin(r) + U * math.sin(p) * math.cos(r)


def fit_plant(x, y, yaw, maxp=24.0, maxr=12.0, clear=0.12):
    """the sole plane under a foot at (x, y) heading yaw: least-squares tilt (clamped), then lifted until no ground point is above
    it. Returns (z of the contact, pitch, roll, gap = the largest air gap under the sole)."""
    U, V, X, Y = foot_grid(x, y, yaw, step=0.5)
    h = ground_hi(X, Y)
    A = np.c_[np.ones_like(U), U, V]
    co = np.linalg.lstsq(A, h, rcond=None)[0]
    pitch = float(np.clip(math.degrees(math.atan(co[1])), -maxp, maxp))
    roll = float(np.clip(-math.degrees(math.atan(co[2])), -maxr, maxr))
    dz = sole_dz(U, V, pitch, roll)
    z = float(np.max(h - dz)) + clear
    inner = (U >= -FOOT_FWD) & (U <= FOOT_BACK) & (np.abs(V) <= FOOT_HW)
    gap = float(np.max((z + dz - h)[inner]))
    return z, pitch, roll, gap


def plant(t, lift, side, x, y, yaw, kind, A=5.0, flat=False):
    z, p, r, gap = fit_plant(x, y, yaw)
    if flat: p = r = 0.0; z, gap = _flat_z(x, y, yaw)
    return dict(t=float(t), lift=None if lift is None else float(lift), side=side, p=np.array((x, y, z)), yaw=float(yaw),
                pitch=p, roll=r, gap=gap, kind=kind, A=A)


def _flat_z(x, y, yaw):
    U, V, X, Y = foot_grid(x, y, yaw); h = ground_hi(X, Y); z = float(h.max()) + 0.12
    inner = (U >= -FOOT_FWD) & (U <= FOOT_BACK) & (np.abs(V) <= FOOT_HW)
    return z, float((z - h)[inner].max())


# ================================================================================================================= the run path
SLEEP_ROOT = np.array((-460.0, 583.26, -14.0))      # dock floor, back against the north wall (rig SLEEP_WALL 16.74 m)
STAND_ROOT = np.array((-460.0, 560.0))          # the rise ends with the hips over the ankles (feet slid in to y 557)
STEP_ROOT = np.array((-460.0, 551.0))
TAIL_X0, TAIL_R1, TAIL_RC, TAIL_TH1, TAIL_RUNOUT = -700.9, 30.0, 33.0, 190.0, 12.0


def _tail_wp(step=6.0):
    """the run's last stretch: south along the cap's axis (x = TAIL_X0; the rail and the bollards leave the feet ~2 m of play), a
    right arc (radius TAIL_R1) tangent to a left arc of radius TAIL_RC round the lighthouse's west side (the left shoulder stays
    clear of the tower, the right foot inside the head's disc) to TAIL_TH1 deg, then a short straight run-out to the take-off."""
    C2 = np.array((-700.0, -168.0)); x0, R1, rc = TAIL_X0, TAIL_R1, TAIL_RC
    ya = C2[1] + math.sqrt((R1 + rc) ** 2 - (x0 - R1 - C2[0]) ** 2)
    C1 = np.array((x0 - R1, ya)); dC = (C2 - C1) / np.linalg.norm(C2 - C1)
    pts = [(x0, y) for y in np.arange(-15.0, ya + 1e-6, -40.0)] + [(x0, ya)]
    phT = math.atan2(dC[1], dC[0])                                     # clockwise from 0 to phT (< 0)
    n = max(2, int(math.ceil(abs(phT) * R1 / step)))
    pts += [tuple(C1 + R1 * np.array((math.cos(phT * k / n), math.sin(phT * k / n)))) for k in range(1, n + 1)]
    thT = math.atan2(-dC[1], -dC[0]); th1 = math.radians(TAIL_TH1)
    n = max(2, int(math.ceil((th1 - thT) * rc / step)))
    pts += [tuple(C2 + rc * np.array((math.cos(thT + (th1 - thT) * k / n), math.sin(thT + (th1 - thT) * k / n)))) for k in range(1, n + 1)]
    E = C2 + rc * np.array((math.cos(th1), math.sin(th1))); d = np.array((-math.sin(th1), math.cos(th1)))
    pts += [tuple(E + d * TAIL_RUNOUT * k / 2) for k in (1, 2)]
    return [(float(x), float(y)) for x, y in pts]


_RUN_TAIL = _tail_wp()


RUN_GEO = dict(y_t=392.0, Ra=150.0, Rb=120.0, psi=44.0)   # searched (out of the dock .. onto the cap): every footfall clear of the
                                                        # posts / bollards / parapet, flat where it shows, 56.8 on the gate, <= 61 deg/s


def _run_geo(y_t, Ra, Rb, psi, x0=-460.0, y0=551.0, step=8.0):
    """the run's track as geometry: south down the dock (heading 0, through the caisson gate), a right arc (Ra) by psi out across the
    harbour shallows, a straight diagonal, a left arc (Rb) back to heading 0 onto the breakwater's cap axis (x = TAIL_X0), south
    along the cap, then the tail round the lighthouse. Sampled densely (the spline through it is the geometry)."""
    ps = math.radians(psi); xb = TAIL_X0
    L = (x0 - xb - (Ra + Rb) * (1 - math.cos(ps))) / math.sin(ps)
    y_m = y_t - (Ra + Rb) * math.sin(ps) - L * math.cos(ps)
    pts = [(x0, y) for y in np.arange(y0, y_t, -step)]
    C1 = np.array((x0 - Ra, y_t)); n = max(2, int(math.ceil(Ra * ps / step)))
    pts += [tuple(C1 + Ra * np.array((math.cos(-ps * k / n), math.sin(-ps * k / n)))) for k in range(0, n + 1)]
    P1 = np.array(pts[-1]); f = np.array((-math.sin(ps), -math.cos(ps)))
    n = max(1, int(math.ceil(L / step)))
    pts += [tuple(P1 + f * L * k / n) for k in range(1, n)]
    C2 = np.array((xb + Rb, y_m)); n = max(2, int(math.ceil(Rb * ps / step)))
    pts += [tuple(C2 + Rb * np.array((math.cos(math.pi - ps * (1 - k / n)), math.sin(math.pi - ps * (1 - k / n))))) for k in range(0, n + 1)]
    pts += [(xb, y) for y in np.arange(y_m - step, _RUN_TAIL[0][1] + 4, -step * 3)]
    return [(float(x), float(y)) for x, y in pts] + _RUN_TAIL


if os.environ.get('RUN_GEO'):                                # a search can try other tracks: RUN_GEO="y_t,Ra,Rb,psi"
    RUN_GEO = dict(zip(('y_t', 'Ra', 'Rb', 'psi'), (float(v) for v in os.environ['RUN_GEO'].split(','))))
RUN_WP = _run_geo(**RUN_GEO)
RUN_T0, RUN_V_AT, TAKEOFF = 54.6, 56.0, 63.4
TAKEOFF_R = 63.25                                    # the trailing right foot leaves first and swings forward (the knee drive)
GATHER = 63.05                                       # the second foot comes down beside the first: a two-footed take-off
RUN_HALF = 6.0                                       # run plants this far either side of the track (the feet are 8.9 m wide)
CAP_LANE = (-716.0, -686.0, -125.0, 400.0)           # the breakwater's cap: west posts (x -712.5) .. east bollards (x -689.2)
CAP_HALF = 5.0                                       # .. leaves the feet 1.1 m either side at this half spread


def run_half(xy):
    return CAP_HALF if CAP_LANE[0] < xy[0] < CAP_LANE[1] and CAP_LANE[2] < xy[1] < CAP_LANE[3] else RUN_HALF


def _poly(wp, n=24):
    P = np.array(wp, float); out = []
    for i in range(len(P) - 1):
        p0 = P[max(0, i - 1)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(len(P) - 1, i + 2)]
        for k in range(n):
            u = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    out.append(P[-1]); out = np.array(out)
    s = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(out, axis=0), axis=1))))
    return out, s


def _smooth_path(pts, sigma=8.0, step=1.0):
    """the polyline resampled every `step` m and low-passed along its length (Gaussian, sigma m), the ends extended straight, so the
    curvature (and the body's yaw rate) has no jumps where the track's arcs meet."""
    P = np.asarray(pts, float); s = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))))
    n = int(s[-1] / step) + 1; ss_ = np.linspace(0.0, s[-1], n)
    Q = np.stack([np.interp(ss_, s, P[:, 0]), np.interp(ss_, s, P[:, 1])], axis=1)
    r = int(3 * sigma / step); k = np.exp(-0.5 * (np.arange(-r, r + 1) * step / sigma) ** 2); k /= k.sum()
    d0 = Q[1] - Q[0]; d1 = Q[-1] - Q[-2]
    pre = Q[0] - d0 * np.arange(r, 0, -1)[:, None]; post = Q[-1] + d1 * np.arange(1, r + 1)[:, None]
    E = np.concatenate((pre, Q, post))
    out = np.stack([np.convolve(E[:, 0], k, mode='valid'), np.convolve(E[:, 1], k, mode='valid')], axis=1)
    return out, np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(out, axis=0), axis=1))))


RUN_PTS, RUN_S = _smooth_path(_poly(RUN_WP)[0])
RUN_LEN = float(RUN_S[-1])


RUN_RAMP = 56.68          # the run builds up over 2 s so the 56.8 footfall lands on the caisson's top (the mech steps up onto the
BURST = (57.0, 58.7, 0.40)  # gate and launches off it), then bursts (+40 % at the peak) and is back on the old track from 58.7


def _vrel(t):
    """relative running speed: ramps up 54.6..56.68, full to 61.9 (+ the burst off the caisson), brakes into the gather (0.42 at
    63.05), 0.3 at the take-off. The integral to 58.7 equals the old profile's, so every footfall from 58.6 on is unchanged."""
    if t <= RUN_T0: return 0.0
    if t < RUN_RAMP: v = ss((t - RUN_T0) / (RUN_RAMP - RUN_T0))
    elif t < 61.9: v = 1.0
    elif t < GATHER: v = 1.0 - 0.58 * ss((t - 61.9) / (GATHER - 61.9))
    else: v = 0.42 - 0.12 * ss((t - GATHER) / (TAKEOFF - GATHER))
    if BURST[0] < t < BURST[1]: v += BURST[2] * math.sin(math.pi * (t - BURST[0]) / (BURST[1] - BURST[0])) ** 2
    return v


_TT = np.linspace(RUN_T0, TAKEOFF, 8801)
_SV = np.concatenate(([0.0], np.cumsum([(_vrel(a) + _vrel(b)) * 0.5 * (b - a) for a, b in zip(_TT[:-1], _TT[1:])])))
RUN_V = RUN_LEN / float(_SV[-1])


def run_s(t): return RUN_V * float(np.interp(t, _TT, _SV))


def run_point(s):
    s = min(max(s, 0.0), RUN_LEN)
    i = min(max(int(np.searchsorted(RUN_S, s, side='right')) - 1, 0), len(RUN_S) - 2)
    u = (s - RUN_S[i]) / max(RUN_S[i + 1] - RUN_S[i], 1e-9)
    p = RUN_PTS[i] + (RUN_PTS[i + 1] - RUN_PTS[i]) * u
    a = max(0, i - 3); b = min(len(RUN_PTS) - 1, i + 4)       # heading over a few samples (no flicker at the knots)
    d = RUN_PTS[b] - RUN_PTS[a]; d = d / max(np.linalg.norm(d), 1e-9)
    return p, d


def run_xy_yaw(t):
    p, d = run_point(run_s(t)); return p, yaw_of(d)


# ================================================================================================================= the leap + the landing
LAND_T = S.T['land']
LAND_ROOT = np.array((-722.0, -258.0)); LAND_YAW = 10.0
APEX = 30.0                                           # the flight's apex above the take-off floor
T_WATER = 64.85                                       # the soles reach the sea (z 0): from here the water brakes the fall


# ================================================================================================================= wade -> grab
WADE_KEYS = [(65.4, (-722.0, -258.0, 10.0)), (66.0, (-721.0, -262.0, 13.0)), (66.6, (-716.5, -271.0, 17.0)), (67.2, (-710.5, -282.0, 20.0)),
             (67.8, (-706.0, -289.5, 18.0)), (68.4, (-701.5, -295.5, 12.0)), (68.9, (-697.5, -299.5, 5.0)), (69.3, (-694.0, -303.0, 0.0))]
GRAB_BLEND = 0.5          # s after the grab over which the root goes from the wade's path onto the held one (position + velocity)
GRAB_T = S.T['grab']


HOLD_HAND = [  # the left palm (~ the chain's last joint) in the root frame while it holds (tuned: shots/../tune_hand); from the
    # grab the body steps 3-4.5 m toward the held hand so the arm reaches straight ahead of the chest (with the palm 17 m out to the
    # left the arm's aim sat at ~-76 deg in the chest frame and the upper arm / pauldron met the chest at every elbow swivel: BVH
    # sweep out/qa/armsweep_d0.log; free from ~-82)
    (69.3, (18.0, -29.0)), (69.7, (14.5, -30.67)), (70.0, (12.7, -31.46)), (70.3, (12.2, -30.75)), (70.7, (12.4, -26.58)),
    (71.0, (12.6, -25.17)), (72.0, (12.6, -24.54)), (72.5, (12.6, -24.62)), (73.0, (12.9, -24.45)), (73.3, (13.9, -23.18)),
    (73.6, (15.0, -19.44)), (73.8, (18.5, -20.87)), (74.0, (20.0, -11.0)), (74.3, (20.0, -9.0)), (74.7, (18.5, -9.0)),
    (75.0, (17.5, -6.0)), (75.5, (16.5, -2.0))]
HOLD_YAW = [  # facing: S at the grab, turning SSW with the pull, backing N facing the city, the clockwise pivot to N, N up the mound
    (69.3, 0.0), (70.0, -4.0), (71.0, -10.0), (72.0, -12.0), (73.0, -8.0), (73.6, -6.0), (74.3, -180.0), (75.5, -182.0)]


def hand_local(t):
    return pchip_keys(HOLD_HAND, t)


def yaw_hold(t):
    return float(pchip_keys([(a, (b,)) for a, b in HOLD_YAW], t)[0])


WIND_LFT, WIND_FWD, WIND_FACE = 17.5, 1.0, 6.0    # the wind (76.0 .. 78.2): the palm this far left of / ahead of the root, the body
                                                 # turned this much in toward the drum (a crouched hauling run, the left arm down at the
                                                 # side, the fist at the hip; both feet inside the head's disc). 19 m: the left arm
                                                 # hangs straight down from the shoulder (lateral ~20 m) and the fist passes outside
                                                 # the thigh (its outer face ~14.6 m from the pelvis); 15.5 put the hand in the thigh
                                                 # and the upper arm into the chest. 17.5 (05.11): 1.5 m in, so the right foot can
                                                 # stand 4 m out of the root (the soles are 8.9 m wide: the feet 12 m apart pass each
                                                 # other with no overlap; at 7 m they crossed) and still keep its centre on the cap


def _wind_root(t):
    tt = min(t, S.WIND['t1'])
    pal = S.palm_path(tt); a = math.radians(S.palm_angle_unwrapped(tt))
    rad = np.array((math.cos(a), math.sin(a))); tang = np.array((-math.sin(a), math.cos(a)))
    fo = tang * math.cos(math.radians(WIND_FACE)) - rad * math.sin(math.radians(WIND_FACE))
    left = np.array((-fo[1], fo[0]))
    return np.asarray(pal[:2], float) - WIND_LFT * left - WIND_FWD * fo, yaw_of(fo)


def _hold_root(t):
    """root from the palm and the hand's place in the body frame (69.3 .. 76.0)."""
    pal = S.palm_path(t); yaw = yaw_hold(t)
    return to_world(pal, yaw, -hand_local(t)) if False else np.asarray(pal[:2]) - rot2(yaw) @ hand_local(t), yaw


def _root_xy_yaw(t):
    """(xy, yaw) without the floor height."""
    if t <= 49.0: return SLEEP_ROOT[:2].copy(), 0.0
    if t <= 52.0:
        k = [(49.0, (SLEEP_ROOT[0], SLEEP_ROOT[1])), (49.6, (SLEEP_ROOT[0], SLEEP_ROOT[1] - 0.4)), (51.6, tuple(STAND_ROOT)), (52.0, tuple(STAND_ROOT))]
        return catmull_keys(k, t), 0.0
    if t <= RUN_T0:
        k = [(52.0, tuple(STAND_ROOT)), (52.4, (STAND_ROOT[0], 559.0)), (53.0, tuple(STEP_ROOT)), (RUN_T0, tuple(STEP_ROOT))]
        return catmull_keys(k, t), 0.0
    if t <= TAKEOFF:
        p, y = run_xy_yaw(t); return p, y * ss((t - RUN_T0) / 0.6)       # it turns onto the track's heading over the first steps
    if t <= LAND_T:
        p0, y0 = run_xy_yaw(TAKEOFF); u = (t - TAKEOFF) / (LAND_T - TAKEOFF)
        d = LAND_ROOT - p0; L = float(np.linalg.norm(d))
        return p0 + d / L * _flight_s(t, L), y0 + wrap180(LAND_YAW - y0) * ss(u)
    if t <= GRAB_T:
        v = catmull_keys(WADE_KEYS, t); return v[:2], float(v[2])
    if t < GRAB_T + GRAB_BLEND:          # the wade's motion carries into the hold (a cubic on position + velocity, yaw likewise)
        t1 = GRAB_T + GRAB_BLEND; dt = 0.01
        a0 = np.asarray(catmull_keys(WADE_KEYS, GRAB_T), float); a1 = np.asarray(catmull_keys(WADE_KEYS, GRAB_T - dt), float)
        v0 = (a0 - a1) / dt
        b0, yb0 = _hold_root(t1); b1, yb1 = _hold_root(t1 - dt)
        p0 = np.array((a0[0], a0[1], a0[2])); m0 = v0
        p1 = np.array((b0[0], b0[1], yb0)); m1 = np.array(((b0[0] - b1[0]) / dt, (b0[1] - b1[1]) / dt, wrap180(yb0 - yb1) / dt))
        p1[2] = p0[2] + wrap180(p1[2] - p0[2])
        h = t1 - GRAB_T; s_ = (t - GRAB_T) / h
        q = ((2 * s_ ** 3 - 3 * s_ ** 2 + 1) * p0 + (s_ ** 3 - 2 * s_ ** 2 + s_) * h * m0 + (-2 * s_ ** 3 + 3 * s_ ** 2) * p1
             + (s_ ** 3 - s_ ** 2) * h * m1)
        return q[:2], float(q[2])
    if t <= 75.5: return _hold_root(t)
    if t < 76.0:
        a, ya = _hold_root(t); b, yb = _wind_root(t); w = ss((t - 75.5) / 0.5)
        return a * (1 - w) + b * w, ya + wrap180(yb - ya) * w
    return _wind_root(t)


def _wade_v0():
    a = catmull_keys(WADE_KEYS, LAND_T)[:2]; b = catmull_keys(WADE_KEYS, LAND_T + 0.02)[:2]
    return float(np.linalg.norm(np.asarray(b) - np.asarray(a))) / 0.02


def _flight_s(t, L):
    """distance along the take-off -> landing line: constant speed in the air, braked linearly in the water to the wade's speed."""
    ve = _wade_v0(); T1 = T_WATER - TAKEOFF; T2 = LAND_T - T_WATER
    va = (L - ve * T2 / 2.0) / (T1 + T2 / 2.0)
    tau = min(max(t - TAKEOFF, 0.0), LAND_T - TAKEOFF)
    if tau <= T1: return va * tau
    s = tau - T1
    return va * T1 + va * s - (va - ve) * s * s / (2.0 * T2)


# ================================================================================================================= plants
def _stand(side, root, yaw, lx=None, ly=SOLE_Y):
    lx = (HIP_X if side == 'L' else -HIP_X) if lx is None else lx
    return to_world(root, yaw, (lx, ly))


def run_stance():
    """stance time (s) of each run footfall 55.0 + 0.6 k: 0.24 at the cruise, shorter in the burst (0.24 / relative speed, >= 0.17)."""
    out = [0.42, 0.32]
    for k in range(2, 12):
        tk = 55.0 + 0.6 * k; out.append(round(max(0.17, 0.24 / max(1.0, _vrel(tk + 0.12))), 3))
    return out + [0.28]


def _plants():
    P = []
    # standing up in the dock (planted from 49.6; before that the sleep pose drives the legs and mechanim blends them in)
    for sd in ('L', 'R'):
        xy = _stand(sd, STAND_ROOT, 0.0); P.append(plant(49.6, None, sd, xy[0], xy[1], 0.0, 'stand'))
    P.append(plant(52.4, None, 'R', -468.6, 546.0, 0.0, 'step_first', A=7.0))
    P.append(plant(53.0, None, 'L', -451.4, 549.0, 0.0, 'step', A=6.0))
    # the run: footfalls every 0.6 s (the score's 55.0 .. 62.8), the foot under the body's mid-stance, +-3.2 m off the track
    stance = run_stance()
    for k in range(14):
        tk = round(55.0 + 0.6 * k, 3); sd = 'L' if k % 2 == 0 else 'R'
        st = stance[k] if k < 13 else TAKEOFF - tk
        p, d = run_point(run_s(tk + 0.5 * min(st, 0.3)))
        yaw = yaw_of(d); h = run_half(p); xy = to_world(p, yaw, ((h if sd == 'L' else -h), SOLE_Y))
        P.append(plant(tk, None, sd, xy[0], xy[1], yaw + (4.0 if sd == 'L' else -4.0), 'run', A=12.0,
                       flat=abs(tk - 56.8) < 1e-6))          # 56.8: the right foot on the caisson's top, level, bridging the gate
    # the gather: the left foot comes down beside the right (62.8) for the two-footed take-off
    p, d = run_point(run_s(63.22)); yaw = yaw_of(d)
    xy = to_world(p, yaw, (HIP_X, -1.0)); P.append(plant(GATHER, None, 'L', xy[0], xy[1], yaw, 'gather', A=8.0))
    # landing: the verified land pose (L forward, R back)
    for sd, lxy in (('L', (9.0, -14.0)), ('R', (-8.6, 12.0))):
        xy = to_world(LAND_ROOT, LAND_YAW, lxy); P.append(plant(LAND_T, None, sd, xy[0], xy[1], LAND_YAW + (6 if sd == 'L' else -6), 'land'))
    # scheduled steps: (side, t_lift, t_land, local target, aim time, kind, swing height)
    sched = [('R', 65.95, 66.45, (-8.6, -4.0), 66.8, 'wade', 4.0), ('L', 66.55, 67.1, (8.6, -6.0), 67.4, 'wade', 4.0),
             ('R', 67.3, 67.85, (-8.6, -3.0), 68.1, 'wade', 4.0), ('L', 68.0, 68.55, (9.0, -15.0), 68.75, 'lunge', 4.0),
             # backing up against the pull, facing the city (72.1 .. 73.25), the clockwise pivot round the held hand (73.3 .. 74.1),
             # the haul north and the climb up the head's mound (74.1 .. 75.3), onto the cap, turning into the wind (75.3 .. 75.95)
             ('R', 72.15, 72.45, (-8.6, 7.0), 72.6, 'back', 4.0), ('L', 72.45, 72.75, (8.6, 7.0), 72.9, 'back', 4.0),
             ('R', 72.75, 73.02, (-8.6, 8.0), 73.15, 'back', 4.0), ('L', 73.02, 73.3, (8.6, 8.0), 73.42, 'back', 4.0),
             ('R', 73.3, 73.58, (-8.6, 8.0), 73.7, 'back', 4.0),
             ('L', 73.58, 73.95, (9.0, -4.0), 74.1, 'pivot', 5.0), ('R', 73.95, 74.3, (-9.0, -2.0), 74.4, 'pivot', 5.0),
             ('L', 74.3, 74.6, (8.6, -6.0), 74.75, 'climb', 6.0), ('R', 74.6, 74.9, (-8.6, -6.0), 75.05, 'climb', 6.0),
             ('L', 74.9, 75.2, (8.6, -6.0), 75.35, 'climb', 6.0), ('R', 75.2, 75.5, (-8.0, -5.0), 75.65, 'climb', 6.0),
             # the wind: a bent-over run round the drum, a footfall on every chord (76.0 .. 77.8), stance 0.4 s; both feet shifted
             # in toward the drum (the right foot keeps inside the head's disc); the brace: the left foot forward at 78.2
             ('L', 75.5, 76.0, (8.0, 0.0), 76.15, 'wind', 6.0), ('R', 75.95, 76.6, (-4.0, 0.0), 76.75, 'wind', 7.0),
             ('L', 76.3, 77.2, (8.0, 0.0), 77.35, 'wind', 7.0), ('R', 76.9, 77.8, (-4.0, 0.0), 77.95, 'wind', 8.0),
             ('L', 77.5, 78.2, (9.0, -10.0), 78.2, 'brace', 5.0)]      # soles >= 0.4 m apart in plan all through (feet_gap)
    for (sd, tl, td, lxy, ta, kind, A) in sched:
        r, y = _root_xy_yaw(ta); xy = to_world(r, y, lxy)
        P.append(plant(td, None, sd, xy[0], xy[1], y + (5 if sd == 'L' else -5), kind, A=A))
        P[-1]['lift_prev'] = tl
    # lifts: each plant lifts when the next plant of the same side starts its swing
    P.sort(key=lambda q: q['t'])
    run_lift = {round(55.0 + 0.6 * k, 3): round(55.0 + 0.6 * k + st, 3) for k, st in enumerate(run_stance())}
    for sd in ('L', 'R'):
        mine = [q for q in P if q['side'] == sd]
        for a, b in zip(mine, mine[1:]):
            if 'lift_prev' in b: a['lift'] = b['lift_prev']
            elif b['kind'] == 'run' and a['kind'] != 'run': a['lift'] = {55.0: 54.6, 55.6: 55.12}.get(round(b['t'], 2), b['t'] - 0.45)
            elif a['kind'] == 'run': a['lift'] = run_lift.get(round(a['t'], 3), a['t'] + 0.24)
            elif b['kind'] == 'step_first': a['lift'] = 52.0
            elif b['kind'] == 'step': a['lift'] = 52.55
            elif b['kind'] == 'gather': a['lift'] = 62.62
            else: a['lift'] = b['t'] - 0.5
        if mine[-1]['lift'] is None: mine[-1]['lift'] = None
    # the take-off: the left foot (the gather) drives off at TAKEOFF, the trailing right one leaves at TAKEOFF_R; the landing plants
    # come after the flight (the swings into them are mechanim's leap)
    for q in P:
        if q['kind'] == 'gather': q['lift'] = TAKEOFF
        elif q['kind'] == 'run' and abs(q['t'] - 62.8) < 1e-6: q['lift'] = TAKEOFF_R
    return P


PLANTS = _plants()
SLIDE = (69.4, 71.6)                  # the drag: both feet plough with the body (sole contact follows the root's motion)


def plants_of(side): return [q for q in PLANTS if q['side'] == side]


# ================================================================================================================= swings with clearance
def bump(u):
    """the swing's lift profile: broad (sin^0.6) in the middle, eased at both ends so the foot leaves and meets the ground smoothly."""
    if u <= 0.0 or u >= 1.0: return 0.0
    return math.sin(math.pi * u) ** 0.6 * ss(u / 0.15) * ss((1.0 - u) / 0.15)


def _swing_state(a, b, u, A):
    e = u * u * (3 - 2 * u)
    da = a['p'][:2] - LH; db = b['p'][:2] - LH; ra = float(np.hypot(*da)); rb = float(np.hypot(*db))
    if ra < 52.0 and rb < 52.0:          # round the drum: swing along the arc (a chord would cut in toward the drum)
        aa = math.atan2(da[1], da[0]); ab = aa + math.radians(wrap180(math.degrees(math.atan2(db[1], db[0]) - aa)))
        ang = aa + (ab - aa) * e; rr = ra + (rb - ra) * e
        xy = LH + rr * np.array((math.cos(ang), math.sin(ang)))
    else:
        xy = a['p'][:2] + (b['p'][:2] - a['p'][:2]) * e
    yaw = a['yaw'] + wrap180(b['yaw'] - a['yaw']) * e
    tilt = 18.0 if b['kind'] in ('run', 'gather') else 8.0
    pitch = lerp(a['pitch'], b['pitch'], e) + tilt * math.sin(math.pi * u) * (1.0 - 2.0 * u)
    roll = lerp(a['roll'], b['roll'], e)
    z = lerp(a['p'][2], b['p'][2], e) + A * bump(u)
    if u < 0.3 or u > 0.7:          # near the ends: lift the foot just enough that no sole point is in the set (the toes on a tilt)
        U, V, X, Y = foot_grid(xy[0], xy[1], yaw, margin=0.0, step=3.0)
        dig = float(np.max(ground_hi(X, Y) - (z + sole_dz(U, V, pitch, roll))))
        if dig > 0.0: z += dig
    return np.array((xy[0], xy[1], z)), yaw, pitch, roll


def _plan_swing(a, b, clear=1.2, n=48):
    """the smallest bump height >= b['A'] for which the whole sole stays `clear` above the set over the swing."""
    A = b['A']; need = 0.0
    for i in range(1, n):
        u = i / n; p, yaw, pitch, roll = _swing_state(a, b, u, 0.0)
        U, V, X, Y = foot_grid(p[0], p[1], yaw, margin=0.6)
        g = ground_hi(X, Y); dz = sole_dz(U, V, pitch, roll)
        cu = clear * ss((u - 0.05) / 0.2) * ss((0.95 - u) / 0.2)
        req = float(np.max(g + cu - (p[2] + dz)))
        if req > 0: need = max(need, req / max(bump(u), 0.25))
    return max(A, need)


for _sd in ('L', 'R'):
    _m = plants_of(_sd)
    for _a, _b in zip(_m, _m[1:]):
        if _b['kind'] == 'land': _b['A_used'] = 0.0; continue         # the flight: no swing (the pose drives the legs)
        _b['A_used'] = _plan_swing(_a, _b)
    _m[0]['A_used'] = 0.0


def foot_at(t, side):
    """dict(p, yaw, pitch, roll, planted, lift) of the sole contact, or None while the mech is in the air (63.4 .. 65.4) or asleep."""
    if t < 49.6 or TAKEOFF < t < LAND_T: return None
    pl = plants_of(side)
    for i, a in enumerate(pl):
        b = pl[i + 1] if i + 1 < len(pl) else None
        if b is not None and t >= b['t']: continue
        if t < a['t']: return None
        if a['lift'] is None or t <= a['lift'] or b is None:
            p = a['p'].copy(); yaw = a['yaw']; pitch, roll = a['pitch'], a['roll']
            if SLIDE[0] < t and a['t'] <= SLIDE[0] and (a['lift'] is None or a['lift'] > SLIDE[0]):
                p, yaw, pitch, roll = _slid(a, t)
            return dict(p=p, yaw=yaw, pitch=pitch, roll=roll, planted=True, lift=0.0, kind=a['kind'])
        if b['kind'] == 'land': return None
        a2 = a
        if SLIDE[0] < a['lift'] and a['t'] <= SLIDE[0]:
            q, yw, pi_, ro = _slid(a, a['lift']); a2 = dict(a, p=q, yaw=yw, pitch=pi_, roll=ro)
        u = (t - a['lift']) / (b['t'] - a['lift'])
        p, yaw, pitch, roll = _swing_state(a2, b, u, b['A_used'])
        return dict(p=p, yaw=yaw, pitch=pitch, roll=roll, planted=False, lift=bump(u), kind=b['kind'])
    return None


def _slid(a, t):
    """a foot ploughing with the body during the drag: carried by the root's motion since SLIDE[0], re-seated on the seabed."""
    tt = min(t, SLIDE[1]); r0, y0 = _root_xy_yaw(SLIDE[0]); r1, y1 = _root_xy_yaw(tt)
    loc = to_local(r0, y0, a['p'][:2]); xy = to_world(r1, y1, loc)
    yaw = a['yaw'] + wrap180(y1 - y0)
    z, p, r, gap = fit_plant(xy[0], xy[1], yaw)
    return np.array((xy[0], xy[1], z)), yaw, p, r


# ================================================================================================================= the floor under the body
def _floor_raw(t):
    zs = []
    for sd in ('L', 'R'):
        f = foot_at(t, sd)
        if f is None: continue
        zs.append(f['p'][2] - (f['lift'] * plants_of(sd)[0]['A'] if False else 0.0) if f['planted'] else None)
        if not f['planted']:
            # in the swing: the floor it left and the floor it is going to (whichever is lower)
            pl = plants_of(sd); prev = [q for q in pl if q['t'] <= t]; nxt = [q for q in pl if q['t'] > t]
            zz = [q['p'][2] for q in (prev[-1:] + nxt[:1])]
            zs[-1] = min(zz) if zz else None
    zs = [z for z in zs if z is not None]
    return min(zs) if zs else None


def _run_floor(t):
    """during the run the pelvis rides over the stance foot: its floor, eased to the next foot's floor in the flight between."""
    rp = sorted([q for q in PLANTS if q['kind'] in ('run', 'gather') or (q['kind'] == 'step' and q['t'] > 52.9)], key=lambda q: q['t'])
    if t <= rp[0]['t']: return rp[0]['p'][2]
    for a, b in zip(rp, rp[1:]):
        if a['t'] <= t <= b['t']:
            l = a['lift'] if a['lift'] is not None else b['t']
            l = min(max(l, a['t']), b['t'])
            if b['p'][2] > a['p'][2] + 2.0 and b['kind'] == 'run': l = a['t']     # a step up: it rises through the push-off too
            if t <= l: return a['p'][2]
            return lerp(a['p'][2], b['p'][2], ss((t - l) / max(b['t'] - l, 1e-6)))
    return rp[-1]['p'][2]


def _flight_g(z0, z1, T):
    """gravity for a ballistic arc from z0 to z1 in T seconds peaking APEX above z0:
    vz^2 = 2 g APEX and z1 = z0 + vz T - g T^2 / 2  ->  (T^4 / 4) g^2 + (d - 2 APEX) T^2 g + d^2 = 0, d = z1 - z0; the larger
    root puts the apex inside the flight."""
    d = z1 - z0
    a = T ** 4 / 4.0; b = (d - 2.0 * APEX) * T * T; c = d * d
    disc = max(b * b - 4 * a * c, 0.0)
    return (-b + math.sqrt(disc)) / (2 * a)


FLIGHT_Z0 = _run_floor(TAKEOFF)                       # the floor the leap leaves (the breakwater head's cap)
FLIGHT_Z1 = _floor_raw(LAND_T + 1e-6)                 # the floor it lands on (the seabed under the landing plants)


def _flight_consts():
    """(g, vz0, vw, k): the arc leaves FLIGHT_Z0 at TAKEOFF going up at vz0, peaks APEX above it and meets the sea (z 0) at T_WATER
    going down at vw (< 0); in the water v = vw / (1 + k s) (drag ~ v^2), k such that it reaches FLIGHT_Z1 exactly at LAND_T."""
    tw = T_WATER - TAKEOFF
    a = tw * tw / 2.0; b = -math.sqrt(2.0 * APEX) * tw; c = -FLIGHT_Z0          # z0 + sqrt(2 g A) tw - g tw^2 / 2 = 0, u = sqrt(g)
    u = (-b + math.sqrt(b * b - 4.0 * a * c)) / (2.0 * a); g = u * u; vz0 = math.sqrt(2.0 * g * APEX); vw = vz0 - g * tw
    T2 = LAND_T - T_WATER; lo, hi = 1e-6, 200.0
    for _ in range(80):
        k = 0.5 * (lo + hi)
        if (vw / k) * math.log(1.0 + k * T2) < FLIGHT_Z1: lo = k          # still too deep: more drag
        else: hi = k
    k = 0.5 * (lo + hi)
    return g, vz0, vw, k


FLIGHT_G, FLIGHT_VZ0, FLIGHT_VW, FLIGHT_K = _flight_consts()
FLIGHT_V_END = FLIGHT_VW / (1.0 + FLIGHT_K * (LAND_T - T_WATER))     # vertical speed at the seabed (the legs take the rest)


def flight_floor(t):
    """the root's height over the leap (TAKEOFF .. LAND_T): ballistic to the sea, braked by the water to the seabed."""
    tau = min(max(t - TAKEOFF, 0.0), LAND_T - TAKEOFF)
    if t <= T_WATER: return FLIGHT_Z0 + FLIGHT_VZ0 * tau - 0.5 * FLIGHT_G * tau * tau
    s = min(t, LAND_T) - T_WATER
    return (FLIGHT_VW / FLIGHT_K) * math.log(1.0 + FLIGHT_K * s)


def flight_vz(t):
    if t <= T_WATER: return FLIGHT_VZ0 - FLIGHT_G * (min(max(t, TAKEOFF), T_WATER) - TAKEOFF)
    return FLIGHT_VW / (1.0 + FLIGHT_K * (min(t, LAND_T) - T_WATER))


_FT = np.round(np.arange(0.0, 90.75, 1.0 / 48), 6)
_FZ = np.zeros(len(_FT))
for _i, _t in enumerate(_FT):
    if _t < 49.6: _FZ[_i] = SLEEP_ROOT[2]
    elif RUN_T0 <= _t <= TAKEOFF: _FZ[_i] = _run_floor(_t)
    elif TAKEOFF < _t < LAND_T: _FZ[_i] = flight_floor(_t)
    else:
        z = _floor_raw(_t); _FZ[_i] = z if z is not None else _FZ[_i - 1]
# smooth the walking phases (not across the flight / the run edges)
_k = np.exp(-0.5 * (np.arange(-7, 8) / 3.5) ** 2); _k /= _k.sum()
_FZs = _FZ.copy()
for _a, _b in ((49.6, RUN_T0), (LAND_T, 90.75)):
    m = (_FT >= _a) & (_FT <= _b); seg = _FZ[m]
    pad = np.concatenate((np.full(7, seg[0]), seg, np.full(7, seg[-1])))
    _FZs[m] = np.convolve(pad, _k, mode='valid')


def floor_at(t):
    if TAKEOFF < t < LAND_T: return flight_floor(t)
    if TAKEOFF - 1.0 / 48 < t <= TAKEOFF: return _run_floor(t)
    if LAND_T <= t < LAND_T + 1.0 / 48: return float(_FZs[np.searchsorted(_FT, LAND_T)])
    return float(np.interp(t, _FT, _FZs))


def root_at(t):
    xy, yaw = _root_xy_yaw(t)
    return np.array((xy[0], xy[1], floor_at(t), yaw))


# ================================================================================================================= splashes (FX)
def _splashes():
    out = []
    for q in PLANTS:
        wz = water_z(q['p'][0], q['p'][1], q['t'])
        if q['p'][2] < wz - 0.5:
            depth = wz - q['p'][2]
            out.append((round(q['t'], 3), (float(q['p'][0]), float(q['p'][1]), wz), round(min(1.0, 0.35 + depth / 40.0), 2), q['kind'], q['side']))
    return out


SPLASHES = _splashes()


def report():
    print('run length %.0f m, top speed %.1f m/s' % (RUN_LEN, RUN_V))
    for q in PLANTS:
        print('%-10s %s t %6.2f lift %-6s p (%7.1f %7.1f %6.1f) yaw %6.1f pitch %5.1f roll %5.1f gap %4.1f A %5.1f water %5.1f' % (
            q['kind'], q['side'], q['t'], ('%.2f' % q['lift']) if q['lift'] is not None else '-', q['p'][0], q['p'][1], q['p'][2],
            q['yaw'], q['pitch'], q['roll'], q['gap'], q.get('A_used', 0.0), water_z(q['p'][0], q['p'][1], q['t'])))


if __name__ == '__main__':
    report()
    for sp in SPLASHES: print('splash', sp)
    for t in (0, 49.0, 49.6, 51.6, 52.4, 53.0, 54.6, 55.0, 57.0, 59.0, 61.0, 62.5, 63.4, 64.2, 65.4, 66.6, 67.2, 68.4, 69.3, 70.0, 71.0,
              72.0, 72.4, 72.8, 73.6, 74.4, 75.2, 75.6, 76.0, 77.0, 78.2, 80.0, 90.0):
        print('root %5.1f' % t, np.round(root_at(t), 1))
