# ANCHOR — the mech's shots (CAMERA department): s04 s05 s25 s26 s27 s28 s30 s31 s32 s33 s34 s35 s36 s37 s39 s41 s42 s43.
# Cameras, per-shot keying (mech / chain / city / port life), shot FX and per-shot post. Camera targets are computed from the
# mech's body at keying time (the track where it is baked, the design where it is not), never from fixed world points, so a
# re-baked mech keeps its framing. Impact shakes are aim-only (act_port.shake_fn): the QA's camera acceleration stays clean.
import math, os
import numpy as np
import common as CM, story as S
import mechplan as MP, mechanim as MA, rigmath as RM
import portlife as PL
import act_port as AP

FPS = 24
def tof(f): return (f - 1) / FPS
def fr(t): return int(round(t * FPS)) + 1
def _v(*x): return np.array(x[0] if len(x) == 1 else x, float)
def ss(x): x = min(1.0, max(0.0, x)); return x * x * (3.0 - 2.0 * x)
def rng(t, a, b): return min(1.0, max(0.0, (t - a) / (b - a)))
def lerp(a, b, u): return a + (b - a) * u
def _n(v): v = np.asarray(v, float); return v / max(float(np.linalg.norm(v)), 1e-9)


# ===================================================================================================================== the body
# Where the mech is, frame by frame: the baked track (what key_range keys) or, past the bake, the numpy design (what the live
# solve below keys; numpy rig == Blender's rig to 0.01 m in FK, the IK limbs to a few cm). {frame: {part: world 4x4}}.
HEAD_LOCAL = {'nest': (1.253, -1.352, 7.703), 'gull': (-0.293, -1.431, 8.638), 'chick': (1.219, -1.243, 7.925),
              'antenna_tip': (-2.2, 2.2, 20.6), 'dome': (0.0, -1.0, 9.0)}
CHEST_LOCAL = {'steam_0': (-4.6, 15.5, 21.2), 'steam_1': (0.0, 15.5, 23.6), 'steam_2': (4.6, 15.5, 19.4)}
_BODY = {}
_POSES = [None]
_PREP = [False]


class _Stub:
    POSES = None


def _poses():
    if _POSES[0] is None:
        src = open(os.path.join(CM.ROOT, 'assets', 'mech.py'), encoding='utf-8').read()
        i = src.index('POSES = {'); j = src.index('\n}\n', i); ns = {}; exec(src[i:j + 3], ns); _POSES[0] = ns['POSES']
    return _POSES[0]


def _prep():
    """the design's facts (sleep feet / hands) and the pelvis-band pass over the whole awake range, as a full bake runs it."""
    if _PREP[0]: return
    _Stub.POSES = _poses()
    MA.prepare_np(_Stub.POSES)
    MA.pelvis_pass(_Stub, MA.fr(MA.T_RISE) + 1, MA.NF)
    _PREP[0] = True


def _M(R, p):
    m = np.eye(4); m[:3, :3] = R; m[:3, 3] = p; return m


def _design_body(t):
    _prep()
    D = MA.design(t, _Stub); P = D['pose']; F = RM.frames(P)
    B = {k: F[k].copy() for k in F}
    for sd in ('L', 'R'):
        ft = D['legs'].get(sd)
        if ft is not None and 'p' in ft and ft.get('w', 1.0) > 0.5:
            L = RM.leg(P, ft, sd, F); Rf = RM.foot_R(ft)
            B['knee' + sd] = _M(F['knee' + sd][:3, :3], L['K']); B['ankle' + sd] = _M(Rf, L['A']); B['sole' + sd] = _M(Rf, ft['p'])
        a = D['arms'].get(sd)
        if a is not None and a[3] > 0.5:
            pos, rot, pole, w = a
            if rot is not None:
                A = RM.arm(P, sd, pos, rot, pole, F)
                B['elbow' + sd] = _M(F['elbow' + sd][:3, :3], A['E']); B['wrist' + sd] = _M(np.asarray(rot, float), A['Wr'])
            B['palm' + sd] = _M(np.asarray(rot, float) if rot is not None else F['wrist' + sd][:3, :3], pos)
        else:
            B['palm' + sd] = _M(F['wrist' + sd][:3, :3], (F['wrist' + sd] @ np.r_[RM.palm_offset(sd), 1.0])[:3])
    H = B['head']; C = B['chest']
    B['visor'] = H.copy()
    for n, l in HEAD_LOCAL.items(): B[n] = _M(H[:3, :3], (H @ np.r_[l, 1.0])[:3])
    for n, l in CHEST_LOCAL.items(): B[n] = _M(C[:3, :3], (C @ np.r_[l, 1.0])[:3])
    return B


def _baked(f):
    TR = MA.load(); return 1 <= f <= MA.NF and bool(TR['valid'][f])


def _body(f):
    f = min(max(int(f), 1), MA.NF)
    B = _BODY.get(f)
    if B is None:
        if _baked(f):
            TR = MA.load(); B = {n: TR['W'][f, k].astype(float) for k, n in enumerate(TR['tracked'])}
            H = B['head']; C = B.get('chest')
            for n, l in HEAD_LOCAL.items():
                if n not in B: B[n] = _M(H[:3, :3], (H @ np.r_[l, 1.0])[:3])
            if C is not None:
                for n, l in CHEST_LOCAL.items():
                    if n not in B: B[n] = _M(C[:3, :3], (C @ np.r_[l, 1.0])[:3])
            if 'visor' not in B: B['visor'] = H.copy()
        else:
            B = _design_body(tof(f))
        _BODY[f] = B
    return B


def Mx(name, t):
    """world 4x4 of a body part at t (rotation of the nearer frame, position linear between frames)."""
    x = t * FPS + 1; f = int(math.floor(x)); u = x - f
    a = _body(f)[name]; b = _body(f + 1)[name]
    m = (a if u < 0.5 else b).copy(); m[:3, 3] = a[:3, 3] * (1 - u) + b[:3, 3] * u
    return m


def P(name, t, local=None):
    m = Mx(name, t)
    return m[:3, 3].copy() if local is None else m[:3, :3] @ np.asarray(local, float) + m[:3, 3]


def Ps(name, t, sig=0.25, local=None):
    """the part's point low-passed (gaussian, sig s) over the frames round t: the camera follows the body, not every bob."""
    x = t * FPS + 1; s = max(sig * FPS, 1e-3); n = int(math.ceil(3.0 * s)); c = int(round(x))
    acc = np.zeros(3); ws = 0.0
    for f in range(c - n, c + n + 1):
        w = math.exp(-0.5 * ((f - x) / s) ** 2)
        m = _body(f)[name]
        p = m[:3, 3] if local is None else m[:3, :3] @ np.asarray(local, float) + m[:3, 3]
        acc += w * p; ws += w
    return acc / ws


def Pw(name, t, sig, f_lo, f_hi, local=None):
    """Ps with its window held inside the shot's frames f_lo..f_hi: past either end the part's path is carried on along its
    last (first) 3-frame velocity, so the camera never reacts to what the body does after the cut (or before it)."""
    def at(f):
        m = _body(f)[name]
        return m[:3, 3] if local is None else m[:3, :3] @ np.asarray(local, float) + m[:3, 3]
    x = t * FPS + 1; s = max(sig * FPS, 1e-3); n = int(math.ceil(3.0 * s)); c = int(round(x))
    a = at(f_lo); va = (at(f_lo + 3) - a) / 3.0; b = at(f_hi); vb = (b - at(f_hi - 3)) / 3.0
    acc = np.zeros(3); ws = 0.0
    for f in range(c - n, c + n + 1):
        w = math.exp(-0.5 * ((f - x) / s) ** 2)
        p = a + va * (f - f_lo) if f < f_lo else (b + vb * (f - f_hi) if f > f_hi else at(f))
        acc += w * p; ws += w
    return acc / ws


def mid(*pts):
    return np.mean([np.asarray(p, float) for p in pts], axis=0)


# ===================================================================================================================== cameras
def _aim(pos, az, el, d=100.0):
    a, e = math.radians(az), math.radians(el)
    return np.asarray(pos, float) + d * np.array((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def az_el(pos, tgt):
    d = np.asarray(tgt, float) - np.asarray(pos, float)
    return math.degrees(math.atan2(d[0], d[1])) % 360.0, math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))


def _cat(keys, t):
    """Catmull-Rom through [(t, value or tuple)] (clamped at the ends)."""
    import timeline as TLm
    return TLm.catmull(keys, t)


def angle_keys(K):
    """K [(t, pos, az, el, lens, roll)] -> cam_fn: position and the aim's compass / elevation on Catmull-Rom splines (a pan stays
    a pan however far it turns)."""
    K = sorted(K, key=lambda k: k[0])
    azs = [K[0][2]]
    for k in K[1:]:
        a = k[2]
        while a - azs[-1] > 180.0: a -= 360.0
        while a - azs[-1] < -180.0: a += 360.0
        azs.append(a)
    PK = [(k[0], tuple(k[1])) for k in K]; AK = [(k[0], (azs[i], k[3])) for i, k in enumerate(K)]
    LK = [(k[0], (k[4], k[5] if len(k) > 5 else 0.0)) for k in K]
    def fn(t):
        pos = np.asarray(_cat(PK, t), float); a, e = _cat(AK, t); l, r = _cat(LK, t)
        return pos, _aim(pos, float(a), float(e)), float(l), float(r)
    return fn


def _shake(fn, events, amp=1.2, w=18.0, k=4.5):
    return AP.shake_fn(fn, events, amp, w, k) if events else fn


def _drift(fn, amp=0.25, freq=5.0, seed=31):
    """a faint hand-held drift of the aim (deg-scale, like act_port._shaky)."""
    import timeline as TLm
    def g(t):
        pos, tgt, lens, roll = fn(t)
        return pos, tgt + TLm.shake(t, amp, freq, seed) * np.linalg.norm(tgt - pos) * 0.004, lens, roll
    return g


CAMS = {}


def cam(sid):
    def deco(fn):
        CAMS[sid] = fn; return fn
    return deco


# ===================================================================================================================== mech keying
def _runs(f0, f1, ok):
    out = []
    for f in range(f0, f1 + 1):
        b = ok(f)
        if out and out[-1][2] == b and out[-1][1] == f - 1: out[-1][1] = f
        else: out.append([f, f, b])
    return out


def _mech(W, f0, f1):
    """the mech for f0..f1: baked frames from the track (mechanim.key_range); frames past the bake solved live from the design
    with the same keys a bake writes (rig channels, eyes / beacon / lamps, gull, chick, vines)."""
    M = W.get('mech')
    if not M: return
    for a, b, baked in _runs(f0, f1, _baked):
        try:
            if baked: MA.key_range(W, a, b)
            else: _solve_range(W, a, b)
        except Exception as ex:
            import traceback; traceback.print_exc(); print('act_mech: mech keys failed %d..%d: %s' % (a, b, ex))


def _solve_range(W, f0, f1):
    M = W['mech']; mech = W.get('mech_mod') or __import__('mech'); TL = W['TL']
    _prep()
    anim = M['anim']; props = M['props']; G = M['gull']; vines = M['vines']; c = M['chick']
    g_rest = G['root'].matrix_basis.copy(); gl = tuple(g_rest.translation); ge = tuple(g_rest.to_euler('XYZ'))
    fold = (tuple(G['wingL']['fold']), tuple(G['wingR']['fold']))
    vrest = {v.name: (tuple(v.matrix_basis.translation), tuple(v.matrix_basis.to_euler('XYZ'))) for v in vines}
    keep = {o.name: (o.location.copy(), o.rotation_euler.copy()) for o in anim}
    prev = {}
    print('act_mech: solving the mech live %d..%d (past the bake)' % (f0, f1), flush=True)
    for f in range(f0, f1 + 1):
        t = tof(f)
        MA.solve(M, mech, t)
        for o in anim:
            e = o.rotation_euler.copy()
            if o.name in prev: e.make_compatible(prev[o.name])
            prev[o.name] = e
            TL.loc(o, f, tuple(o.location)); TL.eul(o, f, tuple(e))
        ey, be, la = MA.eyes(t), MA.beacon(t), MA.lamps(t)
        for o in props['eyes']: TL.prop(o, 'eyes', f, ey)
        for o in props['beacon']: TL.prop(o, 'beacon', f, be)
        for o in props['lamps']: TL.prop(o, 'lamps', f, la)
        # the gull is away from the strike (45.6) on; its return (85.9) is not designed yet: it stays hidden on its rest basis
        TL.loc(G['root'], f, gl); TL.eul(G['root'], f, ge); TL.hide(G['root'], f, True)
        for k, w in enumerate((G['wingL'], G['wingR'])): TL.eul(w, f, fold[k]); TL.hide(w, f, True)
        TL.eul(c, f, MA._chick_eul(c, math.radians(MA.chick_peep(t))))
        for v in vines:
            spec = MA.VINE_TEAR.get(MA.vine_key(v.name))
            gone = spec is not None and t >= spec[0]          # every torn vine is long gone (under the water) past the bake
            l, e = vrest[v.name]
            TL.hide(v, f, gone); TL.loc(v, f, l); TL.eul(v, f, e)
    for o in anim:
        o.location, o.rotation_euler = keep[o.name]


# ===================================================================================================================== FX
def _fx():
    import fx as FXM
    return FXM


def _want(W, name):
    done = W.setdefault('_am_fx', set())
    if name in done: return False
    done.add(name); return True


def _live(fa, fb, f0, f1, pad=0):
    return fb >= f0 - pad and fa <= f1 + pad


def footfalls(W, f0, f1, t_lo=None, t_hi=None, big=1.0):
    """the design's splashes (mechplan.SPLASHES: every foot planted in water) alive in f0..f1: a crown round the shin (its
    height from the plant's depth), once per run whichever shot keys it first (neighbouring shots share them)."""
    FXM = _fx(); C = W['C']['FX']
    for (t, (x, y, wz), size, kind, sd) in MP.SPLASHES:
        if t_lo is not None and t < t_lo - 1e-6: continue
        if t_hi is not None and t > t_hi + 1e-6: continue
        h = (10.0 + 30.0 * float(size)) * big; dur = FXM._auto_dur(h)
        fa = fr(t); fb = fa + dur
        if not _live(fa, fb, f0, f1): continue
        nm = 'FX_am_step_%s_%s' % (('%.2f' % t).replace('.', '_'), sd)
        if not _want(W, nm): continue
        FXM.splash_crown((x, y, wz), radius=5.6, height=h, f0=fa, dur=dur, coll=C, seed=int(t * 100) % 9973 + (7 if sd == 'R' else 0),
                         jets=8, drops=int(40 + 50 * size), name=nm)


# ===================================================================================================================== QA
def _allow(a, b):
    return AP._allow_port(a, b)




# ===================================================================================================================== helpers
def look_mix(pos, items):
    """a target along the weighted mean of the unit directions toward [(point, weight)] (blends near and far subjects by angle)."""
    pos = np.asarray(pos, float); d = np.zeros(3)
    for p, w in items:
        if w > 0.0: d += w * _n(np.asarray(p, float) - pos)
    return pos + _n(d) * 100.0


def _bias(fn, daz=None, del_=None):
    """rotate a cam_fn's aim by daz(t) / del_(t) degrees (compass / elevation)."""
    def g(t):
        pos, tgt, lens, roll = fn(t)
        az, el = az_el(pos, tgt)
        return pos, _aim(pos, az + (daz(t) if daz else 0.0), el + (del_(t) if del_ else 0.0)), lens, roll
    return g


def follow(PK, items, lens, sig=0.25):
    """a camera on Catmull-Rom position keys PK [(t, (x, y, z))] aimed by look_mix at body parts / points:
    items [(name or point or fn(t), weight)] (names are low-passed body parts)."""
    def fn(t):
        pos = np.asarray(_cat(PK, t), float)
        its = []
        for p, w in items:
            if isinstance(p, str): q = Ps(p, t, sig)
            elif callable(p): q = p(t)
            else: q = np.asarray(p, float)
            its.append((q, w))
        return pos, look_mix(pos, its), (lens(t) if callable(lens) else lens), 0.0
    return fn


def _sky():
    import act_sky as SKY
    return SKY


def _storm(W, f0, f1):
    try: _sky().storm_sky(W, f0, f1)
    except Exception as ex: print('act_mech: storm_sky failed', ex)


def _rust():
    try:
        SKY = _sky(); return SKY.rust_mat(), SKY.set_mat
    except Exception:
        return None, None


def _port(W, f0, f1):
    PL.port_life(W, f0, f1)


LH = np.array((float(S.LIGHTHOUSE[0]), float(S.LIGHTHOUSE[1]), 0.0))


def city_mid(t):
    """the city's middle (its houses, trees and rock ~195 m over the collar ring)."""
    M = CM.city_matrix(t); return M[:3, :3] @ _v(0.0, 0.0, 195.0) + M[:3, 3]
EV_RUN = [(t, 0.5 if t < 57.4 else 0.7) for (t, _, _, k, _) in MP.SPLASHES if k in ('run', 'step', 'step_first', 'stand')]


def _events(t0, t1, ev, pad=0.0):
    return [(t, s) for (t, s) in ev if t0 - 1.5 <= t <= t1 + pad]


# ===================================================================================================================== s04
@cam('s04')
def cam_s04(f0, f1):
    """over the sleeping giant's shoulder: NE of its head and above it, the head + mast + nest big on the right (the sunlit side),
    the dock running out to the harbour, the cranes, the floating city with its chain on the left, the lighthouse right of
    centre. A slow push toward the head."""
    t0, t1 = tof(f0), tof(f1)
    h0 = P('head', t0)
    def fn(t):
        u = ss(rng(t, t0 - 0.4, t1 + 0.4))
        pos = h0 + lerp(_v(17.0, 15.0, 3.0), _v(15.5, 13.6, 2.6), u)     # 5 m south of the building north of the dock, over its roof
        return pos, _aim(pos, 185.0, 10.0), 16.0, 0.0
    return _drift(fn, 0.5, 3.0, 41)


def s04(W, f0, f1):
    """WIDE: the port at dawn over the sleeping mech's shoulder: dock 3 and its overgrown giant, the cranes, the floating city
    and its chain far off, the lighthouse."""
    CM.base(W, f0, f1, cam_s04(f0, f1))
    CM.city_key(W, f0, f1); CM.chain_key(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)


# ===================================================================================================================== s05
@cam('s05')
def cam_s05(f0, f1):
    """MACRO on the head from its front-left (the sunlit side): the dark visor, 'UNIT 07' on the brow, the '07' ear disc, the
    moss, the nest on the crown with the chick and the gull. A slow push and a small arc."""
    t0, t1 = tof(f0), tof(f1)
    def T_(t):
        H = Mx('head', t); return H[:3, :3] @ _v(0.4, -2.3, 6.4) + H[:3, 3]
    T0 = T_(t0)
    def fn(t):
        u = ss(rng(t, t0 - 0.3, t1 + 0.3))
        pos = _aim(T0, lerp(146.0, 152.0, u), lerp(12.0, 10.0, u), lerp(18.0, 16.5, u))
        return pos, T_(t), lerp(30.0, 32.0, u), 0.0
    return _drift(fn, 0.5, 3.0, 51)


def s05(W, f0, f1):
    CM.base(W, f0, f1, cam_s05(f0, f1))
    _port(W, f0, f1)
    _mech(W, f0, f1)


# ===================================================================================================================== s25
S25_EV = [(49.3, 0.5), (49.6, 0.35), (50.0, 0.6), (51.5, 0.5)]


@cam('s25')
def cam_s25(f0, f1):
    """LOW on the east quay, 3/4 front-left of the rising giant (sunlit; the storm behind it in the west): the camera tilts up
    with the head as it stands, creeping in along the quay edge."""
    t0, t1 = tof(f0), tof(f1)
    def fn(t):
        u = ss(rng(t, t0 - 0.3, t1 + 0.3))
        pos = lerp(_v(-404.0, 533.0, 6.6), _v(-407.0, 541.0, 6.0), u)
        tgt = Ps('head', t, 0.3) * 0.4 + Ps('chest', t, 0.3) * 0.6
        return pos, tgt, lerp(22.0, 21.0, u), 0.0
    fn = _bias(fn, daz=lambda t: 5.0 * ss(rng(t, 50.4, 52.0)))     # the city's rim would peek into the top-left corner (no CITY here)
    return _shake(fn, S25_EV, 0.9)


def _rise_fx(W):
    if not _want(W, 'rise'): return
    FXM = _fx(); C = W['C']['FX']; rm, setm = _rust()
    # the vines give (49.3 arms, 50.0 jaw, 51.5 chest / knee): rust dust bursts off the joints that tear free; water streams
    # off the forearms, knees and hips as they come up out of the flooded dock (-6)
    for (t, parts, seed) in ((49.3, ('shoulderL', 'shoulderR', 'elbowL', 'elbowR'), 2501), (50.0, ('neck',), 2511),
                             (51.5, ('chest', 'kneeL'), 2521)):
        for k, nm in enumerate(parts):
            p = P(nm, t)
            # a quick burst of fine dust: a dozen small puffs, torn apart from a third of their life (7 puffs of 3 m swelled
            # into one brown ball that hung at the knee like a sack)
            o = FXM.steam(tuple(p), f0=fr(t), dur=30, coll=C, seed=seed + k, count=12, size=1.1, speed=7.5, direction=(0.0, -0.4, 1.0),
                          wind=(-3.0, 0.0, 0.0), life=0.9, spread=0.6, tear=0.3, name='FX_am_rust_%s_%d' % (nm, int(round(t * 10))))
            if rm is not None: setm(o, rm)
            # and flakes of rust scale shaken off the joint, tumbling down into the dock
            FXM.debris(tuple(p), f0=fr(t), dur=60, coll=C, seed=seed + 40 + k, count=16, kinds=('flake',), speed=7.0, spread=0.85,
                       direction=(0.0, -0.5, 0.6), size=1.3, spin=9.0, radius=1.2, delay=0.25, gravity=9.81, z_floor=-6.0,
                       name='FX_am_flake_%s_%d_' % (nm, int(round(t * 10))))
    # water pours off them as they come up: from the moment each part clears the flood (-6; track: wrists ~49.8, shins ~49.6,
    # hips ~50.05) six small bursts 0.16 s apart follow it up, the drops falling off round it into the dock (a burst of 55 thrown
    # UP from the waterline read as a white spiky star at the knee)
    for (nm, ta, seed) in (('wristL', 49.8, 2531), ('wristR', 49.8, 2532), ('kneeL', 49.6, 2533), ('kneeR', 49.7, 2534),
                           ('hipL', 50.05, 2535), ('hipR', 50.05, 2536)):
        for q in range(6):
            tq = ta + 0.16 * q; p = P(nm, tq)
            FXM.droplets((float(p[0]), float(p[1]), float(p[2])), f0=fr(tq), dur=48, coll=C, seed=seed * 10 + q, count=12, speed=2.5,
                         size=0.75, spread=0.5, up=(0.0, 0.0, -1.0), radius=3.0, delay=0.15, z_floor=-6.0,
                         name='FX_am_shed_%s_%d' % (nm, q))


def s25(W, f0, f1):
    """It rises out of the flooded dock, tearing its vines, rust dust bursting off the joints, water streaming off it (low
    angle from the east quay)."""
    CM.base(W, f0, f1, cam_s25(f0, f1))
    _storm(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)
    footfalls(W, f0, f1)
    _rise_fx(W)


# ===================================================================================================================== s26
@cam('s26')
def cam_s26(f0, f1):
    """from low in the dock behind its right leg on the first step's splash, the camera cranes up past the right shoulder while
    the giant looks up: over its shoulder the drifting city and its chain fill the sky (aim blended by angle splash -> head ->
    city)."""
    t0, t1 = tof(f0), tof(f1)
    sp = next(s for s in MP.SPLASHES if s[3] == 'step_first')
    spl = _v(sp[1][0], sp[1][1], sp[1][2] + 9.0)
    PK = [(t0 - 0.1, (-497.0, 583.0, 3.0)), (53.3, (-495.0, 580.0, 16.0)), (54.2, (-491.0, 576.0, 40.0)), (t1 + 0.1, (-488.0, 573.0, 57.0))]
    def fn(t):
        pos = np.asarray(_cat(PK, t), float)
        ws = 1.0 - ss(rng(t, 52.7, 53.7)); wc = ss(rng(t, 53.7, 54.9)); wh = max(0.0, 1.0 - ws - wc)
        tgt = look_mix(pos, [(spl, ws), (Ps('head', t, 0.3), wh + 0.5 * wc), (city_mid(t), 0.5 * wc)])
        return pos, tgt, lerp(22.0, 18.0, ss(rng(t, 53.5, 55.0))), 0.0
    return _shake(fn, [(52.4, 0.9), (53.0, 0.45)], 1.1)


def s26(W, f0, f1):
    """The first step down the flooded dock: a huge splash; it lifts its head to the drifting city."""
    CM.base(W, f0, f1, cam_s26(f0, f1))
    _storm(W, f0, f1)
    CM.city_key(W, f0, f1); CM.chain_key(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)
    footfalls(W, f0, f1, big=1.25)


# ===================================================================================================================== s27
@cam('s27')
def cam_s27(f0, f1):
    """leading track: a drone backs away down the dock basin 80 m ahead of the charging giant, so it runs at the lens (face,
    visor and the spray it throws), keeping its screen-left drift from s26/s28. The rig flies over the basin itself, 14+ m
    east of the giant's line and west of railcrane E's jib (the jib never crosses the line of sight), out over the gate and
    sinks toward the water once it is over the harbour; the giant gains on it (82 -> 68 m) and looms over the low lens at
    the cut to s28. Looking NNW back at the port: the city and the chain stay behind the camera."""
    t0, t1 = tof(f0), tof(f1)
    def fn(t):
        r = Ps('root', t, 0.3); u = ss(rng(t, t0, t1))
        y = float(r[1]) - lerp(82.0, 68.0, u)
        pos = _v(lerp(-446.0, -438.0, u), y, lerp(44.0, 26.0, ss(rng(y, 430.0, 330.0))))
        tgt = Ps('chest', t, 0.25) + _v(0.0, 0.0, -8.0)
        return pos, tgt, 18.0, 0.0
    return _shake(fn, _events(t0, t1, EV_RUN), 0.8)


def s27(W, f0, f1):
    CM.base(W, f0, f1, cam_s27(f0, f1))
    _storm(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)
    footfalls(W, f0, f1, big=1.15)


# ===================================================================================================================== s28
S28_BOATS = [  # (boat index, its position at 58.2, heading az deg): three fishing boats beating home NE in a lane 26-36 m
    # beyond its track (the far side from the lens): each slips through the gap between its legs on screen (boat 6 ~1385,
    # boat 5 ~1389, boat 7 ~1403); hulls 18+ m from every leg segment, 29+ m from each other, 100-130 m from the lens
    (5, (-506.5, 323.2), 40.0), (6, (-493.2, 364.4), 42.0), (7, (-574.0, 255.9), 38.0)]
S28_V = 15.0


@cam('s28')
def cam_s28(f0, f1):
    """low on the swell (10 m) SE of its track, a chase boat running ahead of it: it charges in three-quarter front, then
    strides past in profile right to left (head and visor in frame throughout); the fishing boats beating home the other way
    slip by beyond its legs, seen between them as it strides."""
    t0, t1 = tof(f0), tof(f1)
    A0 = _v(-440.0, 250.0, 10.0); A1 = _v(-525.0, 128.0, 10.0)
    def fn(t):
        u = rng(t, t0 - 0.2, t1 + 0.2)
        pos = lerp(A0, A1, u)
        tgt = Ps('chest', t, 0.2) * 0.6 + Ps('head', t, 0.2) * 0.4 + _v(0.0, 0.0, -14.0)      # the waterline (and the boats) in
        return pos, tgt, 24.0, 0.0                                                          # the lower third, the dome under the top
    return _shake(fn, _events(t0, t1, EV_RUN), 0.7)


def boat28(i, t):
    for (k, p, hd) in S28_BOATS:
        if k == i: break
    a = math.radians(hd); d = np.array((math.sin(a), math.cos(a)))
    q = np.array(p, float) + d * S28_V * (t - 58.2)
    w = 2 * math.pi * 0.9; ph = 1.37 * i
    heave = 0.45 * math.sin(w * t + ph) + 0.25 * math.sin(2.3 * w * t + 2 * ph)
    pitch = -math.radians(4.5) - math.radians(3.2) * math.sin(w * t + ph + 0.9)
    roll = -math.radians(2.0) * math.sin(0.7 * w * t + ph)
    yaw = math.atan2(d[1], d[0]) + math.radians(1.2) * math.sin(0.5 * w * t + ph)
    return (float(q[0]), float(q[1]), heave), (roll, pitch, yaw)


def _boats28(W, f0, f1):
    P_ = W.get('port'); boats = P_.get('boats') if isinstance(P_, dict) else None
    if not boats: return
    TL = W['TL']
    for f in range(f0, f1 + 1):
        for (i, _, _) in S28_BOATS:
            loc, rot = boat28(i, tof(f)); TL.loc(boats[i], f, loc); TL.eul(boats[i], f, rot)
    if _want(W, 's28_bows'):
        FXM = _fx(); C = W['C']['FX']
        fa = f0 - 6; n = int(math.ceil((f1 + 3 - fa) / 3.0))
        for (i, _, _) in S28_BOATS:
            L = float(boats[i].get('length', 18.0)); pts = []
            for k in range(n + 1):
                (x, y, z), (r, pch, yaw) = boat28(i, tof(fa + 3 * k))
                pts.append((x + math.cos(yaw) * (L * 0.5 - 1.5), y + math.sin(yaw) * (L * 0.5 - 1.5)))
            FXM.spray_trail(pts, f0=fa, dur=3 * n, coll=C, seed=2801 + i, size=4.0 + 0.4 * L / 10.0, skip=0.42, name='FX_am_s28_boat%d' % i)


def s28(W, f0, f1):
    """Fishing boats pass between its legs the other way."""
    CM.base(W, f0, f1, cam_s28(f0, f1))
    _storm(W, f0, f1)
    _port(W, f0, f1)
    _boats28(W, f0, f1)             # after port_life: these keys win for the shot's frames (the fleet is moored far east)
    _mech(W, f0, f1)
    footfalls(W, f0, f1)


# ===================================================================================================================== s30
@cam('s30')
def cam_s30(f0, f1):
    """from the lighthouse gallery (WNW side, 1.5 m over the deck): the giant thunders down the breakwater toward the lens,
    passes the tower's west side a few metres off the gallery and crouches on the tip; the camera pans with it N -> W -> SW
    (screen right to left). Early aim biased left: the trailing chain stays out of frame."""
    t0, t1 = tof(f0), tof(f1)
    a = math.radians(304.0)
    # 4.6 m over the deck (z 59.0): clear of the lamp's rotating beam cone (axis z 61.9, r 1.0 out here: z 60.9..62.9) by
    # 0.7 m and of the lantern roof (r 2.95, z 63.4..63.7) by 1.3 m; the railing (top 60.6) stays under the frame
    pos0 = _v(LH[0] + 4.3 * math.sin(a), LH[1] + 4.3 * math.cos(a), 63.6)
    def fn(t):
        tgt = Ps('chest', t, 0.22) * 0.55 + Ps('head', t, 0.22) * 0.45
        return pos0, tgt, 24.0, 0.0
    fn = _bias(fn, daz=lambda t: -5.0 * (1.0 - ss(rng(t, 61.5, 62.3))))
    return _shake(fn, _events(t0, t1, [(61.6, 0.35), (62.2, 0.55), (62.8, 0.75)]), 1.0)


def s30(W, f0, f1):
    """It runs along the breakwater past the lighthouse (low angle from the gallery)."""
    CM.base(W, f0, f1, cam_s30(f0, f1))
    _storm(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)


# ===================================================================================================================== s31
T_BOLT31 = 64.2


@cam('s31')
def cam_s31(f0, f1):
    """low on the water SSE of the landing, the camera tilts up with the leap: the giant launches off the breakwater tip, flies
    toward the lens against the flash (64.2: the bolt behind it, the sky white, its underside dark) and drops toward the sea."""
    t0, t1 = tof(f0), tof(f1)
    fn = follow([(t0 - 0.1, (-699.0, -329.0, 12.0)), (t1 + 0.1, (-701.0, -332.0, 11.0))], [('chest', 0.6), ('head', 0.4)], 35.0, 0.18)
    fn = _bias(fn, daz=lambda t: -2.5, del_=lambda t: -2.5)   # the chain hangs just off the right edge, the city's falls just over
                                                                # the top (neither CHAIN nor CITY is in this shot's sets)
    return _shake(fn, [(63.4, 0.55), (64.2, 0.35)], 0.9)


def _bolt31(W):
    if not _want(W, 's31_bolt'): return
    FXM = _fx(); C = W['C']['FX']; fs = fr(T_BOLT31)
    b = FXM.bolt('FX_am_s31_bolt', (-830.0, 330.0, 1250.0), (-790.0, 190.0, 0.0), seed=3101, branches=6, width=1.6, coll=C, star=False)
    FXM.flicker(b, [fs], pattern=(1.0, 0.3, 1.0, 0.6, 0.3))


def s31(W, f0, f1):
    """It leaps from the breakwater tip against lightning (silhouette)."""
    CM.base(W, f0, f1, cam_s31(f0, f1), local_flash=0.4)
    _storm(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)
    _bolt31(W)


# ===================================================================================================================== s32
@cam('s32')
def cam_s32(f0, f1):
    """low over the water NE of the landing, looking WSW into the storm: it crashes down waist-deep in a crown of water, the ring
    wave races out toward the lens, it wades on. Threaded between the absent sets: the lighthouse head's armour just off the
    right edge early, the trailing chain end just off the left edge late (a slow pan right carries the frame between them)."""
    t0, t1 = tof(f0), tof(f1)
    fn = follow([(t0 - 0.1, (-650.0, -230.0, 14.0)), (t1 + 0.1, (-650.0, -230.0, 14.0))], [('chest', 0.75), ('head', 0.25)], 30.0, 0.25)
    fn = _bias(fn, daz=lambda t: lerp(-3.0, 3.0, ss(rng(t, t0, t1))))
    return _shake(fn, [(65.4, 1.0), (66.45, 0.35)], 1.2)


def _land_fx(W, f0, f1):
    FXM = _fx(); C = W['C']['FX']
    if _want(W, 'land'):
        r = MP.root_at(MP.LAND_T); fl = fr(MP.LAND_T)
        FXM.splash_crown((float(r[0]), float(r[1]), 0.0), radius=16.0, height=46.0, f0=fl, dur=None, coll=C, seed=3201, jets=12,
                         drops=160, name='FX_am_land_crown')
        FXM.foam_ring((float(r[0]), float(r[1]), 0.0), 12.0, 170.0, f0=fl, dur=60, coll=C, seed=3202, band=0.8, name='FX_am_land_ring')
        # (06.11) thrown away from the body (inward ones fell back over the knee, white cones on it at f1612), and alive until
        # each one meets the sea (3.4 s at most): at dur 40 the whole burst vanished in mid-air on s32's last frame (1613)
        FXM.droplets((float(r[0]), float(r[1]), 2.0), f0=fl, dur=84, coll=C, seed=3203, count=90, speed=26.0, size=1.0, spread=0.85,
                     radius=12.0, outward=True, name='FX_am_land_drops')
    footfalls(W, f0, f1, t_lo=MP.LAND_T + 0.5)


def s32(W, f0, f1):
    """Lands waist-deep, ring wave."""
    CM.base(W, f0, f1, cam_s32(f0, f1))
    _storm(W, f0, f1)
    _mech(W, f0, f1)
    _land_fx(W, f0, f1)


# ===================================================================================================================== s33
def _J(i):
    return lambda t: CM.chain_joints(int(round(t * FPS)) + 1)[i]


@cam('s33')
def cam_s33(f0, f1):
    """low east of it, looking west past the reaching left hand: the end link skips over the waves, the hand chases it and
    closes on it (69.3); the visor behind."""
    t0, t1 = tof(f0), tof(f1)
    fn = follow([(t0 - 0.1, (-615.0, -300.0, 9.0)), (t1 + 0.1, (-618.0, -306.0, 9.0))],
                [('palmL', 0.45), (_J(80), 0.2), ('head', 0.35)], 30.0, 0.25)
    return _shake(fn, [(69.3, 0.6)], 0.9)


def _end_skip(W, f0, f1):
    if not _want(W, 'end_skip'): return
    FXM = _fx(); C = W['C']['FX']
    fa, fb = max(f0, fr(67.2)), fr(69.25)
    pts = []
    for f in range(fa, fb + 1, 2):
        J = CM.chain_joints(f); pts.append((float(J[80][0]), float(J[80][1])))
    # (06.11) the run ends as the hand closes on the link (1663): its last skip's spikes, drops and bow drops fall on until the
    # cut to s34 and the wake goes with the cut (all of it vanished at 1665, mid-shot; the wake, frozen, at 1713 in s34)
    FXM.spray_trail(pts, f0=fa, dur=fb - fa, coll=C, seed=3301, size=7.0, skip=0.59, cut=fr(70.0), name='FX_am_end_skip')
    fg = fr(MP.GRAB_T); J = CM.chain_joints(fg)[80]
    # alive until every drop meets the sea (~2.1 s at most; at dur 24 the burst vanished in mid-air at 1688, in s34)
    FXM.droplets((float(J[0]), float(J[1]), float(J[2])), f0=fg, dur=63, coll=C, seed=3302, count=50, speed=12.0, size=0.7, spread=0.8,
                 radius=2.0, z_floor=0.0, name='FX_am_grab_drops')


def s33(W, f0, f1):
    """The hand reaches, the last link skips away, the hand closes on it."""
    CM.base(W, f0, f1, cam_s33(f0, f1))
    _storm(W, f0, f1)
    CM.chain_key(W, f0, f1)
    _mech(W, f0, f1)
    footfalls(W, f0, f1, t_lo=66.9)
    _end_skip(W, f0, f1)


# ===================================================================================================================== s34
@cam('s34')
def cam_s34(f0, f1):
    """low east of it, looking west and up: the chain snaps taut out of the hand toward the city (up out of frame) throwing off
    water; it braces, its feet ploughing the seabed. The jolt at 70.0 shakes the frame."""
    t0, t1 = tof(f0), tof(f1)
    fn = follow([(t0 - 0.1, (-615.0, -305.0, 6.0)), (t1 + 0.1, (-617.0, -310.0, 6.5))],
                [('head', 0.45), ('palmL', 0.3), (_J(66), 0.25)], 24.0, 0.3)
    fn = _bias(fn, del_=lambda t: -5.0)         # the city's falls hang just over the top edge (no CITY here)
    return _shake(fn, [(70.0, 1.0), (70.55, 0.4), (71.3, 0.3)], 1.3)


def _taut_fx(W):
    if not _want(W, 'taut'): return
    FXM = _fx(); C = W['C']['FX']; ft = fr(70.0)
    J = CM.chain_joints(ft); J1 = CM.chain_joints(ft + 2)
    # water torn off every link along the run (not 8 bursts of 40 born in one drawing: each read as a white spiky star stuck
    # on the chain on the cut's first frame), thrown over the first 6 drawings of the snap
    for k, j in enumerate(range(56, 80)):
        p = J[j]; dv = J1[j] - J[j]
        up = _n(dv + _v(0.0, 0.0, 0.2)) if np.linalg.norm(dv) > 1e-3 else _v(0.0, 0.0, 1.0)
        # (06.11) falling on until the cut to s35 (1729): at dur 30 the whole cascade along the chain vanished at 1711, mid-shot;
        # delay 0.125 x 48 frames = the same launches as 0.2 x 30
        FXM.droplets(tuple(float(x) for x in p), f0=ft, dur=48, coll=C, seed=3401 + k, count=14, speed=10.0, size=0.7, spread=0.9,
                     up=tuple(float(x) for x in up), radius=1.6, delay=0.125, z_floor=0.0, name='FX_am_taut_drops%02d' % k)
    for sd in ('L', 'R'):
        s = P('sole' + sd, 70.0)
        FXM.splash_wall((float(s[0]) - 6.0, float(s[1]) + 5.0, 0.0), (float(s[0]) + 6.0, float(s[1]) - 5.0, 0.0), height=12.0, f0=ft,
                        dur=36, coll=C, seed=3410 + (sd == 'R'), zip=0.2, drops=60, name='FX_am_plough%s' % sd)


def s34(W, f0, f1):
    """The chain snaps taut throwing off water; its feet plough the seabed."""
    CM.base(W, f0, f1, cam_s34(f0, f1))
    _storm(W, f0, f1)
    CM.chain_key(W, f0, f1)
    _mech(W, f0, f1)
    _taut_fx(W)


# ===================================================================================================================== s35
@cam('s35')
def cam_s35(f0, f1):
    """CU from below its front left-of-centre (SW of the head), looking up at the face against the storm sky as it backs away
    hauling: the visor flickers (73.0-73.5), steam blasts from the backpack vents and the joints, plates crack with sparks.
    Looking up keeps the absent port (its land and lighthouse) under the frame; the held chain runs behind the lens."""
    t0, t1 = tof(f0), tof(f1)
    def fn(t):
        u = ss(rng(t, t0 - 0.2, t1 + 0.2))
        # the low-pass is held inside the shot: s36's pivot right after the cut (head at 60-140 m/s) must not drag the lens off
        # the face in the last frames (the back-and-climb at 50 m/s keeps the head where it is in frame)
        h = Pw('head', t, 0.3, f0, f1)
        pos = _aim(h, lerp(228.0, 222.0, u), lerp(-18.0, -16.0, u), lerp(30.0, 27.0, u))
        tgt = Pw('head', t, 0.15, f0, f1) + _v(0.0, 0.0, 4.5)
        return pos, tgt, 45.0, 0.0
    return _shake(fn, [(72.0, 0.35), (72.6, 0.3), (73.05, 0.45)], 0.8)


def _strain_fx(W):
    if not _want(W, 'strain'): return
    FXM = _fx(); C = W['C']['FX']
    for k, nm in enumerate(('steam_0', 'steam_1', 'steam_2')):
        for j, t in enumerate((72.0, 72.75)):
            p = P(nm, t)
            FXM.steam(tuple(p), f0=fr(t), dur=30, coll=C, seed=3501 + 3 * k + j, count=8, size=2.6, speed=9.0, direction=(0.0, 0.3, 1.0),
                      wind=(-3.0, 1.0, 0.0), life=1.2, name='FX_am_vent%d_%d' % (k, j))
    for k, (t, nm, loc) in enumerate(((72.15, 'shoulderL', (3.0, -1.0, 4.0)), (72.6, 'elbowL', (0.0, -1.5, -2.0)),
                                      (73.05, 'shoulderR', (-3.0, -1.0, 4.0)), (73.3, 'neck', (0.0, -2.0, 1.0)))):
        q = P(nm, t, loc)
        FXM.sparks(tuple(q), f0=fr(t), dur=15, coll=C, seed=3510 + k, count=36, speed=14.0, direction=(0.0, 0.0, 1.0), spread=0.9,
                   size=0.8, life=(0.2, 0.5), name='FX_am_crack%d' % k)
        FXM.steam(tuple(q), f0=fr(t), dur=24, coll=C, seed=3520 + k, count=5, size=1.8, speed=6.0, direction=(0.0, 0.0, 1.0),
                  wind=(-3.0, 1.0, 0.0), life=0.9, name='FX_am_jsteam%d' % k)


def s35(W, f0, f1):
    """CU: armour cracks, steam from the joints, visor flickers."""
    CM.base(W, f0, f1, cam_s35(f0, f1))
    _storm(W, f0, f1)
    _mech(W, f0, f1)
    _strain_fx(W)
    # no footfall crowns here: the lens rides 30-40 m up beside its backing steps and the 73.02 crown's jets fill the frame at
    # the cut (the feet are far under this close-up anyway)


# ===================================================================================================================== s36
@cam('s36')
def cam_s36(f0, f1):
    """its POV: from just over the visor, up the taut chain at the city hanging over it like a stone sky, the waterspout
    beside it; the view rides the head's path low-passed (it backs, pivots and climbs the mound) and stays on the city."""
    t0, t1 = tof(f0), tof(f1)
    def fn(t):
        pos = Ps('head', t, 0.45) + _v(0.0, 0.0, 4.0)
        sp = S.spout_pos(t)
        its = [(S.collar(t) + _v(0.0, 0.0, 70.0), 0.6), (_J(40)(t), 0.2)]
        if sp is not None: its.append((_v(sp[0], sp[1], 260.0), 0.2))
        return pos, look_mix(pos, its), 18.0, 0.0
    return _shake(fn, [(73.95, 0.4), (74.3, 0.4), (74.6, 0.3)], 0.8)


def s36(W, f0, f1):
    """From the mech looking up: the city like a stone sky, the waterspout beside it."""
    CM.base(W, f0, f1, cam_s36(f0, f1))
    _storm(W, f0, f1)
    CM.city_key(W, f0, f1); CM.chain_key(W, f0, f1)


# ===================================================================================================================== s37
@cam('s37')
def cam_s37(f0, f1):
    """SSW of the lighthouse at 140 m, 40 m up, looking NNE with the chain coming down past the lens from the city: it charges
    round the drum from the right (SE), passes behind the tower (N) and comes out on the left (W) in full view, braced, the
    chain wound into the groove on the near side; the tower bends toward the lens and holds (side-lit by the low sun). A
    slow push and drift left."""
    t0, t1 = tof(f0), tof(f1)
    top = LH + _v(0.0, 0.0, 52.0)
    def at(az, d, z):
        a = math.radians(az); return (LH[0] + d * math.sin(a), LH[1] + d * math.cos(a), z)
    fn = follow([(t0 - 0.1, at(197.0, 142.0, 41.0)), (t1 + 0.1, at(193.0, 136.0, 39.0))], [('chest', 0.55), (top, 0.45)], 28.0, 0.35)
    return _shake(fn, [(77.4, 0.5), (77.8, 0.4), (78.2, 0.8)], 1.0)


def _bite(t):
    """where the chain coming down from the city first lies in the drum's groove at t (r ~18, z ~24 round the lighthouse): the
    lowest-index link in the groove, and its travel direction."""
    f = fr(t); J = CM.chain_joints(f)
    r = np.hypot(J[:, 0] - LH[0], J[:, 1] - LH[1])
    idx = [i for i in range(40, 80) if abs(r[i] - 18.0) < 1.2 and 22.5 < J[i, 2] < 25.8]
    if not idx: return None, None
    i = idx[0]; Jp = CM.chain_joints(f - 2)
    v = J[i] - Jp[i]
    return J[i], (_n(v) if np.linalg.norm(v) > 1e-3 else _v(0.0, 0.0, 1.0))


def _wind_fx(W):
    if not _want(W, 'wind'): return
    FXM = _fx(); C = W['C']['FX']
    # the links bite the stone where the chain first lies in the groove: sparks there as it winds (77.0 .. 78.2)
    for k, t in enumerate((77.05, 77.35, 77.6, 77.85, 78.1)):
        p, v = _bite(t)
        if p is None: continue
        out = _n(_v(p[0] - LH[0], p[1] - LH[1], 0.0))
        d = _n(out * 0.6 + v * 0.5 + _v(0.0, 0.0, 0.5))
        FXM.sparks(tuple(float(x) for x in p), f0=fr(t), dur=18, coll=C, seed=3701 + k, count=40, speed=16.0,
                   direction=tuple(float(x) for x in d), spread=0.7, size=1.0, life=(0.2, 0.55), name='FX_am_grind%d' % k)
    # the tower gives (77.4 .. 78.2): stone chips off the drum's cornice on the pull side (no white puff: it read as spray)
    fc = fr(77.5); k_, dpull = PL.lh_bend(78.2)
    c = LH + _v(dpull[0] * 15.5, dpull[1] * 15.5, 27.5)
    FXM.debris(tuple(float(x) for x in c), f0=fc, dur=48, coll=C, seed=3710, count=14, kinds=('chunk',), speed=12.0, spread=0.8,
               direction=(float(dpull[0]) * 0.6, float(dpull[1]) * 0.6, 0.8), size=0.6, radius=5.0, delay=0.3, z_floor=5.0,
               name='FX_am_chips')


def s37(W, f0, f1):
    """It winds the chain round the lighthouse; the lighthouse bends and holds."""
    CM.base(W, f0, f1, cam_s37(f0, f1))
    _storm(W, f0, f1)
    CM.chain_key(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)
    _wind_fx(W)


# ===================================================================================================================== s39
@cam('s39')
def cam_s39(f0, f1):
    """low on the breakwater's cap 165 m north of the lighthouse, the cap leading into the frame: the giant braced beside the
    tower, the chain wound round the drum rising across the frame to the whole city over them; it shudders and sags, the city
    stops. A slow creep along the cap."""
    t0, t1 = tof(f0), tof(f1)
    drum = LH + _v(0.0, 0.0, 24.0)
    fn = follow([(t0 - 0.1, (-700.0, -2.0, 13.0)), (t1 + 0.1, (-700.0, -9.0, 12.5))],
                [(drum, 0.3), ('head', 0.25), (city_mid, 0.45)], 16.0, 0.4)
    return _shake(fn, [(80.6, 0.5)], 0.8)


def s39(W, f0, f1):
    """The chain shudders and slackens; the city stops."""
    CM.base(W, f0, f1, cam_s39(f0, f1))
    _storm(W, f0, f1)
    CM.city_key(W, f0, f1); CM.chain_key(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)


# ===================================================================================================================== s41
@cam('s41')
def cam_s41(f0, f1):
    """WIDE, golden, calm: low over the harbour NNE of the lighthouse, the low sun from the left: the giant holding the chain
    wound round the lighthouse, the chain rising to the whole city at rest over the open sea; a slow push."""
    t0, t1 = tof(f0), tof(f1)
    drum = LH + _v(0.0, 0.0, 24.0)
    fn = follow([(t0 - 0.1, (-599.0, 22.0, 14.0)), (t1 + 0.1, (-604.0, 13.0, 13.5))],
                [(drum, 0.3), ('head', 0.25), (city_mid, 0.45)], 16.0, 0.4)
    return _drift(fn, 0.4, 2.5, 411)


def s41(W, f0, f1):
    CM.base(W, f0, f1, cam_s41(f0, f1))
    CM.city_key(W, f0, f1); CM.chain_key(W, f0, f1)
    _port(W, f0, f1)
    _mech(W, f0, f1)


# ===================================================================================================================== s42
@cam('s42')
def cam_s42(f0, f1):
    """CU of the head and its nest from its left, a little above (ENE, the low sun behind the lens): the chick in the nest,
    the open sea beyond, where the gull comes home from. Looking down keeps the absent port and chain out of frame."""
    t0, t1 = tof(f0), tof(f1)
    def T_(t):
        H = Mx('head', t); return H[:3, :3] @ _v(0.6, -0.5, 6.0) + H[:3, 3]
    T0 = T_(t0)
    def fn(t):
        u = ss(rng(t, t0 - 0.3, t1 + 0.3))
        pos = _aim(T0, lerp(70.0, 80.0, u), lerp(16.0, 12.0, u), lerp(21.0, 18.0, u))
        return pos, T_(t), 40.0, 0.0
    return _drift(fn, 0.4, 2.5, 421)


def s42(W, f0, f1):
    CM.base(W, f0, f1, cam_s42(f0, f1))
    _mech(W, f0, f1)


# ===================================================================================================================== s43
@cam('s43')
def cam_s43(f0, f1):
    """the face from just below, a slow push, the golden sky behind it: the visor's light dies (88.2 -> 89.4)."""
    t0, t1 = tof(f0), tof(f1)
    def T_(t):
        H = Mx('head', t); return H[:3, :3] @ (AP.EYES_MID + _v(0.0, 0.0, 0.6)) + H[:3, 3]
    H0 = Mx('head', t0); n = H0[:3, :3] @ AP.VIS_N; az0 = math.degrees(math.atan2(n[0], n[1]))
    T0 = T_(t0)
    def fn(t):
        u = ss(rng(t, t0 - 0.3, t1 + 0.3))
        pos = _aim(T0, az0, lerp(-20.0, -18.0, u), lerp(15.0, 12.5, u))
        return pos, T_(t), lerp(42.0, 46.0, u), 0.0
    return _drift(fn, 0.35, 2.5, 431)


def s43(W, f0, f1):
    CM.base(W, f0, f1, cam_s43(f0, f1))
    _mech(W, f0, f1)


# ===================================================================================================================== post, QA
_RAIN = dict(AP.STORM_POST, haze_max=0.32, bloom=1.0, rain=0.5, rain_angle=-28.0)
_GOLD = dict(haze=(0.95, 0.88, 0.76), haze_dist=3000.0, haze_max=0.38, bloom=1.0, gain=(1.0, 0.95, 0.86), vibrance=0.35)
POST = {
    's04': dict(haze_dist=1800.0, haze_max=0.42),
    's05': dict(haze_dist=2000.0, haze_max=0.3, near=40.0),
    's25': dict(AP.STORM_POST, haze_max=0.32, bloom=1.05, rain=0.45),
    's26': dict(AP.STORM_POST, haze_max=0.32, bloom=1.05, rain=0.45),
    's27': dict(_RAIN),
    's28': dict(_RAIN),
    's30': dict(_RAIN),
    's31': dict(_RAIN, haze_max=0.28, bloom=1.2, rain=0.55, rain_angle=-30.0),
    's32': dict(_RAIN, rain=0.55, rain_angle=-30.0, bloom=1.05),
    's33': dict(_RAIN, rain=0.55, rain_angle=-30.0),
    's34': dict(_RAIN, rain=0.55, rain_angle=-30.0, bloom=1.05),
    's35': dict(_RAIN, haze_max=0.2, rain=0.5, rain_angle=-30.0, bloom=1.15, near=50.0, vignette=0.22),
    's36': dict(haze_dist=2400.0, haze_max=0.35, rain=0.55, rain_angle=-34.0),
    's37': dict(haze_dist=2400.0, haze_max=0.35, rain=0.55, rain_angle=-34.0),
    's39': dict(haze_dist=2600.0, haze_max=0.35, rain=0.3, rain_angle=-30.0),
    's41': dict(_GOLD),
    's42': dict(_GOLD, near=45.0),
    's43': dict(_GOLD, near=40.0),
}

QA_ALLOW = {sid: _allow for sid in ('s04', 's05', 's25', 's26', 's27', 's28', 's30', 's31', 's37', 's39', 's41')}
# s25 / s26 / s32: the fingers and vines brush the dock, a foot its shin, all under the opaque water (out/qa/probe_*): passed
# only when every crossing polygon is measured under the sea surface (act_port.under_sea), listed as 'post_allowed'
QA_POST = {sid: AP.under_sea for sid in ('s25', 's26', 's32')}
