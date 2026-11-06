# maskana.py <check dir> [min_area_px] : FX water drawn over the mech's body, from the material-id pass (A png: log depth,
# oid, mid, 1) of maskscan.py. A connected piece of FX water whose outline is (almost) all mech armour is an ISLAND: a puff,
# a crest billow or dissolving lace sitting on the body reads as a hole in it or a white sticker on it. 'front' = the water is
# nearer than the armour round it (drawn on the body), 'gap' = farther (seen through a gap between parts).
# Also the opposite: a small piece of mech whose outline is all FX water (a shard floating in the spray).
# Writes <dir>/islands.json and contact sheets <dir>/isl_NN.jpg (colour pass, island outlined), prints a summary.
import sys, os, json, math, glob, re, collections
import numpy as np
import cv2

D = sys.argv[1]; MINA = int(sys.argv[2]) if len(sys.argv) > 2 else 3
LN = math.log(20001.0)
SHOTS = [('s21', 1009, 1056), ('s22', 1057, 1094), ('s23', 1095, 1138), ('s24', 1139, 1176), ('s25', 1177, 1258), ('s26', 1259, 1320),
         ('s27', 1321, 1378), ('s28', 1379, 1416), ('s30', 1465, 1522), ('s31', 1523, 1570), ('s32', 1571, 1613), ('s33', 1614, 1680),
         ('s34', 1681, 1728), ('s35', 1729, 1766), ('s37', 1825, 1886)]


def shot(f):
    for s, a, b in SHOTS:
        if a <= f <= b: return s
    return 's??'


def srgb_inv(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def rd16(p):
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None: raise FileNotFoundError(p)
    im = im.astype(np.float32) / (65535.0 if im.dtype == np.uint16 else 255.0)
    if im.ndim == 3: im = im[..., ::-1] if im.shape[2] == 3 else np.concatenate([im[..., 2::-1], im[..., 3:]], axis=2)
    return im


cats = json.load(open(os.path.join(D, 'cats.json')))
reg = cats['reg']; coll = cats['coll']
# white water only (not the debris, rust flakes, steam, glows): every collection (shed water may hang on the mech)
WATER = re.compile(r'^M_fx_(water|foam|wake|spfoam|bubble|skirt|spout)')
fx_names = sorted({m for d in coll.values() for m in d if WATER.search(m)})
mech_names = sorted(m for m in coll.get('MECH', {}) if not m.startswith('M_fx'))
fx_ids = np.array(sorted({reg[m] for m in fx_names if m in reg}))
mech_ids = np.array(sorted({reg[m] for m in mech_names if m in reg}))
print('water materials', len(fx_ids), fx_names[:12], '...')
print('mech materials', len(mech_ids), mech_names[:12], '...')
missing = [m for m in fx_names + mech_names if m not in reg]
if missing: print('NOT IN REGISTRY (no mid):', missing[:20])

K5 = np.ones((5, 5), np.uint8); K9 = np.ones((9, 9), np.uint8)
res = []; per_shot = collections.Counter(); nfr = 0
files = sorted(glob.glob(os.path.join(D, 'raw', 'A*.png')))
for p in files:
    f = int(os.path.basename(p)[1:5]); nfr += 1
    A = rd16(p); A[..., :3] = srgb_inv(A[..., :3])
    mid = A[..., 2] * 4096.0; mi = np.rint(mid).astype(np.int32); ok = np.abs(mid - mi) < 0.2
    depth = np.exp(A[..., 0] * LN) - 1.0
    isW = ok & np.isin(mi, fx_ids); isM = ok & np.isin(mi, mech_ids)
    H, Wd = isW.shape
    for kind_src, src, other in (('water', isW, isM), ('shard', isM, isW)):
        n, lab, st, cen = cv2.connectedComponentsWithStats(src.astype(np.uint8), connectivity=8)
        for i in range(1, n):
            x, y, w, h, area = [int(v) for v in st[i]]
            if area < MINA: continue
            if kind_src == 'shard' and area > 0.01 * H * Wd: continue
            if x <= 0 or y <= 0 or x + w >= Wd or y + h >= H: continue        # cut by the frame edge: it goes on outside
            x0, y0 = max(0, x - 6), max(0, y - 6); x1, y1 = min(Wd, x + w + 6), min(H, y + h + 6)
            comp = (lab[y0:y1, x0:x1] == i)
            # the ring 3-4 px out: the pixels right at the outline can be a blend of both sides (a blend can land on another
            # material's id by chance), so the ring is read just past them
            ring = (cv2.dilate(comp.astype(np.uint8), K9) > 0) & ~(cv2.dilate(comp.astype(np.uint8), K5) > 0)
            ring &= ok[y0:y1, x0:x1] & ~src[y0:y1, x0:x1]
            nr = int(ring.sum())
            if nr == 0: continue
            ro = ring & other[y0:y1, x0:x1]
            fo = float(ro.sum()) / nr
            if fo < 0.75: continue
            dI = float(np.median(depth[y0:y1, x0:x1][comp])); dR = float(np.median(depth[y0:y1, x0:x1][ro]))
            kind = ('front' if dI < dR else 'gap') if kind_src == 'water' else ('gap' if dI > dR else 'front')
            mids = collections.Counter(mi[y0:y1, x0:x1][comp].tolist()).most_common(2)
            # sample pixels for the ray probe (full-size pixel coordinates + the pass's z depth there): the component's
            # pixels away from its edge first (the edge pixels can mix surfaces), spread over the whole piece
            er = cv2.erode(comp.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            yy, xx = np.nonzero(er if er.sum() >= 4 else comp)
            pick = np.linspace(0, len(yy) - 1, min(16, len(yy))).astype(int)
            sc_ = 1920.0 / Wd
            smp = [[round((x0 + float(xx[j]) + 0.5) * sc_ - 0.5, 1), round((y0 + float(yy[j]) + 0.5) * sc_ - 0.5, 1),
                    round(float(depth[y0 + yy[j], x0 + xx[j]]), 3)] for j in pick]
            res.append({'f': f, 'shot': shot(f), 'src': kind_src, 'kind': kind, 'area': area, 'bbox': [x, y, w, h],
                        'c': [round(float(cen[i][0]), 1), round(float(cen[i][1]), 1)], 'fo': round(fo, 2), 'dI': round(dI, 2), 'dR': round(dR, 2),
                        'mids': mids, 'smp': smp})
            per_shot[(shot(f), kind_src, kind)] += 1
inv = {v: k for k, v in reg.items()}
for r in res: r['mats'] = [(inv.get(m, '?'), c) for m, c in r['mids']]
json.dump({'res': res, 'frames': nfr, 'scale': 1920.0 / Wd if files else 2.0}, open(os.path.join(D, 'islands.json'), 'w'), indent=0)
print('frames', nfr, 'islands', len(res))
for k in sorted(per_shot): print('  %s %-5s %-5s %d' % (k[0], k[1], k[2], per_shot[k]))
by_f = collections.defaultdict(list)
for r in res: by_f[r['f']].append(r)
print('frames with water islands on the body (front):', sorted({r['f'] for r in res if r['src'] == 'water' and r['kind'] == 'front'}))
big = sorted([r for r in res if r['src'] == 'water' and r['kind'] == 'front'], key=lambda r: -r['area'])
print('biggest front water islands:')
for r in big[:40]: print('  f%d %s area %d c %s fo %.2f d %.1f/%.1f %s' % (r['f'], r['shot'], r['area'], r['c'], r['fo'], r['dI'], r['dR'], r['mats']))
# contact sheets: every front water island (biggest per frame first), and the shards, on the colour pass
def tile(r):
    p = os.path.join(D, 'raw', 'f%04d.png' % r['f'])
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None: return None
    if im.dtype == np.uint16: im = (im / 257).astype(np.uint8)
    cx, cy = r['c']; S = 90
    x0 = int(np.clip(cx - S, 0, im.shape[1] - 2 * S)); y0 = int(np.clip(cy - S, 0, im.shape[0] - 2 * S))
    c = im[y0:y0 + 2 * S, x0:x0 + 2 * S].copy()
    x, y, w, h = r['bbox']
    cv2.rectangle(c, (x - x0 - 2, y - y0 - 2), (x - x0 + w + 1, y - y0 + h + 1), (0, 0, 255) if r['src'] == 'water' else (255, 0, 255), 1)
    c = cv2.resize(c, (360, 360), interpolation=cv2.INTER_NEAREST)
    cv2.putText(c, '%d %s %d' % (r['f'], r['kind'][0], r['area']), (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
    return c
sel = [r for r in res if r['kind'] == 'front']
sel.sort(key=lambda r: (r['src'], r['f'], -r['area']))
for old in glob.glob(os.path.join(D, 'isl_*.jpg')): os.remove(old)
k = 0
for s0 in range(0, len(sel), 20):
    ts = [t for t in (tile(r) for r in sel[s0:s0 + 20]) if t is not None]
    if not ts: continue
    while len(ts) % 5: ts.append(np.zeros_like(ts[0]))
    rows = [np.hstack(ts[i:i + 5]) for i in range(0, len(ts), 5)]
    cv2.imwrite(os.path.join(D, 'isl_%02d.jpg' % k), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85]); k += 1
print('sheets', k)
