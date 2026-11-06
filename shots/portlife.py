# ANCHOR — the port's own life on the film timeline (HARBOR department).
#   port_life(W, f0, f1) keys, for frames f0..f1, everything in the port that moves by itself. Pure function of t: any range,
#   any order, deterministic, no state between calls (only create-once objects/FX guarded in W), never raises.
#     crane A    working pose: trolley over the quay edge, spreader + a blue 40 ft box lowered to 6.9..12 m. The chain end hits
#                it at 42.0 (frame 1009, the baked first contact): ropes snap, spreader + box are flung hard seaward tumbling (clear
#                of the chain end from frame 1014) and splash into the bay 55 m out (~43.7); the west leg buckles (4 deg lean), the
#                crane topples seaward about its waterside bogie edge (inverted-pendulum sinh curve, on ones), the boom slams into
#                the bay at 43.0 (bounces, rests 47 deg from ~43.7),
#                the trolley runs down the tilted boom and jams half under water (~45.3).
#     dock 3     flood plane SEA_dock3 (sea material) rises from under the floor to z -6 over 43.2..44.4 (ease-out), stays.
#     boats      PORT_boat_0..7: fishing far out SW (< 13.8, unseen 11.2..16.4), racing home in a staggered column past the
#                lighthouse (13.8..25, s08 16.4..18.4, on ones), moored at their berths from 25.0 (unseen 18.4..33.2), rocking
#                with S.storm (on twos). Berths beside the pier are 1 m off the pier so the rocking never touches it.
#     lighthouse beam on with the storm (13..17), off again 84..88; rotation driven by the asset at 4.5 deg/frame;
#                77.4..78.2 the tower bends toward the chain's pull (mid 6 deg, top 4 deg more), crack 0 -> 1; after 80.6 it
#                eases back 30 %. The base never moves.
#     FX         the crane-hit events (smash debris + sparks + kira, boom splash, box splash, trolley splash, dock-gate wave)
#                are created once per run when the keyed range overlaps their life.
import math
import numpy as np
import bpy
from mathutils import Vector, Matrix, Quaternion, Euler
import story as S

FPS = 24


def tof(f): return (f - 1) / FPS
def fr(t): return int(round(t * FPS)) + 1
def on2(f): return f - ((f - 1) % 2)                    # props on twos on the global grid
def _cl(x, a=0.0, b=1.0): return a if x < a else (b if x > b else x)
def _ss(x): x = _cl(x); return x * x * (3.0 - 2.0 * x)
def _rng(t, a, b): return _cl((t - a) / (b - a))
def _eout(x, p=2.0): return 1.0 - (1.0 - _cl(x)) ** p


# ============================================================================================================== crane A
T_HIT, T_SLAM = 42.0, 43.0                  # chain end hits the spreader (baked first contact, frame 1009); boom slams the bay
A_REST, B_REST, P_REST = 47.0, 4.0, 2.0    # deg: seaward tip, west lean (buckled leg), boom droop at the hinge
LAM = 2.6                                   # topple growth rate (inverted pendulum, sinh)
LEGS_O = Vector((-370.0, 419.0, 4.0))       # legs origin (ground centre)
PV = Vector((-383.2, 403.38, 4.18))         # pivot: outer seaward bottom corner of the west waterside bogie wheels
HINGE = Vector((0.0, -15.0, 47.0))          # boom hinge (legs-local)
YT0, SPZ, YT_JAM = -2.5, -39.0, -44.0       # trolley (boom-local y) at work, spreader (trolley-local z), trolley jam point
CAB = (2.9, -3.6, -0.35)                    # cab moved clear of the hoist ropes
UNIT_C = Vector((-370.0, 401.5, 9.5))       # spreader+box unit centre at rest (spreader bottom face), world
UNIT_V = Vector((-12.0, -32.0, 7.0))        # its launch velocity (m/s): hard seaward, west, up -- clear of the chain end by 1014
UNIT_W = (2.5, 0.6)                          # its tumble (rad/s): end over end (about its short axis), roll (about its long axis)
G_FX = 9.81 * 1.4                            # drawn gravity
BOX_DZ = -5.12                              # box origin (bottom centre) in spreader space (spreader frame bottom at -2.5)


def crane_tilt(t):
    """(a, b, p) degrees: seaward tip of the whole crane about PV (x axis), west lean (y axis), boom droop at its hinge."""
    if t < T_HIT: return 0.0, 0.0, 0.0
    tau = t - T_HIT; dur = T_SLAM - T_HIT
    if tau <= dur: a = A_REST * math.sinh(LAM * tau) / math.sinh(LAM * dur)
    else:
        s = tau - dur
        a = A_REST - (1.8 * math.exp(-4.0 * s) * abs(math.sin(math.pi * s / 0.24)) if s < 0.72 else 0.0)
    b = B_REST * _ss(_rng(t, T_HIT + 0.05, T_HIT + 0.6))
    p = P_REST * _ss(_rng(t, T_HIT + 0.6, T_SLAM))
    if tau < 0.6: p += 1.6 * math.sin(math.pi * tau / 0.2) * math.exp(-5.0 * tau)          # the rope yank bounces the boom
    if dur < tau < dur + 0.6:
        s = tau - dur; p -= 1.2 * math.exp(-5.0 * s) * math.sin(math.pi * s / 0.18)          # the slam flexes it
    return a, b, p


_TAB = {}


def _trolley_table():
    """trolley boom-local y after the hit: a kick off the rope yank, then it runs down the tilting boom (g sin slope) until it
    jams at YT_JAM, rebounds a little and stays. Integrated once on a fine grid (deterministic)."""
    if 'yt' in _TAB: return _TAB['yt']
    dt = 1.0 / 480.0; t = T_HIT; y = YT0; v = -2.0; ts = [t]; ys = [y]; jam = None
    while t < T_HIT + 10.0:
        a, b, p = crane_tilt(t)
        v += -G_FX * math.sin(math.radians(a + p)) * dt; y += v * dt; t += dt
        if y <= YT_JAM: jam = t; y = YT_JAM; ts.append(t); ys.append(y); break
        ts.append(t); ys.append(y)
    _TAB['yt'] = (np.array(ts), np.array(ys), jam); return _TAB['yt']


def trolley_y(t):
    if t <= T_HIT: return YT0
    ts, ys, jam = _trolley_table()
    if jam is None or t < jam: return float(np.interp(t, ts, ys))
    s = t - jam
    return YT_JAM + (0.6 * math.sin(math.pi * min(s / 0.3, 1.0)) * math.exp(-6.0 * s) if s < 0.3 else 0.0)


def trolley_jam_t():
    return _trolley_table()[2]


def _rot(a, b):
    return Matrix.Rotation(math.radians(a), 4, 'X') @ Matrix.Rotation(-math.radians(b), 4, 'Y')


def crane_mats(t):
    """world matrices {'legs', 'boom', 'trolley', 'unit'} of crane A at t (unit = spreader world matrix)."""
    a, b, p = crane_tilt(t)
    Ml = Matrix.Translation(PV) @ _rot(a, b) @ Matrix.Translation(-PV) @ Matrix.Translation(LEGS_O)
    Mb = Ml @ Matrix.Translation(HINGE) @ Matrix.Rotation(math.radians(p), 4, 'X')
    Mt = Mb @ Matrix.Translation(Vector((0.0, trolley_y(t), 0.0)))
    return {'legs': Ml, 'boom': Mb, 'trolley': Mt, 'unit': unit_world(t, Mt)}


def unit_world(t, Mt=None):
    """spreader world matrix: hanging under the trolley until the hit, then flung (ballistic, tumbling end over end)."""
    if t <= T_HIT:
        if Mt is None: Mt = crane_mats(t)['trolley']
        return Mt @ Matrix.Translation(Vector((0.0, 0.0, SPZ)))
    tau = t - T_HIT
    p = UNIT_C + UNIT_V * tau + Vector((0.0, 0.0, -0.5 * G_FX * tau * tau))
    q = Quaternion((0.0, 1.0, 0.0), UNIT_W[0] * tau) @ Quaternion((1.0, 0.0, 0.0), UNIT_W[1] * tau)
    return Matrix.Translation(p) @ q.to_matrix().to_4x4() @ Matrix.Translation(Vector((0.0, 0.0, 2.5)))


def unit_centre(t):
    tau = max(0.0, t - T_HIT)
    return UNIT_C + UNIT_V * tau + Vector((0.0, 0.0, -0.5 * G_FX * tau * tau))


def unit_splash_t():
    """time the unit centre reaches the sea (z 1)."""
    a = 0.5 * G_FX; b = UNIT_V.z; c = UNIT_C.z - 1.0
    return T_HIT + (b + math.sqrt(b * b + 4 * a * c)) / (2 * a)


def unit_gone_t():
    a = 0.5 * G_FX; b = UNIT_V.z; c = UNIT_C.z + 5.0
    return T_HIT + (b + math.sqrt(b * b + 4 * a * c)) / (2 * a)


def crane_point(local, part, t):
    """world position of a point given in the local space of part ('legs', 'boom', 'trolley', 'unit') at t."""
    return crane_mats(t)[part] @ Vector(local)


def _box(W, sp):
    o = bpy.data.objects.get('PORT_craneA_box')
    if o is not None: return o
    me = bpy.data.meshes.get('PORT_cont12')
    if me is None: return None
    o = bpy.data.objects.new('PORT_craneA_box', me)
    (sp.users_collection[0] if sp.users_collection else W['C']['PORT']).objects.link(o)
    o.parent = sp; o.location = (0.0, 0.0, BOX_DZ); o.rotation_euler = (0.0, 0.0, 0.0)
    import zlib
    o['ccol'] = tuple(_srgb('#2f5fd0')); o['logo'] = (3.0, 0.0, 1.0); o['qa_kind'] = 'container'
    o['oidk'] = (zlib.crc32(o.name.encode()) % 100003) / 100003.0
    return o


def _srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def _crane(W, f0, f1):
    P = W.get('port')
    ca = P.get('craneA') if isinstance(P, dict) else None
    if not ca: return
    TL = W['TL']
    legs, boom, tr, cab, sp, ropes = (ca.get(k) for k in ('legs', 'boom', 'trolley', 'cab', 'spreader', 'ropes'))
    box = _box(W, sp)
    gone = unit_gone_t()
    prev = {}
    for f in range(f0, f1 + 1):
        t = tof(f); M = crane_mats(t)
        a, b, p = crane_tilt(t)
        ql = M['legs'].to_quaternion()
        TL.loc(legs, f, tuple(M['legs'].translation)); TL.quat(legs, f, ql)
        TL.loc(boom, f, tuple(HINGE)); TL.eul(boom, f, (math.radians(p), 0.0, 0.0))
        TL.loc(tr, f, (0.0, trolley_y(t), 0.0)); TL.eul(tr, f, (0.0, 0.0, 0.0))
        TL.loc(cab, f, CAB)
        Ls = M['trolley'].inverted() @ M['unit']
        q = Ls.to_quaternion()
        if 'sp' in prev and prev['sp'].dot(q) < 0: q = -q
        prev['sp'] = q
        TL.loc(sp, f, tuple(Ls.translation)); TL.quat(sp, f, q)
        TL.hide(sp, f, t >= gone)
        if box is not None:
            TL.loc(box, f, (0.0, 0.0, BOX_DZ)); TL.hide(box, f, t >= gone)
        if ropes is not None: TL.hide(ropes, f, t >= T_HIT - 1e-6)


# ============================================================================================================== dock 3 flood
FLOOD_T0, FLOOD_T1, FLOOD_Z0, FLOOD_Z1 = 43.2, 44.4, -14.4, -6.0


def flood_z(t):
    if t < FLOOD_T0: return FLOOD_Z0 - 0.6
    return FLOOD_Z0 + (FLOOD_Z1 - FLOOD_Z0) * _eout(_rng(t, FLOOD_T0, FLOOD_T1), 2.2)


def _flood_plane(W):
    o = bpy.data.objects.get('SEA_dock3')
    if o is not None: return o
    sea = W.get('sea') or bpy.data.objects.get('SEA')
    me = bpy.data.meshes.new('SEA_dock3')
    x0, x1, y0, y1 = -510.6, -409.4, 403.0, 600.6
    me.from_pydata([(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)], [], [(0, 1, 2, 3)])
    if sea is not None:
        for m in sea.data.materials: me.materials.append(m)
    me.update()
    o = bpy.data.objects.new('SEA_dock3', me)
    (W['C']['PORT'] if 'PORT' in W.get('C', {}) else bpy.context.scene.collection).objects.link(o)
    o['qa_kind'] = 'fx'
    return o


def _flood(W, f0, f1):
    o = _flood_plane(W); TL = W['TL']
    for f in range(f0, f1 + 1):
        t = tof(f)
        TL.loc(o, f, (0.0, 0.0, flood_z(t))); TL.hide(o, f, t < FLOOD_T0)


# ============================================================================================================== boats
BERTH_DX = (-1.0, -1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0)          # pier-side boats 1 m further off the pier
T_RACE0, T_MOOR = 13.8, 25.0                                   # fishing -> racing column (unseen), racing -> moored (unseen)
T_PASS, V_RACE = 17.3, 14.0                                    # the column head abeam the lighthouse, racing speed (m/s)
ROUTE = [(-1250.0, -470.0), (-1050.0, -390.0), (-860.0, -318.0), (-740.0, -281.0), (-640.0, -258.0), (-530.0, -222.0),
         (-400.0, -160.0), (-240.0, -70.0), (-60.0, 60.0), (100.0, 210.0), (180.0, 300.0)]
P_PASS = 4                                                     # route index abeam the lighthouse
GAP = (0.0, 30.0, 58.0, 92.0, 121.0, 156.0, 186.0, 222.0)      # metres behind the head
LANE = (0.0, 11.0, -10.0, 13.0, -12.0, 9.0, -11.0, 12.0)       # metres to port (+) / starboard (-)
FISH = [(-1180.0, -600.0, 40.0), (-1105.0, -655.0, 110.0), (-1260.0, -690.0, -20.0), (-1030.0, -560.0, 75.0),
        (-1320.0, -560.0, 160.0), (-1150.0, -760.0, 20.0), (-990.0, -700.0, 130.0), (-1230.0, -820.0, 60.0)]


def _route_table():
    if 'route' in _TAB: return _TAB['route']
    P = [np.array(p, float) for p in ROUTE]
    pts = []
    for i in range(len(P) - 1):
        p0 = P[max(i - 1, 0)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(i + 2, len(P) - 1)]
        for k in range(40):
            u = k / 40.0; u2 = u * u; u3 = u2 * u
            pts.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u3))
    pts.append(P[-1]); pts = np.array(pts)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    sp = s[P_PASS * 40]
    _TAB['route'] = (pts, s, sp); return _TAB['route']


def route_at(sv):
    """(x, y), unit tangent, curvature sign*magnitude (1/m) at arc length sv (clamped to the route)."""
    pts, s, _ = _route_table()
    sv = _cl(sv, 0.0, s[-1] - 0.01)
    x = float(np.interp(sv, s, pts[:, 0])); y = float(np.interp(sv, s, pts[:, 1]))
    e = 4.0
    xa = float(np.interp(max(sv - e, 0), s, pts[:, 0])); ya = float(np.interp(max(sv - e, 0), s, pts[:, 1]))
    xb = float(np.interp(min(sv + e, s[-1]), s, pts[:, 0])); yb = float(np.interp(min(sv + e, s[-1]), s, pts[:, 1]))
    d = np.array((xb - xa, yb - ya)); d /= max(1e-6, np.linalg.norm(d))
    ta = np.array((x - xa, y - ya)); tb = np.array((xb - x, yb - y))
    ha = math.atan2(ta[1], ta[0]); hb = math.atan2(tb[1], tb[0])
    dh = (hb - ha + math.pi) % (2 * math.pi) - math.pi
    return np.array((x, y)), d, dh / max(1e-6, 0.5 * (np.linalg.norm(ta) + np.linalg.norm(tb)))


def boat_s(i, t):
    """arc length of boat i on the route at t (racing column)."""
    _, _, sp = _route_table()
    return sp + V_RACE * (t - T_PASS) - GAP[i]                  # constant speed: the bow spray FX rides the bow exactly


def boat_pose(i, t):
    """(location, (roll, pitch, yaw) radians) of boat root i at t."""
    st = S.storm(t); ph = 1.37 * i
    if t < T_RACE0:                                             # fishing far out: idle drift, gentle rocking
        x, y, hd = FISH[i]; h = math.radians(hd)
        x += 0.3 * t * math.cos(h); y += 0.3 * t * math.sin(h)
        w = 2 * math.pi * 0.35
        return (x, y, 0.15 * math.sin(w * t + ph)), (math.radians(1.6) * math.sin(0.8 * w * t + ph), math.radians(0.8) * math.sin(1.1 * w * t + ph * 0.6),
                                                    h + math.radians(1.0) * math.sin(0.3 * w * t + ph))
    if t < T_MOOR:                                              # racing home: column on the route, bow up, banking, slamming
        sv = boat_s(i, t); p, d, k = route_at(sv)
        n = np.array((-d[1], d[0]))
        q = p + n * LANE[i]
        yaw = math.atan2(d[1], d[0])
        w = 2 * math.pi * 0.9
        heave = 0.45 * math.sin(w * t + ph) + 0.25 * math.sin(2.3 * w * t + 2 * ph)
        pitch = -math.radians(4.5) - math.radians(3.2) * math.sin(w * t + ph + 0.9)          # negative = bow up
        roll = -math.radians(2.0) * math.sin(0.7 * w * t + ph) - _cl(k * V_RACE * V_RACE * 0.02, -0.12, 0.12)
        yaw += math.radians(1.2) * math.sin(0.5 * w * t + ph)
        return (float(q[0]), float(q[1]), heave), (roll, pitch, yaw)
    import port as PT                                           # moored at the berth
    cls, x, y, yaw = PT.BOAT_SPOTS[i]
    x += BERTH_DX[i]
    w = 2 * math.pi * (0.42 + 0.05 * (i % 3))
    heave = (0.12 + 0.33 * st) * math.sin(w * t + ph)
    roll = math.radians(0.8 + 2.6 * st) * math.sin(0.8 * w * t + 1.7 * ph)
    pitch = math.radians(0.4 + 1.3 * st) * math.sin(1.1 * w * t + 0.6 * ph)
    dyaw = math.radians(0.3 + 0.8 * st) * math.sin(0.37 * w * t + ph)
    return (x, y, heave), (roll, pitch, math.radians(yaw) + dyaw)


def _boats(W, f0, f1):
    P = W.get('port'); TL = W['TL']
    boats = P.get('boats') if isinstance(P, dict) else None
    if not boats: return
    for f in range(f0, f1 + 1):
        t = tof(f)
        racing = T_RACE0 <= t < T_MOOR
        te = t if racing else tof(on2(f))                       # racing on ones (fast movers), otherwise on twos
        for i, b in enumerate(boats):
            loc, rot = boat_pose(i, te)
            TL.loc(b, f, loc); TL.eul(b, f, rot)


# ============================================================================================================== lighthouse
LH_T0, LH_T1, LH_TB = 77.4, 78.2, 80.6
MID_DEG, TOP_DEG, EASE = 6.0, 4.0, 0.3
BEAM_SPEED = 4.5                                               # deg per frame (the asset's driver: frame * speed)


def lh_bend(t):
    """(k 0..1 of the full bend, horizontal unit direction of the pull)."""
    tc = min(max(t, LH_T0), LH_T1)
    c = S.city_pos(tc); d = np.array((c[0] - S.LIGHTHOUSE[0], c[1] - S.LIGHTHOUSE[1]))
    d = d / max(1e-6, np.linalg.norm(d))
    k = 0.0
    if t >= LH_T0:
        u = _rng(t, LH_T0, LH_T1)
        k = _ss(u) ** 1.3 + 0.06 * math.sin(math.pi * u) * math.sin(6.0 * math.pi * u)      # it gives in jerks as the chain bites
        if t > LH_T1: k = 1.0 + 0.05 * math.exp(-5.0 * (t - LH_T1)) * math.sin(13.0 * (t - LH_T1))
        k *= 1.0 - EASE * _ss(_rng(t, LH_TB, LH_TB + 0.9))
    return k, d


def lh_beam(t):
    return 1.2 * _ss(_rng(t, 13.0, 17.0)) * (1.0 - 0.8 * _ss(_rng(t, 84.0, 88.0)))


def _lighthouse(W, f0, f1):
    P = W.get('port'); TL = W['TL']
    L = P.get('lighthouse') if isinstance(P, dict) else None
    if not L: return
    lamp = L.get('lamp')
    if lamp is not None and abs(float(lamp.get('beam_speed', 0.0)) - BEAM_SPEED) > 1e-6: lamp['beam_speed'] = BEAM_SPEED
    for f in range(f0, f1 + 1):
        te = tof(on2(f))
        k, d = lh_bend(te)
        ax = Vector((-d[1], d[0], 0.0))                         # UP x d: rotating +Z toward d
        TL.eul(L['mid'], f, tuple(Matrix.Rotation(math.radians(MID_DEG * k), 3, ax).to_euler('XYZ')))
        TL.eul(L['top'], f, tuple(Matrix.Rotation(math.radians(TOP_DEG * k), 3, ax).to_euler('XYZ')))
        cr = _ss(_rng(te, LH_T0 - 0.1, LH_T1 + 0.2))
        for kk in ('base', 'mid', 'top'):
            TL.prop(L[kk], 'crack', f, cr)
        if lamp is not None: TL.prop(lamp, 'beam', f, lh_beam(te))


# ============================================================================================================== event FX
def _fx_events(W, f0, f1):
    fxm = W.get('fx_mod')
    if fxm is None:
        try:
            import fx as fxm
        except Exception: return
    C = W['C'].get('FX')
    done = W.setdefault('_pl_fx', set())

    def want(name, fa, fb):
        if name in done or fb < f0 or fa > f1: return False
        done.add(name); return True
    fh = fr(T_HIT)
    if want('hit', fh, fh + 120):
        c = (-369.0, 399.2, 10.0)
        # thrown out of the smash toward the lens side (east-south-east), clear of the crane as it topples seaward over them;
        # dur long enough for every piece to land in the bay (hidden below z -1.5; at 42 the high ones vanished in mid-air),
        # launches spread over 0.25 s only (the default 0.15 x dur parked pieces at the leg for 0.75 s). Checked on the keyed
        # drawings against the crane's meshes, the quay and the camera.
        fxm.debris(c, f0=fh, dur=120, coll=C, seed=443, count=16, kinds=('container', 'beam', 'chunk'), speed=30.0, spread=0.3,
                   direction=(0.7, -0.65, 0.35), size=0.9, delay=0.05, z_floor=-1.0, name='FX_cA_debris')
        fxm.sparks(c, f0=fh, dur=21, coll=C, seed=422, count=60, speed=26.0, direction=(-0.3, -0.8, 0.5), spread=0.85, size=1.4,
                   name='FX_cA_sparks')
        k = fxm.kira('FX_cA_kira', c, 7.0, coll=C, seed=423)
        fxm.flicker(k, [fh], pattern=(1.0, 0.55, 0.25))
    fs = fr(T_SLAM)
    if want('slam', fs, fs + 140):
        fxm.splash_wall((-373.5, 349.0, 0.0), (-373.5, 318.0, 0.0), height=42.0, f0=fs, dur=96, coll=C, seed=431, zip=0.12, drops=150,
                        name='FX_cA_slam')
        fxm.droplets((-373.5, 330.0, 2.0), f0=fs, dur=36, coll=C, seed=432, count=70, speed=30.0, size=0.9, spread=0.8, radius=6.0,
                     name='FX_cA_slamdrops')
    fu = fr(unit_splash_t())
    if want('box', fu, fu + 90):
        c = unit_centre(unit_splash_t())
        fxm.splash_crown((c.x, c.y, 0.0), radius=6.0, height=26.0, f0=fu, dur=72, coll=C, seed=441, jets=7, drops=60, name='FX_cA_box')
    fw = fr(S.T['wave_dock'])
    if want('gate', fw, fw + 140):
        fxm.splash_wall((-409.0, 396.5, 0.0), (-511.0, 396.5, 0.0), height=38.0, f0=fw, dur=96, coll=C, seed=451, zip=0.42, drops=170,
                        name='FX_dock_wave')
    jt = trolley_jam_t()
    if jt is not None:
        fj = fr(jt - 0.12)
        if want('trolley', fj, fj + 60):
            c = crane_point((0.0, 0.0, 0.0), 'trolley', jt)
            fxm.splash_crown((c.x, c.y, 0.0), radius=4.0, height=14.0, f0=fj, dur=48, coll=C, seed=461, jets=6, drops=40, name='FX_cA_trolley')


# ============================================================================================================== entry
def port_life(W, f0, f1):
    """Key the port's own life for frames f0..f1 (see the header)."""
    if not isinstance(W.get('port'), dict): return
    for fn in (_crane, _flood, _boats, _lighthouse, _fx_events):
        try: fn(W, f0, f1)
        except Exception as ex:
            import traceback; traceback.print_exc(); print('port_life: %s failed: %s' % (fn.__name__, ex))
