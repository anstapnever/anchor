# ANCHOR — the left hand's grip on the chain's end link (numpy; shared by the mech design and the chain keying).
# The end link (link 79, joints 79 -> 80 of the bake) is a studless end link; the fist closes on one of its long side bars:
#   bar centre = palm @ (0, GRIP_Y, GRIP_Z), bar axis = palm X, link plane = palm X/Z, link centre = bar centre + palm Z * LINK_R.
# The palm's X is +-T (the link's axis); its roll about T (phi) is the design's choice (the wrist's), and the chain's links are
# twisted (a roll that grows linearly from the city's link 0 to the end link) so the end link's plane follows the hand.
import os, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
GRIP_Y, GRIP_Z = 1.5, 0.85            # assets/mech.py
LINK_R = 1.8                          # bar centre line from the link's centre: (W_OUT - BAR) / 2
END_EXT = 0.5                         # assets/chain.END_EXT: before SWAP_T the end link's centre sits this far back from its joints' midpoint
END_EXT2 = 2.100                       # assets/chain.END_EXT2: from SWAP_T the long grip link (straight sides 2 * END_EXT2 longer)
END_SHIFT, END_SHIFT2 = -END_EXT, 2.100  # the end link's centre from its joints' midpoint along the chain toward its free end (m): the
                                      # grip link sits forward so the fist on its straight side is clear of link 78 (hooked in its inner end)
SWAP_T = 64.00                         # s: the end link turns into the grip link here (the chain is in no shot 61.0 .. 67.2: s30 .. s32)


def end_shift(t):
    return END_SHIFT2 if t >= SWAP_T - 1e-6 else END_SHIFT
GRIP_FINGERS = (0.72, 0.76, 0.72)
GRIP_THUMB = -0.5                     # the left thumb on the hold: bent back off the long grip link (curl 0 lies on its round
                                      # end; -0.5 clears link 79 by 0.16 m, 76..78 by 0.98 m, its own palm by 0.05 m: side script thumb_fit)
N_LINK = 80
_J = {}
# MECH_palm's frame in its wrist's frame (assets/mech.py body_hand, columns X Y Z); the arm IK takes the WRIST's world rotation
PCONTACT = {'L': np.array(((0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0))),
            'R': np.array(((0.0, 0.0, 1.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)))}


def wrist_rot(Rp, sd='L'):
    """the wrist's world 3x3 for a palm frame Rp (= mech.palm_rot / rigmath.palm_rot)."""
    return np.asarray(Rp, float) @ np.linalg.inv(PCONTACT[sd])


def joints(f):
    """the baked chain at a frame (float frames interpolate)."""
    if 'J' not in _J: _J['J'] = np.load(os.path.join(ROOT, 'out', 'track', 'chain.npy'))
    J = _J['J']; f = min(max(float(f), 1.0), len(J) - 1.0)
    a = int(math.floor(f)); u = f - a; b = min(a + 1, len(J) - 1)
    return J[a] * (1.0 - u) + J[b] * u if u > 1e-9 else J[a].astype(float)


def frames_along(J, roll0=math.pi / 2, up_hint=(0.0, 0.0, 1.0), twist=None):
    """numpy twin of assets/chain.frames_along (+ an optional extra roll per link): centres (n,3), X (n,3), w (n,3) (= link Y)."""
    J = np.asarray(J, float); n = len(J) - 1
    T = J[1:] - J[:-1]; T = T / np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    C = (J[1:] + J[:-1]) * 0.5
    up = np.asarray(up_hint, float)
    nrm = np.cross(T[0], up)
    if np.linalg.norm(nrm) < 1e-3: nrm = np.cross(T[0], np.array((1.0, 0.0, 0.0)))
    nrm = nrm / np.linalg.norm(nrm)
    W = np.zeros_like(T)
    for i in range(n):
        if i > 0:
            nrm = nrm - T[i] * np.dot(nrm, T[i]); ln = np.linalg.norm(nrm)
            if ln < 1e-6: nrm = np.cross(T[i], up); ln = np.linalg.norm(nrm)
            nrm = nrm / ln
        ang = roll0 + (math.pi / 2 if i % 2 else 0.0) + (0.0 if twist is None else float(twist[i]))
        b = np.cross(T[i], nrm)
        W[i] = nrm * math.cos(ang) + b * math.sin(ang)
    return C, T, W


def up_hint(t):
    import story as S
    R = S.rot_xyz(S.city_tilt(t)); return R @ np.array((0.0, 0.0, 1.0))


def end_link(f):
    """(centre, T, w) of the end link at frame f as the chain is keyed without a twist (the centre: the long end link's own)."""
    t = (f - 1) / 24.0
    C, T, W = frames_along(joints(f), math.pi / 2, up_hint(t))
    return C[-1] + T[-1] * end_shift(t), T[-1], W[-1]


def basis(T):
    """two unit vectors spanning the plane normal to T: n1 = world up projected (or world +Y when T is vertical), n2 = T x n1."""
    up = np.array((0.0, 0.0, 1.0))
    n1 = up - T * float(np.dot(up, T))
    if np.linalg.norm(n1) < 1e-3:
        n1 = np.array((0.0, 1.0, 0.0)) - T * float(T[1])
    n1 = n1 / np.linalg.norm(n1); n2 = np.cross(T, n1)
    return n1, n2


def palm_frame(T, phi, sgn=1.0):
    """the palm's world 3x3 (columns X along the bar, Y along the fingers, Z out of the palm): X = sgn T, Z at angle phi (rad) in
    basis(T) (phi 0 = the palm faces up, pi = faces down)."""
    n1, n2 = basis(T)
    Z = n1 * math.cos(phi) + n2 * math.sin(phi)
    X = sgn * T; Y = np.cross(Z, X)
    return np.column_stack((X, Y, Z))


def palm_pos(C, Rp):
    """the palm's origin for a link centre C held in the palm frame Rp."""
    return np.asarray(C, float) - Rp @ np.array((0.0, GRIP_Y, GRIP_Z + LINK_R))


def phi_for(T, forearm, sgn=1.0):
    """the roll that puts the fingers (palm Y) nearest the forearm's direction (the straightest wrist)."""
    n1, n2 = basis(T)
    y = np.asarray(forearm, float); y = y - T * float(np.dot(y, T))
    if np.linalg.norm(y) < 1e-6: return 0.0
    y = y / np.linalg.norm(y)
    # Y = Z x X = sgn (Z x T); with Z = n1 cos + n2 sin: Z x T = cos (n1 x T) + sin (n2 x T) = -cos n2 + sin n1
    # so Y = sgn (sin n1 - cos n2): match y -> sin = sgn y.n1, cos = -sgn y.n2
    return math.atan2(sgn * float(np.dot(y, n1)), -sgn * float(np.dot(y, n2)))


def twist_for(W_end, T_end, Z_palm):
    """the roll (rad) about T that turns the end link's default width axis onto the palm's Z (mod pi: the link is symmetric)."""
    z = np.asarray(Z_palm, float); z = z - T_end * float(np.dot(z, T_end)); z = z / np.linalg.norm(z)
    w = np.asarray(W_end, float)
    a = math.atan2(float(np.dot(np.cross(w, z), T_end)), float(np.dot(w, z)))
    while a > math.pi / 2: a -= math.pi
    while a < -math.pi / 2: a += math.pi
    return a


def unwrap_pi(a):
    """unwrap a sequence of angles defined mod pi."""
    out = np.array(a, float).copy()
    for i in range(1, len(out)):
        while out[i] - out[i - 1] > math.pi / 2: out[i] -= math.pi
        while out[i] - out[i - 1] < -math.pi / 2: out[i] += math.pi
    return out


GRIP_NPZ = os.path.join(ROOT, 'out', 'track', 'grip.npz')
_G = {}


def table():
    """{'f': frames, 'twist': rad, 'phi': rad, 'sgn': +-1, 'w': 0..1 (how much of the twist is applied)} written by the mech design."""
    if 'g' not in _G:
        _G['g'] = dict(np.load(GRIP_NPZ)) if os.path.exists(GRIP_NPZ) else None
    return _G['g']


def chain_twist(f):
    """per-link extra roll (rad, n=80) for frame f, or None (linear from 0 at the city's link to the full twist at the end link)."""
    g = table()
    if g is None: return None
    fs = g['f']; i = int(np.searchsorted(fs, f))
    if i >= len(fs) or fs[i] != f: return None
    a = float(g['twist'][i]) * float(g['w'][i])
    if abs(a) < 1e-9: return None
    return a * np.arange(N_LINK) / (N_LINK - 1.0)
