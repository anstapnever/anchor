# UNDER department (ANCHOR): the harbour seabed, the giant anchor with its D-shackle and pin, kelp forests, coral, sea grass,
# a sunken boat, fish schools, marine snow, drawn god-ray cards and the sea surface seen from below.
#   import under as UW
#   U = UW.build(coll)                    # -> dict: anchor, shackle, pin_a, pin_b, chain_end, seabed, rocks, kelp, ... (see build)
#                                         #    + shackle_a / shackle_b: the halves the bow snaps into (s16), hidden by default
#   UW.set_water(sc, sun_obj=SUN)         # underwater cel light + water uniforms for an underwater shot (call per shot)
#   UW.seabed_z(x, y)                     # seabed height in metres anywhere in the harbour (feet, chain drag, FX)
#   UW.fish_school(coll, center, radius, count, seed, species='sardine') -> [objects]   (linked duplicates)
#   UW.animate_school(objs, f0, f1, mode='circle'|'flee', ...)                           (keyed on twos)
#   UW.water_wrap(mat) / UW.under_all()   # give other departments' LK materials the same underwater fog
# Scene uniforms read by these materials: seaT (sway, caustics, ripples), flash, camP, uwOn uwFogD uwW0..3 uwSun uwTint uwCaus uwCausC uwGlow.
# Object props: UNDER_shackle['heat'] 0..1 (red-hot, drives the pin halves, the bow halves and the anchor eye through drivers).
import bpy, bmesh, math, os, random, time
from mathutils import Vector, Matrix, Euler, Quaternion, noise as MN, geometry as MG
from mathutils.bvhtree import BVHTree
import look as LK, env as EV
from look import NB, srgb

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); TEX = os.path.join(ROOT, 'tex')
D = bpy.data
UP = Vector((0.0, 0.0, 1.0))

# ------------------------------------------------------------------------------------------------------------------ anchor placement
BOW = Vector((-100.0, 150.0, -52.0))            # shackle bow centre (contract)
AS = 1.3                                        # anchor, shackle and pin are modelled in units of 1/AS m and placed at scale AS
PIN_DROP = 4.6                                  # bow centre -> pin axis (shackle hinge), model units
PIN = BOW - Vector((0.0, 0.0, PIN_DROP * AS))
PHI = math.radians(195.0)                       # horizontal heading crown -> shackle (the shank points WSW, along the trench)
THETA = math.radians(5.0)                       # shank elevation (the anchor lies almost flat)
ALPHA = math.radians(30.0)                      # fluke angle from the shank (flukes plough 25 deg into the sand)
SHANK = 18.0                                    # crown centre -> eye centre, model units (23.4 m; ~28 m overall)
FLUKE = 11.0                                    # crown centre -> fluke bill, model units
H = Vector((math.cos(PHI), math.sin(PHI), 0.0))
LAT = Vector((-math.sin(PHI), math.cos(PHI), 0.0))          # pin axis (anchor X')
ZA = H * math.cos(THETA) + UP * math.sin(THETA)              # shank axis (anchor Z')
YA = UP * math.cos(THETA) - H * math.sin(THETA)              # anchor Y'
HEAD = PIN - ZA * (SHANK * AS)
FDIR = (ZA * math.cos(ALPHA) - YA * math.sin(ALPHA)).normalized()
A_MAT = Matrix((LAT, YA, ZA)).transposed().to_4x4(); A_MAT.translation = HEAD; A_MAT = A_MAT @ Matrix.Scale(AS, 4)
S_ROT = Matrix((LAT, UP.cross(LAT), UP)).transposed().to_4x4(); S_ROT.translation = PIN    # shackle frame: X pin axis, Z up
S_MAT = S_ROT @ Matrix.Scale(AS, 4)
FSL = -FDIR.z / max(1e-6, math.hypot(FDIR.x, FDIR.y))      # fluke slope (tan of its dip)
S_TIP = FLUKE * AS * math.hypot(FDIR.x, FDIR.y)             # horizontal reach crown -> bill (m)
BOW_IN = (2.4 - 0.72) * AS                                  # bow centre -> underside of the bow crown (where the first link bears)

# ------------------------------------------------------------------------------------------------------------------ palette
CORAL = ['#ff5f7e', '#ffae3d', '#ff7bc8', '#ffd84a', '#b67bff', '#ff6a3a', '#3fe0c0', '#ff8fa3']
KELP = ['#5cbf4e', '#8cc63f', '#b9c43a', '#3fae6a', '#d0b93c']
WATER = dict(uwOn=1.0, uwFogD=0.0072, uwW0='#c6fbff', uwW1='#24c3e2', uwW2='#0e86d2', uwW3='#0a3a98', uwTint='#b0e8ff',
             uwCaus=0.5, uwCausC='#dcfff8', uwGlow=1.0)
UW_LIGHT = dict(sunC='#ecfdff', skyC='#aeeef8', shadeC='#5299d4', bounceC='#6ee4e4', deepC='#244f9c')


def _S(t):
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def _fbm2(x, y, s, octaves=4, seed=0.0):
    v = 0.0; a = 0.5; f = s
    for i in range(octaves):
        v += a * MN.noise(Vector((x * f + 13.1 * i, y * f - 7.7 * i, seed + 3.3 * i)))
        a *= 0.5; f *= 2.03
    return v


# ------------------------------------------------------------------------------------------------------------------ seabed height
TR_C = (-92.0, 148.0); TR_A = math.radians(15.0); TR_LU = 250.0; TR_LV = 80.0; TR_FLOOR = -61.0


def _trench_t(x, y):
    dx = x - TR_C[0]; dy = y - TR_C[1]
    u = dx * math.cos(TR_A) + dy * math.sin(TR_A); v = -dx * math.sin(TR_A) + dy * math.cos(TR_A)
    v += 16.0 * _fbm2(x, y, 1 / 170.0, 2, 4.0); u += 30.0 * _fbm2(x, y, 1 / 260.0, 2, 8.0)
    return math.sqrt((u / TR_LU) ** 2 + (v / TR_LV) ** 2)


def _furrow(x, y, z):
    """The anchor's bed: a shallow scour bowl under the crown (crown a quarter buried), the flukes ploughing into the sand (the
    bed falls at under half their dip, so each is about half buried with the bill under), sand heaped beyond the bills, and
    the drag furrow trailing away behind the crown."""
    rx = x - HEAD.x; ry = y - HEAD.y
    s = rx * H.x + ry * H.y; l = rx * LAT.x + ry * LAT.y
    k = AS
    if s < -42.0 * k or s > S_TIP + 14.0 * k or abs(l) > 14.0 * k: return z
    zb = HEAD.z - 1.4 * k
    if s <= 0.0:
        tgt = zb + (z - zb) * _S(-s / (7.0 * k))
        tgt -= 0.9 * (1.0 - _S(-s / (32.0 * k))) * (1.0 - _S((abs(l) - 3.0 * k) / (2.0 * k)))
    elif s <= S_TIP: tgt = zb - 0.45 * FSL * s
    else:
        tz = zb - 0.45 * FSL * S_TIP
        tgt = tz + (z + 0.7 - tz) * _S((s - S_TIP) / (3.0 * k))
    tgt += 0.15 * MN.noise(Vector((x * 0.35, y * 0.35, 2.0)))
    w = (1.0 - _S((abs(l) - 7.3 * k) / (5.5 * k))) * (1.0 - _S((s - S_TIP - 4.0 * k) / (5.0 * k)))
    return z + (tgt - z) * w


def seabed_z(x, y, fine=True):
    """Seabed height (m). -12 by the quay (y=400), falling south; the trench (-61) runs WSW-ENE under the city at (-100,150)."""
    z = -12.0 - 16.0 * _S((400.0 - y) / 260.0) - 12.0 * _S((150.0 - y) / 600.0)
    z += 4.0 * _fbm2(x, y, 1 / 230.0, 3, 1.0)
    t = _trench_t(x, y)
    m = 1.0 - _S((t - 0.42) / 0.58)
    m = min(1.0, max(0.0, m + 0.05 * math.sin(m * math.pi * 5.0) * (1.0 - m)))      # a few ledges down the walls
    floor = TR_FLOOR + 1.3 * _fbm2(x, y, 1 / 55.0, 3, 7.0)
    z = z + (floor - z) * m
    if fine: z += 0.45 * _fbm2(x, y, 1 / 13.0, 3, 9.0)
    return _furrow(x, y, z)


def seabed_normal(x, y, e=0.6):
    dzx = seabed_z(x + e, y) - seabed_z(x - e, y); dzy = seabed_z(x, y + e) - seabed_z(x, y - e)
    return Vector((-dzx, -dzy, 2.0 * e)).normalized()


# ------------------------------------------------------------------------------------------------------------------ water uniforms
def refracted_sun(sunD):
    """Direction TO the sun as seen under water (Snell, n = 1.333): the light comes down steeper."""
    d = Vector(sunD).normalized(); hz = Vector((d.x, d.y, 0.0))
    hz = hz.normalized() if hz.length > 1e-6 else Vector((1.0, 0.0, 0.0))
    sz = math.sqrt(max(0.0, 1.0 - d.z * d.z)) / 1.333          # sin of the zenith angle under water
    return (hz * sz + UP * math.sqrt(max(0.0, 1.0 - sz * sz))).normalized()


def _put_uniforms(sc, vals, frame=None):
    for k, v in vals.items():
        sc[k] = srgb(v)[:3] if isinstance(v, str) else v
        if frame is not None: sc.keyframe_insert('["%s"]' % k, frame=frame)


def ensure_water(sc=None):
    """Water uniforms with their defaults, only where missing (never touches the shared cel light)."""
    sc = sc or bpy.context.scene
    _put_uniforms(sc, {k: v for k, v in WATER.items() if k not in sc})
    if 'uwSun' not in sc: sc['uwSun'] = tuple(refracted_sun(sc.get('sunD', (0.6, -0.3, 0.74))))
    for k, v in (('seaT', 0.0), ('flash', 0.0), ('camP', (0.0, 0.0, 0.0))):
        if k not in sc: sc[k] = v


def set_water(sc=None, light=True, sun_obj=None, frame=None, **kw):
    """Underwater look for a shot: water uniforms (+ overrides in kw), the cel light colours for under water (light=True),
    and, with sun_obj, the sun lamp + sunD aimed at the refracted elevation so shadows and caustics fall the right way."""
    sc = sc or bpy.context.scene
    vals = dict(WATER); vals.update({k: v for k, v in kw.items() if k in WATER})
    air = tuple(sc['sunD_air']) if 'sunD_air' in sc else tuple(sc.get('sunD', (0.6, -0.3, 0.74)))
    sc['sunD_air'] = air                                   # the sun above water, so repeated calls never refract twice
    d = refracted_sun(air)
    if sun_obj is not None:
        az = math.degrees(math.atan2(d.x, d.y)); el = math.degrees(math.asin(d.z))
        EV.aim_sun(sc, sun_obj, az, el, frame)
    sc['uwSun'] = tuple(d)
    if frame is not None: sc.keyframe_insert('["uwSun"]', frame=frame)
    _put_uniforms(sc, vals, frame)
    if light: _put_uniforms(sc, {k: v for k, v in UW_LIGHT.items() if k not in kw}, frame)
    for k in ('sunC', 'skyC', 'shadeC', 'bounceC', 'deepC'):
        if k in kw: _put_uniforms(sc, {k: kw[k]}, frame)
    return vals


def clear_water(sc=None, sun_obj=None, frame=None):
    """Back above water: uwOn = 0 (every UNDER / water_wrap'ed material drops its fog, tint and caustics) and, with sun_obj,
    the sun lamp + sunD re-aimed at the air elevation saved by set_water. The cel light colours are the caller's to restore."""
    sc = sc or bpy.context.scene
    _put_uniforms(sc, {'uwOn': 0.0}, frame)
    if sun_obj is not None and 'sunD_air' in sc:
        d = Vector(tuple(sc['sunD_air'])).normalized()
        EV.aim_sun(sc, sun_obj, math.degrees(math.atan2(d.x, d.y)), math.degrees(math.asin(d.z)), frame)


# ------------------------------------------------------------------------------------------------------------------ shader helpers
def _f(nb, n): return nb.attr(n, 'Fac')
def _v(nb, n): return nb.attr(n, 'Vector')
def _c(nb, n): return nb.attr(n, 'Color')


def wgrad(nb, d):
    """The colour of open water seen in direction d (the same gradient the fog melts into): bright up, deep cobalt down."""
    dz = nb.xyz(d)[2]
    c = nb.mixc(_c(nb, 'uwW2'), _c(nb, 'uwW1'), nb.smooth(dz, -0.16, 0.26))
    c = nb.mixc(c, _c(nb, 'uwW0'), nb.smooth(dz, 0.22, 0.86))
    c = nb.mixc(c, _c(nb, 'uwW3'), nb.smooth(dz, -0.08, -0.62))
    s = nb.mx(nb.vmath('DOT_PRODUCT', d, _v(nb, 'uwSun')), 0.0)
    g = nb.add(nb.mul(nb.math('POWER', s, 5.0), 0.28), nb.mul(nb.math('POWER', s, 22.0), 0.32))
    c = nb.cadd(c, nb.vmath('SCALE', _c(nb, 'uwW0'), scale=nb.mul(g, _f(nb, 'uwGlow'))))
    return nb.mixc(c, nb.mixc(c, '#e6f6ff', 0.6), nb.mul(_f(nb, 'flash'), 0.8))


def view(nb):
    P = nb.geo().outputs['Position']
    V = nb.vmath('SUBTRACT', P, _v(nb, 'camP'))
    return P, nb.vmath('LENGTH', V), nb.vmath('NORMALIZE', V)


def water(nb, c, ink=None, fogk=1.0, clear=None):
    """Depth fog into the water gradient + a cool tint with depth. Returns (colour, ink faded by the fog, fog amount).
    clear (0..1 socket, optional): how much of the veil and the tint a self-lit surface punches through (its own light owns its
    colour: a cyan veil or tint over red-hot light reads pink)."""
    P, dist, d = view(nb)
    on = _f(nb, 'uwOn')
    f = nb.mul(nb.sub(1.0, nb.math('EXPONENT', nb.mul(nb.mul(dist, _f(nb, 'uwFogD')), -fogk))), on)
    z = nb.xyz(P)[2]
    dk = nb.mul(nb.math('MINIMUM', nb.mx(nb.mul(z, -1.0 / 70.0), 0.0), 1.0), on)
    if clear is not None:
        keep = nb.sub(1.0, clear); f = nb.mul(f, keep); dk = nb.mul(dk, keep)
    c = nb.mixc(c, nb.cmul(c, _c(nb, 'uwTint')), dk)
    c = nb.mixc(c, wgrad(nb, d), f)
    ink_s = None if ink is None else nb.mul(ink, nb.sub(1.0, nb.smooth(f, 0.18, 0.72)))
    return c, ink_s, f


def litmask(nb, normal=None):
    d = nb.new('ShaderNodeBsdfDiffuse', ins={'Color': (1, 1, 1, 1)})
    if normal is not None: nb.put(d.inputs['Normal'], normal)
    s2r = nb.N.new('ShaderNodeShaderToRGB'); nb.L.new(d.outputs[0], s2r.inputs[0])
    return nb.smooth(nb.bw(s2r.outputs['Color']), 0.012, 0.055)


def tq(nb, k=8.0):
    """seaT on threes (8 steps a second)."""
    return nb.math('DIVIDE', nb.math('FLOOR', nb.mul(_f(nb, 'seaT'), k)), k)


def caustic(nb, P, N, scale=1.0):
    """A drawn net of light (Voronoi cell borders, two scales, crossing knots), projected along the light, warped, broken into
    patches and fading with the distance from the camera (no tiled floor far off); animated on threes."""
    t = tq(nb)
    sx, sy, sz = nb.xyz(_v(nb, 'uwSun')); px, py, pz = nb.xyz(P)
    k = nb.math('DIVIDE', pz, nb.mx(sz, 0.2))
    q = nb.vec(nb.sub(px, nb.mul(sx, k)), nb.sub(py, nb.mul(sy, k)), 0.0)
    qs = nb.vmath('SCALE', q, scale=0.16 / scale)
    w = nb.vec(nb.noise(qs, 1.0, 2.0, 0.5, 0.0, w=nb.mul(t, 0.08)), nb.noise(nb.vmath('ADD', qs, (5.2, 1.3, 0.0)), 1.0, 2.0, 0.5, 0.0, w=nb.mul(t, 0.08)), 0.0)
    q = nb.vmath('ADD', q, nb.vmath('SCALE', nb.vmath('SUBTRACT', w, (0.5, 0.5, 0.0)), scale=2.4 * scale))
    e1 = nb.voronoi(nb.vmath('SCALE', q, scale=1.0 / (2.3 * scale)), 1.0, 'DISTANCE_TO_EDGE', w=nb.mul(t, 0.55))
    qx, qy, _ = nb.xyz(q)
    q2 = nb.vec(nb.add(nb.mul(qx, 0.8), nb.mul(qy, -0.6)), nb.add(nb.mul(qx, 0.6), nb.mul(qy, 0.8)), 0.0)
    e2 = nb.voronoi(nb.vmath('SCALE', q2, scale=1.0 / (1.3 * scale)), 1.0, 'DISTANCE_TO_EDGE', w=nb.add(nb.mul(t, 0.7), 3.0))
    l1 = nb.smooth(e1, 0.05, 0.012); l2 = nb.smooth(e2, 0.034, 0.008)
    c = nb.add(nb.add(nb.mul(l1, 0.8), nb.mul(l2, 0.3)), nb.mul(nb.mul(l1, l2), 0.5))
    c = nb.add(c, nb.mul(nb.smooth(e1, 0.16, 0.0), 0.08))
    patch = nb.add(0.2, nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', q, scale=0.05 / scale), 1.0, 2.0, 0.5, 0.0, w=nb.mul(t, 0.05)), 0.32, 0.68), 1.0))
    face = nb.smooth(nb.xyz(N)[2], 0.0, 0.55)
    dk = nb.remap(pz, -75.0, -4.0, 0.65, 1.0)
    _, dist, _ = view(nb)
    fade = nb.math('EXPONENT', nb.mul(dist, -1.0 / 45.0))
    return nb.mul(nb.mul(c, patch), nb.mul(nb.mul(face, dk), fade))


def ucel(name, color, ink=1.0, paint=0.0, spec=0.0, rim=0.35, deep=0.55, vary=0.07, vscale=0.15, coord='Object', seed=0.0,
         grime=0.0, scuff=0.0, chips=0.0, rust=0.0, algae=0.0, waterline=0.0, wscale=1.0, glow=0.0, alpha=None, wet=0.0, flash=1.0,
         steps=3, caust=1.0, cscale=1.0, post=None, fogk=1.0, blend=False, normal=None, cut=110.0, heat=None):
    """LK.cel built from look.py's own pieces (NB, _vary, weather, shade, finish) plus the water: caustics in the sunlit parts,
    depth fog into the water gradient, a cool tint with depth. post(nb, c, glow) -> (c, glow) hooks colour changes.
    Ink is written as 0 or 1 only, constant over an object: the kit stores ink as the alpha of the A pass and the 16-bit PNG is
    un-premultiplied on save, so any fractional ink divides depth/oid/mid (false contour and dotted lines). Lines fade with the
    fog per object instead: off when the object's origin (minus its prop `inkr`) is further than `cut` metres from camP.
    heat: True or local(nb) -> red heat from the object's prop `heat`; its light is added after the water (not tinted)."""
    nb = NB(name)
    col = nb.rgb(color) if isinstance(color, (str, tuple)) else color(nb)
    if vary: col = LK._vary(nb, col, vary, vscale, coord, steps, seed)
    if grime or scuff or chips or rust or algae:
        col = LK.weather(nb, col, grime, scuff, chips, rust, algae, waterline, wscale, coord, seed)
    c = LK.shade(nb, col, spec, rim, deep, flash=flash, wet=wet)
    if normal is not None:
        for n in nb.N:
            if n.bl_idname == 'ShaderNodeBsdfDiffuse': nb.put(n.inputs['Normal'], normal(nb) if callable(normal) else normal)
    g = nb.geo()
    if caust:
        cm = nb.mul(nb.mul(caustic(nb, g.outputs['Position'], g.outputs['Normal'], cscale), litmask(nb)), nb.mul(_f(nb, 'uwCaus'), caust))
        c = nb.cadd(c, nb.vmath('SCALE', _c(nb, 'uwCausC'), scale=cm))
    if post: c, glow = post(nb, c, glow)
    hot = None; clear = None
    if heat is not None:
        he, hot = _heat_terms(nb, None if heat is True else heat)
        c = nb.mixc(c, nb.cmul(c, '#2a1e1a'), nb.mul(nb.smooth(he, 0.02, 0.25), 0.92))      # soot / scale first
        glow = nb.mx(nb.smooth(he, 0.2, 0.72), glow)
        clear = nb.mul(nb.smooth(he, 0.1, 0.45), 0.85)      # the glowing metal shows through the veil (cool parts keep it all)
    c, _, f = water(nb, c, None, fogk, clear)
    if hot is not None: c = nb.cadd(c, nb.vmath('SCALE', hot, scale=nb.mul(nb.sub(1.0, f), 1.25)))
    inks = 1.0 if ink else 0.0
    if ink and cut is not None:
        oi = nb.N.new('ShaderNodeObjectInfo')
        od = nb.sub(nb.vmath('LENGTH', nb.vmath('SUBTRACT', oi.outputs['Location'], _v(nb, 'camP'))), nb.objattr('inkr'))
        inks = nb.sub(1.0, nb.step(cut, od))
    return LK.finish(nb, c, inks, paint, glow, alpha, blend=blend, hz=0.0)


def uflat(name, color, ink=0.0, paint=0.0, alpha=None, blend=False, fog=True, fogk=1.0, glow=0.0):
    """Unlit (LK.flat's finish) with the water fog."""
    nb = NB(name)
    col = nb.rgb(color) if isinstance(color, (str, tuple)) else color(nb)
    if fog: col, _, _ = water(nb, col, None, fogk)
    return LK.finish(nb, col, ink, paint, glow, alpha, blend=blend, hz=0.0)


def _nb_on(mat):
    nb = NB.__new__(NB); nb.m = mat; nb.nt = mat.node_tree; nb.N = nb.nt.nodes; nb.L = nb.nt.links
    nb._geo = None; nb._tc = None; nb._attrs = {}
    return nb


def water_wrap(mat, fogk=1.0, cut=None):
    """Give another department's LK material (cel / glowmat / flat) the same underwater fog and depth tint.
    Call it in underwater shots only (it edits the material in that scene). Its ink is left as it is (a fog-faded, fractional
    ink breaks the kit's A pass, see ucel); with cut (m) the ink is switched off per object beyond that distance from camP."""
    if mat is None or not mat.use_nodes or mat.get('uw_wrapped') or mat.name.startswith('M_UNDER'): return mat
    nb = _nb_on(mat)
    em = next((n for n in nb.N if n.bl_idname == 'ShaderNodeEmission'), None)
    if em is None: return mat
    inp = em.inputs['Color']
    src = inp.links[0].from_socket if inp.links else nb.rgb(tuple(inp.default_value))
    # what glows (its glow AOV: the chain's red-hot links) shows through the veil and the tint like the UNDER heat does (ucel)
    ga = next((n for n in nb.N if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'glow'), None)
    clear = None
    if ga is not None:
        gv = ga.inputs['Value']
        if gv.links: clear = nb.mul(nb.math('MINIMUM', nb.mx(gv.links[0].from_socket, 0.0), 1.0), 0.85)
        elif gv.default_value > 0.0: clear = min(1.0, gv.default_value) * 0.85
    c, _, _ = water(nb, src, None, fogk, clear)
    nb.L.new(c, inp)
    ink = next((n for n in nb.N if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'ink'), None)
    if ink is not None and cut is not None:
        isrc = ink.inputs['Value'].links[0].from_socket if ink.inputs['Value'].links else ink.inputs['Value'].default_value
        oi = nb.N.new('ShaderNodeObjectInfo')
        od = nb.sub(nb.vmath('LENGTH', nb.vmath('SUBTRACT', oi.outputs['Location'], _v(nb, 'camP'))), nb.objattr('inkr'))
        nb.L.new(nb.mul(isrc, nb.sub(1.0, nb.step(cut, od))), ink.inputs['Value'])
    mat['uw_wrapped'] = 1
    return mat


def under_all(skip=('M_sky', 'M_sea', 'M_cloud'), cut=None):
    """water_wrap every LK material in the file except the sky, sea and clouds (hidden from below anyway)."""
    n = 0
    for m in D.materials:
        if m.name in LK.REG and not m.name.startswith(skip) and not m.name.startswith('M_UNDER'): water_wrap(m, cut=cut); n += 1
    return n


# ------------------------------------------------------------------------------------------------------------------ geometry helpers
ACC = ('sw', 'fl', 'ph', 'zz', 'tint', 'u', 'stem')


def newbm(*layers):
    """A bmesh with its float vertex layers made up front: in Blender 5.2 adding a layer later invalidates every BMVert
    reference Python holds, so layers are never added once verts exist."""
    bm = bmesh.new()
    for k in layers: bm.verts.layers.float.new(k)
    return bm


def setl(bm, verts, **vals):
    """per-vertex float attributes (read in shaders with nb.attr(name, 'Fac', 'GEOMETRY') and by the sway nodes)."""
    for k, v in vals.items():
        lay = bm.verts.layers.float.get(k)
        if lay is None: raise KeyError('bmesh layer %s must be made with newbm() before the verts' % k)
        for x in verts: x[lay] = v(x) if callable(v) else v


def bridge(bm, rings, wrap_u=True, wrap_v=False, cap0=False, cap1=False):
    vv = [[bm.verts.new(tuple(p)) for p in r] for r in rings]
    n = len(vv[0]); m = len(vv)
    for j in range(m - 1 + (1 if wrap_v else 0)):
        a = vv[j]; b = vv[(j + 1) % m]
        for i in range(n - (0 if wrap_u else 1)):
            k = (i + 1) % n
            try: bm.faces.new((a[i], a[k], b[k], b[i]))
            except ValueError: pass
    try:
        if cap0: bm.faces.new(list(reversed(vv[0])))
        if cap1: bm.faces.new(vv[-1])
    except ValueError: pass
    return vv


def flat_verts(vv):
    return [v for r in vv for v in r]


def frames(pts):
    out = []; n = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        if n is None:
            a = UP if abs(t.z) < 0.9 else Vector((1.0, 0.0, 0.0))
            n = (a - t * a.dot(t)).normalized()
        else: n = (n - t * n.dot(t)).normalized()
        out.append((t, n, t.cross(n)))
    return out


def circle(c, n1, n2, r, seg, a0=0.0, sx=1.0):
    return [c + (n1 * (math.cos(a0 + math.tau * i / seg) * sx) + n2 * math.sin(a0 + math.tau * i / seg)) * r for i in range(seg)]


def tube(bm, pts, radii, seg=8, cap0=True, cap1=True, a0=0.0, sx=1.0):
    fr = frames(pts)
    rr = radii if isinstance(radii, (list, tuple)) else [radii] * len(pts)
    return bridge(bm, [circle(p, f[1], f[2], rr[i], seg, a0, sx) for i, (p, f) in enumerate(zip(pts, fr))], True, False, cap0, cap1)


def revolve(bm, prof, seg, M=None, axis='Z', closed=False, a0=0.0):
    """prof: [(r, h)] in the half plane, revolved about local Z (or X). closed=True: the profile is a loop (a ring section)."""
    M = M or Matrix.Identity(4); rings = []
    for (r, h) in prof:
        ring = []
        for k in range(seg):
            a = a0 + math.tau * k / seg; ca, sa = math.cos(a), math.sin(a)
            ring.append(M @ (Vector((r * ca, r * sa, h)) if axis == 'Z' else Vector((h, r * ca, r * sa))))
        rings.append(ring)
    return bridge(bm, rings, True, closed)


def append(dst, src, M=None, **layers):
    vm = {}
    for v in src.verts: vm[v] = dst.verts.new((M @ v.co) if M is not None else v.co)
    for f in src.faces:
        try: dst.faces.new([vm[v] for v in f.verts])
        except ValueError: pass
    src.free()
    nv = list(vm.values())
    if layers: setl(dst, nv, **layers)
    return nv


def rbox(bm, hx, hy, hz, p=5.0, cuts=5, M=None):
    """A superquadric rounded block (cast iron, stones)."""
    t = bmesh.new(); bmesh.ops.create_cube(t, size=2.0)
    bmesh.ops.subdivide_edges(t, edges=t.edges[:], cuts=cuts, use_grid_fill=True)
    for v in t.verts:
        u = v.co.normalized(); k = (abs(u.x) ** p + abs(u.y) ** p + abs(u.z) ** p) ** (1.0 / p)
        v.co = Vector((u.x / k * hx, u.y / k * hy, u.z / k * hz))
    return append(bm, t, M)


def clean(bm, dist=1e-5):
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=dist)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def mkobj(name, bm, mat, coll, kind, smooth=True, sharp=None, M=None):
    o = EV.bm_obj(name, bm, mat, coll, smooth=smooth)
    if sharp is not None:
        try: o.data.set_sharp_from_angle(angle=math.radians(sharp))
        except Exception: pass
    if M is not None: o.matrix_world = M
    o['uw_kind'] = kind
    return o


def _ridged(p, octaves=4):
    s = 0.0; a = 0.5; f = 1.0
    for i in range(octaves):
        n = 1.0 - abs(MN.noise(p * f + Vector((3.1 * i, 1.7 * i, 5.3 * i))))
        s += a * n * n; a *= 0.5; f *= 2.1
    return s


def rock_bm(seed, sub=3, size=(1.0, 1.0, 0.7), amp=0.42, freq=1.15, terr=0.07, flat=0.45):
    """A sea boulder: ridged-noise displaced icosphere, terraced into ledges, its base flattened where it sits in the sand."""
    b = bmesh.new(); bmesh.ops.create_icosphere(b, subdivisions=sub, radius=1.0)
    o = Vector((seed * 7.13, seed * 3.71, seed * 1.91))
    for v in b.verts:
        p = v.co.normalized()
        r = 1.0 + amp * (_ridged(p * freq + o) - 0.45) + 0.06 * MN.noise(p * 4.3 + o)
        k = p.z * 3.4 + 0.7 * MN.noise(p * 1.7 + o)
        r *= 1.0 - terr * _S(((k - math.floor(k)) - 0.7) / 0.22)
        x, y, z = p.x * size[0] * r, p.y * size[1] * r, p.z * size[2] * r
        if z < -flat * size[2]: z = -flat * size[2] + (z + flat * size[2]) * 0.3
        v.co = Vector((x, y, z))
    return b


def spire_bm(seed, h=1.0, sub_u=14, sub_v=22):
    """A stone stack: stacked irregular beds, each its own angular section, tapering to a broken crown. Unit height."""
    R = random.Random(seed); bm = bmesh.new(); rings = []
    beds = []; y = 0.0
    while y < 1.05:
        th = R.choice((R.uniform(0.03, 0.06), R.uniform(0.07, 0.13), R.uniform(0.15, 0.22)))
        n = R.randint(4, 7); a0 = R.uniform(0, math.tau)
        beds.append((y, th, [(a0 + (i + R.uniform(-0.3, 0.3)) / n * math.tau, R.uniform(0.7, 1.18)) for i in range(n)], R.uniform(-0.08, 0.08), R.uniform(-0.08, 0.08)))
        y += th

    def rad(verts, a):
        n = len(verts)
        for i in range(n):
            a1 = verts[i][0]; a2 = verts[(i + 1) % n][0] + (math.tau if i == n - 1 else 0.0)
            x = a
            while x < a1: x += math.tau
            if x <= a2: return verts[i][1] + (verts[(i + 1) % n][1] - verts[i][1]) * (x - a1) / max(1e-6, a2 - a1)
        return 1.0
    for j in range(sub_v + 1):
        v = j / sub_v; bi = 0
        while bi < len(beds) - 2 and v > beds[bi + 1][0]: bi += 1
        b0 = beds[bi]; b1 = beds[bi + 1]; f0 = min(1.0, max(0.0, (v - b0[0]) / b0[1])); f = 0.0 if f0 < 0.8 else (f0 - 0.8) / 0.2
        taper = (0.3 + 0.75 * max(1.0 - v, 0.0) ** 0.6) * (1.0 + 0.5 * math.exp(-v / 0.08))
        crown = max(0.0, 1.0 - max(0.0, (v - 0.92) / 0.08)) ** 0.5
        ring = []
        for i in range(sub_u):
            a = i / sub_u * math.tau
            w = (rad(b0[2], a) * (1 - f) + rad(b1[2], a) * f) * taper * crown + 0.02
            w *= 1.0 + 0.12 * MN.noise(Vector((math.cos(a) * 2 + seed, v * 6.0, math.sin(a) * 2)))
            ox = b0[3] * (1 - f) + b1[3] * f; oy = b0[4] * (1 - f) + b1[4] * f
            ring.append(Vector((math.cos(a) * w * 0.32 + ox * 0.3, math.sin(a) * w * 0.32 + oy * 0.3, v * h)))
        rings.append(ring)
    bridge(bm, rings, True, False, True, True)
    return bm


# ------------------------------------------------------------------------------------------------------------------ seabed mesh
FOCI = [(-96.0, 150.0, 0.7, 30.0), (-80.0, 155.0, 0.6, 30.0), (-60.0, 262.0, 1.2, 26.0), (-52.0, 190.0, 0.9, 28.0), (-150.0, 120.0, 1.4, 30.0)]


def _spacing(x, y):
    return min(s0 + math.hypot(x - fx, y - fy) / k for (fx, fy, s0, k) in FOCI)


def seabed_points(bounds, seed=3, cell=48.0):
    """An adaptive point set: dense (0.7 m) round the anchor and the hero sets, 48 m far out."""
    R = random.Random(seed); pts = []; x0, y0, x1, y1 = bounds

    def rec(ax, ay, w):
        cx, cy = ax + w / 2, ay + w / 2
        if w > _spacing(cx, cy) * 1.05 and w > 0.45:
            h = w / 2
            for dx in (0.0, h):
                for dy in (0.0, h): rec(ax + dx, ay + dy, h)
        else:
            px = cx + R.uniform(-0.3, 0.3) * w; py = cy + R.uniform(-0.3, 0.3) * w
            if x0 + 0.2 < px < x1 - 0.2 and y0 + 0.2 < py < y1 - 0.2: pts.append((px, py))
    for i in range(math.ceil((x1 - x0) / cell)):
        for j in range(math.ceil((y1 - y0) / cell)): rec(x0 + i * cell, y0 + j * cell, cell)
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        L = math.hypot(bx - ax, by - ay); t = 0.0
        while t < L:
            px = ax + (bx - ax) * t / L; py = ay + (by - ay) * t / L
            pts.append((px, py)); t += max(0.5, _spacing(px, py))
    return pts


def seabed_mesh(coll, mat, bounds=(-600.0, -360.0, 460.0, 402.0)):
    pts = seabed_points(bounds)
    out = MG.delaunay_2d_cdt([Vector(p) for p in pts], [], [], 0, 1e-5)
    vco, faces = out[0], out[2]
    verts = [(v.x, v.y, seabed_z(v.x, v.y)) for v in vco]
    o = EV.mesh_obj('UNDER_seabed', verts, faces, mat, coll, smooth=True)
    me = o.data
    if sum(p.normal.z for p in me.polygons[:200]) < 0: me.flip_normals()
    o['uw_kind'] = 'bed'
    return o


# ------------------------------------------------------------------------------------------------------------------ placement
class Space:
    """Keeps scattered things apart: spheres of what is placed + BVH trees of hero meshes (anchor, boat)."""
    def __init__(s): s.sph = []; s.trees = []
    def add(s, p, r): s.sph.append((Vector(p), r))
    def add_tree(s, t, pad=0.0): s.trees.append((t, pad))
    def free(s, p, r, pad=0.2):
        p = Vector(p)
        for q, rq in s.sph:
            if (p - q).length < r + rq + pad: return False
        for t, tp in s.trees:
            hit = t.find_nearest(p, r + pad + tp)
            if hit[0] is not None: return False
        return True


def place_on_bed(o, x, y, sink, yaw, tilt=1.0, extra=None):
    n = seabed_normal(x, y)
    n = (UP * (1.0 - tilt) + n * tilt).normalized()
    q = UP.rotation_difference(n) @ Quaternion(UP, yaw)
    if extra is not None: q = q @ extra
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = q
    o.location = (x, y, seabed_z(x, y) - sink)
    return o


ROCK_MESHES = {}


def rock_meshes(mat):
    if ROCK_MESHES and all(m.name in D.meshes for l in ROCK_MESHES.values() for m in l): return ROCK_MESHES
    ROCK_MESHES.clear()
    for key, sub, seeds, kw in (('big', 4, (1, 2, 3, 4), dict(size=(1.0, 0.85, 0.62))), ('mid', 3, (5, 6, 7), dict(size=(1.0, 0.8, 0.7))),
                                ('small', 2, (8, 9, 10), dict(size=(1.0, 0.85, 0.75), amp=0.3))):
        ROCK_MESHES[key] = []
        for sd in seeds:
            b = rock_bm(sd, sub, **kw); me = D.meshes.new('UNDER_rock_%s%d' % (key, sd)); b.to_mesh(me); b.free(); me.shade_smooth()
            me.materials.append(mat); ROCK_MESHES[key].append(me)
    ROCK_MESHES['spire'] = []
    for sd in (21, 22, 23):
        b = spire_bm(sd); clean(b); me = D.meshes.new('UNDER_spire%d' % sd); b.to_mesh(me); b.free(); me.shade_smooth(); me.materials.append(mat)
        ROCK_MESHES['spire'].append(me)
    return ROCK_MESHES


def scatter_rocks(coll, mat, space, seed=17):
    R = random.Random(seed); RM = rock_meshes(mat); out = []

    def put(key, x, y, s, sink=0.35, tilt=0.8, sq=1.0):
        me = R.choice(RM[key])
        r = s * (1.2 if key != 'spire' else 0.6)
        if not space.free((x, y, seabed_z(x, y) + r * 0.3), r, 0.4): return None
        o = D.objects.new('UNDER_rock', me); coll.objects.link(o)
        o.scale = (s, s * R.uniform(0.75, 1.1), s * sq) if key != 'spire' else (s * 0.9, s * 0.9, s)
        place_on_bed(o, x, y, s * sq * sink * (0.62 if key != 'spire' else 0.12), R.uniform(0, math.tau), tilt)
        o['uw_kind'] = 'rock'; o['tint'] = R.random(); o['inkr'] = float(r)
        space.add((x, y, seabed_z(x, y)), r); out.append(o)
        return o
    # stacks on the trench walls (frame the wide shots), stratified outcrops along both walls
    for (x, y, s) in ((-30.0, 98.0, 22.0), (-172.0, 102.0, 17.0), (12.0, 196.0, 19.0), (-196.0, 196.0, 15.0), (-128.0, 86.0, 13.0),
                      (-60.0, 70.0, 26.0), (-150.0, 58.0, 20.0), (-232.0, 92.0, 28.0), (42.0, 140.0, 24.0), (-262.0, 204.0, 22.0),
                      (-24.0, 236.0, 17.0), (64.0, 92.0, 20.0), (-118.0, 36.0, 30.0), (-300.0, 140.0, 26.0), (96.0, 190.0, 22.0)):
        put('spire', x, y, s, tilt=0.25)
    tries = 0; n = 0
    while n < 34 and tries < 900:
        tries += 1
        x = R.uniform(-330, 140); y = R.uniform(30, 290); t = _trench_t(x, y)
        if not (0.55 < t < 1.05): continue
        if put('big', x, y, R.uniform(4.0, 10.0), sink=0.4, sq=R.uniform(0.6, 1.0)): n += 1
    tries = 0; n = 0
    while n < 40 and tries < 1500:
        tries += 1
        a = R.uniform(0, math.tau); d = 12.0 + (R.random() ** 1.4) * 140.0
        x = -96.0 + math.cos(a) * d; y = 150.0 + math.sin(a) * d
        if put('mid', x, y, R.uniform(1.4, 4.2), sink=0.35): n += 1
    tries = 0; n = 0
    while n < 62 and tries < 2500:
        tries += 1
        a = R.uniform(0, math.tau); d = 7.0 + (R.random() ** 1.6) * 110.0
        x = -96.0 + math.cos(a) * d; y = 150.0 + math.sin(a) * d
        if put('small', x, y, R.uniform(0.35, 1.2), sink=0.3): n += 1
    return out


# ------------------------------------------------------------------------------------------------------------------ materials
def _ga(nb, n): return nb.attr(n, 'Fac', 'GEOMETRY')


def _rot2(nb, P, ang, sx=1.0, sy=1.0):
    px, py, pz = nb.xyz(P); c, s = math.cos(ang), math.sin(ang)
    return nb.vec(nb.mul(nb.add(nb.mul(px, c), nb.mul(py, s)), sx), nb.mul(nb.add(nb.mul(px, -s), nb.mul(py, c)), sy), pz)


def _sand(nb):
    g = nb.geo(); P = g.outputs['Position']; N = g.outputs['Normal']; px, py, pz = nb.xyz(P); nz = nb.xyz(N)[2]
    big = nb.noise(nb.vmath('SCALE', P, scale=0.018), 1.0, 3.0, 0.55, 0.0)
    c = nb.ramp(big, [(0.0, '#b4dccb'), (0.38, '#c9e2c6'), (0.55, '#d9e4c0'), (0.7, '#e4e6c2')], 'CONSTANT')
    mid = nb.noise(nb.vmath('SCALE', P, scale=0.09), 1.0, 3.0, 0.6, 0.3)
    c = nb.mixc(c, '#a9cfc6', nb.mul(nb.smooth(mid, 0.6, 0.63), 0.8))                        # grey-green silt patches
    # ripples: crests across the current, light crest + dark lee line, only on flat sand
    rp = _rot2(nb, P, 0.35, 1.0, 0.25)
    w = nb.wave(rp, 0.2, 'BANDS', 'X', 'SIN', dist=5.0, detail=2.0)
    w2 = nb.wave(_rot2(nb, P, -0.4, 1.0, 0.3), 0.55, 'BANDS', 'X', 'SIN', dist=3.0, detail=1.0)
    flat = nb.mul(nb.smooth(nz, 0.86, 0.95), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.05), 1.0, 2.0, 0.5, 0.0), 0.4, 0.5))
    _, dist, _ = view(nb)
    flat = nb.mul(flat, nb.math('EXPONENT', nb.mul(dist, -1.0 / 80.0)))        # ripples thin out with distance (no zebra far off)
    c = nb.mixc(c, nb.cmul(c, '#fff8e8'), nb.mul(nb.smooth(w, 0.72, 0.78), flat))
    c = nb.mixc(c, nb.cmul(c, '#9ec0cc'), nb.mul(nb.smooth(w, 0.2, 0.14), flat))
    c = nb.mixc(c, nb.cmul(c, '#c4d6d2'), nb.mul(nb.smooth(w2, 0.18, 0.12), nb.mul(flat, 0.3)))
    # slopes: rock and rubble with strata, drawn darker
    rock = nb.smooth(nz, 0.84, 0.7)
    st = nb.wave(nb.vec(nb.mul(px, 0.05), nb.mul(py, 0.05), pz), 0.9, 'BANDS', 'Z', 'SAW', dist=6.0, detail=2.0)
    rc = nb.ramp(st, [(0.0, '#7fa9b9'), (0.55, '#6c97b0'), (0.82, '#5a84a3')], 'CONSTANT')
    c = nb.mixc(c, rc, rock)
    # pebbles, shell grit, little dark holes
    vp = nb.vmath('SCALE', P, scale=1.6)
    d1 = nb.voronoi(vp, 1.0, 'F1'); cid = nb.voronoi(vp, 1.0, 'F1', out='Color')
    pick = nb.bw(cid)
    peb = nb.mul(nb.smooth(d1, 0.2, 0.14), nb.step(0.72, pick))
    c = nb.mixc(c, nb.mixc('#9fb8c8', '#f4efe2', nb.step(0.86, pick)), nb.mul(peb, 0.9))
    hole = nb.mul(nb.smooth(nb.voronoi(nb.vmath('SCALE', P, scale=0.7), 1.0, 'F1'), 0.07, 0.04), nb.step(0.8, nb.bw(nb.voronoi(nb.vmath('SCALE', P, scale=0.7), 1.0, 'F1', out='Color'))))
    c = nb.mixc(c, '#4f7f9c', nb.mul(hole, flat))
    # shallow slope: green algae turf and sea-grass shadow patches
    sh = nb.smooth(pz, -36.0, -24.0)
    gp = nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.06), 1.0, 3.0, 0.6, 0.2), 0.5, 0.53), sh)
    c = nb.mixc(c, '#8cbf6a', nb.mul(gp, 0.85))
    # the trench floor goes a little cooler and darker
    c = nb.mixc(c, nb.cmul(c, '#b7cde6'), nb.smooth(pz, -40.0, -62.0))
    return c


def _rock(nb):
    g = nb.geo(); P = g.outputs['Position']; N = g.outputs['Normal']; px, py, pz = nb.xyz(P); nz = nb.xyz(N)[2]
    st = nb.wave(nb.vec(nb.mul(px, 0.12), nb.mul(py, 0.12), pz), 0.75, 'BANDS', 'Z', 'SAW', dist=7.0, detail=2.0)
    c = nb.ramp(st, [(0.0, '#7eaabc'), (0.4, '#6a98b3'), (0.7, '#5986a8'), (0.9, '#8db7c2')], 'CONSTANT')
    c = nb.hsv(c, nb.add(0.47, nb.mul(nb.objattr('tint'), 0.06)), 1.0, 1.0)
    cr = nb.voronoi(nb.vmath('SCALE', P, scale=0.32), 1.0, 'DISTANCE_TO_EDGE')
    c = nb.mixc(c, '#3d5f8c', nb.smooth(cr, 0.035, 0.01))
    up = nb.smooth(nz, 0.35, 0.7)
    gm = nb.noise(nb.vmath('SCALE', P, scale=0.4), 1.0, 3.0, 0.6, 0.0)
    c = nb.mixc(c, nb.mixc('#69b97a', '#a9d36a', nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=1.3), 1.0, 2.0, 0.5, 0.0), 0.45, 0.55)), nb.mul(nb.smooth(gm, 0.46, 0.49), up))
    c = nb.mixc(c, '#d9e6cf', nb.mul(nb.smooth(gm, 0.3, 0.27), up))                                  # silt settled on the tops
    cl = nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=1.1), 1.0, 3.0, 0.6, 0.0), 0.66, 0.68), nb.smooth(nz, -0.2, 0.3))
    c = nb.mixc(c, nb.mixc('#ff7f9a', '#ffae4a', nb.step(0.5, nb.noise(nb.vmath('SCALE', P, scale=0.5), 1.0, 1.0, 0.5, 0.0))), cl)
    dots = nb.mul(nb.smooth(nb.voronoi(nb.vmath('SCALE', P, scale=3.0), 1.0, 'F1'), 0.16, 0.1), nb.step(0.75, nb.bw(nb.voronoi(nb.vmath('SCALE', P, scale=3.0), 1.0, 'F1', out='Color'))))
    return nb.mixc(c, '#f3eadb', nb.mul(dots, up))


def _iron(nb, s=1.0, growth=1.0):
    """Cast iron after decades on the bottom: dark steel blue, rust bloom, pitting; on the top faces a little algae, coralline
    crust and barnacle scars, kept sparse so the iron still reads as iron."""
    P = nb.tc().outputs['Object']; N = nb.geo().outputs['Normal']; nz = nb.xyz(N)[2]
    c = nb.ramp(nb.noise(nb.vmath('SCALE', P, scale=0.28 * s), 1.0, 3.0, 0.6, 0.2), [(0.0, '#3a4560'), (0.45, '#465374'), (0.62, '#55648a')], 'CONSTANT')
    rn = nb.noise(nb.vmath('MULTIPLY', P, (0.8 * s, 0.8 * s, 0.22 * s)), 1.0, 4.0, 0.6, 0.4)
    c = nb.mixc(c, '#7c4a3a', nb.smooth(rn, 0.57, 0.6))
    c = nb.mixc(c, '#b8643c', nb.smooth(rn, 0.68, 0.7))
    pit = nb.mul(nb.smooth(nb.voronoi(nb.vmath('SCALE', P, scale=2.2 * s), 1.0, 'F1'), 0.1, 0.06), 0.7)
    c = nb.mixc(c, '#283048', pit)
    if growth:
        # growth thins out by raising the thresholds (fewer, smaller patches in full colour), never by a see-through tint
        k = 1.0 - growth
        up = nb.smooth(nz, 0.25, 0.6)
        g = nb.noise(nb.vmath('SCALE', P, scale=0.42 * s), 1.0, 3.0, 0.6, 0.0)
        alg = nb.mixc('#4fae6a', '#93cc5a', nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=1.6 * s), 1.0, 2.0, 0.5, 0.0), 0.42, 0.58))
        c = nb.mixc(c, alg, nb.mul(nb.smooth(g, 0.53 + 0.09 * k, 0.555 + 0.09 * k), up))
        cn = nb.noise(nb.vmath('SCALE', P, scale=0.8 * s), 1.0, 3.0, 0.55, 0.0)
        crust = nb.mul(nb.smooth(cn, 0.66 + 0.07 * k, 0.685 + 0.07 * k), nb.smooth(nz, 0.0, 0.4))
        c = nb.mixc(c, nb.mixc('#ef7d9c', '#a98ae8', nb.step(0.52, nb.noise(nb.vmath('SCALE', P, scale=0.37 * s), 1.0, 1.0, 0.5, 0.0))), crust)
        vp = nb.vmath('SCALE', P, scale=4.5 * s)
        dot = nb.mul(nb.smooth(nb.voronoi(vp, 1.0, 'F1'), 0.16, 0.1), nb.step(0.8 + 0.12 * k, nb.bw(nb.voronoi(vp, 1.0, 'F1', out='Color'))))
        c = nb.mixc(c, '#e2dcea', nb.mul(dot, nb.smooth(nz, 0.1, 0.5)))
    return c


def _heat_terms(nb, local=None):
    """Heat glow from the object's prop `heat` (0..1), the colours of iron in a forge: a cherry-red to orange body, amber in the
    hottest patches, thin yellow-white cracks only here and there; flickers on fours. Every step keeps green well above blue (the
    light reads as fire-orange even through the cool water, never pink). Returns (heat level, emitted colour)."""
    h = nb.objattr('heat')
    if local is not None: h = nb.mul(h, local(nb))
    P = nb.tc().outputs['Object']
    n1 = nb.noise(nb.vmath('SCALE', P, scale=0.9), 1.0, 3.0, 0.6, 0.3, w=tq(nb, 4.0))
    n2 = nb.noise(nb.vmath('SCALE', P, scale=0.45), 1.0, 2.0, 0.5, 0.0, w=nb.add(tq(nb, 4.0), 7.0))
    crack = nb.mul(nb.smooth(nb.voronoi(nb.vmath('SCALE', P, scale=1.3), 1.0, 'DISTANCE_TO_EDGE'), 0.03, 0.0), nb.smooth(n2, 0.5, 0.66))
    he = nb.add(nb.mul(h, 0.4), nb.mul(nb.mul(nb.smooth(n1, 0.42, 0.75), 0.36), h))
    he = nb.math('MINIMUM', nb.add(he, nb.mul(crack, nb.mul(h, 0.4))), 1.0)
    hot = nb.ramp(he, [(0.0, '#000000'), (0.12, '#3c0a04'), (0.3, '#a81c08'), (0.42, '#e2380c'), (0.55, '#ff5c12'),
                       (0.68, '#ff8820'), (0.82, '#ffbc4c'), (1.0, '#fff4d0')], 'LINEAR')
    return he, hot


def _eye_local(nb):
    P = nb.tc().outputs['Object']
    return nb.smooth(nb.vmath('DISTANCE', P, (0.0, 0.0, SHANK)), 6.5, 1.6)


def _half_col(nb):
    """a broken shackle half: its iron, and grey granular fresh metal on the fracture and a hand's width round it (the crown:
    |x| < ~0.3, z > 6.1 in the shackle's frame)."""
    P = nb.tc().outputs['Object']; px, py, pz = nb.xyz(P)
    c = _iron(nb, 2.2, 0.3)
    fresh = nb.mul(nb.smooth(nb.math('ABSOLUTE', px), 0.34, 0.16), nb.smooth(pz, 6.0, 6.25))
    grain = nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=7.0), 1.0, 2.0, 0.6, 0.0), 0.38, 0.62)
    return nb.mixc(c, nb.mixc('#8e98aa', '#cfd6e2', grain), fresh)


def _pin_col(nb):
    P = nb.tc().outputs['Object']; px, py, pz = nb.xyz(P)
    c = _iron(nb, 1.6, 0.35)
    fresh = nb.smooth(nb.math('ABSOLUTE', px), 0.32, 0.2)
    return nb.mixc(c, nb.mixc('#c3c9d6', '#e8ecf2', nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=6.0), 1.0, 2.0, 0.5, 0.0), 0.4, 0.6)), fresh)


def _crust(nb):
    k = _ga(nb, 'kind'); t = _ga(nb, 'tint'); cav = _ga(nb, 'cav')
    barn = nb.mixc('#a9a2b6', '#978fa9', nb.step(0.5, t))
    barn = nb.mixc(barn, '#5a5574', cav)
    spon = nb.ramp(t, [(0.0, '#ff8a3d'), (0.25, '#ffd84a'), (0.5, '#b07cff'), (0.75, '#ff5f6e')], 'CONSTANT')
    spon = nb.mixc(spon, nb.cmul(spon, '#6a4a6a'), cav)
    alg = nb.ramp(t, [(0.0, '#5cbf5a'), (0.4, '#a6d24a'), (0.75, '#e0729a')], 'CONSTANT')
    c = nb.mixc(barn, spon, nb.step(0.5, k))
    return nb.mixc(c, alg, nb.step(1.5, k))


def _coral(pattern):
    def col(nb):
        P = nb.tc().outputs['Object']; px, py, pz = nb.xyz(P)
        base = nb.ramp(nb.objattr('tint'), [(i / len(CORAL), h) for i, h in enumerate(CORAL)], 'CONSTANT')
        if pattern == 'brain':
            m = nb.wave(nb.vmath('SCALE', P, scale=1.0), 2.2, 'BANDS', 'X', 'SIN', dist=16.0, detail=3.0)
            base = nb.mixc(base, nb.cmul(base, '#5a3a6a'), nb.smooth(m, 0.25, 0.18))
            base = nb.mixc(base, nb.mixc(base, '#ffffff', 0.45), nb.smooth(m, 0.8, 0.88))
        elif pattern == 'branch':
            base = nb.mixc(base, nb.mixc(base, '#fff4e8', 0.6), nb.smooth(_ga(nb, 'tip'), 0.75, 0.95))
            base = nb.mixc(nb.cmul(base, '#9a7aa0'), base, nb.smooth(_ga(nb, 'tip'), 0.0, 0.3))
        elif pattern == 'fan':
            v = nb.voronoi(nb.vmath('SCALE', P, scale=7.0), 1.0, 'DISTANCE_TO_EDGE')
            base = nb.mixc(nb.cmul(base, '#5a3a6a'), base, nb.smooth(v, 0.02, 0.06))
        elif pattern == 'table':
            dots = nb.smooth(nb.voronoi(nb.vmath('SCALE', P, scale=9.0), 1.0, 'F1'), 0.28, 0.18)
            base = nb.mixc(base, nb.mixc(base, '#ffffff', 0.4), nb.mul(dots, nb.smooth(pz, 0.55, 0.65)))
            base = nb.mixc(base, nb.cmul(base, '#7a5a8a'), nb.smooth(pz, 0.5, 0.3))
        elif pattern == 'tube':
            base = nb.mixc(base, nb.cmul(base, '#4a3060'), _ga(nb, 'cav'))
            base = nb.mixc(base, nb.mixc(base, '#ffffff', 0.5), _ga(nb, 'tip'))
        return base
    return col


def _kelp(nb):
    t = _ga(nb, 'tint'); u = _ga(nb, 'u'); st = _ga(nb, 'stem')
    c = nb.ramp(t, [(i / len(KELP), h) for i, h in enumerate(KELP)], 'CONSTANT')
    c = nb.mixc(c, nb.mixc(c, '#f4f0a0', 0.45), nb.smooth(u, 0.25, 0.08))                    # pale midrib
    c = nb.mixc(c, nb.cmul(c, '#6f8a6a'), nb.smooth(u, 0.8, 0.95))                           # darker frilled edge
    c = nb.mixc(c, '#7d7a3a', st)
    P = nb.tc().outputs['Object']
    spot = nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=1.8), 1.0, 2.0, 0.6, 0.0), 0.64, 0.67)
    return nb.mixc(c, nb.cmul(c, '#c8b878'), nb.mul(spot, 0.5))


def _translucent(strength=0.6, tint='#f2ff9a'):
    def post(nb, c, glow):
        I = nb.geo().outputs['Incoming']
        back = nb.smooth(nb.vmath('DOT_PRODUCT', nb.vmath('SCALE', I, scale=-1.0), _v(nb, 'uwSun')), 0.25, 0.85)
        up = nb.smooth(nb.xyz(nb.vmath('SCALE', I, scale=-1.0))[2], 0.1, 0.6)
        k = nb.mul(nb.mx(back, nb.mul(up, 0.55)), strength)
        return nb.mixc(c, nb.cmul(nb.cadd(c, '#303010'), tint), k), glow
    return post


def _wood(nb):
    """Boat timber: planks with dark seams, peeling paint (red bottom, white boot stripe, teal topsides), algae and coralline
    patches on the faces that look up."""
    P = nb.tc().outputs['Object']; px, py, pz = nb.xyz(P); N = nb.geo().outputs['Normal']; nz = nb.xyz(N)[2]
    seam = nb.math('FRACT', nb.mul(nb.add(pz, nb.mul(nb.noise(nb.vmath('SCALE', P, scale=0.3), 1.0, 2.0, 0.5, 0.0), 0.12)), 3.4))
    c = nb.ramp(nb.noise(nb.vec(nb.mul(px, 0.25), nb.mul(nb.math('FLOOR', nb.mul(pz, 3.4)), 3.1), 0.0), 1.0, 2.0, 0.5, 0.0),
                [(0.0, '#9c8466'), (0.45, '#b39a74'), (0.6, '#8c7a66')], 'CONSTANT')
    paint = nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.45), 1.0, 4.0, 0.65, 0.3), 0.6, 0.56)
    hull = nb.mixc(nb.mixc('#d2483a', '#f4efe2', nb.smooth(pz, 0.82, 0.86)), '#1f9e9a', nb.smooth(pz, 1.02, 1.06))
    c = nb.mixc(c, hull, paint)
    c = nb.mixc(c, '#4a3a40', nb.smooth(seam, 0.07, 0.0))
    up = nb.smooth(nz, 0.2, 0.6)
    g = nb.noise(nb.vmath('SCALE', P, scale=0.7), 1.0, 3.0, 0.6, 0.0)
    c = nb.mixc(c, nb.mixc('#5cae62', '#a8cf5a', nb.step(0.5, nb.noise(nb.vmath('SCALE', P, scale=2.0), 1.0, 1.0, 0.5, 0.0))), nb.mul(nb.smooth(g, 0.5, 0.53), up))
    c = nb.mixc(c, '#e98aa5', nb.mul(nb.smooth(g, 0.72, 0.74), nb.smooth(nz, -0.3, 0.2)))
    return c


def _fish(back, belly, stripe, tail=None, spots=False):
    def col(nb):
        P = nb.tc().outputs['Object']; px, py, pz = nb.xyz(P)
        c = nb.mixc(nb.rgb(belly), nb.rgb(back), nb.smooth(pz, -0.02, 0.03))
        c = nb.mixc(c, stripe, nb.mul(nb.smooth(nb.math('ABSOLUTE', nb.sub(pz, 0.012)), 0.018, 0.01), nb.smooth(px, -0.45, -0.3)))
        if tail: c = nb.mixc(c, tail, nb.smooth(px, -0.4, -0.46))
        if spots:
            sp = nb.smooth(nb.voronoi(nb.vmath('SCALE', P, scale=14.0), 1.0, 'F1'), 0.22, 0.15)
            c = nb.mixc(c, nb.cmul(c, '#7a4a5a'), nb.mul(sp, 0.8))
        eye = nb.smooth(nb.vmath('DISTANCE', nb.vec(px, nb.mul(nb.math('ABSOLUTE', py), 0.0), pz), (0.36, 0.0, 0.035)), 0.045, 0.035)
        c = nb.mixc(c, '#f8f8ff', eye)
        c = nb.mixc(c, '#1a1630', nb.smooth(nb.vmath('DISTANCE', nb.vec(px, 0.0, pz), (0.365, 0.0, 0.035)), 0.026, 0.018))
        return c
    return col


def _surface(nb):
    """The sea seen from below: Snell's window of bright sky straight up, drawn ripple highlights (wavy noise contours and
    flecks of light, foreshortened by perspective), swell light and shade, the sun glare; melting into the water colour toward
    the horizon (total internal reflection)."""
    P, dist, d = view(nb); up = nb.xyz(d)[2]; px, py, _ = nb.xyz(P)
    t = tq(nb); q = nb.vec(px, py, 0.0)
    n0 = nb.noise(nb.vmath('ADD', nb.vmath('SCALE', q, scale=0.012), nb.vec(nb.mul(t, 0.02), 0.0, 0.0)), 1.0, 3.0, 0.5, 0.0)
    win = nb.smooth(nb.add(up, nb.mul(nb.sub(n0, 0.5), 0.12)), 0.6, 0.84)
    out = nb.mixc(_c(nb, 'uwW2'), _c(nb, 'uwW1'), nb.smooth(up, 0.06, 0.55))
    inn = nb.mixc('#8eeafa', _c(nb, 'uwW0'), nb.smooth(up, 0.7, 0.97))
    c = nb.mixc(out, inn, win)
    sw = nb.smooth(nb.noise(nb.vmath('ADD', nb.vmath('SCALE', q, scale=0.025), nb.vec(4.0, nb.mul(t, 0.04), 0.0)), 1.0, 2.0, 0.5, 0.0), 0.38, 0.6)
    c = nb.mixc(nb.cmul(c, '#b4dcf6'), c, nb.add(0.4, nb.mul(sw, 0.6)))
    w = nb.vec(nb.noise(nb.vmath('SCALE', q, scale=0.04), 1.0, 2.0, 0.5, 0.0, w=nb.mul(t, 0.1)),
               nb.noise(nb.vmath('ADD', nb.vmath('SCALE', q, scale=0.04), (3.3, 7.1, 0.0)), 1.0, 2.0, 0.5, 0.0, w=nb.mul(t, 0.1)), 0.0)
    qw = nb.vmath('ADD', q, nb.vmath('SCALE', nb.vmath('SUBTRACT', w, (0.5, 0.5, 0.0)), scale=14.0))
    n1 = nb.noise(nb.vmath('SCALE', qw, scale=0.25), 1.0, 2.0, 0.55, 0.0, w=nb.mul(t, 0.35))
    n2 = nb.noise(nb.vmath('SCALE', _rot2(nb, qw, 0.7, 1.0, 0.6), scale=0.5), 1.0, 2.0, 0.5, 0.0, w=nb.add(nb.mul(t, 0.5), 3.0))
    lines = nb.add(nb.smooth(nb.math('ABSOLUTE', nb.sub(n1, 0.5)), 0.03, 0.008), nb.mul(nb.smooth(nb.math('ABSOLUTE', nb.sub(n2, 0.5)), 0.026, 0.006), 0.7))
    flecks = nb.smooth(n2, 0.67, 0.71)
    # level of detail: the drawn ripples thin out with distance and at grazing angles (no sparkle noise toward the horizon);
    # what they lose comes back as an even sheen so the far surface stays bright
    near = nb.mul(nb.math('EXPONENT', nb.mul(dist, -1.0 / 170.0)), nb.smooth(up, 0.03, 0.3))
    hl = nb.math('MINIMUM', nb.mul(nb.add(lines, flecks), nb.mul(near, nb.add(0.4, nb.mul(win, 0.6)))), 1.0)
    c = nb.mixc(c, '#ffffff', nb.add(nb.mul(hl, nb.add(0.55, nb.mul(sw, 0.45))), nb.mul(nb.sub(1.0, near), 0.1)))
    s_ = nb.mx(nb.vmath('DOT_PRODUCT', d, _v(nb, 'uwSun')), 0.0)
    gl = nb.add(nb.mul(nb.math('POWER', s_, 160.0), 1.0), nb.mul(nb.math('POWER', s_, 36.0), 0.13))
    c = nb.cadd(c, nb.vmath('SCALE', (0.85, 1.0, 1.0), scale=gl))
    c = nb.mixc(wgrad(nb, d), c, nb.mul(nb.math('EXPONENT', nb.mul(dist, -0.0006)), nb.smooth(up, 0.015, 0.16)))
    return nb.mixc(c, nb.mixc(c, '#e6f2ff', 0.6), nb.mul(_f(nb, 'flash'), 0.8)), gl


def _backdrop(nb):
    _, dist, d = view(nb); c = wgrad(nb, d)
    dx, dy, dz = nb.xyz(d)
    az = nb.math('ARCTAN2', dy, dx)
    for k in range(3):
        n = nb.noise(nb.vec(nb.mul(az, 2.0 + k * 1.3), 3.0 + k * 5.0, 0.0), 1.0, 4.0, 0.55, 0.0)
        h = nb.add(-0.02 + 0.03 * (2 - k), nb.mul(nb.sub(1.0, nb.math('ABSOLUTE', nb.sub(nb.mul(n, 2.0), 1.0))), 0.09 - 0.02 * k))
        m = nb.smooth(nb.sub(dz, h), 0.004, -0.004)
        rc = nb.mixc(_c(nb, 'uwW2'), _c(nb, 'uwW3'), 0.12 + 0.12 * k)
        c = nb.mixc(c, nb.mixc(rc, c, 0.5 + 0.15 * k), nb.mul(m, 0.55 - 0.12 * k))
    return c


def materials():
    M = {}
    M['sand'] = ucel('M_UNDER_sand', _sand, ink=0.0, paint=1.0, vary=0.05, vscale=0.05, coord='Object', rim=0.0, deep=0.3, steps=4)
    M['rock'] = ucel('M_UNDER_rock', _rock, ink=1.0, paint=1.0, vary=0.08, vscale=0.12, rim=0.3, deep=0.6, cut=55.0)
    M['anchor'] = ucel('M_UNDER_anchor', lambda nb: _iron(nb, 1.4, 0.75), ink=1.0, spec=0.35, rim=0.4, deep=0.6, vary=0.06, cut=None, heat=_eye_local)
    M['shackle'] = ucel('M_UNDER_shackle', lambda nb: _iron(nb, 2.2, 0.3), ink=1.0, spec=0.5, rim=0.45, deep=0.6, vary=0.05, cut=None, heat=True)
    M['shackle_half'] = ucel('M_UNDER_shackle_half', _half_col, ink=1.0, spec=0.5, rim=0.45, deep=0.6, vary=0.05, cut=None, heat=True)
    M['pin'] = ucel('M_UNDER_pin', _pin_col, ink=1.0, spec=0.7, rim=0.45, vary=0.04, cut=None, heat=True)
    M['crust'] = ucel('M_UNDER_crust', _crust, ink=0.0, rim=0.3, vary=0.06, cscale=0.5)
    for k in ('brain', 'branch', 'fan', 'table', 'tube'):
        M['coral_' + k] = ucel('M_UNDER_coral_' + k, _coral(k), ink=1.0, rim=0.45, vary=0.07, cscale=0.6, cut=45.0, post=_translucent(0.25, '#ffe8f0') if k in ('fan', 'branch') else None)
    M['kelp'] = ucel('M_UNDER_kelp', _kelp, ink=1.0, rim=0.5, vary=0.06, caust=0.6, post=_translucent(0.75), cut=40.0)
    M['grass'] = ucel('M_UNDER_grass', lambda nb: nb.ramp(_ga(nb, 'tint'), [(0.0, '#5fbf5a'), (0.35, '#8ccf4c'), (0.7, '#3fae78')], 'CONSTANT'), ink=0.0, rim=0.5, caust=0.5, post=_translucent(0.5))
    M['wood'] = ucel('M_UNDER_wood', _wood, ink=1.0, rim=0.35, deep=0.6, vary=0.06, grime=0.5, wscale=0.4, cut=90.0)
    M['fish_sardine'] = ucel('M_UNDER_fish_sardine', _fish('#2f63b8', '#eef8ff', '#8ff0ff'), ink=0.9, spec=0.8, rim=0.5, vary=0.0, caust=0.5, cut=40.0)
    M['fish_snapper'] = ucel('M_UNDER_fish_snapper', _fish('#ff9a2e', '#fff1d6', '#3a6fe0'), ink=0.9, spec=0.6, rim=0.5, vary=0.0, caust=0.5, cut=40.0)
    M['fish_tang'] = ucel('M_UNDER_fish_tang', _fish('#2350d8', '#3d6cf0', '#0d1e70', tail='#ffd84a'), ink=0.9, spec=0.5, rim=0.5, vary=0.0, caust=0.5, cut=40.0)
    M['fish_grouper'] = ucel('M_UNDER_fish_grouper', _fish('#b75a3e', '#e8b48e', '#7a3a2e', spots=True), ink=1.0, spec=0.3, rim=0.4, vary=0.04, caust=0.6, cut=40.0)
    M['snow'] = _snow_mat()
    nb = NB('M_UNDER_surface'); c, gl = _surface(nb); M['surface'] = LK.finish(nb, c, 0.0, 0.25, nb.mul(gl, 0.8), hz=0.0)
    nb = NB('M_UNDER_backdrop'); M['backdrop'] = LK.finish(nb, _backdrop(nb), 0.0, 1.0, 0.0, hz=0.0)
    M['ray'] = _ray_mat()
    return M


def _ray_mat():
    nb = NB('M_UNDER_ray')
    g = nb.geo(); N = g.outputs['Normal']; I = g.outputs['Incoming']
    lz = nb.xyz(nb.tc().outputs['Object'])[2]
    face = nb.math('POWER', nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', N, I)), 1.8)
    along = nb.mul(nb.smooth(lz, 0.0, -0.1), nb.smooth(lz, -1.0, -0.35))
    t = tq(nb)
    fl = nb.add(0.55, nb.mul(nb.noise(nb.vec(nb.mul(lz, 2.5), nb.objattr('seed'), nb.mul(t, 0.5)), 1.0, 2.0, 0.5, 0.0), 0.8))
    _, dist, d = view(nb)
    fog = nb.math('EXPONENT', nb.mul(nb.mul(dist, _f(nb, 'uwFogD')), -0.7))
    a = nb.math('MINIMUM', nb.mul(nb.mul(nb.mul(face, along), nb.mul(fl, nb.objattr('amp'))), nb.mul(fog, _f(nb, 'uwOn'))), 1.0)
    col = nb.mixc(_c(nb, 'uwW0'), '#e4fdff', 0.4)
    m = LK.finish(nb, col, 0.0, 0.0, 0.0, alpha=a, blend=True, hz=0.0)
    try: m.use_backface_culling = True
    except Exception: pass
    return m


def _snow_mat():
    """Marine snow: soft round specks (alpha by facing), fogged, blended so they write no depth and get no ink."""
    nb = NB('M_UNDER_snow')
    g = nb.geo(); N = g.outputs['Normal']; I = g.outputs['Incoming']
    face = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', N, I))
    col, _, f = water(nb, nb.rgb('#f0fdff'), None, 1.3)
    a = nb.mul(nb.smooth(face, 0.15, 0.75), nb.mul(nb.sub(1.0, nb.mul(f, 0.7)), 0.8))
    return LK.finish(nb, col, 0.0, 0.0, 0.0, alpha=a, blend=True, hz=0.0)


# ------------------------------------------------------------------------------------------------------------------ the anchor
SHANK_ST = [(-0.5, 1.3, 1.1), (2.4, 1.3, 1.1), (6.0, 1.2, 1.0), (10.0, 1.1, 0.92), (14.0, 1.0, 0.84), (16.2, 1.05, 0.93), (16.9, 0.98, 0.88), (17.25, 0.94, 0.82)]
FLUKE_ST = [(0.0, 2.3, 1.9), (1.6, 2.4, 1.8), (3.2, 3.0, 1.5), (5.2, 3.9, 1.2), (6.8, 4.3, 1.0), (8.3, 3.9, 0.85), (9.6, 2.9, 0.65), (10.5, 1.6, 0.45), (11.0, 0.35, 0.22)]
FLUKE_SEC = [(-0.5, 0.0), (-0.44, 0.62), (-0.14, 0.95), (0.0, 1.0), (0.14, 0.95), (0.44, 0.62), (0.5, 0.0), (0.42, -0.55), (0.0, -0.7), (-0.42, -0.55)]


def anchor_bm():
    """A stockless (Hall) anchor in its own frame: X' = trunnion and pin axis, Z' = shank (crown centre at the origin, eye at
    Z' = SHANK), both flukes leave the crown toward -Y' at ALPHA from the shank."""
    bm = bmesh.new()
    rbox(bm, 3.7, 1.9, 2.1, p=4.5, cuts=7)                                                        # crown
    rbox(bm, 3.95, 2.12, 0.3, p=6.0, cuts=5, M=Matrix.Translation((0.0, 0.0, 0.8)))              # cast flange band
    for sx in (-1, 1):                                                                            # trunnion bosses
        prof = [(0.0, sx * 3.3), (1.05, sx * 3.3), (1.05, sx * 4.05), (0.9, sx * 4.3), (0.35, sx * 4.33), (0.0, sx * 4.33)]
        revolve(bm, prof, 18, axis='X')
    rings = []
    for z, a, b in SHANK_ST:
        c = min(a, b) * 0.34
        rings.append([Vector((x, y, z)) for x, y in ((a, b - c), (a - c, b), (-a + c, b), (-a, b - c), (-a, -b + c), (-a + c, -b), (a - c, -b), (a, -b + c))])
    bridge(bm, rings, True, False, True, True)
    revolve(bm, [(0.68, -1.5), (1.22, -1.5), (1.42, -1.32), (1.42, 1.32), (1.22, 1.5), (0.68, 1.5)], 30, M=Matrix.Translation((0.0, 0.0, SHANK)), axis='X', closed=True)
    fd = Vector((0.0, -math.sin(ALPHA), math.cos(ALPHA))); fn = Vector((0.0, math.cos(ALPHA), math.sin(ALPHA)))
    for sx in (-1, 1):
        rings = []
        for t, w, th in FLUKE_ST:
            ctr = Vector((sx * (2.2 + 0.6 * _S(t / 7.5)), 0.0, 0.0)) + fd * t
            rings.append([ctr + Vector((sx * u * w, 0.0, 0.0)) + fn * (v * th * 0.5) for u, v in FLUKE_SEC])
        bridge(bm, rings, True, False, True, True)
    clean(bm)
    return bm


SH_RB, SH_RR, SH_Z0 = 2.4, 0.72, 0.85            # shackle bow radius, rod radius, leg foot (model units)
SH_CROWN = 20                                    # index of the bow's top (x = 0) on the shackle's tube path
SH_LUG = 2.4                                     # lug centre |x| on the pin axis (each half's pivot when it breaks)


def _shackle_path():
    Rb, cz, z0 = SH_RB, PIN_DROP, SH_Z0
    path = [Vector((-Rb, 0.0, z0 + (cz - z0) * i / 6)) for i in range(7)]
    path += [Vector((Rb * math.cos(math.pi - math.pi * i / 28), 0.0, cz + Rb * math.sin(math.pi - math.pi * i / 28))) for i in range(1, 28)]
    path += [Vector((Rb, 0.0, cz - (cz - z0) * i / 6)) for i in range(7)]
    return path


def _lug(bm, sx):
    prof = [(0.68, sx * 1.62), (1.1, sx * 1.62), (1.25, sx * 1.76), (1.25, sx * 3.04), (1.1, sx * 3.18), (0.68, sx * 3.18)]
    revolve(bm, prof, 30, axis='X', closed=True)


def shackle_bm():
    """D-shackle in its own frame: origin on the pin axis (the hinge), pin along X, bow up, bow centre at Z = PIN_DROP."""
    bm = bmesh.new()
    tube(bm, _shackle_path(), SH_RR, seg=18)
    for sx in (-1, 1): _lug(bm, sx)
    clean(bm)
    return bm


def _crack_x(y, dz):
    """the fracture surface across the bow's crown (shared by both halves, so they mate): its x offset at a point (y, dz)
    of the rod's section (dz from the crown's centre line), a low jagged ridge (<= 0.13 model units)."""
    r = math.hypot(y, dz)
    return 0.7 * _jag(math.atan2(y, dz), r)


def shackle_half_bm(side):
    """One of the two halves the bow snaps into at its crown (s16): a = the -X leg and lug, b = the +X leg and lug, in the
    shackle's own frame (same origin and axes as shackle_bm). The rod is rebuilt from the crown outward, so both halves share
    the crown's section frame; its end is a jagged fracture face (the same surface for both, 0.02 apart)."""
    bm = bmesh.new(); seg = 18
    path = _shackle_path()
    pts = list(reversed(path[:SH_CROWN + 1])) if side == 'a' else path[SH_CROWN:]
    sg = -1.0 if side == 'a' else 1.0                            # the half's material lies toward sg * X from the crack
    fr_ = frames(pts)
    c0 = pts[0]; X = Vector((1.0, 0.0, 0.0))
    def flat(v): v = v - X * v.dot(X); return v.normalized()
    cf = (None, flat(fr_[0][1]), flat(fr_[0][2]))                 # the crack's section lies in the plane x = 0
    def ring(c, f, r, crack=False):
        out = []
        for k in range(seg):
            a = math.tau * k / seg
            p = c + (f[1] * math.cos(a) + f[2] * math.sin(a)) * r
            if crack: p = p + X * (_crack_x(p.y - c0.y, p.z - c0.z) + 0.01 * sg)
            out.append(p)
        return out
    rings = [ring(c0, cf, r, True) for r in (0.0, 0.18, 0.36, 0.54, SH_RR)]
    rings += [ring(p, f, SH_RR) for p, f in zip(pts[1:], fr_[1:])]
    bridge(bm, rings, True, False, False, True)
    _lug(bm, sg)
    clean(bm)
    return bm


def shackle_halves(coll, M, s):
    """UNDER_shackle_a / _b: the halves, hidden (hide_render) unless a shot keys them on; heat follows the shackle by driver,
    QA treats them as movers. Their frame is the shackle's (the shot places them)."""
    out = []
    for side in ('a', 'b'):
        o = mkobj('UNDER_shackle_' + side, shackle_half_bm(side), M['shackle_half'], coll, 'shackle', smooth=True, sharp=50.0, M=S_MAT.copy())
        _drive_prop(o, 'heat', s, 'heat'); o['qa_mover'] = 'uw'; o.hide_render = True
        out.append(o)
    return out


def _jag(th, r):
    return (0.11 * math.sin(3.0 * th + 0.4) + 0.05 * math.sin(7.0 * th + 1.3)) * (r / 0.6)


def pin_half(side):
    """One half of the pin, split at the shear plane (x = 0 in the shackle frame) by a wavy fracture face; a = head, b = nut."""
    bm = bmesh.new(); seg = 24

    def ring(x, r, jag=False):
        return [Vector((x + (_jag(math.tau * k / seg, r) if jag else 0.0), r * math.cos(math.tau * k / seg), r * math.sin(math.tau * k / seg))) for k in range(seg)]
    if side == 'a':
        rings = [ring(h, r) for r, h in ((0.0, -3.74), (0.96, -3.74), (1.03, -3.66), (1.03, -3.34), (0.96, -3.26), (0.6, -3.26))]
        rings += [ring(-0.016, r, True) for r in (0.6, 0.45, 0.3, 0.15, 0.0)]
        bridge(bm, rings, True, False)
    else:
        rings = [ring(0.016, r, True) for r in (0.0, 0.15, 0.3, 0.45, 0.6)]
        rings += [ring(h, r) for r, h in ((0.6, 3.3), (0.0, 3.3))]
        bridge(bm, rings, True, False)
        revolve(bm, [(0.0, 3.26), (0.92, 3.26), (0.92, 3.72), (0.0, 3.72)], 6, axis='X', a0=math.pi / 6)        # hex nut
        revolve(bm, [(0.0, 3.72), (0.5, 3.72), (0.5, 4.0), (0.42, 4.08), (0.0, 4.08)], 16, axis='X')           # threaded stub
        cot = [Vector((3.9, 0.0, z)) for z in (-0.78, -0.4, 0.0, 0.4, 0.62)] + [Vector((3.9, 0.14, 0.76)), Vector((3.9, 0.32, 0.7))]
        tube(bm, cot, 0.07, seg=6)                                                                                # forelock pin
    clean(bm)
    return bm


def _drive_prop(o, prop, src, src_prop):
    if prop not in o: o[prop] = 0.0
    fc = o.driver_add('["%s"]' % prop); d = fc.driver; d.type = 'AVERAGE'
    v = d.variables.new(); v.type = 'SINGLE_PROP'; v.targets[0].id_type = 'OBJECT'; v.targets[0].id = src; v.targets[0].data_path = '["%s"]' % src_prop
    return fc


def anchor_set(coll, M):
    abm = anchor_bm(); keep = abm.copy()
    a = mkobj('UNDER_anchor', abm, M['anchor'], coll, 'anchor', smooth=True, sharp=38.0, M=A_MAT.copy())
    s = mkobj('UNDER_shackle', shackle_bm(), M['shackle'], coll, 'shackle', smooth=True, sharp=50.0, M=S_MAT.copy())
    pa = mkobj('UNDER_pin_a', pin_half('a'), M['pin'], coll, 'pin', smooth=True, sharp=40.0, M=S_MAT.copy())
    pb = mkobj('UNDER_pin_b', pin_half('b'), M['pin'], coll, 'pin', smooth=True, sharp=40.0, M=S_MAT.copy())
    s['heat'] = 0.0
    for o in (pa, pb, a): _drive_prop(o, 'heat', s, 'heat')
    e = D.objects.new('UNDER_chain_end', None); coll.objects.link(e)
    e.empty_display_type = 'ARROWS'; e.empty_display_size = 4.0
    m = S_ROT.copy(); m.translation = BOW; e.matrix_world = m                       # unscaled: the chain hangs off it
    e['uw_kind'] = 'empty'
    return a, s, pa, pb, e, keep


# ------------------------------------------------------------------------------------------------------------------ growth on the anchor
def _barnacle(bm, M, s, R):
    vv = revolve(bm, [(0.0, -0.14), (1.0, -0.14), (1.0, 0.0), (0.82, 0.34), (0.52, 0.62), (0.38, 0.62), (0.3, 0.4), (0.0, 0.4)], 7,
                 M=M @ Matrix.Diagonal((s, s, s * R.uniform(0.8, 1.15), 1.0)))
    cav = [v for r in vv[5:] for v in r]
    return flat_verts(vv), cav


def _sponge(bm, M, s, R):
    if R.random() < 0.6:
        vv = revolve(bm, [(0.0, -0.15), (0.55, -0.15), (0.62, 0.3), (0.72, 0.9), (0.7, 1.08), (0.57, 1.1), (0.5, 0.62), (0.0, 0.52)], 10,
                     M=M @ Matrix.Diagonal((s, s, s * R.uniform(0.8, 1.3), 1.0)))
        return flat_verts(vv), [v for r in vv[5:] for v in r]
    allv, cav = [], []
    for k in range(R.randint(3, 5)):
        a = R.uniform(0, math.tau); d = R.uniform(0.0, 0.35) * s; h = R.uniform(0.6, 1.5)
        T = M @ Matrix.Translation((math.cos(a) * d, math.sin(a) * d, 0.0)) @ Matrix.Diagonal((s * 0.8, s * 0.8, s * h, 1.0))
        vv = revolve(bm, [(0.0, -0.1), (0.2, -0.1), (0.22, 1.0), (0.15, 1.0), (0.13, 0.65), (0.0, 0.6)], 8, M=T)
        allv += flat_verts(vv); cav += [v for r in vv[3:] for v in r]
    return allv, cav


def _tuft(bm, p, n, R, size, lay_h=0.0):
    """Algae / grass tuft: thin ribbons rising along n, leaning out and curling. Returns verts with sway attributes set by caller."""
    t1 = n.orthogonal().normalized(); t2 = n.cross(t1); out = []
    for k in range(R.randint(4, 7)):
        a = R.uniform(0, math.tau); lean = R.uniform(0.15, 0.6); L = size * R.uniform(0.5, 1.0); w = size * R.uniform(0.06, 0.12)
        d0 = (n + (t1 * math.cos(a) + t2 * math.sin(a)) * lean).normalized()
        side = (t1 * -math.sin(a) + t2 * math.cos(a))
        pts = []
        for i in range(4):
            f = i / 3.0; dd = (d0 + (t1 * math.cos(a) + t2 * math.sin(a)) * (f * f * 0.6)).normalized()
            pts.append(p + dd * L * f)
        rows = [[q - side * (w * (1.0 - i / 3.0) * 0.5), q + side * (w * (1.0 - i / 3.0) * 0.5)] for i, q in enumerate(pts)]
        vv = bridge(bm, rows, False, False)
        for i, r in enumerate(vv):
            for v in r: out.append((v, i / 3.0 * L, k))
    return out


def crust_on(target, bm_local, coll, mat, seed=5, n_barn=900, n_sponge=24, n_tuft=150, keep_out=None, name='UNDER_anchor_crust', kind='crust'):
    """Barnacles, sponges and algae tufts grown on the target's upward faces, in its local frame; one object parented to it."""
    R = random.Random(seed); Mw = target.matrix_world.copy(); R3 = Mw.to_3x3()
    tri = bm_local.copy(); bmesh.ops.triangulate(tri, faces=tri.faces[:]); tri.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(tri)
    pool = []; cum = []; tot = 0.0
    for f in tri.faces:
        nw = (R3 @ f.normal).normalized(); w = f.calc_area() * max(0.0, nw.z + 0.3)
        if w <= 0: continue
        pool.append(([v.co.copy() for v in f.verts], f.normal.copy())); tot += w; cum.append(tot)
    tri.free()
    import bisect

    def sample(rad):
        for _ in range(30):
            i = bisect.bisect_left(cum, R.random() * tot); vs, nl = pool[min(i, len(pool) - 1)]
            a, b = R.random(), R.random()
            if a + b > 1: a, b = 1 - a, 1 - b
            p = vs[0] + (vs[1] - vs[0]) * a + (vs[2] - vs[0]) * b
            pw = Mw @ p
            if pw.z < seabed_z(pw.x, pw.y) + 0.3 + rad * 0.5: continue
            if keep_out and keep_out(p, rad): continue
            hit = tree.ray_cast(p - nl * 0.02, -nl, 0.5)                                # not on a thin edge
            if hit[0] is not None and (hit[0] - p).length < 0.25: continue
            t1 = nl.orthogonal().normalized(); t2 = nl.cross(t1); ok = True
            for k in range(4):                                                         # the base must rest on the surface
                c = p + (t1 * math.cos(k * 1.571) + t2 * math.sin(k * 1.571)) * rad + nl * 0.3
                h = tree.ray_cast(c, -nl, 0.6)
                if h[0] is None or (h[0] - c).length > 0.42: ok = False; break
            if ok: return p, nl
        return None, None
    bm = newbm('kind', 'tint', 'cav', 'sw', 'ph', 'zz'); cav_all = set()

    def frame(p, nl, sink):
        q = Vector((0, 0, 1)).rotation_difference(nl) @ Quaternion((0, 0, 1), R.uniform(0, math.tau))
        return Matrix.Translation(p - nl * sink) @ q.to_matrix().to_4x4()
    clusters = []
    for i in range(n_barn):
        if clusters and R.random() < 0.75:
            cp, cn = R.choice(clusters); off = cn.orthogonal().normalized(); off = Quaternion(cn, R.uniform(0, math.tau)) @ off
            hit = tree.find_nearest(cp + off * R.uniform(0.2, 0.9))
            if hit[0] is None: continue
            p, nl = hit[0], hit[1]
            if keep_out and keep_out(p, 0.3): continue
            pw = Mw @ p
            if pw.z < seabed_z(pw.x, pw.y) + 0.3: continue
        else:
            p, nl = sample(0.25)
            if p is None: continue
            clusters.append((p, nl))
        s = R.uniform(0.07, 0.22)
        vs, cv = _barnacle(bm, frame(p, nl, 0.02 * s), s, R)
        cav_all.update(cv)
        setl(bm, vs, kind=0.0, tint=R.random(), sw=0.0)
    for i in range(n_sponge):
        s = R.uniform(0.22, 0.6); p, nl = sample(s * 0.6)
        if p is None: continue
        vs, cv = _sponge(bm, frame(p, nl, 0.05 * s), s, R)
        cav_all.update(cv); setl(bm, vs, kind=1.0, tint=R.random(), sw=0.0)
    for i in range(n_tuft):
        p, nl = sample(0.15)
        if p is None: continue
        tv = _tuft(bm, p - nl * 0.03, nl, R, R.uniform(0.4, 1.3))
        ph = R.uniform(0, math.tau); tt = R.random()
        setl(bm, [v for v, h, k in tv], kind=2.0, tint=tt, ph=ph)
        lay = bm.verts.layers.float.get('sw'); lz = bm.verts.layers.float.get('zz')
        for v, h, k in tv: v[lay] = 0.18 * h; v[lz] = h
    setl(bm, list(cav_all), cav=1.0)
    for k in ('kind', 'tint', 'cav', 'sw', 'ph', 'zz'):
        if bm.verts.layers.float.get(k) is None: bm.verts.layers.float.new(k)
    o = mkobj(name, bm, mat, coll, kind, smooth=False)
    o.matrix_world = Mw; o.parent = target; o.matrix_parent_inverse = Mw.inverted()
    return o


# ------------------------------------------------------------------------------------------------------------------ sway (seaT -> geometry nodes)
def sway_group():
    """Offset by per-vertex attributes: sw (sway amplitude, m), fl (flutter, m), ph (phase), zz (height along the plant).
    T is driven by the scene's seaT and stepped on threes, so plants move like the drawn FX."""
    ng = D.node_groups.get('UNDER_sway')
    if ng is not None: return ng
    ng = D.node_groups.new('UNDER_sway', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('T', in_out='INPUT', socket_type='NodeSocketFloat')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput'); sp = N.new('GeometryNodeSetPosition')

    def at(name):
        n = N.new('GeometryNodeInputNamedAttribute'); n.data_type = 'FLOAT'; n.inputs['Name'].default_value = name; return n.outputs['Attribute']

    def m(op, a, b=None):
        n = N.new('ShaderNodeMath'); n.operation = op
        for i, x in enumerate((a, b)):
            if x is None: continue
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: L.new(x, n.inputs[i])
        return n.outputs[0]
    t = m('DIVIDE', m('FLOOR', m('MULTIPLY', gi.outputs['T'], 8.0)), 8.0)
    sw, ph, zz, fl = at('sw'), at('ph'), at('zz'), at('fl')
    a1 = m('ADD', m('MULTIPLY', t, 1.05), m('SUBTRACT', ph, m('MULTIPLY', zz, 0.16)))
    a2 = m('ADD', m('MULTIPLY', t, 2.6), m('SUBTRACT', m('MULTIPLY', ph, 1.7), m('MULTIPLY', zz, 0.6)))
    a3 = m('ADD', m('MULTIPLY', t, 0.83), m('SUBTRACT', m('MULTIPLY', ph, 1.3), m('MULTIPLY', zz, 0.12)))
    a4 = m('ADD', m('MULTIPLY', t, 3.1), m('ADD', ph, m('MULTIPLY', zz, 0.9)))
    ox = m('ADD', m('MULTIPLY', m('SINE', a1), sw), m('MULTIPLY', m('SINE', a2), fl))
    oy = m('ADD', m('MULTIPLY', m('COSINE', a3), m('MULTIPLY', sw, 0.6)), m('MULTIPLY', m('COSINE', a4), fl))
    oz = m('MULTIPLY', m('ABSOLUTE', m('SINE', a1)), m('MULTIPLY', sw, -0.1))
    cx = N.new('ShaderNodeCombineXYZ'); L.new(ox, cx.inputs[0]); L.new(oy, cx.inputs[1]); L.new(oz, cx.inputs[2])
    L.new(gi.outputs['Geometry'], sp.inputs['Geometry']); L.new(cx.outputs[0], sp.inputs['Offset']); L.new(sp.outputs[0], go.inputs[0])
    return ng


def _drive_input(md, name, path='["seaT"]', index=-1, idt='SCENE', idb=None):
    ng = md.node_group
    ident = next(it.identifier for it in ng.interface.items_tree if getattr(it, 'in_out', '') == 'INPUT' and it.name == name)
    sock = getattr(md.properties.inputs, ident)
    fc = sock.driver_add('value', index) if index >= 0 else sock.driver_add('value')
    d = fc.driver; d.type = 'AVERAGE'
    v = d.variables.new(); v.type = 'SINGLE_PROP'; v.targets[0].id_type = idt; v.targets[0].id = idb or bpy.context.scene; v.targets[0].data_path = path
    return fc


def add_sway(o):
    md = o.modifiers.new('UNDER_sway', 'NODES'); md.node_group = sway_group()
    _drive_input(md, 'T')
    return md


# ------------------------------------------------------------------------------------------------------------------ coral
CORAL_MESHES = {}


def _mesh(name, bm, mat, smooth=True):
    clean(bm)
    me = D.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth: me.shade_smooth()
    me.materials.append(mat); return me


def coral_meshes(M):
    if CORAL_MESHES and all(m.name in D.meshes for m in CORAL_MESHES.values()): return CORAL_MESHES
    CORAL_MESHES.clear(); R = random.Random(41)
    b = bmesh.new(); bmesh.ops.create_icosphere(b, subdivisions=3, radius=1.0)               # brain dome
    for v in b.verts:
        p = v.co.normalized(); r = 1.0 + 0.07 * MN.noise(p * 2.5 + Vector((2, 3, 4)))
        z = p.z if p.z > -0.25 else -0.25 + (p.z + 0.25) * 0.15
        v.co = Vector((p.x * r, p.y * r, (z + 0.1) * 0.6 * r))
    CORAL_MESHES['brain'] = _mesh('UNDER_coral_brain', b, M['coral_brain'])
    b = newbm('tip')                                                                            # staghorn

    def branch(p, d, L, r, lvl, tip0):
        n = 3; pts = []; q = p.copy()
        for i in range(n + 1):
            pts.append(q.copy()); d = (d + Vector((R.uniform(-0.3, 0.3), R.uniform(-0.3, 0.3), 0.12))).normalized(); q = q + d * (L / n)
        rr = [max(0.014, r * (1.0 - 0.45 * i / n)) for i in range(n + 1)]
        vv = tube(b, pts, rr, seg=5, cap0=True, cap1=True)
        for i, ring in enumerate(vv): setl(b, ring, tip=min(1.0, tip0 + (1.0 - tip0) * (i / n) * (1.0 if lvl == 2 else 0.35)))
        if lvl < 2:
            for k in range(2):
                j = R.randint(1, n)
                nd = (d + Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(0.2, 0.9)))).normalized()
                branch(pts[j], nd, L * R.uniform(0.6, 0.8), rr[j] * 0.85, lvl + 1, min(0.9, tip0 + 0.3))
    for k in range(5):
        a = k / 5 * math.tau + R.uniform(-0.3, 0.3)
        branch(Vector((0.0, 0.0, -0.08)), Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 1.0)).normalized(), R.uniform(0.42, 0.56), 0.075, 0, 0.0)
    CORAL_MESHES['branch'] = _mesh('UNDER_coral_branch', b, M['coral_branch'])
    b = bmesh.new()                                                                             # table
    vv = revolve(b, [(0.0, 0.64), (0.5, 0.66), (0.9, 0.72), (1.0, 0.74), (1.03, 0.7), (0.96, 0.66), (0.5, 0.6), (0.16, 0.57), (0.13, 0.0), (0.18, -0.08), (0.0, -0.08)], 22)
    for ring in vv:
        for v in ring:
            r = math.hypot(v.co.x, v.co.y)
            if r > 0.6:
                a = math.atan2(v.co.y, v.co.x); k = 1.0 + 0.09 * math.sin(9 * a) * (r - 0.6) / 0.4
                v.co.x *= k; v.co.y *= k
    CORAL_MESHES['table'] = _mesh('UNDER_coral_table', b, M['coral_table'])
    b = bmesh.new(); rows = []                                                                  # sea fan
    for j in range(7):
        v = j / 6; row = []
        for i in range(13):
            u = i / 12; a = (u - 0.5) * 2.3; r = 0.12 + v * (0.85 + 0.12 * math.sin(u * 17) + 0.06 * math.sin(u * 37))
            row.append(Vector((math.sin(a) * r, 0.05 * math.sin(u * 9 + v * 4) + 0.08 * v * v, math.cos(a) * r * 0.95 - 0.05)))
        rows.append(row)
    bridge(b, rows, False, False)
    tube(b, [Vector((0, 0, -0.1)), Vector((0, 0, 0.14))], 0.05, seg=5)
    CORAL_MESHES['fan'] = _mesh('UNDER_coral_fan', b, M['coral_fan'])
    b = newbm('cav', 'tip')                                                                     # tube cluster
    for k in range(7):
        a = R.uniform(0, math.tau); d = R.uniform(0.0, 0.3); h = R.uniform(0.35, 0.9); w = R.uniform(0.06, 0.11)
        T = Matrix.Translation((math.cos(a) * d, math.sin(a) * d, -0.06)) @ Euler((R.uniform(-0.25, 0.25), R.uniform(-0.25, 0.25), 0.0)).to_matrix().to_4x4()
        vv = revolve(b, [(0.0, 0.0), (w * 1.25, 0.0), (w, h), (w * 0.72, h), (w * 0.7, h * 0.75), (0.0, h * 0.7)], 8, M=T)
        setl(b, flat_verts(vv[3:]), cav=1.0); setl(b, vv[2] + vv[3], tip=1.0)
    CORAL_MESHES['tube'] = _mesh('UNDER_coral_tube', b, M['coral_tube'])
    for k in ('brain', 'table', 'fan', 'tube', 'branch'):
        me = CORAL_MESHES[k]
        for a in ('tip', 'cav'):
            if a not in me.attributes: me.attributes.new(a, 'FLOAT', 'POINT')
    return CORAL_MESHES


CORAL_SIZE = {'brain': (0.7, 2.3), 'branch': (0.9, 2.0), 'table': (0.9, 2.4), 'fan': (0.9, 2.1), 'tube': (0.6, 1.5)}
CORAL_R = {'brain': 1.1, 'branch': 0.85, 'table': 1.15, 'fan': 1.02, 'tube': 0.5}     # footprint radius / size


def scatter_corals(coll, M, space, patches, seed=23, name='UNDER_coral', kind='coral'):
    R = random.Random(seed); CM = coral_meshes(M); out = []
    kinds = ['brain', 'brain', 'branch', 'branch', 'table', 'fan', 'tube', 'tube']
    for (cx, cy, rad, cnt) in patches:
        placed = 0; tries = 0
        while placed < cnt and tries < cnt * 12:
            tries += 1
            a = R.uniform(0, math.tau); d = rad * math.sqrt(R.random()); x = cx + math.cos(a) * d; y = cy + math.sin(a) * d
            k = R.choice(kinds); s = R.uniform(*CORAL_SIZE[k]); z = seabed_z(x, y)
            rr = s * CORAL_R[k]
            if not space.free((x, y, z + s * 0.3), rr, 0.12): continue
            o = D.objects.new(name, CM[k]); coll.objects.link(o)
            o.scale = (s, s, s)
            place_on_bed(o, x, y, 0.07 * s + 0.06, R.uniform(0, math.tau), 0.85)
            o['tint'] = R.random(); o['uw_kind'] = kind
            space.add((x, y, z + s * 0.3), rr); out.append(o); placed += 1
    return out


def corals_on(target, bm_local, coll, M, n=14, seed=9, keep_out=None, name='UNDER_anchor_coral', kind='acoral'):
    """Coral heads growing on the anchor's upper faces: separate linked duplicates parented to it, bases resting on the iron."""
    R = random.Random(seed); CM = coral_meshes(M); Mw = target.matrix_world.copy(); R3 = Mw.to_3x3(); out = []
    tri = bm_local.copy(); bmesh.ops.triangulate(tri, faces=tri.faces[:]); tree = BVHTree.FromBMesh(tri)
    faces = [(f.calc_area(), [v.co.copy() for v in f.verts], f.normal.copy()) for f in tri.faces if (R3 @ f.normal).normalized().z > 0.55]
    tri.free(); placed = []
    tries = 0
    while len(out) < n and tries < n * 40:
        tries += 1
        ar, vs, nl = R.choices(faces, weights=[f[0] for f in faces])[0]
        a, b = R.random(), R.random()
        if a + b > 1: a, b = 1 - a, 1 - b
        p = vs[0] + (vs[1] - vs[0]) * a + (vs[2] - vs[0]) * b
        k = R.choice(['brain', 'brain', 'branch', 'tube', 'table']); s = R.uniform(0.5, 1.3) * (0.8 if k == 'table' else 1.0)
        pw = Mw @ p
        if pw.z < seabed_z(pw.x, pw.y) + 0.4 + s * 0.5 or (keep_out and keep_out(p, s * 1.1)): continue
        if any((p - q).length < (s + sq) * 0.75 for q, sq in placed): continue
        t1 = nl.orthogonal().normalized(); t2 = nl.cross(t1); ok = True
        rr = s * (0.75 if k in ('brain', 'table') else 0.45)
        for j in range(6):
            c = p + (t1 * math.cos(j * 1.047) + t2 * math.sin(j * 1.047)) * rr + nl * 0.4
            h = tree.ray_cast(c, -nl, 0.9)
            if h[0] is None or (h[0] - c).length > 0.5: ok = False; break
        if not ok: continue
        o = D.objects.new(name, CM[k]); coll.objects.link(o)
        q = Vector((0, 0, 1)).rotation_difference(nl) @ Quaternion((0, 0, 1), R.uniform(0, math.tau))
        loc = Matrix.Translation(p - nl * (0.05 * s + 0.03)) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((s, s, s, 1.0))
        o.matrix_world = Mw @ loc
        o.parent = target; o.matrix_parent_inverse = Mw.inverted()
        o['tint'] = R.random(); o['uw_kind'] = kind
        placed.append((p, s)); out.append(o)
    return out


# ------------------------------------------------------------------------------------------------------------------ kelp and sea grass
KELP_ZONES = [(-150.0, 292.0, 44.0, 150), (-56.0, 302.0, 40.0, 130), (-6.0, 248.0, 22.0, 34), (-132.0, 194.0, 13.0, 14), (-66.0, 190.0, 11.0, 10)]


def kelp_plant(bm, root, H, R, tint, acc):
    """Ribbon kelp: 2-4 broad fronds from one holdfast, rising with a slow twist and a wandering line, ruffled edges.
    acc gets (vert, sw, fl, ph, zz, tint, u, stem) per vertex for the sway nodes and the shader."""
    ph0 = R.uniform(0, math.tau); amp = 0.12 * H; top = root
    for f in range(R.randint(2, 4)):
        Hf = H * R.uniform(0.6, 1.0); ph = ph0 + f * 1.9; la = ph0 + f * 2.1
        lean = Vector((math.cos(la), math.sin(la), 0.0)) * R.uniform(0.04, 0.12)
        n = max(10, int(Hf / 0.7)); W = R.uniform(0.34, 0.62); tw = R.uniform(1.5, 3.5); rows = []
        for i in range(n + 1):
            v = i / n; h = Hf * v
            c = root + Vector((0.0, 0.0, h)) + lean * (h * (0.4 + 0.9 * v)) + Vector((math.sin(v * 3.1 + ph), math.cos(v * 2.6 + ph), 0.0)) * (1.5 * v * v + 0.3 * v)
            a = ph + v * tw; side = Vector((math.cos(a), math.sin(a), 0.0)); nrm = side.cross(UP)
            w = W * (0.25 + 0.75 * _S(v / 0.12)) * (1.0 - 0.85 * _S((v - 0.75) / 0.25)) + 0.02
            ruf = 0.07 * math.sin(v * 37.0 + f) * w / W
            rows.append([c - side * (w * 0.5) + nrm * ruf, c + nrm * 0.02, c + side * (w * 0.5) - nrm * ruf])
        bv = bridge(bm, rows, False, False)
        for i, row in enumerate(bv):
            h = Hf * i / n
            for mi, vtx in enumerate(row): acc.append((vtx, amp * (h / H) ** 1.3, 0.06 * (h / H) * abs(mi - 1), ph, h, tint, abs(mi - 1), 0.0))
        top = rows[-1][1]
    return top


def _apply_acc(bm, acc):
    names = ('sw', 'fl', 'ph', 'zz', 'tint', 'u', 'stem')
    lays = [bm.verts.layers.float.get(n) for n in names]
    for rec in acc:
        v = rec[0]
        for lay, val in zip(lays, rec[1:]): v[lay] = val


def _zone_origin(o, cx, cy, rad):
    """Origin at the zone centre (the per-object ink cut measures from the origin) and prop inkr = the zone radius."""
    c0 = Vector((cx, cy, seabed_z(cx, cy)))
    o.data.transform(Matrix.Translation(-c0)); o.location = c0; o['inkr'] = float(rad)


def kelp_forests(coll, mat, space, seed=31, zones=None, cell=16.0):
    """Kelp in clumps (one object per ~cell x cell m of a zone, origin at the clump centre, prop inkr = its radius), so the
    per-object ink cut keeps lines on the near clumps only."""
    R = random.Random(seed); out = []
    for zi, (cx, cy, rad, cnt) in enumerate(zones or KELP_ZONES):
        clumps = {}; placed = 0; tries = 0; roots = []
        while placed < cnt and tries < cnt * 10:
            tries += 1
            a = R.uniform(0, math.tau); d = rad * math.sqrt(R.random()); x = cx + math.cos(a) * d; y = cy + math.sin(a) * d
            z = seabed_z(x, y); H = min(R.uniform(10.0, 24.0), -z - 3.5)
            if H < 6.0: continue
            if not space.free((x, y, z + 0.8), 1.0, 0.4): continue
            if any(math.hypot(x - rx, y - ry) < 1.6 for rx, ry in roots): continue
            key = (int(math.floor((x - cx) / cell)), int(math.floor((y - cy) / cell)))
            if key not in clumps: clumps[key] = (newbm(*ACC), [], [])
            bm, acc, pts = clumps[key]
            kelp_plant(bm, Vector((x, y, z - 0.35)), H + 0.35, R, R.random(), acc)
            hb = bmesh.new(); bmesh.ops.create_icosphere(hb, subdivisions=1, radius=0.55)
            for v in hb.verts: v.co.z *= 0.45; v.co.x *= R.uniform(0.8, 1.3)
            hv = append(bm, hb, Matrix.Translation((x, y, z - 0.08)))
            for v in hv: acc.append((v, 0.0, 0.0, 0.0, 0.0, 0.3, 0.0, 1.0))
            roots.append((x, y)); pts.append((x, y)); space.add((x, y, z), 1.3); placed += 1
        for ci, key in enumerate(sorted(clumps)):
            bm, acc, pts = clumps[key]
            _apply_acc(bm, acc)
            o = mkobj('UNDER_kelp_%d_%02d' % (zi, ci), bm, mat, coll, 'kelp', smooth=True)
            mx = sum(p[0] for p in pts) / len(pts); my = sum(p[1] for p in pts) / len(pts)
            _zone_origin(o, mx, my, max(math.hypot(p[0] - mx, p[1] - my) for p in pts) + 3.0)
            add_sway(o); out.append(o)
    return out


GRASS_ZONES = [(-150.0, 330.0, 70.0, 520), (-40.0, 335.0, 60.0, 420), (-100.0, 236.0, 40.0, 180), (-20.0, 215.0, 26.0, 90), (-170.0, 222.0, 26.0, 90)]


def grass_meadows(coll, mat, space, seed=37, zones=None):
    R = random.Random(seed); out = []
    for zi, (cx, cy, rad, cnt) in enumerate(zones or GRASS_ZONES):
        bm = newbm(*ACC); acc = []; placed = 0; tries = 0
        while placed < cnt and tries < cnt * 6:
            tries += 1
            a = R.uniform(0, math.tau); d = rad * math.sqrt(R.random()); x = cx + math.cos(a) * d; y = cy + math.sin(a) * d
            if MN.noise(Vector((x * 0.045, y * 0.045, 5.0))) < -0.05: continue
            if y > 396.0: continue
            z = seabed_z(x, y)
            if not space.free((x, y, z + 0.3), 0.45, 0.05): continue
            n = seabed_normal(x, y); ph = R.uniform(0, math.tau); tt = R.random()
            for v, h, k in _tuft(bm, Vector((x, y, z - 0.08)), (n + UP).normalized(), R, R.uniform(0.6, 1.5)):
                acc.append((v, 0.16 * h, 0.0, ph + k * 0.3, h, tt, 0.0, 0.0))
            placed += 1
        if not acc: bm.free(); continue
        _apply_acc(bm, acc)
        o = mkobj('UNDER_grass_%d' % zi, bm, mat, coll, 'grass', smooth=True)
        _zone_origin(o, cx, cy, rad)
        add_sway(o); out.append(o)
    return out


# ------------------------------------------------------------------------------------------------------------------ the sunken boat
BOAT_XY = (-57.0, 192.0); BOAT_YAW = math.radians(58.0); BOAT_PITCH = math.radians(5.0); BOAT_HEEL = math.radians(-38.0)
BOAT_TH = 0.11; BOAT_NS = 48; BOAT_NV = 14


def boat_station(u):
    """Half-breadth at the gunwale, keel z, gunwale z and section exponent at u = -1 (transom) .. 1 (stem). Bow is +X, port +Y."""
    w = 1.85 * max(0.0, 1.0 - u ** 2.4) ** 0.6 if u > 0 else 1.85 * (1.0 - 0.25 * u * u)
    zk = 0.25 + 1.1 * max(0.0, u - 0.55) ** 2 / 0.2025 + 0.35 * max(0.0, -u - 0.6) / 0.4
    zg = 1.75 + 0.55 * max(0.0, u) ** 2 + (0.25 * u * u if u < 0 else 0.0)
    return max(w, 0.07), zk, zg, 2.2 - 0.95 * max(0.0, u) ** 1.5


def boat_section(u, n=BOAT_NV):
    """(y, z) from the port gunwale over the keel to the starboard gunwale (2n + 1 points, superellipse quadrants)."""
    w, zk, zg, p = boat_station(u); e = 2.0 / p; out = []
    for j in range(2 * n + 1):
        th = math.pi / 2 * abs(n - j) / n; s = 1.0 if j < n else -1.0
        out.append((s * w * math.sin(th) ** e, zg - (zg - zk) * math.cos(th) ** e))
    return out


def _boat_hole(seed=77):
    """Broken planks on the starboard bilge, forward: per strake an x-range (jagged plank ends)."""
    R = random.Random(seed); rows = {}; n = BOAT_NV
    for j in range(n + 3, n + 13):
        dj = (j + 0.5 - (n + 7.6)) / 4.6
        if abs(dj) >= 1.0: continue
        half = 1.55 * math.sqrt(1.0 - dj * dj) * R.uniform(0.6, 1.25); off = R.uniform(-0.3, 0.3)
        rows[j] = (2.0 + off - half, 2.0 + off + half)
    return rows


def boat_hull_bm():
    bm = bmesh.new(); hole = _boat_hole(); rings = []
    for i in range(BOAT_NS + 1):
        x = -6.0 + 12.0 * i / BOAT_NS
        rings.append([bm.verts.new((x, y, z)) for y, z in boat_section(x / 6.0)])
    for i in range(BOAT_NS):
        xm = -6.0 + 12.0 * (i + 0.5) / BOAT_NS
        for j in range(2 * BOAT_NV):
            h = hole.get(j)
            if h and h[0] < xm < h[1]: continue
            bm.faces.new((rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]))
    bm.faces.new(list(rings[0]))                                                                   # transom
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.normal_update()
    f = next(f for f in bm.faces if len(f.verts) == 4 and abs(f.calc_center_median().x) < 0.4 and abs(f.calc_center_median().y) < 0.3)
    if f.normal.z > 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:]); bm.normal_update()      # outward
    return bm, hole


def _rib_pts(x, inset):
    sec = boat_section(x / 6.0); out = []
    for j, (y, z) in enumerate(sec):
        a = sec[max(j - 1, 0)]; b = sec[min(j + 1, len(sec) - 1)]
        ty, tz = b[0] - a[0], b[1] - a[1]; L = math.hypot(ty, tz) or 1.0
        ny, nz = tz / L, -ty / L                                     # normal of the curve (port->keel->starboard): points inward
        out.append(Vector((x, y + ny * inset, z + nz * inset)))
    return out


def boat_parts_bm(hole, seed=78):
    R = random.Random(seed); bm = bmesh.new()
    keel = [Vector((x, 0.0, boat_station(x / 6.0)[1] - 0.1)) for x in [-6.0 + 11.9 * k / 30 for k in range(31)]]
    keel += [Vector((6.02, 0.0, 1.8)), Vector((6.05, 0.0, 2.2)), Vector((6.08, 0.0, 2.48))]
    tube(bm, keel, [0.15] * 25 + [0.13] * 6 + [0.11] * 3, seg=6)                                     # keel and stem
    for s in (1.0, -1.0):                                                                           # gunwale rails
        pts = []
        for k in range(33):
            x = -6.0 + 12.0 * k / 32; w, zk, zg, p = boat_station(x / 6.0); pts.append(Vector((x, s * (w - 0.03), zg + 0.04)))
        tube(bm, pts, 0.08, seg=6)
    x = -5.3
    while x < 4.8:                                                                                  # ribs, broken over the hole
        pts = _rib_pts(x, BOAT_TH + 0.045); seg_ = []
        for j, p in enumerate(pts):
            hs = [hole.get(j), hole.get(j - 1)]
            if any(h and h[0] - 0.05 < x < h[1] + 0.05 for h in hs):
                if len(seg_) > 1: tube(bm, seg_, 0.075, seg=4, a0=math.pi / 4)
                seg_ = []
            else: seg_.append(p)
        if len(seg_) > 1: tube(bm, seg_, 0.075, seg=4, a0=math.pi / 4)
        x += 0.75
    for xt in (-3.4, -0.8, 1.8):                                                                   # thwarts
        w, zk, zg, p = boat_station(xt / 6.0); zt = zg - 0.42; t = (zt - zk) / (zg - zk)
        th = math.acos(max(0.0, 1.0 - t) ** (p / 2.0)); y = w * math.sin(th) ** (2.0 / p) - BOAT_TH + 0.03
        rbox(bm, 0.17, y, 0.045, p=8.0, cuts=3, M=Matrix.Translation((xt, 0.0, zt)))
    mz = [0.3 + 4.1 * k / 7 for k in range(8)]                                                     # mast stub, snapped
    vv = tube(bm, [Vector((1.8, 0.0, z)) for z in mz], [0.16 - 0.03 * k / 7 for k in range(8)], seg=10, cap1=False)
    top = vv[-1]; c = Vector((1.8, 0.0, mz[-1] - 0.15))
    for k, v in enumerate(top): v.co.z += 0.32 * math.sin(k * 2.1 + 0.4) + R.uniform(-0.12, 0.12)
    cv = bm.verts.new(c)
    for k in range(len(top)):
        try: bm.faces.new((top[k], top[(k + 1) % len(top)], cv))
        except ValueError: pass
    rbox(bm, 0.05, 0.36, 0.56, p=6.0, cuts=3, M=Matrix.Translation((-6.24, 0.0, 0.95)))          # rudder
    tube(bm, [Vector((-6.14, 0.0, 0.42)), Vector((-6.14, 0.0, 2.05))], 0.065, seg=8)
    tube(bm, [Vector((-6.14, 0.0, 2.02)), Vector((-5.4, 0.0, 2.1)), Vector((-4.85, 0.0, 2.22))], 0.05, seg=6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def boat_matrix(dz=0.0):
    x, y = BOAT_XY
    return (Matrix.Translation((x, y, seabed_z(x, y) + dz)) @ Matrix.Rotation(BOAT_YAW, 4, 'Z') @ Matrix.Rotation(BOAT_PITCH, 4, 'Y')
            @ Matrix.Rotation(BOAT_HEEL, 4, 'X'))


def boat(coll, M, space=None, buried=0.24):
    hb, hole = boat_hull_bm(); keep = hb.copy()
    M0 = boat_matrix(0.0)
    dz = sorted(seabed_z((M0 @ v.co).x, (M0 @ v.co).y) - (M0 @ v.co).z for v in hb.verts)
    dzv = dz[min(len(dz) - 1, int(len(dz) * (1.0 - buried)))]
    Mb = boat_matrix(dzv)
    o = mkobj('UNDER_boat', hb, M['wood'], coll, 'boat', smooth=True, sharp=50.0, M=Mb)
    md = o.modifiers.new('UNDER_solid', 'SOLIDIFY'); md.thickness = BOAT_TH; md.offset = -1.0
    for k, v in (('use_even_offset', True), ('use_rim', True), ('use_quality_normals', True)):
        try: setattr(md, k, v)
        except Exception: pass
    pb = boat_parts_bm(hole); pkeep = pb.copy()
    parts = mkobj('UNDER_boat_parts', pb, M['wood'], coll, 'boat', smooth=True, sharp=45.0, M=Mb.copy())
    parts.parent = o; parts.matrix_parent_inverse = Mb.inverted()
    if space is not None:
        w = keep.copy(); w.transform(Mb); pkeep.transform(Mb)
        both = bmesh.new(); append(both, w); append(both, pkeep)
        space.add_tree(BVHTree.FromBMesh(both), 0.15); both.free()
    else: pkeep.free()
    return o, parts, keep


def boat_debris(coll, M, space, seed=79, n=5):
    """A few loose planks lying on the sand by the wreck."""
    R = random.Random(seed); out = []; tries = 0
    me = D.meshes.get('UNDER_plank')
    if me is None:
        b = bmesh.new(); rbox(b, 1.0, 0.11, 0.035, p=8.0, cuts=3)
        for v in b.verts:
            if v.co.x > 0.7: v.co.z += 0.02 * math.sin(v.co.y * 40.0); v.co.x += 0.12 * math.sin(v.co.y * 23.0 + 1.0)
        me = _mesh('UNDER_plank', b, M['wood'])
    while len(out) < n and tries < 200:
        tries += 1
        a = R.uniform(0, math.tau); d = R.uniform(5.5, 11.0)
        x = BOAT_XY[0] + math.cos(a) * d; y = BOAT_XY[1] + math.sin(a) * d; L = R.uniform(0.8, 1.3)
        if not space.free((x, y, seabed_z(x, y) + 0.1), L * 1.2, 0.2): continue
        o = D.objects.new('UNDER_plank', me); coll.objects.link(o); o.scale = (L, 1.0, 1.0)
        place_on_bed(o, x, y, -0.015, R.uniform(0, math.tau), 1.0)
        o['uw_kind'] = 'debris'; space.add((x, y, seabed_z(x, y) + 0.1), L * 1.2); out.append(o)
    return out


# ------------------------------------------------------------------------------------------------------------------ fish
FISH = {   # body half-height / half-width / back hump / tail fin / dorsal fin (unit length, nose +X), material, size (m), cruise speed (m/s)
    'sardine': dict(h=0.085, w=0.05, hump=0.006, tail=0.12, dorsal=0.05, mat='fish_sardine', size=(0.6, 0.8), speed=2.6),
    'snapper': dict(h=0.15, w=0.066, hump=0.02, tail=0.15, dorsal=0.09, mat='fish_snapper', size=(0.6, 0.9), speed=1.7),
    'tang': dict(h=0.27, w=0.055, hump=0.035, tail=0.14, dorsal=0.11, mat='fish_tang', size=(0.4, 0.55), speed=1.2),
    'grouper': dict(h=0.16, w=0.11, hump=0.025, tail=0.13, dorsal=0.07, mat='fish_grouper', size=(1.3, 1.8), speed=0.8),
}
FISH_MESHES = {}
_MATS = {}


def mats():
    """The UNDER materials, made once per file (fish_school and friends work without calling build first)."""
    if not _MATS or any(m is None or m.name not in D.materials for m in _MATS.values()):
        _MATS.clear(); _MATS.update(materials())
    return _MATS


def _fish_body(P, x):
    t = (0.5 - x) / 0.9
    prof = math.sin(min(1.0, (0.5 - x) / 0.24) * math.pi / 2) ** 0.7
    taper = 1.0 - 0.82 * _S((t - 0.45) / 0.55)
    return P['h'] * prof * taper + 0.004, P['w'] * prof * taper + 0.003, P['hump'] * math.sin(min(1.0, t) * math.pi)


def fish_mesh(sp):
    me = FISH_MESHES.get(sp)
    if me is not None and me.name in D.meshes: return me
    P = FISH[sp]; b = bmesh.new(); seg = 10; rings = []
    for x in (0.5, 0.485, 0.45, 0.39, 0.3, 0.18, 0.05, -0.08, -0.2, -0.29, -0.35, -0.395):
        hh, ww, zc = _fish_body(P, x)
        rings.append([Vector((x, ww * math.cos(math.tau * k / seg), zc + hh * math.sin(math.tau * k / seg))) for k in range(seg)])
    bridge(b, rings, True, False, True, True)
    tl = P['tail']; z0 = _fish_body(P, -0.395)[2]
    A = b.verts.new((-0.37, 0.0, z0 + 0.02)); B = b.verts.new((-0.535, 0.0, z0 + tl)); C = b.verts.new((-0.465, 0.0, z0))
    Dv = b.verts.new((-0.535, 0.0, z0 - tl)); E = b.verts.new((-0.37, 0.0, z0 - 0.02))
    for f in ((A, B, C), (A, C, E), (E, C, Dv)): b.faces.new(f)
    top = lambda x: (lambda r: r[2] + r[0])(_fish_body(P, x))
    b.faces.new((b.verts.new((0.12, 0.0, top(0.12) - 0.01)), b.verts.new((-0.03, 0.0, top(-0.03) + P['dorsal'])), b.verts.new((-0.16, 0.0, top(-0.16) - 0.01))))
    bot = lambda x: (lambda r: r[2] - r[0])(_fish_body(P, x))
    b.faces.new((b.verts.new((-0.12, 0.0, bot(-0.12) + 0.01)), b.verts.new((-0.24, 0.0, bot(-0.24) + 0.008)), b.verts.new((-0.2, 0.0, bot(-0.2) - P['dorsal'] * 0.55))))
    for s in (1.0, -1.0):                                                                     # pectoral fins
        hh, ww, zc = _fish_body(P, 0.22)
        b.faces.new((b.verts.new((0.24, s * (ww - 0.004), zc - hh * 0.3)), b.verts.new((0.16, s * (ww + 0.05), zc - hh * 0.55)), b.verts.new((0.18, s * (ww - 0.004), zc - hh * 0.45))))
    me = _mesh('UNDER_fish_' + sp, b, mats()[P['mat']]); FISH_MESHES[sp] = me
    return me


def fish_school(coll, center, radius, count, seed=0, species='sardine', size=None, thick=0.35, height=None, dirn=1.0):
    """A school as linked duplicates (one mesh per species): a ring of fish round `center` (radius = outer radius, thick = ring
    depth as a fraction of it, height = vertical spread). Per-fish orbit stored in props sch_*; animate with animate_school."""
    R = random.Random(seed); c = Vector(center); me = fish_mesh(species); P = FISH[species]
    lo, hi = size or P['size']; Hh = radius * 0.3 if height is None else height; out = []
    for i in range(count):
        o = D.objects.new('UNDER_fish_' + species, me); coll.objects.link(o)
        s = R.uniform(lo, hi); o.scale = (s, s, s)
        o['sch_c'] = tuple(c); o['sch_r'] = radius * (1.0 - thick * R.random() ** 0.8); o['sch_h'] = R.uniform(-0.5, 0.5) * Hh
        o['sch_ph'] = R.uniform(0.0, math.tau); o['sch_sp'] = P['speed'] * R.uniform(0.85, 1.15); o['sch_bob'] = R.uniform(0.08, 0.35)
        o['sch_dir'] = dirn; o['uw_kind'] = 'fish'
        p, hd = _fish_pose(o, 0.0); _orient(o, p, hd, -0.35 * dirn)
        out.append(o)
    return out


def _fish_pose(o, t):
    c = Vector(o['sch_c']); r = o['sch_r']; dn = o.get('sch_dir', 1.0); ph0 = o['sch_ph']
    ph = ph0 + dn * o['sch_sp'] * t / max(r, 0.5)
    bob = o['sch_bob'] * math.sin(t * 1.3 + ph0 * 3.0); vz = o['sch_bob'] * 1.3 * math.cos(t * 1.3 + ph0 * 3.0)
    p = c + Vector((math.cos(ph) * r, math.sin(ph) * r, o['sch_h'] + bob))
    return p, Vector((-math.sin(ph) * dn * o['sch_sp'], math.cos(ph) * dn * o['sch_sp'], vz)).normalized()


def _orient(o, p, hd, roll=0.0, wig=0.0):
    o.rotation_mode = 'XYZ'
    o.rotation_euler = (roll, -math.asin(max(-1.0, min(1.0, hd.z))), math.atan2(hd.y, hd.x) + wig)
    o.location = p


def animate_school(objs, f0, f1, mode='circle', flee_from=None, flee_frame=None, lead=0.0, step=2, accel=14.0, vmax=10.0, scatter=0.35, seed=0):
    """Key a school on twos (constant interpolation, the drawn look). circle: orbit round the school centre with a bob and a
    tail wiggle. flee: orbit until flee_frame, then every fish snaps away from flee_from and accelerates to vmax (m/s);
    lead = seconds of fleeing already done at flee_frame."""
    import stage as ST
    fps = bpy.context.scene.render.fps or 24; R = random.Random(seed)
    frames = list(range(f0, f1 + 1, step))
    if frames[-1] != f1: frames.append(f1)
    for o in objs:
        dn = o.get('sch_dir', 1.0); fl = None
        for f in frames:
            t = (f - f0) / fps
            if mode == 'flee' and flee_frame is not None and f >= flee_frame:
                if fl is None:
                    p0, _ = _fish_pose(o, (flee_frame - f0) / fps)
                    aw = p0 - Vector(flee_from if flee_from is not None else o['sch_c']); aw.z *= 0.6
                    d = (aw.normalized() + Vector((R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(-0.3, 0.8))) * scatter).normalized()
                    d.z = max(d.z, 0.05); fl = (p0, d.normalized(), o['sch_sp'])
                p0, d, v0 = fl; tt = lead + (f - flee_frame) / fps
                ta = max(0.0, (vmax - v0) / accel); t1 = min(tt, ta)
                p = p0 + d * (v0 * t1 + 0.5 * accel * t1 * t1 + max(0.0, tt - ta) * vmax)
                _orient(o, p, d, 0.0, 0.16 * math.sin(f * 2.9 + o['sch_ph'] * 5.0))
            else:
                p, hd = _fish_pose(o, t)
                _orient(o, p, hd, -0.35 * dn, 0.09 * math.sin(f * 2.2 + o['sch_ph'] * 5.0))
            o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
        ST.set_interp(o, 'CONSTANT')
    return objs


def school_z(cx, cy, r, clear, height=0.0):
    """Centre height for a school of radius r that keeps `clear` metres over the highest seabed under its ring."""
    zs = [seabed_z(cx + rr * math.cos(a), cy + rr * math.sin(a)) for rr in (0.0, r * 0.5, r * 1.1) for a in [k * math.tau / 16 for k in range(16)]]
    return max(zs) + clear + height * 0.5


def default_schools(coll):
    """Sardines circling the chain above the shackle, snappers in the kelp, tangs over the reef by the anchor, two groupers."""
    return {'chain': fish_school(coll, (BOW.x, BOW.y, -40.0), 12.0, 200, seed=3, species='sardine', thick=0.4, height=5.0),
            'kelp': fish_school(coll, (-60.0, 290.0, school_z(-60.0, 290.0, 13.0, 5.0, 4.0)), 13.0, 42, seed=4, species='snapper', thick=0.5, height=4.0, dirn=-1.0),
            'reef': fish_school(coll, (-74.0, 172.0, max(-50.0, school_z(-74.0, 172.0, 7.0, 6.0, 2.5))), 7.0, 20, seed=5, species='tang', thick=0.6, height=2.5),
            'grouper': fish_school(coll, (-72.0, 146.0, max(-55.0, school_z(-72.0, 146.0, 5.0, 4.0, 0.8))), 5.0, 2, seed=6, species='grouper', thick=0.2, height=0.8, dirn=-1.0)}


# ------------------------------------------------------------------------------------------------------------------ marine snow
def _gn_math(ng):
    N = ng.nodes; L = ng.links

    def m(op, a, b=None):
        n = N.new('ShaderNodeMath'); n.operation = op
        for i, x in enumerate((a, b)):
            if x is None: continue
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: L.new(x, n.inputs[i])
        return n.outputs[0]

    def vm(op, a, b=None, sc=None, out=0):
        n = N.new('ShaderNodeVectorMath'); n.operation = op
        for i, x in enumerate((a, b)):
            if x is None: continue
            if isinstance(x, (tuple, list)): n.inputs[i].default_value = x
            else: L.new(x, n.inputs[i])
        if sc is not None:
            if isinstance(sc, (int, float)): n.inputs['Scale'].default_value = sc
            else: L.new(sc, n.inputs['Scale'])
        return n.outputs[out]

    def vec(x, y, z):
        n = N.new('ShaderNodeCombineXYZ')
        for i, v in enumerate((x, y, z)):
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: L.new(v, n.inputs[i])
        return n.outputs[0]

    def at(name):
        n = N.new('GeometryNodeInputNamedAttribute'); n.data_type = 'FLOAT'; n.inputs['Name'].default_value = name; return n.outputs['Attribute']
    return m, vm, vec, at


def snow_group(mat):
    """Points kept in a box of side S round the camera (wrapped), drifting and sinking with T; none above the surface or
    closer than 1 m to the lens; each a tiny ico sphere scaled by the point attribute sz."""
    ng = D.node_groups.get('UNDER_snow')
    if ng is not None: return ng
    ng = D.node_groups.new('UNDER_snow', 'GeometryNodeTree'); I = ng.interface
    I.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    I.new_socket('T', in_out='INPUT', socket_type='NodeSocketFloat')
    I.new_socket('C', in_out='INPUT', socket_type='NodeSocketVector')
    s_ = I.new_socket('S', in_out='INPUT', socket_type='NodeSocketFloat'); s_.default_value = 26.0
    I.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links; m, vm, vec, at = _gn_math(ng)
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    T = gi.outputs['T']; C = gi.outputs['C']; S = gi.outputs['S']; ph = at('ph')
    pos = N.new('GeometryNodeInputPosition').outputs[0]
    drift = vec(m('ADD', m('MULTIPLY', m('SINE', m('ADD', m('MULTIPLY', T, 1.1), ph)), 0.18), m('MULTIPLY', T, 0.06)),
                m('ADD', m('MULTIPLY', m('COSINE', m('ADD', m('MULTIPLY', T, 0.9), m('MULTIPLY', ph, 1.7))), 0.18), m('MULTIPLY', T, 0.035)),
                m('ADD', m('MULTIPLY', m('SINE', m('ADD', m('MULTIPLY', T, 0.7), m('MULTIPLY', ph, 2.3))), 0.1), m('MULTIPLY', T, -0.09)))
    p = vm('ADD', vm('SCALE', pos, sc=S), drift)
    inv = m('DIVIDE', 1.0, S)
    q = vm('ADD', vm('SCALE', vm('SUBTRACT', vm('FRACTION', vm('ADD', vm('SCALE', vm('SUBTRACT', p, C), sc=inv), (0.5, 0.5, 0.5))), (0.5, 0.5, 0.5)), sc=S), C)
    sp = N.new('GeometryNodeSetPosition'); L.new(gi.outputs['Geometry'], sp.inputs['Geometry']); L.new(q, sp.inputs['Position'])
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(q, sep.inputs[0])
    kill = m('MAXIMUM', m('GREATER_THAN', sep.outputs[2], -0.9), m('LESS_THAN', vm('DISTANCE', q, C, out=1), 2.0))
    dl = N.new('GeometryNodeDeleteGeometry'); dl.domain = 'POINT'
    L.new(sp.outputs[0], dl.inputs['Geometry']); L.new(kill, dl.inputs['Selection'])
    ico = N.new('GeometryNodeMeshIcoSphere'); ico.inputs['Radius'].default_value = 1.0; ico.inputs['Subdivisions'].default_value = 1
    ip = N.new('GeometryNodeInstanceOnPoints')
    L.new(dl.outputs[0], ip.inputs['Points']); L.new(ico.outputs['Mesh'], ip.inputs['Instance']); L.new(at('sz'), ip.inputs['Scale'])
    ri = N.new('GeometryNodeRealizeInstances'); L.new(ip.outputs[0], ri.inputs[0])
    sm = N.new('GeometryNodeSetMaterial'); sm.inputs['Material'].default_value = mat
    L.new(ri.outputs[0], sm.inputs['Geometry']); L.new(sm.outputs[0], go.inputs[0])
    return ng


def _socket(md, name):
    ident = next(it.identifier for it in md.node_group.interface.items_tree if getattr(it, 'in_out', '') == 'INPUT' and it.name == name)
    return getattr(md.properties.inputs, ident)


def marine_snow(coll, M=None, n=1800, size=26.0, seed=51):
    """Drifting specks round the camera wherever it goes (driven by camP and seaT). Unlit, fogged, no ink, no shadow."""
    M = M or mats(); R = random.Random(seed)
    me = D.meshes.new('UNDER_snow'); me.from_pydata([(R.random(), R.random(), R.random()) for _ in range(n)], [], [])
    a = me.attributes.new('sz', 'FLOAT', 'POINT'); a.data.foreach_set('value', [R.choice((0.012, 0.016, 0.02, 0.026, 0.034, 0.045)) for _ in range(n)])
    b = me.attributes.new('ph', 'FLOAT', 'POINT'); b.data.foreach_set('value', [R.uniform(0.0, math.tau) for _ in range(n)])
    o = D.objects.new('UNDER_snow', me); coll.objects.link(o)
    md = o.modifiers.new('UNDER_snow', 'NODES'); md.node_group = snow_group(M['snow'])
    _drive_input(md, 'T')
    for i in range(3): _drive_input(md, 'C', '["camP"][%d]' % i, index=i)
    _socket(md, 'S').value = size
    o.visible_shadow = False; o['uw_kind'] = 'snow'
    return o


# ------------------------------------------------------------------------------------------------------------------ god rays
RAY_SPOTS = [(-92.0, 152.0, 30.0, 12), (-58.0, 192.0, 18.0, 4), (-100.0, 292.0, 60.0, 8), (-150.0, 215.0, 40.0, 5), (-35.0, 245.0, 40.0, 4),
             (-200.0, 140.0, 50.0, 4)]


def ray_mesh():
    me = D.meshes.get('UNDER_ray_unit')
    if me is not None: return me
    b = bmesh.new(); seg = 16
    bridge(b, [[Vector((math.cos(math.tau * k / seg), math.sin(math.tau * k / seg), z)) for k in range(seg)] for z in (0.0, -0.5, -1.0)], True, False)
    b.normal_update(); f = next(iter(b.faces)); c = f.calc_center_median()
    if f.normal.dot(Vector((c.x, c.y, 0.0))) < 0: bmesh.ops.reverse_faces(b, faces=b.faces[:])
    me = D.meshes.new('UNDER_ray_unit'); b.to_mesh(me); b.free(); me.shade_smooth()
    return me


def _aim_ray(o, end, S):
    top = end + S * ((-0.7 - end.z) / max(S.z, 0.2))
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(S)
    o.location = top; o.scale = (o.scale.x, o.scale.y, (top - end).length)


def god_rays(coll, M=None, spots=None, seed=61):
    """Drawn light shafts: soft open tubes (unit length along local -Z) from just under the surface down along the refracted
    sun, ending 5-14 m above the bed over the hero areas. Props amp (strength) and seed (flicker). ink 0, no shadow."""
    M = M or mats(); R = random.Random(seed); me = ray_mesh()
    if not me.materials: me.materials.append(M['ray'])
    S = Vector(bpy.context.scene.get('uwSun', (0.5, 0.0, 0.85))).normalized(); out = []
    for (cx, cy, rad, cnt) in (spots or RAY_SPOTS):
        for k in range(cnt):
            a = R.uniform(0, math.tau); d = rad * math.sqrt(R.random()); x = cx + math.cos(a) * d; y = cy + math.sin(a) * d
            o = D.objects.new('UNDER_ray', me); coll.objects.link(o)
            r = R.uniform(1.8, 5.5); o.scale = (r, r * R.uniform(0.45, 1.0), 1.0)
            _aim_ray(o, Vector((x, y, seabed_z(x, y) + R.uniform(5.0, 14.0))), S)
            o['amp'] = R.uniform(0.16, 0.42); o['seed'] = R.uniform(0.0, 100.0); o['uw_kind'] = 'ray'
            o.visible_shadow = False; out.append(o)
    return out


def aim_rays(rays, sc=None):
    """Re-aim the ray cards along the current uwSun (after set_water with another sun), keeping where each one ends."""
    sc = sc or bpy.context.scene; S = Vector(sc.get('uwSun', (0.5, 0.0, 0.85))).normalized()
    for o in rays:
        end = o.matrix_world @ Vector((0.0, 0.0, -1.0)); _aim_ray(o, end, S)


# ------------------------------------------------------------------------------------------------------------------ the sea from below
def underwater_surface(coll, M=None, radius=2600.0, z=-0.3, center=(-100.0, 150.0)):
    """The sea surface seen from below (Snell's window, a drawn net of light, swell shadows, sun glare): a disc facing down
    just under the sea plane. No shadow (the sun lights the water through it)."""
    M = M or mats(); b = bmesh.new(); seg = 96
    rings = [[Vector((center[0] + r * math.cos(math.tau * k / seg), center[1] + r * math.sin(math.tau * k / seg), z)) for k in range(seg)]
             for r in (30.0, 90.0, 200.0, 420.0, 800.0, 1500.0, radius)]
    bridge(b, rings, True, False, True, False)
    b.normal_update()
    if sum(f.normal.z for f in b.faces) > 0: bmesh.ops.reverse_faces(b, faces=b.faces[:])
    o = mkobj('UNDER_surface', b, M['surface'], coll, 'surface', smooth=False)
    o.visible_shadow = False
    return o


def backdrop(coll, M=None, radius=2400.0, z=-0.45, center=(-100.0, 150.0)):
    """Open water all round below the surface: an inward lower hemisphere in the water gradient with faint far ridges."""
    M = M or mats(); b = bmesh.new(); seg = 64; rings = []
    for j in range(12):
        a = math.pi / 2 * j / 12.0; r = radius * math.cos(a); h = z - radius * math.sin(a)
        rings.append([Vector((center[0] + r * math.cos(math.tau * k / seg), center[1] + r * math.sin(math.tau * k / seg), h)) for k in range(seg)])
    bridge(b, rings, True, False, False, True)
    b.normal_update(); cc = Vector((center[0], center[1], z))
    if sum(f.normal.dot(cc - f.calc_center_median()) for f in b.faces) < 0: bmesh.ops.reverse_faces(b, faces=b.faces[:])
    o = mkobj('UNDER_backdrop', b, M['backdrop'], coll, 'backdrop', smooth=True)
    o.visible_shadow = False
    return o


# ------------------------------------------------------------------------------------------------------------------ assembly
CORAL_PATCHES = [(-78.0, 162.0, 14.0, 14), (-97.0, 136.0, 11.0, 8), (-58.0, 192.0, 12.0, 8), (-120.0, 176.0, 12.0, 9),
                 (-40.0, 232.0, 22.0, 16), (-140.0, 246.0, 26.0, 18), (-95.0, 252.0, 20.0, 12), (-10.0, 282.0, 25.0, 14),
                 (-190.0, 300.0, 25.0, 12), (-68.0, 120.0, 14.0, 8)]


def eye_keep(p, r):
    """Nothing grows within 4.6 m of the anchor eye: the shackle and the pin stay clean and free to move."""
    return (p - Vector((0.0, 0.0, SHANK))).length < 4.6 + r


def build(parent=None, **opts):
    """Build the whole underwater set into a collection 'UNDER' (under `parent`). opts (all True by default): rocks, corals,
    crust, kelp, grass, boat, fish, snow, rays, surface, backdrop. Returns a dict (see the keys set below)."""
    t0 = time.time(); sc = bpy.context.scene; ensure_water(sc)
    op = dict(rocks=True, corals=True, crust=True, kelp=True, grass=True, boat=True, fish=True, snow=True, rays=True, surface=True, backdrop=True)
    op.update(opts)
    root = EV.coll('UNDER', parent); M = mats()
    U = {'root': root, 'materials': M, 'rocks': [], 'corals': [], 'acorals': [], 'kelp': [], 'grass': [], 'fish': {}, 'rays': []}
    U['seabed'] = seabed_mesh(root, M['sand'])
    a, s, pa, pb, ce, keep = anchor_set(root, M)
    U.update(anchor=a, shackle=s, pin_a=pa, pin_b=pb, chain_end=ce)
    U['shackle_a'], U['shackle_b'] = shackle_halves(root, M, s)
    sp = Space()
    aw = keep.copy(); aw.transform(A_MAT); sp.add_tree(BVHTree.FromBMesh(aw), 0.3); aw.free()
    sp.add(BOW, 4.0 * AS); sp.add(PIN, 4.0 * AS)
    for k in range(14): sp.add(BOW + Vector((0.0, 0.0, 3.0 + 3.6 * k)), 5.0)             # the chain rises straight up to the city
    bkeep = None
    if op['boat']:
        U['boat'], U['boat_parts'], bkeep = boat(root, M, sp)
        U['debris'] = boat_debris(root, M, sp)
    if op['rocks']: U['rocks'] = scatter_rocks(root, M['rock'], sp)
    if op['corals']: U['corals'] = scatter_corals(root, M, sp, CORAL_PATCHES)
    if op['crust']:
        U['crust'] = crust_on(a, keep, root, M['crust'], n_barn=420, n_sponge=30, n_tuft=220, keep_out=eye_keep); add_sway(U['crust'])
        U['acorals'] = corals_on(a, keep, root, M, n=16, keep_out=eye_keep)
        if bkeep is not None:
            U['bcrust'] = crust_on(U['boat'], bkeep, root, M['crust'], seed=8, n_barn=46, n_sponge=5, n_tuft=44, name='UNDER_boat_crust', kind='bcrust')
            add_sway(U['bcrust'])
            U['bcorals'] = corals_on(U['boat'], bkeep, root, M, n=7, seed=12, name='UNDER_boat_coral', kind='bcoral')
    if op['kelp']: U['kelp'] = kelp_forests(root, M['kelp'], sp)
    if op['grass']: U['grass'] = grass_meadows(root, M['grass'], sp)
    if op['fish']: U['fish'] = default_schools(root)
    if op['snow']: U['snow'] = marine_snow(root, M)
    if op['rays']: U['rays'] = god_rays(root, M)
    if op['surface']: U['surface'] = underwater_surface(root, M)
    if op['backdrop']: U['backdrop'] = backdrop(root, M)
    keep.free()
    if bkeep is not None: bkeep.free()
    U['space'] = sp; U['time'] = time.time() - t0
    return U


_ALLOW = {frozenset(p) for p in (
    ('bed', 'rock'), ('bed', 'kelp'), ('bed', 'grass'), ('bed', 'coral'), ('bed', 'anchor'), ('bed', 'boat'), ('bed', 'debris'),
    ('bed', 'crust'), ('bed', 'bcrust'), ('anchor', 'crust'), ('anchor', 'acoral'), ('crust', 'acoral'),
    ('boat', 'boat'), ('boat', 'bcrust'), ('boat', 'bcoral'), ('bcrust', 'bcoral'),
    ('kelp', 'kelp'), ('grass', 'grass'), ('kelp', 'grass'), ('fish', 'kelp'), ('fish', 'grass'), ('fish', 'fish'))}
_FREE = ('snow', 'ray', 'surface', 'backdrop')


def qa_allow(a, b):
    """Designed contacts for QA.overlaps: things standing in the seabed, growth on its host, plants among plants, fish among
    weed; the FX/sky layers (snow, rays, surface, backdrop) never count."""
    ka, kb = a.get('uw_kind', ''), b.get('uw_kind', '')
    if ka in _FREE or kb in _FREE: return True
    return frozenset((ka, kb)) in _ALLOW


def count_tris(objs):
    dg = bpy.context.evaluated_depsgraph_get(); n = 0
    for o in objs:
        if o.type != 'MESH': continue
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        if me is not None: me.calc_loop_triangles(); n += len(me.loop_triangles)
        ev.to_mesh_clear()
    return n
