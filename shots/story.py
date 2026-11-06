# ANCHOR — the designed story paths (pure numpy, no bpy: the bake runs outside Blender too). Every shot and the chain bake read
# these, so the world stays continuous from shot to shot. Film time t in seconds (frame = round(24 t) + 1).
# The beats sit on the score's hard hits (audio/cues.md, 150 bpm grid).
#   city_pos(t), city_tilt(t), collar(t)   the CITY root, its tilt (deg) and the chain's top joint (CITY_chain_top)
#   spout_pos(t)                           the waterspout's foot on the sea
#   end_guide(t)                           the chain's free end, 30.0 .. 69.3 (after that it is in the mech's palm)
#   palm_path(t)                           the mech's gripping palm, 69.3 .. 90
#   wrap_geom(t, col)                      the chain's contact with the lighthouse drum (shared with the chain bake)
# From the grab on, the city is held by the chain: city_pos keeps the span from the palm (or from the drum) at CHAIN_LEN / rho(t),
# so the chain is taut when the story says so and never longer than it is.
import math
import numpy as np

FPS = 24
CHAIN_N = 80                      # links; joints = 81
PITCH = 5.25
CHAIN_LEN = CHAIN_N * PITCH       # 420 m

T = {   # beats (s) = the score's hits
    'storm_seen': 14.0, 'collar_taut': 20.0, 'strike1': 24.4, 'discharge': 25.8, 'shackle_hot': 28.0, 'pin_shear': 30.0,
    'whip': 31.6, 'burst': 33.2, 'lurch': 35.2, 'crystals': 37.4, 'drift': 39.0, 'crane_hit': 42.0, 'wave_dock': 43.2,
    'mech_wet': 44.0, 'strike2': 45.6, 'eyes_on': 47.4, 'boot': 48.2, 'rise': 49.0, 'stand': 52.0, 'step': 52.4,
    'run0': 55.0, 'leap': 63.4, 'land': 65.4, 'reach': 67.2, 'grab': 69.3, 'taut': 70.0, 'strain': 72.0, 'climb': 73.6,
    'wind0': 76.0, 'wind1': 78.2, 'spout_pass': 78.6, 'slack': 80.6, 'open': 82.0, 'gull_back': 86.4, 'dim': 88.2,
}
FOOTFALLS = [round(55.0 + 0.6 * k, 3) for k in range(14)]     # 55.0 .. 62.8 (shallows to 58.6, breakwater from 61.0)
PUSH_OFF = 63.4
SKIP_PHASE = 0.5                  # the free end touches the sea at t = 0.5 + 0.6 k (score: 39.5 .. 41.3, 59.3 .. 60.5)

ANCHOR = np.array((-100.0, 150.0, -52.0))
LIGHTHOUSE = np.array((-700.0, -168.0, 0.0))
LH_R = 15.0                       # stone drum (bastion) radius, z 5..27; the chain wraps it under the cornice (band z 23.5..26.2,
                                  # centre-line radius 17.8: the radial links' inner edge r 15.3 tucks under the cornice's r 15.55 lip,
                                  # so a link leaving the drum must stay under z 26.3 until it is ~3 m past its tangent point)
LH_TOP = 27.0
WRAP_R = 17.8
GROOVE = (23.5, 26.2)
WRAP_Z = (24.0, 24.0)             # the chain's centre line on the drum: z at the city-side tangent .. at the palm-side tangent
                                  # (3 m under the cornice: the tail rising to the fist at z 30..31.5 and the span lifting to the city
                                  # leave the drum in a straight line and still pass under the lip; at 26 the band clamp kinked them)
FILLET = 3                        # links over which the free span lifts out of the groove
GRIP = (75.6, 76.2)               # the mech lowers the chain end into a level hold along the drum before winding
HEAD_R = 45.0                     # breakwater round-head cap disc radius (z +5)
CAP_Z = 5.0
CRANE_A = np.array((-370.0, 395.0, 0.0))
DOCK = dict(x0=-510.0, x1=-410.0, y0=400.0, y1=600.0, z=-14.0)
COLLAR_OFF = np.array((0.0, 0.0, 0.775))  # joint 0 in the CITY root frame: the pin (CITY_chain_top = the root origin) + 0.775 up the first link


def sstep(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
def rng(t, a, b): return min(1.0, max(0.0, (t - a) / (b - a)))


def rot_xyz(deg):
    rx, ry, rz = [math.radians(a) for a in deg]
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array(((1, 0, 0), (0, cx, -sx), (0, sx, cx))); Ry = np.array(((cy, 0, sy), (0, 1, 0), (-sy, 0, cy)))
    Rz = np.array(((cz, -sz, 0), (sz, cz, 0), (0, 0, 1)))
    return Rz @ Ry @ Rx          # Blender XYZ euler


def catmull(keys, t):
    """keys [(t, vec)] -> Catmull-Rom (uniform-time tangents), clamped at the ends."""
    ts = [k[0] for k in keys]
    if t <= ts[0]: return np.array(keys[0][1], float)
    if t >= ts[-1]: return np.array(keys[-1][1], float)
    i = max(0, min(len(keys) - 2, int(np.searchsorted(ts, t, side='right')) - 1))
    t0, p0 = keys[i]; t1, p1 = keys[i + 1]
    p0 = np.array(p0, float); p1 = np.array(p1, float)
    pm = np.array(keys[i - 1][1], float) if i > 0 else p0 - (p1 - p0)
    tm = keys[i - 1][0] if i > 0 else t0 - (t1 - t0)
    p2 = np.array(keys[i + 2][1], float) if i + 2 < len(keys) else p1 + (p1 - p0)
    t2 = keys[i + 2][0] if i + 2 < len(keys) else t1 + (t1 - t0)
    h = t1 - t0; s = (t - t0) / h
    m0 = (p1 - pm) / (t1 - tm) * h; m1 = (p2 - p0) / (t2 - t0) * h
    s2 = s * s; s3 = s2 * s
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * m1


def hermite(p0, v0, p1, v1, t0, t1, t):
    """cubic Hermite from (p0, velocity v0) at t0 to (p1, v1) at t1 (velocities in units per second)."""
    h = t1 - t0; s = min(1.0, max(0.0, (t - t0) / h)); s2 = s * s; s3 = s2 * s
    return ((2 * s3 - 3 * s2 + 1) * np.asarray(p0, float) + (s3 - 2 * s2 + s) * h * np.asarray(v0, float)
            + (-2 * s3 + 3 * s2) * np.asarray(p1, float) + (s3 - s2) * h * np.asarray(v1, float))


def hold_keys(keys, t):
    """piecewise smoothstep between keys (no overshoot): for paths that must stop dead on a key."""
    if t <= keys[0][0]: return np.array(keys[0][1], float)
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            u = sstep((t - a[0]) / (b[0] - a[0]))
            return np.array(a[1], float) + (np.array(b[1], float) - np.array(a[1], float)) * u
    return np.array(keys[-1][1], float)


# ------------------------------------------------------------------------------------------------------------------------------ city
CITY_KEYS = [  # (t, (x, y, z)) of the CITY root (the collar ring's centre); after the grab these are only the design direction
    (0.0, (-180.0, 60.0, 320.0)), (20.0, (-180.0, 60.0, 320.0)), (23.5, (-188.0, 48.0, 337.0)), (31.6, (-189.0, 47.0, 339.0)),
    (34.0, (-200.0, 66.0, 368.0)), (35.8, (-228.0, 118.0, 396.0)), (38.6, (-300.0, 260.0, 402.0)), (42.0, (-446.0, 406.0, 405.0)),
    (45.6, (-500.0, 330.0, 400.0)), (49.0, (-520.0, 240.0, 398.0)), (55.0, (-560.0, 90.0, 396.0)), (61.0, (-612.0, -80.0, 395.0)),
    # it slows as it nears the spout (the end trails ~85-100 m behind it, so the hanging chain never curls under the collar)
    (65.6, (-686.0, -358.0, 398.0)), (67.5, (-706.0, -393.0, 401.0)), (69.3, (-726.0, -419.0, 405.0)),
    (70.0, (-742.0, -446.0, 408.0)), (72.0, (-766.0, -462.0, 410.0)),
    (76.0, (-800.0, -390.0, 340.0)), (78.2, (-789.0, -327.0, 290.0)), (78.6, (-787.0, -326.0, 288.0)), (80.6, (-780.0, -322.0, 285.0)),
    (82.0, (-772.0, -318.0, 283.0)), (90.0, (-760.0, -312.0, 280.0)),
]
RELEASE = T['whip']               # the end link rips out of the sheared shackle; the city is free from here


def _city_design(t):
    if t <= RELEASE: return hold_keys([k for k in CITY_KEYS if k[0] <= RELEASE], t)
    p = catmull([k for k in CITY_KEYS if k[0] >= RELEASE], t)
    if t < RELEASE + 0.8:              # leave the mooring from rest (no velocity jump at the release)
        u = sstep(rng(t, RELEASE, RELEASE + 0.8)); p = np.array(CITY_KEYS[3][1], float) * (1 - u) + p * u
    return p


RHO_KEYS = [   # chain length / span while the mech holds it: ~1.005 = taut as a bar, 1.04 = a lazy sag
    (70.0, 1.0045), (72.0, 1.0045), (73.6, 1.006), (75.2, 1.012), (76.0, 1.012), (77.8, 1.006), (78.2, 1.0055),
    (80.6, 1.0055), (81.5, 1.022), (83.0, 1.034), (90.0, 1.042),
]


def rho(t):
    return float(hold_keys([(a, (b,)) for a, b in RHO_KEYS], t)[0])


def collar_of(t, root):
    return np.asarray(root, float) + rot_xyz(city_tilt(t)) @ COLLAR_OFF


def wrap_geom(t, col, pal=None):
    """the chain's contact with the lighthouse drum for the collar at `col` and the palm at `pal`: it comes down from the city,
    touches the drum at angle T1 (city side), wraps counter-clockwise to T2 and leaves for the palm. arc <= 0: no wrap."""
    pal = palm_path(t) if pal is None else np.asarray(pal, float)
    c = LIGHTHOUSE[:2]; R = WRAP_R
    dp = pal[:2] - c; rp = max(float(np.linalg.norm(dp)), R + 1e-3)
    dc = np.asarray(col, float)[:2] - c; rc = max(float(np.linalg.norm(dc)), R + 1e-3)
    ac = math.degrees(math.atan2(dc[1], dc[0]))
    T1 = ac + math.degrees(math.acos(R / rc)); T1 = (T1 + 180.0) % 360.0 - 180.0
    T2 = palm_angle_unwrapped(t) - math.degrees(math.acos(R / rp))
    arc = T2 - T1
    g = dict(arc=arc, T1=T1, T2=T2, pal=pal)
    if arc <= 0.0:
        # before it touches the drum: from GRIP on the mech holds the end low and level along the drum (L_grip), the chain lifts
        # over FILLET links and hangs to the city; at the first touch this is exactly the wrapped shape with no arc
        cut = end_cut(t)
        L_grip = math.sqrt(max(0.0, rp * rp - R * R)); wgr = sstep(rng(t, *GRIP)); L_eff = CHAIN_LEN + cut
        dzg = WRAP_Z[1] - float(pal[2]); L_g3 = math.hypot(L_grip, dzg)     # the held end runs down to the wrap's height
        wl = sstep(rng(t, GRIP[0] - 0.9, GRIP[0] - 0.1))      # the city gives that length back before the grip starts
        if wl > 0:
            d = np.asarray(col, float) - pal; phc = math.atan2(d[2], math.hypot(d[0], d[1]))
            extra = (L_g3 - (L_grip * math.cos(phc) + dzg * math.sin(phc))
                     + sum(PITCH * (1.0 - math.cos(phc - 0.8 * phc * k / (FILLET + 1))) for k in range(1, FILLET + 1)))
            L_eff = CHAIN_LEN + cut - wl * extra
        g.update(p1=pal, L_free=CHAIN_LEN + cut, L_eff=L_eff, L_arc=0.0, L_tail=0.0, L_grip=L_grip, dz_grip=dzg, w_grip=wgr); return g
    a1 = math.radians(T1); a2 = math.radians(T2)
    p1 = np.array((c[0] + R * math.cos(a1), c[1] + R * math.sin(a1), WRAP_Z[0]))
    p2 = np.array((c[0] + R * math.cos(a2), c[1] + R * math.sin(a2), WRAP_Z[1]))
    L_arc = math.hypot(math.radians(arc) * R, WRAP_Z[0] - WRAP_Z[1]); L_tail = float(np.linalg.norm(pal - p2))
    L_free = CHAIN_LEN + end_cut(t) - L_arc - L_tail
    # the chain lifts out of the groove over FILLET links (bake_chain): that bend costs a little length against the straight span
    col = np.asarray(col, float); phc = math.atan2(col[2] - p1[2], math.hypot(col[0] - p1[0], col[1] - p1[1]))
    extra = sum(PITCH * (1.0 - math.cos(phc - 0.8 * phc * k / (FILLET + 1))) for k in range(1, FILLET + 1))
    g.update(p1=p1, p2=p2, L_free=L_free, L_eff=L_free - extra, L_arc=L_arc, L_tail=L_tail)
    return g


HOLD_REF = (74.0, 76.0)           # the held direction is taken from the palm, then from the drum's axis (no jump at the wrap)


def _ref(t):
    k = sstep(rng(t, *HOLD_REF))
    return palm_path(t) * (1 - k) + np.array((LIGHTHOUSE[0], LIGHTHOUSE[1], WRAP_Z[0])) * k


def _held_dir(t):
    R = _ref(t); dc = collar_of(t, _city_design(t)); v = dc - R; d = float(np.linalg.norm(v))
    return R, v / d, d


def _solve_s(t, R, e, r):
    """distance along e from R at which the chain (wrapped or not) has span = free length / r."""
    lo, hi = 5.0, CHAIN_LEN + 60.0
    for _ in range(48):
        m = 0.5 * (lo + hi); col = R + e * m; g = wrap_geom(t, col)
        if float(np.linalg.norm(col - g['p1'])) > g['L_eff'] / r: hi = m
        else: lo = m
    return 0.5 * (lo + hi)


_HELD = {}


def _held_table():
    """the held distance sampled every 1/48 s and smoothed (sigma 0.2 s): the chain's path length steps by a metre or two when
    it first touches the drum; the city must not jump. Never closer to straight than rho = 1.0045."""
    if 'ts' in _HELD: return _HELD
    ts = np.arange(T['grab'] - 0.5, 90.75, 1.0 / 48)
    raw = np.zeros(len(ts)); cap = np.zeros(len(ts))
    for i, t in enumerate(ts):
        tt = max(t, T['grab'] + 1e-4); R, e, _ = _held_dir(tt)
        raw[i] = _solve_s(tt, R, e, rho(tt)); cap[i] = _solve_s(tt, R, e, 1.0045)
    k = np.exp(-0.5 * (np.arange(-30, 31) / 9.6) ** 2); k /= k.sum()
    sm = np.convolve(np.pad(raw, 30, mode='edge'), k, mode='valid')
    _HELD.update(ts=ts, s=np.minimum(sm, cap), raw=raw, cap=cap)
    return _HELD


def city_pos(t):
    d = _city_design(t)
    if t <= T['grab']: return d
    H = _held_table(); R, e, s_design = _held_dir(t)
    s = float(np.interp(t, H['ts'], H['s']))
    w = sstep(rng(t, T['grab'], T['taut']))
    col = R + e * (s_design * (1 - w) + s * w)
    return col - rot_xyz(city_tilt(t)) @ COLLAR_OFF


def collar(t):
    return collar_of(t, city_pos(t))


def city_vel(t, dt=1.0 / 48):
    return (city_pos(t + dt) - city_pos(t - dt)) / (2 * dt)


def city_tilt(t):
    """(rx, ry, rz) degrees about the root: still while anchored, a shiver while the chain is taut, the lurch (35.2), a wobble
    while drifting toward the spout, a heave toward the mech while it hauls, level again after the release."""
    rx = ry = rz = 0.0
    if 20.0 < t < RELEASE + 0.3:      # taut: a fine shiver (fades through the release)
        k = sstep(rng(t, 20.0, 22.0)) * (1.0 - sstep(rng(t, RELEASE, RELEASE + 0.3)))
        rx += 0.35 * math.sin(t * 23.0) * k; ry += 0.25 * math.sin(t * 19.0 + 1.0) * k
    if t >= RELEASE:
        # the lurch: a hard tip at the hit, a damped rock back, settling to a smaller lean while drifting
        k = sstep(rng(t, 35.05, 35.55))
        rock = 0.18 * math.sin((t - 35.55) * 2 * math.pi / 1.1) * math.exp(-(t - 35.55) / 0.9) if t > 35.55 else 0.0
        k = (k + rock) * (1.0 - 0.75 * sstep(rng(t, 38.0, 44.0)))
        rx += -7.0 * k; ry += 4.0 * k
        w = sstep(rng(t, 36.0, 40.0)) * (1.0 - sstep(rng(t, 80.6, 84.0)))
        rx += 1.6 * math.sin(t * 0.9) * w; ry += 1.2 * math.sin(t * 0.7 + 1.0) * w
        rz += -6.0 * sstep(rng(t, 37.0, 70.0))
    if t > T['grab']:                 # the mech's pull at the collar tips the base toward it, released at the end
        k = sstep(rng(t, T['grab'], 71.0)) * (1.0 - sstep(rng(t, 80.6, 84.5)))
        rx += 4.0 * k; ry -= 2.5 * k
        k2 = sstep(rng(t, 76.0, 78.2)) * (1.0 - sstep(rng(t, 80.6, 84.5)))
        rx += 2.0 * k2
    return np.array((rx, ry, rz))


# ------------------------------------------------------------------------------------------------------------------------------ waterspout
SPOUT_KEYS = [(22.0, (-3500.0, -2500.0)), (50.0, (-2300.0, -1550.0)), (60.0, (-1900.0, -1250.0)), (70.0, (-1500.0, -850.0)),
              (78.6, (-960.0, -470.0)), (90.0, (-300.0, -900.0))]


def spout_pos(t):
    if t < 22.0: return None
    p = catmull(SPOUT_KEYS, t)
    return np.array((p[0], p[1], 0.0))


# ------------------------------------------------------------------------------------------------------------------------------ sun, eyes
def sun(t):
    if t < 82.0: return 95.0, 17.0, '#ffe6c6'
    u = sstep(rng(t, 82.0, 86.0))
    return 95.0, 17.0 + 3.0 * u, '#ffeccc'


def storm(t):
    if t < 14.0: return 0.0
    if t < 30.0: return 0.15 + 0.85 * sstep(rng(t, 14.0, 30.0))
    if t < 80.6: return 1.0
    return 1.0 - sstep(rng(t, 80.6, 85.0)) * 0.92


def eyes(t):
    """visor brightness 0..1: power-on flicker from 47.4, full at 48.2 (the boot chord), strain flicker 73.0-73.5, dims 88.2."""
    if t < T['eyes_on']: return 0.0
    if t < 47.8:
        return (0.25 + 0.35 * ((int((t - T['eyes_on']) * 10) % 2) == 0)) * sstep(rng(t, 47.4, 47.5))
    if t < T['boot']: return 0.45 + 0.55 * sstep(rng(t, 47.8, T['boot']))
    if 73.0 <= t < 73.5: return 0.55 + 0.45 * (int(t * 12) % 3 != 0)
    if t >= T['dim']: return max(0.0, 1.0 - (t - T['dim']) / 1.2)
    return 1.0


# ------------------------------------------------------------------------------------------------------------------------------ chain end
# 30.0 .. 45.0: designed (the pin shears, the bent shackle holds the link until 31.6, the end whips up through the water, bursts
# out (simulation), is led back down, skips (39.5 .. 41.3), smashes crane A at 42.0, is torn out of the wreck);
# 45.0 .. 65.6: trails behind the drifting city, skipping on the waves; 65.6 .. 69.3: the approach to the mech (it skips away from
# the reaching hand: touch-downs 67.5 / 68.1 / 68.65, and lands in the palm at 69.3).
CRANE_HIT = np.array((-368.0, 398.0, 9.0))      # where the end meets crane A's waterside leg (refined once PORT delivers)
END_KEYS_A = [
    (30.0, tuple(ANCHOR)), (31.1, (-100.3, 149.6, -51.3)), (31.6, (-101.5, 148.0, -47.5)),
    # the whip: the end jerks free (31.6), the wave reaches it, it bursts out at ~80 m/s on the hit (33.2), arcs 44 m high and
    # slams back into the sea (35.4); the chain behind it is simulated
    (32.0, (-103.5, 146.2, -41.6)), (32.4, (-106.5, 143.4, -35.7)), (32.8, (-111.0, 139.3, -23.9)), (33.2, (-118.0, 133.0, 0.0)),
    (33.45, (-122.5, 128.6, 17.7)), (33.7, (-126.5, 124.8, 30.9)), (33.95, (-130.3, 121.0, 39.6)), (34.3, (-135.0, 117.0, 44.0)),
    (34.7, (-140.5, 112.5, 38.2)), (34.95, (-144.0, 109.5, 28.7)), (35.2, (-147.5, 107.0, 14.6)), (35.4, (-150.0, 106.0, 0.5)),
    (35.9, (-158.0, 112.0, 2.0)),
    (37.1, (-175.0, 140.0, 3.0)), (38.6, (-240.0, 230.0, 2.0)), (40.1, (-300.0, 310.0, 3.0)),
    (41.1, (-340.0, 362.0, 5.5)), (42.0, tuple(CRANE_HIT)), (42.7, (-385.0, 390.0, 6.0)), (43.5, (-410.0, 372.0, 2.0)),
    (45.0, (-440.0, 330.0, 1.5)),
]
TRAIL_D = 80.0                 # metres behind the collar (horizontal) while skimming


def skip_z(t, period=0.6, h=2.8):
    """the end skipping on the waves: low arcs between touch-downs at t = SKIP_PHASE + k period (on the sea it rides at +1.2)."""
    ph = ((t - SKIP_PHASE) / period) % 1.0
    k = 0.6 + 0.4 * math.sin(t * 0.77)
    return 1.2 + h * k * 4.0 * ph * (1.0 - ph)


def _trail_point(t):
    c = city_pos(t); v = city_vel(t); v[2] = 0.0
    sp = np.linalg.norm(v)
    back = -v / sp if sp > 1e-3 else np.array((1.0, 0.0, 0.0))
    side = np.array((-back[1], back[0], 0.0))
    wig = 9.0 * math.sin(t * 1.3) + 2.0 * math.sin(t * 2.3 + 0.7)
    p = c + back * TRAIL_D + side * wig
    p[2] = skip_z(t)
    return p


END_KEYS_C = [
    (65.6, None), (66.6, (-653.0, -306.0, 2.5)), (67.5, (-661.0, -315.0, 0.9)), (67.8, (-665.0, -320.0, 6.0)),
    (68.1, (-669.0, -324.0, 0.9)), (68.4, (-672.0, -327.0, 4.0)), (68.65, (-674.0, -329.0, 0.9)), (69.0, (-675.6, -331.2, 2.2)),
    (69.3, (-676.0, -332.0, 2.6)),
]


A_MIN = 16.5     # the free chain's tightest hanging curve (m): 5.25 m links then bend <= 18.2 deg (they interlock to 25)


def _reach(t, p):
    """keep the free end far enough out from under the collar that the hanging chain (an exact-length catenary) never
    curls tighter than A_MIN: the end is pushed radially out (smooth C1 ramp, zero when there is room)."""
    c = collar(t); d = np.asarray(p[:2], float) - c[:2]; h = float(np.hypot(d[0], d[1]))
    v = float(c[2] - p[2]); s2 = CHAIN_LEN ** 2 - v * v
    if s2 <= 0.0 or h < 1e-6: return p
    need = 2.0 * A_MIN * math.asinh(math.sqrt(s2) / (2.0 * A_MIN))
    k = 4.0; x = (need + k - h) / k
    if x <= 0.0: return p
    push = k * (x * x / 4.0 if x < 2.0 else x - 1.0)
    q = np.array(p, float); q[:2] = c[:2] + d / h * (h + push)
    return q


def end_guide(t):
    """world position of the chain's last joint while it is free (30.0 .. 69.3); None before (anchored) / after (in the palm)."""
    if t < T['pin_shear'] or t > T['grab']: return None
    return _reach(t, _end_design(t))


def _end_design(t):
    if t <= 45.0:
        p = catmull(END_KEYS_A, t)
        w = sstep(rng(t, 38.0, 38.6)) * (1.0 - sstep(rng(t, 41.3, 41.7)))
        if w > 0: p[2] = p[2] * (1 - w) + skip_z(t) * w
        return p
    if t <= 65.6:
        p = _trail_point(t)
        if t < 46.5:      # blend out of the designed swing (carried on at its 45.0 velocity) into the trail
            u = sstep(rng(t, 45.0, 46.5))
            v45 = (catmull(END_KEYS_A, 45.0) - catmull(END_KEYS_A, 44.98)) / 0.02
            p = (catmull(END_KEYS_A, 45.0) + v45 * (t - 45.0)) * (1 - u) + p * u
        return p
    keys = [(65.6, tuple(_trail_point(65.6)))] + END_KEYS_C[1:]
    return catmull(keys, t)


# ------------------------------------------------------------------------------------------------------------------------------ the palm
PALM_KEYS = [   # the mech's gripping palm (world) from the grab through the drag; the chain's last joint is pinned to it
    (69.3, (-676.0, -332.0, 2.6)), (69.6, (-679.0, -337.0, 5.0)), (70.0, (-684.0, -345.0, 11.0)), (71.0, (-690.0, -352.0, 13.0)),
    (72.0, (-690.0, -350.0, 15.0)),
]
WIND = dict(t0=76.0, t1=78.2, a0=-40.0, a1=160.0, r=21.5, z=30.0, k0=0.65)   # palm circles the drum CCW at the mech's hip height (deg
                                                 # from +X): the tail runs down from the fist to the wrap under the cornice
HOLD = dict(da=6.0, dr=0.0, dz=0.0)             # after the wind: leans into the pull (78.6 .. 80.6) (the fist keeps its place
                                                 # beside the planted body: the arm clear of the left thigh)
REST_LIFT = dict(t=(80.9, 83.6), dr=0.0, dz=1.5)   # the chain slack, the mech eases up, the fist a little higher (a looser hold)
END_CUT = (69.45, 70.25, 3.0)   # from the grab the chain's last joint sits this far back along the chain from palm_path (the snap
                                 # pulls the fist up the chain): the long grip link's centre is grip.END_SHIFT2 - END_SHIFT = 2.6 m
                                 # further out than the old end link's, its free end 4.2 m; 2.6 leaves that end 0.6 m off the left
                                 # thigh in the rest, 3.4 over 1 m (side script cut_fit). The chain is built CHAIN_LEN + cut
                                 # long to the palm and stops CHAIN_LEN from the collar (bake_chain); the city's held span counts
                                 # the cut (wrap_geom).


def end_cut(t):
    a, b, c = END_CUT
    return c * sstep(rng(t, a, b))


HAUL_LIFT = (74.5, 75.9, 10.0)     # the haul up the head's mound: the fist rides this much higher over this window (sin^2 bump): the
                                  # hips are high on the slope (the legs' band), the arm hangs from them


def _wind_u(t):
    """0..1 along the wind: starts at the approach speed (slope k0), stops dead at t1."""
    x = rng(t, WIND['t0'], WIND['t1']); k0 = WIND['k0']
    return (x ** 3 - 2 * x * x + x) * k0 + (-2 * x ** 3 + 3 * x * x)


def _circle(a_deg, r, z):
    a = math.radians(a_deg)
    return LIGHTHOUSE + np.array((math.cos(a) * r, math.sin(a) * r, z))


def _wind_start_vel():
    w = math.radians(WIND['a1'] - WIND['a0']) * WIND['k0'] / (WIND['t1'] - WIND['t0'])     # rad/s at t0
    a = math.radians(WIND['a0'])
    return np.array((-math.sin(a), math.cos(a), 0.0)) * WIND['r'] * w


def palm_angle_unwrapped(t):
    """continuous angle (deg) of the palm round the lighthouse."""
    if t < WIND['t0']:
        d = palm_path(t) - LIGHTHOUSE; return math.degrees(math.atan2(d[1], d[0]))
    if t <= WIND['t1']:
        return WIND['a0'] + (WIND['a1'] - WIND['a0']) * _wind_u(t)
    return WIND['a1'] + HOLD['da'] * sstep(rng(t, T['spout_pass'], T['slack']))


def palm_path(t):
    if t < T['grab']: return None
    if t <= 72.0: return catmull(PALM_KEYS, t)
    if t < WIND['t0']:            # the haul: from the drag back to the drum's east side, arriving at walking speed
        v0 = (np.array(PALM_KEYS[-1][1]) - np.array(PALM_KEYS[-2][1])) / (PALM_KEYS[-1][0] - PALM_KEYS[-2][0])
        p = hermite(PALM_KEYS[-1][1], v0, _circle(WIND['a0'], WIND['r'], WIND['z']), _wind_start_vel(), 72.0, WIND['t0'], t)
        a, b, h = HAUL_LIFT
        if a < t < b: p = p + np.array((0.0, 0.0, h * math.sin(math.pi * (t - a) / (b - a)) ** 2))
        return p
    if t <= WIND['t1']:
        return _circle(WIND['a0'] + (WIND['a1'] - WIND['a0']) * _wind_u(t), WIND['r'], WIND['z'])
    k = sstep(rng(t, T['spout_pass'], T['slack'])); u = sstep(rng(t, *REST_LIFT['t']))
    return _circle(WIND['a1'] + HOLD['da'] * k, WIND['r'] + HOLD['dr'] * k + REST_LIFT['dr'] * u,
                   WIND['z'] + HOLD['dz'] * sstep(rng(t, T['slack'], T['slack'] + 2.0)) + REST_LIFT['dz'] * u)


# ------------------------------------------------------------------------------------------------------------------------------ the seabed
def bed(x, y):
    """seabed height under the harbour: a trench (-60) under the anchor rising to -12 toward the quay and elsewhere."""
    d2 = (x + 100.0) ** 2 + (y - 150.0) ** 2
    return -60.0 + 48.0 * (1.0 - np.exp(-d2 / (2 * 170.0 ** 2)))
