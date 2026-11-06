# ANCHOR — life under water (HARBOR department).
#   key_range(W, f0, f1) keys, for frames f0..f1 of an UNDER shot (pure function of t, any range, never raises):
#     water + light  the underwater uniforms (calm turquoise at 11-14 s, darker storm water from ~20 s), the cel light colours
#                    for under water, the refracted sun (uniforms + a SUN_UNDER lamp living in the UNDER set, so the key light
#                    exists while ENV is hidden); restore keys on the frames next to the range (outside every UNDER shot) put
#                    uwOn 0 and the air bounce/deep colours back, so air shots in the same run never get the water look
#     the chain      its material(s) get the UNDER department's water_wrap (fog + depth tint; inert while uwOn is 0)
#     shackle        on the pin, swung 18 deg about the pin (s06), 4 deg once the chain is taut (20..24 s);
#                    red-hot 27.2..28.0 -> 30.0, cooling 30.0..31.6 (the pin and the anchor's eye follow by drivers); after the
#                    shear (30.0) it slides off the anchor's eye with the chain end (still for ~0.7 s in the bake), and once its
#                    lugs are clear (~31.5) swings into line on the chain end (crown threaded through the last link's end)
#     pin            the two halves shoot out axially at 30.0 (22 m/s, water drag), then tumble and sink to the bed
#     fish           schools circle (calm, on twos); from 28.3 every school bolts away from the glowing shackle
#     god rays       strength follows the weather (100 % calm, 45 % in the storm)
#     pierce ring    UNDER_pierce: a ring of foam lumps where the chain breaks the surface (seen from below), following the
#                    crossing on twos, slowly turning and breathing
#     FX (once per run when the range overlaps): boiling bubbles round the shackle and the hot bottom links 28.2..30.0;
#                    at the shear a flash, sparks, a bubble burst and the silt explosion; bubble trails off the chain as it whips up
import math
import numpy as np
import bpy
from mathutils import Vector, Matrix, Quaternion
import story as S

FPS = 24


def tof(f): return (f - 1) / FPS
def fr(t): return int(round(t * FPS)) + 1
def on2(f): return f - ((f - 1) % 2)
def _cl(x, a=0.0, b=1.0): return a if x < a else (b if x > b else x)
def _ss(x): x = _cl(x); return x * x * (3.0 - 2.0 * x)
def _rng(t, a, b): return _cl((t - a) / (b - a))
def _eout(x, p=2.0): return 1.0 - (1.0 - _cl(x)) ** p


T_HOT0, T_HOT1 = 27.2, 28.0
T_SHEAR = S.T['pin_shear']
T_COOL = 31.6
T_FLEE = 28.3
TH_SLACK, TH_TAUT = 18.0, 4.0                  # shackle swing about its pin (deg): the last link threads the bow and the
                                               # link before it stays clear of the crown (checked against the bake)
CLEAR_IP = 3.5                                 # m the freed shackle slides in its own plane before its lugs clear the eye boss
CROWN_IN = 0.85                                # riding the chain end: crown centre this far up the last link from the last
                                               # joint (nestled in the link's end, clear of the end bar and the stud)

CALM = dict(uwFogD=0.0072, uwW0='#c6fbff', uwW1='#24c3e2', uwW2='#0e86d2', uwW3='#0a3a98', uwTint='#b0e8ff', uwCaus=0.5,
            uwCausC='#dcfff8', uwGlow=1.0, sunC='#ecfdff', skyC='#aeeef8', shadeC='#5299d4', bounceC='#6ee4e4', deepC='#244f9c')
STORM = dict(uwFogD=0.0095, uwW0='#a6e6f2', uwW1='#1b9cc6', uwW2='#0b5fae', uwW3='#0b2a7a', uwTint='#9ed6f2', uwCaus=0.3,
             uwCausC='#c8eef2', uwGlow=1.0, sunC='#d6eef8', skyC='#8fd2e6', shadeC='#4a82c4', bounceC='#58c8d8', deepC='#22438e')
AIR_KEYS = ('bounceC', 'deepC')


def _srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def _mixv(a, b, k):
    if isinstance(a, str): a = _srgb(a)
    if isinstance(b, str): b = _srgb(b)
    if isinstance(a, tuple): return tuple(x + (y - x) * k for x, y in zip(a, b))
    return a + (b - a) * k


def under_ranges():
    import film
    out = []
    for sid, t0, t1, sets in film.SHOTS:
        if 'UNDER' in sets.split(): out.append(film.frames_of(sid))
    return out


def _in_under(f, R):
    return any(a <= f <= b for a, b in R)


def storm_k(t): return _ss(_rng(t, 16.0, 24.0))


# ------------------------------------------------------------------------------------------------------------------ the shackle
def _UW():
    import under as UW
    return UW


def shackle_theta(t):
    return TH_SLACK + (TH_TAUT - TH_SLACK) * _ss(_rng(t, 20.0, 24.0))


def heat(t):
    h = _ss(_rng(t, T_HOT0, T_HOT1)) * (1.0 - _ss(_rng(t, T_SHEAR, T_COOL)))
    if T_HOT1 <= t < T_SHEAR: h *= 0.92 + 0.08 * math.sin(t * 23.0) * math.sin(t * 7.0)
    return h


def pinned_matrix(t, th=None):
    """shackle world matrix while on the pin: the asset's frame swung th deg about the pin axis (X)."""
    UW = _UW(); th = shackle_theta(t) if th is None else th
    return UW.S_ROT @ Matrix.Rotation(math.radians(th), 4, 'X') @ Matrix.Scale(UW.AS, 4)


def follow_matrix(f):
    """shackle riding the chain end at frame f: bow pointing up the chain, bow plane across the last link (X = the link's
    thickness axis), the crown threaded through the link's end (centre CROWN_IN up the link from the last joint)."""
    import common as CM, chain as CH
    UW = _UW()
    J = CM.chain_joints(f); t = tof(f)
    R = S.rot_xyz(S.city_tilt(t)); up = R @ np.array((0.0, 0.0, 1.0))
    C, qs = CH.frames_along(J, math.pi / 2, tuple(up))
    q = qs[len(qs) - 1]; M = q.to_matrix()
    T = Vector(M.col[0]).normalized(); w = Vector(M.col[1]).normalized()
    Z = -T; X = T.cross(w).normalized(); Y = Z.cross(X).normalized()
    Rm = Matrix((X, Y, Z)).transposed().to_4x4()
    Rm.translation = Vector(J[-1]) + Z * (CROWN_IN - (UW.PIN_DROP + 2.4) * UW.AS)
    return Rm @ Matrix.Scale(UW.AS, 4)


_REL = {}


def _release():
    """(last joint at the shear, pin axis, frame the freed shackle's lugs are clear of the anchor's eye boss)."""
    if 'r' in _REL: return _REL['r']
    import common as CM
    UW = _UW(); fs = fr(T_SHEAR)
    J0 = np.array(CM.chain_joints(fs)[80], float); lat = np.array(tuple(UW.LAT), float)
    fc = fs + 36
    for f in range(fs, fs + 160):
        d = np.array(CM.chain_joints(f)[80], float) - J0
        if np.linalg.norm(d - lat * (d @ lat)) >= CLEAR_IP: fc = f; break
    _REL['r'] = (J0, lat, fc); return _REL['r']


def _slid_matrix(f):
    """freed, still round the anchor's eye boss: the shackle keeps its pinned attitude and slides with the chain end in
    its own plane (the boss between the lugs blocks the pin axis); the pin-axis motion comes in as the lugs clear."""
    import common as CM
    J0, lat, fc = _release()
    d = np.array(CM.chain_joints(f)[80], float) - J0
    a = float(d @ lat); dip = d - lat * a
    k = _ss((float(np.linalg.norm(dip)) - CLEAR_IP) / 1.5)
    return Matrix.Translation(Vector(tuple(dip + lat * a * k))) @ pinned_matrix(T_SHEAR)


def _blend(Ma, Mb, u):
    la, ra, sa = Ma.decompose(); lb, rb, sb = Mb.decompose()
    if ra.dot(rb) < 0: rb = -rb
    return Matrix.LocRotScale(la.lerp(lb, u), ra.slerp(rb, u), sa.lerp(sb, u))


def shackle_matrix(f):
    """pinned until the shear; then it slides off the anchor's eye with the chain end (which the bake holds ~0.7 s before
    the chain starts to drag), and once clear swings into line on the chain end (0.55 s)."""
    t = tof(f)
    if t < T_SHEAR: return pinned_matrix(t)
    J0, lat, fc = _release()
    Ms = _slid_matrix(f)
    u = _ss(_rng(t, tof(fc), tof(fc) + 0.55))
    if u <= 0.0: return Ms
    return _blend(Ms, follow_matrix(f), u)


PIN_K = 3.0                                    # water drag on the flying half (1/s)
PIN_V0 = 22.0                                  # launch speed of the head half (m/s) -> free travel v0 / k = 7.3 m (the bed
                                               # along -LAT is clear for 19 m: the nearest rock is UNDER_rock.086)
PIN_L = {'a': 3.74, 'b': 4.08}                 # outer end (head / threaded stub) from the shear plane, model units
PIN_R = {'a': 1.05, 'b': 1.08}                 # head / nut radius, model units
LUG_OUT = 4.35                                 # m: the broken end is out of the lug beyond this travel
B_KICK = 2.3                                   # m the nut half is kicked out along its axis: out of the eye boss, still
                                               # caught in its lug (rocks and coral lie 7..9 m out on that side)


def pin_matrix(side, f):
    """the pin halves: on the shackle's rest frame (theta 0, the axis never swings) until the shear. Then the head half (a)
    shoots out axially (water drag), sinks once its broken end is out of the lug, spins down and settles on the seabed (each
    end rests on it); the nut half (b) is kicked 2.3 m out of the eye boss, stays caught in its lug and rides the shackle."""
    UW = _UW(); t = tof(f)
    M0 = UW.S_MAT.copy()
    if t < T_SHEAR: return M0
    tau = t - T_SHEAR
    if side == 'b':
        Mk = Matrix.Translation(Vector(UW.LAT) * (B_KICK * _eout(_rng(tau, 0.0, 0.16), 2.5))) @ M0
        return shackle_matrix(f) @ pinned_matrix(T_SHEAR).inverted() @ Mk
    sg = -1.0
    ax = Vector(UW.LAT) * sg; h = Vector((0.0, 0.0, 1.0)).cross(ax).normalized()
    smax = PIN_V0 / PIN_K
    s = smax * (1.0 - math.exp(-PIN_K * tau))
    tc = (-math.log(max(1e-3, 1.0 - LUG_OUT / smax)) / PIN_K) if smax > LUG_OUT + 0.05 else 0.6
    ts = max(0.0, tau - tc); g, vt = 4.0, 3.0
    sink = 0.5 * g * ts * ts if ts < vt / g else vt * ts - vt * vt / (2.0 * g)
    p = Vector(M0.translation) + ax * s
    L = PIN_L[side] * UW.AS
    zf = p.z - sink
    po = p + ax * L; pm = p + ax * (0.5 * L)
    fi = UW.seabed_z(p.x, p.y) + 0.6 * UW.AS + 0.15
    fo = UW.seabed_z(po.x, po.y) + PIN_R[side] * UW.AS + 0.15
    fm = UW.seabed_z(pm.x, pm.y) + 0.6 * UW.AS + 0.15
    zi = max(zf, fi); zo = max(zf, fo)
    zm = 0.5 * (zi + zo)
    if zm < fm: zi += fm - zm; zo += fm - zm
    beta = math.asin(_cl((zo - zi) / L, -0.5, 0.5))
    spin = sg * 2.5 * (1.0 - math.exp(-2.0 * tau))
    R = Matrix.Rotation(-beta, 4, h) @ Matrix.Rotation(spin, 4, ax)
    L0, Rq, Sc = M0.decompose()
    return Matrix.LocRotScale(Vector((p.x, p.y, zi)), (R.to_quaternion() @ Rq), Sc)


# ------------------------------------------------------------------------------------------------------------------ fish
def _fish_calm(o, t):
    c = Vector(o['sch_c']); r = o['sch_r']; dn = o.get('sch_dir', 1.0); ph0 = o['sch_ph']
    ph = ph0 + dn * o['sch_sp'] * t / max(r, 0.5)
    bob = o['sch_bob'] * math.sin(t * 1.3 + ph0 * 3.0); vz = o['sch_bob'] * 1.3 * math.cos(t * 1.3 + ph0 * 3.0)
    p = c + Vector((math.cos(ph) * r, math.sin(ph) * r, o['sch_h'] + bob))
    return p, Vector((-math.sin(ph) * dn * o['sch_sp'], math.cos(ph) * dn * o['sch_sp'], vz)).normalized()


def _fish_rot(hd, roll, wig):
    return (roll, -math.asin(_cl(hd.z, -1.0, 1.0)), math.atan2(hd.y, hd.x) + wig)


def fish_pose(o, t, src):
    """(location, euler) of one fish at t: calm orbit, or bolting from src after T_FLEE."""
    dn = o.get('sch_dir', 1.0); ph0 = o['sch_ph']
    if t < T_FLEE:
        p, hd = _fish_calm(o, t)
        return p, _fish_rot(hd, -0.35 * dn, 0.09 * math.sin(t * 52.8 + ph0 * 5.0))
    p0, _ = _fish_calm(o, T_FLEE)
    R = np.random.RandomState(int(ph0 * 1000.0) % 100000)
    aw = p0 - src; aw.z *= 0.6
    if aw.length < 1e-3: aw = Vector((1.0, 0.0, 0.0))
    d = (aw.normalized() + Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.3, 0.8))) * 0.35).normalized()
    d.z = max(d.z, 0.05); d.normalize()
    v0 = o['sch_sp']; vmax = 10.0 * R.uniform(0.8, 1.2); acc = 16.0
    tt = t - T_FLEE; ta = max(0.0, (vmax - v0) / acc); t1 = min(tt, ta)
    p = p0 + d * (v0 * t1 + 0.5 * acc * t1 * t1 + max(0.0, tt - ta) * vmax)
    return p, _fish_rot(d, 0.0, 0.16 * math.sin(t * 69.6 + ph0 * 5.0))


# ------------------------------------------------------------------------------------------------------------------ setup (once)
def _setup(W):
    st = W.get('_ua')
    if st is not None: return st
    sc = W['sc']; U = W['under']; UW = _UW()
    st = W['_ua'] = {}
    st['air'] = {k: (tuple(sc[k]) if hasattr(sc[k], '__len__') else float(sc[k])) for k in AIR_KEYS if k in sc}
    st['ranges'] = under_ranges()
    lamp = bpy.data.objects.get('SUN_UNDER')                      # the key light under water lives in the UNDER set
    if lamp is None:
        src = W.get('sun')
        ld = src.data.copy() if src is not None else bpy.data.lights.new('SUN_UNDER', 'SUN')
        ld.name = 'SUN_UNDER'
        lamp = bpy.data.objects.new('SUN_UNDER', ld)
        U['root'].objects.link(lamp)
    st['lamp'] = lamp
    mats = set()                                                  # the chain under water: fog + depth tint (inert at uwOn 0)
    for o in W.get('chain', []):
        for s in o.material_slots:
            if s.material is not None: mats.add(s.material)
    for m in mats:
        try: UW.water_wrap(m)
        except Exception as ex: print('underanim: water_wrap failed', m.name, ex)
    for k in ('shackle', 'pin_a', 'pin_b'):
        U[k]['qa_mover'] = 'uw'
    st['rays'] = [(o, float(o.get('amp', 0.3))) for o in U.get('rays', [])]
    st['fish'] = [o for grp in U.get('fish', {}).values() for o in grp]
    try: st['pierce'] = _pierce_obj(U['root'])
    except Exception as ex: st['pierce'] = None; print('underanim: pierce ring failed', ex)
    return st


PIERCE_Z = -0.32                                                  # just under the drawn surface disc (z -0.3, faces down)


def _pierce_obj(coll):
    """a ring of foam lumps hugging the chain where it breaks the surface, seen from below (built once, in the UNDER set)."""
    o = bpy.data.objects.get('UNDER_pierce')
    if o is not None: return o
    import bmesh
    UW = _UW(); R = np.random.RandomState(77); b = bmesh.new()
    for k in range(16):
        a = math.tau * k / 16 + R.uniform(-0.12, 0.12); r = 3.2 + R.uniform(-0.25, 0.7); sz = R.uniform(0.55, 1.15)
        bmesh.ops.create_icosphere(b, subdivisions=2, radius=sz,
                                   matrix=Matrix.Translation((r * math.cos(a), r * math.sin(a), 0.0)) @ Matrix.Diagonal((1.0, 1.0, 0.3, 1.0)))
    for k in range(9):                                            # a few loose flecks further out
        a = R.uniform(0, math.tau); r = R.uniform(4.6, 6.2); sz = R.uniform(0.2, 0.42)
        bmesh.ops.create_icosphere(b, subdivisions=1, radius=sz,
                                   matrix=Matrix.Translation((r * math.cos(a), r * math.sin(a), 0.0)) @ Matrix.Diagonal((1.0, 1.0, 0.3, 1.0)))
    me = bpy.data.meshes.new('UNDER_pierce'); b.to_mesh(me); b.free()
    mat = bpy.data.materials.get('M_UNDER_pierce') or UW.uflat('M_UNDER_pierce', '#e6fbff', alpha=0.88, blend=True, glow=0.25)
    me.materials.append(mat)
    o = bpy.data.objects.new('UNDER_pierce', me); coll.objects.link(o)
    o['qa_kind'] = 'fx'; o.visible_shadow = False
    return o


def pierce_point(f):
    """where the chain crosses the surface at frame f (the first joint pair from the top that straddles it), or None."""
    import common as CM
    J = CM.chain_joints(f)
    for i in range(len(J) - 1):
        za, zb = J[i][2] - PIERCE_Z, J[i + 1][2] - PIERCE_Z
        if za >= 0.0 > zb:
            u = za / (za - zb); return J[i] + (J[i + 1] - J[i]) * u
    return None


def _sun_air(t):
    import env as EV
    az, el, col = S.sun(t); return EV.sun_dir(az, el)


# ------------------------------------------------------------------------------------------------------------------ keys
def _water(W, st, f, t):
    sc = W['sc']; TL = W['TL']; UW = _UW()
    k = storm_k(t)
    for name in CALM:
        TL.prop(sc, name, f, _mixv(CALM[name], STORM[name], k))
    TL.prop(sc, 'uwOn', f, 1.0)
    d = UW.refracted_sun(_sun_air(t))
    TL.prop(sc, 'uwSun', f, tuple(d)); TL.prop(sc, 'sunD', f, tuple(d))
    TL.quat(st['lamp'], f, (-d).to_track_quat('-Z', 'Y'))
    TL.hide(st['lamp'], f, False)
    for o, a in st['rays']:
        TL.prop(o, 'amp', f, a * (1.0 - 0.55 * k))


def _restore(W, st, f):
    sc = W['sc']; TL = W['TL']
    TL.prop(sc, 'uwOn', f, 0.0)
    for k, v in st['air'].items(): TL.prop(sc, k, f, v)
    TL.hide(st['lamp'], f, True)


def _fx(W, f0, f1):
    fxm = W.get('fx_mod')
    if fxm is None:
        try: import fx as fxm
        except Exception: return
    C = W['C'].get('FX'); UW = _UW()
    done = W.setdefault('_ua_fx', set())

    def want(name, fa, fb):
        if name in done or fb < f0 or fa > f1: return False
        done.add(name); return True
    B = Vector(UW.BOW); P = Vector(UW.PIN)
    fb0, fb1 = fr(28.2), fr(T_SHEAR)
    if want('boil', fb0, fb1 + 40):
        fxm.bubbles((B.x, B.y, B.z - 3.0), f0=fb0, dur=fb1 - fb0 + 24, coll=C, seed=611, count=90, radius=4.0, size=0.55, rise=6.0,
                    wobble=0.8, name='FX_uw_boil')
        import common as CM
        J = CM.chain_joints(fr(29.0))
        for i, jj in enumerate((77, 74, 71)):
            p = J[jj]
            fxm.bubbles((float(p[0]), float(p[1]), float(p[2]) - 1.0), f0=fb0 + 3 * i, dur=fb1 - fb0, coll=C, seed=612 + i, count=40,
                        radius=2.5, size=0.42, rise=5.0, name='FX_uw_boil%d' % i)
    fs = fr(T_SHEAR)
    if want('shear', fs, fs + 90):
        k = fxm.kira('FX_uw_shear_kira', (P.x, P.y, P.z), 4.0, coll=C, seed=621, inner='#fffbe8', outer='#ffb347')
        fxm.flicker(k, [fs], pattern=(1.0, 0.45, 0.2))
        ax = Vector(UW.LAT)
        for sg, sd in ((-1.0, 622), (1.0, 623)):
            fxm.sparks((P.x, P.y, P.z), f0=fs, dur=18, coll=C, seed=sd, count=34, speed=14.0, direction=tuple(ax * sg + Vector((0, 0, 0.25))),
                       spread=0.5, size=0.8, gravity=3.0, name='FX_uw_sparks%d' % (sd - 622))
        # (06.11) each bubble breaks up on its own drawing: all 70 went in one frame at 775, in front of s16's lens
        fxm.bubbles((P.x, P.y, P.z), f0=fs, dur=54, coll=C, seed=624, count=70, radius=3.0, size=0.6, rise=7.0, settle=True,
                    name='FX_uw_burst')
        # the silt bursts off the bed: a wall rising behind the eye (away from the s15 lens on the shank side), puffs out to both
        # sides along the pin's line, a low skirt round the eye; no billow comes within 7 m of the s15 camera or 20 m of the s16
        # camera (checked on the FX's own formula), and the shackle above the eye stays clear
        Ys = Vector(UW.UP).cross(ax)
        for k, (off, rad, hgt, cnt) in enumerate(((-Ys * 19.0, 12.0, 12.0, 30), (ax * 9.0 - Ys * 2.0, 7.0, 8.0, 14),
                                                  (-ax * 9.0 - Ys * 2.0, 7.0, 8.0, 14), (-Ys * 3.0, 5.0, 2.0, 12))):
            q = P + off; zb = UW.seabed_z(q.x, q.y)
            fxm.silt((q.x, q.y, zb), f0=fs + 2 + 2 * k, dur=96, coll=C, seed=625 + 7 * k, radius=rad, height=hgt, count=cnt,
                     name='FX_uw_silt%d' % k)
    fw0, fw1 = fr(31.4), fr(33.2)
    if want('whip', fw0, fw1):
        import common as CM
        for i, (jj, tt) in enumerate(((79, 31.7), (76, 31.9), (72, 32.1), (68, 32.3))):
            p = CM.chain_joints(fr(tt))[jj]
            fxm.bubbles((float(p[0]), float(p[1]), float(p[2])), f0=fr(tt), dur=36, coll=C, seed=631 + i, count=36, radius=2.2,
                        size=0.5, rise=9.0, name='FX_uw_trail%d' % i)


def key_range(W, f0, f1, mode=None):
    """Key everything under water for frames f0..f1 (see the header). mode is ignored (the state is a function of t)."""
    if not isinstance(W.get('under'), dict): return
    try:
        st = _setup(W)
    except Exception as ex:
        import traceback; traceback.print_exc(); print('underanim: setup failed', ex); return
    TL = W['TL']; U = W['under']
    try:
        for f in range(f0, f1 + 1):
            _water(W, st, f, tof(f))
        for f in (f0 - 1, f1 + 1):
            if f >= 1 and not _in_under(f, st['ranges']): _restore(W, st, f)
    except Exception as ex:
        import traceback; traceback.print_exc(); print('underanim: water failed', ex)
    try:
        sh = U['shackle']; pa = U['pin_a']; pb = U['pin_b']; prev = {}
        for f in range(f0, f1 + 1):
            for o, M in ((sh, shackle_matrix(f)), (pa, pin_matrix('a', f)), (pb, pin_matrix('b', f))):
                l, q, s = M.decompose()
                if o.name in prev and prev[o.name].dot(q) < 0: q = -q
                prev[o.name] = q
                TL.loc(o, f, tuple(l)); TL.quat(o, f, q); TL.scale(o, f, tuple(s))
            TL.prop(sh, 'heat', f, heat(tof(on2(f))))
    except Exception as ex:
        import traceback; traceback.print_exc(); print('underanim: shackle failed', ex)
    try:
        src = Vector(_UW().BOW)
        for f in range(f0, f1 + 1):
            te = tof(on2(f))
            for o in st['fish']:
                p, e = fish_pose(o, te, src)
                TL.loc(o, f, tuple(p)); TL.eul(o, f, e)
    except Exception as ex:
        import traceback; traceback.print_exc(); print('underanim: fish failed', ex)
    try:
        o = st.get('pierce')
        if o is not None:
            for f in range(f0, f1 + 1):
                p = pierce_point(on2(f)); te = tof(on2(f))
                TL.hide(o, f, p is None)
                if p is not None:
                    TL.loc(o, f, (float(p[0]), float(p[1]), PIERCE_Z)); TL.eul(o, f, (0.0, 0.0, 0.35 * te))
                    k = 1.0 + 0.06 * math.sin(te * 5.3)
                    TL.scale(o, f, (k, k, 1.0))
    except Exception as ex:
        import traceback; traceback.print_exc(); print('underanim: pierce ring failed', ex)
    try: _fx(W, f0, f1)
    except Exception as ex:
        import traceback; traceback.print_exc(); print('underanim: fx failed', ex)
