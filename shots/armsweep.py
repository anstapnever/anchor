# the exact (BVH) left-arm contacts per frame x elbow swivel on the design (the grip DP's ARM_MAP, mechanim.build_grip):
#   blender -b --factory-startup -P armsweep.py -- f0 f1 step tag [PSI=-40:120:10] [FL=f,f,..]   -> out/qa/armsweep_<tag>.npz
#   the wind's map: -- 1806 1840 1 wind PSI=-40:120:2.5 (rebuild it whenever the trunk or the legs change there)
import sys, os, math, time
SH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SH)
A = sys.argv[sys.argv.index('--') + 1:]
f0, f1, st, tag = int(A[0]), int(A[1]), int(A[2]), A[3]
opt = dict(a.split('=') for a in A[4:])
import numpy as np, bpy
from mathutils.bvhtree import BVHTree
import mechpose as MPQ, mech, mechanim as MA
D = float(opt.get('D', 0.0)); SPLIT = float(opt.get('SPLIT', 0.5))
lo_, hi_, stp = (float(x) for x in opt.get('PSI', '-40:120:10').split(':'))
PSIS = np.arange(lo_, hi_ + 1e-6, stp)
if D:
    def bump(t): return D * MA.ss(MA.rng(t, 66.6, 67.1)) * (1.0 - MA.ss(MA.rng(t, 73.6, 74.0)))
    _wc, _hc = MA._wade_channels, MA._hold_channels
    def wc(t):
        ch = _wc(t); b = bump(t); ch['ctw'] += (1 - SPLIT) * b; ch['stw'] += SPLIT * b; return ch
    def hc(t):
        ch = _hc(t); b = bump(t); ch['ctw'] += (1 - SPLIT) * b; ch['stw'] += SPLIT * b; return ch
    MA._wade_channels = wc; MA._hold_channels = hc
OVR = [None]; _gp = MA._grip_psi
MA._grip_psi = lambda t: OVR[0] if OVR[0] is not None else _gp(t)
sc, M = MPQ.build(); B = MPQ.Body(M)
MA.prepare(M, mech)
MA.pelvis_pass(mech, max(1, f0 - 14), min(2160, f1 + 14))


def arm_part(o):
    sg = str(o.get('seg', ''))
    return sg in ('shoulderL', 'elbowL', 'wristL') or sg.startswith(('fingerL', 'thumbL'))


ARM = [o for o in B.objs if arm_part(o) and '_vine_' not in o.name]
OTH = [o for o in B.objs if not arm_part(o) and '_vine_' not in o.name]
print('arm parts', [o.name[5:] for o in ARM], flush=True)
FL = [int(x) for x in opt["FL"].split(",")] if "FL" in opt else None
fs = FL if FL else list(range(f0, f1 + 1, st)); H = np.zeros((len(fs), len(PSIS)), np.int32); WHO = {}
t0 = time.time()
for i, f in enumerate(fs):
    t = MA.tof(f)
    for j, ps in enumerate(PSIS):
        OVR[0] = float(ps); MA.solve(M, mech, t)
        WV = {o.name: B.world(o) for o in ARM + OTH}
        box = {n: (V.min(0), V.max(0)) for n, V in WV.items()}
        tr = {}
        def tree(o):
            if o.name not in tr: tr[o.name] = BVHTree.FromPolygons([tuple(v) for v in WV[o.name]], B.F[o.name], all_triangles=False, epsilon=0.0)
            return tr[o.name]
        n = 0
        for a in ARM:
            la, ha = box[a.name]
            for b in OTH:
                lb, hb = box[b.name]
                if np.any(la > hb + 0.02) or np.any(lb > ha + 0.02): continue
                if MA.allow(a, b, t): continue
                ov = tree(a).overlap(tree(b))
                if ov:
                    n += len(ov); WHO.setdefault((f, float(ps)), []).append('%s/%s %d' % (a.name[5:], b.name[5:], len(ov)))
        H[i, j] = n
    OVR[0] = None
    free = [p for p, h in zip(PSIS, H[i]) if h == 0]
    cur = _gp(t)
    print('f %d t %.2f table psi %s | free %s' % (f, t, '%.1f' % cur if cur is not None else '-',
          ' '.join('%.0f' % p for p in free) if free else 'NONE  (min %d at %.0f: %s)' % (
              H[i].min(), PSIS[int(np.argmin(H[i]))], ', '.join(WHO.get((f, float(PSIS[int(np.argmin(H[i]))])), [])))), flush=True)
np.savez(os.path.join(os.path.dirname(SH), 'out', 'qa', 'armsweep_%s.npz' % tag), f=np.array(fs), psi=PSIS, hits=H)
print('done %.0fs' % (time.time() - t0), flush=True)
