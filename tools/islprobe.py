# ANCHOR - which object (and which element of an element flipbook) draws each water island on the mech's body that
# maskana.py found: camera rays through the island's sample pixels against every surface on the ray (transparent ones too);
# the visible one is the hit whose camera z matches the pass's z depth at that pixel - never a listed "behind" element cut there
# (matte R > 0.5 inside its window: the render does not draw it). Built and keyed as the final render.
#   blender -b -P tools/islprobe.py -- <islands.json> <out.json> [kinds: front|all]
# hit: [object, element, polygon, material, camera z, element centre, verts per element, dp at the hit, world point]
import sys, os, time, json, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'):
    q = os.path.join(ROOT, p)
    if q not in sys.path: sys.path.insert(0, q)
import bpy
import numpy as np
from mathutils import Vector
import film

A = sys.argv[sys.argv.index('--') + 1:]
J = json.load(open(A[0])); OUT = A[1]; KIND = A[2] if len(A) > 2 else 'front'
isl = [r for r in J['res'] if r['src'] == 'water' and (KIND == 'all' or r['kind'] == 'front')]
t0 = time.time()
W = film.build(16, 100)
ids = [s[0] for s in film.SHOTS]
film.key_shots(W, ids)
print('built+keyed %.0fs' % (time.time() - t0), flush=True)
sc = W['sc']
shot_of = {}
for sid in ids:
    f0, f1 = film.frames_of(sid)
    for f in range(f0, f1 + 1): shot_of[f] = sid
rx, ry = 1920, 1080
EL = {}; NV = {}


def elem_size(o):
    """vertices per element of an element flipbook (the per-element 'seed' attribute runs), 0 for a plain mesh."""
    if o.name in EL: return EL[o.name]
    m = 0
    me = o.data
    a = me.attributes.get('seed') if me is not None and hasattr(me, 'attributes') else None
    nv = len(me.vertices) if me is not None else 0
    if a is not None and a.domain == 'POINT' and nv > 1:
        s = np.empty(nv, np.float32); a.data.foreach_get('value', s)
        ch = np.nonzero(np.abs(np.diff(s)) > 1e-7)[0]
        if len(ch):
            m0 = int(ch[0]) + 1
            if nv % m0 == 0 and np.all((ch + 1) % m0 == 0): m = m0
    EL[o.name] = m; NV[o.name] = nv
    return m


# the render's 'behind the mech' cut (shots/bodyfx.json 'behind' + out/matte): a listed element inside its window is not drawn
# where the matte R covers the pixel, so such a hit can never be the visible surface - the march goes on past it. Without
# this a cut element lying at the same depth as the uncut one really drawn there took the blame (06.11: listed crests and
# jets kept 'showing' in s33-s34 while their unlisted neighbours stayed on the armour).
try: BH = json.load(open(os.path.join(ROOT, 'shots', 'bodyfx.json'), encoding='utf-8')).get('behind', {})
except Exception as ex: BH = {}; print('no behind list:', ex, flush=True)
MT = {}


def matte_r(f, x, y):
    if f not in MT:
        MT.clear(); a = None
        p = os.path.join(ROOT, 'out', 'matte', 'm%04d.png' % f)
        if os.path.exists(p):
            im = bpy.data.images.load(p, check_existing=False)
            try:
                im.colorspace_settings.name = 'Non-Color'; im.alpha_mode = 'CHANNEL_PACKED'
                w_, h_ = im.size
                a = np.empty(w_ * h_ * 4, np.float32); im.pixels.foreach_get(a); a = a.reshape(h_, w_, 4)[::-1].copy()
            finally: bpy.data.images.remove(im)
        MT[f] = a
    a = MT[f]
    if a is None: return 0.0
    h_, w_ = a.shape[:2]
    return float(a[min(h_ - 1, int(y * h_ / ry)), min(w_ - 1, int(x * w_ / rx)), 0])


def elem_of(ob, idx, dg):
    m = elem_size(ob)
    if not m: return None
    try: return int(ob.evaluated_get(dg).data.polygons[idx].vertices[0]) // m
    except Exception: return None


def is_cut(ob, idx, dg, f, x, y):
    d = BH.get(ob.name)
    if not d: return False
    e = elem_of(ob, idx, dg)
    rec = d['el'].get(str(e)) if e is not None else None
    if not rec or not (rec['win'][0] <= f <= rec['win'][1]): return False
    return matte_r(f, x, y) > 0.5


by_f = {}
for k, r in enumerate(isl): by_f.setdefault(r['f'], []).append(k)
out = []
cur = None
for f in sorted(by_f):
    sid = shot_of[f]
    if sid != cur: film.apply_sets(W, sid); cur = sid
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    cam = sc.camera; Mc = cam.matrix_world
    fr = [Mc @ v for v in cam.data.view_frame(scene=sc)]
    org = Mc.translation.copy(); fwd = -(Mc.to_3x3() @ Vector((0, 0, 1))).normalized()
    for k in by_f[f]:
        r = isl[k]; hits_all = []
        for (x, y, zd) in r['smp']:
            u = (x + 0.5) / rx; v = (y + 0.5) / ry
            top = fr[3].lerp(fr[0], u); bot = fr[2].lerp(fr[1], u)
            d = (top.lerp(bot, v) - org).normalized()
            o = org.copy(); best = None; seq = []; cbest = None
            for _ in range(32):
                ok, loc, nor, idx, ob, mx = sc.ray_cast(dg, o, d)
                if not ok: break
                z = (loc - org).dot(fwd)
                err = abs(z - zd)
                if is_cut(ob, idx, dg, f, x, y):
                    seq.append((ob.name, round(z, 2), 'cut'))
                    if cbest is None or err < cbest[0]: cbest = (err, ob.name, elem_of(ob, idx, dg), round(z, 2))
                    if z > zd + max(1.0, 0.03 * zd): break
                    o = loc + d * 0.01
                    continue
                seq.append((ob.name, round(z, 2)))
                if best is None or err < best[0]:
                    m = elem_size(ob)
                    e = None; cen = None
                    if m:
                        try:
                            me = ob.evaluated_get(dg).data
                            e = int(me.polygons[idx].vertices[0]) // m
                            Vv = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', Vv)
                            cen = [round(float(x), 5) for x in Vv.reshape(-1, 3)[e * m:(e + 1) * m].astype(np.float64).mean(0)]
                        except Exception: e = None
                    mat = '-'
                    try:
                        me = ob.evaluated_get(dg).data; mi = me.polygons[idx].material_index
                        mat = me.materials[mi].name if me.materials and mi < len(me.materials) and me.materials[mi] else '-'
                    except Exception: pass
                    dpx = None
                    try:
                        me = ob.evaluated_get(dg).data; a = me.attributes.get('dp')
                        pv = list(me.polygons[idx].vertices)
                        if a is not None and a.domain == 'POINT' and len(pv) == 3:
                            lo = mx.inverted() @ loc
                            A_, B_, C_ = [me.vertices[v].co.copy() for v in pv]
                            v0 = B_ - A_; v1 = C_ - A_; v2 = lo - A_
                            d00 = v0.dot(v0); d01 = v0.dot(v1); d11 = v1.dot(v1); d20 = v2.dot(v0); d21 = v2.dot(v1)
                            den = d00 * d11 - d01 * d01
                            bv = (d11 * d20 - d01 * d21) / den if abs(den) > 1e-12 else 1 / 3
                            bw = (d00 * d21 - d01 * d20) / den if abs(den) > 1e-12 else 1 / 3
                            ws = (1 - bv - bw, bv, bw)
                            dpx = [round(sum(ws[i] * a.data[pv[i]].vector[c] for i in range(3)), 4) for c in range(3)]
                    except Exception: dpx = None
                    best = (err, ob.name, e, int(idx), mat, round(z, 2), cen, m, dpx, [round(loc.x, 3), round(loc.y, 3), round(loc.z, 3)])
                if z > zd + max(1.0, 0.03 * zd): break
                o = loc + d * 0.01
            tol = max(0.3, 0.015 * zd)
            rec = {'px': [x, y], 'zd': zd, 'hit': list(best[1:]) if best and best[0] <= tol else None,
                   'err': round(best[0], 3) if best else None, 'seq': seq[:12]}
            # a cut element matching the pixel's depth better than anything drawn: the cut did not happen there (or the
            # drawn surface is missing from the ray) - reported, never taken as the hit
            if cbest and cbest[0] <= tol and (best is None or best[0] > cbest[0]): rec['cutvis'] = [cbest[1], cbest[2], cbest[3], round(cbest[0], 3)]
            hits_all.append(rec)
        out.append({'i': k, 'f': f, 'shot': r['shot'], 'area': r['area'], 'c': r['c'], 'samples': hits_all})
    print('frame %d %s islands %d  %.0fs' % (f, sid, len(by_f[f]), time.time() - t0), flush=True)
json.dump({'islands': out, 'esize': EL, 'nv': NV, 'scale': J.get('scale', 1.0)}, open(OUT, 'w'), indent=0)
# summary: objects (elements) drawing the islands
agg = {}
for r in out:
    for s in r['samples']:
        if s['hit'] is None: agg.setdefault(('?', None), set()).add(r['f']); continue
        agg.setdefault((s['hit'][0], s['hit'][1] is not None), set()).add(r['f'])
for (name, el), fs in sorted(agg.items(), key=lambda kv: -len(kv[1])):
    fs = sorted(fs)
    print('ISL %-36s %s  frames %d: %s' % (name, 'elements' if el else ('plain' if el is not None else ''), len(fs), fs[:30]), flush=True)
cv = collections.Counter((s['cutvis'][0], s['cutvis'][1]) for r in out for s in r['samples'] if s.get('cutvis'))
print('CUTVIS %d samples (a cut element matches the depth better than any drawn one): %s' % (sum(cv.values()), cv.most_common(12)), flush=True)
print('ISLPROBE DONE %.0fs' % (time.time() - t0), flush=True)
