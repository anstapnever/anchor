# ANCHOR — the mech design against the body's limits, in plain Python (no Blender): every frame's IK legs / arms solved with the
# numpy rig (rigmath == mech.py), then: relative hip flexion, knee, elbow, arm reach, hip-ankle band, fist safety.
#   python shots/designcheck.py 49.0 63.4 [every-n-frames]
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import numpy as np
import rigmath as RM, mechanim as MA


def poses():
    src = open(os.path.join(ROOT, 'assets', 'mech.py'), encoding='utf-8').read()
    i = src.index('POSES = {'); j = src.index('\n}\n', i); ns = {}; exec(src[i:j + 3], ns); return ns['POSES']


class Stub:
    POSES = poses()


def run(t0, t1, n=1, verbose=False):
    MA.prepare_np(Stub.POSES)
    f0, f1 = MA.fr(t0), MA.fr(t1)
    lo = max(f0, MA.fr(MA.T_RISE) + 1)
    if f1 >= lo:
        bad = MA.pelvis_pass(Stub, max(MA.fr(MA.T_RISE) + 1, f0 - 12), f1)
        if bad: print('PELVIS BAND CONFLICTS', len(bad), bad[:10])
    issues = {}
    for f in range(f0, f1 + 1, n):
        t = MA.tof(f); D = MA.design(t, Stub); P = D['pose']; F = RM.frames(P)
        row = []
        for sd in ('L', 'R'):
            ft = D['legs'].get(sd)
            if ft is not None and ft.get('w', 1.0) > 0.01:
                L = RM.leg(P, ft, sd, F)
                if L['flex'] > RM.LIM['hip_flex']: issues.setdefault('hipflex' + sd, []).append((f, round(L['flex'], 1)))
                if L['knee'] > RM.LIM['knee']: issues.setdefault('knee' + sd, []).append((f, round(L['knee'], 1)))
                if L['d'] > RM.LEG_L1 + RM.LEG_L2 - 0.05: issues.setdefault('legreach' + sd, []).append((f, round(L['d'], 2)))
                row.append('%s flex %5.1f abd %5.1f knee %5.1f d %4.1f' % (sd, L['flex'], L['abd'], L['knee'], L['d']))
            else:
                h = P.get('hip' + sd, (0, 0, 0)); kn = P.get('knee' + sd, (0, 0, 0))
                if -h[0] > RM.LIM['hip_flex']: issues.setdefault('hipflexFK' + sd, []).append((f, round(-h[0], 1)))
                if kn[0] > RM.LIM['knee']: issues.setdefault('kneeFK' + sd, []).append((f, round(kn[0], 1)))
                row.append('%s FK hip %5.1f knee %5.1f' % (sd, -h[0], kn[0]))
            a = D['arms'].get(sd)
            if a is not None and a[3] > 0.01:
                A = RM.arm(P, sd, a[0], a[1], a[2], F)
                if A['elbow'] > RM.LIM['elbow']: issues.setdefault('elbow' + sd, []).append((f, round(A['elbow'], 1)))
                if not A['reach']: issues.setdefault('armreach' + sd, []).append((f, round(A['d'], 2)))
                row.append('%s arm d %4.1f elb %5.1f' % (sd, A['d'], A['elbow']))
            else:
                e = P.get('elbow' + sd, (0, 0, 0))
                if -e[0] > RM.LIM['elbow']: issues.setdefault('elbowFK' + sd, []).append((f, round(-e[0], 1)))
            c = P.get('fingers' + sd, 0.0); th = P.get('thumb' + sd, 0.0)
            if abs(RM.safe_thumb(c, th) - th) > 1e-6: issues.setdefault('fist' + sd, []).append((f, th))
        back = -(P.get('neck', (0, 0, 0))[0] + P.get('head', (0, 0, 0))[0])
        if back > RM.LIM['look_back']: issues.setdefault('lookback', []).append((f, round(back, 1)))
        if verbose: print('%5d %6.3f  ' % (f, t) + ' | '.join(row))
    for k, v in issues.items():
        fs = [x[0] for x in v]; worst = max(v, key=lambda x: abs(x[1]))
        print('ISSUE %-12s n %4d frames %d..%d worst %s' % (k, len(v), fs[0], fs[-1], worst))
    if not issues: print('DESIGN CLEAN %.2f..%.2f' % (t0, t1))
    return issues


if __name__ == '__main__':
    a = sys.argv[1:]
    run(float(a[0]), float(a[1]), int(a[2]) if len(a) > 2 else 1, verbose=len(a) > 3)
