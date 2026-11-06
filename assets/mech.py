# ANCHOR / MECH department: unit 07, the 80 m harbour labour mech, its rig and pose API.
#   M = build(coll)            -> dict (see build() docstring for every key)
#   set_pose(M, pose) / leg_ik(M, side, foot_pos, foot_yaw) / arm_ik(M, side, hand_pos, pole) / key_pose(M, frame) / POSES
# Textures are generated with PIL by the system python: `python assets/mech.py --tex` (build() does it if they are missing).
import os, sys, math, random, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
TEX = os.path.join(ROOT, 'tex')
PY = os.environ.get('ANCHOR_PY', 'python')   # Python 3.13 with numpy + opencv, outside Blender
FONTS = r'C:\Windows\Fonts'
TEXFILES = ('mech_panel.png', 'mech_fine.png', 'mech_07.png', 'mech_dock3.png', 'mech_unit.png', 'mech_warn.png')


# ====================================================================================================================== textures (PIL)
def make_textures():
    """Panel atlas (seams, bolts, hatches, louvres, stencil words, hazard ticks, rivet rows, chips), a finer close-up sheet, and the
    stencil decals. RGB = detail colour, A = coverage. Everything tiles (drawn with wrap-around)."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
    import numpy as np
    os.makedirs(TEX, exist_ok=True)
    INK = (42, 34, 54)

    def font(name, size):
        return ImageFont.truetype(os.path.join(FONTS, name), size)

    class Wrap:
        """Draw on an RGBA canvas with wrap-around at the borders (so the sheet tiles)."""
        def __init__(s, size):
            s.S = size; s.im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); s.d = ImageDraw.Draw(s.im)
        def _offs(s, box):
            x0, y0, x1, y1 = box; out = [(0, 0)]
            for dx in (-s.S, s.S):
                if (dx < 0 and x1 > s.S) or (dx > 0 and x0 < 0): out.append((dx, 0))
            for dy in (-s.S, s.S):
                if (dy < 0 and y1 > s.S) or (dy > 0 and y0 < 0): out += [(ox, dy) for ox, _ in list(out)]
            return out
        def rect(s, b, fill=None, outline=None, width=1):
            for ox, oy in s._offs(b): s.d.rectangle((b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy), fill=fill, outline=outline, width=width)
        def rrect(s, b, r, fill=None, outline=None, width=1):
            for ox, oy in s._offs(b): s.d.rounded_rectangle((b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy), r, fill=fill, outline=outline, width=width)
        def ell(s, b, fill=None, outline=None, width=1):
            for ox, oy in s._offs(b): s.d.ellipse((b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy), fill=fill, outline=outline, width=width)
        def line(s, pts, fill, width):
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            for ox, oy in s._offs((min(xs), min(ys), max(xs), max(ys))): s.d.line([(x + ox, y + oy) for x, y in pts], fill=fill, width=width)
        def poly(s, pts, fill):
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            for ox, oy in s._offs((min(xs), min(ys), max(xs), max(ys))): s.d.polygon([(x + ox, y + oy) for x, y in pts], fill=fill)
        def text(s, xy, t, f, fill):
            b = s.d.textbbox(xy, t, font=f)
            for ox, oy in s._offs(b): s.d.text((xy[0] + ox, xy[1] + oy), t, font=f, fill=fill)

    def seam(W, b, w):
        x0, y0, x1, y1 = b
        W.rect((x0, y0, x1, y1), outline=INK + (215,), width=w)                          # the groove
        W.line([(x0 + w, y1 + w * 0.6), (x1 + w * 0.6, y1 + w * 0.6)], (255, 255, 255, 120), max(1, w // 2))   # lit lip under it
        W.line([(x1 + w * 0.6, y0 + w), (x1 + w * 0.6, y1 + w * 0.6)], (255, 255, 255, 90), max(1, w // 2))

    def bolt(W, x, y, r):
        W.ell((x - r - 1, y - r - 1, x + r + 1, y + r + 1), fill=INK + (225,))
        W.ell((x - r * 0.55, y - r * 0.75, x + r * 0.35, y + r * 0.15), fill=(255, 250, 235, 170))

    # ---------------------------------------------------------------- the big panel atlas
    S = 2048; R = random.Random(4242); W = Wrap(S)
    leaves = []
    def split(x, y, w, h, d):
        if d < 6 and (w > 170 or h > 170) and (d < 2 or R.random() < 0.82):
            if w > h * R.uniform(0.8, 1.25):
                k = R.uniform(0.3, 0.7) * w; split(x, y, k, h, d + 1); split(x + k, y, w - k, h, d + 1)
            else:
                k = R.uniform(0.3, 0.7) * h; split(x, y, w, k, d + 1); split(x, y + k, w, h - k, d + 1)
        else: leaves.append((x, y, w, h, d))
    split(0, 0, S, S, 0)
    for (x, y, w, h, d) in leaves:                                   # tonal blocks: no two neighbouring panels quite the same paint
        r = R.random()
        if r < 0.28: W.rect((x, y, x + w, y + h), fill=(52, 46, 92, R.randint(22, 52)))
        elif r < 0.5: W.rect((x, y, x + w, y + h), fill=(255, 255, 245, R.randint(22, 55)))
        elif r < 0.58: W.rect((x, y, x + w, y + h), fill=(150, 80, 40, R.randint(25, 45)))
    WORDS = ['07', 'A-07', 'HYD 2', 'NO STEP', 'LIFT', 'DK-3', 'P-14', '24V', 'OIL', 'H-21', 'R-07', 'S-40', 'VENT', 'DRAIN', 'HA-7']
    for (x, y, w, h, d) in leaves:
        seam(W, (x, y, x + w, y + h), 7 if d < 3 else 5)
    for (x, y, w, h, d) in leaves:
        m = 20; iw, ih = w - 2 * m, h - 2 * m
        if iw < 40 or ih < 40: continue
        r = R.random()
        if r < 0.36:
            br = R.uniform(6.5, 9.5)
            pts = [(x + m, y + m), (x + w - m, y + m), (x + m, y + h - m), (x + w - m, y + h - m)]
            if w > 300: pts += [(x + w / 2, y + m), (x + w / 2, y + h - m)]
            if h > 300: pts += [(x + m, y + h / 2), (x + w - m, y + h / 2)]
            for p in pts: bolt(W, p[0], p[1], br)
        elif r < 0.52 and iw > 120 and ih > 90:
            ins = R.uniform(24, 48)
            W.rrect((x + ins, y + ins, x + w - ins, y + h - ins), 12, fill=(40, 36, 74, 70))
            W.rrect((x + ins, y + ins, x + w - ins, y + h - ins), 12, outline=INK + (200,), width=4)
            if R.random() < 0.6: W.rect((x + w / 2 - 26, y + ins + 12, x + w / 2 + 26, y + ins + 22), fill=(235, 232, 220, 210))
        elif r < 0.66 and iw > 110:
            n = R.randint(3, 7); vw = min(iw * 0.7, 200); vh = 11; gap = 24
            vy = y + h / 2 - n * gap / 2
            for i in range(n):
                if gap * i > ih - 20: break
                W.rect((x + w / 2 - vw / 2, vy + i * gap, x + w / 2 + vw / 2, vy + i * gap + vh), fill=(30, 28, 50, 235))
                W.rect((x + w / 2 - vw / 2, vy + i * gap + vh, x + w / 2 + vw / 2, vy + i * gap + vh + 3), fill=(255, 255, 255, 150))
        elif r < 0.8 and iw > 150:
            word = R.choice(WORDS); hh = R.randint(30, 52)
            f = font(R.choice(['STENCIL.TTF', 'bahnschrift.ttf', 'AGENCYB.TTF', 'impact.ttf']), hh)
            W.text((x + m + 6, y + m + 2), word, f, INK + (205,))
            if R.random() < 0.5: W.rect((x + m + 6, y + m + hh + 14, x + m + 6 + R.uniform(50, 140), y + m + hh + 19), fill=INK + (190,))
        elif r < 0.88 and iw > 150:
            col = (216, 64, 47, 225) if R.random() < 0.5 else INK + (215,)
            n = R.randint(3, 7); tw, th = 22, 36; sx, sy = x + m + 4, y + h - m - th
            for i in range(n):
                W.poly([(sx + i * tw * 1.6, sy + th), (sx + i * tw * 1.6 + tw, sy + th), (sx + i * tw * 1.6 + tw * 1.7, sy), (sx + i * tw * 1.6 + tw * 0.7, sy)], col)
        elif r < 0.94:
            cx, cy = x + w / 2, y + h / 2
            for k in (-1, 1):
                W.ell((cx + k * 26 - 15, cy - 15, cx + k * 26 + 15, cy + 15), fill=INK + (215,))
                W.ell((cx + k * 26 - 7, cy - 9, cx + k * 26 + 3, cy + 1), fill=(255, 255, 255, 110))
    for i in range(18):                                              # long weld seams across panels
        x, y, L = R.uniform(0, S), R.uniform(0, S), R.uniform(260, 900)
        if i % 2: W.line([(x, y), (x + L, y)], INK + (170,), 3)
        else: W.line([(x, y), (x, y + L)], INK + (170,), 3)
    for i in range(30):                                              # rivet rows
        x, y, n, st, dx = R.uniform(0, S), R.uniform(0, S), R.randint(6, 16), R.uniform(28, 44), R.random() < 0.5
        for k in range(n): bolt(W, x + (k * st if dx else 0), y + (0 if dx else k * st), 5.5)
    for i in range(5200):                                            # chips, specks, scratches
        s = R.uniform(1.5, 4.5); x, y = R.uniform(0, S), R.uniform(0, S)
        W.rect((x, y, x + s, y + s * R.uniform(0.6, 1.8)), fill=(40, 36, 60, 150) if R.random() < 0.6 else (255, 255, 250, 140))
    for i in range(260):
        x, y, L, a = R.uniform(0, S), R.uniform(0, S), R.uniform(20, 90), R.uniform(0, math.pi)
        W.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], (255, 255, 250, 110), 2)
    W.im.save(os.path.join(TEX, 'mech_panel.png'))

    # ---------------------------------------------------------------- the fine close-up sheet (rebuilt 06.11)
    # Small plates from ONE recursive split, so no two overlap and the seams meet in T-joints; per plate a bolt row along its
    # top edge or a rivet frame inside its border (or nothing); scratches and specks. No words and no labels: the first
    # sheet scattered 40 overlapping frames, 70 rivet rows crossing everything, 26 tags and 14 warning plates at random, so
    # tags lay over plates and plates over the big stencils (UNIT 07 over a plate in s24), and box-projected on the round
    # head and torso they ghosted as doubled half-transparent labels. Words live on the big atlas (inside its panels) and in
    # the stencils.
    S = 1024; R = random.Random(77); W = Wrap(S)
    fl = []
    def fsplit(x, y, w, h, d):
        if d < 6 and (w > 150 or h > 150) and (d < 2 or R.random() < 0.85):
            if w > h * R.uniform(0.8, 1.25):
                k = R.uniform(0.32, 0.68) * w; fsplit(x, y, k, h, d + 1); fsplit(x + k, y, w - k, h, d + 1)
            else:
                k = R.uniform(0.32, 0.68) * h; fsplit(x, y, w, k, d + 1); fsplit(x, y + k, w, h - k, d + 1)
        else: fl.append((x, y, w, h))
    fsplit(0, 0, S, S, 0)
    for (x, y, w, h) in fl:
        W.rect((x, y, x + w, y + h), outline=INK + (150,), width=3)
    for (x, y, w, h) in fl:
        r = R.random()
        if r < 0.5 and w > 70:                                       # a bolt row along the top edge
            n = max(2, int(round((w - 28) / 34.0)) + 1)
            for k in range(n): bolt(W, x + 14 + (w - 28) * k / (n - 1), y + 11, 4.2)
        elif r < 0.78 and w > 70 and h > 70:                         # a rivet frame inside the border
            nx = max(2, int(round((w - 24) / 20.0)) + 1); ny = max(2, int(round((h - 24) / 20.0)) + 1)
            for k in range(nx):
                px = x + 12 + (w - 24) * k / (nx - 1); bolt(W, px, y + 12, 3.2); bolt(W, px, y + h - 12, 3.2)
            for k in range(1, ny - 1):
                py = y + 12 + (h - 24) * k / (ny - 1); bolt(W, x + 12, py, 3.2); bolt(W, x + w - 12, py, 3.2)
    for i in range(1500):
        x, y, L, a = R.uniform(0, S), R.uniform(0, S), R.uniform(6, 40), R.uniform(0, math.pi)
        W.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], (255, 255, 250, 120) if R.random() < 0.6 else INK + (120,), 1)
    for i in range(3000):
        s = R.uniform(1, 3); x, y = R.uniform(0, S), R.uniform(0, S)
        W.rect((x, y, x + s, y + s), fill=(40, 36, 60, 140) if R.random() < 0.5 else (255, 255, 250, 130))
    W.im.save(os.path.join(TEX, 'mech_fine.png'))

    # ---------------------------------------------------------------- stencil decals: white glyphs on clear, distressed by paint loss
    def distress(im, seed, amt=0.42, scale=7):
        a = np.asarray(im.split()[3]).astype(np.float32) / 255.0
        h, w = a.shape; rng = np.random.default_rng(seed)
        acc = np.zeros((h, w), np.float32)
        for k, (cell, wt) in enumerate(((scale * 9, 0.55), (scale * 3, 0.3), (scale, 0.15))):
            g = rng.random((h // cell + 3, w // cell + 3)).astype(np.float32)
            gi = Image.fromarray((g * 255).astype(np.uint8)).resize((w + 2 * cell, h + 2 * cell), Image.BICUBIC)
            acc += np.asarray(gi).astype(np.float32)[cell:cell + h, cell:cell + w] / 255.0 * wt
        keep = (acc > amt * 0.82).astype(np.float32)
        a = a * keep
        out = Image.new('RGBA', (w, h), (255, 255, 255, 0)); out.putalpha(Image.fromarray((a * 255).astype(np.uint8)))
        return out

    def decal(name, lines, size, seed, pad=24, frame=False, amt=0.42):
        w, h = size; im = Image.new('RGBA', (w, h), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
        for (txt, fn, hh, y, align) in lines:
            f = font(fn, hh); b = d.textbbox((0, 0), txt, font=f); tw = b[2] - b[0]
            x = (w - tw) / 2 - b[0] if align == 'c' else pad - b[0]
            d.text((x, y - b[1]), txt, font=f, fill=(255, 255, 255, 255))
        if frame:
            d.rectangle((6, 6, w - 7, h - 7), outline=(255, 255, 255, 255), width=10)
        distress(im, seed, amt).save(os.path.join(TEX, name))
    decal('mech_07.png', [('07', 'STENCIL.TTF', 700, 40, 'c')], (1024, 800), 7, amt=0.40)
    decal('mech_unit.png', [('UNIT 07', 'STENCIL.TTF', 150, 30, 'c')], (1024, 220), 11, amt=0.36)
    # DOCK 3 / HARBOR AUTHORITY: big letters, a rule, the small line, a hazard bar
    w, h = 2048, 1100; im = Image.new('RGBA', (w, h), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
    f1 = font('STENCIL.TTF', 430); f2 = font('bahnschrift.ttf', 150); f3 = font('bahnschrift.ttf', 54)
    b = d.textbbox((0, 0), 'DOCK 3', font=f1); d.text(((w - (b[2] - b[0])) / 2 - b[0], 40 - b[1]), 'DOCK 3', font=f1, fill=(255, 255, 255, 255))
    d.rectangle((90, 560, w - 90, 585), fill=(255, 255, 255, 255))
    b = d.textbbox((0, 0), 'HARBOR AUTHORITY', font=f2); d.text(((w - (b[2] - b[0])) / 2 - b[0], 640 - b[1]), 'HARBOR AUTHORITY', font=f2, fill=(255, 255, 255, 255))
    b = d.textbbox((0, 0), 'HIGH HARBOR PORT WORKS  -  LIFT CLASS 400 T  -  SERIAL HA-07', font=f3)
    d.text(((w - (b[2] - b[0])) / 2 - b[0], 860 - b[1]), 'HIGH HARBOR PORT WORKS  -  LIFT CLASS 400 T  -  SERIAL HA-07', font=f3, fill=(255, 255, 255, 255))
    for i in range(16):
        x = 90 + i * 118; d.polygon([(x, 1060), (x + 60, 1060), (x + 110, 980), (x + 50, 980)], fill=(255, 255, 255, 255))
    distress(im, 3, 0.38).save(os.path.join(TEX, 'mech_dock3.png'))
    # warning plate: triangle + DANGER / HIGH VOLTAGE (white = paint, the shader colours it)
    w, h = 1024, 512; im = Image.new('RGBA', (w, h), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
    d.polygon([(40, 470), (230, 60), (420, 470)], fill=(255, 255, 255, 255))
    d.polygon([(250, 150), (205, 300), (245, 300), (200, 430), (300, 260), (255, 260), (290, 150)], fill=(255, 255, 255, 0))
    f = font('impact.ttf', 150); d.text((470, 60), 'DANGER', font=f, fill=(255, 255, 255, 255))
    f = font('bahnschrift.ttf', 86); d.text((474, 270), 'HIGH VOLTAGE', font=f, fill=(255, 255, 255, 255)); d.text((474, 370), 'KEEP OFF', font=f, fill=(255, 255, 255, 255))
    distress(im, 21, 0.33).save(os.path.join(TEX, 'mech_warn.png'))
    print('mech textures written to', TEX)


if __name__ == '__main__' and '--tex' in sys.argv:
    make_textures(); sys.exit(0)

try:
    import bpy, bmesh
    from mathutils import Vector, Matrix, Euler, Quaternion
    from mathutils.bvhtree import BVHTree
    sys.path.insert(0, os.path.join(ROOT, 'kit'))
    import look as LK
except ImportError:            # system python (texture generation only)
    bpy = None

PI = math.pi
D2R = PI / 180.0


# ====================================================================================================================== geometry kit
class Geo:
    """Vertex/face soup with per-face material slots. Everything is built in REST WORLD coordinates (metres, mech facing -Y)."""
    __slots__ = ('v', 'f', 'm')

    def __init__(s): s.v = []; s.f = []; s.m = []

    def add(s, vf, mat=0, M=None):
        v, f = vf; o = len(s.v)
        if M is not None: v = [M @ Vector(p) for p in v]
        s.v.extend((p[0], p[1], p[2]) for p in v)
        s.f.extend(tuple(i + o for i in q) for q in f)
        s.m.extend([mat] * len(f))
        return s

    def merge(s, g, mat=None):
        o = len(s.v); s.v.extend(g.v); s.f.extend(tuple(i + o for i in q) for q in g.f)
        s.m.extend(g.m if mat is None else [mat] * len(g.f)); return s

    def mirrored(s):
        g = Geo(); g.v = [(-x, y, z) for (x, y, z) in s.v]; g.f = [tuple(reversed(q)) for q in s.f]; g.m = list(s.m); return g

    def ntris(s): return sum(len(q) - 2 for q in s.f)


def G(*parts):
    """G((vf, mat), (vf, mat), ...) -> Geo"""
    g = Geo()
    for p in parts:
        if isinstance(p, Geo): g.merge(p)
        elif len(p) == 2 and isinstance(p[1], int): g.add(p[0], p[1])
        else: g.add(p, 0)
    return g


def hull(pts):
    bm = bmesh.new()
    for p in pts: bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=list(bm.verts))
    kill = list({id(x): x for x in res['geom_interior'] + res['geom_unused'] if isinstance(x, bmesh.types.BMVert) and x.is_valid}.values())
    if kill: bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bmesh.ops.dissolve_limit(bm, angle_limit=0.6 * D2R, verts=list(bm.verts), edges=list(bm.edges))
    bm.verts.index_update()
    v = [tuple(x.co) for x in bm.verts]; f = [tuple(x.index for x in fc.verts) for fc in bm.faces]
    bm.free(); return v, f


_ADJ = {0: (1, 3, 4), 1: (0, 2, 5), 2: (1, 3, 6), 3: (0, 2, 7), 4: (5, 7, 0), 5: (4, 6, 1), 6: (5, 7, 2), 7: (4, 6, 3)}


def chex(corners, ch=0.15):
    """Chamfered convex hexahedron from 8 corners (bottom ring b0..b3 then top ring t0..t3, same order)."""
    pts = []
    for i, c in enumerate(corners):
        c = Vector(c)
        for j in _ADJ[i]:
            d = Vector(corners[j]) - c; L = d.length
            pts.append(c + d * min(ch / max(L, 1e-6), 0.45))
    return hull(pts)


def box(x0, x1, y0, y1, z0, z1, ch=0.15, top=None):
    """Axis box by bounds, chamfered. top = (x0, x1, y0, y1) of the top face (taper/shear)."""
    tx0, tx1, ty0, ty1 = top or (x0, x1, y0, y1)
    return chex([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (tx0, ty0, z1), (tx1, ty0, z1), (tx1, ty1, z1), (tx0, ty1, z1)], ch)


def obox(c, X, Y, Z, hx, hy, hz, ch=0.1, taper=1.0):
    """Oriented chamfered box: centre c, unit axes X Y Z, half sizes; taper scales the +Z face."""
    c = Vector(c); X = Vector(X); Y = Vector(Y); Z = Vector(Z); pts = []
    for sz, k in ((-1, 1.0), (1, taper)):
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts.append(c + X * (sx * hx * k) + Y * (sy * hy * k) + Z * (sz * hz))
    return chex(pts, ch)


def basis(a):
    a = Vector(a).normalized()
    h = Vector((0, 0, 1)) if abs(a.z) < 0.9 else Vector((1, 0, 0))
    x = h.cross(a).normalized(); y = a.cross(x)
    return x, y, a


def cyl(p0, p1, r0, r1=None, seg=16, cap0=True, cap1=True, rot=0.0):
    r1 = r0 if r1 is None else r1
    p0 = Vector(p0); p1 = Vector(p1); X, Y, A = basis(p1 - p0); L = (p1 - p0).length
    v = []; f = []
    for (r, z) in ((r0, 0.0), (r1, L)):
        for i in range(seg):
            t = 2 * PI * i / seg + rot; v.append(p0 + X * (r * math.cos(t)) + Y * (r * math.sin(t)) + A * z)
    for i in range(seg):
        j = (i + 1) % seg; f.append((i, j, seg + j, seg + i))
    if cap0: f.append(tuple(reversed(range(seg))))
    if cap1: f.append(tuple(range(seg, 2 * seg)))
    return v, f


def lathe(prof, p0, axis, seg=16, rot=0.0):
    """Revolve [(r, h), ...] around the axis from p0. Ends with r > 0 are capped."""
    p0 = Vector(p0); X, Y, A = basis(axis); v = []; f = []; n = len(prof)
    for (r, h) in prof:
        for i in range(seg):
            t = 2 * PI * i / seg + rot; v.append(p0 + X * (r * math.cos(t)) + Y * (r * math.sin(t)) + A * h)
    for k in range(n - 1):
        for i in range(seg):
            j = (i + 1) % seg; f.append((k * seg + i, k * seg + j, (k + 1) * seg + j, (k + 1) * seg + i))
    if prof[0][0] > 1e-6: f.append(tuple(reversed(range(seg))))
    if prof[-1][0] > 1e-6: f.append(tuple(range((n - 1) * seg, n * seg)))
    return v, f


def sphere(c, r, nu=16, nv=10, scale=(1, 1, 1)):
    c = Vector(c); v = [c + Vector((0, 0, -r * scale[2]))]
    for j in range(1, nv):
        ph = -PI / 2 + PI * j / nv
        for i in range(nu):
            t = 2 * PI * i / nu
            v.append(c + Vector((r * math.cos(ph) * math.cos(t) * scale[0], r * math.cos(ph) * math.sin(t) * scale[1], r * math.sin(ph) * scale[2])))
    v.append(c + Vector((0, 0, r * scale[2]))); top = len(v) - 1; f = []
    for i in range(nu): f.append((0, 1 + (i + 1) % nu, 1 + i))
    for j in range(nv - 2):
        for i in range(nu):
            a = 1 + j * nu + i; b = 1 + j * nu + (i + 1) % nu; f.append((a, b, b + nu, a + nu))
    base = 1 + (nv - 2) * nu
    for i in range(nu): f.append((base + i, base + (i + 1) % nu, top))
    return v, f


def prism(poly, h0, h1, M):
    """2D polygon (x, y) extruded along local z from h0 to h1, mapped by the 4x4 M."""
    n = len(poly); v = [M @ Vector((x, y, h0)) for x, y in poly] + [M @ Vector((x, y, h1)) for x, y in poly]
    f = [tuple(reversed(range(n))), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, f


def sweep(path, r, sides=6, cap=True, r1=None):
    """Tube along a polyline (parallel transport frames). r may taper to r1."""
    P = [Vector(p) for p in path]; n = len(P); r1 = r if r1 is None else r1
    T = [(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized() for i in range(n)]
    X, Y, _ = basis(T[0]); v = []; f = []
    for i in range(n):
        if i:
            ax = T[i - 1].cross(T[i])
            if ax.length > 1e-6:
                q = Quaternion(ax.normalized(), T[i - 1].angle(T[i])); X = q @ X; Y = q @ Y
        rr = r + (r1 - r) * i / max(1, n - 1)
        for k in range(sides):
            t = 2 * PI * k / sides; v.append(P[i] + X * (rr * math.cos(t)) + Y * (rr * math.sin(t)))
    for i in range(n - 1):
        for k in range(sides):
            j = (k + 1) % sides; f.append((i * sides + k, i * sides + j, (i + 1) * sides + j, (i + 1) * sides + k))
    if cap: f.append(tuple(reversed(range(sides)))); f.append(tuple(range((n - 1) * sides, n * sides)))
    return v, f


def ribs(p0, axis, r0, r1, h, n, seg=20):
    """A ring stack (flexible joint / bellows) along the axis."""
    prof = []
    for i in range(n):
        z0 = h * i / n; z1 = h * (i + 1) / n
        prof += [(r0, z0 + 0.06 * (z1 - z0)), (r1, z0 + 0.22 * (z1 - z0)), (r1, z0 + 0.62 * (z1 - z0)), (r0, z0 + 0.8 * (z1 - z0))]
    return lathe(prof, p0, axis, seg)


class Tube:
    """A body surface around a vertical axis. secs: [(z, rx, ry, cx, cy, e)], interpolated by z (Catmull-Rom).
    u in turns: 0 = front (-Y), 0.25 = +X (the mech's left), 0.5 = back (+Y), 0.75 = -X."""

    def __init__(s, secs):
        s.S = sorted([tuple(float(a) for a in x) + ((2.6,) if len(x) == 5 else ()) for x in secs])
        s.z0 = s.S[0][0]; s.z1 = s.S[-1][0]

    def sec(s, z):
        S = s.S; z = min(max(z, s.z0), s.z1); n = len(S)
        i = 0
        while i < n - 2 and S[i + 1][0] < z: i += 1
        t = (z - S[i][0]) / max(1e-9, S[i + 1][0] - S[i][0])
        a = S[max(i - 1, 0)]; b = S[i]; c = S[i + 1]; d = S[min(i + 2, n - 1)]
        out = [z]
        for k in range(1, 6):
            out.append(0.5 * (2 * b[k] + (-a[k] + c[k]) * t + (2 * a[k] - 5 * b[k] + 4 * c[k] - d[k]) * t * t + (-a[k] + 3 * b[k] - 3 * c[k] + d[k]) * t * t * t))
        return out

    def raw(s, u, z):
        _, rx, ry, cx, cy, e = s.sec(z); a = 2 * PI * u; sa, ca = math.sin(a), math.cos(a); pw = 2.0 / e
        return Vector((cx + rx * math.copysign(abs(sa) ** pw, sa), cy - ry * math.copysign(abs(ca) ** pw, ca), z))

    def n(s, u, z):
        du = s.raw(u + 1e-3, z) - s.raw(u - 1e-3, z); dz = s.raw(u, z + 0.02) - s.raw(u, z - 0.02)
        if dz.length < 1e-9: dz = Vector((0, 0, 1))
        nn = du.cross(dz)
        _, rx, ry, cx, cy, e = s.sec(z)
        P = s.raw(u, z)
        if nn.dot(P - Vector((cx, cy, z))) < 0: nn = -nn
        return nn.normalized()

    def p(s, u, z, off=0.0):
        P = s.raw(u, z)
        return P + s.n(u, z) * off if off else P

    def center(s, z):
        q = s.sec(z); return Vector((q[3], q[4], z))


def _arc_u(T, u0, u1, z, k=10):
    return sum((T.raw(u0 + (u1 - u0) * (i + 1) / k, z) - T.raw(u0 + (u1 - u0) * i / k, z)).length for i in range(k))


def _arc_z(T, u, z0, z1, k=6):
    return sum((T.raw(u, z0 + (z1 - z0) * (i + 1) / k) - T.raw(u, z0 + (z1 - z0) * i / k)).length for i in range(k))


def patch(T, u0, u1, z0, z1, lift=0.15, t=0.6, ch=0.14, nu=None, nv=None, crown=0.0, tilt=0.0, step=1.1):
    """An armour plate lying on the tube: bottom face at offset `lift`, chamfered top at lift+t (+crown pillow, +tilt*(v-.5))."""
    Lu = max(_arc_u(T, u0, u1, 0.5 * (z0 + z1)), 0.05); Lz = max(_arc_z(T, 0.5 * (u0 + u1), z0, z1), 0.05)
    nu = nu or max(2, int(round(Lu / step))); nv = nv or max(1, int(round(Lz / (step * 1.4))))
    cu = min(ch / Lu, 0.3) * (u1 - u0); cz = min(ch / Lz, 0.3) * (z1 - z0)
    v = []; f = []
    def ext(j): return tilt * (j / nv - 0.5)
    top = {}; bot = {}
    for i in range(nu + 1):
        for j in range(nv + 1):
            uu = u0 + cu + (u1 - u0 - 2 * cu) * i / nu; zz = z0 + cz + (z1 - z0 - 2 * cz) * j / nv
            top[i, j] = len(v); v.append(T.p(uu, zz, lift + t + crown * math.sin(PI * i / nu) * math.sin(PI * j / nv) + ext(j)))
    for i in range(nu + 1):
        for j in range(nv + 1):
            bot[i, j] = len(v); v.append(T.p(u0 + (u1 - u0) * i / nu, z0 + (z1 - z0) * j / nv, lift))
    per = [(i, 0) for i in range(nu)] + [(nu, j) for j in range(nv)] + [(i, nv) for i in range(nu, 0, -1)] + [(0, j) for j in range(nv, 0, -1)]
    mid = []
    for (i, j) in per:
        mid.append(len(v)); v.append(T.p(u0 + (u1 - u0) * i / nu, z0 + (z1 - z0) * j / nv, lift + t - ch + ext(j)))
    for i in range(nu):
        for j in range(nv):
            f.append((top[i, j], top[i + 1, j], top[i + 1, j + 1], top[i, j + 1]))
            f.append((bot[i, j + 1], bot[i + 1, j + 1], bot[i + 1, j], bot[i, j]))
    m = len(per)
    for k in range(m):
        a = per[k]; b = per[(k + 1) % m]
        f.append((top[a], top[b], mid[(k + 1) % m], mid[k]))
        f.append((mid[k], mid[(k + 1) % m], bot[b], bot[a]))
    return v, f


def tube_solid(T, z0, z1, off=0.0, nu=28, nz=None, cap0=True, cap1=True, zb=None):
    """Closed solid of the tube between z0 and z1. zb(u) optionally gives a per-u bottom height (a sloped / cut-away bottom)."""
    nz = nz or max(2, int((z1 - z0) / 1.2))
    v = []; f = []
    for j in range(nz + 1):
        for i in range(nu):
            b = zb(i / nu) if zb else z0
            v.append(T.p(i / nu, b + (z1 - b) * j / nz, off))
    for j in range(nz):
        for i in range(nu):
            k = (i + 1) % nu; f.append((j * nu + i, j * nu + k, (j + 1) * nu + k, (j + 1) * nu + i))
    if cap0:
        if zb:
            c = len(v); v.append(tuple(sum((Vector(v[i]) for i in range(nu)), Vector()) / nu))
            for i in range(nu): f.append(((i + 1) % nu, i, c))
        else: f.append(tuple(reversed(range(nu))))
    if cap1: f.append(tuple(range(nz * nu, (nz + 1) * nu)))
    return v, f


def ring_shell(T, z0, z1, lift=0.15, t=0.6, nu=28, nz=None, cap_top=False, dome=0.0):
    """A full ring (or a helmet when cap_top) of armour around the tube between z0 and z1."""
    nz = nz or max(1, int((z1 - z0) / 1.0)); v = []; f = []
    def ring(off, j):
        z = z0 + (z1 - z0) * j / nz
        return [T.p(i / nu, z, off) for i in range(nu)]
    O = []; I = []
    for j in range(nz + 1):
        O.append(len(v)); v.extend(ring(lift + t, j))
        I.append(len(v)); v.extend(ring(lift, j))
    for j in range(nz):
        for i in range(nu):
            k = (i + 1) % nu
            f.append((O[j] + i, O[j] + k, O[j + 1] + k, O[j + 1] + i))
            f.append((I[j + 1] + i, I[j + 1] + k, I[j] + k, I[j] + i))
    for i in range(nu):
        k = (i + 1) % nu; f.append((I[0] + i, I[0] + k, O[0] + k, O[0] + i))
    if cap_top:
        c = T.center(z1); ot = len(v); v.append(c + Vector((0, 0, lift + t + dome))); it = len(v); v.append(c + Vector((0, 0, lift + dome * 0.6)))
        for i in range(nu):
            k = (i + 1) % nu; f.append((O[nz] + i, O[nz] + k, ot)); f.append((I[nz] + k, I[nz] + i, it))
    else:
        for i in range(nu):
            k = (i + 1) % nu; f.append((O[nz] + i, O[nz] + k, I[nz] + k, I[nz] + i))
    return v, f


def shell_cup(c, axis, r_in, r_out, h_open, seg=20, rings=8):
    """A spherical cup around c, open on the -axis side at axial height h_open (h_open in -r..r)."""
    X, Y, A = basis(axis); c = Vector(c)
    prof_o = []; prof_i = []
    a0 = math.acos(max(-1.0, min(1.0, h_open / r_out))); b0 = math.acos(max(-1.0, min(1.0, h_open / r_in)))
    for k in range(rings + 1):
        t = k / rings
        a = a0 * (1 - t); b = b0 * (1 - t)
        prof_o.append((r_out * math.sin(a), r_out * math.cos(a))); prof_i.append((r_in * math.sin(b), r_in * math.cos(b)))
    prof = prof_o + list(reversed(prof_i))
    v = []; f = []; n = len(prof)
    for (r, h) in prof:
        for i in range(seg):
            t = 2 * PI * i / seg; v.append(c + X * (r * math.cos(t)) + Y * (r * math.sin(t)) + A * h)
    for k in range(n - 1):
        for i in range(seg):
            j = (i + 1) % seg; f.append((k * seg + i, k * seg + j, (k + 1) * seg + j, (k + 1) * seg + i))
    for i in range(seg):
        j = (i + 1) % seg; f.append(((n - 1) * seg + i, (n - 1) * seg + j, j, i))
    return v, f


def arc_shell(c, x0, x1, r0, r1, p0, p1, n=14):
    """A cylindrical shell about the X axis through c=(y, z): x0..x1, radii r0..r1, angles p0..p1 (deg, from +Y toward +Z)."""
    v = []; f = []
    for k in range(n + 1):
        a = (p0 + (p1 - p0) * k / n) * D2R
        for (x, r) in ((x0, r0), (x1, r0), (x1, r1), (x0, r1)):
            v.append((x, c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    for k in range(n):
        for i in range(4):
            j = (i + 1) % 4; f.append((k * 4 + i, k * 4 + j, (k + 1) * 4 + j, (k + 1) * 4 + i))
    f.append((0, 1, 2, 3)); f.append((n * 4 + 3, n * 4 + 2, n * 4 + 1, n * 4))
    return v, f


def lathe_ring(prof, p0, axis, seg=24):
    """Revolve a CLOSED profile loop [(r, h), ...] (a ring / collar)."""
    p0 = Vector(p0); X, Y, A = basis(axis); v = []; f = []; n = len(prof)
    for (r, h) in prof:
        for i in range(seg):
            t = 2 * PI * i / seg; v.append(p0 + X * (r * math.cos(t)) + Y * (r * math.sin(t)) + A * h)
    for k in range(n):
        k2 = (k + 1) % n
        for i in range(seg):
            j = (i + 1) % seg; f.append((k * seg + i, k * seg + j, k2 * seg + j, k2 * seg + i))
    return v, f


def arc_ring(prof, p0, a0, a1, seg=24):
    """Revolve a closed convex profile [(r, h), ...] about +Z through p0 from angle a0 to a1 (deg, from +X toward +Y), capped ends."""
    p0 = Vector(p0); v = []; f = []; n = len(prof)
    for i in range(seg + 1):
        t = (a0 + (a1 - a0) * i / seg) * D2R
        for (r, h) in prof: v.append(p0 + Vector((r * math.cos(t), r * math.sin(t), h)))
    for i in range(seg):
        for k in range(n):
            k2 = (k + 1) % n; f.append((i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k))
    f.append(tuple(range(n - 1, -1, -1))); f.append(tuple(seg * n + k for k in range(n)))
    return v, f


def fbox(x0, x1, y0, y1, zb, zt, cp=0.4, palm=-1):
    """Finger segment block: 45-degree chamfers of size cp along the palm-side top and bottom edges (palm side = x0 if palm < 0)."""
    xp, xd = (x0, x1) if palm < 0 else (x1, x0); s = 1 if palm < 0 else -1
    pts = []
    for y in (y0, y1):
        for z, dz in ((zb, 1), (zt, -1)):
            pts += [(xd, y, z), (xp, y, z + dz * cp), (xp + s * cp, y, z)]
    return hull(pts)


def bolts_ring(c, axis, rad, n, r=0.18, h=0.22, a0=0.0):
    """n small hex bolts on a circle (for flanges and covers)."""
    X, Y, A = basis(axis); g = Geo(); c = Vector(c)
    for i in range(n):
        t = 2 * PI * i / n + a0; p = c + X * (rad * math.cos(t)) + Y * (rad * math.sin(t))
        g.add(cyl(p - A * 0.05, p + A * h, r, r * 0.9, 6))
    return g


def bolt_row(p0, p1, n, nrm, r=0.16, h=0.2):
    g = Geo(); p0 = Vector(p0); p1 = Vector(p1); nrm = Vector(nrm).normalized()
    for i in range(n):
        p = p0 + (p1 - p0) * (i / max(1, n - 1)); g.add(cyl(p - nrm * 0.06, p + nrm * h, r, r * 0.9, 6))
    return g


def surf_bolts(T, us, z, off, r=0.16, h=0.2):
    """Bolt heads standing on a tube-surface plate top (off = plate top offset)."""
    g = Geo()
    for u in us:
        p = T.p(u, z, off); n = T.n(u, z); g.add(cyl(p - n * 0.08, p + n * h, r, r * 0.88, 6))
    return g


# ====================================================================================================================== materials (look.py only)
PANEL = os.path.join(TEX, 'mech_panel.png'); FINE = os.path.join(TEX, 'mech_fine.png')


def _boximg(nb, path, P, scale, blend=0.06):
    # blend 0.22 -> 0.06 (06.11): box projection mixes two projections over the blend zone (0.22: 33..57 deg, a
    # quarter of every round surface), so on the head and torso two plate grids lay over each other
    c = nb.image(path, nb.vmath('SCALE', P, scale=scale), extension='REPEAT')
    n = c.node; n.projection = 'BOX'; n.projection_blend = blend
    return c, n.outputs['Alpha']


def _detail(nb, col, P, big=1 / 20.0, fine=1 / 5.0, amt=1.0, near=(80.0, 30.0)):
    """The reference look: a panel atlas (seams, bolts, hatches, louvres, tags); a finer sheet fades in near the camera."""
    tint = nb.mixc((1, 1, 1, 1), nb.cscale(col, 1.45), 0.45)
    c, a = _boximg(nb, PANEL, P, big)
    col = nb.mixc(col, nb.cmul(c, tint), nb.mul(a, amt))
    k = nb.smooth(nb.vmath('LENGTH', nb.coord('Camera')), near[0], near[1])
    c2, a2 = _boximg(nb, FINE, P, fine)
    col = nb.mixc(col, nb.cmul(c2, tint), nb.mul(nb.mul(a2, k), 0.8 * amt))
    return col


def stencil(path, c, U, V, w, h, nrm, ink='#2a2236', amt=0.9):
    """A decal painted IN the shader: planar projection in object space, only on faces looking along nrm."""
    def f(nb, col, P):
        d = nb.vmath('SUBTRACT', P, tuple(c))
        u = nb.add(nb.math('DIVIDE', nb.vmath('DOT_PRODUCT', d, tuple(U)), w), 0.5)
        v = nb.add(nb.math('DIVIDE', nb.vmath('DOT_PRODUCT', d, tuple(V)), h), 0.5)
        img = nb.image(path, nb.vec(u, v, 0.0), extension='CLIP')
        a = img.node.outputs['Alpha']
        face = nb.smooth(nb.vmath('DOT_PRODUCT', nb.tc().outputs['Normal'], tuple(nrm)), 0.3, 0.6)
        return nb.mixc(col, nb.rgb(ink), nb.mul(nb.mul(a, face), amt))
    return f


def armour_mat(name, base='#f2b705', haz=False, stc=None, seed=0.0, chips=0.75, rust=0.7, grime=0.55, big=1 / 20.0, hazf=0.42):
    def fn(nb):
        P = nb.coord('Object'); col = nb.rgb(base)
        if haz: col = nb.stripes(col, nb.rgb('#24202c'), hazf, v=P, axis=(0.577, 0.577, 0.577))
        col = _detail(nb, col, P, big)
        for s in (stc or []): col = s(nb, col, P)
        return col
    return LK.cel(name, fn, spec=0.45, rim=0.4, vary=0.06, vscale=0.12, seed=seed, grime=grime, scuff=0.5, chips=chips, rust=rust, wscale=0.3)


def _chrome(nb):
    g = nb.geo(); N = g.outputs['Normal']; I = g.outputs['Incoming']
    R = nb.vmath('REFLECT', nb.vmath('SCALE', I, scale=-1.0), N)
    e = nb.add(nb.mul(nb.xyz(R)[2], 0.5), 0.5)
    e = nb.add(e, nb.mul(nb.sub(nb.noise(nb.coord('Object'), 1.3, 1.0), 0.5), 0.14))
    return nb.ramp(e, [(0.0, '#b9a894'), (0.36, '#4f78a8'), (0.47, '#5d6488'), (0.5, '#fff4e2'), (0.56, '#f3f6fb'), (0.68, '#c9dcff'), (0.84, '#94b6f6')])


def _visor_parts(nb):
    """Dark glass with painted sky reflections, two amber eye lights behind it (object prop `eyes` 0..1), scanlines.
    Returns (colour, glow): the glow (the post's bloom source) is the lit eyes only, never the glass, so a lightning flash
    on the glass (it reflects the flash) does not bloom the whole visor white; the lit eyes keep their own colour."""
    P = nb.coord('Object'); x, y, z = nb.xyz(P)
    g = nb.geo(); N = g.outputs['Normal']; I = g.outputs['Incoming']
    R = nb.vmath('REFLECT', nb.vmath('SCALE', I, scale=-1.0), N)
    e = nb.add(nb.mul(nb.xyz(R)[2], 0.5), 0.5)
    e = nb.add(e, nb.mul(nb.sub(nb.noise(P, 0.7, 1.0), 0.5), 0.1))
    col = nb.ramp(e, [(0.0, '#0b0d1a'), (0.5, '#121830'), (0.56, '#2b3d6e'), (0.63, '#18223f'), (0.8, '#30487e')])
    eyes = nb.objattr('eyes')
    dx = nb.sub(nb.math('ABSOLUTE', x), 1.6); dz = nb.sub(z, 3.0)
    d = nb.math('SQRT', nb.add(nb.mul(nb.mul(dx, dx), 0.55), nb.mul(nb.mul(dz, dz), 3.2)))
    core = nb.smooth(d, 0.5, 0.36)
    halo = nb.smooth(d, 1.45, 0.3)
    lit = nb.mul(nb.mx(core, nb.mul(halo, 0.6)), eyes)          # how much of this pixel is eye light (0 on the bare glass)
    col = nb.mixc(col, nb.cscale(nb.rgb('#ff9a2a'), 1.25), nb.mul(halo, nb.mul(eyes, 0.6)))
    col = nb.mixc(col, nb.cscale(nb.rgb('#fff1c8'), 1.7), nb.mul(core, eyes))
    sl = nb.step(0.55, nb.math('FRACT', nb.mul(z, 6.5)))
    col = nb.mixc(col, nb.cscale(col, 0.55), nb.mul(sl, 0.6))
    col = nb.mixc(col, nb.mixc(col, '#dfe6ff', 0.5), nb.mul(nb.attr('flash', 'Fac'), nb.sub(1.0, lit)))
    return col, lit


def _visor_mat():
    """the visor (LK.glowmat): its glow AOV carries the eye-light mask times `eyes` (was `eyes` over the whole glass)."""
    out = {}
    def fn(nb):
        col, out['glow'] = _visor_parts(nb)
        return col
    m = LK.glowmat('M_mech_visor', fn, strength=1.0, ink=1.0)
    aov = next((n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'glow'), None)
    if aov is not None: m.node_tree.links.new(out['glow'], aov.inputs['Value'])
    return m


def _beacon(nb):
    b = nb.objattr('beacon')
    g = nb.geo(); fac = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', g.outputs['Normal'], g.outputs['Incoming']))
    off = nb.mixc(nb.rgb('#3e1d0c'), nb.rgb('#7c3a14'), nb.smooth(fac, 0.25, 0.8))
    on = nb.mixc(nb.rgb('#ff7a12'), nb.rgb('#fff0c0'), nb.smooth(fac, 0.5, 0.95))
    return nb.mixc(off, nb.cscale(on, 1.5), b)


def _lamp(nb):
    b = nb.objattr('lamps')
    g = nb.geo(); fac = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', g.outputs['Normal'], g.outputs['Incoming']))
    off = nb.mixc(nb.rgb('#1b2034'), nb.rgb('#4c5a80'), nb.smooth(fac, 0.4, 0.95))
    on = nb.mixc(nb.rgb('#ffd890'), nb.rgb('#fffbe8'), nb.smooth(fac, 0.4, 0.9))
    return nb.mixc(off, nb.cscale(on, 1.6), b)


def _tiplight(nb):
    b = nb.objattr('beacon')
    return nb.mixc(nb.rgb('#7a1c18'), nb.cscale(nb.rgb('#ff4a3a'), 1.6), nb.add(0.25, nb.mul(b, 0.75)))


def _moss(nb):
    P = nb.coord('Object')
    n = nb.noise(P, 1.3, 4.0, 0.62, 0.3); n2 = nb.noise(P, 5.0, 2.0, 0.5)
    col = nb.ramp(nb.add(nb.mul(n, 0.75), nb.mul(n2, 0.25)), [(0.0, '#3c5a24'), (0.42, '#56802f'), (0.55, '#6b8f3a'), (0.66, '#8db04a'), (0.76, '#a9c45c')])
    sp = nb.voronoi(P, 2.2, out='Distance')
    col = nb.mixc(col, nb.rgb('#f2ecd0'), nb.mul(nb.smooth(sp, 0.07, 0.035), 0.9))
    return col


def _leaf(nb):
    P = nb.coord('Object')
    return nb.ramp(nb.noise(P, 0.9, 2.0), [(0.0, '#467a2a'), (0.45, '#5f9a36'), (0.6, '#79b044'), (0.75, '#98c455')])


def _twig(nb):
    P = nb.coord('Object')
    return nb.ramp(nb.noise(P, 2.5, 2.0), [(0.0, '#6e5236'), (0.4, '#8f6c44'), (0.6, '#ad8a5a'), (0.78, '#cdaa74')])


def _drift(nb):
    P = nb.coord('Object')
    return nb.ramp(nb.noise(P, 2.2, 2.0), [(0.0, '#a38d64'), (0.45, '#c0a676'), (0.62, '#d2bb8a'), (0.8, '#e6d4a8')])


def _mud(nb):
    P = nb.coord('Object')
    col = nb.ramp(nb.noise(P, 1.8, 3.0), [(0.0, '#47352a'), (0.45, '#5a4431'), (0.62, '#6e553a'), (0.8, '#866b48')])
    return nb.mixc(col, nb.rgb('#8a7a52'), nb.mul(nb.smooth(nb.voronoi(P, 4.0, out='Distance'), 0.1, 0.05), 0.5))


def _beak(nb):
    P = nb.coord('Object'); x, y, z = nb.xyz(P)
    return nb.mixc(nb.rgb('#f2b705'), nb.rgb('#d23a2e'), nb.smooth(nb.mul(y, -1.0), 0.48 * 1.4, 0.52 * 1.4))


def _chick(nb):
    P = nb.coord('Object')
    sp = nb.voronoi(P, 6.5, out='Distance')
    return nb.mixc(nb.rgb('#d6cdb8'), nb.rgb('#7a6c5a'), nb.smooth(sp, 0.16, 0.09))


def _wing(nb):
    P = nb.coord('Object'); x = nb.math('ABSOLUTE', nb.xyz(P)[0])
    col = nb.mixc(nb.rgb('#a9b2c6'), nb.rgb('#23212b'), nb.smooth(x, 0.95 * 1.4, 1.02 * 1.4))
    return nb.mixc(col, nb.rgb('#f4f1ea'), nb.mul(nb.smooth(x, 1.15 * 1.4, 1.18 * 1.4), 0.9))


def _sole(nb):
    P = nb.coord('Object')
    return nb.stripes(nb.rgb('#2b2a36'), nb.rgb('#3d3c4c'), 1.4, v=P, axis=(0.0, 1.0, 0.0), duty=0.6)


def _glow_by_prop(m, prop, base=0.0):
    """Drive the kit material's 'glow' AOV (the post bloom) by the object prop, so a lamp that is off does not bloom."""
    nt = m.node_tree
    aov = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'glow'), None)
    if aov is None: return m
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_type = 'OBJECT'; at.attribute_name = prop; src = at.outputs['Fac']
    if base:
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = base
        nt.links.new(src, mr.inputs['Value']); src = mr.outputs['Result']
    nt.links.new(src, aov.inputs['Value'])
    return m


def make_mats():
    M = {}
    M['yel'] = armour_mat('M_mech_yellow', '#f2b705')
    M['yel2'] = armour_mat('M_mech_yellow_faded', '#ebc04f', seed=3.0, chips=0.9)
    M['yel3'] = armour_mat('M_mech_yellow_deep', '#efa400', seed=7.0)
    M['haz'] = armour_mat('M_mech_hazard', '#f2b705', haz=True, seed=1.0)
    M['primer'] = armour_mat('M_mech_primer', '#c8553d', seed=5.0, chips=0.45, rust=0.4)
    M['teal'] = armour_mat('M_mech_teal', '#2a8f8a', seed=9.0, chips=0.6)
    M['steel'] = LK.cel('M_mech_steel', lambda nb: _detail(nb, nb.rgb('#3b4152'), nb.coord('Object'), amt=0.8), spec=0.55, rim=0.45, vary=0.05, grime=0.4, scuff=0.7, rust=0.45, wscale=0.3)
    M['steel2'] = LK.cel('M_mech_joint', lambda nb: _detail(nb, nb.rgb('#4b5163'), nb.coord('Object'), amt=0.6), spec=0.8, rim=0.5, vary=0.04, grime=0.5, scuff=0.8, rust=0.35, wscale=0.4)
    M['chrome'] = LK.cel('M_mech_chrome', _chrome, spec=1.0, rim=0.7, vary=0.0)
    M['rubber'] = LK.cel('M_mech_rubber', '#2b2a36', spec=0.3, vary=0.04, grime=0.3, scuff=0.4, wscale=0.5)
    M['sole'] = LK.cel('M_mech_sole', _sole, spec=0.2, vary=0.04, grime=0.5, wscale=0.5)
    M['rust'] = LK.cel('M_mech_rust', '#9a4f2a', vary=0.12, grime=0.6, scuff=0.4, wscale=0.4)
    M['red'] = LK.cel('M_mech_red', '#d23a2e', spec=0.5, vary=0.05, grime=0.4, chips=0.5, wscale=0.4)
    M['white'] = LK.cel('M_mech_white', '#f1ead8', spec=0.4, vary=0.05, grime=0.5, chips=0.4, wscale=0.4)
    M['visor'] = _visor_mat()
    M['beacon'] = _glow_by_prop(LK.glowmat('M_mech_beacon', _beacon, strength=1.0, ink=1.0), 'beacon')
    M['lamp'] = _glow_by_prop(LK.glowmat('M_mech_lamp', _lamp, strength=1.0, ink=1.0), 'lamps')
    M['tip'] = _glow_by_prop(LK.glowmat('M_mech_tiplight', _tiplight, strength=1.0, ink=1.0), 'beacon', 0.25)
    M['moss'] = LK.cel('M_mech_moss', _moss, paint=0.55, rim=0.5, vary=0.1, vscale=0.4, wet=0.8)
    M['vine'] = LK.cel('M_mech_vine', '#4a6b2a', paint=0.3, vary=0.1, vscale=0.6)
    M['leaf'] = LK.cel('M_mech_leaf', _leaf, paint=0.45, rim=0.5, vary=0.1, vscale=0.5)
    M['twig'] = LK.cel('M_mech_twig', _twig, paint=0.35, vary=0.12, vscale=1.5)
    M['drift'] = LK.cel('M_mech_driftwood', _drift, paint=0.35, vary=0.1, vscale=1.5)
    M['mud'] = LK.cel('M_mech_nestmud', _mud, paint=0.3, vary=0.14, vscale=1.2)
    M['weed'] = LK.cel('M_mech_seaweed', '#5b6526', paint=0.35, rim=0.4, vary=0.12, vscale=1.0, wet=0.8)
    M['straw'] = LK.cel('M_mech_straw', '#c2a46a', paint=0.4, vary=0.12, vscale=1.5)
    M['gull'] = LK.cel('M_gull_white', '#f6f3ec', rim=0.6, vary=0.03)
    M['gullwing'] = LK.cel('M_gull_wing', _wing, rim=0.6, vary=0.02)
    M['gullgrey'] = LK.cel('M_gull_grey', '#a9b2c6', rim=0.5, vary=0.02)
    M['black'] = LK.cel('M_gull_black', '#1f1d27', spec=0.8, vary=0.0)
    M['beak'] = LK.cel('M_gull_beak', _beak, spec=0.5, vary=0.0)
    M['leg'] = LK.cel('M_gull_leg', '#e8a07a', vary=0.0)
    M['chick'] = LK.cel('M_gull_chick', _chick, rim=0.5, vary=0.04, paint=0.3)
    return M


# ====================================================================================================================== the rig
# Rest pose: standing straight, arms hanging, facing -Y, the mech's LEFT is +X. Root (MECH_root) = pelvis floor projection.
S_X, S_Y, S_Z = 17.6, 1.0, 64.5          # shoulder pivot (L)
E_Z, W_Z = 53.0, 42.0                    # elbow, wrist pivots (on the same vertical as the shoulder)
H_X, H_Z, K_Z, A_Z = 8.6, 42.0, 24.0, 6.2  # hip, knee, ankle
FING_X = 16.98; FING_Y = (-1.8, 0.0, 1.8); KNUCKLE_Z = 36.25; FING_L = (2.2, 1.8, 1.4)
FD, FW, FR, FE = 1.5, 1.52, 0.37, 0.45     # finger depth (x), width (y), knuckle roller radius, body clearance from a pivot
THUMB_P = (15.75, -2.45, 38.75); THUMB_L = (1.9, 1.55, 1.25); TD, TW = 1.6, 1.6
THUMB_D = (-0.16, -0.42, -1.0); THUMB_F = (-0.9, 0.42, 0.0)      # thumb direction / its curl direction (L side, rest)
CURL = (70.0, 83.0, 63.0); TCURL = (55.0, 70.0, 60.0)              # degrees per segment at curl = 1
SOLE = (H_X, -3.0, 0.0); PALM = (15.9, 1.0, 38.2)       # sole contact (on the ground plane), palm contact (just off the palm pad)
SIDED = ('shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle')


def _thumb_frame(sx=1.0):
    """Rest rotation of the thumb mount: local -Z = thumb direction, local -X = curl direction, local Y = hinge axis."""
    d = Vector((THUMB_D[0] * sx, THUMB_D[1], THUMB_D[2])).normalized()
    f = Vector((THUMB_F[0] * sx, THUMB_F[1], THUMB_F[2])); f = (f - d * f.dot(d)).normalized()
    if sx > 0:
        Z = -d; X = -f; Y = Z.cross(X); R = Matrix((X, Y, Z)).transposed()
    else:   # the exact mirror of the L frame (so mirrored pose values give mirrored motion)
        RL, _, _ = _thumb_frame(1.0); S = Matrix.Diagonal((-1, 1, 1)); R = S @ RL @ S
    return R, d, f


def joint_table():
    """[(name, parent, pivot (rest world), rest rotation 3x3)], parents first."""
    I3 = Matrix.Identity(3)
    J = [('pelvis', None, (0, 0, 44.0), I3), ('spine', 'pelvis', (0, 0.8, 52.0), I3), ('chest', 'spine', (0, 0.9, 56.4), I3),
         ('neck', 'chest', (0, 1.3, 70.8), I3), ('head', 'neck', (0, 1.0, 73.0), I3)]
    for s, sx in (('L', 1.0), ('R', -1.0)):
        J += [('shoulder' + s, 'chest', (S_X * sx, S_Y, S_Z), I3), ('elbow' + s, 'shoulder' + s, (S_X * sx, S_Y, E_Z), I3),
              ('wrist' + s, 'elbow' + s, (S_X * sx, S_Y, W_Z), I3)]
        for i, dy in enumerate(FING_Y):
            z = KNUCKLE_Z; par = 'wrist' + s
            for k, L in enumerate(FING_L):
                nm = 'finger%s%d_%d' % (s, i, k); J.append((nm, par, (FING_X * sx, S_Y + dy, z), I3)); par = nm; z -= L
        R, d, f = _thumb_frame(sx)
        p = Vector((THUMB_P[0] * sx, THUMB_P[1], THUMB_P[2]))
        J.append(('thumb%s_mount' % s, 'wrist' + s, tuple(p), R))
        par = 'thumb%s_mount' % s
        for k, L in enumerate(THUMB_L):
            nm = 'thumb%s_%d' % (s, k); J.append((nm, par, tuple(p), R)); par = nm; p = p + d * L
        J += [('hip' + s, 'pelvis', (H_X * sx, 0.0, H_Z), I3), ('knee' + s, 'hip' + s, (H_X * sx, 0.0, K_Z), I3), ('ankle' + s, 'knee' + s, (H_X * sx, 0.0, A_Z), I3)]
    return J


def rest_world():
    return {n: Matrix.Translation(Vector(p)) @ R.to_4x4() for (n, par, p, R) in joint_table()}




# ---------------------------------------------------------------------------------------------------------------------- palette + layout
PALK = ('yel', 'yel2', 'yel3', 'haz', 'primer', 'teal', 'steel', 'steel2', 'chrome', 'rubber', 'sole', 'rust', 'red', 'white',
        'visor', 'beacon', 'lamp', 'tip', 'black')
Y, Y2, Y3, HZ, PR, TL, ST, JT, CR, RB, SL, RU, RD, WH, VS, BC, LP, TP, BK = range(19)
X0, X1, X2 = 19, 20, 21          # per-object extra slots (stencilled armour)
FOOT_HW = 4.45                   # foot half width: the feet are 8.9 m wide (lead: <= 9 m)

TB_SECS = [(47.6, 9.0, 6.0, 0, 1.2, 2.8), (48.6, 9.8, 6.5, 0, 1.0, 2.8), (50.5, 10.3, 7.1, 0, 0.6, 2.8), (52.4, 10.2, 7.3, 0, 0.4, 2.8)]
TC_SECS = [(55.9, 8.6, 7.2, 0, 1.2, 2.6), (57.6, 10.8, 8.4, 0, 1.1, 2.8), (60.2, 12.3, 9.2, 0, 1.0, 3.0), (63.4, 12.8, 9.4, 0, 0.9, 3.0),
           (66.4, 11.9, 9.2, 0, 0.9, 3.0), (68.5, 9.5, 8.2, 0, 1.0, 2.8), (69.9, 6.8, 6.6, 0, 1.2, 2.6)]
TH_SECS = [(72.9, 3.3, 3.1, 0, 0.9, 2.6), (73.6, 4.2, 4.0, 0, 0.7, 2.8), (75.5, 4.45, 4.3, 0, 0.55, 3.0), (77.5, 4.35, 4.25, 0, 0.6, 3.0),
           (79.3, 3.8, 3.8, 0, 0.75, 2.8), (80.0, 3.1, 3.2, 0, 0.85, 2.6)]
TU_SECS = [(55.4, 2.7, 3.0, S_X, S_Y, 2.6), (58.0, 2.85, 3.15, S_X, S_Y, 2.8), (60.8, 2.9, 3.2, S_X, S_Y, 2.8)]
TF_SECS = [(44.2, 3.0, 3.2, S_X, S_Y + 0.2, 2.6), (46.8, 3.5, 3.6, S_X, S_Y + 0.15, 2.8), (50.0, 3.1, 2.7, S_X, S_Y + 0.5, 2.8)]
TT_SECS = [(30.4, 3.95, 4.25, H_X, 0.1, 2.6), (33.5, 4.2, 4.45, H_X, 0.1, 2.8), (36.5, 4.4, 4.5, H_X, 0.2, 2.8), (38.4, 4.1, 3.8, H_X, 0.5, 2.8)]
TS_SECS = [(8.4, 1.95, 2.3, H_X, 0.2, 2.6), (10.5, 3.3, 3.5, H_X, 0.45, 2.8), (15.5, 3.6, 3.95, H_X, 0.6, 2.8), (20.4, 3.55, 3.85, H_X, 0.4, 2.8)]
STACKS = ((-4.6, 16.0), (0.0, 18.4), (4.6, 14.2)); STACK_Y, STACK_Z0, STACK_R = 16.4, 61.2, 1.1
ANT = (-2.2, 3.2)                # antenna mast (x, y) on the crown
# pistons (L side, rest world): (name, seg of the housing, A, seg of the rod, B, housing length, rod length, housing r, rod r)
EP_A = (S_X, S_Y + 6.2, E_Z + 7.5); EP_B = (S_X, S_Y + 3.2, E_Z + 1.2)
KP_X = H_X - 6.15; KP_A = (KP_X, 2.5, K_Z + 9.0); KP_B = (KP_X, 0.0, K_Z - 2.0)     # knee pistons on the inner side of the knee
PISTONS = (('elbow', 'shoulder', EP_A, 'elbow', EP_B, 6.0, 6.5, 0.7, 0.38),
           ('knee', 'hip', KP_A, 'knee', KP_B, 7.0, 5.0, 0.7, 0.4))


class Builder:
    def __init__(s, coll):
        s.coll = coll; s.objs = []; s.J = {}; s.W = rest_world(); s.parts = {}; s.tris = 0; s.meshes = {}
        s.M = make_mats(); s.PAL = [s.M[k] for k in PALK]; s.pistons = []; s.props = {'eyes': [], 'beacon': [], 'lamps': []}

    def empty(s, name, parent=None, loc=(0, 0, 0), size=1.5, kind='PLAIN_AXES'):
        e = bpy.data.objects.new(name, None); e.empty_display_size = size; e.empty_display_type = kind
        s.coll.objects.link(e); e.parent = parent; e.location = loc; e.rotation_mode = 'XYZ'
        return e

    def rig(s):
        s.root = s.empty('MECH_root', None, size=6.0, kind='ARROWS')
        for (n, par, p, R) in joint_table():
            pe = s.J[par] if par else s.root
            Wp = s.W[par] if par else Matrix.Identity(4)
            e = s.empty('MECH_j_' + n, pe, size=1.2)
            e.location = Wp.inverted() @ Vector(p)
            e.rotation_euler = ((Wp.to_3x3().inverted() @ R) if par else R).to_euler('XYZ')
            e['rest_rot'] = tuple(e.rotation_euler); e['rest_loc'] = tuple(e.location)
            s.J[n] = e
        return s.root

    def mesh(s, name, geo, mats, org, sharp=38.0):
        me = bpy.data.meshes.new(name)
        me.from_pydata([(x - org.x, y - org.y, z - org.z) for (x, y, z) in geo.v], [], geo.f)
        for m in mats: me.materials.append(m)
        if geo.m and len(geo.m) == len(me.polygons): me.polygons.foreach_set('material_index', geo.m)
        me.update()
        bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
        me.shade_smooth(); me.set_sharp_from_angle(angle=sharp * D2R)
        return me

    def put(s, name, geo, seg, kind='body', extra=None, mats=None, bevel=0.05, origin=None, adj=None, touch=None, bang=60.0,
            share=None, sharp=38.0):
        """One object on joint `seg` from a Geo in REST WORLD coordinates. origin defaults to the joint pivot. share: mesh reuse key."""
        W = s.W[seg]; org = Vector(origin) if origin is not None else W.translation.copy()
        mats = mats if mats is not None else s.PAL + list(extra or [])
        if share and share in s.meshes: me = s.meshes[share]
        else:
            me = s.mesh(name, geo, mats, org, sharp)
            if share: s.meshes[share] = me
        o = bpy.data.objects.new(name, me); s.coll.objects.link(o)
        o.parent = s.J[seg]; o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = W.inverted() @ Matrix.Translation(org)
        o['seg'] = seg; o['kind'] = kind
        if adj: o['adj'] = ','.join(adj)
        if touch: o['touch'] = ','.join(touch)
        if bevel:
            md = o.modifiers.new('bevel', 'BEVEL'); md.width = bevel; md.segments = 1; md.limit_method = 'ANGLE'; md.angle_limit = bang * D2R
        s.objs.append(o); s.tris += geo.ntris(); s.parts[name[5:]] = o
        return o

    def pair(s, name, g, seg, extraL=None, extraR=None, **kw):
        """name/seg/adj/touch may hold '{s}' (side). L is g (built on the +X side), R is its mirror."""
        out = []
        for side, gg, ex in (('L', g, extraL), ('R', g.mirrored(), extraR if extraR is not None else extraL)):
            k = dict(kw)
            for key in ('adj', 'touch'):
                if k.get(key): k[key] = [a.format(s=side) for a in k[key]]
            if k.get('origin') is not None and side == 'R': k['origin'] = (-k['origin'][0], k['origin'][1], k['origin'][2])
            if k.get('share'): k['share'] = k['share'] + side
            out.append(s.put(name.format(s=side), gg, seg.format(s=side), extra=ex, **k))
        return out

    def contact(s, name, seg, p, R=None):
        """An empty on joint `seg` at the rest-world point p with the rest-world rotation R (3x3)."""
        W = s.W[seg]; e = s.empty(name, s.J[seg], size=1.0, kind='ARROWS')
        e.matrix_parent_inverse = Matrix.Identity(4)
        e.matrix_basis = W.inverted() @ Matrix.Translation(Vector(p)) @ (R.to_4x4() if R is not None else Matrix.Identity(4))
        s.parts[name[5:]] = e
        return e

    def glow(s, name, geo, seg, mat, prop, touch, origin=None):
        o = s.put(name, geo, seg, kind='glow', mats=[s.M[mat]], touch=touch, bevel=0, origin=origin)
        o[prop] = 0.0; s.props[prop].append(o)
        return o


# ---------------------------------------------------------------------------------------------------------------------- helpers
def _mir(g):
    return Geo().merge(g).merge(g.mirrored())


def _xf(vf, M):
    return [tuple(M @ Vector(p)) for p in vf[0]], vf[1]


def _smat(B, name, tex, c, U, V, w, h, nrm, seg, base='#f2b705', seed=0.0):
    """Armour with a stencil; c (decal centre) in rest world, converted to the part's object space (origin = joint pivot)."""
    piv = B.W[seg].translation
    return armour_mat(name, base, stc=[stencil(os.path.join(TEX, tex), (c[0] - piv.x, c[1] - piv.y, c[2] - piv.z), U, V, w, h, nrm)], seed=seed)


def ear_plate(c, xa, xb, r, anchor):
    """One clevis ear: a disk of radius r about the X axis at c, in the x slab [xa, xb], hulled to the anchor points (y, z) in that slab."""
    pts = []
    for x in (xa, xb):
        for k in range(12):
            t = 2 * PI * k / 12; pts.append((x, c[1] + r * math.cos(t), c[2] + r * math.sin(t)))
        pts += [(x, y, z) for (y, z) in anchor]
    return hull(pts)


def fork(c, gap, w, r, rp, anchor=None):
    """A clevis about the X axis at c: two ears in x = c.x +- (gap/2 .. gap/2 + w) and a pin of radius rp through both."""
    g = Geo(); c = Vector(c)
    for sx in (-1, 1):
        xa = c.x + sx * gap / 2; xb = c.x + sx * (gap / 2 + w); xa, xb = min(xa, xb), max(xa, xb)
        if anchor: g.add(ear_plate(c, xa, xb, r, anchor), ST)
        else: g.add(cyl((xa, c.y, c.z), (xb, c.y, c.z), r, seg=16), ST)
    g.add(cyl((c.x - gap / 2 - w - 0.1, c.y, c.z), (c.x + gap / 2 + w + 0.1, c.y, c.z), rp, seg=10), CR)
    return g


def eye_ring(c, ri, ro, w):
    return lathe_ring([(ri, 0.0), (ro, 0.0), (ro, w), (ri, w)], (c[0] - w / 2, c[1], c[2]), (1, 0, 0), 16)


# ---------------------------------------------------------------------------------------------------------------------- body
def body_pelvis(B):
    TB = Tube(TB_SECS); g = Geo(); h = Geo()
    def belt_zb(q):
        d = min(abs(q % 1.0), abs(q % 1.0 - 0.5), abs(q % 1.0 - 1.0)); t = max(0.0, min(1.0, (d - 0.02) / 0.045))
        return 47.6 + 1.9 * t * t * (3 - 2 * t)
    g.add(tube_solid(TB, 47.6, 52.4, nu=48, zb=belt_zb), ST)                                     # belt, cut high over the hips
    g.add(box(-2.0, 2.0, -4.0, 5.4, 38.8, 48.0, 0.35, top=(-2.9, 2.9, -4.8, 6.2)), ST)          # crotch block
    h.add(cyl((2.0, 0, H_Z), (6.4, 0, H_Z), 1.5, seg=20), JT)                                     # hip axle
    h.add(cyl((2.6, 0, H_Z), (3.3, 0, H_Z), 2.45, seg=20), ST)
    h.merge(bolts_ring((3.3, 0, H_Z), (1, 0, 0), 2.05, 8), ST)
    h.add(sphere((H_X, 0, H_Z), 3.3, 22, 14), JT)                                                 # hip ball (inside the thigh cup)
    for (u0, u1, z0, m) in ((0.075, 0.17, 49.6, Y), (0.18, 0.32, 49.6, Y2), (0.33, 0.47, 49.6, Y)):
        h.add(patch(TB, u0, u1, z0, 52.0, 0.12, 0.6, crown=0.15), m)
    for z in (50.1, 51.6): h.merge(surf_bolts(TB, (0.09, 0.155, 0.195, 0.305, 0.345, 0.455), z, 0.72), ST)
    g.merge(_mir(h))
    g.add(patch(TB, -0.045, 0.045, 48.3, 52.0, 0.12, 0.65, crown=0.2), HZ)
    g.add(box(-2.4, 2.4, -5.2, -4.3, 39.0, 47.2, 0.25, top=(-3.0, 3.0, -5.9, -4.6)), HZ)        # codpiece
    g.add(box(-2.3, 2.3, 5.68, 6.45, 39.4, 46.6, 0.25, top=(-2.6, 2.6, 6.28, 7.05)), Y2)         # seat plate
    B.put('MECH_pelvis', g, 'pelvis')


def body_waist(B):
    B.put('MECH_waist', Geo().add(ribs((0, 0.8, 51.6), (0, 0, 1), 6.0, 6.4, 5.0, 4, 36), JT), 'spine', kind='joint', adj=['pelvis', 'chest'])


def body_chest(B):
    TC = Tube(TC_SECS); g = Geo(); h = Geo()
    g.add(tube_solid(TC, 55.9, 69.9, nu=40), ST)
    pec = Geo().add(patch(TC, 0.035, 0.175, 60.4, 67.6, 0.15, 0.75, crown=0.35), 0)
    g.merge(pec, X0); g.merge(pec.mirrored(), Y)
    m07 = _smat(B, 'M_mech_chest07', 'mech_07.png', TC.p(0.105, 64.0, 1.2), (1, 0, 0), (0, 0, 1), 4.6, 3.6, (0, -1, 0), 'chest', seed=2.0)
    # the recessed chest vent between the pecs: frame, divider, louvres
    vz0, vz1, vx = 60.7, 67.0, 3.7
    for (x0, x1, z0, z1) in ((-vx, vx, vz0, vz0 + 0.55), (-vx, vx, vz1 - 0.55, vz1), (-vx, -vx + 0.55, vz0, vz1), (vx - 0.55, vx, vz0, vz1)):
        g.add(box(x0, x1, -9.5, -8.62, z0, z1, 0.12), ST)
    g.add(box(-0.25, 0.25, -9.25, -8.62, vz0 + 0.3, vz1 - 0.3, 0.1), ST)
    a = 38 * D2R; Dd = Vector((0, -math.cos(a), -math.sin(a))); Xd = Vector((1, 0, 0)); Nd = Xd.cross(Dd)
    for i in range(6):
        for sx in (-1, 1): g.add(obox((sx * 1.72, -8.98, vz0 + 1.0 + i * 0.88), Xd, Dd, Nd, 1.38, 0.4, 0.07, 0.03), BK)
    g.add(patch(TC, -0.165, 0.165, 67.4, 69.6, 0.15, 0.6, crown=0.15), Y2)             # collarbone
    g.add(patch(TC, -0.2, 0.2, 56.1, 58.15, 0.12, 0.55), HZ)                           # hazard band
    g.add(patch(TC, -0.028, 0.028, 58.35, 60.45, 0.12, 0.6), Y3)
    h.add(patch(TC, 0.035, 0.2, 58.35, 60.25, 0.12, 0.6), Y)
    h.add(patch(TC, 0.21, 0.335, 56.3, 61.6, 0.12, 0.65, crown=0.2), Y)
    h.add(patch(TC, 0.185, 0.222, 61.8, 67.15, 0.12, 0.6), Y2)
    h.add(patch(TC, 0.278, 0.345, 61.8, 67.15, 0.12, 0.6), PR)                         # a primer-red replacement plate
    h.add(patch(TC, 0.178, 0.36, 67.4, 70.2, 0.15, 0.7, crown=0.2), Y)                 # trapezius
    h.add(patch(TC, 0.345, 0.497, 56.3, 59.3, 0.12, 0.6), Y2)
    h.merge(surf_bolts(TC, (0.195, 0.25, 0.3, 0.345), 69.5, 0.85), ST)
    h.merge(surf_bolts(TC, (0.22, 0.275, 0.325), 57.0, 0.77), ST)
    h.merge(surf_bolts(TC, (0.05, 0.11, 0.165), 59.3, 0.72), ST)
    # shoulder socket: axle, flange, ball (the deltoid cup of the upper arm closes round it)
    h.add(cyl((11.4, S_Y, S_Z), (15.4, S_Y, S_Z), 1.4, seg=20), JT)
    h.add(cyl((12.2, S_Y, S_Z), (12.95, S_Y, S_Z), 2.3, seg=24), ST)
    h.merge(bolts_ring((12.95, S_Y, S_Z), (1, 0, 0), 1.9, 8), ST)
    h.add(sphere((S_X, S_Y, S_Z), 3.4, 24, 14), JT)
    # backpack (warning decal on its L side), ladder on the R side, hatch, louvres
    g.add(box(-7.6, 7.6, 5.0, 14.8, 59.4, 69.8, 0.6, top=(-7.0, 7.0, 5.0, 14.2)), X1)
    mw = _smat(B, 'M_mech_warn', 'mech_warn.png', (7.33, 9.9, 64.6), (0, 1, 0), (0, 0, 1), 5.2, 2.6, (1, 0, 0), 'chest', seed=4.0)
    for i in range(9):
        z = 60.3 + i * 1.0; xf = -7.6 + 0.6 * (z - 59.4) / 10.4 + 0.12
        g.add(sweep([(xf, 7.6, z), (xf - 0.62, 7.6, z), (xf - 0.62, 9.4, z), (xf, 9.4, z)], 0.07, 6), ST)
    for i in range(4):
        z = 67.0 - i * 0.55; yf = 14.8 - 0.6 * (z - 59.4) / 10.4
        g.add(box(1.4, 3.2, yf - 0.2, yf + 0.18, z, z + 0.32, 0.05), BK)
    # exhaust stacks: rusty pipes, clamps and brackets into the backpack, propped-open rain caps; steam empties at the mouths
    for i, (sx, ht) in enumerate(STACKS):
        z0 = STACK_Z0; r = STACK_R
        prof = [(r, 0), (r, ht - 1.2), (r + 0.18, ht - 1.0), (r + 0.18, ht), (r - 0.12, ht), (r - 0.12, ht - 1.6), (0, ht - 1.6)]
        g.add(lathe(prof, (sx, STACK_Y, z0), (0, 0, 1), 18), RU)
        g.add(cyl((sx, STACK_Y, z0 + 0.7), (sx, 13.6, z0 + 0.7), 0.85, seg=14), RU)
        for zc in (z0 + 2.4, z0 + 7.5, z0 + ht - 4.0):
            g.add(lathe_ring([(r - 0.04, 0), (r + 0.24, 0), (r + 0.24, 0.5), (r - 0.04, 0.5)], (sx, STACK_Y, zc), (0, 0, 1), 18), ST)
            if zc < 69.0: g.add(box(sx - 0.22, sx + 0.22, 13.7, STACK_Y - r + 0.1, zc + 0.05, zc + 0.45, 0.06), ST)
        hy, hz = STACK_Y + r + 0.12, z0 + ht + 0.06
        an = -55 * D2R; ca, sa = math.cos(an), math.sin(an)
        ry_, rz_ = -(r + 0.12), 0.05
        ctr = Vector((sx, hy + ry_ * ca - rz_ * sa, hz + ry_ * sa + rz_ * ca)); nrm = Vector((0, -sa, ca))
        g.add(cyl(ctr - nrm * 0.06, ctr + nrm * 0.06, r + 0.25, seg=18), ST)
        g.add(cyl((sx - 0.55, hy, hz), (sx + 0.55, hy, hz), 0.14, seg=8), ST)
        B.contact('MECH_steam_%d' % i, 'chest', (sx, STACK_Y, z0 + ht + 0.4))
    g.add(arc_ring([(3.7, 0.0), (6.0, 0.0), (5.8, 0.55), (5.0, 1.1), (3.7, 1.1)], (0, 1.1, 69.75), -25, 205, 30), Y3)   # back collar (open at the front: the head bows)
    g.merge(_mir(h))
    B.put('MECH_chest', g, 'chest', extra=[m07, mw])


def body_neck(B):
    B.put('MECH_neck', Geo().add(ribs((0, 1.3, 69.6), (0, 0, 1), 2.4, 2.7, 4.6, 4, 24), JT), 'neck', kind='joint', adj=['chest', 'head'])


def body_head(B):
    TH = Tube(TH_SECS); g = Geo(); h = Geo()
    g.add(tube_solid(TH, 72.9, 80.0, nu=36), ST)
    g.add(patch(TH, -0.168, 0.168, 77.0, 77.9, 0.35, 0.75, ch=0.2), X0)                 # brow: "UNIT 07"
    mu = _smat(B, 'M_mech_brow', 'mech_unit.png', TH.p(0.0, 77.45, 1.1), (1, 0, 0), (0, 0, 1), 3.4, 0.73, (0, -1, 0), 'head', seed=6.0)
    g.add(ring_shell(TH, 78.0, 80.0, 0.15, 0.6, nu=40, cap_top=True, dome=0.3), Y)     # crown
    g.add(patch(TH, -0.17, 0.17, 73.3, 74.8, 0.12, 0.5, crown=0.1), Y3)                 # jaw
    for zz in (73.65, 74.1, 74.55):
        g.add(sweep([TH.p(-0.12 + 0.24 * k / 8, zz, 0.68) for k in range(9)], 0.11, 6), ST)
    g.add(patch(TH, 0.34, 0.66, 73.6, 77.8, 0.15, 0.6, crown=0.15), Y2)                # back plate
    g.merge(surf_bolts(TH, (0.37, 0.45, 0.55, 0.63), 77.3, 0.75), ST)
    h.add(patch(TH, 0.18, 0.33, 73.8, 77.8, 0.18, 0.6, crown=0.15), Y2)                 # cheek
    lp = TH.p(0.115, 78.6, 0.75); ln = TH.n(0.115, 78.6)
    h.add(cyl(lp - ln * 0.1, lp + ln * 0.5, 0.5, seg=12), ST)                            # headlamp housing
    g.merge(_mir(h))
    ep = TH.p(0.25, 76.0, 0.93); en = TH.n(0.25, 76.0)
    ear = Geo().add(cyl(ep - en * 0.12, ep + en * 0.55, 1.3, seg=20), 0)
    hub = Geo().add(cyl(ep + en * 0.5, ep + en * 0.68, 0.45, seg=12), ST)
    g.merge(ear, X1); g.merge(ear.mirrored(), X2); g.merge(hub); g.merge(hub.mirrored())
    ec = ep + en * 0.55
    meL = _smat(B, 'M_mech_earL', 'mech_07.png', ec, (0, 1, 0), (0, 0, 1), 1.9, 1.48, (1, 0, 0), 'head', seed=8.0)
    meR = _smat(B, 'M_mech_earR', 'mech_07.png', (-ec.x, ec.y, ec.z), (0, -1, 0), (0, 0, 1), 1.9, 1.48, (-1, 0, 0), 'head', seed=8.5)
    B.put('MECH_head', g, 'head', extra=[mu, meL, meR])
    B.glow('MECH_visor', Geo().add(patch(TH, -0.17, 0.17, 75.0, 76.9, 0.06, 0.14, ch=0.05, step=0.45), 0), 'head', 'visor', 'eyes', ['MECH_head'])
    lamps = Geo()
    for sx in (1, -1):
        lp = TH.p(0.115 * sx, 78.6, 0.75); ln = TH.n(0.115 * sx, 78.6)
        lamps.add(cyl(lp + ln * 0.44, lp + ln * 0.56, 0.4, seg=12), 0)
    B.glow('MECH_lamps', lamps, 'head', 'lamp', 'lamps', ['MECH_head'])
    # antenna (lightning rod) on the back-right of the crown
    ax, ay = ANT; zb = 80.45
    an = Geo()
    an.add(box(ax - 0.7, ax + 0.7, ay - 0.7, ay + 0.7, zb - 0.45, zb + 0.5, 0.15), ST)
    an.add(cyl((ax, ay, zb + 0.4), (ax, ay, 92.2), 0.3, 0.15, seg=10), ST)
    for zc in (82.5, 85.5, 88.5): an.add(cyl((ax, ay, zc), (ax, ay, zc + 0.3), 0.4, seg=10), ST)
    for k in range(3): an.add(cyl((ax, ay, zb + 0.7 + 0.45 * k), (ax, ay, zb + 0.95 + 0.45 * k), 0.55, seg=12), WH)
    an.add(cyl((ax, ay, 92.6), (ax, ay, 93.6), 0.09, 0.02, seg=6), CR)
    B.put('MECH_antenna', an, 'head', touch=['MECH_head'], origin=(ax, ay, zb))
    B.glow('MECH_tiplight', Geo().add(sphere((ax, ay, 92.35), 0.32, 10, 6), 0), 'head', 'tip', 'beacon', ['MECH_antenna'], origin=(ax, ay, 92.35))
    B.contact('MECH_antenna_tip', 'head', (ax, ay, 93.6))


def body_arm(B):
    S = Vector((S_X, S_Y, S_Z)); E = Vector((S_X, S_Y, E_Z))
    TU = Tube(TU_SECS); TF = Tube(TF_SECS)
    # ---- upper arm (+ pauldron, beacon housing, elbow clevis, piston mount)
    u = Geo()
    u.add(shell_cup(S, (1, 0, 0), 3.6, 4.2, -1.0, 24, 10), JT)
    u.add(tube_solid(TU, 55.4, 60.8, nu=24, zb=lambda q: 55.4 + 1.4 * (1 + math.cos(4 * PI * q)) / 2), ST)   # bottom raised front + back
    u.add(patch(TU, -0.13, 0.13, 57.2, 60.3, 0.1, 0.55, crown=0.2), Y)
    u.add(patch(TU, 0.14, 0.3, 56.2, 60.3, 0.1, 0.55, crown=0.2), Y2)
    u.add(patch(TU, 0.31, 0.415, 57.0, 60.3, 0.1, 0.55), Y)
    u.add(patch(TU, 0.585, 0.69, 57.0, 60.3, 0.1, 0.55), Y)
    u.add(patch(TU, 0.70, 0.86, 56.2, 60.3, 0.1, 0.55, crown=0.2), Y3)
    for (x0, x1, xt0, xt1) in ((14.2, 14.75, 14.6, 15.7), (20.45, 21.0, 19.5, 20.6)):
        u.add(lathe_ring([(1.0, 0.0), (2.5, 0.0), (2.5, x1 - x0), (1.0, x1 - x0)], (x0, S_Y, E_Z), (1, 0, 0), 24), ST)
        u.add(box(x0, x1, S_Y - 1.5, S_Y + 1.5, E_Z + 1.1, 56.0, 0.08), ST)
        u.add(hull([(x, y, 55.8) for x in (x0, x1) for y in (S_Y - 1.5, S_Y + 1.5)] + [(x, y, 56.6) for x in (xt0, xt1) for y in (S_Y - 1.7, S_Y + 1.7)]), ST)
    A = Vector(EP_A)
    u.merge(fork(A, 1.5, 0.32, 0.85, 0.26, anchor=[(A.y + 0.5, A.z + 0.4), (A.y + 0.5, A.z + 1.5), (S_Y + 2.4, A.z + 1.5), (S_Y + 2.4, A.z + 0.6)]))
    u.add(box(14.3, 22.9, -5.9, 7.7, 69.4, 72.0, 0.4, top=(14.8, 22.6, -5.4, 7.2)), Y)                 # pauldron slab
    u.add(box(22.0, 22.9, -5.6, 7.4, 62.6, 69.6, 0.3), X0)                                              # outer flap: "07"
    u.add(box(21.95, 22.95, -5.6, 7.4, 61.2, 62.55, 0.2), HZ)
    u.add(box(14.6, 22.0, -6.2, -5.5, 68.0, 70.0, 0.2), Y2)                                             # front lip
    u.add(box(16.6, 18.6, -0.4, 2.4, 68.2, 69.6, 0.2), ST)                                              # post onto the cup
    u.merge(bolt_row((15.4, -5.0, 72.0), (21.8, -5.0, 72.0), 6, (0, 0, 1)), ST)
    u.merge(bolt_row((15.4, 6.8, 72.0), (21.8, 6.8, 72.0), 6, (0, 0, 1)), ST)
    bc = Vector((19.6, 2.6, 72.45))
    u.add(cyl((bc.x, bc.y, 71.9), (bc.x, bc.y, bc.z), 1.0, seg=16), ST)
    for k in range(4):
        t = PI / 4 + k * PI / 2; p = Vector((bc.x + 0.97 * math.cos(t), bc.y + 0.97 * math.sin(t), 0))
        u.add(cyl((p.x, p.y, bc.z - 0.1), (p.x, p.y, bc.z + 1.05), 0.07, seg=6), ST)
    u.add(lathe_ring([(0.9, 0), (1.04, 0), (1.04, 0.12), (0.9, 0.12)], (bc.x, bc.y, bc.z + 0.95), (0, 0, 1), 16), ST)
    mfL = _smat(B, 'M_mech_shoulder07L', 'mech_07.png', (22.9, 1.0, 66.1), (0, 1, 0), (0, 0, 1), 5.0, 3.9, (1, 0, 0), 'shoulderL', seed=3.0)
    mfR = _smat(B, 'M_mech_shoulder07R', 'mech_07.png', (-22.9, 1.0, 66.1), (0, -1, 0), (0, 0, 1), 5.0, 3.9, (-1, 0, 0), 'shoulderR', seed=3.5)
    B.pair('MECH_upperarm{s}', u, 'shoulder{s}', extraL=[mfL], extraR=[mfR])
    bg = Geo().add(sphere(bc, 0.8, 12, 8), 0)
    for side, gg in (('L', bg), ('R', bg.mirrored())):
        B.glow('MECH_beacon' + side, gg, 'shoulder' + side, 'beacon', 'beacon', ['MECH_upperarm' + side], origin=(bc.x if side == 'L' else -bc.x, bc.y, bc.z))
    # ---- forearm (+ elbow roller and pin, lever, wrist cuff)
    f = Geo()
    for (x0, x1) in ((14.9, 16.72), (18.48, 20.3)): f.add(cyl((x0, S_Y, E_Z), (x1, S_Y, E_Z), 2.4, seg=24), JT)   # roller, slotted for the rod
    f.add(cyl((13.75, S_Y, E_Z), (21.45, S_Y, E_Z), 0.9, seg=14), CR)
    f.add(box(15.3, 19.9, S_Y - 2.2, S_Y + 2.1, 49.4, 52.2, 0.3), ST)
    f.add(tube_solid(TF, 44.2, 50.0, nu=24), ST)
    Bp = Vector(EP_B)
    f.merge(fork(Bp, 1.2, 0.3, 0.72, 0.24, anchor=[(S_Y + 0.4, E_Z - 0.9), (S_Y + 1.8, E_Z - 1.6), (S_Y + 0.4, E_Z + 0.6), (S_Y + 1.6, E_Z + 0.9)]))
    f.add(patch(TF, -0.14, 0.14, 44.6, 48.6, 0.12, 0.6, crown=0.25), Y)
    f.add(patch(TF, 0.15, 0.36, 44.6, 49.6, 0.12, 0.6, crown=0.2), TL)                  # a teal replacement plate
    f.add(patch(TF, 0.37, 0.63, 44.6, 49.0, 0.12, 0.6, crown=0.2), Y)
    f.add(patch(TF, 0.64, 0.85, 44.6, 49.6, 0.12, 0.6), Y3)
    f.merge(surf_bolts(TF, (-0.1, 0.0, 0.1), 49.1, 0.72), ST)
    f.add(ring_shell(TF, 42.6, 44.3, 0.15, 0.55, nu=28), HZ)                              # wrist cuff
    fR = f.mirrored()
    for m_i in range(len(fR.m)):
        if fR.m[m_i] == TL: fR.m[m_i] = Y2                                                # the R forearm keeps its yellow plate
    B.put('MECH_forearmL', f, 'elbowL'); B.put('MECH_forearmR', fR, 'elbowR')


def body_hand(B):
    Wr = Vector((S_X, S_Y, W_Z))
    hd = Geo()
    hd.add(sphere(Wr, 2.0, 18, 12), JT)
    hd.add(cyl((S_X, S_Y, 39.2), (S_X, S_Y, 41.4), 1.35, seg=16), ST)
    pts = []
    for y in (-1.7, 3.7):
        pts += [(16.15, y, 39.6), (18.95, y, 39.6), (16.15, y, 37.3), (16.75, y, 36.7), (19.05, y, 36.7), (19.05, y, 39.3)]
    hd.add(hull(pts), ST)                                                                  # palm block (big chamfer on the palm side)
    hd.add(box(17.85, 19.05, -1.6, 3.6, 36.0, 36.9, 0.15), ST)                            # knuckle guard (back side)
    hd.add(box(19.0, 19.6, -1.5, 3.5, 35.9, 39.4, 0.2, top=(19.0, 19.45, -1.3, 3.3)), Y)  # back-of-hand armour
    hd.merge(bolt_row((19.6, -1.0, 38.9), (19.6, 3.0, 38.9), 4, (1, 0, 0), 0.14, 0.16), ST)
    hd.add(box(15.95, 16.2, -1.2, 3.2, 37.6, 39.2, 0.08), RB)                             # palm pad
    # thumb root (thenar): a block in the thumb mount frame hulled onto the palm's front corner
    Rm, d, fdir = _thumb_frame(1.0); Mm = Matrix.Translation(Vector(THUMB_P)) @ Rm.to_4x4()
    tv, tf = fbox(-0.85, 0.85, -0.85, 0.85, FE, 1.7, 0.5)
    hd.add(hull([tuple(Mm @ Vector(p)) for p in tv] + [(16.15, -1.7, 39.0), (16.15, -1.7, 39.6), (16.9, -1.7, 39.6), (16.9, -1.7, 39.0)]), ST)
    B.pair('MECH_hand{s}', hd, 'wrist{s}')
    # fingers: 3 x 3 segments (linked duplicates), knuckle roller on the distal side of every joint, claw caps
    for k in range(3):
        L = FING_L[k]; zt = -FE; zb = -L if k == 2 else -(L - FE)
        g = Geo()
        g.add(fbox(-FD / 2, FD / 2, -FW / 2, FW / 2, zb + (0.15 if k == 2 else 0.0), zt, 0.5), ST)
        g.add(box(0.7, 1.02, -0.62, 0.62, zb + 0.14, zt - 0.12, 0.1), Y)
        g.add(cyl((0, -0.6, 0), (0, 0.6, 0), FR, seg=14), JT)
        if k == 2:
            g.add(hull([(x, y, zb + 0.4) for x in (-0.68, 0.7) for y in (-0.7, 0.7)] + [(-0.64, y, zb - 0.55) for y in (-0.3, 0.3)] +
                       [(-0.1, y, zb - 0.35) for y in (-0.42, 0.42)]), BK)
        for i in range(3):
            piv = Vector((FING_X, S_Y + FING_Y[i], KNUCKLE_Z - sum(FING_L[:k])))
            gw = Geo(); gw.v = [(x + piv.x, y + piv.y, z + piv.z) for (x, y, z) in g.v]; gw.f = g.f; gw.m = g.m
            B.pair('MECH_finger{s}%d_%d' % (i, k), gw, 'finger{s}%d_%d' % (i, k), share='fing%d' % k, bevel=0.03)
    for k in range(3):
        L = THUMB_L[k]; zb = -L if k == 2 else -(L - FE)
        g = Geo()
        g.add(fbox(-TD / 2, TD / 2, -TW / 2, TW / 2, zb + (0.15 if k == 2 else 0.0), -FE, 0.5), ST)
        g.add(box(TD / 2 - 0.05, TD / 2 + 0.28, -0.62, 0.62, zb + 0.14, -FE - 0.12, 0.1), Y)
        g.add(cyl((0, -0.62, 0), (0, 0.62, 0), 0.4, seg=14), JT)
        if k == 2:
            g.add(hull([(x, y, zb + 0.4) for x in (-0.75, 0.78) for y in (-0.75, 0.75)] + [(-0.7, y, zb - 0.55) for y in (-0.32, 0.32)] +
                       [(-0.1, y, zb - 0.35) for y in (-0.45, 0.45)]), BK)
        Wk = B.W['thumbL_%d' % k]
        B.pair('MECH_thumb{s}_%d' % k, _geo_xf(g, Wk), 'thumb{s}_%d' % k, bevel=0.03)
    for side, sx in (('L', 1), ('R', -1)):
        P = Matrix(((0, 0, -sx), (sx, 0, 0), (0, -1, 0)))       # columns: X (thumb side is -X on L), Y along the fingers, Z out of the palm
        B.contact('MECH_palm' + side, 'wrist' + side, (PALM[0] * sx, PALM[1], PALM[2]), P)


def _geo_xf(g, M4):
    out = Geo(); out.v = [tuple(M4 @ Vector(p)) for p in g.v]; out.f = list(g.f); out.m = list(g.m); return out


def body_leg(B):
    TT = Tube(TT_SECS); TS = Tube(TS_SECS)
    # ---- thigh (hip cup, knee clevis + housing, tasset, knee piston mount)
    t = Geo()
    t.add(shell_cup((H_X, 0, H_Z), (1, 0, 0), 3.5, 4.3, -0.8, 24, 10), Y3)
    t.add(tube_solid(TT, 30.4, 38.2, nu=28, zb=lambda q: 30.4 + 2.2 * (1 - math.cos(2 * PI * q)) / 2), ST)
    t.add(box(5.0, 12.2, -2.5, 2.6, 27.6, 30.9, 0.3), ST)
    for (x0, x1, xt0, xt1) in ((3.7, 4.4, 4.3, 5.6), (12.8, 13.5, 11.6, 12.9)):
        t.add(lathe_ring([(1.05, 0.0), (2.9, 0.0), (2.9, x1 - x0), (1.05, x1 - x0)], (x0, 0, K_Z), (1, 0, 0), 24), ST)
        t.add(box(x0, x1, -1.7, 1.7, K_Z + 1.15, 28.2, 0.08), ST)
        t.add(hull([(x, y, 28.0) for x in (x0, x1) for y in (-1.7, 1.7)] + [(x, y, 31.6) for x in (xt0, xt1) for y in (-2.0, 2.0)]), ST)
    t.add(arc_shell((0, K_Z), 4.9, 12.3, 4.0, 4.6, 95, 178, 14), ST)
    t.add(patch(TT, -0.13, 0.13, 27.6, 36.9, 0.12, 0.7, crown=0.35), Y)
    t.add(patch(TT, 0.14, 0.36, 31.0, 38.0, 0.12, 0.55, crown=0.15), Y2)
    t.add(patch(TT, 0.37, 0.63, 33.0, 38.0, 0.12, 0.6, crown=0.2), Y)
    t.add(patch(TT, 0.64, 0.86, 31.0, 38.0, 0.12, 0.6), Y3)
    t.merge(surf_bolts(TT, (-0.1, 0.0, 0.1), 37.1, 0.82), ST)
    A = Vector(KP_A)
    t.merge(fork(A, 1.5, 0.32, 0.85, 0.26, anchor=[(A.y - 0.6, A.z + 0.5), (A.y + 0.6, A.z + 0.5), (A.y - 0.6, A.z + 1.4), (A.y + 0.6, A.z + 1.4)]))
    t.add(box(A.x - 1.07, H_X - 4.0, A.y - 0.6, A.y + 0.6, A.z + 0.8, A.z + 1.4, 0.1), ST)
    # ---- shin (roller + pin, knee guard, ankle shroud + ball, piston mount)
    s = Geo()
    s.add(cyl((4.6, 0, K_Z), (12.6, 0, K_Z), 3.2, seg=28), JT)
    s.add(cyl((3.3, 0, K_Z), (13.65, 0, K_Z), 1.0, seg=14), CR)
    s.add(box(5.2, 12.0, -2.4, 2.6, 19.6, 23.0, 0.3), ST)
    s.add(tube_solid(TS, 8.4, 20.4, nu=28), ST)
    s.add(arc_shell((0, K_Z), 4.7, 12.5, 5.0, 5.8, 150, 222, 16), HZ)                      # knee guard
    s.add(box(7.0, 10.2, -4.1, -3.0, 19.9, 21.3, 0.15), ST)
    s.add(patch(TS, -0.13, 0.13, 10.6, 19.4, 0.12, 0.7, crown=0.3), Y)
    s.add(patch(TS, 0.14, 0.36, 10.6, 19.0, 0.12, 0.6, crown=0.2), X0)                    # "DOCK 3 / HARBOR AUTHORITY"
    s.add(patch(TS, 0.37, 0.63, 10.6, 18.0, 0.12, 0.85, crown=0.35), Y)                    # calf
    s.add(patch(TS, 0.64, 0.86, 10.6, 19.0, 0.12, 0.6, crown=0.2), Y3)
    s.merge(surf_bolts(TS, (-0.09, 0.0, 0.09), 18.9, 0.82), ST)
    s.add(ring_shell(TS, 9.3, 10.9, 0.15, 0.6, nu=32), HZ)                                 # ankle shroud
    s.add(sphere((H_X, 0, A_Z), 2.5, 20, 12), JT)
    s.add(cyl((H_X, 0, A_Z), (H_X, 0, 8.9), 1.6, seg=16), ST)
    Bk = Vector(KP_B)
    s.merge(fork(Bk, 1.24, 0.3, 0.72, 0.24, anchor=[(Bk.y - 0.6, Bk.z - 0.5), (Bk.y + 0.6, Bk.z - 0.5), (Bk.y - 0.6, Bk.z - 1.5), (Bk.y + 0.6, Bk.z - 1.5)]))
    s.add(box(Bk.x - 0.92, H_X - 3.0, -0.6, 0.6, Bk.z - 1.6, Bk.z - 1.0, 0.1), ST)
    mdL = _smat(B, 'M_mech_dock3', 'mech_dock3.png', TS.p(0.25, 14.8, 0.95), (0, 1, 0), (0, 0, 1), 5.0, 2.69, (1, 0, 0), 'kneeL', seed=5.0)
    mdR = armour_mat('M_mech_shinR', '#ebc04f', seed=5.5, chips=0.9)
    B.pair('MECH_thigh{s}', t, 'hip{s}')
    B.pair('MECH_shin{s}', s, 'knee{s}', extraL=[mdL], extraR=[mdR])


def body_foot(B):
    ft = Geo(); hw = FOOT_HW
    ft.add(box(H_X - hw + 0.1, H_X + hw - 0.1, -9.0, 5.8, 0.0, 0.8, 0.2), SL)
    ft.add(box(H_X - 4.1, H_X + 4.1, -8.6, 5.4, 0.75, 3.0, 0.3, top=(H_X - 3.8, H_X + 3.8, -8.0, 5.0)), ST)
    for (x0, x1) in ((H_X + 2.75, H_X + 3.45), (H_X - 3.45, H_X - 2.75)):
        pts = []
        for x in (x0, x1):
            for k in range(12):
                tt = 2 * PI * k / 12; pts.append((x, 1.3 * math.cos(tt), A_Z + 1.3 * math.sin(tt)))
            pts += [(x, -2.6, 2.8), (x, 2.6, 2.8)]
        ft.add(hull(pts), ST)
        ft.add(cyl((x0 if x0 > H_X else x1, 0, A_Z), ((x1 + 0.12) if x0 > H_X else (x0 - 0.12), 0, A_Z), 0.7, seg=12), ST)
    ft.add(box(H_X - 3.5, H_X + 3.5, -8.2, -3.1, 2.9, 3.7, 0.25, top=(H_X - 3.3, H_X + 3.3, -7.6, -3.1)), Y)     # instep
    for xc in (H_X - 2.85, H_X, H_X + 2.85):
        ft.add(box(xc - 1.3, xc + 1.3, -12.0, -8.4, 0.05, 2.2, 0.25, top=(xc - 1.2, xc + 1.2, -11.0, -8.4)), HZ)   # toe plates
    ft.add(box(H_X - 3.8, H_X + 3.8, 5.3, 6.6, 0.3, 3.4, 0.3), Y2)                                               # heel
    for sx in (1, -1):
        xa, xb = sorted((H_X + sx * 4.05, H_X + sx * 4.45))
        ft.add(box(xa, xb, -7.6, 4.6, 0.9, 2.7, 0.12), Y)
    ft.merge(bolt_row((H_X - 3.0, -7.85, 3.55), (H_X + 3.0, -7.85, 3.55), 5, (0, -0.3, 1)), ST)
    B.pair('MECH_foot{s}', ft, 'ankle{s}')
    for side, sx in (('L', 1), ('R', -1)):
        B.contact('MECH_sole' + side, 'ankle' + side, (SOLE[0] * sx, SOLE[1], SOLE[2]))


def body_pistons(B):
    """Hydraulic pistons as plain objects: the housing on the proximal joint, the rod on the distal one. set_pose aims them."""
    for (nm, sa, A, sb, Bp, Lh, Lr, rh, rr) in PISTONS:
        for side, sx in (('L', 1), ('R', -1)):
            a = Vector((A[0] * sx, A[1], A[2])); b = Vector((Bp[0] * sx, Bp[1], Bp[2])); d = (b - a).normalized()
            hg = Geo()
            hg.add(eye_ring(a, 0.32, rh, 2 * rh - 0.06), ST)
            hg.add(lathe([(rh, 0.45), (rh, Lh - 0.35), (rh + 0.12, Lh - 0.35), (rh + 0.12, Lh), (rr + 0.06, Lh), (rr + 0.06, 0.62), (0.0, 0.62)], a, d, 18), ST)
            rg = Geo()
            rg.add(eye_ring(b, 0.3, rr + 0.2, 2 * (rr + 0.2) - 0.1), ST)
            rg.add(lathe([(rr, 0.3), (rr, Lr)], b, -d, 16), CR)
            ho = B.put('MECH_piston_%s%s_housing' % (nm, side), hg, sa + side, kind='piston', origin=tuple(a), touch=['MECH_piston_%s%s_rod' % (nm, side)])
            ro = B.put('MECH_piston_%s%s_rod' % (nm, side), rg, sb + side, kind='piston', origin=tuple(b), touch=['MECH_piston_%s%s_housing' % (nm, side)])
            pa = a - B.W[sa + side].translation; pb = b - B.W[sb + side].translation
            B.pistons.append({'housing': ho, 'rod': ro, 'ja': sa + side, 'jb': sb + side, 'a': tuple(pa), 'b': tuple(pb), 'd': tuple(b - a)})


# ====================================================================================================================== pose API
POSE_KEYS = ('pelvis', 'spine', 'chest', 'neck', 'head')
LEG_L1, LEG_L2 = H_Z - K_Z, K_Z - A_Z                        # 18.0, 17.8
ARM_L1, ARM_L2 = S_Z - E_Z, E_Z - W_Z                        # 11.5, 11.0


def _aim_pistons(M):
    """Point every piston housing at its rod mount and every rod at its housing mount (pure math on the two joints' local transforms)."""
    J = M['joints']
    for p in M['pistons']:
        Mab = J[p['jb']].matrix_basis                         # jb is the direct child of ja; parent inverses are identity
        a = Vector(p['a']); b = Vector(p['b']); d0 = Vector(p['d'])
        p['housing'].rotation_euler = d0.rotation_difference(Mab @ b - a).to_euler('XYZ')
        p['rod'].rotation_euler = (-d0).rotation_difference(Mab.inverted() @ a - b).to_euler('XYZ')


def set_pose(M, pose):
    """pose = {'root': (x, y, z, yaw_deg), 'hips': (dx, dy, dz) optional pelvis offset in the root frame (sitting, crouching),
    'pelvis' / 'spine' / 'chest' / 'neck' / 'head': (rx, ry, rz) deg (+rx bends forward),
    'shoulderL/R', 'elbowL/R', 'wristL/R', 'hipL/R', 'kneeL/R', 'ankleL/R': (rx, ry, rz) deg, R values MIRRORED (same numbers as L =
    a symmetric pose); +knee rx bends the knee, -elbow rx bends the elbow, -hip rx swings the leg forward, -shoulder rx raises the arm forward,
    'fingersL/R': curl 0..1 (or a tuple of 3, one per finger), 'thumbL/R': curl 0..1}. Missing keys go to rest.
    Sets the complete local transform of every object in M['anim']; no depsgraph update."""
    J = M['joints']; root = M['root']
    r = pose.get('root', (0.0, 0.0, 0.0, 0.0))
    root.location = (r[0], r[1], r[2]); root.rotation_euler = (0.0, 0.0, r[3] * D2R)
    hp = pose.get('hips', (0.0, 0.0, 0.0)); pe = J['pelvis']; rl = pe['rest_loc']
    pe.location = (rl[0] + hp[0], rl[1] + hp[1], rl[2] + hp[2])
    for k in POSE_KEYS:
        v = pose.get(k, (0.0, 0.0, 0.0)); J[k].rotation_euler = (v[0] * D2R, v[1] * D2R, v[2] * D2R)
    for base in SIDED:
        for side, sg in (('L', 1.0), ('R', -1.0)):
            v = pose.get(base + side, (0.0, 0.0, 0.0))
            J[base + side].rotation_euler = (v[0] * D2R, sg * v[1] * D2R, sg * v[2] * D2R)
    for side, sg in (('L', 1.0), ('R', -1.0)):
        c = pose.get('fingers' + side, 0.0); cs = tuple(c) if isinstance(c, (list, tuple)) else (c, c, c)
        for i in range(3):
            for k in range(3): J['finger%s%d_%d' % (side, i, k)].rotation_euler = (0.0, sg * cs[i] * CURL[k] * D2R, 0.0)
        t = pose.get('thumb' + side, 0.0)
        for k in range(3): J['thumb%s_%d' % (side, k)].rotation_euler = (0.0, sg * t * TCURL[k] * D2R, 0.0)
    _aim_pistons(M)


def get_pose(M):
    """The current pose as a set_pose dict (R values mirrored back)."""
    J = M['joints']; r = M['root']
    out = {'root': (r.location.x, r.location.y, r.location.z, r.rotation_euler.z / D2R)}
    rl = J['pelvis']['rest_loc']; pl = J['pelvis'].location
    out['hips'] = (pl.x - rl[0], pl.y - rl[1], pl.z - rl[2])
    for k in POSE_KEYS: out[k] = tuple(a / D2R for a in J[k].rotation_euler)
    for base in SIDED:
        for side, sg in (('L', 1.0), ('R', -1.0)):
            e = J[base + side].rotation_euler; out[base + side] = (e.x / D2R, sg * e.y / D2R, sg * e.z / D2R)
    for side, sg in (('L', 1.0), ('R', -1.0)):
        out['fingers' + side] = tuple(sg * J['finger%s%d_0' % (side, i)].rotation_euler.y / D2R / CURL[0] for i in range(3))
        out['thumb' + side] = sg * J['thumb%s_0' % side].rotation_euler.y / D2R / TCURL[0]
    return out


def _wm(e):
    """World matrix from the local transforms (no depsgraph): every parent inverse in the rig is identity."""
    m = e.matrix_basis.copy(); p = e.parent
    while p is not None:
        m = p.matrix_basis @ m; p = p.parent
    return m


def _two_bone(S, T, L1, L2, pole):
    v = T - S; d = v.length; reach = d <= L1 + L2 - 0.02
    d = min(max(d, abs(L1 - L2) + 0.5), L1 + L2 - 0.02)
    u = v.normalized(); pp = Vector(pole) - u * Vector(pole).dot(u)
    if pp.length < 1e-6:
        pp = Vector((0, 1, 0)) - u * u.y
    pp.normalize()
    ca = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d); sa = math.sqrt(max(0.0, 1 - ca * ca))
    Mid = S + (u * ca + pp * sa) * L1
    cg = (L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2)
    return Mid, pp, PI - math.acos(max(-1.0, min(1.0, cg))), reach


def leg_ik(M, side, foot_pos, foot_yaw=0.0, pitch=0.0, roll=0.0, pole=None):
    """Put the sole contact MECH_sole<side> on foot_pos (world), the foot heading foot_yaw (WORLD yaw in deg, 0 = facing -Y as the root at
    yaw 0), optional pitch (+ = toes down) / roll (deg). Solves the hip (3 dof), the knee bend and the ankle analytically.
    Call it after set_pose (it reads the root, hips and pelvis). pole: world direction the knee points to (default: the foot's front).
    Returns the knee bend in degrees, or None if the target is out of reach (the leg is then stretched toward it)."""
    J = M['joints']; s = side
    Wp = _wm(J['pelvis']); Rp = Wp.to_3x3()
    H = Wp @ Vector(J['hip' + s]['rest_loc'])
    Rf = Matrix.Rotation(foot_yaw * D2R, 3, 'Z') @ Euler((pitch * D2R, roll * D2R, 0.0), 'XYZ').to_matrix()
    At = Vector(foot_pos) - Rf @ Vector((0.0, SOLE[1], SOLE[2] - A_Z))
    pl = Vector(pole) if pole is not None else Rf @ Vector((0.0, -1.0, 0.0))
    K, pp, bend, reach = _two_bone(H, At, LEG_L1, LEG_L2, pl)
    Zt = (H - K).normalized(); Yt = -(pp - Zt * pp.dot(Zt)).normalized(); Xt = Yt.cross(Zt)
    Rt = Matrix((Xt, Yt, Zt)).transposed()
    J['hip' + s].rotation_euler = (Rp.inverted() @ Rt).to_euler('XYZ')
    J['knee' + s].rotation_euler = (bend, 0.0, 0.0)
    J['ankle' + s].rotation_euler = ((Rt @ Matrix.Rotation(bend, 3, 'X')).inverted() @ Rf).to_euler('XYZ')
    _aim_pistons(M)
    return bend / D2R if reach else None


def arm_ik(M, side, hand_pos, pole=None, hand_rot=None, iters=4):
    """Put the palm contact MECH_palm<side> on hand_pos (world). pole: world direction the elbow points to (default: the rest elbow direction
    - back, a little out and down in the chest frame - swung with the arm toward the target, i.e. no upper-arm roll). hand_rot: optional world 3x3 of the hand (= of MECH_palm minus its fixed offset; the wrist turns to it);
    otherwise the wrist keeps its current local rotation. Call after set_pose. Returns the elbow bend in degrees, or None if out of reach."""
    J = M['joints']; s = side; sx = 1.0 if s == 'L' else -1.0
    Wc = _wm(J['chest']); Rc = Wc.to_3x3()
    S = Wc @ Vector(J['shoulder' + s]['rest_loc'])
    off = Vector(((PALM[0] - S_X) * sx, PALM[1] - S_Y, PALM[2] - W_Z))
    if pole is not None: pl = Vector(pole)
    else:   # default: the rest elbow direction (back, a little out and down) carried by the minimal swing from the hanging arm to the target
        d = (Vector(hand_pos) - S).normalized(); d0 = Rc @ Vector((0.0, 0.0, -1.0))
        pl = d0.rotation_difference(d) @ (Rc @ Vector((0.35 * sx, 1.0, -0.25)))
    Rw = J['wrist' + s].rotation_euler.to_matrix()
    Rh = Matrix(hand_rot) if hand_rot is not None else _wm(J['wrist' + s]).to_3x3()
    for it in range(iters):
        E, pp, bend, reach = _two_bone(S, Vector(hand_pos) - Rh @ off, ARM_L1, ARM_L2, pl)
        Zu = (S - E).normalized(); Yu = (pp - Zu * pp.dot(Zu)).normalized(); Xu = Yu.cross(Zu)
        Ru = Matrix((Xu, Yu, Zu)).transposed()
        Rfa = Ru @ Matrix.Rotation(-bend, 3, 'X')
        if hand_rot is None: Rh = Rfa @ Rw
        else: break
    J['shoulder' + s].rotation_euler = (Rc.inverted() @ Ru).to_euler('XYZ')
    J['elbow' + s].rotation_euler = (-bend, 0.0, 0.0)
    if hand_rot is not None: J['wrist' + s].rotation_euler = (Rfa.inverted() @ Matrix(hand_rot)).to_euler('XYZ')
    _aim_pistons(M)
    return bend / D2R if reach else None


def palm_rot(side, out, along):
    """World 3x3 to pass as arm_ik(hand_rot=...): turns MECH_palm<side>'s +Z (out of the palm) to `out` and its +Y (along the fingers,
    toward the tips) to `along` (world directions; `along` is made perpendicular to `out`)."""
    sx = 1.0 if side == 'L' else -1.0
    Z = Vector(out).normalized(); Yv = Vector(along); Yv = (Yv - Z * Yv.dot(Z)).normalized(); X = Yv.cross(Z)
    return Matrix((X, Yv, Z)).transposed() @ Matrix(((0, 0, -sx), (sx, 0, 0), (0, -1, 0))).inverted()


def key_pose(M, frame):
    """Keyframe the location and rotation of every animated object (M['anim']) at `frame`."""
    for o in M['anim']:
        o.keyframe_insert('location', frame=frame); o.keyframe_insert('rotation_euler', frame=frame)


def set_props(M, eyes=None, beacon=None, lamps=None):
    """Shader props live on the objects themselves (keyable): eyes -> MECH_visor; beacon -> MECH_beaconL/R + MECH_tiplight; lamps -> MECH_lamps."""
    for k, v in (('eyes', eyes), ('beacon', beacon), ('lamps', lamps)):
        if v is not None:
            for o in M['props'][k]: o[k] = float(v)


def qa_allow(a, b):
    """Designed contacts only: a 'joint' piece (waist / neck bellows) may touch the parts of the joints in its 'adj'; any part may touch the
    objects named in its 'touch' (lenses in their housings, the antenna in the crown, piston housing/rod, overgrowth on its host)."""
    for x, y in ((a, b), (b, a)):
        if x.get('kind') == 'joint' and y.get('seg') in str(x.get('adj', '')).split(','): return True
        if y.name in str(x.get('touch', '')).split(','): return True
    return False


# Baked poses (built with leg_ik / arm_ik, QA-clean). sleep: sitting on the floor (z = root z), reclined against a quay wall of local
# height SLEEP_LEDGE: the backpack's lower edge touches the wall face at local y = SLEEP_WALL; above SLEEP_LEDGE the backpack and stacks
# lean back over the quay top (up to local y = SLEEP_OVER). pull: hauling a chain up across the body (both hands on GRIP).
POSES = {
    'sleep': {
        'root': (0, 0, 0, 0), 'hips': (0, 2, -36.86), 'pelvis': (-26, 0, 0), 'spine': (8, 0, 2), 'chest': (10, 0, -3), 'neck': (17, 0, 0),
        'head': (17, 9, 6), 'shoulderL': (-12.13, -21.34, -11.96), 'elbowL': (-24.4, 0, 0), 'wristL': (22.22, 8.6, 23.3), 'shoulderR': (-3.57, -20.07, -12.76), 'elbowR': (-36.5, 0, 0),
        'wristR': (25.01, 7.34, 22.07), 'hipL': (-99.26, 6.47, 8.98), 'kneeL': (63.07, 0, 0), 'ankleL': (48.33, -8.75, -6.43), 'hipR': (-83.02, 20.05, 16.38), 'kneeR': (29.25, 0, 0),
        'ankleR': (44.08, -11.98, -23.7), 'fingersL': (0.3, 0.42, 0.5), 'thumbL': 0.25, 'fingersR': (0.35, 0.45, 0.55), 'thumbR': 0.2,
    },
    'stand': {
        'root': (0, 0, 0, 0), 'hips': (0, 0, 0), 'pelvis': (0, 0, 0), 'spine': (0, 0, 0), 'chest': (2, 0, 0), 'neck': (-3, 0, 0),
        'head': (1, 0, 0), 'shoulderL': (3, -9, 2), 'elbowL': (-16, 0, 0), 'wristL': (6, -4, 0), 'shoulderR': (3, -9, 2), 'elbowR': (-16, 0, 0),
        'wristR': (6, -4, 0), 'hipL': (0, 0, 0), 'kneeL': (0, 0, 0), 'ankleL': (0, 0, 0), 'hipR': (0, 0, 0), 'kneeR': (0, 0, 0),
        'ankleR': (0, 0, 0), 'fingersL': (0.3, 0.38, 0.45), 'thumbL': 0.2, 'fingersR': (0.3, 0.38, 0.45), 'thumbR': 0.2,
    },
    'crouch': {
        'root': (0, 0, 0, 0), 'hips': (0, 2, -12.5), 'pelvis': (24, 0, 0), 'spine': (8, 0, 0), 'chest': (6, 0, 0), 'neck': (-9, 0, 0),
        'head': (-10, 0, 0), 'shoulderL': (-56.7, -18, -5.45), 'elbowL': (-25.39, 0, 0), 'wristL': (23.36, -22.35, 22.87), 'shoulderR': (-56.7, -18, -5.45), 'elbowR': (-25.39, 0, 0),
        'wristR': (23.36, -22.35, 22.87), 'hipL': (-84.95, 4.88, 13.4), 'kneeL': (94.65, 0, 0), 'ankleL': (-33, -1.52, -4.05), 'hipR': (-84.95, 4.88, 13.4), 'kneeR': (94.65, 0, 0),
        'ankleR': (-33, -1.52, -4.05), 'fingersL': (0.8, 0.8, 0.8), 'thumbL': 0.3, 'fingersR': (0.8, 0.8, 0.8), 'thumbR': 0.3,
    },
    'reach': {
        'root': (0, 0, 0, 0), 'hips': (0, -2, -2), 'pelvis': (4, 0, -5), 'spine': (-4, 0, -5), 'chest': (-5, -3, -6), 'neck': (-10, 0, -5),
        'head': (-12, 0, 0), 'shoulderL': (-22, -16, 0), 'elbowL': (-30, 0, 0), 'wristL': (8, -6, 0), 'shoulderR': (-103.94, -3.83, -4.55), 'elbowR': (-32.66, 0, 0),
        'wristR': (0, 0, 0), 'hipL': (-30.63, 0.03, 11.02), 'kneeL': (31.87, 0, 0), 'ankleL': (-5.17, 0.73, -0.07), 'hipR': (7.06, -3.92, 7.29), 'kneeR': (13.13, 0, 0),
        'ankleR': (-24.24, 4.03, -1.81), 'fingersL': (0.3, 0.38, 0.45), 'thumbL': 0.2, 'fingersR': (0.12, 0.12, 0.12), 'thumbR': 0.1,
    },
    'pull': {
        'root': (0, 0, 0, 0), 'hips': (0, 3, -7), 'pelvis': (-4, 0, -6), 'spine': (-5, 0, -7), 'chest': (-3, 0, -6), 'neck': (8, 0, 8),
        'head': (6, 0, 4), 'shoulderL': (-25.1, -5.32, -15.34), 'elbowL': (-54.61, 0, 0), 'wristL': (7.54, -19.67, 74.25), 'shoulderR': (10.95, -10.21, -15.54), 'elbowR': (-66.8, 0, 0),
        'wristR': (19.05, 29.7, -34.09), 'hipL': (-37.04, -0.24, 11.55), 'kneeL': (9.68, 0, 0), 'ankleL': (31.28, 0.32, -1.61), 'hipR': (9.45, -9.59, 7.35), 'kneeR': (45.36, 0, 0),
        'ankleR': (-51.15, 5.71, -7.04), 'fingersL': (0.72, 0.76, 0.72), 'thumbL': 0, 'fingersR': (0.72, 0.76, 0.72), 'thumbR': 0,
    },
}
SLEEP_WALL = 16.74        # local +Y from the root to the wall plane the back rests on (POSES['sleep'])
SLEEP_LEDGE = 18.0        # local z of the quay top: nothing is beyond SLEEP_WALL below it
SLEEP_OVER = 27.65        # max local y of the sleeping mech (stack tops at local z ~39, over the quay top)
# Grip on a 1.4 m bar (chain link 8.4 x 5.0): bar centre in MECH_palm space (0, GRIP_Y, GRIP_Z), bar axis = palm X;
# fingers GRIP_FINGERS (tuple per finger, index..little), thumb 0 (lies along the index finger).
GRIP_Y, GRIP_Z = 1.5, 0.85
GRIP_FINGERS = (0.72, 0.76, 0.72)


def build(coll, overgrowth=True):
    """Build unit 07 into `coll` (rest = standing, facing -Y, the root at the pelvis' floor projection) and return M:
    'root' (MECH_root), 'joints' {name: empty}, 'parts' {name without MECH_: object or empty}, 'anim' (every object set_pose drives:
    the root, all joint empties, the piston housings/rods), 'pistons', 'props' {'eyes'|'beacon'|'lamps': [objects carrying the prop]},
    'meshes', 'steam' (empties), 'moss', 'vines', 'nest', 'gull' ({'root', 'wingL', 'wingR'}), 'chick', 'tris', 'build_s'."""
    t0 = time.time()
    if not all(os.path.exists(os.path.join(TEX, f)) for f in TEXFILES):
        subprocess.run([PY, os.path.abspath(__file__), '--tex'], check=False)
    B = Builder(coll); B.rig()
    body_pelvis(B); body_waist(B); body_chest(B); body_neck(B); body_head(B)
    body_arm(B); body_hand(B); body_leg(B); body_foot(B); body_pistons(B)
    M = {'root': B.root, 'joints': B.J, 'parts': B.parts, 'pistons': B.pistons, 'props': B.props, 'builder': B}
    M['anim'] = [B.root] + [B.J[n] for (n, par, p, R) in joint_table()] + [x for p in B.pistons for x in (p['housing'], p['rod'])]
    M['steam'] = [B.parts['steam_%d' % i] for i in range(len(STACKS))]
    M['moss'] = []; M['vines'] = []; M['nest'] = None; M['gull'] = None; M['chick'] = None
    if overgrowth and 'build_overgrowth' in globals(): build_overgrowth(B, M)
    M['meshes'] = [o for o in B.objs]
    set_pose(M, POSES['stand'])
    M['tris'] = B.tris; M['build_s'] = time.time() - t0
    return M


# ====================================================================================================================== overgrowth
# Built in POSES['sleep'] (moss draped by ray casts, vines settled as ropes against the body and the floor), then parented to the joints.
# Every piece is a plain object with its origin at its attachment point; none of them is in M['anim'] (set_pose never touches them).
# Specs are in REST-world coordinates of the host joint (carried into the sleep pose by that joint).
MOSS = [   # (name, host object, host joint, rest point near the surface, radius, cast direction in rest space (None = world down), extra touch)
    ('crown', 'head', 'head', (-1.6, 2.0, 80.3), 2.3, None, ['MECH_antenna']),
    ('brow', 'head', 'head', (2.6, -1.2, 80.1), 1.3, None, []),
    ('pauldronL', 'upperarmL', 'shoulderL', (16.6, -2.6, 72.0), 1.7, None, []),
    ('pauldronL2', 'upperarmL', 'shoulderL', (21.3, 5.4, 72.0), 1.2, None, []),
    ('pauldronR', 'upperarmR', 'shoulderR', (-17.0, -2.2, 72.0), 2.0, None, []),
    ('flapR', 'upperarmR', 'shoulderR', (-22.9, -1.5, 65.0), 1.6, (-1.0, 0.0, 0.25), []),
    ('collarL', 'chest', 'chest', (5.6, -6.2, 68.6), 1.7, None, []),
    ('collarR', 'chest', 'chest', (-5.2, -6.0, 68.2), 1.4, None, []),
    ('pack', 'chest', 'chest', (-3.5, 9.5, 69.8), 2.4, None, []),
    ('forearmL', 'forearmL', 'elbowL', (20.6, -0.5, 47.0), 1.5, (1.0, -0.2, 0.2), []),
    ('forearmR', 'forearmR', 'elbowR', (-20.6, 1.0, 46.0), 1.3, (-1.0, 0.0, 0.2), []),
    ('thighL', 'thighL', 'hipL', (8.6, -5.0, 33.0), 2.7, None, []),
    ('thighR', 'thighR', 'hipR', (-8.0, -5.0, 31.0), 3.0, None, []),
    ('kneeL', 'shinL', 'kneeL', (8.6, -6.0, 24.0), 1.7, None, []),
    ('shinR', 'shinR', 'kneeR', (-8.6, -4.3, 15.5), 2.0, None, []),
    ('footL', 'footL', 'ankleL', (8.6, -5.6, 3.7), 1.6, None, []),
    ('toeR', 'footR', 'ankleR', (-9.5, -10.2, 2.2), 1.3, None, []),
    ('beltL', 'pelvis', 'pelvis', (6.5, -5.8, 52.0), 1.4, None, []),
]
VINES = [  # (name, host object, host joint, rest anchor near the surface, length, radius)
    ('pauldronL_a', 'upperarmL', 'shoulderL', (16.2, -6.3, 68.2), 13.0, 0.306),
    ('pauldronL_b', 'upperarmL', 'shoulderL', (21.0, -6.3, 68.2), 8.0, 0.252),
    ('pauldronR_a', 'upperarmR', 'shoulderR', (-17.4, -6.3, 68.2), 16.0, 0.324),
    ('pauldronR_b', 'upperarmR', 'shoulderR', (-20.6, -6.3, 68.2), 10.0, 0.27),
    ('flapR', 'upperarmR', 'shoulderR', (-23.0, 3.0, 61.3), 12.0, 0.27),
    ('chestL', 'chest', 'chest', (3.2, -8.9, 66.0), 7.0, 0.234),
    ('chestR', 'chest', 'chest', (-4.8, -8.7, 64.5), 10.0, 0.27),
    ('jaw', 'head', 'head', (-1.2, -3.9, 73.4), 4.5, 0.18),
    ('forearmL', 'forearmL', 'elbowL', (20.5, 2.5, 49.5), 7.0, 0.234),
    ('forearmR', 'forearmR', 'elbowR', (-20.4, -1.5, 48.5), 9.0, 0.252),
    ('belt', 'pelvis', 'pelvis', (7.0, -6.6, 50.0), 6.0, 0.216),
    ('kneeL', 'shinL', 'kneeL', (10.5, -6.0, 23.0), 6.0, 0.216),
]
NEST_AT = (1.3, -0.5, 80.4)       # rest point on the crown (front-left, clear of the antenna)


def _bvh_of(objs):
    dg = bpy.context.evaluated_depsgraph_get(); V = []; F = []; own = []
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh(); Mw = o.matrix_world.copy(); b = len(V)
        V.extend(Mw @ v.co for v in me.vertices)
        for p in me.polygons: F.append([b + i for i in p.vertices]); own.append(o.name)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(V, F, all_triangles=False, epsilon=0.0), own


def _attach(B, name, gw, seg, mats, origin, touch, kind='growth', sharp=180.0, parent=None):
    """Object from WORLD-space geometry (current pose) parented to joint `seg` (or to `parent`), origin at the world point `origin`."""
    P = parent if parent is not None else B.J[seg]
    Pw = P.matrix_world.copy() if parent is not None else _wm(P)
    org = Vector(origin); R = Pw.to_3x3().normalized(); Ri = R.inverted()
    g = Geo(); g.v = [tuple(Ri @ (Vector(v) - org)) for v in gw.v]; g.f = list(gw.f); g.m = list(gw.m)
    me = B.mesh(name, g, mats, Vector((0, 0, 0)), sharp)
    o = bpy.data.objects.new(name, me); B.coll.objects.link(o)
    o.parent = P; o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = Pw.inverted() @ Matrix.Translation(org) @ R.to_4x4()
    o['seg'] = seg; o['kind'] = kind
    if touch: o['touch'] = ','.join(touch)
    B.objs.append(o); B.tris += g.ntris(); B.parts[name[5:]] = o
    return o


def _attach_local(B, name, g, seg, mats, Mw, touch, parent, Pw):
    """Object from LOCAL geometry placed at the world matrix Mw, parented to `parent` (whose world matrix is Pw)."""
    me = B.mesh(name, g, mats, Vector((0, 0, 0)), 180.0)
    o = bpy.data.objects.new(name, me); B.coll.objects.link(o)
    o.parent = parent; o.matrix_parent_inverse = Matrix.Identity(4); o.matrix_basis = Pw.inverted() @ Mw
    o['seg'] = seg; o['kind'] = 'growth'
    if touch: o['touch'] = ','.join(touch)
    B.objs.append(o); B.tris += g.ntris(); B.parts[name[5:]] = o
    return o


def _carry(B, seg, p, d=None):
    """A rest-world point (and direction) carried into the current pose by joint `seg`."""
    T = _wm(B.J[seg]) @ B.W[seg].inverted()
    return (T @ Vector(p)), ((T.to_3x3() @ Vector(d)).normalized() if d is not None else None)


def _moss_geo(tree, c, R, rng, up, h=0.32, cell=0.28, drop=3.0, tufts=True):
    """A lumpy moss cushion draped on a surface: a polar grid over a noisy disc around c, cast along -up (top + buried bottom + rim, so
    the outline is a smooth curve), with round clumps on top. Vertex layout: (top, bottom) pairs first, then the clumps."""
    X = up.orthogonal().normalized(); Y = up.cross(X)
    ph = [rng.uniform(0, 2 * PI) for _ in range(3)]; am = [rng.uniform(0.05, 0.15) for _ in range(3)]
    def rad(a): return R * (1.0 + sum(am[i] * math.sin((i + 2) * a + ph[i]) for i in range(3)))
    blobs = [(rng.uniform(-0.6, 0.6) * R, rng.uniform(-0.6, 0.6) * R, rng.uniform(0.18, 0.4) * R, rng.uniform(0.25, 0.7)) for _ in range(6)]
    c0, n0, _, _ = tree.ray_cast(c + up * drop, -up, 2 * drop)
    if c0 is None: return None, None
    nr = max(3, int(round(R / cell))); na = max(16, int(2 * PI * R / cell)); grid = {}
    for k in range(nr + 1):
        for j in range(na if k else 1):
            a = 2 * PI * j / na; t = k / nr; rr = rad(a) * t; x, y = rr * math.cos(a), rr * math.sin(a)
            loc, nor, _, _ = tree.ray_cast(c + X * x + Y * y + up * drop, -up, 2 * drop)
            if loc is None or nor.dot(up) < 0.2 or (loc - c0).dot(up) < -1.2: continue
            bump = sum(w * math.exp(-((x - bx) ** 2 + (y - by) ** 2) / (2 * s * s)) for (bx, by, s, w) in blobs)
            grid[k, j] = (loc, nor, h * (1.0 - t * t) ** 0.6 * (0.55 + bump))
    faces = []
    for j in range(na):
        j2 = (j + 1) % na
        if (0, 0) in grid and (1, j) in grid and (1, j2) in grid: faces.append([(0, 0), (1, j), (1, j2)])
    for k in range(1, nr):
        for j in range(na):
            j2 = (j + 1) % na; q = [(k, j), (k + 1, j), (k + 1, j2), (k, j2)]
            if all(x in grid for x in q): faces.append(q)
    used = sorted({x for q in faces for x in q})
    v = []; f = []; top = {}; bot = {}
    for x in used:
        loc, nor, th = grid[x]
        top[x] = len(v); v.append(tuple(loc + nor * (th - 0.05)))
        bot[x] = len(v); v.append(tuple(loc - nor * 0.09))
    edges = set()
    for q in faces:
        f.append(tuple(top[x] for x in q)); f.append(tuple(bot[x] for x in reversed(q)))
        for a in range(len(q)): edges.add((q[a], q[(a + 1) % len(q)]))
    for (a, b) in edges:
        if (b, a) not in edges: f.append((top[b], top[a], bot[a], bot[b]))
    if tufts and h > 0:     # clumps: half-sunk balls on the inner part of the cushion
        cand = [x for x in used if x[0] <= 0.72 * nr]
        for x in rng.sample(cand, min(len(cand), int(2.5 * R * R))):
            loc, nor, th = grid[x]; rr = rng.uniform(0.13, 0.28) * (1.0 - 0.4 * x[0] / nr)
            sv, sf = sphere(loc + nor * (th - 0.05 - rr * 0.45), rr, 8, 5)
            o = len(v); v.extend(tuple(p) for p in sv); f.extend(tuple(i + o for i in q) for q in sf)
    return (v, f), c0


def _rope(tree, anchor, L, r, seg=0.42, it=220):
    """Verlet rope hanging from `anchor`, pushed out of the body (BVH) and above the floor (z = r)."""
    n = max(4, int(L / seg)); P = [anchor + Vector((0.0, 0.0, -seg * k)) for k in range(n + 1)]; O = [p.copy() for p in P]
    g = Vector((0.0, 0.0, -0.035))
    for _ in range(it):
        for k in range(1, n + 1):
            v = (P[k] - O[k]) * 0.94; O[k] = P[k].copy(); P[k] = P[k] + v + g
        for _ in range(3):
            for k in range(n):
                a, b = P[k], P[k + 1]; d = b - a; l = max(d.length, 1e-6); corr = d * ((l - seg) / l)
                if k == 0: P[1] = b - corr
                else: P[k] = a + corr * 0.5; P[k + 1] = b - corr * 0.5
            for k in range(1, n + 1):
                loc, nor, _, dist = tree.find_nearest(P[k])
                if loc is not None and ((P[k] - loc).dot(nor) < 0.0 or dist < r): P[k] = loc + nor * r
                if P[k].z < r: P[k].z = r
    return P


def _clump(c, t, sz, rng, nu=10, nv=7):
    """A lumpy foliage ball, stretched 1.45x along t."""
    X, Y, A = basis(t); v, f = sphere((0, 0, 0), 1.0, nu, nv); out = []
    for p in v:
        k = sz * rng.uniform(0.84, 1.16); out.append(tuple(c + X * (p[0] * k) + Y * (p[1] * k) + A * (p[2] * k * 1.45)))
    return out, f


def _vine_geo(P, r0, rng, tree=None):
    """Stem + foliage clumps every ~2.3 m (they carry the vine at a distance, where single leaves become ink specks) + single leaves.
    tree: the body BVH; a clump is pushed off the surface so at most ~40% of it sinks in."""
    g = Geo(); g.add(sweep([tuple(p) for p in P], r0, 6, True, r0 * 0.45), 0)
    acc = 0.0; nxt = rng.uniform(0.6, 1.6); n = len(P)
    for k in range(1, n - 1):
        acc += (P[k] - P[k - 1]).length
        if acc < nxt: continue
        acc = 0.0; nxt = rng.uniform(1.2, 3.4)
        t = (P[k + 1] - P[k - 1]).normalized(); sz0 = rng.uniform(0.6, 1.3) * (1.0 - 0.35 * k / n)
        for j in range(2 if rng.random() < 0.35 else 1):          # sometimes a pair: clusters, not beads on a string
            sz = sz0 * (1.0 if j == 0 else rng.uniform(0.55, 0.8))
            off = Matrix.Rotation(rng.uniform(0, 2 * PI), 3, t) @ t.orthogonal().normalized()
            c = P[k] + off * (r0 * 0.6 + sz * rng.uniform(0.0, 0.5)) + t * (j * sz0 * rng.uniform(0.6, 1.0))
            if tree is not None:
                loc, nor, _, dist = tree.find_nearest(c)
                if loc is not None and ((c - loc).dot(nor) < 0 or dist < 0.6 * sz): c = loc + nor * (0.6 * sz)
            g.add(_clump(c, t, sz, rng), 1)
    acc = 0.0
    for k in range(1, len(P) - 1):
        acc += (P[k] - P[k - 1]).length
        if acc < rng.uniform(0.35, 0.6): continue
        acc = 0.0
        t = (P[k + 1] - P[k - 1]).normalized(); s = Matrix.Rotation(rng.uniform(0, 2 * PI), 3, t) @ t.orthogonal().normalized()
        Ln = rng.uniform(0.8, 1.3); Wd = Ln * 0.5
        base = P[k] + s * (r0 * 0.7); tip = base + (s * 0.85 + t * 0.4 + Vector((0, 0, -0.3))).normalized() * Ln
        side = (tip - base).cross(t).normalized() * (Wd / 2); mid = base + (tip - base) * 0.45
        g.add(([tuple(base), tuple(mid + side), tuple(tip), tuple(mid - side)], [(0, 1, 2, 3)]), 1)
    return g


NEST_PROF = [(1.7, 0.02), (1.92, 0.38), (1.86, 0.74), (1.6, 0.96), (1.36, 0.93), (1.12, 0.62), (0.9, 0.3)]   # core: outer foot .. rim .. cup (r, h)


def _nest_at(s):
    """(r, h, nr, nh) on NEST_PROF at the arc-length fraction s (0 = outer foot .. 1 = cup floor edge), with the outward normal."""
    P = NEST_PROF; L = [0.0]
    for i in range(len(P) - 1): L.append(L[-1] + math.hypot(P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]))
    d = min(max(s, 0.0), 1.0) * L[-1]; i = 0
    while i < len(P) - 2 and d > L[i + 1]: i += 1
    dr = P[i + 1][0] - P[i][0]; dh = P[i + 1][1] - P[i][1]; ln = math.hypot(dr, dh); u = (d - L[i]) / ln
    return P[i][0] + dr * u, P[i][1] + dh * u, dh / ln, -dr / ln


def _ribbon(pts, nrm, w0, w1):
    """A flat strip along pts, its face along the normals nrm (seaweed, feathers)."""
    v = []; f = []; n = len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized(); s = t.cross(nrm[i]).normalized() * ((w0 + (w1 - w0) * i / (n - 1)) / 2)
        v.append(tuple(p + s)); v.append(tuple(p - s))
    for i in range(n - 1): f.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    return v, f


def _nest_geo(c, rng, tree=None):
    """Twig nest, level, base centre c (world), 4 m wide: a dark mud core ring + floor + a straw lining, ~230 twigs woven round the ring
    and across its section, straight sticks laid on the outer wall (their ends stand off it: a ragged silhouette), twigs spilling over
    the crown (ray cast on `tree`), straw wisps over the rim, seaweed, a few feathers.  mats: 0 twig, 1 straw, 2 weed, 3 mud, 4 feather,
    5 driftwood."""
    g = Geo(); c = Vector(c)
    g.add(lathe_ring([(0.85, 0.0)] + NEST_PROF, c, (0, 0, 1), 32), 3)
    g.add(cyl(c, c + Vector((0, 0, 0.3)), 1.0, seg=20), 3)
    g.add(lathe([(0.0, 0.28), (1.0, 0.28), (1.13, 0.62), (0.93, 0.52), (0.5, 0.45), (0.0, 0.43)], c, (0, 0, 1), 24), 1)

    def at(a, s, off):
        r, h, nr, nh = _nest_at(s); r += nr * off; h += nh * off
        return c + Vector((r * math.cos(a), r * math.sin(a), h))

    for k in range(150):        # woven twigs
        s0 = rng.uniform(-0.02, 1.0); a0 = rng.uniform(0, 2 * PI); rt = rng.uniform(0.07, 0.125)
        Lt = rng.uniform(1.3, 2.8); ds = rng.uniform(-0.25, 0.25); lift = rng.uniform(0.0, 0.07); span = Lt / max(_nest_at(s0)[0], 0.9)
        pts = [at(a0 + span * (t / 5.0 - 0.5), s0 + ds * (t / 5.0 - 0.5), rt + lift + 0.03 * math.sin(3.0 * t + k)) for t in range(6)]
        g.add(sweep([tuple(p) for p in pts], rt, 5, True, rt * 0.7), 0 if rng.random() < 0.65 else 5)
    for k in range(30):         # straight sticks on the outer wall
        s0 = rng.uniform(0.0, 0.55); a0 = rng.uniform(0, 2 * PI); rt = rng.uniform(0.08, 0.13)
        r, h, nr, nh = _nest_at(s0); n = Vector((nr * math.cos(a0), nr * math.sin(a0), nh)); p = at(a0, s0, rt + 0.07)
        d = Matrix.Rotation(rng.uniform(-0.9, 0.9), 3, n) @ Vector((-math.sin(a0), math.cos(a0), 0.0))
        d = (d + Vector((math.cos(a0), math.sin(a0), 0.0)) * rng.uniform(-0.1, 0.3)).normalized()
        Ls = rng.uniform(1.0, 2.2); e = rng.uniform(0.35, 0.65)
        g.add(sweep([tuple(p - d * (Ls * e)), tuple(p), tuple(p + d * (Ls * (1 - e)) + Vector((0, 0, rng.uniform(-0.05, 0.12))))], rt, 5, True, rt * 0.6),
              5 if rng.random() < 0.5 else 0)
    if tree is not None:        # twigs spilling over the crown
        for k in range(24):
            a = rng.uniform(0, 2 * PI); rt = rng.uniform(0.07, 0.11); r0 = rng.uniform(1.5, 1.9); r1 = r0 + rng.uniform(0.5, 1.0); da = rng.uniform(-0.25, 0.25)
            pts = []
            for t in range(5):
                rr = r0 + (r1 - r0) * t / 4.0; aa = a + da * t / 4.0
                hit, nor, _, _ = tree.ray_cast(c + Vector((rr * math.cos(aa), rr * math.sin(aa), 2.5)), Vector((0, 0, -1)), 7.0)
                if hit is None or nor.z < 0.55 or hit.z < c.z - 1.0: break
                pts.append(hit + nor * (rt + 0.02))
            if len(pts) == 5: g.add(sweep([tuple(p) for p in pts], rt, 5, True, rt * 0.7), 5 if rng.random() < 0.5 else 0)
    for k in range(44):         # straw wisps over the rim
        a = rng.uniform(0, 2 * PI); s0 = rng.uniform(0.2, 0.45); s1 = s0 + rng.uniform(0.2, 0.45); da = rng.uniform(-0.2, 0.2)
        pts = [at(a + da * t / 3.0, s0 + (s1 - s0) * t / 3.0, 0.17 + 0.04 * math.sin(t * 2.0)) for t in range(4)]
        g.add(sweep([tuple(p) for p in pts], 0.032, 4, True, 0.02), 1)
    for k in range(8):          # seaweed over the outer wall
        a = rng.uniform(0, 2 * PI); da = rng.uniform(-0.06, 0.06); ss = [0.44 - 0.14 * t for t in range(4)]
        pts = [at(a + da * t, ss[t], 0.16) for t in range(4)]
        nrm = [Vector((_nest_at(s)[2] * math.cos(a), _nest_at(s)[2] * math.sin(a), _nest_at(s)[3])) for s in ss]
        pts.append(pts[-1] + Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, -0.5))); nrm.append(nrm[-1])
        g.add(_ribbon(pts, nrm, 0.3, 0.12), 2)
    for k in range(6):          # feathers stuck in the weave
        a = rng.uniform(0, 2 * PI); s0 = rng.uniform(0.12, 0.5); p = at(a, s0, 0.14)
        r, h, nr, nh = _nest_at(s0); n = Vector((nr * math.cos(a), nr * math.sin(a), nh))
        d = (n * 0.6 + Vector((-math.sin(a), math.cos(a), 0.0)) * rng.uniform(-0.8, 0.8) + Vector((0, 0, 0.5))).normalized()
        L = rng.uniform(0.4, 0.6); q = [p + d * (L * t / 3.0) for t in range(4)]
        g.add(_ribbon(q, [d.cross(n).cross(d).normalized()] * 4, 0.1, 0.2), 4)
        g.add(sweep([tuple(p - d * 0.1), tuple(p + d * L)], 0.014, 3, True), 4)
    return g


BIRD = 1.4                         # bird scale (gull ~1.4 m long, ~3.9 m wingspan; chick ~1.1 m)


def _bird(g):
    g.v = [(x * BIRD, y * BIRD, z * BIRD) for (x, y, z) in g.v]; return g


def _chick_geo():
    """Gull chick (local: origin at its feet, -Y forward, +Z up), ~1.1 m."""
    g = Geo()
    g.add(sphere((0, 0.04, 0.3), 0.3, 14, 9, (1.0, 1.1, 0.95)), 0)
    g.add(sphere((0, -0.14, 0.62), 0.2, 12, 8), 0)
    g.add(cyl((0, -0.31, 0.62), (0, -0.44, 0.6), 0.05, 0.012, seg=8), 1)
    for sx in (1, -1):
        g.add(sphere((0.1 * sx, -0.3, 0.68), 0.032, 6, 4), 2)
        g.add(sphere((0.27 * sx, 0.06, 0.34), 0.12, 8, 6, (0.5, 1.2, 0.9)), 0)
    return _bird(g)


def _gull_geo():
    """Adult gull body (local: origin between the feet, -Y forward, +Z up), ~1.4 m long; mats: white, grey, black, beak, leg."""
    g = Geo()
    g.add(sphere((0, 0.05, 0.45), 0.2, 16, 10, (1.0, 2.1, 1.0)), 0)                      # body
    g.add(sphere((0, 0.12, 0.53), 0.17, 12, 8, (1.05, 1.9, 0.6)), 1)                     # grey mantle
    g.add(sphere((0, -0.34, 0.68), 0.14, 12, 8), 0)                                      # head
    g.add(cyl((0, -0.44, 0.67), (0, -0.62, 0.64), 0.045, 0.015, seg=8), 3)               # beak (red spot at y < -0.5)
    g.add(hull([(0, 0.42, 0.52), (0.12, 0.45, 0.47), (-0.12, 0.45, 0.47), (0.09, 0.7, 0.47), (-0.09, 0.7, 0.47), (0, 0.66, 0.44)]), 2)   # tail
    for sx in (1, -1):
        g.add(sphere((0.08 * sx, -0.41, 0.72), 0.024, 6, 4), 2)
        g.add(cyl((0.06 * sx, 0.05, 0.3), (0.06 * sx, 0.02, 0.0), 0.022, seg=6), 4)    # leg
        g.add(([(0.06 * sx - 0.07, -0.1, 0.0), (0.06 * sx + 0.07, -0.1, 0.0), (0.06 * sx, 0.06, 0.0)], [(0, 1, 2)]), 4)
    return _bird(g)


def _wing_geo(sx):
    """Spread wing along +X*sx from the pivot (local origin); |x| runs 0..1.25 * BIRD (the wing shader's tip bands use it)."""
    out = [(0.0, -0.11), (0.45, -0.15), (0.9, -0.1), (1.25, 0.04), (1.02, 0.17), (0.6, 0.24), (0.15, 0.2)]
    v = []; f = []; n = len(out)
    for z in (0.022, -0.022):
        for (x, y) in out: v.append((x * sx, y, z + 0.06 * x * x))
    f.append(tuple(range(n)) if sx > 0 else tuple(reversed(range(n)))); f.append(tuple(range(2 * n - 1, n - 1, -1)) if sx > 0 else tuple(range(n, 2 * n)))
    for i in range(n):
        j = (i + 1) % n; f.append((i, j, n + j, n + i))
    g = Geo(); g.add((v, f), 0); return _bird(g)


def build_overgrowth(B, M):
    rng = random.Random(707); P = B.parts
    set_pose(M, POSES['sleep']); bpy.context.view_layer.update()
    body = [o for o in B.objs if o['kind'] != 'growth']
    T_all, own = _bvh_of(body)
    trees = {}
    def tree(nm):
        if nm not in trees: trees[nm] = _bvh_of([P[nm]])[0]
        return trees[nm]
    up = Vector((0.0, 0.0, 1.0)); mm = B.M
    # ---- the nest (level in the sleep pose), its chick, the gull on the rim
    c, _ = _carry(B, 'head', NEST_AT)
    hit, nor, _, _ = tree('head').ray_cast(c + up * 4.0, -up, 8.0)
    base = hit - up * 0.18
    ng = _nest_geo(base, random.Random(77), tree('head'))
    wedge, _ = _moss_geo(tree('head'), base, 1.85, random.Random(9), up, h=0.0, cell=0.3, tufts=False)
    if wedge:   # a twig/mud mound under the bowl down to the crown (the low side of the tilted head)
        wv = [Vector(p) for p in wedge[0]]
        wv = [Vector((p.x, p.y, max(base.z + 0.12, wv[i + 1].z + 0.11))) if i % 2 == 0 else p for i, p in enumerate(wv)]
        ng.add(([tuple(p) for p in wv], wedge[1]), 3)
    nest = _attach(B, 'MECH_nest', ng, 'head', [mm['twig'], mm['straw'], mm['weed'], mm['mud'], mm['gull'], mm['drift']], tuple(hit),
                   ['MECH_head', 'MECH_antenna'], sharp=60.0)
    Nw = _wm(B.J['head']) @ nest.matrix_basis
    chick_at = base + up * 0.43
    chick = _attach_local(B, 'MECH_chick', _chick_geo(), 'head', [mm['chick'], mm['beak'], mm['black']],
                          Matrix.Translation(chick_at) @ Matrix.Rotation(rng.uniform(-0.6, 0.6), 4, 'Z'), ['MECH_nest'], nest, Nw)
    ga = math.radians(205.0); foot = base + Vector((1.5 * math.cos(ga), 1.5 * math.sin(ga), 1.19))   # standing on the twig layer
    fwd = Vector((math.cos(ga + PI / 2), math.sin(ga + PI / 2), 0.0))      # tangential, walking along the rim
    Rg = Matrix((up.cross(fwd), -fwd, up)).transposed()                     # bird frame: X, Y = -forward, Z = up
    gull = _attach_local(B, 'MECH_gull', _gull_geo(), 'head', [mm['gull'], mm['gullgrey'], mm['black'], mm['beak'], mm['leg']],
                         Matrix.Translation(foot) @ Rg.to_4x4(), ['MECH_nest', 'MECH_gull_wingL', 'MECH_gull_wingR'], nest, Nw)
    wings = {}
    for side, sx in (('L', 1.0), ('R', -1.0)):
        wg = _wing_geo(sx); wme = B.mesh('MECH_gull_wing' + side, wg, [mm['gullwing']], Vector((0, 0, 0)), 180.0)
        w = bpy.data.objects.new('MECH_gull_wing' + side, wme); B.coll.objects.link(w)
        w.parent = gull; w.matrix_parent_inverse = Matrix.Identity(4); w.rotation_mode = 'XYZ'
        w.location = (0.17 * sx * BIRD, -0.08 * BIRD, 0.56 * BIRD)      # shoulder pivot in the bird frame
        fold = Euler((1.222, 0.14 * sx, 1.606 * sx), 'XYZ')             # folded back along the flank, tip drooped; (0, 0, 0) = spread
        w.rotation_euler = fold; w['fold'] = tuple(fold); w['kind'] = 'growth'; w['seg'] = 'head'; w['touch'] = 'MECH_gull'
        B.objs.append(w); B.tris += wg.ntris(); B.parts[w.name[5:]] = w; wings[side] = w
    # ---- moss pads
    moss = []
    for (nm, host, seg, p, R, d, extra) in MOSS:
        cc, dd = _carry(B, seg, p, d)
        u = dd if dd is not None else up
        geo, at = _moss_geo(tree(host), cc, R, random.Random(sum(map(ord, nm)) * 7 + 1), u)
        if not geo: continue
        g = Geo(); g.add(geo, 0)
        moss.append(_attach(B, 'MECH_moss_' + nm, g, seg, [mm['moss']], tuple(at), ['MECH_' + host] + extra + (['MECH_nest'] if host == 'head' else [])))
    # ---- vines (settled in the sleep pose)
    vines = []
    for (nm, host, seg, p, L, r) in VINES:
        a, _ = _carry(B, seg, p)
        loc, nor, _, _ = tree(host).find_nearest(a)
        a = loc + nor * (r + 0.05)
        pts = _rope(T_all, a, L, r + 0.06)
        touch = {'MECH_' + host}
        for q in pts:
            l2, n2, i2, d2 = T_all.find_nearest(q)
            if l2 is not None and d2 < r + 0.9: touch.add(own[i2])
        for mo in moss: touch.add(mo.name)
        g = _vine_geo(pts, r, rng, T_all)
        for q in g.v[::2]:      # the foliage clumps rest on whatever they hang against
            l2, n2, i2, d2 = T_all.find_nearest(Vector(q))
            if l2 is not None and d2 < 0.35: touch.add(own[i2])
        vines.append(_attach(B, 'MECH_vine_' + nm, g, seg, [mm['vine'], mm['leaf']], tuple(a), sorted(touch), sharp=60.0))
    for mo in moss:     # moss may meet the vines hanging over it
        mo['touch'] = ','.join(sorted(set(str(mo['touch']).split(',')) | {v.name for v in vines}))
    M['moss'] = moss; M['vines'] = vines; M['nest'] = nest; M['chick'] = chick
    M['gull'] = {'root': gull, 'wingL': wings['L'], 'wingR': wings['R']}


if __name__ == '__main__' and bpy is not None and '--tex' not in sys.argv:
    pass
