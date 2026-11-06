# ANCHOR environment: sky dome, sun, cumulus towers, the sea, the render setup and the compositor (paint mix + data passes).
# World units are metres, Blender Z up, sea level z = 0. North +Y, east +X. The storm comes from the west (-X).
import bpy, bmesh, math, os, random, json, time
from mathutils import Vector, Matrix, Euler
import look as LK
from look import NB, srgb

D = bpy.data


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    return sc


def coll(name, parent=None):
    c = D.collections.new(name); (parent or bpy.context.scene.collection).children.link(c); return c


def link(o, c=None):
    (c or bpy.context.scene.collection).objects.link(o); return o


def mesh_obj(name, verts, faces, mat=None, c=None, smooth=False):
    me = D.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces]); me.update()
    if smooth: me.shade_smooth()
    o = D.objects.new(name, me); link(o, c)
    if mat: me.materials.append(mat)
    return o


def bm_obj(name, bm, mat=None, c=None, smooth=False):
    me = D.meshes.new(name); bm.to_mesh(me); bm.free(); me.update()
    if smooth: me.shade_smooth()
    o = D.objects.new(name, me); link(o, c)
    if mat: me.materials.append(mat)
    return o


# ---------------------------------------------------------------------------------------------------------------------------------- sun
def sun_dir(az_deg, el_deg):
    """Direction TO the sun. az: 0 = north (+Y), 90 = east (+X)."""
    a = math.radians(az_deg); e = math.radians(el_deg)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def sun(sc, az=100.0, el=18.0, color='#fff1dc', c=None):
    ld = D.lights.new('SUN', 'SUN'); ld.energy = 1.0; ld.angle = math.radians(0.35); ld.color = (1, 1, 1)
    try: ld.use_shadow = True; ld.shadow_maximum_resolution = 0.001
    except Exception: pass
    o = D.objects.new('SUN', ld); link(o, c)
    aim_sun(sc, o, az, el)
    LK.set_uniforms(sc, sunD=tuple(sun_dir(az, el)), sunC=color)
    return o


def aim_sun(sc, o, az, el, frame=None):
    d = sun_dir(az, el)
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = (-d).to_track_quat('-Z', 'Y')
    sc['sunD'] = tuple(d)
    if frame is not None:
        o.keyframe_insert('rotation_quaternion', frame=frame); sc.keyframe_insert('["sunD"]', frame=frame)


# ---------------------------------------------------------------------------------------------------------------------------------- sky
SKY_PRESETS = {
    # zenith, mid, horizon (cool side), horizon (sun side), sun glow
    'morning': ('#1544c9', '#2b74e8', '#b4dafe', '#ffe2bd', '#fff6e4'),
    'storm':   ('#2a2f6e', '#4b4f96', '#8d8fc4', '#f2c9a0', '#ffe9cc'),
    'clear':   ('#1747d0', '#2f7ef0', '#c9e8ff', '#fff0d6', '#ffffff'),
}


def sky(sc, preset='morning', radius=24000.0, c=None):
    """A painted dome: gradient by elevation, warm horizon on the sun side, cirrus wisps. Colours are scene uniforms so shots can blend."""
    z, m, hc, hw, sg = SKY_PRESETS[preset]
    for k, v in (('skyZ', z), ('skyM', m), ('skyHc', hc), ('skyHw', hw), ('skyG', sg)): sc[k] = srgb(v)[:3]
    sc['skyStorm'] = 0.0; sc['skyDeck'] = 0.0
    nb = NB('M_sky')
    g = nb.geo(); P = g.outputs['Position']
    # direction from the dome centre (the dome follows the camera, so use the object-space position)
    d = nb.vmath('NORMALIZE', nb.tc().outputs['Object'])
    dx, dy, dz = nb.xyz(d)
    eld = nb.math('ARCSINE', nb.math('MAXIMUM', dz, -1.0))
    el = nb.mul(eld, 57.2958)
    sunD = nb.attr('sunD', 'Vector')
    sx, sy, sz = nb.xyz(sunD)
    hd = nb.vmath('NORMALIZE', nb.vec(dx, dy, 0.0)); hs = nb.vmath('NORMALIZE', nb.vec(sx, sy, 0.0))
    side = nb.add(nb.mul(nb.vmath('DOT_PRODUCT', hd, hs), 0.5), 0.5)
    hor = nb.mixc(nb.attr('skyHc'), nb.attr('skyHw'), nb.smooth(side, 0.35, 1.0))
    h = nb.mx(el, 0.0)
    col = nb.mixc(hor, nb.attr('skyM'), nb.smooth(h, 0.0, 9.0))
    col = nb.mixc(col, nb.attr('skyZ'), nb.smooth(h, 6.0, 62.0))
    toSun = nb.vmath('DOT_PRODUCT', d, sunD)
    glow = nb.math('POWER', nb.mx(toSun, 0.0), 14.0)
    col = nb.mixc(col, nb.mixc(hor, (1, 1, 1, 1), 0.35), nb.mul(glow, 0.5))
    disk = nb.smooth(toSun, 0.99955, 0.99975)
    # skyDeck (0..1, scene uniform; common.base keys it 1 from the first strike to the release): the storm deck is overhead,
    # the whole dome is under it whatever the heading; it hides the sun's disc (the glow still lifts the east horizon a little)
    storm = nb.attr('skyStorm', 'Fac')
    deck = nb.attr('skyDeck', 'Fac')
    disk = nb.mul(disk, nb.sub(1.0, deck))
    col = nb.mixc(col, nb.cscale(nb.attr('skyG'), 1.6), disk)
    # cirrus wisps: stretched noise in the sky plane, only up in the blue
    cp = nb.vmath('DIVIDE', nb.vec(dx, dy, 0.0), nb.vec(nb.add(dz, 0.25), nb.add(dz, 0.25), 1.0))
    rot = nb.vec(nb.add(nb.mul(nb.xyz(cp)[0], 0.8), nb.mul(nb.xyz(cp)[1], 0.6)), nb.add(nb.mul(nb.xyz(cp)[0], -0.6), nb.mul(nb.xyz(cp)[1], 0.8)), 0.0)
    st = nb.vmath('MULTIPLY', rot, (0.9, 5.5, 1.0))
    n1 = nb.noise(st, 1.4, 4.0, 0.55, 0.0, w=nb.attr('skyDrift', 'Fac'))
    n2 = nb.noise(nb.vmath('SCALE', rot, scale=0.5), 1.2, 2.0, 0.5, 0.0)
    wisp = nb.mul(nb.mul(nb.smooth(nb.mul(n1, n2), 0.29, 0.36), nb.smooth(dz, 0.1, 0.35)), 0.3)
    col = nb.mixc(col, nb.mixc(col, (1, 1, 1, 1), 0.7), wisp)
    # storm: the dome darkens from the west under a bruise of indigo while the storm comes in; once the deck is overhead it
    # covers every heading in the same tones (the west keeps exactly its look)
    west = nb.smooth(nb.mul(dx, -1.0), -0.6, 0.7)
    cover = nb.mx(west, deck)
    sto = nb.mixc(col, nb.mixc(srgb('#33306b'), srgb('#6a5ea8'), nb.smooth(h, 30.0, 0.0)), nb.mul(cover, 0.85))
    col = nb.mixc(col, sto, storm)
    below = nb.step(0.0, nb.mul(dz, -1.0))
    col = nb.mixc(col, nb.cscale(hor, 0.98), below)
    flash = nb.attr('flash', 'Fac')
    col = nb.mixc(col, nb.mixc(col, srgb('#e6ecff'), 0.65), flash)
    m = LK.finish(nb, col, ink=0.0, paint=1.0, hz=0.0)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=radius)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    o = bm_obj('SKY', bm, m, c, smooth=True)
    o.visible_shadow = False
    try: o.visible_diffuse = False; o.visible_glossy = False; o.visible_volume_scatter = False
    except Exception: pass
    sc['skyDrift'] = 0.0
    return o


# ---------------------------------------------------------------------------------------------------------------------------------- clouds
def cloud_mat(name='M_cloud', lit='#ffffff', mid='#f1f4fb', shadec='#98a5da', base='#b7c1e8', far=0.0):
    """Cumulus: three hard tones from the sun, a blue base, a silver rim against the sun, painted by the brush."""
    nb = NB(name)
    g = nb.geo(); N = g.outputs['Normal']; I = g.outputs['Incoming']; P = g.outputs['Position']
    sunD0 = nb.attr('sunD', 'Vector')
    # the whole tower is one big volume: blend each billow's normal with the tower's ellipsoid normal (like the reference)
    rel = nb.vmath('SUBTRACT', P, nb.objattr('tc', 'Vector'))
    trad = nb.objattr('trad', 'Vector')
    tN = nb.vmath('NORMALIZE', nb.vmath('DIVIDE', rel, nb.vmath('MULTIPLY', trad, trad)))
    nn = nb.vmath('NORMALIZE', nb.vmath('ADD', nb.vmath('SCALE', N, scale=0.42), nb.vmath('SCALE', tN, scale=0.58)))
    n1 = nb.noise(nb.vmath('SCALE', P, scale=1.0), nb.objattr('nscale'), 3.0, 0.6, 0.0)
    n2 = nb.noise(nb.vmath('SCALE', P, scale=2.7), nb.objattr('nscale'), 2.0, 0.6, 0.0)
    band = nb.mul(nb.sub(nb.add(nb.mul(n1, 0.7), nb.mul(n2, 0.3)), 0.5), 0.3)
    Lraw = nb.add(nb.vmath('DOT_PRODUCT', nn, sunD0), band)
    tl = nb.smooth(Lraw, -0.06, 0.02)
    th = nb.smooth(Lraw, 0.42, 0.5)
    c = nb.mixc(nb.rgb(shadec), nb.rgb(mid), tl)
    c = nb.mixc(c, nb.rgb(lit), th)
    # flat bases sit in their own blue
    hz = nb.objattr('hbase'); z = nb.xyz(P)[2]
    bm = nb.mul(nb.smooth(z, nb.add(hz, nb.objattr('hband')), hz), nb.sub(1.0, th))
    c = nb.mixc(c, nb.rgb(base), nb.mul(bm, 0.55))
    sunD = nb.attr('sunD', 'Vector'); sunC = nb.attr('sunC')
    back = nb.smooth(nb.vmath('DOT_PRODUCT', nb.vmath('SCALE', I, scale=-1.0), sunD), 0.35, 0.95)
    facing = nb.sub(1.0, nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', tN, I)))
    c = nb.mixc(c, nb.cscale(sunC, 1.12), nb.mul(nb.smooth(facing, 0.72, 0.9), nb.mul(back, 0.85)))
    c = nb.mixc(c, nb.mixc(c, nb.rgb(mid), 0.45), nb.mul(back, nb.sub(1.0, th)))
    c = nb.cmul(c, nb.mixc((1, 1, 1, 1), sunC, 0.55))
    # storm tint (scene) and lightning flash: the storm's own clouds (prop stormy) always, every cloud once the deck is
    # overhead (skyDeck, see sky(): no white fair-weather towers under a storm sky)
    sto = nb.attr('cloudStorm', 'Fac')
    c = nb.mixc(c, nb.cmul(c, '#6f6fae'), nb.mul(sto, nb.mx(nb.objattr('stormy'), nb.attr('skyDeck', 'Fac'))))
    c = nb.mixc(c, nb.mixc(c, srgb('#eef2ff'), 0.7), nb.attr('flash', 'Fac'))
    return LK.finish(nb, c, ink=0.0, paint=1.0, hz=0.25)


def cumulus(name, center, width, height, puff=None, seed=1, mat=None, c=None, lean=0.0, flat_base=True, detail=1.0, stormy=0.0):
    """A cauliflower tower of displaced spheres (rows of billows, buds on the rims, a flat base). center = base centre (x, y, z)."""
    R = random.Random(seed); cx, cy, cz = center
    R0 = puff or max(width, height) * 0.16
    rows = max(1, round(height / (R0 * 0.9)))
    bm = bmesh.new(); puffs = []
    for k in range(rows + 1):
        f = k / rows if rows else 0
        z = cz + R0 * 0.55 + f * (height - R0 * 1.35)
        w = max(R0 * 0.6, width * (1 - 0.42 * f * f))
        n = max(1, round(w / (R0 * 1.12)))
        for i in range(n):
            u = 0 if n == 1 else i / (n - 1) - 0.5
            ang = R.uniform(0, math.tau)
            x = cx + lean * f * height + u * (w - R0) + R.uniform(-0.3, 0.3) * R0
            y = cy + R.uniform(-0.45, 0.45) * w * 0.5
            r = R0 * R.uniform(0.8, 1.15) * (1 - 0.2 * f)
            puffs.append((x, y, z + R.uniform(-0.3, 0.3) * R0, r))
    body = len(puffs)
    for i in range(int(body * 1.6 * detail)):
        x, y, z, r = puffs[i % body]
        if z < cz + height * 0.25 or R.random() < 0.35: continue
        a = R.uniform(0.25, math.pi - 0.25); b = R.uniform(0, math.tau)
        puffs.append((x + math.cos(a) * math.cos(b) * r * 0.85, y + math.cos(a) * math.sin(b) * r * 0.85, z + math.sin(a) * r * 0.8, r * R.uniform(0.32, 0.5)))
    for (x, y, z, r) in puffs:
        segs = 18 if r > R0 * 0.6 else 12
        m = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2 + 2, radius=r)
        for v in m['verts']:
            v.co.x += x; v.co.y += y; v.co.z += z
    if flat_base:
        for v in bm.verts:
            if v.co.z < cz: v.co.z = cz + (v.co.z - cz) * 0.08
    o = bm_obj(name, bm, mat, c, smooth=True)
    o['hbase'] = cz; o['hband'] = height * 0.18; o['nscale'] = 3.0 / max(R0, 1.0); o['stormy'] = stormy
    o['tc'] = (cx + lean * height * 0.5, cy, cz + height * 0.45); o['trad'] = (width * 0.55, width * 0.35, height * 0.55)
    md = o.modifiers.new('disp', 'DISPLACE'); tx = D.textures.new(name + '_tx', 'CLOUDS'); tx.noise_scale = R0 * 0.6; tx.noise_depth = 2
    md.texture = tx; md.strength = R0 * 0.22; md.mid_level = 0.5; md.texture_coords = 'GLOBAL'
    o.visible_shadow = False
    return o


def cloud_ring(sc, mat, c=None, dist=9500.0, seed=7310, n=18, storm_west=False):
    """Towering nyudo-gumo all round the horizon so every view of the sea has a castle in it."""
    R = random.Random(seed); out = []
    for i in range(n):
        az = i / n * 360 + R.uniform(-8, 8)
        d = dist * R.uniform(0.85, 1.25)
        a = math.radians(az); x = math.sin(a) * d; y = math.cos(a) * d
        w = R.uniform(2200, 4200); h = R.uniform(1500, 3400)
        o = cumulus('CLOUD_ring%02d' % i, (x, y, R.uniform(120, 300)), w, h, puff=min(w, h) * 0.13, seed=seed + i, mat=mat, c=c, lean=R.uniform(-0.06, 0.06))
        out.append(o)
    return out


# ---------------------------------------------------------------------------------------------------------------------------------- the sea
def sea_mat(name='M_sea'):
    """Shaded, not displaced (like the reference): five hard painted tones from long crest-shaped patches drifting downwind, cloud shadows,
    foam streaks along the wind, drawn whitecap dashes (white with a lavender under-shade) that bloom and fade, sun glints, a fresnel band
    of sky. The wind blows from the west: crests drift toward +X."""
    nb = NB(name)
    g = nb.geo(); P = g.outputs['Position']; I = g.outputs['Incoming']
    px, py, pz = nb.xyz(P)
    t = nb.attr('seaT', 'Fac')
    calm = nb.attr('seaCalm', 'Fac'); rough = nb.attr('seaRough', 'Fac')
    q = nb.vec(px, py, 0.0)
    WX, WY = 0.96, 0.28
    along = nb.add(nb.mul(px, WX), nb.mul(py, WY)); cross = nb.add(nb.mul(px, -WY), nb.mul(py, WX))
    dist = nb.vmath('LENGTH', nb.vmath('SUBTRACT', P, nb.attr('camP', 'Vector')))
    # domain warp so the crests wander
    wv = nb.vec(nb.noise(nb.vmath('SCALE', q, scale=0.0016), 1.0, 2.0, 0.5, 0.0), nb.noise(nb.vmath('ADD', nb.vmath('SCALE', q, scale=0.0016), (13, 7, 0)), 1.0, 2.0, 0.5, 0.0), 0.0)
    wx, wy, _ = nb.xyz(wv)
    al = nb.add(along, nb.mul(nb.sub(wx, 0.5), 260.0)); cr = nb.add(cross, nb.mul(nb.sub(wy, 0.5), 260.0))
    amp = nb.mul(nb.add(nb.mul(calm, -0.8), 1.0), nb.add(nb.mul(rough, 0.7), 1.0))

    def layer(lam_along, lam_cross, speed, seed, detail=3.0):
        v = nb.vec(nb.math('DIVIDE', nb.sub(al, nb.mul(t, speed)), lam_along), nb.math('DIVIDE', cr, lam_cross), seed)
        return nb.sub(nb.noise(v, 1.0, detail, 0.55, 0.0), 0.5)
    n1 = layer(140.0, 420.0, 7.0, 0.0)
    n2 = layer(42.0, 130.0, 4.5, 3.0)
    n3 = layer(13.0, 36.0, 2.6, 7.0, 2.0)
    big = nb.noise(nb.vmath('SCALE', q, scale=0.00042), 1.0, 3.0, 0.5, 0.0)
    near2 = nb.smooth(dist, 2200.0, 700.0); near3 = nb.smooth(dist, 600.0, 180.0)
    tone = nb.add(0.42, nb.mul(nb.sub(big, 0.5), 0.9))
    tone = nb.add(tone, nb.mul(n1, nb.mul(amp, 1.15)))
    tone = nb.add(tone, nb.mul(nb.mul(n2, near2), nb.mul(amp, 0.62)))
    tone = nb.add(tone, nb.mul(nb.mul(n3, near3), nb.mul(amp, 0.38)))
    deep = nb.attr('seaDeep'); shal = nb.attr('seaShallow')
    c0 = nb.mixc(deep, srgb('#061a6b'), 0.55); c1 = deep; c2 = nb.mixc(deep, shal, 0.42); c3 = nb.mixc(deep, shal, 0.82); c4 = nb.mixc(shal, srgb('#dbfffa'), 0.45)
    body = c0
    for edge, cc in ((0.24, c1), (0.45, c2), (0.63, c3), (0.82, c4)):
        body = nb.mixc(body, cc, nb.smooth(tone, edge - 0.01, edge + 0.01))
    farK = nb.smooth(dist, 3500.0, 11000.0)
    farBody = nb.mixc(deep, nb.mixc(deep, shal, 0.55), nb.math('MULTIPLY', nb.sub(big, 0.3), 2.2, clamp=True))
    body = nb.mixc(body, farBody, nb.mul(farK, 0.8))
    # hard cloud shadows drifting over the sea
    cs = nb.noise(nb.vmath('ADD', nb.vmath('SCALE', q, scale=0.00026), nb.vec(nb.mul(t, 0.0012), 4.0, 0.0)), 1.0, 3.0, 0.5, 0.0)
    csh = nb.mul(nb.smooth(cs, 0.545, 0.56), nb.sub(1.0, nb.mul(farK, 0.4)))
    body = nb.mixc(body, nb.cmul(body, srgb('#9eadeb')), nb.mul(csh, nb.attr('seaCloudSh', 'Fac')))
    # sky band by fresnel (view grazing)
    cosv = nb.math('ABSOLUTE', nb.xyz(I)[2])
    fres = nb.add(0.03, nb.mul(0.97, nb.math('POWER', nb.sub(1.0, cosv), 5.0)))
    body = nb.mixc(body, nb.attr('seaSky'), nb.math('MINIMUM', nb.mul(fres, 0.6), 0.55))
    # foam streaks combed along the wind
    sv1 = nb.vec(nb.math('DIVIDE', nb.sub(al, nb.mul(t, 3.0)), 260.0), nb.math('DIVIDE', cr, 14.0), 3.0)
    sv2 = nb.vec(nb.math('DIVIDE', nb.sub(al, nb.mul(t, 4.0)), 90.0), nb.math('DIVIDE', cr, 5.0), 9.0)
    st = nb.add(nb.mul(nb.noise(sv1, 1.0, 2.0, 0.5, 0.0), 0.65), nb.mul(nb.noise(sv2, 1.0, 2.0, 0.5, 0.0), 0.42))
    gust = nb.smooth(nb.noise(nb.vmath('SCALE', q, scale=0.0011), 1.0, 3.0, 0.5, 0.0), 0.45, 0.62)
    streak = nb.mul(nb.mul(nb.smooth(st, 0.69, 0.72), gust), nb.smooth(dist, 2600.0, 500.0))
    # a streak seen end-on from low over the water is no line any more but a pale veil running from the lens to the horizon
    # (s21, 06.11: the camera 10 m over the bay looking up the wind; camera rays found nothing but the sea there): the streaks
    # whose local course (an iso-line of the warped cross coordinate: the warp turns it up to ~30 deg off the wind) runs
    # within 9..28 deg of the view ray's course fade out, only where the view grazes the water (|I.z| < 0.3..0.5)
    hh = 4.0
    def _wy(dx, dy):
        return nb.noise(nb.vmath('ADD', nb.vmath('SCALE', nb.vmath('ADD', q, (dx, dy, 0.0)), scale=0.0016), (13, 7, 0)), 1.0, 2.0, 0.5, 0.0)
    gx = nb.add(-WY, nb.mul(nb.sub(_wy(hh, 0.0), wy), 260.0 / hh))
    gy = nb.add(WX, nb.mul(nb.sub(_wy(0.0, hh), wy), 260.0 / hh))
    ix, iy, _iz = nb.xyz(I)
    endon = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', nb.vmath('NORMALIZE', nb.vec(gy, nb.mul(gx, -1.0), 0.0)),
                                         nb.vmath('NORMALIZE', nb.vec(ix, iy, 0.0))))
    streak = nb.mul(streak, nb.sub(1.0, nb.mul(nb.smooth(endon, 0.883, 0.988), nb.smooth(cosv, 0.5, 0.3))))
    body = nb.mixc(body, nb.mixc(c3, (1, 1, 1, 1), 0.35), nb.mul(streak, nb.add(0.16, nb.mul(rough, 0.3))))
    # whitecaps: one dash per voronoi cell (stretched across the wind), per-cell random size/phase, bloom and fade
    caps = None; capsh = None
    for csz, seed, dens, l0, l1 in ((5.0, 4.0, 0.26, 0.0, 140.0), (16.0, 1.0, 0.30, 40.0, 650.0), (55.0, 2.0, 0.34, 220.0, 2600.0), (190.0, 3.0, 0.42, 900.0, 9000.0)):
        pv = nb.vec(nb.math('DIVIDE', nb.sub(al, nb.mul(t, csz * 0.08)), csz), nb.math('DIVIDE', cr, csz * 2.6), seed)
        vn = nb.N.new('ShaderNodeTexVoronoi'); vn.feature = 'F1'; vn.voronoi_dimensions = '3D'; vn.inputs['Scale'].default_value = 1.0; vn.inputs['Randomness'].default_value = 0.85
        nb.put(vn.inputs['Vector'], pv)
        off = nb.vmath('SUBTRACT', pv, vn.outputs['Position'])
        ox, oy, _ = nb.xyz(off)
        rc = nb.xyz(vn.outputs['Color'])
        on = nb.step(nb.sub(1.0, nb.mul(dens, nb.add(0.75, nb.mul(rough, 0.9)))), rc[0])
        age = nb.math('FRACT', nb.add(nb.math('DIVIDE', t, nb.add(2.4, nb.mul(rc[1], 3.0))), nb.mul(rc[2], 7.0)))
        grow = nb.mul(nb.smooth(age, 0.0, 0.2), nb.smooth(age, 1.0, 0.55))
        size = nb.mul(nb.add(0.55, nb.mul(rc[1], 0.6)), grow)
        bend = nb.add(ox, nb.mul(nb.mul(oy, oy), 1.6))
        e = nb.add(nb.math('POWER', nb.math('DIVIDE', bend, nb.mul(size, 0.075)), 2.0), nb.math('POWER', nb.math('DIVIDE', oy, nb.mul(size, 0.36)), 2.0))
        nz = nb.noise(nb.vmath('SCALE', pv, scale=11.0), 1.0, 2.0, 0.6, 0.0)
        lod = nb.mul(nb.smooth(dist, l0 * 0.5, l0) if l0 > 0 else 1.0, nb.smooth(dist, l1, l1 * 0.55))
        m = nb.mul(nb.mul(nb.step(e, nb.sub(1.15, nb.mul(nz, 0.5))), on), lod)
        msh = nb.mul(nb.mul(nb.step(e, nb.sub(2.6, nb.mul(nz, 0.8))), on), lod)
        caps = m if caps is None else nb.mx(caps, m)
        capsh = msh if capsh is None else nb.mx(capsh, msh)
    k_ = nb.add(nb.mul(calm, -0.8), 1.0)
    caps = nb.mul(caps, k_); capsh = nb.mul(capsh, k_)
    sunD = nb.attr('sunD', 'Vector'); sunC = nb.attr('sunC')
    gc = nb.voronoi(nb.vmath('SCALE', q, scale=0.35), 1.0, 'F1', out='Position', w=nb.math('FLOOR', nb.mul(t, 8.0)))
    tilt = nb.vmath('SCALE', nb.vmath('SUBTRACT', nb.vec(nb.noise(gc, 30.0, 0.0), nb.noise(nb.vmath('ADD', gc, (3, 3, 3)), 30.0, 0.0), 0.5), (0.5, 0.5, 0.5)), scale=0.6)
    nf = nb.vmath('NORMALIZE', nb.vmath('ADD', (0, 0, 1.0), tilt))
    R_ = nb.vmath('REFLECT', nb.vmath('SCALE', I, scale=-1.0), nf)
    gl = nb.smooth(nb.vmath('DOT_PRODUCT', R_, sunD), 0.993, 0.998)
    gd = nb.voronoi(nb.vmath('SCALE', q, scale=0.35), 1.0, 'F1', w=nb.math('FLOOR', nb.mul(t, 8.0)))
    glint = nb.mul(gl, nb.smooth(gd, 0.16, 0.08))
    col = nb.mixc(body, nb.cmul(body, srgb('#b9c3ff')), nb.mul(capsh, 0.55))
    col = nb.mixc(col, nb.mixc(srgb('#ffffff'), nb.attr('seaFoamT'), 0.2), caps)
    col = nb.mixc(col, nb.cscale(sunC, 2.0), nb.mul(glint, nb.attr('seaGlint', 'Fac')))
    col = nb.mixc(col, nb.mixc(col, srgb('#e6ecff'), 0.55), nb.attr('flash', 'Fac'))
    m = LK.finish(nb, col, ink=0.0, paint=0.0, glow=nb.mul(glint, 0.6))
    return m


def sea(sc, size=60000.0, c=None, z=0.0):
    sc['seaT'] = 0.0; sc['seaCalm'] = 0.0; sc['seaRough'] = 0.0; sc['seaCloudSh'] = 0.55; sc['seaGlint'] = 1.0
    for k, v in (('seaDeep', '#1238b8'), ('seaShallow', '#1fc0d8'), ('seaSky', '#7fb0f5'), ('seaFoamT', '#cfe8ff')): sc[k] = srgb(v)[:3]
    sc['camP'] = (0.0, 0.0, 0.0)
    m = sea_mat()
    o = mesh_obj('SEA', [(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)], [(0, 1, 2, 3)], m, c)
    o.visible_shadow = False
    return o


# ---------------------------------------------------------------------------------------------------------------------------------- render
AOVS = ('oid', 'mid', 'ink', 'paint', 'glow', 'hz')


def render_setup(sc, samples=16, res=100, fps=24):
    r = sc.render; r.engine = 'BLENDER_EEVEE'; r.resolution_x = 1920; r.resolution_y = 1080; r.resolution_percentage = res; r.fps = fps
    e = sc.eevee
    for k, v in (('taa_render_samples', samples), ('use_raytracing', False), ('use_shadows', True), ('shadow_ray_count', 1), ('shadow_step_count', 6),
                 ('use_fast_gi', False), ('use_volumetric_shadows', False), ('volumetric_tile_size', '8'), ('volumetric_samples', 48), ('volumetric_end', 3000.0)):
        try: setattr(e, k, v)
        except Exception as ex: print('skip', k, ex)
    try: e.shadow_resolution_scale = 1.0
    except Exception: pass
    try: e.shadow_pool_size = '1024'          # kelp, crowds of houses: the default pool overflows
    except Exception as ex: print('skip shadow_pool_size', ex)
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0.0; sc.view_settings.gamma = 1.0
    r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '16'; r.image_settings.color_mode = 'RGB'; r.film_transparent = False
    r.use_motion_blur = False
    wd = D.worlds.new('W'); sc.world = wd; wd.use_nodes = True
    bg = wd.node_tree.nodes.get('Background')
    if bg: bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0
    vl = sc.view_layers[0]; vl.use_pass_z = True; vl.use_pass_normal = True
    for nm in AOVS:
        if nm not in vl.aovs: av = vl.aovs.add(); av.name = nm; av.type = 'VALUE'
    return vl


def compositor(sc, outdir, prefix='', kuwa=9.0, far0=700.0, far1=2600.0):
    """Color = mix(image, anisotropic Kuwahara(image), paint mask); the data passes go to three RGBA16 PNGs per frame:
       A = (log depth, oid, mid, 1)   B = (normal*0.5+0.5, 1)   G = (glow, hz, ink, 1).
       Alpha is always 1: the PNG writer un-premultiplies RGB by alpha, so no data may live in alpha."""
    vl = sc.view_layers[0]; pct = sc.render.resolution_percentage / 100.0
    ng = D.node_groups.new('anchor_comp', 'CompositorNodeTree'); sc.compositing_node_group = ng
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    N = ng.nodes; L = ng.links
    rl = N.new('CompositorNodeRLayers'); rl.scene = sc; rl.layer = vl.name
    def m(op, a, b=None, clamp=False):
        n = N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        (L.new(a, n.inputs[0]) if not isinstance(a, (int, float)) else setattr(n.inputs[0], 'default_value', a))
        if b is not None: (L.new(b, n.inputs[1]) if not isinstance(b, (int, float)) else setattr(n.inputs[1], 'default_value', b))
        return n.outputs[0]
    depth = rl.outputs['Depth']
    far = N.new('ShaderNodeMapRange'); far.inputs['From Min'].default_value = far0; far.inputs['From Max'].default_value = far1; far.clamp = True; L.new(depth, far.inputs['Value'])
    pm = m('MAXIMUM', rl.outputs['paint'], far.outputs['Result'])
    kw = N.new('CompositorNodeKuwahara'); kw.inputs['Type'].default_value = 'Anisotropic'
    for k_, v_ in (('Size', kuwa * pct), ('Uniformity', 4), ('Sharpness', 0.5), ('Eccentricity', 1.0)):
        try: kw.inputs[k_].default_value = v_
        except Exception as ex: print('kuwa', k_, ex)
    L.new(rl.outputs['Image'], kw.inputs['Image'])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'
    def sk(n, ident, out=False):
        for x in (n.outputs if out else n.inputs):
            if x.identifier == ident: return x
    L.new(pm, sk(mx, 'Factor_Float')); L.new(rl.outputs['Image'], sk(mx, 'A_Color')); L.new(kw.outputs[0], sk(mx, 'B_Color'))
    go = N.new('NodeGroupOutput'); L.new(sk(mx, 'Result_Color', True), go.inputs[0])
    # data
    ld = m('DIVIDE', m('LOGARITHM', m('ADD', depth, 1.0), 2.718281828), math.log(20001.0), clamp=True)
    def comb(r_, g_, b_, a_):
        n = None
        for t in ('CompositorNodeCombineColor', 'ShaderNodeCombineColor'):
            try: n = N.new(t); break
            except Exception: pass
        try: n.mode = 'RGB'
        except Exception: pass
        ins = [x for x in n.inputs if x.enabled]
        for sock, v in zip(ins, (r_, g_, b_, a_)):
            if v is None: continue
            if isinstance(v, (int, float)): sock.default_value = v
            else: L.new(v, sock)
        return n.outputs[0]
    A = comb(ld, rl.outputs['oid'], rl.outputs['mid'], 1.0)
    nrm = rl.outputs['Normal']
    sep = None
    for t in ('CompositorNodeSeparateColor', 'ShaderNodeSeparateColor'):
        try: sep = N.new(t); break
        except Exception: pass
    try: sep.mode = 'RGB'
    except Exception: pass
    L.new(nrm, sep.inputs[0])
    so = [x for x in sep.outputs if x.enabled]
    Bc = comb(m('ADD', m('MULTIPLY', so[0], 0.5), 0.5), m('ADD', m('MULTIPLY', so[1], 0.5), 0.5), m('ADD', m('MULTIPLY', so[2], 0.5), 0.5), 1.0)
    fo = N.new('CompositorNodeOutputFile'); fo.directory = outdir + os.sep; fo.file_name = prefix
    fo.format.media_type = 'IMAGE'; fo.format.file_format = 'PNG'; fo.format.color_mode = 'RGBA'; fo.format.color_depth = '16'
    for nm in ('A', 'B', 'G'): fo.file_output_items.new('RGBA', nm)
    L.new(A, fo.inputs['A']); L.new(Bc, fo.inputs['B'])
    Gc = comb(rl.outputs['glow'], rl.outputs['hz'], rl.outputs['ink'], 1.0); L.new(Gc, fo.inputs['G'])
    sc.render.use_compositing = True
    return fo


def camera(name='CAM', lens=35.0, c=None, clip=(0.5, 60000.0)):
    cd = D.cameras.new(name); cd.lens = lens; cd.sensor_width = 36.0; cd.sensor_fit = 'HORIZONTAL'; cd.clip_start, cd.clip_end = clip
    o = D.objects.new(name, cd); link(o, c); bpy.context.scene.camera = o
    return o


def look_at(cam, pos, tgt, roll=0.0):
    cam.location = pos
    d = Vector(tgt) - Vector(pos)
    q = d.to_track_quat('-Z', 'Y')
    if roll: q = q @ Euler((0, 0, math.radians(roll))).to_quaternion()
    cam.rotation_mode = 'QUATERNION'; cam.rotation_quaternion = q


def gpu_lock(tag='anchor'):
    """Serialise our own GPU renders (departments + lead) with an atomic mkdir lock."""
    lk = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', '.gpu_lock')
    t0 = time.time()
    while True:
        try: os.mkdir(lk); open(os.path.join(lk, 'who'), 'w').write('%s %d' % (tag, os.getpid())); return lk
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lk) > 900: os.rmdir(lk) if not os.listdir(lk) else [os.remove(os.path.join(lk, f)) for f in os.listdir(lk)]
            except Exception: pass
            time.sleep(1.0)
            if time.time() - t0 > 3600: return None


def gpu_unlock(lk):
    if not lk: return
    try:
        for f in os.listdir(lk): os.remove(os.path.join(lk, f))
        os.rmdir(lk)
    except Exception: pass
