# ANCHOR — unit 07's performance across the whole film (lead). Every frame is solved once (bake: FK design + leg/arm IK on the
# rig) and stored in out/track/mech_track.npz, so every shot keys exactly the same motion (cuts match) and cameras / FX can ask
# where any part of the mech is at any time.
#   blender -b -P shots/mechanim.py -- bake [f0-f1]          solve frames (default all) -> merged into out/track/mech_track.npz
#   blender -b -P shots/mechanim.py -- lab t1,t2,.. [view]   stills of those moments (mech + ground proxy) -> out/lab/mech
#   blender -b -P shots/mechanim.py -- qa [f0-f1] [step]     self-intersection / ground / chain checks on the track
# In a film run: key_range(W, f0, f1) keys the rig (root, joints, pistons), the props (eyes, beacon, lamps), the gull, the chick
# and the vines on frames f0..f1 from the track.  Queries (numpy only): mat(name, t) 4x4 world, point(name, t) xyz,
# fwd(name, t) the part's facing (-Y of its frame), gull_world(t).  Tracked names: TRACKED below.
import math, os, sys, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
for _p in ('kit', 'assets', 'shots'):
    _q = os.path.join(ROOT, _p)
    if _q not in sys.path: sys.path.insert(0, _q)
import story as S
import mechplan as MP

FPS = 24
NF = 2160
TRACK = os.path.join(ROOT, 'out', 'track', 'mech_track.npz')


def tof(f): return (f - 1) / FPS
def fr(t): return int(round(t * FPS)) + 1
def ss(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
def rng(t, a, b): return min(1.0, max(0.0, (t - a) / (b - a)))
def lerp(a, b, u): return a + (b - a) * u
def twos(t): return math.floor(t * FPS / 2.0 + 1e-6) * 2.0 / FPS


def pulse(t, t0, up=0.08, down=0.4):
    """0 -> 1 in `up` s, then an exponential settle (down = time to ~8 %)."""
    if t < t0: return 0.0
    if t < t0 + up: return ss((t - t0) / up)
    return math.exp(-2.5 * (t - t0 - up) / down)


# ===================================================================================================================== beats
T_GULL_OFF = 44.05            # the water crashes over the head: the gull bursts off the nest
T_GULL_GONE = 45.6            # out of every shot before the strike
T_GULL_IN = 86.4              # the return: seen from s42's cut on, in low over the open sea beyond its camera (gull_home)
T_GULL_LAND = 87.45
T_JOLT = 45.62                # lightning on the antenna: one jolt through the frame
T_BOOT = S.T['boot']
T_RISE = S.T['rise']
T_DIM = S.T['dim']

TRACKED = ['root', 'pelvis', 'spine', 'chest', 'neck', 'head', 'shoulderL', 'shoulderR', 'elbowL', 'elbowR', 'wristL', 'wristR',
           'hipL', 'hipR', 'kneeL', 'kneeR', 'ankleL', 'ankleR', 'palmL', 'palmR', 'soleL', 'soleR', 'antenna_tip', 'visor',
           'steam_0', 'steam_1', 'steam_2', 'nest', 'gull', 'chick']


# ===================================================================================================================== props
def eyes(t): return S.eyes(t)


def beacon(t):
    """the shoulder beacons + the antenna tip: amber, blinking 1 Hz from the boot, out with the visor."""
    if t < T_BOOT or t >= T_DIM + 1.2: return 0.0
    on = 1.0 if ((t - T_BOOT) % 1.0) < 0.55 else 0.12
    return on * (1.0 if t < T_DIM else max(0.0, 1.0 - (t - T_DIM) / 1.2))


def lamps(t):
    """the head's work lamps: on a beat after the eyes, off with them."""
    if t < 48.45: return 0.0
    k = ss(rng(t, 48.45, 48.62))
    if t >= T_DIM: k *= max(0.0, 1.0 - (t - T_DIM) / 1.0)
    return k


# ===================================================================================================================== the design
SLEEP_ROOT = MP.SLEEP_ROOT


def _addv(a, b, k=1.0): return tuple(x + k * y for x, y in zip(a, b))


def design(t, mech, raw=False):
    """the FK pose dict at t (set_pose format) + IK targets: {'pose': {...}, 'legs': {side: dict(p, yaw, pitch, roll, pole, w) or
    None}, 'arms': {side: (pos, hand rot 3x3 or None, pole or None, weight) or None}, 'look': (target, weight, neck share) or None}.
    raw: without the pelvis-band correction (pelvis_pass must have run for the frame otherwise)."""
    if t <= T_RISE: return _sleep(t, mech)
    D = _awake(t, mech)
    fill = D.pop('fill', None)
    if not raw:
        c = _DZC.get(fr(t), 0.0) if abs(fr(t) - (t * FPS + 1)) < 1e-6 else _dzc_at(t)
        if c:
            P = D['pose']; h = P['hips']; P['hips'] = (h[0], h[1], h[2] + c)
        if fill is not None: fill(t, D)
    D.setdefault('look', None)
    return D


def _sleep(t, mech):
    P = {k: (tuple(v) if isinstance(v, (tuple, list)) else v) for k, v in mech.POSES['sleep'].items()}
    P['root'] = (float(SLEEP_ROOT[0]), float(SLEEP_ROOT[1]), float(SLEEP_ROOT[2]), 0.0)
    # 45.62: the strike on the antenna runs through the frame: the head snaps back, the fingers twitch
    j = pulse(t, T_JOLT, 0.05, 0.45)
    if j > 0:
        P['head'] = _addv(P['head'], (-3.0 * j, 0.0, 1.5 * j)); P['neck'] = _addv(P['neck'], (-1.5 * j, 0.0, 0.0))
        P['chest'] = _addv(P['chest'], (-0.8 * j, 0.0, 0.0))
        P['fingersL'] = tuple(c + 0.22 * j for c in P['fingersL']); P['fingersR'] = tuple(c + 0.25 * j for c in P['fingersR'])
    # 48.2: the boot chord: one shudder; 48.5 .. 49.0: the head lifts (the first motion of its own)
    b = pulse(t, T_BOOT, 0.06, 0.3)
    if b > 0:
        P['chest'] = _addv(P['chest'], (1.2 * b, 0.0, 0.0)); P['head'] = _addv(P['head'], (1.0 * b, 0.0, 0.0))
    u = ss(rng(t, 48.5, 49.0))
    if u > 0:
        P['neck'] = _addv(P['neck'], (-5.0 * u, 0.0, 0.0)); P['head'] = _addv(P['head'], (-8.0 * u, -4.0 * u, -3.0 * u))
    return {'pose': P, 'legs': {'L': None, 'R': None}, 'arms': {'L': None, 'R': None}, 'look': None}


# ===================================================================================================================== rig numbers (numpy)
HIP_OFF = np.array((8.6, 0.0, -2.0))       # hip pivot from the pelvis pivot (rest)
PELVIS_Z = 44.0
SOLE_ANK = np.array((0.0, -3.0, -6.2))     # sole contact minus ankle pivot (rest)
D_MIN, D_MAX = 23.6, 35.3                  # hip-ankle distance band of a planted leg (knee <= ~100 deg .. nearly straight)
STAND_DZ = -0.9                            # the standing pelvis: knees soft (~22 deg)


def Rx(a): a = math.radians(a); c, s = math.cos(a), math.sin(a); return np.array(((1, 0, 0), (0, c, -s), (0, s, c)))
def Ry(a): a = math.radians(a); c, s = math.cos(a), math.sin(a); return np.array(((c, 0, s), (0, 1, 0), (-s, 0, c)))
def Rz(a): a = math.radians(a); c, s = math.cos(a), math.sin(a); return np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))
def eul(e): return Rz(e[2]) @ Ry(e[1]) @ Rx(e[0])


def hip_world(root, hips, pelvis, side):
    sx = 1.0 if side == 'L' else -1.0
    pl = np.array((0.0, 0.0, PELVIS_Z)) + np.asarray(hips, float)
    return np.asarray(root[:3], float) + Rz(root[3]) @ (pl + eul(pelvis) @ (HIP_OFF * (sx, 1.0, 1.0)))


def ankle_of(ft):
    Rf = Rz(ft.get('yaw', 0.0)) @ Ry(ft.get('roll', 0.0)) @ Rx(ft.get('pitch', 0.0))
    return np.asarray(ft['p'], float) - Rf @ SOLE_ANK


def keys_at(keys, t):
    """pchip through [(t, value or tuple)], clamped."""
    k2 = [(a, tuple(v) if isinstance(v, (tuple, list)) else (v,)) for a, v in keys]
    r = MP.pchip_keys(k2, t)
    return tuple(float(x) for x in r) if len(r) > 1 else float(r[0])


def _RM():
    import rigmath as RM
    return RM


def base_pose():
    P = {k: (tuple(v) if isinstance(v, (tuple, list)) else v) for k, v in STAND.items()}
    return P


STAND = {
    'root': (0, 0, 0, 0), 'hips': (0, 0, STAND_DZ), 'pelvis': (0, 0, 0), 'spine': (0, 0, 0), 'chest': (2, 0, 0), 'neck': (-3, 0, 0),
    'head': (1, 0, 0), 'shoulderL': (3, -9, 2), 'elbowL': (-16, 0, 0), 'wristL': (6, -4, 0), 'shoulderR': (3, -9, 2), 'elbowR': (-16, 0, 0),
    'wristR': (6, -4, 0), 'hipL': (0, 0, 0), 'kneeL': (0, 0, 0), 'ankleL': (0, 0, 0), 'hipR': (0, 0, 0), 'kneeR': (0, 0, 0),
    'ankleR': (0, 0, 0), 'fingersL': (0.3, 0.38, 0.45), 'thumbL': 0.2, 'fingersR': (0.3, 0.38, 0.45), 'thumbR': 0.2,
}

_SLEEP_FEET = {}            # the sleep pose's sole frames {side: dict(p, yaw, pitch, roll)} (set in Blender before designing)


def _pl(side, kind=None, t=None):
    """the mechplan plant of a side by kind / time."""
    for q in MP.plants_of(side):
        if (kind is None or q['kind'] == kind) and (t is None or abs(q['t'] - t) < 1e-6): return q
    raise KeyError((side, kind, t))


def _foot_from_plan(t, sd):
    f = MP.foot_at(t, sd)
    if f is None: return None
    return dict(p=np.array(f['p'], float), yaw=f['yaw'], pitch=f['pitch'], roll=f['roll'], planted=f['planted'], w=1.0)


def _with_root(P, t, root_xyz, yaw, pelvis_pivot=None, hips=None):
    """set P['root'] and P['hips'] either from a world pelvis pivot or from a hips offset."""
    P['root'] = (float(root_xyz[0]), float(root_xyz[1]), float(root_xyz[2]), float(yaw))
    if pelvis_pivot is not None:
        loc = Rz(yaw).T @ (np.asarray(pelvis_pivot, float) - np.asarray(root_xyz, float)) - np.array((0.0, 0.0, PELVIS_Z))
        P['hips'] = tuple(float(x) for x in loc)
    elif hips is not None: P['hips'] = tuple(float(x) for x in hips)
    return P


# ===================================================================================================================== 49.0 .. 51.8 the rise
# Its shoulders can't lift sideways (the pauldrons meet the collar past ~20 deg of abduction; out/qa/cone_shoulderL.npz) and nothing
# but the wall is within arm's reach (the knees are 25+ m from the shoulders, the dock floor 26 m below), so it rises like a wall
# slide: the arms strain up out of the water (the arm vines tear at 49.3), cock back with clenched fists while the feet slide in
# and the back pushes up the wall, then swing forward hard (50.3 .. 50.8) as the legs drive the hips forward over the feet; the
# torso comes upright and it straightens into the stand pose (51.8). Every arm motion stays in the sagittal plane.
RISE_END = 51.8
RISE_KEYS = [  # t, (pelvis pivot y, z, pelvis rx, spine rx, chest rx, neck rx, head rx)
    (49.0, (585.26, -6.86, -26.0, 8.0, 10.0, 12.0, 9.0)), (49.3, (585.26, -6.82, -25.9, 8.0, 10.2, 7.0, 5.0)),
    (49.55, (585.2, -6.4, -25.5, 8.2, 10.4, 2.0, 0.5)), (49.9, (585.26, -2.6, -23.0, 8.0, 9.5, -1.0, -1.5)),
    (50.25, (585.4, 0.8, -20.5, 7.0, 8.5, -2.5, -2.5)), (50.5, (585.2, 3.2, -19.0, 6.5, 7.5, -3.5, -3.5)),
    (50.75, (580.5, 11.5, -6.0, 4.0, 4.0, -6.0, -6.0)), (51.0, (572.5, 19.5, 10.0, 4.0, 3.0, -8.0, -8.0)),
    (51.25, (565.0, 25.8, 12.0, 3.0, 2.5, -8.0, -6.0)), (51.5, (561.0, 28.6, 6.0, 2.0, 2.0, -6.0, -4.0)),
    (51.8, (560.0, 29.22, 2.0, 1.0, 2.0, -3.0, 1.0))]
RISE_HEAD_TURN = [(49.0, (5.0, 3.0)), (49.5, (0.0, 0.0))]          # the head lift's ry / rz fade out
RISE_TWIST_FADE = (49.0, 49.6)                                     # the sleep pose's spine / chest twist (rz) fades out
RISE_SLIDE = {'L': (49.9, 50.35), 'R': (49.93, 50.38)}                  # the feet slide in to the stand marks
RISE_ARM_HOLD = 49.3                                               # the arms keep the sleep pose until the vines give
RISE_ARM_KEYS = [  # after the sleep keys (49.0, 49.3): (shoulder rx, ry, rz, elbow rx, wrist rx, ry, rz); + rx = the arm back
    (49.6, (12.0, -18.0, -8.0, -32.0, 16.0, 4.0, 14.0)),      # the arms tear free and swing back past the hips
    (49.9, (26.0, -12.0, -2.0, -60.0, 10.0, 0.0, 4.0)),       # cocked back, fists behind the hips
    (50.3, (34.0, -10.0, 0.0, -80.0, 8.0, 0.0, 0.0)),
    (50.8, (-50.0, -11.0, 0.0, -62.0, 6.0, 0.0, 0.0)),        # the forward swing that carries the body over the feet
    (51.15, (-38.0, -10.0, 1.0, -44.0, 6.0, -2.0, 0.0)),
    (51.5, (-8.0, -9.0, 2.0, -22.0, 6.0, -4.0, 0.0)),
    (RISE_END, (3.0, -9.0, 2.0, -16.0, 6.0, -4.0, 0.0))]
RISE_FINGERS = [(49.3, 0.92), (50.9, 0.92), (51.3, 0.7), (RISE_END, 0.4)]     # the fists clench in the strain (49.05 .. 49.3)
_SLEEP_HANDS = {}           # {side: dict(p = palm, R = wrist world 3x3)} of the sleep pose at 49.0
_SLEEP_POLES = {}           # {side: the sleep pose's knee direction off the hip-ankle line} (the rise's IK starts in that plane)
RISE_POLE = (T_RISE, 51.0)  # .. and turns to the foot's own front over this


def _rise(t, mech):
    import rigmath as RM
    P = base_pose()
    sl = mech.POSES['sleep']
    k = keys_at(RISE_KEYS, t)
    tw = 1.0 - ss(rng(t, *RISE_TWIST_FADE))
    P['pelvis'] = (k[2], 0.0, 0.0); P['spine'] = (k[3], 0.0, sl['spine'][2] * tw); P['chest'] = (k[4], 0.0, sl['chest'][2] * tw)
    hr = keys_at(RISE_HEAD_TURN, t)
    P['neck'] = (k[5], 0.0, 0.0); P['head'] = (k[6], hr[0], hr[1])
    pivot = np.array((-460.0, k[0], k[1]))
    w_end = ss(rng(t, 50.5, 51.5))
    root = np.array((-460.0, k[0] - 2.0 * (1.0 - w_end), lerp(-14.0, -13.88, ss(rng(t, 49.0, RISE_END)))))
    _with_root(P, t, root, 0.0, pelvis_pivot=pivot)
    for sd in ('L', 'R'):
        k0 = (sl['shoulder' + sd][0], sl['shoulder' + sd][1], sl['shoulder' + sd][2], sl['elbow' + sd][0],
              sl['wrist' + sd][0], sl['wrist' + sd][1], sl['wrist' + sd][2])
        v = keys_at([(T_RISE, k0), (RISE_ARM_HOLD, k0)] + RISE_ARM_KEYS, t)
        # the strain: a tremor through the arms before the vines give (49.05 .. 49.3)
        tr = math.sin(2 * math.pi * 9.0 * (t - 49.0)) * ss(rng(t, 49.05, 49.15)) * (1.0 - ss(rng(t, 49.24, 49.3)))
        P['shoulder' + sd] = (v[0] + 0.6 * tr, v[1], v[2]); P['elbow' + sd] = (v[3] - 0.8 * tr, 0.0, 0.0); P['wrist' + sd] = (v[4], v[5], v[6])
        f0 = tuple(sl['fingers' + sd]) if isinstance(sl['fingers' + sd], (tuple, list)) else (sl['fingers' + sd],) * 3
        c = keys_at([(T_RISE, f0), (49.05, f0)] + [(a, (b, b + 0.03, b)) for a, b in RISE_FINGERS], t)
        th = keys_at([(T_RISE, sl['thumb' + sd]), (49.05, sl['thumb' + sd]), (49.3, 0.42), (50.9, 0.42), (RISE_END, 0.22)], t)
        P['fingers' + sd] = c; P['thumb' + sd] = RM.safe_thumb(c, th)
    legs = {}
    for sd in ('L', 'R'):
        a = _SLEEP_FEET[sd]; b = _pl(sd, 'stand'); t0, t1 = RISE_SLIDE[sd]
        u = ss(rng(t, t0, t1))
        p = a['p'] + (b['p'] - a['p']) * u + np.array((0.0, 0.0, 0.8 * math.sin(math.pi * u)))
        ft = dict(p=p, yaw=lerp(a['yaw'], b['yaw'], u), pitch=lerp(a['pitch'], b['pitch'], u), roll=lerp(a['roll'], b['roll'], u),
                  w=1.0, planted=u >= 1.0)
        wp = ss(rng(t, *RISE_POLE)); fr_ = (Rz(ft['yaw']) @ Ry(ft['roll']) @ Rx(ft['pitch'])) @ np.array((0.0, -1.0, 0.0))
        pv = (1.0 - wp) * _SLEEP_POLES[sd] + wp * fr_; ft['pole'] = pv / max(np.linalg.norm(pv), 1e-9)
        legs[sd] = ft
    look = None
    if t > 51.1: look = (city_look(t), ss(rng(t, 51.1, RISE_END)), 0.45)
    return {'pose': P, 'legs': legs, 'arms': {'L': None, 'R': None}, 'look': look}


def prepare_np(mech_poses):
    """the sleep pose's sole frames and hands at 49.0, from the numpy rig (identical to Blender's)."""
    import rigmath as RM
    class _M: POSES = mech_poses
    P = _sleep(T_RISE, _M)['pose']; F = RM.frames(P)
    for sd in ('L', 'R'):
        m = F['sole' + sd]; R = m[:3, :3]
        pitch = math.degrees(math.atan2(R[2, 1], R[2, 2])); roll = math.degrees(-math.asin(max(-1.0, min(1.0, R[2, 0]))))
        yaw = math.degrees(math.atan2(R[1, 0], R[0, 0]))
        _SLEEP_FEET[sd] = dict(p=m[:3, 3].copy(), pitch=pitch, roll=roll, yaw=yaw)
        Wr = F['wrist' + sd]
        _SLEEP_HANDS[sd] = dict(p=(Wr @ np.r_[RM.palm_offset(sd), 1.0])[:3], R=Wr[:3, :3].copy())
        H = F['hip' + sd][:3, 3]; K = F['knee' + sd][:3, 3]; Aw = F['ankle' + sd][:3, 3]
        u = (Aw - H) / np.linalg.norm(Aw - H); pk = (K - H) - u * float(np.dot(K - H, u))
        _SLEEP_POLES[sd] = pk / np.linalg.norm(pk)


def city_look(t):
    """where the mech looks when it looks at the city: a point on the rock's underside, a little above the collar."""
    return np.asarray(S.city_pos(t), float) + np.array((0.0, 0.0, 60.0))


# ===================================================================================================================== 52.0 .. 54.6 standing, two steps
def _stand_steps(t, mech):
    P = base_pose()
    r = MP.root_at(t)
    # weight over the stance foot: left before the right step, right before the left step, centred after
    dx = keys_at([(51.8, 0.0), (52.0, 1.6), (52.4, 1.2), (52.55, -1.6), (53.0, -1.0), (53.4, 0.0)], t)
    dip = 1.4 * (pulse(t, 52.4, 0.12, 0.35) + pulse(t, 53.0, 0.12, 0.35))
    crouch = ss(rng(t, 54.1, 54.6))
    P['hips'] = (dx, 0.0, STAND_DZ - dip - 2.6 * crouch)
    P['pelvis'] = (2.0 + 12.0 * crouch, 0.0, keys_at([(52.0, 0.0), (52.2, -3.0), (52.5, 3.0), (52.8, 3.0), (53.1, -2.0), (53.5, 0.0)], t))
    lb = ss(rng(t, 51.8, 52.6)) * (1.0 - ss(rng(t, 53.9, 54.4)))      # leaning back to look up at the city
    P['spine'] = (1.0 + 4.0 * crouch - 3.0 * lb, 0.0, 0.0)
    P['chest'] = (2.0 + 3.0 * crouch - 5.0 * lb, 0.0, keys_at([(52.0, 0.0), (52.3, 4.0), (52.8, -4.0), (53.3, 0.0)], t))
    for sd, sg in (('L', 1.0), ('R', -1.0)):
        sw = sg * keys_at([(52.0, 0.0), (52.3, -8.0), (52.6, 0.0), (52.9, 8.0), (53.3, 0.0)], t)
        P['shoulder' + sd] = (3.0 + sw - 22.0 * crouch, -9.0 - 3.0 * crouch, 2.0); P['elbow' + sd] = (-16.0 - 50.0 * crouch, 0.0, 0.0)
        c = keys_at([(53.5, 0.4), (54.2, 0.95)], t); P['fingers' + sd] = (c, c + 0.03, c)
        P['thumb' + sd] = _RM().safe_thumb((c, c + 0.03, c), keys_at([(53.5, 0.22), (54.2, 0.42)], t))
    _with_root(P, t, r[:3], r[3], hips=P['hips'])
    legs = {}
    for sd in ('L', 'R'):
        q = _plant_now(t, sd)
        into_run = q is not None and q['lift'] is not None and q['lift'] >= MP.RUN_T0 - 1e-6
        legs[sd] = _walk_foot(t, sd, heel=HEEL_UP if into_run else WALK_HEEL)
    look = (city_look(t), 1.0 - ss(rng(t, 54.15, 54.6)), 0.45)
    return {'pose': P, 'legs': legs, 'arms': {'L': None, 'R': None}, 'look': look}


# ===================================================================================================================== 54.6 .. 63.4 the run
# Sprint: footfalls on the score (55.0 + 0.6 k), stance 0.24 s, a flight between. Every leg is IK all the time: the stance foot sits on
# its plant; the swing ankle follows a path designed in the body frame (toe-off -> heel kick -> knee drive -> reach -> touchdown),
# spliced in world space between the two plants with zero velocity at both ends (no foot slide), lifted where the set needs it and
# held inside the leg's band (the knee never past ~95 deg, never locked straight). The foot hangs off the shin (its pitch relative to
# the shin, inside the ankle's range), the knees point forward and a little out. The trunk leans ~20 deg (40 % of it in the pelvis so
# the hips keep their forward range), banks a little into the turns (low-passed yaw rate, small round the lighthouse); the arms pump in
# the sagittal plane with 14 deg of abduction (clear of the thighs). 62.95 .. 63.4: the gather - a crouch on both feet, the drive up.
RUN_CLOCK = [round(55.0 + 0.6 * k, 3) for k in range(14)]
SW_VIA = [(0.28, (12.0, 22.5)), (0.55, (-4.0, 25.4)), (0.8, (-16.0, 27.0))]   # u, (back + / forward -, down) of the ankle from the hip
SW_VIA_WIND = [(0.25, (10.0, 22.5)), (0.5, (2.0, 25.0)), (0.72, (-8.0, 26.0))]   # the crouched run round the drum: a lower knee drive,
                             # the last via earlier (the foot settles onto its plant over the last 28 %, no late brake)
SW_VIA_MAX = 0.94            # a via point is at most this fraction of the stride along it (no reaching past the plant)
SW_IN = 2.0                  # the swing ankle runs this much inside the hip's line (the swing foot passes the stance foot ~4 m clear)
SW_IN_WIND = 0.5             # .. round the drum: the hips lean out to the right there (LEAN), the left swing's sole brushed the planted
                             # right foot's inner edge at its mid-swing (76.75) with 2.0
SW_PITCH = [(0.0, 22.0), (0.15, 20.0), (0.5, 8.0), (0.8, -6.0), (1.0, 0.0)]   # the swing foot's world pitch (+ toes down): near level
SW_ANKLE = (-55.0, 45.0)     # .. held inside the ankle's range off the shin (out/qa/cone_ankleL: about -60 .. +60 free)
WIND_PITCH = [(0.0, 22.0), (0.15, 18.0), (0.35, 6.0), (0.5, 0.0), (0.7, -3.0), (0.85, -4.0), (1.0, 0.0)]   # round the drum: the
                             # foot passes the low hips nearly level (toes neither dig nor scrape), a little toe-up into the footfall
SOFT_K = 6.0                 # deg: the wind swings' ankle-range clamp is a smooth max / min (no kink in the pitch where it bites)
SW_WIND_RMAX = 2.0           # m: round the drum a swing's via points keep within the plants' ring + this (the right foot swept out over
                             # the cap's rim into the crown rail of the breakwater, r 46.9 north-west)


def _soft_max(a, b, k): return 0.5 * (a + b + math.sqrt((a - b) ** 2 + k * k))
def _soft_min(a, b, k): return 0.5 * (a + b - math.sqrt((a - b) ** 2 + k * k))
SW_KEEP = (24.0, 36.0, 3.0)  # the swing ankle keeps this far (m) from the lighthouse's axis while it is below this z (soft over 3 m)
SW_CLEAR = 1.2               # m the whole sole keeps above the set in a swing
SW_SOFT = 1.0                # m: the band is a soft limit (no velocity kink where it bites)
SW_BAND = (D_MIN + 0.6, D_MAX - 0.4)
SW_V_UP, SW_V_DN = 26.0, 14.0   # m/s: the heel leaves the ground going up, the foot comes down onto its plant (no horizontal slide)
SW_A_MAX = 8.0               # m: the most the clearance pass may lift a swing
RUN_POLE_OUT = 0.12          # the knees point forward and this much out
HEEL_T, HEEL_UP = 0.14, 24.0 # the push-off: over the last HEEL_T s of a stance the heel rises to HEEL_UP deg (the toes stay put)
GATHER_K = (62.95, 63.22, MP.TAKEOFF)    # crouch from, deepest, the drive ends at the take-off
ARM_DRIVE = (62.95, 63.2)                # the arms leave the run's swing for the leap's keys (each from its own phase)
_SWING_CACHE = {}
_DZC_VER = [0]


def _speed(t, dt=1.0 / 48):
    a = MP.run_xy_yaw(max(MP.RUN_T0, t - dt))[0]; b = MP.run_xy_yaw(min(MP.TAKEOFF, t + dt))[0]
    return float(np.linalg.norm(np.asarray(b) - np.asarray(a))) / (2 * dt)


def _yaw_rate(t, dt=1.0 / 24):
    a = MP.run_xy_yaw(max(MP.RUN_T0, t - dt))[1]; b = MP.run_xy_yaw(min(MP.TAKEOFF, t + dt))[1]
    return MP.wrap180(b - a) / (2 * dt)


_BANK_W = np.exp(-0.5 * (np.linspace(-0.3, 0.3, 13) / 0.15) ** 2); _BANK_W /= _BANK_W.sum()


def _bank(t):
    """the trunk's bank into the turns (deg, + = toward its left): the low-passed yaw rate, small round the lighthouse."""
    yr = sum(w * _yaw_rate(min(max(t + d, MP.RUN_T0), MP.TAKEOFF)) for w, d in zip(_BANK_W, np.linspace(-0.3, 0.3, 13)))
    p, _ = MP.run_xy_yaw(t); r = float(np.hypot(*(np.asarray(p) - MP.LH)))
    cap = 3.0 + 5.0 * ss((r - 40.0) / 25.0)
    return max(-cap, min(cap, 0.06 * yr))


def _swing_pair(t, sd):
    """(a, b, u) = the plant left, the plant aimed at and the swing phase, or None while planted / outside a swing."""
    pl = MP.plants_of(sd)
    for a, b in zip(pl, pl[1:]):
        if a['lift'] is not None and a['lift'] < t < b['t']: return a, b, (t - a['lift']) / (b['t'] - a['lift'])
    return None


WIND_HEEL = (0.24, 20.0)     # the wind run's push-off (HEEL_T, HEEL_UP): a longer, gentler roll onto the toes through its 0.3 s stance


def _heel_of(a):
    """(push-off time, heel-up deg) of a plant's lift: the wind run's for the lifts inside it (its stances are driven by _wind)."""
    if a.get('lift') is not None and WIND_T0 + 1e-6 < a['lift'] < WIND_T1 + 1e-6: return WIND_HEEL
    return HEEL_T, HEEL_UP


def _heel_k(t, lift, ht=None):
    """0 .. 1 over the push-off: starts with no velocity and no acceleration (3x^3 - 2x^4), still rising at the lift (slope 1 / HEEL_T)
    so the swing carries on from it."""
    ht = HEEL_T if ht is None else ht
    x = rng(t, lift - ht, lift); return x * x * x * (3.0 - 2.0 * x)


def _heel_foot(ft, k, hu=None):
    """the planted foot frame rolled heel-up over its toe line by k * HEEL_UP."""
    hu = HEEL_UP if hu is None else hu
    if k <= 0.0: return ft
    R0 = Rz(ft['yaw']) @ Ry(ft['roll']) @ Rx(ft['pitch']); toe_l = np.array((0.0, -MP.FOOT_FWD, 0.0))
    toe = np.asarray(ft['p'], float) + R0 @ toe_l
    pitch = ft['pitch'] + hu * k
    R1 = Rz(ft['yaw']) @ Ry(ft['roll']) @ Rx(pitch)
    out = dict(ft); out['p'] = toe - R1 @ toe_l; out['pitch'] = pitch
    return out


def _plant_now(t, sd):
    """the plant record a side stands on at t (the last one down), or None."""
    cur = None
    for q in MP.plants_of(sd):
        if q['t'] <= t + 1e-9: cur = q
    return cur


def _heel_start(a, ht=None, hu=None):
    """(foot frame, ankle velocity m/s) of a plant at its lift, after the push-off."""
    ht = HEEL_T if ht is None else ht
    f1 = _heel_foot(a, 1.0, hu); f0 = _heel_foot(a, 0.99, hu)
    v = (ankle_of(f1) - ankle_of(f0)) / 0.01 / ht
    return f1, v


WALK_HEEL = 16.0             # deg of heel-up at a walking step's lift (the run's push-off is HEEL_UP)


def _walk_foot(t, sd, heel=WALK_HEEL):
    """a walking leg's foot frame from the plan (mechplan.foot_at), with the push-off: the stance foot rolls over its toes before the
    lift and the swing starts from that rolled foot (the roll fades out over the first 35 % of the swing)."""
    f = MP.foot_at(t, sd)
    if f is None: return None
    ft = dict(p=np.array(f['p'], float), yaw=f['yaw'], pitch=f['pitch'], roll=f['roll'], planted=f['planted'], w=1.0)
    q = _plant_now(t, sd)
    if q is None: return ft
    if f['planted'] and q['lift'] is None:
        ft['land'] = 1.0 - ss(rng(t, q['t'], q['t'] + 0.1)); return ft
    if q['lift'] is None or heel <= 0.0: return ft
    if f['planted']:
        k = _heel_k(t, q['lift'])
        if k > 0.0: ft = _heel_foot_by(ft, k * heel); ft['heel'] = k
        ft['land'] = 1.0 - ss(rng(t, q['t'], q['t'] + 0.1))      # the pelvis band keeps the knee soft through the footfall
        return ft
    nxt = [b for b in MP.plants_of(sd) if b['t'] > q['t']]
    if not nxt: return ft
    u = (t - q['lift']) / max(nxt[0]['t'] - q['lift'], 1e-6); w = 1.0 - ss(u / 0.35)
    if w <= 0.0: return ft
    g = MP.foot_at(q['lift'] - 1e-6, sd)                    # the foot as it stood at the lift (carried, if it was ploughing)
    g = dict(p=np.array(g['p'], float), yaw=g['yaw'], pitch=g['pitch'], roll=g['roll'])
    gh = _heel_foot_by(g, heel)
    ft['p'] = ft['p'] + (gh['p'] - g['p']) * w; ft['pitch'] = ft['pitch'] + heel * w
    return ft


def _heel_foot_by(ft, deg):
    """the foot frame rolled heel-up over its toe line by deg."""
    if deg <= 0.0: return ft
    R0 = Rz(ft['yaw']) @ Ry(ft['roll']) @ Rx(ft['pitch']); toe_l = np.array((0.0, -MP.FOOT_FWD, 0.0))
    toe = np.asarray(ft['p'], float) + R0 @ toe_l
    pitch = ft['pitch'] + deg
    R1 = Rz(ft['yaw']) @ Ry(ft['roll']) @ Rx(pitch)
    out = dict(ft); out['p'] = toe - R1 @ toe_l; out['pitch'] = pitch
    return out


def _run_pole(t, yaw, sd):
    sx = 1.0 if sd == 'L' else -1.0
    o = RUN_POLE_OUT * ss(rng(t, MP.RUN_T0, 55.2))
    if sd == 'R':
        k = _lean_k(t)
        if k > 0.0: o = o * (1.0 - k) + LEAN['pole_r'] * k      # the wind's lean-out: the right knee further out
    v = Rz(yaw) @ np.array((sx * o, -1.0, 0.0))
    return v / np.linalg.norm(v)


def _run_trunk(t):
    """the run's pose without the legs (set_pose dict, root set): hips, trunk, head, arms."""
    P = base_pose()
    r = MP.root_at(t)
    v = _speed(t); vk = min(1.0, v / MP.RUN_V)
    k_in = ss(rng(t, MP.RUN_T0, 55.6))
    ff = [x for x in RUN_CLOCK if x <= t + 1e-6]; tk = ff[-1] if ff else 55.0
    tau = t - tk if ff else t - 54.4
    bob = -2.7 - 0.7 * math.cos(2 * math.pi * (tau - 0.12) / 0.6)          # low at mid-stance, high in the flight
    g = ss(rng(t, GATHER_K[0], GATHER_K[1])); e = ss(rng(t, GATHER_K[1], GATHER_K[2]))
    dz = lerp(lerp(STAND_DZ - 2.6, bob, k_in), -9.0, g)
    if t > GATHER_K[1]: dz = _drive_dz(t)
    lean = lerp(14.0, 16.0 + 4.0 * vk, k_in) + 8.0 * g
    if e > 0.0: lean = lerp(lean, _leap_val('lean', t), e)
    bk = _bank(t) * k_in * (1.0 - g)
    phL = 2 * math.pi * (t - 55.0) / 1.2                        # 0 at the L footfalls
    tw = -7.0 * math.cos(phL) * k_in * (1.0 - g)              # the pelvis turns the swing hip forward (L hip ahead at the L footfall)
    P['hips'] = (0.0, 0.0, dz)
    P['pelvis'] = (0.4 * lean, 0.3 * bk, tw)
    P['spine'] = (0.3 * lean, 0.35 * bk, -0.6 * tw); P['chest'] = (0.3 * lean, 0.35 * bk, -1.0 * tw)
    P['neck'] = (-0.5 * lean - 3.0, -0.4 * bk, 0.3 * tw); P['head'] = (-0.45 * lean, -0.3 * bk, 0.3 * tw)
    # arms pump against the legs (the L arm back at the L footfall); the gather: both back, then forward with the drive
    ea = ss(rng(t, *ARM_DRIVE))
    A = 34.0 * k_in
    for sd, ph in (('L', phL), ('R', phL + math.pi)):
        sw = A * math.cos(ph)
        rx = -14.0 * k_in + sw
        el = -(30.0 + 50.0 * k_in) - 12.0 * max(0.0, -math.cos(ph)) * k_in
        if ea > 0.0: rx = lerp(rx, _leap_val('arm' + sd, t), ea); el = lerp(el, _leap_val('elb' + sd, t), ea)
        P['shoulder' + sd] = (rx, -14.0, 3.0); P['elbow' + sd] = (el, 0.0, 0.0)
        P['wrist' + sd] = (10.0, -4.0, 0.0); P['fingers' + sd] = (0.95, 0.97, 0.95); P['thumb' + sd] = 0.42
    b = ss(rng(t, MP.RUN_T0, MP.RUN_T0 + 0.45))
    if b < 1.0:
        Ps = _stand_end_pose()
        for j in ('pelvis', 'spine', 'chest', 'neck', 'head', 'shoulderL', 'shoulderR', 'elbowL', 'elbowR', 'wristL', 'wristR',
                  'fingersL', 'fingersR', 'thumbL', 'thumbR'):
            x, y = Ps[j], P[j]
            P[j] = tuple(lerp(p, q, b) for p, q in zip(x, y)) if isinstance(y, tuple) else lerp(x, y, b)
    _with_root(P, t, r[:3], r[3], hips=P['hips'])
    return P


_STAND_END = {}


def _stand_end_pose():
    if 'P' not in _STAND_END: _STAND_END['P'] = _stand_steps(MP.RUN_T0, None)['pose']
    return _STAND_END['P']


def _dzc_at(t):
    f = t * FPS + 1.0; f0 = int(math.floor(f)); u = f - f0
    return (1.0 - u) * _DZC.get(f0, 0.0) + u * _DZC.get(f0 + 1, 0.0)


def _trunk_at(t):
    P = _wind_trunk(t) if t >= WIND_T0 else _run_trunk(t)
    h = P['hips']; P['hips'] = (h[0], h[1], h[2] + _dzc_at(t)); return P


def _run(t, mech):
    P = _run_trunk(t)
    legs = {}
    for sd in ('L', 'R'):
        f = MP.foot_at(t, sd)
        if f is None:
            sp = _swing_pair(t, sd)
            legs[sd] = dict(swing=True, planted=False, w=1.0) if (sp is not None and sp[1]['kind'] == 'land') else None
        elif f['planted'] or _swing_pair(t, sd) is None:
            ft = dict(p=np.array(f['p'], float), yaw=f['yaw'], pitch=f['pitch'], roll=f['roll'], planted=True, w=1.0,
                      pole=_run_pole(t, P['root'][3], sd))
            q = _plant_now(t, sd)
            if q is not None and q['lift'] is not None:
                k = _heel_k(t, q['lift']); ft = _heel_foot(ft, k); ft['heel'] = k
            if q is not None and q['kind'] in ('run', 'gather'): ft['land'] = 1.0 - ss(rng(t, q['t'], q['t'] + 0.08))
            legs[sd] = ft
        else: legs[sd] = dict(swing=True, planted=False, w=1.0)      # filled by _run_swing once the pelvis band is applied
    return {'pose': P, 'legs': legs, 'arms': {'L': None, 'R': None}, 'look': None, 'fill': _run_swing}


def _bump(u): return MP.bump(u)


def _keep_r(*ankles):
    """the swing's keep radius around the lighthouse: SW_KEEP[0], or less when an end of the swing stands nearer (the band must not
    move the swing's own ends: the foot would jump at the lift / the touchdown)."""
    r = min(float(np.linalg.norm(np.asarray(x)[:2] - MP.LH)) for x in ankles)
    return min(SW_KEEP[0], r - SW_KEEP[2] - 0.3)


def _soft_band(d, lo, hi, m):
    if d < lo + m: return lo + m * math.exp((d - lo - m) / m)
    if d > hi - m: return hi - m * math.exp((hi - m - d) / m)
    return d


def _hermite(pl, t):
    ts, ps, m = pl['ts'], pl['ps'], pl['m']
    i = min(max(int(np.searchsorted(ts, t, side='right')) - 1, 0), len(ts) - 2)
    h = ts[i + 1] - ts[i]; s = min(1.0, max(0.0, (t - ts[i]) / h))
    return ((2 * s ** 3 - 3 * s ** 2 + 1) * ps[i] + (s ** 3 - 2 * s ** 2 + s) * h * m[i] + (-2 * s ** 3 + 3 * s ** 2) * ps[i + 1]
            + (s ** 3 - s ** 2) * h * m[i + 1])


def _knee_np(H, A, pole):
    v = A - H; d0 = float(np.linalg.norm(v)); L1, L2 = 18.0, 17.8
    d = min(max(d0, abs(L1 - L2) + 0.5), L1 + L2 - 0.02); u = v / max(d0, 1e-9)
    pp = pole - u * float(np.dot(pole, u)); pp = pp / max(np.linalg.norm(pp), 1e-9)
    ca = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d); sa = math.sqrt(max(0.0, 1 - ca * ca))
    return H + (u * ca + pp * sa) * L1


def _swing_foot(t, sd, a, b, u, P, pl):
    """the swing foot frame at t (dict as the plants) from the swing plan pl and the trunk P."""
    a = pl.get('a', a)                  # the plant as it left the ground (heel up)
    A = _hermite(pl, t) + np.array((0.0, 0.0, pl['A'] * _bump(u)))
    H = hip_world(P['root'], P['hips'], P['pelvis'], sd)
    v = A - H; d = float(np.linalg.norm(v)); A = H + v * (_soft_band(d, SW_BAND[0], SW_BAND[1], SW_SOFT) / max(d, 1e-9))
    rv = A[:2] - MP.LH; r = float(np.linalg.norm(rv)); kp = pl.get('keep', SW_KEEP[0])
    if r < kp + SW_KEEP[2] and A[2] < SW_KEEP[1]:
        A = A.copy(); A[:2] = MP.LH + rv / max(r, 1e-9) * _soft_band(r, kp, 1e9, SW_KEEP[2])
    yaw_r = P['root'][3]; e = ss(u)
    if 'wyaw' in pl: fyaw = pl['wyaw'][0] + pl['wyaw'][1] * e     # round the drum: turned in the world (no turn-rate jump at either end)
    else: fyaw = yaw_r + pl['ya'] + (pl['yb'] - pl['ya']) * e
    froll = lerp(a['roll'], b['roll'], e)
    if sd == 'R' and b['kind'] in ('wind', 'brace') and 0.0 < u < 1.0:
        k = _lean_k(t) * ss(rng(t, pl['ts'][0], pl['ts'][0] + LEAN['sw_in']))
        froll += LEAN['swing_roll_r'] * k * (1.0 - ss(rng(t, pl['ts'][-1] - LEAN['sw_out'], pl['ts'][-1])))
        if a.get('kind') == 'climb': fyaw += LEAN['swing_toe_r'] * k * (1.0 - ss(rng(u, 0.55, 0.95)))
    pole = _run_pole(t, yaw_r, sd)
    K = _knee_np(H, A, pole); sdir = (A - K) / max(np.linalg.norm(A - K), 1e-9); sl = Rz(fyaw).T @ sdir
    p_shin = math.degrees(math.atan2(sl[1], -sl[2]))
    key = keys_at(pl.get('pitch_keys', SW_PITCH), u); lo_a, hi_a = p_shin + SW_ANKLE[0], p_shin + SW_ANKLE[1]
    if pl.get('soft'): pm = _soft_min(_soft_max(key, lo_a, SOFT_K), hi_a, SOFT_K)
    else: pm = min(max(key, lo_a), hi_a)
    tau = max(0.0, t - pl['ts'][0])           # the toes keep turning down for a moment after the lift (the push-off's follow-through)
    ht, hu = pl.get('heel', (HEEL_T, HEEL_UP))
    p0 = a['pitch'] + (hu / ht) * tau * math.exp(-tau / 0.06)
    pitch = lerp(lerp(p0, pm, ss(u / 0.25)), b['pitch'], ss((u - 0.8) / 0.2))
    def frame(pt): return dict(p=A + (Rz(fyaw) @ Ry(froll) @ Rx(pt)) @ SOLE_ANK, yaw=fyaw, pitch=pt, roll=froll)
    def dig(pt):
        X = _sole_points(frame(pt), top=0.0); return float(np.max(MP.ground_hi(X[:, 0], X[:, 1]) - X[:, 2]))
    f = frame(pitch)
    if pl.get('soft'):
        if dig(pitch) > -0.05:       # the sole near the set: the nearest pitch (either way, inside the ankle's range) that clears it
            cand = None
            for k in range(1, 41):
                for sg in (1.0, -1.0):
                    pt = pitch + sg * k
                    if lo_a <= pt <= hi_a and dig(pt) <= -0.05: cand = pt; break
                if cand is not None: break
            if cand is None:
                grid = [x for x in np.arange(pitch - 40.0, pitch + 40.5, 1.0) if lo_a <= x <= hi_a] or [pitch]
                f = frame(min(grid, key=dig))
            else:
                bad, good = cand - math.copysign(1.0, cand - pitch), cand
                for _ in range(10):
                    mid = 0.5 * (bad + good)
                    if dig(mid) > -0.05: bad = mid
                    else: good = mid
                f = frame(good)
    elif dig(pitch) > -0.05:         # the sole near the set: the least turn toward the plant's pitch that clears it (continuous)
        base = lerp(a['pitch'], b['pitch'], ss((u - 0.3) / 0.4))
        if dig(base) > -0.05: f = frame(base)
        else:
            lo, hi = 0.0, 1.0
            for _ in range(12):
                mid = 0.5 * (lo + hi)
                if dig(lerp(pitch, base, mid)) > -0.05: lo = mid
                else: hi = mid
            f = frame(lerp(pitch, base, hi))
    f.update(planted=False, w=1.0, pole=pole, ankle=A, d=d)
    return f


def _sole_points(ft, top=3.0):
    """world points of the sole rectangle (and its top edge) of a foot frame."""
    Rf = Rz(ft['yaw']) @ Ry(ft['roll']) @ Rx(ft['pitch'])
    U = np.linspace(-MP.FOOT_FWD, MP.FOOT_BACK, 7); V = np.linspace(-MP.FOOT_HW, MP.FOOT_HW, 4)
    pts = [(v, u, z) for u in U for v in V for z in (0.0, top)]
    return np.asarray(ft['p'], float) + np.array(pts) @ Rf.T


def _swing_plan(sd, a, b):
    key = (sd, round(a['t'], 3), _DZC_VER[0])
    if key in _SWING_CACHE: return _SWING_CACHE[key]
    tl, td = a['lift'], b['t']; T = td - tl
    hp = _heel_of(a); a_h, v0 = _heel_start(a, *hp)
    A0 = ankle_of(a_h); A1 = ankle_of(b)
    Lw = float(np.linalg.norm(A1[:2] - A0[:2])); amp = min(1.0, max(0.0, (Lw - 15.0) / 45.0))
    sx = 1.0 if sd == 'L' else -1.0
    ts = [tl]; ps = [A0]
    for u, (back, down) in (SW_VIA_WIND if b['kind'] in ('wind', 'brace') else SW_VIA):
        tau = tl + u * T; Pt = _trunk_at(tau)
        H = hip_world(Pt['root'], Pt['hips'], Pt['pelvis'], sd)
        swin = (SW_IN_WIND if b['kind'] in ('wind', 'brace') else SW_IN) + (MP.RUN_HALF - MP.run_half(Pt['root'][:2]))
        # (on the narrow cap the swing runs closer in, as the plants do)
        sprint = H + Rz(Pt['root'][3]) @ np.array((-sx * swin, back, -down))
        walk = A0 + (A1 - A0) * ss(u) + np.array((0.0, 0.0, 6.0 * math.sin(math.pi * u)))
        ts.append(tau); ps.append(walk + (sprint - walk) * amp)
    ts.append(td); ps.append(A1)
    dxy = A1[:2] - A0[:2]; L = float(np.linalg.norm(dxy))
    if L > 1e-3:
        n = dxy / L
        for i in range(1, len(ps) - 1):
            over = float(np.dot(ps[i][:2] - A0[:2], n)) - SW_VIA_MAX * L
            if over > 0.0: ps[i] = ps[i] - np.array((n[0], n[1], 0.0)) * over
    if b['kind'] in ('wind', 'brace'):
        rlim = max(float(np.hypot(*(A0[:2] - MP.LH))), float(np.hypot(*(A1[:2] - MP.LH)))) + SW_WIND_RMAX
        for i in range(1, len(ps) - 1):
            rv = ps[i][:2] - MP.LH; r = float(np.linalg.norm(rv))
            if r > rlim: ps[i] = np.array((MP.LH[0] + rv[0] * rlim / r, MP.LH[1] + rv[1] * rlim / r, ps[i][2]))
    ts = np.array(ts); ps = np.array(ps); m = np.zeros_like(ps)
    for i in range(1, len(ts) - 1): m[i] = (ps[i + 1] - ps[i - 1]) / (ts[i + 1] - ts[i - 1])
    m[0] = v0; m[-1] = (0.0, 0.0, -(SW_V_DN * amp + 6.0 * (1 - amp)))
    ya = MP.wrap180(a['yaw'] - MP.root_at(tl)[3]); yb = MP.wrap180(b['yaw'] - MP.root_at(td)[3])
    pl = dict(ts=ts, ps=ps, m=m, A=0.0, ya=ya, yb=yb, amp=amp, deficit=0.0, a=a_h, keep=_keep_r(A0, A1), heel=hp)
    if b['kind'] in ('wind', 'brace'):
        pl.update(wyaw=(a_h['yaw'], MP.wrap180(MP.root_at(td)[3] - MP.root_at(tl)[3]) + yb - ya), pitch_keys=WIND_PITCH, soft=True)
    for it in range(7):              # lift the path (a bump that keeps both ends) until the whole sole clears the set
        need = 0.0; worst = 0.0
        for k in range(2, 31):
            u = k / 32.0; tt = tl + u * T
            f = _swing_foot(tt, sd, a, b, u, _trunk_at(tt), pl)
            X = _sole_points(f); g = MP.ground_hi(X[:, 0], X[:, 1])
            req = SW_CLEAR * ss(rng(u, 0.12, 0.3)) * ss(rng(1.0 - u, 0.12, 0.3))    # the ends: the foot's own pitch clamp (no dig-in)
            dfc = float(np.max(g + req - X[:, 2]))
            if dfc > 0: need = max(need, dfc / max(_bump(u), 0.3)); worst = max(worst, dfc)
        pl['deficit'] = worst
        if need <= 1e-4 or pl['A'] >= SW_A_MAX: break
        pl['A'] = min(SW_A_MAX, pl['A'] + need + 0.2)
    _SWING_CACHE[key] = pl
    return pl


def _run_swing(t, D):
    P = D['pose']
    for sd in ('L', 'R'):
        ft = D['legs'].get(sd)
        if ft is None or not ft.get('swing'): continue
        sp = _swing_pair(t, sd)
        if sp is None: D['legs'][sd] = None; continue
        a, b, u = sp
        D['legs'][sd] = _swing_foot(t, sd, a, b, u, P, _leap_plan(sd) if b['kind'] == 'land' else _swing_plan(sd, a, b))


def _hold_placeholder(t, mech):
    raise NotImplementedError('phase after %.2f not designed yet' % t)


# ===================================================================================================================== 63.22 .. 65.4 the leap
# The drive (63.22 .. 63.4) accelerates the hips into the launch speed (MP.FLIGHT_VZ0) and swings the arms through the take-off with
# no stop (they carry on up and settle in the air). In the air the legs fold under (the tuck), the left arm leads and the right swings
# back, then the left leg reaches forward and the right back for the landing plants. The soles meet the sea at MP.T_WATER, the water
# brakes the fall, the feet reach the seabed at 65.4 (the cut to s32) and the legs take the rest (the landing crouch). The legs are IK
# all the way: ankle paths spliced in world space from the push-off through body-frame via points to the land plants, inside the band.
DZ_DRIVE = 0.18 * 0.5        # the drive's rise = launch speed * its time / 2 (speed eased in: smoothstep, no jolt at either end)
DZ_TO = -9.0 + MP.FLIGHT_VZ0 * DZ_DRIVE   # hips dz at the take-off (the flight keeps it, then the keys)
LEAP = {
    'lean': [(63.22, 25.0), (63.31, 18.0), (63.4, 10.0), (63.52, 7.0), (63.7, 10.0), (64.0, 17.0), (64.35, 18.0), (64.7, 12.0),
             (65.0, 7.0), (65.25, 5.0), (65.4, 6.0)],
    'dz':   [(63.4, DZ_TO), (63.5, DZ_TO), (63.75, -4.0), (64.0, -4.5), (64.7, -4.5), (65.0, -5.0), (65.25, -5.5), (65.4, -6.0)],
    # the left arm swings back with the run (to ~63.12), then drives up with the right knee; the right arm is already coming forward
    'armL': [(62.95, -38.0), (63.05, -23.0), (63.12, -13.0), (63.2, -15.0), (63.3, -40.0), (63.4, -72.0), (63.52, -94.0),
             (63.65, -102.0), (63.8, -97.0), (64.0, -82.0), (64.35, -66.0), (64.7, -54.0), (65.0, -44.0), (65.25, -38.0), (65.4, -36.0)],
    'elbL': [(62.95, -80.0), (63.12, -82.0), (63.25, -70.0), (63.4, -48.0), (63.52, -34.0), (63.7, -32.0), (64.0, -40.0),
             (64.35, -38.0), (64.7, -34.0), (65.0, -30.0), (65.4, -32.0)],
    'armR': [(62.95, 10.0), (63.05, -6.0), (63.15, -24.0), (63.25, -42.0), (63.4, -70.0), (63.52, -88.0), (63.65, -93.0),
             (63.8, -80.0), (64.0, -42.0), (64.35, 4.0), (64.7, 16.0), (65.0, 6.0), (65.25, -8.0), (65.4, -14.0)],
    'elbR': [(62.95, -80.0), (63.15, -76.0), (63.3, -60.0), (63.4, -48.0), (63.52, -38.0), (63.7, -38.0), (64.0, -52.0),
             (64.35, -50.0), (64.7, -44.0), (65.0, -38.0), (65.4, -36.0)],
    'fist': [(63.15, 0.95), (63.4, 0.95), (63.52, 0.9), (63.7, 0.8), (64.0, 0.62), (64.35, 0.5), (64.7, 0.45), (65.0, 0.4),
             (65.4, 0.36)],
}
FL_VIA = {  # the ankle from its hip in the root's yaw frame: (in toward the mid-plane, back + / forward -, down), at these times.
    # a hitch-kick: the right leg (off first) drives its knee forward then goes back for the landing, the left trails, then reaches
    'L': [(63.6, (1.0, 10.0, 31.0)), (63.95, (1.5, 0.0, 27.0)), (64.3, (1.5, -8.0, 25.0)), (64.65, (1.0, -10.0, 26.0)),
          (64.95, (0.5, -12.0, 30.0))],
    'R': [(63.55, (1.5, -6.0, 24.8)), (63.85, (1.5, -8.0, 25.0)), (64.25, (1.5, -3.0, 25.5)), (64.65, (1.0, 5.0, 27.0)),
          (65.0, (0.5, 10.0, 27.5))],
}
FL_PITCH = [(0.0, 30.0), (0.2, 26.0), (0.55, 14.0), (0.85, 4.0), (1.0, 0.0)]     # the foot's world pitch (+ toes down) in the air


def _leap_val(name, t):
    return keys_at(LEAP[name], t)


def _drive_dz(t):
    """the drive's hips dz (63.22 .. 63.4): from the crouch at rest, the rising speed eased up (smoothstep) to the launch speed."""
    T = GATHER_K[2] - GATHER_K[1]; x = rng(t, GATHER_K[1], GATHER_K[2])
    return -9.0 + MP.FLIGHT_VZ0 * T * (x ** 3 - 0.5 * x ** 4)


def _leap_trunk(t):
    """the leap's pose without the legs (63.4 .. 65.4), root on the flight path."""
    P = base_pose(); r = MP.root_at(t)
    lean = _leap_val('lean', t)
    dz = DZ_TO + (_leap_val('dz', t) - DZ_TO) * ss(rng(t, MP.TAKEOFF, MP.TAKEOFF + 0.25))
    P['hips'] = (0.0, 0.0, dz)
    P['pelvis'] = (0.4 * lean, 0.0, 0.0); P['spine'] = (0.3 * lean, 0.0, 0.0); P['chest'] = (0.3 * lean, 0.0, 0.0)
    P['neck'] = (-0.5 * lean - 3.0, 0.0, 0.0); P['head'] = (-0.45 * lean, 0.0, 0.0)
    c = _leap_val('fist', t)
    for sd in ('L', 'R'):
        P['shoulder' + sd] = (_leap_val('arm' + sd, t), -14.0, 3.0); P['elbow' + sd] = (_leap_val('elb' + sd, t), 0.0, 0.0)
        P['wrist' + sd] = (10.0, -4.0, 0.0); P['fingers' + sd] = (c, c + 0.02, c)
        P['thumb' + sd] = _RM().safe_thumb((c, c + 0.02, c), 0.42 if c > 0.88 else 0.3)
    _with_root(P, t, r[:3], r[3], hips=P['hips'])
    return P


def _takeoff_plant(sd):
    pl = MP.plants_of(sd); i = [k for k, q in enumerate(pl) if q['kind'] == 'land'][0]
    return pl[i - 1]


def _land_plant(sd):
    return [q for q in MP.plants_of(sd) if q['kind'] == 'land'][0]


def _leap_plan(sd):
    key = ('leap', sd, _DZC_VER[0])
    if key in _SWING_CACHE: return _SWING_CACHE[key]
    a = _takeoff_plant(sd); b = _land_plant(sd); tl, td = a['lift'], MP.LAND_T
    a_h, v0 = _heel_start(a)
    sx = 1.0 if sd == 'L' else -1.0
    ts = [tl]; ps = [ankle_of(a_h)]
    for tau, (inn, back, down) in FL_VIA[sd]:
        Pt = _leap_trunk(tau); H = hip_world(Pt['root'], Pt['hips'], Pt['pelvis'], sd)
        ts.append(tau); ps.append(H + Rz(Pt['root'][3]) @ np.array((-sx * inn, back, -down)))
    ts.append(td); ps.append(ankle_of(b))
    ts = np.array(ts); ps = np.array(ps); m = np.zeros_like(ps)
    for i in range(1, len(ts) - 1): m[i] = (ps[i + 1] - ps[i - 1]) / (ts[i + 1] - ts[i - 1])
    r1 = MP.root_at(td - 0.02); r0 = MP.root_at(td - 0.04)
    m[0] = v0; m[-1] = np.array(((r1[0] - r0[0]) / 0.02, (r1[1] - r0[1]) / 0.02, MP.FLIGHT_V_END))
    ya = MP.wrap180(a['yaw'] - MP.root_at(tl)[3]); yb = MP.wrap180(b['yaw'] - MP.root_at(td)[3])
    pl = dict(ts=ts, ps=ps, m=m, A=0.0, ya=ya, yb=yb, amp=1.0, deficit=0.0, a=a_h, pitch_keys=FL_PITCH, keep=_keep_r(ps[0], ps[-1]))
    _SWING_CACHE[key] = pl
    return pl


def _flight(t, mech):
    P = _leap_trunk(t)
    legs = {sd: dict(swing=True, planted=False, w=1.0) for sd in ('L', 'R')}
    look = (_chain_end_look(t), 0.6 * ss(rng(t, 63.7, 64.3)), 0.45)
    return {'pose': P, 'legs': legs, 'arms': {'L': None, 'R': None}, 'look': look, 'fill': _flight_legs}


def _flight_legs(t, D):
    P = D['pose']
    for sd in ('L', 'R'):
        a = _takeoff_plant(sd); u = (t - a['lift']) / (MP.LAND_T - a['lift'])
        D['legs'][sd] = _swing_foot(t, sd, a, _land_plant(sd), u, P, _leap_plan(sd))


def _chain_end_look(t):
    """where the mech looks while it goes for the chain: its free end (smoothed: the skips don't shake the head)."""
    ts = np.linspace(-0.25, 0.25, 11); w = np.exp(-0.5 * (ts / 0.12) ** 2); w /= w.sum()
    acc = np.zeros(3)
    for dt, wk in zip(ts, w):
        tt = min(max(t + dt, 30.0), S.T['grab']); e = S.end_guide(tt)
        acc += wk * np.asarray(e if e is not None else S.palm_path(S.T['grab']), float)
    return acc


# ===================================================================================================================== 65.4 .. 69.3 the landing, the wade
# The feet hit the seabed at 65.4 with the body still falling at MP.FLIGHT_V_END: the hips carry that speed into a crouch (a damped
# dip), the trunk pitches forward and comes back. It wades toward the skipping end of the chain (4 steps, the pelvis turning with each),
# the arms swinging against the legs; from 67.2 the left arm goes for the end; the last step is a lunge (68.0 .. 68.55) and the trunk
# reaches down over the front knee: the palm closes on the end at 69.3.
DZ_LAND = LEAP['dz'][-1][1]
LAND_DIP = 5.0               # m the hips sink below their landing height in the dip
WADE_DZ = [(65.4, DZ_LAND), (65.9, -4.5), (66.3, -3.5), (67.6, -3.5), (68.1, -5.0), (68.6, -8.0), (69.1, -10.0), (69.3, -10.0)]
WADE_LEAN = [(65.4, 6.0), (65.62, 22.0), (65.9, 18.0), (66.3, 14.0), (67.2, 15.0), (67.8, 17.0), (68.3, 22.0), (68.8, 25.0),
             (69.3, 25.0)]
HOLD_IN = (68.5, 69.2)       # the wade's trunk gives way to the hold's keyed channels (the reach for the grab)
WADE_TW = [(65.4, -4.0), (65.95, -2.0), (66.45, 5.0), (67.1, -5.0), (67.85, 5.0), (68.55, -8.0), (69.3, -6.0)]
WADE_ARM = {  # (shoulder rx, elbow rx); + rx = the arm back
    'L': [(65.4, (-36.0, -32.0)), (65.62, (-48.0, -36.0)), (65.95, (-22.0, -36.0)), (66.45, (-34.0, -38.0)), (67.0, (-42.0, -36.0)),
          (67.2, (-46.0, -34.0))],
    'R': [(65.4, (-14.0, -36.0)), (65.62, (-34.0, -40.0)), (65.95, (-6.0, -38.0)), (66.45, (16.0, -40.0)), (67.1, (-22.0, -38.0)),
          (67.85, (14.0, -40.0)), (68.55, (24.0, -42.0))],
}


def _land_dz(t):
    tau = t - MP.LAND_T; v0 = -MP.FLIGHT_V_END; tc = LAND_DIP * math.e / max(v0, 1e-3)
    return keys_at(WADE_DZ, t) - v0 * tau * math.exp(-tau / tc)


LOOK_BACK_MAX = 27.0         # the FK neck + head back-tilt stays under the rig's limit (rigmath.LIM look_back 30)
CHANNELS = ('pz', 'lean', 'bend', 'ptw', 'stw', 'ctw')


def _neck_head(lean, bd=0.0, tw=0.0):
    """FK neck / head against the trunk's lean (the head kept near level), the back-tilt capped at LOOK_BACK_MAX."""
    n, h = -0.5 * lean - 3.0, -0.45 * lean
    back = -(n + h)
    if back > LOOK_BACK_MAX: k = LOOK_BACK_MAX / back; n *= k; h *= k
    return (n, -0.3 * bd, 0.3 * tw), (h, -0.2 * bd, 0.3 * tw)


def _wade_channels(t):
    lean = keys_at(WADE_LEAN, t); tw = keys_at(WADE_TW, t)
    return dict(pz=float(MP.root_at(t)[2]) + PELVIS_Z + _land_dz(t), lean=lean, bend=0.0, ptw=tw, stw=-0.6 * tw, ctw=-1.0 * tw)


def _trunk_from(P, ch, r):
    """set the hips / pelvis / spine / chest / neck / head of P from trunk channels (pz = the pelvis pivot's WORLD z)."""
    lean, bd = ch['lean'], ch['bend']; ps = ch.get('psh', 0.4); qs = 0.5 * (1.0 - ps)    # the pelvis's share of the lean
    P['hips'] = (0.0, 0.0, ch['pz'] - float(r[2]) - PELVIS_Z)
    P['pelvis'] = (ps * lean, 0.4 * bd, ch['ptw']); P['spine'] = (qs * lean, 0.3 * bd, ch['stw'])
    P['chest'] = (qs * lean, 0.3 * bd, ch['ctw'])
    P['neck'], P['head'] = _neck_head(lean, bd, ch['ptw'])


def _wade_trunk(t):
    P = base_pose(); r = MP.root_at(t)
    ch = _wade_channels(t); k = ss(rng(t, *HOLD_IN))
    if k > 0.0:
        hc = _hold_channels(t); ch = {c: lerp(ch[c], hc[c], k) for c in CHANNELS}
    _trunk_from(P, ch, r); _grab_hips(P, t)
    for sd in ('L', 'R'):
        if sd == 'L': v = keys_at(WADE_ARM['L'], t); v = (v[0], -14.0, v[1])
        else: v = keys_at(R_ARM, t)
        P['shoulder' + sd] = (v[0], v[1], 3.0); P['elbow' + sd] = (v[2], 0.0, 0.0); P['wrist' + sd] = (10.0, -4.0, 0.0)
        if sd == 'L':       # spread for the grab (67.4 .. 68.2), closing on the bar 69.1 .. 69.3
            c = keys_at([(65.4, 0.36), (65.9, 0.5), (67.0, 0.5), (67.4, 0.2), (68.2, FING_OPEN)], t); k = ss(rng(t, *GRIP_CLOSE))
            fg = tuple(lerp(c + (0.02 if i == 1 else 0.0), g, k) for i, g in enumerate(GR.GRIP_FINGERS))
            P['fingersL'] = fg       # the thumb swings back off the bar while the hand comes down (done before the close)
            P['thumbL'] = _RM().safe_thumb(fg, lerp(0.25, GR.GRIP_THUMB, ss(rng(t, 68.4, 69.05))))
            continue
        c = 0.55
        P['fingers' + sd] = (c, c + 0.02, c); P['thumb' + sd] = _RM().safe_thumb((c, c + 0.02, c), 0.25)
    _with_root(P, t, r[:3], r[3], hips=P['hips'])
    return P


def _wade(t, mech):
    P = _wade_trunk(t)
    legs = {sd: _walk_foot(t, sd) for sd in ('L', 'R')}
    look = (_chain_end_look(t), 0.75, 0.45)     # (continued by _hold_look past the grab)
    return {'pose': P, 'legs': legs, 'arms': {'L': None, 'R': None}, 'look': look, 'fill': _left_fill}


# ===================================================================================================================== 67.2 .. 90 the left hand
# From 67.2 the left arm goes for the skipping end (IK to a smoothed aim that lags the end and hovers over it, clamped to the arm's
# reach: the end skips away from it twice); at 69.3 the fist closes on the end link (grip.py: round a side bar of the studless end
# link) and from then the palm IS the end link's grip frame: X along the link (GRIP_SGN), its roll about the link (phi) the one that
# keeps the wrist straightest for the forearm. The elbow's swivel about the shoulder-wrist line (psi) is chosen per frame along a
# smooth path (dynamic programming, then a light gaussian) by build_grip, which also writes the chain's twist that turns the end
# link into the hand: out/track/grip.npz (f, psi, sgn, twist, w, phi).
import grip as GR

GRIP_T = MP.GRAB_T
GRIP_END = 90.0                      # the grip is designed to the film's end
WIND_T1 = 78.2                       # the wind ends (the brace)
REACH_W = (67.2, 67.75)              # the left arm's IK weight ramps in
REACH_LAG = (0.28, 68.75, 69.25)     # the aim trails the end by this (s), gone over this window
REACH_HOVER = (3.5, 68.95, GRIP_T)   # m above the end, gone over this window (the hand comes down onto the bar)
REACH_EXACT = (68.95, 69.25)         # the smoothed aim gives way to the end link itself
REACH_MAX = 0.985                    # of the arm's length: an aim beyond it is pulled in along the shoulder line (no locked elbow)
REACH_SNAP = (70.45, 70.85, 72.85, 73.25, 0.991)   # the snap and the drag (s34, s35): the taut chain pulls the arm out straighter
                                     # (elbow ~17 deg instead of ~20). With the end cut (story.END_CUT) the bar ran 5-11 cm past the
                                     # 0.985 reach at 71.1-71.75 / 72.2-72.75 and the fist's middle finger cut into it (QA s34, 06.11);
                                     # outside those frames the arm is not at its limit, so nothing else moves (side script short_scan)
GRIP_CLOSE = (69.1, GRIP_T)          # the fingers close on the bar
FING_OPEN = 0.1
TWIST_IN = (68.6, 69.2)              # the chain's twist into the hand's frame ramps in
PSI_GRID = np.arange(-40.0, 122.5, 2.5)
AIM_AZ = -84.0                       # while the target is out of reach the arm's aim (chest frame, -90 = straight ahead) is held at
AIM_K = 2.0                          # or inside this azimuth, the bias coming in over the first AIM_K m out of reach (past ~-80 the
                                     # upper arm / pauldron meet the chest at every swivel: out/qa/armsweep_d0.log)
PSI_PREF = 20.0                      # the elbow's preferred swivel (deg, 0 = down, + = out)
PSI_DP, PSI_SM = 6.0, 2.0            # the swivel path: cost per deg^2 of change per frame; final gaussian sigma (frames)
ARM_MAP = os.path.join(ROOT, 'out', 'qa', 'armsweep_wind.npz')   # the exact (BVH) left-arm contacts, frames x PSI_GRID, where
ARM_MAP_K = 2500.0                   # sampled (shots/armsweep.py -- 1806 1840 1 wind PSI=-40:120:2.5): the cone maps are 12 / 30 deg
                                     # guides and missed the upper arm on the chest's left flank at the run's start (75.7 .. 76.0). A
                                     # swivel within one grid step of a contact costs as a wrist hit (the path is smoothed after the DP).
                                     # Rebuild the map whenever the trunk or the legs change in its window.
GRIP_SGN = 1.0                       # the bar's sense in the left fist (+: the palm's X along T, the chain leaves on the thumb side)
_CONE = {}


def _end_now(t):
    return GR.end_link(t * FPS + 1.0)


_EAIM_K = np.exp(-0.5 * (np.linspace(-0.2, 0.2, 9) / 0.09) ** 2); _EAIM_K /= _EAIM_K.sum()


def _grip_aim(t):
    """(link centre, axis T) the hand is put on: before the grab a smoothed end that lags and hovers, the end link from 69.25."""
    C1, T1, _ = _end_now(t)
    if t >= REACH_EXACT[1]: return C1, T1
    lag = REACH_LAG[0] * (1.0 - ss(rng(t, REACH_LAG[1], REACH_LAG[2])))
    Cs = np.zeros(3); Ts = np.zeros(3)
    for dt, k in zip(np.linspace(-0.2, 0.2, 9), _EAIM_K):
        c, tt, _ = _end_now(min(t - lag + dt, GRIP_T)); Cs += k * c; Ts += k * tt
    Ts /= np.linalg.norm(Ts)
    e = ss(rng(t, *REACH_EXACT))
    C = Cs * (1.0 - e) + C1 * e; Tn = Ts * (1.0 - e) + T1 * e; Tn /= np.linalg.norm(Tn)
    C = C + np.array((0.0, 0.0, REACH_HOVER[0] * (1.0 - ss(rng(t, REACH_HOVER[1], REACH_HOVER[2])))))
    return C, Tn


def _pole_of(Rc, S_, Wt, psi):
    """the elbow's pole for a swivel psi (deg) about the shoulder-wrist line: 0 = down-and-back (the chest's -Z+Y across the line:
    down for a reach ahead, back for a hanging arm), + = out (the chest's +X). The reference was the chest's -Z alone, which runs
    along the line when the arm hangs (the wind / the rest): the elbow's plane then spun with every degree of the aim."""
    u = Wt - S_; u = u / max(np.linalg.norm(u), 1e-9)
    dn = (Rc[:, 1] - Rc[:, 2]) * math.sqrt(0.5); r0 = dn - u * float(np.dot(dn, u))
    if np.linalg.norm(r0) < 1e-6: r0 = Rc[:, 1] - u * float(np.dot(Rc[:, 1], u))
    r0 = r0 / np.linalg.norm(r0)
    ou = Rc[:, 0]; r1 = ou - u * float(np.dot(ou, u)) - r0 * float(np.dot(ou, r0)); r1 = r1 / max(np.linalg.norm(r1), 1e-9)
    a = math.radians(psi)
    return r0 * math.cos(a) + r1 * math.sin(a)


def _upper_frames(S_, E, Wt, pole, bend):
    """(Ru, Rfa): the upper arm's and the forearm's world 3x3 exactly as mech.arm_ik builds them."""
    Zu = S_ - E; Zu = Zu / np.linalg.norm(Zu)
    u = Wt - S_; u = u / max(np.linalg.norm(u), 1e-9); pp = pole - u * float(np.dot(pole, u)); pp = pp / max(np.linalg.norm(pp), 1e-9)
    Yu = pp - Zu * float(np.dot(pp, Zu)); Yu = Yu / max(np.linalg.norm(Yu), 1e-9); Xu = np.cross(Yu, Zu)
    Ru = np.column_stack((Xu, Yu, Zu))
    return Ru, Ru @ Rx(-bend)


def _swing_twist(q):
    """(swing deg of the hand's axis off the forearm's, twist deg about the forearm) of a wrist local rotation."""
    z = q[:, 2]; c = max(-1.0, min(1.0, float(z[2]))); sw = math.degrees(math.acos(c))
    ax = np.cross(np.array((0.0, 0.0, 1.0)), z); n = float(np.linalg.norm(ax))
    if n < 1e-9: Rs = np.eye(3)
    else:
        ax = ax / n; a = math.acos(c); K = np.array(((0, -ax[2], ax[1]), (ax[2], 0, -ax[0]), (-ax[1], ax[0], 0)))
        Rs = np.eye(3) + math.sin(a) * K + (1.0 - math.cos(a)) * (K @ K)
    r = Rs.T @ q
    return sw, math.degrees(math.atan2(r[1, 0], r[0, 0]))


def _min_rot(a, b):
    """the minimal rotation (3x3) taking unit a to unit b (the half turn about X for antipodes, as conemap.base_rot)."""
    a = np.asarray(a, float); b = np.asarray(b, float); c = float(np.dot(a, b))
    if c < -0.9999: return Rx(180.0)
    v = np.cross(a, b); K = np.array(((0, -v[2], v[1]), (v[2], 0, -v[0]), (-v[1], v[0], 0)))
    return np.eye(3) + K + (K @ K) / (1.0 + c)


SH_K = 20.0                          # cost per unit of the shoulder map's contact (out/qa/cone_shoulderL.npz, interpolated)


def _shoulder_hits(q):
    """self contact of a left shoulder local rotation (chest -> upper arm) in out/qa/cone_shoulderL.npz: the 3 nearest sampled
    directions (inverse-angle weights), linear in the twist. A guide (12 deg / 30 deg samples); mechpose's BVH test is the judge."""
    if 's' not in _CONE:
        z = np.load(os.path.join(ROOT, 'out', 'qa', 'cone_shoulderL.npz')); _CONE['s'] = (z['dirs'], z['twist'], z['hits'].astype(float))
    D, TW, H = _CONE['s']
    d = q @ np.array((0.0, 0.0, -1.0)); R0 = _min_rot((0.0, 0.0, -1.0), d)
    x = R0 @ np.array((1.0, 0.0, 0.0)); y = (q @ R0.T) @ x
    tw = math.atan2(float(np.dot(np.cross(x, y), d)), float(np.dot(x, y)))
    cs = D @ d; near = np.argsort(-cs)[:3]; ang = np.degrees(np.arccos(np.clip(cs[near], -1.0, 1.0)))
    w = 1.0 / (ang + 1.0); w /= w.sum()
    tg = np.concatenate((TW, [TW[0] + 2.0 * math.pi])); twu = tw if tw >= tg[0] else tw + 2.0 * math.pi
    j = max(0, min(int(np.searchsorted(tg, twu) - 1), len(tg) - 2)); u = (twu - tg[j]) / (tg[j + 1] - tg[j])
    k0 = j % len(TW); k1 = (j + 1) % len(TW)
    return float(np.sum(w * (H[near, k0] * (1.0 - u) + H[near, k1] * u)))


def _wrist_hits(q):
    """self-contact count of a left wrist local rotation in out/qa/cone_wristL.npz (the 3 nearest sampled directions, the nearest
    twist; the map is sampled every 12 deg / 30 deg, so this is a guide: mechpose's BVH test is the judge)."""
    if 'w' not in _CONE:
        z = np.load(os.path.join(ROOT, 'out', 'qa', 'cone_wristL.npz')); _CONE['w'] = (z['dirs'], z['twist'], z['hits'])
    D, TW, H = _CONE['w']
    d = q @ np.array((0.0, 0.0, -1.0)); R0 = _min_rot((0.0, 0.0, -1.0), d)
    x = R0 @ np.array((1.0, 0.0, 0.0)); y = (q @ R0.T) @ x
    tw = math.atan2(float(np.dot(np.cross(x, y), d)), float(np.dot(x, y)))
    k = int(np.argmin(np.abs((TW - tw + math.pi) % (2 * math.pi) - math.pi)))
    near = np.argsort(-(D @ d))[:3]
    return int(H[near, k].sum())


def _arm_try(P, C, T, psi, sgn, F=None, t=None):
    """the left arm on the link (centre C, axis T) with the elbow swivel psi: dict(Pp palm target, Rw wrist world, Rp palm, pole,
    bend, d shoulder-wrist, swing, twist, hits, cost, phi, E, S, short = m the palm misses the link by)."""
    RMm = _RM(); F = F or RMm.frames(P)
    S_ = F['shoulderL'][:3, 3]; Rc = F['chest'][:3, :3]; off = RMm.palm_offset('L'); Lmax = (RMm.ARM_L1 + RMm.ARM_L2) * reach_max(t)
    fa = np.asarray(C, float) - S_; short = 0.0
    for it in range(3):
        phi = GR.phi_for(T, fa, sgn); Rp = GR.palm_frame(T, phi, sgn); Rw = GR.wrist_rot(Rp, 'L')
        Pp = GR.palm_pos(C, Rp); Wt = Pp - Rw @ off
        v = Wt - S_; dv = float(np.linalg.norm(v)); short = max(0.0, dv - Lmax)
        if dv > Lmax:
            vc = Rc.T @ v; az = math.degrees(math.atan2(vc[1], vc[0])); kb = ss(min(1.0, short / AIM_K))
            if az > AIM_AZ and kb > 0.0: v = Rc @ (Rz(-(az - AIM_AZ) * kb) @ vc)     # reach toward it inside the free cone
            Wt = S_ + v * (Lmax / dv); Pp = Wt + Rw @ off
        pole = _pole_of(Rc, S_, Wt, psi)
        E, bend, d = RMm.two_bone(S_, Wt, RMm.ARM_L1, RMm.ARM_L2, pole)
        fa = Wt - E
    Ru, Rfa = _upper_frames(S_, E, Wt, pole, bend)
    q = Rfa.T @ Rw; sw, tw = _swing_twist(q); hits = _wrist_hits(q); sh = _shoulder_hits(Rc.T @ Ru)
    cost = (sw * sw + (0.4 * tw) ** 2 + (0.35 * (psi - PSI_PREF)) ** 2 + 60.0 * max(0.0, bend - 90.0) ** 2
            + (2500.0 if hits else 0.0) + 30.0 * max(0.0, sw - 42.0) ** 2 + SH_K * sh)
    return dict(Pp=Pp, Rw=Rw, Rp=Rp, pole=pole, bend=bend, d=d, swing=sw, twist=tw, hits=hits, cost=cost, phi=phi, E=E, S=S_,
                short=short, psi=psi, sh=sh)


def reach_max(t):
    """the left arm's reach limit (fraction of its length) at t: REACH_MAX, eased up to REACH_SNAP's value over the snap."""
    if t is None: return REACH_MAX
    a, b, c, d, v = REACH_SNAP
    return REACH_MAX + (v - REACH_MAX) * ss(rng(t, a, b)) * (1.0 - ss(rng(t, c, d)))


def _left_w(t):
    return ss(rng(t, *REACH_W))


def _grip_psi(t):
    """the designed swivel at t from out/track/grip.npz, or None (outside the table / no table)."""
    g = GR.table()
    if g is None or 'psi' not in g: return None
    f = t * FPS + 1.0; fs = g['f']
    if f < fs[0] - 1e-6 or f > fs[-1] + 1e-6: return None
    return float(np.interp(f, fs, g['psi']))


def _left_fill(t, D):
    """the left arm's IK target (after the pelvis band): the hand on the aim with the table's swivel (or the best one, unsmoothed)."""
    if t < REACH_W[0]: return
    P = D['pose']; C, T = _grip_aim(t); F = _RM().frames(P)
    psi = _grip_psi(t)
    if psi is not None: a = _arm_try(P, C, T, psi, GRIP_SGN, F, t)
    else:
        a = min((_arm_try(P, C, T, ps, GRIP_SGN, F, t) for ps in PSI_GRID), key=lambda r: r['cost']); D['grip_fallback'] = True
    D['arms']['L'] = (a['Pp'], a['Rw'], a['pole'], _left_w(t))
    D['grip'] = a


def _trunk_only(t, mech):
    """the design at t with the pelvis band applied but without the fill (the trunk the left arm hangs from)."""
    D = _awake(t, mech); D.pop('fill', None)
    c = _DZC.get(fr(t), 0.0) if abs(fr(t) - (t * FPS + 1)) < 1e-6 else _dzc_at(t)
    if c:
        P = D['pose']; h = P['hips']; P['hips'] = (h[0], h[1], h[2] + c)
    return D


def _arm_map():
    """(frames, the contact mask frames x PSI_GRID grown by one grid step either way) from ARM_MAP, or None."""
    if 'map' not in _CONE:
        _CONE['map'] = None
        if os.path.exists(ARM_MAP):
            z = np.load(ARM_MAP)
            if len(z['psi']) == len(PSI_GRID) and np.allclose(z['psi'], PSI_GRID):
                h = z['hits'] > 0; d = h.copy(); d[:, 1:] |= h[:, :-1]; d[:, :-1] |= h[:, 1:]
                _CONE['map'] = (z['f'].astype(int), d.astype(float))
    return _CONE['map']


def grip_frames():
    return list(range(fr(REACH_W[0]) - 2, fr(GRIP_END)))


def build_grip(mech, write=True, verbose=True):
    """the left hand over grip_frames(): the swivel path (DP over PSI_GRID + gaussian), the chain twist; -> out/track/grip.npz.
    pelvis_pass must have run over these frames (+- 12)."""
    fs = grip_frames(); n = len(fs); m = len(PSI_GRID)
    Cst = np.zeros((n, m)); trunk = []
    for i, f in enumerate(fs):
        t = tof(f); D = _trunk_only(t, mech); P = D['pose']; F = _RM().frames(P); C, T = _grip_aim(max(t, REACH_W[0]))
        trunk.append((P, F, C, T))
        for j, ps in enumerate(PSI_GRID): Cst[i, j] = _arm_try(P, C, T, ps, GRIP_SGN, F, t)['cost']
    am = _arm_map()
    if am is not None:
        af, bad = am; idx = {int(f): k for k, f in enumerate(af)}
        for i, f in enumerate(fs):
            if f in idx: Cst[i] += ARM_MAP_K * bad[idx[f]]
    trans = PSI_DP * (PSI_GRID[:, None] - PSI_GRID[None, :]) ** 2
    acc = Cst[0].copy(); back = np.zeros((n, m), int)
    for i in range(1, n):
        tot = acc[None, :] + trans; back[i] = np.argmin(tot, axis=1); acc = tot[np.arange(m), back[i]] + Cst[i]
    path = np.zeros(n, int); path[-1] = int(np.argmin(acc))
    for i in range(n - 1, 0, -1): path[i - 1] = back[i, path[i]]
    raw = PSI_GRID[path].astype(float)
    R = int(math.ceil(3 * PSI_SM)); k = np.exp(-0.5 * (np.arange(-R, R + 1) / PSI_SM) ** 2); k /= k.sum()
    psi = np.convolve(np.pad(raw, R, mode='edge'), k, mode='valid')
    tw = []; ws = []; phis = []; rep = []
    for i, f in enumerate(fs):
        P, F, C, T = trunk[i]; a = _arm_try(P, C, T, float(psi[i]), GRIP_SGN, F, tof(f))
        Ce, Te, We = _end_now(tof(f))
        tw.append(GR.twist_for(We, Te, a['Rp'][:, 2])); ws.append(ss(rng(tof(f), *TWIST_IN))); phis.append(a['phi'])
        rep.append((f, a))
    tw = GR.unwrap_pi(tw)
    if write:
        np.savez(GR.GRIP_NPZ, f=np.array(fs, float), psi=psi, sgn=np.full(n, GRIP_SGN), twist=tw, w=np.array(ws), phi=np.array(phis))
        GR._G.clear()
    if verbose:
        print('grip %d frames %d..%d  twist %.1f .. %.1f deg' % (n, fs[0], fs[-1], math.degrees(tw.min()), math.degrees(tw.max())))
        for f, a in rep[::6]:
            print('  f %d t %.3f psi %6.1f bend %5.1f d %5.2f short %4.2f swing %5.1f twist %6.1f hits %d' % (
                f, tof(f), a['psi'], a['bend'], a['d'], a['short'], a['swing'], a['twist'], a['hits']))
    return rep


# ===================================================================================================================== 69.3 .. 76.0 the hold
# 69.3 the grab, leaning over the water (the left arm down to the end); 69.3 .. 70.0 the slack runs out, the chain snaps taut at 70.0
# and yanks it forward; 70.0 .. 71.6 dragged SSW leaning back, the feet ploughing; 72.0 .. 73.6 the strain: backing up against the pull
# step by step, leaning back (armour cracks, steam); 73.6 .. 74.3 the pivot (clockwise, the chain kept on the left); 74.3 .. 75.5
# hauling north up the head's mound (the fist rides high on the slope: story.HAUL_LIFT); 75.5 .. 76.0 onto the cap, turning into
# the wind, crouched. The pelvis is keyed in WORLD z (the root's floor jumps on the mound's steps).
HOLD_K = {   # t: pelvis pivot height over the smoothed floor (dz, as hips z), lean, side bend (+ toward the left), pelvis / spine / chest twist (rz; - = the left side forward)
    'dz':   [(68.5, -7.52), (68.8, -9.02), (69.1, -9.92), (GRIP_T, -10.02), (69.6, -8.72), (70.0, -7.12), (70.15, -7.92),
             (70.4, -6.52), (70.8, -5.12), (71.6, -4.52), (72.0, -4.52), (72.6, -4.92), (73.2, -4.92), (73.6, -4.92), (73.95, -6.0),
             (74.3, -7.0), (74.7, -8.5), (75.0, -9.5), (75.5, -10.0), (76.0, -11.0), (77.9, -11.0),
             (78.2, -11.5), (78.45, -13.0), (78.6, -12.5), (80.6, -12.5), (80.72, -13.5), (81.0, -12.7), (83.6, -12.0), (90.0, -12.0)],
    'lean': [(68.5, 23.0), (68.8, 23.0), (69.1, 22.0), (GRIP_T, 21.0), (69.55, 18.0), (69.8, 14.0), (70.0, 12.0), (70.12, 16.0),
             (70.35, 6.0), (70.7, -6.0), (71.2, -12.0), (71.8, -14.0), (72.4, -15.0), (73.0, -14.0), (73.6, -13.0), (73.95, 8.0),
             (74.3, 20.0), (74.7, 24.0), (75.0, 25.0), (75.5, 25.0), (76.0, 24.0), (77.9, 24.0),
             (78.2, 27.0), (78.45, 31.0), (78.6, 29.0), (80.6, 27.0), (80.7, 31.0), (81.0, 27.0), (83.9, 18.0), (88.2, 16.0),
             (90.0, 19.0)],
    'bend': [(68.5, 0.0), (69.0, 4.0), (GRIP_T, 6.0), (69.8, 4.0), (70.3, 0.0), (72.0, -3.0), (73.6, -3.0), (74.3, 2.0), (75.5, 8.0),
             (76.0, 15.0), (77.9, 15.0), (78.2, 12.0), (78.6, 8.0), (80.6, 8.0), (83.6, 6.0), (90.0, 6.0)],
    'ptw':  [(68.5, -7.0), (69.0, -8.0), (GRIP_T, -7.0), (70.0, -5.0), (72.0, -4.0), (73.6, -4.0), (74.3, 0.0), (76.0, 0.0), (90.0, 0.0)],
    'stw':  [(68.5, 4.2), (69.0, 1.0), (GRIP_T, -1.0), (70.0, -4.0), (72.0, -5.0), (73.6, -4.0), (74.3, 2.0), (76.0, 0.0), (90.0, 0.0)],
    'ctw':  [(68.5, 7.0), (69.0, 2.0), (GRIP_T, 0.0), (70.0, -6.0), (71.0, -7.0), (72.0, -7.0), (73.6, -6.0), (74.3, 4.0),
             (75.5, 0.0), (76.0, 0.0), (90.0, 0.0)],
}
R_ARM = [(a, (v[0], -14.0, v[1])) for a, v in WADE_ARM['R']] + [  # the right arm (shoulder rx, ry, elbow rx) from the wade on: back
    # and out for balance in the drag (the shoulder's abduction stays under the pauldrons' ~20 deg), pumping while backing up,
    # forward and down toward the slope in the climb
    (GRIP_T, (28.0, -14.0, -40.0)), (69.6, (14.0, -16.0, -46.0)), (70.0, (0.0, -17.0, -52.0)), (70.2, (34.0, -18.0, -58.0)),
    (70.6, (32.0, -18.0, -54.0)), (71.6, (28.0, -17.0, -50.0)), (72.4, (24.0, -16.0, -56.0)), (73.0, (16.0, -16.0, -60.0)),
    (73.6, (8.0, -15.0, -62.0)), (73.95, (-12.0, -15.0, -66.0)), (74.3, (-20.0, -14.0, -62.0)), (75.0, (-24.0, -14.0, -60.0)),
    (75.5, (-24.0, -13.0, -62.0)), (76.0, (-24.0, -13.0, -64.0))]


_FLOOR_S = {}


def _floor_s(t):
    """the root's floor (mechplan.floor_at: the lowest planted sole) smoothed (sigma 0.2 s): the walking body's reference height."""
    if 'f' not in _FLOOR_S:
        ts = np.arange(66.0, 92.0, 1.0 / 48); z = np.array([MP.floor_at(x) for x in ts])
        k = np.exp(-0.5 * (np.arange(-29, 30) / 9.6) ** 2); k /= k.sum()
        _FLOOR_S['f'] = (ts, np.convolve(np.pad(z, 29, mode='edge'), k, mode='valid'))
    ts, zs = _FLOOR_S['f']
    return float(np.interp(t, ts, zs))


PSH_K = [(75.5, 0.4), (90.0, 0.4)]   # the pelvis's share of the lean (as the run: the hips keep their forward range)


GRAB_SHIFT = dict(t=(68.9, 70.7), ramp=0.35, turn=10.0, hips=(4.0, -6.0, 1.0))
# over the grab the chest turns 10 deg toward the end it takes and the weight goes onto it (the hips 4 m left, 6 m ahead, 1 m up,
# root frame): the left arm reaches the bar with the elbow bent ~40-50 deg inside the shoulder's free cone. Straight, its aim sat
# 14 deg out to the left of the chest and the upper arm / pauldron met the collar at every swivel (out/qa/armsweep_d0.log);
# tuned in memory: side script grab_sweep.py CT=10 HX=4 HY=-6 DZ=1 (the reach exact from 69.12, no band conflicts)


def _grab_k(t):
    a, b = GRAB_SHIFT['t']; r = GRAB_SHIFT['ramp']
    if t <= a or t >= b: return 0.0
    return ss(rng(t, a, a + r)) * (1.0 - ss(rng(t, b - r, b)))


def _grab_hips(P, t):
    """the grab's weight shift on the hips offset (root frame)."""
    k = _grab_k(t)
    if k > 0.0:
        h = P['hips']; d = GRAB_SHIFT['hips']; P['hips'] = (h[0] + d[0] * k, h[1] + d[1] * k, h[2] + d[2] * k)


def _hold_channels(t):
    ch = {c: keys_at(HOLD_K[c], t) for c in CHANNELS if c != 'pz'}
    ch['ctw'] += GRAB_SHIFT['turn'] * _grab_k(t)
    ch['pz'] = _floor_s(t) + PELVIS_Z + keys_at(HOLD_K['dz'], t)
    ch['psh'] = keys_at(PSH_K, t)
    return ch


def _hold_look(t):
    """(target, weight): the end in the hand (the wade's look carried on), up the chain as it snaps taut, the city in the strain,
    ahead in the haul."""
    J = GR.joints(t * FPS + 1.0); up = J[50]
    if t < 70.0:
        k = ss(rng(t, 69.45, 70.0))
        return _lmix(_chain_end_look(t), up, k), 0.75 - 0.05 * ss(rng(t, GRIP_T, 69.6))
    if t < 73.6: return _lmix(up, city_look(t), ss(rng(t, 72.0, 72.8))), 0.7
    ahead = np.array((S.LIGHTHOUSE[0], S.LIGHTHOUSE[1], 30.0))
    k = ss(rng(t, 73.6, 74.3))
    return _lmix(city_look(t), ahead, k), 0.7 - 0.2 * k


# The wind's lean-out (05.11): the fist holds the chain at the drum side of the hip (WIND_LFT), so the pelvis shifts away from it, 4 m
# to the right in the root frame, rolled 6 deg left side down: the left thigh and shin clear the fist and the forearm through the run's
# left push-offs. The shift eases off (60 %) round the right push-off at 76.95 (the right thigh's crotch side clears the pelvis; the
# fist has room there: the left leg is forward), the roll (70 %) round the left mid-swing at 76.75 (the left hip a little higher: the
# swing's sole clears the cap with the knee at its fold limit). The right knee points further out (pole_r) and its swing foot rolls
# the outer edge down (swing_roll_r); the first swing off the climb plant turns its toes out too (swing_toe_r). In on the climb onto the cap (74.9 .. 75.5, s36: off screen), out after the brace (78.4 .. 79.0).
LEAN = dict(t=(74.9, 75.5, 78.4, 79.0), dx=-4.0, roll=6.0, dx_relief=(76.65, 76.95, 77.25, 0.6),
            roll_relief=(76.45, 76.75, 77.05, 0.7), pole_r=0.5, swing_roll_r=-12.0, swing_toe_r=-8.0, sw_in=0.08, sw_out=0.12)
# (the right swing's roll / toe-out come in over the first sw_in s after the lift; the roll goes over the last sw_out s before the
#  footfall, the toe-out over 55 .. 95 % of the swing: nothing left at the footfall, no pop)


def _lean_k(t):
    a, b, c, d = LEAN['t']
    return ss(rng(t, a, b)) * (1.0 - ss(rng(t, c, d)))


def _relief(t, r):
    return r[3] * ss(rng(t, r[0], r[1])) * (1.0 - ss(rng(t, r[1], r[2])))


def _lean_out(P, t):
    k = _lean_k(t)
    if k <= 0.0: return
    kx = k * (1.0 - _relief(t, LEAN['dx_relief'])); kr = k * (1.0 - _relief(t, LEAN['roll_relief']))
    h = P['hips']; P['hips'] = (h[0] + LEAN['dx'] * kx, h[1], h[2])
    a = P['pelvis']; P['pelvis'] = (a[0], a[1] + LEAN['roll'] * kr, a[2])


def _hold_trunk(t):
    P = base_pose(); r = MP.root_at(t)
    _trunk_from(P, _hold_channels(t), r); _grab_hips(P, t); _lean_out(P, t)
    v = keys_at(R_ARM, t)
    P['shoulderR'] = (v[0], v[1], 3.0); P['elbowR'] = (v[2], 0.0, 0.0); P['wristR'] = (10.0, -4.0, 0.0)
    P['fingersR'] = (0.8, 0.82, 0.8); P['thumbR'] = _RM().safe_thumb((0.8, 0.82, 0.8), 0.3)
    # the left arm's FK (under the IK at weight 1): the wade's last FK pose; the fist on the bar
    P['shoulderL'] = (-46.0, -14.0, 3.0); P['elbowL'] = (-34.0, 0.0, 0.0); P['wristL'] = (10.0, -4.0, 0.0)
    P['fingersL'] = tuple(GR.GRIP_FINGERS); P['thumbL'] = GR.GRIP_THUMB
    _with_root(P, t, r[:3], r[3], hips=P['hips'])
    return P


def _hold(t, mech):
    P = _hold_trunk(t)
    legs = {}
    for sd in ('L', 'R'):          # a stance that lifts into the wind's run pushes off like the run (its swing starts heel-up HEEL_UP)
        q = _plant_now(t, sd)
        into_run = q is not None and q['lift'] is not None and q['lift'] >= WIND_T0 - 1e-6
        legs[sd] = _walk_foot(t, sd, heel=HEEL_UP if into_run else WALK_HEEL)
    tg, w = _hold_look(t)
    return {'pose': P, 'legs': legs, 'arms': {'L': None, 'R': None}, 'look': (tg, w, 0.45), 'fill': _left_fill}


# ===================================================================================================================== 75.5 .. 78.2 the wind
# A crouched hauling run round the drum (hips low, the trunk leaning ~24 deg and banked 8 deg into the circle), the left arm down at
# the side with the fist at the hip (the chain runs from it down to the wrap under the cornice), the body beside the palm: a footfall
# on every chord (76.0, 76.6, 77.2, 77.8), stance 0.4 s, the run's swing machinery
# (heel kick, knee drive, the soft band), the pelvis bobbing low after each footfall, the right arm pumping against the right leg.
# The run fades into the brace (the left foot forward at 78.2, the palm stops dead on the last chord). 75.5 .. 76.0 (unseen) the haul's
# keys hand over: the legs switch to the run's swings at the right foot's last climb plant (75.5, the left foot just lifting).
WIND_T0 = 75.5
WIND_FALLS = [76.0, 76.6, 77.2, 77.8, 78.2]
WIND_RUN = (75.5, 76.0)                # the run's bob / twist / arm pump fade in over this
WIND_STOP = (77.8, WIND_T1)            # .. and out into the brace


def _wind_k(t):
    return ss(rng(t, *WIND_RUN)) * (1.0 - ss(rng(t, *WIND_STOP)))


def _wind_phase(t):
    return 2 * math.pi * (t - 76.0) / 1.2          # 0 at the left footfalls (76.0, 77.2)


def _wind_channels(t):
    ch = _hold_channels(t); k = _wind_k(t)
    if k <= 0.0: return ch
    ff = [x for x in WIND_FALLS if x <= t + 1e-6]; tk = ff[-1] if ff else WIND_FALLS[0] - 0.6
    bob = -0.3 * math.cos(2 * math.pi * (t - tk - 0.12) / 0.6)          # low just after the footfall, high in the flight (small:
                                                                        # the fist holds the chain, the swing's clearance)
    tw = -6.0 * math.cos(_wind_phase(t))                                  # the pelvis turns the swing hip forward
    ch['pz'] += bob * k; ch['ptw'] += tw * k; ch['stw'] += -0.5 * tw * k; ch['ctw'] += -0.5 * tw * k     # the chest stays square
    return ch


def _wind_arm_r(t):
    """(shoulder rx, ry, elbow rx) of the right arm: the hold's keys handing over to the run's pump (30 deg each way against the
    right leg, forward at the left footfalls)."""
    v0 = keys_at(R_ARM, min(t, 76.0)); k = _wind_k(t)
    c = math.cos(_wind_phase(t))
    v1 = (-14.0 - 30.0 * c, -14.0, -80.0 - 12.0 * max(0.0, c))       # the run's pump (forward at the left footfalls)
    kk = ss(rng(t, *WIND_RUN))
    rest = (-26.0, -13.0, -40.0)                  # the brace: the arm hangs, a little bent
    w = v1 if k >= kk - 1e-9 else tuple(lerp(rest[i], v1[i], k / max(kk, 1e-9)) for i in range(3))
    return tuple(lerp(v0[i], w[i], kk) for i in range(3))


def _wind_look(t):
    """ahead round the drum (a point on the wrap ~45 deg on), handing over from the haul's look."""
    a = math.radians(S.palm_angle_unwrapped(min(t, WIND_T1)) + 45.0)
    ahead = np.array((S.LIGHTHOUSE[0] + 16.0 * math.cos(a), S.LIGHTHOUSE[1] + 16.0 * math.sin(a), S.WRAP_Z[0]))
    tg, w = _hold_look(min(t, 76.0)); k = ss(rng(t, *WIND_RUN))
    return _lmix(tg, ahead, k), lerp(w, 0.5, k)


def _wind_trunk(t):
    P = base_pose(); r = MP.root_at(t)
    _trunk_from(P, _wind_channels(t), r); _lean_out(P, t)
    v = _wind_arm_r(t)
    P['shoulderR'] = (v[0], v[1], 3.0); P['elbowR'] = (v[2], 0.0, 0.0); P['wristR'] = (10.0, -4.0, 0.0)
    P['fingersR'] = (0.8, 0.82, 0.8); P['thumbR'] = _RM().safe_thumb((0.8, 0.82, 0.8), 0.3)
    P['shoulderL'] = (-46.0, -14.0, 3.0); P['elbowL'] = (-34.0, 0.0, 0.0); P['wristL'] = (10.0, -4.0, 0.0)     # (the hold's FK)
    P['fingersL'] = tuple(GR.GRIP_FINGERS); P['thumbL'] = GR.GRIP_THUMB
    _with_root(P, t, r[:3], r[3], hips=P['hips'])
    return P


def _wind_fill(t, D):
    _run_swing(t, D); _left_fill(t, D)


def _wind(t, mech):
    P = _wind_trunk(t)
    legs = {}
    for sd in ('L', 'R'):
        f = MP.foot_at(t, sd)
        if f is None: legs[sd] = None; continue
        if f['planted'] or _swing_pair(t, sd) is None:
            ft = dict(p=np.array(f['p'], float), yaw=f['yaw'], pitch=f['pitch'], roll=f['roll'], planted=True, w=1.0,
                      pole=_run_pole(t, P['root'][3], sd))
            q = _plant_now(t, sd)
            if q is not None and q['lift'] is not None:
                ht_, hu_ = _heel_of(q); k = _heel_k(t, q['lift'], ht_); ft = _heel_foot(ft, k, hu_); ft['heel'] = k
            if q is not None and q['kind'] in ('wind', 'brace'): ft['land'] = 1.0 - ss(rng(t, q['t'], q['t'] + 0.08))
            legs[sd] = ft
        else: legs[sd] = dict(swing=True, planted=False, w=1.0)      # filled by _run_swing once the pelvis band is applied
    tg, w = _wind_look(t)
    return {'pose': P, 'legs': legs, 'arms': {'L': None, 'R': None}, 'look': (tg, w, 0.45), 'fill': _wind_fill}


# ===================================================================================================================== 78.2 .. 90 the brace, the rest
# 78.2 the brace: the left foot down forward on the last chord, the palm stops dead, the hips drop and the trunk rises a little against
# the pull (78.2 .. 78.6); held through the spout's pass; 80.6 the slack: a shudder as the tension goes; 81.0 .. 83.6 it eases up
# (the trunk to ~14 deg, the fist a little higher: story.REST_LIFT), looking up the chain to the city; 86.4 .. 87.45 the
# gull comes home to the nest (the head steady: gull_home); 88.2 the visor dims and the head sinks a little.
def _rest_arm_r(t, lean):
    k = ss(rng(t, WIND_T1, 78.6))
    v0 = _wind_arm_r(min(t, WIND_T1)); v1 = (-0.9 * lean - 4.0, -13.0, -40.0)
    return tuple(lerp(v0[i], v1[i], k) for i in range(3))


def _rest_look(t):
    pal = np.asarray(S.palm_path(t), float) + np.array((0.0, 0.0, 4.0))
    tg0, w0 = _wind_look(min(t, WIND_T1))
    k1 = ss(rng(t, WIND_T1, 78.6)); tg = _lmix(tg0, pal, k1)
    k2 = ss(rng(t, 80.9, 82.8)); tg = _lmix(tg, city_look(t), k2)
    w = lerp(lerp(w0, 0.45, k1), 0.55, k2) * (1.0 - 0.6 * ss(rng(t, 88.3, 89.6)))
    return tg, w


def _rest_trunk(t):
    P = base_pose(); r = MP.root_at(t); ch = _hold_channels(t)
    _trunk_from(P, ch, r); _lean_out(P, t)
    v = _rest_arm_r(t, ch['lean'])
    P['shoulderR'] = (v[0], v[1], 3.0); P['elbowR'] = (v[2], 0.0, 0.0); P['wristR'] = (10.0, -4.0, 0.0)
    c = lerp(0.8, 0.55, ss(rng(t, 81.0, 83.0)))
    P['fingersR'] = (c, c + 0.02, c); P['thumbR'] = _RM().safe_thumb((c, c + 0.02, c), lerp(0.3, 0.25, ss(rng(t, 81.0, 83.0))))
    P['shoulderL'] = (-46.0, -14.0, 3.0); P['elbowL'] = (-34.0, 0.0, 0.0); P['wristL'] = (10.0, -4.0, 0.0)     # (the hold's FK)
    P['fingersL'] = tuple(GR.GRIP_FINGERS); P['thumbL'] = GR.GRIP_THUMB
    _with_root(P, t, r[:3], r[3], hips=P['hips'])
    return P


def _rest(t, mech):
    P = _rest_trunk(t)
    legs = {}
    for sd in ('L', 'R'):
        ft = _walk_foot(t, sd)
        if ft is not None: ft['pole'] = _run_pole(t, P['root'][3], sd)       # the wind's knee poles carried on (no swing at 78.2)
        legs[sd] = ft
    tg, w = _rest_look(t)
    return {'pose': P, 'legs': legs, 'arms': {'L': None, 'R': None}, 'look': (tg, w, 0.45), 'fill': _left_fill}


def _awake(t, mech):
    if t < RISE_END: return _rise(t, mech)
    if t < MP.RUN_T0: return _stand_steps(t, mech)
    if t <= MP.TAKEOFF: return _run(t, mech)
    if t < MP.LAND_T: return _flight(t, mech)
    if t < MP.GRAB_T: return _wade(t, mech)
    if t < WIND_T0: return _hold(t, mech)
    if t < WIND_T1: return _wind(t, mech)
    if t <= 90.0: return _rest(t, mech)
    return _hold_placeholder(t, mech)


# ===================================================================================================================== the pelvis band
# Every frame: a planted (IK-weighted) leg needs its hip within [D_MIN, D_MAX] of its ankle. The design's hips dz is corrected by
# the smallest smooth offset that keeps every planted leg in the band (erode/dilate, then blur with the same support: the bound holds).
_DZC = {}


def _dz_bounds(D):
    P = D['pose']; root = P['root']; hips = np.array(P['hips'], float); lo, hi = -1e9, 1e9
    for sd in ('L', 'R'):
        ft = D['legs'].get(sd)
        if ft is None or ft.get('w', 1.0) < 0.5 or ft.get('swing'): continue
        A = ankle_of(ft); H = hip_world(root, hips, P['pelvis'], sd)
        dh = float(np.hypot(*(H[:2] - A[:2]))); vz = float(H[2] - A[2])
        dmax = lerp(D_MAX, SW_BAND[1] - SW_SOFT - 0.15, max(ft.get('heel', 0.0), ft.get('land', 0.0)))
        # hip z moves 1:1 with dz (the root is yaw-only)
        if dh < dmax: hi = min(hi, hips[2] + (math.sqrt(dmax ** 2 - dh ** 2) - vz))
        else: hi = min(hi, hips[2] - vz)
        if dh < D_MIN: lo = max(lo, hips[2] + (math.sqrt(D_MIN ** 2 - dh ** 2) - vz))
    return lo, hi


DZ_SMOOTH = os.environ.get('DZ_SMOOTH', '1') == '1'
DZ_LAM = 5e-4                # the correction's stiffness: it spreads over ~ (1 / DZ_LAM) ** 0.25 ~ 7 frames each way


def _smooth_box(c0, lo, hi, lam=DZ_LAM, iters=4000):
    """the correction c (from c0) minimising |second differences of c|^2 + lam |c|^2 with lo <= c <= hi (accelerated projected
    gradient): the designed hips are kept where the legs allow, and the band's corrections come in and go out without a kink."""
    lo = np.minimum(lo, hi)                       # conflicting bounds: the upper one wins (as the clamp before)
    x = np.clip(np.asarray(c0, float), lo, hi); y = x.copy(); tk = 1.0; eta = 1.0 / (2.0 * (16.0 + lam)); n = len(x)
    if n < 5: return x
    for _ in range(iters):
        d = y[2:] - 2.0 * y[1:-1] + y[:-2]
        g = lam * y; g[:-2] += d; g[1:-1] -= 2.0 * d; g[2:] += d
        xn = np.clip(y - 2.0 * eta * g, lo, hi)
        tn = 0.5 * (1.0 + math.sqrt(1.0 + 4.0 * tk * tk)); y = xn + ((tk - 1.0) / tn) * (xn - x); x = xn; tk = tn
    return x


def pelvis_pass(mech, f0=1, f1=NF):
    """compute the dz corrections for frames f0..f1 (needs _SLEEP_FEET)."""
    n = f1 - f0 + 1; dz = np.zeros(n); lo = np.full(n, -1e9); hi = np.full(n, 1e9); awake = np.zeros(n, bool)
    for i, f in enumerate(range(f0, f1 + 1)):
        t = tof(f)
        if t <= T_RISE: continue
        D = design(t, mech, raw=True); awake[i] = True
        dz[i] = D['pose']['hips'][2]; lo[i], hi[i] = _dz_bounds(D)
    ch = np.minimum(0.0, hi - dz); cl = np.maximum(0.0, lo - dz)
    R = 3
    def erode(x):
        p = np.pad(x, R, mode='edge'); return np.array([p[i:i + 2 * R + 1].min() for i in range(len(x))])
    def dilate(x):
        p = np.pad(x, R, mode='edge'); return np.array([p[i:i + 2 * R + 1].max() for i in range(len(x))])
    k = np.exp(-0.5 * (np.arange(-R, R + 1) / 1.6) ** 2); k /= k.sum()
    def blur(x):
        p = np.pad(x, R, mode='edge'); return np.convolve(p, k, mode='valid')
    corr = blur(erode(ch)) + blur(dilate(cl))
    out = dz + corr
    out = np.minimum(out, hi); out = np.maximum(out, lo)          # residual (conflicting bounds keep the upper one last)
    out = np.minimum(out, hi)
    if DZ_SMOOTH and awake.any():                                  # one smooth correction under the band (no kink where a bound bites)
        ia = np.flatnonzero(awake); a0, a1 = int(ia[0]), int(ia[-1]) + 1
        c = _smooth_box(out[a0:a1] - dz[a0:a1], lo[a0:a1] - dz[a0:a1], hi[a0:a1] - dz[a0:a1])
        out[a0:a1] = dz[a0:a1] + c
    bad = [(f0 + i, round(lo[i], 2), round(hi[i], 2)) for i in range(n) if awake[i] and lo[i] > hi[i] + 0.05]
    for i, f in enumerate(range(f0, f1 + 1)):
        if awake[i]: _DZC[f] = float(out[i] - dz[i])
    _DZC_VER[0] += 1; _SWING_CACHE.clear()
    return bad


# ===================================================================================================================== the gull
def gull_flight(t, p0, f0):
    """world (pos, forward, up, flap deg, spread 0..1) of the gull fleeing the nest (T_GULL_OFF .. T_GULL_GONE); p0/f0 = its
    standing position / facing on the nest. It crouches 2 frames, springs up and back, flaps hard and climbs away north-east."""
    tau = t - T_GULL_OFF
    if tau < 0: return p0, f0, np.array((0.0, 0.0, 1.0)), 0.0, 0.0
    if tau < 0.09:
        k = tau / 0.09
        return p0 - np.array((0.0, 0.0, 0.12 * k)), f0, np.array((0.0, 0.0, 1.0)), 30.0 * k, k
    tf = tau - 0.09
    away = np.array((0.55, 0.83, 0.0)); away /= np.linalg.norm(away)
    v0 = away * 3.0 + np.array((0.0, 0.0, 7.5)); acc = away * 4.5 + np.array((0.0, 0.0, -1.2))
    p = p0 + v0 * tf + 0.5 * acc * tf * tf
    v = v0 + acc * tf
    hz = np.array((v[0], v[1], 0.0)); h = np.linalg.norm(hz)
    fwd_ = hz / h if h > 1e-6 else f0
    w = ss(tf / 0.35); fh = f0 * (1 - w) + fwd_ * w; fh = fh / max(np.linalg.norm(fh), 1e-9)
    pitch = math.radians(min(35.0, math.degrees(math.atan2(v[2], max(h, 1e-6)))) * 0.7)
    fwd3 = fh * math.cos(pitch) + np.array((0.0, 0.0, math.sin(pitch)))
    flap = 12.0 + 52.0 * math.sin(2 * math.pi * 2.6 * tf + 0.6)
    roll = math.radians(8.0 * math.sin(2 * math.pi * 1.1 * tf))
    side = np.cross(np.array((0.0, 0.0, 1.0)), fwd3); side /= max(np.linalg.norm(side), 1e-9)
    up = np.cross(fwd3, side); up = up * math.cos(roll) + side * math.sin(roll)
    return p, fwd3, up, flap, 1.0


def bird_frame(fwd_, up):
    """3x3 of the bird frame (columns X = up x fwd, Y = -fwd, Z = up), as mech.build_overgrowth builds it."""
    f = np.asarray(fwd_, float); f = f / np.linalg.norm(f); u = np.asarray(up, float); u = u - f * np.dot(u, f); u /= np.linalg.norm(u)
    return np.stack((np.cross(u, f), -f, u), 1)


def gull_idle_yaw(t):
    """small turns on the rim while it sleeps (deg about its up axis), on twos."""
    t = twos(t)
    keys = [(0.0, 0.0), (9.95, 0.0), (10.12, 28.0), (10.9, 28.0), (11.0, 18.0), (12.0, 18.0), (12.2, -10.0), (43.9, -10.0), (44.05, 0.0)]
    return float(np.interp(t, [k[0] for k in keys], [k[1] for k in keys]))


# The return (s42, on twos; numpy, world): seen from the cut (86.4), 15 m out over the open sea beyond s42's camera, low, two beats
# and a glide in toward the nest (a cubic through the rest point, cruising to 40 % of the way, then braking to a near stop), the
# flare over the far rim (nose up 38 deg, braking beats with the wings above the twigs), down at 87.45 with the wings up; it stands
# upright on the rim (its rest frame is the sleeping head's: 34 deg off the vertical on the kneeling one), folds and turns to the
# chick. Checked against every mech part, the nest and the chick by BVH (the legs alone meet the twigs) and from s42's camera.
GULL_HOME = dict(t_s=86.25, t_land=T_GULL_LAND, az0=268.0, d0=15.0, z0=-0.8, curve=10.0, az_f=250.0, d_f=3.2, z_f=-1.0,
                 beats=(86.4, 3.0, 1.6), flare=0.42, settle=0.55, pitch_flare=38.0, flare_flap=(22.0, 64.0), up_land=60.0,
                 fold=(0.1, 0.42), idle=[(87.45, 0.0), (88.0, 0.0), (88.12, 18.0), (89.0, 18.0), (89.12, 0.0)])
_GH = {}


def _hv(az):
    a = math.radians(az); return np.array((math.sin(a), math.cos(a), 0.0))


def _gh_ctrl(p_rest):
    g = GULL_HOME
    B0 = p_rest + _hv(g['az0']) * g['d0'] + np.array((0.0, 0.0, g['z0']))
    B1 = B0 + _hv(g['az0'] + 180.0 + g['curve']) * (0.4 * g['d0'])
    B2 = p_rest + _hv(g['az_f']) * g['d_f'] + np.array((0.0, 0.0, g['z_f']))
    return [B0, B1, B2, p_rest + np.array((0.0, 0.0, 0.12))]


def _bez3(B, s):
    u = 1.0 - s; return B[0] * u ** 3 + 3 * B[1] * u * u * s + 3 * B[2] * u * s * s + B[3] * s ** 3


def _bez3_d(B, s):
    u = 1.0 - s; return 3 * (B[1] - B[0]) * u * u + 6 * (B[2] - B[1]) * u * s + 3 * (B[3] - B[2]) * s * s


def _gh_timing():
    if 's' not in _GH:
        tau = np.linspace(0.0, 1.0, 401); v = np.array([1.0 - 0.96 * ss((x - 0.4) / 0.6) for x in tau])
        sv = np.concatenate(([0.0], np.cumsum(0.5 * (v[1:] + v[:-1]) * np.diff(tau)))); sv /= sv[-1]
        _GH['s'] = (tau, sv)
    return _GH['s']


def _gh_vel(t, B):
    g = GULL_HOME; ts, tl = g['t_s'], g['t_land']; tg, sg = _gh_timing()
    ta = rng(t, ts, tl); sa = float(np.interp(ta, tg, sg))
    d = float(np.interp(min(ta + 0.01, 1.0), tg, sg)) - float(np.interp(max(ta - 0.01, 0.0), tg, sg))
    return _bez3_d(B, sa) * d / (0.02 * (tl - ts))


def gull_home(t, p_rest, R_rest, p_chick=None):
    """dict(p, fwd, up, flap deg, spread 0..1) of the gull coming home at t (world). p_rest / R_rest: its rest frame on the nest now
    (the touchdown point), p_chick: the chick (it turns to face it)."""
    g = GULL_HOME; ts, tl = g['t_s'], g['t_land']; tg, sg = _gh_timing()
    B = _gh_ctrl(p_rest); zup = np.array((0.0, 0.0, 1.0))
    if t >= tl:
        p = p_rest + np.array((0.0, 0.0, 0.12 * (1.0 - ss(rng(t, tl, tl + 0.12))) - 0.08 * math.sin(math.pi * rng(t, tl + 0.08, tl + 0.4))))
        d = _bez3_d(B, 1.0); f0 = np.array((d[0], d[1], 0.0)); f0 /= np.linalg.norm(f0)
        if p_chick is not None: f1 = np.asarray(p_chick, float) - p_rest
        else: f1 = -R_rest[:, 1]
        f1 = np.array((f1[0], f1[1], 0.0)); f1 /= np.linalg.norm(f1)
        a0 = math.atan2(f0[1], f0[0]); a1 = math.atan2(f1[1], f1[0])
        a1 += math.radians(float(np.interp(t, [k[0] for k in g['idle']], [k[1] for k in g['idle']])))
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi; a = a0 + da * ss(rng(t, tl + 0.1, tl + g['settle']))
        fh = np.array((math.cos(a), math.sin(a), 0.0))
        pitch = math.radians(g['pitch_flare'] * (1.0 - ss(rng(t, tl, tl + 0.3))))
        fwd3 = fh * math.cos(pitch) + zup * math.sin(pitch)
        side = np.cross(zup, fwd3); side /= np.linalg.norm(side)
        k = ss(rng(t, tl + g['fold'][0], tl + g['fold'][1]))
        return dict(p=p, fwd=fwd3, up=np.cross(fwd3, side), flap=g['up_land'] * (1.0 - k), spread=1.0 - k)
    tau = rng(t, ts, tl); p = _bez3(B, float(np.interp(tau, tg, sg)))
    v = _gh_vel(t, B); acc = (_gh_vel(t + 0.04, B) - _gh_vel(t - 0.04, B)) / 0.08
    hz = np.array((v[0], v[1], 0.0)); h = float(np.linalg.norm(hz))
    fh = hz / h if h > 0.3 else -R_rest[:, 1] * np.array((1.0, 1.0, 0.0))
    fh = fh / np.linalg.norm(fh)
    tf = tl - g['flare']; kf = ss(rng(t, tf, tf + 0.3))
    pitch = math.radians(0.5 * math.degrees(math.atan2(v[2], max(h, 1e-6))) * (1 - kf) + g['pitch_flare'] * kf)
    fwd3 = fh * math.cos(pitch) + zup * math.sin(pitch)
    side = np.cross(zup, fwd3); side /= max(np.linalg.norm(side), 1e-9)
    roll = max(-0.6, min(0.6, math.atan2(float(np.dot(acc, side)) if h > 0.3 else 0.0, 9.8))) * (1.0 - kf)
    up = np.cross(fwd3, side); up = up * math.cos(roll) + side * math.sin(roll)
    tb, fb, nb = g['beats']
    if t < tf:
        x = t - tb; wb = 1.0 - ss(rng(x, nb / fb - 0.2, nb / fb + 0.05))
        flap = (12.0 + 46.0 * math.sin(2 * math.pi * fb * x + 0.4)) * wb + (5.0 + 4.0 * math.sin(2 * math.pi * 0.9 * x)) * (1 - wb)
    else:
        lo, hi = g['flare_flap']; x = t - tf
        flap = 0.5 * (lo + hi) + 0.5 * (hi - lo) * math.sin(2 * math.pi * 4.2 * x + 1.3)
        w = ss(rng(t, tl - 0.12, tl)); flap = flap * (1 - w) + g['up_land'] * w
    return dict(p=p, fwd=fwd3, up=up, flap=flap, spread=1.0)


def chick_peep(t):
    """the chick's head-up peeps (deg about its X): two in the macro shot, ducking when the water hits."""
    t = twos(t)
    keys = [(0.0, 0.0), (9.9, 0.0), (10.0, -14.0), (10.25, 0.0), (10.6, -12.0), (10.8, 0.0), (43.95, 0.0), (44.05, 9.0), (46.0, 9.0), (46.5, 0.0),
            (87.42, 0.0), (87.55, -16.0), (87.8, 0.0), (88.05, -10.0), (88.25, 0.0)]       # .. and two when the gull lands
    return float(np.interp(t, [k[0] for k in keys], [k[1] for k in keys]))


# ===================================================================================================================== Blender side
def _bpy():
    import bpy
    from mathutils import Matrix, Vector, Euler, Quaternion
    return bpy, Matrix, Vector, Euler, Quaternion


def solve(M, mech, t, D=None):
    """set the rig to the design at t (FK, then the IK targets blended in by their weights). Returns the design."""
    bpy, Matrix, Vector, Euler, Quaternion = _bpy()
    D = D or design(t, mech)
    mech.set_pose(M, D['pose'])
    J = M['joints']
    for sd in ('L', 'R'):
        ft = D['legs'].get(sd)
        if ft is None: continue
        w = ft.get('w', 1.0)
        fk = [J[n + sd].rotation_euler.copy() for n in ('hip', 'knee', 'ankle')]
        mech.leg_ik(M, sd, tuple(ft['p']), ft.get('yaw', 0.0), ft.get('pitch', 0.0), ft.get('roll', 0.0), ft.get('pole'))
        if w < 0.999:
            for n, e0 in zip(('hip', 'knee', 'ankle'), fk):
                q = e0.to_quaternion().slerp(J[n + sd].rotation_euler.to_quaternion(), w); J[n + sd].rotation_euler = q.to_euler('XYZ', e0)
    for sd in ('L', 'R'):
        a = D['arms'].get(sd)
        if a is None: continue
        pos, rot, pole, w = a
        fk = [J[n + sd].rotation_euler.copy() for n in ('shoulder', 'elbow', 'wrist')]
        mech.arm_ik(M, sd, tuple(pos), pole=None if pole is None else tuple(pole), hand_rot=None if rot is None else Matrix([list(r) for r in rot]))
        if w < 0.999:
            for n, e0 in zip(('shoulder', 'elbow', 'wrist'), fk):
                q = e0.to_quaternion().slerp(J[n + sd].rotation_euler.to_quaternion(), w); J[n + sd].rotation_euler = q.to_euler('XYZ', e0)
    lk = D.get('look')
    if lk is not None and lk[1] > 1e-3: _look_at(M, mech, lk[0], lk[1], lk[2] if len(lk) > 2 else 0.4)
    mech._aim_pistons(M)
    return D


LOOK_MAX = (38.0, 30.0)       # the head may turn at most this much off the neck, the neck this much off the chest (deg)
LOOK_KNEE = 0.35              # the limits are soft: the last 35 % of each eases onto it (C1, no kink when a limit starts to bite)


def _soft_cap(x, lim, knee):
    """x as is up to lim - knee, then easing onto lim (value and slope continuous: a turn that runs into a limit slows to it)."""
    x0 = lim - knee
    if knee <= 0.0 or x <= x0: return min(x, lim)
    return x0 + knee * (1.0 - math.exp(-(x - x0) / knee))


class _LB:
    """a look target blended between two others (points or blends) by direction from the head (slerp) and distance (geometric),
    not by position: a near point and a far one mixed by position drag the line of sight past the face (05.11: the head whipped
    15 deg a frame at 69.6 and 81.2 as the blend swept by it)."""
    __slots__ = ('a', 'b', 'k')

    def __init__(self, a, b, k): self.a, self.b, self.k = a, b, k


def _lmix(a, b, k):
    if k <= 0.0: return a
    if k >= 1.0: return b
    return _LB(a, b, k)


def _look_point(tg, head):
    """the world point of a look target (a point or an _LB) seen from the head."""
    head = np.asarray(head, float)
    if not isinstance(tg, _LB): return np.asarray(tg, float)
    pa = _look_point(tg.a, head) - head; pb = _look_point(tg.b, head) - head; k = tg.k
    na, nb = float(np.linalg.norm(pa)), float(np.linalg.norm(pb))
    if na < 1e-6 or nb < 1e-6: return head + pa * (1 - k) + pb * k
    ua, ub = pa / na, pb / nb; om = math.acos(max(-1.0, min(1.0, float(np.dot(ua, ub)))))
    if om < 1e-6: u = ua
    elif math.sin(om) < 1e-3: u = ua * (1 - k) + ub * k; u = u / max(float(np.linalg.norm(u)), 1e-9)
    else: u = (math.sin((1 - k) * om) * ua + math.sin(k * om) * ub) / math.sin(om)
    return head + u * math.exp(math.log(na) * (1 - k) + math.log(nb) * k)


def _aim_rot(Rp, d, lim):
    """local rotation (3x3, mathutils) of a joint whose parent world rotation is Rp so that its -Y points along world d, limited to
    `lim` degrees off the parent's own -Y (the shortest arc, so no roll is introduced)."""
    bpy, Matrix, Vector, Euler, Quaternion = _bpy()
    dl = (Rp.inverted() @ Vector(d)).normalized()
    f0 = Vector((0.0, -1.0, 0.0)); q = f0.rotation_difference(dl)
    ang = q.angle; lr = math.radians(lim); a2 = _soft_cap(ang, lr, LOOK_KNEE * lr)
    if a2 < ang - 1e-9: q = Quaternion(q.axis, a2)
    return q.to_matrix()


LOOK_UP_MAX = 24.0            # a look target is lowered to at most this elevation above the chest's own horizon (deg)


def _look_cap(Wc, head_pos, target):
    """the target lowered (same azimuth in the chest frame) so its elevation over the chest's horizon is at most LOOK_UP_MAX (soft)."""
    Rc = np.array(Wc.to_3x3().normalized()); d = np.asarray(target, float) - np.asarray(head_pos, float); n = float(np.linalg.norm(d))
    if n < 1e-6: return target
    dc = Rc.T @ (d / n); el = math.degrees(math.asin(max(-1.0, min(1.0, dc[2]))))
    el2 = _soft_cap(el, LOOK_UP_MAX, LOOK_KNEE * LOOK_UP_MAX)
    if el2 >= el - 1e-9: return target
    h = np.array((dc[0], dc[1], 0.0)); hn = float(np.linalg.norm(h)); h = h / hn if hn > 1e-6 else np.array((0.0, -1.0, 0.0))
    e = math.radians(el2); dc2 = h * math.cos(e) + np.array((0.0, 0.0, math.sin(e)))
    return np.asarray(head_pos, float) + (Rc @ dc2) * n


def _look_at(M, mech, target, w, neck_share):
    """turn the neck (share) and the head toward a world point, blended by w over their FK rotations."""
    bpy, Matrix, Vector, Euler, Quaternion = _bpy()
    J = M['joints']
    hp = tuple(mech._wm(J['head']).translation)
    target = _look_cap(mech._wm(J['chest']), hp, _look_point(target, hp))
    for jn, share, lim in (('neck', neck_share, LOOK_MAX[1]), ('head', 1.0, LOOK_MAX[0])):
        j = J[jn]; Wj = mech._wm(j); Rp = (mech._wm(j.parent).to_3x3() if j.parent is not None else Matrix.Identity(3)).normalized()
        cur = Wj.to_3x3().normalized()
        d = Vector(tuple(target)) - Wj.translation
        if d.length < 1e-6: continue
        want = cur @ _aim_rot(cur, d.normalized(), lim * share if jn == 'neck' else lim)     # extra rotation in the joint's own frame
        if jn == 'neck':        # only a share of the turn goes into the neck
            qa = cur.to_quaternion(); qb = want.to_quaternion(); want = qa.slerp(qb, share).to_matrix()
        loc = (Rp.inverted() @ want).to_quaternion()
        e0 = j.rotation_euler.copy(); q0 = e0.to_quaternion()
        j.rotation_euler = q0.slerp(loc, w).to_euler('XYZ', e0)


def _objs(M):
    """tracked name -> object."""
    P = M['parts']; J = M['joints']; out = {'root': M['root']}
    for n in TRACKED:
        if n in J: out[n] = J[n]
        elif n in P: out[n] = P[n]
    if M.get('nest') is not None: out['nest'] = M['nest']
    if M.get('gull'): out['gull'] = M['gull']['root']
    if M.get('chick') is not None: out['chick'] = M['chick']
    return out


def _np(m): return np.array([[m[i][j] for j in range(4)] for i in range(4)], np.float64)


def _new_track(M):
    anim = M['anim']; n = len(anim); F = NF + 1; nv = len(M['vines'])
    return {'names': np.array([o.name for o in anim]), 'loc': np.zeros((F, n, 3), np.float32), 'rot': np.zeros((F, n, 3), np.float32),
            'props': np.zeros((F, 3), np.float32), 'valid': np.zeros(F, bool),
            'tracked': np.array(TRACKED), 'W': np.zeros((F, len(TRACKED), 4, 4), np.float32),
            'gull_vis': np.ones(F, np.float32), 'gull_loc': np.zeros((F, 3), np.float32), 'gull_rot': np.zeros((F, 3), np.float32),
            'wing': np.zeros((F, 2, 3), np.float32), 'chick_rot': np.zeros((F, 3), np.float32),
            'vine_names': np.array([v.name for v in M['vines']]), 'vine_vis': np.ones((F, nv), np.float32),
            'vine_loc': np.zeros((F, nv, 3), np.float32), 'vine_rot': np.zeros((F, nv, 3), np.float32)}


def bake(M, mech, f0=1, f1=NF, out=TRACK):
    """solve frames f0..f1 and merge them into the track file."""
    bpy, Matrix, Vector, Euler, Quaternion = _bpy()
    anim = M['anim']
    TR = None
    if os.path.exists(out):
        d = np.load(out); TR = {k: np.array(d[k]) for k in d.files}
        if list(TR['names']) != [o.name for o in anim] or list(TR['tracked']) != TRACKED: TR = None
    if TR is None: TR = _new_track(M)
    obj = _objs(M)
    G = M['gull']; gull, wL, wR = G['root'], G['wingL'], G['wingR']; chick = M['chick']; nest = M['nest']
    g_rest = gull.matrix_basis.copy(); c_rest = chick.matrix_basis.copy()
    fold = {'L': Euler(tuple(wL['fold']), 'XYZ'), 'R': Euler(tuple(wR['fold']), 'XYZ')}
    v_rest = [(v.location.copy(), v.rotation_euler.copy()) for v in M['vines']]
    # the gull's standing world frame (sleep pose)
    mech.set_pose(M, design(0.0, mech)['pose'])
    Nw0 = mech._wm(nest); Gw0 = Nw0 @ g_rest
    prepare(M, mech)
    lo = fr(T_RISE) + 1; hi = max(f1, max(fr(x[0]) for x in VINE_TEAR.values()) + 2)
    if hi >= max(f0, lo):
        bad = pelvis_pass(mech, max(lo, min(f0, fr(min(x[0] for x in VINE_TEAR.values()))) - 12), hi)
        if bad: print('PELVIS BAND CONFLICTS', len(bad), bad[:12], flush=True)
    VL = vine_locals(M); v_rest_m = {v.name: v.matrix_basis.copy() for v in M['vines']}
    VT = vine_tears(M, mech, VL)
    gp0 = np.array(Gw0.translation); gf0 = -np.array(Gw0.to_3x3().col[1]); gf0[2] = 0.0; gf0 /= np.linalg.norm(gf0)
    vprev = {}
    prev = {}
    NWD = {}             # frame -> (nest world, chick) for the gull's drawings on twos
    t_start = time.time()
    for f in range(max(1, f0), min(NF, f1) + 1):
        t = tof(f)
        solve(M, mech, t)
        for i, o in enumerate(anim):
            e = o.rotation_euler.copy()
            if o.name in prev: e.make_compatible(prev[o.name])
            prev[o.name] = e
            TR['loc'][f, i] = tuple(o.location); TR['rot'][f, i] = tuple(e)
        TR['props'][f] = (eyes(t), beacon(t), lamps(t))
        # the gull + the chick (local to the nest)
        Nw = mech._wm(nest)
        NWD[f] = (Nw.copy(), np.array(mech._wm(M['chick']).translation) if M.get('chick') is not None else None)
        if t < T_GULL_OFF:
            L = g_rest @ Matrix.Rotation(math.radians(gull_idle_yaw(t)), 4, 'Z'); vis = 1.0; wl = fold['L'].copy(); wr = fold['R'].copy()
        elif t < T_GULL_GONE:
            p, fw, up, flap, spread = gull_flight(twos(t), gp0, gf0)
            Rw = bird_frame(fw, up); Gw = Matrix.Translation(Vector(tuple(p))) @ Matrix([list(r) for r in Rw]).to_4x4()
            L = Nw.inverted() @ Gw; vis = 1.0
            a = math.radians(flap)
            wl = Euler(tuple(x * (1 - spread) for x in fold['L']), 'XYZ'); wl.y += -a * spread
            wr = Euler(tuple(x * (1 - spread) for x in fold['R']), 'XYZ'); wr.y += a * spread
        elif t < T_GULL_IN:
            L = g_rest; vis = 0.0; wl = fold['L'].copy(); wr = fold['R'].copy()
        else:
            L, vis, wl, wr = _gull_return(t, M, mech, g_rest, fold, Nw, NWD.get(fr(twos(t))))
        TR['gull_vis'][f] = vis
        TR['gull_loc'][f] = tuple(L.translation); TR['gull_rot'][f] = tuple(L.to_euler('XYZ'))
        TR['wing'][f, 0] = tuple(wl); TR['wing'][f, 1] = tuple(wr)
        TR['chick_rot'][f] = (math.radians(chick_peep(t)), 0.0, 0.0)
        vis = vine_pose(M, mech, t, VT, VL, v_rest_m)
        for k, v in enumerate(M['vines']):
            e = v.matrix_basis.to_euler('XYZ')
            if v.name in vprev: e.make_compatible(vprev[v.name])
            vprev[v.name] = e
            TR['vine_vis'][f, k] = vis[v.name]
            TR['vine_loc'][f, k] = tuple(v.matrix_basis.translation); TR['vine_rot'][f, k] = tuple(e)
        # world matrices of the tracked parts (the overgrowth posed as keyed)
        gull.matrix_basis = L; chick.matrix_basis = c_rest @ Matrix.Rotation(float(TR['chick_rot'][f][0]), 4, 'X')
        for k, nm in enumerate(TRACKED):
            o = obj.get(nm)
            if o is not None: TR['W'][f, k] = _np(mech._wm(o))
        gull.matrix_basis = g_rest; chick.matrix_basis = c_rest
        for v in M['vines']: v.matrix_basis = v_rest_m[v.name]
        TR['valid'][f] = True
        if f % 240 == 0: print('bake f %d  %.1fs' % (f, time.time() - t_start), flush=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez_compressed(out, **TR)
    _CACHE.clear()
    print('BAKED %d..%d -> %s (%.1fs)' % (f0, f1, out, time.time() - t_start))
    return TR


def prepare(M, mech):
    """facts the design reads from the rig: the sleep pose's sole frames and hands (numpy rig == Blender's, checked to 0.01 m)."""
    prepare_np(mech.POSES)


def _gull_return(t, M, mech, g_rest, fold, Nw, draw=None):
    """(local matrix to the nest, vis, wing L euler, wing R euler) of the gull coming home at t (gull_home on twos; the wings as
    the flee: the fold scaled by 1 - spread, the flap about the wing's Y). draw = (nest world, chick) at the drawing's own frame:
    the flight is aimed from where the nest was when the drawing was made, so a drawing holds still in the world on its second
    frame (aimed from the nest now, it crept 5..8 mm with the breathing head: QA s42 read the flight on twos as teleports)."""
    bpy, Matrix, Vector, Euler, Quaternion = _bpy()
    if draw is not None: R0w = draw[0] @ g_rest; pc = draw[1]
    else:
        R0w = Nw @ g_rest
        pc = np.array(mech._wm(M['chick']).translation) if M.get('chick') is not None else None
    o = gull_home(twos(t), np.array(R0w.translation), np.array(R0w.to_3x3()), pc)
    Rw = bird_frame(o['fwd'], o['up'])
    L = Nw.inverted() @ (Matrix.Translation(Vector(tuple(o['p']))) @ Matrix([list(r) for r in Rw]).to_4x4())
    a = math.radians(o['flap']); sp = o['spread']
    wl = Euler(tuple(x * (1 - sp) for x in fold['L']), 'XYZ'); wl.y += -a * sp
    wr = Euler(tuple(x * (1 - sp) for x in fold['R']), 'XYZ'); wr.y += a * sp
    return L, 1.0, wl, wr


# ===================================================================================================================== contacts
def allow(a, b, t=None):
    """designed contacts at t (default: the scene's frame). Asleep: mech.qa_allow (the overgrowth settled on the body and the floor).
    Awake: a growth piece (moss, vine, nest, bird) may touch only the parts of its own rigid segment; the rest as mech.qa_allow."""
    import mech
    if t is None:
        bpy = _bpy()[0]; t = tof(bpy.context.scene.frame_current)
    if t > T_RISE and ('_vine_' in a.name or '_vine_' in b.name): return True   # the vines awake: shots/vineqa.py (depth vs the sleep pose)
    if t > T_RISE and 'growth' in (a.get('kind'), b.get('kind')):
        return str(a.get('seg')) == str(b.get('seg'))
    return mech.qa_allow(a, b)


# ===================================================================================================================== the vines
# Torn off in the rise on the score's tears (49.3 / 50.0 / 50.7 / 51.5). From its tear on a vine flies as one rigid piece: half its
# host's velocity at the tear (it drags) + a kick out from the body and up, gravity, a slow tilt outward about its centroid; hidden
# once all of it is under the water (or VINE_LIFE s after the tear).
VINE_TEAR = {  # name: (t, kick (out, y, z) m/s with out = away from the body's mid-plane, tilt rad/s (+ = the lower end swings out
    # about the top), share of the host's velocity it keeps, horizontal drag time constant s (0 = none)).
    # Chosen by shots/vineqa.py -- search: each one clean on its host until the tear and in flight until it is under the water.
    # 49.3 the arms tear free; 50.0 the head jerks up as the body starts to climb; 51.5 it straightens (the chest vines, the last one).
    'pauldronL_b': (49.3, (0.0, -14.0, -10.0), 0.0, 1.0, 0.0), 'pauldronR_a': (49.3, (0.0, 0.0, -15.0), 0.0, 0.5, 0.0),
    'pauldronR_b': (49.3, (0.0, -14.0, -10.0), 0.0, 1.0, 0.0), 'flapR': (49.3, (8.0, 0.0, -6.0), 0.6, 0.5, 0.0),
    'forearmL': (49.3, (8.0, 0.0, -6.0), 0.6, 0.5, 0.0), 'forearmR': (49.3, (0.0, -14.0, -10.0), -0.6, 0.5, 0.0),
    'belt': (49.3, (-6.0, 0.0, -8.0), 0.0, 1.0, 0.0),
    'jaw': (50.0, (0.0, -25.0, 6.0), 0.0, 0.5, 0.0),
    'pauldronL_a': (51.5, (0.0, -14.0, -10.0), 0.6, 0.5, 0.0), 'chestL': (51.5, (0.0, -14.0, -10.0), 0.0, 0.5, 0.0),
    'chestR': (51.5, (0.0, -14.0, -10.0), 0.0, 0.5, 0.0), 'kneeL': (51.5, (0.0, 0.0, -15.0), -0.6, 0.5, 0.0)}
VINE_G = 30.0
VINE_DRAG = float(os.environ.get('VINE_DRAG', '1.0'))   # s: the horizontal drag time constant
VINE_LIFE = 4.5


def vine_key(name): return name[len('MECH_vine_'):] if name.startswith('MECH_vine_') else name


def _rodrigues(axis, ang):
    a = np.asarray(axis, float); n = float(np.linalg.norm(a))
    if n < 1e-9 or abs(ang) < 1e-12: return np.eye(3)
    a = a / n; K = np.array(((0, -a[2], a[1]), (a[2], 0, -a[0]), (-a[1], a[0], 0)))
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)


def vine_tears(M, mech, V_local):
    """{vine object name: dict(t, W0 world 4x4 at the tear, v0 world velocity of its centroid, axis = the chest's xy, c = local
    centroid)}. Solves the design at each tear (and a frame before): call it before a frame loop (it leaves the rig posed)."""
    J = M['joints']; out = {}; by_t = {}
    for v in M['vines']:
        spec = VINE_TEAR.get(vine_key(v.name))
        if spec is not None: by_t.setdefault(spec[0], []).append(v)
    for tt, vs in sorted(by_t.items()):
        solve(M, mech, tt - 1.0 / FPS); A = {v.name: _np(mech._wm(v)) for v in vs}
        solve(M, mech, tt); axis = np.array(_np(mech._wm(J['chest']))[:2, 3])
        for v in vs:
            W0 = _np(mech._wm(v)); c = V_local[v.name].mean(0)
            v0 = ((W0[:3, :3] @ c + W0[:3, 3]) - (A[v.name][:3, :3] @ c + A[v.name][:3, 3])) * FPS
            out[v.name] = dict(t=tt, W0=W0, v0=v0, axis=axis, c=c)
    return out


def vine_flight(t, VT, name, V_local=None, spec=None):
    """(world 4x4 of a torn vine at t or None while it is on its host, visibility 1/0). The vine keeps its shape: its top (origin)
    flies with the centroid's ballistic path, the vine turns about the top (the rise faces -Y: 'out' is +-X)."""
    spec = spec or VINE_TEAR.get(vine_key(name)); d = VT.get(name)
    if spec is None or d is None or t < d['t']: return None, 1.0
    tau = t - d['t']; W0 = d['W0']; c0 = W0[:3, :3] @ d['c'] + W0[:3, 3]
    sx = 1.0 if c0[0] > d['axis'][0] else -1.0
    k = spec[1]; vel = spec[3] * d['v0'] + np.array((k[0] * sx, k[1], k[2]))
    T = spec[4] if len(spec) > 4 else VINE_DRAG               # horizontal air drag time constant (0 = none), plain gravity
    hx = T * (1.0 - math.exp(-tau / T)) if T and T > 0 else tau
    dc = np.array((vel[0] * hx, vel[1] * hx, vel[2] * tau - 0.5 * VINE_G * tau * tau))
    R = _rodrigues(np.cross(np.array((0.0, 0.0, 1.0)), np.array((sx, 0.0, 0.0))), -spec[2] * tau) @ W0[:3, :3]
    W = np.eye(4); W[:3, :3] = R; W[:3, 3] = W0[:3, 3] + dc
    vis = 1.0
    if tau > VINE_LIFE: vis = 0.0
    elif V_local is not None:
        Vw = V_local @ R.T + W[:3, 3]; k = int(np.argmax(Vw[:, 2]))
        if Vw[k, 2] < MP.water_z(float(Vw[k, 0]), float(Vw[k, 1]), t) + VINE_SUNK: vis = 0.0
    return W, vis


VINE_SUNK = -0.6        # hidden once its highest point is this far under the water


def vine_locals(M):
    """{vine object name: its evaluated vertices in its own frame}."""
    bpy = _bpy()[0]; dg = bpy.context.evaluated_depsgraph_get(); out = {}
    for v in M['vines']:
        ev = v.evaluated_get(dg); me = ev.to_mesh(); out[v.name] = np.array([x.co[:] for x in me.vertices], np.float64); ev.to_mesh_clear()
    return out


def vine_pose(M, mech, t, VT, VL, rest):
    """put every vine where it is at t (on its host = its rest basis, or flying); -> {name: visible}."""
    bpy, Matrix, Vector, Euler, Quaternion = _bpy(); vis = {}
    for v in M['vines']:
        W, vs = vine_flight(t, VT, v.name, VL.get(v.name))
        if W is None: v.matrix_basis = rest[v.name]
        else:
            Pw = _np(mech._wm(v.parent)); v.matrix_basis = Matrix((np.linalg.inv(Pw) @ W).tolist())
        vis[v.name] = vs
    return vis


# ===================================================================================================================== film keying
_CACHE = {}


def load(path=TRACK):
    if path not in _CACHE:
        d = np.load(path, allow_pickle=False); _CACHE[path] = {k: d[k] for k in d.files}
    return _CACHE[path]


def key_range(W, f0, f1, src=None):
    """key the mech for frames f0..f1 from the track (every frame: the mech moves on ones, in step with the chain).
    src: optional frame -> track frame map (the lab keys other moments onto spare frames)."""
    M = W.get('mech')
    if not M: return
    TR = load(); TL = W['TL']
    names = list(TR['names']); anim = M['anim']
    assert [o.name for o in anim] == names, 'mech rig changed since the bake'
    props = M['props']; G = M['gull']; vines = M['vines']
    for f in range(f0, f1 + 1):
        g = min(max(f if src is None else src(f), 1), NF)
        if not TR['valid'][g]: raise RuntimeError('mech track: frame %d not baked' % g)
        for i, o in enumerate(anim):
            TL.loc(o, f, tuple(float(x) for x in TR['loc'][g, i])); TL.eul(o, f, tuple(float(x) for x in TR['rot'][g, i]))
        e, b, l = (float(x) for x in TR['props'][g])
        for o in props['eyes']: TL.prop(o, 'eyes', f, e)
        for o in props['beacon']: TL.prop(o, 'beacon', f, b)
        for o in props['lamps']: TL.prop(o, 'lamps', f, l)
        gv = TR['gull_vis'][g] < 0.5
        TL.loc(G['root'], f, tuple(float(x) for x in TR['gull_loc'][g])); TL.eul(G['root'], f, tuple(float(x) for x in TR['gull_rot'][g]))
        TL.hide(G['root'], f, gv)
        for k, w in enumerate((G['wingL'], G['wingR'])):
            TL.eul(w, f, tuple(float(x) for x in TR['wing'][g, k])); TL.hide(w, f, gv)
        c = M['chick']; TL.eul(c, f, _chick_eul(c, float(TR['chick_rot'][g][0])))
        for k, v in enumerate(vines):
            TL.hide(v, f, TR['vine_vis'][g, k] < 0.5)
            TL.loc(v, f, tuple(float(x) for x in TR['vine_loc'][g, k])); TL.eul(v, f, tuple(float(x) for x in TR['vine_rot'][g, k]))


_CHICK0 = {}


def _chick_eul(c, peep):
    bpy, Matrix, Vector, Euler, Quaternion = _bpy()
    if c.name not in _CHICK0: _CHICK0[c.name] = c.matrix_basis.copy()
    m = _CHICK0[c.name] @ Matrix.Rotation(peep, 4, 'X')
    return tuple(m.to_euler('XYZ'))


# ===================================================================================================================== queries
def mat(name, t):
    """4x4 world matrix of a tracked part at t (position linear between frames)."""
    TR = load(); k = list(TR['tracked']).index(name)
    x = t * FPS + 1; f = int(math.floor(x)); u = x - f
    a = TR['W'][min(max(f, 1), NF), k].astype(float); b = TR['W'][min(max(f + 1, 1), NF), k].astype(float)
    m = a.copy(); m[:3, 3] = a[:3, 3] * (1 - u) + b[:3, 3] * u
    return m


def point(name, t, local=(0.0, 0.0, 0.0)):
    m = mat(name, t); return m[:3, :3] @ np.asarray(local, float) + m[:3, 3]


def fwd(name, t):
    m = mat(name, t); v = -m[:3, 1]; return v / np.linalg.norm(v)


def gull_world(t): return point('gull', t)
def head_pos(W, t): return point('head', t)
def head_fwd(W, t): return fwd('head', t)


# ===================================================================================================================== command line
def _args():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def _build_mech():
    import env as EV, mech
    sc = EV.reset()
    C = EV.coll('MECH')
    t0 = time.time(); M = mech.build(C); print('mech built %.1fs' % (time.time() - t0), flush=True)
    return sc, M, mech


if __name__ == '__main__':
    A = _args()
    if A and A[0] == 'bake':
        f0, f1 = 1, NF
        if len(A) > 1: f0, f1 = (int(x) for x in A[1].split('-'))
        sc, M, mech = _build_mech()
        bake(M, mech, f0, f1)
