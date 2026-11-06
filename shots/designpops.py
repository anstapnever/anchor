# ANCHOR — pops in the mech design (numpy rig, no Blender): the same test as shots/popcheck.py (a frame whose deviation from the
# midpoint of its neighbours spikes over the local level and a floor) on the design's world points and limb directions: pelvis,
# chest, head, shoulders, elbows, wrists (FK), hips, knees, ankles, soles (IK legs), thigh / shin / foot directions.
#   python shots/designpops.py 49.05 63.38 [all]
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import rigmath as RM, mechanim as MA, designcheck as DC, popcheck as PC

POP_K, POS_FLOOR, DIR_FLOOR = PC.POP_K, PC.POS_FLOOR, PC.ROT_FLOOR


def sample(t, Stub):
    D = MA.design(t, Stub); P = D['pose']; F = RM.frames(P); pts = {}; dirs = {}
    for n in ('pelvis', 'chest', 'head', 'shoulderL', 'shoulderR', 'elbowL', 'elbowR', 'wristL', 'wristR'):
        pts[n] = F[n][:3, 3].copy()
    dirs['head'] = F['head'][:3, :3] @ np.array((0.0, -1.0, 0.0)); dirs['chest'] = F['chest'][:3, :3] @ np.array((0.0, -1.0, 0.0))
    for sd in ('L', 'R'):
        ft = D['legs'].get(sd)
        if ft is None: continue
        L = RM.leg(P, ft, sd, F)
        pts['hip' + sd] = L['H']; pts['knee' + sd] = L['K']; pts['ankle' + sd] = L['A']; pts['sole' + sd] = np.asarray(ft['p'], float)
        dirs['thigh' + sd] = (L['K'] - L['H']) / np.linalg.norm(L['K'] - L['H'])
        dirs['shin' + sd] = (L['A'] - L['K']) / np.linalg.norm(L['A'] - L['K'])
        dirs['foot' + sd] = RM.foot_R(ft) @ np.array((0.0, -1.0, 0.0))
    for sd in ('L', 'R'):
        a = D['arms'].get(sd)
        if a is not None and a[3] > 0.01:
            A = RM.arm(P, sd, a[0], a[1], a[2], F)
            for k in ('E', 'W', 'K'):
                if k in A: pts['ik_' + k + sd] = np.asarray(A[k], float)
    return pts, dirs


def run(t0, t1, all_frames=False, quiet=False):
    MA.prepare_np(DC.Stub.POSES)
    f0, f1 = MA.fr(t0), MA.fr(t1)          # frames f0 .. f1 are tested; f0 - 1 and f1 + 1 must be designed too
    MA.pelvis_pass(DC.Stub, max(MA.fr(MA.T_RISE) + 1, f0 - 13), f1 + 1)
    show = None if all_frames else PC.shown_frames(); cuts = PC.cut_frames()
    S = [sample(MA.tof(f), DC.Stub) for f in range(f0 - 1, f1 + 2)]
    found = []
    keys_p = sorted(set().union(*[s[0].keys() for s in S])); keys_d = sorted(set().union(*[s[1].keys() for s in S]))
    for kind, keys, floor in (('pos', keys_p, POS_FLOOR), ('dir', keys_d, DIR_FLOOR)):
        for nm in keys:
            idx = 0 if kind == 'pos' else 1
            dev = np.full(len(S), np.nan)
            for i in range(1, len(S) - 1):
                a, b, c = S[i - 1][idx].get(nm), S[i][idx].get(nm), S[i + 1][idx].get(nm)
                if a is None or b is None or c is None: continue
                if kind == 'pos': dev[i] = float(np.linalg.norm(b - 0.5 * (a + c)))
                else:
                    m = a + c; m = m / max(np.linalg.norm(m), 1e-9)
                    dev[i] = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(b, m))))))
            for i in range(1, len(S) - 1):
                f = f0 - 1 + i
                if np.isnan(dev[i]) or (show is not None and f not in show) or f in cuts: continue
                nb = dev[max(1, i - 5):i].tolist() + dev[i + 1:min(len(S) - 1, i + 6)].tolist(); nb = [x for x in nb if not np.isnan(x)]
                med = float(np.median(nb)) if nb else 0.0
                if dev[i] > floor and dev[i] > POP_K * max(med, 0.05 if kind == 'pos' else 0.1):
                    found.append((f, nm, kind, round(float(dev[i]), 2), round(med, 2)))
    found.sort()
    if not quiet:
        byf = {}
        for x in found: byf.setdefault(x[0], []).append('%s/%s:%.2f' % (x[1], x[2], x[3]))
        for f in sorted(byf): print('POP f %d t %.3f  %s' % (f, MA.tof(f), ' '.join(byf[f])))
    print('DESIGNPOPS %.2f..%.2f %s: %d pops in %d frames' % (t0, t1, 'all' if all_frames else 'shown', len(found), len({x[0] for x in found})))
    return found


if __name__ == '__main__':
    a = sys.argv[1:]
    run(float(a[0]), float(a[1]), len(a) > 2 and a[2] == 'all')
