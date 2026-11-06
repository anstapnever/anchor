# PORT department (ANCHOR): quay, DRY DOCK 3, ship-to-shore cranes, container terminal, warehouses, silos, hillside town and hills,
# fishing boats + pier, west breakwater with tetrapods and the LIGHTHOUSE (round stone bastion + red/white tower), east breakwater.
#   P = build(parent_collection, **opts) -> dict        (see build() docstring for the API)
#   cut_sea(sea_obj)            the shared sea quad would flood the dry dock: this re-meshes it as a frame with the basin cut out
#   set_crack(P, v, frame=None) / set_beam(P, v, frame=None)    lighthouse props (keyed when frame is given)
#   qa(P)                       QA.overlaps groups (tetrapods, containers, props) -> dict of results
import bpy, bmesh, math, random, os, sys, time, subprocess, json, zlib
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
for _p in (os.path.join(ROOT, 'kit'), HERE):
    if _p not in sys.path: sys.path.insert(0, _p)
import look as LK, env as EV
D = bpy.data
TEX = os.path.join(ROOT, 'tex')
PYEXE = os.environ.get('ANCHOR_PY', 'python')   # Python 3.13 with numpy + opencv, outside Blender

# ------------------------------------------------------------------------------------------------------------------------------ layout
QY, QZ = 400.0, 4.0                                   # quay line (y) and quay top (z)
DX0, DX1, DY0, DY1, DZ = -510.0, -410.0, 400.0, 600.0, -14.0   # DRY DOCK 3 basin (top opening) and floor
CRANE_X = (-370.0, -290.0, -210.0, -130.0)            # STS cranes A..D (x of the crane centre line)
RAIL_W, RAIL_L = 404.0, 434.0                         # waterside / landside crane rails (y)
BW_X, BW_Y0, BW_Y1, BW_Z, BW_W = -700.0, 400.0, -150.0, 5.0, 24.0   # west breakwater: axis x, root y, tip y, cap top, cap width
LH_C = (-700.0, -168.0)                               # lighthouse centre
LH_R, LH_TOPZ = 15.0, 27.0                            # stone drum (bastion) radius and top: clean wall r <= 15.3 from z 5 to 27
HEAD_R = 45.0                                         # breakwater round head: flat cap disc radius around the lighthouse (clear ring r 15.5..45)
TW_Z0, TW_H, TW_R0, TW_R1 = 27.0, 32.0, 5.0, 3.5      # tower foot z (pivot), height, foot radius, top radius
CRACK_Z0, CRACK_H = 5.0, 66.0                         # crack map spans tower-space z 5..71
SIGN_ROWS = ['DRY DOCK 3', '3', 'A', 'B', 'C', 'D', 'HIGH HARBOR', 'FISH MARKET', 'HARBOR AUTHORITY', 'ICE PLANT',
             'W-1', 'W-2', 'W-3', 'W-4', 'GRAIN', 'DANGER']
BRANDS = ['TRITON', 'HIGH HARBOR', 'KAIRO', 'NAVIS', 'OCEANA', 'MERIDIAN', 'GULL LINE', 'HHL']
BOATS = ['HH-07  ALBA', 'HH-12  MARISOL', 'HH-21  STELLA', 'HH-03  PERLA', 'HH-15  NINA', 'HH-09  AURORA', 'HH-30  GAVIOTA', 'HH-18  LUNA']

# ------------------------------------------------------------------------------------------------------------------------------ textures (PIL, run outside Blender)
_TEXGEN = r'''
import sys, os, math, random, json
from PIL import Image, ImageDraw, ImageFont
out = sys.argv[1]; cfg = json.loads(sys.argv[2])
F = r'C:\Windows\Fonts'
def font(n, s): return ImageFont.truetype(os.path.join(F, n), s)
def atlas(path, rows, W, RH, fname, fsize):
    im = Image.new('L', (W, RH * len(rows)), 0); d = ImageDraw.Draw(im)
    for i, t in enumerate(rows):
        f = font(fname, fsize); bb = d.textbbox((0, 0), t, font=f); w = bb[2] - bb[0]; h = bb[3] - bb[1]
        s = min(1.0, (W * 0.94) / max(w, 1), (RH * 0.84) / max(h, 1))
        if s < 1.0:
            f = font(fname, max(8, int(fsize * s))); bb = d.textbbox((0, 0), t, font=f); w = bb[2] - bb[0]; h = bb[3] - bb[1]
        d.text(((W - w) / 2 - bb[0], i * RH + (RH - h) / 2 - bb[1]), t, fill=255, font=f)
    im.save(path)
atlas(os.path.join(out, 'port_signs.png'), cfg['signs'], 2048, 128, 'arialbd.ttf', 112)
atlas(os.path.join(out, 'port_brands.png'), cfg['brands'], 1024, 128, 'impact.ttf', 112)
atlas(os.path.join(out, 'port_boats.png'), cfg['boats'], 1024, 128, 'arialbd.ttf', 96)
# crack map around the lighthouse (u = angle, v = height 5..52 m): value = 1 - birth time, so a threshold grows the cracks
W, H = 1024, 2048; R = random.Random(11); segs = []
def walk(u, v, t, n, dv, wd, depth):
    for k in range(n):
        u2 = u + R.gauss(0, 0.0035); v2 = v + dv * R.uniform(0.4, 1.3); t2 = t + R.uniform(0.003, 0.009)
        segs.append((t2, u, v, u2, v2, wd)); u, v, t = u2, v2, t2
        if v < 0.0 or v > 1.0: return
        if depth < 3 and R.random() < 0.06: walk(u, v, t, int(n * 0.45), dv * R.choice((1, -1, 0.5)), max(1, wd - 1), depth + 1)
        if R.random() < 0.05: dv = -dv * 0.3 + R.gauss(0, 0.004)
for vj, ns in zip(cfg['joints'], cfg['jn']):
    for i in range(ns):
        u0 = (i + R.uniform(0.1, 0.9)) / ns; t0 = R.uniform(0.0, 0.3)
        for sgn in (1, -1): walk(u0, vj + R.uniform(-0.01, 0.01), t0, R.randint(30, 75), sgn * 0.0045, 3, 0)
segs.sort(key=lambda s: -s[0])
im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
for t, u, v, u2, v2, wd in segs:
    val = max(1, int(255 * (1.0 - min(t, 0.99))))
    for off in (-1, 0, 1):
        d.line([((u + off) * W, (1 - v) * H), ((u2 + off) * W, (1 - v2) * H)], fill=val, width=max(1, wd - 1))
im.save(os.path.join(out, 'port_crack.png'))
print('textures ok')
'''


def textures(force=False):
    os.makedirs(TEX, exist_ok=True)
    need = ['port_signs.png', 'port_brands.png', 'port_boats.png', 'port_crack.png']
    stamp = os.path.join(TEX, 'port_tex.json')
    cfg = dict(signs=SIGN_ROWS, brands=BRANDS, boats=BOATS, joints=[(TW_Z0 - CRACK_Z0) / CRACK_H, (TW_Z0 + TW_H * 0.5 - CRACK_Z0) / CRACK_H,
                                                                     (19.5 - CRACK_Z0) / CRACK_H], jn=[9, 7, 5])
    ok = all(os.path.exists(os.path.join(TEX, n)) for n in need)
    try: ok = ok and json.load(open(stamp)) == cfg
    except Exception: ok = False
    if ok and not force: return
    r = subprocess.run([PYEXE, '-c', _TEXGEN, TEX, json.dumps(cfg)], capture_output=True, text=True)
    print('PORT textures:', r.stdout.strip(), r.stderr.strip()[-400:])
    json.dump(cfg, open(stamp, 'w'))


def tex(name): return os.path.join(TEX, name)


# ------------------------------------------------------------------------------------------------------------------------------ geometry
MAT = {}                                              # key -> material (filled by materials())


class Geo:
    """Polygon soup with a material key per face (and a smooth flag) -> one mesh. Fast: plain lists, one from_pydata."""
    def __init__(s): s.V = []; s.F = []; s.M = []; s.S = []

    def add(s, verts, faces, mat, smooth=False):
        o = len(s.V); s.V.extend(tuple(v) for v in verts)
        for f in faces: s.F.append(tuple(i + o for i in f)); s.M.append(mat); s.S.append(smooth)
        return o

    def box(s, c, d, mat, R=None):
        hx, hy, hz = d[0] * 0.5, d[1] * 0.5, d[2] * 0.5
        P = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
        if R is not None: P = [tuple(R @ Vector(p)) for p in P]
        return s.add([(c[0] + p[0], c[1] + p[1], c[2] + p[2]) for p in P],
                     [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], mat)

    def blh(s, lo, hi, mat):
        return s.box(((lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5, (lo[2] + hi[2]) * 0.5), (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]), mat)

    def beam(s, p0, p1, w, h, mat, up=(0, 0, 1)):
        """Box from p0 to p1, cross-section w (side) x h (along 'up')."""
        p0 = Vector(p0); p1 = Vector(p1); ax = p1 - p0; L = ax.length
        if L < 1e-6: return
        X = ax / L; U = Vector(up)
        if abs(X.dot(U)) > 0.98: U = Vector((1, 0, 0)) if abs(X.x) < 0.9 else Vector((0, 1, 0))
        Y = U.cross(X).normalized(); Z = X.cross(Y)
        R = Matrix((X, Y, Z)).transposed()
        return s.box(tuple((p0 + p1) * 0.5), (L, w, h), mat, R)

    def cyl(s, p0, p1, r0, r1=None, n=12, mat=None, caps=(True, True), smooth=True, a0=0.0):
        r1 = r0 if r1 is None else r1; p0 = Vector(p0); p1 = Vector(p1); ax = p1 - p0; L = ax.length
        Z = ax / L; X = Vector((1, 0, 0)) if abs(Z.x) < 0.9 else Vector((0, 1, 0)); Y = Z.cross(X).normalized(); X = Y.cross(Z)
        ring = [(math.cos(a0 + i * math.tau / n), math.sin(a0 + i * math.tau / n)) for i in range(n)]
        V = [tuple(p0 + (X * c + Y * q) * r0) for c, q in ring] + [tuple(p1 + (X * c + Y * q) * r1) for c, q in ring]
        s.add(V, [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)], mat, smooth)
        if caps[0]: s.add(V[:n], [tuple(range(n - 1, -1, -1))], mat)
        if caps[1]: s.add(V[n:], [tuple(range(n))], mat)

    def tube(s, pts, r, n=8, mat=None, caps=True):
        for a, b in zip(pts, pts[1:]): s.cyl(a, b, r, n=n, mat=mat, caps=(caps, caps))

    def sphere(s, c, r, mat, nu=10, nv=6, sz=1.0, smooth=True):
        V = [(c[0], c[1], c[2] - r * sz)]
        for j in range(1, nv):
            t = math.pi * j / nv - math.pi / 2
            for i in range(nu):
                a = math.tau * i / nu; V.append((c[0] + r * math.cos(t) * math.cos(a), c[1] + r * math.cos(t) * math.sin(a), c[2] + r * sz * math.sin(t)))
        V.append((c[0], c[1], c[2] + r * sz)); top = len(V) - 1; F = []
        for i in range(nu): F.append((0, 1 + (i + 1) % nu, 1 + i))
        for j in range(nv - 2):
            for i in range(nu):
                a = 1 + j * nu + i; b = 1 + j * nu + (i + 1) % nu; F.append((a, b, b + nu, a + nu))
        for i in range(nu): F.append((1 + (nv - 2) * nu + i, 1 + (nv - 2) * nu + (i + 1) % nu, top))
        s.add(V, F, mat, smooth)

    def prism(s, pts, z0, z1, mat, cap=True):
        """Vertical extrusion of a simple polygon (counter-clockwise, xy) between z0 and z1."""
        n = len(pts); V = [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
        F = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        if cap: F += [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        s.add(V, F, mat)

    def extrude(s, prof, p0, p1, mat, up=(0, 0, 1)):
        """Extrude a 2D profile [(u, v)...] (u side, v up, counter-clockwise) from p0 to p1."""
        p0 = Vector(p0); p1 = Vector(p1); X = (p1 - p0).normalized(); U = Vector(up)
        Y = U.cross(X).normalized(); Z = X.cross(Y); n = len(prof)
        V = [tuple(p0 + Y * u + Z * v) for u, v in prof] + [tuple(p1 + Y * u + Z * v) for u, v in prof]
        F = [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)] + [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
        s.add(V, F, mat)

    def mesh(s, name, recalc=False):
        keys = []
        for k in s.M:
            if k not in keys: keys.append(k)
        km = {k: i for i, k in enumerate(keys)}
        me = D.meshes.new(name); me.from_pydata(s.V, [], s.F)
        me.polygons.foreach_set('material_index', [km[k] for k in s.M])
        me.polygons.foreach_set('use_smooth', s.S)
        for k in keys: me.materials.append(MAT[k])
        if recalc:
            bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
        me.update(); return me

    def tris(s): return sum(len(f) - 2 for f in s.F)


def bevel_mesh(me, width=0.08, angle=30.0, segs=1):
    """Bake a bevel into a shared mesh (linked duplicates then render without per-object modifiers)."""
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    ed = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(angle)]
    if ed: bmesh.ops.bevel(bm, geom=ed, offset=width, segments=segs, affect='EDGES', clamp_overlap=True, profile=0.5)
    bm.to_mesh(me); bm.free(); me.update(); return me


def obj(name, data, coll, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, bevel=0.0, bangle=30.0, props=None):
    o = D.objects.new(name, data); coll.objects.link(o)
    if parent is not None: o.parent = parent
    o.location = loc; o.rotation_euler = rot
    if bevel and data is not None:
        b = o.modifiers.new('bev', 'BEVEL'); b.width = bevel; b.segments = 1; b.limit_method = 'ANGLE'; b.angle_limit = math.radians(bangle)
    for k, v in (props or {}).items(): o[k] = v
    return o


def gobj(name, g, coll, bevel=0.0, loc=(0, 0, 0), parent=None, props=None, bangle=30.0):
    return obj(name, g.mesh(name), coll, loc=loc, parent=parent, bevel=bevel, props=props, bangle=bangle)


def empty(name, coll, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, size=2.0):
    o = obj(name, None, coll, loc, rot, parent); o.empty_display_size = size; o.empty_display_type = 'PLAIN_AXES'; return o


def ntris(objs):
    dg = bpy.context.evaluated_depsgraph_get(); n = 0
    for o in objs:
        if o.type != 'MESH': continue
        ev = o.evaluated_get(dg); me = ev.to_mesh(); me.calc_loop_triangles(); n += len(me.loop_triangles); ev.to_mesh_clear()
    return n




# ------------------------------------------------------------------------------------------------------------------------------ shader helpers
def _O(nb): return nb.tc().outputs['Object']
def _W(nb): return nb.geo().outputs['Position']
def _ON(nb): return nb.tc().outputs['Normal']                      # object-space normal
def inr(nb, v, a, b): return nb.mul(nb.math('GREATER_THAN', v, a), nb.math('LESS_THAN', v, b))
def rect(nb, u, v, u0, u1, v0, v1): return nb.mul(inr(nb, u, u0, u1), inr(nb, v, v0, v1))
def lines(nb, v, period, width, off=0.0):
    """1 on thin lines (width in metres) every `period`."""
    f = nb.math('FRACT', nb.math('DIVIDE', nb.add(v, off) if off else v, period))
    return nb.math('LESS_THAN', nb.mn(f, nb.sub(1.0, f)), width / period * 0.5)
def per(nb, v, period): return nb.math('FRACT', nb.math('DIVIDE', v, period))
def hashv(nb, v, w=0.0): return nb.noise(nb.vmath('ADD', nb.vmath('SCALE', v, scale=0.7311), (w, w * 1.7, w * 0.3)), 37.0, 0.0, 0.5, 0.0)
def orand(nb): return nb.new('ShaderNodeObjectInfo').outputs['Random']
def ocol(nb, name): return nb.attr(name, 'Color', 'OBJECT')
def text(nb, img, row, nrows, u, v, u0, u1, v0, v1, ra=16.0, crop=None):
    """Text row `row` of an atlas (rows of aspect ra = width/height, text centred) inside the rect u0..u1 x v0..v1 of the (u, v)
    surface coordinates. Only the central part of the row that keeps the glyphs' aspect is mapped (crop = rect aspect / ra)."""
    lu = nb.math('DIVIDE', nb.sub(u, u0), u1 - u0); lv = nb.math('DIVIDE', nb.sub(v, v0), v1 - v0)
    if crop is None: crop = min(1.0, ((u1 - u0) / (v1 - v0)) / ra)
    tu = nb.add(0.5, nb.mul(nb.sub(lu, 0.5), crop))
    av = nb.math('DIVIDE', nb.add(nb.sub(nrows - 1.0, row), lv), float(nrows))
    t = nb.image(img, nb.vec(tu, av, 0.0), extension='CLIP')
    return nb.mul(nb.bw(t), rect(nb, u, v, u0, u1, v0, v1))
def facing(nb, axis, th=0.6): return nb.math('GREATER_THAN', nb.vmath('DOT_PRODUCT', _ON(nb), axis), th)
def puddles(nb, col, P, amt=1.0, scale=0.045, th=0.66, sky='#a9c6f2'):
    n = nb.noise(nb.vmath('SCALE', P, scale=scale), 1.0, 3.0, 0.6, 0.2)
    m = nb.mul(nb.smooth(n, th, th + 0.012), amt)
    rimm = nb.mul(nb.sub(nb.smooth(n, th - 0.03, th - 0.02), nb.smooth(n, th, th + 0.012)), amt)
    col = nb.mixc(col, nb.cmul(col, '#8f8aa6'), nb.mul(rimm, 0.6))
    refl = nb.mixc(nb.cmul(col, '#7d86b8'), nb.rgb(sky), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.6), 1.0, 1.0), 0.45, 0.6))
    return nb.mixc(col, refl, m)


# ------------------------------------------------------------------------------------------------------------------------------ colour functions: ground
def c_quaywall(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    u = nb.add(x, y)
    col = nb.rgb('#cdc4b2')
    blk = nb.vec(nb.math('FLOOR', nb.math('DIVIDE', u, 6.0)), nb.math('FLOOR', nb.math('DIVIDE', z, 2.0)), 0.0)
    col = nb.hsv(col, 0.5, 1.0, nb.remap(hashv(nb, blk), 0.25, 0.75, 0.9, 1.06))
    j = nb.mx(lines(nb, u, 6.0, 0.12), lines(nb, z, 2.0, 0.1))
    col = nb.mixc(col, nb.cmul(col, '#8e88a3'), nb.mul(j, 0.75))
    st = nb.mul(nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (0.9, 0.9, 0.06)), 1.0, 3.0, 0.6), 0.55, 0.6), nb.smooth(z, 4.0, 1.0))
    return nb.mixc(col, nb.cmul(col, '#a9a2c2'), nb.mul(st, 0.6))


def c_cope(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    col = nb.rgb('#e4ddcc')
    col = nb.mixc(col, nb.rgb('#f2b705'), nb.mul(nb.math('GREATER_THAN', z, 4.05), nb.math('LESS_THAN', per(nb, nb.add(x, y), 3.0), 0.5)))
    return nb.mixc(col, nb.cmul(col, '#8e88a3'), lines(nb, nb.add(x, y), 12.0, 0.1))


def c_apron(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    cell = nb.vec(nb.math('FLOOR', nb.math('DIVIDE', x, 7.5)), nb.math('FLOOR', nb.math('DIVIDE', y, 7.5)), 0.0)
    col = nb.hsv(nb.rgb('#cbc4b5'), 0.5, 1.0, nb.remap(hashv(nb, cell, 3.0), 0.25, 0.75, 0.9, 1.05))
    yard = nb.mul(inr(nb, x, -404.0, -14.0), inr(nb, y, 444.0, 646.0))
    asph = nb.hsv(nb.rgb('#a4a0a6'), 0.5, 1.0, nb.remap(hashv(nb, cell, 9.0), 0.25, 0.75, 0.94, 1.04))
    col = nb.mixc(col, asph, yard)
    jl = nb.mx(lines(nb, x, 7.5, 0.1), lines(nb, y, 7.5, 0.1))
    col = nb.mixc(col, nb.cmul(col, '#8a85a0'), nb.mul(jl, nb.sub(0.55, nb.mul(yard, 0.45))))
    sl = nb.mx(lines(nb, nb.sub(y, 450.0), 4.3, 0.16), lines(nb, nb.sub(x, -400.0), 12.8, 0.16))
    col = nb.mixc(col, nb.rgb('#eeeae0'), nb.mul(sl, nb.mul(yard, 0.85)))
    lane = nb.mul(nb.mx(lines(nb, nb.sub(x, -400.0), 116.0, 0.3, 2.0), lines(nb, nb.sub(y, 450.0), 38.0, 0.3, 1.0)), yard)
    col = nb.mixc(col, nb.rgb('#f2b705'), lane)
    col = nb.mixc(col, nb.rgb('#f2b705'), inr(nb, y, 401.6, 402.1))
    tl = None
    for ly in (410.0, 417.0, 424.0, 431.0):
        m = inr(nb, y, ly - 0.1, ly + 0.1); tl = m if tl is None else nb.mx(tl, m)
    tl = nb.mul(nb.mul(tl, nb.math('LESS_THAN', per(nb, x, 8.0), 0.55)), inr(nb, x, -400.0, 40.0))
    col = nb.mixc(col, nb.rgb('#f4f1e8'), tl)
    for ry in (RAIL_W, RAIL_L):
        col = nb.mixc(col, nb.cmul(col, '#9d98ae'), nb.mul(inr(nb, y, ry - 0.6, ry + 0.6), inr(nb, x, -400.0, 40.0)))
    bal = inr(nb, y, 649.0, 655.0)
    sleep = nb.mul(inr(nb, y, 650.2, 653.8), nb.math('LESS_THAN', per(nb, x, 0.7), 0.32))
    col = nb.mixc(col, nb.mixc(nb.rgb('#a39a8c'), nb.rgb('#8a8174'), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=3.0), 1.0, 1.0), 0.4, 0.6)), bal)
    col = nb.mixc(col, nb.rgb('#6e5a4c'), sleep)
    road = inr(nb, y, 656.0, 668.0)
    col = nb.mixc(col, nb.hsv(nb.rgb('#8f8c96'), 0.5, 1.0, nb.remap(hashv(nb, cell, 5.0), 0.3, 0.7, 0.95, 1.04)), road)
    col = nb.mixc(col, nb.rgb('#f1ede2'), nb.mul(inr(nb, y, 661.85, 662.15), nb.math('LESS_THAN', per(nb, x, 9.0), 0.45)))
    col = nb.mixc(col, nb.rgb('#f1ede2'), nb.mx(inr(nb, y, 656.4, 656.6), inr(nb, y, 667.4, 667.6)))
    oil = nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.11), 1.0, 3.0, 0.6, 0.4), 0.64, 0.66), 0.45)
    col = nb.mixc(col, nb.cmul(col, '#7c7896'), oil)
    tyre = nb.mul(nb.mul(nb.mx(lines(nb, y, 2.2, 0.25), lines(nb, y, 3.1, 0.2)), nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (0.02, 0.4, 1.0)), 1.0, 2.0), 0.55, 0.6)), 0.3)
    col = nb.mixc(col, nb.cmul(col, '#8e8aa6'), tyre)
    return puddles(nb, col, P, 1.0, 0.035, 0.68)


def c_dockwall(nb):
    """Granite ashlar courses (dry dock walls and altars)."""
    P = _W(nb); x, y, z = nb.xyz(P)
    u = nb.add(x, y)
    row = nb.math('FLOOR', nb.math('DIVIDE', z, 1.1))
    uo = nb.add(u, nb.mul(nb.math('FRACT', nb.mul(row, 0.5)), 2.4))
    blk = nb.vec(nb.math('FLOOR', nb.math('DIVIDE', uo, 2.4)), row, 0.0)
    h = hashv(nb, blk, 1.0)
    col = nb.mixc(nb.rgb('#cfc3ad'), nb.rgb('#b9b3a6'), nb.smooth(h, 0.45, 0.55))
    col = nb.hsv(col, 0.5, 1.0, nb.remap(h, 0.2, 0.8, 0.9, 1.07))
    j = nb.mx(lines(nb, uo, 2.4, 0.09), lines(nb, z, 1.1, 0.08))
    col = nb.mixc(col, nb.cmul(col, '#8c86a0'), nb.mul(j, 0.85))
    col = nb.mixc(col, nb.cmul(col, '#a7b49a'), nb.mul(nb.smooth(z, -9.0, -12.5), 0.7))
    rs = nb.mul(nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (0.7, 0.7, 0.05)), 1.0, 3.0, 0.6), 0.6, 0.63), 0.55)
    col = nb.mixc(col, nb.mixc(col, nb.rgb('#9a4f2a'), 0.5), rs)
    sg = tex('port_signs.png')
    t3 = nb.mx(nb.mul(text(nb, sg, 1, 16, nb.sub(y, 500.0), z, -5.0, 5.0, -13.4, -7.0), facing(nb, (1, 0, 0))),
               nb.mul(text(nb, sg, 1, 16, nb.mul(nb.sub(y, 500.0), -1.0), z, -5.0, 5.0, -13.4, -7.0), facing(nb, (-1, 0, 0))))
    t0 = nb.mul(text(nb, sg, 0, 16, nb.mul(nb.sub(y, 470.0), -1.0), z, -24.0, 24.0, 0.8, 3.6), facing(nb, (-1, 0, 0)))
    return nb.mixc(col, nb.rgb('#f4efe2'), nb.mx(t3, t0))


def c_dockfloor(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    cell = nb.vec(nb.math('FLOOR', nb.math('DIVIDE', x, 5.0)), nb.math('FLOOR', nb.math('DIVIDE', y, 5.0)), 0.0)
    col = nb.hsv(nb.rgb('#bdb6a8'), 0.5, 1.0, nb.remap(hashv(nb, cell, 2.0), 0.25, 0.75, 0.9, 1.05))
    col = nb.mixc(col, nb.cmul(col, '#8f8aa3'), nb.mx(lines(nb, x, 5.0, 0.08), lines(nb, y, 5.0, 0.08)))
    col = nb.mixc(col, nb.rgb('#5d5a6e'), nb.mx(inr(nb, x, -505.0, -503.6), inr(nb, x, -416.4, -415.0)))
    col = nb.mixc(col, nb.rgb('#f2b705'), nb.mul(inr(nb, nb.math('ABSOLUTE', nb.sub(x, -460.0)), -1.0, 0.25), nb.math('LESS_THAN', per(nb, y, 6.0), 0.6)))
    st = nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.08), 1.0, 3.0, 0.6, 0.3), 0.6, 0.62), 0.5)
    col = nb.mixc(col, nb.mixc(col, nb.rgb('#9a4f2a'), 0.45), st)
    col = nb.mixc(col, nb.cmul(col, '#a6b39a'), nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.05), 1.0, 2.0), 0.58, 0.6), 0.6))
    return puddles(nb, col, P, 1.0, 0.06, 0.6, '#b7d3ff')


def c_caisson(nb):
    P = _O(nb); x, y, z = nb.xyz(P); ny = nb.xyz(_ON(nb))[1]
    col = nb.rgb('#2f6f78')
    col = nb.mixc(col, nb.cmul(col, '#7d7aa0'), nb.mx(lines(nb, x, 4.0, 0.12), lines(nb, z, 3.0, 0.12)))
    riv = nb.mul(nb.mx(lines(nb, nb.add(x, 0.3), 4.0, 0.05), lines(nb, nb.add(z, 0.3), 3.0, 0.05)), nb.math('LESS_THAN', per(nb, nb.add(x, z), 0.45), 0.35))
    col = nb.mixc(col, nb.hsv(col, 0.5, 1.0, 1.35), nb.mul(riv, 0.8))
    rr = nb.mul(nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (0.9, 0.9, 0.06)), 1.0, 3.0, 0.6), 0.58, 0.62), 0.7)
    col = nb.mixc(col, nb.mixc(col, nb.rgb('#9a4f2a'), 0.8), rr)
    sea = nb.math('LESS_THAN', ny, -0.5)
    an = nb.noise(nb.vmath('SCALE', P, scale=1.2), 1.0, 3.0, 0.6)
    zz = nb.add(z, nb.mul(nb.sub(an, 0.5), 0.9))
    under = nb.mul(nb.smooth(zz, 0.15, -0.15), sea)
    band = nb.mul(nb.mul(nb.smooth(zz, 1.4, 1.0), nb.sub(1.0, under)), sea)
    col = nb.mixc(col, nb.cmul(col, '#b8b39a'), nb.mul(band, 0.8))
    col = nb.mixc(col, nb.rgb('#3f5a3a'), under)
    dry = nb.mul(nb.math('GREATER_THAN', ny, 0.5), nb.smooth(z, -12.0, -13.6))
    col = nb.mixc(col, nb.cmul(col, '#a7b49a'), nb.mul(dry, 0.7))
    col = nb.mixc(col, nb.rgb('#f2b705'), nb.mul(inr(nb, z, 3.2, 3.9), nb.math('LESS_THAN', per(nb, nb.add(x, z), 2.0), 0.5)))
    sg = tex('port_signs.png')
    col = nb.mixc(col, nb.rgb('#f4efe2'), nb.mul(text(nb, sg, 0, 16, nb.sub(x, -460.0), z, -24.0, 24.0, 0.4, 3.1), facing(nb, (0, -1, 0))))
    return nb.mixc(col, nb.rgb('#f4efe2'), nb.mul(text(nb, sg, 1, 16, nb.mul(nb.sub(x, -460.0), -1.0), z, -6.0, 6.0, -9.0, 3.0), facing(nb, (0, 1, 0))))


def c_bwcap(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    cx, cy = LH_C; dx = nb.sub(x, cx); dy = nb.sub(y, cy)
    r = nb.vmath('LENGTH', nb.vec(dx, dy, 0.0)); a = nb.math('ARCTAN2', dy, dx)
    hw = BW_W * 0.5; ysj = cy + math.sqrt(HEAD_R ** 2 - hw ** 2)
    head = nb.math('LESS_THAN', y, ysj)
    # trunk: 6 x 8 m slabs, alternate rows offset; head: rings of 5.5 m cut into ~7 m sectors
    rowt = nb.math('FLOOR', nb.math('DIVIDE', y, 8.0))
    ut = nb.add(nb.sub(x, cx), nb.mul(nb.math('FRACT', nb.mul(rowt, 0.5)), 6.0))
    ring = nb.math('FLOOR', nb.math('DIVIDE', r, 5.5))
    arcl = nb.mul(nb.add(a, math.pi), nb.mul(nb.add(ring, 0.5), 5.5))
    seg = nb.math('FLOOR', nb.math('DIVIDE', arcl, 7.0))
    cellt = nb.vec(nb.math('FLOOR', nb.math('DIVIDE', ut, 6.0)), rowt, 0.0)
    cellh = nb.vec(seg, nb.add(ring, 100.0), 0.0)
    h = nb.math('MAXIMUM', nb.mul(hashv(nb, cellt, 4.0), nb.sub(1.0, head)), nb.mul(hashv(nb, cellh, 4.5), head))
    col = nb.hsv(nb.rgb('#d6cfbf'), 0.5, 1.0, nb.remap(h, 0.25, 0.75, 0.88, 1.06))
    col = nb.mixc(col, nb.rgb('#c9c0ad'), nb.math('GREATER_THAN', h, 0.68))
    jt = nb.mx(lines(nb, y, 8.0, 0.12), lines(nb, ut, 6.0, 0.1))
    jh = nb.mx(lines(nb, r, 5.5, 0.12), lines(nb, arcl, 7.0, 0.1))
    j = nb.mx(nb.mul(jt, nb.sub(1.0, head)), nb.mul(jh, head))
    col = nb.mixc(col, nb.rgb('#6f687e'), nb.mul(j, 0.75))
    # hairline cracks (voronoi edges, only in some slabs) and chipped light edges
    ve = nb.voronoi(nb.vmath('SCALE', P, scale=0.32), 1.0, 'DISTANCE_TO_EDGE', out='Distance')
    cm = nb.mul(nb.smooth(ve, 0.035, 0.012), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.05), 1.0, 2.0), 0.55, 0.6))
    col = nb.mixc(col, nb.rgb('#7a7290'), nb.mul(cm, 0.8))
    # seaward spray strip (wet, darker, green-black at the very edge), salt crust and lichen
    sea = nb.mx(nb.mul(nb.smooth(nb.sub(cx - hw + 3.5, x), -0.5, 3.0), nb.sub(1.0, head)), nb.mul(nb.smooth(r, HEAD_R - 6.0, HEAD_R - 0.5), head))
    wn = nb.noise(nb.vmath('SCALE', P, scale=0.22), 1.0, 3.0, 0.6, 0.3)
    wet = nb.mul(sea, nb.smooth(wn, 0.38, 0.5))
    col = nb.mixc(col, nb.cmul(col, '#9a98b8'), nb.mul(wet, 0.55))
    col = nb.mixc(col, nb.rgb('#5f6f52'), nb.mul(nb.mul(sea, nb.smooth(wn, 0.6, 0.66)), 0.6))
    salt = nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.5), 1.0, 4.0, 0.7), 0.64, 0.67), nb.add(0.25, sea))
    col = nb.mixc(col, nb.rgb('#f4f1ea'), nb.mul(salt, 0.6))
    lich = nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.07), 1.0, 3.0, 0.6), 0.6, 0.62)
    col = nb.mixc(col, nb.cmul(col, '#b3bda4'), nb.mul(lich, 0.6))
    sp = nb.noise(nb.vmath('SCALE', P, scale=3.1), 1.0, 1.0, 0.5)
    col = nb.mixc(col, nb.rgb('#8d8699'), nb.mul(nb.smooth(sp, 0.7, 0.72), 0.7))
    col = nb.mixc(col, nb.rgb('#efe9dc'), nb.mul(nb.smooth(sp, 0.3, 0.28), 0.5))
    # drains along the harbour edge, a yellow edge line, a dashed white path line on the trunk axis
    drn = nb.mul(nb.mul(inr(nb, x, cx + hw - 1.25, cx + hw - 0.75), nb.math('LESS_THAN', per(nb, y, 6.0), 0.12)), nb.sub(1.0, head))
    col = nb.mixc(col, nb.rgb('#3a3448'), drn)
    col = nb.mixc(col, nb.rgb('#f2b705'), nb.mul(inr(nb, x, cx + hw - 2.4, cx + hw - 2.0), nb.math('GREATER_THAN', y, ysj + 4.0)))
    col = nb.mixc(col, nb.rgb('#f3efe6'), nb.mul(nb.mul(inr(nb, x, cx - 0.18, cx + 0.18), nb.math('LESS_THAN', per(nb, y, 9.0), 0.5)),
                                                 nb.math('GREATER_THAN', y, ysj + 4.0)))
    # head: hazard ring round the drum foot and a thin white circle at r 30 (a painted turning circle)
    hz = nb.mul(inr(nb, r, 16.2, 17.4), nb.math('LESS_THAN', per(nb, nb.mul(a, 9.0), 1.0), 0.5))
    col = nb.mixc(col, nb.rgb('#f2b705'), nb.mul(inr(nb, r, 16.2, 17.4), head))
    col = nb.mixc(col, nb.rgb('#2a2236'), nb.mul(hz, head))
    col = nb.mixc(col, nb.rgb('#f3efe6'), nb.mul(nb.mul(inr(nb, r, 29.8, 30.25), nb.math('LESS_THAN', per(nb, nb.mul(a, 14.0), 1.0), 0.62)), head))
    st = nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.16), 1.0, 3.0, 0.65, 0.5), 0.62, 0.64), 0.5)
    col = nb.mixc(col, nb.mixc(col, nb.rgb('#9a4f2a'), 0.5), st)
    return puddles(nb, col, P, 1.0, 0.085, 0.645)


def c_crown(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    col = nb.rgb('#cdc5b3')
    col = nb.mixc(col, nb.cmul(col, '#8c87a2'), nb.mx(lines(nb, y, 8.0, 0.14), lines(nb, z, 1.5, 0.06, 0.3)))
    st = nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (0.8, 0.8, 0.07)), 1.0, 3.0, 0.6), 0.52, 0.56)
    return nb.mixc(col, nb.cmul(col, '#a7a2bf'), nb.mul(st, 0.6))


def c_stoneblocks(nb):
    """Rubble / armour rock and the mound under the tetrapods: voronoi stones."""
    P = nb.vmath('SCALE', _W(nb), scale=0.42)
    v = nb.voronoi(P, 1.0, 'F1', out='Distance')
    v2 = nb.voronoi(P, 1.0, 'DISTANCE_TO_EDGE', out='Distance')
    cc = nb.voronoi(P, 1.0, 'F1', out='Color')
    col = nb.mixc(nb.rgb('#bdb09a'), nb.rgb('#a39a8e'), nb.bw(cc))
    col = nb.hsv(col, 0.5, 1.0, nb.remap(v, 0.0, 0.8, 1.06, 0.92))
    return nb.mixc(col, nb.rgb('#6e6684'), nb.smooth(v2, 0.08, 0.03))


def c_terrain(nb):
    P = _W(nb); x, y, z = nb.xyz(P); nz = nb.xyz(nb.geo().outputs['Normal'])[2]
    q = nb.math('SNAP', nb.noise(nb.vmath('SCALE', P, scale=0.006), 1.0, 3.0, 0.55, 0.3), 0.25)
    col = nb.ramp(q, [(0.0, '#5f8f3e'), (0.38, '#76a248'), (0.55, '#8fb04f'), (0.75, '#a9b85a')])
    fld = nb.voronoi(nb.vmath('MULTIPLY', P, (0.012, 0.02, 0.0)), 1.0, 'F1', out='Color')
    farm = nb.mul(nb.smooth(y, 1180.0, 1300.0), nb.smooth(nz, 0.9, 0.96))
    col = nb.mixc(col, nb.ramp(nb.bw(fld), [(0.0, '#8fb04f'), (0.3, '#c9b86a'), (0.55, '#6f9a43'), (0.8, '#b7c06a')]), nb.mul(farm, 0.85))
    rock = nb.mul(nb.smooth(nz, 0.64, 0.5), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.012), 1.0, 2.0), 0.42, 0.52))
    col = nb.mixc(col, nb.mixc(nb.rgb('#c2ae92'), nb.rgb('#a8957f'), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.08), 1.0, 2.0), 0.45, 0.55)), rock)
    col = nb.mixc(col, nb.rgb('#e7d7aa'), nb.smooth(z, 3.2, 1.6))
    col = nb.mixc(col, nb.rgb('#5a7a48'), nb.smooth(z, 0.4, -0.4))
    town = nb.mul(nb.mul(nb.smooth(y, 690.0, 720.0), nb.smooth(y, 1170.0, 1120.0)), nb.mul(inr(nb, x, -900.0, 700.0), nb.sub(1.0, rock)))
    tz = nb.math('ABSOLUTE', nb.sub(nb.math('FRACT', nb.math('DIVIDE', nb.sub(z, 6.0), 14.0)), 0.5))
    street = nb.mul(nb.math('LESS_THAN', tz, 0.065), town)
    col = nb.mixc(col, nb.mixc(col, nb.rgb('#e2d6bf'), 0.55), nb.mul(town, 0.55))
    col = nb.mixc(col, nb.rgb('#ded5c4'), street)
    return nb.mixc(col, nb.rgb('#a39c97'), nb.mul(street, nb.math('LESS_THAN', tz, 0.01)))




# ------------------------------------------------------------------------------------------------------------------------------ colour functions: machines, buildings
def c_container(L):
    def f(nb):
        P = _O(nb); x, y, z = nb.xyz(P); nx, ny, nz = nb.xyz(_ON(nb))
        base = ocol(nb, 'ccol')
        side = nb.math('GREATER_THAN', nb.math('ABSOLUTE', ny), 0.6)
        endf = nb.math('GREATER_THAN', nb.math('ABSOLUTE', nx), 0.6)
        top = nb.math('GREATER_THAN', nz, 0.6)
        groove = nb.math('LESS_THAN', per(nb, x, 0.62), 0.42)
        col = nb.mixc(base, nb.hsv(base, 0.5, 1.0, 0.8), nb.mul(nb.mx(side, top), groove))
        col = nb.mixc(col, nb.hsv(base, 0.5, 0.9, 1.18), nb.mul(side, lines(nb, x, 0.62, 0.06, 0.26)))
        # end doors: centre split, four lock bars, hinges
        bars = nb.mx(nb.mx(lines(nb, nb.sub(y, -0.85), 1e6, 0.06), lines(nb, nb.sub(y, -0.35), 1e6, 0.06)), nb.mx(lines(nb, nb.sub(y, 0.35), 1e6, 0.06), lines(nb, nb.sub(y, 0.85), 1e6, 0.06)))
        dpan = nb.math('LESS_THAN', per(nb, z, 0.5), 0.12)
        col = nb.mixc(col, nb.hsv(base, 0.5, 1.0, 0.72), nb.mul(endf, nb.mx(lines(nb, y, 1e6, 0.05), nb.mul(dpan, 0.5))))
        col = nb.mixc(col, nb.rgb('#d9d6d0'), nb.mul(endf, nb.mul(bars, inr(nb, z, 0.2, 2.4))))
        frame = nb.mx(nb.mx(nb.math('LESS_THAN', z, 0.17), nb.math('GREATER_THAN', z, 2.43)), nb.math('GREATER_THAN', nb.math('ABSOLUTE', x), L * 0.5 - 0.17))
        col = nb.mixc(col, nb.hsv(base, 0.5, 0.85, 0.66), frame)
        logo = ocol(nb, 'logo'); lg = nb.xyz(logo)
        us = nb.mul(x, nb.math('SIGN', nb.mul(ny, -1.0)))
        bv0, bv1 = (0.55, 2.15) if L > 7.0 else (0.95, 1.75)
        t = text(nb, tex('port_brands.png'), lg[0], 8, us, z, -L * 0.4, L * 0.4, bv0, bv1, ra=8.0)
        col = nb.mixc(col, nb.mixc(nb.rgb('#f6f2ea'), nb.rgb('#26304e'), lg[1]), nb.mul(nb.mul(t, side), lg[2]))
        return col
    return f


def c_cranewhite(nb):
    P = _O(nb); x, y, z = nb.xyz(P); nx, ny, nz = nb.xyz(_ON(nb))
    col = nb.rgb('#f0ebe1')
    col = nb.mixc(col, nb.rgb('#c8322b'), nb.mul(nb.math('LESS_THAN', y, -48.0), nb.math('LESS_THAN', per(nb, y, 4.0), 0.5)))
    col = nb.mixc(col, nb.cmul(col, '#9893b0'), nb.mul(lines(nb, y, 6.0, 0.08), nb.math('LESS_THAN', nb.math('ABSOLUTE', nz), 0.5)))
    sx = nb.math('SIGN', nx)
    sideface = nb.math('GREATER_THAN', nb.math('ABSOLUTE', nx), 0.6)
    sg = tex('port_signs.png')
    let = text(nb, sg, nb.add(2.0, nb.objattr('cid')), 16, nb.mul(sx, nb.add(y, 30.0)), z, -5.0, 5.0, -1.7, 2.3)
    hh = text(nb, sg, 6, 16, nb.mul(sx, nb.add(y, 9.0)), z, -12.0, 12.0, -0.9, 1.6)
    return nb.mixc(col, nb.rgb('#c8322b'), nb.mul(nb.mx(let, hh), sideface))


def c_cranered(nb):
    P = _O(nb); x, y, z = nb.xyz(P)
    col = nb.rgb('#c8322b')
    haz = nb.mul(nb.math('LESS_THAN', z, 3.0), nb.math('LESS_THAN', per(nb, nb.add(nb.add(x, y), z), 1.2), 0.5))
    col = nb.mixc(col, nb.rgb('#f2b705'), nb.mul(haz, nb.math('GREATER_THAN', z, 0.6)))
    col = nb.mixc(col, nb.rgb('#24202e'), nb.mul(nb.math('LESS_THAN', z, 3.0), nb.mul(nb.sub(1.0, haz), nb.math('GREATER_THAN', z, 0.6))))
    return nb.mixc(col, nb.cmul(col, '#9a90aa'), nb.mul(lines(nb, z, 5.0, 0.1), 0.6))


def c_hazard(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    return nb.mixc(nb.rgb('#f2b705'), nb.rgb('#221d2b'), nb.math('LESS_THAN', per(nb, nb.add(nb.add(x, y), z), 0.9), 0.5))


def c_glass(nb):
    P = _W(nb); x, y, z = nb.xyz(P); N = nb.geo().outputs['Normal']
    col = nb.mixc(nb.rgb('#35557f'), nb.rgb('#8fc2e8'), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.05), 1.0, 2.0), 0.4, 0.62))
    st = nb.math('LESS_THAN', per(nb, nb.add(nb.add(x, y), nb.mul(z, 1.6)), 7.0), 0.18)
    col = nb.mixc(col, nb.rgb('#d6f0ff'), nb.mul(st, 0.75))
    return nb.mixc(col, nb.rgb('#e9e4d6'), nb.mx(lines(nb, nb.add(x, y), 1.4, 0.1), lines(nb, z, 1.6, 0.08)))


def c_warehouse(nb):
    P = _O(nb); x, y, z = nb.xyz(P); nx, ny, nz = nb.xyz(_ON(nb))
    hx = nb.objattr('hx'); hz = nb.objattr('hz')
    base = ocol(nb, 'wcol'); u = nb.add(x, y)
    col = nb.mixc(base, nb.hsv(base, 0.5, 1.0, 0.82), nb.math('LESS_THAN', per(nb, u, 0.9), 0.4))
    col = nb.mixc(col, nb.rgb('#b9b2a6'), nb.math('LESS_THAN', z, 1.2))
    wband = inr(nb, z, nb.sub(hz, 3.4), nb.sub(hz, 1.7))
    win = nb.mixc(nb.rgb('#4c6f99'), nb.rgb('#a6d0ee'), nb.math('LESS_THAN', per(nb, nb.add(u, z), 5.0), 0.3))
    col = nb.mixc(col, nb.mixc(win, nb.rgb('#e8e2d4'), lines(nb, u, 3.0, 0.18)), wband)
    sfront = nb.math('GREATER_THAN', nb.math('ABSOLUTE', ny), 0.6)
    dsp = 16.0; du = nb.sub(per(nb, nb.add(x, 8.0), dsp), 0.5)
    door = nb.mul(nb.mul(nb.math('LESS_THAN', nb.math('ABSOLUTE', du), 3.2 / dsp), nb.math('LESS_THAN', z, 6.4)), sfront)
    door = nb.mul(door, nb.math('LESS_THAN', nb.math('ABSOLUTE', x), nb.sub(hx, 4.0)))
    slat = nb.mixc(nb.rgb('#d9d6cf'), nb.rgb('#aeaab4'), nb.math('LESS_THAN', per(nb, z, 0.35), 0.25))
    col = nb.mixc(col, nb.rgb('#3b4152'), nb.mul(sfront, nb.mul(nb.math('LESS_THAN', nb.math('ABSOLUTE', du), 3.55 / dsp), nb.mul(nb.math('LESS_THAN', z, 6.75), nb.math('LESS_THAN', nb.math('ABSOLUTE', x), nb.sub(hx, 4.0))))))
    col = nb.mixc(col, slat, door)
    sg = text(nb, tex('port_signs.png'), nb.add(10.0, nb.objattr('wn')), 16, nb.mul(x, nb.math('SIGN', nb.mul(ny, -1.0))), nb.sub(z, nb.sub(hz, 5.6)), -8.2, 8.2, 0.0, 2.2)
    col = nb.mixc(col, nb.rgb('#f6f1e4'), nb.mul(sg, sfront))
    return col


def c_metalroof(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    col = nb.rgb('#8ea2b2')
    col = nb.mixc(col, nb.hsv(col, 0.5, 1.0, 0.85), nb.math('LESS_THAN', per(nb, x, 0.8), 0.4))
    return nb.mixc(col, nb.mixc(col, nb.rgb('#9a4f2a'), 0.5), nb.mul(nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (0.3, 0.05, 0.3)), 1.0, 3.0), 0.6, 0.63), 0.6))


def c_silo(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    col = nb.rgb('#ece5d4')
    col = nb.mixc(col, nb.cmul(col, '#a49fb8'), nb.mul(lines(nb, z, 1.25, 0.06), 0.6))
    st = nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (1.2, 1.2, 0.04)), 1.0, 3.0, 0.6), 0.56, 0.6)
    col = nb.mixc(col, nb.cmul(col, '#aaa2bd'), nb.mul(st, nb.smooth(z, 50.0, 20.0)))
    return col


def c_office(nb):
    P = _O(nb); x, y, z = nb.xyz(P); nz = nb.xyz(_ON(nb))[2]
    base = ocol(nb, 'wcol'); u = nb.add(x, y)
    cu = per(nb, u, 3.2); cz = per(nb, nb.sub(z, 0.4), 3.4)
    win = nb.mul(inr(nb, cu, 0.2, 0.8), inr(nb, cz, 0.28, 0.82))
    glass = nb.mixc(nb.rgb('#3d5d88'), nb.rgb('#9cc8ea'), nb.math('LESS_THAN', per(nb, nb.add(u, nb.mul(z, 0.7)), 9.0), 0.35))
    col = nb.mixc(base, glass, nb.mul(win, nb.math('GREATER_THAN', z, 3.0)))
    col = nb.mixc(col, nb.hsv(base, 0.5, 1.0, 0.82), nb.math('LESS_THAN', z, 0.8))
    col = nb.mixc(col, nb.rgb('#b8b2a8'), nb.math('GREATER_THAN', nz, 0.6))
    return col


def c_house(nb):
    P = _O(nb); x, y, z = nb.xyz(P); nx, ny, nz = nb.xyz(_ON(nb))
    base = ocol(nb, 'wcol'); scol = ocol(nb, 'scol'); u = nb.add(x, y)
    cu = per(nb, nb.add(u, 0.4), 2.9); cz = per(nb, z, 3.0)
    wall = nb.math('LESS_THAN', nb.math('ABSOLUTE', nz), 0.5)
    win = nb.mul(nb.mul(inr(nb, cu, 0.36, 0.64), inr(nb, cz, 0.3, 0.78)), wall)
    sh = nb.mul(nb.mul(nb.mx(inr(nb, cu, 0.2, 0.34), inr(nb, cu, 0.66, 0.8)), inr(nb, cz, 0.3, 0.78)), wall)
    col = nb.mixc(base, nb.rgb('#e7e0d0'), nb.mul(nb.mul(nb.mx(inr(nb, cu, 0.33, 0.67), 0.0), inr(nb, cz, 0.26, 0.82)), wall))
    col = nb.mixc(col, nb.mixc(nb.rgb('#3a4a6e'), nb.rgb('#7fa7cf'), nb.math('LESS_THAN', per(nb, nb.add(u, z), 2.0), 0.3)), win)
    col = nb.mixc(col, scol, sh)
    door = nb.mul(nb.mul(nb.math('LESS_THAN', nb.math('ABSOLUTE', x), 0.6), nb.math('LESS_THAN', z, 2.3)), nb.math('LESS_THAN', ny, -0.6))
    col = nb.mixc(col, nb.hsv(scol, 0.5, 1.0, 0.8), door)
    col = nb.mixc(col, nb.rgb('#bdb4a3'), nb.math('LESS_THAN', z, 0.7))
    st = nb.mul(nb.smooth(nb.noise(nb.vmath('MULTIPLY', _W(nb), (0.9, 0.9, 0.12)), 1.0, 3.0, 0.6), 0.58, 0.62), 0.5)
    return nb.mixc(col, nb.cmul(col, '#c4bccf'), st)


def c_roof(nb):
    P = _O(nb); x, y, z = nb.xyz(P)
    h = nb.objattr('rhue')
    base = nb.ramp(h, [(0.0, '#c8553d'), (0.3, '#b9472f'), (0.55, '#d26a43'), (0.8, '#a94a3a'), (0.92, '#2a8f8a')])
    row = nb.math('FLOOR', nb.math('DIVIDE', z, 0.34))
    col = nb.mixc(base, nb.hsv(base, 0.5, 1.0, 0.78), lines(nb, z, 0.34, 0.06))
    col = nb.mixc(col, nb.hsv(base, 0.5, 1.0, 0.86), nb.mul(lines(nb, nb.add(nb.add(x, y), nb.mul(row, 0.13)), 0.26, 0.04), 0.7))
    return nb.mixc(col, nb.cmul(col, '#c9c2a0'), nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', _W(nb), scale=0.4), 1.0, 2.0), 0.6, 0.64), 0.6))


def c_rowhouse(nb):
    """Terrace houses: UV = (metres along the wall, metres above the street-side floor); per-face attributes wcol, scol, hw, front."""
    U, V, _u = nb.xyz(nb.tc().outputs['UV']); nz = nb.xyz(nb.geo().outputs['Normal'])[2]
    base = nb.attr('wcol', 'Color', 'GEOMETRY'); scol = nb.attr('scol', 'Color', 'GEOMETRY')
    fr = nb.attr('front', 'Fac', 'GEOMETRY'); hw = nb.attr('hw', 'Fac', 'GEOMETRY')
    wall = nb.math('LESS_THAN', nb.math('ABSOLUTE', nz), 0.5)
    cu = per(nb, nb.add(U, 0.45), 2.9); cz = per(nb, V, 3.0)
    up = nb.mul(nb.math('GREATER_THAN', V, 2.9), wall)
    win = nb.mul(nb.mul(inr(nb, cu, 0.36, 0.64), inr(nb, cz, 0.3, 0.78)), up)
    sh = nb.mul(nb.mul(nb.mx(inr(nb, cu, 0.2, 0.34), inr(nb, cu, 0.66, 0.8)), inr(nb, cz, 0.3, 0.78)), up)
    col = nb.mixc(base, nb.rgb('#e9e2d2'), nb.mul(nb.mul(inr(nb, cu, 0.33, 0.67), inr(nb, cz, 0.26, 0.82)), up))
    col = nb.mixc(col, nb.mixc(nb.rgb('#3a4a6e'), nb.rgb('#7fa7cf'), nb.math('LESS_THAN', per(nb, nb.add(U, V), 2.0), 0.3)), win)
    col = nb.mixc(col, scol, sh)
    # ground floor: a door mid-front, small barred windows elsewhere, a grey plinth and a string course
    dd = nb.math('ABSOLUTE', nb.sub(U, nb.mul(hw, 0.5)))
    door = nb.mul(nb.mul(nb.math('LESS_THAN', dd, 0.62), nb.math('LESS_THAN', V, 2.3)), nb.mul(fr, wall))
    gwin = nb.mul(nb.mul(nb.mul(inr(nb, cu, 0.34, 0.66), inr(nb, V, 1.0, 2.1)), nb.math('GREATER_THAN', dd, 1.1)), nb.mul(fr, wall))
    col = nb.mixc(col, nb.rgb('#43506f'), gwin)
    col = nb.mixc(col, nb.hsv(scol, 0.5, 1.0, 0.75), door)
    col = nb.mixc(col, nb.rgb('#bdb4a3'), nb.mul(nb.math('LESS_THAN', V, 0.7), wall))
    col = nb.mixc(col, nb.cmul(col, '#d9d2e2'), nb.mul(inr(nb, V, 2.85, 3.05), wall))
    st = nb.mul(nb.smooth(nb.noise(nb.vmath('MULTIPLY', _W(nb), (0.9, 0.9, 0.12)), 1.0, 3.0, 0.6), 0.58, 0.62), 0.5)
    return nb.mixc(col, nb.cmul(col, '#c4bccf'), st)


def c_rowroof(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    h = nb.attr('rhue', 'Fac', 'GEOMETRY')
    base = nb.ramp(h, [(0.0, '#c8553d'), (0.3, '#b9472f'), (0.55, '#d26a43'), (0.8, '#a94a3a'), (0.92, '#2a8f8a')])
    row = nb.math('FLOOR', nb.math('DIVIDE', z, 0.34))
    col = nb.mixc(base, nb.hsv(base, 0.5, 1.0, 0.78), lines(nb, z, 0.34, 0.06))
    col = nb.mixc(col, nb.hsv(base, 0.5, 1.0, 0.86), nb.mul(lines(nb, nb.add(nb.add(x, y), nb.mul(row, 0.13)), 0.26, 0.04), 0.7))
    return nb.mixc(col, nb.cmul(col, '#c9c2a0'), nb.mul(nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.4), 1.0, 2.0), 0.6, 0.64), 0.6))


def c_tree(nb):
    r = orand(nb)
    base = nb.ramp(r, [(0.0, '#4f8a3a'), (0.3, '#5f9a40'), (0.55, '#3f7a3e'), (0.8, '#76a44a')])
    nz = nb.xyz(nb.geo().outputs['Normal'])[2]
    v = nb.voronoi(nb.vmath('SCALE', _W(nb), scale=0.5), 1.0, 'F1', out='Distance')
    return nb.mixc(base, nb.hsv(base, 0.5, 1.0, 1.22), nb.mul(nb.smooth(nz, 0.2, 0.6), nb.smooth(v, 0.5, 0.3)))


# ------------------------------------------------------------------------------------------------------------------------------ colour functions: boats, lighthouse
def c_hull(nb):
    P = _O(nb); x, y, z = nb.xyz(P); nx, ny, nz = nb.xyz(_ON(nb))
    main = ocol(nb, 'hcol'); band = ocol(nb, 'bcol'); sheer = nb.objattr('sheer')
    col = nb.mixc(main, band, nb.math('GREATER_THAN', z, nb.sub(nb.add(sheer, nb.mul(nb.math('MAXIMUM', nb.sub(x, 2.0), 0.0), 0.09)), 0.55)))
    col = nb.mixc(col, nb.rgb('#2a2236'), inr(nb, z, 0.18, 0.42))
    col = nb.mixc(col, nb.rgb('#b8352c'), nb.math('LESS_THAN', z, 0.18))
    L = nb.objattr('blen')
    u = nb.math('DIVIDE', nb.mul(nb.math('SIGN', nb.mul(ny, -1.0)), nb.sub(x, nb.mul(L, 0.22))), nb.mul(L, 0.36))
    t = text(nb, tex('port_boats.png'), nb.objattr('nrow'), 8, u, nb.math('DIVIDE', nb.sub(z, 0.7), 0.8), -0.5, 0.5, 0.0, 1.0,
             crop=nb.math('MINIMUM', nb.mul(L, 0.45 / 8.0), 1.0))
    side = nb.math('GREATER_THAN', nb.math('ABSOLUTE', ny), 0.35)
    col = nb.mixc(col, nb.rgb('#f7f3ea'), nb.mul(t, side))
    sc = nb.mul(nb.mul(nb.math('LESS_THAN', per(nb, x, 2.3), 0.12), inr(nb, z, 0.6, nb.sub(sheer, 0.3))), nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (2.0, 2.0, 0.3)), 1.0, 2.0), 0.45, 0.5))
    return nb.mixc(col, nb.mixc(col, nb.rgb('#9a4f2a'), 0.7), nb.mul(sc, side))


def _towerz(nb): return nb.add(nb.xyz(_O(nb))[2], nb.objattr('zoff'))


def _crack(nb, col, zt):
    x, y, z = nb.xyz(_O(nb))
    a = nb.math('ARCTAN2', y, x)
    u = nb.add(nb.math('DIVIDE', a, math.tau), 0.5); v = nb.math('DIVIDE', nb.sub(zt, CRACK_Z0), CRACK_H)
    # threshold floored above the map's background (0): at crack 1 the old 1 - 1.02 went below 0 and painted the whole tower
    # ink-dark from 78.4 s on. The faintest crack is 29/255 sRGB (0.012 linear), so every crack still shows at crack 1.
    cr = nb.objattr('crack'); th = nb.mx(nb.sub(1.0, nb.mul(cr, 1.02)), 0.005)
    cm = nb.bw(nb.image(tex('port_crack.png'), nb.vec(u, v, 0.0), extension='REPEAT', interp='Closest'))
    on = nb.math('GREATER_THAN', cr, 0.001)
    m = nb.mul(nb.math('GREATER_THAN', cm, th), on)
    cm2 = nb.bw(nb.image(tex('port_crack.png'), nb.vec(nb.add(u, 0.0025), nb.add(v, 0.0015), 0.0), extension='REPEAT', interp='Closest'))
    halo = nb.mul(nb.math('GREATER_THAN', cm2, th), on)
    col = nb.mixc(col, nb.rgb('#efe6d2'), nb.mul(nb.mul(halo, nb.sub(1.0, m)), 0.85))
    return nb.mixc(col, nb.rgb('#2a2236'), m)


def c_bastion(nb):
    P = _O(nb); x, y, z = nb.xyz(P); nz = nb.xyz(_ON(nb))[2]
    zt = _towerz(nb); a = nb.math('ARCTAN2', y, x)
    arc = nb.mul(a, LH_R)
    row = nb.math('FLOOR', nb.math('DIVIDE', zt, 0.9))
    uo = nb.add(arc, nb.mul(nb.math('FRACT', nb.mul(row, 0.5)), 1.9))
    blk = nb.vec(nb.math('FLOOR', nb.math('DIVIDE', uo, 1.9)), row, 0.0)
    h = hashv(nb, blk, 6.0)
    col = nb.mixc(nb.rgb('#ddd0b6'), nb.rgb('#c9bca4'), nb.smooth(h, 0.42, 0.58))
    col = nb.hsv(col, 0.5, 1.0, nb.remap(h, 0.2, 0.8, 0.88, 1.08))
    wallf = nb.math('LESS_THAN', nb.math('ABSOLUTE', nz), 0.5)
    j = nb.mx(lines(nb, uo, 1.9, 0.07), lines(nb, zt, 0.9, 0.07))
    col = nb.mixc(col, nb.cmul(col, '#8c86a0'), nb.mul(j, wallf))
    # plinth course and a string course
    col = nb.mixc(col, nb.cmul(col, '#c7c0d8'), nb.mul(nb.mx(inr(nb, zt, 4.0, 6.2), inr(nb, zt, 25.6, 26.4)), wallf))
    # door (north, toward the breakwater path): arched, deep-set
    da = nb.mul(nb.sub(a, math.pi / 2), LH_R)
    mz = nb.math('MAXIMUM', nb.sub(zt, 8.6), 0.0)
    arch = nb.mul(nb.add(nb.mul(da, da), nb.mul(mz, mz)), 1.0 / 1.4 ** 2)
    dframe = nb.mul(nb.mul(nb.math('LESS_THAN', arch, 1.0 + 0.9), nb.math('LESS_THAN', zt, 10.6)), wallf)
    door = nb.mul(nb.mul(nb.math('LESS_THAN', arch, 1.0), nb.math('LESS_THAN', zt, 9.9)), wallf)
    col = nb.mixc(col, nb.rgb('#efe7d6'), dframe)
    col = nb.mixc(col, nb.mixc(nb.rgb('#2f6f5e'), nb.rgb('#24564a'), nb.math('LESS_THAN', per(nb, nb.add(da, 3.0), 0.45), 0.15)), door)
    col = nb.mixc(col, nb.rgb('#241f30'), nb.mul(door, inr(nb, da, -1.4, -1.05)))
    # small deep-set windows: dark opening, a lit reveal on one side, a sill
    for zw0, zw1, off in ((12.4, 13.9, 0.0), (18.8, 20.3, 0.52), (23.2, 24.6, 0.26)):
        wa = nb.mul(nb.sub(per(nb, nb.add(a, off), math.tau / 6.0), 0.5), math.tau / 6.0 * LH_R)
        wz = inr(nb, zt, zw0, zw1)
        hole = nb.mul(nb.mul(nb.math('LESS_THAN', nb.math('ABSOLUTE', wa), 0.45), wz), wallf)
        rev = nb.mul(nb.mul(inr(nb, wa, -0.45, -0.18), wz), wallf)
        sill = nb.mul(nb.mul(nb.math('LESS_THAN', nb.math('ABSOLUTE', wa), 0.62), inr(nb, zt, zw0 - 0.28, zw0)), wallf)
        col = nb.mixc(col, nb.rgb('#f1e9d8'), sill)
        col = nb.mixc(col, nb.rgb('#2b2638'), hole)
        col = nb.mixc(col, nb.rgb('#b9ad98'), rev)
    rs = nb.mul(nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (0.6, 0.6, 0.05)), 1.0, 3.0, 0.6), 0.57, 0.61), 0.45)
    col = nb.mixc(col, nb.cmul(col, '#a49cb7'), rs)
    # rain streaks under the windows, chipped and repaired stones, moss at the foot and in the joints low down
    for zw0, off in ((12.4, 0.0), (18.8, 0.52), (23.2, 0.26)):
        wa = nb.mul(nb.sub(per(nb, nb.add(a, off), math.tau / 6.0), 0.5), math.tau / 6.0 * LH_R)
        stk = nb.mul(nb.mul(nb.math('LESS_THAN', nb.math('ABSOLUTE', wa), 0.5), inr(nb, zt, zw0 - 4.5, zw0 - 0.28)),
                     nb.smooth(nb.noise(nb.vec(nb.mul(wa, 3.0), nb.mul(zt, 0.15), 3.0), 1.0, 2.0), 0.42, 0.5))
        col = nb.mixc(col, nb.cmul(col, '#8f88a6'), nb.mul(nb.mul(stk, wallf), nb.smooth(zt, zw0 - 4.5, zw0 - 1.0)))
    rep = nb.mul(nb.math('GREATER_THAN', h, 0.9), wallf)
    col = nb.mixc(col, nb.rgb('#e9e1cf'), nb.mul(rep, 0.7))
    mz = nb.add(zt, nb.mul(nb.sub(nb.noise(nb.vmath('SCALE', P, scale=0.7), 1.0, 3.0, 0.6), 0.5), 2.2))
    moss = nb.mul(nb.smooth(mz, 7.4, 5.6), wallf)
    col = nb.mixc(col, nb.mixc(nb.rgb('#6b8f3a'), nb.rgb('#8fae4a'), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=2.0), 1.0, 2.0), 0.4, 0.6)), nb.mul(moss, 0.85))
    col = nb.mixc(col, nb.rgb('#6b8f3a'), nb.mul(nb.mul(j, wallf), nb.mul(nb.smooth(zt, 11.0, 7.0), 0.7)))
    # corbel band under the parapet (painted dentils) and a carved plaque over the door
    cb = nb.mul(inr(nb, zt, 25.0, 26.9), wallf)
    dent = nb.mul(nb.math('LESS_THAN', per(nb, arc, 1.6), 0.45), inr(nb, zt, 25.0, 26.0))
    col = nb.mixc(col, nb.rgb('#e6dcc6'), nb.mul(cb, 0.6))
    col = nb.mixc(col, nb.rgb('#7d7593'), nb.mul(dent, wallf))
    pl = nb.mul(nb.mul(inr(nb, da, -4.2, 4.2), inr(nb, zt, 10.9, 12.0)), wallf)
    col = nb.mixc(col, nb.rgb('#efe7d6'), pl)
    tt = text(nb, tex('port_signs.png'), 6, 16, da, zt, -4.0, 4.0, 11.0, 11.9)
    col = nb.mixc(col, nb.rgb('#5b5370'), nb.mul(tt, wallf))
    return _crack(nb, col, zt)


def c_tower(nb):
    P = _O(nb); x, y, z = nb.xyz(P)
    zt = _towerz(nb); a = nb.math('ARCTAN2', y, x)
    bandi = nb.math('FLOOR', nb.math('DIVIDE', nb.sub(zt, TW_Z0), TW_H / 5.0))
    red = nb.math('GREATER_THAN', nb.math('FRACT', nb.mul(bandi, 0.5)), 0.25)
    col = nb.mixc(nb.rgb('#f1ead8'), nb.rgb('#d23a2e'), red)
    wz = per(nb, nb.sub(zt, TW_Z0 + 3.2), TW_H / 5.0)
    side = nb.math('FLOOR', nb.math('DIVIDE', nb.sub(zt, TW_Z0 + 3.2), TW_H / 5.0))
    ang = nb.add(math.pi / 2, nb.mul(nb.math('FRACT', nb.mul(side, 0.5)), math.pi * 2 * 0.5))
    da = nb.math('ABSOLUTE', nb.sub(per(nb, nb.sub(a, ang), math.tau), 0.5))
    win = nb.mul(nb.math('GREATER_THAN', da, 0.46), inr(nb, wz, 0.0, 0.2))
    frame = nb.mul(nb.math('GREATER_THAN', da, 0.445), inr(nb, wz, -0.02, 0.22))
    col = nb.mixc(col, nb.rgb('#f7f2e6'), frame)
    col = nb.mixc(col, nb.mixc(nb.rgb('#2b3550'), nb.rgb('#6f93c0'), nb.math('LESS_THAN', wz, 0.07)), win)
    door = nb.mul(nb.math('GREATER_THAN', nb.math('ABSOLUTE', nb.sub(per(nb, nb.sub(a, math.pi / 2), math.tau), 0.5)), 0.46), nb.math('LESS_THAN', zt, TW_Z0 + 2.6))
    col = nb.mixc(col, nb.rgb('#2f6f5e'), door)
    rs = nb.mul(nb.mul(nb.smooth(nb.noise(nb.vmath('MULTIPLY', P, (1.4, 1.4, 0.08)), 1.0, 3.0, 0.6), 0.6, 0.64), 0.5), nb.add(0.4, red))
    col = nb.mixc(col, nb.mixc(col, nb.rgb('#9a4f2a'), 0.45), rs)
    # cast-iron ring seams every 1.6 m with rivet dots, vertical seams every 30 deg, a thin dark line at each band edge
    seam = nb.mx(lines(nb, zt, 1.6, 0.05), lines(nb, nb.mul(a, 6.0 / math.pi), 1.0, 0.012))
    col = nb.mixc(col, nb.cmul(col, '#9d96b4'), nb.mul(seam, 0.8))
    rv = nb.mul(lines(nb, nb.add(zt, 0.13), 1.6, 0.06), nb.math('LESS_THAN', per(nb, nb.mul(a, 60.0 / math.pi), 1.0), 0.3))
    col = nb.mixc(col, nb.hsv(col, 0.5, 1.0, 1.25), nb.mul(rv, 0.7))
    be = lines(nb, nb.sub(zt, TW_Z0), TW_H / 5.0, 0.08)
    col = nb.mixc(col, nb.rgb('#5b2a32'), nb.mul(be, 0.7))
    return _crack(nb, col, zt)


def c_lamp(nb):
    b = nb.objattr('beam')
    return nb.mixc(nb.rgb('#c9b98a'), nb.cscale(nb.rgb('#fff1c2'), 6.0), nb.math('MINIMUM', b, 1.0))


def c_beam(nb):
    return nb.cscale(nb.rgb('#fff3cf'), 1.6)


def a_beam(nb):
    P = _O(nb); x, y, z = nb.xyz(P)
    d = nb.math('ABSOLUTE', x)
    rad = nb.add(0.9, nb.mul(d, 0.07))
    core = nb.smooth(nb.math('DIVIDE', nb.vmath('LENGTH', nb.vec(0.0, y, z)), rad), 1.0, 0.2)
    fade = nb.math('POWER', nb.math('MAXIMUM', nb.sub(1.0, nb.math('DIVIDE', d, 240.0)), 0.0), 1.6)
    # gone near the lens: from the gallery (s30, 4.3 m off the lamp) the shaft's dense first metres crossed the frame as a flat
    # translucent band with hard edges (06.11); seen from 35 m and more it is unchanged
    near = nb.smooth(nb.N.new('ShaderNodeCameraData').outputs['View Distance'], 10.0, 35.0)
    return nb.mul(nb.mul(nb.mul(nb.mul(core, fade), nb.math('MINIMUM', nb.objattr('beam'), 1.5)), 0.42), near)




def celhz(name, color, ink=1.0, paint=0.0, hz=1.0, spec=0.0, rim=0.35, deep=0.55, vary=0.07, vscale=0.15, coord='Object', seed=0.0,
          grime=0.0, scuff=0.0, chips=0.0, rust=0.0, algae=0.0, waterline=0.0, wscale=1.0, wet=0.6, flash=1.0, steps=3):
    """LK.cel step for step (NB, _vary, weather, shade, finish) plus finish's haze key `hz`, which LK.cel does not expose.
    Used for the far-seen town, trees and hills: they carry a light constant ink, and a lower haze key keeps them from washing out."""
    nb = LK.NB(name)
    col = nb.rgb(color) if isinstance(color, (str, tuple)) else color(nb)
    if vary: col = LK._vary(nb, col, vary, vscale, coord, steps, seed)
    if grime or scuff or chips or rust or algae:
        col = LK.weather(nb, col, grime, scuff, chips, rust, algae, waterline, wscale, coord, seed)
    c = LK.shade(nb, col, spec, rim, deep, flash=flash, wet=wet)
    return LK.finish(nb, c, ink, paint, 0.0, None, 1.0, False, hz)


def sign_props(w, h, fv=0.7, bcol='#2a8f8a'):
    """Props for a sign plate (text row from tex/port_signs.png drawn on its -y face, aspect kept by cropping the row)."""
    return {'tk': min(0.5, 0.5 * (w / h) / (16.0 * fv)), 'fv': fv, 'sw': w, 'sh': h, 'bcol': LK.srgb(bcol)[:3]}


def c_sign(nb):
    gx, gy, gz = nb.xyz(nb.tc().outputs['Generated'])
    tk = nb.objattr('tk'); fv = nb.objattr('fv'); row = nb.objattr('row')
    u = nb.add(0.5, nb.mul(nb.sub(gx, 0.5), nb.mul(tk, 2.0)))
    v = nb.add(0.5, nb.math('DIVIDE', nb.sub(gz, 0.5), fv))
    av = nb.math('DIVIDE', nb.add(nb.sub(15.0, row), v), 16.0)
    t = nb.bw(nb.image(tex('port_signs.png'), nb.vec(u, av, 0.0), extension='CLIP'))
    t = nb.mul(nb.mul(t, inr(nb, v, 0.0, 1.0)), facing(nb, (0, -1, 0), 0.5))
    bx = nb.math('DIVIDE', 0.3, nb.objattr('sw')); bz = nb.math('DIVIDE', 0.3, nb.objattr('sh'))
    inner = nb.mul(inr(nb, gx, bx, nb.sub(1.0, bx)), inr(nb, gz, bz, nb.sub(1.0, bz)))
    col = nb.mixc(ocol(nb, 'bcol'), nb.rgb('#f4efe4'), inner)
    return nb.mixc(col, nb.rgb('#24407a'), t)


def c_wood(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    k = nb.math('FLOOR', nb.math('DIVIDE', nb.add(x, z), 0.36))
    col = nb.hsv(nb.rgb('#a77a50'), 0.5, 1.0, nb.remap(hashv(nb, nb.vec(k, 0.0, 0.0), 2.0), 0.25, 0.75, 0.82, 1.08))
    return nb.mixc(col, nb.rgb('#5e4636'), lines(nb, nb.add(x, z), 0.36, 0.035))


def c_net(nb):
    P = _W(nb); x, y, z = nb.xyz(P)
    g = nb.mx(lines(nb, nb.add(nb.add(x, y), z), 0.22, 0.035), lines(nb, nb.sub(nb.add(x, z), y), 0.22, 0.035))
    col = nb.mixc(nb.rgb('#3f8f6a'), nb.rgb('#2f6c58'), nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.8), 1.0, 2.0), 0.4, 0.6))
    return nb.mixc(col, nb.rgb('#9fd0a6'), nb.mul(g, 0.6))


def glow_alpha(name, color_fn, alpha_fn, strength=1.0, glow=1.0):
    """LK.glowmat with a node-built alpha (the kit's glowmat only takes a constant alpha); same LK.NB + LK.finish pipeline."""
    nb = LK.NB(name)
    return LK.finish(nb, color_fn(nb), 0.0, 0.0, glow, alpha_fn(nb), strength, True)


def materials(far_ink=None):
    """far_ink: ink weight for the far town, trees and hills (default 0.3)."""
    MAT.clear(); C = LK.cel; W = 'World'
    fi = (lambda d: d if far_ink is None else float(far_ink))
    MAT.update({
        'quaywall': C('PORT_quaywall', c_quaywall, algae=1.0, waterline=0.0, grime=0.5, wscale=0.5, coord=W, vary=0.04),
        'cope': C('PORT_cope', c_cope, grime=0.4, chips=0.4, wscale=0.6, coord=W),
        'apron': C('PORT_apron', c_apron, grime=0.3, wscale=0.15, coord=W, vary=0.03),
        'dockwall': C('PORT_dockwall', c_dockwall, grime=0.4, wscale=0.4, coord=W, vary=0.03, algae=0.7, waterline=-12.6),
        'dockfloor': C('PORT_dockfloor', c_dockfloor, grime=0.4, wscale=0.3, coord=W, vary=0.03),
        'caisson': C('PORT_caisson', c_caisson, spec=0.3, rust=0.6, grime=0.4, chips=0.3, wscale=0.6),
        'kconc': C('PORT_kconc', '#cfc8b8', grime=0.6, chips=0.4, wscale=0.8, coord=W, vary=0.08, vscale=0.4),
        'kwood': C('PORT_kwood', c_wood, grime=0.6, wscale=0.6, coord=W),
        'bwcap': C('PORT_bwcap', c_bwcap, grime=0.3, wscale=0.3, coord=W, vary=0.03),
        'crown': C('PORT_crown', c_crown, grime=0.5, algae=0.8, waterline=4.2, wscale=0.4, coord=W),
        'tetra': C('PORT_tetrapod', '#d3ccbc', algae=1.0, waterline=0.5, grime=0.6, chips=0.35, wscale=0.9, coord=W, vary=0.1, vscale=0.25),
        'rock': C('PORT_rock', c_stoneblocks, algae=1.0, waterline=0.3, grime=0.3, coord=W, paint=0.35, vary=0.06),
        'terrain': celhz('PORT_terrain', c_terrain, ink=fi(0.3), hz=0.6, paint=1.0, coord=W, vary=0.05, vscale=0.02),
        'steel': C('PORT_steel', '#4b5163', spec=0.6, grime=0.5, scuff=0.6, rust=0.3, wscale=0.4),
        'steeldk': C('PORT_steeldk', '#3b4152', spec=0.5, grime=0.5, rust=0.35, wscale=0.4),
        'rail': C('PORT_rail', '#a19fae', spec=0.9, scuff=0.4, vary=0.02),
        'cranered': C('PORT_cranered', c_cranered, spec=0.45, grime=0.5, chips=0.4, rust=0.35, wscale=0.35),
        'cranewhite': C('PORT_cranewhite', c_cranewhite, spec=0.4, grime=0.55, chips=0.3, rust=0.3, wscale=0.3),
        'yellow': C('PORT_yellow', '#f2b705', spec=0.5, grime=0.6, chips=0.5, rust=0.3, scuff=0.4, wscale=0.4),
        'hazard': C('PORT_hazard', c_hazard, grime=0.5, chips=0.4, wscale=0.5),
        'glass': C('PORT_glass', c_glass, spec=1.0, rim=0.2, vary=0.0),
        'rubber': C('PORT_rubber', '#2c2a35', grime=0.3, scuff=0.5, wscale=0.6),
        'wood': C('PORT_wood', c_wood, grime=0.5, algae=1.0, waterline=0.2, wscale=0.6, coord=W),
        'rope': C('PORT_rope', '#d9c9a0', grime=0.4),
        'net': C('PORT_net', c_net, grime=0.2, coord=W),
        'orange': C('PORT_orange', '#ff7a1a', spec=0.5, grime=0.3, scuff=0.3),
        'sign': C('PORT_sign', c_sign, spec=0.3, grime=0.3, rust=0.2, wscale=0.5),
        'white': C('PORT_white', '#f1ead8', spec=0.3, grime=0.4, chips=0.2, rust=0.2, wscale=0.4),
        'teal': C('PORT_teal', '#2a8f8a', spec=0.4, grime=0.5, chips=0.5, rust=0.4, wscale=0.35),
        'concrete': C('PORT_concrete', '#cfc8b8', grime=0.5, chips=0.3, wscale=0.6, coord=W, algae=1.0, waterline=0.0),
        'redlight': LK.glowmat('PORT_redlight', '#ff4a3a', 3.0),
        'lampglow': LK.glowmat('PORT_lampglow', '#ffe2a8', 1.6),
        'cont12': C('PORT_cont12', c_container(12.19), spec=0.25, grime=0.5, scuff=0.4, rust=0.45, chips=0.25, wscale=0.8, coord=W, vary=0.04),
        'cont6': C('PORT_cont6', c_container(6.06), spec=0.25, grime=0.5, scuff=0.4, rust=0.45, chips=0.25, wscale=0.8, coord=W, vary=0.04),
        'warehouse': C('PORT_warehouse', c_warehouse, grime=0.5, rust=0.35, wscale=0.4),
        'mroof': C('PORT_mroof', c_metalroof, grime=0.4, coord=W, wscale=0.4),
        'silo': C('PORT_silo', c_silo, grime=0.4, coord=W, wscale=0.3),
        'office': C('PORT_office', c_office, grime=0.3, wscale=0.4),
        'house': celhz('PORT_house', c_house, ink=fi(0.3), hz=0.6, grime=0.25, vary=0.05, coord=W, wscale=0.6),
        'roof': celhz('PORT_roof', c_roof, ink=fi(0.3), hz=0.6, grime=0.2, vary=0.05, coord=W),
        'rowhouse': celhz('PORT_rowhouse', c_rowhouse, ink=fi(0.3), hz=0.6, grime=0.25, vary=0.05, coord=W, wscale=0.6),
        'rowroof': celhz('PORT_rowroof', c_rowroof, ink=fi(0.3), hz=0.6, grime=0.2, vary=0.05, coord=W),
        'flatroof': celhz('PORT_flatroof', '#d8d0c2', ink=fi(0.3), hz=0.6, grime=0.5, vary=0.06, coord=W, wscale=0.8),
        'tree': celhz('PORT_tree', c_tree, ink=fi(0.3), hz=0.6, paint=1.0, vary=0.05, coord=W, rim=0.5),
        'trunk': celhz('PORT_trunk', '#6b4f3a', ink=fi(0.3), hz=0.6, grime=0.3),
        'hull': C('PORT_hull', c_hull, spec=0.35, grime=0.5, rust=0.4, chips=0.3, algae=1.0, waterline=0.0, wscale=0.5),
        'cabin': C('PORT_cabin', '#f4efe4', spec=0.3, grime=0.45, rust=0.35, wscale=0.5),
        'deck': C('PORT_deck', '#7f9a92', grime=0.6, scuff=0.5, rust=0.3, wscale=0.6),
        'bastion': C('LH_bastion', c_bastion, grime=0.35, wscale=0.5, vary=0.03),
        'tower': C('LH_tower', c_tower, spec=0.2, grime=0.35, chips=0.25, wscale=0.4, vary=0.03),
        'lhdark': C('LH_dark', '#2e3a3c', spec=0.6, grime=0.3, rust=0.3),
        'lhdome': C('LH_dome', '#d23a2e', spec=0.7, grime=0.3, chips=0.3),
        'lhglass': C('LH_glass', '#b4e1ee', spec=1.0, rim=0.6, vary=0.0, alpha=0.5),
        'lamp': LK.glowmat('LH_lampmat', c_lamp, 1.0),
        'beam': glow_alpha('LH_beammat', c_beam, a_beam),
    })
    mid12 = LK.REG[MAT['cont12'].name]['mid'] / 4096.0
    for k in ('cont12', 'cont6'): _oid_lod(MAT[k], mid_far=mid12)
    return MAT


def _oid_lod(mat, d0=230.0, d1=380.0, mid_far=None):
    """The post draws an id edge wherever the oid (or mid) AOV changes. Near the camera every container keeps its own oid (each box
    outlined); once the object is farther than its own threshold (spread over d0..d1 by Object Info Random, so a moving camera does not
    flip a whole yard at once) it writes the id shared by its yard block ('oidk') and, with mid_far, one material id for 40 ft and 20 ft
    boxes: a far block reads as stacked colour bands outlined as a block, instead of a solid mass of 1-2 px lines.
    Camera position in the shader = P + Incoming * View Distance; the switch is per object (object location), so it never cuts a box."""
    nt = mat.node_tree; N = nt.nodes; Lk = nt.links
    aov = next(n for n in N if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'oid')
    for l in list(aov.inputs['Value'].links): Lk.remove(l)
    geo = N.new('ShaderNodeNewGeometry'); cam = N.new('ShaderNodeCameraData'); oi = N.new('ShaderNodeObjectInfo')
    at = N.new('ShaderNodeAttribute'); at.attribute_type = 'OBJECT'; at.attribute_name = 'oidk'
    def vm(op, a, b):
        n = N.new('ShaderNodeVectorMath'); n.operation = op; Lk.new(a, n.inputs[0])
        if op == 'SCALE': Lk.new(b, n.inputs['Scale'])
        else: Lk.new(b, n.inputs[1])
        return n
    cp = vm('ADD', geo.outputs['Position'], vm('SCALE', geo.outputs['Incoming'], cam.outputs['View Distance']).outputs['Vector'])
    dist = vm('DISTANCE', cp.outputs['Vector'], oi.outputs['Location']).outputs['Value']
    def mth(op, a, b):
        n = N.new('ShaderNodeMath'); n.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: Lk.new(v, n.inputs[i])
        return n.outputs[0]
    thr = mth('ADD', mth('MULTIPLY', oi.outputs['Random'], d1 - d0), d0)
    far = mth('GREATER_THAN', dist, thr)
    oid = mth('ADD', oi.outputs['Random'], mth('MULTIPLY', mth('SUBTRACT', at.outputs['Fac'], oi.outputs['Random']), far))
    Lk.new(oid, aov.inputs['Value'])
    if mid_far is not None:
        ma = next(n for n in N if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'mid')
        own = ma.inputs['Value'].default_value
        Lk.new(mth('ADD', own, mth('MULTIPLY', far, mid_far - own)), ma.inputs['Value'])


# ------------------------------------------------------------------------------------------------------------------------------ terrain
from mathutils import noise as _noise


def _ss(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))); return t * t * (3 - 2 * t)


def coast_y(x):
    if x < -712.0: return 400.0 + (-712.0 - x) * 0.55
    if x > 615.0: return 400.0 - (x - 615.0) * 0.45
    return 400.0


def hills_h(x, y):
    n1 = _noise.noise(Vector((x * 0.0021, y * 0.0021, 0.3))); n2 = _noise.noise(Vector((x * 0.0065, y * 0.0065, 1.7)))
    t = (y - 690.0) / 470.0
    if t <= 0: h = 4.0
    elif t <= 1: h = 4.0 + 126.0 * (0.45 * t + 0.55 * t * t)
    else: h = 130.0 + 52.0 * _ss(1160.0, 1420.0, y) + 30.0 * _ss(1500.0, 2200.0, y) + 120.0 * _ss(2400.0, 3400.0, y)
    k = min(1.0, max(0.0, t))
    h += (n1 * 26.0 + n2 * 7.0) * k * (1.0 + 0.7 * _ss(1200.0, 2600.0, y))
    return h


def coastal_h(x, y):
    d = y - coast_y(x)
    n = _noise.noise(Vector((x * 0.012, y * 0.012, 4.1))); n2 = _noise.noise(Vector((x * 0.04, y * 0.04, 2.2)))
    if d < 0: return d * 0.35 + n2 * 1.2
    return 26.0 * _ss(0.0, 55.0, d) + max(0.0, d - 55.0) * 0.22 + (n * 9.0 + n2 * 2.5) * _ss(0.0, 30.0, d)


def terrain_h(x, y):
    wp = _ss(-790.0, -712.0, x) * _ss(660.0, 615.0, x)
    hh = hills_h(x, y)
    nat = max(coastal_h(x, y), hh if y > 690 else -99.0)
    port = hh if y > 690 else 4.0
    return nat + (port - nat) * wp, wp


def in_dock(x, y): return DX0 - 1e-6 <= x <= DX1 + 1e-6 and DY0 - 1e-6 <= y <= DY1 + 1e-6


def build_terrain(coll):
    xs = [float(v) for v in list(range(-2400, -1000, 50)) + list(range(-1000, 900, 10)) + list(range(900, 2400, 50))]
    ys = [float(v) for v in list(range(380, 800, 10)) + list(range(800, 1400, 15)) + list(range(1400, 3000, 50)) + list(range(3000, 4400, 100))]
    nx, ny = len(xs), len(ys)
    H = [[terrain_h(x, y) for x in xs] for y in ys]
    V = [(xs[i], ys[j], H[j][i][0]) for j in range(ny) for i in range(nx)]
    g = Geo(); g.V = V
    for j in range(ny - 1):
        for i in range(nx - 1):
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            hs = (H[j][i][0], H[j][i + 1][0], H[j + 1][i + 1][0], H[j + 1][i][0]); wp = max(H[j][i][1], H[j + 1][i + 1][1])
            if max(hs) < -2.5: continue
            if wp > 0.5 and y0 < 400.0 - 1e-6: continue
            if DX0 <= x0 and x1 <= DX1 and DY0 <= y0 and y1 <= DY1: continue
            a = j * nx + i
            flat = max(abs(h - 4.0) for h in hs) < 0.02 and wp > 0.5
            g.F.append((a, a + 1, a + nx + 1, a + nx)); g.M.append('apron' if flat else 'terrain'); g.S.append(not flat)
    o = gobj('PORT_terrain', g, coll, props={'qa_kind': 'ground'})
    return o


# ------------------------------------------------------------------------------------------------------------------------------ quay, dock
def build_quay(coll):
    g = Geo()
    for xa, xb, ca, cb in ((-712.0, DX0 - 18.0, -712.0, DX0 - 1.6), (DX1 + 18.0, 615.0, DX1 + 1.6, 615.0)):
        g.blh((xa, 400.0, -12.0), (xb, 404.0, 3.93), 'quaywall')
        g.blh((ca, 399.4, 3.55), (cb, 401.3, 4.32), 'cope')
    q = gobj('PORT_quay', g, coll, bevel=0.06, props={'qa_kind': 'ground'})
    # furniture: bollards, fenders, ladders, crane rails, lamps, life buoys, railings
    f = Geo(); R = random.Random(5)
    def skip(x): return DX0 - 8.0 < x < DX1 + 8.0 or 188.0 < x < 212.0 or x < -684.0
    x = -705.0
    while x < 612.0:
        if not skip(x):
            f.cyl((x, 401.9, 3.98), (x, 401.9, 4.7), 0.33, n=12, mat='steeldk'); f.cyl((x, 401.9, 4.7), (x, 401.9, 4.86), 0.5, n=12, mat='yellow')
            f.blh((x - 0.6, 401.3, 3.98), (x + 0.6, 402.5, 4.36), 'steeldk')
        xf = x + 10.0
        if not skip(xf) and xf < 612.0:
            f.cyl((xf, 400.0, 1.2), (xf, 398.6, 1.2), 0.75, 0.6, n=12, mat='rubber')
            f.blh((xf - 1.2, 398.25, -0.8), (xf + 1.2, 398.6, 3.2), 'yellow')
            f.blh((xf - 1.0, 398.1, -0.6), (xf + 1.0, 398.25, 3.0), 'rubber')
        x += 20.0
    for xl in range(-690, 610, 60):
        xl = float(xl) + 23.0
        if skip(xl): continue
        for s in (-0.25, 0.25):
            f.blh((xl + s - 0.05, 399.25, -3.0), (xl + s + 0.05, 399.37, 4.25), 'steel')
        for zz in range(-10, 14):
            z = zz * 0.3
            if z < -2.9 or z > 4.1: continue
            f.blh((xl - 0.25, 399.27, z - 0.03), (xl + 0.25, 399.35, z + 0.03), 'steel')
        for zb in (-2.0, 1.0, 3.2):
            f.blh((xl - 0.32, 399.37, zb - 0.06), (xl + 0.32, 400.02, zb + 0.06), 'steel')
        f.blh((xl - 0.6, 399.8, 4.25), (xl - 0.5, 400.4, 5.3), 'yellow'); f.blh((xl + 0.5, 399.8, 4.25), (xl + 0.6, 400.4, 5.3), 'yellow')
    for ry in (RAIL_W, RAIL_L):
        f.blh((-395.0, ry - 0.08, 3.95), (45.0, ry + 0.08, 4.17), 'rail')
        for xe in (-395.0, 45.0):
            f.blh((xe - 0.6, ry - 0.7, 3.95), (xe + 0.6, ry + 0.7, 5.1), 'hazard')
    lamps = [x for x in range(-680, 600, 42) if not (-420 < x < 60) and not skip(float(x))]
    for xl in lamps:
        xl = float(xl); y0 = 406.5
        f.cyl((xl, y0, 3.98), (xl, y0, 12.0), 0.16, 0.11, n=8, mat='steel')
        f.blh((xl - 0.35, y0 - 0.35, 3.98), (xl + 0.35, y0 + 0.35, 4.6), 'concrete')
        f.beam((xl, y0, 11.6), (xl, y0 - 1.6, 12.1), 0.12, 0.12, 'steel')
        f.blh((xl - 0.32, y0 - 2.1, 11.75), (xl + 0.32, y0 - 1.3, 12.15), 'steeldk'); f.blh((xl - 0.26, y0 - 2.0, 11.6), (xl + 0.26, y0 - 1.4, 11.75), 'lampglow')
    for xb in range(-660, 610, 85):
        xb = float(xb) + 31.0
        if skip(xb) or -420 < xb < 60: continue
        f.blh((xb - 0.08, 402.9, 3.98), (xb + 0.08, 403.06, 5.6), 'white')
        ring = []
        for k in range(14):
            a = k / 14 * math.tau; ring.append((xb + math.cos(a) * 0.42, 402.75, 5.0 + math.sin(a) * 0.42))
        f.tube(ring + ring[:1], 0.08, n=6, mat='orange', caps=False)
    for xa, xb in ((300.0, 612.0), (-700.0, -540.0)):
        x = xa
        while x <= xb:
            f.blh((x - 0.05, 401.0, 4.3), (x + 0.05, 401.1, 5.4), 'white'); x += 2.5
        for zr in (4.85, 5.35):
            f.blh((xa, 400.98, zr - 0.04), (xb, 401.12, zr + 0.04), 'white')
    fo = gobj('PORT_quayprops', f, coll, bevel=0.03, props={'qa_kind': 'prop'})
    return q, fo


def build_dock(coll):
    g = Geo(); OX0, OX1, OY1 = DX0 - 20.0, DX1 + 20.0, DY1 + 20.0
    g.blh((OX0, DY0 - 2.0, DZ - 2.0), (OX1, OY1, DZ), 'dockfloor')
    levels = ((0.0, 0.5, 3.93), (1.6, -3.0, 0.5), (3.2, -6.5, -3.0), (4.8, DZ - 0.5, -6.5))
    for e, z0, z1 in levels:
        ys = DY0 + 10.0 if e > 0 else DY0
        g.blh((OX0, ys, z0), (DX0 + e, DY1 - e, z1), 'dockwall')
        g.blh((DX1 - e, ys, z0), (OX1, DY1 - e, z1), 'dockwall')
        g.blh((OX0, DY1 - e, z0), (OX1, OY1, z1), 'dockwall')
    g.blh((OX0, DY0 - 0.1, DZ - 0.5), (DX0, DY0 + 10.0, 3.93), 'dockwall'); g.blh((DX1, DY0 - 0.1, DZ - 0.5), (OX1, DY0 + 10.0, 3.93), 'dockwall')
    # rim coping round the basin
    g.blh((DX0 - 1.6, DY0 + 0.0, 3.6), (DX0 + 0.15, DY1 + 1.6, 4.32), 'cope'); g.blh((DX1 - 0.15, DY0 + 0.0, 3.6), (DX1 + 1.6, DY1 + 1.6, 4.32), 'cope')
    g.blh((DX0 - 1.6, DY1 - 0.15, 3.6), (DX1 + 1.6, DY1 + 1.6, 4.32), 'cope')
    # stair flights down the altars (west and east walls)
    for side in (-1, 1):
        xw = DX0 if side < 0 else DX1
        for k, (e, z0, z1) in enumerate(levels[:-1]):
            e2, zlow = levels[k + 1][0], levels[k + 1][2]
            n = int((z1 - zlow) / 0.32)
            for s in range(n):
                zt = z1 - (s + 1) * (z1 - zlow) / n
                yy = 470.0 + k * 9.0 + s * 0.42
                x0 = xw - side * e; x1 = xw - side * e2
                g.blh((min(x0, x1) + 0.02, yy, zlow - 0.3), (max(x0, x1) - 0.02, yy + 0.42, zt), 'dockwall')
    d = gobj('PORT_dock', g, coll, bevel=0.08, props={'qa_kind': 'ground'})
    # side (bilge) block rows only outside x -490..-430: the mech sits in the middle and walks out over the gate
    kb = Geo()
    for xx in (-498.5, -421.5):
        for yy in range(416, 592, 7):
            kb.blh((xx - 1.0, yy - 0.8, DZ - 0.05), (xx + 1.0, yy + 0.8, DZ + 1.2), 'kconc'); kb.blh((xx - 0.9, yy - 0.7, DZ + 1.2), (xx + 0.9, yy + 0.7, DZ + 1.55), 'kwood')
    for wx, sgn in ((DX0 + 4.8, 1.0), (DX1 - 4.8, -1.0)):
        for yl in (452.0, 548.0):
            xr = wx + sgn * 0.25
            for sy in (-0.3, 0.3):
                kb.blh((xr - 0.05, yl + sy - 0.05, DZ + 0.02), (xr + 0.05, yl + sy + 0.05, -6.3), 'steel')
            z = DZ + 0.35
            while z < -6.6:
                kb.blh((xr - 0.03, yl - 0.3, z - 0.03), (xr + 0.03, yl + 0.3, z + 0.03), 'steel'); z += 0.3
            for zb in (-12.0, -9.0, -7.0):
                for sy in (-0.3, 0.3):
                    kb.blh((min(wx - sgn * 0.05, xr), yl + sy - 0.04, zb - 0.04), (max(wx - sgn * 0.05, xr), yl + sy + 0.04, zb + 0.04), 'steel')
    k = gobj('PORT_keelblocks', kb, coll, bevel=0.05, props={'qa_kind': 'prop'})
    # caisson gate: a flat-topped steel box (top z 3.95, nothing on it: the mech walks out over it), stiffener ribs on the sea face
    c = Geo(); y0, y1 = DY0 + 0.05, DY0 + 7.0
    c.blh((DX0 + 0.05, y0, DZ + 0.05), (DX1 - 0.05, y1, 3.95), 'caisson')
    for xr in range(int(DX0) + 6, int(DX1) - 3, 6):
        c.blh((xr - 0.25, y0 - 0.45, -11.0), (xr + 0.25, y0, 3.4), 'caisson')
    c.blh((DX0 + 0.05, y0 - 0.5, 3.4), (DX1 - 0.05, y0, 3.9), 'caisson')
    gate = gobj('PORT_caisson', c, coll, bevel=0.05, props={'qa_kind': 'prop'})
    return d, k, gate




# ------------------------------------------------------------------------------------------------------------------------------ ship-to-shore cranes
HINGE = (0.0, -15.0, 47.0)        # boom hinge in legs-local coordinates (legs origin = ground centre between the 4 legs)
ROPE_TOP, SPREADER_Z = -0.6, -28.35  # trolley-local z of the rope top and of the spreader headblock top (the frame bottom is 2.5 m lower)
APEX = (0.0, 8.0, 78.0)


def _rail(g, pts, z0, h, mat='white', step=2.5, post=0.07):
    """Railing along a polyline at deck height z0: posts every `step`, top + knee rails."""
    for a, b in zip(pts, pts[1:]):
        a = Vector(a); b = Vector(b); L = (b - a).length; n = max(1, int(L / step))
        for i in range(n + 1):
            p = a + (b - a) * (i / n); g.blh((p.x - post, p.y - post, z0), (p.x + post, p.y + post, z0 + h), mat)
        for zr in (h * 0.5, h):
            g.beam((a.x, a.y, z0 + zr), (b.x, b.y, z0 + zr), post * 1.2, post * 1.2, mat)


def crane_meshes():
    """Shared meshes: legs (portal, apex, backreach girder, machinery house, stairs, bogies), boom, trolley, cab, spreader, ropes."""
    L = Geo()
    for sx in (-9.0, 9.0):
        for sy in (-15.0, 15.0):
            L.blh((sx - 1.0, sy - 1.0, 1.9), (sx + 1.0, sy + 1.0, 43.6), 'cranered')
            L.blh((sx - 4.2, sy - 0.75, 0.78), (sx + 4.2, sy + 0.75, 1.9), 'yellow')
            L.blh((sx - 1.3, sy - 1.3, 1.85), (sx + 1.3, sy + 1.3, 2.6), 'steeldk')
            for wx in (-3.1, -1.05, 1.05, 3.1):
                L.cyl((sx + wx, sy - 0.62, 0.64), (sx + wx, sy + 0.62, 0.64), 0.46, n=12, mat='steeldk')
            for e in (-4.55, 4.25):
                L.blh((sx + e, sy - 0.45, 0.95), (sx + e + 0.3, sy + 0.45, 1.6), 'hazard')
            for zl in (12.0, 24.0, 36.0):
                L.blh((sx - 1.06, sy - 0.25, zl), (sx + 1.06, sy + 0.25, zl + 0.5), 'steeldk')
        L.beam((sx, -14.0, 13.0), (sx, 14.0, 13.0), 1.6, 2.2, 'cranered')
        L.beam((sx, -14.0, 14.6), (sx, 14.0, 42.2), 1.1, 1.1, 'cranered')
        L.beam((sx, -16.0, 45.0), (sx, 16.0, 45.0), 2.0, 3.0, 'cranered')
        L.beam((sx, -6.0, 46.3), (sx * 0.24, 8.0, 77.5), 1.2, 1.2, 'cranered')
        L.beam((sx, 15.0, 46.3), (sx * 0.24, 8.0, 77.5), 1.2, 1.2, 'cranered')
    L.beam((-10.6, -15.0, 45.0), (10.6, -15.0, 45.0), 2.4, 3.0, 'cranered')
    L.beam((-10.6, 15.0, 45.0), (10.6, 15.0, 45.0), 2.4, 3.0, 'cranered')
    L.beam((-10.6, 15.0, 13.0), (10.6, 15.0, 13.0), 1.4, 1.8, 'cranered')
    L.blh((-2.7, 6.7, 77.0), (2.7, 9.3, 79.6), 'cranered'); L.blh((-3.4, 6.2, 79.6), (3.4, 9.8, 79.8), 'steel')
    _rail(L, [(-3.3, 6.3), (3.3, 6.3), (3.3, 9.7), (-3.3, 9.7), (-3.3, 6.3)], 79.8, 1.1, 'white', 1.6, 0.05)
    L.sphere((0.0, 8.0, 80.3), 0.3, 'redlight', 8, 5)
    for sx in (-4.5, 4.5):
        L.blh((sx - 1.0, -14.2, 47.0), (sx + 1.0, 46.0, 50.5), 'cranewhite')
        L.blh((sx - 0.8, -15.6, 46.45), (sx + 0.8, -14.4, 46.97), 'steeldk'); L.blh((sx - 0.8, 14.4, 46.45), (sx + 0.8, 15.6, 47.05), 'steeldk')
        L.beam((0.0, 8.0, 78.0), (sx, 44.5, 50.6), 0.55, 0.55, 'cranered')
        _rail(L, [(sx + 0.85 * (1 if sx > 0 else -1), -14.0), (sx + 0.85 * (1 if sx > 0 else -1), 45.8)], 50.5, 1.1, 'white', 3.0, 0.05)
    for yy in (-8.0, 4.0, 18.0, 26.0):
        L.blh((-3.6, yy - 0.4, 49.6), (3.6, yy + 0.4, 50.4), 'cranewhite')
    L.blh((-6.2, 28.0, 50.45), (6.2, 45.0, 56.6), 'cranewhite'); L.blh((-6.5, 27.7, 56.6), (6.5, 45.3, 57.1), 'steeldk')
    for yv in (31.0, 35.0, 39.0):
        L.blh((-1.2, yv, 57.1), (1.2, yv + 2.0, 58.3), 'steel')
    L.blh((-6.28, 30.0, 52.0), (-6.18, 43.0, 54.0), 'glass'); L.blh((6.18, 30.0, 52.0), (6.28, 43.0, 54.0), 'glass')
    L.blh((-6.27, 44.0, 50.6), (-6.19, 44.9, 53.0), 'steeldk')
    # stair tower on the landside +x leg: landings and flights with handrails
    zs = [7.0 + 6.0 * k for k in range(7)]
    for k, z in enumerate(zs):
        ya, yb = (11.0, 13.0) if k % 2 == 0 else (17.0, 19.0)
        L.blh((10.15, ya, z - 0.2), (12.4, yb, z), 'steel'); L.blh((10.0, (ya + yb) / 2 - 0.3, z - 0.6), (10.2, (ya + yb) / 2 + 0.3, z), 'steel')
        _rail(L, [(12.35, ya), (12.35, yb)], z, 1.1, 'yellow', 1.0, 0.04)
        if k + 1 < len(zs):
            y0, y1 = (13.0, 17.0) if k % 2 == 0 else (17.0, 13.0)
            L.beam((11.3, y0, z - 0.1), (11.3, y1, zs[k + 1] - 0.1), 1.0, 0.22, 'steel')
            L.beam((12.3, y0, z + 1.0), (12.3, y1, zs[k + 1] + 1.0), 0.06, 0.06, 'yellow')
    L.cyl((10.4, 21.0, 10.0), (12.6, 21.0, 10.0), 2.6, n=18, mat='steeldk'); L.cyl((10.2, 21.0, 10.0), (12.8, 21.0, 10.0), 0.6, n=10, mat='yellow')
    L.blh((10.0, 19.6, 8.6), (10.6, 22.4, 11.4), 'steel')
    for sy in (-15.0, 15.0):
        _rail(L, [(-10.6, sy - 1.3), (10.6, sy - 1.3)], 46.5, 1.1, 'white', 2.0, 0.05)
    legs = L.mesh('PORT_crane_legs')
    # BOOM (boom-local: origin at the hinge; tip toward -y)
    B = Geo()
    for sx in (-4.5, 4.5):
        B.blh((sx - 1.0, -40.0, 0.0), (sx + 1.0, -1.0, 3.5), 'cranewhite')
        B.add([(sx - 1.0, -40.0, 0.0), (sx + 1.0, -40.0, 0.0), (sx + 1.0, -40.0, 3.5), (sx - 1.0, -40.0, 3.5),
               (sx - 1.0, -59.0, 0.6), (sx + 1.0, -59.0, 0.6), (sx + 1.0, -59.0, 3.0), (sx - 1.0, -59.0, 3.0)],
              [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], 'cranewhite')
        B.blh((sx - 0.25, -59.0, -0.25), (sx + 0.25, -1.0, 0.02), 'rail')
        B.beam((sx, -28.0, 3.5), (sx * 0.4, 23.0, 31.0), 0.5, 0.5, 'cranered')
        B.beam((sx, -55.0, 3.1), (sx * 0.4, 23.0, 31.0), 0.45, 0.45, 'cranered')
        so = 1 if sx > 0 else -1
        _rail(B, [(sx + 0.85 * so, -57.0), (sx + 0.85 * so, -1.2)], 3.5, 1.1, 'white', 3.0, 0.05)
        B.cyl((sx - 1.0, -0.4, 0.9), (sx + 1.0, -0.4, 0.9), 0.75, n=12, mat='steeldk')
    for yy in (-6.0, -16.0, -26.0, -36.0, -46.0, -56.0):
        B.blh((-3.6, yy - 0.4, 2.6), (3.6, yy + 0.4, 3.4), 'cranewhite')
    B.blh((-5.6, -60.2, 0.6), (5.6, -58.8, 3.4), 'cranered')
    B.sphere((-5.0, -59.6, 3.8), 0.3, 'redlight', 8, 5); B.sphere((5.0, -59.6, 3.8), 0.3, 'redlight', 8, 5)
    for yy in (-12.0, -27.0, -42.0, -55.0):
        for sx in (-5.6, 5.6):
            B.blh((sx - 0.25, yy - 0.3, -0.6), (sx + 0.25, yy + 0.3, 0.0), 'steeldk'); B.blh((sx - 0.2, yy - 0.25, -0.75), (sx + 0.2, yy + 0.25, -0.6), 'lampglow')
    boom = B.mesh('PORT_crane_boom')
    # TROLLEY (trolley-local: origin at its centre on the boom rails)
    T = Geo()
    T.blh((-3.3, -4.0, -0.35), (3.3, 4.0, 0.4), 'yellow'); T.blh((-2.4, -3.2, 0.4), (2.4, 3.2, 2.2), 'steel')
    for sx in (-3.0, 3.0):
        for sy in (-3.2, 3.2):
            T.cyl((sx - 0.2, sy, 0.05), (sx + 0.2, sy, 0.05), 0.42, n=10, mat='steeldk')
    T.cyl((-2.0, 0.0, 1.3), (2.0, 0.0, 1.3), 0.9, n=14, mat='steeldk')
    for sx in (-1.2, 1.2):
        T.blh((sx - 0.3, -1.0, -0.55), (sx + 0.3, 1.0, -0.35), 'steeldk')
    trolley = T.mesh('PORT_crane_trolley')
    # CAB (cab-local: origin at its hanger top)
    Cb = Geo()
    Cb.blh((-0.3, -0.3, -0.7), (0.3, 0.3, -0.03), 'steeldk')
    Cb.blh((-1.7, -2.3, -3.8), (1.7, 2.3, -0.7), 'white'); Cb.blh((-1.85, -2.45, -0.9), (1.85, 2.45, -0.6), 'steeldk')
    Cb.blh((-1.5, -2.4, -3.3), (1.5, -2.25, -1.2), 'glass'); Cb.blh((-1.78, -2.0, -3.1), (-1.68, 1.6, -1.4), 'glass'); Cb.blh((1.68, -2.0, -3.1), (1.78, 1.6, -1.4), 'glass')
    Cb.blh((-1.3, -2.0, -3.9), (1.3, 0.5, -3.8), 'glass')
    cab = Cb.mesh('PORT_crane_cab')
    # SPREADER (spreader-local: origin at the top of its headblock, where the four ropes end; the frame is 2.5 m deep)
    S = Geo(); zsp = -2.2
    S.blh((-1.4, -2.0, zsp + 1.2), (1.4, 2.0, zsp + 2.2), 'yellow')
    S.blh((-6.1, -1.22, zsp), (6.1, 1.22, zsp + 0.9), 'yellow'); S.blh((-0.8, -1.0, zsp + 0.9), (0.8, 1.0, zsp + 1.2), 'steeldk')
    for sx in (-6.0, 6.0):
        S.blh((sx - 0.25, -1.3, zsp - 0.3), (sx + 0.25, 1.3, zsp + 0.05), 'hazard')
    spreader = S.mesh('PORT_crane_spreader')
    # ROPES (ropes-local: unit length from z 0 down to z -1; a driver scales z to reach the spreader, see build_cranes)
    Rp = Geo()
    for sx in (-0.9, 0.9):
        for sy in (-1.6, 1.6):
            Rp.cyl((sx, sy * 0.7, 0.0), (sx, sy, -1.0), 0.05, n=5, mat='steeldk', caps=(False, False))
    ropes = Rp.mesh('PORT_crane_ropes')
    return dict(legs=legs, boom=boom, trolley=trolley, cab=cab, spreader=spreader, ropes=ropes)


def build_cranes(coll, M):
    out = []; parts = {}
    for i, cx in enumerate(CRANE_X):
        tag = 'ABCD'[i]; base = (cx, (RAIL_W + RAIL_L) / 2.0, QZ)
        lg = obj('PORT_crane%s_legs' % tag, M['legs'], coll, base, bevel=0.06, props={'qa_kind': 'crane', 'cid': float(i)})
        bm = obj('PORT_crane%s_boom' % tag, M['boom'], coll, HINGE, parent=lg, bevel=0.06, props={'qa_kind': 'crane', 'cid': float(i)})
        yt = (-14.0, -27.0, -40.0, -21.0)[i]
        tr = obj('PORT_crane%s_trolley' % tag, M['trolley'], coll, (0.0, yt, 0.0), parent=bm, bevel=0.04, props={'qa_kind': 'crane'})
        cb = obj('PORT_crane%s_cab' % tag, M['cab'], coll, (2.0, -3.6, -0.35), parent=tr, bevel=0.03, props={'qa_kind': 'crane'})
        sp = obj('PORT_crane%s_spreader' % tag, M['spreader'], coll, (0.0, 0.0, SPREADER_Z), parent=tr, bevel=0.03, props={'qa_kind': 'crane'})
        rp = obj('PORT_crane%s_ropes' % tag, M['ropes'], coll, (0.0, 0.0, ROPE_TOP), parent=tr, props={'qa_kind': 'crane'})
        # hoist: animate the spreader's local z (trolley space); the ropes stretch from the trolley to the headblock by themselves
        fc = rp.driver_add('scale', 2); dv = fc.driver; dv.type = 'SCRIPTED'
        v = dv.variables.new(); v.name = 'sz'; v.type = 'SINGLE_PROP'; v.targets[0].id = sp; v.targets[0].data_path = 'location[2]'
        dv.expression = 'max(0.05, %.3f - sz)' % ROPE_TOP
        d = dict(legs=lg, boom=bm, trolley=tr, cab=cb, spreader=sp, ropes=rp)
        out.append(d); parts[tag] = d
    return out


# ------------------------------------------------------------------------------------------------------------------------------ dock rail cranes (portal jib cranes)
def railcrane_mesh():
    g = Geo(); h = Geo()
    for sx in (-4.0, 4.0):
        for sy in (-4.0, 4.0):
            g.blh((sx - 0.45, sy - 0.45, 1.3), (sx + 0.45, sy + 0.45, 9.6), 'teal')
            g.blh((sx - 0.6, sy - 1.6, 0.62), (sx + 0.6, sy + 1.6, 1.3), 'yellow')
            for wy in (-1.0, 1.0):
                g.cyl((sx - 0.35, sy + wy, 0.58), (sx + 0.35, sy + wy, 0.58), 0.4, n=10, mat='steeldk')
        g.beam((sx, -4.5, 9.6), (sx, 4.5, 9.6), 1.0, 1.2, 'teal'); g.beam((sx, -4.0, 2.4), (sx, 4.0, 8.4), 0.4, 0.4, 'teal')
    for sy in (-4.0, 4.0):
        g.beam((-4.5, sy, 9.6), (4.5, sy, 9.6), 1.0, 1.2, 'teal')
    g.cyl((0, 0, 10.2), (0, 0, 10.8), 3.0, n=20, mat='steeldk')
    portal = g.mesh('PORT_railcrane_portal'); g = h
    g.blh((-3.2, -2.5, 10.85), (3.2, 5.5, 15.4), 'teal'); g.blh((-3.4, -2.7, 15.4), (3.4, 5.7, 15.7), 'steeldk')
    g.blh((-3.21, 0.0, 12.6), (-3.11, 4.0, 14.2), 'glass'); g.blh((3.11, 0.0, 12.6), (3.21, 4.0, 14.2), 'glass')
    g.blh((-1.6, -4.2, 11.4), (1.6, -2.5, 14.6), 'white'); g.blh((-1.4, -4.3, 12.6), (1.4, -4.2, 14.2), 'glass')
    g.blh((-2.4, 5.5, 11.2), (2.4, 8.0, 14.4), 'steeldk')
    tip = Vector((0.0, -30.0, 34.0)); root = Vector((0.0, -1.0, 15.0))
    for sx in (-0.9, 0.9):
        g.beam((sx, root.y, root.z), (sx * 0.4, tip.y, tip.z), 0.5, 0.9, 'yellow')
    k = 0
    while k < 12:
        a = root.lerp(tip, k / 12); b = root.lerp(tip, (k + 1) / 12)
        g.beam((-0.8 + 0.5 * k / 12, a.y, a.z), (0.8 - 0.5 * (k + 1) / 12, b.y, b.z), 0.12, 0.12, 'yellow'); k += 1
    g.beam((0.0, 2.0, 15.6), (0.0, -2.0, 25.0), 0.5, 0.5, 'teal'); g.beam((0.0, -2.0, 25.0), tip, 0.18, 0.18, 'steeldk')
    g.beam((0.0, -2.0, 25.0), (0.0, 7.5, 14.6), 0.18, 0.18, 'steeldk')
    g.cyl((0.0, tip.y, tip.z - 0.3), (0.0, tip.y, 14.0), 0.04, n=5, mat='steeldk', caps=(False, False))
    g.blh((-0.5, tip.y - 0.4, 12.5), (0.5, tip.y + 0.4, 14.0), 'yellow'); g.blh((-0.12, tip.y - 0.12, 11.8), (0.12, tip.y + 0.12, 12.5), 'steeldk')
    g.sphere((0.0, tip.y, tip.z + 0.5), 0.25, 'redlight', 8, 5)
    return portal, g.mesh('PORT_railcrane_slew')


def build_railcranes(coll):
    mp, ms = railcrane_mesh(); out = []; f = Geo()
    for name, x, y, yaw in (('PORT_railcraneW', DX0 - 9.0, 545.0, 0.0), ('PORT_railcraneE', DX1 + 9.0, 470.0, -60.0)):
        o = obj(name, mp, coll, (x, y, QZ), bevel=0.04, props={'qa_kind': 'crane'})
        s2 = obj(name + '_slew', ms, coll, (0, 0, 0), (0, 0, math.radians(yaw)), parent=o, bevel=0.04, props={'qa_kind': 'crane'})
        out += [o, s2]
        for rx in (x - 4.0, x + 4.0):
            f.blh((rx - 0.08, 410.0, 3.95), (rx + 0.08, 598.0, 4.17), 'rail')
            for ye in (410.0, 598.0):
                f.blh((rx - 0.6, ye - 0.6, 3.95), (rx + 0.6, ye + 0.6, 4.9), 'hazard')
    rails = gobj('PORT_dockrails', f, coll, props={'qa_kind': 'prop'})
    return out, rails




# ------------------------------------------------------------------------------------------------------------------------------ containers, carriers, yard
CPAL = [('#d23a2e', 0), ('#f07a2a', 4), ('#f2b705', 7), ('#3fa34d', 2), ('#2a8f8a', 1), ('#2f5fd0', 3), ('#24407a', 5),
        ('#ece8df', 6), ('#8e2f3a', 0), ('#8d93a5', 7), ('#4fb3e8', 3), ('#c23b7a', 6), ('#e85a2a', 1), ('#5c6fd8', 5)]
CW, CH, CL40, CL20 = 2.44, 2.59, 12.19, 6.06
YARD_X = ((-392.0, 9), (-266.8, 9), (-141.6, 8))
YARD_Y = [452.0 + k * 37.8 for k in range(5)]
ROW_P, SLOT_P = 4.3, 12.8


def container_meshes():
    out = {}
    for key, L in (('cont12', CL40), ('cont6', CL20)):
        g = Geo(); g.box((0.0, 0.0, CH * 0.5), (L, CW, CH), key)
        me = g.mesh('PORT_' + key); bevel_mesh(me, 0.045)
        out[key] = me
    return out


def _cprops(o, R, oidk=None):
    c, brand = CPAL[R.randrange(len(CPAL))]
    o['ccol'] = LK.srgb(c)[:3]
    on = 1.0 if R.random() < 0.72 else 0.0
    dark = c in ('#ece8df', '#f2b705', '#4fb3e8')
    o['logo'] = (float(brand), 1.0 if dark else 0.0, on)
    o['qa_kind'] = 'container'
    # far id shared by one yard block (see _oid_lod); a container on its own (on a carrier or truck) keeps a unique one
    o['oidk'] = oidk if oidk is not None else (zlib.crc32(o.name.encode()) % 100003) / 100003.0


def build_containers(coll, R):
    M = container_meshes(); conts = []; slots = []
    n = 0
    for bx, (x0, ns) in enumerate(YARD_X):
        for by, y0 in enumerate(YARD_Y):
            rk = ((bx * 5 + by) * 0.6180339887 + 0.137) % 1.0      # far id shared by the whole block (see _oid_lod)
            for r in range(6):
                y = y0 + r * ROW_P + CW * 0.5
                for s in range(ns):
                    xc = x0 + s * SLOT_P + CL40 * 0.5
                    u = R.random()
                    h = 0 if u < 0.13 else (1 if u < 0.33 else (2 if u < 0.62 else (3 if u < 0.92 else 4)))
                    slots.append((xc, y, h))
                    for k in range(h):
                        z = QZ + 0.03 + k * (CH + 0.025)
                        if R.random() < 0.16:
                            for e in (-1, 1):
                                o = obj('PORT_cont_%04d' % n, M['cont6'], coll, (xc + e * (CL20 * 0.5 + 0.035), y, z), (0, 0, math.pi if R.random() < 0.5 else 0.0)); n += 1
                                _cprops(o, R, rk); conts.append(o)
                        else:
                            o = obj('PORT_cont_%04d' % n, M['cont12'], coll, (xc, y, z), (0, 0, math.pi if R.random() < 0.5 else 0.0)); n += 1
                            _cprops(o, R, rk); conts.append(o)
    return conts, slots, M


def straddle_mesh():
    g = Geo()
    for sy in (-2.15, 2.15):
        g.blh((-4.6, sy - 0.4, 0.95), (4.6, sy + 0.4, 1.75), 'yellow')
        for wx in (-3.9, -1.3, 1.3, 3.9):
            g.cyl((wx, sy - 0.32, 0.62), (wx, sy + 0.32, 0.62), 0.6, n=12, mat='rubber')
        for lx in (-3.8, 3.8):
            g.blh((lx - 0.36, sy - 0.32, 1.75), (lx + 0.36, sy + 0.32, 12.7), 'yellow')
            g.blh((lx - 0.3, sy - 0.33, 4.0), (lx + 0.3, sy + 0.33, 4.6), 'hazard')
        g.blh((-4.4, sy - 0.42, 12.6), (4.4, sy + 0.42, 13.7), 'yellow')
        g.beam((-3.6, sy, 2.0), (3.6, sy, 12.4), 0.25, 0.25, 'steel')
    for lx in (-3.8, 3.8):
        g.blh((lx - 0.5, -2.6, 13.1), (lx + 0.5, 2.6, 14.1), 'yellow')
    g.blh((-4.2, -2.5, 14.1), (-0.6, 2.5, 15.9), 'white'); g.blh((-3.8, -1.6, 15.9), (-2.4, 1.6, 16.5), 'steeldk')
    g.cyl((-1.4, 1.5, 15.9), (-1.4, 1.5, 17.3), 0.18, n=8, mat='steeldk')
    g.blh((2.4, 0.6, 13.4), (4.5, 2.7, 16.0), 'white'); g.blh((4.5, 0.8, 14.2), (4.6, 2.5, 15.6), 'glass'); g.blh((2.6, 2.7, 14.3), (4.3, 2.8, 15.6), 'glass')
    g.blh((-4.0, -1.9, 12.0), (4.0, -1.5, 12.55), 'steeldk'); g.blh((-4.0, 1.5, 12.0), (4.0, 1.9, 12.55), 'steeldk')
    g.sphere((0.0, 0.0, 16.0), 0.22, 'orange', 8, 5)
    return g.mesh('PORT_straddle')


def truck_mesh():
    g = Geo()
    g.blh((-7.2, -1.15, 0.9), (7.2, 1.15, 1.35), 'steeldk')
    for wx in (-6.0, -4.8, 4.5):
        for sy in (-0.95, 0.95):
            g.cyl((wx, sy - 0.3, 0.52), (wx, sy + 0.3, 0.52), 0.5, n=10, mat='rubber')
    g.blh((4.0, -1.25, 0.8), (7.6, 1.25, 1.5), 'steel')
    g.blh((5.6, -1.25, 1.5), (7.8, 1.25, 3.7), 'orange'); g.blh((7.8, -1.0, 2.5), (7.9, 1.0, 3.5), 'glass')
    g.blh((5.7, -1.26, 2.6), (7.2, -1.25, 3.5), 'glass'); g.blh((5.7, 1.25, 2.6), (7.2, 1.26, 3.5), 'glass')
    g.cyl((5.5, -1.0, 1.5), (5.5, -1.0, 4.4), 0.1, n=6, mat='steeldk')
    return g.mesh('PORT_truck')


def mast_mesh():
    g = Geo()
    g.blh((-0.9, -0.9, 3.9), (0.9, 0.9, 4.6), 'concrete')
    g.cyl((0, 0, 4.6), (0, 0, 38.0), 0.55, 0.3, n=10, mat='steel')
    g.cyl((0, 0, 38.0), (0, 0, 38.3), 2.4, n=16, mat='steeldk')
    for k in range(8):
        a = k / 8 * math.tau; c, s = math.cos(a), math.sin(a)
        g.blh((c * 2.0 - 0.45, s * 2.0 - 0.45, 38.3), (c * 2.0 + 0.45, s * 2.0 + 0.45, 39.0), 'steeldk')
        g.blh((c * 2.0 - 0.38, s * 2.0 - 0.38, 38.22), (c * 2.0 + 0.38, s * 2.0 + 0.38, 38.3), 'lampglow')
    _rail(g, [(math.cos(k / 12 * math.tau) * 2.35, math.sin(k / 12 * math.tau) * 2.35) for k in range(13)], 38.3, 1.0, 'yellow', 1.2, 0.04)
    for k in range(int(33 / 0.4)):
        z = 5.0 + k * 0.4; g.blh((0.5, -0.22, z), (0.62, 0.22, z + 0.05), 'steel')
    return g.mesh('PORT_mast')


def build_yard(coll, R, conts, slots, CM):
    out = {'straddles': [], 'trucks': [], 'masts': []}
    sm = straddle_mesh(); n = len(conts)
    # carriers driving in the lanes, and two straddling rows where the stack is low
    lane_x = [YARD_X[0][0] + YARD_X[0][1] * SLOT_P + 5.0, YARD_X[1][0] + YARD_X[1][1] * SLOT_P + 5.0]
    picks = [(lane_x[0], 470.0, 90.0), (lane_x[0], 556.0, 90.0), (lane_x[1], 512.0, 90.0), (lane_x[1], 590.0, 90.0),
             (-330.0, YARD_Y[1] + 6 * ROW_P + 6.0, 0.0), (-150.0, YARD_Y[3] + 6 * ROW_P + 6.0, 0.0)]
    low = [s for s in slots if s[2] <= 1 and -380 < s[0] < -60]
    R.shuffle(low)
    for s in low[:3]: picks.append((s[0], s[1], 0.0, s[2]))
    for i, p in enumerate(picks):
        x, y, yaw = p[0], p[1], p[2]
        o = obj('PORT_straddle_%d' % i, sm, coll, (x, y, QZ + 0.02), (0, 0, math.radians(yaw)), bevel=0.04, props={'qa_kind': 'prop'})
        out['straddles'].append(o)
        if i % 2 == 0:
            hz = QZ + 0.03 + (p[3] if len(p) > 3 else 0) * (CH + 0.025) + 1.2 + 4.0
            hz = min(hz, QZ + 12.0 - CH - 0.1)
            c = obj('PORT_cont_%04d' % n, CM['cont12'], coll, (0.0, 0.0, hz - QZ - 0.02), parent=o); n += 1
            _cprops(c, R); conts.append(c)
    tm = truck_mesh()
    for i, (x, y) in enumerate([(-372.0, 417.0), (-298.0, 424.0), (-210.0, 410.0), (-125.0, 417.0), (-60.0, 431.0), (-250.0, 438.5)]):
        o = obj('PORT_truck_%d' % i, tm, coll, (x, y, QZ + 0.02), bevel=0.03, props={'qa_kind': 'prop'}); out['trucks'].append(o)
        if i % 3 != 2:
            c = obj('PORT_cont_%04d' % n, CM['cont12'], coll, (-0.9, 0.0, 1.38), parent=o); n += 1
            _cprops(c, R); conts.append(c)
    mm = mast_mesh()
    for i, (x, y) in enumerate([(lane_x[0], 445.0), (lane_x[1], 445.0), (lane_x[0], 640.0), (lane_x[1], 640.0), (-30.0, 445.0), (-30.0, 600.0), (-398.0, 640.0)]):
        out['masts'].append(obj('PORT_mast_%d' % i, mm, coll, (x, y, 0.0), bevel=0.03, props={'qa_kind': 'prop'}))
    return out




# ------------------------------------------------------------------------------------------------------------------------------ buildings
def sawroof(g, hx, y0, y1, hz, T=3.4, P=8.0):
    """North-light sawtooth: each tooth's glazing faces north (+y, toward the town); the sea side sees the metal slopes."""
    n = max(1, round((y1 - y0) / P)); P = (y1 - y0) / n
    for k in range(n):
        a = y0 + k * P; b = a + P
        V = [(-hx, a, hz), (hx, a, hz), (-hx, b, hz), (hx, b, hz), (-hx, b, hz + T), (hx, b, hz + T)]
        g.add(V, [(3, 2, 4, 5)], 'glass'); g.add(V, [(0, 1, 5, 4)], 'mroof'); g.add(V, [(0, 2, 3, 1), (0, 4, 2), (1, 3, 5)], 'warehouse')
        g.blh((-hx - 0.2, b - 0.25, hz + T - 0.05), (hx + 0.2, b + 0.25, hz + T + 0.25), 'white')
        for xv in range(int(-hx) + 8, int(hx) - 4, 16):
            g.cyl((xv, a + P * 0.55, hz + T * 0.5), (xv, a + P * 0.55, hz + T * 0.5 + 1.6), 0.45, n=8, mat='steel')
            g.cyl((xv, a + P * 0.55, hz + T * 0.5 + 1.6), (xv, a + P * 0.55, hz + T * 0.5 + 1.9), 0.75, n=8, mat='steeldk')


def warehouse(coll, name, x0, x1, y0, y1, hz, col, wn, roof='saw'):
    hx = (x1 - x0) * 0.5; cy = (y0 + y1) * 0.5; hy = (y1 - y0) * 0.5
    g = Geo(); g.blh((-hx, -hy, -0.6), (hx, hy, hz), 'warehouse')
    if roof == 'saw': sawroof(g, hx, -hy, hy, hz)
    else:
        V = [(-hx - 0.4, -hy - 0.4, hz), (hx + 0.4, -hy - 0.4, hz), (hx + 0.4, hy + 0.4, hz), (-hx - 0.4, hy + 0.4, hz), (-hx - 0.4, 0, hz + hy * 0.35), (hx + 0.4, 0, hz + hy * 0.35)]
        g.add(V, [(0, 1, 5, 4), (2, 3, 4, 5)], 'mroof'); g.add(V, [(0, 4, 3), (1, 2, 5), (0, 3, 2, 1)], 'warehouse')
    for sx in (-1, 1):
        g.blh((sx * hx - 0.3 * (sx > 0) - 0.0, -hy - 0.5, hz - 0.5), (sx * hx + 0.3 * (sx < 0), -hy, hz + 0.1), 'steeldk') if False else None
        for xp in range(int(-hx) + 4, int(hx) - 2, 24):
            g.blh((xp - 0.15, sx * (hy + 0.2) - 0.15, 0.0), (xp + 0.15, sx * (hy + 0.2) + 0.15, hz + 0.2), 'steel')
    g.blh((-hx - 0.3, -hy - 0.6, hz - 0.4), (hx + 0.3, -hy, hz + 0.15), 'steeldk'); g.blh((-hx - 0.3, hy, hz - 0.4), (hx + 0.3, hy + 0.6, hz + 0.15), 'steeldk')
    dsp = 16.0; xd = -hx + 4.0
    while xd < hx - 4.0:
        xc = round((xd + 8.0) / dsp) * dsp - 8.0
        if -hx + 4.0 < xc < hx - 4.0: g.blh((xc - 4.2, -hy - 1.6, 6.9), (xc + 4.2, -hy, 7.2), 'steeldk')
        xd += dsp
    o = gobj(name, g, coll, bevel=0.05, loc=((x0 + x1) * 0.5, cy, QZ), props={'qa_kind': 'building', 'hx': hx, 'hz': hz, 'wcol': LK.srgb(col)[:3], 'wn': float(wn)})
    return o


def office(coll, name, x0, x1, y0, y1, h, col, sign=None, tower=False):
    hx = (x1 - x0) * 0.5; hy = (y1 - y0) * 0.5
    g = Geo(); g.blh((-hx, -hy, -0.6), (hx, hy, h), 'office')
    g.blh((-hx - 0.25, -hy - 0.25, h), (hx + 0.25, hy + 0.25, h + 0.9), 'white')
    g.blh((-hx * 0.4, -hy * 0.4, h + 0.9), (hx * 0.1, hy * 0.3, h + 3.2), 'steel')
    for k in range(3):
        g.cyl((hx * 0.3 + k * 1.8, hy * 0.2, h + 0.9), (hx * 0.3 + k * 1.8, hy * 0.2, h + 2.0), 0.6, n=10, mat='steeldk')
    g.blh((-hx * 0.5, -hy - 2.2, 3.2), (hx * 0.5, -hy, 3.5), 'steeldk')
    if tower:
        g.blh((hx - 7.0, -hy, h), (hx, -hy + 7.0, h + 8.0), 'office'); g.blh((hx - 7.6, -hy - 0.6, h + 8.0), (hx + 0.6, -hy + 7.6, h + 11.0), 'glass')
        g.blh((hx - 8.0, -hy - 1.0, h + 11.0), (hx + 1.0, -hy + 8.0, h + 11.6), 'white')
        g.cyl((hx - 3.5, -hy + 3.5, h + 11.6), (hx - 3.5, -hy + 3.5, h + 18.0), 0.12, n=6, mat='steeldk')
    o = gobj(name, g, coll, bevel=0.05, loc=((x0 + x1) * 0.5, (y0 + y1) * 0.5, QZ), props={'qa_kind': 'building', 'wcol': LK.srgb(col)[:3]})
    if sign is not None:
        s = Geo(); w = min(hx * 1.6, 26.0)
        s.blh((-w * 0.5, -hy - 0.45, h - 3.2), (w * 0.5, -hy - 0.15, h - 0.6), 'sign')
        so = gobj(name + '_sign', s, coll, loc=o.location, props=dict(sign_props(w, 2.6, 0.62), qa_kind='building', row=float(sign)))
    return o


def silos(coll):
    g = Geo(); out = []
    for r in range(2):
        for k in range(5):
            x = 14.0 + k * 11.3; y = 478.0 + r * 11.3
            g.cyl((x, y, 3.4), (x, y, 42.0), 5.5, n=24, mat='silo')
            g.cyl((x, y, 42.0), (x, y, 43.2), 5.7, 5.0, n=24, mat='silo')
            for zr in (12.0, 22.0, 32.0):
                g.cyl((x, y, zr), (x, y, zr + 0.45), 5.62, n=24, mat='silo', caps=(False, False))
    g.blh((8.0, 472.0, 43.2), (66.0, 495.5, 47.6), 'white'); g.blh((7.6, 471.6, 47.6), (66.4, 495.9, 48.0), 'steeldk')
    g.blh((-14.0, 470.0, 3.4), (2.0, 486.0, 56.0), 'silo'); g.blh((-14.4, 469.6, 56.0), (2.4, 486.4, 57.0), 'steeldk')
    g.blh((-14.05, 472.0, 50.0), (-13.95, 484.0, 53.5), 'glass')
    g.beam((-6.0, 470.0, 50.0), (-6.0, 414.0, 24.0), 3.0, 3.6, 'white')
    g.blh((-9.0, 405.0, 3.98), (-3.0, 416.0, 26.5), 'steel'); g.blh((-10.0, 404.0, 26.5), (-2.0, 417.0, 29.0), 'white')
    g.beam((-6.0, 410.0, 25.0), (-6.0, 392.0, 15.0), 1.4, 1.6, 'steel'); g.cyl((-6.0, 392.0, 15.0), (-6.0, 392.0, 9.0), 0.6, n=10, mat='steeldk')
    for zz in range(6, 26, 4):
        g.blh((-9.3, 404.7, zz), (-2.7, 416.3, zz + 0.25), 'steeldk')
    o = gobj('PORT_silos', g, coll, bevel=0.05, props={'qa_kind': 'building'})
    s = Geo(); s.blh((-12.5, 469.4, 40.0), (0.5, 469.8, 47.0), 'sign')
    so = gobj('PORT_silos_sign', s, coll, props=dict(sign_props(13.0, 7.0, 0.5, '#d23a2e'), qa_kind='building', row=14.0))
    return [o, so]


def market(coll):
    g = Geo(); x0, x1, y0, y1 = 132.0, 248.0, 428.0, 466.0
    hx = (x1 - x0) / 2; hy = (y1 - y0) / 2
    g.blh((-hx, -hy, -0.6), (hx, hy, 7.0), 'warehouse')
    n = 6
    for k in range(n):
        a = -hx + k * (2 * hx / n); b = a + 2 * hx / n
        V = [(a, -hy - 1.0, 7.0), (b, -hy - 1.0, 7.0), (b, hy + 1.0, 7.0), (a, hy + 1.0, 7.0), ((a + b) / 2, -hy - 1.0, 11.5), ((a + b) / 2, hy + 1.0, 11.5)]
        g.add(V, [(0, 4, 5, 3), (1, 2, 5, 4)], 'roof'); g.add(V, [(0, 1, 4), (2, 3, 5), (0, 3, 2, 1)], 'warehouse')
    g.blh((-hx * 0.9, -hy - 4.0, 4.4), (hx * 0.9, -hy, 4.7), 'teal')
    for xb in (-12.0, 12.0): g.blh((xb - 0.15, -hy - 1.23, 9.5), (xb + 0.15, -hy - 0.9, 9.9), 'steeldk')
    for xp in range(int(-hx * 0.9), int(hx * 0.9) + 1, 8):
        g.blh((xp - 0.12, -hy - 3.9, -0.4), (xp + 0.12, -hy - 3.6, 4.4), 'steel')
    o = gobj('PORT_market', g, coll, bevel=0.05, loc=((x0 + x1) / 2, (y0 + y1) / 2, QZ), props={'qa_kind': 'building', 'hx': hx, 'hz': 7.0, 'wcol': LK.srgb('#2a8f8a')[:3], 'wn': -3.0})
    s = Geo(); s.blh((-16.0, -hy - 1.55, 8.6), (16.0, -hy - 1.25, 10.9), 'sign')
    so = gobj('PORT_market_sign', s, coll, loc=o.location, props=dict(sign_props(32.0, 2.3, 0.72, '#c8553d'), qa_kind='building', row=7.0))
    return [o, so]


def build_buildings(coll):
    B = []
    W = [('PORT_wh1', 312, 408, 432, 478, 12.0, '#2a8f8a', 0), ('PORT_wh2', 422, 520, 432, 478, 13.0, '#d9cdb0', 1),
         ('PORT_wh3', 312, 448, 498, 558, 14.0, '#5c78b8', 2), ('PORT_wh4', 466, 600, 498, 558, 12.0, '#c8553d', 3),
         ('PORT_wh5', -692, -604, 448, 520, 13.0, '#e2d3b0', 0), ('PORT_wh6', -692, -560, 540, 626, 15.0, '#8e9bb0', 1),
         ('PORT_wh7', 330, 440, 580, 640, 11.0, '#e8b04a', 2)]
    for n, x0, x1, y0, y1, h, c, wn in W: B.append(warehouse(coll, n, x0, x1, y0, y1, h, c, wn))
    B.append(warehouse(coll, 'PORT_pumphouse', -478.0, -442.0, 612.0, 634.0, 9.0, '#c8553d', 2, roof='gable'))
    O = [('PORT_office1', 470, 530, 580, 640, 18.0, '#f1ead8', None, False), ('PORT_office2', 545, 600, 586, 640, 24.0, '#e9d9c4', None, False),
         ('PORT_harbormaster', -600, -562, 432, 470, 14.0, '#f1ead8', 8, True), ('PORT_iceplant', 262, 296, 430, 470, 20.0, '#eef0f2', 9, False),
         ('PORT_office3', -540, -500, 640, 646, 10.0, '#f1ead8', None, False)]
    for n, x0, x1, y0, y1, h, c, sg, tw in O: B.append(office(coll, n, x0, x1, y0, y1, h, c, sg, tw))
    R = random.Random(21); x = -700.0
    while x < 600.0:
        w = R.uniform(16.0, 30.0); h = R.choice((9.0, 12.0, 15.0, 18.0))
        if not (-470 < x < -380):
            B.append(office(coll, 'PORT_block_%d' % int(x + 1000), x, x + w, 675.0, 675.0 + R.uniform(12.0, 18.0), h, R.choice(('#f1ead8', '#f3e3c6', '#e9d6cf', '#dfe6e8', '#f4ecd2')), None, False))
        x += w + R.uniform(6.0, 14.0)
    B += silos(coll); B += market(coll)
    return B


# ------------------------------------------------------------------------------------------------------------------------------ hillside town and trees
HOUSE_V = [(8.0, 7.0, 6.0, 'gable'), (10.0, 8.0, 9.0, 'hip'), (7.0, 7.0, 6.2, 'flat'), (12.0, 8.0, 12.0, 'gable'), (6.0, 6.0, 3.6, 'gable'), (9.0, 9.0, 9.0, 'hip')]


def house_mesh(i):
    w, d, h, kind = HOUSE_V[i]; g = Geo(); hx, hy = w * 0.5, d * 0.5
    g.blh((-hx, -hy, -4.0), (hx, hy, h), 'house')
    if kind == 'gable':
        r = d * 0.36; o = 0.35
        V = [(-hx - o, -hy - o, h), (hx + o, -hy - o, h), (hx + o, hy + o, h), (-hx - o, hy + o, h), (-hx - o, 0, h + r), (hx + o, 0, h + r)]
        g.add(V, [(0, 1, 5, 4), (2, 3, 4, 5), (0, 3, 2, 1)], 'roof'); g.add([(-hx, -hy, h), (-hx, hy, h), (-hx, 0, h + r * 0.92), (hx, -hy, h), (hx, hy, h), (hx, 0, h + r * 0.92)], [(0, 2, 1), (3, 4, 5)], 'house')
    elif kind == 'hip':
        r = min(w, d) * 0.32; o = 0.35; k = (w - d) * 0.5 if w > d else 0.0
        V = [(-hx - o, -hy - o, h), (hx + o, -hy - o, h), (hx + o, hy + o, h), (-hx - o, hy + o, h), (-k, 0, h + r), (k + 1e-3, 0, h + r)]
        g.add(V, [(0, 1, 5, 4), (1, 2, 5), (2, 3, 4, 5), (3, 0, 4), (0, 3, 2, 1)], 'roof')
    else:
        g.blh((-hx - 0.1, -hy - 0.1, h), (hx + 0.1, hy + 0.1, h + 0.8), 'house'); g.blh((-hx + 0.4, -hy + 0.4, h + 0.79), (hx - 0.4, hy - 0.4, h + 0.82), 'roof')
        g.blh((hx * 0.2, -hy * 0.3, h + 0.8), (hx * 0.8, hy * 0.4, h + 2.6), 'house')
    g.blh((hx * 0.35, hy * 0.1, h - 0.5), (hx * 0.35 + 0.8, hy * 0.1 + 0.8, h + (d * 0.36 if kind != 'flat' else 1.2) + 1.2), 'house')
    if i % 2 == 0: g.blh((-hx * 0.6, -hy - 1.1, 2.9), (hx * 0.1, -hy, 3.1), 'house'); _rail(g, [(-hx * 0.6, -hy - 1.05), (hx * 0.1, -hy - 1.05)], 3.1, 0.9, 'steeldk', 0.6, 0.03)
    me = g.mesh('PORT_house%d' % i); return me


def tree_meshes():
    out = []
    for k, (r, sz, trunk) in enumerate(((3.2, 1.0, 2.6), (4.2, 0.9, 3.0), (1.3, 3.6, 1.2), (6.5, 0.8, 3.5))):
        g = Geo(); g.cyl((0, 0, -1.0), (0, 0, trunk + r * 0.3), max(0.2, r * 0.09), n=6, mat='trunk')
        nu, nv = (9, 6) if k in (0, 2) else (8, 5)
        g.sphere((0, 0, trunk + r * sz), r, 'tree', nu, nv, sz)
        if k in (1, 3): g.sphere((r * 0.55, r * 0.2, trunk + r * sz * 1.25), r * 0.6, 'tree', 7, 4, sz); g.sphere((-r * 0.5, -r * 0.25, trunk + r * sz * 0.95), r * 0.55, 'tree', 7, 4, sz)
        out.append(g.mesh('PORT_tree%d' % k))
    return out


def _street(h): return abs(((h - 6.0) / 14.0) % 1.0 - 0.5) < 0.1


def contour_y(x, H, ya=690.0, yb=1185.0):
    """y where the terrain at x reaches height H (the town slope rises with y), or None."""
    if terrain_h(x, ya)[0] > H or terrain_h(x, yb)[0] < H: return None
    for _ in range(22):
        ym = (ya + yb) * 0.5
        if terrain_h(x, ym)[0] > H: yb = ym
        else: ya = ym
    return (ya + yb) * 0.5


def _sat(A, B):
    """Do two convex 2D polygons overlap (separating axis test)?"""
    for P in (A, B):
        n = len(P)
        for i in range(n):
            ex, ey = P[(i + 1) % n][0] - P[i][0], P[(i + 1) % n][1] - P[i][1]; ax, ay = -ey, ex
            pa = [ax * q[0] + ay * q[1] for q in A]; pb = [ax * q[0] + ay * q[1] for q in B]
            if max(pa) < min(pb) or max(pb) < min(pa): return False
    return True


class Terrace:
    """One terrace segment: houses side by side along a street contour, one mesh with per-face UV (metres) and colour attributes."""
    def __init__(s): s.g = Geo(); s.meta = []          # per face: (house origin, street floor z, house dict, is_front)

    def face(s, pts, mat, h, front=False, flip=False):
        if flip: pts = pts[::-1]
        s.g.add(pts, [tuple(range(len(pts)))], mat); s.meta.append((h, front))

    def house(s, FL, FR, depth, zb, zbase, top, roof, R, extras=True):
        t = Vector((FR[0] - FL[0], FR[1] - FL[1], 0.0)); w = t.length; t /= w; n_in = Vector((-t.y, t.x, 0.0))
        e = 0.0
        fl = Vector((FL[0], FL[1], 0.0)) - t * e; fr = Vector((FR[0], FR[1], 0.0)) + t * e
        bl = fl + n_in * depth; br = fr + n_in * depth
        h = dict(o=fl.copy(), t=t.copy(), zb=zb, w=w + 2 * e, wcol=LK.srgb(R.choice(TWALLS))[:3], scol=LK.srgb(R.choice(TSHUT))[:3],
                 rhue=R.random() * 0.86 if R.random() > 0.07 else 0.95)
        def P(v, z): return (v.x, v.y, z)
        # walls (front faces the street, downhill) and the floor slab underside is buried
        s.face([P(fl, zbase), P(fr, zbase), P(fr, top), P(fl, top)], 'rowhouse', h, True)
        s.face([P(br, zbase), P(bl, zbase), P(bl, top), P(br, top)], 'rowhouse', h)
        s.face([P(bl, zbase), P(fl, zbase), P(fl, top), P(bl, top)], 'rowhouse', h)
        s.face([P(fr, zbase), P(br, zbase), P(br, top), P(fr, top)], 'rowhouse', h)
        s.face([P(fl, zbase), P(bl, zbase), P(br, zbase), P(fr, zbase)], 'rowhouse', h)
        o = 0.35
        if roof == 'gable':                        # ridge along the row
            r = depth * 0.32
            a0 = fl + t * 0.01 - n_in * o; a1 = fr - t * 0.01 - n_in * o; b0 = bl + t * 0.01 + n_in * o; b1 = br - t * 0.01 + n_in * o
            m0 = (fl + bl) * 0.5 + t * 0.01; m1 = (fr + br) * 0.5 - t * 0.01
            s.face([P(a0, top - 0.12), P(a1, top - 0.12), P(m1, top + r), P(m0, top + r)], 'rowroof', h)
            s.face([P(b1, top - 0.12), P(b0, top - 0.12), P(m0, top + r), P(m1, top + r)], 'rowroof', h)
            s.face([P(fl, top), P(bl, top), P((fl + bl) * 0.5, top + r * 0.9)], 'rowhouse', h, flip=True)
            s.face([P(fr, top), P((fr + br) * 0.5, top + r * 0.9), P(br, top)], 'rowhouse', h, flip=True)
            if extras and R.random() < 0.45:      # chimney through the back slope
                c = fl + t * (w * R.uniform(0.2, 0.8)) + n_in * (depth * 0.7)
                n0 = len(s.g.F); s.g.box((c.x, c.y, top + r * 0.6 + 0.6), (0.7, 0.7, 2.2), 'rowhouse', Euler((0, 0, math.atan2(t.y, t.x))).to_matrix())
                s.meta += [(h, False)] * (len(s.g.F) - n0)
        else:                                      # flat roof terrace with a parapet and a water tank or a stair hut
            pz = top + 0.9
            ring = [(fl - t * 0.05 - n_in * 0.05), (fr + t * 0.05 - n_in * 0.05), (br + t * 0.05 + n_in * 0.05), (bl - t * 0.05 + n_in * 0.05)]
            inner = [fl + t * 0.25 + n_in * 0.25, fr - t * 0.25 + n_in * 0.25, br - t * 0.25 - n_in * 0.25, bl + t * 0.25 - n_in * 0.25]
            for i in range(4):
                a, b = ring[i], ring[(i + 1) % 4]; c, d = inner[i], inner[(i + 1) % 4]
                s.face([P(a, top - 0.1), P(b, top - 0.1), P(b, pz), P(a, pz)], 'rowhouse', h)
                s.face([P(a, pz), P(b, pz), P(d, pz), P(c, pz)], 'rowhouse', h)
                s.face([P(d, top + 0.02), P(c, top + 0.02), P(c, pz), P(d, pz)], 'rowhouse', h)
            s.face([P(inner[0], top + 0.02), P(inner[1], top + 0.02), P(inner[2], top + 0.02), P(inner[3], top + 0.02)], 'flatroof', h)
            if extras:
                c = fl + t * (w * R.uniform(0.25, 0.75)) + n_in * (depth * R.uniform(0.45, 0.7))
                n0 = len(s.g.F)
                if R.random() < 0.5: s.g.cyl((c.x, c.y, top), (c.x, c.y, top + 1.7), 0.75, n=10, mat='flatroof')
                else: s.g.box((c.x, c.y, top + 1.2), (2.4, 2.4, 2.4), 'rowhouse', Euler((0, 0, math.atan2(t.y, t.x))).to_matrix())
                s.meta += [(h, False)] * (len(s.g.F) - n0)
        if extras and R.random() < 0.3:            # a front balcony slab with a solid parapet on the second floor
            zf = zb + 3.0 * R.choice((1, 2))
            if zf + 1.2 < top:
                b0 = fl + t * (w * 0.2) - n_in * 1.0; b1 = fl + t * (w * 0.8) - n_in * 1.0; c0 = fl + t * (w * 0.2) + n_in * 0.1; c1 = fl + t * (w * 0.8) + n_in * 0.1
                for (za, zz) in ((zf - 0.18, zf), (zf, zf + 1.0)):
                    if za > zf - 0.1:
                        q0, q1 = b0, b1; qq0, qq1 = b0 + n_in * 0.12, b1 + n_in * 0.12
                    else:
                        q0, q1 = b0, b1; qq0, qq1 = c0, c1
                    s.face([P(q0, za), P(q1, za), P(q1, zz), P(q0, zz)], 'rowhouse', h)
                    s.face([P(qq1, za), P(qq0, za), P(qq0, zz), P(qq1, zz)], 'rowhouse', h)
                    s.face([P(q0, zz), P(q1, zz), P(qq1, zz), P(qq0, zz)], 'rowhouse', h)
                    s.face([P(qq0, za), P(qq1, za), P(q1, za), P(q0, za)], 'rowhouse', h)
                    s.face([P(qq0, za), P(q0, za), P(q0, zz), P(qq0, zz)], 'rowhouse', h)
                    s.face([P(q1, za), P(qq1, za), P(qq1, zz), P(q1, zz)], 'rowhouse', h)
        return [(fl.x, fl.y), (fr.x, fr.y), (br.x, br.y), (bl.x, bl.y)]

    def build(s, name, coll):
        me = s.g.mesh(name); nf = len(me.polygons)
        assert nf == len(s.meta), (nf, len(s.meta))
        uv = me.uv_layers.new(name='UVMap'); U = [0.0] * (2 * len(me.loops))
        WC = []; SC = []; RH = []; HW = []; FR = []
        for poly, (h, front) in zip(me.polygons, s.meta):
            n = poly.normal; tf = Vector((-n.y, n.x, 0.0))
            if tf.length < 1e-6: tf = h['t']
            else: tf.normalize()
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                U[2 * li] = (co - h['o']).dot(tf) if not front else (co - h['o']).dot(h['t'])
                U[2 * li + 1] = co.z - h['zb']
            WC += list(h['wcol']) + [1.0]; SC += list(h['scol']) + [1.0]; RH.append(h['rhue']); HW.append(h['w']); FR.append(1.0 if front else 0.0)
        uv.data.foreach_set('uv', U)
        for nm, kind, vals, key in (('wcol', 'FLOAT_COLOR', WC, 'color'), ('scol', 'FLOAT_COLOR', SC, 'color'), ('rhue', 'FLOAT', RH, 'value'),
                                    ('hw', 'FLOAT', HW, 'value'), ('front', 'FLOAT', FR, 'value')):
            a = me.attributes.new(nm, kind, 'FACE'); a.data.foreach_set(key, vals)
        me.update()
        return obj(name, me, coll, props={'qa_kind': 'house'})


TWALLS = ['#f1ead8', '#f4eedf', '#efe3c8', '#f2dccb', '#e6eef0', '#f6efd2', '#ead9c0', '#f1ead8', '#f8f3e8', '#f3e6d0', '#e9e4f0', '#f6e2c8']
TSHUT = ['#2a8f8a', '#3c6fb4', '#2f7a4f', '#8e2f3a', '#5f8fbf', '#c8553d', '#3f8f6a']


def build_town(coll, R):
    HM = [house_mesh(i) for i in range(len(HOUSE_V))]
    TM = tree_meshes()
    houses = []; trees = []; grid = {}; rects = {}
    def free(x, y, r):
        gx, gy = int(x // 20), int(y // 20)
        for i in range(gx - 1, gx + 2):
            for j in range(gy - 1, gy + 2):
                for (a, b, c) in grid.get((i, j), ()):
                    if (a - x) ** 2 + (b - y) ** 2 < (c + r) ** 2: return False
        return True
    def put(x, y, r): grid.setdefault((int(x // 20), int(y // 20)), []).append((x, y, r))
    def rput(q, segid):
        cx_ = sum(p[0] for p in q) / 4; cy_ = sum(p[1] for p in q) / 4
        rects.setdefault((int(cx_ // 20), int(cy_ // 20)), []).append((q, segid))
        put(cx_, cy_, max(math.hypot(p[0] - cx_, p[1] - cy_) for p in q) * 0.8)
    def rfree(q, segid):
        cx_ = sum(p[0] for p in q) / 4; cy_ = sum(p[1] for p in q) / 4; gx, gy = int(cx_ // 20), int(cy_ // 20)
        for i in range(gx - 1, gx + 2):
            for j in range(gy - 1, gy + 2):
                for (qq, sid) in rects.get((i, j), ()):
                    if sid != segid and _sat(q, qq): return False
        return True
    WALLS = TWALLS; SHUT = TSHUT
    # church with a campanile on a shoulder of the hill (placed first, the rows keep clear of it)
    cx, cy = -160.0, 1000.0; ch, _ = terrain_h(cx, cy)
    rput([(cx - 12, cy - 19), (cx + 20, cy - 19), (cx + 20, cy + 19), (cx - 12, cy + 19)], -1)
    # terraced rows: along each street contour (street centre heights 13, 27, 41 ...), a front row just above the street and,
    # where the slope leaves room, a second row half way up the block
    nseg = 0; nhouse = 0
    for k in range(10):
        hs = 6.0 + 14.0 * (k + 0.5)
        for lvl, dH in ((0, 2.2), (1, 7.4)):
            H = hs + dH; x = -880.0
            while x < 690.0:
                sparse = x < -650.0 or x > 450.0
                nseg_h = R.randint(3, 9) if not sparse else R.randint(2, 4)
                if (sparse and R.random() < 0.55) or (lvl == 1 and R.random() < 0.25):
                    x += R.uniform(14.0, 40.0); continue
                seg = Terrace(); segq = []; xs = x; ya = contour_y(xs, H)
                floors = R.choice((2, 3, 3, 4)) if k < 5 else R.choice((2, 2, 3))
                for i in range(nseg_h):
                    w = R.choice((6.5, 7.5, 8.5, 9.5, 11.0)); xb = xs + w; yb = contour_y(xb, H)
                    if ya is None or yb is None or abs(yb - ya) > w * 1.1: break
                    FL, FR = (xs, ya), (xb, yb)
                    t = Vector((xb - xs, yb - ya, 0.0)).normalized(); n_in = Vector((-t.y, t.x, 0.0))
                    depth = R.uniform(8.0, 11.0)
                    if lvl == 1:
                        ym = contour_y(0.5 * (xs + xb), hs + 2.2)
                        if ym is None or (0.5 * (ya + yb) - ym) < 13.5: break
                    ytop = contour_y(0.5 * (xs + xb), hs + 12.4)
                    if ytop is not None and (ytop - 0.5 * (ya + yb)) < depth + 1.5: depth = ytop - 0.5 * (ya + yb) - 1.5
                    if depth < 6.0: break
                    q = [(FL[0], FL[1]), (FR[0], FR[1]), (FR[0] + n_in.x * depth, FR[1] + n_in.y * depth), (FL[0] + n_in.x * depth, FL[1] + n_in.y * depth)]
                    if not rfree(q, nseg): break
                    cs = [terrain_h(px, py)[0] for px, py in q]
                    zb = max(cs[0], cs[1]); zbase = min(cs) - 0.6; fl_ = floors if R.random() > 0.25 else max(2, floors + R.choice((-1, 1)))
                    top = zb + 3.0 * fl_ + 0.4
                    if max(cs) > top - 2.0: break
                    roof = 'gable' if R.random() < 0.62 else 'flat'
                    seg.house(FL, FR, depth, zb, zbase, top, roof, R)
                    segq.append(q); xs, ya = xb, yb
                if segq:
                    for q in segq: rput(q, nseg)
                    houses.append(seg.build('PORT_row_%03d' % nseg, coll)); nhouse += len(segq)
                    nseg += 1
                    x = xs + R.uniform(3.5, 12.0)
                else:
                    x += R.uniform(6.0, 16.0)
    # detached villas on the outskirts and high up
    for _ in range(4000):
        if len(houses) >= nseg + 110: break
        x = R.uniform(-880.0, 680.0); y = R.uniform(700.0, 1170.0)
        h, _w = terrain_h(x, y)
        if h > 150.0 or _street(h): continue
        if -650 < x < 450 and h < 110.0: continue
        hx1, _ = terrain_h(x + 4.0, y); hy1, _ = terrain_h(x, y + 4.0)
        if abs(hx1 - h) > 2.6 or abs(hy1 - h) > 3.0: continue
        v = R.choices(range(len(HOUSE_V)), weights=(5, 3, 3, 1.5, 2, 2))[0]
        w, d, hh, kind = HOUSE_V[v]; r = math.hypot(w, d) * 0.5 + 0.6
        if not free(x, y, r): continue
        cs = [terrain_h(x + sx * w * 0.5, y + sy * d * 0.5)[0] for sx in (-1, 1) for sy in (-1, 1)]
        if max(cs) - min(cs) > 3.6 or _street(max(cs)) or _street(min(cs)): continue
        rot = math.radians(R.uniform(-7, 7)); cr, sr = math.cos(rot), math.sin(rot)
        q = [(x + cr * px - sr * py, y + sr * px + cr * py) for px, py in ((-w / 2 - 0.4, -d / 2 - 1.2), (w / 2 + 0.4, -d / 2 - 1.2), (w / 2 + 0.4, d / 2 + 0.4), (-w / 2 - 0.4, d / 2 + 0.4))]
        if not rfree(q, -2): continue
        put(x, y, r); rput(q, -3)
        o = obj('PORT_house_%03d' % len(houses), HM[v], coll, (x, y, min(cs) - 0.15), (0, 0, rot), props={'qa_kind': 'house'})
        o['wcol'] = LK.srgb(R.choice(WALLS))[:3]; o['scol'] = LK.srgb(R.choice(SHUT))[:3]; o['rhue'] = R.random() * 0.86 if R.random() > 0.08 else 0.95
        houses.append(o)
    print('PORT town: %d terrace segments, %d terrace houses, %d villas' % (nseg, nhouse, len(houses) - nseg))
    g = Geo(); g.blh((-9, -16, -6), (9, 16, 14), 'house')
    V = [(-9.6, -16.6, 14), (9.6, -16.6, 14), (9.6, 16.6, 14), (-9.6, 16.6, 14), (0, -16.6, 20.5), (0, 16.6, 20.5)]
    g.add(V, [(0, 1, 5, 4), (2, 3, 4, 5)], 'roof'); g.add([(-9, -16, 14), (9, -16, 14), (0, -16, 20.0)], [(0, 1, 2)], 'house')
    g.blh((10.0, -16.0, -6), (17.0, -9.0, 34.0), 'house'); g.blh((9.6, -16.4, 34.0), (17.4, -8.6, 35.0), 'white')
    V = [(9.6, -16.4, 35.0), (17.4, -16.4, 35.0), (17.4, -8.6, 35.0), (9.6, -8.6, 35.0), (13.5, -12.5, 42.0)]
    g.add(V, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2, 1)], 'roof')
    g.blh((11.2, -16.05, 28.0), (15.8, -15.95, 32.5), 'steeldk')
    church = obj('PORT_church', g.mesh('PORT_church'), coll, (cx, cy, ch - 0.5), props={'qa_kind': 'house'})
    church['wcol'] = LK.srgb('#f6f1e6')[:3]; church['scol'] = LK.srgb('#2a8f8a')[:3]; church['rhue'] = 0.1
    houses.append(church)
    # trees: gardens in the town, forest on the hills and headlands, a row along the waterfront road
    nt = 0
    for k in range(40):
        x = -680.0 + k * 32.0 + R.uniform(-2, 2)
        if -540 < x < -380: continue
        o = obj('PORT_tree_%04d' % nt, TM[2], coll, (x, 671.0, QZ - 0.3), props={'qa_kind': 'tree'}); trees.append(o); nt += 1; put(x, 671.0, 1.6)
    for _ in range(26000):
        if nt >= 1500: break
        x = R.uniform(-2000.0, 2000.0); y = R.uniform(300.0, 2600.0)
        h, wp = terrain_h(x, y)
        if h < 3.0 or (wp > 0.5 and y < 700.0): continue
        far = y > 1200.0 or x < -900.0 or x > 750.0
        if far and R.random() > 0.55: continue
        if not far and (R.random() > 0.5 or _street(h)): continue
        k = 3 if (y > 1350.0 or abs(x) > 1100.0) else R.choice((0, 0, 1, 2))
        sc = R.uniform(0.8, 1.25); r = (3.5, 5.0, 1.5, 7.6)[k] * sc
        if not free(x, y, r): continue
        hx1, _ = terrain_h(x + 3.0, y)
        if abs(hx1 - h) > 4.5: continue
        put(x, y, r)
        o = obj('PORT_tree_%04d' % nt, TM[k], coll, (x, y, h - 0.3), (0, 0, R.uniform(0, 6.28)), props={'qa_kind': 'tree'})
        o.scale = (sc, sc, sc * R.uniform(0.9, 1.15)); trees.append(o); nt += 1
    return houses, trees




# ------------------------------------------------------------------------------------------------------------------------------ fishing boats
BOAT_L = (15.0, 18.5, 22.0)
BOAT_SPOTS = [(1, 191.0, 368.0, 90.0), (0, 191.6, 340.0, 90.0), (2, 209.8, 372.0, 90.0), (1, 209.4, 341.0, 92.0),
              (0, 128.0, 362.0, 75.0), (2, 152.0, 336.0, 102.0), (1, 262.0, 364.0, 84.0), (0, 288.0, 338.0, 98.0)]
BOAT_COL = [('#d23a2e', '#f4efe4'), ('#2f5fd0', '#f4efe4'), ('#3fa34d', '#f4efe4'), ('#f2b705', '#2f5fd0'), ('#2a8f8a', '#f4efe4'),
            ('#f07a2a', '#24407a'), ('#24407a', '#f2b705'), ('#ece8df', '#d23a2e')]


class BoatSpec:
    def __init__(s, L):
        s.L = L; s.hb0 = L * 0.165; s.D = L * 0.105; s.z0 = 0.08 * L
    def hb(s, t):
        if t > 0: return s.hb0 * max(0.05, 1 - t ** 2.2) ** 0.55
        return s.hb0 * (0.86 + 0.14 * (1 - (-t) ** 3))
    def zk(s, t):
        return -s.D + 0.72 * s.D * _ss(0.3, 1.0, t) + 0.3 * s.D * _ss(-0.8, -1.0, t)
    def zs(s, t): return s.z0 + 0.07 * s.L * max(0.0, t) ** 2 + 0.01 * s.L * max(0.0, -t)
    def x(s, t): return t * s.L * 0.5
    def t(s, x): return x / (s.L * 0.5)


def hull_mesh(sp, name):
    N = 20; g = Geo(); rings = []
    for k in range(N + 1):
        t = -1.0 + 2.0 * k / N; x = sp.x(t); hb = sp.hb(t); zk = sp.zk(t); zs = sp.zs(t)
        half = [(hb * 1.03, zs), (hb * 1.0, zs * 0.4), (hb * 0.97, 0.0), (hb * 0.84, zk * 0.42), (hb * 0.5, zk * 0.84), (min(0.18, hb * 0.3), zk)]
        ring = [(x, y, z) for y, z in half] + [(x, -y, z) for y, z in reversed(half)]
        rings.append(ring)
    n = len(rings[0]); V = [p for r in rings for p in r]; base = g.add(V, [], 'hull')
    for k in range(N):
        a = k * n; b = (k + 1) * n
        for i in range(n - 1):
            g.F.append((base + a + i, base + b + i, base + b + i + 1, base + a + i + 1)); g.M.append('hull'); g.S.append(True)
        g.F.append((base + a + n - 1, base + b + n - 1, base + b, base + a)); g.M.append('deck'); g.S.append(False)
    g.F.append(tuple(base + i for i in range(n))); g.M.append('hull'); g.S.append(False)
    g.F.append(tuple(base + N * n + i for i in range(n - 1, -1, -1))); g.M.append('hull'); g.S.append(False)
    return g.mesh(name, recalc=True)


def boat_top_mesh(sp, cls, name, R):
    g = Geo(); L = sp.L; hb = sp.hb0
    # bulwark rail along the sheer, both sides
    for side in (-1, 1):
        for k in range(16):
            t0 = -0.98 + 1.96 * k / 16; t1 = -0.98 + 1.96 * (k + 1) / 16
            p0 = (sp.x(t0), side * sp.hb(t0) * 0.98, sp.zs(t0)); p1 = (sp.x(t1), side * sp.hb(t1) * 0.98, sp.zs(t1))
            g.beam((p0[0], p0[1], p0[2] + 0.38), (p1[0], p1[1], p1[2] + 0.38), 0.16, 0.8, 'hull' if False else 'white')
    tc0, tc1 = 0.02, 0.3 + 0.04 * cls
    x0, x1 = sp.x(tc0), sp.x(tc1); zd = sp.zs(tc1) - 0.05; w = hb * 0.62
    g.blh((x0, -w, zd - 0.4), (x1, w, zd + 1.7), 'cabin')
    g.blh((x0 + 0.08, -w + 0.08, zd + 1.7), (x1 - 0.08, w - 0.08, zd + 2.45), 'glass')
    g.blh((x0 - 0.3, -w - 0.25, zd + 2.45), (x1 + 0.35, w + 0.25, zd + 2.72), 'cabin')
    if cls >= 1:
        g.blh((x0 + 0.6, -w * 0.7, zd + 2.72), (x1 - 0.5, w * 0.7, zd + 3.9), 'cabin'); g.blh((x0 + 0.66, -w * 0.7 + 0.06, zd + 3.3), (x1 - 0.56, w * 0.7 - 0.06, zd + 3.85), 'glass')
        g.blh((x0 + 0.45, -w * 0.75, zd + 3.9), (x1 - 0.35, w * 0.75, zd + 4.1), 'cabin'); ztop = zd + 4.1
    else: ztop = zd + 2.72
    xm = (x0 + x1) * 0.5 - 0.4
    g.cyl((xm, 0, ztop), (xm, 0, ztop + 4.5 + cls), 0.12, n=8, mat='steeldk')
    g.beam((xm, -1.6, ztop + 3.2), (xm, 1.6, ztop + 3.2), 0.1, 0.1, 'steeldk')
    g.blh((xm - 0.9, -0.12, ztop + 1.6), (xm + 0.9, 0.12, ztop + 1.75), 'white'); g.cyl((xm, 0, ztop + 1.2), (xm, 0, ztop + 1.6), 0.12, n=6, mat='steeldk')
    for sy in (-1.5, 1.5): g.sphere((xm, sy, ztop + 3.32), 0.12, 'orange', 6, 4)
    g.cyl((x1 - 0.6, w * 0.5, ztop), (x1 - 0.6, w * 0.5, ztop + 2.4), 0.03, n=4, mat='steeldk')
    ring = [(x1 - 0.03 + 0.0 * k, -w - 0.06, zd + 0.9 + 0.38 * math.sin(k / 12 * math.tau)) for k in range(13)]
    ring = [((x0 + x1) / 2 + 0.38 * math.cos(k / 12 * math.tau), -w - 0.08, zd + 0.85 + 0.38 * math.sin(k / 12 * math.tau)) for k in range(13)]
    g.tube(ring, 0.07, n=5, mat='orange', caps=False)
    # foremast and outriggers
    tf = 0.55; xf = sp.x(tf); zf = sp.zs(tf)
    g.cyl((xf, 0, zf - 0.2), (xf, 0, zf + 6.0 + cls), 0.14, n=8, mat='white')
    if cls != 1:
        for side in (-1, 1):
            g.cyl((xf - 0.4, side * 0.3, zf + 0.6), (xf - 2.2, side * (hb + L * 0.32), zf + L * 0.42), 0.09, n=6, mat='steeldk')
            g.cyl((xf, 0, zf + 5.6 + cls), (xf - 2.2, side * (hb + L * 0.32), zf + L * 0.42), 0.02, n=4, mat='steeldk', caps=(False, False))
    else:
        g.beam((xf, 0, zf + 1.5), (xf - 5.5, 0, zf + 4.0), 0.14, 0.14, 'steeldk')
    # stern gantry, net drum, nets, fish boxes, buoys, tyres
    ta = -0.86; xa = sp.x(ta); za = sp.zs(ta); wa = sp.hb(ta) * 0.86
    for side in (-1, 1):
        g.beam((xa, side * wa, za - 0.1), (xa + 0.4, side * wa * 0.8, za + 4.6), 0.3, 0.3, 'yellow')
    g.beam((xa + 0.4, -wa * 0.8 - 0.2, za + 4.6), (xa + 0.4, wa * 0.8 + 0.2, za + 4.6), 0.35, 0.35, 'yellow')
    g.cyl((xa + 0.4, -0.4, za + 4.3), (xa + 0.4, -0.4, za + 2.6), 0.03, n=4, mat='steeldk'); g.blh((xa + 0.25, -0.6, za + 2.3), (xa + 0.55, -0.2, za + 2.6), 'steeldk')
    td = -0.55; xd = sp.x(td); zdd = sp.zs(td)
    g.cyl((xd, -w * 0.9, zdd + 1.0), (xd, w * 0.9, zdd + 1.0), 0.95, n=14, mat='net')
    for side in (-1, 1):
        g.blh((xd - 0.5, side * w * 0.9 - 0.1 * (side < 0), zdd - 0.05), (xd + 0.5, side * w * 0.9 + 0.1 * (side > 0) + 0.0001, zdd + 1.4), 'steel')
    g.sphere((sp.x(-0.72), w * 0.25, zdd + 0.2), 1.3, 'net', 9, 5, 0.45)
    for k in range(4 + cls * 2):
        bx = sp.x(-0.3) + (k % 3) * 0.75; by = -w * 0.55 + (k // 3) * 0.62; bz = sp.zs(-0.3) - 0.05 + 0.0
        g.blh((bx, by, bz), (bx + 0.7, by + 0.55, bz + 0.38), 'teal' if k % 2 else 'orange')
    for side in (-1, 1):
        for tt in (-0.62, -0.25, 0.12):
            yb = side * (sp.hb(tt) * 1.03 + 0.32); g.sphere((sp.x(tt), yb, sp.zs(tt) - 0.5), 0.3, 'orange', 8, 5)
            g.beam((sp.x(tt), side * sp.hb(tt) * 0.98, sp.zs(tt) + 0.7), (sp.x(tt), yb, sp.zs(tt) - 0.2), 0.02, 0.02, 'rope')
        for tt in (-0.45, -0.08, 0.28):
            yb = side * (sp.hb(tt) * 1.0 + 0.2); g.cyl((sp.x(tt) - 0.32, yb, sp.zs(tt) * 0.62), (sp.x(tt) + 0.32, yb, sp.zs(tt) * 0.62), 0.42, n=10, mat='rubber')
    g.blh((sp.x(0.8) - 0.5, -0.4, sp.zs(0.8) - 0.1), (sp.x(0.8) + 0.3, 0.4, sp.zs(0.8) + 0.5), 'steeldk')
    return g.mesh(name)


def build_boats(coll, R):
    hulls = [hull_mesh(BoatSpec(L), 'PORT_hull%d' % i) for i, L in enumerate(BOAT_L)]
    tops = [boat_top_mesh(BoatSpec(L), i, 'PORT_boattop%d' % i, R) for i, L in enumerate(BOAT_L)]
    boats = []
    for i, (cls, x, y, yaw) in enumerate(BOAT_SPOTS):
        root = empty('PORT_boat_%d' % i, coll, (x, y, 0.0), (0, 0, math.radians(yaw)), size=4.0)
        sp = BoatSpec(BOAT_L[cls]); mc, bc = BOAT_COL[i]
        h = obj('PORT_boat_%d_hull' % i, hulls[cls], coll, (0, 0, 0), parent=root, bevel=0.0,
                props={'qa_kind': 'boat', 'hcol': LK.srgb(mc)[:3], 'bcol': LK.srgb(bc)[:3], 'sheer': sp.z0, 'blen': sp.L, 'nrow': float(i)})
        t = obj('PORT_boat_%d_top' % i, tops[cls], coll, (0, 0, 0), parent=root, bevel=0.03, props={'qa_kind': 'boat'})
        root['length'] = sp.L; root['beam'] = sp.hb0 * 2.0
        boats.append(root)
    return boats


# ------------------------------------------------------------------------------------------------------------------------------ fishing pier
def build_pier(coll, R):
    g = Geo(); x0, x1, y0, y1 = 195.0, 205.0, 318.0, 400.0; zt = 3.6
    g.blh((x0, y0, zt - 0.6), (x1, 399.3, zt), 'wood')
    g.blh((x0 - 0.15, y0, zt - 1.0), (x0 + 0.25, 399.3, zt - 0.5), 'concrete'); g.blh((x1 - 0.25, y0, zt - 1.0), (x1 + 0.15, 399.3, zt - 0.5), 'concrete')
    yp = y0 + 1.0
    while yp < 399.0:
        for xp in (x0 + 0.4, x1 - 0.4):
            g.cyl((xp, yp, -6.0), (xp, yp, zt - 1.0), 0.35, n=10, mat='concrete')
        g.beam((x0 + 0.4, yp, 1.2), (x1 - 0.4, yp, 1.2), 0.3, 0.4, 'concrete')
        yp += 6.0
    for yb in range(int(y0) + 4, 398, 10):
        for xb in (x0 + 0.45, x1 - 0.45):
            g.cyl((xb, yb, zt - 0.02), (xb, yb, zt + 0.55), 0.22, n=10, mat='steeldk'); g.cyl((xb, yb, zt + 0.55), (xb, yb, zt + 0.66), 0.32, n=10, mat='steeldk')
        for xt, s in ((x0, -1), (x1, 1)):
            g.cyl((xt + s * 0.28, yb + 5.0 - 0.35, 1.9), (xt + s * 0.28, yb + 5.0 + 0.35, 1.9), 0.5, n=10, mat='rubber')
    for yl in (330.0, 356.0, 382.0):
        g.cyl((x1 - 0.6, yl, zt - 0.02), (x1 - 0.6, yl, zt + 6.5), 0.11, 0.08, n=8, mat='steel')
        g.beam((x1 - 0.6, yl, zt + 6.3), (x1 - 1.8, yl, zt + 6.6), 0.1, 0.1, 'steel'); g.blh((x1 - 2.2, yl - 0.25, zt + 6.35), (x1 - 1.6, yl + 0.25, zt + 6.65), 'steeldk')
        g.blh((x1 - 2.15, yl - 0.2, zt + 6.25), (x1 - 1.65, yl + 0.2, zt + 6.35), 'lampglow')
    g.blh((198.0, 319.0, zt - 0.02), (204.2, 325.0, zt + 2.8), 'white'); g.blh((197.7, 318.7, zt + 2.8), (204.5, 325.3, zt + 3.1), 'roof')
    g.blh((199.0, 318.94, zt + 0.9), (201.6, 319.0, zt + 2.0), 'glass'); g.blh((202.2, 318.95, zt), (203.6, 319.0, zt + 2.1), 'teal')
    for k in range(10):
        bx = 196.0 + (k % 2) * 0.8; by = 335.0 + (k // 4) * 0.7 + (k % 4 // 2) * 7.0; bz = zt + (k // 2 % 2) * 0.4
        g.blh((bx, by, bz), (bx + 0.72, by + 0.56, bz + 0.38), 'teal' if k % 3 else 'orange')
    g.sphere((202.5, 348.0, zt + 0.2), 1.4, 'net', 9, 5, 0.42); g.sphere((197.4, 372.0, zt + 0.2), 1.1, 'net', 9, 5, 0.45)
    for (cx, cy) in ((203.2, 362.0), (196.6, 389.0)):
        for k in range(4):
            g.cyl((cx, cy, zt + k * 0.12), (cx, cy, zt + k * 0.12 + 0.12), 0.6 - k * 0.04, n=12, mat='rope')
    for zz in range(0, 13):
        z = 0.2 + zz * 0.28
        g.blh((x0 - 0.42, 352.6, z), (x0 - 0.36, 353.4, z + 0.05), 'steel')
    for sy in (352.6, 353.36):
        g.blh((x0 - 0.45, sy, -1.0), (x0 - 0.33, sy + 0.04 + 0.0, zt + 1.0), 'steel')
    o = gobj('PORT_pier', g, coll, bevel=0.03, props={'qa_kind': 'ground'})
    return o




# ------------------------------------------------------------------------------------------------------------------------------ breakwaters
BW_E0, BW_E1 = (600.0, 400.0), (400.0, 60.0)
SEABED = -12.0
TOE_W = 15.0 + 1.5 * (2.5 - SEABED)          # trunk seaward toe offset from the axis (crown wall foot at |x+700| = 15, z 2.5)
TOE_E = 12.0 + 1.5 * (4.0 - SEABED)          # trunk harbour-side toe offset
TOE_H = 48.0 + 1.5 * (2.0 - SEABED)          # round-head toe radius


def rock_meshes(R):
    out = []
    for k in range(4):
        g = Geo(); g.sphere((0, 0, 0), 1.0, 'rock', 7, 5, 0.75, smooth=False)
        rr = random.Random(100 + k)
        g.V = [(x * rr.uniform(0.75, 1.25), y * rr.uniform(0.75, 1.25), z * rr.uniform(0.7, 1.2)) for (x, y, z) in g.V]
        out.append(g)
    return out


def scatter_rocks(g, RM, R, pts):
    """Merge rock instances (random rotation/scale) into one rubble mesh."""
    for (p, s) in pts:
        src = RM[R.randrange(len(RM))]
        M = Euler((R.uniform(0, 6.28), R.uniform(0, 6.28), R.uniform(0, 6.28))).to_matrix()
        sc = Vector((s * R.uniform(0.8, 1.3), s * R.uniform(0.8, 1.3), s * R.uniform(0.6, 0.9)))
        V = [tuple(Vector(p) + M @ Vector((v[0] * sc.x, v[1] * sc.y, v[2] * sc.z))) for v in src.V]
        g.add(V, src.F, 'rock')


def bw_outline():
    """Cap outline of the west breakwater: trunk (24 m) + round head (r 45) as one simple polygon (counter-clockwise)."""
    hw = BW_W * 0.5; cx, cy = LH_C
    a0 = math.asin(hw / HEAD_R); ys = cy + HEAD_R * math.cos(a0)
    pts = [(BW_X - hw, BW_Y0), (BW_X - hw, ys)]
    n = 96
    for k in range(1, n):
        a = (math.pi / 2 + a0) + (2 * math.pi - 2 * a0) * k / n
        pts.append((cx + HEAD_R * math.cos(a), cy + HEAD_R * math.sin(a)))
    pts += [(BW_X + hw, ys), (BW_X + hw, BW_Y0)]
    return pts


def build_west_breakwater(coll, R, RM):
    out = {}; hw = BW_W * 0.5; cx, cy = LH_C
    # cap slab (one surface: no coplanar overlaps) + root ramp + edge kerb
    g = Geo(); P = bw_outline()
    g.prism(P, 2.0, BW_Z, 'bwcap')
    g.add([(BW_X - hw, BW_Y0, BW_Z), (BW_X + hw, BW_Y0, BW_Z), (BW_X + hw, BW_Y0 + 12.0, 3.9), (BW_X - hw, BW_Y0 + 12.0, 3.9),
           (BW_X - hw, BW_Y0, 3.9), (BW_X + hw, BW_Y0, 3.9)], [(0, 3, 2, 1), (0, 4, 3), (1, 2, 5), (4, 5, 2, 3), (0, 1, 5, 4)], 'bwcap')
    ys = cy + math.sqrt(HEAD_R ** 2 - hw ** 2)
    g.blh((BW_X + hw - 0.45, ys + 3.0, BW_Z - 0.1), (BW_X + hw - 0.02, BW_Y0, BW_Z + 0.3), 'crown')
    # berm skirt round the head (r 45 -> 48), outside the trunk sector
    a0 = math.asin((hw + 1.0) / HEAD_R); n = 90; ring0 = []; ring1 = []
    for k in range(n + 1):
        a = (math.pi / 2 + a0) + (2 * math.pi - 2 * a0) * k / n
        ring0.append((cx + HEAD_R * math.cos(a), cy + HEAD_R * math.sin(a), BW_Z)); ring1.append((cx + 48.0 * math.cos(a), cy + 48.0 * math.sin(a), 2.0))
    b = g.add(ring0 + ring1, [], 'crown')
    for k in range(n):
        g.F.append((b + k, b + n + 1 + k, b + n + 2 + k, b + k + 1)); g.M.append('crown'); g.S.append(False)
    cap = obj('PORT_bw_cap', g.mesh('PORT_bw_cap', recalc=True), coll, props={'qa_kind': 'ground'})
    # crown wall on the seaward side of the trunk (x -715..-712, top +7.5)
    # it stops 52 m from the lighthouse (not at the head's rim, 46.5): the wind's right swing (s37, 77.29) sweeps a 9 m sole
    # across the trunk's root, toes down, and touched the wall's end and its rail there (QA s37: footR x crown 0.12 m)
    c = Geo(); yc0 = cy + math.sqrt(max(0.0, 52.0 ** 2 - (hw + 1.5) ** 2))
    c.blh((BW_X - 15.0, yc0, 1.5), (BW_X - hw - 0.02, BW_Y0 + 2.0, 7.5), 'crown')
    c.blh((BW_X - 15.3, yc0, 7.5), (BW_X - hw - 0.02, BW_Y0 + 2.0, 7.8), 'crown')
    crown = gobj('PORT_bw_crown', c, coll, bevel=0.08, props={'qa_kind': 'ground'})
    # rubble core: trunk trapezoid + head frustum (seabed -12)
    k = Geo()
    prof = [(-15.0, 2.5), (-TOE_W, SEABED), (TOE_E, SEABED), (12.0, 4.0)]
    V = [(BW_X + u, BW_Y0 + 20.0, z) for u, z in prof] + [(BW_X + u, cy, z) for u, z in prof]
    k.add(V, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (0, 3, 2, 1), (4, 5, 6, 7)], 'rock')
    n = 72; top = []; bot = []
    for i in range(n):
        a = i / n * math.tau
        top.append((cx + 47.9 * math.cos(a), cy + 47.9 * math.sin(a), 2.05)); bot.append((cx + TOE_H * math.cos(a), cy + TOE_H * math.sin(a), SEABED))
    b = k.add(top + bot, [], 'rock')
    for i in range(n):
        j = (i + 1) % n; k.F.append((b + i, b + n + i, b + n + j, b + j)); k.M.append('rock'); k.S.append(False)
    k.F.append(tuple(b + i for i in range(n))); k.M.append('rock'); k.S.append(False)
    k.F.append(tuple(b + n + i for i in range(n - 1, -1, -1))); k.M.append('rock'); k.S.append(False)
    core = obj('PORT_bw_core', k.mesh('PORT_bw_core', recalc=True), coll, props={'qa_kind': 'ground'})
    # harbour-side armour rocks (one rubble mesh) on the trunk's east slope
    rg = Geo(); pts = []
    y = BW_Y0 - 2.0
    while y > -96.0:
        for _ in range(3):
            u = R.uniform(12.6, 24.0); z = 4.0 - (u - 12.0) / 1.5
            pts.append(((BW_X + u, y + R.uniform(-1.2, 1.2), z + 0.25), R.uniform(1.0, 1.7)))
        y -= 2.2
    scatter_rocks(rg, RM, R, pts)
    rocks = gobj('PORT_bw_rocks', rg, coll, props={'qa_kind': 'ground'})
    # edge furniture: slim bollards + lamps on the harbour edge, lamps + railing on the crown wall
    f = Geo(); y = BW_Y0 - 14.0; i = 0
    while y > ys + 4.0:
        xb = BW_X + hw - 0.22
        f.cyl((xb, y, BW_Z + 0.25), (xb, y, BW_Z + 0.95), 0.18, n=10, mat='steeldk'); f.cyl((xb, y, BW_Z + 0.95), (xb, y, BW_Z + 1.05), 0.21, n=10, mat='yellow')
        if i % 2 == 0 and y - 12.0 > ys + 4.0:
            xl = BW_X + hw - 0.22; yl = y - 12.0
            f.cyl((xl, yl, BW_Z + 0.25), (xl, yl, BW_Z + 8.5), 0.13, 0.09, n=8, mat='white')
            f.beam((xl, yl, BW_Z + 8.3), (xl + 0.5, yl, BW_Z + 8.6), 0.08, 0.08, 'white')
            f.blh((xl + 0.25, yl - 0.25, BW_Z + 8.45), (xl + 0.85, yl + 0.25, BW_Z + 8.75), 'steeldk'); f.blh((xl + 0.3, yl - 0.2, BW_Z + 8.35), (xl + 0.8, yl + 0.2, BW_Z + 8.45), 'lampglow')
            xw = BW_X - 13.5
            f.cyl((xw, yl + 20.0, 7.8), (xw, yl + 20.0, 14.5), 0.13, 0.09, n=8, mat='white')
            f.blh((xw - 0.3, yl + 19.7, 14.4), (xw + 0.3, yl + 20.3, 14.75), 'steeldk'); f.blh((xw - 0.25, yl + 19.75, 14.3), (xw + 0.25, yl + 20.25, 14.4), 'lampglow')
        y -= 25.0; i += 1
    _rail(f, [(BW_X - 14.7, BW_Y0), (BW_X - 14.7, yc0 + 1.0)], 7.8, 1.1, 'white', 2.5, 0.05)
    props = gobj('PORT_bw_props', f, coll, bevel=0.02, props={'qa_kind': 'prop'})
    out.update(cap=cap, crown=crown, core=core, rocks=rocks, props=props)
    return out


# ------------------------------------------------------------------------------------------------------------------------------ tetrapods
TETRA_DIRS = [Vector((0, 0, 1)), Vector((math.sqrt(8 / 9), 0, -1 / 3)), Vector((-math.sqrt(2 / 9), math.sqrt(2 / 3), -1 / 3)), Vector((-math.sqrt(2 / 9), -math.sqrt(2 / 3), -1 / 3))]


def tetra_geo(L=2.5, r0=0.95, r1=0.62):
    g = Geo()
    for d in TETRA_DIRS:
        g.cyl(tuple(-d * 0.35), tuple(d * L), r0, r1, n=8, mat='tetra', caps=(True, True), smooth=False)
    return g


def build_tetrapods(coll, R, avoid_bvh):
    tg = tetra_geo(); me = tg.mesh('PORT_tetrapod'); base = [Vector(v) for v in tg.V]; F = tg.F
    cx, cy = LH_C; placed = []; grid = {}; objs = []
    def ok(Vw, c):
        gx, gy = int(c.x // 7), int(c.y // 7)
        t = BVHTree.FromPolygons(Vw, F, all_triangles=False, epsilon=0.0)
        for i in range(gx - 1, gx + 2):
            for j in range(gy - 1, gy + 2):
                for (cc, tt) in grid.get((i, j), ()):
                    if (cc - c).length < 6.2 and t.overlap(tt): return None
        for ab in avoid_bvh:
            if t.overlap(ab): return None
        return t
    def attempt(c, normal):
        M = Euler((R.uniform(0, 6.28), R.uniform(0, 6.28), R.uniform(0, 6.28))).to_matrix()
        Vw = [tuple(c + M @ v) for v in base]
        for v in Vw:
            if v[1] < BW_Y1 + 70.0 and math.hypot(v[0] - cx, v[1] - cy) < 48.2: return False
            if abs(v[0] - BW_X) < 15.05 and v[1] > cy: return False
        t = ok(Vw, c)
        if t is None: return False
        grid.setdefault((int(c.x // 7), int(c.y // 7)), []).append((c, t)); placed.append((c, M)); return True
    # trunk seaward side: x <= -715, two layers on the 1:1.5 slope
    sn = Vector((-1.0, 0.0, 1.5)).normalized()
    for layer, off, tries in ((0, 1.25, 3), (1, 3.4, 2)):
        y = BW_Y0 - 3.0
        while y > cy + 42.0:
            for _ in range(2):
                u = R.uniform(15.6, 28.0) if layer == 0 else R.uniform(15.6, 22.0)
                z = 2.5 - (u - 15.0) / 1.5
                c = Vector((BW_X - u, y + R.uniform(-1.2, 1.2), z)) + sn * off
                if c.z < -3.5: continue
                for _t in range(tries):
                    if attempt(c, sn): break
            y -= 2.6 if layer == 0 else 3.6
    # round head: everything outside r 48 (except the trunk on the north)
    for layer, off, tries in ((0, 1.25, 3), (1, 3.4, 2)):
        n = 150 if layer == 0 else 110
        for i in range(n):
            a = i / n * math.tau + R.uniform(-0.01, 0.01)
            for _ in range(2):
                rr = R.uniform(49.6, 60.0) if layer == 0 else R.uniform(49.6, 55.0)
                z = 2.0 - (rr - 48.0) / 1.5
                dn = Vector((math.cos(a), math.sin(a), 0.0))
                nn = (dn + Vector((0, 0, 1.5))).normalized()
                c = Vector((cx, cy, 0.0)) + dn * rr + Vector((0, 0, z)) + nn * off
                if c.z < -3.5: continue
                for _t in range(tries):
                    if attempt(c, nn): break
    for i, (c, M) in enumerate(placed):
        o = obj('PORT_tetra_%04d' % i, me, coll, tuple(c), M.to_euler(), props={'qa_kind': 'tetra'})
        objs.append(o)
    return objs


# ------------------------------------------------------------------------------------------------------------------------------ east breakwater
def build_east_breakwater(coll, R, RM):
    p0 = Vector((*BW_E0, 0.0)); p1 = Vector((*BW_E1, 0.0)); d = (p1 - p0).normalized(); nrm = Vector((-d.y, d.x, 0.0))
    hw = 6.0; zt = 4.5; g = Geo(); P = []
    P.append(tuple((p0 - nrm * hw).xy)); P.append(tuple((p1 - nrm * hw).xy))
    for k in range(1, 24):
        a = -math.pi / 2 + math.pi * k / 24
        q = p1 + (d * math.cos(a) + nrm * math.sin(a)) * hw; P.append((q.x, q.y))
    P.append(tuple((p1 + nrm * hw).xy)); P.append(tuple((p0 + nrm * hw).xy))
    area = sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))
    if area < 0: P.reverse()
    g.prism(P, 2.0, zt, 'bwcap')
    cap = gobj('PORT_bwE_cap', g, coll, props={'qa_kind': 'ground'})
    k = Geo(); w0 = hw + 0.2; w1 = hw + 1.5 * (2.4 - SEABED)
    k.extrude([(-w0, 2.4), (-w1, SEABED), (w1, SEABED), (w0, 2.4)], tuple(p0 - d * 30.0), tuple(p1), 'rock')
    n = 40; top = []; bot = []
    for i in range(n):
        a = i / n * math.tau
        top.append((p1.x + w0 * math.cos(a), p1.y + w0 * math.sin(a), 2.4)); bot.append((p1.x + w1 * math.cos(a), p1.y + w1 * math.sin(a), SEABED))
    b = k.add(top + bot, [], 'rock')
    for i in range(n):
        j = (i + 1) % n; k.F.append((b + i, b + n + i, b + n + j, b + j)); k.M.append('rock'); k.S.append(False)
    k.F.append(tuple(b + i for i in range(n))); k.M.append('rock'); k.S.append(False)
    core = obj('PORT_bwE_core', k.mesh('PORT_bwE_core', recalc=True), coll, props={'qa_kind': 'ground'})
    rg = Geo(); pts = []; L = (p1 - p0).length; s = 2.0
    while s < L:
        for side in (-1, 1):
            for _ in range(2):
                u = R.uniform(hw + 0.7, hw + 11.0); z = 2.4 - (u - w0) / 1.5
                pts.append((tuple(p0 + d * (s + R.uniform(-1, 1)) + nrm * side * u + Vector((0, 0, z + 0.2))), R.uniform(1.0, 1.6)))
        s += 2.4
    for i in range(30):
        a = i / 30 * math.pi * 2
        for _ in range(2):
            u = R.uniform(hw + 0.7, hw + 11.0); z = 2.4 - (u - w0) / 1.5
            q = p1 + Vector((math.cos(a), math.sin(a), 0)) * u
            if (q - p1).dot(d) < -1.0: continue
            pts.append(((q.x, q.y, z + 0.2), R.uniform(1.0, 1.6)))
    scatter_rocks(rg, RM, R, pts)
    rocks = gobj('PORT_bwE_rocks', rg, coll, props={'qa_kind': 'ground'})
    f = Geo(); s = 20.0
    while s < L - 10.0:
        q = p0 + d * s + nrm * (hw - 0.6)
        f.cyl((q.x, q.y, zt - 0.05), (q.x, q.y, zt + 6.5), 0.12, 0.08, n=8, mat='white'); f.blh((q.x - 0.3, q.y - 0.3, zt + 6.4), (q.x + 0.3, q.y + 0.3, zt + 6.7), 'steeldk')
        q2 = p0 + d * (s + 12.0) - nrm * (hw - 0.6)
        f.cyl((q2.x, q2.y, zt - 0.05), (q2.x, q2.y, zt + 0.7), 0.25, n=10, mat='steeldk'); f.cyl((q2.x, q2.y, zt + 0.7), (q2.x, q2.y, zt + 0.82), 0.33, n=10, mat='steeldk')
        s += 40.0
    q = p1
    f.cyl((q.x, q.y, zt - 0.1), (q.x, q.y, zt + 1.0), 2.0, n=16, mat='concrete')
    f.cyl((q.x, q.y, zt + 1.0), (q.x, q.y, zt + 9.0), 1.25, 1.0, n=16, mat='teal')
    for zb in (zt + 3.0, zt + 6.0):
        f.cyl((q.x, q.y, zb), (q.x, q.y, zb + 1.0), 1.2, 1.1, n=16, mat='white', caps=(False, False))
    f.cyl((q.x, q.y, zt + 9.0), (q.x, q.y, zt + 9.2), 1.6, n=16, mat='steeldk')
    f.cyl((q.x, q.y, zt + 9.2), (q.x, q.y, zt + 10.6), 0.7, n=12, mat='lhglass'); f.cyl((q.x, q.y, zt + 10.6), (q.x, q.y, zt + 11.4), 0.85, 0.15, n=12, mat='teal')
    _rail(f, [(q.x + 1.5 * math.cos(k / 12 * math.tau), q.y + 1.5 * math.sin(k / 12 * math.tau)) for k in range(13)], zt + 9.2, 0.9, 'white', 0.8, 0.03)
    props = gobj('PORT_bwE_props', f, coll, bevel=0.02, props={'qa_kind': 'prop'})
    return dict(cap=cap, core=core, rocks=rocks, props=props)




# ------------------------------------------------------------------------------------------------------------------------------ lighthouse
def _tube_ring(g, z0, z1, r_out, r_in, mat, n=64):
    o = []; i = []
    for k in range(n):
        a = k / n * math.tau; c, s = math.cos(a), math.sin(a)
        o += [(c * r_out, s * r_out, z0), (c * r_out, s * r_out, z1)]; i += [(c * r_in, s * r_in, z0), (c * r_in, s * r_in, z1)]
    b = g.add(o + i, [], mat); m = 2 * n
    for k in range(n):
        j = (k + 1) % n
        g.F += [(b + 2 * k, b + 2 * j, b + 2 * j + 1, b + 2 * k + 1), (b + m + 2 * k, b + m + 2 * k + 1, b + m + 2 * j + 1, b + m + 2 * j),
                (b + 2 * k + 1, b + 2 * j + 1, b + m + 2 * j + 1, b + m + 2 * k + 1), (b + 2 * k, b + m + 2 * k, b + m + 2 * j, b + 2 * j)]
        g.M += [mat] * 4; g.S += [True, True, False, False]


def build_lighthouse(coll):
    cx, cy = LH_C; L = {}
    # LH_base: the stone drum (r 15, z 5..27, nothing beyond r 15.3 in that band), mooring rings flush, cornice + parapet above z 27
    g = Geo(); zt = LH_TOPZ - BW_Z
    g.cyl((0, 0, -0.6), (0, 0, zt + 0.3), LH_R, n=96, mat='bastion', caps=(True, True))
    for k in range(6):
        a = (k + 0.5) / 6 * math.tau; c, s_ = math.cos(a), math.sin(a); T = Vector((-s_, c, 0.0)); Nn = Vector((c, s_, 0.0))
        g.box((c * (LH_R - 0.03), s_ * (LH_R - 0.03), 2.35), (0.12, 0.34, 0.34), 'steeldk', Euler((0, 0, a)).to_matrix())
        ring = [tuple(Nn * (LH_R + 0.09) + T * (0.42 * math.sin(q / 12 * math.tau)) + Vector((0, 0, 1.85 - 0.42 * math.cos(q / 12 * math.tau)))) for q in range(13)]
        g.tube(ring, 0.06, n=5, mat='steeldk', caps=False)
    _tube_ring(g, zt, zt + 0.6, LH_R + 0.55, LH_R - 1.2, 'bastion', 96)
    _tube_ring(g, zt + 0.55, zt + 1.7, LH_R + 0.25, LH_R - 0.45, 'bastion', 96)
    for k in range(28):
        a = k / 28 * math.tau
        g.box((math.cos(a) * (LH_R - 0.1), math.sin(a) * (LH_R - 0.1), zt + 1.98), (0.62, 1.25, 0.6), 'bastion', Euler((0, 0, a)).to_matrix())
    g.blh((6.6, -3.0, zt - 0.05), (11.8, 3.0, zt + 3.1), 'white'); g.blh((6.3, -3.3, zt + 3.1), (12.1, 3.3, zt + 3.45), 'lhdome')
    g.blh((6.5, -0.7, zt + 0.2), (6.62, 0.7, zt + 2.4), 'lhdark'); g.blh((8.3, -3.08, zt + 1.1), (10.1, -2.98, zt + 2.3), 'glass')
    g.cyl((10.6, 1.8, zt + 3.4), (10.6, 1.8, zt + 4.5), 0.3, n=8, mat='bastion')
    base = obj('LH_base', g.mesh('LH_base'), coll, (cx, cy, BW_Z), bevel=0.04, props={'qa_kind': 'lh', 'crack': 0.0, 'zoff': BW_Z})
    # LH_mid: the lower half of the red/white tower, pivot at its foot on the drum top (z 27)
    def r_at(zw): return TW_R0 + (TW_R1 - TW_R0) * (zw - TW_Z0) / TW_H
    hm = TW_H * 0.5; zj = TW_Z0 + hm
    m = Geo(); m.cyl((0, 0, -1.2), (0, 0, hm), r_at(TW_Z0 - 1.2), r_at(zj), n=56, mat='tower')
    m.cyl((0, 0, -1.1), (0, 0, 0.8), TW_R0 + 0.38, TW_R0 + 0.32, n=56, mat='bastion')
    mid = obj('LH_mid', m.mesh('LH_mid'), coll, (0, 0, TW_Z0 - BW_Z), parent=base, props={'qa_kind': 'lh', 'crack': 0.0, 'zoff': TW_Z0})
    # LH_top: upper tower, gallery, lantern, dome, vane (pivot at the mid joint)
    t = Geo(); h = TW_H * 0.5
    t.cyl((0, 0, -0.1), (0, 0, h + 0.1), r_at(zj - 0.1), TW_R1, n=56, mat='tower')
    t.cyl((0, 0, -0.06), (0, 0, 0.6), r_at(zj) + 0.3, r_at(zj) + 0.25, n=56, mat='tower')
    t.cyl((0, 0, h - 0.6), (0, 0, h + 0.05), TW_R1 + 0.05, TW_R1 + 0.6, n=56, mat='white')
    for k in range(16):
        a = k / 16 * math.tau; c, s_ = math.cos(a), math.sin(a)
        t.beam((c * (TW_R1 - 0.1), s_ * (TW_R1 - 0.1), h - 1.6), (c * 5.2, s_ * 5.2, h - 0.02), 0.22, 0.3, 'white')
    t.cyl((0, 0, h), (0, 0, h + 0.45), 5.45, n=56, mat='lhdark')
    posts = [(math.cos(k / 44 * math.tau) * 5.25, math.sin(k / 44 * math.tau) * 5.25) for k in range(45)]
    _rail(t, posts, h + 0.45, 1.15, 'white', 0.75, 0.035)
    t.cyl((0, 0, h + 0.4), (0, 0, h + 1.4), 2.75, n=40, mat='lhdark')
    t.cyl((0, 0, h + 1.4), (0, 0, h + 4.4), 2.55, n=40, mat='lhglass', caps=(False, False))
    for k in range(12):
        a = k / 12 * math.tau
        t.box((math.cos(a) * 2.58, math.sin(a) * 2.58, h + 2.9), (0.14, 0.16, 3.1), 'lhdark', Euler((0, 0, a)).to_matrix())
    t.cyl((0, 0, h + 2.85), (0, 0, h + 2.95), 2.62, n=40, mat='lhdark', caps=(False, False))
    t.cyl((0, 0, h + 4.4), (0, 0, h + 4.7), 2.95, n=40, mat='lhdark')
    t.cyl((0, 0, h + 4.65), (0, 0, h + 6.4), 2.85, 0.45, n=40, mat='lhdome')
    t.sphere((0, 0, h + 6.85), 0.5, 'lhdark', 12, 8)
    t.cyl((0, 0, h + 7.3), (0, 0, h + 9.2), 0.06, n=6, mat='lhdark')
    t.beam((-0.9, 0, h + 8.4), (0.9, 0, h + 8.4), 0.05, 0.05, 'lhdark'); t.blh((0.5, -0.02, h + 8.5), (1.2, 0.02, h + 8.9), 'lhdome')
    t.cyl((0, 0, h + 1.35), (0, 0, h + 1.95), 0.45, n=16, mat='steeldk')
    top = obj('LH_top', t.mesh('LH_top'), coll, (0, 0, hm), parent=mid, props={'qa_kind': 'lh', 'crack': 0.0, 'zoff': zj})
    # LH_lamp (prop beam 0..1.5) and the rotating double beam cone LH_beam (driven)
    lm = Geo(); lm.cyl((0, 0, -0.8), (0, 0, 0.8), 1.0, n=20, mat='lamp'); lm.cyl((0, 0, -1.05), (0, 0, -0.8), 1.1, n=20, mat='steeldk')
    zl = h + 1.4 + 1.5
    lamp = obj('LH_lamp', lm.mesh('LH_lamp'), coll, (0, 0, zl), parent=top, props={'qa_kind': 'lh', 'beam': 0.0, 'beam_speed': 3.0})
    bg = Geo()
    for s in (-1.0, 1.0):
        bg.cyl((s * 1.1, 0, 0), (s * 240.0, 0, 0), 0.8, 0.8 + 0.07 * 240.0, n=20, mat='beam', caps=(False, False))
    beam = obj('LH_beam', bg.mesh('LH_beam'), coll, (0, 0, 0), parent=lamp, props={'qa_kind': 'fx', 'beam': 0.0})
    beam.visible_shadow = False
    fc = beam.driver_add('["beam"]'); dv = fc.driver; dv.type = 'SCRIPTED'
    v = dv.variables.new(); v.name = 'b'; v.type = 'SINGLE_PROP'; v.targets[0].id = lamp; v.targets[0].data_path = '["beam"]'; dv.expression = 'b'
    fc = beam.driver_add('rotation_euler', 2); dv = fc.driver; dv.type = 'SCRIPTED'
    v = dv.variables.new(); v.name = 'spd'; v.type = 'SINGLE_PROP'; v.targets[0].id = lamp; v.targets[0].data_path = '["beam_speed"]'
    dv.expression = 'frame * spd * 0.0174533'
    L.update(base=base, mid=mid, top=top, lamp=lamp, beam=beam)
    return L


# ------------------------------------------------------------------------------------------------------------------------------ API
def cut_sea(sea, hole=None):
    """Re-mesh the shared sea quad as a frame around the dry dock basin so the dock stays dry (the hole edges hide inside the
    caisson and the dock walls). Call once after build() and after EV.sea(). Idempotent."""
    if sea is None or sea.get('port_cut'): return sea
    hx0, hx1, hy0, hy1 = hole or (DX0, DX1, DY0 + 3.5, DY1)
    me = sea.data; Mi = sea.matrix_world.inverted()
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; z = me.vertices[0].co.z
    X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)
    hl = [Mi @ Vector((x, y, 0.0)) for x, y in ((hx0, hy0), (hx1, hy0), (hx1, hy1), (hx0, hy1))]
    V = [(X0, Y0, z), (X1, Y0, z), (X1, Y1, z), (X0, Y1, z)] + [(p.x, p.y, z) for p in hl]
    F = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    new = D.meshes.new(me.name + '_portcut'); new.from_pydata(V, [], F)
    for m in me.materials: new.materials.append(m)
    new.update(); sea.data = new; sea['port_cut'] = 1
    return sea


def set_crack(P, v, frame=None):
    for k in ('base', 'mid', 'top'):
        o = P['lighthouse'][k]; o['crack'] = float(v)
        if frame is not None: o.keyframe_insert('["crack"]', frame=frame)


def set_beam(P, v, frame=None):
    o = P['lighthouse']['lamp']; o['beam'] = float(v)
    if frame is not None: o.keyframe_insert('["beam"]', frame=frame)


def build(parent_collection=None, **opts):
    """Build the whole port. opts: seed (int, default 7); sea (the SEA object to cut, default: the object named 'SEA' if present);
    cut_sea (bool, default True); tetrapods (bool, default True); far_ink (ink weight of the far town/trees/hills, default 0.3).
    Returns a dict: collection, terrain, quay, quay_props, dock, dock_blocks, caisson, railcranes, dock_rails, cranes (4 dicts) and
    craneA {legs, boom, trolley, cab, spreader, ropes}, containers, straddles, trucks, masts, containers_near_A, buildings, houses, trees,
    pier, boats (root empties PORT_boat_0..7), bw {cap, crown, core, rocks, props}, bwE {cap, core, rocks, props}, tetrapods,
    lighthouse {base, mid, top, lamp, beam}, info. Everything is named PORT_* / LH_*."""
    t0 = time.time(); R = random.Random(opts.get('seed', 7))
    textures(); materials(opts.get('far_ink'))
    root = EV.coll('PORT', parent_collection)
    C = {k: EV.coll('PORT_' + k, root) for k in ('ground', 'dock', 'cranes', 'yard', 'buildings', 'town', 'boats', 'breakwater', 'lighthouse')}
    P = {'collection': root}
    P['terrain'] = build_terrain(C['ground'])
    P['quay'], P['quay_props'] = build_quay(C['ground'])
    P['dock'], P['dock_blocks'], P['caisson'] = build_dock(C['dock'])
    P['railcranes'], P['dock_rails'] = build_railcranes(C['dock'])
    cm = crane_meshes()
    P['cranes'] = build_cranes(C['cranes'], cm); P['craneA'] = P['cranes'][0]
    conts, slots, CM = build_containers(C['yard'], R)
    yard = build_yard(C['yard'], R, conts, slots, CM)
    P['containers'] = conts; P.update(yard)
    ca = Vector((CRANE_X[0], 430.0, 4.0))
    P['containers_near_A'] = sorted([o for o in conts if o.parent is None and (o.location - ca).length < 70.0], key=lambda o: (o.location - ca).length)
    P['buildings'] = build_buildings(C['buildings'])
    P['houses'], P['trees'] = build_town(C['town'], R)
    P['pier'] = build_pier(C['boats'], R)
    P['boats'] = build_boats(C['boats'], R)
    RM = rock_meshes(R)
    P['bw'] = build_west_breakwater(C['breakwater'], R, RM)
    P['bwE'] = build_east_breakwater(C['breakwater'], R, RM)
    dg = bpy.context.evaluated_depsgraph_get(); avoid = []
    for k in ('crown', 'cap', 'rocks'):
        o = P['bw'][k]; me = o.data
        avoid.append(BVHTree.FromPolygons([tuple(o.matrix_world @ v.co) for v in me.vertices], [tuple(p.vertices) for p in me.polygons], all_triangles=False, epsilon=0.0))
    P['tetrapods'] = build_tetrapods(C['breakwater'], R, avoid) if opts.get('tetrapods', True) else []
    P['lighthouse'] = build_lighthouse(C['lighthouse'])
    sea = opts.get('sea', D.objects.get('SEA'))
    if sea is not None and opts.get('cut_sea', True): cut_sea(sea)
    P['info'] = dict(lighthouse_centre=(LH_C[0], LH_C[1]), bastion_radius=LH_R, bastion_z=(BW_Z, LH_TOPZ), tower=(TW_Z0, TW_Z0 + TW_H, TW_R0, TW_R1),
                     head_radius=HEAD_R, cap_width=BW_W, toe_west=TOE_W, toe_east=TOE_E, toe_head=TOE_H, seabed=SEABED,
                     craneA_hinge=(CRANE_X[0], (RAIL_W + RAIL_L) / 2 + HINGE[1], QZ + HINGE[2]), build_s=round(time.time() - t0, 1))
    print('PORT build %.1fs' % (time.time() - t0))
    return P


def all_objects(P):
    out = []
    for c in P['collection'].children_recursive: out += list(c.objects)
    return out


def _root(o):
    while o.parent is not None: o = o.parent
    return o


def qa_allow(a, b):
    ka, kb = a.get('qa_kind', ''), b.get('qa_kind', '')
    if 'fx' in (ka, kb): return True
    if ka == 'ground' and kb == 'ground': return True
    if 'ground' in (ka, kb):
        o = b if ka == 'ground' else a; g = a if ka == 'ground' else b; ko = o.get('qa_kind', '')
        if ko in ('prop', 'building', 'house', 'tree', 'crane', 'lh'): return True
        if ko == 'tetra' and g.name == 'PORT_bw_core': return True
        return False
    ra, rb = _root(a), _root(b)
    return ra is rb


def qa(P, tile=60.0, verbose=False):
    """QA.overlaps on spatial tiles (non-ground objects), plus boats/containers/tetrapods against the ground they must not enter."""
    import qa as QA
    objs = [o for o in all_objects(P) if o.type == 'MESH' and o.get('qa_kind', '') not in ('ground', 'fx')]
    dg = bpy.context.evaluated_depsgraph_get(); tiles = {}
    for o in objs:
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        x0, x1 = min(v.x for v in bb), max(v.x for v in bb); y0, y1 = min(v.y for v in bb), max(v.y for v in bb)
        for i in range(int(x0 // tile), int(x1 // tile) + 1):
            for j in range(int(y0 // tile), int(y1 // tile) + 1): tiles.setdefault((i, j), []).append(o)
    bad = {}
    for key, lst in tiles.items():
        if len(lst) < 2: continue
        for a, b, n in QA.overlaps(lst, allow=qa_allow, dg=dg):
            bad[tuple(sorted((a, b)))] = n
    ground = [P['quay'], P['pier'], P['bw']['cap'], P['bw']['crown'], P['dock'], P['caisson']]
    boats = [o for o in all_objects(P) if o.get('qa_kind') == 'boat']
    gb = QA.overlaps(boats, ground, dg=dg)
    tet = QA.overlaps(P['tetrapods'], [P['bw']['cap'], P['bw']['crown'], P['bw']['rocks']], dg=dg) if P['tetrapods'] else []
    return dict(pairs=sorted(bad.items()), boats_vs_ground=gb, tetra_vs_cap=tet, n_objects=len(objs), n_tiles=len(tiles))
