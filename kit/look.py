# ANCHOR look library (Blender 5.2, Eevee). Every surface of the film is built here, so the whole film shares one look:
#   cel tones with lavender shadows (the key is the sun lamp, read through Shader-to-RGB), a warm bounce from below, a deep tone under
#   overhangs, hard specular, a rim when the sun is behind, hard-edged weathering, and five AOVs for the post: oid (object), mid (material),
#   ink (line weight), paint (gouache brush mask), glow (bloom source). Lights are never physical: every material ends in an Emission.
# Scene "uniforms" (custom props on the scene, read with VIEW_LAYER attribute nodes, keyable per frame):
#   sunD (unit vector TO the sun), sunC, skyC, shadeC, bounceC, deepC, flashC, flash (0..1 lightning), wet (0..1 storm wetness)
import bpy, math, os

REG = {}                      # material name -> {'mid': int, 'ink': float, 'paint': float}
_MID = [1]
SUNS = ('sunD', 'sunC', 'skyC', 'shadeC', 'bounceC', 'deepC', 'flashC')


def srgb(h, a=1.0):
    if isinstance(h, (tuple, list)): return tuple(h) if len(h) == 4 else (*h, a)
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c], a)


def set_uniforms(sc, **kw):
    """Scene uniforms with their defaults (Leviathan values); call once per scene, then key them per shot."""
    d = dict(sunD=(0.6, -0.3, 0.74), sunC='#fff1dc', skyC='#a9c4ff', shadeC='#9da3d6', bounceC='#d8c6c4', deepC='#6f68a3', flashC='#d9e4ff', flash=0.0, wet=0.0)
    d.update(kw)
    for k, v in d.items():
        if isinstance(v, str): v = srgb(v)[:3]
        sc[k] = v
    return d


def key_uniform(sc, name, frame, value):
    if isinstance(value, str): value = srgb(value)[:3]
    sc[name] = value; sc.keyframe_insert('["%s"]' % name, frame=frame)


class NB:
    """A small node builder: every helper returns an output socket."""
    def __init__(s, name):
        m = bpy.data.materials.new(name); m.use_nodes = True
        s.m = m; s.nt = m.node_tree; s.N = s.nt.nodes; s.L = s.nt.links; s.N.clear(); s._geo = None; s._tc = None; s._attrs = {}

    def put(s, sock, v):
        if v is None: return
        if isinstance(v, bpy.types.NodeSocket): s.L.new(v, sock)
        elif isinstance(v, str): sock.default_value = srgb(v)
        else:
            try: sock.default_value = v
            except TypeError: sock.default_value = (*v, 1.0) if len(v) == 3 else v

    @staticmethod
    def sock(n, ident, out=False):
        for x in (n.outputs if out else n.inputs):
            if x.identifier == ident: return x
        for x in (n.outputs if out else n.inputs):
            if x.name == ident and x.enabled: return x
        raise KeyError(ident)

    def new(s, t, props=None, ins=None):
        n = s.N.new(t)
        for k, v in (props or {}).items(): setattr(n, k, v)
        for k, v in (ins or {}).items(): s.put(n.inputs[k], v)
        return n

    # ---- scalars
    def math(s, op, a, b=None, c=None, clamp=False):
        n = s.N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        s.put(n.inputs[0], a)
        if b is not None: s.put(n.inputs[1], b)
        if c is not None: s.put(n.inputs[2], c)
        return n.outputs[0]
    def add(s, a, b): return s.math('ADD', a, b)
    def mul(s, a, b): return s.math('MULTIPLY', a, b)
    def sub(s, a, b): return s.math('SUBTRACT', a, b)
    def mx(s, a, b): return s.math('MAXIMUM', a, b)
    def mn(s, a, b): return s.math('MINIMUM', a, b)
    def smooth(s, v, e0, e1):          # smoothstep(e0, e1, v); e0 > e1 gives the falling edge
        if isinstance(e0, (int, float)) and isinstance(e1, (int, float)) and e0 > e1: return s.math('SUBTRACT', 1.0, s.smooth(v, e1, e0))
        n = s.N.new('ShaderNodeMapRange'); n.interpolation_type = 'SMOOTHSTEP'; n.clamp = True
        s.put(n.inputs['Value'], v); s.put(n.inputs['From Min'], e0); s.put(n.inputs['From Max'], e1)
        return n.outputs['Result']
    def remap(s, v, a0, a1, b0, b1, clamp=True):
        n = s.N.new('ShaderNodeMapRange'); n.clamp = clamp; s.put(n.inputs['Value'], v)
        for k, x in (('From Min', a0), ('From Max', a1), ('To Min', b0), ('To Max', b1)): s.put(n.inputs[k], x)
        return n.outputs['Result']
    def step(s, edge, v): return s.math('GREATER_THAN', v, edge)

    # ---- vectors
    def vmath(s, op, a, b=None, scale=None):
        n = s.N.new('ShaderNodeVectorMath'); n.operation = op
        s.put(n.inputs[0], a)
        if b is not None: s.put(n.inputs[1], b)
        if scale is not None: s.put(n.inputs['Scale'], scale)
        return n.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs['Vector']
    def xyz(s, v):
        n = s.N.new('ShaderNodeSeparateXYZ'); s.put(n.inputs[0], v); return n.outputs['X'], n.outputs['Y'], n.outputs['Z']
    def vec(s, x, y, z):
        n = s.N.new('ShaderNodeCombineXYZ'); s.put(n.inputs[0], x); s.put(n.inputs[1], y); s.put(n.inputs[2], z); return n.outputs[0]
    def geo(s):
        if s._geo is None: s._geo = s.N.new('ShaderNodeNewGeometry')
        return s._geo
    def tc(s):
        if s._tc is None: s._tc = s.N.new('ShaderNodeTexCoord')
        return s._tc
    def coord(s, kind='Object', scale=None, offset=None):
        v = s.tc().outputs[kind] if kind in ('Object', 'Generated', 'UV', 'Camera', 'Window') else s.geo().outputs['Position']
        if scale is not None: v = s.vmath('MULTIPLY', v, scale if not isinstance(scale, (int, float)) else (scale, scale, scale))
        if offset is not None: v = s.vmath('ADD', v, offset)
        return v

    # ---- colours
    def rgb(s, h):
        n = s.N.new('ShaderNodeRGB'); n.outputs[0].default_value = srgb(h); return n.outputs[0]
    def mixc(s, a, b, f, blend='MIX', clamp=False):
        n = s.N.new('ShaderNodeMix'); n.data_type = 'RGBA'; n.blend_type = blend; n.clamp_result = clamp
        s.put(s.sock(n, 'Factor_Float'), f); s.put(s.sock(n, 'A_Color'), a); s.put(s.sock(n, 'B_Color'), b)
        return s.sock(n, 'Result_Color', out=True)
    def cmul(s, a, b): return s.mixc(a, b, 1.0, 'MULTIPLY')
    def cadd(s, a, b, f=1.0): return s.mixc(a, b, f, 'ADD')
    def cscale(s, a, k): return s.vmath('SCALE', a, scale=k)
    def hsv(s, c, h=0.5, sat=1.0, val=1.0):
        n = s.N.new('ShaderNodeHueSaturation'); s.put(n.inputs['Color'], c); s.put(n.inputs['Hue'], h); s.put(n.inputs['Saturation'], sat); s.put(n.inputs['Value'], val)
        return n.outputs['Color']
    def ramp(s, v, stops, interp='CONSTANT'):
        r = s.N.new('ShaderNodeValToRGB'); r.color_ramp.interpolation = interp; e = r.color_ramp.elements
        e[0].position = stops[0][0]; e[0].color = srgb(stops[0][1]); e[1].position = stops[1][0]; e[1].color = srgb(stops[1][1])
        for p, c in stops[2:]: x = e.new(p); x.color = srgb(c)
        s.put(r.inputs['Fac'], v); return r.outputs['Color']
    def bw(s, c):
        n = s.N.new('ShaderNodeRGBToBW'); s.put(n.inputs[0], c); return n.outputs[0]
    def attr(s, name, out='Color', kind='VIEW_LAYER'):
        key = (name, kind)
        if key not in s._attrs:
            a = s.N.new('ShaderNodeAttribute'); a.attribute_type = kind; a.attribute_name = name; s._attrs[key] = a
        return s._attrs[key].outputs[out]
    def objattr(s, name, out='Fac'): return s.attr(name, out, 'OBJECT')

    # ---- textures
    def noise(s, v=None, scale=1.0, detail=2.0, rough=0.5, dist=0.0, w=None, out='Fac'):
        n = s.N.new('ShaderNodeTexNoise'); n.noise_dimensions = '4D' if w is not None else '3D'
        s.put(n.inputs['Scale'], scale); s.put(n.inputs['Detail'], detail); s.put(n.inputs['Roughness'], rough); s.put(n.inputs['Distortion'], dist)
        if w is not None: s.put(n.inputs['W'], w)
        s.put(n.inputs['Vector'], v if v is not None else s.coord()); return n.outputs[out]
    def voronoi(s, v=None, scale=1.0, feature='F1', metric='EUCLIDEAN', rand=1.0, out='Distance', w=None):
        n = s.N.new('ShaderNodeTexVoronoi'); n.feature = feature; n.distance = metric; n.voronoi_dimensions = '4D' if w is not None else '3D'
        s.put(n.inputs['Scale'], scale); s.put(n.inputs['Randomness'], rand)
        if w is not None: s.put(n.inputs['W'], w)
        s.put(n.inputs['Vector'], v if v is not None else s.coord()); return n.outputs[out]
    def wave(s, v=None, scale=1.0, kind='BANDS', axis='X', profile='SIN', dist=0.0, detail=0.0, phase=0.0):
        n = s.N.new('ShaderNodeTexWave'); n.wave_type = kind; n.bands_direction = axis; n.wave_profile = profile
        s.put(n.inputs['Scale'], scale); s.put(n.inputs['Distortion'], dist); s.put(n.inputs['Detail'], detail); s.put(n.inputs['Phase Offset'], phase)
        s.put(n.inputs['Vector'], v if v is not None else s.coord()); return n.outputs['Fac']
    def image(s, path, v=None, extension='CLIP', interp='Linear', alpha=False, noncolor=False):
        n = s.N.new('ShaderNodeTexImage'); img = bpy.data.images.load(path, check_existing=True)
        if noncolor: img.colorspace_settings.name = 'Non-Color'
        n.image = img; n.extension = extension; n.interpolation = interp
        if v is not None: s.put(n.inputs['Vector'], v)
        return n.outputs['Alpha'] if alpha else n.outputs['Color']
    def stripes(s, a, b, freq=1.0, v=None, axis=(1.0, 0.0, 1.0), duty=0.5):
        """Hazard stripes: bands along dot(p, axis)*freq, hard edges."""
        p = v if v is not None else s.coord()
        d = s.vmath('DOT_PRODUCT', p, axis); f = s.math('FRACT', s.mul(d, freq))
        return s.mixc(a, b, s.step(duty, f))


def _vary(nb, col, amt, scale, coord='Object', steps=3, seed=0.0):
    """Painted value patches: snapped noise, like gouache laid in a few strokes."""
    n = nb.noise(nb.coord(coord), scale, 3.0, 0.55, 0.3, w=seed)
    q = nb.math('SNAP', n, 1.0 / steps)
    k = nb.remap(q, 0.3, 0.7, 1.0 - amt, 1.0 + amt)
    return nb.hsv(col, 0.5, 1.0, k)


def weather(nb, col, grime=0.0, scuff=0.0, chips=0.0, rust=0.0, algae=0.0, waterline=0.0, scale=1.0, coord='Object', seed=0.0):
    """Leviathan-style hard-edged weathering. scale: 1 = sized for a ~10 m panel."""
    P = nb.coord(coord)
    if grime:
        g = nb.noise(nb.vmath('SCALE', P, scale=0.35 * scale), 1.0, 4.0, 0.62, 0.6, w=seed + 1.0)
        m = nb.mul(nb.smooth(g, 0.56, 0.585), grime)
        col = nb.mixc(col, nb.cmul(col, '#b9b3d6'), m)
    if scuff:
        sv = nb.vmath('MULTIPLY', P, (2.4 * scale, 2.4 * scale, 0.32 * scale))
        g = nb.noise(sv, 1.0, 3.0, 0.7, 0.0, w=seed + 2.0)
        m = nb.mul(nb.smooth(g, 0.66, 0.68), scuff)
        col = nb.mixc(col, nb.hsv(col, 0.5, 0.8, 1.22), m)
    if chips:
        g = nb.noise(nb.vmath('SCALE', P, scale=1.6 * scale), 1.0, 5.0, 0.68, 0.25, w=seed + 3.0)
        rim = nb.mul(nb.smooth(g, 0.615, 0.63), chips)
        core = nb.mul(nb.smooth(g, 0.655, 0.665), chips)
        col = nb.mixc(col, '#e4dccb', rim); col = nb.mixc(col, '#4a3f4e', core)
    if rust:
        sv = nb.vmath('MULTIPLY', P, (3.2 * scale, 3.2 * scale, 0.22 * scale))
        g = nb.noise(sv, 1.0, 4.0, 0.6, 0.4, w=seed + 4.0)
        g2 = nb.noise(nb.vmath('SCALE', P, scale=0.5 * scale), 1.0, 2.0, 0.5, 0.0, w=seed + 5.0)
        m = nb.mul(nb.mul(nb.smooth(g, 0.6, 0.63), nb.smooth(g2, 0.45, 0.55)), rust)
        col = nb.mixc(col, nb.mixc(col, '#9a4f2a', 0.75), m)
    if algae:
        z = nb.xyz(nb.geo().outputs['Position'])[2]
        n = nb.noise(nb.vmath('SCALE', P, scale=2.0 * scale), 1.0, 3.0, 0.6, 0.0, w=seed + 6.0)
        zz = nb.add(z, nb.mul(nb.sub(n, 0.5), 0.9))
        under = nb.smooth(zz, waterline + 0.15, waterline - 0.15)
        band = nb.mul(nb.smooth(zz, waterline + 1.4, waterline + 1.0), nb.sub(1.0, under))
        col = nb.mixc(col, nb.cmul(col, '#b8b39a'), nb.mul(band, 0.8 * algae))
        col = nb.mixc(col, '#3f5a3a', nb.mul(under, algae))
    return col


def shade(nb, col, spec=0.0, rim=0.35, deep=0.55, lit_override=None, flash=1.0, wet=0.0):
    """The cel light model. Returns the shaded colour socket."""
    if lit_override is None:
        d = nb.new('ShaderNodeBsdfDiffuse', ins={'Color': (1, 1, 1, 1)})
        s2r = nb.N.new('ShaderNodeShaderToRGB'); nb.L.new(d.outputs[0], s2r.inputs[0])
        Lraw = nb.bw(s2r.outputs['Color'])
        lit = nb.smooth(Lraw, 0.012, 0.055)
    else: lit = lit_override
    g = nb.geo(); N = g.outputs['Normal']; I = g.outputs['Incoming']
    up = nb.add(nb.mul(nb.xyz(N)[2], 0.5), 0.5)
    sunC = nb.attr('sunC'); skyC = nb.attr('skyC'); sunD = nb.attr('sunD', 'Vector')
    litT = nb.mixc(skyC, nb.cscale(sunC, 1.06), 0.85)
    litCol = nb.cmul(col, litT)
    shadeCol = nb.cmul(nb.cmul(col, nb.attr('shadeC')), nb.mixc(nb.attr('bounceC'), (1, 1, 1, 1), up))
    c = nb.mixc(shadeCol, litCol, 0.12)
    c = nb.mixc(c, litCol, lit)
    ndl = nb.vmath('DOT_PRODUCT', N, sunD)
    if deep:
        dm = nb.mul(nb.mul(nb.smooth(ndl, -0.45, -0.62), nb.smooth(nb.xyz(N)[2], -0.25, -0.42)), nb.mul(nb.sub(1.0, lit), deep))
        c = nb.mixc(c, nb.cmul(col, nb.attr('deepC')), dm)
    if spec:
        R = nb.vmath('REFLECT', nb.vmath('SCALE', I, scale=-1.0), N)
        sd = nb.vmath('DOT_PRODUCT', R, sunD)
        sm = nb.mul(nb.mul(nb.smooth(sd, 0.982, 0.99), lit), spec)
        c = nb.mixc(c, nb.cscale(sunC, 1.25), sm)
    if rim:
        back = nb.math('POWER', nb.mx(nb.vmath('DOT_PRODUCT', nb.vmath('SCALE', I, scale=-1.0), sunD), 0.0), 2.0)
        facing = nb.sub(1.0, nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', N, I)))
        rm = nb.mul(nb.mul(nb.smooth(facing, 0.62, 0.8), back), rim)
        c = nb.mixc(c, nb.cscale(sunC, 1.3), rm)
    if flash:
        fl = nb.mul(nb.attr('flash', 'Fac'), nb.mul(nb.add(nb.mul(up, 0.5), 0.5), flash))
        c = nb.mixc(c, nb.cmul(nb.attr('flashC'), nb.mixc(col, (1, 1, 1, 1), 0.5)), nb.mul(fl, 0.8))
    if wet:
        wv = nb.mul(nb.attr('wet', 'Fac'), wet)
        c = nb.mixc(c, nb.cmul(c, '#c9cde6'), nb.mul(wv, 0.5))
    return c


def finish(nb, col, ink=1.0, paint=0.0, glow=0.0, alpha=None, strength=1.0, blend=False, hz=1.0):
    m = nb.m; mid = _MID[0]; _MID[0] += 1
    REG[m.name] = {'mid': mid, 'ink': float(ink) if not isinstance(ink, bpy.types.NodeSocket) else -1, 'paint': float(paint) if not isinstance(paint, bpy.types.NodeSocket) else -1}
    out = nb.N.new('ShaderNodeOutputMaterial'); em = nb.N.new('ShaderNodeEmission'); nb.put(em.inputs['Color'], col); nb.put(em.inputs['Strength'], strength)
    surf = em.outputs[0]
    if alpha is not None:
        tr = nb.N.new('ShaderNodeBsdfTransparent'); mxs = nb.N.new('ShaderNodeMixShader'); nb.put(mxs.inputs['Fac'], alpha)
        nb.L.new(tr.outputs[0], mxs.inputs[1]); nb.L.new(surf, mxs.inputs[2]); surf = mxs.outputs[0]
        m.surface_render_method = 'BLENDED' if blend else 'DITHERED'
    nb.L.new(surf, out.inputs['Surface'])
    oi = nb.N.new('ShaderNodeObjectInfo')
    for name, v in (('oid', oi.outputs['Random']), ('mid', mid / 4096.0), ('ink', ink), ('paint', paint), ('glow', glow), ('hz', hz)):
        a = nb.N.new('ShaderNodeOutputAOV'); a.aov_name = name; nb.put(a.inputs['Value'], v)
    return m


def cel(name, color, ink=1.0, paint=0.0, spec=0.0, rim=0.35, deep=0.55, vary=0.07, vscale=0.15, coord='Object', seed=0.0,
        grime=0.0, scuff=0.0, chips=0.0, rust=0.0, algae=0.0, waterline=0.0, wscale=1.0, glow=0.0, alpha=None, wet=0.6, flash=1.0, steps=3):
    """The workhorse. color: hex string, or a callable nb -> colour socket (stripes, windows, decals...)."""
    nb = NB(name)
    col = nb.rgb(color) if isinstance(color, (str, tuple)) else color(nb)
    if vary: col = _vary(nb, col, vary, vscale, coord, steps, seed)
    if grime or scuff or chips or rust or algae:
        col = weather(nb, col, grime, scuff, chips, rust, algae, waterline, wscale, coord, seed)
    c = shade(nb, col, spec, rim, deep, flash=flash, wet=wet)
    return finish(nb, c, ink, paint, glow, alpha)


def glowmat(name, color, strength=4.0, ink=0.0, alpha=None, glow=1.0, blend=False):
    """Self-lit: beacons, visor, crystals, lightning. color may be a callable."""
    nb = NB(name)
    col = nb.rgb(color) if isinstance(color, (str, tuple)) else color(nb)
    return finish(nb, col, ink, 0.0, glow, alpha, strength, blend)


def flat(name, color, ink=0.0, paint=0.0, alpha=None, strength=1.0, blend=False):
    """Unlit colour (painted cards, far backdrops)."""
    nb = NB(name)
    col = nb.rgb(color) if isinstance(color, (str, tuple)) else color(nb)
    return finish(nb, col, ink, paint, 0.0, alpha, strength, blend)


def assign(o, m, slot=None):
    if o.data is None: return o
    if slot is None:
        o.data.materials.clear(); o.data.materials.append(m)
    else:
        while len(o.data.materials) <= slot: o.data.materials.append(m)
        o.data.materials[slot] = m
    return o


def save_registry(path):
    import json
    json.dump(REG, open(path, 'w'), indent=0)
