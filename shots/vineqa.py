# ANCHOR — the vines of the rise (lead). Every vine must stay clean while it is on its host (no deeper into another segment of the
# body than it rests in the approved sleep pose, + VQ_TOL) and while it flies after its tear (no visible contact at all). This script
#   1. measures the sleep baseline (t = 48.4, before the head lifts): per vine and body part, how deep its vertices sit inside the part;
#   2. checks the attached phase from 48.4 to the vine's tear;
#   3. for the flight, tries kick candidates and reports for each the clean flight time (until the first visible contact) and when the
#      vine is under the water.
#   blender -b -P shots/vineqa.py -- [search]      -> out/qa/vineqa.json + a compact print
# Depth of a vertex inside a part = distance to the part's nearest surface point when it lies behind that face (closed meshes).
import sys, os, math, time, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'):
    q = os.path.join(ROOT, p)
    if q not in sys.path: sys.path.insert(0, q)
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import mechpose as MPQ, mechanim as MA, mechplan as MP, mech

VQ_TOL = 0.2           # m deeper than in the sleep pose that an attached vine may sit inside another segment (~2 px in a wide)
T_BASE = 48.4
T_END = float(os.environ.get('VQ_END', '52.6'))
FLY_CLEAR = 0.2      # s a torn vine has to come off the surface it rested on


def depth_into(tree, V, lo, hi):
    """max depth of the points V (n,3) inside the closed mesh of `tree` (bbox lo/hi prefilter); 0 if none inside."""
    m = np.all((V >= lo - 0.05) & (V <= hi + 0.05), axis=1)
    best = 0.0
    for v in V[m]:
        loc, nor, idx, dist = tree.find_nearest(Vector(v))
        if loc is None: continue
        if (Vector(v) - loc).dot(nor) < 0.0 and dist > best: best = dist
    return best


def visible(V, t):
    if len(V) == 0: return V
    wz = MP.water_z(float(V[0, 0]), float(V[0, 1]), t)
    return V[V[:, 2] > wz + MPQ.W_VIS]


def main(search):
    sc, M = MPQ.build(); B = MPQ.Body(M)
    MA.prepare(M, mech)
    f_base, f_end = MA.fr(T_BASE), MA.fr(T_END)
    MA.pelvis_pass(mech, MA.fr(MA.T_RISE) + 1, f_end + 2)
    vines = list(M['vines']); body = [o for o in B.objs if o.get('kind') != 'growth' and 'vine' not in o.name]
    rest = {v.name: v.matrix_basis.copy() for v in vines}
    VL = {v.name: B.V[v.name] for v in vines}
    seg = {o.name: str(o.get('seg')) for o in B.objs}
    # the body per frame: world vertices + lazily built trees
    frames = {}
    t0 = time.time()
    for f in range(f_base, f_end + 1):
        t = MA.tof(f); MA.solve(M, mech, t)
        frames[f] = {o.name: B.world(o).astype(np.float64) for o in body}
        frames[f]['_vw'] = {v.name: B.world(v) for v in vines}          # attached vine positions (rest basis)
    print('body cached %d frames %.0fs' % (len(frames), time.time() - t0), flush=True)
    trees = {}
    def tree(f, n):
        k = (f, n)
        if k not in trees:
            trees[k] = BVHTree.FromPolygons([tuple(v) for v in frames[f][n]], B.F[n], all_triangles=False, epsilon=0.0)
        return trees[k]
    def box(f, n):
        V = frames[f][n]; return V.min(0), V.max(0)
    # 1. baseline
    base = {}
    for v in vines:
        Vw = frames[f_base]['_vw'][v.name]
        for o in body:
            if seg[o.name] == seg[v.name]: continue
            lo, hi = box(f_base, o.name)
            if np.any(Vw.min(0) > hi + 0.05) or np.any(lo > Vw.max(0) + 0.05): continue
            d = depth_into(tree(f_base, o.name), Vw, lo, hi)
            if d > 0: base[(v.name, o.name)] = d
    print('baseline pairs', len(base), flush=True)
    # 2. attached phase
    for kv in [x for x in os.environ.get('VQ_TEAR', '').split(',') if x]:
        nm, tt = kv.split(':'); sp = list(MA.VINE_TEAR[nm]); sp[0] = float(tt); MA.VINE_TEAR[nm] = tuple(sp)
    only = [x for x in os.environ.get('VQ_ONLY', '').split(',') if x]
    if only: vines = [v for v in vines if MA.vine_key(v.name) in only]
    VT = MA.vine_tears(M, mech, VL)
    out = {'attached': {}, 'flight': {}}; dtear = {}
    for v in vines:
        tt = VT[v.name]['t'] if v.name in VT else T_END
        worst = {}
        for f in range(f_base + 1, min(MA.fr(tt), f_end) + 1):
            t = MA.tof(f); Vw = visible(frames[f]['_vw'][v.name], t)
            if len(Vw) == 0: continue
            for o in body:
                if seg[o.name] == seg[v.name]: continue
                lo, hi = box(f, o.name)
                if np.any(Vw.min(0) > hi + 0.05) or np.any(lo > Vw.max(0) + 0.05): continue
                d = depth_into(tree(f, o.name), Vw, lo, hi)
                if d > base.get((v.name, o.name), 0.0) + VQ_TOL:
                    w = worst.setdefault(o.name, [f, f, 0.0]); w[1] = f; w[2] = max(w[2], d - base.get((v.name, o.name), 0.0))
        out['attached'][v.name] = {k: [int(a), int(b), round(c, 2)] for k, (a, b, c) in worst.items()}
        print('ATTACHED %-22s tear %.2f  %s' % (v.name[10:], tt, ', '.join('%s %d-%d +%.2f' % (k[5:], a, b, c) for k, (a, b, c) in worst.items()) or 'clean'), flush=True)
    # 3. flights
    cands = {'drop': (0.0, 0.0, -8.0), 'out': (9.0, 0.0, 3.0), 'fwd': (0.0, -10.0, 3.0), 'outfwd': (7.0, -7.0, 3.0), 'outup': (6.0, 0.0, 8.0),
             'outdown': (8.0, 0.0, -6.0), 'back': (0.0, 6.0, 2.0), 'slide': (0.0, 0.0, -15.0), 'outfast': (14.0, 0.0, 2.0),
             'fwdfast': (0.0, -15.0, 3.0), 'fwdup': (0.0, -10.0, 8.0), 'outfwdup': (8.0, -8.0, 7.0), 'fwddown': (0.0, -10.0, -6.0),
             'fwddownfast': (0.0, -14.0, -10.0), 'indown': (-6.0, 0.0, -8.0), 'outfwddown': (7.0, -7.0, -6.0),
             'fwdupfast': (0.0, -20.0, 10.0), 'fwdfast2': (0.0, -25.0, 6.0), 'fwdhigh': (0.0, -18.0, 14.0)}
    for v in vines:
        if v.name not in VT: continue
        tt = VT[v.name]['t']; res = {}
        if search:
            specs = {'%s/%.1f/%.1f/%.1f' % (cn, tilt, inh, dr): (tt, k, tilt, inh, dr) for cn, k in cands.items()
                     for tilt, inh in ((0.0, 1.0), (0.6, 1.0), (-0.6, 1.0), (0.0, 0.5), (0.6, 0.5), (-0.6, 0.5)) for dr in (0.0, 1.0)}
        else: specs = {'table': MA.VINE_TEAR[MA.vine_key(v.name)]}
        for key, spec in specs.items():
            clean_until = None; sub = None; what = None
            for f in range(MA.fr(tt), f_end + 1):
                t = MA.tof(f); tau = t - tt
                W, vis = MA.vine_flight(t, VT, v.name, VL[v.name], spec=spec)
                if W is None: continue
                last = W
                if vis < 0.5: sub = tau; break
                Vv = visible(VL[v.name] @ W[:3, :3].T + W[:3, 3], t)
                if len(Vv) == 0: continue
                hit = False
                for o in body:
                    lo, hi = box(f, o.name)
                    if np.any(Vv.min(0) > hi + 0.05) or np.any(lo > Vv.max(0) + 0.05): continue
                    if (v.name, o.name) not in dtear:       # the resting contact at the tear: no deeper than that (+ VQ_TOL)
                        V0 = visible(frames[MA.fr(tt)]['_vw'][v.name], tt); l0, h0 = box(MA.fr(tt), o.name)
                        dtear[(v.name, o.name)] = depth_into(tree(MA.fr(tt), o.name), V0, l0, h0) if len(V0) else 0.0
                    allow_d = dtear[(v.name, o.name)] + (VQ_TOL if dtear[(v.name, o.name)] > 0 else 0.08)
                    dd = depth_into(tree(f, o.name), Vv, lo, hi)
                    if dd > allow_d: hit = True; what = '%s %.2f' % (o.name[5:], dd); break
                # the set: a visible vertex under the ground (quay, walls) counts too
                g = MPQ.ground_lo(Vv[:, 0], Vv[:, 1])
                if not hit and np.any(Vv[:, 2] < g - 0.1): hit = True; what = 'ground %.2f' % float(np.max(g - Vv[:, 2]))
                if hit: clean_until = tau; break
            if sub is None and clean_until is None and not search:
                Vl = VL[v.name] @ last[:3, :3].T + last[:3, 3]
                what = 'end: top z %.1f at (%.0f, %.0f)' % (Vl[:, 2].max(), Vl[:, 0].mean(), Vl[:, 1].mean())
            res[key] = (clean_until, sub, what)
        out['flight'][v.name] = res
        best = sorted(res.items(), key=lambda kv: (-(kv[1][0] if kv[1][0] is not None else 9.0), kv[1][1] if kv[1][1] is not None else 9.0))
        if search and best and best[0][1][0] is None and best[0][1][1] is not None:
            cn, tilt, inh, dr = best[0][0].split('/')
            print('PICK %r: (%.2f, %r, %s, %s, %s),' % (MA.vine_key(v.name), tt, cands[cn], tilt, inh, dr), flush=True)
        print('FLIGHT %-22s tear %.2f  ' % (v.name[10:], tt) + '  '.join('%s clean %s sub %s [%s]' % (k, 'all' if a is None else '%.2f' % a, '-' if b is None else '%.2f' % b, w) for k, (a, b, w) in best[:int(os.environ.get('VQ_SHOW', '5'))]), flush=True)
    json.dump({'attached': out['attached'], 'flight': {k: {c: list(x) for c, x in v.items()} for k, v in out['flight'].items()}},
              open(os.path.join(ROOT, 'out', 'qa', 'vineqa.json'), 'w'))
    return out


if __name__ == '__main__':
    A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    main('search' in A)        # without 'search': verify the VINE_TEAR table as it is
