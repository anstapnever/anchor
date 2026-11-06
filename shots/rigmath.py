# ANCHOR — unit 07's rig in numpy (lead): forward kinematics of the torso / arms / legs and the two-bone solves exactly as
# assets/mech.py does them, so a design can be checked against the body's own limits before Blender ever runs:
#   relative hip flexion (thigh vs pelvis; the armour collides past ~100 deg), knee <= ~100, elbow <= ~100, arm reach,
#   look-up (neck + head back-tilt <= ~30), fist (thumb curl vs finger curl).
import math
import numpy as np

PELVIS_P = np.array((0.0, 0.0, 44.0)); SPINE_P = np.array((0.0, 0.8, 52.0)); CHEST_P = np.array((0.0, 0.9, 56.4))
NECK_P = np.array((0.0, 1.3, 70.8)); HEAD_P = np.array((0.0, 1.0, 73.0))
S_X, S_Y, S_Z, E_Z, W_Z = 17.6, 1.0, 64.5, 53.0, 42.0
H_X, H_Z, K_Z, A_Z = 8.6, 42.0, 24.0, 6.2
PALM = np.array((15.9, 1.0, 38.2))
LEG_L1, LEG_L2 = H_Z - K_Z, K_Z - A_Z            # 18.0, 17.8
ARM_L1, ARM_L2 = S_Z - E_Z, E_Z - W_Z            # 11.5, 11.0
SOLE_ANK = np.array((0.0, -3.0, -6.2))
LIM = dict(hip_flex=100.0, knee=98.0, elbow=98.0, look_back=30.0)


def Rx(a): a = math.radians(a); c, s = math.cos(a), math.sin(a); return np.array(((1, 0, 0), (0, c, -s), (0, s, c)))
def Ry(a): a = math.radians(a); c, s = math.cos(a), math.sin(a); return np.array(((c, 0, s), (0, 1, 0), (-s, 0, c)))
def Rz(a): a = math.radians(a); c, s = math.cos(a), math.sin(a); return np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))
def eul(e): return Rz(e[2]) @ Ry(e[1]) @ Rx(e[0])
def side_e(e, sd): return (e[0], e[1], e[2]) if sd == 'L' else (e[0], -e[1], -e[2])


def T(R, p):
    m = np.eye(4); m[:3, :3] = R; m[:3, 3] = p; return m


def frames(P):
    """world 4x4 of root, pelvis, spine, chest, neck, head, shoulder/elbow/wrist L/R (pivots) for a set_pose dict (FK only)."""
    r = P['root']; out = {}
    W = T(Rz(r[3]), np.array(r[:3], float)); out['root'] = W
    hp = np.array(P.get('hips', (0, 0, 0)), float)
    W = W @ T(eul(P.get('pelvis', (0, 0, 0))), PELVIS_P + hp); out['pelvis'] = W
    W = W @ T(eul(P.get('spine', (0, 0, 0))), SPINE_P - PELVIS_P); out['spine'] = W
    C = W @ T(eul(P.get('chest', (0, 0, 0))), CHEST_P - SPINE_P); out['chest'] = C
    N = C @ T(eul(P.get('neck', (0, 0, 0))), NECK_P - CHEST_P); out['neck'] = N
    out['head'] = N @ T(eul(P.get('head', (0, 0, 0))), HEAD_P - NECK_P)
    for sd, sx in (('L', 1.0), ('R', -1.0)):
        Sh = C @ T(eul(side_e(P.get('shoulder' + sd, (0, 0, 0)), sd)), np.array((S_X * sx, S_Y, S_Z)) - CHEST_P); out['shoulder' + sd] = Sh
        El = Sh @ T(eul(side_e(P.get('elbow' + sd, (0, 0, 0)), sd)), np.array((0.0, 0.0, E_Z - S_Z))); out['elbow' + sd] = El
        out['wrist' + sd] = El @ T(eul(side_e(P.get('wrist' + sd, (0, 0, 0)), sd)), np.array((0.0, 0.0, W_Z - E_Z)))
        Hp = out['pelvis'] @ T(eul(side_e(P.get('hip' + sd, (0, 0, 0)), sd)), np.array((H_X * sx, 0.0, H_Z)) - PELVIS_P); out['hip' + sd] = Hp
        Kn = Hp @ T(eul(side_e(P.get('knee' + sd, (0, 0, 0)), sd)), np.array((0.0, 0.0, K_Z - H_Z))); out['knee' + sd] = Kn
        An = Kn @ T(eul(side_e(P.get('ankle' + sd, (0, 0, 0)), sd)), np.array((0.0, 0.0, A_Z - K_Z))); out['ankle' + sd] = An
        out['sole' + sd] = An @ T(np.eye(3), SOLE_ANK)
    return out


def pos(m): return m[:3, 3].copy()


def two_bone(S, Tt, L1, L2, pole):
    v = Tt - S; d0 = float(np.linalg.norm(v)); d = min(max(d0, abs(L1 - L2) + 0.5), L1 + L2 - 0.02)
    u = v / max(d0, 1e-9); pp = np.asarray(pole, float) - u * float(np.dot(pole, u))
    if np.linalg.norm(pp) < 1e-6: pp = np.array((0.0, 1.0, 0.0)) - u * u[1]
    pp = pp / np.linalg.norm(pp)
    ca = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d); sa = math.sqrt(max(0.0, 1 - ca * ca))
    Mid = S + (u * ca + pp * sa) * L1
    cg = (L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2)
    return Mid, math.degrees(math.pi - math.acos(max(-1.0, min(1.0, cg)))), d0


def foot_R(ft): return Rz(ft.get('yaw', 0.0)) @ Ry(ft.get('roll', 0.0)) @ Rx(ft.get('pitch', 0.0))


def leg(P, ft, sd, F=None):
    """the IK leg to the foot frame ft: dict(knee=bend deg, flex=relative hip flexion deg (+ forward), abd=abduction deg, d=hip-ankle,
    K=knee world, H=hip world, A=ankle world)."""
    F = F or frames(P)
    H = pos(F['hip' + sd]); Rf = foot_R(ft); A = np.asarray(ft['p'], float) - Rf @ SOLE_ANK
    pole = Rf @ np.array((0.0, -1.0, 0.0)) if ft.get('pole') is None else np.asarray(ft['pole'], float)
    K, bend, d = two_bone(H, A, LEG_L1, LEG_L2, pole)
    Rp = F['pelvis'][:3, :3]; v = Rp.T @ (K - H); sx = 1.0 if sd == 'L' else -1.0
    return dict(knee=bend, flex=math.degrees(math.atan2(-v[1], -v[2])), abd=math.degrees(math.asin(max(-1.0, min(1.0, sx * v[0] / max(np.linalg.norm(v), 1e-9))))),
                d=d, K=K, H=H, A=A)


def palm_offset(sd):
    sx = 1.0 if sd == 'L' else -1.0
    return np.array(((PALM[0] - S_X) * sx, PALM[1] - S_Y, PALM[2] - W_Z))


def arm(P, sd, hand_pos, hand_R, pole=None, F=None):
    """the IK arm to a palm position (+ the hand's world rotation): dict(elbow=bend deg, d=shoulder-wrist, reach=ok, S, E, Wr)."""
    F = F or frames(P); S = pos(F['shoulder' + sd]); sx = 1.0 if sd == 'L' else -1.0
    Wt = np.asarray(hand_pos, float) - np.asarray(hand_R) @ palm_offset(sd)
    if pole is None:
        Rc = F['chest'][:3, :3]; pole = Rc @ np.array((0.35 * sx, 1.0, -0.25))
    E, bend, d = two_bone(S, Wt, ARM_L1, ARM_L2, pole)
    return dict(elbow=bend, d=d, reach=d <= ARM_L1 + ARM_L2 - 0.05, S=S, E=E, Wr=Wt)


def palm_rot(sd, out, along):
    """numpy twin of mech.palm_rot: the wrist's world 3x3 that turns MECH_palm's +Z to `out` and +Y to `along`."""
    sx = 1.0 if sd == 'L' else -1.0
    Z = np.asarray(out, float); Z = Z / np.linalg.norm(Z); Y = np.asarray(along, float); Y = Y - Z * float(np.dot(Y, Z)); Y /= np.linalg.norm(Y)
    X = np.cross(Y, Z)
    C = np.array(((0, 0, -sx), (sx, 0, 0), (0, -1, 0)), float)
    return np.column_stack((X, Y, Z)) @ np.linalg.inv(C)


# --------------------------------------------------------------------------------------------------------------- quaternions
def m2q(R):
    R = np.asarray(R, float); tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2; return np.array((0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s))
    i = int(np.argmax((R[0, 0], R[1, 1], R[2, 2])))
    if i == 0:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2; return np.array(((R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s))
    if i == 1:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2; return np.array(((R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s))
    s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2; return np.array(((R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s))


def q2m(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array(((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
                     (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
                     (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))))


def slerp_m(A, B, u):
    qa = m2q(A); qb = m2q(B)
    if np.dot(qa, qb) < 0: qb = -qb
    d = float(np.clip(np.dot(qa, qb), -1.0, 1.0))
    if d > 0.9995: q = qa + (qb - qa) * u
    else:
        th = math.acos(d); q = (math.sin((1 - u) * th) * qa + math.sin(u * th) * qb) / math.sin(th)
    return q2m(q)


def safe_thumb(c, t):
    """the thumb's curl that clears the curled fingers (measured: finger 0's tip meets the thumb past these)."""
    c = max(c) if isinstance(c, (tuple, list)) else c
    if c < 0.62: return t
    if c < 0.88: return min(t, 0.3)
    return min(t, 0.42)
