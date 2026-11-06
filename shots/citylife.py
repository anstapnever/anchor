# ANCHOR — High Harbor's own life (SKY department). city_life(W, f0, f1) keys everything in the city that moves, for any frame
# range, as a pure function of film time t (no state carried between calls; caches below only hold build-time rest data and
# deterministic tables). common.city_key calls it for every shot that shows the city. It never raises.
#   sails     turn with the wind (brisk at dawn, faster with story.storm, wild in s09), three are ripped off by the waterspout
#             (79.25 / 79.6 / 80.0) and fly away tumbling, the rest turn calmly again after 82
#   cloth     laundry swings out with the wind and ripples (Wave modifier phase + height keyed); ten pieces torn away in s09
#   bell      alarm swing 18.1 .. 82.6 (clapper lags and strikes the rim, never beyond the rim)
#   vanes     point into the dawn breeze (SE); the western wind front sweeps the city from the west rim (~14.2) to the east
#             rim (~15.1) and swings them round to the west (damped spring), gusting through the storm; they keep west in the
#             world while the city yaws
#   falls     bendX / bendY: the water column hangs plumb while the city tilts, is blown east by the storm wind and trails
#             behind the city's motion; straight again by 84.4
#   crystals  power: shimmer, a jolt at the strikes, a stutter at the lurch, drained (0.4) after it, the flare at 37.4 (a wave
#             up the cone, 0.4 s; act_sky.s19 adds a drawn starburst on the crystals it passes), then glow
#   lamps     'lit' on every lit object as the storm darkens (per-house switch-on times), off again after the storm
#   tiles     slide off their roofs in the lurch (35.25 .. 36.3), fall (world gravity, city frame), hidden where they land
#   rivets    pop 20.15 .. 21.9 along their own axis, tumble away, hidden 1.3 s later
#   houses    a short shudder in the lurch
# Props animate on twos on the global grid (frame f holds the value of f - ((f - 1) % 2)).
import math, zlib, traceback
import numpy as np
from mathutils import Matrix, Vector, Euler, Quaternion
import story as S

FPS = 24
G = 9.81


def tof(f): return (f - 1) / FPS
def twos(f): return f - ((f - 1) % 2)
def sst(x): x = min(1.0, max(0.0, x)); return x * x * (3.0 - 2.0 * x)
def rng(t, a, b): return min(1.0, max(0.0, (t - a) / (b - a)))
def h01(name, k=0): return (zlib.crc32(('%s:%d' % (name, k)).encode()) & 0xffffffff) / 4294967296.0


# --------------------------------------------------------------------------------------------------------------------------- story
TEAR = dict(center=(-50.0, -115.0), radius=16.0, n=10, t0=18.62, t1=19.75)      # s09: laundry torn off at M3's yard
RIP = {2: 79.25, 1: 79.6, 3: 80.0}                                               # mill index -> time its sails are ripped off
RIP_HIDE = 81.9
TILE_T = (35.25, 36.3)
RIVET_T = (20.15, 21.9)
LURCH = 35.2


def flash_at(t):
    try:
        import common as CM
        return CM.flash_at(t)
    except Exception:
        return 0.0


_RM = {}
_CV = {}


def root_M(t):
    """4x4 world matrix of CITY_root at t (cached)."""
    k = round(float(t), 6)
    M = _RM.get(k)
    if M is None:
        if len(_RM) > 60000: _RM.clear()
        M = np.eye(4); M[:3, :3] = S.rot_xyz(S.city_tilt(t)); M[:3, 3] = S.city_pos(t); _RM[k] = M
    return M.copy()


def city_vel(t):
    k = round(float(t), 6)
    v = _CV.get(k)
    if v is None:
        if len(_CV) > 60000: _CV.clear()
        v = np.array(S.city_vel(t), float); _CV[k] = v
    return v.copy()


def wind(t, xw=0.0):
    """world wind (blow vector m/s, 3d) at film time t and world x: a light SE breeze at dawn; the westerly front sweeps
    across from the west at ~14 s; storm-strong with gusts; easing after 81."""
    t_arr = 14.15 + 1.0 * min(1.0, max(0.0, (xw + 350.0) / 340.0))       # west rim ~14.2, mid-town ~14.5, east rim ~15.1 (score: vanes squeak 14.3 / 15.1)
    k = sst(rng(t, t_arr - 0.15, t_arr + 0.45))
    dawn = np.array((-0.62, 0.78, 0.0)) * (1.6 + 0.6 * math.sin(t * 0.7))
    st = S.storm(t)
    gust = 1.0 + 0.22 * math.sin(t * 1.7 - xw * 0.01) + 0.12 * math.sin(t * 3.3 + 1.3)
    spd = (6.0 + 20.0 * st) * gust
    if 18.4 <= t <= 20.2: spd *= 1.0 + 0.35 * sst(rng(t, 18.3, 18.8)) * (1.0 - sst(rng(t, 19.8, 20.2)))   # s09: the gale
    west = np.array((0.99, 0.12, 0.0)); west /= np.linalg.norm(west)
    return dawn * (1.0 - k) + west * spd * k


# ------------------------------------------------------------------------------------------------------------------- rest data
def _rest(W):
    """build-time rest data of the city (root-local matrices, rest rotations), cached per run in W."""
    c = W.get('city')
    R = W.get('_cl_rest')
    if R is not None and R.get('root') is c.get('root'): return R
    root = c['root']; Ri = root.matrix_world.inverted()
    R = {'root': root, 'Ri': Ri}
    def rel(o): return np.array(Ri @ o.matrix_world)
    R['sails'] = []
    for i, sv in enumerate(c.get('sails') or []):
        hub = sv.parent
        R['sails'].append(dict(o=sv, i=i, rot=tuple(sv.rotation_euler), hub=rel(hub) if hub is not None else np.eye(4),
                               ph=h01(sv.name)))
    R['cloth'] = []
    for o in c.get('cloth') or []:
        md = o.modifiers.get('flap')
        M = rel(o)
        Pm = np.array(Ri @ o.parent.matrix_world) if o.parent is not None and o.parent is not root else np.eye(4)
        R['cloth'].append(dict(o=o, loc=tuple(o.location), rot=tuple(o.rotation_euler), M=M, P=Pm,
                               to=md.time_offset if md else 0.0, h=md.height if md else 0.0, sp=md.speed if md else 0.1,
                               md=md is not None, ph=h01(o.name) * 6.283, x14=float(M[0, 3] + S.city_pos(14.0)[0])))
    R['vanes'] = []
    for o in c.get('vanes') or []:
        R['vanes'].append(dict(o=o, rot=tuple(o.rotation_euler), M=rel(o), P=rel(o.parent) if o.parent is not None else np.eye(4),
                               ph=h01(o.name) * 6.283))
    R['falls'] = []
    info = c.get('info') or {}
    fi = info.get('falls') or []
    for k, o in enumerate(c.get('falls') or []):
        d = np.array(fi[k]['dir'][:2], float) if k < len(fi) else np.array((1.0, 0.0))
        d /= max(np.linalg.norm(d), 1e-9)
        drop = abs(float(fi[k]['start'][2] - fi[k]['end'][2])) if k < len(fi) else 300.0
        R['falls'].append(dict(o=o, d=d, side=np.array((-d[1], d[0])), drop=drop, ph=h01(o.name) * 6.283))
    R['crystals'] = [dict(o=o, z=float(rel(o)[2, 3]), ph=h01(o.name) * 6.283) for o in (c.get('crystals') or [])]
    R['lit'] = [dict(o=o, on=h01(o.name, 1), off=h01(o.name, 2)) for o in (c.get('objs') or []) if 'lit' in o.keys()]
    R['tiles'] = [dict(o=o, M=rel(o), rot=tuple(o.rotation_euler), loc=tuple(o.location), i=i) for i, o in enumerate(c.get('tiles') or [])]
    R['rivets'] = [dict(o=o, M=rel(o), rot=tuple(o.rotation_euler), loc=tuple(o.location), i=i) for i, o in enumerate(c.get('rivets') or [])]
    sh = list(c.get('houses') or []) + list(c.get('mills') or [])
    for k in ('campanile', 'church', 'watertower'):
        if c.get(k) is not None: sh.append(c[k])
    R['shake'] = [dict(o=o, loc=tuple(o.location), ph=h01(o.name, 3) * 6.283, a=0.6 + 0.4 * h01(o.name, 4)) for o in sh]
    R['bell'] = c.get('bell'); R['clapper'] = c.get('clapper')
    R['bell_rot'] = tuple(c['bell'].rotation_euler) if c.get('bell') is not None else (0, 0, 0)
    R['clap_rot'] = tuple(c['clapper'].rotation_euler) if c.get('clapper') is not None else (0, 0, 0)
    W['_cl_rest'] = R
    return R


# ------------------------------------------------------------------------------------------------------------------- tables
_TAB = {}


def _sail_omega(t):
    """rev/s of the windmills: a brisk 0.59 at dawn (M4 passes the s02 camera on the score's whooshes, every 0.45 s), faster
    as the storm builds, wild in s09's gale, back to an easy turn after the release. Steps stay < 40 deg per drawing."""
    calm = 0.592 + 0.03 * math.sin(t * 0.5) * sst(rng(t, 14.0, 16.0))
    st = S.storm(t)
    w = calm + 0.42 * sst(rng(st, 0.12, 0.95))
    gust = 0.07 * math.sin(t * 1.9) + 0.05 * math.sin(t * 3.7 + 0.4)
    w += gust * sst(rng(t, 14.0, 16.0))
    wild = sst(rng(t, 18.2, 18.7)) * (1.0 - sst(rng(t, 19.9, 20.6)))
    w += 0.3 * wild
    k = sst(rng(t, 80.8, 83.0))
    return w * (1.0 - k) + (0.42 + 0.02 * math.sin(t * 0.6)) * k


# a sail of mill i points at hub-frame angle ang (deg, from the hub's X toward its Z) at film time t: the sail sweeping past
# the s02 lens lands on the first whoosh of the score (3.0 s)
SAIL_SYNC = {4: (3.0, -108.7)}


def _sail_phase(i, sp, r0y):
    if i not in SAIL_SYNC: return 0.0
    t0, ang = SAIL_SYNC[i]
    want = math.pi / 4 - math.radians(ang)              # an arm's angle in the hub XZ plane is pi/4 + k pi/2 - a
    have = sail_angle(t0) * sp + r0y
    return (want - have) % (math.pi / 2)


def sail_angle(t):
    """integrated sail turn (radians) at t, from a 1/240 s table."""
    if 'sail' not in _TAB:
        dt = 1.0 / 240.0; ts = np.arange(0.0, 96.0, dt)
        w = np.array([_sail_omega(x) for x in ts]) * 2 * math.pi
        a = np.concatenate([[0.0], np.cumsum((w[1:] + w[:-1]) * 0.5 * dt)])
        _TAB['sail'] = (ts, a)
    ts, a = _TAB['sail']
    return float(np.interp(t, ts, a))


def cloth_K(t):
    """integrated flutter clock (s): the Wave modifier phase runs this fast."""
    if 'clothK' not in _TAB:
        dt = 1.0 / 240.0; ts = np.arange(0.0, 96.0, dt)
        def k(x):
            st = S.storm(x)
            v = 1.0 + 1.6 * sst(rng(st, 0.1, 0.9))
            v += 0.9 * sst(rng(x, 18.3, 18.7)) * (1.0 - sst(rng(x, 19.9, 20.4)))
            return v * (1.0 - 0.5 * sst(rng(x, 81.0, 85.0)))
        kv = np.array([k(x) for x in ts])
        K = np.concatenate([[0.0], np.cumsum((kv[1:] + kv[:-1]) * 0.5 * dt)])
        _TAB['clothK'] = (ts, K)
    ts, K = _TAB['clothK']
    return float(np.interp(t, ts, K))


def vane_yaw_table(name, xw_fn):
    """the vane's world yaw (radians) over 0 .. 96 s: a damped spring chasing the wind direction (computed once per vane)."""
    key = ('vane', name)
    if key in _TAB: return _TAB[key]
    dt = 1.0 / 240.0; ts = np.arange(0.0, 96.0, dt)
    ph = h01(name) * 6.283
    psi = np.zeros(len(ts))
    wn, z = 6.5, 0.33
    x = None; v = 0.0
    for i, t in enumerate(ts):
        b = wind(t, xw_fn(t))
        tgt = math.atan2(-b[1], -b[0])              # the arrow points into the wind
        if tgt > 0.5: tgt -= 2 * math.pi            # the swing goes clockwise (through south) from SE to W
        tgt += math.radians(3.0) * math.sin(t * 0.8 + ph) + math.radians(9.0) * S.storm(t) * (math.sin(t * 1.4 + ph) + 0.6 * math.sin(t * 3.1 + 2 * ph))
        if x is None: x = tgt
        if t < 12.0:
            x = tgt; v = 0.0
        else:
            a = wn * wn * (tgt - x) - 2 * z * wn * v
            v += a * dt; x += v * dt
        psi[i] = x
    _TAB[key] = (ts, psi)
    return _TAB[key]


# ------------------------------------------------------------------------------------------------------------------- keying
class _Keys:
    """keys through the shot Store: always the first frame of the range, afterwards only when the value changes (CONSTANT
    keys make that identical to keying every frame)."""
    def __init__(s, TL, f0): s.TL = TL; s.f0 = f0; s.last = {}

    def _skip(s, k, f, v):
        if f != s.f0 and s.last.get(k) == v: return True
        s.last[k] = v; return False

    def loc(s, o, f, v):
        v = tuple(round(float(x), 5) for x in v)
        if not s._skip((o.name, 'loc'), f, v): s.TL.loc(o, f, v)

    def eul(s, o, f, v):
        v = tuple(round(float(x), 6) for x in v)
        if not s._skip((o.name, 'eul'), f, v): s.TL.eul(o, f, v)

    def prop(s, o, name, f, v):
        v = round(float(v), 5)
        if not s._skip((o.name, 'p', name), f, v): s.TL.prop(o, name, f, v)

    def path(s, idb, path, f, v):
        v = round(float(v), 5)
        if not s._skip((idb.name, 'path', path), f, v): s.TL.set(idb, path, f, v)

    def hide(s, o, f, h):
        h = bool(h)
        if not s._skip((o.name, 'hide'), f, h): s.TL.hide(o, f, h)


def _mat_to_loc_eul(M, prev=None):
    Mm = Matrix([list(r) for r in M])
    loc, q, sc = Mm.decompose()
    e = q.to_euler('XYZ', prev) if prev is not None else q.to_euler('XYZ')
    return tuple(loc), e


def _rot_axis(axis, ang):
    axis = np.asarray(axis, float); axis = axis / max(np.linalg.norm(axis), 1e-12)
    return np.array(Matrix.Rotation(ang, 3, Vector(axis)))


# ------------------------------------------------------------------------------------------------------------------- the city BVH
def _region_bvh(W, lo, hi, skip=('cloth', 'line', 'tile', 'fall', 'crystal', 'root', 'sails', 'vane', 'bell', 'empty', 'collar', 'lug', 'rock')):
    from mathutils.bvhtree import BVHTree
    key = ('bvh', tuple(round(x, 1) for x in lo), tuple(round(x, 1) for x in hi))
    if key in W.setdefault('_cl_bvh', {}): return W['_cl_bvh'][key]
    c = W['city']; Ri = _rest(W)['Ri']
    V = []; F = []
    for o in c.get('objs') or []:
        if o.type != 'MESH' or o.get('qa') in skip: continue
        M = Ri @ o.matrix_world
        bb = [M @ Vector(x) for x in o.bound_box]
        if any(min(p[i] for p in bb) > hi[i] or max(p[i] for p in bb) < lo[i] for i in range(3)): continue
        me = o.data; base = len(V)
        V.extend(M @ v.co for v in me.vertices)
        F.extend(tuple(base + i for i in p.vertices) for p in me.polygons)
    t = BVHTree.FromPolygons(V, F) if F else None
    W['_cl_bvh'][key] = t
    return t


def _first_hit(bvh, pts, k0=0):
    """index of the first segment pts[k] -> pts[k+1] (k >= k0) that hits the BVH, or None."""
    if bvh is None: return None
    for k in range(k0, len(pts) - 1):
        a = Vector(pts[k]); b = Vector(pts[k + 1]); d = b - a; L = d.length
        if L < 1e-6: continue
        h = bvh.ray_cast(a, d / L, L)
        if h[0] is not None: return k
    return None


# ================================================================================================================= elements
def _sails(W, R, K, frames, T):
    for s in R['sails']:
        o = s['o']; i = s['i']; r0 = s['rot']
        sp = 0.92 + 0.16 * s['ph']
        trip = RIP.get(i)
        hub = s['hub']
        fly = None
        if trip is not None:
            # world matrix of the sails at the rip, then a tumbling flight toward the waterspout
            a_r = sail_angle(trip) * sp + r0[1] + _sail_phase(i, sp, r0[1])
            M0 = root_M(trip) @ hub @ np.array(Matrix.Rotation(a_r, 4, 'Y'))
            sp_ = S.spout_pos(trip)
            p0 = M0[:3, 3]
            dsp = (np.array((sp_[0], sp_[1], p0[2])) - p0) if sp_ is not None else np.array((-1.0, -1.0, 0.0))
            dsp[2] = 0.0; dsp /= max(np.linalg.norm(dsp), 1e-9)
            tang = np.array((-dsp[1], dsp[0], 0.0))
            v0 = city_vel(trip) + dsp * (14.0 + 6.0 * s['ph']) + tang * 9.0 + np.array((0.0, 0.0, 11.0))
            acc = dsp * 16.0 + tang * 10.0 + np.array((0.0, 0.0, -3.0))
            ax = np.array((0.3, 1.0, 0.5)) + (s['ph'] - 0.5); w_t = 3.2 + 2.0 * s['ph']
            w_spin = 2 * math.pi * _sail_omega(trip) * sp
            fly = (M0, p0, v0, acc, ax, w_t, w_spin, trip)
        prev = None
        for f in frames:
            t = T[f]
            if fly is not None and t >= fly[7]:
                M0, p0, v0, acc, ax, w_t, w_spin, tr = fly
                tau = t - tr
                hide = t >= min(tr + 2.4, RIP_HIDE)
                p = p0 + v0 * tau + 0.5 * acc * tau * tau
                Rw = _rot_axis(ax, w_t * tau) @ M0[:3, :3] @ np.array(Matrix.Rotation(w_spin * tau * math.exp(-tau * 0.8), 3, 'Y'))
                Mw = np.eye(4); Mw[:3, :3] = Rw; Mw[:3, 3] = p
                Ml = np.linalg.inv(root_M(t) @ hub) @ Mw
                loc, e = _mat_to_loc_eul(Ml, prev); prev = e
                K.loc(o, f, loc); K.eul(o, f, tuple(e)); K.hide(o, f, hide)
            else:
                a = sail_angle(t) * sp + r0[1] + _sail_phase(i, sp, r0[1])
                K.loc(o, f, (0.0, 0.0, 0.0)); K.eul(o, f, (r0[0], a, r0[2])); K.hide(o, f, False)


def _bell(W, R, K, frames, T):
    bell = R['bell']; clap = R['clapper']
    if bell is None: return
    b0 = R['bell_rot']; c0 = R['clap_rot']
    P = 1.42
    for f in frames:
        t = T[f]
        A = math.radians(37.0) * sst(rng(t, 18.1, 18.85)) * (1.0 - sst(rng(t, 81.2, 82.8)))
        th = 2 * math.pi * (t - 18.1) / P
        a = A * math.sin(th)
        K.eul(bell, f, (b0[0], b0[1] + a, b0[2]))
        if clap is not None:
            ca = 0.6 * A * math.sin(th - 0.95) - a
            lim = math.radians(25.5)
            ca = max(-lim, min(lim, ca))
            K.eul(clap, f, (c0[0], c0[1] + ca, c0[2]))


def _vanes(W, R, K, frames, T):
    for v in R['vanes']:
        o = v['o']; P = v['P']; M = v['M']; r0 = v['rot']
        # the front arrives by world x at ~14 s (the city is still moored then): use the rest-time x
        x14 = float((root_M(14.0) @ M)[0, 3])
        ts, psi = vane_yaw_table(o.name, lambda t, x=x14: x)
        for f in frames:
            t = T[f]
            yw = float(np.interp(t, ts, psi))
            Pw = root_M(t) @ P
            pyaw = math.atan2(Pw[1, 0], Pw[0, 0])
            loc_z = yw - pyaw
            # keep near the rest value's branch (continuity of the euler)
            while loc_z - r0[2] > math.pi: loc_z -= 2 * math.pi
            while loc_z - r0[2] < -math.pi: loc_z += 2 * math.pi
            K.eul(o, f, (r0[0], r0[1], loc_z))


def _falls(W, R, K, frames, T):
    def bottom(t, fl):
        Rm = S.rot_xyz(S.city_tilt(t))
        dl = Rm.T @ np.array((0.0, 0.0, -1.0))
        tilt = fl['drop'] * dl[:2] / max(-dl[2], 0.5)
        wv = wind(t, -300.0); stk = sst(rng(S.storm(t), 0.18, 1.0))
        bw = np.array((wv[0], wv[1], 0.0)) * 1.25 * stk
        bw = bw - 0.55 * np.array((*city_vel(t)[:2], 0.0))
        n = np.linalg.norm(bw[:2])
        if n > 48.0: bw *= 48.0 / n
        bl = (Rm.T @ bw)[:2]
        sway = 1.2 * np.array((math.sin(t * 0.45 + fl['ph']), math.sin(t * 0.37 + 2 * fl['ph'])))
        return tilt + bl + sway
    for fl in R['falls']:
        o = fl['o']; sk = o.data.shape_keys
        if sk is None: continue
        kbx = sk.key_blocks.get('bendX'); kby = sk.key_blocks.get('bendY')
        if kbx is None or kby is None: continue
        for kb in (kbx, kby):
            kb.slider_min = -6.0; kb.slider_max = 6.0
        for f in frames:
            t = T[f]
            # the column answers the tilt and the wind with a short lag (exponential kernel over the last ~0.5 s)
            acc = np.zeros(2); ws = 0.0
            for j in range(8):
                w_ = math.exp(-j * 0.45); acc += bottom(t - j * 0.07, fl) * w_; ws += w_
            B = acc / ws
            K.path(sk, 'key_blocks["bendX"].value', f, float(np.dot(B, fl['side']) / 14.0))
            K.path(sk, 'key_blocks["bendY"].value', f, float(np.dot(B, fl['d']) / 10.0))


def _crystals(W, R, K, frames, T):
    for c in R['crystals']:
        o = c['o']; z = c['z']; ph = c['ph']
        for f in frames:
            t = T[f]
            p = 1.0 + 0.06 * math.sin(t * 2.3 + ph)
            fl = flash_at(t)
            if 24.3 < t < 26.0: p += 0.9 * fl
            tf = S.T['crystals'] + (z - 20.0) / 150.0 * 0.4      # the flare runs up the cone from the collar
            if LURCH <= t < 35.9:                       # the levitation stutters: the city drops
                u = (t - LURCH) * 12.0
                p *= 0.35 + 0.65 * (int(u + ph * 3) % 3 == 0)
            elif 35.9 <= t < tf:                        # drained after the drop: a weak pulse until the flare reaches it
                p *= 0.4 + 0.06 * math.sin(t * 5.3 + ph)
            if t >= tf:
                d = t - tf
                p = max(p, 1.42 + 0.68 * math.exp(-d / 0.45) + (0.3 if d < 0.17 else 0.0))
                p += 0.08 * math.sin(t * 3.1 + ph) * sst(rng(d, 0.5, 1.5))
            if t > 81.0: p = p + (1.08 - p) * sst(rng(t, 81.0, 84.0))
            K.prop(o, 'power', f, p)


def _lamps(W, R, K, frames, T):
    for L in R['lit']:
        o = L['o']
        lamp = o.name == 'CITY_lamps'
        for f in frames:
            t = T[f]
            if lamp:
                v = sst(rng(S.storm(t), 0.3, 0.75))
            else:
                ton = 16.5 + 9.0 * L['on']; toff = 82.5 + 4.0 * L['off']
                v = sst(rng(t, ton, ton + 0.25)) * (1.0 - sst(rng(t, toff, toff + 0.25)))
            if v > 0 and (24.4 <= t < 24.9 or LURCH <= t < 35.7):            # brown-outs at the strike and the lurch
                v *= 0.25 + 0.75 * ((int(t * 12) + int(L['on'] * 5)) % 3 != 0)
            K.prop(o, 'lit', f, v)


def _shudder(W, R, K, frames, T):
    for h in R['shake']:
        o = h['o']; l0 = h['loc']; ph = h['ph']; a = h['a']
        for f in frames:
            t = T[f]
            if LURCH <= t < 36.4:
                d = t - LURCH; e = math.exp(-d * 3.2) * a
                off = (0.07 * e * math.sin(d * 61.0 + ph), 0.07 * e * math.sin(d * 53.0 + 2 * ph), 0.035 * e * math.sin(d * 71.0 + 3 * ph))
            else:
                off = (0.0, 0.0, 0.0)
            K.loc(o, f, (l0[0] + off[0], l0[1] + off[1], l0[2] + off[2]))


def _tiles(W, R, K, frames, T):
    tl = R['tiles']
    if not tl: return
    need = any(TILE_T[0] - 0.05 <= T[f] <= TILE_T[1] + 3.5 for f in frames)
    plan = W.get('_cl_tiles')
    if plan is None and need:
        plan = _plan_tiles(W, R); W['_cl_tiles'] = plan
    if not need: plan = None
    for k, d in enumerate(tl):
        o = d['o']
        if plan is None:
            for f in frames:
                hid = T[f] >= TILE_T[0]          # (only reached when no tile frame is in range: then they are long gone)
                K.loc(o, f, d['loc']); K.eul(o, f, d['rot']); K.hide(o, f, hid)
            continue
        P = plan[k]
        prev = None
        for f in frames:
            t = T[f]
            if t < P['t0']:
                K.loc(o, f, d['loc']); K.eul(o, f, d['rot']); K.hide(o, f, False); continue
            Ml = _tile_local(P, t)
            if Ml is None:
                K.hide(o, f, True); continue
            loc, e = _mat_to_loc_eul(Ml, prev); prev = e
            K.loc(o, f, loc); K.eul(o, f, tuple(e)); K.hide(o, f, False)


def _tile_local(P, t):
    """root-local matrix of the tile at t (None = landed / gone)."""
    if t >= P['t_hide']: return None
    M0 = P['M0']
    tau = t - P['t0']
    if tau < P['tau_e']:                                 # sliding down the roof in the city frame
        s = 0.5 * P['a'] * tau * tau
        M = M0.copy(); M[:3, 3] = M0[:3, 3] + P['dn'] * s
        return M
    tf = tau - P['tau_e']
    p = P['pe_w'] + P['ve_w'] * tf + 0.5 * np.array((0.0, 0.0, -G)) * tf * tf
    Rw = _rot_axis(P['ax'], P['w'] * tf) @ P['Re_w']
    Mw = np.eye(4); Mw[:3, :3] = Rw; Mw[:3, 3] = p
    return np.linalg.inv(root_M(t)) @ Mw


def _plan_tiles(W, R):
    """for each tile: detach time, slide to its eave (ray casts on its roof), then the fall; the landing time from segment ray
    casts against the city around it (root-local)."""
    from mathutils.bvhtree import BVHTree
    tl = R['tiles']
    P = np.array([d['M'][:3, 3] for d in tl])
    lo = P.min(0) - np.array((25.0, 25.0, 30.0)); hi = P.max(0) + np.array((25.0, 25.0, 12.0))
    bvh = _region_bvh(W, tuple(lo), tuple(hi))
    out = []
    for k, d in enumerate(tl):
        M0 = d['M'].copy(); p0 = M0[:3, 3]; dn = M0[:3, 1] / np.linalg.norm(M0[:3, 1]); nr = M0[:3, 2] / np.linalg.norm(M0[:3, 2])
        if dn[2] > 0: dn = -dn                                         # down the slope
        h = h01(d['o'].name, 7)
        t0 = TILE_T[0] + (TILE_T[1] - TILE_T[0]) * (0.15 * (k % 3) + 0.85 * h)
        # eave: march down the slope until the roof is no longer under the tile
        se = 0.0
        if bvh is not None:
            for j in range(1, 140):
                s = j * 0.05; q = Vector(p0 + dn * s + nr * 0.6)
                hit = bvh.ray_cast(q, Vector(-nr), 0.9)
                if hit[0] is None: se = s; break
            else: se = 7.0
        se = max(se, 0.15)
        a = 4.2
        tau_e = math.sqrt(2.0 * se / a); ve = a * tau_e
        te = t0 + tau_e
        Mr = root_M(te)
        pe_l = p0 + dn * se
        pe_w = (Mr @ np.array((*pe_l, 1.0)))[:3]
        ve_w = Mr[:3, :3] @ (dn * ve + nr * 0.6) + city_vel(te)
        Re_w = Mr[:3, :3] @ M0[:3, :3]
        ax = Mr[:3, :3] @ (M0[:3, 0] / np.linalg.norm(M0[:3, 0])) + 0.4 * (np.array((h, 1 - h, 0.5)) - 0.5)
        w = (9.0 + 6.0 * h01(d['o'].name, 8)) * (1 if h > 0.5 else -1)
        Pp = dict(M0=M0, dn=dn, a=a, tau_e=tau_e, t0=t0, pe_w=pe_w, ve_w=ve_w, Re_w=Re_w, ax=ax, w=w, t_hide=t0 + tau_e + 2.2)
        # landing: sample the fall in root-local coordinates
        pts = []; ts_ = []
        for j in range(0, 120):
            tt = te + j / 48.0
            if tt > Pp['t_hide']: break
            Ml = _tile_local(dict(Pp, t_hide=1e9), tt)
            pts.append(tuple(Ml[:3, 3])); ts_.append(tt)
        kh = _first_hit(bvh, pts, 2)
        if kh is not None: Pp['t_hide'] = ts_[kh + 1]
        if pts and min(p[2] for p in pts) < 150.0:                      # off the rim: let it fall out of sight first
            pass
        out.append(Pp)
    return out


def rivet_plan(R):
    """per rivet: pop time tp, world position p0 and axis zax at the pop, launch velocity v0, tumble (cached in R)."""
    out = R.get('_rv_plan')
    if out is not None: return out
    out = []
    for d in R['rivets']:
        o = d['o']; k = d['i']; M0 = d['M']
        h = h01(o.name, 11)
        order = [5, 12, 2, 9, 14, 0, 7, 10, 3, 15, 6, 1, 13, 8, 4, 11][k % 16]
        tp = RIVET_T[0] + (RIVET_T[1] - RIVET_T[0]) * (order / 15.0) ** 0.8 + 0.05 * h
        Mr = root_M(tp)
        p0 = (Mr @ M0)[:3, 3]
        zax = Mr[:3, :3] @ (M0[:3, 2] / np.linalg.norm(M0[:3, 2]))
        side = np.cross(zax, np.array((0.0, 0.0, 1.0))); side /= max(np.linalg.norm(side), 1e-9)
        v0 = zax * (15.0 + 8.0 * h) + side * (h - 0.5) * 6.0 + np.array((0.0, 0.0, 3.0 + 3.0 * h)) + city_vel(tp)
        ax = np.array((h, 1.0 - h, 0.3 + h)); w = 18.0 + 10.0 * h01(o.name, 12)
        out.append(dict(o=o, d=d, tp=tp, p0=p0, zax=zax, v0=v0, ax=ax, w=w, R0=(Mr @ M0)[:3, :3]))
    R['_rv_plan'] = out
    return out


def _rivets(W, R, K, frames, T):
    for P in rivet_plan(R):
        o = P['o']; d = P['d']; tp = P['tp']
        prev = None
        for f in frames:
            t = T[f]
            if t < tp:
                K.loc(o, f, d['loc']); K.eul(o, f, d['rot']); K.hide(o, f, False); continue
            tau = t - tp
            if tau > 1.3:
                K.hide(o, f, True); continue
            p = P['p0'] + P['v0'] * tau + 0.5 * np.array((0.0, 0.0, -G)) * tau * tau
            Mw = np.eye(4); Mw[:3, :3] = _rot_axis(P['ax'], P['w'] * tau) @ P['R0']; Mw[:3, 3] = p
            Ml = np.linalg.inv(root_M(t)) @ Mw
            loc, e = _mat_to_loc_eul(Ml, prev); prev = e
            K.loc(o, f, loc); K.eul(o, f, tuple(e)); K.hide(o, f, False)


def cloth_swing(d, t):
    """angle (rad) the piece swings out about its line (its local X) at t: the wind's push across it plus a flutter."""
    Rm = S.rot_xyz(S.city_tilt(t))
    b = wind(t, d['x14'])
    nl = d['M'][:3, 1] / max(np.linalg.norm(d['M'][:3, 1]), 1e-9)
    wn = float(np.dot(Rm.T @ b, nl))
    st = S.storm(t); ph = d['ph']
    flut = math.radians(6.0 + 14.0 * st) * (math.sin(t * (5.0 + 3.0 * st) + ph) * 0.7 + math.sin(t * 9.0 + 2 * ph) * 0.3)
    ang = math.atan(0.075 * wn * abs(wn) / 4.0) * 1.15 + flut * min(1.0, 0.3 + abs(wn) / 8.0)
    return max(-1.35, min(1.35, ang))


def _cloth_tear_plan(W, R):
    plan = W.get('_cl_tear')
    if plan is not None: return plan
    cx, cy = TEAR['center']
    cand = []
    for k, d in enumerate(R['cloth']):
        p = d['M'][:3, 3]
        dd = math.hypot(p[0] - cx, p[1] - cy)
        if dd < TEAR['radius']: cand.append((dd, k))
    cand.sort()
    plan = {}
    if cand:
        P = np.array([R['cloth'][k]['M'][:3, 3] for _, k in cand])
        lo = P.min(0) - np.array((10.0, 10.0, 6.0)); hi = P.max(0) + np.array((70.0, 30.0, 45.0))
        bvh = _region_bvh(W, tuple(lo), tuple(hi))
        for j, (dd, k) in enumerate(cand):
            if len(plan) >= TEAR['n']: break
            d = R['cloth'][k]; h = h01(d['o'].name, 21)
            tt = TEAR['t0'] + (TEAR['t1'] - TEAR['t0']) * ((len(plan) * 0.618) % 1.0)
            ok = False
            for steep in (False, True):
                fl = _cloth_flight(d, tt, h, steep)
                pts = []
                for i in range(0, 40):
                    Ml = _cloth_flight_local(fl, tt + i / 24.0)
                    pts.append(tuple(Ml[:3, 3] + Ml[:3, 2] * -0.4))        # the cloth's middle
                if _first_hit(bvh, pts, 1) is None: ok = True; break
            if ok: plan[k] = fl
    W['_cl_tear'] = plan
    return plan


def _cloth_flight(d, tt, h, steep=False):
    Mr = root_M(tt)
    r0 = d['rot']
    Mb = np.array(Matrix.Translation(Vector(d['loc'])) @ Euler((r0[0] + cloth_swing(d, tt), r0[1], r0[2]), 'XYZ').to_matrix().to_4x4())
    Mw0 = Mr @ (d['P'] @ Mb)
    b = wind(tt, Mw0[0, 3])
    up = 7.0 + 4.0 * h + (8.0 if steep else 0.0)
    vt = b * 0.62 + np.array((0.0, 0.0, up))
    ax = np.array((h - 0.5, 1.0, 0.6 - h)); w = (4.0 + 4.0 * h01(d['o'].name, 22)) * (1 if h > 0.5 else -1)
    return dict(t=tt, Mw0=Mw0, p0=Mw0[:3, 3].copy(), v0=city_vel(tt), vt=vt, tau=0.3, ax=ax, w=w)


def _cloth_flight_local(fl, t):
    tau = max(0.0, t - fl['t'])
    e = math.exp(-tau / fl['tau'])
    p = fl['p0'] + fl['vt'] * tau + (fl['v0'] - fl['vt']) * fl['tau'] * (1.0 - e)
    Rw = _rot_axis(fl['ax'], fl['w'] * tau) @ fl['Mw0'][:3, :3]
    Mw = np.eye(4); Mw[:3, :3] = Rw; Mw[:3, 3] = p
    return np.linalg.inv(root_M(t)) @ Mw


def _cloth(W, R, K, frames, T):
    cl = R['cloth']
    if not cl: return
    tear = {}
    if any(TEAR['t0'] - 0.1 <= T[f] for f in frames):
        tear = _cloth_tear_plan(W, R)
    KT = {}; ST = {}
    for f in frames:
        t = T[f]
        if t not in KT: KT[t] = cloth_K(t); ST[t] = S.storm(t)
    for k, d in enumerate(cl):
        o = d['o']; r0 = d['rot']
        fl = tear.get(k)
        prev = None
        for f in frames:
            t = T[f]
            if fl is not None and t >= fl['t']:
                if t > fl['t'] + 1.6:
                    K.hide(o, f, True); continue
                Ml = np.linalg.inv(d['P']) @ _cloth_flight_local(fl, t)
                loc, e = _mat_to_loc_eul(Ml, prev); prev = e
                K.loc(o, f, loc); K.eul(o, f, tuple(e)); K.hide(o, f, False)
                hgt = d['h'] * 5.0
            else:
                e = (r0[0] + cloth_swing(d, t), r0[1], r0[2]); prev = Euler(e, 'XYZ')
                K.loc(o, f, d['loc']); K.eul(o, f, e); K.hide(o, f, False)
                hgt = d['h'] * (1.0 + 2.6 * sst(rng(ST[t], 0.1, 0.9)))
            if d['md']:
                K.path(o, 'modifiers["flap"].time_offset', f, d['to'] + (f - 1) - FPS * KT[t])
                K.path(o, 'modifiers["flap"].height', f, hgt)


# ================================================================================================================= entry
def _mark_movers(R):
    """the loose parts are QA movers (checked against the set and the chain in every shot they are visible in)."""
    for key in ('tiles', 'rivets', 'sails'):
        for d in R[key]:
            o = d['o']
            if o.get('qa_mover') is None: o['qa_mover'] = 'city'


def city_life(W, f0, f1):
    try:
        c = W.get('city')
        if not isinstance(c, dict) or c.get('root') is None: return
        R = _rest(W)
        _mark_movers(R)
        K = _Keys(W['TL'], f0)
        frames = list(range(int(f0), int(f1) + 1))
        T = {f: tof(twos(f)) for f in frames}
    except Exception:
        traceback.print_exc(); print('citylife: setup failed'); return
    for name, fn in (('sails', _sails), ('bell', _bell), ('vanes', _vanes), ('falls', _falls), ('crystals', _crystals),
                     ('lamps', _lamps), ('shudder', _shudder), ('tiles', _tiles), ('rivets', _rivets), ('cloth', _cloth)):
        try: fn(W, R, K, frames, T)
        except Exception:
            traceback.print_exc(); print('citylife: %s failed for %d..%d' % (name, f0, f1))
