# ANCHOR — fast checks of unit 07's motion (lead). Mech only (builds in seconds), the rig's own evaluated meshes:
#   self overlaps (BVH triangle overlap between parts, mech.qa_allow designed contacts excepted) and the ground (every vertex against
#   the baked heightfield out/track/ground.npz + the thin furniture; only what is above the water counts as visible).
#   blender -b -P shots/mechpose.py -- design 1177-1522 [step] [tag]   solve the design (no bake) and check it
#   blender -b -P shots/mechpose.py -- bake 1177-1522 [step] [tag]     bake the range into the track, then check the track
#   blender -b -P shots/mechpose.py -- track 1177-1522 [step] [tag]    check the baked track
#   blender -b -P shots/mechpose.py -- poses file.json [tag]          {name: set_pose dict} -> self overlaps of each pose
#   blender -b -P shots/mechpose.py -- measure                         foot / hand extents in their contact frames
# Report: out/qa/pose_<tag>.json + a compact print (pairs with frame ranges; ground: part, frames, deepest visible penetration).
import sys, os, math, time, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'):
    q = os.path.join(ROOT, p)
    if q not in sys.path: sys.path.insert(0, q)
import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import env as EV, mech, mechanim as MA, mechplan as MP

SKIP = ('gull', 'chick')           # animated apart from the rig (the film QA checks them)
G_TOL = 0.06                       # metres a vertex may sit below the heightfield before it counts (the grid is 1 m)
W_VIS = -0.4                       # below this under the water line nothing shows (the sea is opaque)


def build():
    sc = EV.reset(); C = EV.coll('MECH'); t0 = time.time(); M = mech.build(C)
    print('mech built %.1fs' % (time.time() - t0), flush=True)
    return sc, M


class Body:
    """the rig's mesh parts with their evaluated LOCAL geometry (modifiers applied once: the parts are rigid)."""
    def __init__(self, M):
        dg = bpy.context.evaluated_depsgraph_get(); self.M = M
        self.objs = [o for o in M['meshes'] if o.type == 'MESH' and not any(s in o.name for s in SKIP)]
        self.V = {}; self.F = {}
        for o in self.objs:
            ev = o.evaluated_get(dg); me = ev.to_mesh()
            self.V[o.name] = np.array([v.co[:] for v in me.vertices], np.float64)
            self.F[o.name] = [tuple(p.vertices) for p in me.polygons]
            ev.to_mesh_clear()
        self.vines = {v.name: k for k, v in enumerate(M['vines'])}
        print('body parts %d, verts %d' % (len(self.objs), sum(len(v) for v in self.V.values())), flush=True)

    def world(self, o):
        m = np.array(mech._wm(o)); return self.V[o.name] @ m[:3, :3].T + m[:3, 3]


def ground_lo(x, y):
    fx, fy, i, j = MP._cells(x, y)
    z = np.minimum(np.minimum(MP.GH[j, i], MP.GH[j, i + 1]), np.minimum(MP.GH[j + 1, i], MP.GH[j + 1, i + 1]))
    return np.maximum(z, MP.furniture_z(x, y))


def _vis_overlaps(ov, Va, Fa, Vb, Fb, t):
    """the overlapping polygon pairs of which at least one polygon is (partly) above the water line (the sea is opaque)."""
    n = 0
    for i, j in ov:
        pa = Va[list(Fa[i])]; pb = Vb[list(Fb[j])]
        za = pa[:, 2].max(); zb = pb[:, 2].max(); c = pa.mean(0)
        if max(za, zb) > MP.water_z(float(c[0]), float(c[1]), t) + W_VIS: n += 1
    return n


def check(B, t, hidden=()):
    """-> (self pairs {(a, b): n visible triangle pairs}, ground {part: (deepest visible penetration, z there)})"""
    WV = {}; box = {}
    for o in B.objs:
        if o.name in hidden: continue
        V = B.world(o); WV[o.name] = (o, V); box[o.name] = (V.min(0), V.max(0))
    names = sorted(WV); trees = {}
    def tree(n):
        if n not in trees: trees[n] = BVHTree.FromPolygons([tuple(v) for v in WV[n][1]], B.F[n], all_triangles=False, epsilon=0.0)
        return trees[n]
    pairs = {}
    for i, a in enumerate(names):
        la, ha = box[a]
        for b in names[i + 1:]:
            lb, hb = box[b]
            if np.any(la > hb + 0.02) or np.any(lb > ha + 0.02): continue
            if MA.allow(WV[a][0], WV[b][0], t): continue
            if t > MA.T_RISE and ('_vine_' in a or '_vine_' in b): continue     # the vines awake: shots/vineqa.py (depth vs the sleep pose)
            ov = tree(a).overlap(tree(b))
            if ov:
                n = _vis_overlaps(ov, WV[a][1], B.F[a], WV[b][1], B.F[b], t)
                if n: pairs[(a, b)] = n
    ground = {}
    for n in names:
        V = WV[n][1]; lo, hi = box[n]
        if hi[2] < W_VIS - 0.01 and not MP.in_dock(float(V[0, 0]), float(V[0, 1])): continue
        g = ground_lo(V[:, 0], V[:, 1])
        wz = np.array([MP.water_z(x, y, t) for x, y in V[::max(1, len(V) // 16), :2]]).max() if len(V) else 0.0
        vis = V[:, 2] > wz + W_VIS
        pen = (g - G_TOL - V[:, 2]) * vis
        k = int(np.argmax(pen))
        if pen[k] > 0: ground[n] = (round(float(pen[k] + G_TOL), 2), round(float(V[k, 2]), 2))
    return pairs, ground


def _ranges(fs):
    out = []
    for f in sorted(fs):
        if out and f - out[-1][1] <= 2: out[-1][1] = f
        else: out.append([f, f])
    return ' '.join('%d' % a if a == b else '%d-%d' % (a, b) for a, b in out)


def report(tag, res, extra=None):
    selfp = {}; grd = {}
    for f, (pairs, ground) in res.items():
        for k, n in pairs.items(): selfp.setdefault(k, []).append((f, n))
        for k, (d, z) in ground.items(): grd.setdefault(k, []).append((f, d, z))
    print('==== POSECHECK %s  frames %d  self pairs %d  ground parts %d' % (tag, len(res), len(selfp), len(grd)))
    for k, v in sorted(selfp.items(), key=lambda kv: kv[1][0][0]):
        print('  SELF %-28s %-28s n %3d  max %4d  frames %s' % (k[0][5:], k[1][5:], len(v), max(x[1] for x in v), _ranges([x[0] for x in v])))
    for k, v in sorted(grd.items(), key=lambda kv: kv[1][0][0]):
        print('  GRND %-28s n %3d  deepest %5.2f  frames %s' % (k[5:], len(v), max(x[1] for x in v), _ranges([x[0] for x in v])))
    os.makedirs(os.path.join(ROOT, 'out', 'qa'), exist_ok=True)
    json.dump(dict(self={'%s|%s' % k: v for k, v in selfp.items()}, ground={k: v for k, v in grd.items()}, extra=extra or {}),
              open(os.path.join(ROOT, 'out', 'qa', 'pose_%s.json' % tag), 'w'))


def run_design(M, B, f0, f1, step, tag):
    MA.prepare(M, mech)
    lo = MA.fr(MA.T_RISE) + 1; hi = max(f1, max(MA.fr(x[0]) for x in MA.VINE_TEAR.values()) + 2)
    if hi >= max(f0, lo):
        bad = MA.pelvis_pass(mech, max(lo, min(f0, MA.fr(min(x[0] for x in MA.VINE_TEAR.values()))) - 12), hi)
        if bad: print('PELVIS BAND CONFLICTS', len(bad), bad[:12], flush=True)
    rest = {v.name: v.matrix_basis.copy() for v in M['vines']}
    VL = {v.name: B.V[v.name] for v in M['vines']}
    VT = MA.vine_tears(M, mech, VL)
    res = {}; t0 = time.time()
    for f in range(f0, f1 + 1, step):
        t = MA.tof(f); MA.solve(M, mech, t)
        vis = MA.vine_pose(M, mech, t, VT, VL, rest)
        res[f] = check(B, t, {n for n, x in vis.items() if x < 0.5})
        if (f - f0) % (24 * step) == 0: print('  f %d  %.0fs' % (f, time.time() - t0), flush=True)
    for v in M['vines']: v.matrix_basis = rest[v.name]
    report(tag, res)


def run_track(M, B, f0, f1, step, tag):
    TR = MA.load(); anim = M['anim']
    assert [o.name for o in anim] == list(TR['names'])
    res = {}
    for f in range(f0, f1 + 1, step):
        if not TR['valid'][f]: continue
        for i, o in enumerate(anim):
            o.location = tuple(float(x) for x in TR['loc'][f, i]); o.rotation_euler = tuple(float(x) for x in TR['rot'][f, i])
        for k, v in enumerate(M['vines']):
            v.location = tuple(float(x) for x in TR['vine_loc'][f, k]); v.rotation_euler = tuple(float(x) for x in TR['vine_rot'][f, k])
        hid = {v.name for k, v in enumerate(M['vines']) if TR['vine_vis'][f, k] < 0.5}
        res[f] = check(B, MA.tof(f), hid)
    report(tag, res)


def measure(M):
    P = M['parts']
    for side in ('L', 'R'):
        S = mech._wm(P['sole' + side]); Si = np.array(S.inverted())
        for nm in ('foot' + side,) + tuple(n for n in P if n.startswith('toe') and n.endswith(side)):
            o = P.get(nm)
            if o is None or o.type != 'MESH': continue
            me = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
            V = np.array([(Matrix(Si.tolist()) @ mech._wm(o) @ v.co)[:] for v in me.vertices])
            print('%s in sole frame: x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f' % (nm, *V[:, 0].min(0, keepdims=True), V[:, 0].max(),
                  V[:, 1].min(), V[:, 1].max(), V[:, 2].min(), V[:, 2].max()))


if __name__ == '__main__':
    A = sys.argv[sys.argv.index('--') + 1:]
    mode = A[0]
    sc, M = build(); B = Body(M)
    if mode in ('design', 'bake', 'track'):
        f0, f1 = (int(x) for x in A[1].split('-')); step = int(A[2]) if len(A) > 2 else 1
        tag = A[3] if len(A) > 3 else '%s_%d_%d' % (mode, f0, f1)
        if mode == 'design': run_design(M, B, f0, f1, step, tag)
        else:
            if mode == 'bake': MA.bake(M, mech, f0, f1)
            run_track(M, B, f0, f1, step, tag)
    elif mode == 'poses':
        poses = json.load(open(A[1])); tag = A[2] if len(A) > 2 else 'poses'; res = {}
        for i, (nm, P) in enumerate(poses.items()):
            mech.set_pose(M, P); pairs, _ = check(B, 0.0)
            print('POSE %-24s %s' % (nm, ', '.join('%s/%s:%d' % (a[5:], b[5:], n) for (a, b), n in sorted(pairs.items())) or 'clean'), flush=True)
    elif mode == 'measure': measure(M)
