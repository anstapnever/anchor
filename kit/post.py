# ANCHOR post: ink from the data passes, atmosphere, god rays, bloom, rain, the high-key anime grade.
#   python post.py <frames_dir> <out_dir> <f0> <f1> [shot_params.json] [workers]
# Inputs per frame N: fNNNN.png (16-bit colour after the paint mix), ANNNN.png (log depth, oid, mid, 1), BNNNN.png (normal, 1),
# GNNNN.png (glow, hz, ink, 1). (data_layout 1 = the old one with ink in A's alpha - wrong wherever ink is fractional)
import os, sys, json, math
import numpy as np
import cv2

LN = math.log(20001.0)
INK = np.array([0x2a, 0x22, 0x36], np.float32) / 255.0


def srgb_inv(x):
    """the data passes (A, B, G) go through the scene's Standard view transform on the way to PNG: undo the sRGB curve."""
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def rd16(p):
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None: raise FileNotFoundError(p)
    im = im.astype(np.float32) / (65535.0 if im.dtype == np.uint16 else 255.0)
    if im.ndim == 3: im = im[..., ::-1] if im.shape[2] == 3 else np.concatenate([im[..., 2::-1], im[..., 3:]], axis=2)
    return im


def vnoise(h, w, cell, seed=0):
    rng = np.random.default_rng(seed)
    gh, gw = int(h / cell) + 3, int(w / cell) + 3
    g = rng.random((gh, gw), dtype=np.float32)
    return cv2.resize(g, (int(gw * cell), int(gh * cell)), interpolation=cv2.INTER_CUBIC)[:h, :w]


def shift(a, dx, dy):
    """a[y+dy, x+dx] with edge clamp."""
    h, w = a.shape[:2]
    ys = np.clip(np.arange(h) + dy, 0, h - 1); xs = np.clip(np.arange(w) + dx, 0, w - 1)
    return a[ys][:, xs]


DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]


MATTE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', 'matte')


def mech_sil(frame, h, w):
    """the mech at this frame from out/matte/m<frame>.png (the 'behind the mech' mattes): (seen, own) bool masks - seen = R,
    the mech with only solid things (sea, port, chain) able to hide it, no FX surface counted (ink_lines keeps the inked
    pixels of it: where FX water lies on the mech the pixel is ink-free); own = alpha, the mech's own silhouette (alone, its
    parts under the sea included) - or None (no matte for this frame)."""
    p = os.path.join(MATTE_DIR, 'm%04d.png' % frame)
    if not os.path.exists(p): return None
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None or im.ndim != 3 or im.shape[2] != 4: return None
    if int(im[0, 0, 1]) + 256 * int(im[0, 0, 0]) != frame: return None        # G + 256 B = the frame it was rendered for
    a = im[..., 3].astype(np.float32) / 255.0; r = im[..., 2].astype(np.float32) / 255.0
    if a.shape != (h, w):
        a = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA); r = cv2.resize(r, (w, h), interpolation=cv2.INTER_AREA)
    return (r > 0.5, a > 0.5) if r.max() >= 0.5 else None


INK0_MID_RANGES = ((-5.0, 8.0), (18.0, 31.0), (140.0, 215.0))    # x 1/4096: sky, sea, cloud; city water / mist; UNDER + all M_fx_* (150..188), wide: the estimate is noisy


def blend_of_two(ys, xs, oid, mid, wv, pure):
    """True where the pixel (ys, xs) is, within noise, a blend of two clean pixels within 2 px of it whose id differs: one
    share a fits oid, mid and ink at once (each channel to its 16-bit noise + 5 % of the step between the two)."""
    h, w = oid.shape
    n = len(ys)
    expl = np.zeros(n, bool)
    if not n: return expl
    offs = [(dx, dy) for dy in range(-2, 3) for dx in range(-2, 3) if (dx, dy) != (0, 0)]
    V = np.stack([oid[ys, xs], mid[ys, xs], wv[ys, xs]], 1).astype(np.float64)
    S = np.array([3e-5, 3e-5, 2e-3])
    Wt = 1.0 / S ** 2
    NB = []
    for dx, dy in offs:
        yq = np.clip(ys + dy, 0, h - 1); xq = np.clip(xs + dx, 0, w - 1)
        NB.append((pure[yq, xq], np.stack([oid[yq, xq], mid[yq, xq], wv[yq, xq]], 1).astype(np.float64)))
    for i in range(len(offs)):
        pa, A = NB[i]
        if not pa.any(): continue
        for j in range(i + 1, len(offs)):
            pb, B = NB[j]
            m = pa & pb & ~expl
            if not m.any(): continue
            D = B - A
            m &= (np.abs(D[:, 0]) > 2e-4) | (np.abs(D[:, 1]) > 1e-4)
            if not m.any(): continue
            al = ((V - A) * D * Wt).sum(1) / np.maximum((D * D * Wt).sum(1), 1e-30)
            R = np.abs(V - A - al[:, None] * D) / (S + 0.05 * np.abs(D))
            expl |= m & (al > -0.05) & (al < 1.05) & (R.max(1) <= 1.0)
    return expl


def despeckle(depth, oid, mid, inkw, nrm):
    """a sub-pixel ink-free thing (a far drop, one dithered sample of spray) leaves a few % of its oid / mid / ink in the pixels
    of an inked surface round where its sample fell (the film filter spreads it over up to 3x3): the id test (2e-4) took that
    for an edge and inked a 2-3 px dot (06.11: s33-s34 pauldrons, once the white mass in front went behind the mech; a 2-3 %
    admixture, invisible in the colour). Per pixel: the best-inked pixel within 2 px is the clean surface (nearest in depth
    among equals); c = its ink - this ink. A pixel (0.0001 < c < 0.15, nothing ink-free within 2 px) whose oid / mid are off
    that pixel's by no more than an ink-free admixture of c can move them (oid <= c, mid <= 0.06 c) takes that pixel's depth,
    oid, mid, ink and normal - if the admixture is ink-free water / sky / mist: from c' = c / ink >= 0.01 the implied
    intruder's material (mid_ref + d mid / c') must lie in INK0_MID_RANGES and its oid within 0..1, 0.02 off the clean one's; fainter ones (c' < 0.01)
    only where the ink does not step by 0.15 within 2 px (no object boundary of a lighter-inked thing). Real edges keep their
    pixels: two inked surfaces mix without an ink deficit, another object's id is off by far more than c, the rim of
    ink-free water or a glow has an ink-free pixel next to it."""
    h, w = inkw.shape
    k5 = np.ones((5, 5), np.uint8)
    wv = inkw.astype(np.float32)
    hi = cv2.dilate(wv, k5); lo = cv2.erode(wv, k5)
    c0 = hi - wv
    ys, xs = np.nonzero((c0 > 1e-4) & (c0 < 0.15) & (lo >= 0.05))
    if not len(ys): return depth, oid, mid, inkw, nrm, 0
    # a clean reference: a pixel of one surface, not an anti-aliased mix - at least 3 of its 8 neighbours carry its very oid,
    # mid and ink (a mixed rim pixel of a higher-inked object next to a plain one passed for 'the clean surface' and pasted
    # its mixed id onto the plain pixel: a new line along every such rim)
    same = np.zeros((h, w), np.uint8)
    for dx, dy in DIRS:
        same += ((np.abs(shift(oid, dx, dy) - oid) < 2e-5) & (np.abs(shift(mid, dx, dy) - mid) < 2e-6) & (np.abs(shift(wv, dx, dy) - wv) < 1e-3)).astype(np.uint8)
    pure = same >= 3
    dp = depth[ys, xs]; best = np.full(len(ys), -1e9, np.float32); by = ys.copy(); bx = xs.copy()
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx == 0 and dy == 0: continue
            yq = np.clip(ys + dy, 0, h - 1); xq = np.clip(xs + dx, 0, w - 1)
            key = np.where(pure[yq, xq], wv[yq, xq] - 1e-3 * np.minimum(np.abs(depth[yq, xq] - dp) / np.maximum(dp, 1e-3), 1.0), -1e9)
            m = key > best
            best = np.where(m, key, best); by = np.where(m, yq, by); bx = np.where(m, xq, bx)
    wr = np.where(best > -1e8, wv[by, bx], wv[ys, xs]); c = wr - wv[ys, xs]
    o0 = oid[by, bx]; m0 = mid[by, bx]
    do = oid[ys, xs] - o0; dm = mid[ys, xs] - m0
    # another object (oid off the clean one's), moved no further than an ink-free admixture of c can move it
    ok = (c > 1e-4) & (c < 0.15) & (np.abs(do) > 2e-5) & (np.abs(do) <= c * 1.05 + 1e-5) & (np.abs(dm) <= c * 0.06 + 1e-6)
    cp = c / np.maximum(wr, 1e-3)
    strong = cp >= 0.01
    mx = (m0 + dm / np.maximum(cp, 1e-4)) * 4096.0; ox = o0 + do / np.maximum(cp, 1e-4)
    in0 = np.zeros(len(mx), bool)
    for a_, b_ in INK0_MID_RANGES: in0 |= (mx >= a_) & (mx <= b_)
    ok &= np.where(strong, in0 & (ox > -0.05) & (ox < 1.05) & (np.abs(ox - o0) > 0.02), (hi[ys, xs] - lo[ys, xs]) < 0.15)
    # a real anti-aliased edge between two inked things (a tree on a wall, a pier rim, a roof edge) is a blend of two clean
    # pixels next to it: when the two inks are close the ink-0 extrapolation above can still pass it (06.11 fix1: outlines
    # broke into teeth across the town) - a pixel that one pair of clean pixels within 2 px explains in oid, mid and ink with
    # one share is left alone
    if ok.any():
        ii = np.nonzero(ok)[0]
        ok[ii[blend_of_two(ys[ii], xs[ii], oid, mid, wv, pure)]] = False
    n = int(ok.sum())
    if not n: return depth, oid, mid, inkw, nrm, 0
    ys, xs, by, bx = ys[ok], xs[ok], by[ok], bx[ok]
    depth = depth.copy(); oid = oid.copy(); mid = mid.copy(); inkw = inkw.copy(); nrm = nrm.copy()
    depth[ys, xs] = depth[by, bx]; oid[ys, xs] = oid[by, bx]; mid[ys, xs] = mid[by, bx]; inkw[ys, xs] = inkw[by, bx]; nrm[ys, xs] = nrm[by, bx]
    return depth, oid, mid, inkw, nrm, n


def ink_lines_raw(depth, oid, mid, inkw, nrm, frame, P, mech=None):
    """Leviathan-style: id edges (front side only), relative depth edges, normal creases; pressure noise; thinner far away.
    mech ((seen, own) masks, frames with 'behind' mattes): water marked behind the mech is cut at its outline but lies nearer
    than the armour in the depth pass - the mech's outline there must still count as the front side (06.11): an armour pixel
    the mech is seen at, next to a pixel outside the mech's own silhouette that is ink-free, is in front of it."""
    h, w = depth.shape
    inkw0 = inkw
    if mech is not None:
        seen, own = mech
        seen = seen & (inkw0 > 0.5)        # R counts the mech under FX water too: the mech is seen where its ink weight is

    def over(dx, dy):              # p: the mech seen there; q (p + d): outside the mech's own silhouette and ink-free
        return seen & ~shift(own, dx, dy) & (shift(inkw0, dx, dy) < 0.05)
    if P.get('ink_front', 0):
        # an anti-aliased edge pixel of an ink-0 object (water, glows) lying over an inked one carries part of the ink weight of
        # what is behind it, and its id and depth differ from both sides: it drew a faint false outline round ink-0 objects.
        # Such a pixel takes the ink weight of its front-most 3x3 neighbour when that neighbour is ink-free.
        dmin = depth.copy(); wf = inkw.copy()
        for dx, dy in DIRS:
            dq = shift(depth, dx, dy); m = dq < dmin
            if mech is not None: m &= ~over(dx, dy)
            dmin = np.where(m, dq, dmin); wf = np.where(m, shift(inkw, dx, dy), wf)
        inkw = np.where(wf < 0.05, wf, inkw)
    best = np.zeros((h, w), np.float32)
    for r in (1, 2):
        acc = np.zeros((h, w), np.float32)
        for dx, dy in DIRS:
            dq = shift(depth, dx * r, dy * r)
            front = (depth <= dq * 1.0005).astype(np.float32)
            if mech is not None: front = np.maximum(front, over(dx * r, dy * r).astype(np.float32))
            idd = ((np.abs(shift(oid, dx * r, dy * r) - oid) > 2e-4) | (np.abs(shift(mid, dx * r, dy * r) - mid) > 1e-4)).astype(np.float32) * front
            rel = np.clip((dq - depth) / np.maximum(depth, 1e-3), 0, 10)
            de = np.clip((rel - P['dep0']) / (P['dep1'] - P['dep0']), 0, 1)
            nq = shift(nrm, dx * r, dy * r)
            dt = np.sum(nrm * nq, axis=2)
            ne = np.clip((P['nrm0'] - dt) / (P['nrm0'] - P['nrm1']), 0, 1) * 0.85
            ne = ne * (np.abs(shift(oid, dx * r, dy * r) - oid) <= 2e-4)      # creases only within one object (no rims round ink-0 FX)
            acc = np.maximum(acc, np.maximum(np.maximum(idd, de), ne))
        if r == 1: best = acc
        else:
            # the second ring only where the pen presses (pressure noise) and the object is near
            press = vnoise(h, w, 34.0, 1000 + frame // 2)
            near = np.clip(P['near'] / np.maximum(depth, 1e-3), 0.5, 1.25)
            wide = np.clip((press * 0.56 + 0.72) * near - 0.95, 0, 1) * 1.6
            best = np.maximum(best, acc * np.clip(wide, 0, 1) * 0.9)
    press = vnoise(h, w, 34.0, 77 + frame // 2) * 0.56 + 0.72
    # lines thin out with distance (far lattices, roofs and yards would otherwise turn to solid ink)
    far = np.clip((P['line_far1'] - depth) / (P['line_far1'] - P['line_far0']), P['line_far_min'], 1.0)
    return np.clip(best * inkw * np.clip(press, 0, 1.15) * far, 0, 1)


DOT_AREA = 80       # px: a speck of ink at most this big (8-connected, line > 0.03) - one stray sample inks its 3x3 spread
                    # plus the 1-2 px rings round it (39-44 px, 06.11 s33-s34), two close ones up to ~80 ...
DOT_GONE = 0.7      # ... that the despeckled data no longer draws (this share of its ink gone) is a drop dot


def drop_dots(L0, depth, oid, mid, inkw, nrm, frame, P, mech=None):
    """the lines without the dots of sub-pixel ink-free things (despeckle): only small isolated specks that vanish once the
    data is despeckled change - a long line keeps every pixel even where the despeckle touched it, no ink is ever added."""
    d2, o2, m2, w2, n2, n = despeckle(depth, oid, mid, inkw, nrm)
    if not n: return L0, 0
    L1 = ink_lines_raw(d2, o2, m2, w2, n2, frame, P, mech)
    k, lab, st, _ = cv2.connectedComponentsWithStats((L0 > 0.03).astype(np.uint8), connectivity=8)
    if k <= 1: return L0, 0
    lost = np.maximum(L0 - L1, 0)
    s0 = np.bincount(lab.ravel(), L0.ravel(), k); s1 = np.bincount(lab.ravel(), lost.ravel(), k)
    acc = (st[:, 4] <= DOT_AREA) & (s1 >= DOT_GONE * np.maximum(s0, 1e-6))
    acc[0] = False
    if not acc.any(): return L0, 0
    A = cv2.dilate(acc[lab].astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    return np.where(A, np.minimum(L0, L1), L0).astype(L0.dtype), int(acc.sum())


def ink_lines(depth, oid, mid, inkw, nrm, frame, P, mech=None):
    L0 = ink_lines_raw(depth, oid, mid, inkw, nrm, frame, P, mech)
    if not P.get('despeckle', 1): return L0
    return drop_dots(L0, depth, oid, mid, inkw, nrm, frame, P, mech)[0]


def god_rays(mask, sun_xy, strength, samples=28, decay=0.965):
    if strength <= 0: return None
    h, w = mask.shape
    s = 0.5; mh, mw = int(h * s), int(w * s)
    m = cv2.resize(mask, (mw, mh), interpolation=cv2.INTER_AREA)
    cx, cy = sun_xy[0] * mw, sun_xy[1] * mh
    yy, xx = np.mgrid[0:mh, 0:mw].astype(np.float32)
    acc = np.zeros_like(m); wsum = 0.0; wgt = 1.0
    for k in range(samples):
        f = 1.0 - k / samples * 0.85
        mx = cx + (xx - cx) * f; my = cy + (yy - cy) * f
        acc += cv2.remap(m, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT) * wgt; wsum += wgt; wgt *= decay
    acc /= wsum
    return cv2.resize(acc, (w, h), interpolation=cv2.INTER_LINEAR) * strength


def bloom(c, glow, thr, strength):
    lum = c.max(axis=2)
    src = c * np.clip((lum - thr) / 0.4, 0, 1)[..., None] + c * glow[..., None] * 0.9
    h, w = lum.shape; out = np.zeros_like(c)
    small = src
    for i, wt in enumerate((0.35, 0.3, 0.25, 0.2, 0.15)):
        small = cv2.pyrDown(small)
        up = small
        for _ in range(i + 1): up = cv2.pyrUp(up)
        up = cv2.resize(up, (w, h), interpolation=cv2.INTER_LINEAR)
        out += up * wt
    return out * strength


def rain_layer(h, w, frame, density, angle_deg, seed=5):
    if density <= 0: return None
    rng = np.random.default_rng(seed * 1000 + frame // 2)
    img = np.zeros((h, w), np.float32)
    n = int(1400 * density)
    a = math.radians(angle_deg)
    for _ in range(n):
        x = rng.integers(-200, w + 200); y = rng.integers(-200, h); L = rng.integers(30, 90); b = rng.uniform(0.25, 0.8)
        cv2.line(img, (int(x), int(y)), (int(x + math.sin(a) * L), int(y + math.cos(a) * L)), b, 1, cv2.LINE_AA)
    return cv2.GaussianBlur(img, (0, 0), 0.6)


def grade(c, P, frame):
    c = c / (1.0 + np.maximum(c - 1.0, 0.0) * 0.6)
    c = c * P['exposure']
    c = np.power(np.maximum(c, 0.0), P['gamma'])
    l = c @ np.array([0.299, 0.587, 0.114], np.float32)
    chroma = c.max(axis=2) - c.min(axis=2)
    k = P['sat'] * (1.0 + P['vibrance'] * (1.0 - chroma))
    c = l[..., None] + (c - l[..., None]) * k[..., None]
    lift = np.array(P['lift'], np.float32); gain = np.array(P['gain'], np.float32)
    c = lift + c * (gain - lift)
    h, w = l.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    q2 = ((xx / w - 0.5) ** 2 + (yy / h - 0.5) ** 2)
    c = c * (1.0 - P['vignette'] * q2 * 1.6)[..., None]
    rng = np.random.default_rng(frame * 7919 + 13)
    g = (rng.random((h, w), dtype=np.float32) - 0.5) * P['grain']
    c = c + g[..., None]
    return np.clip(c, 0, 1)


DEF = dict(dep0=0.015, dep1=0.035, nrm0=0.78, nrm1=0.6, near=180.0, ink_mix=0.25, ink_dark=0.32,
           haze=(0.78, 0.86, 1.0), haze_dist=2600.0, haze_max=0.55, sun_xy=None, rays=0.0, ray_col=(1.0, 0.93, 0.78),
           bloom=0.9, bloom_thr=0.92, exposure=1.06, gamma=0.9, sat=1.0, vibrance=0.3, lift=(0x14 / 255, 0x10 / 255, 0x1e / 255), gain=(1.0, 0xfa / 255, 0xf2 / 255),
           vignette=0.16, grain=0.02, rain=0.0, rain_angle=-12.0, flash=0.0, under=0.0, fade=0.0, fade_col=(0, 0, 0),
           line_far0=320.0, line_far1=1400.0, line_far_min=0.3,
           ink_front=1)          # no false dark outline round ink-free water / glows over inked objects (A/B 05.11, both water checks)


def process(fr, src, dst, P):
    n = '%04d' % fr
    c = rd16(os.path.join(src, 'f%s.png' % n))[..., :3]
    A = rd16(os.path.join(src, 'A%s.png' % n)); B = rd16(os.path.join(src, 'B%s.png' % n)); G = rd16(os.path.join(src, 'G%s.png' % n))
    if P.get('data_srgb', 1):          # RGB of the data passes are sRGB-encoded by the view transform (alpha stays linear)
        A[..., :3] = srgb_inv(A[..., :3]); B[..., :3] = srgb_inv(B[..., :3]); G[..., :3] = srgb_inv(G[..., :3])
    depth = np.exp(A[..., 0] * LN) - 1.0; oid = A[..., 1]; mid = A[..., 2]
    inkw = A[..., 3] if P.get('data_layout', 2) == 1 else G[..., 2]
    nrm = B[..., :3] * 2.0 - 1.0; glow = G[..., 0]; hzk = G[..., 1]
    sky = depth > 15000.0
    # atmosphere: aerial perspective toward the horizon colour (not on the sky dome)
    if P['haze_max'] > 0:
        hz = (1.0 - np.exp(-depth / P['haze_dist'])) * P['haze_max'] * hzk; hz[sky] = 0
        c = c + (np.array(P['haze'], np.float32) - c) * hz[..., None]
    # underwater: depth fog toward the water colour, a cooler grade
    if P['under'] > 0:
        uw = 1.0 - np.exp(-depth / P.get('under_dist', 60.0))
        wc = np.array(P.get('under_col', (0.05, 0.42, 0.55)), np.float32)
        c = c + (wc - c) * (uw * P['under'])[..., None]
    lines = ink_lines(depth, oid, mid, inkw, nrm, fr, P, mech_sil(fr, depth.shape[0], depth.shape[1]))
    inkc = INK * (1 - P['ink_mix']) + c * P['ink_dark'] * P['ink_mix']
    c = c + (inkc - c) * lines[..., None]
    if P['sun_xy'] is not None and P['rays'] > 0:
        lum = c.max(axis=2)
        m = (sky.astype(np.float32) * np.clip((lum - 0.75) / 0.25, 0, 1))
        gr = god_rays(m, P['sun_xy'], P['rays'])
        c = c + gr[..., None] * np.array(P['ray_col'], np.float32)
    c = c + bloom(c, glow, P['bloom_thr'], P['bloom'])
    if P['rain'] > 0:
        rl = rain_layer(c.shape[0], c.shape[1], fr, P['rain'], P['rain_angle'])
        c = c + (np.array((0.85, 0.9, 1.0), np.float32) - c) * (rl * 0.55)[..., None]
    if P['flash'] > 0: c = c + (np.array((0.9, 0.93, 1.0), np.float32) - c) * P['flash'] * 0.35
    c = grade(c, P, fr)
    if P['fade'] > 0: c = c + (np.array(P['fade_col'], np.float32) - c) * P['fade']
    out = (c[..., ::-1] * 255.0 + 0.5).astype(np.uint8)
    cv2.imwrite(os.path.join(dst, 'f%s.png' % n), out)
    return fr


def params_for(fr, spec):
    """spec: {'default': {...}, 'ranges': [[f0, f1, {...}], ...], 'keys': {'flash': [[frame, value], ...], ...}}"""
    P = dict(DEF); P.update(spec.get('default', {}))
    for f0, f1, d in spec.get('ranges', []):
        if f0 <= fr <= f1: P.update(d)
    for k, kv in spec.get('keys', {}).items():
        kv = sorted(kv)
        if fr <= kv[0][0]: P[k] = kv[0][1]
        elif fr >= kv[-1][0]: P[k] = kv[-1][1]
        else:
            for (a, va), (b, vb) in zip(kv, kv[1:]):
                if a <= fr <= b:
                    u = (fr - a) / max(1, b - a)
                    P[k] = [x + (y - x) * u for x, y in zip(va, vb)] if isinstance(va, list) else va + (vb - va) * u
                    break
    return P


def _job(a):
    fr, src, dst, spec = a
    try: return process(fr, src, dst, params_for(fr, spec))
    except FileNotFoundError as e: print('missing', e); return -fr


if __name__ == '__main__':
    src, dst, f0, f1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    spec = json.load(open(sys.argv[5])) if len(sys.argv) > 5 and sys.argv[5] != '-' else {}
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 6
    os.makedirs(dst, exist_ok=True)
    jobs = [(f, src, dst, spec) for f in range(f0, f1 + 1)]
    if workers <= 1:
        for j in jobs: print(_job(j))
    else:
        from multiprocessing import Pool
        with Pool(workers) as p:
            for r in p.imap_unordered(_job, jobs): pass
    print('post done', f0, f1)
