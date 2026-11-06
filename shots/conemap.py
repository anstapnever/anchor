# ANCHOR — joint range maps of unit 07 (lead): which local rotations of the shoulder / the hip / the wrist are free of self
# contact. A joint's local rotation is sampled as (direction of the bone in the parent frame, twist about it); the parts riding on
# the joint (not its child joints) are tested against the parts of the parent chain (BVH triangle overlap, designed contacts
# excepted). Maps: out/qa/cone_<joint>.npz {dirs (n,3), twist (m,), hits (n,m)} -> rigmath.cone_hits() looks them up.
#   blender -b -P shots/conemap.py -- shoulderL hipL wristL
import sys, os, math, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'):
    q = os.path.join(ROOT, p)
    if q not in sys.path: sys.path.insert(0, q)
import bpy, numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
import mechpose as MPQ, mech

REST_DIR = {'shoulderL': (0.0, 0.0, -1.0), 'hipL': (0.0, 0.0, -1.0), 'wristL': (0.0, 0.0, -1.0), 'ankleL': (0.0, 0.0, -1.0)}
TIP = (0.0, 1.0, 0.0)                     # the bone's 'back' axis (elbow tip / knee back / back of the wrist)
STATIC_OF = {'shoulderL': ('pelvis', 'spine', 'chest', 'neck', 'head', 'hipL', 'hipR'),
             'hipL': ('pelvis', 'spine', 'chest', 'hipR'),
             'wristL': ('elbowL', 'shoulderL'), 'ankleL': ('kneeL', 'hipL')}


def dirs_grid(step=12.0):
    out = [(0.0, 0.0, -1.0), (0.0, 0.0, 1.0)]
    for el in np.arange(-90 + step, 90 - 1e-6, step):
        n = max(1, int(round(360.0 * math.cos(math.radians(el)) / step)))
        for k in range(n):
            az = 360.0 * k / n; e, a = math.radians(el), math.radians(az)
            out.append((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    return np.array(out)


def base_rot(d):
    """minimal rotation taking the rest direction (0,0,-1) to d (3x3 numpy); the antipode is the half turn about X."""
    r = Vector((0.0, 0.0, -1.0)); v = Vector(tuple(d))
    if r.dot(v) < -0.9999: return np.array(Matrix.Rotation(math.pi, 3, 'X'))
    return np.array(r.rotation_difference(v).to_matrix())


def rot_about(axis, ang):
    return np.array(Matrix.Rotation(ang, 3, Vector(tuple(axis))))


def main(joints):
    sc, M = MPQ.build(); B = MPQ.Body(M); J = M['joints']
    mech.set_pose(M, dict(mech.POSES['stand']))
    def owner(o):
        sg = str(o.get('seg', ''))
        if sg.startswith(('fingerL', 'thumbL')): return 'wristL'
        if sg.startswith(('fingerR', 'thumbR')): return 'wristR'
        return sg
    own = {o.name: owner(o) for o in B.objs}
    def bvh(o): return BVHTree.FromPolygons([tuple(v) for v in B.world(o)], B.F[o.name], all_triangles=False, epsilon=0.0)
    for jn in joints:
        t0 = time.time()
        mech.set_pose(M, dict(mech.POSES['stand']))
        mov = [o for o in B.objs if own[o.name] == jn and 'vine' not in o.name]
        sta = [o for o in B.objs if own[o.name] in STATIC_OF[jn] and 'vine' not in o.name]
        print(jn, 'moving', [o.name[5:] for o in mov], 'static', len(sta), flush=True)
        ST = [(o, bvh(o)) for o in sta]
        j = J[jn]; e0 = j.rotation_euler.copy()
        D = dirs_grid(); TW = np.radians(np.arange(-150, 151, 30)); H = np.zeros((len(D), len(TW)), np.int32)
        for i, d in enumerate(D):
            R0 = base_rot(d)
            for k, tw in enumerate(TW):
                R = rot_about(d, tw) @ R0
                j.rotation_euler = Matrix(R.tolist()).to_euler('XYZ')
                n = 0
                for o in mov:
                    t = bvh(o)
                    for oo, tt in ST:
                        if mech.qa_allow(o, oo): continue
                        ov = t.overlap(tt)
                        if ov: n += len(ov)
                H[i, k] = n
        j.rotation_euler = e0
        np.savez_compressed(os.path.join(ROOT, 'out', 'qa', 'cone_%s.npz' % jn), dirs=D, twist=TW, hits=H)
        free = (H == 0).mean()
        print('%s: %d dirs x %d twists, free %.0f%%  (%.0fs)' % (jn, len(D), len(TW), 100 * free, time.time() - t0), flush=True)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:])
