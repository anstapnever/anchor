# ANCHOR — SKY department: the shots in the air round High Harbor.
#   s01 EST (the city above the cumulus)   s02 street CU (sails, laundry, bell tower)   s03 dive down the chain to the port
#   s07 the storm wall seen from the rim     s09 the gale in the streets                     s10 the iron collar, rivets pop
#   s11 the waterspout forms                 s12 the strike at the collar                    s13 the discharge runs down the chain
#   s18 the lurch                            s19 the crystals flare under the city           s29 the city before the spout
#   s38 the spout passes, sails ripped off   s40 the release: the clouds tear open
# Every shot keys its camera + world uniforms through common.base, the city through common.city_key (citylife does the
# city's own life), the chain through common.chain_key; the FX are made per shot (fx.py, keyed on threes).
import math
import numpy as np
import bpy
from mathutils import Vector, Matrix, Euler, Quaternion
import common as CM
import story as S
import env as EV
import citylife as CL

FPS = 24


def tof(f): return (f - 1) / FPS
def fr(t): return int(round(t * FPS)) + 1
def sst(x): x = min(1.0, max(0.0, x)); return x * x * (3.0 - 2.0 * x)
def rng(t, a, b): return min(1.0, max(0.0, (t - a) / (b - a)))
def A(*v): return np.array(v, float)
def lerp(a, b, u): return a + (b - a) * u


def FXM():
    import fx
    return fx


def fxc(W): return W['C']['FX']


# ------------------------------------------------------------------------------------------------------------------- cameras
def roll_to_up(pos, tgt, up):
    """camera roll (deg, look_quat convention) that turns the image's up toward `up` (e.g. the city's up axis)."""
    d = np.asarray(tgt, float) - np.asarray(pos, float); d /= max(np.linalg.norm(d), 1e-9)
    z = np.array((0.0, 0.0, 1.0))
    u0 = z - d * d.dot(z); n0 = np.linalg.norm(u0)
    U = np.asarray(up, float) - d * d.dot(up); n1 = np.linalg.norm(U)
    if n0 < 1e-6 or n1 < 1e-6: return 0.0
    u0 /= n0; U /= n1
    a = -d
    return math.degrees(math.atan2(float(np.dot(np.cross(a, u0), U)), float(np.dot(u0, U))))


def kick(t, events, w=16.0):
    """a heavy, low-frequency decaying wobble (yaw, pitch, roll in degrees) after each event (t0, degrees). Slow enough to
    read as mass (and to stay inside the QA's smoothness limits)."""
    out = np.zeros(3)
    for t0, k in events:
        dt = t - t0
        if 0.0 <= dt < 1.8:
            e = math.exp(-dt * 2.6) * k * sst(dt / 0.1)
            out += e * np.array((math.sin(dt * w + 0.3), 0.8 * math.sin(dt * w * 1.13 + 1.9), 0.55 * math.sin(dt * w * 0.87 + 0.7)))
    return out


def apply_kick(pos, tgt, roll, k):
    d = tgt - pos; L = np.linalg.norm(d); f = d / L
    r = np.cross(f, np.array((0.0, 0.0, 1.0)))
    if np.linalg.norm(r) < 1e-6: r = np.array((1.0, 0.0, 0.0))
    r /= np.linalg.norm(r); u = np.cross(r, f)
    tgt = pos + (f + r * math.tan(math.radians(k[0])) + u * math.tan(math.radians(k[1]))) * L
    return tgt, roll + k[2]


def world_cam(keys, events=None, shake=0.0, seed=1, freq=5.0):
    fn0 = CM.cam_keys(keys, shake_amp=shake, shake_freq=freq, seed=seed)
    if not events: return fn0
    def fn(t):
        p, g, lens, roll = fn0(t)
        g, roll = apply_kick(p, g, roll, kick(t, events))
        return p, g, lens, roll
    return fn


def city_cam(keys, follow=True, events=None, shake=0.0, seed=3, freq=5.0):
    """keys in the city's own frame (root-local). follow: the camera is rigid to the city (the horizon tilts with it)."""
    fl = CM.cam_keys(keys, shake_amp=shake, shake_freq=freq, seed=seed)
    def fn(t):
        pl, tl, lens, roll = fl(t)
        M = CL.root_M(t)
        pw = M[:3, :3] @ np.asarray(pl, float) + M[:3, 3]
        tw = M[:3, :3] @ np.asarray(tl, float) + M[:3, 3]
        if follow: roll = roll + roll_to_up(pw, tw, M[:3, 2])
        if events: tw, roll = apply_kick(pw, tw, roll, kick(t, events))
        return pw, tw, lens, roll
    return fn


def smooth_cam(fn, sigma_f=2.5, n=8):
    """fn low-passed in time (gaussian, sigma in frames) - position, target, lens and roll. For a camera rigid to the city
    high above its pivot (the collar): the lurch tilts it so fast that the rigid path has acceleration kinks; smoothed, the
    camera lags the jolt by a metre or two and catches up, like an operator absorbing it."""
    ks = list(range(-n, n + 1)); ws = [math.exp(-0.5 * (k / sigma_f) ** 2) for k in ks]; sw = sum(ws)
    def g(t):
        P = np.zeros(3); G = np.zeros(3); L = 0.0; R = 0.0
        for k, w in zip(ks, ws):
            p, tg, l, r = fn(t + k / FPS)
            P += w * np.asarray(p, float); G += w * np.asarray(tg, float); L += w * l; R += w * r
        return P / sw, G / sw, L / sw, R / sw
    return g


def L2W(t, p):
    M = CL.root_M(t); return M[:3, :3] @ np.asarray(p, float) + M[:3, 3]


# ------------------------------------------------------------------------------------------------------------------- helpers
def show_only(W, objs, ranges):
    """visible only on the frame ranges [(f0, f1), ...] (hide_render keys at the borders)."""
    TL = W['TL']
    ranges = sorted(ranges)
    for o in objs:
        TL.hide(o, max(1, ranges[0][0] - 1), True)
        for a, b in ranges:
            TL.hide(o, a, False); TL.hide(o, b + 1, True)


def cloud_clearance(W, sid, fn, f0, f1, objs, warn=4.0):
    """prints the camera's nearest distance to the given cloud meshes (QA does not test clouds)."""
    try:
        from mathutils.bvhtree import BVHTree
        dg = bpy.context.evaluated_depsgraph_get()
        trees = []
        for o in objs:
            ev = o.evaluated_get(dg); me = ev.to_mesh(); Mw = o.matrix_world
            trees.append((o.name, BVHTree.FromPolygons([Mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])))
            ev.to_mesh_clear()
        worst = (1e9, None, None)
        for f in range(f0, f1 + 1):
            p = Vector(fn(tof(f))[0])
            for nm, tr in trees:
                loc, nrm, idx, d = tr.find_nearest(p)
                if loc is not None and d < worst[0]: worst = (d, nm, f)
        print('SKYCHECK %s camera-cloud nearest %.1f m (%s, frame %s)%s' % (sid, worst[0], worst[1], worst[2], '  <-- CLOSE' if worst[0] < warn else ''))
    except Exception as ex:
        print('SKYCHECK %s failed: %s' % (sid, ex))


def storm_sky(W, f0, f1, az=(198.0, 342.0)):
    """the horizon cumulus (env.cloud_ring) that stand in the storm's arc (west, compass az) are sunlit white towers in front
    of the dark storm wall: hidden in this shot's frames. Every call re-keys the union of the ranges asked for so far in this
    run, so the keys are right whatever order the shots are keyed in (adjacent ranges never get a 'show' key between them)."""
    TL = W['TL']
    rs = W.setdefault('_sky_ringhide', [])
    rs.append((f0, f1)); rs.sort()
    U = []
    for a, b in rs:
        if U and a <= U[-1][1] + 1: U[-1] = (U[-1][0], max(U[-1][1], b))
        else: U.append((a, b))
    objs = []
    for o in W.get('ring') or []:
        cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
        c = sum(cs, Vector()) / 8.0
        a = math.degrees(math.atan2(c.x, c.y)) % 360.0
        if az[0] <= a <= az[1]: objs.append(o)
    for o in objs:
        if U[0][0] > 1: TL.hide(o, 1, False)
        for a, b in U:
            TL.hide(o, a, True); TL.hide(o, b + 1, False)
        for a, b in rs:                     # an earlier call's 'show' key that now falls inside a hidden range
            if any(ua <= b + 1 <= ub for ua, ub in U): TL.hide(o, b + 1, True)


def rust_mat():
    FX = FXM()
    m = bpy.data.materials.get('M_sky_rust')
    if m is None: m = FX.water_mat('M_sky_rust', ('#f3d2ae', '#d69a68', '#a8673f', '#6f4636'), edges=(0.28, 0.46, 0.7), inside=0.0, shadow=0.2, edge=0.0)
    return m


def set_mat(objs, m):
    for o in objs if isinstance(objs, (list, tuple)) else [objs]:
        if o.type == 'MESH':
            if o.data.materials: o.data.materials[0] = m
            else: o.data.materials.append(m)


# ===================================================================================================== dawn: s01 s02 s03
def _dawn_clouds(W):
    """cumulus round the chain and under the falls (the chain dives into them, the falls pour into them); dawn shots only."""
    if '_sky_dawn' in W: return W['_sky_dawn']
    mat = W['cloudmat']; c = W['C']['ENV']
    # a ring round the chain at 155..250 m: the dive (s03) drops through its hole; the falls pour into their own clouds;
    # one big cumulus in the foreground of the opening rise (s01)
    cx, cy = -158.0, 68.0
    ring = [((92.0, 0.0), 95, 72, 160.0), ((-92.0, 0.0), 95, 70, 162.0), ((0.0, 76.0), 90, 74, 158.0), ((0.0, -74.0), 90, 70, 165.0),
            ((66.0, 60.0), 80, 66, 155.0), ((-66.0, -60.0), 80, 62, 168.0), ((68.0, -58.0), 80, 60, 170.0), ((-68.0, 60.0), 80, 64, 160.0)]
    spec = [('CLOUD_skyR%d' % i, (cx + o[0], cy + o[1], z), w, h, 811 + i) for i, (o, w, h, z) in enumerate(ring)]
    spec += [('CLOUD_skyF0', (-80.0, 200.0, 165.0), 140, 68, 831), ('CLOUD_skyF1', (-72.0, -62.0, 168.0), 150, 72, 832),
             ('CLOUD_skyF2', (-206.0, -84.0, 172.0), 130, 66, 833), ('CLOUD_skyF3', (-332.0, 140.0, 170.0), 150, 70, 834),
             ('CLOUD_skyG', (165.0, -390.0, 262.0), 200, 90, 835)]
    objs = [EV.cumulus(n, p, w, h, seed=s, mat=mat, c=c) for (n, p, w, h, s) in spec]
    show_only(W, objs, [(1, fr(7.4) - 1)])
    W['_sky_dawn'] = objs
    return objs


def s01(W, f0, f1):
    """EST: High Harbor floating above a sea of cumulus at sunrise; a slow rising arc from the south-east; the falls pour
    into the clouds, the chain dives through them to the sea."""
    cl = _dawn_clouds(W)
    keys = [(0.0, A(300.0, -470.0, 362.0), A(-200.0, 70.0, 468.0), 24.0, -1.5),
            (1.5, A(196.0, -540.0, 470.0), A(-195.0, 64.0, 478.0), 25.0, -0.8),
            (3.0, A(80.0, -590.0, 598.0), A(-190.0, 60.0, 472.0), 26.0, 0.0)]
    fn = world_cam(keys)
    CM.base(W, f0, f1, fn)
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    cloud_clearance(W, 's01', fn, f0, f1, cl)


def s02(W, f0, f1):
    """street CU on the east rim, beside M4: its sails sweep through the top and left of frame (a sail passes on each of the
    score's whooshes, 3.0 / 3.45 / 3.9 / 4.35, see citylife.SAIL_SYNC), the miller's laundry flaps in the yard below, the
    street climbs to the bell tower; a slow drift in."""
    keys = [(3.0, A(174.4, 33.4, 212.1), A(25.8, 21.4, 231.6), 23.0, 0.0),
            (4.6, A(173.4, 33.8, 212.3), A(25.8, 21.0, 231.6), 23.8, 0.0)]
    CM.base(W, f0, f1, city_cam(keys, follow=False, shake=0.35, seed=21))
    CM.city_key(W, f0, f1)


def s03(W, f0, f1):
    """the dive: from under the collar straight down along the chain, through the cloud layer; the camera pulls out of the
    dive below the clouds and the port opens up ahead (north-west), the chain running down into the sea."""
    cl = _dawn_clouds(W)
    # the first key sits before the shot's first frame (t 4.583): already diving on frame 1, no start-from-rest jerk
    keys = [(4.5, A(-166.0, 52.0, 312.0), A(-168.0, 72.0, 160.0), 20.0, 0.0),
            (5.3, A(-165.0, 56.0, 262.0), A(-166.0, 74.0, 110.0), 20.0, 3.0),
            (5.9, A(-162.0, 60.0, 205.0), A(-160.0, 80.0, 60.0), 21.0, 5.0),
            (6.5, A(-152.0, 58.0, 150.0), A(-190.0, 200.0, 40.0), 22.0, 3.0),
            (7.0, A(-136.0, 50.0, 118.0), A(-290.0, 380.0, 40.0), 22.0, 1.0),
            (7.4, A(-126.0, 46.0, 102.0), A(-330.0, 420.0, 40.0), 22.0, 0.0)]
    base = world_cam(keys)
    def fn(t):
        # the view direction as one smooth pitch-up / yaw (the key targets above give the same frames at 4.6 / 7.0 / 7.4):
        # looking almost straight down, target points let the yaw wander and the QA saw the jerk
        p, g, lens, roll = base(t)
        pitch = math.radians(-83.0 + 74.7 * sst(rng(t, 5.7, 7.2)))
        yaw = math.radians(-4.0 - 24.6 * sst(rng(t, 5.7, 7.4)))
        d = A(math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), math.sin(pitch))
        return p, p + d * 150.0, lens, roll
    CM.base(W, f0, f1, fn)
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    cloud_clearance(W, 's03', fn, f0, f1, cl)


# ===================================================================================================== the storm: s07 s09
def _storm_bolt_toward(W, pos, d):
    """the storm wall's bolt closest to the view direction d from pos."""
    fx = W.get('fx') or {}
    st = fx.get('storm') or {}
    bpy.context.view_layer.update()
    best = None
    for b in st.get('bolts') or []:
        p = np.array(b.matrix_world.translation)
        v = p - pos; v /= max(np.linalg.norm(v), 1e-9)
        s = float(np.dot(v, d))
        if best is None or s > best[0]: best = (s, b)
    return best[1] if best else None


def s07(W, f0, f1):
    """the west rim, over the roofs: the storm wall towers above the sea, flickering; the wind front reaches the rim at ~14.2
    and the roof vane in the right foreground swings round from the dawn breeze (SE) to face the storm; a slow push."""
    keys = [(14.0, A(-134.5, 40.0, 219.5), A(-212.9, -21.3, 230.0), 22.0, 0.0),
            (16.4, A(-136.5, 38.2, 219.9), A(-214.9, -23.1, 230.4), 23.0, 0.0)]
    fl = sorted(CM.FLASHES + [(14.35, 0.3)])
    fn = city_cam(keys, follow=False, shake=0.3, seed=7)
    CM.base(W, f0, f1, fn, flashes=fl)
    CM.city_key(W, f0, f1)
    p, g = fn(15.1)[:2]; d = (g - p) / np.linalg.norm(g - p)
    b = _storm_bolt_toward(W, p, d)
    if b is not None: FXM().flicker(b, [fr(14.35), fr(15.1)])
    storm_sky(W, f0, f1)


def s09(W, f0, f1):
    """the gale: M3's sails race in the foreground, its yard's laundry tears loose and flies off east, the bell swings in
    the campanile behind; a creeping push in."""
    keys = [(18.4, A(-60.0, -146.0, 218.0), A(-14.4, -58.8, 228.0), 26.0, -2.0),
            (20.0, A(-58.8, -143.0, 218.4), A(-13.4, -56.0, 228.4), 27.5, -2.0)]
    CM.base(W, f0, f1, city_cam(keys, follow=False, shake=0.9, seed=9, freq=7.0))
    CM.city_key(W, f0, f1)
    storm_sky(W, f0, f1)


# ===================================================================================================== the collar: s10 s12 s13
def s10(W, f0, f1):
    """CU of the iron collar as the chain snaps taut: the city is hauled down, the collar groans, rivets pop one after the
    other with sparks and rust dust."""
    R = CL._rest(W)
    plan = CL.rivet_plan(R)
    ev = [(20.02, 1.4)] + [(P['tp'], 0.35) for P in plan]
    def cam(t):
        c = S.city_pos(t); u = sst(rng(t, 20.0, 22.0))
        pos = c + lerp(A(20.0, -8.0, 5.0), A(16.5, -6.5, 4.5), u)
        tgt = c + lerp(A(0.0, 0.5, 3.0), A(0.0, 0.5, 3.5), u)
        tgt, roll = apply_kick(pos, tgt, 0.0, kick(t, ev))
        return pos, tgt, 26.0 + 4.0 * u, roll
    CM.base(W, f0, f1, cam)
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    storm_sky(W, f0, f1)
    FX = FXM(); C = fxc(W); rm = rust_mat()
    for k, P in enumerate(plan):
        f = fr(P['tp'])
        if not (f0 <= f <= f1): continue
        FX.sparks(tuple(P['p0']), f0=f, dur=15, coll=C, seed=100 + k, count=22, speed=14.0, direction=tuple(P['zax'] + A(0, 0, 0.35)),
                  spread=0.5, size=0.45, life=(0.2, 0.5), star=True, name='FX_s10_sparks%02d' % k)
        # the flakes fall on far below the frame (the sea is far down): they thin out over the last 4 drawings (all 30 vanished
        # in mid-air on one frame, 509 / 514; 06.11)
        fl = FX.droplets(tuple(P['p0']), f0=f, dur=22, coll=C, seed=200 + k, count=30, speed=9.0, size=0.045, spread=0.55,
                         up=tuple(P['zax'] + A(0, 0, 0.2)), fadeout=4, name='FX_s10_rust%02d' % k)
        set_mat(fl, rm)


def s12(W, f0, f1):
    """the first strike: a bolt leaps from the storm onto the collar; white-out flash, sparks, the top links glow."""
    ts = S.T['strike1']
    def cam(t):
        c = S.city_pos(t); u = sst(rng(t, 24.4, 25.8))
        pos = c + lerp(A(10.0, -62.0, -24.0), A(8.0, -55.0, -21.0), u)
        tgt = c + lerp(A(-6.0, 0.0, 9.0), A(-6.0, 0.0, 8.0), u)
        tgt, roll = apply_kick(pos, tgt, 0.0, kick(t, [(ts, 2.0), (ts + 0.25, 0.8)]))
        return pos, tgt, 30.0, roll
    CM.base(W, f0, f1, cam, local_flash=0.8)
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    storm_sky(W, f0, f1)
    FX = FXM(); C = fxc(W)
    c = S.collar(ts)
    p0 = c + A(-720.0, 140.0, 400.0)
    b = FX.bolt('FX_s12_bolt', tuple(p0), tuple(c), seed=24, branches=5, width=0.55, coll=C, star=True, star_size=9.0)
    FX.flicker(b, [fr(ts)])
    FX.sparks(tuple(c), f0=fr(ts), dur=27, coll=C, seed=12, count=70, speed=28.0, direction=(0.2, -0.3, -0.4), spread=1.0, size=1.3,
              life=(0.3, 0.9), star=True, name='FX_s12_sparks')
    FX.steam(tuple(c + A(0, 0, 3.0)), f0=fr(ts + 0.12), dur=30, coll=C, seed=13, count=8, size=3.0, direction=(0, 0, 1), speed=6.0, life=1.1,
             wind=(6.0, 0.0, 0.0), name='FX_s12_steam')


def _chain_glow_index(t, n=80):
    return (n + 4) * sst(rng(t, S.T['discharge'], 27.4)) - 2.0


def s13(W, f0, f1):
    """the discharge: the glow races down the taut chain, sparks off the links it passes, and bursts into the sea in a
    cloud of steam; the camera whips down with it."""
    J0 = CM.chain_joints(fr(27.4))
    sea_i = next((i for i in range(80) if J0[i, 2] >= 0.5 > J0[i + 1, 2]), 66)
    sea_p = J0[sea_i] + (J0[sea_i + 1] - J0[sea_i]) * (J0[sea_i, 2] / max(J0[sea_i, 2] - J0[sea_i + 1, 2], 1e-3))
    sea_p[2] = 0.0
    mid = CM.chain_joints(fr(26.6))[40]
    pos0 = mid + A(52.0, -40.0, 40.0)
    def cam(t):
        J = CM.chain_joints(fr(t))
        # look up the chain at the start, follow the glow down (a smooth whip, a little behind the glow front),
        # settle on the steam burst at the sea
        kk = 6.0 + (sea_i - 6.0) * sst(rng(t, 25.95, 27.45))
        i0 = min(int(kk), 79); fr_ = kk - i0
        g = J[i0] * (1 - fr_) + J[min(i0 + 1, 80)] * fr_
        hold = sst(rng(t, 27.3, 27.8))
        g = lerp(g, sea_p + A(0, 0, 12.0), hold)
        pos = pos0 + A(-6.0, 4.0, -24.0) * sst(rng(t, 25.8, 28.0))
        return pos, g, 24.0 + 4.0 * hold, 0.0
    CM.base(W, f0, f1, cam)
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    storm_sky(W, f0, f1)
    FX = FXM(); C = fxc(W)
    for i in (10, 22, 34, 46, 58):
        # the glow passes link i at t where _chain_glow_index(t) == i
        tt = S.T['discharge'] + (27.4 - S.T['discharge']) * _inv_sst((i + 2.0) / 84.0)
        f = fr(tt)
        if f0 <= f <= f1:
            p = CM.chain_joints(f)[i]
            FX.sparks(tuple(p), f0=f, dur=12, coll=C, seed=300 + i, count=18, speed=16.0, direction=(0.0, 0.0, -1.0), spread=1.0, size=0.9,
                      life=(0.2, 0.5), star=True, name='FX_s13_sparks%02d' % i)
    tb = S.T['discharge'] + (27.4 - S.T['discharge']) * _inv_sst((sea_i + 2.0) / 84.0)
    fb = fr(tb)
    FX.steam(tuple(sea_p + A(0, 0, 2.0)), f0=fb, dur=max(6, f1 - fb + 6), coll=C, seed=41, count=14, size=9.0, direction=(0, 0, 1), speed=16.0,
             life=1.0, wind=(7.0, 0.0, 0.0), spread=0.5, name='FX_s13_steam')
    kr = FX.kira('FX_s13_kira', tuple(sea_p + A(0, 0, 4.0)), 14.0, C, inner='#ffffff', outer='#7fe8ff', seed=43)
    FX.flicker(kr, [fb], pattern=(1.0, 0.6, 0.3))
    FX.foam_ring(tuple(sea_p), 4.0, 40.0, f0=fb, dur=40, coll=C, seed=44, name='FX_s13_foam')
    FX.droplets(tuple(sea_p), f0=fb, dur=30, coll=C, seed=45, count=50, speed=26.0, size=0.9, spread=0.6, name='FX_s13_drops')


def _inv_sst(y):
    """inverse of smoothstep on 0..1"""
    y = min(1.0, max(0.0, y))
    return 0.5 - math.sin(math.asin(1.0 - 2.0 * y) / 3.0)


# ===================================================================================================== the spout forms: s11
def _funnel_tip(V, frac=0.13, floor=0.02):
    """the lowering funnel's tip (06.11): the lowest `frac` of the funnel mesh (rings of vertices at one height, its foot
    first) closes to a rounded rope point: each ring keeps its centre (the S-bend) and gets the radius
    r_ref * (floor + (1 - floor) * (1 - (1 - u) ** 2.2)), r_ref the first ring above the taper, u the height in it 0..1
    (the flared foot goes with it; the slope is 0 where the taper meets the rope, so no kink)."""
    z = np.round(V[:, 2], 3); lv = np.unique(z)
    z0, z1 = float(lv[0]), float(lv[-1]); zt = z0 + frac * (z1 - z0)
    rings = [np.nonzero(z == h)[0] for h in lv]
    ref = next(ix for h, ix in zip(lv, rings) if h >= zt)
    c_ref = V[ref, :2].mean(0); r_ref = float(np.linalg.norm(V[ref, :2] - c_ref, axis=1).mean())
    V = V.copy()
    for h, ix in zip(lv, rings):
        if h >= zt: break
        u = (h - z0) / (zt - z0)
        c = V[ix, :2].mean(0); rr = float(np.linalg.norm(V[ix, :2] - c, axis=1).mean())
        k = r_ref * (floor + (1.0 - floor) * (1.0 - (1.0 - u) ** 2.2)) / max(rr, 1e-6)
        V[ix, :2] = c + (V[ix, :2] - c) * k
    return V


def _spout_forming(W, f0, f1):
    """22.0 .. 23.3 the funnel lowers out of the collar cloud (an un-hooked copy of the funnel mesh, scaled down from the
    cloud base: the real funnel's top is pinned by its bend hook) and touches the sea at 23.3, where the real funnel takes
    over at rest; the spray bell bursts up round the foot, the foam spreads, the debris starts to fly. Ends at rest."""
    fx = W.get('fx') or {}
    sp = fx.get('spout')
    if not sp: return
    TL = W['TL']
    H = float(sp['top'].location.z)
    fun = sp['funnel']; sk = sp.get('skirt'); fo = sp.get('foam'); col = sp.get('collar'); deb = sp.get('debris') or []
    T_TOUCH = 23.3
    cp = bpy.data.objects.get('FX_s11_funnel')
    if cp is None:
        # NOT parented to the spout root: common.world_fx un-hides every child of the root in every spout shot, which would
        # leave this copy overlapping the real funnel for the rest of the film
        # Its own mesh (06.11): the real funnel's foot is flared and open, with a white rim (it stands in the sea inside the
        # spray bell); lowered through the air it hung there as a flat-cut pipe end. The copy closes its lowest part to a
        # rope point in the funnel's own tones; at the touch the real funnel takes over with its foot and the bell bursts.
        me = fun.data.copy(); me.name = 'FX_s11_funnel'
        V0 = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', V0)
        me.vertices.foreach_set('co', _funnel_tip(V0.reshape(-1, 3).astype(np.float64)).astype(np.float32).ravel())
        cd = me.attributes.get('cd')
        if cd is not None:
            C3 = np.empty(len(cd.data) * 3, np.float32); cd.data.foreach_get('vector', C3); C3 = C3.reshape(-1, 3)
            C3[:, 2] = np.maximum(C3[:, 2], 0.065); cd.data.foreach_set('vector', C3.ravel())
        me.update()
        cp = bpy.data.objects.new('FX_s11_funnel', me)
        (fun.users_collection[0] if fun.users_collection else fxc(W)).objects.link(cp)
        cp['twist'] = 0.0
    for f in range(f0, f1 + 1):
        t = tof(f - ((f - f0) % 2))                                      # the forming draws on twos
        u = rng(t, 22.0, T_TOUCH)
        s = max(0.004, u ** 1.5)
        sx = 0.35 + 0.65 * sst(rng(t, 22.3, T_TOUCH))
        before = t < T_TOUCH
        p = S.spout_pos(tof(f))                                          # where world_fx puts the root on this frame
        TL.loc(cp, f, (float(p[0]), float(p[1]), H * (1.0 - s))); TL.scale(cp, f, (sx, sx, s))
        TL.prop(cp, 'twist', f, 1.6 * max(0.0, tof(f) - 22.0))
        TL.hide(cp, f, not before); TL.hide(fun, f, before)
        if col is not None:
            k = 1.0 if f == f1 else 0.72 + 0.28 * sst(rng(t, 22.0, 23.6))
            TL.scale(col, f, (k, k, 1.0 if f == f1 else 0.8 + 0.2 * sst(rng(t, 22.0, 23.6))))
        if sk is not None:
            k = 1.0 if f == f1 else 0.12 + 0.88 * (1.0 - (1.0 - rng(t, T_TOUCH, T_TOUCH + 0.6)) ** 2.2)
            TL.scale(sk, f, (k, k, k)); TL.hide(sk, f, before)
        if fo is not None:
            k = 1.0 if f == f1 else 0.15 + 0.85 * (1.0 - (1.0 - rng(t, T_TOUCH, T_TOUCH + 0.9)) ** 2.0)
            TL.scale(fo, f, (k, k, 1.0)); TL.hide(fo, f, before)
        for d in deb: TL.hide(d, f, t < T_TOUCH + 0.4)
    TL.hide(cp, max(1, f0 - 1), True); TL.hide(cp, f1 + 1, True)


def s11(W, f0, f1):
    """WIDE: far to the south-west a funnel lowers out of the storm's dark collar cloud and touches the sea; the spray bell
    bursts up round its foot. From low under the city, beside the taut chain (it runs through the left of frame); low
    enough that the low cumulus over the bay stay above the frame; a slow drift toward the spout."""
    keys = [(22.0, A(-105.0, 155.0, 82.0), A(-3450.0, -2450.0, 200.0), 35.0, 0.0),
            (24.4, A(-110.0, 149.0, 79.0), A(-3400.0, -2420.0, 195.0), 37.0, 0.0)]
    fn = world_cam(keys, shake=0.25, seed=11)
    CM.base(W, f0, f1, fn)
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    storm_sky(W, f0, f1)
    _spout_forming(W, f0, f1)
    cloud_clearance(W, 's11', fn, f0, f1, W.get('low') or [])


# ===================================================================================================== the lurch: s18 s19
def s18(W, f0, f1):
    """the lurch, from the top of the west street's stairs: the city drops and tips, the horizon swings, the houses shudder,
    roof tiles slide off and rain into the street. The camera starts past the laundry line over the street (x -59.3) and
    creeps on down the stairs."""
    keys = [(35.2, A(-62.0, 7.4, 230.4), A(-170.0, 8.5, 214.0), 24.0, 0.0),
            (37.4, A(-65.5, 7.5, 230.0), A(-170.0, 7.0, 214.5), 26.0, 0.0)]
    ev = [(35.2, 2.0), (35.55, 1.0), (36.45, 0.6)]
    rig = smooth_cam(city_cam(keys, follow=True), 2.5)
    def fn(t):
        p, g, lens, roll = rig(t)
        g, roll = apply_kick(p, g, roll, kick(t, ev))
        return p, g, lens, roll
    CM.base(W, f0, f1, fn)
    CM.city_key(W, f0, f1)
    storm_sky(W, f0, f1)


def s19(W, f0, f1):
    """under the city: the crystal cone flares from the collar up to the rim (37.4) and stays lit; the camera rides with
    the city in a slow arc beneath it."""
    keys = [(37.4, A(78.0, -52.0, -22.0), A(-4.0, 6.0, 86.0), 22.0, 0.0),
            (39.0, A(62.0, -80.0, -12.0), A(-4.0, 0.0, 96.0), 22.0, 0.0)]
    fn = city_cam(keys, follow=True, events=[(37.4, 0.8)])
    CM.base(W, f0, f1, fn)
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    storm_sky(W, f0, f1)
    _crystal_flares(W, f0, f1, A(78.0, -52.0, -22.0), fn)


def _crystal_flares(W, f0, f1, cam_l, cam_fn, n=16):
    """a drawn starburst on the crystals (on the camera's side of the cone) at the moment the flare wave passes them
    (citylife: 37.4 + (z - 20) / 150 * 0.4), bottom to top; the CITY set renders in s19, so they live in its collection.
    Each star sits 18 m in front of its crystal on the line of sight, so the rock never clips the impostor."""
    c = W.get('city') or {}
    info = (c.get('info') or {}).get('crystals') or []
    objs = c.get('crystals') or []
    if not info or len(info) != len(objs): return
    FX = FXM(); C = W['C']['CITY']
    cand = []
    for k, ci in enumerate(info):
        p = np.array(ci['p'], float); nr = np.array(ci['n'], float)
        to_cam = cam_l - p
        if float(np.dot(nr[:2], to_cam[:2])) <= 0.25 * np.linalg.norm(to_cam[:2]) * np.linalg.norm(nr[:2]): continue
        ax = nr + A(0.0, 0.0, -0.75); ax /= np.linalg.norm(ax)
        q = p + ax * ci['size'] * 0.45
        tf = S.T['crystals'] + (float(ci['z']) - 20.0) / 150.0 * 0.4
        if f0 <= fr(tf) <= f1 - 9: cand.append((float(ci['z']), k, q, tf, float(ci['size'])))
    cand.sort()
    if len(cand) > n: cand = [cand[int(round(i * (len(cand) - 1) / (n - 1)))] for i in range(n)]
    for z, k, q, tf, size in cand:
        qw = L2W(tf, q); cw = np.asarray(cam_fn(tf)[0], float)
        d = cw - qw; qw = qw + d * (18.0 / max(np.linalg.norm(d), 1e-6))
        kr = FX.kira('FX_s19_kira%02d' % k, tuple(qw), min(6.5, max(3.2, 0.7 * size)), C, inner='#ffffff', outer='#7fe8ff', seed=190 + k)
        FX.flicker(kr, [fr(tf)], pattern=(1.0, 0.6, 0.3))


# ===================================================================================================== the spout: s29 s38
def spout_swarm(W, sid, f0, f1, n=24, rad=(150.0, 430.0), zr=(40.0, 760.0), size=(2.6, 4.6), seed=0):
    """big debris (planks, container panels, beams, chunks) whirling round the waterspout's axis, spiralling in and up,
    keyed on twos (visible only in f0..f1)."""
    FX = FXM(); C = fxc(W); TL = W['TL']
    R = np.random.RandomState(seed)
    kinds = ('plank', 'container', 'chunk', 'beam')
    bases = FX._debris_bases(seed + 5, kinds, 1.0)
    t0 = tof(f0); objs = []
    for i in range(n):
        kind = kinds[i % len(kinds)]
        me, _ = bases[kind][R.randint(len(bases[kind]))]
        o = bpy.data.objects.new('FX_%s_swarm%02d' % (sid, i), me); C.objects.link(o)
        sc = R.uniform(*size); o.scale = (sc, sc, sc)
        r0 = R.uniform(*rad); a0 = R.uniform(0, 2 * math.pi); w = R.uniform(0.3, 0.5) * math.sqrt(300.0 / r0)
        z0 = R.uniform(*zr); climb = R.uniform(10.0, 34.0)
        ax = Vector(tuple(R.normal(size=3))).normalized(); spin = R.uniform(1.2, 3.5); q0 = Quaternion(Vector(tuple(R.normal(size=3))).normalized(), R.uniform(0, 6.28))
        prev = None
        for f in range(f0, f1 + 1):
            tt = tof(f - ((f - f0) % 2)); dt = tt - t0
            sp = S.spout_pos(tt)
            if sp is None: sp = A(-3500.0, -2500.0, 0.0)
            a = a0 + w * dt; rr = r0 * (1.0 - 0.06 * dt)
            p = (float(sp[0] + rr * math.cos(a)), float(sp[1] + rr * math.sin(a)), float(z0 + climb * dt))
            e = (Quaternion(ax, spin * dt) @ q0).to_euler('XYZ', prev) if prev is not None else (Quaternion(ax, spin * dt) @ q0).to_euler('XYZ')
            prev = e
            TL.loc(o, f, p); TL.eul(o, f, tuple(e))
        objs.append(o)
    show_only(W, objs, [(f0, f1)])
    return objs


def s29(W, f0, f1):
    """from high in the north-east, above the low cumulus: the drifting city on the right, the colossal spout and its
    collar cloud on the left behind it, the debris whirling round it; the chain hangs from the collar to the sea, its free
    end throwing spray off the wave tops at the bottom of frame. A slow drift."""
    keys = [(59.0, A(340.0, 297.0, 450.0), A(-1198.0, -583.0, 217.0), 28.0, 0.0),
            (61.0, A(328.0, 284.0, 452.0), A(-1174.0, -590.0, 220.0), 29.0, 0.0)]
    fn = world_cam(keys, shake=0.3, seed=29)
    CM.base(W, f0, f1, fn)
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    storm_sky(W, f0, f1)
    cloud_clearance(W, 's29', fn, f0, f1, W.get('low') or [])
    FX = FXM(); C = fxc(W)
    pts = [tuple(CM.chain_joints(f)[80][:2]) + (0.0,) for f in range(f0, f1 + 1, 4)]
    FX.spray_trail(pts, f0=f0, dur=f1 - f0 + 1, coll=C, seed=290, size=9.0, skip=0.3, name='FX_s29_trail')
    spout_swarm(W, 's29', f0, f1, n=26, seed=291)


def s38(W, f0, f1):
    """the spout passes the city by metres: from the south rim (rigid with the rocking city) the funnel crosses the frame
    right to left; M2's, M1's and M3's sails are torn off and whirl into it."""
    keys = [(78.6, A(40.0, -60.0, 228.0), A(-80.0, -160.0, 258.0), 22.0, 0.0),
            (80.6, A(34.0, -64.0, 227.0), A(-70.0, -165.0, 262.0), 22.0, 0.0)]
    ev = [(CL.RIP[2], 0.8), (CL.RIP[1], 0.6), (CL.RIP[3], 1.0)]
    CM.base(W, f0, f1, city_cam(keys, follow=True, events=ev, shake=0.6, seed=38, freq=6.0))
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    storm_sky(W, f0, f1)


# ===================================================================================================== the release: s40
def _release_clouds(W):
    if '_sky_rel' in W: return W['_sky_rel']
    mat = W['cloudmat']; c = W['C']['ENV']
    spec = [('CLOUD_skyX1', (520.0, -560.0, 760.0), 900, 420, 941, (0.0, 260.0)),
            ('CLOUD_skyX2', (560.0, -980.0, 820.0), 820, 380, 942, (0.0, -300.0)),
            ('CLOUD_skyX3', (300.0, -760.0, 980.0), 700, 300, 943, (120.0, 40.0))]
    out = []
    for (n, p, w, h, s, mv) in spec:
        o = EV.cumulus(n, p, w, h, seed=s, mat=mat, c=c, stormy=1.0)
        o['tc0'] = tuple(o['tc'])
        out.append((o, np.array(p, float), np.array(mv + (0.0,), float)))
    W['_sky_rel'] = out
    return out


def s40(W, f0, f1):
    """the release: the storm tears open over the city; the sun breaks through, beams stream down; the city settles level
    and its falls hang straight again. The camera floats back from the west, the sun high right of frame."""
    keys = [(82.0, A(-1300.0, -560.0, 372.0), A(-720.0, -408.0, 470.0), 28.0, 0.0),
            (84.4, A(-1340.0, -580.0, 380.0), A(-718.0, -421.0, 478.0), 27.0, 0.0)]
    CM.base(W, f0, f1, world_cam(keys))
    CM.city_key(W, f0, f1)
    CM.chain_key(W, f0, f1)
    TL = W['TL']
    rc = _release_clouds(W)
    for (o, p0, mv) in rc:
        for f in range(f0, f1 + 1):
            t = tof(f - ((f - f0) % 2)); u = sst(rng(t, 82.0, 84.4)) ** 0.8
            TL.loc(o, f, tuple(mv * u))
            TL.prop(o, 'tc', f, tuple(np.array(o['tc0']) + mv * u))
    show_only(W, [o for (o, _, _) in rc], [(f0, f1)])


# ------------------------------------------------------------------------------------------------------------------- QA
def _port_assembly(a, b):
    """designed contacts inside the PORT department's assemblies (parts of one lighthouse / boat / crane touch by design;
    the lighthouse stands on the breakwater cap). Shots that only show the port in the distance."""
    def grp(n):
        if n.startswith('LH_'): return 'LH'
        if n.startswith('PORT_boat_'): return '_'.join(n.split('_')[:3])
        if n.startswith('PORT_craneA_'): return 'craneA'
        return None
    ga, gb = grp(a.name), grp(b.name)
    if ga is not None and ga == gb: return True
    if 'LH' in (ga, gb) and (a.name.startswith('PORT_bw') or b.name.startswith('PORT_bw')): return True
    return False


QA_ALLOW = {'s01': _port_assembly, 's03': _port_assembly}


# ------------------------------------------------------------------------------------------------------------------- post
POST = {
    's01': dict(haze=(0.78, 0.86, 1.0), haze_dist=2600.0, haze_max=0.42, bloom=0.85),
    's02': dict(haze_dist=2000.0, haze_max=0.3),
    's03': dict(haze_dist=2000.0, haze_max=0.38),
    's07': dict(haze=(0.74, 0.8, 0.98), haze_dist=3400.0, haze_max=0.4),
    's09': dict(haze_dist=2400.0, haze_max=0.3, rain=0.12, rain_angle=-28.0),
    's10': dict(haze_dist=2400.0, haze_max=0.3, near=60.0, rain=0.15, rain_angle=-24.0),
    's11': dict(haze=(0.72, 0.78, 0.96), haze_dist=4200.0, haze_max=0.45, rain=0.18, rain_angle=-24.0),
    's12': dict(haze_dist=2400.0, haze_max=0.3, near=80.0, rain=0.25, rain_angle=-24.0, bloom=1.1),
    's13': dict(haze_dist=2400.0, haze_max=0.35, rain=0.3, rain_angle=-24.0, bloom=1.05),
    's18': dict(haze_dist=2200.0, haze_max=0.35, rain=0.45, rain_angle=-30.0),
    's19': dict(haze_dist=2200.0, haze_max=0.35, rain=0.35, rain_angle=-30.0, bloom=1.1),
    's29': dict(haze=(0.72, 0.76, 0.94), haze_dist=4000.0, haze_max=0.45, rain=0.45, rain_angle=-26.0),
    's38': dict(haze_dist=2400.0, haze_max=0.35, rain=0.55, rain_angle=-34.0),
    # rays: the sun sits behind the big release cloud; a little below its true spot (0.76, 0.26) so the city's own ray
    # shadow does not draw a streaky band across the clean blue on the left
    's40': dict(haze=(0.95, 0.88, 0.76), haze_dist=3000.0, haze_max=0.4, sun_xy=(0.8, 0.34), rays=0.42, ray_col=(1.0, 0.88, 0.66),
                bloom=1.0, gain=(1.0, 0.95, 0.86), vibrance=0.35),
}
