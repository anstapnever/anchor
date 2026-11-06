# CITY department: HIGH HARBOR, the floating island-city (ANCHOR, see BIBLE.md).
#   textures (system python + PIL, run once):   python assets/city.py --tex      -> tex/city_*.png
#   in Blender:   import city; C = city.build(coll)
# Everything is built in the local frame of the root empty CITY_root (the collar point, world (-100, 150, 320)); the top surface is at
# local z ~206..232 (world ~526..552). Moving / rotating CITY_root moves and tilts the whole city.
import math, os, sys, random, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); TEX = os.path.join(ROOT, 'tex')

# ================================================================================================================================ textures
# The facade atlas: 4 x 4 tiles, one tile = one window bay of one storey (2.4 m x 3.0 m). Two images: colour (painted, with ink
# outlines) and mask (R = wall tint, G = paint tint for shutters / doors / awnings, B = glass). The shader multiplies the colour by the
# per-house wall and shutter colours (object props), so 16 drawings give hundreds of different facades.
TW, TH = 320, 400                     # pixels per tile
BAYW, STOREY = 2.4, 3.0
DESIGNS = ['win_open', 'win_closed', 'win_half', 'win_french', 'win_arch', 'win_box', 'win_small', 'blank_plant',
           'door_arch', 'door_rect', 'shop', 'gwin_grille', 'blank', 'balc_door', 'attic', 'door_double']
DID = {n: i for i, n in enumerate(DESIGNS)}


def make_textures():
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np
    os.makedirs(TEX, exist_ok=True)
    INK = (42, 34, 54)
    S = TW / BAYW
    R = random.Random(5)
    col = Image.new('RGB', (TW * 4, TH * 4), (255, 255, 255))
    msk = Image.new('RGB', (TW * 4, TH * 4), (255, 0, 0))
    dc = ImageDraw.Draw(col); dm = ImageDraw.Draw(msk)

    class T:
        def __init__(s, i): s.ox = (i % 4) * TW; s.oy = (i // 4) * TH
        def p(s, x, y): return (s.ox + x * S, s.oy + TH - y * S)
        def rect(s, x0, y0, x1, y1, fill, m=(0, 0, 0), ol=INK, w=3):
            a = s.p(x0, y1); b = s.p(x1, y0)
            dc.rectangle([a, b], fill=fill, outline=ol, width=w if ol else 0); dm.rectangle([a, b], fill=m)
        def poly(s, pts, fill, m=(0, 0, 0), ol=INK, w=3):
            q = [s.p(*t) for t in pts]
            dc.polygon(q, fill=fill); dm.polygon(q, fill=m)
            if ol: dc.line(q + [q[0]], fill=ol, width=w, joint='curve')
        def ell(s, cx, cy, rx, ry, fill, m=(0, 0, 0), ol=INK, w=3):
            a = s.p(cx - rx, cy + ry); b = s.p(cx + rx, cy - ry)
            dc.ellipse([a, b], fill=fill, outline=ol, width=w if ol else 0); dm.ellipse([a, b], fill=m)
        def line(s, pts, fill=INK, w=3):
            dc.line([s.p(*t) for t in pts], fill=fill, width=w)
        def wall(s, pts, v):            # painted value on the wall (still wall-tinted)
            q = [s.p(*t) for t in pts]; dc.polygon(q, fill=(v, v, v)); dm.polygon(q, fill=(255, 0, 0))

    STONE = (233, 224, 205); STONE2 = (214, 203, 182); FRAME = (246, 243, 236)
    GLASS = (46, 58, 112); GLASS2 = (70, 92, 150); REFL = (150, 186, 232)

    def arch_pts(x0, x1, y0, ys, n=14, up=0.0):
        """Opening outline: rectangle x0..x1 from y0 to the spring ys, then a semicircle."""
        r = (x1 - x0) / 2; cx = (x0 + x1) / 2
        pts = [(x0, y0), (x1, y0), (x1, ys)]
        for k in range(1, n):
            a = math.pi * k / n; pts.append((cx + r * math.cos(a), ys + (r + up) * math.sin(a)))
        pts.append((x0, ys))
        return pts

    def glass(t, x0, y0, x1, y1, mull=True, arch=False):
        if arch:
            t.poly(arch_pts(x0, x1, y0, y1 - (x1 - x0) / 2), GLASS, (0, 0, 255))
        else:
            t.rect(x0, y0, x1, y1, GLASS, (0, 0, 255))
        # recess shadow on the top / left inside
        t.poly([(x0, y1), (x1, y1), (x1 - 0.06, y1 - 0.08), (x0 + 0.06, y1 - 0.08)] if not arch else [(x0, y0), (x0 + 0.07, y0), (x0 + 0.07, y1 - 0.5), (x0, y1 - 0.5)], (30, 36, 78), (0, 0, 255), None)
        # sky reflection: two diagonal bands
        h = y1 - y0; w = x1 - x0
        for k, (a, b) in enumerate(((0.18, 0.42), (0.52, 0.62))):
            yy0 = y0 + h * a; yy1 = y0 + h * b
            pts = [(x0 + 0.04, yy0), (x0 + 0.04, yy1), (x1 - 0.04, yy1 + w * 0.5), (x1 - 0.04, yy0 + w * 0.5)]
            pts = [(px, min(py, y1 - 0.1 - (0.0 if not arch else 0.4))) for px, py in pts]
            t.poly(pts, REFL if k == 0 else GLASS2, (0, 0, 255), None)
        if mull:
            xm = (x0 + x1) / 2
            t.rect(xm - 0.03, y0, xm + 0.03, y1 - (0.0 if not arch else (x1 - x0) / 2 * 0.2), FRAME, (0, 0, 0), INK, 2)
            ym = y0 + (y1 - y0) * 0.62
            t.rect(x0, ym - 0.03, x1, ym + 0.03, FRAME, (0, 0, 0), INK, 2)
        # outline of the opening
        if arch: t.line(arch_pts(x0, x1, y0, y1 - (x1 - x0) / 2) + [(x0, y0)], INK, 3)
        else: t.rect(x0, y0, x1, y1, None, None, INK, 3) if False else t.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], INK, 3)

    def shutter(t, x0, y0, x1, y1, slats=True, arch_top=None):
        t.rect(x0, y0, x1, y1, (214, 214, 214), (0, 255, 0))
        t.rect(x0 + 0.05, y0 + 0.05, x1 - 0.05, y1 - 0.05, (196, 196, 196), (0, 255, 0), (120, 120, 120), 2)
        if slats:
            y = y0 + 0.1
            while y < y1 - 0.08:
                t.line([(x0 + 0.06, y), (x1 - 0.06, y)], (140, 140, 140), 2); y += 0.075
        t.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], INK, 3)
        # hinges
        for yy in (y0 + 0.25, y1 - 0.25): t.rect(x0 - 0.01, yy - 0.02, x0 + 0.1, yy + 0.02, (60, 56, 70), (0, 0, 0), None)

    def sill(t, x0, x1, y):
        t.wall([(x0 + 0.05, y - 0.1), (x1 - 0.05, y - 0.1), (x1 - 0.1, y - 0.45), (x0 + 0.1, y - 0.45)], 236)    # rain grime under the sill
        t.rect(x0, y - 0.1, x1, y + 0.02, STONE, (0, 0, 0), INK, 3)

    def surround(t, x0, y0, x1, y1, d=0.09):
        t.rect(x0 - d, y0 - d, x1 + d, y1 + d, STONE, (0, 0, 0), INK, 3)

    def flowers(t, x0, x1, y, n=10, cols=((224, 52, 74), (246, 120, 160), (250, 246, 240), (236, 88, 52))):
        t.rect(x0, y - 0.32, x1, y, (190, 92, 58), (0, 0, 0), INK, 3)
        for k in range(n * 3):
            cx = R.uniform(x0 + 0.05, x1 - 0.05); cy = y + R.uniform(-0.05, 0.22)
            t.ell(cx, cy, 0.09, 0.08, (78, 140, 62), (0, 0, 0), None)
        for k in range(10):          # hanging leaves
            cx = R.uniform(x0 + 0.05, x1 - 0.05); t.ell(cx, y - 0.32 - R.uniform(0.0, 0.25), 0.06, 0.1, (66, 124, 56), (0, 0, 0), None)
        c = cols[R.randrange(len(cols))]
        for k in range(n):
            cx = R.uniform(x0 + 0.08, x1 - 0.08); cy = y + R.uniform(0.05, 0.28)
            t.ell(cx, cy, 0.07, 0.065, c, (0, 0, 0), (120, 40, 60), 1)

    def plinth(t):
        t.rect(-0.05, -0.05, BAYW + 0.05, 0.32, STONE2, (0, 0, 0), INK, 3)
        for x in (0.3, 0.95, 1.6, 2.2): t.line([(x, 0.0), (x, 0.32)], (150, 140, 128), 2)
        t.wall([(0, 0.32), (BAYW, 0.32), (BAYW, 0.55), (0, 0.55)], 238)      # splash grime

    def pot(t, cx, h=0.45, c=(78, 140, 62), fl=None):
        t.poly([(cx - 0.18, 0.0), (cx + 0.18, 0.0), (cx + 0.24, h), (cx - 0.24, h)], (196, 98, 60), (0, 0, 0))
        t.rect(cx - 0.27, h - 0.06, cx + 0.27, h + 0.04, (176, 84, 52), (0, 0, 0), INK, 2)
        for k in range(9): t.ell(cx + R.uniform(-0.25, 0.25), h + R.uniform(0.1, 0.55), 0.13, 0.12, c, (0, 0, 0), (40, 70, 40), 1)
        if fl:
            for k in range(6): t.ell(cx + R.uniform(-0.22, 0.22), h + R.uniform(0.2, 0.6), 0.06, 0.06, fl, (0, 0, 0), None)

    def crack(t):
        x = R.uniform(0.2, 2.2); y = R.uniform(0.6, 2.6); pts = [(x, y)]
        for k in range(4): x += R.uniform(-0.12, 0.12); y -= R.uniform(0.08, 0.2); pts.append((x, y))
        t.line(pts, (196, 196, 196), 2)

    def patch(t, v=244):
        x = R.uniform(0.0, 1.8); y = R.uniform(0.2, 2.2); w = R.uniform(0.3, 0.7); h = R.uniform(0.2, 0.5)
        t.wall([(x, y), (x + w, y + 0.05), (x + w - 0.05, y + h), (x + 0.04, y + h - 0.03)], v)

    W0, W1 = 0.7, 1.7          # standard window opening
    for i, name in enumerate(DESIGNS):
        t = T(i)
        if R.random() < 0.6: patch(t)
        if R.random() < 0.4: crack(t)
        if name in ('win_open', 'win_box', 'win_half', 'win_closed'):
            surround(t, W0, 0.9, W1, 2.4)
            sill(t, W0 - 0.18, W1 + 0.18, 0.9)
            glass(t, W0, 0.9, W1, 2.4)
            if name == 'win_closed':
                shutter(t, W0, 0.9, 1.2, 2.4); shutter(t, 1.2, 0.9, W1, 2.4)
            elif name == 'win_half':
                shutter(t, W0 - 0.52, 0.9, W0 - 0.02, 2.4); shutter(t, 1.2, 0.9, W1, 2.4)
            else:
                shutter(t, W0 - 0.56, 0.9, W0 - 0.1, 2.4); shutter(t, W1 + 0.1, 0.9, W1 + 0.56, 2.4)
            if name == 'win_box': flowers(t, W0 - 0.1, W1 + 0.1, 0.84)
        elif name == 'win_french':
            surround(t, 0.75, 0.05, 1.65, 2.5)
            glass(t, 0.75, 0.05, 1.65, 2.5)
            shutter(t, 0.22, 0.05, 0.68, 2.5); shutter(t, 1.72, 0.05, 2.18, 2.5)
            t.rect(0.62, 0.0, 1.78, 0.1, STONE, (0, 0, 0), INK, 2)
            t.line([(0.66, 0.95), (1.74, 0.95)], (40, 36, 50), 5)
            for k in range(9): xx = 0.7 + k * 0.125; t.line([(xx, 0.1), (xx, 0.95)], (40, 36, 50), 3)
            t.line([(0.7, 0.5), (1.7, 0.5)], (40, 36, 50), 2)
        elif name == 'win_arch':
            t.poly(arch_pts(W0 - 0.09, W1 + 0.09, 0.81, 1.95, up=0.09), STONE, (0, 0, 0))
            t.line(arch_pts(W0 - 0.09, W1 + 0.09, 0.81, 1.95, up=0.09) + [(W0 - 0.09, 0.81)], INK, 3)
            sill(t, W0 - 0.18, W1 + 0.18, 0.9)
            glass(t, W0, 0.9, W1, 2.45, arch=True)
            shutter(t, W0 - 0.56, 0.9, W0 - 0.1, 1.95); shutter(t, W1 + 0.1, 0.9, W1 + 0.56, 1.95)
            t.rect(1.12, 2.38, 1.28, 2.55, STONE2, (0, 0, 0), INK, 2)                # keystone
        elif name == 'win_small':
            surround(t, 0.85, 1.35, 1.55, 2.1)
            sill(t, 0.75, 1.65, 1.35)
            glass(t, 0.85, 1.35, 1.55, 2.1, mull=False)
            t.line([(1.2, 1.35), (1.2, 2.1)], FRAME, 4)
        elif name == 'blank_plant':
            # bougainvillea climbing from the lower left
            t.line([(0.25, 0.0), (0.4, 0.8), (0.3, 1.5), (0.6, 2.2), (1.2, 2.6)], (110, 78, 60), 6)
            for k in range(70):
                a = R.random(); x = 0.15 + a * 1.3 + R.gauss(0, 0.18); y = 0.6 + a * 2.0 + R.gauss(0, 0.2)
                t.ell(x, y, 0.09, 0.08, (82, 134, 60), (0, 0, 0), None)
            for k in range(90):
                a = R.random(); x = 0.2 + a * 1.4 + R.gauss(0, 0.2); y = 1.0 + a * 1.7 + R.gauss(0, 0.2)
                t.ell(x, y, 0.06, 0.055, R.choice([(222, 52, 140), (238, 92, 170), (196, 40, 120)]), (0, 0, 0), None)
            t.rect(1.9, 0.0, 2.0, 3.0, (176, 170, 168), (0, 0, 0), INK, 2)             # drain pipe
        elif name == 'blank':
            t.rect(1.95, 0.0, 2.05, 3.0, (176, 170, 168), (0, 0, 0), INK, 2)
            for yy in (0.6, 1.6, 2.6): t.rect(1.9, yy, 2.1, yy + 0.06, (120, 116, 120), (0, 0, 0), None)
            patch(t, 240); patch(t, 247)
        elif name == 'attic':
            t.ell(1.2, 0.85, 0.36, 0.36, STONE, (0, 0, 0), INK, 3)
            t.ell(1.2, 0.85, 0.26, 0.26, GLASS, (0, 0, 255), INK, 3)
            t.poly([(1.02, 0.74), (1.12, 1.04), (1.2, 1.04), (1.1, 0.74)], REFL, (0, 0, 255), None)
            t.line([(1.2, 0.59), (1.2, 1.11)], FRAME, 3); t.line([(0.94, 0.85), (1.46, 0.85)], FRAME, 3)
        elif name in ('door_arch', 'door_rect', 'door_double', 'balc_door', 'shop', 'gwin_grille'):
            if name == 'door_arch':
                t.poly(arch_pts(0.6, 1.8, 0.0, 1.85, up=0.1), STONE, (0, 0, 0)); t.line(arch_pts(0.6, 1.8, 0.0, 1.85, up=0.1) + [(0.6, 0.0)], INK, 3)
                t.poly(arch_pts(0.72, 1.68, 0.0, 1.85), (200, 200, 200), (0, 255, 0))
                for xx in (0.88, 1.04, 1.2, 1.36, 1.52): t.line([(xx, 0.05), (xx, 2.0 + 0.2 * math.sin(math.acos(min(1, abs(xx - 1.2) / 0.48))))], (150, 150, 150), 2)
                t.line(arch_pts(0.72, 1.68, 0.0, 1.85) + [(0.72, 0.0)], INK, 3)
                t.ell(1.42, 1.0, 0.05, 0.05, (60, 56, 70), (0, 0, 0), None)
                t.rect(0.5, -0.05, 1.9, 0.12, STONE2, (0, 0, 0), INK, 2)                  # step
                pot(t, 0.28, fl=(224, 52, 74)); pot(t, 2.12, c=(70, 128, 58))
            elif name == 'door_rect':
                surround(t, 0.75, 0.0, 1.65, 2.45, 0.1)
                t.rect(0.75, 0.0, 1.65, 2.05, (200, 200, 200), (0, 255, 0))
                t.rect(0.83, 1.15, 1.57, 1.95, (186, 186, 186), (0, 255, 0), (120, 120, 120), 2)
                t.rect(0.83, 0.12, 1.57, 1.0, (186, 186, 186), (0, 255, 0), (120, 120, 120), 2)
                t.line([(0.75, 0.0), (1.65, 0.0), (1.65, 2.05), (0.75, 2.05), (0.75, 0.0)], INK, 3)
                glass(t, 0.8, 2.1, 1.6, 2.42, mull=False)
                t.ell(1.5, 1.05, 0.04, 0.04, (220, 190, 90), (0, 0, 0), None)
                # wall lantern
                t.rect(0.3, 2.0, 0.42, 2.06, (40, 36, 50), (0, 0, 0), None)
                t.poly([(0.22, 1.72), (0.4, 1.72), (0.44, 2.0), (0.18, 2.0)], (255, 226, 150), (0, 0, 0))
                t.poly([(0.16, 2.0), (0.46, 2.0), (0.31, 2.15)], (40, 36, 50), (0, 0, 0))
                pot(t, 2.05, fl=(250, 246, 240))
            elif name == 'door_double':
                t.poly(arch_pts(0.25, 2.15, 0.0, 1.75, up=0.12), STONE, (0, 0, 0)); t.line(arch_pts(0.25, 2.15, 0.0, 1.75, up=0.12) + [(0.25, 0.0)], INK, 3)
                t.poly(arch_pts(0.37, 2.03, 0.0, 1.75), (196, 196, 196), (0, 255, 0))
                for xx in (0.6, 0.85, 1.2, 1.55, 1.8): t.line([(xx, 0.05), (xx, 2.3)], (140, 140, 140), 2)
                t.line([(1.2, 0.0), (1.2, 2.55)], INK, 3)
                t.line([(0.4, 0.3), (1.15, 1.4)], (150, 150, 150), 4); t.line([(1.25, 1.4), (2.0, 0.3)], (150, 150, 150), 4)
                t.line(arch_pts(0.37, 2.03, 0.0, 1.75) + [(0.37, 0.0)], INK, 3)
            elif name == 'balc_door':
                surround(t, 0.7, 0.0, 1.7, 2.5)
                glass(t, 0.7, 0.0, 1.7, 2.5)
                shutter(t, 0.16, 0.0, 0.64, 2.5); shutter(t, 1.76, 0.0, 2.24, 2.5)
            elif name == 'shop':
                t.rect(0.18, 0.0, 2.22, 2.25, STONE, (0, 0, 0), INK, 3)
                glass(t, 0.28, 0.3, 1.45, 2.05, mull=False)
                # goods on display
                for k in range(7):
                    x = 0.36 + k * 0.15; h = R.uniform(0.2, 0.45)
                    t.rect(x, 0.32, x + 0.1, 0.32 + h, R.choice([(232, 180, 60), (210, 70, 60), (90, 160, 90), (240, 236, 220), (80, 120, 200)]), (0, 0, 0), INK, 1)
                t.rect(1.55, 0.0, 2.12, 2.05, (200, 200, 200), (0, 255, 0))
                glass(t, 1.62, 1.1, 2.05, 1.95, mull=False)
                t.line([(1.55, 0.0), (2.12, 0.0), (2.12, 2.05), (1.55, 2.05), (1.55, 0.0)], INK, 3)
                # striped awning (paint tint on the coloured stripes)
                y0, y1 = 2.2, 2.8
                for k in range(8):
                    xa = 0.12 + k * 0.27; xb = xa + 0.27
                    c, m = ((230, 230, 230), (0, 255, 0)) if k % 2 == 0 else ((250, 248, 240), (0, 0, 0))
                    t.poly([(xa + 0.06, y1), (xb + 0.06, y1), (xb, y0), (xa, y0)], c, m, None)
                for k in range(8):
                    xa = 0.12 + k * 0.27
                    t.ell(xa + 0.135, y0, 0.135, 0.07, (230, 230, 230) if k % 2 == 0 else (250, 248, 240), (0, 255, 0) if k % 2 == 0 else (0, 0, 0), None)
                t.line([(0.12, y0), (0.18, y1), (2.34, y1), (2.28, y0)], INK, 3)
            elif name == 'gwin_grille':
                surround(t, 0.65, 0.75, 1.75, 2.15)
                sill(t, 0.5, 1.9, 0.75)
                glass(t, 0.65, 0.75, 1.75, 2.15)
                for k in range(7): xx = 0.72 + k * 0.16; t.line([(xx, 0.75), (xx, 2.15)], (40, 36, 50), 4)
                t.line([(0.65, 1.45), (1.75, 1.45)], (40, 36, 50), 3)
                pot(t, 2.1, c=(78, 140, 62), fl=(236, 88, 52))
    # soften the drawing a touch (gouache, not vector)
    col = col.filter(ImageFilter.SMOOTH)
    col.save(os.path.join(TEX, 'city_bay.png')); msk.save(os.path.join(TEX, 'city_baym.png'))

    # ---- roof: barrel tiles (coppi), 2 m x 2 m, value only (tinted by the roof colour)
    N = 512; im = Image.new('L', (N, N), 170); d = ImageDraw.Draw(im); s = N / 2.0
    cw = 0.2 * s; rh = 0.4 * s
    for j in range(10):
        x0 = j * cw; cap = j % 2 == 0
        for i in range(6):
            y0 = N - i * rh - (rh * 0.5 if cap else 0.0)
            v = R.randint(-14, 12) + (0 if R.random() > 0.06 else -40)
            if cap:
                d.rectangle([x0, y0 - rh - 4, x0 + cw, y0], fill=200 + v)
                d.rectangle([x0 + cw * 0.3, y0 - rh - 4, x0 + cw * 0.62, y0], fill=228 + v)
                d.rectangle([x0, y0 - rh - 4, x0 + cw * 0.12, y0], fill=168 + v)
                d.rectangle([x0 + cw * 0.88, y0 - rh - 4, x0 + cw, y0], fill=160 + v)
                d.ellipse([x0 - 1, y0 - cw * 0.35, x0 + cw + 1, y0 + cw * 0.35], fill=120)
                d.ellipse([x0 + 2, y0 - cw * 0.42, x0 + cw - 2, y0 + cw * 0.22], fill=206 + v)
            else:
                d.rectangle([x0, y0 - rh, x0 + cw, y0], fill=150 + v)
                d.rectangle([x0 + cw * 0.35, y0 - rh, x0 + cw * 0.65, y0], fill=166 + v)
                d.line([x0, y0, x0 + cw, y0], fill=110, width=3)
        d.line([x0, 0, x0, N], fill=96, width=2)
    im = im.filter(ImageFilter.SMOOTH)
    im.save(os.path.join(TEX, 'city_roof.png'))

    # ---- clock dial
    N = 512; im = Image.new('RGB', (N, N), (238, 232, 214)); d = ImageDraw.Draw(im); c = N / 2
    d.ellipse([8, 8, N - 8, N - 8], fill=(40, 46, 74)); d.ellipse([30, 30, N - 30, N - 30], fill=(244, 238, 222))
    d.ellipse([46, 46, N - 46, N - 46], outline=(42, 34, 54), width=4)
    try: f = ImageFont.truetype(r'C:\Windows\Fonts\georgiab.ttf', 44)
    except Exception: f = ImageFont.load_default()
    num = ['XII', 'I', 'II', 'III', 'IIII', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI']
    for k in range(12):
        a = math.radians(90 - k * 30); rr = c - 100
        x = c + math.cos(a) * rr; y = c - math.sin(a) * rr
        d.text((x, y), num[k], fill=(42, 34, 54), font=f, anchor='mm')
        x2 = c + math.cos(a) * (c - 58); y2 = c - math.sin(a) * (c - 58); x3 = c + math.cos(a) * (c - 72); y3 = c - math.sin(a) * (c - 72)
        d.line([x2, y2, x3, y3], fill=(42, 34, 54), width=6)
    for ang, L, w in ((math.radians(90 - 7.6 * 30), 0.48, 16), (math.radians(90 - 8 * 6), 0.7, 9)):     # 7:40
        d.line([c, c, c + math.cos(ang) * c * L, c - math.sin(ang) * c * L], fill=(30, 26, 40), width=w)
    d.ellipse([c - 16, c - 16, c + 16, c + 16], fill=(196, 150, 60))
    im.save(os.path.join(TEX, 'city_clock.png'))

    # ---- water tower lettering (mask in R, wraps once round the tank)
    im = Image.new('L', (2048, 256), 0); d = ImageDraw.Draw(im)
    try: f = ImageFont.truetype(r'C:\Windows\Fonts\impact.ttf', 118)
    except Exception: f = ImageFont.load_default()
    for x0 in (250, 1274):
        d.text((x0, 128), 'HIGH HARBOR', fill=255, font=f, anchor='lm')
    # anchor emblems between the words
    for cx in (130, 1154):
        d.ellipse([cx - 22, 40, cx + 22, 84], outline=255, width=12); d.line([cx, 84, cx, 210], fill=255, width=16)
        d.line([cx - 40, 110, cx + 40, 110], fill=255, width=12); d.arc([cx - 70, 120, cx + 70, 220], 20, 160, fill=255, width=14)
    im.save(os.path.join(TEX, 'city_sign.png'))
    print('textures written to', TEX)


if __name__ == '__main__' and '--tex' in sys.argv:
    make_textures()

# ================================================================================================================================ blender side
import numpy as np
try:
    import bpy
    from mathutils import Vector, Matrix, Euler, Quaternion
    from mathutils import noise as MN
    from mathutils.kdtree import KDTree
    from mathutils.bvhtree import BVHTree
    sys.path.insert(0, os.path.join(ROOT, 'kit'))
    import look as LK
    IN_BL = True
except ImportError:
    IN_BL = False

ORIGIN = (-100.0, 150.0, 320.0)       # the collar point = CITY_root (world)
ZR = 206.0                            # rim height above the collar point (world ~526)
HILL = np.array((-6.0, 8.0))          # plaza / campanile hill (local xy)
PLAZA_R = 19.0
WT = np.array((84.0, 66.0))           # water tower hill
RADIALS = [180.0, 128.0, 72.0, 25.0, -22.0, -70.0, -128.0]   # stepped streets, angles seen from the plaza
FALLS = [48.0, -46.0, -99.0, 154.0]                          # canals -> waterfalls, angles seen from the plaza
MILLS = [None, (195.0, 0.875), (214.0, 0.875), (250.0, 0.87), (10.0, 0.875), (100.0, 0.875)]   # W1 sits on the west street
OUT_A, OUT_B = 172.0, 140.0

# grid flags
F_STREET, F_HOUSE, F_CANAL, F_SPECIAL, F_TREE, F_GARDEN, F_MILL, F_OUT, F_LAMP, F_LINE, F_PLAZA, F_BALC = 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048
F_BUILD = F_STREET | F_HOUSE | F_CANAL | F_SPECIAL | F_MILL | F_OUT | F_PLAZA | F_GARDEN | F_LAMP | F_BALC


def sstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lin(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def wchoice(R, items):
    tot = sum(w for _, w in items); x = R.uniform(0, tot)
    for it, w in items:
        x -= w
        if x <= 0: return it
    return items[-1][0]


# ------------------------------------------------------------------------------------------------------------------ island shape
def r_outline(th):
    th = np.asarray(th, dtype=float)
    re = OUT_A * OUT_B / np.sqrt((OUT_B * np.cos(th)) ** 2 + (OUT_A * np.sin(th)) ** 2)
    f = (1 + 0.04 * np.sin(2 * th + 0.7) + 0.045 * np.sin(3 * th + 2.1) + 0.028 * np.sin(5 * th + 0.4)
         + 0.016 * np.sin(8 * th + 1.3) + 0.009 * np.sin(13 * th + 2.2))
    for c, a, w in ((3.49, 0.07, 0.22), (0.61, 0.05, 0.25), (1.83, -0.05, 0.3), (-1.05, 0.04, 0.2)):
        d = np.angle(np.exp(1j * (th - c)))
        f = f + a * np.exp(-(d / w) ** 2)
    return re * f


RBAR = float(np.mean(r_outline(np.linspace(0, math.tau, 720, endpoint=False))))


def rho_xy(x, y):
    return np.hypot(x, y) / r_outline(np.arctan2(y, x))


def inset_xy(x, y):
    """Distance inside the rim, measured along the ray from the island centre."""
    return r_outline(np.arctan2(y, x)) - np.hypot(x, y)


_FN = []
_r = random.Random(3)
for _k in range(9):
    _lam = _r.uniform(28, 95); _a = _r.uniform(0, math.tau)
    _FN.append((math.cos(_a) * math.tau / _lam, math.sin(_a) * math.tau / _lam, _r.uniform(0, math.tau), _r.uniform(0.15, 0.33)))


def fnoise(x, y):
    s = 0.0
    for kx, ky, ph, a in _FN: s = s + a * np.sin(kx * x + ky * y + ph)
    return s


def H0(x, y):
    """Natural ground height of the top (local), before the streets are cut in."""
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    th = np.arctan2(y, x); rho = np.hypot(x, y) / r_outline(th)
    h = ZR + 5.0 * (1.0 - np.clip(rho, 0, 1) ** 2)
    d1 = np.hypot(x - HILL[0], y - HILL[1])
    h = h + 21.0 * sstep(80.0, 20.0, d1)
    d2 = np.hypot(x - WT[0], y - WT[1])
    h = h + 8.0 * sstep(44.0, 8.0, d2)
    dth = np.angle(np.exp(1j * (th - 3.6)))
    h = h + 4.0 * np.exp(-((rho - 0.86) / 0.075) ** 2) * np.exp(-(dth / 0.5) ** 2)
    h = h + fnoise(x, y) * sstep(19.0, 30.0, d1)
    h = h - 0.9 * sstep(0.962, 1.0, rho)
    return h


# rock body profile: scale of the outline by height (local z), the neck sits inside the collar
S_TAB = [(5.0, 0.0459), (14.0, 0.0459), (15.5, 0.05), (20.0, 0.068), (28.0, 0.112), (38.0, 0.175), (50.0, 0.252), (65.0, 0.345),
         (80.0, 0.44), (95.0, 0.535), (110.0, 0.63), (125.0, 0.725), (140.0, 0.815), (150.0, 0.87), (160.0, 0.915), (170.0, 0.95),
         (180.0, 0.972), (190.0, 0.988), (200.0, 0.998), (210.0, 1.0)]
_SZ = np.array([a for a, b in S_TAB]); _SS = np.array([b for a, b in S_TAB])


def s_prof(z): return np.interp(z, _SZ, _SS)


class Ctx:
    pass


def rock_R(ctx, th, z, jitter=False):
    """Radius of the rock surface at angles th (array) and height z (scalar or array), without per-vertex jitter."""
    th = np.atleast_1d(np.asarray(th, dtype=float)); z = np.broadcast_to(np.asarray(z, dtype=float), th.shape)
    r = r_outline(th)
    t = sstep(30.0, 130.0, z)
    sp = s_prof(z)
    base = (1 - t) * sp * RBAR + t * sp * r
    g = np.zeros_like(th)
    for fa in ctx.fall_th:
        g = np.maximum(g, np.exp(-(np.angle(np.exp(1j * (th - fa))) / 0.07) ** 2))
    k1 = np.minimum(1.0, base / 35.0) * sstep(15.0, 28.0, z) * (1 - 0.9 * g)
    k2 = np.minimum(1.0, base / 45.0) * sstep(15.0, 34.0, z) * (1 - 0.95 * g)
    st = np.zeros_like(th)
    for lo, hi, hd in ctx.layers:
        st = st + hd * sstep(lo - 0.45, lo + 0.45, z) * sstep(hi + 0.45, hi - 0.45, z)
    nz = np.empty_like(th)
    for i in range(len(th)):
        c, s = math.cos(th[i]), math.sin(th[i]); zz = float(z[i])
        nz[i] = 6.0 * MN.noise(Vector((c * 1.6, s * 1.6, zz / 38.0))) + 2.2 * MN.noise(Vector((c * 5.0 + 11.0, s * 5.0, zz / 13.0)))
    gully = 3.5 * g * sstep(ZR - 90.0, ZR - 8.0, z)
    return base + st * 1.7 * k1 + nz * k2 - gully


def rock_point(ctx, th, z):
    R = float(rock_R(ctx, [th], z)[0])
    p = Vector((R * math.cos(th), R * math.sin(th), z))
    e = 0.02
    Ra = float(rock_R(ctx, [th + e], z)[0]); Rz = float(rock_R(ctx, [th], z + 1.0)[0])
    pa = Vector((Ra * math.cos(th + e), Ra * math.sin(th + e), z)); pz = Vector((Rz * math.cos(th), Rz * math.sin(th), z + 1.0))
    n = (pa - p).cross(pz - p).normalized()
    if n.dot(Vector((math.cos(th), math.sin(th), 0))) < 0: n = -n
    return p, n


# ------------------------------------------------------------------------------------------------------------------ mesh builder
class MB:
    """Accumulates one mesh: verts, faces, material index per face, per-loop UVs, smooth flags."""
    def __init__(s):
        s.V = []; s.F = []; s.M = []; s.UV = []; s.SM = []

    def v(s, p):
        s.V.append((float(p[0]), float(p[1]), float(p[2]))); return len(s.V) - 1

    def f(s, idx, m=0, uv=None, sm=False):
        s.F.append(tuple(idx)); s.M.append(m); s.UV.append(uv); s.SM.append(sm)

    def fh(s, idx, hint, m=0, uv=None, sm=False):
        """Face whose winding is flipped if its normal points away from the hint direction."""
        P = [s.V[i] for i in idx]; nx = ny = nz = 0.0
        for k in range(len(P)):
            a = P[k]; b = P[(k + 1) % len(P)]
            nx += (a[1] - b[1]) * (a[2] + b[2]); ny += (a[2] - b[2]) * (a[0] + b[0]); nz += (a[0] - b[0]) * (a[1] + b[1])
        if nx * hint[0] + ny * hint[1] + nz * hint[2] < 0:
            idx = list(reversed(idx)); uv = list(reversed(uv)) if uv else uv
        s.f(idx, m, uv, sm)

    def poly(s, pts, m=0, uv=None, sm=False):
        s.f([s.v(p) for p in pts], m, uv, sm)

    def n(s): return len(s.V)

    def xform(s, i0, M):
        for i in range(i0, len(s.V)):
            s.V[i] = tuple(M @ Vector(s.V[i]))

    def merge(s, o, M=None):
        i0 = len(s.V)
        s.V.extend(o.V if M is None else [tuple(M @ Vector(p)) for p in o.V])
        for f, m, uv, sm in zip(o.F, o.M, o.UV, o.SM): s.f([i + i0 for i in f], m, uv, sm)

    def mesh(s, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata(s.V, [], s.F)
        me.polygons.foreach_set('material_index', s.M)
        me.polygons.foreach_set('use_smooth', [bool(x) for x in s.SM])
        if any(u is not None for u in s.UV):
            uvl = me.uv_layers.new(name='UVMap'); flat = []
            for f, uv in zip(s.F, s.UV):
                if uv is None: flat.extend([0.0] * (2 * len(f)))
                else:
                    for a, b in uv: flat.append(a); flat.append(b)
            uvl.data.foreach_set('uv', flat)
        me.update()
        return me


def box(mb, c, h, m=0, R=None):
    cs = ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))
    idx = []
    for sx, sy, sz in cs:
        p = Vector((sx * h[0], sy * h[1], sz * h[2]))
        if R is not None: p = R @ p
        idx.append(mb.v((c[0] + p[0], c[1] + p[1], c[2] + p[2])))
    ms = m if isinstance(m, (list, tuple)) else [m] * 6
    for k, f in enumerate(((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5))):
        mb.f([idx[i] for i in f], ms[k])


def frame_of(d, up=(0.0, 0.0, 1.0)):
    d = Vector(d).normalized(); u = Vector(up)
    if abs(d.dot(u)) > 0.95: u = Vector((1.0, 0.0, 0.0)) if abs(d.x) < 0.9 else Vector((0.0, 1.0, 0.0))
    x = u.cross(d).normalized(); y = d.cross(x).normalized()
    return x, y, d


def beam(mb, p0, p1, w, t, m=0, up=(0.0, 0.0, 1.0)):
    """Box from p0 to p1 with cross-section w (side) x t (up)."""
    p0 = Vector(p0); p1 = Vector(p1); L = (p1 - p0).length
    x, y, d = frame_of(p1 - p0, up)
    R = Matrix((x, y, d)).transposed()
    box(mb, (p0 + p1) / 2, (w / 2, t / 2, L / 2), m, R)


def prism(mb, pts, z0, z1, m=0, mtop=None, mbot=None):
    b = [mb.v((x, y, z0)) for x, y in pts]; t = [mb.v((x, y, z1)) for x, y in pts]; n = len(pts)
    mb.f(list(reversed(b)), m if mbot is None else mbot); mb.f(t, m if mtop is None else mtop)
    for i in range(n):
        j = (i + 1) % n; mb.f([b[i], b[j], t[j], t[i]], m)


def ring_rect(mb, c, ho, hi, z0, z1, ms=0, mt=None, mbot=None):
    """Rectangular ring (cornice, parapet): outer half sizes ho, inner half sizes hi."""
    O = [(c[0] - ho[0], c[1] - ho[1]), (c[0] + ho[0], c[1] - ho[1]), (c[0] + ho[0], c[1] + ho[1]), (c[0] - ho[0], c[1] + ho[1])]
    I = [(c[0] - hi[0], c[1] - hi[1]), (c[0] + hi[0], c[1] - hi[1]), (c[0] + hi[0], c[1] + hi[1]), (c[0] - hi[0], c[1] + hi[1])]
    o0 = [mb.v((x, y, z0)) for x, y in O]; o1 = [mb.v((x, y, z1)) for x, y in O]
    i0 = [mb.v((x, y, z0)) for x, y in I]; i1 = [mb.v((x, y, z1)) for x, y in I]
    mt = ms if mt is None else mt; mbot = ms if mbot is None else mbot
    for k in range(4):
        j = (k + 1) % 4
        mb.f([o1[k], o1[j], i1[j], i1[k]], mt)
        mb.f([o0[k], i0[k], i0[j], o0[j]], mbot)
        mb.f([o0[k], o0[j], o1[j], o1[k]], ms)
        mb.f([i0[k], i1[k], i1[j], i0[j]], ms)


def lathe(mb, prof, n, m=0, c=(0.0, 0.0, 0.0), sm=True, a0=0.0, caps=True, uvk=None, sx=1.0, sy=1.0):
    rings = []
    for r, z in prof:
        if r <= 1e-6: rings.append(mb.v((c[0], c[1], c[2] + z)))
        else: rings.append([mb.v((c[0] + sx * r * math.cos(a0 + math.tau * k / n), c[1] + sy * r * math.sin(a0 + math.tau * k / n), c[2] + z)) for k in range(n)])
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        for k in range(n):
            k2 = (k + 1) % n
            uv = None
            if uvk is not None:
                (ra, za), (rb, zb) = prof[i], prof[i + 1]
                uv = [(k / n * uvk[0], za * uvk[1]), (k2 / n * uvk[0] if k2 else uvk[0], za * uvk[1]), (k2 / n * uvk[0] if k2 else uvk[0], zb * uvk[1]), (k / n * uvk[0], zb * uvk[1])]
            if isinstance(A, int) and isinstance(B, int): continue
            if isinstance(A, int): mb.f([A, B[k2], B[k]], m, uv[:3] if uv else None, sm)
            elif isinstance(B, int): mb.f([A[k], A[k2], B], m, uv[:3] if uv else None, sm)
            else: mb.f([A[k], A[k2], B[k2], B[k]], m, uv, sm)
    if caps:
        if not isinstance(rings[0], int): mb.f(list(reversed(rings[0])), m, None, False)
        if not isinstance(rings[-1], int): mb.f(list(rings[-1]), m, None, False)
    return rings


def cyl(mb, p0, p1, r0, r1=None, n=8, m=0, sm=True, caps=True):
    r1 = r0 if r1 is None else r1
    p0 = Vector(p0); p1 = Vector(p1); x, y, d = frame_of(p1 - p0)
    A = [mb.v(p0 + (x * math.cos(math.tau * k / n) + y * math.sin(math.tau * k / n)) * r0) for k in range(n)]
    B = [mb.v(p1 + (x * math.cos(math.tau * k / n) + y * math.sin(math.tau * k / n)) * r1) for k in range(n)]
    for k in range(n):
        k2 = (k + 1) % n; mb.f([A[k], A[k2], B[k2], B[k]], m, None, sm)
    if caps: mb.f(list(reversed(A)), m); mb.f(B, m)


def tube(mb, pts, radii, n=6, m=0, sm=True, cap0=True, cap1=True):
    """Tube along a polyline (parallel-transport frames)."""
    P = [Vector(p) for p in pts]; rings = []
    t0 = (P[1] - P[0]).normalized(); x, y, _ = frame_of(t0)
    for i, p in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        x = (x - t * x.dot(t)).normalized(); y = t.cross(x)
        rings.append([mb.v(p + (x * math.cos(math.tau * k / n) + y * math.sin(math.tau * k / n)) * radii[i]) for k in range(n)])
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        for k in range(n):
            k2 = (k + 1) % n; mb.f([A[k], A[k2], B[k2], B[k]], m, None, sm)
    if cap0: mb.f(list(reversed(rings[0])), m)
    if cap1: mb.f(rings[-1], m)


def sphere(mb, c, r, nu=10, nv=6, m=0, sm=True, sq=(1.0, 1.0, 1.0), R=None, jit=0.0):
    prof = [(0.0, -1.0)] + [(math.sin(math.pi * k / nv), -math.cos(math.pi * k / nv)) for k in range(1, nv)] + [(0.0, 1.0)]
    i0 = mb.n()
    lathe(mb, [(a * r, b * r) for a, b in prof], nu, m, (0.0, 0.0, 0.0), sm, R.uniform(0, 6.3) if R else 0.0, caps=False)
    for i in range(i0, mb.n()):
        x, y, z = mb.V[i]
        if jit and R:
            k = 1.0 + R.uniform(-jit, jit); x *= k; y *= k; z *= k
        mb.V[i] = (c[0] + x * sq[0], c[1] + y * sq[1], c[2] + z * sq[2])


def slab(mb, pts, tk, m, uv=None, ms=None):
    """Closed slab under a top polygon (CCW seen from above), thickness tk straight down."""
    n = len(pts)
    T = [mb.v(p) for p in pts]; B = [mb.v((p[0], p[1], p[2] - tk)) for p in pts]
    ms = m if ms is None else ms
    mb.f(T, m, uv); mb.f(list(reversed(B)), ms)
    for i in range(n):
        j = (i + 1) % n; mb.f([B[i], B[j], T[j], T[i]], ms)


def arch_plate(mb, W, H, T, ow, sill, spring, M=None, m=0, nseg=12):
    """A wall plate W (x) by H (z), thickness T (y, front at -T/2) with an arched opening ow wide from z=sill, semicircle above
    z=spring. Built as a ring of quads between the outline and the opening (rays from the opening centre)."""
    r = ow / 2; O = (0.0, (sill + spring) / 2)
    outer = [(-W / 2, 0.0), (W / 2, 0.0), (W / 2, H), (-W / 2, H)]
    inner = [(-r, sill), (r, sill), (r, spring)] + [(r * math.cos(math.pi * k / nseg), spring + r * math.sin(math.pi * k / nseg)) for k in range(1, nseg)] + [(-r, spring)]
    def ang(p): return math.atan2(p[1] - O[1], p[0] - O[0]) % math.tau
    angs = sorted(set([round(ang(p), 6) for p in outer + inner] + [k * math.tau / 32 for k in range(32)]))
    def hit(poly, a):
        d = (math.cos(a), math.sin(a)); best = None
        for i in range(len(poly)):
            p = poly[i]; q = poly[(i + 1) % len(poly)]
            ex, ey = q[0] - p[0], q[1] - p[1]
            den = d[0] * (-ey) - d[1] * (-ex)
            if abs(den) < 1e-12: continue
            wx, wy = p[0] - O[0], p[1] - O[1]
            t = (wx * (-ey) - wy * (-ex)) / den; u = (d[0] * wy - d[1] * wx) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best): best = t
        return (O[0] + d[0] * best, O[1] + d[1] * best)
    po = [hit(outer, a) for a in angs]; pi_ = [hit(inner, a) for a in angs]
    def P(p, yy):
        v = Vector((p[0], yy, p[1]))
        return M @ v if M is not None else v
    n = len(angs)
    fo = [mb.v(P(p, -T / 2)) for p in po]; bo = [mb.v(P(p, T / 2)) for p in po]
    fi = [mb.v(P(p, -T / 2)) for p in pi_]; bi = [mb.v(P(p, T / 2)) for p in pi_]
    yv = (M.to_3x3() @ Vector((0, 1, 0))) if M is not None else Vector((0, 1, 0))
    for k in range(n):
        j = (k + 1) % n
        mb.fh([fi[k], fo[k], fo[j], fi[j]], -yv, m)
        mb.fh([bi[k], bo[k], bo[j], bi[j]], yv, m)
        mo = (Vector(mb.V[fo[k]]) + Vector(mb.V[fo[j]])) / 2; mi = (Vector(mb.V[fi[k]]) + Vector(mb.V[fi[j]])) / 2
        c3 = P(O, 0.0)
        mb.fh([fo[k], bo[k], bo[j], fo[j]], mo - c3, m)
        mb.fh([fi[k], bi[k], bi[j], fi[j]], c3 - mi, m)


# ------------------------------------------------------------------------------------------------------------------ materials
def _patch(maker, name, colfn, extra, **kw):
    """Build with LK.cel / LK.glowmat, then wire an alpha or glow socket computed in the same node tree."""
    box_ = {}
    def cf(nb):
        for k, fn in extra.items(): box_[k] = fn(nb)
        return colfn(nb)
    m = maker(name, cf, **kw); nt = m.node_tree
    if 'alpha' in box_:
        mx = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeMixShader'][0]; nt.links.new(box_['alpha'], mx.inputs['Fac'])
    if 'glow' in box_:
        av = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'glow'][0]; nt.links.new(box_['glow'], av.inputs['Value'])
    return m


def _stone(nb, c1='#ddd0b6', c2='#c8b796', mort='#8f8271', bw=0.95, rh=0.42):
    x, y, z = nb.xyz(nb.coord('Object'))
    v = nb.vec(nb.add(x, y), z, 0.0)
    br = nb.new('ShaderNodeTexBrick', props={'offset': 0.5}, ins={'Vector': v, 'Color1': c1, 'Color2': c2, 'Mortar': mort, 'Scale': 1.0,
                                                                  'Mortar Size': 0.028, 'Brick Width': bw, 'Row Height': rh, 'Bias': 0.0})
    return br.outputs['Color']


FAR_INK = dict(d0=140.0, d1=650.0, k=0.3)        # ink weight x1 up to d0 metres from the camera, x k beyond d1 (build(far_ink=...))


def ink_far(m, d0, d1, k):
    """The pen thins with distance: the material's ink AOV goes from its weight to weight*k over d0..d1 m of view distance,
    so 300 houses at 600 m read as colour, not as a black tangle of 1-px lines."""
    nt = m.node_tree
    av = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'ink']
    if not av or av[0].inputs['Value'].is_linked: return
    w = float(av[0].inputs['Value'].default_value)
    if w <= 0.0 or k >= 1.0: return
    cam = nt.nodes.new('ShaderNodeCameraData'); mr = nt.nodes.new('ShaderNodeMapRange')
    mr.interpolation_type = 'SMOOTHSTEP'; mr.clamp = True
    mr.inputs['From Min'].default_value = d0; mr.inputs['From Max'].default_value = d1
    mr.inputs['To Min'].default_value = w; mr.inputs['To Max'].default_value = w * k
    nt.links.new(cam.outputs['View Distance'], mr.inputs['Value']); nt.links.new(mr.outputs['Result'], av[0].inputs['Value'])


def materials(far_ink=None):
    P = lambda f: os.path.join(TEX, f)
    M = {}

    def wall(nb):
        uv = nb.tc().outputs['UV']
        c = nb.image(P('city_bay.png'), uv, 'EXTEND', 'Linear')
        mk = nb.image(P('city_baym.png'), uv, 'EXTEND', 'Linear', noncolor=True)
        mr, mg, _ = nb.xyz(mk)
        c = nb.cmul(c, nb.mixc((1, 1, 1, 1), nb.objattr('wallC', 'Color'), mr))
        c = nb.cmul(c, nb.mixc((1, 1, 1, 1), nb.objattr('shutC', 'Color'), mg))
        z = nb.xyz(nb.coord('Object'))[2]
        c = nb.mixc(c, '#cdbfa4', nb.mul(nb.step(z, 0.3), mr))
        return c
    M['wall'] = LK.cel('M_city_wall', wall, vary=0.05, vscale=0.12, grime=0.3, wscale=0.8, rim=0.3)

    def roof(nb):
        t = nb.xyz(nb.image(P('city_roof.png'), nb.tc().outputs['UV'], 'REPEAT', 'Linear', noncolor=True))[0]
        c = nb.cscale(nb.objattr('roofC', 'Color'), nb.remap(t, 0.35, 0.92, 0.58, 1.1))
        li = nb.smooth(nb.noise(nb.coord('Object', 0.4), 1.0, 3.0, 0.6), 0.62, 0.66)
        return nb.mixc(c, nb.mixc(c, '#c9c27e', 0.45), li)
    M['roof'] = LK.cel('M_city_roof', roof, vary=0.06, vscale=0.2, grime=0.25, wscale=0.8, spec=0.12)
    M['trim'] = LK.cel('M_city_trim', '#efe8d8', vary=0.05, grime=0.3, wscale=0.8)
    M['stone'] = LK.cel('M_city_stone', lambda nb: _stone(nb), vary=0.06, grime=0.4, wscale=0.6, paint=0.25)

    def stone_m(nb):                                   # rubble courses on UV metres (mill ground storeys)
        u, v, _ = nb.xyz(nb.tc().outputs['UV'])
        j = nb.noise(nb.vec(nb.mul(u, 0.7), nb.mul(v, 0.7), 2.0), 1.0, 2.0, 0.5)
        br = nb.new('ShaderNodeTexBrick', props={'offset': 0.43, 'squash': 0.8, 'squash_frequency': 3},
                    ins={'Vector': nb.vec(nb.add(u, nb.mul(j, 0.25)), v, 0.0), 'Color1': '#d8c6a4', 'Color2': '#b49c7c', 'Mortar': '#8a7a69',
                         'Scale': 1.0, 'Mortar Size': 0.035, 'Mortar Smooth': 0.2, 'Brick Width': 0.62, 'Row Height': 0.34, 'Bias': 0.0})
        return nb.mixc(br.outputs['Color'], '#a8977f', nb.mul(nb.smooth(j, 0.55, 0.75), 0.35))
    M['stone_m'] = LK.cel('M_city_stone_m', stone_m, vary=0.08, grime=0.5, wscale=0.6, paint=0.3)
    M['iron'] = LK.cel('M_city_iron', '#323849', spec=0.5, grime=0.3, rust=0.3, chips=0.2, wscale=0.8)

    def terrace(nb):
        x, y, z = nb.xyz(nb.coord('Object'))
        g = nb.mx(nb.step(0.93, nb.math('FRACT', nb.mul(x, 2.2))), nb.step(0.93, nb.math('FRACT', nb.mul(y, 2.2))))
        return nb.mixc('#e3c7a2', '#b89a7c', g)
    M['terrace'] = LK.cel('M_city_terrace', terrace, vary=0.06, grime=0.4, wscale=0.6)

    def wood(nb):
        P_ = nb.coord('Object'); x, y, z = nb.xyz(P_)
        g = nb.wave(nb.vec(nb.add(x, y), nb.mul(z, 0.2), 0.0), 3.0, 'BANDS', 'X', 'SIN', 6.0, 2.0)
        return nb.mixc('#8a5a3a', '#6e4630', nb.smooth(g, 0.55, 0.62))
    M['wood'] = LK.cel('M_city_wood', wood, vary=0.06, grime=0.3)
    M['dome'] = LK.cel('M_city_dome', lambda nb: nb.objattr('roofC', 'Color'), vary=0.05, spec=0.3, grime=0.2)

    def leaf(nb):
        P_ = nb.coord('Object'); base = nb.objattr('leafC', 'Color')
        v = nb.voronoi(nb.vmath('SCALE', P_, scale=1.15), 1.0, 'F1', out='Distance')
        c = nb.mixc(nb.cscale(base, 1.2), nb.cscale(base, 0.8), nb.smooth(v, 0.32, 0.56))
        vf = nb.voronoi(nb.vmath('SCALE', P_, scale=2.7), 1.0, 'F1', out='Distance')
        c = nb.mixc(c, '#f4c430', nb.mul(nb.smooth(vf, 0.14, 0.1), nb.objattr('fruit')))
        return c
    M['leaf'] = LK.cel('M_city_leaf', leaf, ink=0.55, paint=0.6, rim=0.45, vary=0.08, vscale=0.3)
    M['bark'] = LK.cel('M_city_bark', '#76574a', vary=0.08, grime=0.3)
    M['pot'] = LK.cel('M_city_pot', '#c8553d', vary=0.08, grime=0.35, wscale=0.6)

    def ground(nb):
        P_ = nb.coord('Object'); gm = nb.attr('gm', 'Color', 'GEOMETRY'); gr, gg, gb = nb.xyz(gm)
        n1 = nb.noise(nb.vmath('SCALE', P_, scale=0.045), 1.0, 3.0, 0.6)
        n2 = nb.noise(nb.vmath('SCALE', P_, scale=0.21), 1.0, 2.0, 0.6)
        g = nb.mixc('#86b44c', '#64983c', nb.smooth(n1, 0.47, 0.53))
        g = nb.mixc(g, '#b0b45c', nb.mul(nb.smooth(n2, 0.63, 0.67), 0.75))
        vd = nb.voronoi(nb.vmath('SCALE', P_, scale=1.3), 1.0, 'F1', out='Distance')
        vc = nb.xyz(nb.voronoi(nb.vmath('SCALE', P_, scale=1.3), 1.0, 'F1', out='Color'))[0]
        fl = nb.ramp(vc, [(0.0, '#ffffff'), (0.4, '#f4d34a'), (0.7, '#f08cb4'), (0.88, '#b98ae8')])
        g = nb.mixc(g, fl, nb.mul(nb.smooth(vd, 0.17, 0.12), nb.smooth(gb, 0.3, 0.7)))
        # painted grass near the camera: dark tufts with a lit tip, sparse wild flowers (faded out by 160 m so far shots stay calm)
        nk = nb.smooth(nb.new('ShaderNodeCameraData').outputs['View Distance'], 160.0, 60.0)
        n3 = nb.noise(nb.vmath('SCALE', P_, scale=0.6), 1.0, 2.0, 0.5)
        td = nb.voronoi(nb.vmath('SCALE', P_, scale=1.8), 1.0, 'F1', out='Distance')
        g = nb.mixc(g, '#4a8034', nb.mul(nb.mul(nb.smooth(td, 0.36, 0.15), nb.smooth(n3, 0.3, 0.5)), nb.mul(nk, 0.8)))
        g = nb.mixc(g, '#b9d46a', nb.mul(nb.mul(nb.smooth(td, 0.11, 0.03), nb.smooth(n3, 0.4, 0.6)), nb.mul(nk, 0.7)))
        fd = nb.voronoi(nb.vmath('SCALE', P_, scale=0.55), 1.0, 'F1', out='Distance')
        fc = nb.xyz(nb.voronoi(nb.vmath('SCALE', P_, scale=0.55), 1.0, 'F1', out='Color'))[0]
        fl2 = nb.ramp(fc, [(0.0, '#ffffff'), (0.5, '#f4d34a'), (0.8, '#f08cb4')])
        g = nb.mixc(g, fl2, nb.mul(nb.mul(nb.smooth(fd, 0.085, 0.055), nb.smooth(n2, 0.42, 0.55)), nk))
        town = nb.smooth(nb.add(gr, nb.mul(nb.sub(n2, 0.5), 0.7)), 0.42, 0.5)
        tc = nb.mixc('#cdb995', '#b8a07c', nb.smooth(n1, 0.45, 0.55))
        pv = nb.voronoi(nb.vmath('SCALE', P_, scale=0.9), 1.0, 'DISTANCE_TO_EDGE', out='Distance')
        tc = nb.mixc(tc, '#9a876c', nb.mul(nb.smooth(pv, 0.05, 0.02), 0.6))
        soil = nb.mixc('#8a6646', '#6f5038', nb.smooth(n2, 0.45, 0.55))
        c = nb.mixc(g, soil, nb.smooth(gg, 0.4, 0.6))
        return nb.mixc(c, tc, town)
    M['ground'] = LK.cel('M_city_ground', ground, ink=0.5, paint=1.0, vary=0.08, vscale=0.05, rim=0.25)

    def rock(nb):
        P_ = nb.coord('Object'); x, y, z = nb.xyz(P_)
        nz = nb.xyz(nb.tc().outputs['Normal'])[2]
        w1 = nb.noise(nb.vmath('SCALE', P_, scale=0.012), 1.0, 2.0, 0.5)
        w2 = nb.noise(nb.vmath('SCALE', P_, scale=0.06), 1.0, 2.0, 0.5)
        zz = nb.add(z, nb.add(nb.mul(nb.sub(w1, 0.5), 22.0), nb.mul(nb.sub(w2, 0.5), 4.0)))
        band = nb.math('FRACT', nb.math('DIVIDE', zz, 31.0))
        col = nb.ramp(band, [(0.0, '#c99a4e'), (0.15, '#e2c48e'), (0.26, '#a8603a'), (0.41, '#8b7f9b'), (0.54, '#c7a26a'),
                             (0.66, '#9d6b4c'), (0.79, '#7c7192'), (0.9, '#d5b17c')])
        fine = nb.math('FRACT', nb.math('DIVIDE', zz, 5.3))
        col = nb.mixc(col, nb.cmul(col, '#a090b0'), nb.mul(nb.smooth(fine, 0.88, 0.92), 0.6))
        cr = nb.voronoi(nb.vmath('MULTIPLY', P_, (0.05, 0.05, 0.022)), 1.0, 'DISTANCE_TO_EDGE', out='Distance')
        cm = nb.noise(nb.vmath('SCALE', P_, scale=0.02), 1.0, 2.0, 0.5)
        col = nb.mixc(col, '#5a4c6c', nb.mul(nb.smooth(cr, 0.016, 0.006), nb.mul(nb.smooth(cm, 0.35, 0.55), 0.7)))
        mn = nb.noise(nb.vmath('SCALE', P_, scale=0.15), 1.0, 3.0, 0.6)
        col = nb.mixc(col, '#6b8f3a', nb.mul(nb.smooth(nz, 0.4, 0.56), nb.smooth(mn, 0.35, 0.45)))
        col = nb.mixc(col, '#7fb048', nb.smooth(nz, 0.68, 0.8))
        # dark drip streaks down from the rim and the ledges
        st = nb.noise(nb.vec(nb.mul(nb.math('ARCTAN2', y, x), 40.0), nb.mul(z, 0.02), 0.0), 1.0, 2.0, 0.6)
        col = nb.mixc(col, nb.cmul(col, '#8c80a6'), nb.mul(nb.smooth(st, 0.6, 0.64), nb.smooth(nz, 0.2, -0.2)))
        return col
    M['rock'] = LK.cel('M_city_rock', rock, ink=0.7, paint=1.0, vary=0.1, vscale=0.03, grime=0.3, wscale=0.08, rim=0.4, deep=0.6, steps=4)

    def street(nb):
        P_ = nb.coord('Object')
        v = nb.vmath('SCALE', P_, scale=1.35)
        d = nb.voronoi(v, 1.0, 'DISTANCE_TO_EDGE', out='Distance')
        k = nb.xyz(nb.voronoi(v, 1.0, 'F1', out='Color'))[0]
        c = nb.mixc('#dacbad', '#c5b293', nb.step(0.6, k))
        c = nb.mixc(c, '#e8ddc4', nb.step(0.86, k))
        return nb.mixc(c, '#8f826f', nb.smooth(d, 0.07, 0.035))
    M['street'] = LK.cel('M_city_street', street, vary=0.06, vscale=0.08, grime=0.35, wscale=0.5, paint=0.2)
    M['step'] = LK.cel('M_city_step', '#e4d7bb', vary=0.05, grime=0.3, wscale=0.5)

    def plaza(nb):
        x, y, z = nb.xyz(nb.coord('Object'))
        r = nb.math('SQRT', nb.add(nb.mul(x, x), nb.mul(y, y))); a = nb.math('ARCTAN2', y, x)
        rings = nb.step(0.9, nb.math('FRACT', nb.math('DIVIDE', r, 1.3)))
        rays = nb.step(0.94, nb.math('FRACT', nb.mul(a, nb.math('DIVIDE', nb.math('ROUND', nb.mul(r, 2.8)), 6.2832))))
        band = nb.step(0.5, nb.math('FRACT', nb.math('DIVIDE', r, 5.2)))
        c = nb.mixc('#e2d4b6', '#cdb48c', band)
        return nb.mixc(c, '#8f826f', nb.mx(rings, rays))
    M['plaza'] = LK.cel('M_city_plaza', plaza, vary=0.06, vscale=0.06, grime=0.3, wscale=0.5)

    def water(nb):
        u, v, _ = nb.xyz(nb.tc().outputs['UV']); t = nb.attr('seaT', 'Fac')
        vv = nb.sub(v, nb.mul(t, 1.6))
        n1 = nb.noise(nb.vec(nb.mul(u, 3.0), nb.mul(vv, 0.25), 0.0), 1.0, 2.0, 0.6)
        n2 = nb.noise(nb.vec(nb.mul(u, 8.0), nb.mul(vv, 0.7), 2.0), 1.0, 1.0, 0.5)
        c = nb.mixc('#2a9fc0', '#58d0dc', nb.smooth(n1, 0.45, 0.55))
        return nb.mixc(c, '#e2fbff', nb.smooth(nb.add(nb.mul(n1, 0.5), nb.mul(n2, 0.6)), 0.74, 0.78))
    M['water'] = LK.cel('M_city_water', water, ink=0.0, spec=0.8, rim=0.2, vary=0.0, wet=0.0)

    def fall(nb):
        u, v, _ = nb.xyz(nb.tc().outputs['UV']); t = nb.attr('seaT', 'Fac')
        vv = nb.sub(v, nb.mul(t, 9.0))
        s1 = nb.noise(nb.vec(nb.mul(u, 14.0), nb.mul(vv, 0.035), 0.0), 1.0, 2.0, 0.6)
        s2 = nb.noise(nb.vec(nb.mul(u, 40.0), nb.mul(vv, 0.09), 3.0), 1.0, 1.0, 0.5)
        c = nb.mixc('#64b4e8', '#b4ecfc', nb.smooth(s1, 0.42, 0.5))
        c = nb.mixc(c, '#ffffff', nb.smooth(nb.add(nb.mul(s1, 0.6), nb.mul(s2, 0.5)), 0.6, 0.64))
        return nb.mixc(c, '#ffffff', nb.add(nb.smooth(v, 3.0, 0.0), nb.smooth(nb.math('DIVIDE', v, nb.objattr('fallL')), 0.55, 0.85)))
    def fall_a(nb):
        u, v, _ = nb.xyz(nb.tc().outputs['UV']); t = nb.attr('seaT', 'Fac')
        vv = nb.sub(v, nb.mul(t, 9.0)); k = nb.math('DIVIDE', v, nb.objattr('fallL'))
        fr = nb.noise(nb.vec(nb.mul(u, 9.0), nb.mul(vv, 0.02), 7.0), 1.0, 3.0, 0.6)
        return nb.smooth(nb.add(fr, nb.mul(nb.sub(0.62, k), 1.7)), 0.36, 0.44)
    M['fall'] = _patch(LK.cel, 'M_city_fall', fall, {'alpha': fall_a}, ink=0.0, rim=0.5, vary=0.0, alpha=1.0, wet=0.0, deep=0.3)

    def veil_a(nb):
        u, v, _ = nb.xyz(nb.tc().outputs['UV']); t = nb.attr('seaT', 'Fac')
        vv = nb.sub(v, nb.mul(t, 7.0)); k = nb.math('DIVIDE', v, nb.objattr('fallL'))
        st = nb.noise(nb.vec(nb.mul(u, 11.0), nb.mul(vv, 0.03), 4.0), 1.0, 3.0, 0.65)
        grow = nb.smooth(k, 0.1, 0.38); fade = nb.smooth(k, 1.0, 0.8)
        return nb.mul(nb.smooth(st, 0.5, 0.62), nb.mul(nb.mul(grow, fade), 0.85))
    M['veil'] = _patch(LK.cel, 'M_city_veil', lambda nb: nb.mixc('#d9f4ff', '#ffffff', nb.smooth(nb.xyz(nb.tc().outputs['UV'])[0], 0.3, 0.7)),
                       {'alpha': veil_a}, ink=0.0, paint=0.6, rim=0.6, vary=0.0, alpha=1.0, wet=0.0, deep=0.25)

    def mist_a(nb):
        g = nb.geo(); f = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', g.outputs['Normal'], g.outputs['Incoming']))
        t = nb.attr('seaT', 'Fac')
        n = nb.noise(nb.vmath('ADD', nb.vmath('SCALE', nb.coord('Object'), scale=0.12), nb.vec(0.0, 0.0, nb.mul(t, -0.5))), 1.0, 4.0, 0.62)
        return nb.mul(nb.smooth(nb.add(nb.mul(f, 0.9), nb.mul(nb.sub(n, 0.5), 1.1)), 0.05, 0.8), 0.5)

    def mist_col(nb):                                  # soft wrap light: bright on the sun side, cool sky tint underneath
        g = nb.geo(); N = g.outputs['Normal']
        lit = nb.smooth(nb.vmath('DOT_PRODUCT', N, nb.attr('sunD', 'Vector')), -0.6, 0.7)
        up = nb.smooth(nb.xyz(N)[2], -0.9, 0.7)
        sh = nb.cmul(nb.mixc('#c3cfe8', '#e8edf9', up), nb.mixc(nb.attr('skyC'), (1, 1, 1, 1), 0.65))
        li = nb.cmul('#ffffff', nb.mixc(nb.attr('sunC'), (1, 1, 1, 1), 0.35))
        c = nb.mixc(sh, li, lit)
        return nb.mixc(c, nb.attr('flashC'), nb.mul(nb.attr('flash', 'Fac'), 0.6))
    M['mist'] = _patch(LK.flat, 'M_city_mist', mist_col, {'alpha': mist_a}, ink=0.0, paint=1.0, alpha=1.0)

    def spray_a(nb):                                   # the sheath: soft, streaked downward, growing with the fall, scrolling with seaT
        g = nb.geo(); f = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', g.outputs['Normal'], g.outputs['Incoming']))
        u, v, _ = nb.xyz(nb.tc().outputs['UV']); t = nb.attr('seaT', 'Fac')
        k = nb.math('DIVIDE', v, nb.objattr('fallL')); vv = nb.sub(v, nb.mul(t, 4.0))
        n = nb.noise(nb.vec(nb.mul(u, 5.0), nb.mul(vv, 0.045), 7.0), 1.0, 4.0, 0.6)
        a = nb.smooth(nb.add(nb.mul(f, 0.8), nb.mul(nb.sub(n, 0.5), 1.4)), 0.15, 0.85)
        # fades out over k 0.85 .. fallX: the sheath runs on ~110 m past the falls' old end, widening, and the water dissolves
        # into mist there (06.11: the old end, a cluster of 16 mist balls, read as cotton wool once no cloud hid it)
        return nb.mul(a, nb.mul(nb.mul(nb.smooth(k, 0.2, 0.55), nb.smooth(k, nb.objattr('fallX'), 0.85)), 0.5))
    M['spray'] = _patch(LK.flat, 'M_city_spray', mist_col, {'alpha': spray_a}, ink=0.0, paint=1.0, alpha=1.0)

    def crystal(nb):
        g = nb.geo(); pw = nb.objattr('power')
        fa = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', g.outputs['Normal'], g.outputs['Incoming']))
        k = nb.noise(nb.vmath('SCALE', nb.tc().outputs['Normal'], scale=2.3), 1.0, 0.0, 0.5)
        c = nb.ramp(k, [(0.0, '#1c5cc4'), (0.36, '#35a6ee'), (0.58, '#6fe6ff'), (0.8, '#dcffff')])
        c = nb.mixc(c, '#ffffff', nb.mul(nb.smooth(fa, 0.3, 0.06), 0.85))
        lv = nb.xyz(nb.coord('Object'))[2]
        c = nb.mixc(c, nb.cscale(c, 1.5), nb.smooth(lv, 0.6, 1.0))
        return nb.cscale(c, nb.add(0.22, nb.mul(pw, 0.78)))
    M['crystal'] = _patch(LK.glowmat, 'M_city_crystal', crystal, {'glow': lambda nb: nb.mul(nb.objattr('power'), 0.55)}, strength=1.0, ink=0.35)

    def cloth(nb):
        x, y, z = nb.xyz(nb.coord('Object'))
        a = nb.objattr('clothC', 'Color'); b = nb.objattr('clothC2', 'Color'); pat = nb.objattr('pat')
        st = nb.step(0.5, nb.math('FRACT', nb.mul(x, 5.0)))
        ch = nb.math('ABSOLUTE', nb.sub(nb.step(0.5, nb.math('FRACT', nb.mul(x, 4.0))), nb.step(0.5, nb.math('FRACT', nb.mul(z, 4.0)))))
        c = nb.mixc(a, nb.mixc(a, b, st), nb.step(0.5, pat))
        return nb.mixc(c, nb.mixc(a, b, ch), nb.step(1.5, pat))
    M['cloth'] = LK.cel('M_city_cloth', cloth, vary=0.04, rim=0.4, ink=0.8)

    def collar(nb):
        x, y, z = nb.xyz(nb.coord('Object'))
        s = nb.noise(nb.vec(nb.mul(nb.math('ARCTAN2', y, x), 9.0), nb.mul(z, 0.08), 0.0), 1.0, 3.0, 0.6)
        return nb.mixc('#4b5163', '#8f4a2a', nb.mul(nb.smooth(s, 0.57, 0.62), 0.85))
    M['collar'] = LK.cel('M_city_collar', collar, spec=0.5, grime=0.6, rust=0.9, chips=0.6, scuff=0.4, wscale=0.35)

    def bronze(nb):
        n = nb.noise(nb.coord('Object', 2.5), 1.0, 3.0, 0.6)
        return nb.mixc('#b8843e', '#5fa792', nb.smooth(n, 0.6, 0.64))
    M['bronze'] = LK.cel('M_city_bronze', bronze, spec=0.9, vary=0.04)
    M['clock'] = LK.cel('M_city_clock', lambda nb: nb.image(P('city_clock.png'), nb.tc().outputs['UV'], 'EXTEND'), vary=0.0)

    def tank(nb):
        uv = nb.tc().outputs['UV']
        s = nb.xyz(nb.image(P('city_sign.png'), uv, 'REPEAT', 'Linear', noncolor=True))[0]
        x, y, z = nb.xyz(nb.coord('Object'))
        st = nb.noise(nb.vec(nb.mul(nb.math('ARCTAN2', y, x), 12.0), nb.mul(z, 0.12), 0.0), 1.0, 2.0, 0.6)
        c = nb.mixc('#2a8f8a', '#f3ecd8', s)
        return nb.mixc(c, '#8f4a2a', nb.mul(nb.smooth(st, 0.6, 0.66), 0.7))
    M['tank'] = LK.cel('M_city_tank', tank, spec=0.4, grime=0.4, rust=0.4, wscale=0.6)

    def awn(nb):
        x, y, z = nb.xyz(nb.coord('Object'))
        return nb.mixc(nb.objattr('awnC', 'Color'), '#f7f1e3', nb.step(0.5, nb.math('FRACT', nb.mul(nb.add(x, y), 1.6))))
    M['awning'] = LK.cel('M_city_awning', awn, vary=0.04, rim=0.4)
    M['canvas'] = LK.cel('M_city_canvas', lambda nb: nb.mixc('#efe4cc', '#d9caa8', nb.step(0.9, nb.math('FRACT', nb.mul(nb.xyz(nb.coord('Object'))[0], 1.4)))), vary=0.05)
    M['lamp'] = LK.glowmat('M_city_lampglass', lambda nb: nb.cscale(nb.rgb('#ffdc94'), nb.add(0.55, nb.mul(nb.objattr('lit'), 2.5))), strength=1.0, glow=0.3)

    def root_(nb):
        n = nb.noise(nb.coord('Object', 0.3), 1.0, 3.0, 0.6)
        return nb.mixc('#6c5446', '#5f7d34', nb.smooth(n, 0.55, 0.6))
    M['root'] = LK.cel('M_city_root', root_, vary=0.08, ink=0.8, paint=0.4)

    def garden(nb):
        x, y, z = nb.xyz(nb.coord('Object'))
        row = nb.step(0.5, nb.math('FRACT', nb.mul(x, 1.6)))
        v = nb.voronoi(nb.vmath('MULTIPLY', nb.coord('Object'), (1.6, 3.2, 1.0)), 1.0, 'F1', out='Distance')
        crop = nb.mul(row, nb.smooth(v, 0.42, 0.3))
        c = nb.mixc('#8a6142', '#74503a', nb.step(0.5, nb.math('FRACT', nb.mul(x, 3.2))))
        return nb.mixc(c, nb.objattr('cropC', 'Color'), crop)
    M['garden'] = LK.cel('M_city_garden', garden, vary=0.06, paint=0.5, ink=0.6)
    fi = dict(FAR_INK); fi.update(far_ink or {})
    for m in M.values(): ink_far(m, fi['d0'], fi['d1'], fi['k'])
    return M


# ------------------------------------------------------------------------------------------------------------------ layout helpers
RISER, TREAD, GAP = 0.22, 0.4, 0.02
CAN_HW, CAN_OW, COPE = 1.2, 1.7, 0.3          # canal: water half width, outer wall half width, coping above the water
WHITE_UV = (0.03125, 0.2383)                   # a plain wall spot in the facade atlas


class Grid:
    def __init__(s, x0, y0, st, nx, ny):
        s.x0, s.y0, s.st, s.nx, s.ny = x0, y0, st, nx, ny
        s.xs = x0 + (np.arange(nx) + 0.5) * st; s.ys = y0 + (np.arange(ny) + 0.5) * st
        s.X, s.Y = np.meshgrid(s.xs, s.ys)

    def sample(s, A, x, y):
        fx = np.clip((np.asarray(x, float) - s.x0) / s.st - 0.5, 0, s.nx - 1.0001)
        fy = np.clip((np.asarray(y, float) - s.y0) / s.st - 0.5, 0, s.ny - 1.0001)
        i = fx.astype(int); j = fy.astype(int); u = fx - i; v = fy - j
        return A[j, i] * (1 - u) * (1 - v) + A[j, i + 1] * u * (1 - v) + A[j + 1, i] * (1 - u) * v + A[j + 1, i + 1] * u * v

    def win(s, x0, y0, x1, y1):
        i0 = max(0, int((x0 - s.x0) / s.st)); i1 = min(s.nx, int((x1 - s.x0) / s.st) + 2)
        j0 = max(0, int((y0 - s.y0) / s.st)); j1 = min(s.ny, int((y1 - s.y0) / s.st) + 2)
        return np.s_[j0:j1, i0:i1]

    def rect(s, c, hx, hy, yaw, pad=0.0):
        return s.rect_ab(c, -hx - pad, hx + pad, -hy - pad, hy + pad, yaw)

    def rect_ab(s, c, x0, x1, y0, y1, yaw):
        """Cells inside the local box [x0,x1]x[y0,y1] of a frame at c rotated by yaw."""
        cs, sn = math.cos(yaw), math.sin(yaw); r = max(abs(x0), abs(x1), abs(y0), abs(y1)) * 1.42 + 0.5
        w = s.win(c[0] - r, c[1] - r, c[0] + r, c[1] + r)
        dx = s.X[w] - c[0]; dy = s.Y[w] - c[1]
        lx = dx * cs + dy * sn; ly = -dx * sn + dy * cs
        return w, (lx >= x0) & (lx <= x1) & (ly >= y0) & (ly <= y1)

    def disc(s, c, r):
        w = s.win(c[0] - r, c[1] - r, c[0] + r, c[1] + r)
        return w, np.hypot(s.X[w] - c[0], s.Y[w] - c[1]) <= r

    def ij(s, x, y):
        return int((y - s.y0) / s.st), int((x - s.x0) / s.st)


def blur(A, r):
    B = A.astype(float)
    for _ in range(3):
        for ax in (0, 1):
            pad = [(r + 1, r) if a == ax else (0, 0) for a in (0, 1)]
            c = np.cumsum(np.pad(B, pad, mode='edge'), axis=ax)
            B = ((c[2 * r + 1:, :] - c[:-2 * r - 1, :]) if ax == 0 else (c[:, 2 * r + 1:] - c[:, :-2 * r - 1])) / (2 * r + 1)
    return B


def resample(P, step, closed=False):
    P = np.asarray(P, float)
    Q = np.vstack([P, P[:1]]) if closed else P
    d = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    n = max(2, int(round(d[-1] / step)) + 1)
    s = np.linspace(0.0, d[-1], n)
    return np.c_[np.interp(s, d, Q[:, 0]), np.interp(s, d, Q[:, 1])]


def pdist(P, Q, want_t=False):
    """Distance from points P (M,2) to the open polyline Q (K,2); optionally the arc length of the nearest point."""
    P = np.atleast_2d(np.asarray(P, float)); out = np.full(len(P), 1e9); arc = np.zeros(len(P))
    A = Q[:-1]; B = Q[1:]; segl = np.linalg.norm(B - A, axis=1); S0 = np.r_[0.0, np.cumsum(segl)][:-1]
    for p0 in range(0, len(P), 1024):
        pp = P[p0:p0 + 1024]; ar = np.arange(len(pp))
        for c in range(0, len(A), 384):
            a = A[c:c + 384]; ab = B[c:c + 384] - a; L2 = np.maximum((ab * ab).sum(1), 1e-12)
            ap = pp[:, None, :] - a[None]
            t = np.clip((ap * ab[None]).sum(2) / L2[None], 0.0, 1.0)
            d = np.sqrt(((ap - t[..., None] * ab[None]) ** 2).sum(2))
            k = d.argmin(1); dm = d[ar, k]
            cur = out[p0:p0 + 1024]; better = dm < cur
            out[p0:p0 + 1024] = np.where(better, dm, cur)
            if want_t:
                aa = S0[c:c + 384][k] + t[ar, k] * segl[c:c + 384][k]
                arc[p0:p0 + 1024] = np.where(better, aa, arc[p0:p0 + 1024])
    return (out, arc) if want_t else out


def ray_rim(o, d):
    lo, hi = 0.0, 400.0
    for _ in range(50):
        m = (lo + hi) / 2; p = o + d * m
        if rho_xy(p[0], p[1]) < 1.0: lo = m
        else: hi = m
    return lo


def merge_runs(q, minrun):
    q = q.copy(); n = len(q)
    starts = np.r_[0, np.nonzero(np.diff(q))[0] + 1]; ends = np.r_[starts[1:], n]
    for a, b in zip(starts, ends):
        if b - a < minrun and a > 0: q[a:b] = q[a - 1]
    return q


def runs(z):
    st = np.r_[0, np.nonzero(np.abs(np.diff(z)) > 1e-6)[0] + 1]; en = np.r_[st[1:], len(z)]
    return list(zip(st.tolist(), en.tolist()))


class Street:
    def __init__(s, name, pts, hw, pri, closed=False, kind='ring'):
        s.name, s.hw, s.pri, s.closed, s.kind = name, hw, pri, closed, kind
        s.P = resample(pts, 0.1, closed)
        s.ds = float(np.linalg.norm(np.diff(s.P, axis=0), axis=1).sum()) / (len(s.P) - 1)
        s.L = s.ds * (len(s.P) - 1)
        T = np.gradient(s.P, axis=0)
        if closed: T[0] = T[-1] = s.P[1] - s.P[-2]
        s.T = T / np.linalg.norm(T, axis=1, keepdims=True)
        s.P1 = resample(pts, 1.0, closed)
        s.lo = s.P.min(0) - hw - 1.0; s.hi = s.P.max(0) + hw + 1.0
        s.humps = []; s.nohouse = []

    def at(s, sv):
        f = np.clip(np.asarray(sv, float) / s.ds, 0, len(s.P) - 1.000001)
        k = f.astype(int); t = (f - k)[..., None]
        p = s.P[k] * (1 - t) + s.P[k + 1] * t
        T = s.T[k] * (1 - t) + s.T[k + 1] * t; T = T / np.linalg.norm(T, axis=-1, keepdims=True)
        return p, T, np.stack([-T[..., 1], T[..., 0]], -1)

    def zbase_at(s, sv):
        k = np.clip(np.round(np.asarray(sv, float) / s.ds).astype(int), 0, len(s.zb) - 1)
        return s.zb[k]

    def z_at(s, sv):
        k = np.clip(np.round(np.asarray(sv, float) / s.ds).astype(int), 0, len(s.z) - 1)
        return s.z[k]

    def profile(s, ctx):
        h = ctx.G.sample(ctx.Hs, s.P[:, 0], s.P[:, 1])
        q = merge_runs(np.round(h / RISER).astype(int), 5)
        if s.closed: q[-1] = q[0]
        s.zb = q * RISER

    def apply_humps(s):
        z = s.zb.copy(); sv = np.arange(len(z)) * s.ds
        for sc, Ht, hb in s.humps:
            d = np.abs(sv - sc)
            if s.closed: d = np.minimum(d, s.L - d)
            z = np.maximum(z, Ht - RISER * np.ceil(np.maximum(0.0, d - hb) / TREAD - 1e-6))
        s.z = z


class Canal:
    def __init__(s, name, pts):
        s.name = name
        s.P = resample(pts, 0.5)
        s.L = float(np.linalg.norm(np.diff(s.P, axis=0), axis=1).sum()); s.ds = s.L / (len(s.P) - 1)
        T = np.gradient(s.P, axis=0); s.T = T / np.linalg.norm(T, axis=1, keepdims=True)
        s.N = np.stack([-s.T[:, 1], s.T[:, 0]], -1)
        s.lo = s.P.min(0) - 6; s.hi = s.P.max(0) + 6
        s.bridges = []


def seg_cross(A, C):
    """All intersections between the polylines A and C: list of (segment i on A, t on it, segment j on C, u on it)."""
    a0 = A[:-1][:, None, :]; a1 = A[1:][:, None, :]; c0 = C[:-1][None, :, :]; c1 = C[1:][None, :, :]
    r = a1 - a0; s_ = c1 - c0
    den = r[..., 0] * s_[..., 1] - r[..., 1] * s_[..., 0]
    q = c0 - a0
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (q[..., 0] * s_[..., 1] - q[..., 1] * s_[..., 0]) / den
        u = (q[..., 0] * r[..., 1] - q[..., 1] * r[..., 0]) / den
    ok = (np.abs(den) > 1e-12) & (t >= 0) & (t < 1) & (u >= 0) & (u < 1)
    I, J = np.nonzero(ok)
    return [(int(i), float(t[i, j]), int(j), float(u[i, j])) for i, j in zip(I, J)]


# ------------------------------------------------------------------------------------------------------------------ house variants
VARIANTS = [
    dict(name='hipA', w=7.2, d=6.0, S=2, roof='hip', chim=1, lantern=True, wt=1.3),
    dict(name='hipB', w=9.6, d=7.2, S=3, roof='hip', balc=[(1, 1), (2, 1)], chim=2, string=True, wt=1.0),
    dict(name='towerC', w=4.8, d=6.0, S=3, roof='hip', chim=1, wt=0.9),
    dict(name='flatD', w=7.2, d=7.2, S=2, roof='flat', terrace=('pergola', 'tank', 'laundry'), wt=1.0),
    dict(name='gableE', w=12.0, d=7.2, S=3, roof='gable', balc=[(1, 1), (1, 3), (2, 2)], chim=2, wt=0.8),
    dict(name='belvF', w=7.2, d=9.6, S=4, roof='hip', belv=True, chim=1, string=True, wt=0.55),
    dict(name='ellG', w=9.6, d=7.2, S=3, roof='gable', wing=(4.8, 4.8, 2), chim=1, wt=0.7),
    dict(name='shopH', w=7.2, d=6.0, S=3, roof='gable', shop=(0, 2), awning=True, chim=1, flat_only=True, wt=0.9),
    dict(name='domeI', w=6.0, d=6.0, S=2, roof='dome', wt=0.5),
    dict(name='stairJ', w=9.6, d=6.0, S=2, roof='flat', stair=True, terrace=('pots', 'laundry'), flat_only=True, wt=0.6),
    dict(name='pyrK', w=6.0, d=6.0, S=3, roof='pyr', chim=1, wt=0.6),
    dict(name='gableL', w=7.2, d=4.8, S=2, roof='gable', chim=1, lantern=True, wt=1.1),
]
EAVE = {'hip': 0.45, 'pyr': 0.45, 'gable': 0.4, 'flat': 0.08, 'dome': 0.08}
WALLS = [('#f1ead8', 6), ('#f6f0e2', 4), ('#efe3c2', 3), ('#f3d9b8', 1.5), ('#ecc9a2', 1.0), ('#f2e2a4', 1.2), ('#dfe8d6', 0.8),
         ('#d4e2ec', 0.9), ('#f2d3cb', 0.9), ('#e6dcf0', 0.5)]
SHUTS = [('#2a8f8a', 3), ('#3d6fb6', 2.5), ('#4f8a4a', 1.5), ('#a8473a', 1.0), ('#d8a13a', 0.8), ('#5a8fc4', 1.5), ('#7a5a9a', 0.6), ('#2f5f8f', 1.0)]
ROOFS = [('#c8553d', 5), ('#b84a34', 3), ('#d46a48', 2.5), ('#a8442f', 1.5), ('#2a8f8a', 2.0), ('#3a9a94', 1.0)]
DOMES = [('#2f6fd0', 3), ('#2a8f8a', 2), ('#3d8fd8', 1)]
AWNS = [('#d23a2e', 1.0), ('#2a8f8a', 1.0), ('#3d6fb6', 1.0), ('#f2b705', 0.8), ('#4f8a4a', 0.6)]
LEAVES = [('#5f9e3c', 3), ('#6aa84f', 3), ('#4f8a3a', 2), ('#7cb35a', 2), ('#8fbf5a', 1), ('#5d8f45', 2)]
CLOTH = ['#f4f1ea', '#e94f4f', '#f2b705', '#3d6fb6', '#5fc3e4', '#f08cb4', '#8fd16a', '#ffffff', '#f7a03c', '#b98ae8', '#2a8f8a']
CROPS = ['#5f9e3c', '#8fbf5a', '#e94f4f', '#f2b705', '#7cb35a', '#b98ae8']


def house_dims(V):
    """Roof (eaves) rectangle in house-local coordinates and how far things stick out at the front (balconies, awnings, stairs)."""
    hx, hy = V['w'] / 2, V['d'] / 2; e = EAVE[V['roof']]
    ex0, ex1, ey0, ey1 = -hx - e, hx + e, -hy - e, hy + e
    if V['roof'] == 'gable': ex0, ex1 = -hx - 0.28, hx + 0.28
    if V.get('wing'):
        ww, wd, _ = V['wing']; ex1 = max(ex1, hx + ww + 0.1)
    front = 0.0
    if V.get('balc'): front = 1.1
    if V.get('awning'): front = max(front, 1.25)
    if V.get('stair'): front = max(front, 1.15)
    if V.get('lantern'): front = max(front, 0.6)
    return (ex0, ex1, ey0, ey1), front


# ------------------------------------------------------------------------------------------------------------------ the plan
def plan(ctx):
    R = ctx.R
    G = ctx.G = Grid(-186.0, -156.0, 0.5, 744, 624)
    X, Y = G.X, G.Y
    ctx.Hn = H0(X, Y)
    ctx.Hs = blur(ctx.Hn, 10)
    ctx.ins = inset_xy(X, Y)
    ctx.flags = np.zeros(X.shape, np.uint16)
    ctx.zplaza = round(float(G.sample(ctx.Hs, HILL[0], HILL[1])) / RISER) * RISER
    w, m = G.disc(HILL, PLAZA_R + 0.3); ctx.flags[w][m] |= F_PLAZA
    # ---- the specials around the plaza
    a = math.radians(206.0); ctx.camp = HILL + 12.0 * np.array((math.cos(a), math.sin(a)))
    w, m = G.rect(ctx.camp, 4.6, 4.6, 0.0); ctx.flags[w][m] |= F_SPECIAL
    a = math.radians(100.0); ctx.church_dir = np.array((math.cos(a), math.sin(a)))
    ctx.church = HILL + ctx.church_dir * (PLAZA_R + 10.6)
    ctx.church_yaw = math.atan2(-ctx.church_dir[0], ctx.church_dir[1])          # local +y points away from the plaza
    w, m = G.rect_ab(ctx.church, -6.4, 6.4, -10.4, 15.2, ctx.church_yaw); ctx.flags[w][m] |= F_SPECIAL
    a = math.radians(37.0); ctx.wt = HILL + 80.0 * np.array((math.cos(a), math.sin(a)))
    w, m = G.disc(ctx.wt, 8.5); ctx.flags[w][m] |= F_SPECIAL
    # ---- streets
    S = []
    for k, ang in enumerate(RADIALS):
        ar = math.radians(ang); d = np.array((math.cos(ar), math.sin(ar))); nrm = np.array((-d[1], d[0]))
        Lr = ray_rim(HILL, d)
        rr = random.Random(100 + k); ph = rr.uniform(0, 6.28); amp = rr.uniform(2.0, 4.0) * (1 if k else 0.4); fr = rr.uniform(1.0, 1.8)
        pts = []
        n = int(Lr / 2.0)
        for i in range(n + 1):
            t = i / n; s0 = (PLAZA_R - 2.0) + t * (Lr - 2.2 - (PLAZA_R - 2.0))
            off = amp * math.sin(math.pi * fr * t + ph) * math.sin(math.pi * t)
            pts.append(HILL + d * s0 + nrm * off)
        S.append(Street('rad%d' % k, pts, 3.0, 3, False, 'radial'))
        S[-1].ang = ang
    th = np.linspace(0, math.tau, 240, endpoint=False)
    r1 = 50.0 + 3.0 * np.sin(3 * th + 1.0) + 2.0 * np.sin(5 * th + 2.0)
    S.append(Street('ring1', HILL + np.c_[np.cos(th), np.sin(th)] * r1[:, None], 2.6, 2, True))
    th = np.linspace(0, math.tau, 420, endpoint=False)
    rr2 = r_outline(th) * (0.63 + 0.02 * np.sin(4 * th + 0.5))
    S.append(Street('ring2', np.c_[np.cos(th), np.sin(th)] * rr2[:, None], 2.6, 2, True))
    rr3 = r_outline(th) - 13.0 - 1.5 * np.sin(5 * th + 1.2)
    S.append(Street('prom', np.c_[np.cos(th), np.sin(th)] * rr3[:, None], 2.1, 1, True))
    ctx.streets = S
    # ---- canals (from springs by the plaza to the rim, where they spill off as waterfalls)
    C = []
    for k, ang in enumerate(FALLS):
        ar = math.radians(ang); d = np.array((math.cos(ar), math.sin(ar))); nrm = np.array((-d[1], d[0]))
        Lr = ray_rim(HILL, d); rr = random.Random(200 + k); ph = rr.uniform(0, 6.28)
        pts = []
        s0 = PLAZA_R + 6.8; n = int((Lr + 1.4 - s0) / 2.0)
        for i in range(n + 1):
            t = i / n; s_ = s0 + t * (Lr + 1.4 - s0)
            off = 2.5 * math.sin(math.pi * 1.4 * t + ph) * math.sin(math.pi * min(1.0, t * 1.15))
            pts.append(HILL + d * s_ + nrm * off)
        cn = Canal('canal%d' % k, pts); cn.ang = ang; cn.spring = HILL + d * (PLAZA_R + 4.3); cn.dir = d
        C.append(cn)
    ctx.canals = C
    # canal levels: smoothed ground + 0.45, never rising downstream, 0.5 m weirs, none near a street crossing
    for cn in C:
        h = G.sample(ctx.Hs, cn.P[:, 0], cn.P[:, 1]) + 0.45
        lev = np.empty(len(h)); Lc = math.floor(h[0] * 10) / 10; run = 99
        for i in range(len(h)):
            if run >= 5 and h[i] < Lc - 0.35:
                Lc -= max(0.4, round(min(1.1, Lc - h[i]) * 10) / 10); run = 0
            lev[i] = Lc; run += 1
        cn.lev = lev
    ctx.cross = []
    for st in S:
        for ci, cn in enumerate(C):
            for (i, ti, j, tj) in seg_cross(st.P1, cn.P):
                p = st.P1[i] + (st.P1[i + 1] - st.P1[i]) * ti
                _, sc = pdist(p[None], st.P, want_t=True)
                ctx.cross.append([st, ci, float(sc[0]), (j + tj) * cn.ds, p])
    for st, ci, sc, sca, p in ctx.cross:          # level the canal around a bridge (no weir under a deck)
        cn = C[ci]; j0 = max(0, int((sca - 6.0) / cn.ds)); j1 = min(len(cn.lev), int((sca + 6.0) / cn.ds) + 1)
        cn.lev[j0:j1] = cn.lev[j0]
        cn.lev = np.minimum.accumulate(cn.lev)
    for st in S: st.profile(ctx)
    for cr in ctx.cross:
        st, ci, sc, sca, p = cr; cn = C[ci]
        _, T, _ = st.at(sc); jc = min(len(cn.P) - 1, int(round(sca / cn.ds)))
        sina = abs(float(T[0] * cn.T[jc][1] - T[1] * cn.T[jc][0])); sina = max(sina, 0.35)
        cosa = math.sqrt(max(0.0, 1 - sina * sina))
        hb = (CAN_OW + 0.3) / sina + st.hw * cosa / sina + 0.3
        hb = math.ceil(hb / st.ds) * st.ds; sc_ = round(sc / st.ds) * st.ds
        zb = float(st.zbase_at(sc_)); lc = float(cn.lev[jc])
        Ht = zb + RISER * max(2, math.ceil((lc + COPE + 0.06 + 0.45 - zb) / RISER))
        st.humps.append((sc_, Ht, hb))
        nst = int(math.ceil((Ht - zb) / RISER))
        st.nohouse.append((sc_ - hb - nst * TREAD - 1.5, sc_ + hb + nst * TREAD + 1.5))
        cn.bridges.append(dict(sca=sca, Ht=Ht, st=st, sc=sc_, hb=hb, lev=lc))
        cr.append(Ht)
    for st in S: st.apply_humps()
    # ---- rasterise streets / plaza / canals: flags, the carved ground and the nearest-street direction
    dmin = np.full(X.shape, 1e9); zst = np.zeros(X.shape); ang = np.zeros(X.shape)
    for st in S:
        Pc = st.P1; S1 = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Pc, axis=0), axis=1))]
        scale = st.L / max(S1[-1], 1e-9)
        for k in range(len(Pc) - 1):
            a, b = Pc[k], Pc[k + 1]; reach = st.hw + 4.5
            w = G.win(min(a[0], b[0]) - reach, min(a[1], b[1]) - reach, max(a[0], b[0]) + reach, max(a[1], b[1]) + reach)
            Xw = G.X[w]; Yw = G.Y[w]; ab = b - a; L2 = max(float(ab @ ab), 1e-9)
            t = np.clip(((Xw - a[0]) * ab[0] + (Yw - a[1]) * ab[1]) / L2, 0, 1)
            dd = np.hypot(Xw - (a[0] + t * ab[0]), Yw - (a[1] + t * ab[1])) - st.hw
            upd = dd < dmin[w]
            if not upd.any(): continue
            zz = st.zbase_at((S1[k] + t * math.sqrt(L2)) * scale)
            dmin[w] = np.where(upd, dd, dmin[w]); zst[w] = np.where(upd, zz, zst[w])
            ang[w] = np.where(upd, math.atan2(ab[1], ab[0]), ang[w])
    dpl = np.hypot(X - HILL[0], Y - HILL[1]) - PLAZA_R
    upd = dpl < dmin; dmin = np.where(upd, dpl, dmin); zst = np.where(upd, ctx.zplaza, zst)
    ang = np.where(upd, np.arctan2(Y - HILL[1], X - HILL[0]) + math.pi / 2, ang)
    ctx.dstreet = dmin; ctx.ang = ang
    ctx.flags[dmin < 0] |= F_STREET
    wgt = sstep(4.0, 1.2, dmin)
    Gc = ctx.Hn + (zst - 0.3 - ctx.Hn) * wgt
    dc = np.full(X.shape, 1e9); lvl = np.zeros(X.shape)
    for cn in C:
        for k in range(len(cn.P) - 1):
            a, b = cn.P[k], cn.P[k + 1]; reach = CAN_OW + 3.5
            w = G.win(min(a[0], b[0]) - reach, min(a[1], b[1]) - reach, max(a[0], b[0]) + reach, max(a[1], b[1]) + reach)
            Xw = G.X[w]; Yw = G.Y[w]; ab = b - a; L2 = max(float(ab @ ab), 1e-9)
            t = np.clip(((Xw - a[0]) * ab[0] + (Yw - a[1]) * ab[1]) / L2, 0, 1)
            dd = np.hypot(Xw - (a[0] + t * ab[0]), Yw - (a[1] + t * ab[1])) - CAN_OW
            upd = dd < dc[w]
            dc[w] = np.where(upd, dd, dc[w]); lvl[w] = np.where(upd, cn.lev[k], lvl[w])
        w, m = G.disc(cn.spring, 3.6); ctx.flags[w][m] |= F_CANAL
    ctx.dcanal = dc
    ctx.flags[dc < 0.9] |= F_CANAL
    wc = sstep(3.0, 1.0, dc)
    Gc = Gc + (np.minimum(Gc, lvl - 0.2) - Gc) * wc
    ctx.Gc = Gc
    # ---- windmills: W1 beside the west street (shot 02), the others on the rim ridges
    ctx.mills = []
    st0 = S[0]; p, T, N = st0.at(70.0); side = 1.0 if N[1] > 0 else -1.0
    c = p + N * side * (st0.hw + 4.4)
    ctx.mills.append(dict(c=c, face=math.atan2(T[1], T[0]), street=True))        # sails face down the street (west, into the wind)
    for ang_, rho_ in MILLS[1:]:
        a = math.radians(ang_); r0 = float(r_outline(a)) * rho_
        c = np.array((math.cos(a), math.sin(a))) * r0
        ctx.mills.append(dict(c=c, face=a, street=False))
    for ml in ctx.mills:
        w, m = G.disc(ml['c'], 10.8); ctx.flags[w][m] |= F_MILL
    # ---- lookouts at the ends of the radials
    ctx.looks = []
    for st in S:
        if st.kind != 'radial': continue
        p, T, N = st.at(st.L); ctx.looks.append(dict(p=p, d=T, z=float(st.z[-1]), st=st))
        w, m = G.disc(p + T * 1.5, 6.5); ctx.flags[w][m] |= F_OUT
    place_lamps(ctx)
    place_houses(ctx)
    place_gardens(ctx)
    place_trees(ctx)
    ground_paint(ctx)


def place_lamps(ctx):
    """Freestanding lamps: round the plaza, along the rim side of the promenade, at the lookouts."""
    G = ctx.G; L = []
    for k in range(10):
        a = math.radians(18 + k * 36)
        p = HILL + np.array((math.cos(a), math.sin(a))) * (PLAZA_R - 1.2)
        if np.hypot(*(p - ctx.camp)) < 6.5: continue
        if abs((18 + k * 36 - 100 + 180) % 360 - 180) < 20: continue          # the church apron
        L.append((p, ctx.zplaza, 'plaza'))
    prom = [s for s in ctx.streets if s.name == 'prom'][0]
    s = 6.0
    while s < prom.L - 6:
        p, T, N = prom.at(s); q = p + N * (prom.hw + 1.7); q2 = p - N * (prom.hw + 1.7)
        q = q if inset_xy(q[0], q[1]) < inset_xy(q2[0], q2[1]) else q2
        f = ctx.flags[G.win(q[0] - 0.5, q[1] - 0.5, q[0] + 0.5, q[1] + 0.5)]
        if not (f & (F_STREET | F_CANAL | F_OUT | F_MILL | F_SPECIAL | F_HOUSE)).any() and inset_xy(q[0], q[1]) > 4.0:
            L.append((q, None, 'prom'))
        s += 26.0
    for lk in ctx.looks:
        nn = np.array((-lk['d'][1], lk['d'][0]))
        for sd in (-1, 1):
            L.append((lk['p'] + lk['d'] * 1.2 + nn * sd * 4.0, lk['z'], 'look'))
    ctx.lamps = L
    for p, z, kind in L:
        w, m = G.disc(p, 1.3); ctx.flags[w][m] |= F_LAMP


def house_ok(ctx, c, yaw, V, front_pad):
    """Roof footprint (+ things sticking out at the front) free of other houses / specials; walls off the streets except the front strip."""
    G = ctx.G; (ex0, ex1, ey0, ey1), front = house_dims(V)
    w, m = G.rect_ab(c, ex0 - 0.4, ex1 + 0.4, ey0 - 0.4 - front, ey1 + 0.4, yaw)
    f = ctx.flags[w][m]
    if (f & (F_HOUSE | F_SPECIAL | F_MILL | F_OUT | F_LAMP | F_PLAZA | F_CANAL | F_GARDEN | F_BALC)).any(): return False
    hy = V['d'] / 2
    y0 = -hy + front_pad if front_pad is not None else ey0
    w, m = G.rect_ab(c, ex0, ex1, y0, ey1, yaw)
    if (ctx.flags[w][m] & F_STREET).any(): return False
    for lx, ly in ((ex0, ey0 - front), (ex1, ey0 - front), (ex0, ey1), (ex1, ey1)):
        x = c[0] + lx * math.cos(yaw) - ly * math.sin(yaw); y = c[1] + lx * math.sin(yaw) + ly * math.cos(yaw)
        if inset_xy(x, y) < 5.5: return False
    return True


def house_stamp(ctx, c, yaw, V):
    G = ctx.G; (ex0, ex1, ey0, ey1), front = house_dims(V)
    w, m = G.rect_ab(c, ex0, ex1, ey0, ey1, yaw); ctx.flags[w][m] |= F_HOUSE
    if front:
        w, m = G.rect_ab(c, ex0, ex1, ey0 - front, ey0, yaw); ctx.flags[w][m] |= F_BALC


def place_houses(ctx):
    R = ctx.R; G = ctx.G; H = []
    vw = [(i, V['wt']) for i, V in enumerate(VARIANTS)]
    order = sorted(ctx.streets, key=lambda s: -s.pri)
    for st in order:
        for side in (1, -1):
            s = R.uniform(0.5, 3.0)
            while s < st.L - 4.0:
                placed = False
                for attempt in range(5):
                    vi = wchoice(R, vw); V = VARIANTS[vi]; wv = V['w'] + (V['wing'][0] if V.get('wing') else 0.0)
                    if s + wv > st.L - 0.5: continue
                    if any(a < s + wv and s < b for a, b in st.nohouse): break
                    mid = s + wv / 2
                    p, T, N = st.at(mid); nside = N * side
                    yaw = math.atan2(-nside[0], nside[1])
                    xaxis = np.array((math.cos(yaw), math.sin(yaw)))
                    off = st.hw - 0.25 + V['d'] / 2
                    xs = np.linspace(-wv / 2, wv / 2, 5)
                    for it in range(4):
                        cpos = p + nside * off
                        fronts = cpos[None, :] + xs[:, None] * xaxis[None, :] - nside[None, :] * (V['d'] / 2)
                        dmn = float(pdist(fronts, st.P1).min())
                        if dmn >= st.hw - 0.32: break
                        off += (st.hw - 0.28 - dmn)
                    if dmn > st.hw + 0.35 or dmn < st.hw - 0.34: continue
                    cc = cpos - xaxis * (V['wing'][0] / 2 if V.get('wing') else 0.0)
                    ss = np.linspace(s, s + wv, 7); zz = st.zbase_at(ss)
                    if V.get('flat_only') and zz.max() - zz.min() > 0.3: continue
                    if zz.max() - zz.min() > 1.6: continue
                    if not house_ok(ctx, cc, yaw, V, 0.32): continue
                    hx = V['w'] / 2; nb = max(1, round(V['w'] / BAYW)); bw = V['w'] / nb
                    door_x = -hx + bw * (nb // 2 + 0.5)
                    gpt = cc + xaxis * door_x
                    _, sdoor = pdist(gpt[None], st.P, want_t=True)
                    floor = float(st.zbase_at(sdoor[0]))
                    house_stamp(ctx, cc, yaw, V)
                    H.append(dict(v=vi, c=cc, yaw=yaw, floor=floor, street=st, side=side, s0=s, s1=s + wv))
                    s += wv + R.uniform(0.3, 1.3) + (EAVE[V['roof']] * 2 if V['roof'] in ('hip', 'pyr') else 0.0)
                    placed = True
                    break
                if not placed: s += R.uniform(1.5, 3.5)
    ctx.n_street_houses = len(H)
    tries = 0
    pool = [(k, VARIANTS[k]['wt']) for k in range(len(VARIANTS)) if not VARIANTS[k].get('flat_only')]
    while len(H) < 330 and tries < 9000:
        tries += 1
        x = R.uniform(-175, 175); y = R.uniform(-145, 145)
        if inset_xy(x, y) < 9.0: continue
        j, i = G.ij(x, y)
        if not (0 <= i < G.nx and 0 <= j < G.ny) or ctx.flags[j, i]: continue
        vi = wchoice(R, pool); V = VARIANTS[vi]
        yaw = float(ctx.ang[j, i]) + R.choice((0.0, math.pi / 2, math.pi, -math.pi / 2)) + R.uniform(-0.05, 0.05)
        c = np.array((x, y))
        if not house_ok(ctx, c, yaw, V, None): continue
        hx, hy = V['w'] / 2, V['d'] / 2
        cs, sn = math.cos(yaw), math.sin(yaw)
        gz = np.array([G.sample(ctx.Gc, c[0] + lx * cs - ly * sn, c[1] + lx * sn + ly * cs) for lx in (-hx, 0, hx) for ly in (-hy, 0, hy)])
        if gz.max() - gz.min() > 3.2: continue
        house_stamp(ctx, c, yaw, V)
        H.append(dict(v=vi, c=c, yaw=yaw, floor=float(np.percentile(gz, 35)), street=None, side=0, s0=0, s1=0))
    ctx.houses = H


def place_gardens(ctx):
    R = ctx.R; G = ctx.G; out = []; tries = 0
    while len(out) < 16 and tries < 4000:
        tries += 1
        x = R.uniform(-170, 170); y = R.uniform(-140, 140)
        if inset_xy(x, y) < 7.0: continue
        j, i = G.ij(x, y)
        if not (0 <= i < G.nx and 0 <= j < G.ny) or ctx.flags[j, i]: continue
        gw = R.uniform(5.0, 10.0); gd = R.uniform(3.5, 6.5); yaw = float(ctx.ang[j, i]) + R.choice((0.0, math.pi / 2))
        c = np.array((x, y))
        w, m = G.rect(c, gw / 2, gd / 2, yaw, pad=0.8)
        if (ctx.flags[w][m] & (F_BUILD | F_TREE)).any(): continue
        cs, sn = math.cos(yaw), math.sin(yaw)
        corners = [(x + lx * cs - ly * sn, y + lx * sn + ly * cs) for lx in (-gw / 2, gw / 2) for ly in (-gd / 2, gd / 2)]
        if min(inset_xy(a, b) for a, b in corners) < 6.0: continue
        gz = [G.sample(ctx.Gc, a, b) for a, b in corners]
        if max(gz) - min(gz) > 1.2: continue
        w, m = G.rect(c, gw / 2, gd / 2, yaw, pad=0.3); ctx.flags[w][m] |= F_GARDEN
        out.append(dict(c=c, w=gw, d=gd, yaw=yaw, z=float(np.mean(gz))))
    ctx.gardens = out


TREES = [  # name, crown radius (plan), height, weight
    ('round', 2.4, 6.5, 3.0), ('roundL', 3.4, 8.5, 1.4), ('cypress', 1.2, 9.5, 1.6), ('pine', 4.2, 9.0, 0.8),
    ('olive', 2.6, 5.0, 1.6), ('lemon', 1.8, 4.2, 1.4), ('shrub', 1.5, 2.2, 1.6), ('roundS', 1.9, 5.0, 2.0)]


def place_trees(ctx):
    R = ctx.R; G = ctx.G; out = []; tries = 0
    tw = [(i, t[3]) for i, t in enumerate(TREES)]
    while len(out) < 300 and tries < 30000:
        tries += 1
        x = R.uniform(-178, 178); y = R.uniform(-148, 148)
        ins = inset_xy(x, y)
        if ins < 3.2: continue
        j, i = G.ij(x, y)
        if not (0 <= i < G.nx and 0 <= j < G.ny) or ctx.flags[j, i] & (F_BUILD | F_TREE): continue
        ti = wchoice(R, tw); k = R.uniform(0.85, 1.12); rc = TREES[ti][1] * k
        if ins < rc + 2.0: continue
        if ti == 3 and ins < 12: continue
        w, m = G.disc((x, y), rc + 0.4)
        if (ctx.flags[w][m] & (F_HOUSE | F_BALC | F_SPECIAL | F_MILL | F_OUT | F_LAMP | F_STREET | F_PLAZA | F_GARDEN)).any(): continue
        w2, m2 = G.disc((x, y), 0.9)
        if (ctx.flags[w2][m2] & (F_CANAL | F_TREE)).any(): continue
        out.append(dict(t=ti, c=np.array((x, y)), r=rc, k=k))
        w, m = G.disc((x, y), max(0.9, rc * 0.55)); ctx.flags[w][m] |= F_TREE
    ctx.trees = out


def ground_paint(ctx):
    town = ((ctx.flags & (F_STREET | F_PLAZA | F_HOUSE | F_BALC | F_SPECIAL)) > 0).astype(float)
    town = np.clip(blur(town, 3) * 1.8, 0, 1)
    town = np.maximum(town, sstep(2.5, 0.5, ctx.dstreet))
    soil = np.clip(blur(((ctx.flags & F_GARDEN) > 0).astype(float), 2) * 1.6, 0, 1)
    fl = ((ctx.flags & F_MILL) > 0).astype(float) * 0.8 + sstep(30.0, 6.0, ctx.ins) * 0.7
    fl = np.clip(blur(fl, 6) * (1 - town), 0, 1)
    ctx.paint = (town, soil, fl)


# ------------------------------------------------------------------------------------------------------------------ objects
def mkobj(ctx, name, data, mats=(), qa='prop', parent=None, props=None, loc=None, rot=None):
    o = bpy.data.objects.new(name, data)
    ctx.coll.objects.link(o)
    o.parent = parent if parent is not None else ctx.root
    if loc is not None: o.location = tuple(float(v) for v in loc)
    if rot is not None: o.rotation_euler = tuple(float(v) for v in rot)
    if data is not None and isinstance(data, bpy.types.Mesh) and len(data.materials) == 0:
        for m in mats: data.materials.append(m)
    o['qa'] = qa
    for k, v in (props or {}).items(): o[k] = v
    ctx.objs.append(o)
    return o


def gz(ctx, x, y):
    loc, nrm, idx, d = ctx.gbvh.ray_cast(Vector((float(x), float(y), 700.0)), Vector((0.0, 0.0, -1.0)))
    return loc.z if loc is not None else float(ctx.G.sample(ctx.Gc, x, y))


def rotz(yaw, t=(0.0, 0.0, 0.0)):
    return Matrix.Translation(Vector(t)) @ Matrix.Rotation(yaw, 4, 'Z')


# ------------------------------------------------------------------------------------------------------------------ terrain and rock
def build_terrain(ctx):
    G = ctx.G; NA, NR = 720, 165
    th = np.linspace(0, math.tau, NA, endpoint=False); ro = r_outline(th)
    rh = np.linspace(0, 1, NR + 1)[1:]
    KH = int(np.searchsorted(rh, 0.5))                                  # rings 0..KH-1 use every other angle
    rows = []; V = [np.array([[0.0, 0.0, float(G.sample(ctx.Gc, 0.0, 0.0))]])]; base = 1
    for k in range(NR):
        step = 2 if k < KH else 1; idx = np.arange(0, NA, step)
        X = ro[idx] * rh[k] * np.cos(th[idx]); Y = ro[idx] * rh[k] * np.sin(th[idx])
        V.append(np.c_[X, Y, G.sample(ctx.Gc, X, Y)]); rows.append(base + np.arange(len(idx))); base += len(idx)
    V = np.vstack(V)
    F = []
    r0 = rows[0]; n0 = len(r0)
    F += [(0, int(r0[i]), int(r0[(i + 1) % n0])) for i in range(n0)]
    for k in range(NR - 1):
        A_, B_ = rows[k], rows[k + 1]; na, nb_ = len(A_), len(B_)
        if na == nb_:
            for i in range(na):
                j = (i + 1) % na; F.append((int(A_[i]), int(B_[i]), int(B_[j]), int(A_[j])))
        else:                                                           # 360 -> 720 seam: three triangles per coarse step
            for i in range(na):
                j = (i + 1) % na
                F += [(int(A_[i]), int(B_[2 * i]), int(B_[2 * i + 1])), (int(A_[i]), int(B_[2 * i + 1]), int(A_[j])),
                      (int(A_[j]), int(B_[2 * i + 1]), int(B_[(2 * i + 2) % nb_]))]
    me = bpy.data.meshes.new('CITY_ground'); me.from_pydata(V.tolist(), [], F); me.update(); me.shade_smooth()
    town, soil, fl = ctx.paint
    cols = np.c_[G.sample(town, V[:, 0], V[:, 1]), G.sample(soil, V[:, 0], V[:, 1]), G.sample(fl, V[:, 0], V[:, 1]), np.ones(len(V))]
    ca = me.color_attributes.new('gm', 'FLOAT_COLOR', 'POINT'); ca.data.foreach_set('color', cols.astype(np.float32).ravel())
    o = mkobj(ctx, 'CITY_ground', me, [ctx.M['ground']], 'ground')
    ctx.gbvh = BVHTree.FromPolygons(V.tolist(), F)
    ctx.rim = V[-NA:].copy(); ctx.rim_th = th
    return o


def build_rock(ctx):
    R = ctx.R; rim = ctx.rim; th = ctx.rim_th; NA = len(th)
    rim_r = np.hypot(rim[:, 0], rim[:, 1]); rim_z = rim[:, 2]
    ctx.layers = []
    z = 24.0
    while z < 176.0:
        t = R.uniform(4.0, 11.0); hd = R.uniform(1.0, 2.6) if R.random() < 0.62 else R.uniform(-0.9, -0.3)
        ctx.layers.append((z, min(z + t, 178.0), hd)); z += t + R.uniform(2.0, 8.0)
    rings = [rim.copy()]
    for D in (0.35, 0.9, 1.7, 2.7, 4.0, 5.6, 7.6, 10.0, 12.6, 15.4, 18.4, 21.5):
        zz = rim_z - D
        Rr = rock_R(ctx, th, zz)
        Rr = rim_r + (Rr - rim_r) * sstep(0.0, 5.0, D)
        rings.append(np.c_[Rr * np.cos(th), Rr * np.sin(th), zz])
    zt = float(rim_z.min()) - 24.0
    lv = set(np.round(np.arange(zt, 16.0, -2.6), 2).tolist())
    for lo, hi, hd in ctx.layers:
        for e in (lo - 0.45, lo + 0.45, hi - 0.45, hi + 0.45): lv.add(round(e, 2))
    lv |= {14.0, 12.0, 10.0, 8.0, 6.5, 5.6, 5.0}
    for zz in sorted([v for v in lv if v <= zt], reverse=True):
        Rr = rock_R(ctx, th, zz)
        rings.append(np.c_[Rr * np.cos(th), Rr * np.sin(th), np.full(NA, zz)])
    V = np.vstack(rings + [np.array([[0.0, 0.0, 5.0]])])
    nr = len(rings); a = np.arange(NA); a1 = (a + 1) % NA
    r = np.arange(nr - 1)[:, None]
    q = np.stack([r * NA + a, (r + 1) * NA + a, (r + 1) * NA + a1, r * NA + a1], -1).reshape(-1, 4)
    F = [tuple(x) for x in q.tolist()]
    c = len(V) - 1; last = (nr - 1) * NA
    F += [(c, last + int(j), last + int(i)) for i, j in zip(a, a1)]
    me = bpy.data.meshes.new('CITY_rock'); me.from_pydata(V.tolist(), [], F); me.update(); me.shade_smooth()
    o = mkobj(ctx, 'CITY_rock', me, [ctx.M['rock']], 'rock')
    ctx.rbvh = BVHTree.FromPolygons(V.tolist(), F)
    ctx.rock_rings = rings
    return o


# ------------------------------------------------------------------------------------------------------------------ streets
def root(p, q, fn, it=22):
    a = np.array(p, float); b = np.array(q, float); fa = fn(a) > 0
    for _ in range(it):
        m = (a + b) * 0.5
        if (fn(m) > 0) == fa: a = m
        else: b = m
    return (a + b) * 0.5


def clip_poly(poly, fv, types, fn):
    out = []; ot = []; n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]; fp, fq = fv[i], fv[(i + 1) % n]
        if fp > 0:
            out.append(np.asarray(p, float)); ot.append(types[i])
            if fq <= 0: out.append(root(p, q, fn)); ot.append('C')
        elif fq > 0:
            out.append(root(p, q, fn)); ot.append(types[i])
    return out, ot


def densify(poly, types, step=0.45):
    P = []; T = []; n = len(poly)
    for i in range(n):
        a = np.asarray(poly[i], float); b = np.asarray(poly[(i + 1) % n], float)
        m = max(1, int(math.ceil(float(np.hypot(*(b - a))) / step)))
        for k in range(m):
            P.append(a + (b - a) * (k / m)); T.append(types[i])
    return P, T


def split_cut(out, ot):
    """A clipped convex tread with several cut edges falls apart into several pieces: piece k runs from the re-entry after
    cut k-1 to the exit of cut k and is closed along the cut line."""
    cs = [i for i, t in enumerate(ot) if t == 'C']
    if len(cs) < 2: return [(out, ot)]
    n = len(out); pieces = []
    for a in range(len(cs)):
        i = (cs[a - 1] + 1) % n; idx = []
        while True:
            idx.append(i)
            if i == cs[a]: break
            i = (i + 1) % n
        P = [out[i] for i in idx]; T = [ot[i] for i in idx]; T[-1] = 'C'
        if len(P) >= 2: pieces.append((P, T))
    return pieces


def poly_area(P):
    P = np.asarray(P, float)
    return 0.5 * abs(float(np.dot(P[:, 0], np.roll(P[:, 1], -1)) - np.dot(P[:, 1], np.roll(P[:, 0], -1))))


def arc_fix(out, ot, fn, step=0.3):
    """Bend the straight cut edges ('C') of a clipped tread onto the curved cut line, so no chord pokes under the plaza or a higher street."""
    P2 = []; T2 = []; n = len(out)
    for i in range(n):
        P2.append(np.asarray(out[i], float)); T2.append(ot[i])
        if ot[i] != 'C': continue
        a = np.asarray(out[i], float); b = np.asarray(out[(i + 1) % n], float)
        m = int(math.ceil(float(np.hypot(*(b - a))) / step))
        for k in range(1, m):
            c = a + (b - a) * (k / m)
            for _ in range(5):
                f0 = fn(c)
                g = np.array((fn(c + (0.01, 0.0)) - fn(c - (0.01, 0.0)), fn(c + (0.0, 0.01)) - fn(c - (0.0, 0.01)))) / 0.02
                g2 = float(g @ g)
                if g2 < 1e-9 or abs(f0) < 1e-4: break
                c = c - f0 * g / g2
            P2.append(c); T2.append('C')
    return P2, T2


def street_mesh(ctx, st, mb, higher):
    G = ctx.G

    def fv(P):
        P = np.atleast_2d(np.asarray(P, float))
        f = np.hypot(P[:, 0] - HILL[0], P[:, 1] - HILL[1]) - PLAZA_R - GAP
        for h in higher:
            m = (P[:, 0] > h.lo[0]) & (P[:, 0] < h.hi[0]) & (P[:, 1] > h.lo[1]) & (P[:, 1] < h.hi[1])
            if m.any(): f[m] = np.minimum(f[m], pdist(P[m], h.P1) - h.hw - GAP)
        return f
    f1 = lambda p: float(fv(p)[0])

    def zbot(P, z):
        P = np.asarray(P, float)
        g = G.sample(ctx.Gc, P[:, 0], P[:, 1])
        dc = G.sample(ctx.dcanal, P[:, 0], P[:, 1])
        return np.where(dc < 0.15, z - 0.45, np.minimum(z - 0.6, g - 0.3))

    def tread(poly, types, z):
        P = np.array(poly); n = len(P)
        top = [mb.v((x, y, z)) for x, y in P]
        mb.fh(top, (0.0, 0.0, 1.0), 0)
        zb = zbot(P, z); bot = [None] * n; cen = P.mean(0)
        for i in range(n):
            if types[i] == 'X': continue
            j = (i + 1) % n
            if bot[i] is None: bot[i] = mb.v((P[i][0], P[i][1], zb[i]))
            if bot[j] is None: bot[j] = mb.v((P[j][0], P[j][1], zb[j]))
            e = P[j] - P[i]; out = np.array((e[1], -e[0]))
            if out @ ((P[i] + P[j]) / 2 - cen) < 0: out = -out
            mb.fh([top[i], top[j], bot[j], bot[i]], (out[0], out[1], 0.0), 1)

    RN = runs(st.z); n_all = len(st.z)
    for ri, (ia, ib) in enumerate(RN):
        z = float(st.z[ia])
        sa = 0.0 if ia == 0 else (ia - 0.5) * st.ds
        sb = st.L if ib == n_all else (ib - 0.5) * st.ds
        if sb - sa > 1e-4:
            n = max(1, int(math.ceil((sb - sa) / 1.0)))
            ss = np.linspace(sa, sb, n + 1)
            p, T, N = st.at(ss)
            Lp = p + N * st.hw; Rp = p - N * st.hw
            fL = fv(Lp); fR = fv(Rp)
            for k in range(n):
                poly = [Rp[k], Rp[k + 1], Lp[k + 1], Lp[k]]
                fvals = [fR[k], fR[k + 1], fL[k + 1], fL[k]]
                first = (ia == 0 and k == 0 and not st.closed); last = (ib == n_all and k == n - 1 and not st.closed)
                types = ['R', 'E' if last else 'X', 'L', 'S' if first else 'X']
                if min(fvals) < 2.0 * st.hw + 0.5:                      # near a cut line: test the edges, not only the corners
                    dp, dt = densify(poly, types)
                    dv = fv(np.array(dp))
                    if min(dv) <= 0: poly, types, fvals = dp, dt, list(dv)
                if min(fvals) > 0: tread(poly, types, z); continue
                if max(fvals) <= 0: continue
                for out, ot in split_cut(*clip_poly(poly, fvals, types, f1)):
                    out, ot = arc_fix(out, ot, f1)
                    if len(out) >= 3 and poly_area(out) > 0.004: tread(out, ot, z)
        if ib < n_all or st.closed:
            z2 = float(st.z[ib]) if ib < n_all else float(st.z[0])
            if abs(z2 - z) < 1e-6: continue
            p, T, N = st.at(sb); a = p + N * st.hw; b = p - N * st.hw
            fa, fb = f1(a), f1(b)
            if fa <= 0 and fb <= 0: continue
            if fa <= 0: a = root(b, a, f1)
            if fb <= 0: b = root(a, b, f1)
            lo, hi = min(z, z2), max(z, z2); hint = -T if z2 > z else T
            mb.fh([mb.v((a[0], a[1], lo)), mb.v((b[0], b[1], lo)), mb.v((b[0], b[1], hi)), mb.v((a[0], a[1], hi))], (hint[0], hint[1], 0.0), 1)


def build_streets(ctx):
    mb = MB()
    for st in ctx.streets:
        street_mesh(ctx, st, mb, [h for h in ctx.streets if h.pri > st.pri])
    return mkobj(ctx, 'CITY_streets', mb.mesh('CITY_streets'), [ctx.M['street'], ctx.M['step']], 'street')


def build_plaza(ctx):
    mb = MB(); n = 96
    rs = [PLAZA_R, 18.0, 16.2, 14.4, 12.6, 10.8, 9.0, 7.2, 5.4, 3.6, 1.8, 0.0]
    lathe(mb, [(r, 0.0) for r in rs], n, 0, (0.0, 0.0, 0.0), False, caps=False)
    for k in range(n):
        a0 = math.tau * k / n; a1 = math.tau * (k + 1) / n
        p0 = (PLAZA_R * math.cos(a0), PLAZA_R * math.sin(a0)); p1 = (PLAZA_R * math.cos(a1), PLAZA_R * math.sin(a1))
        b0 = gz(ctx, HILL[0] + p0[0], HILL[1] + p0[1]) - ctx.zplaza - 0.3; b1 = gz(ctx, HILL[0] + p1[0], HILL[1] + p1[1]) - ctx.zplaza - 0.3
        b0 = min(b0, -0.6); b1 = min(b1, -0.6)
        mb.fh([mb.v((p0[0], p0[1], 0.0)), mb.v((p1[0], p1[1], 0.0)), mb.v((p1[0], p1[1], b1)), mb.v((p0[0], p0[1], b0))],
              (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0.0), 1)
    return mkobj(ctx, 'CITY_plaza', mb.mesh('CITY_plaza'), [ctx.M['plaza'], ctx.M['step']], 'street', loc=(HILL[0], HILL[1], ctx.zplaza))


# ------------------------------------------------------------------------------------------------------------------ canals, springs, bridges
def disc_fan(mb, c, r, z, n, m, uvs=0.25):
    ring = [mb.v((c[0] + r * math.cos(math.tau * k / n), c[1] + r * math.sin(math.tau * k / n), z)) for k in range(n)]
    cv = mb.v((c[0], c[1], z))
    for k in range(n):
        k2 = (k + 1) % n
        uv = [(0.5, 0.5), (0.5 + 0.5 * math.cos(math.tau * k / n) * r * uvs, 0.5 + 0.5 * math.sin(math.tau * k / n) * r * uvs),
              (0.5 + 0.5 * math.cos(math.tau * k2 / n) * r * uvs, 0.5 + 0.5 * math.sin(math.tau * k2 / n) * r * uvs)]
        mb.f([cv, ring[k], ring[k2]], m, uv)


def build_canals(ctx):
    G = ctx.G; mb = MB(); wb = MB()
    ctx.spouts = []
    for cn in ctx.canals:
        P, N, T, lev = cn.P, cn.N, cn.T, cn.lev; n = len(P)
        ins = inset_xy(P[:, 0], P[:, 1])
        gL = G.sample(ctx.Gc, P[:, 0] + N[:, 0] * CAN_OW, P[:, 1] + N[:, 1] * CAN_OW)
        gR = G.sample(ctx.Gc, P[:, 0] - N[:, 0] * CAN_OW, P[:, 1] - N[:, 1] * CAN_OW)
        gC = G.sample(ctx.Gc, P[:, 0], P[:, 1])
        past = ins < 0.8
        bot = np.where(past, lev - 0.95, np.minimum(np.minimum(gL, gR), gC) - 0.45)
        sv = np.arange(n) * cn.ds
        Oc = {1.0: P + N * CAN_OW, -1.0: P - N * CAN_OW}; Ic = {1.0: P + N * CAN_HW, -1.0: P - N * CAN_HW}
        RN = runs(lev)
        for ri, (a, b) in enumerate(RN):
            L = float(lev[a]); i1 = min(b, n - 1); top = L + COPE
            idx = list(range(a, i1 + 1))
            if len(idx) >= 2:
                for sd in (1.0, -1.0):
                    O = Oc[sd]; I = Ic[sd]
                    for i in idx[:-1]:
                        j = i + 1; hint = (N[i][0] * sd, N[i][1] * sd, 0.0)
                        mb.fh([mb.v((O[i][0], O[i][1], bot[i])), mb.v((O[j][0], O[j][1], bot[j])), mb.v((O[j][0], O[j][1], top)), mb.v((O[i][0], O[i][1], top))], hint, 0)
                        mb.fh([mb.v((O[i][0], O[i][1], top)), mb.v((O[j][0], O[j][1], top)), mb.v((I[j][0], I[j][1], top)), mb.v((I[i][0], I[i][1], top))], (0.0, 0.0, 1.0), 1)
                        mb.fh([mb.v((I[i][0], I[i][1], top)), mb.v((I[j][0], I[j][1], top)), mb.v((I[j][0], I[j][1], L - 0.12)), mb.v((I[i][0], I[i][1], L - 0.12))], (-hint[0], -hint[1], 0.0), 0)
                for i in idx[:-1]:
                    j = i + 1
                    wb.fh([wb.v((Ic[-1.0][i][0], Ic[-1.0][i][1], L)), wb.v((Ic[-1.0][j][0], Ic[-1.0][j][1], L)), wb.v((Ic[1.0][j][0], Ic[1.0][j][1], L)), wb.v((Ic[1.0][i][0], Ic[1.0][i][1], L))],
                          (0.0, 0.0, 1.0), 0, uv=[(0.0, sv[i]), (0.0, sv[j]), (1.0, sv[j]), (1.0, sv[i])])
                    if past[i] and past[j]:
                        mb.fh([mb.v((Oc[-1.0][i][0], Oc[-1.0][i][1], bot[i])), mb.v((Oc[1.0][i][0], Oc[1.0][i][1], bot[i])), mb.v((Oc[1.0][j][0], Oc[1.0][j][1], bot[j])), mb.v((Oc[-1.0][j][0], Oc[-1.0][j][1], bot[j]))], (0.0, 0.0, -1.0), 0)
            if b < n:                     # weir: end caps, crest face, spill sheet
                L2 = float(lev[b]); Tb = T[b]; th_ = (Tb[0], Tb[1], 0.0)
                for sd in (1.0, -1.0):
                    O = Oc[sd][b]; I = Ic[sd][b]
                    mb.fh([mb.v((O[0], O[1], L2 + COPE)), mb.v((O[0], O[1], top)), mb.v((I[0], I[1], top)), mb.v((I[0], I[1], L2 + COPE))], th_, 0)
                A = Ic[-1.0][b]; B = Ic[1.0][b]
                mb.fh([mb.v((A[0], A[1], L2 - 0.12)), mb.v((B[0], B[1], L2 - 0.12)), mb.v((B[0], B[1], L - 0.04)), mb.v((A[0], A[1], L - 0.04))], th_, 0)
                rows = []
                for t in (0.0, 0.2, 0.45, 0.7, 1.0):
                    zz = L - 0.005 - (L - L2 + 0.005) * t ** 1.7; off = 0.03 + 0.42 * t
                    rows.append([wb.v((P[b][0] + N[b][0] * x + Tb[0] * off, P[b][1] + N[b][1] * x + Tb[1] * off, zz)) for x in np.linspace(-CAN_HW + 0.03, CAN_HW - 0.03, 5)])
                tv = [0.0, 0.2, 0.45, 0.7, 1.0]
                for r_ in range(4):
                    for c_ in range(4):
                        wb.fh([rows[r_][c_], rows[r_][c_ + 1], rows[r_ + 1][c_ + 1], rows[r_ + 1][c_]], (Tb[0], Tb[1], 0.6), 1,
                              uv=[(c_ / 4, tv[r_]), ((c_ + 1) / 4, tv[r_]), ((c_ + 1) / 4, tv[r_ + 1]), (c_ / 4, tv[r_ + 1])])
        # the spout over the rim: end caps, the lip, a corbel into the rock face
        e = n - 1; Te = T[e]; th_ = (Te[0], Te[1], 0.0); Le = float(lev[e])
        for sd in (1.0, -1.0):
            O = Oc[sd][e]; I = Ic[sd][e]
            mb.fh([mb.v((O[0], O[1], bot[e])), mb.v((O[0], O[1], Le + COPE)), mb.v((I[0], I[1], Le + COPE)), mb.v((I[0], I[1], bot[e]))], th_, 0)
        A = Ic[-1.0][e]; B = Ic[1.0][e]
        mb.fh([mb.v((A[0], A[1], bot[e])), mb.v((B[0], B[1], bot[e])), mb.v((B[0], B[1], Le - 0.03)), mb.v((A[0], A[1], Le - 0.03))], th_, 0)
        irim = int(np.argmax(ins < 0.0)) if (ins < 0.0).any() else e
        s0 = max(0, irim - 3); zt = float(bot[e])
        prof = [(P[s0], zt), (P[e], zt), (P[s0], zt - 3.6)]
        Ne = N[e]; w_ = CAN_OW - 0.15
        Lft = [mb.v((p[0] + Ne[0] * w_, p[1] + Ne[1] * w_, z)) for p, z in prof]; Rgt = [mb.v((p[0] - Ne[0] * w_, p[1] - Ne[1] * w_, z)) for p, z in prof]
        mb.fh(Lft, (Ne[0], Ne[1], 0.0), 0); mb.fh(Rgt, (-Ne[0], -Ne[1], 0.0), 0)
        for k in range(3):
            k2 = (k + 1) % 3; mid = (np.array(prof[k][0]) + np.array(prof[k2][0])) / 2
            hz = (prof[k][1] + prof[k2][1]) / 2
            hint = Vector((mid[0] - P[s0][0] * 0.5 - P[e][0] * 0.5, mid[1] - P[s0][1] * 0.5 - P[e][1] * 0.5, hz - (zt - 1.2)))
            mb.fh([Lft[k], Lft[k2], Rgt[k2], Rgt[k]], tuple(hint), 0)
        ctx.spouts.append(dict(p=np.array(P[e]), d=np.array(Te), lev=Le, canal=cn))
        # the spring basin
        sp = cn.spring; L0 = float(lev[0]); g0 = gz(ctx, sp[0], sp[1])
        lathe(mb, [(2.7, min(g0, L0) - 0.5), (2.7, L0 + COPE), (2.2, L0 + COPE), (2.2, L0 - 0.12)], 28, 0, (sp[0], sp[1], 0.0), False, caps=False)
        disc_fan(wb, sp, 2.2, L0, 28, 0)
        cyl(mb, (sp[0], sp[1], L0 - 0.15), (sp[0], sp[1], L0 + 1.25), 0.32, 0.28, 10, 0, False)
        cyl(mb, (sp[0], sp[1], L0 + 1.25), (sp[0], sp[1], L0 + 1.4), 0.46, 0.46, 10, 1, False)
        sphere(mb, (sp[0], sp[1], L0 + 1.58), 0.2, 10, 6, 2)
        d = cn.dir
        cyl(mb, (sp[0] + d[0] * 0.2, sp[1] + d[1] * 0.2, L0 + 0.9), (sp[0] + d[0] * 0.7, sp[1] + d[1] * 0.7, L0 + 0.88), 0.07, 0.06, 8, 2)
    o = mkobj(ctx, 'CITY_canals', mb.mesh('CITY_canals'), [ctx.M['stone'], ctx.M['trim'], ctx.M['bronze']], 'canal')
    w = mkobj(ctx, 'CITY_water', wb.mesh('CITY_water'), [ctx.M['water'], ctx.M['fall']], 'canal', props={'fallL': 1000.0})
    return o, w


def sweep_wall(mb, A, B, z0, z1, m_side, m_top):
    """A wall swept along two parallel polylines A (one face) and B (the other face)."""
    n = len(A)
    a0 = [mb.v((p[0], p[1], z0)) for p in A]; a1 = [mb.v((p[0], p[1], z1)) for p in A]
    b0 = [mb.v((p[0], p[1], z0)) for p in B]; b1 = [mb.v((p[0], p[1], z1)) for p in B]
    for i in range(n - 1):
        j = i + 1; ha = Vector((A[i][0] - B[i][0], A[i][1] - B[i][1], 0.0))
        mb.fh([a0[i], a0[j], a1[j], a1[i]], tuple(ha), m_side)
        mb.fh([b0[i], b0[j], b1[j], b1[i]], tuple(-ha), m_side)
        mb.fh([a1[i], a1[j], b1[j], b1[i]], (0.0, 0.0, 1.0), m_top)
    for i, s in ((0, -1), (n - 1, 1)):
        k = 1 if i == 0 else n - 2
        hint = Vector((A[i][0] - A[k][0], A[i][1] - A[k][1], 0.0))
        mb.fh([a0[i], b0[i], b1[i], a1[i]], tuple(hint), m_side)


def build_bridges(ctx):
    mb = MB()
    for cn in ctx.canals:
        for br in cn.bridges:
            st, sc, hb, Ht = br['st'], br['sc'], br['hb'], br['Ht']
            ss = np.linspace(sc - hb, sc + hb, max(2, int(2 * hb / 0.8)) + 1)
            if st.closed: ss = np.mod(ss, st.L)
            p, T, N = st.at(ss)
            for sd in (1.0, -1.0):
                A = p + N * sd * (st.hw - 0.08); B = p + N * sd * (st.hw - 0.38)
                sweep_wall(mb, A, B, Ht - 0.03, Ht + 0.7, 0, 1)
                for e in (0, len(ss) - 1):
                    c = p[e] + N[e] * sd * (st.hw - 0.23)
                    yaw = math.atan2(T[e][1], T[e][0])
                    box(mb, (c[0], c[1], Ht + 0.45), (0.3, 0.3, 0.48), 0, Matrix.Rotation(yaw, 3, 'Z'))
                    box(mb, (c[0], c[1], Ht + 0.97), (0.36, 0.36, 0.05), 1, Matrix.Rotation(yaw, 3, 'Z'))
                    sphere(mb, (c[0], c[1], Ht + 1.16), 0.15, 8, 5, 1)
    if not mb.F: return None
    return mkobj(ctx, 'CITY_bridges', mb.mesh('CITY_bridges'), [ctx.M['stone'], ctx.M['trim']], 'bridge')


# ------------------------------------------------------------------------------------------------------------------ rim: lookouts, railing, lamps, benches
def bench_geo(mb, c, yaw, z, mw=0, mi=1):
    """A bench; the sitter looks along local -y."""
    i0 = mb.n()
    box(mb, (0.0, 0.0, 0.45), (0.9, 0.22, 0.035), mw)
    box(mb, (0.0, 0.25, 0.78), (0.9, 0.03, 0.2), mw)
    for x in (-0.72, 0.72):
        box(mb, (x, 0.0, 0.2), (0.035, 0.2, 0.23), mi)
        box(mb, (x, 0.25, 0.6), (0.035, 0.035, 0.38), mi)
    mb.xform(i0, rotz(yaw, (c[0], c[1], z)))


def lamp_geo(mb, x, y, g):
    box(mb, (x, y, g + 0.05), (0.26, 0.26, 0.3), 0)
    cyl(mb, (x, y, g + 0.34), (x, y, g + 3.55), 0.075, 0.055, 8, 1)
    cyl(mb, (x, y, g + 1.0), (x, y, g + 1.14), 0.12, 0.12, 8, 1)
    box(mb, (x, y, g + 3.6), (0.2, 0.2, 0.05), 1)
    box(mb, (x, y, g + 3.9), (0.15, 0.15, 0.25), 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(mb, (x + sx * 0.16, y + sy * 0.16, g + 3.9), (0.022, 0.022, 0.26), 1)
    lathe(mb, [(0.27, 4.15), (0.0, 4.45)], 4, 1, (x, y, g), False, a0=math.pi / 4)
    cyl(mb, (x, y, g + 4.44), (x, y, g + 4.62), 0.03, 0.01, 6, 1)


def build_rimstuff(ctx):
    M = ctx.M; G = ctx.G
    # ---- lookouts
    lb = MB(); ctx.look_info = []
    for lk in ctx.looks:
        p, d = lk['p'], lk['d']; z0 = lk['z'] + 0.15
        nn = np.array((-d[1], d[0]))
        outline = [(-0.3, -3.6), (3.0, -3.6)] + [(3.0 + 3.6 * math.sin(a), -3.6 * math.cos(a)) for a in np.linspace(0, math.pi, 15)[1:-1]] + [(3.0, 3.6), (-0.3, 3.6)]
        P2 = [p + d * u + nn * v for u, v in outline]
        slab(lb, [(q[0], q[1], z0) for q in P2], 0.42, 4, ms=0)
        c = p + d * 3.0
        lathe(lb, [(0.45, z0 - 6.0), (1.6, z0 - 2.4), (3.2, z0 - 0.4)], 20, 0, (c[0], c[1], 0.0), False, caps=True)
        rail = [(0.7, -3.42), (3.0, -3.42)] + [(3.0 + 3.42 * math.sin(a), -3.42 * math.cos(a)) for a in np.linspace(0, math.pi, 15)[1:-1]] + [(3.0, 3.42), (0.7, 3.42)]
        Rp = [p + d * u + nn * v for u, v in rail]
        Rd = resample(np.array(Rp), 0.55)
        for q in Rd:
            box(lb, (q[0], q[1], z0 + 0.42), (0.09, 0.09, 0.42), 0)
        A = []; B = []
        Rd2 = resample(np.array(Rp), 0.4)
        T2 = np.gradient(Rd2, axis=0); T2 /= np.linalg.norm(T2, axis=1, keepdims=True); N2 = np.c_[-T2[:, 1], T2[:, 0]]
        sweep_wall(lb, Rd2 + N2 * 0.13, Rd2 - N2 * 0.13, z0 + 0.84, z0 + 0.97, 1, 1)
        tp = p + d * 5.4
        cyl(lb, (tp[0], tp[1], z0), (tp[0], tp[1], z0 + 1.15), 0.06, 0.05, 8, 2)
        cyl(lb, (tp[0] - d[0] * 0.45, tp[1] - d[1] * 0.45, z0 + 1.12), (tp[0] + d[0] * 0.5, tp[1] + d[1] * 0.5, z0 + 1.38), 0.08, 0.11, 10, 2)
        bench_geo(lb, p + d * 1.4, math.atan2(d[0], -d[1]), z0, 3, 2)
        ctx.look_info.append(dict(p=p, d=d, z=z0, tip=p + d * 6.6))
    ctx.lookouts = mkobj(ctx, 'CITY_lookouts', lb.mesh('CITY_lookouts'), [M['stone'], M['trim'], M['iron'], M['wood'], M['street']], 'look')
    # ---- rim railing
    rb = MB()
    th = np.linspace(0, math.tau, 7200, endpoint=False); rr = r_outline(th) - 0.9
    pts = np.c_[rr * np.cos(th), rr * np.sin(th)]
    seg = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1); cum = np.r_[0.0, np.cumsum(seg)]
    npost = int(cum[-1] / 2.5); sel = np.searchsorted(cum, np.linspace(0, cum[-1], npost, endpoint=False))
    posts = pts[np.clip(sel, 0, len(pts) - 1)]
    keep = np.ones(len(posts), bool)
    for spo in ctx.spouts: keep &= np.hypot(posts[:, 0] - spo['p'][0], posts[:, 1] - spo['p'][1]) > 3.4
    for li in ctx.look_info:
        c = li['p'] + li['d'] * 3.0; keep &= np.hypot(posts[:, 0] - c[0], posts[:, 1] - c[1]) > 7.4
    gzs = np.array([gz(ctx, q[0], q[1]) for q in posts])
    for i, q in enumerate(posts):
        if not keep[i]: continue
        g = gzs[i]
        box(rb, (q[0], q[1], g + 0.33), (0.1, 0.1, 0.63), 0)
        box(rb, (q[0], q[1], g + 1.0), (0.14, 0.14, 0.045), 1)
        j = (i + 1) % len(posts)
        if keep[j]:
            for h in (0.42, 0.86):
                beam(rb, (q[0], q[1], gzs[i] + h), (posts[j][0], posts[j][1], gzs[j] + h), 0.06, 0.06, 2)
    ctx.railing = mkobj(ctx, 'CITY_railing', rb.mesh('CITY_railing'), [M['stone'], M['trim'], M['iron']], 'prop')
    # ---- lamps
    mb = MB()
    for p, z, kind in ctx.lamps:
        g = gz(ctx, p[0], p[1]) if (z is None or kind == 'look') else z
        lamp_geo(mb, p[0], p[1], g)
    ctx.lampobj = mkobj(ctx, 'CITY_lamps', mb.mesh('CITY_lamps'), [M['stone'], M['iron'], M['lamp']], 'prop', props={'lit': 0.0})
    # ---- benches along the promenade (rim side) and round the plaza
    bb = MB()
    prom = [s for s in ctx.streets if s.name == 'prom'][0]
    s = 19.0
    while s < prom.L - 10:
        p, T, N = prom.at(s); q = p + N * (prom.hw + 1.2); q2 = p - N * (prom.hw + 1.2)
        sgn = 1.0 if inset_xy(q[0], q[1]) < inset_xy(q2[0], q2[1]) else -1.0
        q = p + N * sgn * (prom.hw + 1.2)
        f = ctx.flags[G.win(q[0] - 1.2, q[1] - 1.2, q[0] + 1.2, q[1] + 1.2)]
        clear = all(np.hypot(*(t['c'] - q)) > t['r'] + 1.2 for t in ctx.trees)
        if clear and not (f & (F_HOUSE | F_CANAL | F_OUT | F_MILL | F_SPECIAL | F_LAMP | F_TREE | F_BALC)).any() and inset_xy(q[0], q[1]) > 3.5:
            nrm = N * sgn          # the sitter looks out to sea
            bench_geo(bb, q, math.atan2(nrm[0], -nrm[1]), gz(ctx, q[0], q[1]) - 0.03)
            w, m = G.disc(q, 1.2); ctx.flags[w][m] |= F_LAMP
        s += 52.0
    for ang in (100.0, 175.0, 330.0):
        a = math.radians(ang); q = HILL + np.array((math.cos(a), math.sin(a))) * 8.6
        bench_geo(bb, q, a - math.pi / 2, ctx.zplaza)
    ctx.benches = mkobj(ctx, 'CITY_benches', bb.mesh('CITY_benches'), [M['wood'], M['iron']], 'prop')


# ------------------------------------------------------------------------------------------------------------------ plaza furniture
def build_fountain(ctx):
    mb = MB(); z0 = 0.0
    lathe(mb, [(4.25, -0.4), (4.25, 0.62), (3.8, 0.62), (3.8, 0.3)], 40, 0, (0, 0, 0), False, caps=False)
    disc_fan(mb, (0.0, 0.0), 3.8, 0.47, 40, 2, 0.2)
    lathe(mb, [(0.6, 0.3), (0.55, 0.8), (0.42, 1.4), (0.36, 1.9), (0.5, 2.05), (1.55, 2.2), (1.7, 2.42), (1.48, 2.42), (0.6, 2.32)], 24, 0, (0, 0, 0), True, caps=False)
    disc_fan(mb, (0.0, 0.0), 1.5, 2.36, 24, 2, 0.4)
    lathe(mb, [(0.28, 2.3), (0.22, 2.75), (0.3, 3.0), (0.86, 3.12), (0.92, 3.28), (0.76, 3.28), (0.3, 3.2)], 20, 0, (0, 0, 0), True, caps=False)
    disc_fan(mb, (0.0, 0.0), 0.78, 3.23, 20, 2, 0.6)
    lathe(mb, [(0.0, 3.2), (0.14, 3.24), (0.2, 3.5), (0.12, 3.75), (0.18, 3.95), (0.0, 4.2)], 12, 1, (0, 0, 0), True, caps=False)
    for (rt, zt, rb, zb, n) in ((1.66, 2.4, 1.95, 0.47, 32), (0.9, 3.26, 1.12, 2.36, 20)):
        top = [mb.v((rt * math.cos(math.tau * k / n), rt * math.sin(math.tau * k / n), zt)) for k in range(n + 1)]
        bot = [mb.v((rb * math.cos(math.tau * k / n), rb * math.sin(math.tau * k / n), zb)) for k in range(n + 1)]
        for k in range(n):
            a = math.tau * (k + 0.5) / n
            mb.fh([top[k], top[k + 1], bot[k + 1], bot[k]], (math.cos(a), math.sin(a), 0.2), 3,
                  uv=[(k / n * 3, 0.0), ((k + 1) / n * 3, 0.0), ((k + 1) / n * 3, zt - zb), (k / n * 3, zt - zb)])
    return mkobj(ctx, 'CITY_fountain', mb.mesh('CITY_fountain'), [ctx.M['stone'], ctx.M['trim'], ctx.M['water'], ctx.M['fall']], 'special',
                 loc=(HILL[0], HILL[1], ctx.zplaza), props={'fallL': 3.2})


def stall_mesh(R):
    mb = MB()
    for x, y, h in ((-1.2, -0.8, 2.25), (1.2, -0.8, 2.25), (-1.2, 0.8, 2.5), (1.2, 0.8, 2.5)):
        box(mb, (x, y, h / 2 - 0.01), (0.05, 0.05, h / 2 + 0.01), 0)
    box(mb, (0.0, -0.15, 0.82), (1.15, 0.55, 0.04), 0)
    box(mb, (0.0, -0.68, 0.43), (1.15, 0.02, 0.36), 1)
    for k in range(4): box(mb, (-0.9 + k * 0.6, 0.45, 0.39), (0.24, 0.18, 0.41), 0)
    # canopy: sloped striped canvas + valance
    zb, zf = 2.55, 2.2
    pts = [(-1.4, -1.05, zf), (1.4, -1.05, zf), (1.4, 0.95, zb), (-1.4, 0.95, zb)]
    t = [mb.v(p) for p in pts]; b = [mb.v((p[0], p[1], p[2] - 0.04)) for p in pts]
    mb.f(t, 2); mb.f(list(reversed(b)), 2)
    for i in range(4):
        j = (i + 1) % 4; mb.f([b[i], b[j], t[j], t[i]], 2)
    box(mb, (0.0, -1.06, zf - 0.13), (1.4, 0.012, 0.13), 2)
    # goods: crates of fruit and rolls of cloth
    for k in range(6):
        x = -0.92 + k * 0.37
        box(mb, (x, -0.2, 0.92), (0.15, 0.2, 0.06), 0)
        for q in range(4):
            sphere(mb, (x + R.uniform(-0.08, 0.08), -0.2 + R.uniform(-0.12, 0.12), 1.0), 0.06, 6, 4, 3 if k % 2 else 4)
    return mb.mesh('CITY_stall')


def build_plaza_props(ctx):
    R = ctx.R; out = []
    me = stall_mesh(random.Random(4))
    me.materials.append(ctx.M['wood']); me.materials.append(ctx.M['canvas']); me.materials.append(ctx.M['awning']); me.materials.append(ctx.M['cloth'])
    me.materials.append(ctx.M['leaf'])
    for i, ang in enumerate((10.0, 45.0, 125.0, 250.0, 285.0, 345.0)):
        a = math.radians(ang); c = HILL + np.array((math.cos(a), math.sin(a))) * 13.0
        yaw = a - math.pi / 2                                            # canopy front toward the fountain
        cl = R.sample(CLOTH, 2)
        o = mkobj(ctx, 'CITY_stall_%d' % i, me, (), 'special', loc=(c[0], c[1], ctx.zplaza), rot=(0, 0, yaw),
                  props={'awnC': lin(wchoice(R, AWNS)), 'clothC': lin(cl[0]), 'clothC2': lin(cl[1]), 'pat': float(R.randrange(3)),
                         'leafC': lin('#f08a3c'), 'fruit': 1.0})
        out.append(o)
    return out


# ------------------------------------------------------------------------------------------------------------------ facades
HM = dict(wall=0, roof=1, trim=2, stone=3, iron=4, wood=5, terrace=6, awning=7, dome=8, leaf=9, lamp=10, pot=11, clock=12)
HMATS = ['wall', 'roof', 'trim', 'stone', 'iron', 'wood', 'terrace', 'awning', 'dome', 'leaf', 'lamp', 'pot']


def tile_uv(name, x0=0.0, x1=BAYW, z0=0.0, z1=STOREY):
    k = DID[name]; c = k % 4; r = 3 - k // 4; e = 0.012
    cl = lambda a, lo, hi: min(max(a, lo + e), hi - e)
    x0 = cl(x0, 0, BAYW); x1 = cl(x1, 0, BAYW); z0 = cl(z0, 0, STOREY); z1 = cl(z1, 0, STOREY)
    return [((c + x0 / BAYW) / 4, (r + z0 / STOREY) / 4), ((c + x1 / BAYW) / 4, (r + z0 / STOREY) / 4),
            ((c + x1 / BAYW) / 4, (r + z1 / STOREY) / 4), ((c + x0 / BAYW) / 4, (r + z1 / STOREY) / 4)]


def tile_pt(name, x, z):
    k = DID[name]; c = k % 4; r = 3 - k // 4
    return ((c + min(max(x, 0.012), BAYW - 0.012) / BAYW) / 4, (r + min(max(z, 0.012), STOREY - 0.012) / STOREY) / 4)


WUV = [WHITE_UV] * 4


def wquad(mb, p0, p1, a0, a1, z0, z1, uv, m=0):
    """A quad on the wall line p0->p1 (outward normal on the right), between arc positions a0..a1 and heights z0..z1."""
    d = (p1[0] - p0[0], p1[1] - p0[1]); L = math.hypot(*d); d = (d[0] / L, d[1] / L)
    A = (p0[0] + d[0] * a0, p0[1] + d[1] * a0); B = (p0[0] + d[0] * a1, p0[1] + d[1] * a1)
    mb.f([mb.v((A[0], A[1], z0)), mb.v((B[0], B[1], z0)), mb.v((B[0], B[1], z1)), mb.v((A[0], A[1], z1))], m, uv)


def wpoly(mb, p0, p1, pts, uvfn, m=0):
    """A polygon on the wall line p0->p1 given as (a, z) points, counter-clockwise seen from outside."""
    d = (p1[0] - p0[0], p1[1] - p0[1]); L = math.hypot(*d); d = (d[0] / L, d[1] / L)
    mb.f([mb.v((p0[0] + d[0] * a, p0[1] + d[1] * a, z)) for a, z in pts], m, [uvfn(a, z) for a, z in pts])


def bay(mb, p0, p1, a0, a1, z0, z1, name):
    """One facade bay: the design tile at its true width, plain wall strips left and right when the bay is wider."""
    w = a1 - a0
    if w > BAYW + 0.06:
        m = (w - BAYW) / 2
        wquad(mb, p0, p1, a0, a0 + m, z0, z1, WUV); wquad(mb, p0, p1, a1 - m, a1, z0, z1, WUV)
        a0, a1 = a0 + m, a1 - m
    wquad(mb, p0, p1, a0, a1, z0, z1, tile_uv(name))


def xz_prism(mb, pts, y0, y1, m):
    """A polygon in the (x, z) plane, extruded along y from y0 to y1."""
    F = [mb.v((x, y0, z)) for x, z in pts]; B = [mb.v((x, y1, z)) for x, z in pts]
    s = 1.0 if y1 > y0 else -1.0
    mb.fh(F, (0.0, -s, 0.0), m); mb.fh(B, (0.0, s, 0.0), m)
    ar = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    o = 1.0 if ar > 0 else -1.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts); dx = pts[j][0] - pts[i][0]; dz = pts[j][1] - pts[i][1]
        mb.fh([F[i], F[j], B[j], B[i]], (dz * o, 0.0, -dx * o), m)


def facade(R, wall, nb, S):
    D = [[None] * nb for _ in range(S)]
    col = []
    for j in range(nb):
        if wall == 'front': col.append(wchoice(R, [('win_open', 3), ('win_closed', 2), ('win_half', 2), ('win_box', 3), ('win_french', 1.2), ('win_arch', 0.6)]))
        elif wall == 'back': col.append(wchoice(R, [('win_open', 2), ('win_closed', 3), ('win_half', 2), ('win_small', 1.5), ('blank', 1.0), ('win_box', 1)]))
        else: col.append(wchoice(R, [('blank', 3), ('win_small', 2.5), ('win_closed', 1.5), ('win_open', 1), ('blank_plant', 0.7)]))
    for k in range(S):
        for j in range(nb):
            if k == 0:
                if wall == 'front': D[k][j] = wchoice(R, [('win_closed', 2), ('win_half', 1.5), ('gwin_grille', 2), ('blank_plant', 1.0), ('win_small', 1.0), ('win_box', 1.0)])
                elif wall == 'back': D[k][j] = wchoice(R, [('win_closed', 2), ('gwin_grille', 1.5), ('blank', 1.5), ('door_rect', 0.6), ('win_small', 1)])
                else: D[k][j] = wchoice(R, [('blank', 3), ('blank_plant', 1.2), ('win_small', 1.5), ('gwin_grille', 0.8)])
            else:
                D[k][j] = col[j] if R.random() < 0.75 else wchoice(R, [('win_open', 2), ('win_closed', 2), ('win_box', 2), ('win_half', 1), ('blank', 0.4)])
                if k == S - 1 and D[k][j] in ('win_open', 'win_closed') and R.random() < 0.25: D[k][j] = 'win_arch'
    return D


def walls_box(mb, x0, x1, y0, y1, S, designs, c=0.12, top=None, skip=()):
    """Four facades of a rectangular block with chamfered corners. designs: dict wall -> D[k][j]."""
    top = S * STOREY if top is None else top
    lines = {'front': ((x0 + c, y0), (x1 - c, y0)), 'right': ((x1, y0 + c), (x1, y1 - c)),
             'back': ((x1 - c, y1), (x0 + c, y1)), 'left': ((x0, y1 - c), (x0, y0 + c))}
    cham = {'fr': ((x1 - c, y0), (x1, y0 + c)), 'br': ((x1, y1 - c), (x1 - c, y1)), 'bl': ((x0 + c, y1), (x0, y1 - c)), 'fl': ((x0, y0 + c), (x0 + c, y0))}
    for wname, (p0, p1) in lines.items():
        if wname in skip: continue
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]); D = designs[wname]; nb = len(D[0]); bw = L / nb
        for k in range(S):
            for j in range(nb):
                bay(mb, p0, p1, j * bw, (j + 1) * bw, k * STOREY, (k + 1) * STOREY, D[k][j])
        if top > S * STOREY + 1e-6:
            wquad(mb, p0, p1, 0.0, L, S * STOREY, top, WUV)
    for key, (p0, p1) in cham.items():
        if 'left' in skip and key in ('fl', 'bl'): continue
        wquad(mb, p0, p1, 0.0, math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 0.0, top, WUV)
    return lines


def roof_hip(mb, ax, ay, z0, pitch=24.0, th=0.16):
    """Hip roof (a pyramid when ax == ay) over the eave rectangle +-ax, +-ay at height z0. Returns the top height."""
    t = math.tan(math.radians(pitch)); cs = math.cos(math.radians(pitch))
    E = [(-ax, -ay), (ax, -ay), (ax, ay), (-ax, ay)]
    if abs(ax - ay) < 1e-4:
        rise = ax * t; rA = rB = (0.0, 0.0)
        faces = [[E[0], E[1], rA], [E[1], E[2], rA], [E[2], E[3], rA], [E[3], E[0], rA]]
    elif ax > ay:
        rise = ay * t; rA = (-(ax - ay), 0.0); rB = (ax - ay, 0.0)
        faces = [[E[0], E[1], rB, rA], [E[1], E[2], rB], [E[2], E[3], rA, rB], [E[3], E[0], rA]]
    else:
        rise = ax * t; rA = (0.0, -(ay - ax)); rB = (0.0, ay - ax)
        faces = [[E[0], E[1], rA], [E[1], E[2], rB, rA], [E[2], E[3], rB], [E[3], E[0], rA, rB]]
    zt = z0 + rise
    for f in faces:
        e0, e1 = f[0], f[1]; ed = (e1[0] - e0[0], e1[1] - e0[1]); L = math.hypot(*ed); ed = (ed[0] / L, ed[1] / L)
        inward = (-ed[1], ed[0])
        zs = [z0, z0] + [zt] * (len(f) - 2)
        uv = [(((p[0] - e0[0]) * ed[0] + (p[1] - e0[1]) * ed[1]) / 2.0, ((p[0] - e0[0]) * inward[0] + (p[1] - e0[1]) * inward[1]) / cs / 2.0) for p in f]
        mb.f([mb.v((p[0], p[1], z)) for p, z in zip(f, zs)], HM['roof'], uv)
        mb.f(list(reversed([mb.v((p[0], p[1], z - th)) for p, z in zip(f, zs)])), HM['trim'])
    for i in range(4):
        a, b = E[i], E[(i + 1) % 4]
        mb.fh([mb.v((a[0], a[1], z0 - th)), mb.v((b[0], b[1], z0 - th)), mb.v((b[0], b[1], z0)), mb.v((a[0], a[1], z0))], (b[1] - a[1], a[0] - b[0], 0.0), HM['trim'])
    if rA != rB: beam(mb, (rA[0], rA[1], zt), (rB[0], rB[1], zt), 0.22, 0.16, HM['roof'])
    for e in E:
        r_ = rA if (e[0] < 0 if ax > ay else e[1] < 0) else rB
        beam(mb, (e[0], e[1], z0 + 0.01), (r_[0], r_[1], zt + 0.01), 0.2, 0.12, HM['roof'])
    return zt


def roof_gable(mb, ax, ay, z0, pitch=30.0, th=0.16):
    """Gable roof, ridge along x. Returns the ridge height."""
    t = math.tan(math.radians(pitch)); cs = math.cos(math.radians(pitch)); zt = z0 + ay * t
    for sgn in (-1.0, 1.0):
        if sgn < 0: q = [(-ax, -ay, z0), (ax, -ay, z0), (ax, 0.0, zt), (-ax, 0.0, zt)]
        else: q = [(ax, ay, z0), (-ax, ay, z0), (-ax, 0.0, zt), (ax, 0.0, zt)]
        uv = [((p[0] * (-sgn)) / 2.0, (ay - abs(p[1])) / cs / 2.0) for p in q]
        mb.f([mb.v(p) for p in q], HM['roof'], uv)
        mb.f(list(reversed([mb.v((p[0], p[1], p[2] - th)) for p in q])), HM['trim'])
        mb.fh([mb.v((-ax, sgn * ay, z0 - th)), mb.v((ax, sgn * ay, z0 - th)), mb.v((ax, sgn * ay, z0)), mb.v((-ax, sgn * ay, z0))], (0.0, sgn, 0.0), HM['trim'])
        for sx in (-1.0, 1.0):
            mb.fh([mb.v((sx * ax, sgn * ay, z0 - th)), mb.v((sx * ax, 0.0, zt - th)), mb.v((sx * ax, 0.0, zt)), mb.v((sx * ax, sgn * ay, z0))], (sx, 0.0, 0.0), HM['trim'])
    beam(mb, (-ax - 0.02, 0.0, zt), (ax + 0.02, 0.0, zt), 0.24, 0.18, HM['roof'])
    return zt


def gable_walls(mb, hx, hy, Hw, z0, ay, pitch, c=0.12, oculus=True):
    """The two pentagons under a gable roof (ridge along x) on the walls x = +-hx."""
    t = math.tan(math.radians(pitch)); zu = lambda y: z0 - 0.16 + (ay - abs(y)) * t
    for p0, p1 in (((hx, -hy + c), (hx, hy - c)), ((-hx, hy - c), (-hx, -hy + c))):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]); ys = p0[1]; dy = (p1[1] - p0[1]) / L
        yat = lambda a: ys + dy * a; am = -ys / dy
        if oculus and zu(0.45) - Hw > 1.35:
            wpoly(mb, p0, p1, [(0.0, Hw), (am - 1.2, Hw), (am - 1.2, zu(yat(am - 1.2))), (0.0, zu(yat(0.0)))], lambda a, z: WHITE_UV)
            wpoly(mb, p0, p1, [(am - 1.2, Hw), (am + 1.2, Hw), (am + 1.2, zu(yat(am + 1.2))), (am, zu(0.0)), (am - 1.2, zu(yat(am - 1.2)))],
                  lambda a, z: tile_pt('attic', a - am + 1.2, z - Hw))
            wpoly(mb, p0, p1, [(am + 1.2, Hw), (L, Hw), (L, zu(yat(L))), (am + 1.2, zu(yat(am + 1.2)))], lambda a, z: WHITE_UV)
        else:
            wpoly(mb, p0, p1, [(0.0, Hw), (L, Hw), (L, zu(yat(L))), (am, zu(0.0)), (0.0, zu(yat(0.0)))], lambda a, z: WHITE_UV)


def parapet(mb, x0, x1, y0, y1, Hw, h=0.95):
    """Flat-roof terrace: inner faces, floor, coping and a cornice band (the outer faces are the walls continued by walls_box(top=))."""
    i = 0.24; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; ex, ey = (x1 - x0) / 2, (y1 - y0) / 2
    ring_rect(mb, (cx, cy), (ex + 0.05, ey + 0.05), (ex - i - 0.05, ey - i - 0.05), Hw + h, Hw + h + 0.1, HM['trim'])
    ring_rect(mb, (cx, cy), (ex + 0.1, ey + 0.1), (ex - 0.1, ey - 0.1), Hw - 0.12, Hw + 0.1, HM['trim'])
    xa, xb, ya, yb = x0 + i, x1 - i, y0 + i, y1 - i
    q = [(xa, ya), (xb, ya), (xb, yb), (xa, yb)]
    mb.f([mb.v((x, y, Hw + 0.02)) for x, y in q], HM['terrace'])
    for k in range(4):
        a, b = q[k], q[(k + 1) % 4]
        mb.fh([mb.v((a[0], a[1], Hw + 0.02)), mb.v((b[0], b[1], Hw + 0.02)), mb.v((b[0], b[1], Hw + h)), mb.v((a[0], a[1], Hw + h))],
              ((cx - (a[0] + b[0]) / 2), (cy - (a[1] + b[1]) / 2), 0.0), HM['wall'], uv=WUV)


def pot_geo(mb, x, y, z, R, big=False):
    r = 0.24 if big else 0.18; h = 0.42 if big else 0.34; z = z - 0.01
    lathe(mb, [(r * 0.7, z), (r, z + h), (r * 1.12, z + h), (r * 1.12, z + h + 0.06), (r * 0.9, z + h + 0.06)], 8, HM['pot'], (x, y, 0.0), False, caps=True)
    for k in range(2 if big else 1):
        sphere(mb, (x + R.uniform(-0.06, 0.06), y + R.uniform(-0.06, 0.06), z + h + 0.16 + k * 0.12), r * R.uniform(1.1, 1.5), 7, 4, HM['leaf'], True, R=R, jit=0.12)


def chimney(mb, x, y, zb, zt, R):
    box(mb, (x, y, (zb + zt) / 2), (0.3, 0.3, (zt - zb) / 2), HM['trim'])
    box(mb, (x, y, zt + 0.04), (0.38, 0.38, 0.06), HM['stone'])
    for o in ([0.0] if R.random() < 0.5 else [-0.13, 0.13]):
        cyl(mb, (x + o, y, zt + 0.08), (x + o, y, zt + 0.42), 0.09, 0.08, 8, HM['pot'])


def balcony(mb, xc, bw, y0, z, R):
    """Balcony on the front wall (y = y0, outward -y) at floor height z, centred at xc."""
    hw = bw / 2 + 0.12; D = 1.0
    box(mb, (xc, y0 - D / 2 + 0.01, z - 0.075), (hw, D / 2 + 0.01, 0.075), HM['stone'])
    for sx in (-1, 1):
        box(mb, (xc + sx * (hw - 0.18), y0 - 0.3, z - 0.29), (0.08, 0.32, 0.16), HM['stone'])
    yf = y0 - D + 0.05
    n = max(4, int(2 * hw / 0.2))
    for i in range(n + 1):
        box(mb, (xc - hw + 0.05 + i * (2 * hw - 0.1) / n, yf, z + 0.46), (0.016, 0.016, 0.48), HM['iron'])
    for sx in (-1, 1):
        for k in range(1, 5):
            box(mb, (xc + sx * (hw - 0.05), y0 - 0.06 - k * (D - 0.11) / 5, z + 0.46), (0.016, 0.016, 0.48), HM['iron'])
        beam(mb, (xc + sx * (hw - 0.05), y0 + 0.01, z + 0.95), (xc + sx * (hw - 0.05), yf, z + 0.95), 0.05, 0.05, HM['iron'])
    beam(mb, (xc - hw + 0.03, yf, z + 0.95), (xc + hw - 0.03, yf, z + 0.95), 0.05, 0.05, HM['iron'])
    beam(mb, (xc - hw + 0.03, yf, z + 0.1), (xc + hw - 0.03, yf, z + 0.1), 0.04, 0.04, HM['iron'])
    pot_geo(mb, xc - hw + 0.35, y0 - 0.35, z, R)
    if R.random() < 0.6: pot_geo(mb, xc + hw - 0.35, y0 - 0.35, z, R, big=True)


def house_mesh(V, seed):
    R = random.Random(seed); mb = MB(); meta = {'lines': [], 'vane': None, 'roof': V['roof']}
    w, d, S = V['w'], V['d'], V['S']; hx, hy = w / 2, d / 2; Hw = S * STOREY; c = 0.12; roof = V['roof']
    nbF = max(1, round((w - 2 * c) / BAYW)); nbS = max(1, round((d - 2 * c) / BAYW)); bwF = (w - 2 * c) / nbF
    D = {'front': facade(R, 'front', nbF, S), 'back': facade(R, 'back', nbF, S), 'left': facade(R, 'side', nbS, S), 'right': facade(R, 'side', nbS, S)}
    door = nbF // 2
    D['front'][0][door] = R.choice(['door_arch', 'door_rect', 'door_double', 'door_rect'])
    for j in V.get('shop', ()): D['front'][0][j] = 'shop'
    for (k, j) in V.get('balc', ()): D['front'][k][j] = 'balc_door'
    if V.get('stair'):
        D['front'][1][2] = 'door_rect'; D['front'][0][0] = 'blank'; D['front'][0][1] = 'blank'; D['front'][0][2] = 'gwin_grille'
        D['front'][0][3] = R.choice(['door_arch', 'door_rect'])
    flat = roof in ('flat', 'dome')
    walls_box(mb, -hx, hx, -hy, hy, S, D, c, top=Hw + 0.95 if flat else None)
    bx = lambda j: -hx + c + (j + 0.5) * bwF
    # ---- roof
    if roof in ('hip', 'pyr'):
        ring_rect(mb, (0.0, 0.0), (hx + 0.16, hy + 0.16), (hx - 0.1, hy - 0.1), Hw - 0.26, Hw + 0.05, HM['trim'])
        zt = roof_hip(mb, hx + 0.45, hy + 0.45, Hw + 0.05)
        meta['vane'] = (0.0, 0.0, zt + 0.08); meta['top'] = zt
    elif roof == 'gable':
        ring_rect(mb, (0.0, 0.0), (hx + 0.16, hy + 0.16), (hx - 0.1, hy - 0.1), Hw - 0.26, Hw + 0.05, HM['trim'])
        zt = roof_gable(mb, hx + 0.28, hy + 0.4, Hw + 0.05)
        gable_walls(mb, hx, hy, Hw, Hw + 0.05, hy + 0.4, 30.0, c)
        meta['vane'] = (hx * 0.7, 0.0, zt + 0.08); meta['top'] = zt
    else:
        parapet(mb, -hx, hx, -hy, hy, Hw)
        zt = Hw + 1.05; meta['top'] = zt
        if roof == 'dome':
            lathe(mb, [(2.2, Hw), (2.2, Hw + 1.1)], 8, HM['trim'], (0.0, 0.0, 0.0), False, a0=math.pi / 8, caps=False)
            prof = [(2.45, Hw + 1.1)] + [(2.45 * math.cos(a), Hw + 1.1 + 2.3 * math.sin(a)) for a in np.linspace(0.15, math.pi / 2 - 0.12, 6)] + [(0.0, Hw + 3.42)]
            lathe(mb, prof, 24, HM['dome'], (0.0, 0.0, 0.0), True, caps=True)
            cyl(mb, (0.0, 0.0, Hw + 3.3), (0.0, 0.0, Hw + 3.9), 0.28, 0.24, 8, HM['trim'])
            sphere(mb, (0.0, 0.0, Hw + 4.02), 0.14, 8, 5, HM['iron'])
            beam(mb, (0.0, 0.0, Hw + 4.0), (0.0, 0.0, Hw + 4.75), 0.06, 0.06, HM['iron'])
            beam(mb, (-0.22, 0.0, Hw + 4.48), (0.22, 0.0, Hw + 4.48), 0.05, 0.05, HM['iron'])
            meta['top'] = Hw + 4.7
            for k in range(4):
                a = math.pi / 4 + k * math.pi / 2; pot_geo(mb, 2.42 * math.cos(a), 2.42 * math.sin(a), Hw + 0.02, R, big=True)
        else:
            hut = (-hx + 0.26, -hx + 2.66, hy - 2.66, hy - 0.26)           # stair hut with a door onto the terrace
            wquad(mb, (hut[0], hut[2]), (hut[1], hut[2]), 0.0, 2.4, Hw, Hw + 2.4, tile_uv('door_rect', 0, BAYW, 0.0, 2.4))
            wquad(mb, (hut[1], hut[2]), (hut[1], hut[3]), 0.0, 2.4, Hw, Hw + 2.4, WUV)
            wquad(mb, (hut[1], hut[3]), (hut[0], hut[3]), 0.0, 2.4, Hw, Hw + 2.4, WUV)
            wquad(mb, (hut[0], hut[3]), (hut[0], hut[2]), 0.0, 2.4, Hw, Hw + 2.4, WUV)
            box(mb, ((hut[0] + hut[1]) / 2, (hut[2] + hut[3]) / 2, Hw + 2.46), (1.32, 1.32, 0.07), HM['trim'])
        ter = V.get('terrace', ())
        if 'pergola' in ter:
            xs = (-hx + 0.7, -hx + 3.5); ys = (-hy + 0.7, -hy + 3.1)
            for x in xs:
                for y in ys: box(mb, (x, y, Hw + 1.16), (0.07, 0.07, 1.16), HM['wood'])
            for y in ys: box(mb, ((xs[0] + xs[1]) / 2, y, Hw + 2.36), ((xs[1] - xs[0]) / 2 + 0.3, 0.06, 0.07), HM['wood'])
            for k in range(7):
                x = xs[0] - 0.15 + k * (xs[1] - xs[0] + 0.3) / 6
                box(mb, (x, (ys[0] + ys[1]) / 2, Hw + 2.46), (0.04, (ys[1] - ys[0]) / 2 + 0.3, 0.04), HM['wood'])
            for k in range(6):
                sphere(mb, (R.uniform(xs[0], xs[1]), R.uniform(ys[0], ys[1]), Hw + 2.62), R.uniform(0.6, 0.9), 9, 4, HM['leaf'], True, sq=(1.0, 1.0, 0.45), R=R, jit=0.1)
            for x in xs: pot_geo(mb, x + 0.3, ys[0] - 0.05, Hw + 0.02, R, big=True)
        if 'tank' in ter:
            box(mb, (hx - 1.0, -hy + 1.0, Hw + 0.11), (0.5, 0.35, 0.1), HM['stone'])
            cyl(mb, (hx - 1.0, -hy + 1.0, Hw + 0.19), (hx - 1.0, -hy + 1.0, Hw + 1.25), 0.5, 0.5, 12, HM['iron'], True)
        if 'laundry' in ter:
            x0, x1 = -0.4, hx - 0.7; yl = 0.2 if 'pergola' in ter else -hy + 1.3
            for x in (x0, x1):
                box(mb, (x, yl, Hw + 0.89), (0.03, 0.03, 0.89), HM['iron'])
                box(mb, (x, yl, Hw + 1.76), (0.03, 0.32, 0.025), HM['iron'])
            for dy in (-0.27, 0.27):
                meta['lines'].append(((x0, yl + dy, Hw + 1.74), (x1, yl + dy, Hw + 1.74)))
        if 'pots' in ter:
            for k in range(5):
                pot_geo(mb, -hx + 3.2 + k * 0.9, -hy + 0.45, Hw + 0.02, R, big=k % 2 == 0)
    # ---- chimneys
    for k in range(V.get('chim', 0)):
        sg = -1 if k == 0 else 1
        if V.get('belv'):
            chimney(mb, hx * 0.45 * sg, -hy * 0.62, meta['top'] - 1.6, meta['top'] + 0.75, R)
        elif roof in ('hip', 'pyr'):
            if hx >= hy: x = sg * min(hx * 0.45, max(0.6, (hx - hy) * 0.6)); y = 0.35
            else: x = 0.5 * sg; y = sg * min(hy * 0.45, max(0.6, (hy - hx) * 0.6))
            chimney(mb, x, y, meta['top'] - 1.6, meta['top'] + 0.75, R)
        elif roof == 'gable':
            chimney(mb, -hx * 0.55 if k == 0 else hx * 0.3, 0.45, meta['top'] - 1.4, meta['top'] + 0.7, R)
    # ---- belvedere tower through a hip roof
    if V.get('belv'):
        b = 1.7; z0 = Hw - 0.2; z1 = meta['top'] + 0.4
        for p0, p1 in (((-b, -b), (b, -b)), ((b, -b), (b, b)), ((b, b), (-b, b)), ((-b, b), (-b, -b))):
            wquad(mb, p0, p1, 0.0, 2 * b, z0, z1, WUV)
        za = z1
        for i, (tx, ty, yaw) in enumerate(((0.0, -b + 0.15, 0.0), (b - 0.15, 0.0, math.pi / 2), (0.0, b - 0.15, math.pi), (-b + 0.15, 0.0, -math.pi / 2))):
            W = 2 * b if i % 2 == 0 else 2 * b - 0.56
            arch_plate(mb, W, 2.6, 0.3, 1.5, 0.0, 1.55, Matrix.Translation((tx, ty, za)) @ Matrix.Rotation(yaw, 4, 'Z'), HM['trim'], 10)
        box(mb, (0.0, 0.0, za + 0.05), (b - 0.28, b - 0.28, 0.05), HM['terrace'])
        ring_rect(mb, (0.0, 0.0), (b + 0.12, b + 0.12), (b - 0.2, b - 0.2), za + 2.58, za + 2.82, HM['trim'])
        zt2 = roof_hip(mb, b + 0.35, b + 0.35, za + 2.82, 28.0)
        meta['vane'] = (0.0, 0.0, zt2 + 0.04); meta['top'] = zt2
    # ---- wing with a roof terrace
    if V.get('wing'):
        ww, wd, Sw = V['wing']; x0, x1, y0, y1 = hx - c, hx + ww, -hy, -hy + wd
        Dw = {'front': facade(R, 'front', 2, Sw), 'right': facade(R, 'side', 2, Sw), 'back': facade(R, 'back', 2, Sw), 'left': facade(R, 'side', 2, Sw)}
        Dw['front'][0][1] = 'door_arch'
        walls_box(mb, x0, x1, y0, y1, Sw, Dw, c, top=Sw * STOREY + 0.95, skip=('left',))
        parapet(mb, x0, x1, y0, y1, Sw * STOREY)
        for k in range(3): pot_geo(mb, x0 + 0.9 + k * 1.3, y0 + 0.55, Sw * STOREY + 0.02, R, big=k == 1)
    # ---- string courses
    if V.get('string'):
        for k in range(1, S):
            ring_rect(mb, (0.0, 0.0), (hx + 0.05, hy + 0.05), (hx - 0.1, hy - 0.1), k * STOREY - 0.06, k * STOREY + 0.06, HM['trim'])
    # ---- balconies, awnings, lanterns, the outside stair
    for (k, j) in V.get('balc', ()): balcony(mb, bx(j), bwF, -hy, k * STOREY, R)
    if V.get('awning'):
        for j in V.get('shop', ()):
            xa, xb = bx(j) - bwF / 2 + 0.1, bx(j) + bwF / 2 - 0.1
            q = [(xa, -hy + 0.01, 2.98), (xb, -hy + 0.01, 2.98), (xb, -hy - 1.18, 2.5), (xa, -hy - 1.18, 2.5)]
            t_ = [mb.v(p) for p in q]; b_ = [mb.v((p[0], p[1], p[2] - 0.03)) for p in q]
            mb.fh(t_, (0.0, -0.4, 1.0), HM['awning']); mb.fh(b_, (0.0, 0.4, -1.0), HM['awning'])
            for i in range(4):
                i2 = (i + 1) % 4; mid = ((q[i][0] + q[i2][0]) / 2 - (xa + xb) / 2, (q[i][1] + q[i2][1]) / 2 + hy + 0.6, 0.0)
                mb.fh([b_[i], b_[i2], t_[i2], t_[i]], mid, HM['awning'])
            box(mb, ((xa + xb) / 2, -hy - 1.19, 2.37), ((xb - xa) / 2, 0.012, 0.13), HM['awning'])
            for x in (xa + 0.06, xb - 0.06):
                beam(mb, (x, -hy + 0.02, 2.55), (x, -hy - 1.15, 2.49), 0.035, 0.035, HM['iron'])
    if V.get('lantern'):
        x = bx(door) + bwF / 2 - 0.22
        beam(mb, (x, -hy + 0.02, 2.62), (x, -hy - 0.42, 2.62), 0.04, 0.05, HM['iron'])
        box(mb, (x, -hy - 0.42, 2.4), (0.1, 0.1, 0.16), HM['lamp'])
        lathe(mb, [(0.15, 2.56), (0.0, 2.72)], 4, HM['iron'], (x, -hy - 0.42, 0.0), False, a0=math.pi / 4)
    if V.get('stair'):
        x0 = -hx + 0.3; xL = x0 + 3.6; yb = -hy - 1.05; yw = -hy + 0.02
        prof = [(x0, -0.5), (xL + 0.02, -0.5), (xL + 0.02, 3.0)]
        for i in range(11, -1, -1):
            prof += [(x0 + i * 0.3, (i + 1) * 0.25)] if i == 11 else [(x0 + (i + 1) * 0.3, (i + 1) * 0.25), (x0 + i * 0.3, (i + 1) * 0.25)]
        prof = [p for k_, p in enumerate(prof) if k_ == 0 or abs(p[0] - prof[k_ - 1][0]) + abs(p[1] - prof[k_ - 1][1]) > 1e-6]
        xz_prism(mb, prof, yb, yw, HM['trim'])
        xz_prism(mb, [(x0 - 0.02, 0.0), (xL, 2.75), (xL, 3.9), (x0 - 0.02, 1.15)], yb - 0.02, yb + 0.16, HM['trim'])
        box(mb, (xL + 1.6, (yb + yw) / 2, 2.85), (1.6, (yw - yb) / 2, 0.15), HM['trim'])
        xz_prism(mb, [(xL - 0.01, 2.7), (xL + 3.2, 2.7), (xL + 3.2, 3.9), (xL - 0.01, 3.9)], yb - 0.02, yb + 0.16, HM['trim'])
        box(mb, (xL + 3.08, (yb + yw) / 2, 3.45), (0.12, (yw - yb) / 2, 0.45), HM['trim'])
        box(mb, (xL + 3.05, yb + 0.2, 1.1), (0.15, 0.15, 1.62), HM['trim'])
        for k in range(3): pot_geo(mb, xL + 0.6 + k * 0.95, yb + 0.5, 3.0, R, big=k == 1)
    return mb.mesh('CITY_h_%s_%d' % (V['name'], seed % 100)), meta


def house_props(R, V):
    return {'wallC': lin(wchoice(R, WALLS)), 'shutC': lin(wchoice(R, SHUTS)), 'roofC': lin(wchoice(R, DOMES if V['roof'] == 'dome' else ROOFS)),
            'awnC': lin(wchoice(R, AWNS)), 'leafC': lin(wchoice(R, LEAVES)), 'fruit': 0.0, 'lit': 0.0, 'seed': R.uniform(0, 100)}


def plinth(ctx, o, rects, floor, name, top=0.12, margin=0.06, extra=0.35):
    """Stone foundation boxes under object o (object-local rectangles) down below the lowest ground, where the ground dips under the floor."""
    cs, sn = math.cos(o.rotation_euler.z), math.sin(o.rotation_euler.z); ox, oy = o.location.x, o.location.y
    fb = MB(); need = False
    for (x0, x1, y0, y1) in rects:
        g = min(gz(ctx, ox + lx * cs - ly * sn, oy + lx * sn + ly * cs) for lx in np.linspace(x0 - margin, x1 + margin, 5) for ly in np.linspace(y0 - margin, y1 + margin, 4))
        if g - floor < 0.4:
            need = True; zb = min(g - floor - extra, top - 0.3)
            box(fb, ((x0 + x1) / 2, (y0 + y1) / 2, (zb + top) / 2), ((x1 - x0) / 2 + margin, (y1 - y0) / 2 + margin, (top - zb) / 2), 0)
    if need:
        return mkobj(ctx, name, fb.mesh(name), [ctx.M['stone']], 'found', parent=o)
    return None


def bevel_prep(me, amin=0.6, ang=40.0):
    """Weld the separately built pieces of a mesh and mark its big sharp edges (both faces >= amin m2) for a weighted bevel."""
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.edges.ensure_lookup_table()
    lay = bm.edges.layers.float.get('bevel_weight_edge') or bm.edges.layers.float.new('bevel_weight_edge')
    lim = math.radians(ang)
    for e in bm.edges:
        lf = e.link_faces
        e[lay] = 1.0 if (len(lf) == 2 and e.calc_face_angle(0.0) >= lim and lf[0].calc_area() >= amin and lf[1].calc_area() >= amin) else 0.0
    bm.to_mesh(me); bm.free(); me.update()


def add_bevel(o, width=0.05, weighted=True, ang=40.0):
    """Look rule 5: a one-segment bevel so the cel light catches the edges (weighted on the many houses, by angle on the few landmarks)."""
    md = o.modifiers.new('bevel', 'BEVEL'); md.width = width; md.segments = 1; md.use_clamp_overlap = True; md.harden_normals = False
    if weighted: md.limit_method = 'WEIGHT'
    else: md.limit_method = 'ANGLE'; md.angle_limit = math.radians(ang)
    return md


def build_houses(ctx):
    R = ctx.R; M = ctx.M
    mats = [M[k] for k in HMATS]
    ctx.hmesh = {}
    for vi, V in enumerate(VARIANTS):
        for s in (0, 1):
            me, meta = house_mesh(V, 1000 + vi * 10 + s)
            for m in mats: me.materials.append(m)
            bevel_prep(me, 0.6)
            ctx.hmesh[(vi, s)] = (me, meta)
    ctx.house_objs = []; ctx.found_objs = []
    for i, h in enumerate(ctx.houses):
        V = VARIANTS[h['v']]; me, meta = ctx.hmesh[(h['v'], R.randrange(2))]
        o = mkobj(ctx, 'CITY_house_%03d' % i, me, (), 'house', loc=(h['c'][0], h['c'][1], h['floor']), rot=(0.0, 0.0, h['yaw']), props=house_props(R, V))
        h['obj'] = o; h['meta'] = meta; add_bevel(o, 0.05)
        ctx.house_objs.append(o)
        hx, hy = V['w'] / 2, V['d'] / 2
        rects = [(-hx, hx, -hy, hy)]
        if V.get('wing'): rects.append((hx - 0.12, hx + V['wing'][0], -hy, -hy + V['wing'][1]))
        f = plinth(ctx, o, rects, h['floor'], 'CITY_found_%03d' % i)
        if f is not None: bevel_prep(f.data, 0.2); add_bevel(f, 0.04); ctx.found_objs.append(f)


# ------------------------------------------------------------------------------------------------------------------ the campanile and its bell
def build_campanile(ctx):
    M = ctx.M; mb = MB()
    b = 3.5
    box(mb, (0.0, 0.0, 0.5), (b + 0.35, b + 0.35, 0.8), HM['stone'])
    S = 9; z0 = 1.3
    i0 = mb.n()
    D = {}
    for wname in ('front', 'right', 'back', 'left'):
        rows = [['blank'] * 3 for _ in range(S)]
        for k in (2, 4, 6, 8): rows[k][1] = 'win_small'
        D[wname] = rows
    D['right'][0][1] = 'door_arch'; D['front'][0][1] = 'blank_plant'
    walls_box(mb, -b, b, -b, b, S, D, 0.12)
    mb.xform(i0, Matrix.Translation((0.0, 0.0, z0)))
    zs = z0 + S * STOREY
    for zz in (z0 + 9.0, z0 + 18.0):
        ring_rect(mb, (0, 0), (b + 0.12, b + 0.12), (b - 0.1, b - 0.1), zz - 0.12, zz + 0.12, HM['trim'])
    for k in range(int((zs - z0) / 0.6)):
        zz = z0 + 0.3 + k * 0.6; lng = k % 2 == 0
        for sx in (-1, 1):
            for sy in (-1, 1):
                ax_, ay_ = (0.55, 0.3) if lng else (0.3, 0.55)
                box(mb, (sx * (b - ax_ + 0.06), sy * (b - ay_ + 0.06), zz), (ax_, ay_, 0.26), HM['stone'])
    # clock stage
    ring_rect(mb, (0, 0), (b + 0.2, b + 0.2), (b - 0.1, b - 0.1), zs - 0.05, zs + 0.3, HM['trim'])
    for p0, p1 in (((-b, -b), (b, -b)), ((b, -b), (b, b)), ((b, b), (-b, b)), ((-b, b), (-b, -b))):
        wquad(mb, p0, p1, 0.0, 2 * b, zs + 0.3, zs + 4.6, WUV)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(mb, (sx * (b - 0.2), sy * (b - 0.2), zs + 2.45), (0.3, 0.3, 2.15), HM['stone'])
    zc = zs + 2.45
    for (nx, ny) in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        cen = Vector((nx * (b + 0.02), ny * (b + 0.02), zc)); n_ = Vector((nx, ny, 0.0)); t_ = Vector((-ny, nx, 0.0)); u_ = Vector((0.0, 0.0, 1.0))
        ring = []; rr = 1.55; nseg = 32
        for k in range(nseg):
            a = math.tau * k / nseg; ring.append(cen + n_ * 0.1 + (t_ * math.cos(a) + u_ * math.sin(a)) * rr)
        cv = mb.v(cen + n_ * 0.1)
        for k in range(nseg):
            k2 = (k + 1) % nseg; a = math.tau * k / nseg; a2 = math.tau * k2 / nseg
            mb.fh([cv, mb.v(ring[k]), mb.v(ring[k2])], tuple(n_), HM['clock'], uv=[(0.5, 0.5), (0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)), (0.5 + 0.5 * math.cos(a2), 0.5 + 0.5 * math.sin(a2))])
            mb.fh([mb.v(ring[k] - n_ * 0.12), mb.v(ring[k2] - n_ * 0.12), mb.v(ring[k2]), mb.v(ring[k])], tuple((ring[k] + ring[k2]) / 2 - cen - n_ * 0.1), HM['trim'])
        tube(mb, [cen + n_ * 0.12 + (t_ * math.cos(math.tau * k / 40) + u_ * math.sin(math.tau * k / 40)) * 1.66 for k in range(41)], [0.11] * 41, 6, HM['trim'], True, False, False)
    zb = zs + 4.6
    ring_rect(mb, (0, 0), (b + 0.3, b + 0.3), (b - 0.1, b - 0.1), zb, zb + 0.4, HM['trim'])
    # belfry: four arched walls, floor, bell frame
    zf = zb + 0.4; H = 6.5; T = 0.7
    for (tx, ty, yaw, W) in ((0.0, -b + T / 2, 0.0, 2 * b), (b - T / 2, 0.0, math.pi / 2, 2 * b - 2 * T + 0.04), (0.0, b - T / 2, math.pi, 2 * b), (-b + T / 2, 0.0, -math.pi / 2, 2 * b - 2 * T + 0.04)):
        arch_plate(mb, W, H, T, 2.9, 0.95, 4.5, Matrix.Translation((tx, ty, zf)) @ Matrix.Rotation(yaw, 4, 'Z'), HM['trim'], 14)
    box(mb, (0.0, 0.0, zf + 0.85), (b - T + 0.02, b - T + 0.02, 0.1), HM['wood'])
    zp = zf + 4.55
    for sy in (-1.45, 1.45):
        box(mb, (0.0, sy, zp + 0.42), (b - T + 0.02, 0.16, 0.2), HM['wood'])
        for sx in (-2.4, 2.4):
            box(mb, (sx, sy, (zf + 0.93 + zp + 0.24) / 2), (0.14, 0.14, (zp + 0.24 - zf - 0.93) / 2), HM['wood'])
        box(mb, (0.0, sy, zp + 0.1), (0.2, 0.17, 0.13), HM['iron'])
    zt = zf + H
    ring_rect(mb, (0, 0), (b + 0.32, b + 0.32), (b - 0.2, b - 0.2), zt, zt + 0.42, HM['trim'])
    ring_rect(mb, (0, 0), (b + 0.05, b + 0.05), (b - 0.25, b - 0.25), zt + 0.4, zt + 1.15, HM['trim'])
    for sx in (-1, 1):
        for sy in (-1, 1):
            lathe(mb, [(0.3, zt + 1.13), (0.3, zt + 1.4), (0.18, zt + 1.5), (0.0, zt + 2.3)], 4, HM['trim'], (sx * (b - 0.1), sy * (b - 0.1), 0.0), False, a0=math.pi / 4, caps=True)
    box(mb, (0.0, 0.0, zt + 0.47), (b - 0.22, b - 0.22, 0.05), HM['terrace'])
    lathe(mb, [(2.7, zt + 0.45), (2.7, zt + 2.2), (2.95, zt + 2.2), (2.95, zt + 2.45), (2.6, zt + 2.45)], 8, HM['trim'], (0, 0, 0), False, a0=math.pi / 8, caps=False)
    prof = [(2.6, zt + 2.45)] + [(2.6 * math.cos(a), zt + 2.45 + 2.9 * math.sin(a)) for a in np.linspace(0.2, math.pi / 2 - 0.25, 6)] + [(0.45, zt + 5.25)]
    lathe(mb, prof, 24, HM['dome'], (0, 0, 0), True, caps=False)
    lathe(mb, [(0.45, zt + 5.25), (0.5, zt + 5.3), (0.5, zt + 6.1), (0.65, zt + 6.2), (0.3, zt + 6.55), (0.0, zt + 6.75)], 12, HM['trim'], (0, 0, 0), True, caps=False)
    sphere(mb, (0.0, 0.0, zt + 6.95), 0.25, 10, 6, HM['iron'])
    cyl(mb, (0.0, 0.0, zt + 6.7), (0.0, 0.0, zt + 7.25), 0.05, 0.04, 6, HM['iron'])
    mats = [M[k] for k in HMATS] + [M['clock']]
    o = mkobj(ctx, 'CITY_campanile', mb.mesh('CITY_campanile'), mats, 'special', loc=(ctx.camp[0], ctx.camp[1], ctx.zplaza - 0.02),
              props={'wallC': lin('#efe0bf'), 'shutC': lin('#2a8f8a'), 'roofC': lin('#2a8f8a'), 'awnC': lin('#d23a2e'), 'leafC': lin('#5f9e3c'), 'fruit': 0.0, 'lit': 0.0})
    ctx.camp_top = zt + 7.25; ctx.camp_pivot = zp; ctx.camp_obj = o
    # ---- the bell (origin on its axle, swings about local Y) and the clapper (origin inside the crown)
    bb = MB()
    box(bb, (0.0, 0.0, 0.0), (0.22, 0.95, 0.24), 1)
    cyl(bb, (0.0, -1.42, 0.0), (0.0, 1.42, 0.0), 0.075, 0.075, 10, 2)
    BS = 1.2
    outer = [(0.0, -0.18), (0.42, -0.2), (0.52, -0.35), (0.58, -0.7), (0.68, -1.15), (0.86, -1.55), (0.97, -1.78), (0.97, -1.86)]
    inner = [(0.86, -1.86), (0.84, -1.74), (0.72, -1.5), (0.55, -1.1), (0.46, -0.7), (0.4, -0.42), (0.0, -0.36)]
    outer = [(r * BS, z * BS) for r, z in outer]; inner = [(r * BS, z * BS) for r, z in inner]
    lathe(bb, [inner[-1]] + list(reversed(inner[:-1])) + list(reversed(outer)), 28, 0, (0, 0, 0), True, caps=False)
    lathe(bb, [(0.9 * BS, -1.4 * BS), (1.0 * BS, -1.5 * BS), (1.0 * BS, -1.6 * BS), (0.92 * BS, -1.63 * BS)], 28, 0, (0, 0, 0), True, caps=False)
    bell = mkobj(ctx, 'CITY_bell', bb.mesh('CITY_bell'), [M['bronze'], M['wood'], M['iron']], 'bell', parent=o, loc=(0.0, 0.0, zp))
    cb = MB()
    cyl(cb, (0.0, 0.0, 0.0), (0.0, 0.0, -1.44), 0.04, 0.04, 6, 0)
    sphere(cb, (0.0, 0.0, -1.58), 0.16, 10, 6, 0)
    clap = mkobj(ctx, 'CITY_clapper', cb.mesh('CITY_clapper'), [M['iron']], 'bell', parent=bell, loc=(0.0, 0.0, -0.48))
    bell['axis'] = 'Y'; clap['axis'] = 'Y'
    return o, bell, clap


# ------------------------------------------------------------------------------------------------------------------ the church
def build_church(ctx):
    M = ctx.M; mb = MB()
    hx, hy, Hw = 8.5, 5.5, 10.0; c = 0.12; up = 0.48
    yaw = math.atan2(ctx.church_dir[1], ctx.church_dir[0])        # local +x away from the plaza, the facade at x = -hx
    lines = {'front': ((-hx + c, -hy), (hx - c, -hy)), 'right': ((hx, -hy + c), (hx, hy - c)), 'back': ((hx - c, hy), (-hx + c, hy)), 'left': ((-hx, hy - c), (-hx, -hy + c))}
    for wname in ('front', 'back'):                                # the long walls with tall arched windows
        p0, p1 = lines[wname]; L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]); nb = 6; bw = L / nb
        for j in range(nb):
            wquad(mb, p0, p1, j * bw, (j + 1) * bw, 0.0, 7.5, WUV if j in (0, nb - 1) else tile_uv('win_arch'))
        wquad(mb, p0, p1, 0.0, L, 7.5, Hw, WUV)
    p0, p1 = lines['left']; L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]); m_ = L / 2  # the facade toward the plaza
    for (a0, a1, z0, z1) in ((0.0, m_ - 1.92, 0.0, 4.8), (m_ + 1.92, L, 0.0, 4.8), (0.0, L, 4.8, 6.0), (0.0, m_ - 1.6, 6.0, 9.2), (m_ + 1.6, L, 6.0, 9.2), (0.0, L, 9.2, Hw)):
        wquad(mb, p0, p1, a0, a1, z0, z1, WUV)
    wquad(mb, p0, p1, m_ - 1.92, m_ + 1.92, 0.0, 4.8, [tile_pt('door_double', 0.0, 0.0), tile_pt('door_double', 2.4, 0.0), tile_pt('door_double', 2.4, 3.0), tile_pt('door_double', 0.0, 3.0)])
    zr = 7.6
    wpoly(mb, p0, p1, [(m_ - 1.6, 6.0), (m_ + 1.6, 6.0), (m_ + 1.6, 9.2), (m_ - 1.6, 9.2)], lambda a, z: tile_pt('attic', (a - m_) / 4.0 + 1.2, (z - zr) / 4.0 + 0.85))
    p0, p1 = lines['right']; wquad(mb, p0, p1, 0.0, math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 0.0, Hw, WUV)
    for p0, p1 in (((hx - c, -hy), (hx, -hy + c)), ((hx, hy - c), (hx - c, hy)), ((-hx + c, hy), (-hx, hy - c)), ((-hx, -hy + c), (-hx + c, -hy))):
        wquad(mb, p0, p1, 0.0, math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 0.0, Hw, WUV)
    ring_rect(mb, (0.0, 0.0), (hx + 0.2, hy + 0.2), (hx - 0.1, hy - 0.1), Hw - 0.3, Hw + 0.05, HM['trim'])
    ring_rect(mb, (0.0, 0.0), (hx + 0.1, hy + 0.1), (hx - 0.1, hy - 0.1), 4.7, 4.9, HM['trim'])
    zt = roof_gable(mb, hx + 0.32, hy + 0.45, Hw + 0.05, 25.0)
    gable_walls(mb, hx, hy, Hw, Hw + 0.05, hy + 0.45, 25.0, c, oculus=False)
    for sgn in (-1.0, 1.0):                                         # raking cornice of the pediment
        beam(mb, (-hx - 0.36, sgn * (hy + 0.5), Hw + 0.02), (-hx - 0.36, 0.0, zt + 0.02), 0.3, 0.22, HM['trim'])
    for sy in (-1, 1):                                              # pilasters and buttresses
        box(mb, (-hx - 0.12, sy * (hy - 0.32), Hw / 2 - 0.1), (0.16, 0.38, Hw / 2 + 0.1), HM['trim'])
        for x in (-5.59, -2.8, 0.0, 2.79, 5.59):
            box(mb, (x, sy * (hy + 0.4), 3.2), (0.38, 0.42, 3.4), HM['trim'])
            box(mb, (x, sy * (hy + 0.42), 6.68), (0.44, 0.47, 0.13), HM['stone'])
    # the apse with a half dome
    n = 12; ax0 = hx - 0.3
    pts = [(ax0 + 4.0 * math.cos(a), 4.0 * math.sin(a)) for a in np.linspace(-math.pi / 2, math.pi / 2, n + 1)]
    for k in range(n):
        a, b_ = pts[k], pts[k + 1]
        wquad(mb, a, b_, 0.0, math.hypot(b_[0] - a[0], b_[1] - a[1]), 0.0, 7.5, WUV if k % 3 else tile_uv('win_small', 0.7, 1.7))
    prof = [(4.3, 7.5)] + [(4.3 * math.cos(a), 7.5 + 3.4 * math.sin(a)) for a in np.linspace(0.2, math.pi / 2 - 0.2, 5)]
    angs = np.linspace(-math.pi / 2, math.pi / 2, n + 1)
    rings = [[mb.v((ax0 + r * math.cos(a), r * math.sin(a), z)) for a in angs] for (r, z) in prof]
    apex = mb.v((ax0, 0.0, 10.9))
    for i in range(len(prof) - 1):
        for k in range(n):
            mb.f([rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]], HM['roof'], [(k * 0.9, i * 0.5), ((k + 1) * 0.9, i * 0.5), ((k + 1) * 0.9, (i + 1) * 0.5), (k * 0.9, (i + 1) * 0.5)])
    for k in range(n):
        mb.f([rings[-1][k], rings[-1][k + 1], apex], HM['roof'], [(k * 0.9, 2.5), ((k + 1) * 0.9, 2.5), ((k + 0.5) * 0.9, 3.0)])
    for k in range(n):                                              # the eave underside of the half dome
        mb.f([mb.v((ax0 + 4.3 * math.cos(angs[k]), 4.3 * math.sin(angs[k]), 7.5)), mb.v((ax0 + 3.9 * math.cos(angs[k]), 3.9 * math.sin(angs[k]), 7.5)),
              mb.v((ax0 + 3.9 * math.cos(angs[k + 1]), 3.9 * math.sin(angs[k + 1]), 7.5)), mb.v((ax0 + 4.3 * math.cos(angs[k + 1]), 4.3 * math.sin(angs[k + 1]), 7.5))], HM['trim'])
    # steps down to the plaza and an apron reaching into it
    for k, (xa, wy) in enumerate(((0.8, 3.0), (1.2, 3.4), (1.6, 3.8))):
        box(mb, (-hx - xa / 2 + 0.01, 0.0, -(k * 0.16) / 2 - 1.0), (xa / 2 + 0.01, wy, 1.0 - k * 0.08), HM['stone'])
    box(mb, (-hx - 3.3, 0.0, -up - 1.48), (3.3, 5.2, 1.5), HM['stone'])
    mats = [M[k] for k in HMATS]
    o = mkobj(ctx, 'CITY_church', mb.mesh('CITY_church'), mats, 'special', loc=(ctx.church[0], ctx.church[1], ctx.zplaza + up), rot=(0.0, 0.0, yaw),
              props={'wallC': lin('#f6f0e2'), 'shutC': lin('#7a5a3a'), 'roofC': lin('#c8553d'), 'awnC': lin('#d23a2e'), 'leafC': lin('#5f9e3c'), 'fruit': 0.0, 'lit': 0.0})
    plinth(ctx, o, [(-hx, hx, -hy, hy), (hx - 0.3, hx + 3.9, -3.9, 3.9)], ctx.zplaza + up, 'CITY_church_found', top=-0.02, margin=0.3, extra=0.5)
    ctx.church_top = (-hx - 0.3, 0.0, zt + 0.2); ctx.church_obj = o
    return o


# ------------------------------------------------------------------------------------------------------------------ the water tower
def build_watertower(ctx):
    M = ctx.M; mb = MB()
    cx, cy = float(ctx.wt[0]), float(ctx.wt[1])
    g = min([gz(ctx, cx + 5.4 * math.cos(a), cy + 5.4 * math.sin(a)) for a in np.linspace(0, math.tau, 13)[:-1]] + [gz(ctx, cx, cy)])
    legs = []
    for k in range(6):
        a = math.tau * k / 6 + 0.26
        p0 = (5.4 * math.cos(a), 5.4 * math.sin(a), -0.6); p1 = (4.4 * math.cos(a), 4.4 * math.sin(a), 22.0)
        legs.append((p0, p1)); beam(mb, p0, p1, 0.4, 0.4, 0)
        box(mb, (p0[0], p0[1], -0.15), (0.55, 0.55, 0.6), 2)
    def lp(k, z):
        p0, p1 = legs[k % 6]; t = (z + 0.6) / 22.6
        return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, z)
    for z in (7.4, 14.8, 21.7):
        for k in range(6): beam(mb, lp(k, z), lp(k + 1, z), 0.22, 0.22, 0)
    for (za, zb_) in ((0.6, 7.4), (7.4, 14.8), (14.8, 21.7)):
        for k in range(6):
            beam(mb, lp(k, za), lp(k + 1, zb_), 0.1, 0.1, 0); beam(mb, lp(k + 1, za), lp(k, zb_), 0.1, 0.1, 0)
    cyl(mb, (0.0, 0.0, -0.4), (0.0, 0.0, 22.5), 0.5, 0.5, 10, 0)
    # deck and its railing
    lathe(mb, [(5.3, 22.25), (6.6, 22.25), (6.6, 22.45), (5.3, 22.45)], 36, 4, (0, 0, 0), False, caps=False)
    for k in range(36):
        a = math.tau * k / 36; box(mb, (6.45 * math.cos(a), 6.45 * math.sin(a), 22.94), (0.03, 0.03, 0.51), 0)
    tube(mb, [(6.45 * math.cos(a), 6.45 * math.sin(a), 23.45) for a in np.linspace(0, math.tau, 37)], [0.045] * 37, 5, 0, True, False, False)
    tube(mb, [(6.45 * math.cos(a), 6.45 * math.sin(a), 22.95) for a in np.linspace(0, math.tau, 37)], [0.03] * 37, 5, 0, True, False, False)
    # ladder up the inside of one leg
    p0, p1 = legs[0]; d = Vector(p1) - Vector(p0); sd = Vector((-p0[1], p0[0], 0.0)).normalized()
    rin0 = Vector((p0[0], p0[1], 0.0)).normalized() * 0.45; rin1 = Vector((p1[0], p1[1], 0.0)).normalized() * 0.45
    for s_ in (-0.3, 0.3):
        beam(mb, Vector(p0) + sd * s_ + Vector((0, 0, 0.6)) - rin0, Vector(p1) + sd * s_ - rin1 + Vector((0, 0, 0.2)), 0.05, 0.05, 0)
    for k in range(1, 44):
        t = k / 44; q = Vector(p0) + d * t - (rin0 * (1 - t) + rin1 * t)
        beam(mb, q - sd * 0.3, q + sd * 0.3, 0.035, 0.035, 0)
    # tank with the town's name, hoops and a conical roof
    n = 48; zb, zt = 22.43, 30.2; zc = 26.3; hh = 2.12
    for (za, zz, vmode) in ((zb, zc - hh, 0), (zc - hh, zc + hh, 1), (zc + hh, zt, 0)):
        for k in range(n):
            a0 = math.tau * k / n; a1 = math.tau * (k + 1) / n
            q = [(5.4 * math.cos(a0), 5.4 * math.sin(a0), za), (5.4 * math.cos(a1), 5.4 * math.sin(a1), za), (5.4 * math.cos(a1), 5.4 * math.sin(a1), zz), (5.4 * math.cos(a0), 5.4 * math.sin(a0), zz)]
            if vmode: uv = [(k / n, (za - zc + hh) / (2 * hh)), ((k + 1) / n, (za - zc + hh) / (2 * hh)), ((k + 1) / n, (zz - zc + hh) / (2 * hh)), (k / n, (zz - zc + hh) / (2 * hh))]
            else: uv = [(k / n, 0.02)] * 4
            mb.fh([mb.v(p) for p in q], (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0.0), 1, uv)
    for z in (zb + 0.25, zc - hh - 0.3, zc + hh + 0.3, zt - 0.25):
        lathe(mb, [(5.38, z - 0.08), (5.48, z - 0.08), (5.48, z + 0.08), (5.38, z + 0.08)], n, 0, (0, 0, 0), False, caps=False)
    lathe(mb, [(0.0, zb), (5.4, zb)], n, 0, (0, 0, 0), False, caps=False)
    lathe(mb, [(5.75, zt), (5.75, zt + 0.15), (0.6, zt + 2.6), (0.0, zt + 2.75)], n, 3, (0, 0, 0), True, caps=True)
    sphere(mb, (0.0, 0.0, zt + 2.9), 0.25, 10, 6, 0)
    # a hatch and a little vent on the roof
    box(mb, (2.2, 0.0, zt + 1.55), (0.45, 0.4, 0.25), 2)
    cyl(mb, (-2.0, 1.0, zt + 1.2), (-2.0, 1.0, zt + 2.1), 0.14, 0.14, 8, 0)
    mats = [M['iron'], M['tank'], M['stone'], M['dome'], M['wood']]
    o = mkobj(ctx, 'CITY_watertower', mb.mesh('CITY_watertower'), mats, 'special', loc=(cx, cy, g), props={'roofC': lin('#2a8f8a')})
    ctx.wt_top = (cx, cy, g + zt + 3.15); ctx.wt_obj = o
    return o


# ------------------------------------------------------------------------------------------------------------------ windmills
def sails_mesh():
    """Four lattice sails round a hub, in the local XZ plane; the axle is local +Y (pointing out of the mill)."""
    mb = MB()
    cyl(mb, (0.0, -0.3, 0.0), (0.0, 0.62, 0.0), 0.55, 0.5, 12, 0)
    sphere(mb, (0.0, 0.66, 0.0), 0.32, 10, 6, 0)
    for k in range(4):
        ph = math.pi / 4 + k * math.pi / 2; a = Vector((math.cos(ph), 0.0, math.sin(ph))); o_ = Vector((-math.sin(ph), 0.0, math.cos(ph)))
        y0 = Vector((0.0, 0.22, 0.0))
        beam(mb, y0 + a * 0.3, y0 + a * 9.7, 0.26, 0.22, 0, up=(0.0, 1.0, 0.0))
        for off in (0.28, 1.75):
            beam(mb, y0 + a * 1.5 + o_ * off, y0 + a * 9.5 + o_ * off, 0.08, 0.08, 0, up=(0.0, 1.0, 0.0))
        for i in range(15):
            r = 1.5 + i * (8.0 / 14)
            beam(mb, y0 + a * r + o_ * 0.05, y0 + a * r + o_ * 1.8, 0.06, 0.06, 0, up=(0.0, 1.0, 0.0))
        dy = Vector((0.0, 0.07, 0.0))
        if k % 2 == 0:
            q = [y0 + a * 1.9 + o_ * 0.32 + dy, y0 + a * 9.1 + o_ * 0.32 + dy, y0 + a * 9.1 + o_ * 1.7 + dy, y0 + a * 1.9 + o_ * 1.7 + dy]
            t_ = [mb.v(p) for p in q]; b_ = [mb.v(p + Vector((0, 0.025, 0))) for p in q]
            mb.fh(t_, (0.0, -1.0, 0.0), 1); mb.fh(b_, (0.0, 1.0, 0.0), 1)
            for i in range(4):
                j = (i + 1) % 4; mb.fh([t_[i], t_[j], b_[j], b_[i]], tuple((q[i] + q[j]) / 2 - (q[0] + q[2]) / 2), 1)
        else:
            cyl(mb, y0 + a * 1.9 + o_ * 1.62 + dy, y0 + a * 9.0 + o_ * 1.62 + dy, 0.13, 0.11, 8, 1)
    return mb.mesh('CITY_sails')


def build_mills(ctx):
    M = ctx.M; R = random.Random(51)
    smesh = sails_mesh(); smesh.materials.append(M['wood']); smesh.materials.append(M['canvas'])
    mills, hubs, sails = [], [], []
    ctx.mill_info = []
    H = 12.0
    rz = lambda z: 3.6 - 0.6 * z / H
    for i, ml in enumerate(ctx.mills):
        mb = MB(); cx, cy = float(ml['c'][0]), float(ml['c'][1]); f = ml['face']
        g = min(gz(ctx, cx + 3.95 * math.cos(a), cy + 3.95 * math.sin(a)) for a in np.linspace(0, math.tau, 13)[:-1])
        gc = gz(ctx, cx, cy); z0 = gc + 0.45                         # object origin: top of the plinth
        lathe(mb, [(3.95, g - z0 - 0.6), (3.95, 0.0), (3.4, 0.0)], 8, HM['stone'], (0, 0, 0), False, a0=math.pi / 8 + f, caps=False)
        for k in range(8):                                              # octagonal tapered tower, 4 storeys of windows
            a0 = f + math.pi / 8 + math.tau * k / 8; a1 = a0 + math.tau / 8
            for s in range(4):
                za, zb = s * 3.0, (s + 1) * 3.0
                q = [(rz(za) * math.cos(a0), rz(za) * math.sin(a0), za), (rz(za) * math.cos(a1), rz(za) * math.sin(a1), za),
                     (rz(zb) * math.cos(a1), rz(zb) * math.sin(a1), zb), (rz(zb) * math.cos(a0), rz(zb) * math.sin(a0), zb)]
                if s == 0 and k == 7: dname = 'door_arch'
                elif (k + s) % 3 == 0: dname = 'win_small'
                elif s == 0 and k == 3: dname = 'gwin_grille'
                else: dname = 'blank'
                if s == 0 and dname != 'door_arch':                    # rubble-stone ground storey, UV in metres around the tower
                    wa_, wb_ = 2.0 * rz(za) * math.sin(math.pi / 8), 2.0 * rz(zb) * math.sin(math.pi / 8)
                    uc = (k + 0.5) * 2.0 * rz((za + zb) / 2) * math.sin(math.pi / 8)
                    mb.fh([mb.v(p) for p in q], (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0.0), 12,
                          [(uc - wa_ / 2, za), (uc + wa_ / 2, za), (uc + wb_ / 2, zb), (uc - wb_ / 2, zb)])
                else:
                    mb.fh([mb.v(p) for p in q], (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0.0), HM['wall'],
                          tile_uv(dname, 0.05, 1.8) if dname == 'blank' else tile_uv(dname))
        lathe(mb, [(2.6, H - 0.25), (3.32, H - 0.25), (3.32, H + 0.3)], 16, HM['trim'], (0, 0, 0), False, caps=False)
        lathe(mb, [(3.35, H + 0.25), (3.4, H + 0.5), (2.6, H + 2.2), (1.1, H + 3.6), (0.0, H + 4.15)], 16, HM['roof'], (0, 0, 0), True, caps=True, uvk=(10.0, 0.5))
        ax = Vector((math.cos(f), math.sin(f), math.tan(math.radians(5.0)))).normalized()
        hub = Vector((0.0, 0.0, H + 1.7)) + ax * 5.3
        cyl(mb, (0.0, 0.0, H + 1.7), hub - ax * 0.02, 0.3, 0.28, 10, HM['wood'])
        # tail pole from the back of the cap down to a cart wheel on the ground, two struts, a bench by the door
        back = Vector((-math.cos(f), -math.sin(f), 0.0)); side = Vector((-math.sin(f), math.cos(f), 0.0))
        gt = gz(ctx, cx + back.x * 8.4, cy + back.y * 8.4) - z0
        P0 = back * 3.1 + Vector((0, 0, H + 0.9)); P1 = back * 8.4 + Vector((0, 0, gt + 0.85))
        beam(mb, P0, P1, 0.22, 0.22, HM['wood'])
        for s_ in (-1.0, 1.0):
            beam(mb, back * 2.3 + side * (1.5 * s_) + Vector((0, 0, H + 0.6)), P0.lerp(P1, 0.45), 0.12, 0.12, HM['wood'])
        cyl(mb, P1 - side * 0.25, P1 + side * 0.25, 0.09, 0.09, 8, HM['iron'])
        wp = [P1 + (back * math.cos(t) + Vector((0, 0, 1)) * math.sin(t)) * 0.85 for t in np.linspace(0, math.tau, 25)]
        tube(mb, wp, [0.06] * 25, 6, HM['wood'], True, False, False)
        for t in np.linspace(0, math.tau, 7)[:-1]:
            beam(mb, P1, P1 + (back * math.cos(t) + Vector((0, 0, 1)) * math.sin(t)) * 0.82, 0.05, 0.05, HM['wood'], up=tuple(side))
        th_b = f - math.pi / 8; bxy = (math.cos(th_b) * 4.75, math.sin(th_b) * 4.75)
        bench_geo(mb, bxy, th_b + math.pi / 2, gz(ctx, cx + bxy[0], cy + bxy[1]) - z0 - 0.03, HM['wood'], HM['iron'])
        mats = [M[k] for k in HMATS] + [M['stone_m']]
        o = mkobj(ctx, 'CITY_mill_%d' % i, mb.mesh('CITY_mill_%d' % i), mats, 'special', loc=(cx, cy, z0),
                  props={'wallC': lin('#f6f0e2'), 'shutC': lin(R.choice(['#2a8f8a', '#3d6fb6', '#a8473a'])), 'roofC': lin(R.choice(['#b07a48', '#c8553d', '#a86a40'])),
                         'awnC': lin('#d23a2e'), 'leafC': lin('#5f9e3c'), 'fruit': 0.0, 'lit': 0.0})
        mills.append(o)
        hb = bpy.data.objects.new('CITY_hub_%d' % i, None); ctx.coll.objects.link(hb); hb.parent = o
        hb.empty_display_size = 1.0; hb['qa'] = 'empty'
        yv = ax; zv = (Vector((0, 0, 1)) - yv * yv.z).normalized(); xv = yv.cross(zv)
        Mx = Matrix((xv, yv, zv)).transposed().to_4x4(); Mx.translation = hub
        hb.matrix_basis = Mx
        hubs.append(hb)
        sv = mkobj(ctx, 'CITY_sails_%d' % i, smesh, (), 'sails', parent=hb, rot=(0.0, R.uniform(0, math.pi / 2), 0.0))
        sv['axis'] = 'Y'
        sails.append(sv)
        ctx.mill_info.append(dict(c=(cx, cy, z0), hub=(cx + hub.x, cy + hub.y, z0 + hub.z), face=f, cap=(cx, cy, z0 + H + 4.15)))
    return mills, hubs, sails


def yz_prism(mb, pts, x0, x1, m):
    """A polygon in the (y, z) plane, extruded along x from x0 to x1."""
    F = [mb.v((x0, y, z)) for y, z in pts]; B = [mb.v((x1, y, z)) for y, z in pts]
    s = 1.0 if x1 > x0 else -1.0
    mb.fh(F, (-s, 0.0, 0.0), m); mb.fh(B, (s, 0.0, 0.0), m)
    ar = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    o = 1.0 if ar > 0 else -1.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts); dy = pts[j][0] - pts[i][0]; dz = pts[j][1] - pts[i][1]
        mb.fh([F[i], F[j], B[j], B[i]], (0.0, dz * o, -dy * o), m)


# ------------------------------------------------------------------------------------------------------------------ trees
TREE_LEAF = {'cypress': ['#3f6e3a', '#466f3f', '#3b6a45'], 'pine': ['#4f7f3c', '#56813f'], 'olive': ['#8aa36a', '#97ad74', '#7f9a62'],
             'lemon': ['#5d9a3c', '#4f8a3a']}


def tree_mesh(ti, seed):
    """Round Ghibli-style trees: bark slot 0, leaf slot 1. Crowns stay inside the plan radius TREES[ti][1]."""
    R = random.Random(seed); mb = MB()
    name, cr, h, _ = TREES[ti]
    up = Vector((0.0, 0.0, 1.0))
    if name in ('round', 'roundL', 'roundS', 'lemon'):
        lx, ly = R.uniform(-0.15, 0.15), R.uniform(-0.15, 0.15)
        zc = h - cr * 0.85; top = Vector((lx, ly, zc)); r0 = max(0.13, cr * 0.085)
        pts = [Vector((0, 0, -0.5)), Vector((0, 0, 0.2)), Vector((lx * 0.3, ly * 0.3, zc * 0.4)), Vector((lx * 0.7, ly * 0.7, zc * 0.72)), top]
        tube(mb, pts, [r0 * 1.3, r0 * 1.15, r0, r0 * 0.75, r0 * 0.5], 7, 0, True, True, True)
        for k in range(3):
            a = R.uniform(0, math.tau); p0 = pts[2].lerp(pts[3], R.uniform(0.3, 0.9))
            p1 = top + Vector((math.cos(a) * cr * 0.42, math.sin(a) * cr * 0.42, R.uniform(-0.1, 0.35) * cr))
            tube(mb, [p0, p0.lerp(p1, 0.5) + up * 0.2, p1], [r0 * 0.5, r0 * 0.38, r0 * 0.25], 5, 0, True, False, True)
        sphere(mb, top + up * (cr * 0.05), cr * 0.64, 10, 6, 1, True, R=R, jit=0.07)
        n = 7 if name == 'roundL' else 5
        for k in range(n):
            a = math.tau * k / n + R.uniform(-0.3, 0.3); rr = cr * R.uniform(0.36, 0.44); d = cr - rr * 1.14
            sphere(mb, top + Vector((math.cos(a) * d, math.sin(a) * d, R.uniform(-0.3, 0.25) * cr)), rr, 9, 5, 1, True, R=R, jit=0.07)
        sphere(mb, top + Vector((R.uniform(-0.15, 0.15) * cr, R.uniform(-0.15, 0.15) * cr, cr * 0.48)), cr * 0.42, 9, 5, 1, True, R=R, jit=0.07)
    elif name == 'cypress':
        tube(mb, [Vector((0, 0, -0.4)), Vector((0, 0, 1.4))], [0.17, 0.12], 6, 0, True, True, True)
        prof = [(0.0, 0.35), (0.55 * cr, 0.1 * h), (0.86 * cr, 0.3 * h), (0.8 * cr, 0.55 * h), (0.52 * cr, 0.8 * h), (0.16 * cr, 0.95 * h), (0.0, h)]
        lathe(mb, prof, 12, 1, (0, 0, 0), True, R.uniform(0, 1), caps=False)
        for k in range(2):
            a = R.uniform(0, math.tau); s = 0.3 * cr
            pr = [(0.0, 0.2 * h), (0.5 * cr, 0.32 * h), (0.5 * cr, 0.5 * h), (0.25 * cr, 0.66 * h), (0.0, 0.72 * h)]
            lathe(mb, [(r, z + R.uniform(-0.06, 0.06) * h) for r, z in pr], 9, 1, (math.cos(a) * s, math.sin(a) * s, 0.0), True, caps=False)
    elif name == 'pine':
        b = Vector((R.uniform(-0.45, 0.45), R.uniform(-0.45, 0.45), 0.0)); top = b + Vector((0, 0, h - 1.4))
        pts = [Vector((0, 0, -0.5)), Vector((0, 0, 0.3)), b * 0.15 + Vector((0, 0, h * 0.35)), b * 0.7 + Vector((0, 0, h * 0.7)), top]
        tube(mb, pts, [0.36, 0.3, 0.25, 0.2, 0.14], 7, 0, True, True, True)
        cc = top + Vector((0, 0, 0.45))
        sphere(mb, cc, cr * 0.7, 12, 6, 1, True, sq=(1.0, 1.0, 0.34), R=R, jit=0.06)
        for k in range(5):
            a = math.tau * k / 5 + R.uniform(-0.3, 0.3); rr = cr * R.uniform(0.33, 0.4); d = cr * 0.84 - rr * 1.06
            c = cc + Vector((math.cos(a) * d, math.sin(a) * d, R.uniform(-0.35, 0.2)))
            sphere(mb, c, rr, 10, 5, 1, True, sq=(1.0, 1.0, 0.45), R=R, jit=0.06)
            tube(mb, [top.lerp(pts[3], 0.3), c - Vector((0, 0, rr * 0.3))], [0.12, 0.06], 5, 0, True, False, True)
    elif name == 'olive':
        for k in range(R.choice((2, 3))):
            a = R.uniform(0, math.tau); d = cr * 0.4
            tip = Vector((math.cos(a) * d, math.sin(a) * d, h * 0.62))
            pts = [Vector((0, 0, -0.4)), Vector((0, 0, 0.3)), Vector((math.cos(a + 1.0) * 0.25, math.sin(a + 1.0) * 0.25, h * 0.3)), tip * 0.75, tip]
            tube(mb, pts, [0.26, 0.22, 0.17, 0.12, 0.08], 6, 0, True, k == 0, True)
        for k in range(4):
            a = math.tau * k / 4 + R.uniform(-0.4, 0.4); rr = cr * R.uniform(0.42, 0.5); d = cr * 0.92 - rr * 1.05
            sphere(mb, (math.cos(a) * d, math.sin(a) * d, h * 0.66 + R.uniform(-0.3, 0.3)), rr, 9, 5, 1, True, sq=(1.0, 1.0, 0.72), R=R, jit=0.08)
        sphere(mb, (0.0, 0.0, h * 0.8), cr * 0.45, 9, 5, 1, True, sq=(1.0, 1.0, 0.7), R=R, jit=0.08)
    else:                                                               # shrub: puffs on the ground
        for k in range(R.choice((3, 4))):
            a = math.tau * k / 4 + R.uniform(-0.4, 0.4); rr = cr * R.uniform(0.42, 0.52); d = cr * 0.95 - rr * 1.06
            sphere(mb, (math.cos(a) * d, math.sin(a) * d, rr * 0.45), rr, 9, 5, 1, True, R=R, jit=0.08)
        sphere(mb, (0.0, 0.0, cr * 0.55), cr * 0.5, 9, 5, 1, True, R=R, jit=0.08)
    return mb.mesh('CITY_tree_%s_%d' % (name, seed % 10))


def tree_props(R, name):
    leaf = R.choice(TREE_LEAF[name]) if name in TREE_LEAF else wchoice(R, LEAVES)
    fruit = 1.0 if name == 'lemon' else (0.7 if name == 'round' and R.random() < 0.12 else 0.0)
    return {'leafC': lin(leaf), 'fruit': fruit}


def build_trees(ctx):
    M = ctx.M; R = random.Random(61)
    ctx.tmesh = {}
    for ti in range(len(TREES)):
        for s in range(3):
            me = tree_mesh(ti, 2000 + ti * 10 + s); me.materials.append(M['bark']); me.materials.append(M['leaf'])
            ctx.tmesh[(ti, s)] = me
    out = []
    for i, t in enumerate(ctx.trees):
        name = TREES[t['t']][0]
        if name in ('shrub', 'lemon', 'olive') and float(ctx.G.sample(ctx.dcanal, t['c'][0], t['c'][1])) < t['r'] + 0.4: continue
        g = gz(ctx, t['c'][0], t['c'][1])
        o = mkobj(ctx, 'CITY_tree_%03d' % i, ctx.tmesh[(t['t'], R.randrange(3))], (), 'tree', loc=(t['c'][0], t['c'][1], g - 0.12),
                  rot=(0.0, 0.0, R.uniform(0, math.tau)), props=tree_props(R, name))
        o.scale = (t['k'], t['k'], t['k'] * R.uniform(0.92, 1.08))
        out.append(o)
    ctx.tree_objs = out
    return out


def build_ledge_trees(ctx, n=48):
    """Trees and shrubs that grow out of cracks in the cliff, leaning out and up towards the light."""
    R = random.Random(63); out = []; tries = 0
    kinds = (6, 6, 7, 7, 0, 3, 4)                                       # shrub, roundS, round, umbrella pine, olive
    up = Vector((0.0, 0.0, 1.0))
    def clear(q, m):
        thq = math.atan2(q.y, q.x)
        return math.hypot(q.x, q.y) - rock_r_at(ctx, thq, q.z) > m
    while len(out) < n and tries < 2000:
        tries += 1
        th = R.uniform(0, math.tau); z = R.uniform(62.0, ZR - 22.0)
        if min(abs(math.remainder(th - fa, math.tau)) for fa in ctx.fall_th) < 0.16: continue
        c, s_ = math.cos(th), math.sin(th)
        loc, nrm, idx, dist = ctx.rbvh.ray_cast(Vector((c * 300.0, s_ * 300.0, z)), Vector((-c, -s_, 0.0)), 299.5)
        if loc is None: continue
        if any((Vector(o.location) - loc).length < 7.0 for o in out): continue
        rad = Vector((c, s_, 0.0)); side = Vector((-s_, c, 0.0))
        ti = R.choice(kinds); name, cr0, h0, _ = TREES[ti]
        k = R.uniform(0.6, 0.9) if ti in (3, 7, 4) else R.uniform(0.8, 1.15)
        cr = cr0 * k; hh = h0 * k
        base = loc - rad * 0.4
        for lean in (R.uniform(38.0, 52.0), 62.0, 74.0):
            a = (up * math.cos(math.radians(lean)) + rad * math.sin(math.radians(lean))).normalized()
            cc = base + a * max(hh - cr * 0.85, hh * 0.45)
            pts = [base + a * (hh * f) for f in (0.3, 0.55)] + [cc] + [cc + v * (cr * 1.02) for v in (up, -up, rad, -rad, side, -side, (up - rad).normalized())]
            if all(clear(q, 0.12) for q in pts): break
        else:
            continue
        spin = R.uniform(0, math.tau)
        q = up.rotation_difference(a) @ Quaternion(up, spin)
        o = mkobj(ctx, 'CITY_ltree_%02d' % len(out), ctx.tmesh[(ti, R.randrange(3))], (), 'tree', loc=base, props=tree_props(R, name))
        o.rotation_euler = q.to_euler('XYZ')
        o.scale = (k, k, k)
        out.append(o)
    ctx.ltree_objs = out
    return out


# ------------------------------------------------------------------------------------------------------------------ vegetable gardens
def build_gardens(ctx):
    M = ctx.M; out = []
    for gi, gd in enumerate(ctx.gardens):
        R = random.Random(700 + gi); mb = MB()
        c = gd['c']; w, d, yaw = gd['w'], gd['d'], gd['yaw']; cs, sn = math.cos(yaw), math.sin(yaw)
        z0 = gz(ctx, c[0], c[1])
        W = lambda lx, ly: (c[0] + lx * cs - ly * sn, c[1] + lx * sn + ly * cs)
        gl = lambda lx, ly: gz(ctx, *W(lx, ly)) - z0
        nx = max(2, int(math.ceil(w / 0.5))); ny = max(2, int(math.ceil(d / 0.5)))
        xs = np.linspace(-w / 2, w / 2, nx + 1); ys = np.linspace(-d / 2, d / 2, ny + 1)
        Z = [[gl(x, y) + 0.08 for x in xs] for y in ys]
        V_ = [[mb.v((x, y, Z[j][i])) for i, x in enumerate(xs)] for j, y in enumerate(ys)]
        for j in range(ny):
            for i in range(nx):
                mb.f([V_[j][i], V_[j][i + 1], V_[j + 1][i + 1], V_[j + 1][i]], 0)
        bd = [(i, 0) for i in range(nx)] + [(nx, j) for j in range(ny)] + [(i, ny) for i in range(nx, 0, -1)] + [(0, j) for j in range(ny, 0, -1)]
        for k in range(len(bd)):
            (i0, j0), (i1, j1) = bd[k], bd[(k + 1) % len(bd)]
            a = (xs[i0], ys[j0], Z[j0][i0]); b = (xs[i1], ys[j1], Z[j1][i1])
            mb.fh([mb.v(a), mb.v(b), mb.v((b[0], b[1], b[2] - 0.38)), mb.v((a[0], a[1], a[2] - 0.38))], (b[1] - a[1], a[0] - b[0], 0.0), 1)
        kind = gi % 3
        if kind == 0:                                                   # stakes with climbing plants
            for y in np.arange(-d / 2 + 0.7, d / 2 - 0.5, 0.9):
                for x in np.arange(-w / 2 + 0.5, w / 2 - 0.3, 0.7):
                    zb = gl(x, y)
                    box(mb, (x, y, zb + 0.55), (0.02, 0.02, 0.75), 1)
                    sphere(mb, (x + R.uniform(-0.06, 0.06), y + R.uniform(-0.06, 0.06), zb + R.uniform(0.6, 0.9)), R.uniform(0.2, 0.27), 6, 4, 2, True, sq=(1.0, 1.0, 1.5), R=R, jit=0.15)
        elif kind == 1:                                                 # cabbages
            for y in np.arange(-d / 2 + 0.45, d / 2 - 0.3, 0.6):
                for x in np.arange(-w / 2 + 0.4, w / 2 - 0.3, 0.5):
                    sphere(mb, (x + R.uniform(-0.05, 0.05), y, gl(x, y) + 0.2), R.uniform(0.16, 0.22), 6, 3, 2, True, sq=(1.0, 1.0, 0.75), R=R, jit=0.1)
        else:                                                           # lavender / herb rows
            for y in np.arange(-d / 2 + 0.45, d / 2 - 0.3, 0.7):
                xr = np.arange(-w / 2 + 0.35, w / 2 - 0.3, 0.5)
                tube(mb, [(x, y, gl(x, y) + 0.2) for x in xr], [0.2] * len(xr), 6, 2, True, True, True)
        # fence with a gap for the gate
        per = [(-w / 2 - 0.25, -d / 2 - 0.25), (w / 2 + 0.25, -d / 2 - 0.25), (w / 2 + 0.25, d / 2 + 0.25), (-w / 2 - 0.25, d / 2 + 0.25)]
        posts = []
        for k in range(4):
            a, b = per[k], per[(k + 1) % 4]; L = math.hypot(b[0] - a[0], b[1] - a[1]); m = max(1, int(round(L / 1.15)))
            for q in range(m): posts.append((a[0] + (b[0] - a[0]) * q / m, a[1] + (b[1] - a[1]) * q / m))
        gate = R.randrange(len(posts))
        gp = [gl(x, y) for x, y in posts]
        for k, (x, y) in enumerate(posts):
            box(mb, (x, y, gp[k] + 0.35), (0.045, 0.045, 0.65), 1)
            sphere(mb, (x, y, gp[k] + 1.02), 0.06, 6, 3, 1, False)
            j = (k + 1) % len(posts)
            if k == gate: continue
            for hh in (0.45, 0.85):
                beam(mb, (x, y, gp[k] + hh), (posts[j][0], posts[j][1], gp[j] + hh), 0.04, 0.07, 1)
        if w > 6.5 and gi % 2 == 0:                                     # tool shed in a corner, water barrel
            sx, sy = w / 2 - 1.0, d / 2 - 0.8; zb = min(gl(sx + dx, sy + dy) for dx in (-0.8, 0.8) for dy in (-0.6, 0.6)) - 0.1
            yz_prism(mb, [(sy - 0.6, zb), (sy + 0.6, zb), (sy + 0.6, zb + 2.42), (sy - 0.6, zb + 2.14)], sx - 0.8, sx + 0.8, 1)
            slab(mb, [(sx - 0.95, sy - 0.8, zb + 2.15), (sx + 0.95, sy - 0.8, zb + 2.15), (sx + 0.95, sy + 0.8, zb + 2.45), (sx - 0.95, sy + 0.8, zb + 2.45)], 0.08, 3, uv=[(0, 0), (1, 0), (1, 0.8), (0, 0.8)], ms=1)
            box(mb, (sx, sy - 0.61, zb + 0.9), (0.32, 0.02, 0.75), 4)
        bx_, by_ = -w / 2 + 0.5, d / 2 - 0.5
        cyl(mb, (bx_, by_, gl(bx_, by_) - 0.05), (bx_, by_, gl(bx_, by_) + 0.85), 0.32, 0.36, 10, 1, True)
        o = mkobj(ctx, 'CITY_garden_%02d' % gi, mb.mesh('CITY_garden_%02d' % gi), [M['garden'], M['wood'], M['leaf'], M['roof'], M['iron']], 'garden',
                  loc=(c[0], c[1], z0), rot=(0.0, 0.0, yaw),
                  props={'cropC': lin(R.choice(CROPS)), 'leafC': lin('#8f7fc4' if kind == 2 else R.choice(['#5f9e3c', '#7cb35a', '#4f8a3a'])),
                         'fruit': 0.5 if kind == 0 else 0.0, 'roofC': lin(R.choice(['#c8553d', '#8a5a3a', '#2a8f8a']))})
        out.append(o)
    ctx.garden_objs = out
    return out


# ------------------------------------------------------------------------------------------------------------------ laundry: lines across the streets and on the roof terraces, cloth that flaps
def cloth_obj(ctx, name, top_pts, length, R):
    """A piece of laundry hanging from the points top_pts (world, root-local) along a line; flaps with a Wave modifier."""
    p0, p1 = Vector(top_pts[0]), Vector(top_pts[-1]); mid = (p0 + p1) / 2
    dx = p1 - p0; dx.z = 0.0; w = dx.length; ex = dx.normalized(); yaw = math.atan2(ex.y, ex.x)
    nx = max(2, int(round(w / 0.18))); nz = max(2, int(round(length / 0.18)))
    mb = MB(); idx = []
    for j in range(nz + 1):
        row = []
        for i in range(nx + 1):
            t = i / nx; tp = Vector(top_pts[0]).lerp(Vector(top_pts[-1]), t) if len(top_pts) == 2 else _polyline_at(top_pts, t)
            z = tp.z - 0.015 - mid.z - length * j / nz
            row.append(mb.v(((t - 0.5) * w, 0.0, z)))
        idx.append(row)
    for j in range(nz):
        for i in range(nx):
            mb.f([idx[j][i], idx[j + 1][i], idx[j + 1][i + 1], idx[j][i + 1]], 0)
    for t in (0.08, 0.92):
        tp = _polyline_at(top_pts, t) if len(top_pts) > 2 else Vector(top_pts[0]).lerp(Vector(top_pts[-1]), t)
        box(mb, ((t - 0.5) * w, 0.0, tp.z - mid.z - 0.02), (0.012, 0.012, 0.04), 1)
    me = mb.mesh(name)
    cl = R.sample(CLOTH, 2)
    o = mkobj(ctx, name, me, [ctx.M['cloth'], ctx.M['wood']], 'cloth', loc=mid, rot=(0.0, 0.0, yaw),
              props={'clothC': lin(cl[0]), 'clothC2': lin(cl[1]), 'pat': float(R.choice((0, 0, 1, 2)))})
    vg = o.vertex_groups.new(name='flap')
    zs = [me.vertices[k].co.z for k in range(len(me.vertices))]
    ztop = max(zs)
    for k, v in enumerate(me.vertices):
        if k >= (nx + 1) * (nz + 1): vg.add([k], 0.0, 'REPLACE'); continue
        j = k // (nx + 1)
        vg.add([k], (j / nz) ** 1.3, 'REPLACE')
    md = o.modifiers.new('flap', 'WAVE')
    md.use_x = True; md.use_y = False; md.use_normal = True
    md.height = R.uniform(0.045, 0.08); md.width = R.uniform(0.45, 0.7); md.narrowness = 1.2; md.speed = R.uniform(0.12, 0.2)
    md.time_offset = R.uniform(-60, 0); md.use_cyclic = True; md.vertex_group = 'flap'
    md.start_position_x = R.uniform(-1, 1)
    o['flap'] = 1.0
    return o


def _polyline_at(P, t):
    P = [Vector(p) for p in P]; L = [0.0]
    for i in range(1, len(P)): L.append(L[-1] + (P[i] - P[i - 1]).length)
    s = t * L[-1]
    for i in range(1, len(P)):
        if s <= L[i] or i == len(P) - 1:
            u = (s - L[i - 1]) / max(L[i] - L[i - 1], 1e-9); return P[i - 1].lerp(P[i], min(max(u, 0.0), 1.0))


def build_laundry(ctx):
    M = ctx.M; R = random.Random(77); lb = MB(); cloths = []; ctx.lines_info = []
    byst = {}
    for h in ctx.houses:
        if h['street'] is not None: byst.setdefault(h['street'].name, []).append(h)
    def front_hit(h, p, N):
        V = VARIANTS[h['v']]; hx, hy = V['w'] / 2, V['d'] / 2; c = np.array(h['c']); y_ = h['yaw']
        nyw = np.array((-math.sin(y_), math.cos(y_))); nxw = np.array((math.cos(y_), math.sin(y_)))
        den = float(np.dot(N, nyw))
        if abs(den) < 0.5: return None
        t = (-hy - float(np.dot(p - c, nyw))) / den; a = p + N * t
        lx = float(np.dot(a - c, nxw))
        if abs(lx) > hx - 0.5: return None
        return a
    for sname, hs in byst.items():
        A = [h for h in hs if h['side'] == 1]; B = [h for h in hs if h['side'] == -1]
        for h1 in A:
            if R.random() > 0.5: continue
            for h2 in B:
                lo = max(h1['s0'], h2['s0']); hi = min(h1['s1'], h2['s1'])
                if hi - lo < 2.4: continue
                st = h1['street']; sm = R.uniform(lo + 0.8, hi - 0.8)
                p, T, N = st.at(sm); p = np.array(p); N = np.array(N)
                a1 = front_hit(h1, p, N); a2 = front_hit(h2, p, N)
                if a1 is None or a2 is None: break
                zlo = max(h1['floor'], h2['floor']) + 4.4; zhi = min(h1['floor'], h2['floor']) + 5.2
                if zlo > zhi: break
                z = R.uniform(zlo, zhi); P1 = Vector((a1[0], a1[1], z)); P2 = Vector((a2[0], a2[1], z))
                L = (P2 - P1).length
                if L < 4.0 or L > 9.5: break
                dv = (P2 - P1).normalized()
                for P, sg in ((P1, 1.0), (P2, -1.0)):
                    beam(lb, P - dv * sg * 0.08, P + dv * sg * 0.32, 0.04, 0.04, 0)
                    sphere(lb, P + dv * sg * 0.32, 0.035, 6, 3, 0, False)
                Q1 = P1 + dv * 0.32; Q2 = P2 - dv * 0.32; sag = 0.1 + 0.035 * L
                pts = [Q1.lerp(Q2, k / 16) - Vector((0, 0, sag * 4 * (k / 16) * (1 - k / 16))) for k in range(17)]
                tube(lb, pts, [0.011] * 17, 5, 0, True, False, False)
                ctx.lines_info.append((tuple(P1), tuple(P2)))
                # laundry along the middle, at least 1.3 m from both walls
                s = 1.3
                while s < L - 1.3 - 0.4:
                    wv = R.choice((0.45, 0.55, 0.7, 0.85, 1.0)); ln = R.choice((0.5, 0.6, 0.75, 0.9, 1.05))
                    if s + wv > L - 1.3: break
                    t0 = (s - 0.32) / (L - 0.64); t1 = (s + wv - 0.32) / (L - 0.64)
                    tops = [_polyline_at(pts, t0 + (t1 - t0) * q / 4) for q in range(5)]
                    cloths.append(cloth_obj(ctx, 'CITY_cloth_%03d' % len(cloths), [tuple(v) for v in tops], ln, R))
                    s += wv + R.uniform(0.12, 0.35)
                break
    # roof terraces of the flat houses
    for h in ctx.houses:
        meta = h.get('meta')
        if not meta or not meta['lines'] or R.random() > 0.65: continue
        o = h['obj']; Mx = o.matrix_basis
        for (a, b) in meta['lines']:
            A = Mx @ Vector(a); B = Mx @ Vector(b); L = (B - A).length; s = 0.35
            cyl(lb, A, B, 0.009, 0.009, 5, 0, False)
            while s < L - 0.75:
                wv = R.choice((0.4, 0.5, 0.6, 0.75)); ln = R.choice((0.4, 0.5, 0.6))
                if s + wv > L - 0.35: break
                cloths.append(cloth_obj(ctx, 'CITY_cloth_%03d' % len(cloths), [tuple(A.lerp(B, s / L)), tuple(A.lerp(B, (s + wv) / L))], ln, R))
                s += wv + R.uniform(0.15, 0.4)
    mill_yards(ctx, lb, cloths, R)
    lines = mkobj(ctx, 'CITY_lines', lb.mesh('CITY_lines'), [M['iron'], M['wood']], 'line') if lb.F else None
    ctx.cloth_objs = cloths
    return lines, cloths


def mill_yards(ctx, lb, cloths, R):
    """The miller's washing: two T-posts in the yard behind each windmill carrying two lines of laundry, placed where the posts,
    lines and hanging cloth keep 0.55 m from every built thing (the near layer of shot 02: sails, washing, bell tower)."""
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    T0 = Matrix.Translation(-Vector(ORIGIN)); occ = []
    for o in ctx.objs:
        if o.type != 'MESH' or o.get('qa') in ('ground', 'rock', 'fall', 'crystal', 'root', 'cloth', 'line'): continue
        Mw = T0 @ o.matrix_world; bb = [Mw @ Vector(c) for c in o.bound_box]
        occ.append([o, Mw, Vector([min(p[i] for p in bb) for i in range(3)]), Vector([max(p[i] for p in bb) for i in range(3)]), None])
    def near(lo, hi):
        out = []
        for rec in occ:
            if any(rec[2][i] > hi[i] or rec[3][i] < lo[i] for i in range(3)): continue
            if rec[4] is None:
                me = rec[0].data
                rec[4] = BVHTree.FromPolygons([rec[1] @ v.co for v in me.vertices], [tuple(p_.vertices) for p_ in me.polygons])
            out.append(rec[4])
        return out
    for mi in ctx.mill_info:
        cx, cy, z0 = mi['c']; f = mi['face']; placed = False
        rels = [100, 260, 115, 245, 130, 230, 150, 210, 180]          # beside the tower first, clear of the sail disc
        for rel in rels:
            for dist in (7.0, 8.5, 10.0):
                a = f + math.radians(rel); rad = Vector((math.cos(a), math.sin(a), 0.0)); tng = Vector((-rad.y, rad.x, 0.0))
                C0 = Vector((cx, cy, 0.0)) + rad * dist; half = R.uniform(2.6, 3.3)
                A2 = C0 - tng * half; B2 = C0 + tng * half
                zA = gz(ctx, A2.x, A2.y); zB = gz(ctx, B2.x, B2.y)
                if abs(zA - zB) > 0.9: continue
                ztop = max(zA, zB) + 2.45
                if ztop - max(gz(ctx, *A2.lerp(B2, k / 8).xy) for k in range(9)) < 2.2: continue
                pts = []
                for P2, zg in ((A2, zA), (B2, zB)):
                    pts += [Vector((P2.x, P2.y, zg + 0.05 + (ztop - zg) * k / 8)) for k in range(9)]
                    pts += [Vector((P2.x, P2.y, ztop)) + rad * s_ for s_ in (-0.5, 0.5)]
                for s_ in (-0.38, 0.38):
                    for k in range(13):
                        Q = A2.lerp(B2, k / 12) + rad * s_
                        pts += [Vector((Q.x, Q.y, ztop + dz)) for dz in (0.0, -0.5, -1.05)]
                lo = Vector([min(p_[i] for p_ in pts) - 1.0 for i in range(3)]); hi = Vector([max(p_[i] for p_ in pts) + 1.0 for i in range(3)])
                bv = near(lo, hi)
                if any(t_.find_nearest(p_, 0.55)[0] is not None for t_ in bv for p_ in pts): continue
                for P2, zg in ((A2, zA), (B2, zB)):
                    beam(lb, (P2.x, P2.y, zg - 0.35), (P2.x, P2.y, ztop + 0.04), 0.075, 0.075, 1, up=tuple(tng))
                    beam(lb, Vector((P2.x, P2.y, ztop - 0.04)) - rad * 0.5, Vector((P2.x, P2.y, ztop - 0.04)) + rad * 0.5, 0.06, 0.07, 1)
                for s_ in (-0.38, 0.38):
                    Q1 = Vector((A2.x, A2.y, ztop + 0.01)) + rad * s_; Q2 = Vector((B2.x, B2.y, ztop + 0.01)) + rad * s_
                    L = (Q2 - Q1).length; sag = 0.06 + 0.02 * L
                    lp = [Q1.lerp(Q2, k / 16) - Vector((0, 0, sag * 4 * (k / 16) * (1 - k / 16))) for k in range(17)]
                    tube(lb, lp, [0.011] * 17, 5, 0, True, False, False)
                    ctx.lines_info.append((tuple(Q1), tuple(Q2)))
                    s = 0.45
                    while s < L - 0.85:
                        wv = R.choice((0.45, 0.55, 0.7, 0.85)); ln = R.choice((0.5, 0.6, 0.75, 0.9))
                        if s + wv > L - 0.45: break
                        tops = [_polyline_at(lp, (s + wv * q / 4) / L) for q in range(5)]
                        cloths.append(cloth_obj(ctx, 'CITY_cloth_%03d' % len(cloths), [tuple(v) for v in tops], ln, R))
                        s += wv + R.uniform(0.12, 0.3)
                placed = True; break
            if placed: break
        mi['yard'] = placed


# ------------------------------------------------------------------------------------------------------------------ weather vanes, the church cross
def vane_mesh():
    mb = MB()
    cyl(mb, (0, 0, -0.12), (0, 0, 1.7), 0.026, 0.02, 6, 0)
    sphere(mb, (0, 0, 0.95), 0.075, 8, 5, 1)
    sphere(mb, (0, 0, 1.72), 0.045, 6, 4, 1)
    for a in (0.0, math.pi / 2):
        beam(mb, (math.cos(a) * -0.42, math.sin(a) * -0.42, 0.78), (math.cos(a) * 0.42, math.sin(a) * 0.42, 0.78), 0.022, 0.022, 0)
        for s_ in (-1, 1): sphere(mb, (math.cos(a) * 0.44 * s_, math.sin(a) * 0.44 * s_, 0.78), 0.035, 6, 3, 1, False)
    beam(mb, (-0.72, 0, 1.25), (0.72, 0, 1.25), 0.03, 0.03, 0)
    xz_prism(mb, [(0.7, 1.13), (1.0, 1.25), (0.7, 1.37)], -0.012, 0.012, 1)
    xz_prism(mb, [(-0.8, 1.235), (-0.5, 1.235), (-0.6, 1.5), (-0.86, 1.55)], -0.01, 0.01, 1)
    rooster = [(-0.35, 0.05), (-0.2, 0.0), (0.15, 0.0), (0.25, 0.08), (0.3, 0.25), (0.38, 0.3), (0.45, 0.36), (0.37, 0.4), (0.33, 0.47), (0.27, 0.48),
               (0.24, 0.43), (0.19, 0.35), (0.11, 0.29), (-0.05, 0.29), (-0.2, 0.5), (-0.38, 0.56), (-0.36, 0.36), (-0.42, 0.2)]
    xz_prism(mb, [(x, z + 1.26) for x, z in rooster], -0.012, 0.012, 1)
    return mb.mesh('CITY_vane')


def build_vanes(ctx):
    M = ctx.M; R = random.Random(81)
    me = vane_mesh(); me.materials.append(M['iron']); me.materials.append(M['bronze'])
    out = []
    def add(parent, loc, sc):
        o = mkobj(ctx, 'CITY_vane_%02d' % len(out), me, (), 'vane', parent=parent, loc=loc, rot=(0.0, 0.0, R.uniform(0, math.tau)))
        o.scale = (sc, sc, sc); o['axis'] = 'Z'; out.append(o)
    add(ctx.camp_obj, (0.0, 0.0, ctx.camp_top - 0.1), 1.7)
    add(ctx.wt_obj, (0.0, 0.0, ctx.wt_top[2] - ctx.wt_obj.location.z), 1.3)
    for o_, mi in zip(ctx.mill_objs, ctx.mill_info):
        add(o_, (0.0, 0.0, mi['cap'][2] - o_.location.z - 0.05), 1.0)
    cand = [h for h in ctx.houses if h['meta']['vane'] is not None]
    cand.sort(key=lambda h: h['c'][0])
    for h in cand[:6] + R.sample(cand[6:], min(4, max(0, len(cand) - 6))):
        add(h['obj'], h['meta']['vane'], 0.95)
    # a cross on the church gable
    cb = MB()
    box(cb, (0, 0, 0.75), (0.07, 0.07, 0.85), 0); box(cb, (0, 0, 1.05), (0.07, 0.42, 0.07), 0)
    sphere(cb, (0, 0, -0.05), 0.12, 8, 5, 1)
    cr = mkobj(ctx, 'CITY_church_cross', cb.mesh('CITY_church_cross'), [M['iron'], M['bronze']], 'vane', parent=ctx.church_obj, loc=ctx.church_top)
    ctx.vane_objs = out
    return out, cr


# ------------------------------------------------------------------------------------------------------------------ loose roof tiles (for the storm to tear off)
def tile_mesh():
    mb = MB(); n = 6; r0, r1 = 0.105, 0.093; Lh = 0.21
    for (r, sgn) in ((r0, 1.0), (r1, -1.0)):
        ring0 = [mb.v((r * math.cos(math.pi * k / n), -Lh, r * math.sin(math.pi * k / n) - 0.0)) for k in range(n + 1)]
        ring1 = [mb.v((r * math.cos(math.pi * k / n), Lh, r * math.sin(math.pi * k / n))) for k in range(n + 1)]
        for k in range(n):
            mid = Vector((math.cos(math.pi * (k + 0.5) / n), 0.0, math.sin(math.pi * (k + 0.5) / n))) * sgn
            mb.fh([ring0[k], ring0[k + 1], ring1[k + 1], ring1[k]], tuple(mid), 0, uv=[(0.3, 0.3)] * 4)
    for yy, sg in ((-Lh, -1.0), (Lh, 1.0)):
        for k in range(n):
            a0 = math.pi * k / n; a1 = math.pi * (k + 1) / n
            mb.fh([mb.v((r0 * math.cos(a0), yy, r0 * math.sin(a0))), mb.v((r0 * math.cos(a1), yy, r0 * math.sin(a1))),
                   mb.v((r1 * math.cos(a1), yy, r1 * math.sin(a1))), mb.v((r1 * math.cos(a0), yy, r1 * math.sin(a0)))], (0.0, sg, 0.0), 0, uv=[(0.3, 0.3)] * 4)
    for x in (-1, 1):
        mb.fh([mb.v((x * r0, -Lh, 0.0)), mb.v((x * r0, Lh, 0.0)), mb.v((x * r1, Lh, 0.0)), mb.v((x * r1, -Lh, 0.0))], (0.0, 0.0, -1.0), 0, uv=[(0.3, 0.3)] * 4)
    return mb.mesh('CITY_tile')


def build_tiles(ctx, n=30):
    M = ctx.M; R = random.Random(85); me = tile_mesh(); me.materials.append(M['roof'])
    st0 = ctx.streets[0]; ref = np.array(st0.at(70.0)[0])
    cand = [h for h in ctx.houses if h['meta']['roof'] in ('hip', 'gable', 'pyr')]
    cand.sort(key=lambda h: float(np.hypot(*(np.array(h['c']) - ref))))
    bvh = {}; out = []
    for h in cand[:24]:
        o = h['obj']; hm = o.data
        if hm.name not in bvh:
            bvh[hm.name] = BVHTree.FromPolygons([v.co.copy() for v in hm.vertices], [tuple(p.vertices) for p in hm.polygons])
        tb = bvh[hm.name]; V = VARIANTS[h['v']]; hx, hy = V['w'] / 2, V['d'] / 2; top = h['meta']['top']
        placed = 0
        for attempt in range(40):
            if placed >= 2 or len(out) >= n: break
            x, y = R.uniform(-hx + 0.3, hx - 0.3), R.uniform(-hy - 0.2, hy + 0.2)
            loc, nrm, idx, dist = tb.ray_cast(Vector((x, y, top + 3.0)), Vector((0, 0, -1)))
            if loc is None or hm.polygons[idx].material_index != HM['roof'] or not (0.82 < nrm.z < 0.95): continue
            dn = Vector((nrm.x, nrm.y, 0.0)); dn = (dn - nrm * nrm.dot(dn)).normalized()
            side = dn.cross(nrm).normalized()
            okp = True
            for du, dv in ((-0.13, -0.24), (0.13, -0.24), (-0.13, 0.24), (0.13, 0.24)):
                q = loc + side * du + dn * dv
                l2, n2, i2, d2 = tb.ray_cast(q + nrm * 1.0, -nrm)
                if l2 is None or abs((l2 - q).dot(nrm)) > 0.012 or hm.polygons[i2].material_index != HM['roof'] or n2.dot(nrm) < 0.999: okp = False; break
            if not okp: continue
            a = R.uniform(-0.25, 0.25)
            side2 = side * math.cos(a) + dn * math.sin(a); dn2 = nrm.cross(side2)
            Ml = Matrix((side2, dn2, nrm)).transposed().to_4x4(); Ml.translation = loc + nrm * 0.012
            t = mkobj(ctx, 'CITY_tile_%02d' % len(out), me, (), 'tile', props={'roofC': tuple(o['roofC'])})
            t.matrix_basis = o.matrix_basis @ Ml
            out.append(t); placed += 1
    ctx.tile_objs = out
    return out


# ------------------------------------------------------------------------------------------------------------------ waterfalls
def fall_w(f):
    """Half width (across) and half thickness of the falling water at fraction f of the drop: a 2.3 m canal mouth opening
    to a 32 m curtain."""
    return 1.15 + 15.0 * f ** 1.1, 0.35 + 4.0 * f


def build_falls(ctx, drop=300.0):
    M = ctx.M; R = random.Random(87); out = []; ctx.fall_info = []
    for fi, sp in enumerate(ctx.spouts):
        p = sp['p']; d = Vector((float(sp['d'][0]), float(sp['d'][1]), 0.0)).normalized(); side = Vector((-d.y, d.x, 0.0))
        start = Vector((float(p[0]), float(p[1]), float(sp['lev']) - 0.04))
        T = math.sqrt(2 * drop / 9.81); N = 72
        best = None
        for v0 in (3.2, 3.8, 4.6, 5.6, 7.0, 8.5):
            C = []; ok = True
            for k in range(N + 1):
                t = T * (k / N) ** 1.5
                x = v0 * t * (1.0 - 0.025 * t); z = -4.9 * t * t
                C.append((start + d * x + Vector((0, 0, z)), (k / N) ** 1.4))
            for k in range(2, len(C)):
                c, f = C[k]; tg = (C[min(k + 1, len(C) - 1)][0] - C[k - 1][0]).normalized(); ax2 = tg.cross(side).normalized()
                wa, wb = fall_w(f)
                for j in range(10):
                    q = c + side * (wa * math.cos(math.tau * j / 10)) + ax2 * (wb * math.sin(math.tau * j / 10))
                    if q.z < 6.0: continue
                    thq = math.atan2(q.y, q.x)
                    if math.hypot(q.x, q.y) - max(rock_r_at(ctx, thq, q.z), rock_r_at(ctx, thq, q.z + 1.5)) < 0.8: ok = False; break
                if not ok: break
            if ok: best = (v0, C); break
        if best is None: best = (8.5, C)
        v0, C = best
        mb = MB(); n = 16; rings = []; svals = []; sacc = 0.0
        pts = [start - d * 1.2] + [c for c, f in C]; fs = [0.0] + [f for c, f in C]
        for k, c in enumerate(pts):
            if k: sacc += (pts[k] - pts[k - 1]).length
            svals.append(sacc)
        L = sacc
        frames = []
        for k, c in enumerate(pts):
            tg = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
            frames.append(tg.cross(side).normalized())
        def tube_(sc_a, sc_b, k0, m, uofs, sh=0.0):
            rr = []
            for k in range(k0, len(pts)):
                wa, wb = fall_w(fs[k]); ax2 = frames[k]
                rr.append((k, [mb.v(pts[k] + side * (wa * sc_a * math.cos(math.tau * j / n)) + ax2 * (wb * (sh + sc_b * math.sin(math.tau * j / n)))) for j in range(n)]))
            for (ka, ra), (kb, rb) in zip(rr, rr[1:]):
                for j in range(n):
                    j2 = (j + 1) % n
                    mb.f([ra[j], ra[j2], rb[j2], rb[j]], m, [(uofs + j / n, svals[ka]), (uofs + (j + 1) / n, svals[ka]), (uofs + (j + 1) / n, svals[kb]), (uofs + j / n, svals[kb])], True)
            return rr
        rr = tube_(1.0, 1.0, 0, 0, 0.0)
        rings = [r_ for k_, r_ in rr]
        mb.f(list(reversed(rings[0])), 0, [(0.5, 0.0)] * n)
        k_veil = next(k for k in range(len(pts)) if fs[k] >= 0.1)
        veil = tube_(1.45, 1.9, k_veil, 2, 0.37)                       # the torn outer curtain (own streaky alpha)
        k_sh = next(k for k in range(len(pts)) if fs[k] >= 0.25)
        # the dissolve: the path runs on for another 17 % of the fall time (~110 m more drop) for the spray sheath alone, which
        # widens and fades out over it (spray_a, k 0.85 .. fallX); the ribbon and the torn curtain end where they did
        end = pts[-1]
        TX = T * 1.17; NX = 12
        for j in range(1, NX + 1):
            t = T + (TX - T) * j / NX
            pts.append(start + d * (v0 * t * (1.0 - 0.025 * t)) + Vector((0, 0, -4.9 * t * t)))
            fs.append(1.0 + 0.45 * j / NX)
            sacc += (pts[-1] - pts[-2]).length; svals.append(sacc)
        frames = []
        for k, c in enumerate(pts):
            tg = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
            frames.append(tg.cross(side).normalized())
        LX = sacc
        veil += tube_(2.1, 2.6, k_sh, 3, 0.11, sh=0.8)                 # the spray sheath: one soft envelope, no beads
        nv_rib = mb.n()
        # spray: overlapping clusters hugging the lower ribbon, growing as it falls; a mist cloud where it dissolves
        sv_m = []
        for k in range(len(pts)):
            if True: continue                                          # (accent puffs retired: the sheath carries the spray)
            c = pts[k]; wa, wb = fall_w(fs[k]); ax2 = frames[k]
            for q in range(1 + int(fs[k] * 3)):
                off = side * (R.uniform(-0.9, 0.9) * wa) + ax2 * (R.uniform(-1.2, 1.2) * wb) + d * (R.uniform(0.0, 0.5) * wb)
                rr_ = wa * R.uniform(0.42, 0.75) * (0.6 + 0.4 * fs[k])
                nu, nv = (10, 6) if rr_ < 4.0 else (12, 7)
                i0 = mb.n(); sphere(mb, c + off, rr_, nu, nv, 1, True, sq=(1.0, 0.8, 1.7), R=R, jit=0.1); sv_m.append((i0, mb.n(), svals[k]))
        me = mb.mesh('CITY_fall_%d' % fi)
        o = mkobj(ctx, 'CITY_fall_%d' % fi, me, [M['fall'], M['mist'], M['veil'], M['spray']], 'fall',
                  props={'fallL': float(L), 'fallX': float(LX / L) - 0.03})
        # shape keys for wind: bendX sideways, bendY outward (grow with the square of the distance down)
        vs = np.zeros(len(me.vertices))
        for (k, ring) in rr + veil:
            for vi in ring: vs[vi] = svals[k]
        for i0, i1, sv in sv_m: vs[i0:i1] = sv
        o.shape_key_add(name='Basis')
        for nm, vec, amp in (('bendX', side, 14.0), ('bendY', d, 10.0)):
            sk = o.shape_key_add(name=nm, from_mix=False)
            for vi in range(len(me.vertices)):
                f = (vs[vi] / L) ** 2
                sk.data[vi].co = me.vertices[vi].co + vec * (amp * f)
        out.append(o)
        ctx.fall_info.append(dict(start=tuple(start), dir=tuple(d), v0=v0, L=L, end=tuple(end)))
    ctx.fall_objs = out
    return out


# ------------------------------------------------------------------------------------------------------------------ levitation crystals under the rock
def crystal_geo(mb, R, size, n):
    tips = []
    for i in range(n):
        tilt = R.uniform(0.0, 0.62) if i else R.uniform(0.0, 0.15); az = R.uniform(0, math.tau)
        dirn = Vector((math.sin(tilt) * math.cos(az), math.sin(tilt) * math.sin(az), math.cos(tilt)))
        Lc = size * (R.uniform(0.75, 1.0) if i == 0 else R.uniform(0.35, 0.75)); rc = Lc * R.uniform(0.13, 0.19)
        base = Vector((R.uniform(-0.3, 0.3) * size, R.uniform(-0.3, 0.3) * size, 0.0)) if i else Vector((0, 0, 0))
        tm = MB()
        lathe(tm, [(0.0, -0.35 * Lc), (rc * 0.85, -0.05 * Lc), (rc, 0.7 * Lc), (0.0, Lc)], 6, 0, (0, 0, 0), False, R.uniform(0, 1), caps=False)
        x, y, z = frame_of(dirn)
        Mx = Matrix((x, y, z)).transposed().to_4x4(); Mx.translation = base
        mb.merge(tm, Mx)
        tips.append((base, base + dirn * Lc, rc))
    return tips


def build_crystals(ctx, n=46):
    M = ctx.M; R = random.Random(89); out = []; ctx.crystal_info = []
    fall_pts = []
    for o in ctx.fall_objs:
        me = o.data; co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co); fall_pts.append(co.reshape(-1, 3)[::5])
    allf = np.vstack(fall_pts) if fall_pts else np.zeros((0, 3))
    rings = []
    for k in range(8):                                                  # a crown of crystals just above the collar
        rings.append((math.radians(k * 45 + 20) + R.uniform(-0.15, 0.15), R.uniform(17.5, 22.5), R.uniform(5.5, 7.5)))
    for k in range(9):                                                  # the lower cone: big clusters, the levitation engine
        rings.append((math.radians(k * 40 + 5) + R.uniform(-0.2, 0.2), R.uniform(28.0, 52.0), R.uniform(7.5, 10.5)))
    tries = 0
    while len(rings) < n + 40 and tries < 4000:
        tries += 1
        z = 55.0 + 115.0 * R.random() ** 1.3
        rings.append((R.uniform(0, math.tau), z, (4.5 + 4.5 * (1 - (z - 55) / 115)) * R.uniform(0.8, 1.15)))
    for th, z, size in rings:
        if len(out) >= n: break
        p, nr = rock_point(ctx, th, z)
        if any((Vector(ci['p']) - p).length < max(13.0, size * 2.0) for ci in ctx.crystal_info): continue
        ax_ = (nr + Vector((0, 0, -0.75))).normalized()
        x, y, zz = frame_of(ax_)
        Mx = Matrix((x, y, zz)).transposed().to_4x4(); Mx.translation = p - nr * 0.4
        mb = MB(); tips = crystal_geo(mb, R, size, R.randint(4, 7))
        ok = True
        for b0, b1, rc in tips:
            for q in (Mx @ b1, Mx @ b0.lerp(b1, 0.6)):
                if q.z < 14.5 and math.hypot(q.x, q.y) < 10.8: ok = False
                if len(allf) and float(np.min(np.linalg.norm(allf - np.array(tuple(q)), axis=1))) < 6.0 + rc: ok = False
            for q in (Mx @ b1, Mx @ b0.lerp(b1, 0.75)):
                if math.hypot(q.x, q.y) - rock_r_at(ctx, math.atan2(q.y, q.x), q.z) < 0.4: ok = False
        if not ok: continue
        o = mkobj(ctx, 'CITY_crystal_%02d' % len(out), mb.mesh('CITY_crystal_%02d' % len(out)), [M['crystal']], 'crystal', props={'power': 1.0})
        o.matrix_basis = Mx
        out.append(o)
        ctx.crystal_info.append(dict(p=tuple(p), n=tuple(nr), size=size, z=z))
    ctx.crystal_objs = out
    return out


# ------------------------------------------------------------------------------------------------------------------ hanging roots and vines
def rock_r_at(ctx, th, z):
    """Radius of the real rock mesh along the ray at angle th and height z (0 above the rim or below the neck)."""
    c, s = math.cos(th), math.sin(th)
    loc, nrm, idx, dist = ctx.rbvh.ray_cast(Vector((c * 300.0, s * 300.0, z)), Vector((-c, -s, 0.0)), 299.5)
    return math.hypot(loc.x, loc.y) if loc is not None else 0.0


def build_roots(ctx, n_rim=80, n_ledge=60):
    M = ctx.M; R = random.Random(91); mb = MB()
    rim = ctx.rim; NA = len(rim)
    looks = [np.array(li['p']) for li in ctx.look_info]
    cry = [(Vector(ci['p']), ci['size']) for ci in ctx.crystal_info]
    def blocked(th, z):
        if min(abs(math.remainder(th - fa, math.tau)) for fa in ctx.fall_th) < 0.1: return True
        q = np.array((math.cos(th), math.sin(th))) * float(r_outline(th))
        return any(np.hypot(*(q - lp)) < 10.0 for lp in looks)
    def grow(th, z, r, L, r0, leafy):
        pts = [Vector((r * math.cos(th), r * math.sin(th), z))]; s = 0.0; dth = R.gauss(0, 0.002)
        while s < L:
            z -= 1.15; th += dth + R.gauss(0, 0.0015)
            rr = rock_r_at(ctx, th, z)
            r = max(rr + 0.22, r - 0.12) if r - rr < 1.2 else r - 0.04
            p = Vector((r * math.cos(th), r * math.sin(th), z))
            if any((p - cp).length < cs * 1.3 + 1.5 for cp, cs in cry): break
            pts.append(p); s += 1.15
        if len(pts) < 3: return
        radii = [r0 * (1 - 0.8 * (k / (len(pts) - 1)) ** 0.7) + 0.03 for k in range(len(pts))]
        tube(mb, pts, radii, 6, 0, True, True, True)
        if leafy:
            for c_ in range(R.choice((1, 1, 2, 2, 3))):
                k = R.randrange(1, len(pts) - 1); q = pts[k]; o_ = Vector((q.x, q.y, 0.0)).normalized()
                cr_ = R.uniform(0.55, 1.1)
                for j_ in range(R.randint(3, 5)):
                    off = o_ * (radii[k] + cr_ * 0.45) + Vector((R.uniform(-0.6, 0.6), R.uniform(-0.6, 0.6), R.uniform(-1.4, 0.4))) * cr_
                    sphere(mb, q + off, cr_ * R.uniform(0.55, 0.9), 8, 5, 1, True, sq=(1.0, 1.0, 1.25), R=R, jit=0.15)
    k = 0; tries = 0
    while k < n_rim and tries < 600:
        tries += 1; i = R.randrange(NA); th = float(ctx.rim_th[i]); z = float(rim[i][2]) - 0.35
        if blocked(th, z): continue
        r = math.hypot(rim[i][0], rim[i][1]) - 0.3
        grow(th, z, r, R.uniform(5.0, 26.0), R.uniform(0.14, 0.32), R.random() < 0.6); k += 1
    good = [L for L in ctx.layers if L[2] > 0.6]
    k = 0; tries = 0
    while k < n_ledge and tries < 600 and good:
        tries += 1; lo, hi, hd = R.choice(good); th = R.uniform(0, math.tau)
        if blocked(th, lo): continue
        r = rock_r_at(ctx, th, lo + 0.3) - 0.25
        grow(th, lo + 0.3, r, R.uniform(4.0, 18.0), R.uniform(0.14, 0.3), R.random() < 0.45); k += 1
    o = mkobj(ctx, 'CITY_roots', mb.mesh('CITY_roots'), [M['root'], M['leaf']], 'root', props={'leafC': lin('#5d8f45'), 'fruit': 0.0})
    return o


# ------------------------------------------------------------------------------------------------------------------ the iron collar round the neck, the swivel lug, the chain point
LUG_YAW = 132.0


def build_collar(ctx):
    M = ctx.M; mb = MB(); NS = 96
    prof = [(0.0, 3.9), (9.3, 3.9), (9.3, 4.4), (9.0, 4.4), (9.0, 12.95), (9.3, 12.95), (9.3, 13.4), (7.32, 13.4), (7.32, 4.9), (0.0, 4.9)]
    for i in range(len(prof) - 1):
        lathe(mb, [prof[i], prof[i + 1]], NS, 0, (0, 0, 0), True, caps=False, uvk=(24.0, 0.25))
    lathe(mb, [(0.0, 3.2), (3.6, 3.2), (3.6, 3.92)], 40, 0, (0, 0, 0), True, caps=False)
    lathe(mb, [(3.6, 3.45), (3.85, 3.45), (3.85, 3.62), (3.6, 3.62)], 40, 0, (0, 0, 0), True, caps=False)
    for zr in (5.0, 8.7, 12.4):                                         # rivet rows
        for k in range(72):
            a = math.tau * (k + 0.5 * (zr == 8.7)) / 72
            sphere(mb, (9.0 * math.cos(a), 9.0 * math.sin(a), zr), 0.12, 6, 3, 0, True)
    for k in range(48):                                                 # rivets on the top lip
        a = math.tau * k / 48; sphere(mb, (8.3 * math.cos(a), 8.3 * math.sin(a), 13.4), 0.1, 6, 3, 0, True)
    for k in range(8):                                                  # gussets under the plate
        a = math.radians(LUG_YAW) + math.pi / 8 + k * math.pi / 4
        tm = MB(); xz_prism(tm, [(3.4, 3.92), (8.9, 3.92), (3.4, 2.6)], -0.17, 0.17, 0)
        mb.merge(tm, Matrix.Rotation(a, 4, 'Z'))
    rivets = []
    for k in range(4):                                                  # bolted flanges where the four ring segments meet
        a = math.radians(LUG_YAW) + math.pi / 4 + k * math.pi / 2
        tm = MB()
        for s_ in (-1, 1):
            box(tm, (9.65, s_ * 0.18, 8.68), (0.75, 0.15, 4.25), 0)
        for z in (5.4, 7.3, 9.2, 11.1, 12.5):
            cyl(tm, (9.75, -0.48, z), (9.75, 0.48, z), 0.11, 0.11, 8, 0)
            cyl(tm, (9.75, 0.33, z), (9.75, 0.45, z), 0.24, 0.24, 6, 0)
        mb.merge(tm, Matrix.Rotation(a, 4, 'Z'))
        for z in (5.4, 7.3, 9.2, 11.1):
            bt = MB(); cyl(bt, (0, 0, 0), (0, 0, 0.14), 0.24, 0.24, 6, 0)
            sphere(bt, (0, 0, 0.14), 0.12, 6, 3, 0)
            ro = mkobj(ctx, 'CITY_rivet_%02d' % len(rivets), bt.mesh('CITY_rivet_%02d' % len(rivets)), [M['collar']], 'collar')
            loc = Matrix.Rotation(a, 4, 'Z') @ Vector((9.75, -0.32, z)); dirn = Matrix.Rotation(a, 3, 'Z') @ Vector((0, -1, 0))
            x, y, zz = frame_of(dirn); Mx = Matrix((x, y, zz)).transposed().to_4x4(); Mx.translation = loc
            ro.matrix_basis = Mx
            rivets.append(ro)
    collar = mkobj(ctx, 'CITY_collar', mb.mesh('CITY_collar'), [M['collar']], 'collar')
    # the swivel lug: disc under the hub, two cheeks, the pin (along local X) the chain hangs on
    lb = MB()
    lathe(lb, [(0.0, 2.62), (3.0, 2.62), (3.0, 3.18), (0.0, 3.18)], 40, 0, (0, 0, 0), True, caps=False)
    for k in range(16):
        a = math.tau * k / 16; cyl(lb, (2.65 * math.cos(a), 2.65 * math.sin(a), 2.5), (2.65 * math.cos(a), 2.65 * math.sin(a), 2.64), 0.13, 0.13, 6, 0)
    cheek = [(-1.7, 2.66)] + [(1.7 * math.cos(a), 1.7 * math.sin(a)) for a in np.linspace(math.pi, math.tau, 13)] + [(1.7, 2.66)]
    for s_ in (-1, 1):
        tm = MB(); xz_prism(tm, cheek, -0.325, 0.325, 0)               # built in (y, z), extruded along x
        mb2 = Matrix.Translation((s_ * 1.525, 0.0, 0.0)) @ Matrix.Rotation(math.pi / 2, 4, 'Z')
        lb.merge(tm, mb2)
    cyl(lb, (-2.25, 0, 0), (2.25, 0, 0), 0.95, 0.95, 24, 0, True, True)
    for s_ in (-1, 1):
        cyl(lb, (s_ * 1.85, 0, 0), (s_ * 2.12, 0, 0), 1.28, 1.28, 6, 0, False, True)
        tube(lb, [(s_ * 2.2, 0.0, 0.62), (s_ * 2.42, 0.0, 0.62), (s_ * 2.42, 0.0, 0.3)], [0.07] * 3, 6, 0)
    lug = mkobj(ctx, 'CITY_lug', lb.mesh('CITY_lug'), [M['collar']], 'lug', rot=(0.0, 0.0, math.radians(LUG_YAW)))
    lug['axis'] = 'Z'
    ct = bpy.data.objects.new('CITY_chain_top', None); ctx.coll.objects.link(ct); ct.parent = lug
    ct.empty_display_type = 'ARROWS'; ct.empty_display_size = 3.0; ct['qa'] = 'empty'
    ct['note'] = 'pin centre; pin axis = local X; first link top curve centre 0.15 below, joint 0 at 0.775 along the link axis'
    return collar, lug, ct, rivets


# ------------------------------------------------------------------------------------------------------------------ QA allowance and the build
ALLOW = {frozenset(p) for p in [
    ('ground', 'street'), ('ground', 'canal'), ('ground', 'house'), ('ground', 'found'), ('ground', 'special'), ('ground', 'tree'),
    ('ground', 'prop'), ('ground', 'look'), ('ground', 'rock'), ('ground', 'garden'),
    ('street', 'house'), ('street', 'found'), ('street', 'bridge'), ('street', 'special'), ('street', 'prop'), ('street', 'look'),
    ('rock', 'crystal'), ('rock', 'root'), ('rock', 'look'), ('rock', 'canal'), ('rock', 'tree'),
    ('house', 'line'), ('ground', 'line'), ('house', 'found'), ('house', 'vane'), ('line', 'cloth'), ('vane', 'special'),
    ('bell', 'special'), ('bell', 'bell'), ('sails', 'special'), ('tree', 'tree'), ('fall', 'canal'), ('collar', 'collar'),
    ('canal', 'canal'), ('rock', 'prop'), ('street', 'street'), ('found', 'special'), ('canal', 'street')]}


def qa_allow(a, b):
    return frozenset((a.get('qa', ''), b.get('qa', ''))) in ALLOW


def tri_count(objs, evaluated=True):
    """Triangles as rendered (after the bevel and wave modifiers)."""
    dg = bpy.context.evaluated_depsgraph_get() if evaluated else None; n = 0
    for o in objs:
        if o.type != 'MESH': continue
        if dg is None or not o.modifiers:
            me = o.data; tot = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', tot); n += int((tot - 2).sum()); continue
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        tot = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', tot); n += int((tot - 2).sum())
        ev.to_mesh_clear()
    return n


def build(parent_collection=None, seed=11, trees=True, laundry=True, prune=True, **opts):
    """Build HIGH HARBOR under CITY_root (world ORIGIN = the collar point). Returns the API dict."""
    t0 = time.time(); tm = {}
    ctx = Ctx(); ctx.R = random.Random(seed)
    coll = bpy.data.collections.new('CITY')
    (parent_collection or bpy.context.scene.collection).children.link(coll)
    ctx.coll = coll; ctx.objs = []
    root = bpy.data.objects.new('CITY_root', None); coll.objects.link(root)
    root.location = ORIGIN; root.empty_display_size = 20.0; root['qa'] = 'empty'; ctx.root = root
    ctx.M = materials(opts.get('far_ink')); tm['materials'] = time.time() - t0
    plan(ctx); tm['plan'] = time.time() - t0
    build_terrain(ctx)
    build_canals(ctx)
    ctx.fall_th = [math.atan2(float(s['p'][1]), float(s['p'][0])) for s in ctx.spouts]
    build_rock(ctx); tm['land'] = time.time() - t0
    build_streets(ctx); build_plaza(ctx); build_bridges(ctx); build_rimstuff(ctx); build_fountain(ctx)
    stalls = build_plaza_props(ctx); tm['streets'] = time.time() - t0
    build_houses(ctx); tm['houses'] = time.time() - t0
    camp, bell, clap = build_campanile(ctx)
    church = build_church(ctx)
    wt = build_watertower(ctx)
    mills, hubs, sails = build_mills(ctx); ctx.mill_objs = mills
    for o_ in [camp, church, wt] + mills: add_bevel(o_, 0.05, weighted=False)
    gardens = build_gardens(ctx); tm['specials'] = time.time() - t0
    tr = build_trees(ctx) if trees else []
    ltr = build_ledge_trees(ctx) if trees else []; tm['trees'] = time.time() - t0
    lines, cloth = build_laundry(ctx) if laundry else (None, [])
    vanes, cross = build_vanes(ctx)
    tiles = build_tiles(ctx); tm['props'] = time.time() - t0
    falls = build_falls(ctx)
    crystals = build_crystals(ctx)
    roots = build_roots(ctx)
    collar, lug, chain_top, rivets = build_collar(ctx); tm['under'] = time.time() - t0
    bpy.context.view_layer.update()
    removed = []
    if prune:                                                           # drop trees that touch anything they must not touch
        sys.path.insert(0, os.path.join(ROOT, 'kit'))
        import qa as QA
        others = [o for o in ctx.objs if o.get('qa') not in ('tree', 'ground', 'rock')]
        bad = QA.overlaps(tr + ltr, others, allow=qa_allow)
        names = set()
        for a, b, n_ in bad:
            for nm in (a, b):
                if nm.startswith('CITY_tree_') or nm.startswith('CITY_ltree_'): names.add(nm)
        for nm in sorted(names):
            o = bpy.data.objects.get(nm)
            if o is None: continue
            ctx.objs.remove(o); removed.append(nm)
            if o in tr: tr.remove(o)
            if o in ltr: ltr.remove(o)
            bpy.data.objects.remove(o, do_unlink=True)
        tm['prune'] = time.time() - t0
    info = dict(
        origin=ORIGIN, rim_z=float(np.mean(ctx.rim[:, 2])), plaza=(float(HILL[0]), float(HILL[1]), float(ctx.zplaza)), plaza_r=PLAZA_R,
        campanile=(float(ctx.camp[0]), float(ctx.camp[1]), float(ctx.zplaza)), campanile_top=float(ctx.zplaza + ctx.camp_top), bell_pivot=float(ctx.zplaza - 0.02 + ctx.camp_pivot),
        church=(float(ctx.church[0]), float(ctx.church[1]), float(ctx.zplaza + 0.48)), church_dir=(float(ctx.church_dir[0]), float(ctx.church_dir[1])),
        watertower=ctx.wt_top, mills=ctx.mill_info, lookouts=[dict(p=(float(l['p'][0]), float(l['p'][1])), d=(float(l['d'][0]), float(l['d'][1])), z=float(l['z'])) for l in ctx.look_info],
        street0=[(float(q[0]), float(q[1]), float(ctx.streets[0].z_at(s))) for s in range(0, int(ctx.streets[0].L), 10) for q in [ctx.streets[0].at(float(s))[0]]],
        falls=ctx.fall_info, crystals=ctx.crystal_info, lines=getattr(ctx, "lines_info", []), collar=(0.0, 0.0, 0.0), chain_top=(0.0, 0.0, 0.0),
        rock_bottom=5.0, neck_r=float(s_prof(10.0) * RBAR))
    C = dict(root=root, coll=coll, sails=sails, hubs=hubs, mills=mills, cloth=cloth, lines=lines, tiles=tiles, falls=falls, crystals=crystals,
             bell=bell, clapper=clap, vanes=vanes, cross=cross, campanile=camp, church=church, watertower=wt, stalls=stalls, gardens=gardens,
             trees=tr, ledge_trees=ltr, houses=ctx.house_objs, roots=roots, collar=collar, lug=lug, chain_top=chain_top, rivets=rivets,
             objs=ctx.objs, qa_allow=qa_allow, info=info, ctx=ctx, removed=removed)
    bpy.context.view_layer.update()
    C['tris'] = tri_count(ctx.objs); C['time'] = time.time() - t0; C['timing'] = tm
    return C
