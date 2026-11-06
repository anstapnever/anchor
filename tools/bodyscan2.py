# ANCHOR - drops drawn over the mech's body, with everything that can hide the body (06.11). bodyscan.py v1 cast the camera
# rays against the mech alone: a drop over the sea in front of a leg standing waist-deep, or over a dock wall with the leg
# behind it, counted as "over the body" (683 elements, s34's plough splash 56/60). Here a point of a drop element is OVER the
# body only when the first surface right behind it on the camera ray is the mech: not the water (analytic, mechplan.water_z:
# a mech hit under the water line is hidden, a drop point under it too), not an FX water mass, the chain, the port, the
# city, nor anything else the shot renders (static objects in one BVH per shot, animated ones in one BVH per frame, both from
# the evaluated meshes). A point the camera ray reaches only after another surface is hidden and never counts.
# Writes <out.json> (per object: n, per element its frames over the body: [f, sx, sy, rpx, nover, gap m]) and a summary.
#   blender -b -P tools/bodyscan2.py -- <out.json>
import sys, os, time, json, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'):
    q = os.path.join(ROOT, p)
    if q not in sys.path: sys.path.insert(0, q)
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import film, lenscull as LC, fx as FXM, mechplan as MP

A = sys.argv[sys.argv.index('--') + 1:]
OUT = A[0]
t0 = time.time()
W = film.build(24, 100)
ids = [s[0] for s in film.SHOTS]
film.key_shots(W, ids)
print('built+keyed %.0fs' % (time.time() - t0), flush=True)
sc = W['sc']; FPS = 24.0
sets_of = {}; shot_of = {}
for s, a, b, sets in film.SHOTS:
    fa, fb = film.frames_of(s)
    for f in range(fa, fb + 1): sets_of[f] = set(sets.split()); shot_of[f] = s
home = {}
for k, c in W['C'].items():
    for o in c.all_objects: home.setdefault(o.name, set()).add(k)
cams = LC._cams(W)
f_first, f_last = min(cams), max(cams)

Vt = FXM.tpl_drop()[0]
PROBE = [int(np.argmax(Vt[:, 2])), int(np.argmin(Vt[:, 2])), int(np.argmax(Vt[:, 0])), int(np.argmin(Vt[:, 0])),
         int(np.argmax(Vt[:, 1])), int(np.argmin(Vt[:, 1]))]
M_TPL = LC.M_TPL
assert len(Vt) == M_TPL

# ---- the drop flipbooks (the subjects) and the frames to test
need = {}; objs = {}
for k, c in W['C'].items():
    for o in c.all_objects:
        if o.type != 'MESH' or o.name in objs or not LC.PAT.search(o.name): continue
        nv = len(o.data.vertices)
        if nv == 0 or nv % M_TPL: continue
        objs[o.name] = o
        sets = home.get(o.name, {k})
        dr = LC._drawings(o, nv)
        for j, (fa, i) in enumerate(dr):
            fb = dr[j + 1][0] if j + 1 < len(dr) else f_last + 1
            fa = max(fa, f_first)
            if fb <= fa: continue
            for f in LC._shown(o, fa, fb):
                ss = sets_of.get(f, set())
                if f in cams and 'MECH' in ss and (ss & sets): need.setdefault(f, []).append((o.name, i))
print('drop objects', len(objs), 'frames to test', len(need), flush=True)

mech = [o for o in W['C']['MECH'].all_objects if o.type == 'MESH']
mech_names = {o.name for o in mech}
SKIP = re.compile(r'^SEA$|rain|kira|star|bolt|spark|flash|flare|_arc$', re.I)


def animated(o):
    x = o
    while x is not None:
        ad = x.animation_data
        if ad is not None and (ad.action is not None or len(ad.drivers)): return True
        x = x.parent
    d = getattr(o, 'data', None)
    sk = getattr(d, 'shape_keys', None) if d is not None else None
    if sk is not None and sk.animation_data is not None: return True
    if d is not None and getattr(d, 'animation_data', None) is not None: return True
    return False


occ_static = {}; occ_dyn = {}
for k, c in W['C'].items():
    if k == 'MECH': continue
    for o in c.all_objects:
        if o.type not in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT') or o.name in objs or o.name in mech_names or SKIP.search(o.name):
            continue
        (occ_dyn if animated(o) else occ_static)[o.name] = o
print('occluders: static %d, animated %d' % (len(occ_static), len(occ_dyn)), flush=True)


def tris_of(oe, Mw=None):
    try: me = oe.to_mesh()
    except Exception: return None
    if me is None or not len(me.vertices): oe.to_mesh_clear(); return None
    me.calc_loop_triangles()
    nv = len(me.vertices); co = np.empty(nv * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    nt = len(me.loop_triangles)
    if nt == 0: oe.to_mesh_clear(); return None
    tri = np.empty(nt * 3, np.int32); me.loop_triangles.foreach_get('vertices', tri)
    oe.to_mesh_clear()
    M = np.array(oe.matrix_world if Mw is None else Mw)
    return co.astype(np.float64) @ M[:3, :3].T + M[:3, 3], tri.reshape(-1, 3)


def bvh_of(parts):
    if not parts: return None, 0
    VV = []; TT = []; off = 0
    for V, T in parts: VV.append(V); TT.append(T + off); off += len(V)
    V = np.vstack(VV); T = np.vstack(TT)
    return BVHTree.FromPolygons([tuple(v) for v in V], [tuple(t) for t in T], all_triangles=True), len(T)


def bbox_mind(o, C):
    M = np.array(o.matrix_world); B = np.array([tuple(v) for v in o.bound_box]) @ M[:3, :3].T + M[:3, 3]
    lo = B.min(0); hi = B.max(0); q = np.clip(C, lo, hi)
    return float(np.linalg.norm(q - C))


geo = {}


def pts(o, i):
    key = (o.name, i)
    if key not in geo:
        nv = len(o.data.vertices); n = nv // M_TPL
        V = np.empty(nv * 3, np.float32)
        (o.data.vertices if i is None else o.data.shape_keys.key_blocks[i].data).foreach_get('co', V)
        V = V.reshape(n, M_TPL, 3).astype(np.float64)
        Mw = np.array(LC._world(o)); Aw = Mw[:3, :3]; tw = Mw[:3, 3]
        cc = V.mean(1)
        r = np.linalg.norm(V - cc[:, None, :], axis=2).max(1) * float(np.max(np.linalg.norm(Aw, axis=0)))
        P = np.concatenate([cc[:, None, :], V[:, PROBE, :]], 1) @ Aw.T + tw
        geo[key] = (P, r)
    return geo[key]


def first_hit(trees, C, u, dmax=1e9):
    best = None
    for t in trees:
        if t is None: continue
        h = t.ray_cast(C, u, dmax)
        if h[0] is not None and (best is None or h[3] < best[3]): best = h
    return best


res = {}; stats = {'hidden': 0, 'water': 0, 'occl': 0, 'over': 0, 'free': 0}
cur = None; st_tree = None; tb = time.time(); nray = 0
for kf, f in enumerate(sorted(need)):
    sid = shot_of[f]; t = (f - 1) / FPS
    if sid != cur:
        film.apply_sets(W, sid); cur = sid
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
        Pc0 = cams[f][0]
        parts = []
        for o in occ_static.values():
            if not (home.get(o.name, set()) & sets_of[f]) or o.hide_render: continue
            if bbox_mind(o, Pc0) > 3000.0: continue
            r_ = tris_of(o.evaluated_get(dg))
            if r_ is not None: parts.append(r_)
        st_tree, nst = bvh_of(parts)
        print('shot %s: static occluder tris %d (%d objects)' % (sid, nst, len(parts)), flush=True)
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    mp = []
    for ob in mech:
        if ob.hide_render: continue
        r_ = tris_of(ob.evaluated_get(dg))
        if r_ is not None: mp.append(r_)
    if not mp: continue
    m_tree, nm = bvh_of(mp)
    Vm = np.vstack([v for v, _ in mp])
    Pc, Rc, fpx = cams[f]
    dmax_m = float(np.linalg.norm(Vm - Pc, axis=1).max()) + 50.0
    dp = []
    for o in occ_dyn.values():
        if not (home.get(o.name, set()) & sets_of[f]) or o.hide_render: continue
        if bbox_mind(o, Pc) > dmax_m: continue
        r_ = tris_of(o.evaluated_get(dg))
        if r_ is not None: dp.append(r_)
    d_tree, nd = bvh_of(dp)
    v = (Vm - Pc) @ Rc; dep = -v[:, 2]; okv = dep > 0.5
    sx_m = v[okv, 0] / dep[okv] * fpx; sy_m = v[okv, 1] / dep[okv] * fpx
    bx0, bx1, by0, by1 = sx_m.min(), sx_m.max(), sy_m.min(), sy_m.max()
    C = Vector(tuple(Pc))
    for name, i in need[f]:
        o = objs[name]; P, r = pts(o, i)
        alive = r > 1e-5
        c = P[:, 0, :]; vc = (c - Pc) @ Rc; dc = -vc[:, 2]
        front = dc > 0.05; dd = np.where(front, dc, 1.0)
        sx = vc[:, 0] / dd * fpx; sy = vc[:, 1] / dd * fpx; rpx = r / dd * fpx
        cand = alive & front & (sx + rpx > bx0) & (sx - rpx < bx1) & (sy + rpx > by0) & (sy - rpx < by1) & \
            (np.abs(sx) < 960 + rpx) & (np.abs(sy) < 540 + rpx)
        for e in np.nonzero(cand)[0]:
            nover = 0; gaps = []
            for q in range(7):
                p = P[e, q]
                if p[2] < MP.water_z(float(p[0]), float(p[1]), t) - 0.02: stats['water'] += 1; continue
                d = p - Pc; L = float(np.linalg.norm(d))
                if L < 1e-3: continue
                u = Vector(tuple(d / L)); nray += 1
                hm = m_tree.ray_cast(C, u)
                ho = first_hit((st_tree, d_tree), C, u)
                dm = hm[3] if hm[0] is not None else None
                do = ho[3] if ho is not None else None
                first = min(x for x in (dm, do, 1e18) if x is not None)
                if first < L - 0.02: stats['hidden'] += 1; continue
                if dm is None: stats['free'] += 1; continue
                if do is not None and do < dm: stats['occl'] += 1; continue
                H = hm[0]
                if H.z < MP.water_z(H.x, H.y, t) - 0.02: stats['water'] += 1; continue
                nover += 1; gaps.append(dm - L)
            if nover:
                stats['over'] += 1
                res.setdefault(name, {}).setdefault(int(e), []).append([int(f), round(float(sx[e]), 1), round(float(sy[e]), 1),
                                                                        round(float(rpx[e]), 1), nover, round(float(min(gaps)), 2)])
    if kf % 50 == 0:
        print('frame %d (%s) %d/%d  mech tris %d  dyn occluder tris %d  rays %d  %.0fs' % (f, sid, kf, len(need), nm, nd, nray,
              time.time() - tb), flush=True)

json.dump({'res': res, 'n': {k: len(o.data.vertices) // M_TPL for k, o in objs.items()}}, open(OUT, 'w'))
print('point verdicts', stats, flush=True)
print('=== OVER THE BODY (object: elements over / n; shots; frames; max px radius; min gap m)')
for name in sorted(res, key=lambda k: -len(res[k])):
    els = res[name]; fr_ = sorted({x[0] for v in els.values() for x in v})
    shots = sorted({shot_of[f] for f in fr_})
    mx = max(x[3] for v in els.values() for x in v); mg = min(x[5] for v in els.values() for x in v)
    print('OVER %-34s %4d/%4d  %s  f%d-%d (%d frames)  max r %.0f px  min gap %.1f m' % (
        name, len(els), len(objs[name].data.vertices) // M_TPL, ','.join(shots), fr_[0], fr_[-1], len(fr_), mx, mg), flush=True)
for f in (1606, 1609, 1612, 1613, 1664, 1667):
    hits = [(name, e, x) for name, els in res.items() for e, v in els.items() for x in v if x[0] == f]
    print('AT', f, len(hits), [(h[0], h[1]) for h in hits][:16], flush=True)
print('BODYSCAN2 DONE %.0fs' % (time.time() - t0), flush=True)
