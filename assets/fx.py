# ANCHOR - FX department (assets/fx.py)
# Drawn effects for the whole film: lightning, the storm wall, the waterspout, splashes, foam, spray trails, droplets,
# steam, sparks, silt, bubbles, debris.
#
# LOOK: hard cel tones (white / pale blue / blue shadow for water), crisp silhouettes, white cores, no particle soup.
#   Every material is built with kit/look.py: LK.NB + LK.finish (exactly the path of LK.flat / LK.glowmat; used directly
#   because the FX need per-pixel alpha sockets for the hard dissolve), LK.cel for the debris props (ink 1).
#   Water masses are lit by a "drawn light": the sun direction mixed with a camera-space upper-left key, so every mass
#   keeps a shade side even when the sun is behind the camera. Scene 'flash' brightens everything.
#
# TIME (frame conventions): every FX takes f0 = first visible frame and dur = length in frames and keys itself ON THREES:
#   drawing k is held on frames f0+3k .. f0+3k+2. Deforming FX are shape-key flipbooks (absolute keys, eval_time keyed
#   CONSTANT); rigid pieces key loc/rot CONSTANT. Objects are hidden (hide_render + hide_viewport keyed) before f0 and from
#   the first frame after their last drawing. Object prop 't' = seconds since f0 (keyed on threes) drives the in-shader
#   hard dissolve and the brush 'boil' between drawings.
#
# Every function returns its objects and takes a collection (coll=None -> scene collection). Names start with FX_.
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
for _p in (os.path.join(ROOT, 'kit'), HERE):
    if _p not in sys.path: sys.path.insert(0, _p)
import look as LK
import env as EV
import stage as ST

D = bpy.data
FPS = 24.0
STEP = 3
WATER_INK = float(os.environ.get('ANCHOR_WATER_INK', '0.0'))   # ink on the water masses (contract: 0; env override for A/B). ~0.3 = the reference's light lines
TAU = 2.0 * math.pi

# hi, lit, shade, deep
PAL_WATER = ('#ffffff', '#edf6ff', '#bfd7f4', '#8eaee2')
PAL_SPRAY = ('#ffffff', '#f0f8ff', '#c8dcf5', '#9bb7e4')
PAL_STEAM = ('#ffffff', '#efeff8', '#c3c0de', '#938fbd')
PAL_SILT = ('#e8d4ae', '#c6a77a', '#8f7357', '#5f4d42')
PAL_SKIRT = ('#f9faff', '#dde2f5', '#a9b0dd', '#7277b4')


# ================================================================================================================ basics
def _coll(c):
    return c or bpy.context.scene.collection


def _ft(f0, dur):
    """frames of the drawings (on threes), their times in seconds since f0, the first hidden frame."""
    n = max(1, int(math.ceil(float(dur) / STEP)))
    frames = [int(f0) + STEP * k for k in range(n)]
    return frames, np.arange(n) * STEP / FPS, int(f0) + STEP * n


def _sm(x):
    x = np.clip(x, 0.0, 1.0); return x * x * (3.0 - 2.0 * x)


def _eout(x, p=2.0):
    x = np.clip(x, 0.0, 1.0); return 1.0 - (1.0 - x) ** p


def _ein(x, p=2.0):
    x = np.clip(x, 0.0, 1.0); return x ** p


def _nrm(v):
    v = np.asarray(v, np.float64); n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


def _xyz(p, z=0.0):
    p = tuple(float(x) for x in p)
    return np.array(p if len(p) == 3 else (p[0], p[1], z), np.float64)


def _empty(name, loc=(0, 0, 0), coll=None, parent=None, size=5.0):
    o = D.objects.new(name, None); o.empty_display_size = size; o.empty_display_type = 'PLAIN_AXES'
    _coll(coll).objects.link(o)
    if parent is not None: o.parent = parent
    o.location = tuple(loc)
    return o


def _mesh(name, V, F, coll=None, mat=None, loc=(0, 0, 0), smooth=True, attrs=None):
    V = np.asarray(V, np.float32).reshape(-1, 3); F = np.asarray(F, np.int32).reshape(-1, 3)
    me = D.meshes.new(name)
    me.vertices.add(len(V)); me.vertices.foreach_set('co', V.ravel())
    me.loops.add(len(F) * 3); me.loops.foreach_set('vertex_index', F.ravel())
    me.polygons.add(len(F)); me.polygons.foreach_set('loop_start', np.arange(0, len(F) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    if smooth: me.shade_smooth()
    if attrs: _attrs(me, attrs)
    o = D.objects.new(name, me); _coll(coll).objects.link(o); o.location = tuple(loc)
    if mat is not None: me.materials.append(mat)
    o.visible_shadow = False
    return o


def _attrs(me, d):
    for k, arr in d.items():
        arr = np.asarray(arr, np.float32)
        if arr.ndim == 2:
            a = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT'); a.data.foreach_set('vector', arr.ravel())
        else:
            a = me.attributes.new(k, 'FLOAT', 'POINT'); a.data.foreach_set('value', arr.ravel())


def _std(at, nv):
    """the attribute set every water-type mesh carries (missing ones get neutral defaults)."""
    for k, v in (('tone', 0.0), ('seed', 0.0), ('d0', 1e5), ('d1', 2e5), ('bk', 1.0), ('op', 0.0)):
        if k not in at: at[k] = np.full(nv, v, np.float32)
    if 'rp' not in at: at['rp'] = np.zeros((nv, 3), np.float32)
    if 'dp' not in at: at['dp'] = at['rp']
    return at


def _interp(idb, kind='CONSTANT', paths=None):
    for fc in ST.fcurves(idb):
        if paths is None or fc.data_path in paths:
            for k in fc.keyframe_points: k.interpolation = kind


def _show(o, f_on, f_off):
    """visible on [f_on, f_off), hidden before and after."""
    for a in ('hide_render', 'hide_viewport'):
        setattr(o, a, True); o.keyframe_insert(a, frame=f_on - 1)
        setattr(o, a, False); o.keyframe_insert(a, frame=f_on)
        setattr(o, a, True); o.keyframe_insert(a, frame=f_off)


def _keyp(o, name, frames, values):
    for f, v in zip(frames, values):
        o[name] = v if isinstance(v, (tuple, list)) else float(v); o.keyframe_insert('["%s"]' % name, frame=int(f))
    _interp(o, 'CONSTANT', ('["%s"]' % name,))


def _flip(o, Vs, frames):
    """shape-key flipbook: drawing k (vertex array Vs[k], object space) from frame frames[k]."""
    me = o.data
    me.vertices.foreach_set('co', np.asarray(Vs[0], np.float32).ravel())
    if len(Vs) > 1:
        b = o.shape_key_add(name='d000', from_mix=False); b.interpolation = 'KEY_LINEAR'
        for k in range(1, len(Vs)):
            kb = o.shape_key_add(name='d%03d' % k, from_mix=False); kb.interpolation = 'KEY_LINEAR'
            kb.data.foreach_set('co', np.asarray(Vs[k], np.float32).ravel())
        key = me.shape_keys; key.use_relative = False
        for k, f in enumerate(frames):
            key.eval_time = key.key_blocks[k].frame; key.keyframe_insert('eval_time', frame=int(f))
        _interp(key, 'CONSTANT')
    me.update()


def _driver(o, path, src, src_path, expr='var', index=-1):
    fc = o.driver_add(path, index) if index >= 0 else o.driver_add(path)
    d = fc.driver; d.type = 'SCRIPTED'
    v = d.variables.new(); v.name = 'var'; v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'; v.targets[0].id = src; v.targets[0].data_path = src_path
    d.expression = expr
    return fc


# ================================================================================================================ geometry
_ICO = {}


def _ico(sub):
    """unit icosphere arrays (sub 2 = 42 verts, 3 = 162, 4 = 642)."""
    if sub not in _ICO:
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        bm.verts.ensure_lookup_table(); bm.verts.index_update()
        V = np.array([v.co[:] for v in bm.verts], np.float64)
        F = np.array([[v.index for v in f.verts] for f in bm.faces], np.int32)
        bm.free()
        _ICO[sub] = (V / np.linalg.norm(V, axis=1, keepdims=True), F)
    return _ICO[sub]


def _bumps(V, R, n=7, amp=0.13, width=0.8):
    """cauliflower lumps on a unit sphere."""
    C = _nrm(R.normal(size=(n, 3)))
    d = np.clip(V @ C.T - width, 0.0, None) / (1.0 - width)
    return V * (1.0 + amp * np.max(d ** 1.5, axis=1))[:, None]


def tpl_billow(seed=1, sub=3, buds=3):
    """a drawn billow: one lumpy sphere and 2-4 buds on its upper side (one mesh, radius ~1)."""
    R = np.random.RandomState(seed); V0, F0 = _ico(sub)
    Vs = [_bumps(V0, R)]; Fs = [F0]; RPs = [V0.copy()]
    for b in range(buds):
        a = R.uniform(0, TAU); el = R.uniform(0.05, 1.15)
        d = np.array([math.cos(el) * math.cos(a), math.cos(el) * math.sin(a), math.sin(el)])
        r = R.uniform(0.42, 0.6); c = d * (1.0 - 0.32 * r)
        Vs.append(_bumps(V0, R, 5, 0.1) * r + c); Fs.append(F0 + len(V0) * (b + 1)); RPs.append(V0 * r + c + 2.37 * (b + 1))
    return np.vstack(Vs), np.vstack(Fs), np.vstack(RPs)


def tpl_tongue(seed=2, sub=3, k=1.7):
    """a lumpy tongue pointing along +z (tip at z ~ 1+k), round root at -z."""
    R = np.random.RandomState(seed); V0, F0 = _ico(sub)
    V = _bumps(V0, R, 8, 0.12); z = V0[:, 2]; up = np.clip(z, 0, None)
    tp = 1.0 - 0.78 * up ** 1.4
    V[:, 0] *= tp; V[:, 1] *= tp; V[:, 2] = V[:, 2] + k * up ** 1.25
    return V, F0.copy(), V0.copy()


def tpl_drop(sub=3, tail=1.7, sharp=0.86):
    """a drawn droplet: round head at +z, tail trailing to -z. sub 3 (162 vertices): on the 42-vertex ball a drop near the
    lens showed flat facets and a straight light/shade split - a white ice crystal (s26 f1259, 06.11)."""
    V0, F0 = _ico(sub); V = V0.copy(); z = V0[:, 2]; dn = np.clip(-z, 0, None)
    tp = 1.0 - sharp * dn ** 1.3
    V[:, 0] *= tp; V[:, 1] *= tp; V[:, 2] = z - tail * dn ** 1.2
    return V, F0.copy(), V0.copy()


def tpl_spindle():
    V = np.array([(0, 0, 1.0), (0, 0, -1.0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)], np.float64)
    F = np.array([(0, 2, 3), (0, 3, 4), (0, 4, 5), (0, 5, 2), (1, 3, 2), (1, 4, 3), (1, 5, 4), (1, 2, 5)], np.int32)
    return V, F, V.copy()


def tpl_star(seed=5, spikes=12, core=0.26):
    """a spiky 3D starburst (reads as a drawn 'kira' from any side)."""
    R = np.random.RandomState(seed); V0, F0 = _ico(2)
    Vs = [V0 * core]; Fs = [F0]; n = len(V0)
    dirs = _nrm(R.normal(size=(spikes, 3)))
    for d in dirs:
        L = R.uniform(0.55, 1.0); a = _nrm(np.cross(d, [0.3, 0.5, 0.8])); b = np.cross(d, a)
        ring = [d * core * 0.7 + (math.cos(q) * a + math.sin(q) * b) * core * 0.42 for q in np.arange(4) * TAU / 4]
        Vs.append(np.array(ring + [d * L])); i0 = n
        Fs.append(np.array([(i0 + j, i0 + (j + 1) % 4, i0 + 4) for j in range(4)], np.int32)); n += 5
    return np.vstack(Vs), np.vstack(Fs), np.vstack(Vs)


def _frame_z(d):
    """(n,3) directions -> (n,3,3) rotations whose 3rd column is the direction."""
    z = _nrm(d)
    a = np.where(np.abs(z[:, 2:3]) < 0.95, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
    x = _nrm(np.cross(a, z)); y = np.cross(z, x)
    return np.stack([x, y, z], axis=2)


def _rot(axis, ang):
    axis = _nrm(axis); x, y, z = axis[:, 0], axis[:, 1], axis[:, 2]; c = np.cos(ang); s = np.sin(ang); C = 1.0 - c
    R = np.empty((len(ang), 3, 3))
    R[:, 0, 0] = c + x * x * C; R[:, 0, 1] = x * y * C - z * s; R[:, 0, 2] = x * z * C + y * s
    R[:, 1, 0] = y * x * C + z * s; R[:, 1, 1] = c + y * y * C; R[:, 1, 2] = y * z * C - x * s
    R[:, 2, 0] = z * x * C - y * s; R[:, 2, 1] = z * y * C + x * s; R[:, 2, 2] = c + z * z * C
    return R


def _scale(R, sx, sy=None, sz=None):
    sy = sx if sy is None else sy; sz = sx if sz is None else sz
    return R * np.stack([np.broadcast_to(sx, (len(R),)), np.broadcast_to(sy, (len(R),)), np.broadcast_to(sz, (len(R),))], 1)[:, None, :]


def _cone_dirs(R, n, up, spread):
    """random unit directions inside a cone of half-angle spread*90deg around up."""
    up = _nrm(np.asarray(up, np.float64)[None])[0]
    a = R.uniform(0, TAU, n); c = 1.0 - R.uniform(0, 1, n) * (1.0 - math.cos(min(spread, 1.0) * math.pi * 0.5))
    s = np.sqrt(np.clip(1 - c * c, 0, 1))
    loc = np.stack([s * np.cos(a), s * np.sin(a), c], 1)
    return loc @ _frame_z(up[None])[0].T


def _props(o, props):
    for k, v in (props or {}).items(): o[k] = tuple(float(x) for x in v) if isinstance(v, (tuple, list, np.ndarray)) else float(v)
    return o


def _pobj(name, tpl, Ps, Ms, frames, f_end, coll, mat, loc=(0, 0, 0), eattr=None, seed=0, rp_scale=1.0, props=None, sel=None):
    """an element flipbook: n copies of a template, transformed per drawing (Ps (n,3), Ms (n,3,3) per drawing).
    sel: optional boolean mask choosing a subset of the elements; props: object props (mk, mz, mdir...)."""
    if sel is not None:
        Ps = [P[sel] for P in Ps]; Ms = [M[sel] for M in Ms]
        eattr = {k: np.asarray(v)[sel] for k, v in (eattr or {}).items()}
    Vt, Ft, RPt = tpl; m = len(Vt); n = Ps[0].shape[0]
    F = (Ft[None] + (np.arange(n) * m)[:, None, None]).reshape(-1, 3)
    Vs = [(np.einsum('nij,mj->nmi', M, Vt) + P[:, None, :]).reshape(-1, 3) for P, M in zip(Ps, Ms)]
    R = np.random.RandomState(seed + 991)
    off = R.uniform(-60, 60, (n, 3))
    at = {'rp': (RPt[None] * rp_scale + off[:, None, :]).reshape(-1, 3)}
    if 'seed' not in (eattr or {}): at['seed'] = np.repeat(R.uniform(0, 1, n), m)
    for k, v in (eattr or {}).items(): at[k] = np.repeat(np.asarray(v, np.float32), m)
    o = _mesh(name, Vs[0], F, coll, mat, loc, attrs=_std(at, len(Vs[0])))
    _props(o, props)
    _flip(o, Vs, frames); _show(o, frames[0], f_end)
    _keyp(o, 't', frames, [(f - frames[0]) / FPS for f in frames])
    return o


def _tube(path, rad, sides=8):
    """a tube along a polyline (parallel-transport frames), capped. -> V, F"""
    P = np.asarray(path, np.float64); n = len(P); rad = np.asarray(rad, np.float64)
    seg = _nrm(np.diff(P, axis=0))
    T = np.empty((n, 3)); T[0] = seg[0]; T[-1] = seg[-1]
    if n > 2: T[1:-1] = seg[:-1] + seg[1:]
    T = _nrm(T)
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    Nv = _nrm(np.cross(T[0], ref)); Ns = []; Bs = []
    for i in range(n):
        Nv = _nrm(Nv - np.dot(Nv, T[i]) * T[i]); Ns.append(Nv); Bs.append(np.cross(T[i], Nv))
    Ns = np.array(Ns); Bs = np.array(Bs)
    ang = np.arange(sides) / sides * TAU
    ring = P[:, None, :] + rad[:, None, None] * (np.cos(ang)[None, :, None] * Ns[:, None, :] + np.sin(ang)[None, :, None] * Bs[:, None, :])
    V = np.vstack([ring.reshape(-1, 3), P[0] - T[0] * rad[0] * 0.6, P[-1] + T[-1] * rad[-1] * 0.6])
    I, J = np.meshgrid(np.arange(n - 1), np.arange(sides), indexing='ij')
    a = I * sides + J; b = I * sides + (J + 1) % sides; c = (I + 1) * sides + (J + 1) % sides; d = (I + 1) * sides + J
    F = [np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)]
    cs, ce = n * sides, n * sides + 1; j = np.arange(sides)
    F.append(np.stack([np.full(sides, cs), (j + 1) % sides, j], -1))
    F.append(np.stack([np.full(sides, ce), (n - 1) * sides + j, (n - 1) * sides + (j + 1) % sides], -1))
    return V, np.vstack(F)


# ================================================================================================================ materials
def _mk(name, fn, ink=0.0, paint=0.0, strength=1.0, blend=False, setup=None, hz=1.0):
    """material through the look kit (LK.NB + LK.finish). fn(nb) -> colour or (colour, alpha, glow)."""
    m = D.materials.get(name)
    if m is not None: return m
    nb = LK.NB(name)
    res = fn(nb)
    col, alpha, glow = (tuple(res) + (None, 0.0))[:3] if isinstance(res, tuple) else (res, None, 0.0)
    m = LK.finish(nb, col, ink, paint, glow, alpha, strength, blend, hz)
    if setup: setup(m)
    return m


def _dlight(nb, k=0.6, cam=(-0.55, 0.62, 0.56)):
    """the drawn key light: sun direction mixed with a camera-space upper-left light."""
    vt = nb.new('ShaderNodeVectorTransform', props={'vector_type': 'VECTOR', 'convert_from': 'CAMERA', 'convert_to': 'WORLD'})
    vt.inputs['Vector'].default_value = cam
    Lc = nb.vmath('NORMALIZE', vt.outputs['Vector'])
    sd = nb.attr('sunD', 'Vector')
    return nb.vmath('NORMALIZE', nb.vmath('ADD', nb.vmath('SCALE', sd, scale=1.0 - k), nb.vmath('SCALE', Lc, scale=k)))


def _sunlit(nb):
    d = nb.new('ShaderNodeBsdfDiffuse', ins={'Color': (1, 1, 1, 1)})
    s2r = nb.N.new('ShaderNodeShaderToRGB'); nb.L.new(d.outputs[0], s2r.inputs[0])
    return nb.smooth(nb.bw(s2r.outputs['Color']), 0.012, 0.055)


def _decay(nb):
    t = nb.objattr('t'); d0 = nb.attr('d0', 'Fac', 'GEOMETRY'); d1 = nb.attr('d1', 'Fac', 'GEOMETRY')
    return nb.math('DIVIDE', nb.sub(t, d0), nb.mx(nb.sub(d1, d0), 0.001), clamp=True)


ERASERS = 8                  # per object: er<i>c (dp centre), er<i>r (dp radius, 0 = off), er<i>t (s, the object's own t)
ERASE_RUN = 0.375            # s: an eraser eats its spot over 3 drawings (on threes) before er<i>t


def _erase(nb, k, dp, t):
    """spots of a water mesh dissolved early (shots/bodyfx.py, 06.11: the last lace of a sheet left alone on the mech's body
    read as a white sticker on the armour; a vertex melt is limited by the mesh, and on a sheet near the lens one face is
    a big piece of the frame): the dissolve factor k is raised to 1 within 0.7 r of the spot's centre in dp (the lace
    noise's own coordinates, so pixel-exact), falling to 0 at r, over ERASE_RUN s up to er<i>t; the lace eats the spot
    with its white edges like any dissolve. An object without the props (r = 0): k unchanged."""
    ke = None
    for i in range(ERASERS):
        r = nb.objattr('er%dr' % i); tk = nb.objattr('er%dt' % i)
        rs = nb.mx(r, 1e-5)
        w = nb.smooth(nb.vmath('DISTANCE', dp, nb.objattr('er%dc' % i, 'Vector')), rs, nb.mul(rs, 0.7))
        g = nb.math('DIVIDE', nb.add(nb.sub(t, tk), ERASE_RUN), ERASE_RUN, clamp=True)
        e = nb.mul(nb.mul(w, g), nb.math('GREATER_THAN', r, 0.0))
        ke = e if ke is None else nb.mx(ke, e)
    return nb.mx(k, ke)


MATTE_DIR = os.path.join(ROOT, 'out', 'matte')          # the mech's own mattes per frame (out/matte/m<frame>.png)
MATTE_PASS = os.environ.get('ANCHOR_MATTE') == '1'      # the matte render itself: marked water is simply not drawn in its window
_MATTE_SEQ = []


def _matte_seq():
    """the matte image sequence, loaded once: files m<P>..m<Q> without a gap, P and Q black pads (frames before / after the
    sequence read them); None when there are no mattes."""
    if _MATTE_SEQ: return _MATTE_SEQ[0]
    seq = None
    try: fs = sorted(int(x[1:-4]) for x in os.listdir(MATTE_DIR) if x.startswith('m') and x.endswith('.png') and x[1:-4].isdigit())
    except OSError: fs = []
    if len(fs) >= 3 and fs[-1] - fs[0] + 1 == len(fs):
        P, Q = fs[0], fs[-1]
        img = D.images.load(os.path.join(MATTE_DIR, 'm%04d.png' % P), check_existing=True)
        img.source = 'SEQUENCE'; img.colorspace_settings.name = 'Non-Color'; img.alpha_mode = 'CHANNEL_PACKED'
        seq = (img, P, Q); print('BEHIND mattes m%04d..m%04d' % (P, Q), flush=True)
    elif fs: print('BEHIND mattes with gaps (%d files, %d..%d): not used' % (len(fs), fs[0], fs[-1]), flush=True)
    _MATTE_SEQ.append(seq)
    return seq


def _behind(nb, alpha):
    """water marked 'behind the mech' (shots/bodyfx.py 'behind', 06.11: the crown splashes were made without the body - a
    column sliced the pauldron, the head stood inside a column, a ball sank into the pauldron, s32-s34): vertex attrs
    bh0/bh1 (frames) open the window; inside it the piece is not drawn where the mech's matte covers the pixel - the mech
    as seen with every other surface in front of it (out/matte/m<frame>.png: R the matte, G + 256 B the frame number, which
    must equal the scene uniform bh_fr, so a stale or shifted matte never cuts) - so it passes behind the armour exactly at
    its outline, keeping its shape, tones and timing. Camera rays only. No attrs (bh1 = 0) or no mattes: alpha unchanged."""
    fr = nb.attr('bh_fr', 'Fac')
    win = nb.mul(nb.math('GREATER_THAN', fr, nb.attr('bh0', 'Fac', 'GEOMETRY')), nb.math('LESS_THAN', fr, nb.attr('bh1', 'Fac', 'GEOMETRY')))
    if MATTE_PASS: return nb.mul(alpha, nb.sub(1.0, win))
    seq = _matte_seq()
    if seq is None: return alpha
    img, P, Q = seq
    ti = nb.new('ShaderNodeTexImage', props={'interpolation': 'Linear', 'extension': 'EXTEND'}); ti.image = img
    iu = ti.image_user; iu.frame_start = P + 1; iu.frame_offset = P; iu.frame_duration = Q - P; iu.use_cyclic = False; iu.use_auto_refresh = True
    nb.L.new(nb.tc().outputs['Window'], ti.inputs['Vector'])
    sp = nb.new('ShaderNodeSeparateColor'); nb.L.new(ti.outputs['Color'], sp.inputs[0])
    code = nb.add(nb.math('ROUND', nb.mul(sp.outputs[1], 255.0)), nb.mul(nb.math('ROUND', nb.mul(sp.outputs[2], 255.0)), 256.0))
    ok = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.sub(code, fr)), 0.5)
    # R carries render noise of a few levels (06.11: ~8 % of the mech's pixels read 253/255 at f1323): 1 - 0.992 left the
    # piece 0.8 % opaque, the dithered water kept a sample now and then, and its oid / mid / ink went into the data passes as
    # specks the post inked all over the armour (s27 moss pad, s33). Hardened: R <= 0.03 no cut, R >= 0.97 the full cut.
    cut = nb.math('DIVIDE', nb.sub(sp.outputs[0], 0.03), 0.94, clamp=True)
    cam = nb.new('ShaderNodeLightPath').outputs['Is Camera Ray']
    return nb.mul(alpha, nb.sub(1.0, nb.mul(nb.mul(nb.mul(win, ok), cut), cam)))


def water_mat(name='M_fx_water', pal=PAL_WATER, edges=(0.28, 0.45, 0.64), camk=0.6, inside=0.35, shadow=0.25, brush=0.75,
              lace=1.7, ink=None, flash=0.6, tint=None, edge=0.7):
    """the drawn-water material: 4 hard tones (white-dominant) from the drawn light on a blended 'mass normal' + a boiling
    brush (bk > 1 adds hard shade blobs); hard dissolve into lace with white edges (edge = their strength, 0 = none: steam,
    silt). Object props (all optional): t (s, drives boil + dissolve),
    mk (0..1 how much the whole effect shades as one mass), mz (mass centre height above the origin, m), mdir (unit vector:
    the mass is a cylinder along it - walls/trails; 0 = a ball). Vertex attrs: rp (brush coords), dp (dissolve coords),
    tone, seed, d0, d1 (dissolve start/end, s), bk (brush weight), op (1 = open sheet: keeps its back faces while dissolving;
    closed masses lose them so the holes go through)."""
    def fn(nb):
        g = nb.geo(); N = g.outputs['Normal']; P = g.outputs['Position']
        oi = nb.N.new('ShaderNodeObjectInfo')
        rel = nb.vmath('SUBTRACT', P, nb.vmath('ADD', oi.outputs['Location'], nb.vec(0.0, 0.0, nb.objattr('mz'))))
        md = nb.objattr('mdir', 'Vector')
        rel = nb.vmath('SUBTRACT', rel, nb.vmath('SCALE', md, scale=nb.vmath('DOT_PRODUCT', rel, md)))
        mk = nb.objattr('mk')
        nn = nb.vmath('NORMALIZE', nb.vmath('ADD', nb.vmath('SCALE', N, scale=nb.sub(1.0, mk)), nb.vmath('SCALE', nb.vmath('NORMALIZE', rel), scale=mk)))
        L = _dlight(nb, camk)
        ndl = nb.vmath('DOT_PRODUCT', nn, L)
        rp = nb.attr('rp', 'Vector', 'GEOMETRY')
        t = nb.objattr('t')
        sd = nb.attr('seed', 'Fac', 'GEOMETRY')
        w = nb.add(nb.mul(nb.math('FLOOR', nb.mul(t, 8.0)), 0.71), nb.mul(sd, 11.0))
        br = nb.noise(nb.vmath('SCALE', rp, scale=0.9), 1.0, 2.0, 0.55, 0.15, w=w)
        bk = nb.attr('bk', 'Fac', 'GEOMETRY')
        s = nb.add(nb.mul(ndl, 0.85), nb.mul(nb.mul(nb.sub(br, 0.5), bk), 1.1 * brush))
        # bk > 1: the brush also cuts hard blobs (big drawn shade shapes on sheets and curtains)
        s = nb.add(s, nb.mul(nb.mul(nb.mx(nb.sub(bk, 1.0), 0.0), nb.sub(nb.smooth(br, 0.4, 0.6), 0.5)), 0.6))
        s = nb.sub(s, nb.attr('tone', 'Fac', 'GEOMETRY'))
        if shadow: s = nb.sub(s, nb.mul(nb.sub(1.0, _sunlit(nb)), shadow))
        if inside: s = nb.sub(s, nb.mul(g.outputs['Backfacing'], inside))
        k = _decay(nb)
        dp = nb.attr('dp', 'Vector', 'GEOMETRY')
        k = _erase(nb, k, dp, t)
        dn = nb.noise(nb.vmath('ADD', nb.vmath('SCALE', dp, scale=lace), (3.1, 7.7, 1.3)), 1.0, 1.3, 0.45, 0.12)
        dn = nb.smooth(dn, 0.3, 0.7)          # spread the noise over 0..1 so the holes grow through the whole d0..d1 window
        # ... and the window ends with nothing left: at 0.97 k - 0.03 the threshold stopped at 0.94, every spot of noise
        # over ~0.64 (some 7 % of the mass) stayed as lace for good and vanished with the object, mid-shot (the step crowns'
        # surge at s26 f1269 / s34 f1725, 06.11)
        thr = nb.sub(nb.mul(k, 1.03), 0.03)
        alpha = nb.math('GREATER_THAN', dn, thr)
        # a dissolving closed mass loses its back faces, so its holes go right through (open sheets: vertex op = 1 keep them)
        thru = nb.mul(nb.mul(g.outputs['Backfacing'], nb.math('GREATER_THAN', k, 0.01)), nb.sub(1.0, nb.attr('op', 'Fac', 'GEOMETRY')))
        alpha = nb.mul(alpha, nb.sub(1.0, thru))
        alpha = _behind(nb, alpha)
        if edge:
            el = nb.mul(nb.math('LESS_THAN', dn, nb.add(thr, 0.09)), nb.math('GREATER_THAN', k, 0.01))
            s = nb.add(s, nb.mul(el, edge))
        v = nb.add(nb.mul(s, 0.5), 0.5)
        col = nb.ramp(v, [(0.0, pal[3]), (edges[0], pal[2]), (edges[1], pal[1]), (edges[2], pal[0])])
        if tint: col = nb.cmul(col, tint)
        col = nb.mixc(col, nb.mixc(col, '#eef2ff', 0.65), nb.mul(nb.attr('flash', 'Fac'), flash))
        return col, alpha, 0.0
    return _mk(name, fn, ink=WATER_INK if ink is None else ink)


def glow_mat(name='M_fx_bolt', band1='#79e6ff', band2='#9a72ff', rim='#2f2489', core=3.2, edge=0.06):
    """self-lit tube: white-hot core, two hard colour bands, a dark rim; prop 'power' (0..1+) and vertex 'lvl'."""
    def fn(nb):
        g = nb.geo(); fac = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', g.outputs['Normal'], g.outputs['Incoming']))
        pw = nb.objattr('power'); lvl = nb.attr('lvl', 'Fac', 'GEOMETRY')
        on = nb.math('GREATER_THAN', pw, nb.add(nb.mul(lvl, 0.95), 0.02))
        pc = nb.math('MINIMUM', pw, 1.0)
        cth = nb.add(0.62, nb.mul(nb.sub(1.0, pc), 0.26))
        col = nb.mixc(nb.rgb(rim), nb.rgb(band2), nb.math('GREATER_THAN', fac, 0.2))
        col = nb.mixc(col, nb.rgb(band1), nb.math('GREATER_THAN', fac, 0.43))
        hot = nb.cscale(nb.rgb('#ffffff'), nb.add(0.6, nb.mul(pc, core)))
        col = nb.mixc(col, hot, nb.math('GREATER_THAN', fac, cth))
        col = nb.cscale(col, nb.add(0.3, nb.mul(pc, 0.7)))
        alpha = nb.mul(on, nb.math('GREATER_THAN', fac, edge))
        return col, alpha, 1.0
    return _mk(name, fn)


def spark_mat(name='M_fx_spark'):
    """sparks: hot white-yellow core cooling to orange-red with age; vertex birth/life + prop t."""
    def fn(nb):
        g = nb.geo(); fac = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', g.outputs['Normal'], g.outputs['Incoming']))
        t = nb.objattr('t'); b = nb.attr('d0', 'Fac', 'GEOMETRY'); life = nb.attr('d1', 'Fac', 'GEOMETRY')
        age = nb.math('DIVIDE', nb.sub(t, b), nb.mx(nb.sub(life, b), 0.01), clamp=True)
        col = nb.mixc(nb.rgb('#ff5a1f'), nb.rgb('#ffa83a'), nb.math('GREATER_THAN', fac, 0.3))
        hot = nb.mixc(nb.cscale(nb.rgb('#fff6d8'), 2.6), nb.rgb('#ffcf5a'), nb.smooth(age, 0.35, 0.8))
        col = nb.mixc(col, hot, nb.math('GREATER_THAN', fac, nb.add(0.55, nb.mul(age, 0.3))))
        col = nb.mixc(col, nb.cmul(col, '#ff7a5a'), nb.smooth(age, 0.6, 1.0))
        return col, nb.math('GREATER_THAN', fac, 0.05), 1.0
    return _mk(name, fn)


def bubble_mat(name='M_fx_bubble'):
    """bubbles: bright rim, clear inside, two highlight spots (camera space)."""
    def fn(nb):
        g = nb.geo(); N = g.outputs['Normal']
        fac = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', N, g.outputs['Incoming']))
        vt = nb.new('ShaderNodeVectorTransform', props={'vector_type': 'NORMAL', 'convert_from': 'WORLD', 'convert_to': 'CAMERA'})
        nb.put(vt.inputs['Vector'], N); nc = vt.outputs['Vector']
        s1 = nb.math('GREATER_THAN', nb.vmath('DOT_PRODUCT', nc, (-0.45, 0.55, 0.70)), 0.93)
        s2 = nb.math('GREATER_THAN', nb.vmath('DOT_PRODUCT', nc, (0.50, -0.45, 0.74)), 0.975)
        rim = nb.math('LESS_THAN', fac, 0.52)
        col = nb.mixc(nb.rgb('#8fe4f2'), nb.rgb('#e8fcff'), nb.math('LESS_THAN', fac, 0.36))
        col = nb.mixc(col, nb.rgb('#ffffff'), nb.mx(s1, s2))
        col = nb.mixc(col, nb.mixc(col, '#ffffff', 0.5), nb.attr('flash', 'Fac'))
        return col, nb.mx(rim, nb.mx(s1, s2)), 0.15
    return _mk(name, fn)


def foam_mat(name='M_fx_foam'):
    """flat foam on the sea (rings, discs): solid white + pale cyan lace, eaten away with prop 'age' (0..1).
    The lace is fixed in the world (cells of prop 'cell' m) so an expanding ring spreads through it.
    vertex: ra (radius fraction 0..1). object: t, age, band (ring inner fraction), fill (inner churn), cell, sd (seed)."""
    def fn(nb):
        ra = nb.attr('ra', 'Fac', 'GEOMETRY')
        oi = nb.N.new('ShaderNodeObjectInfo')
        rel = nb.vmath('SUBTRACT', nb.geo().outputs['Position'], oi.outputs['Location'])
        rp = nb.vmath('ADD', nb.vmath('DIVIDE', rel, nb.vec(nb.objattr('cell'), nb.objattr('cell'), 1.0)), nb.vec(nb.objattr('sd'), 0.0, 0.0))
        t = nb.objattr('t'); age = nb.objattr('age'); band = nb.objattr('band'); fill = nb.objattr('fill')
        w = nb.math('FLOOR', nb.mul(t, 8.0))
        l1 = nb.noise(rp, 1.0, 3.0, 0.62, 0.35, w=nb.mul(w, 0.29))
        l2 = nb.noise(nb.vmath('SCALE', rp, scale=2.8), 1.0, 2.0, 0.6, 0.2, w=nb.add(nb.mul(w, 0.41), 3.0))
        lace = nb.add(nb.mul(l1, 0.72), nb.mul(l2, 0.28))
        ring = nb.mul(nb.smooth(ra, band, nb.add(band, 0.13)), nb.smooth(ra, 1.0, 0.93))
        inner = nb.mul(fill, nb.smooth(ra, nb.add(band, 0.06), nb.sub(band, 0.35)))
        dens = nb.mx(nb.mul(ring, nb.sub(1.0, nb.mul(age, 0.55))), nb.mul(inner, nb.sub(1.0, age)))
        F = nb.add(nb.mul(dens, 0.78), nb.mul(nb.sub(lace, 0.5), 3.0))
        F = nb.sub(F, nb.mul(age, 0.25))
        alpha = nb.math('GREATER_THAN', F, 0.36)
        col = nb.mixc(nb.rgb('#bfe9f4'), nb.rgb('#ffffff'), nb.math('GREATER_THAN', F, 0.58))
        col = nb.mixc(col, nb.mixc(col, '#eef2ff', 0.5), nb.attr('flash', 'Fac'))
        return col, alpha, 0.0
    return _mk(name, fn)


def wake_mat(name='M_fx_wake'):
    """foam strip revealed along a path. vertex: u (path fraction), ra (|across| 0..1), rp. object: head (fraction),
    L (path length m), spd (m/s), fade (s), t."""
    def fn(nb):
        rp = nb.attr('rp', 'Vector', 'GEOMETRY'); ra = nb.attr('ra', 'Fac', 'GEOMETRY'); u = nb.attr('u', 'Fac', 'GEOMETRY')
        t = nb.objattr('t'); head = nb.objattr('head')
        behind = nb.sub(head, u)
        vis = nb.math('GREATER_THAN', behind, -0.0005)
        age = nb.math('DIVIDE', nb.math('DIVIDE', nb.mul(nb.mx(behind, 0.0), nb.objattr('L')), nb.mx(nb.objattr('spd'), 0.01)), nb.mx(nb.objattr('fade'), 0.01))
        w = nb.math('FLOOR', nb.mul(t, 8.0))
        l1 = nb.noise(nb.vmath('SCALE', rp, scale=3.0), 1.0, 3.0, 0.62, 0.35, w=nb.mul(w, 0.29))
        l2 = nb.noise(nb.vmath('SCALE', rp, scale=8.0), 1.0, 2.0, 0.6, 0.2, w=nb.add(nb.mul(w, 0.37), 5.0))
        lace = nb.add(nb.mul(l1, 0.7), nb.mul(l2, 0.3))
        wid = nb.add(0.25, nb.mul(nb.math('MINIMUM', nb.mul(age, 1.6), 1.0), 0.75))
        core = nb.smooth(ra, wid, nb.mul(wid, 0.5))
        mid = nb.mul(nb.smooth(ra, nb.mul(wid, 0.45), 0.0), nb.math('MINIMUM', nb.mul(age, 3.0), 1.0))
        dens = nb.mul(nb.sub(core, nb.mul(mid, 0.45)), nb.sub(1.0, nb.math('MINIMUM', age, 1.0)))
        F = nb.add(nb.mul(dens, 0.78), nb.mul(nb.sub(lace, 0.5), 3.0))
        alpha = nb.mul(vis, nb.math('GREATER_THAN', F, 0.38))
        col = nb.mixc(nb.rgb('#bfe9f4'), nb.rgb('#ffffff'), nb.math('GREATER_THAN', F, 0.6))
        col = nb.mixc(col, nb.mixc(col, '#eef2ff', 0.5), nb.attr('flash', 'Fac'))
        return col, alpha, 0.0
    return _mk(name, fn)


def storm_mat(name='M_fx_storm'):
    """cumulonimbus: tones by height in the tower ('ht'), sun facing and up facing, a painted brush; two inner flash cells
    (object props fl1/fp1, fl2/fp2: strength, world position); scene flash. Painted (paint=1), ink 0."""
    def fn(nb):
        g = nb.geo(); N = g.outputs['Normal']; P = g.outputs['Position']
        sunD = nb.attr('sunD', 'Vector')
        ht = nb.attr('ht', 'Fac', 'GEOMETRY'); rp = nb.attr('rp', 'Vector', 'GEOMETRY'); tb = nb.attr('tone', 'Fac', 'GEOMETRY')
        br = nb.noise(nb.vmath('SCALE', rp, scale=1.1), 1.0, 3.0, 0.6, 0.25)
        # one big volume per tower: blend each billow's normal with the tower's ellipsoid normal (vertex 'tn', 0 = own normal)
        tn = nb.attr('tn', 'Vector', 'GEOMETRY')
        nn = nb.vmath('NORMALIZE', nb.vmath('ADD', nb.vmath('SCALE', N, scale=0.45), nb.vmath('SCALE', tn, scale=0.55)))
        nz = nb.xyz(nn)[2]; ndl = nb.vmath('DOT_PRODUCT', nn, sunD)
        tone = nb.add(nb.mul(nb.math('POWER', ht, 1.2), 1.2), nb.add(nb.mul(ndl, 0.22), nb.mul(nz, 0.3)))
        tone = nb.add(tone, nb.sub(nb.mul(nb.sub(br, 0.5), 0.45), nb.add(0.36, tb)))
        col = nb.ramp(tone, [(0.0, '#1b1842'), (0.13, '#282460'), (0.3, '#3d377b'), (0.48, '#625a9e'), (0.66, '#9b8fc2'), (0.8, '#e6cfc9'), (0.91, '#fff0dc')])
        sunC = nb.attr('sunC')
        col = nb.cmul(col, nb.mixc((1, 1, 1, 1), sunC, nb.smooth(tone, 0.6, 0.8)))
        gl = None
        facing = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', nn, g.outputs['Incoming']))
        for i in (1, 2):
            fl = nb.objattr('fl%d' % i); fp = nb.objattr('fp%d' % i, 'Vector')
            dd = nb.vmath('DISTANCE', P, fp)
            rim = nb.math('POWER', nb.sub(1.0, facing), 1.3)          # lit from inside: billow edges glow, centres stay dark
            e = nb.mul(nb.mul(fl, nb.smooth(dd, 1800.0, 200.0)), nb.add(0.3, nb.mul(rim, 0.95)))
            e = nb.add(e, nb.mul(nb.sub(br, 0.5), 0.35))
            e = nb.mul(e, nb.math('GREATER_THAN', fl, 0.01))
            col = nb.mixc(col, nb.mixc(col, nb.rgb('#7a6cc8'), 0.75), nb.math('GREATER_THAN', e, 0.22))
            col = nb.mixc(col, nb.rgb('#b3a6ee'), nb.math('GREATER_THAN', e, 0.5))
            col = nb.mixc(col, nb.cscale(nb.rgb('#f6f2ff'), 1.3), nb.math('GREATER_THAN', e, 0.86))
            gi = nb.add(nb.mul(nb.math('GREATER_THAN', e, 0.5), 0.35), nb.mul(nb.math('GREATER_THAN', e, 0.86), 0.45))
            gl = gi if gl is None else nb.mx(gl, gi)
        col = nb.mixc(col, nb.mixc(col, '#dfe4ff', 0.55), nb.mul(nb.attr('flash', 'Fac'), 0.75))
        return col, None, gl
    return _mk(name, fn, paint=1.0, hz=0.3)


def rain_mat(name='M_fx_rain'):
    """rain curtain card: slanted streaks over a thin veil, ragged soft sides, fading into the cloud base and the sea.
    vertex 'uvr' = (across m, up m, seed), 'hv' = up fraction, 'hw' = across fraction (-1..1)."""
    def fn(nb):
        u, v, sd = nb.xyz(nb.attr('uvr', 'Vector', 'GEOMETRY')); hv = nb.attr('hv', 'Fac', 'GEOMETRY'); hw = nb.attr('hw', 'Fac', 'GEOMETRY')
        x = nb.add(u, nb.mul(v, 0.22))
        n1 = nb.noise(nb.vec(nb.mul(x, 0.045), nb.mul(v, 0.0012), nb.mul(sd, 7.0)), 1.0, 2.0, 0.5, 0.0)
        n2 = nb.noise(nb.vec(nb.mul(x, 0.0035), nb.mul(v, 0.0006), nb.add(nb.mul(sd, 3.0), 5.0)), 1.0, 2.0, 0.5, 0.0)
        st = nb.math('GREATER_THAN', nb.add(nb.mul(n1, 0.65), nb.mul(n2, 0.45)), 0.58)
        body = nb.smooth(n2, 0.32, 0.55)
        edge = nb.add(0.42, nb.mul(nb.noise(nb.vec(nb.mul(v, 0.0015), nb.mul(sd, 2.0), nb.mul(hw, 0.4)), 1.0, 2.0, 0.5, 0.0), 0.75))
        side = nb.smooth(nb.math('ABSOLUTE', hw), nb.add(edge, 0.22), nb.sub(edge, 0.25))
        fade = nb.mul(nb.mul(nb.smooth(hv, 1.0, 0.84), nb.smooth(hv, 0.0, 0.06)), side)
        a = nb.mul(nb.add(nb.mul(body, 0.34), nb.mul(st, 0.26)), fade)
        col = nb.mixc(nb.rgb('#36336f'), nb.rgb('#5a578f'), st)
        col = nb.mixc(col, nb.rgb('#8d8bbd'), nb.smooth(hv, 0.22, 0.0))
        col = nb.mixc(col, nb.mixc(col, '#dfe4ff', 0.6), nb.attr('flash', 'Fac'))
        return col, a, 0.0
    def setup(m):
        m.use_backface_culling = False
    return _mk(name, fn, paint=1.0, blend=True, setup=setup, hz=0.3)


def spout_mat(name='M_fx_spout'):
    """the waterspout funnel: helical stripes scrolling with prop 'twist', drawn-light tones, mostly opaque (blended at 0.85,
    solid at the silhouette), darker into the cloud at the top, white spray at the foot. vertex 'cd' = (cos th, sin th, v)."""
    def fn(nb):
        g = nb.geo(); N = g.outputs['Normal']; I = g.outputs['Incoming']
        cx, cy, v = nb.xyz(nb.attr('cd', 'Vector', 'GEOMETRY'))
        th = nb.math('ARCTAN2', cy, cx)
        tw = nb.objattr('twist')
        ph = nb.add(nb.mul(nb.sub(th, tw), 3.0 / TAU), nb.mul(v, 5.0))
        wob = nb.noise(nb.vec(nb.mul(cx, 1.3), nb.mul(cy, 1.3), nb.mul(v, 12.0)), 1.0, 2.0, 0.5, 0.0)
        st = nb.math('GREATER_THAN', nb.math('FRACT', nb.add(ph, nb.mul(wob, 0.5))), 0.6)
        fine = nb.math('GREATER_THAN', nb.math('FRACT', nb.add(nb.mul(ph, 3.0), nb.mul(wob, 1.1))), 0.82)
        L = _dlight(nb, 0.55)
        s = nb.add(nb.mul(nb.vmath('DOT_PRODUCT', N, L), 0.9), nb.mul(nb.sub(wob, 0.5), 0.3))
        s = nb.sub(s, nb.add(nb.mul(st, 0.38), nb.mul(fine, 0.2)))
        s = nb.sub(s, nb.mul(nb.smooth(v, 0.42, 0.88), 0.95))
        col = nb.ramp(nb.add(nb.mul(s, 0.5), 0.5), [(0.0, '#3f3b78'), (0.24, '#5f5b9c'), (0.42, '#8d8cc4'), (0.6, '#c2c3e6'), (0.78, '#eceefb')])
        col = nb.mixc(col, nb.rgb('#f7f9ff'), nb.mul(nb.smooth(v, 0.06, 0.0), 0.85))
        fac = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', N, I))
        a = nb.add(0.84, nb.mul(nb.mx(nb.math('LESS_THAN', fac, 0.42), nb.smooth(v, 0.7, 0.85)), 0.14))
        col = nb.mixc(col, nb.mixc(col, '#e6ecff', 0.6), nb.mul(nb.attr('flash', 'Fac'), 0.7))
        return col, a, 0.0
    def setup(m):
        m.use_backface_culling = True
    return _mk(name, fn, blend=True, setup=setup)


def spfoam_mat(name='M_fx_spfoam'):
    """the foam spiral round the waterspout foot (rotates with the object). vertex rp, ra."""
    def fn(nb):
        rp = nb.attr('rp', 'Vector', 'GEOMETRY'); ra = nb.attr('ra', 'Fac', 'GEOMETRY')
        x, y, _ = nb.xyz(rp)
        th = nb.math('ARCTAN2', y, x)
        arms = nb.math('SINE', nb.add(nb.mul(th, 3.0), nb.mul(nb.math('LOGARITHM', nb.mx(ra, 0.01), 2.718281828), 5.0)))
        l1 = nb.noise(nb.vmath('SCALE', rp, scale=14.0), 1.0, 3.0, 0.62, 0.3)
        dens = nb.add(nb.mul(nb.mul(nb.add(nb.mul(arms, 0.5), 0.5), nb.smooth(ra, 1.0, 0.45)), 0.85), nb.mul(nb.smooth(ra, 0.3, 0.12), 0.9))
        F = nb.add(dens, nb.mul(nb.sub(l1, 0.5), 1.2))
        col = nb.mixc(nb.rgb('#bfe6f2'), nb.rgb('#ffffff'), nb.math('GREATER_THAN', F, 0.62))
        return col, nb.math('GREATER_THAN', F, 0.42), 0.0
    return _mk(name, fn)


# ================================================================================================================ lightning
def _jag(a, b, R, rough=0.22, levels=5):
    """lightning leg: long straight runs and sharp kinks (midpoint displacement, both perpendicular axes)."""
    a = np.asarray(a, np.float64); b = np.asarray(b, np.float64)
    d = b - a; L = np.linalg.norm(d); dn = d / max(L, 1e-9)
    ref = np.array([0.0, 0.0, 1.0]) if abs(dn[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    U = _nrm(np.cross(dn, ref)); W = np.cross(dn, U)
    pts = [a, b]; amp = L * rough
    for _ in range(levels):
        nx = [pts[0]]
        for i in range(len(pts) - 1):
            p, q = pts[i], pts[i + 1]
            m = p + (q - p) * R.uniform(0.3, 0.7) + U * R.uniform(-1, 1) * amp + W * R.uniform(-1, 1) * amp
            nx += [m, q]
        pts = nx; amp *= 0.5
    return np.array(pts)


def bolt(name, p0, p1, seed=1, branches=4, width=1.0, coll=None, rough=0.2, star=True, mat=None, star_size=None, taper=0.0):
    """Lightning from p0 (cloud) to p1 (strike point): a jagged main channel with forks (and sub-forks), and a drawn
    starburst at p1 (child object '<name>_kira', a camera-facing impostor, see kira()).
    One mesh, origin at p0. White-hot core, cyan + violet bands, dark rim (glow AOV -> bloom).
    Props: 'power' (0..1+; 0 = hidden). Branches carry vertex 'lvl' (0.3..0.9) so they die first as power falls.
    Radius = 0.0035 * length * width (a 900 m bolt is ~6 m thick); star radius 0.1 * length * width. taper: the main
    channel narrows over its last fifth to (1 - taper) x (0.7 x radius) at p1 (a small target: the end bites into it).
    Visible (power 1) until flicker() keys it (flicker keys the star too)."""
    R = np.random.RandomState(seed)
    p0 = np.asarray(p0, np.float64); p1 = np.asarray(p1, np.float64)
    L = np.linalg.norm(p1 - p0); r0 = 0.0035 * L * width
    Vs, Fs, LV, SS = [], [], [], []
    nv = 0

    def add(V, F, lvl, s):
        nonlocal nv
        Vs.append(V); Fs.append(F + nv); LV.append(np.full(len(V), lvl)); SS.append(np.full(len(V), s)); nv += len(V)

    main = _jag(p0, p1, R, rough, 5)
    n = len(main); sv = np.linspace(0, 1, n)
    V, F = _tube(main, r0 * (1.0 - 0.3 * sv) * (1 + 0.15 * R.uniform(-1, 1, n)) * (1.0 - taper * _sm((sv - 0.8) / 0.2)), 8)
    add(V, F, 0.0, 0.0)
    down = _nrm(p1 - p0)
    for b in range(branches):
        i0 = int(R.uniform(0.1, 0.72) * (n - 1)); s0 = main[i0]
        side = _nrm(np.cross(down, _nrm(R.normal(size=3))))
        dirb = _nrm(down * R.uniform(0.55, 0.9) + side * R.uniform(0.45, 0.95))
        lb = L * R.uniform(0.16, 0.4) * (1.0 - 0.5 * i0 / n)
        pts = _jag(s0, s0 + dirb * lb, R, rough * 1.25, 4)
        m = len(pts); lvl = R.uniform(0.3, 0.85)
        V, F = _tube(pts, r0 * 0.55 * np.linspace(1.0, 0.25, m), 6)
        add(V, F, lvl, 0.0)
        if R.uniform() < 0.6:
            j0 = int(R.uniform(0.2, 0.6) * (m - 1)); q0 = pts[j0]
            d2 = _nrm(dirb + _nrm(R.normal(size=3)) * 0.8 + down * 0.3)
            pts2 = _jag(q0, q0 + d2 * lb * R.uniform(0.3, 0.55), R, rough * 1.3, 3)
            V, F = _tube(pts2, r0 * 0.3 * np.linspace(1.0, 0.2, len(pts2)), 5)
            add(V, F, min(lvl + 0.12, 0.95), 0.0)
    V = np.vstack(Vs) - p0; F = np.vstack(Fs)
    o = _mesh(name, V, F, coll, mat or glow_mat(), loc=tuple(p0), attrs={'lvl': np.concatenate(LV), 'sv': np.concatenate(SS)})
    o['power'] = 1.0
    if star:
        ss = star_size or 0.1 * L * width
        k = kira(name + '_kira', p1 + np.array([0, 0, ss * 0.3]), ss, coll, seed=seed)
        k.parent = o; k.location = tuple(p1 + np.array([0, 0, ss * 0.3]) - p0)
    return o


def kira_mat(name=None, inner='#ffffff', outer='#5fe3ff', n=11, core=2.6):
    """a drawn starburst on a camera-facing impostor: the sphere's pixels are mapped to camera-plane coordinates round
    the object's origin, so the star is always flat to the camera (like a drawn 'kira'). Outer star in `outer` with n
    uneven spikes, inner white-hot star (HDR) between them; hard alpha, glow AOV 1. Object props: power (scales the star),
    rad (sphere radius, m), rot (spin, radians), sd (seed)."""
    name = name or 'M_fx_kira_%s_%s' % (inner.strip('#'), outer.strip('#'))
    def fn(nb):
        g = nb.geo(); oi = nb.N.new('ShaderNodeObjectInfo')
        rel = nb.vmath('SUBTRACT', g.outputs['Position'], oi.outputs['Location'])
        vt = nb.new('ShaderNodeVectorTransform', props={'vector_type': 'VECTOR', 'convert_from': 'WORLD', 'convert_to': 'CAMERA'})
        nb.put(vt.inputs['Vector'], rel)
        x, y, _ = nb.xyz(vt.outputs['Vector'])
        Rr = nb.mul(nb.objattr('rad'), nb.mx(nb.objattr('power'), 0.02))
        r = nb.math('DIVIDE', nb.vmath('LENGTH', nb.vec(x, y, 0.0)), Rr)
        a = nb.add(nb.math('ARCTAN2', y, x), nb.objattr('rot'))
        sd = nb.objattr('sd')

        def star(off, base, amp, p, so):
            k = nb.add(nb.mul(a, n / TAU), off)
            idx = nb.math('FLOOR', nb.add(k, 0.5))
            tri = nb.sub(1.0, nb.mul(nb.math('ABSOLUTE', nb.sub(k, idx)), 2.0))
            im = nb.math('MODULO', nb.add(idx, 10.0 * n), float(n))
            ln = nb.noise(nb.vec(nb.add(nb.mul(im, 0.731), 0.17), nb.add(sd, so), 0.37), 1.0, 0.0, 0.5, 0.0)
            ln = nb.remap(ln, 0.3, 0.7, 0.3, 1.0)
            return nb.add(base, nb.mul(nb.math('POWER', tri, p), nb.mul(ln, amp)))
        Lo = star(0.0, 0.24, 0.7, 2.0, 0.0)
        Li = star(0.5, 0.15, 0.38, 2.6, 5.0)
        ino = nb.math('LESS_THAN', r, Lo); ini = nb.math('LESS_THAN', r, nb.mx(Li, 0.2))
        col = nb.mixc(nb.rgb(outer), nb.cscale(nb.rgb(inner), core), ini)
        col = nb.cscale(col, nb.add(0.4, nb.mul(nb.math('MINIMUM', nb.objattr('power'), 1.0), 0.6)))
        return col, ino, 1.0
    def setup(m):
        m.use_backface_culling = True
    return _mk(name, fn, setup=setup)


def kira(name, pos, size, coll=None, inner='#ffffff', outer='#5fe3ff', n=11, seed=0, rot=None):
    """A drawn starburst flash at pos, radius `size` m, always flat to the camera (impostor sphere, kira_mat). Props
    power (1 = full size; key it with flicker()), rot. Hidden only through power/flicker or hide keys."""
    R = np.random.RandomState(seed + 17); V0, F0 = _ico(3)
    o = _mesh(name, V0 * size, F0, coll, kira_mat(None, inner, outer, n), loc=tuple(_xyz(pos)))
    o['power'] = 1.0; o['rad'] = float(size); o['rot'] = float(R.uniform(0, TAU) if rot is None else rot); o['sd'] = float(R.uniform(0, 50))
    return o


FLICKER = (1.0, 0.2, 1.0, 0.6, 0.3)     # strike, gap, re-strike, fade, fade (each held 3 frames), then off


def flicker(obj, frames, pattern=FLICKER, sc=None, flash=0.0, step=STEP):
    """Key 'power' (and hide_render/hide_viewport at 0) on threes for each strike frame in `frames`:
    default pattern = strike 1.0, gap 0.2, re-strike 1.0, fade 0.6, 0.3, off. A later strike overrides the tail of an
    earlier one. sc + flash>0: also key the scene uniform 'flash' = power*flash on the same frames (CONSTANT)."""
    objs = obj if isinstance(obj, (list, tuple)) else [obj]
    objs = objs + [c for o in objs for c in o.children if 'power' in c.keys()]
    tl = {}
    for f in sorted(int(x) for x in frames):
        for k in [k for k in tl if k >= f]: del tl[k]
        for i, p in enumerate(pattern): tl[f + i * step] = float(p)
        tl[f + len(pattern) * step] = 0.0
    keys = sorted(tl.items())
    if not keys: return 0
    keys = [(keys[0][0] - 1, 0.0)] + keys
    for o in objs:
        for f, p in keys:
            o['power'] = p; o.keyframe_insert('["power"]', frame=f)
            for a in ('hide_render', 'hide_viewport'):
                setattr(o, a, p <= 0.0); o.keyframe_insert(a, frame=f)
        _interp(o, 'CONSTANT', ('["power"]',))
    if sc is not None and flash > 0:
        for f, p in keys:
            sc['flash'] = p * flash; sc.keyframe_insert('["flash"]', frame=f)
        _interp(sc, 'CONSTANT', ('["flash"]',))
    return keys[-1][0]


# ================================================================================================================ storm wall
def _tower_puffs(R, c, rad_dir, tan_dir, width, height, lean=0.0, detail=1.0, R0=None, depth=0.6):
    """cumulus tower puffs (x, y, z, r) like env.cumulus, spread along tan_dir, base centre c."""
    cx, cy, cz = c
    R0 = R0 or max(width, height) * 0.16
    rows = max(1, int(round(height / (R0 * 0.9)))); out = []
    for k in range(rows + 1):
        f = k / rows
        z = cz + R0 * 0.55 + f * (height - R0 * 1.35)
        w = max(R0 * 0.6, width * (1 - 0.42 * f * f))
        n = max(1, int(round(w / (R0 * 1.12))))
        for i in range(n):
            u = 0 if n == 1 else i / (n - 1) - 0.5
            off = lean * f * height + u * (w - R0) + R.uniform(-0.3, 0.3) * R0
            dep = R.uniform(-0.45, 0.45) * w * 0.5 * depth
            r = R0 * R.uniform(0.8, 1.15) * (1 - 0.2 * f)
            out.append((cx + tan_dir[0] * off + rad_dir[0] * dep, cy + tan_dir[1] * off + rad_dir[1] * dep, z + R.uniform(-0.3, 0.3) * R0, r))
    body = len(out)
    for i in range(int(body * 1.6 * detail)):
        x, y, z, r = out[i % body]
        if z < cz + height * 0.25 or R.uniform() < 0.35: continue
        a = R.uniform(0.25, math.pi - 0.25); b = R.uniform(0, TAU)
        out.append((x + math.cos(a) * math.cos(b) * r * 0.85, y + math.cos(a) * math.sin(b) * r * 0.85, z + math.sin(a) * r * 0.8, r * R.uniform(0.32, 0.5)))
    return out


def _spheres(puffs, big=320.0):
    """puffs [(x, y, z, r[, top, tid, zscale])] -> V, F, RP, puff index per vertex (big ones get the finer sphere)."""
    Vs, Fs, RPs, PI = [], [], [], []; nv = 0
    for i, p in enumerate(puffs):
        x, y, z, r = p[:4]; zs = p[6] if len(p) > 6 else 1.0
        V0, F0 = _ico(4 if r > big else 3)
        Vs.append(V0 * (r, r, r * zs) + (x, y, z)); Fs.append(F0 + nv); RPs.append(V0 * (r / 400.0) + (i * 3.17, i * 1.31, 0)); PI.append(np.full(len(V0), i)); nv += len(V0)
    return np.vstack(Vs), np.vstack(Fs), np.vstack(RPs), np.concatenate(PI)


def _flatten_below(V, z0, k=0.06):
    zb = V[:, 2] < z0
    V[zb, 2] = z0 + (V[zb, 2] - z0) * k
    return V


def storm_wall(coll=None, origin=(0.0, 0.0), az=(206.0, 334.0), dist=(8200.0, 11000.0), base=900.0, top=(1900.0, 5600.0),
               seed=7, towers=9, anvils=2, shelf=True, rain=18, bolts=4, name='FX_storm'):
    """The western storm: cumulonimbus towers on an arc (compass azimuths az, 270 = west) at dist (m) from origin, a continuous
    flat dark base at z=base, sunlit cauliflower tops (sun low in the east), anvils on the tallest, a tiered shelf cloud ~1.5 km
    in front of the base, rain curtains (blended streak cards with ragged sides) under it, `bolts` cloud-to-ground bolts
    (hidden until storm_flash / flicker keys them). Inner flashes: object props fl1/fl2 (0..1) at fp1/fp2 (world xyz) on
    S['mass'] and S['shelf'] - use storm_flash(). Everything is parented to S['root'] (move/rotate the whole storm).
    Returns dict: root, mass, shelf, rain[list], bolts[list], cells[list of world xyz for flashes]."""
    C = _coll(coll); R = np.random.RandomState(seed); ox, oy = origin
    root = _empty(name + '_root', (ox, oy, 0.0), C, size=200.0)
    mat = storm_mat()
    puffs = []; cells = []; TW = []
    span = az[1] - az[0]
    us = (np.arange(towers) + R.uniform(0.2, 0.8, towers)) / towers
    bell = np.exp(-((us - 0.55) / 0.38) ** 2)
    Hs = top[0] + (top[1] - top[0]) * (0.2 + 0.8 * bell) * R.uniform(0.5, 1.08, towers)
    tall = set(np.argsort(-Hs)[:anvils].tolist())
    for i in range(towers):
        H = Hs[i]; Wd = R.uniform(1900, 3600) * (0.8 + 0.35 * H / top[1]); d = R.uniform(dist[0], dist[1])
        a = math.radians(az[0] + span * us[i]); rd = (math.sin(a), math.cos(a)); td = (math.cos(a), -math.sin(a))
        cx, cy = ox + rd[0] * d, oy + rd[1] * d
        lean = R.uniform(-0.07, 0.07)
        tp = _tower_puffs(R, (cx, cy, base), rd, td, Wd, H, lean=lean, detail=1.0, depth=0.7, R0=Wd * 0.21)
        tid = len(TW)
        puffs += [(x, y, z, r, base + H, tid) for (x, y, z, r) in tp]
        if i in tall:   # anvil: wide flat billows spreading at the top
            na = 13
            for k in range(na):
                s_ = (k / (na - 1) - 0.42) * 2.0
                off = s_ * Wd * 1.35 + lean * H; dep = R.uniform(-0.35, 0.35) * Wd * 0.6
                z = base + H * R.uniform(0.9, 0.98) - abs(s_) * H * 0.06
                r = Wd * R.uniform(0.2, 0.28) * (1 - 0.3 * abs(s_))
                puffs.append((cx + td[0] * off + rd[0] * dep, cy + td[1] * off + rd[1] * dep, z, r, base + H, tid, 0.38))
        TW.append((np.array([cx + td[0] * lean * H * 0.5, cy + td[1] * lean * H * 0.5, base + H * 0.42]), np.array([td[0], td[1], 0.0]),
                   np.array([rd[0], rd[1], 0.0]), np.array([Wd * 0.6, Wd * 0.42, H * 0.58])))
        for _ in range(3): cells.append((cx + R.uniform(-0.3, 0.3) * Wd * td[0], cy + R.uniform(-0.3, 0.3) * Wd * td[1], base + R.uniform(300, 0.5 * H)))
    # a continuous flat base along the whole arc
    nbs = int(span / 4.0)
    for j in range(nbs):
        a = math.radians(az[0] + 2 + (span - 4) * (j + R.uniform(0.2, 0.8)) / nbs)
        d = R.uniform(dist[0] - 300, dist[0] + 1000); r = R.uniform(650, 1000)
        puffs.append((ox + math.sin(a) * d, oy + math.cos(a) * d, base + r * 0.3, r, base + 1700.0, -1, 0.8))
    V, F, RP, PI = _spheres(puffs)
    V = _flatten_below(V, base)
    tops = np.array([p[4] for p in puffs])[PI]
    ht = np.clip((V[:, 2] - base) / np.maximum(tops - base, 1.0), 0, 1)
    tone = np.where(V[:, 2] < base + 60.0, 0.12, 0.0)
    tid = np.array([p[5] for p in puffs])[PI]; TN = np.zeros_like(V)
    for i, (tc, ta, tb, trad) in enumerate(TW):
        sel = tid == i; rel = V[sel] - tc
        loc = np.stack([rel @ ta, rel @ tb, rel[:, 2]], 1) / trad ** 2
        TN[sel] = _nrm(ta[None] * loc[:, :1] + tb[None] * loc[:, 1:2] + np.array([0, 0, 1.0])[None] * loc[:, 2:3])
    mass = _mesh(name + '_mass', V - (ox, oy, 0), F, C, mat, (ox, oy, 0.0), attrs={'ht': ht, 'rp': RP, 'tone': tone, 'tn': TN})
    md = mass.modifiers.new('lumps', 'DISPLACE'); tx = D.textures.new(name + '_tx', 'CLOUDS'); tx.noise_scale = 380.0; tx.noise_depth = 2
    md.texture = tx; md.strength = 150.0; md.mid_level = 0.5; md.texture_coords = 'GLOBAL'
    mass['fl1'] = 0.0; mass['fl2'] = 0.0; mass['fp1'] = (0.0, 0.0, -1e5); mass['fp2'] = (0.0, 0.0, -1e5)
    mass.parent = root; mass.location = (0, 0, 0)
    out = {'root': root, 'mass': mass, 'shelf': None, 'rain': [], 'bolts': [], 'cells': cells}
    # ---- shelf cloud: tiers of flattened billows stepping up and back, ragged flat underside hanging below the base
    if shelf:
        sp = []; z_low = base - 230.0
        ds0 = dist[0] - 1500.0
        for tier, (dd, dz, rr, zs) in enumerate(((0.0, -120.0, 400.0, 0.36), (420.0, 110.0, 470.0, 0.4), (850.0, 330.0, 560.0, 0.45))):
            arc = math.radians(span - 10) * (ds0 + dd)
            nb_ = int(arc / (rr * 1.05))
            for j in range(nb_):
                q = (j + R.uniform(0.3, 0.7)) / nb_
                endk = _sm(min(q, 1 - q) / 0.06)
                a = math.radians(az[0] + 5 + (span - 10) * q)
                d = ds0 + dd + 160 * math.sin(q * 9.0 + tier) + R.uniform(-90, 90)
                r = rr * R.uniform(0.75, 1.25) * (0.5 + 0.5 * endk)
                sp.append((ox + math.sin(a) * d, oy + math.cos(a) * d, base + dz + R.uniform(-40, 40) - (1 - endk) * 120, r, 0.0, -1, zs))
        V, F, RP, PI = _spheres(sp, 380.0)
        V = _flatten_below(V, z_low, 0.05)
        ht = np.clip((V[:, 2] - z_low) / 1500.0, 0, 1) * 0.75
        tone = np.where(V[:, 2] < z_low + 40.0, 0.1, 0.0)
        sh = _mesh(name + '_shelf', V - (ox, oy, 0), F, C, mat, (ox, oy, 0.0), attrs={'ht': ht, 'rp': RP + 50.0, 'tone': tone, 'tn': np.zeros((len(V), 3))})
        mds = sh.modifiers.new('lumps', 'DISPLACE'); mds.texture = tx; mds.strength = 90.0; mds.mid_level = 0.5; mds.texture_coords = 'GLOBAL'
        sh['fl1'] = 0.0; sh['fl2'] = 0.0; sh['fp1'] = (0.0, 0.0, -1e5); sh['fp2'] = (0.0, 0.0, -1e5)
        sh.parent = root; sh.location = (0, 0, 0)
        out['shelf'] = sh
    # ---- rain curtains: two rows of cards facing the origin (rows never cross), ragged soft sides in the shader
    if rain:
        rm = rain_mat()
        for row, (d0_, d1_) in enumerate(((dist[0] - 1250, dist[0] - 950), (dist[0] - 350, dist[0] + 150))):
            nrow = rain // 2 + (rain % 2 if row == 0 else 0)
            sp_ = span - 14
            for k in range(nrow):
                a = math.radians(az[0] + 7 + sp_ * (k + R.uniform(0.2, 0.8)) / nrow)
                d = R.uniform(d0_, d1_); w = min(R.uniform(700, 1500), d * math.radians(sp_ / nrow) * 1.15)
                rd = np.array([math.sin(a), math.cos(a), 0]); td = np.array([math.cos(a), -math.sin(a), 0])
                ctr = np.array([ox, oy, 0]) + rd * d
                h0, h1 = -15.0, base + 60.0; nu, nv_ = 3, 6
                us_ = np.linspace(-0.5, 0.5, nu); vs = np.linspace(0, 1, nv_)
                UU, VV = np.meshgrid(us_, vs, indexing='ij')
                P = ctr[None, None, :] + td[None, None, :] * (UU * w)[..., None] + np.array([0, 0, 1.0])[None, None, :] * (h0 + VV * (h1 - h0))[..., None]
                P = P.reshape(-1, 3)
                I, J = np.meshgrid(np.arange(nu - 1), np.arange(nv_ - 1), indexing='ij')
                a_ = I * nv_ + J; b_ = (I + 1) * nv_ + J; c_ = (I + 1) * nv_ + J + 1; d_ = I * nv_ + J + 1
                F = np.vstack([np.stack([a_, b_, c_], -1).reshape(-1, 3), np.stack([a_, c_, d_], -1).reshape(-1, 3)])
                sd = R.uniform(0, 10)
                uvr = np.stack([(UU * w).ravel(), (h0 + VV * (h1 - h0)).ravel(), np.full(nu * nv_, sd)], -1)
                o = _mesh('%s_rain%02d' % (name, len(out['rain'])), P - ctr, F, C, rm, tuple(ctr), smooth=False,
                          attrs={'uvr': uvr, 'hv': VV.ravel(), 'hw': (UU * 2.0).ravel()})
                o.parent = root; o.location = tuple(ctr - np.array([ox, oy, 0]))
                out['rain'].append(o)
    # ---- cloud-to-ground bolts under the base (power 0 until storm_flash)
    for k in range(bolts):
        a = math.radians(az[0] + 12 + (span - 24) * (k + R.uniform(0.2, 0.8)) / max(bolts, 1))
        d = R.uniform(dist[0] - 1200, dist[0] - 300)
        p0 = (ox + math.sin(a) * d, oy + math.cos(a) * d, base + 60.0)
        p1 = (p0[0] + R.uniform(-250, 250), p0[1] + R.uniform(-250, 250), 0.0)
        b = bolt('%s_bolt%d' % (name, k), p0, p1, seed=seed * 31 + k, branches=5, width=2.2, coll=C)
        for o_ in [b] + list(b.children):
            o_['power'] = 0.0; o_.hide_render = True; o_.hide_viewport = True
        b.parent = root; b.location = (p0[0] - ox, p0[1] - oy, p0[2])
        out['bolts'].append(b)
    return out


def storm_flash(S, frames, seed=0, bolts=True, sc=None, flash=0.0, pattern=(1.0, 0.35, 0.85, 0.3)):
    """Key the storm's inner flashes (fl1/fl2 at random cells) on threes, one flash per frame in `frames`, alternating
    the two slots; with bolts=True every second flash also fires one of the storm's bolts (flicker). sc+flash: scene
    'flash' too (strongest wins)."""
    R = np.random.RandomState(seed); objs = [o for o in (S.get('mass'), S.get('shelf')) if o is not None]
    cells = S.get('cells') or [(0, 0, 1500)]
    tl = {1: {}, 2: {}}; pos = {1: [], 2: []}; bolt_frames = {}; scene = {}
    for i, f in enumerate(sorted(int(x) for x in frames)):
        slot = 1 + i % 2
        for k in [k for k in tl[slot] if k >= f]: del tl[slot][k]
        for j, p in enumerate(pattern): tl[slot][f + 3 * j] = p
        tl[slot][f + 3 * len(pattern)] = 0.0
        pos[slot].append((f, cells[R.randint(len(cells))]))
        for j, p in enumerate(pattern): scene[f + 3 * j] = max(scene.get(f + 3 * j, 0.0), p)
        scene.setdefault(f + 3 * len(pattern), 0.0)
        if bolts and S.get('bolts') and i % 2 == 0:
            b = S['bolts'][(i // 2) % len(S['bolts'])]; bolt_frames.setdefault(b.name, (b, []))[1].append(f + 3)
    for o in objs:
        for slot in (1, 2):
            ks = sorted(tl[slot].items())
            if not ks: continue
            ks = [(ks[0][0] - 1, 0.0)] + ks
            for f, p in ks: o['fl%d' % slot] = p; o.keyframe_insert('["fl%d"]' % slot, frame=f)
            for f, c in pos[slot]: o['fp%d' % slot] = tuple(c); o.keyframe_insert('["fp%d"]' % slot, frame=f)
        _interp(o, 'CONSTANT', ('["fl1"]', '["fl2"]', '["fp1"]', '["fp2"]'))
    for b, fr in bolt_frames.values(): flicker(b, fr)
    if sc is not None and flash > 0:
        for f, p in sorted(scene.items()): sc['flash'] = p * flash; sc.keyframe_insert('["flash"]', frame=f)
        _interp(sc, 'CONSTANT', ('["flash"]',))


# ================================================================================================================ waterspout
def waterspout(coll=None, root=(-2300.0, -1700.0), height=900.0, seed=3, r_min=26.0, r_top=190.0, r_base=46.0, bend=55.0, debris=30,
               collar=True, name='FX_spout'):
    """A waterspout: funnel from the cloud base (height) to the sea at root (x, y): a tapering, S-bent rope with helical
    stripes (blended, mostly opaque); a big spray skirt at the foot (a lobed spray bell ~3.4 x r_base = ~155 m tall with
    billows heaped inside it, climbing the funnel, thrown over its rim and ringed on the sea, plus droplets; one static mesh
    rotating and boiling with twist); a foam spiral on the sea; a wide flat dark collar cloud (~1.6 km) with a lowered wall
    cloud round the funnel top; debris spiralling up (wrapping inside the skirt and the collar, so nothing pops).
    Returns dict: root, top, funnel, skirt, foam, collar (if collar), debris [list].
    Animate: W['root'] location (moves everything), W['top'] location relative to the root (bends the upper funnel with a
    hook; the collar follows it), W['root']['twist'] (radians; stripes, skirt, foam and debris all follow it through
    drivers) - spout_spin() keys it on threes."""
    C = _coll(coll); R = np.random.RandomState(seed)
    rt = _empty(name + '_root', (root[0], root[1], 0.0), C, size=40.0); rt['twist'] = 0.0
    tp = _empty(name + '_top', (0, 0, height), C, parent=rt, size=40.0)
    # ---- funnel
    NV, NU = 110, 48; Hf = height + 70.0
    v = np.linspace(0, 1, NV); z = v * Hf - 6.0
    th = np.arange(NU) / NU * TAU
    s1, s2, s3 = R.uniform(0, 6.28, 3)
    r = r_min * (1 + 0.1 * np.sin(v * 6.3 + s1) + 0.05 * np.sin(v * 17 + s2)) + (r_base - r_min) * np.exp(-np.clip(z, 0, None) / 38.0) \
        + (r_top - r_min) * v ** 5.0
    rope = 1 + 0.07 * np.sin(3 * th[None, :] - z[:, None] * 0.05)
    mx = bend * np.sin(v * 3.1 + s3) * np.sin(v * math.pi); my = bend * 0.5 * np.sin(v * 2.3 + s1) * np.sin(v * math.pi)
    X = r[:, None] * rope * np.cos(th)[None, :] + mx[:, None]; Y = r[:, None] * rope * np.sin(th)[None, :] + my[:, None]
    Z = np.repeat(z[:, None], NU, 1)
    V = np.stack([X, Y, Z], -1).reshape(-1, 3)
    I, J = np.meshgrid(np.arange(NV - 1), np.arange(NU), indexing='ij')
    a_ = I * NU + J; b_ = I * NU + (J + 1) % NU; c_ = (I + 1) * NU + (J + 1) % NU; d_ = (I + 1) * NU + J
    F = np.vstack([np.stack([a_, b_, c_], -1).reshape(-1, 3), np.stack([a_, c_, d_], -1).reshape(-1, 3)])
    cd = np.stack([np.tile(np.cos(th), NV), np.tile(np.sin(th), NV), np.repeat(v, NU)], -1)
    fn = _mesh(name + '_funnel', V, F, C, spout_mat(), attrs={'cd': cd})
    fn.parent = rt; fn.location = (0, 0, 0); fn['twist'] = 0.0
    _driver(fn, '["twist"]', rt, '["twist"]')
    vg = fn.vertex_groups.new(name='top'); w = _sm((np.repeat(v, NU) - 0.06) / 0.94) ** 1.2
    for wi in np.unique(np.round(w, 3)):
        idx = np.nonzero(np.abs(np.round(w, 3) - wi) < 1e-9)[0].tolist()
        if wi > 0: vg.add(idx, float(wi), 'REPLACE')
    bpy.context.view_layer.update()
    hk = fn.modifiers.new('bend', 'HOOK'); hk.object = tp; hk.vertex_group = 'top'; hk.falloff_type = 'NONE'
    hk.center = (0, 0, height); hk.matrix_inverse = tp.matrix_world.inverted() @ fn.matrix_world
    out = {'root': rt, 'top': tp, 'funnel': fn}
    # ---- skirt: the spray bell at the foot: a lobed sheet flaring out, billows heaped inside it and thrown out over its rim,
    #      a ring of spray billows on the sea, droplets; rotates and boils with twist (static mesh, drivers)
    wm = water_mat('M_fx_skirt', PAL_SKIRT, edges=(0.3, 0.46, 0.68))
    parts = []          # (V, F, attrs)
    Hs = 3.4 * r_base; rb = r_base * 1.05; Rt = r_base * 2.9
    NC, NR = 64, 10; K = 9
    phi = (np.arange(K) + R.uniform(-0.3, 0.3, K)) / K * TAU; wk = math.pi / K * R.uniform(0.8, 1.1, K); ak = R.uniform(0.55, 1.0, K)
    thc = np.arange(NC) / NC * TAU
    dth = (thc[:, None] - phi[None, :] + math.pi) % TAU - math.pi
    ftop = np.max(ak[None, :] * np.clip(1 - (np.abs(dth) / wk[None, :]) ** 2, 0, 1) ** 0.5, axis=1)
    vj = np.linspace(0, 1, NR + 1)
    zt = Hs * (0.6 + 0.4 * ftop)
    zz = zt[None, :] * vj[:, None] - 2.0 * (1 - vj[:, None])
    rr = rb + (Rt - rb) * np.clip(zz / Hs, 0, None) ** 1.4 * (1 + 0.06 * np.sin(3 * thc + s2))[None, :]
    Vb = np.stack([rr * np.cos(thc)[None, :], rr * np.sin(thc)[None, :], zz], -1).reshape(-1, 3)
    J, I = np.meshgrid(np.arange(NR), np.arange(NC), indexing='ij')
    a_ = J * NC + I; b_ = J * NC + (I + 1) % NC; c_ = (J + 1) * NC + (I + 1) % NC; d_ = (J + 1) * NC + I
    Fb = np.vstack([np.stack([a_, b_, c_], -1).reshape(-1, 3), np.stack([a_, c_, d_], -1).reshape(-1, 3)])
    VV = np.repeat(vj, NC); TT = np.tile(thc, NR + 1)
    parts.append((Vb, Fb, {'rp': np.stack([np.cos(TT) * 6.0, np.sin(TT) * 6.0, VV * 0.7], -1) + 30.0, 'tone': 0.14 * (1 - VV) ** 2,
                           'bk': np.full(len(VV), 1.35), 'seed': np.zeros(len(VV))}))
    tpl = tpl_billow(seed + 11, 3, 3); Vt, Ft, RPt = tpl

    def billows(P, sz, zs, tilt, tn_):
        n_ = len(P); azs = np.arctan2(P[:, 1], P[:, 0])
        Tl = _rot(np.stack([-np.sin(azs), np.cos(azs), np.zeros(n_)], 1), tilt)
        M = _scale(Tl @ _rot(np.tile([[0, 0, 1.0]], (n_, 1)), R.uniform(0, TAU, n_)), sz, sz, sz * zs)
        parts.append(((np.einsum('nij,mj->nmi', M, Vt) + P[:, None, :]).reshape(-1, 3), (Ft[None] + (np.arange(n_) * len(Vt))[:, None, None]).reshape(-1, 3),
                      {'rp': (RPt[None] + R.uniform(-60, 60, (n_, 3))[:, None, :]).reshape(-1, 3), 'tone': np.repeat(tn_ + R.uniform(0, 0.06, n_), len(Vt)),
                       'bk': np.full(n_ * len(Vt), 1.0), 'seed': np.repeat(R.uniform(0, 1, n_), len(Vt))}))

    def ring(n_, ra, zr, size, zs, tilt, tn_):
        azs = (np.arange(n_) + R.uniform(0.1, 0.9, n_)) / n_ * TAU
        rad = R.uniform(*ra, n_); zz_ = R.uniform(*zr, n_)
        P = np.stack([np.cos(azs) * rad + np.interp(zz_, z, mx), np.sin(azs) * rad + np.interp(zz_, z, my), zz_], 1)
        billows(P, r_base * R.uniform(*size, n_), zs * R.uniform(0.85, 1.15, n_), R.uniform(*tilt, n_), np.full(n_, tn_))
    ring(14, (r_base * 0.9, r_base * 1.6), (0, Hs * 0.5), (0.42, 0.62), 0.85, (0.1, 0.3), 0.04)            # heaped inside the bell
    ring(10, (r_base * 0.75, r_base * 1.1), (Hs * 0.7, Hs * 1.7), (0.26, 0.4), 1.15, (0.0, 0.2), 0.0)      # sheath up the funnel
    # thrown over the rim: short arcs of 3 shrinking billows going up and out
    na = 12; az0 = (np.arange(na) + R.uniform(0.2, 0.8, na)) / na * TAU
    for j in range(3):
        f_ = j / 2.0
        rad = Rt * (0.95 + 0.55 * f_) * R.uniform(0.9, 1.1, na); zz_ = Hs * (0.75 + 0.3 * f_ - 0.35 * f_ * f_) * R.uniform(0.85, 1.15, na)
        P = np.stack([np.cos(az0 + 0.08 * j) * rad, np.sin(az0 + 0.08 * j) * rad, zz_], 1)
        billows(P, r_base * (0.4 - 0.1 * j) * R.uniform(0.8, 1.2, na), np.full(na, 0.95), R.uniform(0.3, 0.7, na), np.full(na, 0.02 + 0.03 * j))
    ring(26, (r_base * 2.8, r_base * 4.8), (-2, Hs * 0.1), (0.32, 0.5), 0.6, (0.1, 0.4), 0.08)              # spray ring on the sea
    # droplets round the bell
    nd = 70; Vd, Fd, RPd = tpl_drop()
    ad = R.uniform(0, TAU, nd); rd_ = Rt * R.uniform(0.9, 2.0, nd); zd = Hs * R.uniform(0.2, 1.4, nd)
    Pd = np.stack([np.cos(ad) * rd_, np.sin(ad) * rd_, zd], 1)
    vel = np.stack([np.cos(ad) * 0.6, np.sin(ad) * 0.6, R.uniform(-1.0, 0.4, nd)], 1)
    sd_ = r_base * R.uniform(0.05, 0.1, nd)
    M = _scale(_frame_z(vel), sd_, sd_, sd_ * 1.5)
    parts.append(((np.einsum('nij,mj->nmi', M, Vd) + Pd[:, None, :]).reshape(-1, 3), (Fd[None] + (np.arange(nd) * len(Vd))[:, None, None]).reshape(-1, 3),
                  {'rp': (RPd[None] + R.uniform(-60, 60, (nd, 3))[:, None, :]).reshape(-1, 3), 'tone': np.full(nd * len(Vd), 0.02),
                   'bk': np.full(nd * len(Vd), 0.6), 'seed': np.repeat(R.uniform(0, 1, nd), len(Vd))}))
    V = np.vstack([p_[0] for p_ in parts]); offs = np.cumsum([0] + [len(p_[0]) for p_ in parts[:-1]])
    F = np.vstack([p_[1] + o_ for p_, o_ in zip(parts, offs)])
    at = _std({k: np.concatenate([p_[2][k] for p_ in parts]) for k in ('rp', 'tone', 'bk', 'seed')}, len(V))
    sk = _mesh(name + '_skirt', V, F, C, wm, attrs=at); sk.parent = rt; sk.location = (0, 0, 0); sk['t'] = 0.0
    _driver(sk, 'rotation_euler', rt, '["twist"]', 'var*0.45', 2)
    _driver(sk, '["t"]', rt, '["twist"]', 'var*0.6')
    out['skirt'] = sk
    # ---- foam spiral on the sea
    NA, NRr = 96, 12; Rf = 260.0
    ra = np.linspace(0.06, 1.0, NRr); an = np.arange(NA) / NA * TAU
    RR, AA = np.meshgrid(ra, an, indexing='ij')
    V = np.stack([RR * Rf * np.cos(AA), RR * Rf * np.sin(AA), np.zeros_like(RR)], -1).reshape(-1, 3)
    I, J = np.meshgrid(np.arange(NRr - 1), np.arange(NA), indexing='ij')
    a_ = I * NA + J; b_ = I * NA + (J + 1) % NA; c_ = (I + 1) * NA + (J + 1) % NA; d_ = (I + 1) * NA + J
    F = np.vstack([np.stack([a_, c_, b_], -1).reshape(-1, 3), np.stack([a_, d_, c_], -1).reshape(-1, 3)])
    lift = _lift(Rf * 0.5)
    sf = _mesh(name + '_foam', V, F, C, spfoam_mat(), smooth=False, attrs={'rp': V / Rf, 'ra': RR.ravel()})
    sf.parent = rt; sf.location = (0, 0, lift)
    _driver(sf, 'rotation_euler', rt, '["twist"]', 'var*0.3', 2)
    out['foam'] = sf
    # ---- collar: the wide, flat-bottomed dark cloud the funnel hangs from, with a lowered wall cloud round the funnel top
    if collar:
        pu = []
        for k in range(70):
            a = R.uniform(0, TAU); d = 820.0 * math.sqrt(R.uniform(0.02, 1)); rr_ = R.uniform(110, 220) * (1.15 - 0.4 * d / 820)
            pu.append((math.cos(a) * d, math.sin(a) * d, 30 + R.uniform(0, 160) * (1 - 0.6 * d / 820), rr_, 0.0, -1, 0.6))
        for k in range(16):
            a = R.uniform(0, TAU); d = 230.0 * math.sqrt(R.uniform(0, 1)); rr_ = R.uniform(110, 170)
            pu.append((math.cos(a) * d + mx[-1] * 0.5, math.sin(a) * d + my[-1] * 0.5, -70 + R.uniform(-15, 25), rr_, 0.0, -1, 0.75))
        V, F, RP, PI = _spheres(pu, 220.0)
        low = np.array([p_[2] < -40 for p_ in pu])[PI]
        V[~low] = _flatten_below(V[~low], -25.0, 0.08)
        V[low] = _flatten_below(V[low], -150.0, 0.1)
        ht = np.clip((V[:, 2] + 150.0) / 560.0, 0, 1) * 0.85
        cl = _mesh(name + '_collar', V, F, C, storm_mat(), attrs={'ht': ht, 'rp': RP + 90.0, 'tone': np.full(len(V), 0.02), 'tn': np.zeros((len(V), 3))})
        mdc = cl.modifiers.new('lumps', 'DISPLACE'); txc = D.textures.new(name + '_tx', 'CLOUDS'); txc.noise_scale = 120.0; txc.noise_depth = 2
        mdc.texture = txc; mdc.strength = 55.0; mdc.mid_level = 0.5; mdc.texture_coords = 'GLOBAL'
        cl.parent = tp; cl.location = (0, 0, 0)
        cl['fl1'] = 0.0; cl['fl2'] = 0.0; cl['fp1'] = (0.0, 0.0, -1e5); cl['fp2'] = (0.0, 0.0, -1e5)
        out['collar'] = cl
    # ---- debris spiralling up (drivers from twist: orbit, climb, tumble); wraps from the collar back into the skirt
    out['debris'] = []
    if debris:
        bases = _debris_bases(seed + 5, ('plank', 'tile', 'chunk', 'container'), 2.2)
        Hc = height - 15.0
        for k in range(debris):
            kind = ('plank', 'tile', 'chunk', 'plank', 'container')[k % 5]
            me_, mt_ = bases[kind][k % len(bases[kind])]
            o = D.objects.new('%s_deb%02d' % (name, k), me_); C.objects.link(o); o.parent = rt
            r0 = R.uniform(1.5, 2.4) * r_min + R.uniform(8, 30); a0 = R.uniform(0, TAU); wv = R.uniform(1.6, 3.0)
            climb = R.uniform(18.0, 40.0); z0 = R.uniform(0, Hc)
            zf = 'fmod(var*%.3f + %.3f, %.3f)' % (climb, z0, Hc)
            rk = '(%.3f + %.5f*%s)' % (r0, (r_top * 0.5) / Hc, zf)
            _driver(o, 'location', rt, '["twist"]', '%s*cos(%.4f + var*%.3f)' % (rk, a0, wv), 0)
            _driver(o, 'location', rt, '["twist"]', '%s*sin(%.4f + var*%.3f)' % (rk, a0, wv), 1)
            _driver(o, 'location', rt, '["twist"]', '8.0 + %s' % zf, 2)
            for ax in range(3):
                _driver(o, 'rotation_euler', rt, '["twist"]', '%.3f + var*%.3f' % (R.uniform(0, 6.28), R.uniform(-4, 4)), ax)
                _driver(o, 'scale', rt, '["twist"]', 'min(max(min(%s/60.0, (%.1f - %s)/80.0), 0.0), 1.0)' % (zf, Hc, zf), ax)
            out['debris'].append(o)
    return out


def spout_spin(W, f0, f1, speed=1.0, step=STEP):
    """key W['root']['twist'] on threes from f0 to f1: speed 1 = 1.6 rad/s of vortex rotation."""
    rt = W['root']; fr = list(range(int(f0), int(f1) + 1, step))
    for f in fr:
        rt['twist'] = speed * 1.6 * (f - f0) / FPS; rt.keyframe_insert('["twist"]', frame=f)
    _interp(rt, 'CONSTANT', ('["twist"]',))
    return fr


# ================================================================================================================ splashes
TIP_SLOPE = 0.3                                 # a spike's radius at arc length s behind its head <= TIP_SLOPE x (s + the tip's
                                                # reach): an emerging (short) jet is a slender needle, never a squat white pyramid
PLUME = dict(tip=0.9, slope=None, streak=0.3, lump=(0.2, 0.1), bk=1.1)    # the big splashes' jets drawn as foam plumes (see _jet_tubes, _plume_lobes)
HEAD_R, HEAD_GAP, HEAD_SHARE = 0.55, 4.0, 0.65   # jet head drop: radius (x the spike's head radius), centre ahead of the
                                                # spike's head element (x that radius: a clear gap past the pointed tip), share
                                                # of jets that throw one


def _jets(R, roots, dirs, H, ts, T, per=7, w=1.0, Te=0.3, ta=0.42, delay=None, dieT=(0.12, 0.3), tone=0.0, hmax=None, info=None,
          head_w=0.3):
    """continuous jets thrown from roots: water leaves during [0, Te*T] and flies ballistically, so each column
    stretches, lifts off and falls apart by itself. -> Ps, Ms, attrs, head mask (heads: drop template stretched along
    their velocity; the bodies are drawn by _jet_tubes from `info`: per drawing the elements' positions, radii, released
    and alive masks)."""
    nj = len(roots); n = nj * per
    f = np.tile(np.arange(per) / max(per - 1, 1), nj); jid = np.repeat(np.arange(nj), per)
    Hj = H[jid]; dj = dirs[jid]; r0 = roots[jid]
    Te_ = Te * T; ta_ = ta * T
    cz = np.clip(dj[:, 2], 0.3, 1.0)
    V = 2 * Hj / ta_ / cz; g = 2 * Hj / ta_ ** 2
    tau = Te_ * f ** 1.25
    dl = (np.asarray(delay) if delay is not None else R.uniform(0, 0.05 * T, nj))[jid]
    Vk = V * (1 - 0.5 * tau / max(Te_, 1e-6))
    hm = hmax or H.max()
    # a spike, not a bottle: thin at the head (the first, fastest water), full from ~60 % down, a little thinner at the very
    # tail (the jet weakens as the release ends)
    # (head_w: the head's share of the full width - 0.3 a spike; plumes keep a full head under their crest of billows)
    prof = ((head_w + (1.0 - head_w) * np.sin(0.5 * np.pi * np.minimum(f / 0.6, 1.0)) ** 0.8) * (1.0 - 0.3 * np.clip((f - 0.78) / 0.22, 0, 1))
            * R.uniform(0.8, 1.2, n))
    rb = w * prof * (Hj / hm * 0.6 + 0.45)
    head = f < 1e-6
    # which jets throw a head drop: a hash of the roots (R's sequence - so every other draw - stays as it was)
    rh = np.asarray(roots, np.float64) @ np.array([12.9898, 78.233, 37.719]) + np.arange(nj) * 1.618
    hk = ((np.abs(np.sin(rh)) * 43758.5453) % 1.0 < HEAD_SHARE)[jid]
    spin = R.uniform(0, TAU, n)
    Ps, Ms = [], []
    if info is not None:
        info.update(jid=jid, f=f, per=per, nj=nj, roots=np.asarray(roots, np.float64), dirs=np.asarray(dirs, np.float64), H=np.asarray(H, np.float64),
                    rb=rb, pos=[], r=[], rel=[], alive=[], age=[], ta=ta_, T=T)
    for k, t in enumerate(ts):
        age = t - dl - tau; alive = age > 0; a = np.clip(age, 0, None)
        pos = r0 + dj * (Vk * a)[:, None]; pos[:, 2] -= 0.5 * g * a ** 2
        vel = dj * Vk[:, None]; vel[:, 2] -= g * a
        r = rb * (0.7 + 0.5 * np.clip(a / (0.45 * T), 0, 1)) * (1 - 0.3 * np.clip((a - ta_) / (0.7 * ta_), 0, 1))
        sp = np.linalg.norm(vel, axis=1)
        st = np.where(head, np.clip(0.9 + sp * 0.3 / np.maximum(V, 1e-3), 0.9, 1.2), np.clip(0.85 + sp * 0.35 / np.maximum(V, 1e-3), 0.85, 1.25))
        alive &= pos[:, 2] > -r * 0.7
        Rm = _frame_z(vel) @ _rot(np.tile([[0, 0, 1.0]], (n, 1)), spin + k * 0.35)
        # the head: a small drop already torn off, flying ahead of the spike's pointed tip with a clear gap (never a pin head
        # sitting on the spike); only HEAD_SHARE of the jets throw one
        rr = np.where(head, r * HEAD_R, r)
        M = _scale(Rm, rr, rr, rr * st); M[~alive] = 0.0; M[head & ~hk] = 0.0
        posd = pos.copy(); posd[head] += _nrm(vel[head] + 1e-9) * (r[head] * HEAD_GAP)[:, None]
        Ps.append(posd); Ms.append(M)
        if info is not None:
            info['pos'].append(pos.copy()); info['r'].append(r.copy()); info['rel'].append(age > 0); info['alive'].append(alive.copy())
            info['age'].append(age.copy())
    d0 = ta_ + dl + R.uniform(dieT[0], dieT[0] + 0.15, n) * T + 0.1 * T * f
    at = {'tone': tone + 0.1 * f + R.uniform(0, 0.05, n), 'd0': d0, 'd1': d0 + dieT[1] * T, 'bk': np.full(n, 0.9)}
    if info is not None: info.update(tone=at['tone'].copy(), d0=d0.copy(), d1=(d0 + dieT[1] * T).copy())
    return Ps, Ms, at, head


def _jet_tubes(name, info, frames, f_end, coll, mat, loc, seed, props=None, nring=28, sides=12, thick=0.86, lump=(0.15, 0.08),
               pinch=0.11, mk=0.12, bk=1.35, tip=1.6, slope=TIP_SLOPE, streak=1.0, geo=None):
    """the jets' bodies as continuous columns of water: per jet one lumpy tube through its ballistic elements in release
    order (head -> tail), down into the sea through the root while water still leaves it, lifted off after that, ending
    where elements fell back into the sea. A shape-key flipbook needs a fixed topology: ring i always stands for the same
    fraction f_i of the jet (so its attributes - tone, dissolve times, brush coords - stay with that water) and rings with
    no water collapse to a point. The silhouette boils on every drawing (two lobe waves round and along the column, a pinch
    wave running up it). A spike: thin under the head drop, flaring into the sea while attached; once it has lifted off,
    its lower part thins out (the tail breaking away, not a blunt bottle end). mk: the tubes shade mostly by their own
    normals (each spike keeps its own shade side); bk > 1: hard shade blobs.
    Plumes (the big splashes): tip ~0.9 (a round end, hidden in the crest of billows _plume_lobes puts on it), slope None
    (no needle), streak < 1 (the brush stretched along the column: flow streaks, not ice-like blobs), geo = {} records
    per drawing the jets' ring centres / radii / frames / live masks for _plume_lobes."""
    R = np.random.RandomState(seed + 7)
    nj = int(info['nj']); E = int(info['per']); fe = np.arange(E) / max(E - 1, 1)
    fi = np.linspace(0.0, 1.0, nring); ui = fi * (E - 1)
    ang = np.arange(sides) / sides * TAU; ca = np.cos(ang); sa = np.sin(ang)
    ph1 = R.uniform(0, TAU, nj); ph2 = R.uniform(0, TAU, nj); sgn = R.choice([-1.0, 1.0], nj); ph3 = R.uniform(0, TAU, nj)
    dirs = _nrm(info['dirs'])
    refs = _nrm(np.cross(dirs, np.array([0.0, 0.0, 1.0])) + np.array([1e-4, 0.0, 0.0]))     # stable round-the-column reference
    roots = info['roots']
    nv1 = nring * sides + 2
    Vs = []
    for k in range(len(frames)):
        Pk = info['pos'][k].reshape(nj, E, 3); Rk = info['r'][k].reshape(nj, E)
        rel = info['rel'][k].reshape(nj, E); al = info['alive'][k].reshape(nj, E)
        V = np.empty((nj, nv1, 3))
        if geo is not None:
            gk = {'C': np.zeros((nj, nring, 3)), 'rad': np.zeros((nj, nring)), 'T': np.zeros((nj, nring, 3)), 'N': np.zeros((nj, nring, 3)),
                  'B': np.zeros((nj, nring, 3)), 'on': np.zeros(nj, bool)}
        for j in range(nj):
            # control points: released elements still in the air, from the head; then (if water is still leaving) the root,
            # sunk 1.5 radii under the sea so the column runs down into it
            Q = []; Rq = []; att = False
            for e in range(E):
                if rel[j, e]:
                    if not al[j, e]: break
                    Q.append(Pk[j, e]); Rq.append(Rk[j, e])
                else:
                    if Q:
                        rn = Rq[-1]; Q.append(roots[j] + np.array([0.0, 0.0, -1.5 * rn])); Rq.append(rn); att = True
                    break
            m = len(Q) - 1
            if m < 1:
                c = Q[0] if Q else roots[j] + np.array([0.0, 0.0, -2.0])
                V[j] = c
                if geo is not None: gk['on'][j] = False
                continue
            Q = np.array(Q); Rq = np.array(Rq)
            Qx = np.vstack([2 * Q[0] - Q[1], Q, 2 * Q[-1] - Q[-2]])           # extrapolated ends for Catmull-Rom
            seg = np.minimum(np.floor(ui).astype(int), m - 1); tt = np.clip(ui - seg, 0.0, 1.0)
            live = ui <= m + 1e-9
            p0 = Qx[seg]; p1 = Qx[seg + 1]; p2 = Qx[seg + 2]; p3 = Qx[seg + 3]
            t1 = tt[:, None]; t2 = t1 * t1; t3 = t2 * t1
            C = 0.5 * ((2 * p1) + (-p0 + p2) * t1 + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            rad = (Rq[seg] * (1 - tt) + Rq[seg + 1] * tt) * thick
            gi = np.clip(ui / m, 0.0, 1.0)                                  # 0 at the head .. 1 at the drawn tail end
            rad = rad * ((1.0 + 0.22 * _sm((gi - 0.82) / 0.18)) if att else (1.0 - 0.6 * _sm((gi - 0.5) / 0.5)))
            C[~live] = Q[-1]; rad[~live] = 0.0
            sarc = np.cumsum(np.r_[0.0, np.linalg.norm(np.diff(C, axis=0), axis=1)])
            if slope is not None: rad = np.minimum(rad, slope * (sarc + 1.6 * rad[0]))
            # ring frames: tangent from neighbouring centres, the normal from a fixed per-jet reference (no spinning lobes)
            Tg = np.empty_like(C); Tg[1:-1] = C[2:] - C[:-2]; Tg[0] = C[1] - C[0]; Tg[-1] = C[-1] - C[-2]
            nt = np.linalg.norm(Tg, axis=1)
            for i in range(nring):
                if nt[i] < 1e-6: Tg[i] = Tg[i - 1] if i > 0 and nt[i - 1] >= 1e-6 else dirs[j]
            Tg = _nrm(Tg)
            Nn = _nrm(refs[j][None, :] - (Tg @ refs[j])[:, None] * Tg)
            Bn = np.cross(Tg, Nn)
            wob = (1.0 + lump[0] * np.sin(3 * ang[None, :] + 9.0 * fi[:, None] + ph1[j] + 0.8 * k * sgn[j])
                   + lump[1] * np.sin(5 * ang[None, :] - 17.0 * fi[:, None] + ph2[j] - 1.3 * k))
            wob = wob * (1.0 + pinch * np.sin(TAU * 2.3 * fi + ph3[j] + 0.55 * k))[:, None]
            rr = rad[:, None] * wob
            ring = C[:, None, :] + rr[..., None] * (ca[None, :, None] * Nn[:, None, :] + sa[None, :, None] * Bn[:, None, :])
            last = int(np.nonzero(live)[0].max())
            V[j, :nring * sides] = ring.reshape(-1, 3)
            V[j, nring * sides] = C[0] - Tg[0] * rad[0] * tip                  # tip (1.6 pointed: the head drop pinches off ahead of it)
            V[j, nring * sides + 1] = C[last] + Tg[last] * rad[last] * 0.5     # rounded tail end
            if geo is not None:
                gk['C'][j] = C; gk['rad'][j] = rad * live; gk['T'][j] = Tg; gk['N'][j] = Nn; gk['B'][j] = Bn; gk['on'][j] = True
        Vs.append(V.reshape(-1, 3))
        if geo is not None: geo.setdefault('k', []).append(gk)
    # faces (per jet, offset)
    I, J = np.meshgrid(np.arange(nring - 1), np.arange(sides), indexing='ij')
    a_ = I * sides + J; b_ = I * sides + (J + 1) % sides; c_ = (I + 1) * sides + (J + 1) % sides; d_ = (I + 1) * sides + J
    F1 = [np.stack([a_, b_, c_], -1).reshape(-1, 3), np.stack([a_, c_, d_], -1).reshape(-1, 3)]
    cs, ce = nring * sides, nring * sides + 1; jj = np.arange(sides)
    F1.append(np.stack([np.full(sides, cs), (jj + 1) % sides, jj], -1))
    F1.append(np.stack([np.full(sides, ce), (nring - 1) * sides + jj, (nring - 1) * sides + (jj + 1) % sides], -1))
    F1 = np.vstack(F1)
    F = np.vstack([F1 + j * nv1 for j in range(nj)])
    # attributes: fixed per vertex (ring i = fraction f_i of jet j)
    fv = np.concatenate([np.repeat(fi, sides), [0.0, 1.0]])
    av = np.concatenate([np.tile(ang, nring), [0.0, 0.0]])
    tone = np.empty(nj * nv1); d0 = np.empty(nj * nv1); d1 = np.empty(nj * nv1); rp = np.empty((nj * nv1, 3)); sd = np.empty(nj * nv1)
    for j in range(nj):
        sl = slice(j * nv1, (j + 1) * nv1); ix = np.arange(j * E, (j + 1) * E)
        tone[sl] = np.interp(fv, fe, info['tone'][ix]); d0[sl] = np.interp(fv, fe, info['d0'][ix]); d1[sl] = np.interp(fv, fe, info['d1'][ix])
        rbar = max(float(np.mean(info['rb'][ix])), 1e-3)
        lz = float(info['H'][j]) / rbar * 0.5                         # brush blobs ~ a column radius apart along it
        sa_ = 1.0 / max(streak, 1e-3) ** 0.5                             # streak < 1: finer round the column, longer along it
        rp[sl] = np.stack([np.cos(av) * sa_, np.sin(av) * sa_, fv * lz * streak], 1) + R.uniform(-40, 40, 3)
        sd[sl] = R.uniform(0, 1)
    tone = tone + 0.1 * np.tile(fv, nj)                                   # the lower column a shade deeper
    at = _std({'rp': rp, 'tone': tone, 'd0': d0, 'd1': d1, 'bk': np.full(nj * nv1, bk), 'seed': sd}, nj * nv1)
    o = _mesh(name, Vs[0], F, coll, mat, loc=tuple(loc), attrs=at)
    _props(o, props)
    if mk is not None: o['mk'] = float(mk)
    _flip(o, Vs, frames); _show(o, frames[0], f_end)
    _keyp(o, 't', frames, [(f - frames[0]) / FPS for f in frames])
    if geo is not None: geo['nring'] = nring
    return o


CREST_N, FLANK_N = 5, 7          # billows crowning each plume's head / half sunk into its flanks


def _plume_lobes(name, info, geo, frames, f_end, coll, mat, loc, seed, props=None, ncrest=CREST_N, nflank=FLANK_N, crest=1.0,
                 flank=1.0, bk=0.85):
    """the foam on the big jets (the plumes of splash_crown / splash_wall): a crest of billows round each jet's head - a
    cauliflower top that loosens and tears apart once the water peaks (never a needle: upward water never ends in a point) -
    and billows half sunk into its flanks (a lumpy foam column like a cumulus tower, never a smooth icicle). They ride the
    rings _jet_tubes recorded in `geo` (ring i = the same water all along, so a flank billow keeps its water's tone and
    dissolve times) and dissolve with that water. Each billow shades by its own form (props mk 0): white crowns, blue-lavender
    undersides. crest / flank scale the billows' sizes."""
    R = np.random.RandomState(seed + 13)
    nj = int(info['nj']); E = int(info['per']); fe = np.arange(E) / max(E - 1, 1)
    nring = int(geo['nring']); fi = np.linspace(0.0, 1.0, nring)
    ta = float(info['ta']); T = float(info['T'])
    nl = ncrest + nflank; n = nj * nl
    jid = np.repeat(np.arange(nj), nl); slot = np.tile(np.arange(nl), nj); isc = slot < ncrest
    # crest: billow 0 rides ahead of the head; the others ring it, a little back; flank billows sit on fixed rings
    ang = np.where(isc, (slot - 1) / max(ncrest - 1, 1) * TAU, 0.0) + R.uniform(0, TAU, n) * np.where(isc, 0.15, 1.0) + np.repeat(R.uniform(0, TAU, nj), nl)
    # flank billows over the upper ~60 % of the column, denser toward the head (u^1.6): big enough (0.72..0.95 of the local
    # radius, centred 0.6..0.74 out) that they make the silhouette - a cauliflower tower, not warts on a smooth trunk
    ring = np.where(isc, 0, (0.05 + 0.55 * R.uniform(0.0, 1.0, n) ** 1.6) * (nring - 1)).astype(int)
    size = np.where(isc, np.where(slot == 0, 1.15, R.uniform(0.8, 1.0, n)) * crest, R.uniform(0.72, 0.95, n) * flank)
    lat = np.where(isc, np.where(slot == 0, 0.12, R.uniform(0.6, 0.74, n)), R.uniform(0.6, 0.74, n))
    ahead = np.where(isc, np.where(slot == 0, 0.32, R.uniform(-0.3, 0.05, n)), 0.0)
    spin = R.uniform(0, TAU, n); drift = R.uniform(0.6, 1.3, n)
    Ps, Ms = [], []
    for k in range(len(frames)):
        gk = geo['k'][k]; age = info['age'][k].reshape(nj, E)[:, 0]
        C = gk['C'][jid, ring]; rad = gk['rad'][jid, ring]; Tg = gk['T'][jid, ring]; Nn = gk['N'][jid, ring]; Bn = gk['B'][jid, ring]
        on = gk['on'][jid] & (rad > 1e-4)
        # crest size: the head ring's radius, never less than 0.55 of the column's widest ring (a full crest, not a bead)
        rmax = gk['rad'].max(axis=1)[jid]
        rh = np.where(isc, np.maximum(rad, 0.55 * rmax), rad)
        # past the peak the crest loosens: its billows drift apart and shrink as they dissolve
        brk = np.where(isc, np.clip((age[jid] - ta) / max(0.55 * ta, 1e-3), 0.0, 1.0), 0.0)
        out = np.cos(ang)[:, None] * Nn + np.sin(ang)[:, None] * Bn
        pos = C + out * (lat * rh * (1.0 + 0.9 * brk * drift))[:, None] - Tg * (ahead * rh * (1.0 + 0.5 * brk))[:, None]
        s = size * rh * (1.0 - 0.25 * brk)
        up = _nrm(np.where(isc[:, None], -Tg * 1.0 + out * np.where(slot == 0, 0.25, 0.9)[:, None], out + 1e-9))
        M = _scale(_frame_z(up) @ _rot(np.tile([[0, 0, 1.0]], (n, 1)), spin + k * 0.3), s, s, s * 0.92)
        M[~on] = 0.0
        Ps.append(pos); Ms.append(M)
    fv = fi[ring]
    tone = np.array([np.interp(fv[i], fe, info['tone'][jid[i] * E:(jid[i] + 1) * E]) for i in range(n)]) + 0.1 * fv
    d0 = np.array([np.interp(fv[i], fe, info['d0'][jid[i] * E:(jid[i] + 1) * E]) for i in range(n)])
    d1 = np.array([np.interp(fv[i], fe, info['d1'][jid[i] * E:(jid[i] + 1) * E]) for i in range(n)])
    pr = dict(props or {}); pr['mk'] = 0.0
    return _pobj(name, tpl_billow(seed + 3, 3, 3), Ps, Ms, frames, f_end, coll, mat, loc,
                 {'tone': tone - 0.04, 'd0': d0, 'd1': d1, 'bk': np.full(n, bk)}, seed + 3, props=pr)


def _drops_state(R, P0, V0, te, size, ts, g, z_floor=0.0, stretch=0.03):
    n = len(P0); Ps, Ms = [], []
    for t in ts:
        a = t - te; alive = a >= 0; a = np.clip(a, 0, None)
        pos = P0 + V0 * a[:, None]; pos[:, 2] -= 0.5 * g * a ** 2
        vel = V0.copy(); vel[:, 2] -= g * a
        sp = np.linalg.norm(vel, axis=1)
        # never squashed below its drawn shape: at 0.6-0.9 (every slow crown drop) the round head went flat and the tail
        # stubby, a squat white cone; four of them over the mech's knee read as thorns on it (s32 f1612, 06.11)
        st = np.clip(0.55 + sp * stretch, 1.0, 1.6)
        # gone from the drawing its round head would touch the sea (half sunk it read as a white fin standing in the water),
        # and half a drawing's fall before that: on threes a drop drawn just over the water, seen from a low lens, still
        # stood on it as a white cone (s26, 06.11)
        alive &= pos[:, 2] > z_floor + size * st * 1.2 + np.maximum(-vel[:, 2], 0.0) * (0.5 * STEP / FPS)
        M = _scale(_frame_z(vel + 1e-6), size, size, size * st); M[~alive] = 0.0
        Ps.append(pos); Ms.append(M)
    return Ps, Ms


def _fadeout(Ms, seed, K=4):
    """the elements still drawn on the last drawing (the object ends there: they all vanished in one frame, mid-flight;
    s10's rust, 06.11) leave one by one instead: each on its own drawing among the last K (none sooner than 2 drawings
    after it appears), drawn at 0.55 x on the drawing before. Ms: per drawing (n, 3, 3); changed in place and returned."""
    nd = len(Ms)
    if nd < 2 or not len(Ms[-1]): return Ms
    on = np.array([np.abs(M.reshape(len(M), -1)).sum(1) > 0 for M in Ms])          # (drawings, elements)
    live = np.nonzero(on[-1])[0]
    if not len(live): return Ms
    R = np.random.RandomState(seed + 7919); K = max(1, min(int(K), nd - 1))
    born = np.argmax(on[:, live], axis=0)
    e = np.maximum(nd - 1 - R.randint(0, K, len(live)), np.minimum(born + 2, nd - 1))
    for i, ei, b in zip(live, e, born):
        for k in range(ei, nd): Ms[k][i] = 0.0
        if ei - 1 >= b: Ms[ei - 1][i] = Ms[ei - 1][i] * 0.55
    return Ms


def _lift(r):
    """height of flat foam above the sea: +0.05 m minimum, more for big pieces (seen from farther away) so the depth
    buffer always separates it from the sea plane: needs lift > d * cam_height / 2.8e6 (d = camera distance)."""
    return max(0.05, 0.012 * r)


def foam_ring(center, r0, r1, f0=1, dur=48, coll=None, seed=0, band=0.62, fill=0.0, lift=None, cell=None, name='FX_foam'):
    """A flat foam ring on the sea (white + pale-cyan lace) expanding from r0 to r1 (m) and eaten away.
    z = center z + lift (default _lift(r1) = max(0.05, 0.012*r1); never coplanar with the sea).
    band = inner edge of the ring as a fraction of its radius; fill > 0 also fills the inside with churn; cell = lace size (m).
    Keys on threes: object scale (radius), props t, age (0..1)."""
    c = _xyz(center); R = np.random.RandomState(seed)
    frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    NA, NRr = 128, 10
    ra = np.concatenate([np.linspace(0.0, band - 0.02, 5)[1:], np.linspace(band - 0.02, 1.0, NRr)]) if fill > 0 else np.linspace(max(band - 0.08, 0.02), 1.0, NRr)
    an = np.arange(NA) / NA * TAU
    RR, AA = np.meshgrid(ra, an, indexing='ij')
    wob = 1 + 0.035 * np.sin(AA * 5 + R.uniform(0, 6)) + 0.02 * np.sin(AA * 13 + R.uniform(0, 6))
    V = np.stack([RR * wob * np.cos(AA), RR * wob * np.sin(AA), np.zeros_like(RR)], -1).reshape(-1, 3)
    nr = len(ra)
    I, J = np.meshgrid(np.arange(nr - 1), np.arange(NA), indexing='ij')
    a_ = I * NA + J; b_ = I * NA + (J + 1) % NA; c_ = (I + 1) * NA + (J + 1) % NA; d_ = (I + 1) * NA + J
    F = np.vstack([np.stack([a_, c_, b_], -1).reshape(-1, 3), np.stack([a_, d_, c_], -1).reshape(-1, 3)])
    lift = _lift(r1) if lift is None else lift
    o = _mesh(name, V, F, coll, foam_mat(), loc=(c[0], c[1], c[2] + lift), smooth=False, attrs={'ra': RR.ravel()})
    o['band'] = float(band); o['fill'] = float(fill); o['cell'] = float(cell or max(0.5, r1 / 13.0)); o['sd'] = float(R.uniform(0, 100))
    for f, t in zip(frames, ts):
        u = t / T; s = r0 + (r1 - r0) * _eout(u / 0.85, 2.2)
        o.scale = (s, s, 1.0); o.keyframe_insert('scale', frame=f)
    _keyp(o, 't', frames, ts); _keyp(o, 'age', frames, np.clip(ts / T, 0, 1) ** 1.2)
    _show(o, frames[0], f_end); _interp(o, 'CONSTANT')
    return o


def _auto_dur(height, k=0.62, lo=1.5, hi=6.0):
    """heavy drawn timing for big water: a splash `height` m tall lasts ~k*sqrt(height) s (36 m -> 3.7 s), in frames.
    (Faster reads as a miniature; this is ~3-4 g instead of 1 g.)"""
    return int(round(float(np.clip(k * math.sqrt(max(height, 1.0)), lo, hi)) * FPS))


def splash_crown(center, radius=4.0, height=36.0, f0=1, dur=None, coll=None, seed=0, jets=8, drops=70, foam=True, name='FX_crown',
                 plume_w=0.11):
    """A crown splash round a foot/pillar of `radius` (m) standing in the sea at center (x, y[, z water level]); nothing
    enters r < radius except the surge billows' inner edge (the designed contact at the waterline). A lobed crown sheet
    (~0.6 x height) rising and flaring, round rim beads riding its lobe tips, foam plumes thrown above it (up to
    ~1.3 x height: lumpy columns crowned and flanked by billows, _plume_lobes; the beads live in the jets' element set), a
    heaped base surge rolling out, droplets flung off the rim at the break, a foam ring. Timing (dur None = _auto_dur):
    rise 0-34 % of dur, break ~45 %, fall and dissolve to the end. The water masses shade as one mass (props mk/mz).
    Returns [sheet, jets, beads, crests, surge, drops, foam]."""
    c = _xyz(center); R = np.random.RandomState(seed)
    dur = dur or _auto_dur(height)
    frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    wm = water_mat(); out = []
    props = {'mk': 0.35, 'mz': height * 0.3, 'mdir': (0.0, 0.0, 0.0)}
    # ---- the crown sheet: rounded lobes, flaring out
    NC, NR = 72, 12
    K = R.randint(9, 13)
    phi = (np.arange(K) + R.uniform(-0.3, 0.3, K)) / K * TAU; wk = math.pi / K * R.uniform(0.75, 1.05, K); ak = R.uniform(0.5, 1.0, K)
    th = np.arange(NC) / NC * TAU
    dth = (th[:, None] - phi[None, :] + math.pi) % TAU - math.pi
    ftop = np.max(ak[None, :] * np.clip(1 - (np.abs(dth) / wk[None, :]) ** 2, 0, 1) ** 0.6, axis=1)
    s1, s2 = R.uniform(0, 6.28, 2)
    rr = radius * (1.12 + 0.05 * np.sin(3 * th + s1) + 0.035 * np.sin(7 * th + s2))
    vj = np.linspace(0, 1, NR + 1)
    Vs = []
    for k, t in enumerate(ts):
        u = t / T
        rise = _eout(u / 0.34, 2.4); fall = _ein((u - 0.46) / 0.5, 1.7)
        # it falls right back under the sea (at 0.1 x its height its last band stood at the waterline as white teeth)
        h = height * 0.62 * rise * (1 - fall)
        opn = 0.18 + 0.4 * _sm(u / 0.55)
        top = h * (0.6 + 0.4 * ftop) * (1 + 0.03 * np.sin(th * 9 + k * 1.7))
        z = top[None, :] * vj[:, None] ** 0.9 - 0.8 * (1 - vj[:, None]) - 0.8 * fall * vj[:, None]
        zc = np.clip(z, 0, None)
        r = rr[None, :] + opn * zc * np.sqrt(zc / max(height, 1e-3)) + 0.1 * height * vj[:, None] ** 4 * rise
        Vs.append(np.stack([r * np.cos(th)[None, :], r * np.sin(th)[None, :], z], -1).reshape(-1, 3))
    J, I = np.meshgrid(np.arange(NR), np.arange(NC), indexing='ij')
    a_ = J * NC + I; b_ = J * NC + (I + 1) % NC; c_ = (J + 1) * NC + (I + 1) % NC; d_ = (J + 1) * NC + I
    F = np.vstack([np.stack([a_, b_, c_], -1).reshape(-1, 3), np.stack([a_, c_, d_], -1).reshape(-1, 3)])
    VV = np.repeat(vj, NC); TT = np.tile(th, NR + 1)
    d0s = (0.4 + 0.15 * (1 - VV)) * T             # top 0.4-0.7 T, the low band 0.55-0.85 T (was 0.62-0.98: ragged teeth at the end)
    # brush: fine round the crown, long up it (flow streaks, not ice-like blobs)
    at = _std({'rp': np.stack([np.cos(TT) * 5.0, np.sin(TT) * 5.0, VV * 1.5], -1) + R.uniform(-40, 40, 3), 'op': np.ones(len(VV)),
               'dp': np.stack([np.cos(TT) * 2.2, np.sin(TT) * 2.2, VV * 1.6], -1) + R.uniform(-40, 40, 3),
               'tone': 0.16 * (1 - VV) ** 1.5, 'bk': np.full(len(VV), 1.25), 'd0': d0s, 'd1': d0s + 0.3 * T}, len(VV))
    sh = _mesh(name + '_sheet', Vs[0], F, coll, wm, loc=tuple(c), attrs=at)
    _props(sh, props)
    _flip(sh, Vs, frames); _show(sh, frames[0], f_end); _keyp(sh, 't', frames, ts)
    out.append(sh)
    # ---- jets from the rim: columns of billows with round heads
    az = phi[np.argsort(-ak)[:jets]] if jets <= K else R.uniform(0, TAU, jets)
    pol = R.uniform(0.06, 0.32, jets)
    dirs = np.stack([np.sin(pol) * np.cos(az), np.sin(pol) * np.sin(az), np.cos(pol)], 1)
    roots = np.stack([np.cos(az) * radius * 1.25, np.sin(az) * radius * 1.25, np.full(jets, -0.5)], 1)
    Hs = height * R.uniform(0.85, 1.3, jets)
    JI = {}
    # plume_w: the plumes' width (x height; the spikes were 0.085 - slender white needles read as ice)
    Ps, Ms, at, head = _jets(R, roots, dirs, Hs, ts, T, per=7, w=height * plume_w, Te=0.3, ta=0.4, hmax=height * 1.3, info=JI, head_w=0.72)
    nbody = len(head)
    # rim beads (in the jets object): round billows riding the sheet's lobe tips, hiding its edge, dissolving with the top
    nbd = 2 * K; jl = np.repeat(np.arange(K), 2); tip = np.arange(nbd) % 2 == 0
    col = np.round(((phi[jl] + np.where(tip, 0.0, R.uniform(-0.6, 0.6, nbd)) * wk[jl]) % TAU) / TAU * NC).astype(int) % NC
    bsz = height * R.uniform(0.042, 0.06, nbd) * (0.75 + 0.35 * ak[jl]) * np.where(tip, 1.0, 0.72); bsp = R.uniform(0, TAU, nbd)
    out_d = np.stack([np.cos(th[col]), np.sin(th[col]), np.zeros(nbd)], 1)
    for k in range(len(ts)):
        rise = _eout(ts[k] / T / 0.34, 2.4); s_ = bsz * (0.45 + 0.55 * rise)
        tp_ = Vs[k].reshape(NR + 1, NC, 3)[NR, col]
        push = np.maximum(s_ * 0.3, radius + s_ * 0.95 - np.linalg.norm(tp_[:, :2], axis=1))      # never into the foot
        Ps[k] = np.vstack([Ps[k], tp_ + out_d * push[:, None] + np.array([0.0, 0.0, 1.0]) * (s_ * 0.2)[:, None]])
        Ms[k] = np.concatenate([Ms[k], _scale(_rot(np.tile([[0, 0, 1.0]], (nbd, 1)), bsp + k * 0.3), s_, s_, s_ * 0.9)])
    bd0 = (0.4 + R.uniform(0, 0.08, nbd)) * T
    at = {'tone': np.concatenate([at['tone'], R.uniform(0.0, 0.05, nbd)]), 'd0': np.concatenate([at['d0'], bd0]),
          'd1': np.concatenate([at['d1'], bd0 + 0.3 * T]), 'bk': np.concatenate([at['bk'], np.full(nbd, 0.9)])}
    head = np.concatenate([head, np.zeros(nbd, bool)])
    bead = np.arange(len(head)) >= nbody
    GEO = {}
    out.append(_jet_tubes(name + '_jets', JI, frames, f_end, coll, wm, tuple(c), seed + 1, props=props, geo=GEO, **PLUME))
    out.append(_pobj(name + '_beads', tpl_billow(seed + 1, 3, 2), Ps, Ms, frames, f_end, coll, wm, tuple(c), at, seed + 1, props=props, sel=bead))
    out.append(_plume_lobes(name + '_crests', JI, GEO, frames, f_end, coll, wm, tuple(c), seed + 5, props=props))
    # ---- base surge (heaped billows rolling outward)
    n = 22
    azc = np.sort(R.uniform(0, TAU, n)); sz0 = height * R.uniform(0.085, 0.125, n)
    rad0 = radius * 1.1 + sz0 * 0.9; rad1 = radius * R.uniform(1.6, 2.5, n) + sz0
    hk = R.uniform(0.3, 1.0, n); spin = R.uniform(0, TAU, n)
    Ps, Ms = [], []
    for k, t in enumerate(ts):
        u = t / T; gk = _eout(u / 0.62, 2.0)
        rad = rad0 + (rad1 - rad0) * gk
        s = sz0 * (0.35 + 0.75 * np.clip(u / 0.2, 0, 1)) * (1 - 0.3 * _sm((u - 0.6) / 0.4))
        z = height * 0.07 * hk * (1.0 - 0.7 * gk) - s * 0.3
        Ps.append(np.stack([np.cos(azc) * rad, np.sin(azc) * rad, z], 1))
        Ms.append(_scale(_rot(np.tile([[0, 0, 1.0]], (n, 1)), spin + k * 0.3), s * 1.15, s * 1.15, s * (0.85 - 0.3 * gk)))
    d0 = R.uniform(0.58, 0.72, n) * T
    # every billow is dissolved by the last drawing (d1 ran to 1.02 T: the late ones were still half there when the object
    # ended, a pop mid-shot)
    out.append(_pobj(name + '_surge', tpl_billow(seed + 2), Ps, Ms, frames, f_end, coll, wm, tuple(c),
                     {'tone': R.uniform(0.02, 0.1, n), 'd0': d0, 'd1': np.minimum(d0 + 0.3 * T, ts[-1] - 0.01)}, seed + 2, props=props))
    # ---- droplets flung off the rim
    nd = drops
    te = np.where(R.uniform(size=nd) < 0.6, R.uniform(0.36, 0.5, nd), R.uniform(0.1, 0.36, nd)) * T
    a = R.uniform(0, TAU, nd); hfr = R.uniform(0.5, 0.95, nd)
    rise_te = _eout(te / T / 0.34, 2.4)
    z0 = height * 0.62 * hfr * rise_te
    rad = radius * 1.12 + (0.18 + 0.4 * _sm(te / T / 0.55)) * z0 * np.sqrt(np.clip(z0, 0, None) / height)
    P0 = np.stack([np.cos(a) * rad, np.sin(a) * rad, z0], 1)
    Vup = 2 * height / (0.4 * T); g = 2 * height / (0.4 * T) ** 2
    V0 = np.stack([np.cos(a), np.sin(a), np.zeros(nd)], 1) * (Vup * R.uniform(0.12, 0.4, nd))[:, None] + np.array([0, 0, 1.0]) * (Vup * R.uniform(0.05, 0.45, nd))[:, None]
    sz = height * R.uniform(0.012, 0.03, nd)
    Ps, Ms = _drops_state(R, P0, V0, te, sz, ts, g, z_floor=0.0, stretch=0.6 / Vup)
    out.append(_pobj(name + '_drops', tpl_drop(), Ps, Ms, frames, f_end, coll, wm, tuple(c), {'tone': R.uniform(0, 0.08, nd)}, seed + 3))
    if foam:
        out.append(foam_ring((c[0], c[1], c[2]), radius * 1.0, radius * 3.4, f0 + 2, int(dur * 1.25), coll, seed + 4, band=0.6, fill=0.7, name=name + '_foam'))
    return out


def _strip(path, width, nacross=5):
    """a flat ribbon along a polyline -> V, F, u (fraction along), across (-1..1), length."""
    P = np.asarray(path, np.float64); n = len(P)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); cl = np.concatenate([[0], np.cumsum(seg)]); L = max(cl[-1], 1e-3)
    T = np.empty((n, 3)); T[1:-1] = P[2:] - P[:-2]; T[0] = P[1] - P[0]; T[-1] = P[-1] - P[-2]; T = _nrm(T)
    S = _nrm(np.stack([-T[:, 1], T[:, 0], np.zeros(n)], 1))
    ac = np.linspace(-1, 1, nacross)
    wv = np.broadcast_to(np.asarray(width, np.float64), (n,))
    V = (P[:, None, :] + S[:, None, :] * (ac[None, :, None] * wv[:, None, None] * 0.5)).reshape(-1, 3)
    I, J = np.meshgrid(np.arange(n - 1), np.arange(nacross - 1), indexing='ij')
    a_ = I * nacross + J; b_ = (I + 1) * nacross + J; c_ = (I + 1) * nacross + J + 1; d_ = I * nacross + J + 1
    F = np.vstack([np.stack([a_, b_, c_], -1).reshape(-1, 3), np.stack([a_, c_, d_], -1).reshape(-1, 3)])
    return V, F, np.repeat(cl / L, nacross), np.tile(ac, n), L


def _resample(points, step):
    P = np.array([_xyz(p) for p in points]); seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cl = np.concatenate([[0], np.cumsum(seg)]); L = cl[-1]
    s = np.linspace(0, L, max(2, int(L / step) + 1))
    return np.stack([np.interp(s, cl, P[:, i]) for i in range(3)], 1), L


def _foam_strip(path, width, frames, ts, f_end, head, speed, fade, coll, name, lift, seed=0):
    V, F, u, ac, L = _strip(path, width, 9)
    R = np.random.RandomState(seed)
    c = V.mean(0); c[2] = 0.0
    rp = (V - c) / max(np.mean(width) * 0.8, 1e-3) + R.uniform(-30, 30, 3) * np.array([1, 1, 0])
    o = _mesh(name, V - c, F, coll, wake_mat(), loc=(c[0], c[1], lift), smooth=False, attrs={'u': u, 'ra': np.abs(ac), 'rp': rp})
    o['L'] = float(L); o['spd'] = float(max(speed, 1e-3)); o['fade'] = float(fade)
    _keyp(o, 'head', frames, head); _keyp(o, 't', frames, ts)
    _show(o, frames[0], f_end)
    return o


def splash_wall(p0, p1, height=150.0, f0=1, dur=None, coll=None, seed=0, zip=0.35, plumes=None, drops=160, foam=True, name='FX_wall',
                plume_w=0.095):
    """A wall of spray along the sea line p0 -> p1 (the chain tearing out of the bay): a curtain sheet with a lobed top,
    big foam plumes along it (lumpy columns crowned and flanked by billows), a base surge rolling out on both sides, droplets, a foam
    band revealed behind the burst. zip = fraction of dur the burst takes to run from p0 to p1 (dur None = _auto_dur,
    capped at 6 s). The masses shade as one long mass along the line (props mk/mz/mdir).
    Returns [sheet, plumes, crests, surge, drops, foam]."""
    A = _xyz(p0); B = _xyz(p1); zc = A[2]; A[2] = B[2] = 0.0
    dur = dur or _auto_dur(height)
    R = np.random.RandomState(seed); frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3); Tz = zip * T
    L = np.linalg.norm(B - A); d = (B - A) / max(L, 1e-6); nr = np.array([-d[1], d[0], 0.0])
    ctr = (A + B) * 0.5; ctr[2] = zc
    wm = water_mat(); out = []
    props = {'mk': 0.5, 'mz': height * 0.3, 'mdir': tuple(d)}
    # ---- curtain
    NC = int(np.clip(L / 4.0, 24, 180)); NR = 14
    s = np.linspace(0, 1, NC)
    K = max(6, int(L / 16))
    ph = (np.arange(K) + R.uniform(-0.3, 0.3, K)) / K; wkk = 0.5 / K * R.uniform(0.6, 0.95, K); ak = R.uniform(0.55, 1.0, K)
    ftop = np.max(ak[None, :] * np.clip(1 - (np.abs(s[:, None] - ph[None, :]) / wkk[None, :]) ** 2, 0, 1) ** 0.6, axis=1)
    endt = _sm(s / 0.06) * _sm((1 - s) / 0.06)
    Hc = height * 0.48 * (0.55 + 0.45 * ftop) * (0.35 + 0.65 * endt) * (0.9 + 0.1 * np.sin(s * 23 + R.uniform(0, 6)))
    bow = np.sin(s * math.pi * R.uniform(1.4, 2.6) + R.uniform(0, 6))
    tb = Tz * s
    vj = np.linspace(0, 1, NR + 1)
    lump = 0.05 * np.sin(s[None, :] * L / 9.0 + vj[:, None] * 5.0 + R.uniform(0, 6)) * np.sin(math.pi * vj[:, None])         + 0.035 * np.sin(s[None, :] * L / 4.3 - vj[:, None] * 7.0 + R.uniform(0, 6))
    Vs = []
    for k, t in enumerate(ts):
        tau = t - tb
        rise = _eout(tau / (0.3 * T), 2.4) * (tau > 0); fall = _ein((tau - 0.36 * T) / (0.5 * T), 1.7)
        h = Hc * rise * (1 - 0.92 * fall) * (1 + 0.03 * np.sin(s * 40 + k * 1.3))
        z = h[None, :] * vj[:, None] ** 0.9 - 1.0 * (1 - vj[:, None])
        off = (bow * 0.07 * Hc * rise)[None, :] * np.sin(math.pi * vj[:, None]) + 0.06 * Hc[None, :] * vj[:, None] ** 4 * rise[None, :]
        P = A[None, None, :] + d[None, None, :] * (s * L)[None, :, None] + nr[None, None, :] * (off + lump * Hc[None, :] * rise[None, :])[..., None]
        P[..., 2] = z
        Vs.append((P - ctr * np.array([1, 1, 0])).reshape(-1, 3))
    J, I = np.meshgrid(np.arange(NR), np.arange(NC - 1), indexing='ij')
    a_ = J * NC + I; b_ = J * NC + I + 1; c_ = (J + 1) * NC + I + 1; d_ = (J + 1) * NC + I
    F = np.vstack([np.stack([a_, b_, c_], -1).reshape(-1, 3), np.stack([a_, c_, d_], -1).reshape(-1, 3)])
    VV = np.repeat(vj, NC); SS = np.tile(s, NR + 1)
    d0s = np.tile(tb + 0.5 * T, NR + 1)
    # brush: fine along the line, long up the curtain (flow streaks, not ice-like blobs)
    at = _std({'rp': np.stack([SS * L / 5.0, np.zeros_like(SS), VV * float(Hc.mean()) / 30.0], -1) + R.uniform(-40, 40, 3), 'tone': 0.12 * (1 - VV) ** 2,
               'bk': np.full(len(VV), 1.35), 'op': np.ones(len(VV)), 'd0': d0s, 'd1': d0s + 0.42 * T}, len(VV))
    sh = _mesh(name + '_sheet', Vs[0], F, coll, wm, loc=(ctr[0], ctr[1], zc), attrs=at)
    _props(sh, dict(props, mk=0.15))          # the thin curtain lies on the mass axis: mostly its own normal (lit face)
    _flip(sh, Vs, frames); _show(sh, frames[0], f_end); _keyp(sh, 't', frames, ts)
    out.append(sh)
    # ---- plume fans along the line
    npl = plumes or max(4, int(L / 28))
    sp = np.clip((np.arange(npl) + 0.5 + R.uniform(-0.25, 0.25, npl)) / npl, 0.03, 0.97)
    roots, dirs, Hs, dl = [], [], [], []
    for i in range(npl):
        base = A + d * sp[i] * L - ctr * np.array([1, 1, 0])
        for j in range(3):
            lean = R.uniform(0.05, 0.42); side = R.choice([-1, 1]) * R.uniform(0.3, 1.0); along = R.uniform(-0.5, 0.5)
            dv = _nrm(np.array([0, 0, 1.0]) * math.cos(lean) + (nr * side + d * along) * math.sin(lean))
            roots.append(base + d * R.uniform(-6, 6) + nr * R.uniform(-4, 4) + np.array([0, 0, -1.0])); dirs.append(dv)
            Hs.append(height * R.uniform(0.6, 1.08) * (0.55 + 0.45 * endt[int(sp[i] * (NC - 1))])); dl.append(Tz * sp[i] + R.uniform(0, 0.04) * T)
    roots = np.array(roots); dirs = np.array(dirs); Hs = np.array(Hs)
    JI = {}
    Ps, Ms, at, head = _jets(R, roots, dirs, Hs, ts, T, per=7, w=height * plume_w, Te=0.32, ta=0.4, delay=np.array(dl), hmax=height * 1.08,
                             info=JI, head_w=0.72)
    GEO = {}
    out.append(_jet_tubes(name + '_plumes', JI, frames, f_end, coll, wm, (ctr[0], ctr[1], zc), seed + 1, props=props, geo=GEO, **PLUME))
    out.append(_plume_lobes(name + '_crests', JI, GEO, frames, f_end, coll, wm, (ctr[0], ctr[1], zc), seed + 6, props=props))
    # ---- base surge, both sides
    n = max(16, int(L / 5)) * 2
    sb = R.uniform(0.02, 0.98, n); side = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    out1 = height * R.uniform(0.05, 0.3, n); sz0 = height * R.uniform(0.07, 0.12, n); spin = R.uniform(0, TAU, n)
    tbn = Tz * sb
    Ps, Ms = [], []
    for k, t in enumerate(ts):
        tau = np.clip(t - tbn, 0, None); u = tau / T; gk = _eout(u / 0.6, 2.0)
        base = A + d * (sb * L)[:, None] - ctr * np.array([1, 1, 0])
        pos = base + nr * (side * (height * 0.02 + out1 * gk))[:, None]
        sz = sz0 * (0.3 + 0.8 * np.clip(u / 0.2, 0, 1)) * (t > tbn)
        pos[:, 2] = height * 0.03 * (1 - 0.6 * gk) - sz * 0.3
        Ps.append(pos); Ms.append(_scale(_rot(np.tile([[0, 0, 1.0]], (n, 1)), spin + k * 0.3), sz * 1.2, sz * 1.2, sz * (0.85 - 0.3 * gk)))
    d0 = tbn + R.uniform(0.5, 0.65, n) * T
    # every billow is dissolved by the last drawing (the late end of the zip ran to 1.15 T: bits of it vanished with the
    # object, s34 f1717; 06.11): the window ends on the last drawing and is at least 0.12 T long
    d1 = np.minimum(d0 + 0.3 * T, ts[-1] - 0.01); d0 = np.minimum(d0, d1 - 0.12 * T)
    out.append(_pobj(name + '_surge', tpl_billow(seed + 2), Ps, Ms, frames, f_end, coll, wm, (ctr[0], ctr[1], zc),
                     {'tone': R.uniform(0.02, 0.1, n), 'd0': d0, 'd1': d1}, seed + 2, props=props))
    # ---- droplets
    nd = drops; sd = R.uniform(0, 1, nd)
    te = Tz * sd + R.uniform(0.15, 0.45, nd) * T
    P0 = A + d * (sd * L)[:, None] - ctr * np.array([1, 1, 0]) + nr * R.uniform(-5, 5, nd)[:, None]
    P0[:, 2] = height * R.uniform(0.4, 1.0, nd)
    Vup = 2 * height / (0.4 * T); g = 2 * height / (0.4 * T) ** 2
    V0 = (nr * R.choice([-1, 1], nd)[:, None] * R.uniform(0.08, 0.3, nd)[:, None] + d * R.uniform(-0.1, 0.1, nd)[:, None]) * Vup
    V0[:, 2] = Vup * R.uniform(0.0, 0.35, nd)
    Ps, Ms = _drops_state(R, P0, V0, te, height * R.uniform(0.01, 0.022, nd), ts, g, 0.0, 0.6 / Vup)
    out.append(_pobj(name + '_drops', tpl_drop(), Ps, Ms, frames, f_end, coll, wm, (ctr[0], ctr[1], zc), {'tone': R.uniform(0, 0.1, nd)}, seed + 3))
    if foam:
        path = [A - d * height * 0.15, B + d * height * 0.15]
        pth, Lp = _resample(path, max(L / 60.0, 2.0))
        head = np.clip((ts - 0.0) / max(Tz, 1e-3), 0, 1) * 1.0 + np.where(ts > Tz, (ts - Tz) / T, 0)
        fo = _foam_strip(pth, height * 0.9, frames, ts, int(f_end + dur * 0.4), head, Lp / max(Tz, 1e-3), 0.9 * T, coll, name + '_foam',
                         lift=_lift(height * 0.5), seed=seed + 5)
        out.append(fo)
    return out


def _bow_sheets(name, hps, hds, ts, T, size, frames, f_end, coll, mat, loc, seed, NU=48, NV=10):
    """the bow spray of something ploughing the sea: two open sheets thrown up and out from the head (a V swept back),
    highest a quarter of the way back, the top a lip curling out and over. The lip is scalloped into round lobes that run
    back along it on every drawing, each crowned by a foam bead riding its tip, so the sheet's edge never shows (torn into
    thin spikes on a flat white sheet it read as ice floes standing in the sea: check3 f1630 / f1647, 06.11); the brush runs
    up the sheet in flow streaks; drops peel off the lip; the sheets rise out of the sea at both ends. hps/hds: head
    position (rel. to loc) and travel direction per drawing. Grows in over 0.3 s and drops back at the end.
    -> [sheets, beads, drops]"""
    R = np.random.RandomState(seed)
    u = np.linspace(0.0, 1.0, NU); v = np.linspace(0.0, 1.0, NV)
    UU, VV = np.meshgrid(u, v, indexing='ij')                      # (NU, NV)
    NS = 12
    c0 = R.uniform(0, 1.1, (2, NS)); amp = R.uniform(0.08, 0.3, (2, NS)); wid = R.uniform(0.018, 0.04, (2, NS))
    phr = R.uniform(0, TAU, 2)
    # the lobes and their beads: an own stream (R's draws above and the drops' below stay as they were)
    Rb = np.random.RandomState(seed + 31)
    ak = 0.55 + 0.45 * (amp - 0.08) / 0.22                          # lobe heights 0.55 .. 1
    wl = Rb.uniform(0.045, 0.075, (2, NS))                          # lobe half-widths (fraction of the sheet's run)
    bs = Rb.uniform(0.1, 0.15, (2, NS)); bsp = Rb.uniform(0, TAU, (2, NS))
    sink = 0.35 * size
    lip = _sm((VV - 0.78) / 0.22)
    env = np.sin(np.pi * u ** 0.55) ** 0.75                         # the sheet's height along it: 0 at both ends
    Vs = []; tops = []; BP = []; BM = []
    for k, t in enumerate(ts):
        gt = _sm(t / 0.3) * (1.0 - _sm((t - (T * 0.98 - 0.25)) / 0.25))
        hp = np.asarray(hps[k], np.float64); hd = _nrm(np.asarray(hds[k], np.float64) * np.array([1.0, 1.0, 0.0]) + np.array([1e-6, 0, 0]))
        hs = np.array([-hd[1], hd[0], 0.0])
        V = []; tp = []; bp = []; bm = []
        for w, sgn in enumerate((1.0, -1.0)):
            cc = (c0[w] + 0.045 * k) % 1.1
            lob = np.max(ak[w][None, :] * np.clip(1.0 - ((u[:, None] - cc[None, :]) / wl[w][None, :]) ** 2, 0.0, 1.0) ** 0.5, axis=1)
            lob = lob + 0.04 * np.sin(u * 23.0 + 2.3 * k + phr[w])
            htop = size * 1.15 * gt * env * (0.8 + 0.24 * lob) + 0.05 * size * gt     # (NU,)
            base = hp[None, :] + hs[None, :] * (sgn * size * (0.2 + 1.0 * u ** 0.85))[:, None] - hd[None, :] * (size * (-0.1 + 2.0 * u))[:, None]
            ht = htop[:, None]
            z = -sink + VV ** 0.85 * (ht + sink) - 0.1 * ht * lip               # the lip droops as it curls out
            outw = 0.5 * VV ** 1.7 * ht + 0.16 * ht * lip + 0.06 * size * np.sin(UU * 9.0 + VV * 3.0 + 1.7 * k + phr[w]) * VV
            back = 0.3 * VV ** 1.3 * ht
            P = (base[:, None, :] + hs[None, None, :] * (sgn * outw)[..., None] - hd[None, None, :] * back[..., None])
            P[..., 2] = base[:, None, 2] + z
            V.append(P.reshape(-1, 3)); tp.append(P[:, -1, :].copy())
            # a bead on each lobe's tip, as big as the sheet is high there: grown in off the bow, none past the stern
            cu = np.clip(cc, 0.0, 1.0)
            pt = np.stack([np.interp(cu, u, P[:, -1, c]) for c in range(3)], 1)
            r = size * bs[w] * gt * np.interp(cu, u, env) * (0.75 + 0.25 * ak[w]) * _sm(cc / 0.12) * _sm((1.0 - cc) / 0.1)
            pt = pt + hs[None, :] * (sgn * 0.25 * r)[:, None] + np.array([0.0, 0.0, 1.0])[None, :] * (0.15 * r)[:, None]
            bp.append(pt); bm.append(_scale(_rot(np.tile([[0, 0, 1.0]], (NS, 1)), bsp[w] + k * 0.3), r, r, r * 0.9))
        Vs.append(np.vstack(V)); tops.append(tp); BP.append(np.vstack(bp)); BM.append(np.concatenate(bm))
    I, J = np.meshgrid(np.arange(NU - 1), np.arange(NV - 1), indexing='ij')
    a_ = I * NV + J; b_ = (I + 1) * NV + J; c_ = (I + 1) * NV + J + 1; d_ = I * NV + J + 1
    F1 = np.vstack([np.stack([a_, b_, c_], -1).reshape(-1, 3), np.stack([a_, c_, d_], -1).reshape(-1, 3)])
    nv1 = NU * NV
    F = np.vstack([F1, F1[:, ::-1] + nv1])                        # mirrored wing: flip the winding so both face outward
    Uf = np.tile(UU.ravel(), 2); Vf = np.tile(VV.ravel(), 2); sg = np.repeat([1.0, -1.0], nv1)
    # brush: fine along the sheet, long up it (flow streaks; the hard blobs of bk 1.5 on a flat sheet read as ice)
    rp = np.stack([Uf * 12.0, Vf * 1.4, sg * 5.0], 1) + R.uniform(-40, 40, 3)
    at = _std({'rp': rp, 'tone': 0.03 + 0.12 * (1 - Vf) ** 2, 'bk': np.full(2 * nv1, 1.25), 'op': np.ones(2 * nv1),
               'seed': np.repeat([0.3, 0.7], nv1)}, 2 * nv1)
    o = _mesh(name, Vs[0], F, coll, mat, loc=tuple(loc), attrs=at)
    # dropped back flat (its top edge on the sea) from 0.98 T: gone from that drawing when the drawings run on past the
    # head's stop (spray_trail's cut); otherwise the object's own end
    kz = next((k for k, t in enumerate(ts) if t >= T * 0.98), None)
    f_flat = frames[kz] if kz is not None else f_end
    _flip(o, Vs, frames); _show(o, frames[0], f_flat)
    _keyp(o, 't', frames, [(f - frames[0]) / FPS for f in frames])
    ob = _pobj(name + 'beads', tpl_billow(seed + 7, 3, 2), BP, BM, frames, f_flat, coll, mat, tuple(loc),
               {'tone': Rb.uniform(0.0, 0.05, 2 * NS), 'bk': np.full(2 * NS, 0.9)}, seed + 7)
    # drops peeling off the torn edge: born on the edge of the drawing they leave from, thrown out, up and back
    dt = STEP / FPS
    ne = max(6, int(T * 34)); wg = np.arange(ne) % 2
    tb = R.uniform(0.2, max(0.25, T * 0.95 - 0.3), ne); kb = np.clip(np.round(tb / dt).astype(int), 0, len(ts) - 1); tb = kb * dt + R.uniform(0, dt * 0.9, ne)
    ue = R.uniform(0.1, 0.65, ne)
    g = 9.81 * 2.2; Vd = math.sqrt(2 * g * size * 0.55)
    P0 = np.empty((ne, 3)); V0 = np.empty((ne, 3))
    for i in range(ne):
        tp = tops[kb[i]][wg[i]]
        P0[i] = np.array([np.interp(ue[i], u, tp[:, c]) for c in range(3)])
        hd = _nrm(np.asarray(hds[kb[i]], np.float64) * np.array([1.0, 1.0, 0.0]) + np.array([1e-6, 0, 0])); hs = np.array([-hd[1], hd[0], 0.0])
        sgn = 1.0 if wg[i] == 0 else -1.0
        V0[i] = (hs * sgn * R.uniform(0.3, 0.6) - hd * R.uniform(0.2, 0.5) + np.array([0, 0, 1.0]) * R.uniform(0.35, 0.8)) * Vd
    Ps, Ms = _drops_state(R, P0, V0, tb, size * R.uniform(0.035, 0.07, ne), ts, g, 0.0, 0.6 / Vd)
    od = _pobj(name + 'drops', tpl_drop(), Ps, Ms, frames, f_end, coll, mat, tuple(loc), {'tone': R.uniform(0, 0.08, ne)}, seed + 1)
    return [o, ob, od]

SKIP_T = 0.75                   # s: a trail skip's crown of spikes (release 0.19 s, apex 0.3 s, gone by ~0.8 s)


def spray_trail(points, f0=1, dur=48, coll=None, seed=0, size=6.0, skip=0.33, lift=None, cut=None, name='FX_trail'):
    """The chain end skipping over the waves along `points` [(x, y[, z]), ...] (travelled at constant speed over dur):
    every `skip` seconds a skip splash (billows stretched along their flight + droplets thrown back and sideways), a bow
    spray at the head, a V foam wake revealed behind the head (widening and dissolving with age). size ~ splash width in m.
    cut (frame, after the run's end): the drawings go on until the shot's cut with the head at rest (the bow has dropped
    back; the last skip's spikes, the drops and the bow's drops fall into the sea) and everything, the wake too, is gone
    from the cut - not on the frame the run ends, mid-shot (s33 f1665: the hand closing on the link; 06.11).
    Returns [spray, drops, wake]."""
    R = np.random.RandomState(seed); frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    if cut is not None and int(cut) > f_end:
        frames, ts, _ = _ft(f0, int(cut) - f0); f_end = int(cut)
    path, L = _resample(points, max(size * 0.5, 0.5))
    cl = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    spd = L / T
    def at_s(sv):
        return np.stack([np.interp(sv, cl, path[:, i]) for i in range(3)], -1)
    def tan_s(sv):
        e = max(L * 0.002, 0.05)
        return _nrm(at_s(np.clip(sv + e, 0, L)) - at_s(np.clip(sv - e, 0, L)))
    ctr = path.mean(0); ctr[2] = path[0, 2]
    wm = water_mat(); out = []
    nc = max(1, int(T / skip)); tcs = (np.arange(nc) + R.uniform(0.2, 0.8, nc)) * skip
    tcs = tcs[tcs < T * 0.95]; nc = len(tcs)
    B = 8; NW = 6; nb = nc * B + NW
    pc = at_s(np.minimum(tcs * spd, L)); dc = tan_s(np.minimum(tcs * spd, L))
    te = np.concatenate([np.repeat(tcs, B), np.zeros(NW)])
    p0 = np.concatenate([np.repeat(pc, B, 0), np.repeat(path[:1], NW, 0)]) - ctr
    dirc = np.concatenate([np.repeat(dc, B, 0), [dc[0] if nc else np.array([1.0, 0, 0])] * NW])
    side = np.concatenate([np.tile(np.where(np.arange(B) % 2 == 0, 1.0, -1.0), nc), np.where(np.arange(NW) < NW // 2, 1.0, -1.0)])
    sn = np.stack([-dirc[:, 1], dirc[:, 0], np.zeros(nb)], 1)
    Vs_ = math.sqrt(2 * 9.81 * 2.2 * size * 1.4)
    V0 = (-dirc * R.uniform(0.2, 0.6, nb)[:, None] + sn * (side * R.uniform(0.35, 0.8, nb))[:, None]) * Vs_ * 0.7
    V0[:, 2] = Vs_ * R.uniform(0.55, 1.0, nb)
    sz = size * R.uniform(0.18, 0.3, nb); g = 9.81 * 2.2; life = R.uniform(0.55, 0.85, nb); spin = R.uniform(0, TAU, nb)
    Ps, Ms = [], []
    for k, t in enumerate(ts):
        a = t - te; alive = (a >= 0) & (a < life); a = np.clip(a, 0, None)
        pos = p0 + V0 * a[:, None]; pos[:, 2] -= 0.5 * g * a ** 2
        vel = V0.copy(); vel[:, 2] -= g * a
        r = sz * (0.6 + 0.8 * np.clip(a / 0.35, 0, 1))
        # the bow spray rides with the head: two wings of 3 billows each, swept back, out and up (a V of spray)
        hp = at_s(min(t * spd, L)) - ctr; hd = tan_s(min(t * spd, L))
        hs = np.array([-hd[1], hd[0], 0.0])
        for q in range(NW):
            j = nb - NW + q; sgn = side[j]; w_ = q % (NW // 2)
            back, outw, up, rad = ((0.2, 0.35, 0.25, 0.24), (0.95, 0.8, 0.65, 0.18), (1.75, 1.15, 0.95, 0.13))[w_]
            pos[j] = hp + hs * sgn * size * outw - hd * size * back + np.array([0, 0, size * up])
            vel[j] = (hs * sgn * (0.6 + 0.3 * w_) - hd * (0.5 + 0.3 * w_) + np.array([0, 0, 1.0])) * Vs_
            r[j] = size * rad * (1.0 + 0.12 * math.sin(k * 2.1 + j)); alive[j] = t < T * 0.98
        alive &= pos[:, 2] > -r * 0.6
        st = np.clip(0.9 + np.linalg.norm(vel, axis=1) / Vs_ * 0.6, 0.9, 1.5)
        Rm = _frame_z(vel) @ _rot(np.tile([[0, 0, 1.0]], (nb, 1)), spin + k * 0.4)
        M = _scale(Rm, r, r, r * st); M[~alive] = 0.0
        Ps.append(pos); Ms.append(M)
    d0 = te + life * 0.55
    wing = np.arange(nb) >= nb - NW
    eat = {'tone': R.uniform(0.02, 0.12, nb), 'd0': np.where(wing, 1e5, d0), 'd1': np.where(wing, 2e5, te + life)}
    # the bow spray is drawn as two sheets (the wing billows above only keep the random stream of the skips unchanged)
    hps = [at_s(min(t * spd, L)) - ctr for t in ts]; hds = [tan_s(min(t * spd, L)) for t in ts]
    out.extend(_bow_sheets(name + '_bow', hps, hds, ts, T, size, frames, f_end, coll, wm, tuple(ctr), seed + 11))
    if nc:
        # every skip throws a small crown of spikes (the crowns' jets: ballistic columns that stretch, lift off and fall apart
        # by themselves) along the throws above - not big round drops, which read as white pillows on the sea. Own random
        # stream: the drops below keep theirs.
        Rj = np.random.RandomState(seed + 21); JPS = 5
        sj = np.concatenate([np.arange(c * B, c * B + JPS) for c in range(nc)])
        dj = _nrm(V0[sj] * np.array([1.0, 1.0, 1.35]))
        rj = p0[sj] + sn[sj] * (side[sj] * size * Rj.uniform(0.05, 0.3, len(sj)))[:, None] + np.array([0.0, 0.0, -0.4])
        Hj = size * Rj.uniform(0.55, 1.05, len(sj))
        JI = {}
        Pj, Mj, atj, hj = _jets(Rj, rj, dj, Hj, ts, SKIP_T, per=7, w=size * 0.11, Te=0.25, ta=0.4, delay=te[sj], hmax=size * 1.05, info=JI)
        out.append(_jet_tubes(name + '_skips', JI, frames, f_end, coll, wm, tuple(ctr), seed + 4))
        out.append(_pobj(name + '_skiph', tpl_drop(3, 1.0, 0.7), Pj, Mj, frames, f_end, coll, wm, tuple(ctr), atj, seed + 5, sel=hj))
    nd = nc * 12
    if nd:
        ted = np.repeat(tcs, 12) + R.uniform(0, 0.08, nd); pd = np.repeat(pc, 12, 0) - ctr; dd = np.repeat(dc, 12, 0)
        sdd = np.stack([-dd[:, 1], dd[:, 0], np.zeros(nd)], 1)
        V0d = (-dd * R.uniform(0.1, 0.7, nd)[:, None] + sdd * R.uniform(-0.9, 0.9, nd)[:, None]) * Vs_
        V0d[:, 2] = Vs_ * R.uniform(0.6, 1.25, nd)
        Ps, Ms = _drops_state(R, pd, V0d, ted, size * R.uniform(0.03, 0.06, nd), ts, g, 0.0, 0.5 / Vs_)
        out.append(_pobj(name + '_drops', tpl_drop(), Ps, Ms, frames, f_end, coll, wm, tuple(ctr), {'tone': R.uniform(0, 0.1, nd)}, seed + 2))
    lift = _lift(size * 3) if lift is None else lift
    head = np.clip(ts * spd / L, 0, 1)
    out.append(_foam_strip(path, size * 4.0, frames, ts, int(f_end + 48) if cut is None else int(f_end), head, spd, 2.2, coll,
                           name + '_wake', lift, seed + 3))
    return out


def droplets(center, f0=1, dur=36, coll=None, seed=0, count=60, speed=20.0, size=0.6, spread=0.7, up=(0, 0, 1), radius=0.0,
             gravity=None, delay=0.0, z_floor=0.0, outward=False, fadeout=0, name='FX_drops'):
    """A burst of drawn droplets (teardrops stretched along their velocity) from center (a disc of `radius`), inside a
    cone round `up` (spread 0..1 = 0..90 deg), speeds 0.45..1 x speed, launch spread over delay*dur, ballistic with
    gravity (default 1.6 g: snappy drawn timing), gone when they reach z_floor.
    outward: a splash round a body throws its drops away from it: a drop whose direction points back over the disc's
    centre is mirrored to point away from it (the same drops otherwise; the random stream is unchanged).
    fadeout = K: the drops still falling on the last drawing (far above their floor: rust off a chain in the sky) thin out
    over the last K drawings (_fadeout) instead of all vanishing with the object."""
    c = _xyz(center); R = np.random.RandomState(seed); frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    n = count; dirs = _cone_dirs(R, n, up, spread)
    spd = speed * R.uniform(0.45, 1.0, n)
    a = R.uniform(0, TAU, n); rr = radius * np.sqrt(R.uniform(0, 1, n))
    P0 = np.stack([np.cos(a) * rr, np.sin(a) * rr, np.zeros(n)], 1)
    if outward:
        rad = np.stack([np.cos(a), np.sin(a), np.zeros(n)], 1)
        dirs = dirs - 2.0 * np.minimum((dirs * rad).sum(1), 0.0)[:, None] * rad
    V0 = dirs * spd[:, None]
    te = R.uniform(0, delay, n) * T
    Ps, Ms = _drops_state(R, P0, V0, te, size * R.uniform(0.5, 1.2, n), ts, gravity or 9.81 * 1.6, z_floor - c[2], 1.3 / max(speed, 1e-3))
    if fadeout: Ms = _fadeout(Ms, seed, int(fadeout))
    return _pobj(name, tpl_drop(), Ps, Ms, frames, f_end, coll, water_mat(), tuple(c), {'tone': R.uniform(0, 0.12, n)}, seed)


# ================================================================================================================ steam, sparks, silt, bubbles
def steam(pos, f0=1, dur=48, coll=None, seed=0, count=10, size=3.0, direction=(0, 0, 1), speed=5.0, life=1.4, wind=(2.0, 0.0, 0.0),
          spread=0.25, tear=0.5, name='FX_steam'):
    """Steam puffs from pos: billows emitted over the duration, shot along `direction`, slowing (drag), drifting with
    `wind` (m/s), swelling from 0.35 to 1.6 x size, each torn apart by the hard dissolve from `tear` x its life on."""
    c = _xyz(pos); R = np.random.RandomState(seed); frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    n = count
    te = np.sort(np.concatenate([[0.0], R.uniform(0, max(T - life * 0.7, 0.05), n - 1)])) if n > 1 else np.zeros(1)
    dirs = _cone_dirs(R, n, direction, spread)
    v0 = dirs * (speed * R.uniform(0.7, 1.25, n))[:, None]
    lf = life * R.uniform(0.8, 1.2, n); s0 = size * R.uniform(0.75, 1.2, n); spin = R.uniform(0, TAU, n); k_ = 2.2
    # every puff is torn apart and gone by the last drawing: the late ones lived past the end and vanished whole with the
    # object (s12 f619, s23 f1133, the joints' rust dust, s35's vents; 06.11)
    lf = np.maximum(np.minimum(lf, (ts[-1] - te) / 1.02), 2.0 * STEP / FPS)
    wv = np.asarray(wind, np.float64)
    Ps, Ms = [], []
    for k, t in enumerate(ts):
        a = t - te; alive = (a >= 0) & (a <= lf); a = np.clip(a, 0, None)
        drag = (1 - np.exp(-a * k_)) / k_
        p = v0 * drag[:, None] + wv[None, :] * a[:, None]
        s = s0 * (0.35 + 1.25 * _eout(a / lf, 1.8))
        M = _scale(_rot(np.tile([[0, 0, 1.0]], (n, 1)), spin + k * 0.25), s, s, s * 0.9); M[~alive] = 0.0
        Ps.append(p); Ms.append(M)
    d0 = te + lf * tear
    return _pobj(name, tpl_billow(seed + 1), Ps, Ms, frames, f_end, coll, water_mat('M_fx_steam', PAL_STEAM, edges=(0.28, 0.45, 0.68), inside=0.0, edge=0.0),
                 tuple(c), {'tone': R.uniform(0, 0.12, n), 'd0': d0, 'd1': te + lf * 1.02}, seed)


def sparks(pos, f0=1, dur=24, coll=None, seed=0, count=40, speed=18.0, direction=(0, 0, 1), spread=0.9, size=1.0, gravity=9.81,
           life=(0.25, 0.7), burst=0.6, star=True, name='FX_sparks'):
    """Sparks from pos: glowing streaks (white-yellow core cooling to orange, glow AOV) on ballistic paths, length from
    their speed; `burst` = fraction thrown on the first drawing, the rest trickle; an optional star flash (2 drawings)."""
    c = _xyz(pos); R = np.random.RandomState(seed); frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    n = count; dirs = _cone_dirs(R, n, direction, spread)
    V0 = dirs * (speed * R.uniform(0.4, 1.0, n))[:, None]
    nb_ = int(n * burst); te = np.concatenate([np.zeros(nb_), R.uniform(0, max(T * 0.6, 0.05), n - nb_)])
    lf = R.uniform(life[0], life[1], n); g = gravity
    w = size * 0.06 * R.uniform(0.7, 1.3, n)
    Ps, Ms = [], []
    for t in ts:
        a = t - te; alive = (a >= 0) & (a <= lf); a = np.clip(a, 0, None)
        p = V0 * a[:, None]; p[:, 2] -= 0.5 * g * a ** 2
        vel = V0.copy(); vel[:, 2] -= g * a
        Ln = np.clip(np.linalg.norm(vel, axis=1) * 0.065, size * 0.3, size * 3.0) * (1 - 0.45 * np.clip(a / lf, 0, 1))
        M = _scale(_frame_z(vel + 1e-6), w, w, Ln); M[~alive] = 0.0
        Ps.append(p + _nrm(vel) * Ln[:, None] * -0.5); Ms.append(M)
    sp = _pobj(name, tpl_spindle(), Ps, Ms, frames, f_end, coll, spark_mat(), tuple(c), {'d0': te, 'd1': te + lf, 'lvl': np.zeros(n)}, seed)
    sp['power'] = 1.0
    out = [sp]
    if star:
        st = kira(name + '_star', c, size * 2.4, coll, inner='#fffbe6', outer='#ffab3d', n=9, seed=seed)
        flicker(st, [frames[0]], pattern=(1.0, 0.45))
        out.append(st)
    return out





def silt(center, f0=1, dur=72, coll=None, seed=0, radius=30.0, height=14.0, count=34, size=None, name='FX_silt'):
    """Brown underwater silt cloud bursting from center on the seabed: a ring of billows surging outward along the floor,
    a mushrooming plume in the middle, swelling and torn apart by the hard dissolve in the second half."""
    c = _xyz(center); R = np.random.RandomState(seed); frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    size = size or radius * 0.22
    n1 = int(count * 0.7); n2 = count - n1; n = count
    az = R.uniform(0, TAU, n); rf = np.concatenate([R.uniform(0.55, 1.0, n1), R.uniform(0.0, 0.3, n2)])
    zf = np.concatenate([R.uniform(0.0, 0.35, n1), R.uniform(0.35, 1.1, n2)])
    dl = R.uniform(0, 0.08, n) * T; s0 = size * R.uniform(0.7, 1.25, n); spin = R.uniform(0, TAU, n)
    Ps, Ms = [], []
    for k, t in enumerate(ts):
        a = np.clip(t - dl, 0, None); u = a / T; gk = _eout(u / 0.55, 2.3)
        rad = radius * rf * (0.15 + 0.85 * gk)
        z = height * zf * (0.25 + 0.75 * _eout(u / 0.7, 1.6))
        s = s0 * (0.4 + 0.95 * _eout(u / 0.6, 1.5)) * (t >= dl)
        Ps.append(np.stack([np.cos(az) * rad, np.sin(az) * rad, z], 1))
        Ms.append(_scale(_rot(np.tile([[0, 0, 1.0]], (n, 1)), spin + k * 0.2), s * 1.2, s * 1.2, s * 0.9))
    d0 = R.uniform(0.45, 0.62, n) * T
    return _pobj(name, tpl_billow(seed + 1), Ps, Ms, frames, f_end, coll, water_mat('M_fx_silt', PAL_SILT, edges=(0.3, 0.48, 0.72), inside=0.0, shadow=0.15, edge=0.0),
                 tuple(c), {'tone': R.uniform(0, 0.15, n), 'd0': d0, 'd1': d0 + 0.42 * T}, seed)


def bubbles(center, f0=1, dur=48, coll=None, seed=0, count=50, radius=4.0, size=0.45, rise=4.0, top=None, wobble=0.6, settle=False,
            name='FX_bubbles'):
    """Rising bubbles from a disc at center: bright rims, clear inside, highlight spots; they swell and wobble (squash
    on threes) and vanish at z = top (the sea surface, default 0) or after rising for the whole duration.
    settle: each bubble breaks up on its own drawing (shrinking over two drawings), the last one on the last drawing,
    instead of all of them going with the object (s16 f775: 70 bubbles in front of the lens gone in one frame, 06.11)."""
    c = _xyz(center); R = np.random.RandomState(seed); frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    top = 0.0 if top is None else top
    n = count; te = R.uniform(0, 0.7, n) * T
    a = R.uniform(0, TAU, n); rr = radius * np.sqrt(R.uniform(0, 1, n))
    P0 = np.stack([np.cos(a) * rr, np.sin(a) * rr, np.zeros(n)], 1)
    vr = rise * R.uniform(0.7, 1.3, n); s0 = size * R.uniform(0.4, 1.3, n) ** 1.5; ph = R.uniform(0, TAU, n)
    if settle:                                   # an own stream: the bubbles above keep theirs
        tend = te + (ts[-1] - te) * np.random.RandomState(seed + 4409).uniform(0.55, 1.0, n); w_ = 2.0 * STEP / FPS
    Ps, Ms = [], []
    for k, t in enumerate(ts):
        ag = t - te; alive = ag >= 0; ag = np.clip(ag, 0, None)
        z = vr * ag * (1 + 0.25 * ag)
        p = P0 + np.stack([wobble * np.sin(ag * 5 + ph), wobble * np.cos(ag * 4 + ph * 1.3), z], 1)
        s = s0 * (1 + 0.15 * ag)
        if settle:
            alive &= t < tend; s = s * np.clip((tend - t) / w_, 0.0, 1.0) ** 0.5
        sq = 0.13 * np.sin(k * 2.3 + ph)
        alive &= (c[2] + p[:, 2]) < top - s
        M = _scale(np.tile(np.eye(3), (n, 1, 1)), s * (1 + sq), s * (1 + sq), s * (1 - sq)); M[~alive] = 0.0
        Ps.append(p); Ms.append(M)
    return _pobj(name, (_ico(3)[0], _ico(3)[1], _ico(3)[0]), Ps, Ms, frames, f_end, coll, bubble_mat(), tuple(c), None, seed)


# ================================================================================================================ debris
def _box(sx, sy, sz):
    V = np.array([(x, y, z) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5)]) * (sx, sy, sz)
    F = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    return V, F


def _debris_mats():
    return {
        'flake': D.materials.get('M_fx_flake') or LK.cel('M_fx_flake', '#9c5530', ink=1.0, vary=0.18, vscale=0.6, grime=0.35, wscale=2.5),
        'wood': LK.cel('M_fx_wood', lambda nb: nb.mixc(nb.rgb('#b3804c'), nb.rgb('#82552f'), nb.step(0.62, nb.wave(nb.coord(), 1.6, 'BANDS', 'X', dist=4.0, detail=2.0))), ink=1.0, vary=0.1, grime=0.35, wscale=2.0) if D.materials.get('M_fx_wood') is None else D.materials['M_fx_wood'],
        'tile': D.materials.get('M_fx_tile') or LK.cel('M_fx_tile', '#c8553d', ink=1.0, vary=0.12, grime=0.3, chips=0.3, wscale=3.0),
        'concrete': D.materials.get('M_fx_concrete') or LK.cel('M_fx_concrete', '#c9c2b4', ink=1.0, vary=0.12, grime=0.5, chips=0.3, wscale=1.5),
        'steel': D.materials.get('M_fx_steel') or LK.cel('M_fx_steel', '#4b5163', ink=1.0, spec=0.6, rust=0.6, scuff=0.4, wscale=1.0),
        'cont': [D.materials.get('M_fx_cont%d' % i) or LK.cel('M_fx_cont%d' % i, (lambda c0, c1: (lambda nb: nb.stripes(nb.rgb(c0), nb.rgb(c1), 1.4, axis=(1.0, 0.0, 0.0), duty=0.5)))(c0, c1),
                                                               ink=1.0, spec=0.3, rust=0.45, chips=0.5, grime=0.3, wscale=0.8)
                 for i, (c0, c1) in enumerate((('#c43a2b', '#9e2c22'), ('#1f4fb0', '#183d88'), ('#2a8f8a', '#1f6d69'), ('#f2b705', '#c99404'), ('#ea7a24', '#c0621b')))],
    }


def _debris_bases(seed, kinds, size):
    """base meshes (shared by linked duplicates): kind -> [(mesh, material), ...] at the given size scale."""
    R = np.random.RandomState(seed); M = _debris_mats(); out = {}
    for kind in kinds:
        lst = []
        for v in range(3):
            if kind == 'plank':
                V, F = _box(3.2, 0.3, 0.1); mt = M['wood']
            elif kind == 'tile':
                a = np.linspace(-1.2, 1.2, 7); Vs = []
                for y in (-0.21, 0.21):
                    for k_ in a: Vs += [(math.sin(k_) * 0.17, y, math.cos(k_) * 0.17 - 0.12), (math.sin(k_) * 0.13, y, math.cos(k_) * 0.13 - 0.12)]
                V = np.array(Vs); n7 = 7; F = []
                idx = lambda yi, i, o: yi * n7 * 2 + i * 2 + o
                for i in range(n7 - 1):
                    for o in (0, 1):
                        q = (idx(0, i, o), idx(0, i + 1, o), idx(1, i + 1, o), idx(1, i, o)); F += [(q[0], q[1], q[2]), (q[0], q[2], q[3])] if o == 0 else [(q[0], q[2], q[1]), (q[0], q[3], q[2])]
                for yi in (0, 1):
                    for i in range(n7 - 1):
                        q = (idx(yi, i, 0), idx(yi, i + 1, 0), idx(yi, i + 1, 1), idx(yi, i, 1)); F += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
                V = V * 1.6; F = np.array(F); mt = M['tile']
            elif kind == 'container':
                nx_ = 9; xs = np.linspace(-2.4, 2.4, nx_); Vs = []
                bend = R.uniform(-0.5, 0.5)
                for x in xs:
                    zb = bend * (x / 2.4) ** 2 * 1.2
                    for y in (-1.2, 1.2):
                        for o in (-0.06, 0.06): Vs.append((x, y, zb + o))
                V = np.array(Vs); F = []
                idx = lambda i, yi, o: i * 4 + yi * 2 + o
                for i in range(nx_ - 1):
                    for o, flip in ((1, False), (0, True)):
                        q = (idx(i, 0, o), idx(i + 1, 0, o), idx(i + 1, 1, o), idx(i, 1, o))
                        F += [(q[0], q[1], q[2]), (q[0], q[2], q[3])] if not flip else [(q[0], q[2], q[1]), (q[0], q[3], q[2])]
                    for yi in (0, 1):
                        q = (idx(i, yi, 0), idx(i + 1, yi, 0), idx(i + 1, yi, 1), idx(i, yi, 1)); F += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
                F = np.array(F); mt = M['cont'][R.randint(len(M['cont']))]
            elif kind == 'beam':
                V, F = _box(4.5, 0.4, 0.32); mt = M['steel']
            elif kind == 'flake':
                # a flake of rust scale: a thin ragged plate ~1 m across (x size), curled
                ns = 7; a_ = np.sort(R.uniform(0, TAU, ns)); r_ = R.uniform(0.3, 0.55, ns)
                rim = np.stack([np.cos(a_) * r_, np.sin(a_) * r_ * R.uniform(0.55, 0.85), np.zeros(ns)], 1)
                h_ = 0.025
                V = np.vstack([[[0, 0, h_]], rim + (0, 0, h_), [[0, 0, -h_]], rim - (0, 0, h_)])
                V[:, 2] += R.uniform(0.4, 0.9) * V[:, 0] ** 2
                F = []
                for i in range(ns):
                    j = (i + 1) % ns
                    F += [(0, 1 + i, 1 + j), (ns + 1, ns + 2 + j, ns + 2 + i), (1 + i, ns + 2 + i, ns + 2 + j), (1 + i, ns + 2 + j, 1 + j)]
                F = np.array(F); mt = M['flake']
            else:   # chunk
                V0, F0 = _ico(2); V = V0 * R.uniform(0.6, 0.95, (len(V0), 1)) * np.array([1.0, 0.8, 0.65]) * 0.8; F = F0; mt = M['concrete']
            me = D.meshes.new('FX_debris_%s%d' % (kind, v))
            Vv = np.asarray(V, np.float32) * size
            me.vertices.add(len(Vv)); me.vertices.foreach_set('co', Vv.ravel())
            Fi = np.asarray(F, np.int32)
            me.loops.add(len(Fi) * 3); me.loops.foreach_set('vertex_index', Fi.ravel())
            me.polygons.add(len(Fi)); me.polygons.foreach_set('loop_start', np.arange(0, len(Fi) * 3, 3, dtype=np.int32))
            me.update(calc_edges=True); me.materials.append(mt)
            lst.append((me, None))
        out[kind] = lst
    return out


def debris(center, f0=1, dur=60, coll=None, seed=0, count=24, kinds=('plank', 'tile', 'container', 'chunk'), speed=28.0, spread=0.7,
           direction=(0, 0, 1), size=1.0, gravity=None, spin=6.0, radius=0.0, delay=0.15, z_floor=0.0, name='FX_debris'):
    """Debris thrown from center: planks, roof tiles, container panels (bent, corrugated, saturated colours), steel
    beams, concrete chunks (kinds), on ballistic arcs with tumbling spin (rad/s), keyed loc + rotation on threes; each
    piece is hidden from the drawing it falls below z_floor. Linked duplicates, ink 1 (props). Returns the objects."""
    c = _xyz(center); R = np.random.RandomState(seed); frames, ts, f_end = _ft(f0, dur); T = max(dur / FPS, 1e-3)
    bases = _debris_bases(seed + 3, kinds, size); C = _coll(coll)
    dirs = _cone_dirs(R, count, direction, spread); g = gravity or 9.81 * 1.4
    out = []
    for i in range(count):
        kind = kinds[i % len(kinds)]; me, _ = bases[kind][R.randint(len(bases[kind]))]
        o = D.objects.new('%s%02d' % (name, i), me); C.objects.link(o); o.rotation_mode = 'QUATERNION'
        v0 = dirs[i] * speed * R.uniform(0.45, 1.0); te = R.uniform(0, delay) * T
        a = R.uniform(0, TAU); rr = radius * math.sqrt(R.uniform()); p0 = c + np.array([math.cos(a) * rr, math.sin(a) * rr, 0.0])
        ax = Vector(_nrm(R.normal(size=3))); w = spin * R.uniform(0.4, 1.2); q0 = Quaternion(Vector(_nrm(R.normal(size=3))), R.uniform(0, TAU))
        # hidden only once the whole piece is under the water (its centre a bounding radius below): hidden with its centre
        # at -0.5 m a tumbling plank still stood out of the sea on the drawing before and vanished from it (s21 f1051, 06.11)
        rad_ = max((v.co.length for v in me.vertices), default=0.5)
        gone = None
        for f, t in zip(frames, ts):
            ag = max(t - te, 0.0)
            p = p0 + v0 * ag; p[2] -= 0.5 * g * ag * ag
            if p[2] < z_floor - rad_ - 0.3 and gone is None: gone = f
            o.location = tuple(p); o.keyframe_insert('location', frame=f)
            o.rotation_quaternion = Quaternion(ax, w * ag) @ q0; o.keyframe_insert('rotation_quaternion', frame=f)
        _show(o, frames[0], gone if gone is not None else f_end)
        _interp(o, 'CONSTANT')
        out.append(o)
    return out


# ================================================================================================================ build
def build(parent_collection=None, storm=True, spout=True, storm_opts=None, spout_opts=None, **opts):
    """The persistent FX set pieces: {'coll', 'storm': storm_wall(...), 'spout': waterspout(...)}. Everything else is
    made per shot with the functions above."""
    C = EV.coll('FX', parent_collection)
    out = {'coll': C}
    if storm: out['storm'] = storm_wall(C, **(storm_opts or {}))
    if spout: out['spout'] = waterspout(C, **(spout_opts or {}))
    return out
