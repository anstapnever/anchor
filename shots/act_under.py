# ANCHOR — the underwater shots (HARBOR department): s06, s14, s15, s16.
# Everything that lives under water (water look + light, shackle, pin, fish, rays, FX) is keyed by underanim.key_range;
# the chain by common.chain_key (the bake). Here: cameras, per-shot post, designed contacts.
import math
import numpy as np
import common as CM, story as S
import underanim as UA

UNDER_POST = dict(haze_max=0.0, under=0.0, vignette=0.2, bloom=1.0)
POST = {
    's06': dict(UNDER_POST),
    's14': dict(UNDER_POST, bloom=1.15, vignette=0.24),
    's15': dict(UNDER_POST, bloom=1.2, vignette=0.24),
    's16': dict(UNDER_POST, bloom=1.05, vignette=0.22),
}


def _v(x): return np.array(x, float)


BOW = _v((-100.0, 150.0, -52.0))
PIN = _v((-100.0, 150.0, -57.98))


def _under(W, f0, f1, K, shake=0.0):
    CM.base(W, f0, f1, CM.cam_keys(K, shake_amp=shake))
    CM.chain_key(W, f0, f1)
    UA.key_range(W, f0, f1)


# ---------------------------------------------------------------------------------------------------------------------------- s06
def s06(W, f0, f1):
    """UNDERWATER: the whole coral-covered anchor lies across the trench floor (crown and flukes left, shackle right), fish
    schools, god rays; the camera cranes up and pans right with the chain as it rises from the shackle toward the light."""
    t0, t1 = CM.tof(f0), CM.tof(f1)
    K = [(t0, (-98.5, 175.3, -46.0), (-94.2, 151.6, -59.0), 22.0, 0.0),
         (t0 + 0.5 * (t1 - t0), (-101.5, 172.0, -44.8), (-112.0, 136.0, -46.0), 22.0, -0.5),
         (t1, (-104.5, 168.5, -43.0), (-141.0, 102.0, -12.0), 24.0, -1.0)]
    _under(W, f0, f1, K, shake=0.15)


# ---------------------------------------------------------------------------------------------------------------------------- s14
def s14(W, f0, f1):
    """UNDERWATER: the shackle glows red-hot, the water boils off it, the fish bolt; slow push in."""
    t0, t1 = CM.tof(f0), CM.tof(f1)
    K = [(t0, (-82.0, 141.5, -54.0), (-100.0, 149.5, -51.0), 32.0, 0.0),
         (t1, (-87.5, 143.5, -53.0), (-100.5, 149.0, -50.0), 34.0, -1.0)]
    _under(W, f0, f1, K, shake=0.3)


# ---------------------------------------------------------------------------------------------------------------------------- s15
def s15(W, f0, f1):
    """MACRO: the pin shears (flash, sparks, the halves shoot out), silt explodes off the bed, the shackle is torn away."""
    t0, t1 = CM.tof(f0), CM.tof(f1)
    lat = np.array((0.2588, -0.9659, 0.0)); ys = np.array((0.9659, 0.2588, 0.0))
    c = PIN + np.array((0.0, 0.0, 0.6))
    K = [(t0, tuple(c + ys * 9.0 - lat * 2.5 + _v((0, 0, 0.8))), tuple(c - lat * 0.8), 45.0, 0.0),
         (t0 + 0.35, tuple(c + ys * 9.6 - lat * 2.7 + _v((0, 0, 0.9))), tuple(c - lat * 0.9 + _v((0, 0, 0.6))), 44.0, 0.0),
         (t1, tuple(c + ys * 11.5 - lat * 3.2 + _v((0, 0, 1.6))), tuple(c - lat * 1.0 + _v((0, 0, 3.5))), 40.0, 0.0)]
    _under(W, f0, f1, K, shake=0.6)


# ---------------------------------------------------------------------------------------------------------------------------- s16
def _end_aim(f, back=3.0, win=3):
    """the chain end's aim point at frame f: the last joint + back m along the end link (toward the shackle), box-averaged over
    +-win frames of the bake (smooth, a hair ahead of the action)."""
    acc = np.zeros(3)
    for k in range(f - win, f + win + 1):
        J = CM.chain_joints(k); T = J[80] - J[79]; T = T / np.linalg.norm(T); acc += J[80] + T * back
    return acc / (2 * win + 1)


def s16(W, f0, f1):
    """UNDERWATER: the freed chain whips up toward the light, the shackle swinging on its end: the camera hangs off to the side
    of its path (18-25 m), looks down on it as it swings into line over the silt, and tilts up with it (whip-pan, -34 -> +57 deg)
    until it breaks for the bright surface. Mid-whip the shackle's bow snaps at the crown (BREAK): the end link tears out
    between the two halves and goes on bare (s17 on: no shackle), the halves tumble back and sink."""
    A = _v((-97.2, 127.6, -34.0)); B = _v((-98.0, 127.0, -31.0))

    def cam(t):
        f = int(round(t * CM.FPS)) + 1
        u = min(1.0, max(0.0, (f - f0) / float(f1 - f0))); u = u * u * (3.0 - 2.0 * u)
        pos = A * (1.0 - u) + B * u
        tgt = _end_aim(f)
        tgt = tgt + CM.T.shake(t, 0.25, 6.0, 16) * np.linalg.norm(tgt - pos) * 0.004
        return pos, tgt, 22.0, -4.0 * u
    CM.base(W, f0, f1, cam)
    CM.chain_key(W, f0, f1)
    UA.key_range(W, f0, f1)
    _break_keys(W, f0, f1)


# the shackle breaks (s16). Its pin sheared at 30.0 and the heat cycle left the iron brittle; at the whip's first peak pull on
# the end (62 m/s^2 in the bake) the bow snaps at the crown, inside the end link. The halves spring open about their lugs on
# that frame (each crack end moves >= 1 m off the link's plane: the link's 1.4 m bar tears out between them), then coast on
# their momentum against the water's drag, open further, tumble back and sink, while the end whips on bare (story.RELEASE:
# "the end link rips out of the sheared shackle"; s33's palm closes on the bare last link). The nut half of the pin stays
# caught in half b's lug. underanim (not this file) keys the whole shackle and the pin; the keys here override them from BREAK.
BREAK = 778             # 32.375 s: the bake's first acceleration peak on the end; on the score's 32.4 grid beat (no HIT there)
POP = 9.0               # deg each half springs open about its lug on the break frame
OPEN = 16.0             # deg more it opens over the next ~0.5 s (eases out)
TUMBLE = (-40.0, 52.0)  # deg each half (a, b) turns about the pin's line through its own centre, easing out (0.35 s): the
                        # crack ends swing out of the link's plane, a to +Y, b to -Y (the end swings on toward +X and drifts
                        # +Y in the shackle's frame, past half b). Checked on the meshes every frame 778..797: the crack faces
                        # clear the end link by 0.85 / 0.90 m on the break frame, then >= 1.2 m (b passes it at ~2 m, 781-787);
                        # the halves stay >= 2.5 m apart, the nut half clear of both
RECOIL = 5.0            # m/s the halves spring back down the chain's line (-Z) as the pull lets go, easing out (0.3 s)
SPREAD = 1.2            # m the halves drift apart along the pin's line
DRAG = 0.045            # 1/m quadratic water drag on a flung half: v = v0 / (1 + v0 DRAG t)
SINK = 6.0              # m/s^2 net pull down on the iron (eased by the drag)


def _break_motion(W):
    """(M0, v0, X, Z, centroids) at the break frame: the shackle's pose and velocity, its pin axis and bow axis (up the
    chain), each half's mesh centre (its own frame, model units)."""
    from mathutils import Vector
    U = W['under']
    M0 = UA.shackle_matrix(BREAK); Mp = UA.shackle_matrix(BREAK - 1)
    v0 = (M0.translation - Mp.translation) * CM.FPS
    X = M0.col[0].xyz.normalized(); Z = M0.col[2].xyz.normalized()
    cl = {}
    for side in ('a', 'b'):
        me = U['shackle_' + side].data; acc = Vector((0.0, 0.0, 0.0))
        for v in me.vertices: acc += v.co
        cl[side] = acc / max(1, len(me.vertices))
    return M0, v0, X, Z, cl


_BM = {}


def half_matrix(W, side, f):
    """world matrix of shackle half `side` ('a' = the -X leg and lug, 'b' = the +X one) at frame f >= BREAK."""
    import under as UW
    from mathutils import Vector, Matrix
    if _BM.get('W') is not W: _BM.clear(); _BM['W'] = W; _BM['m'] = _break_motion(W)
    M0, v0, X, Z, cl = _BM['m']
    sg = -1.0 if side == 'a' else 1.0
    tau = max(0.0, (f - BREAK) / float(CM.FPS))
    piv = Vector((sg * UW.SH_LUG, 0.0, 0.0))
    def about_lug(deg): return Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, 'Y') @ Matrix.Translation(-piv)
    Op = about_lug(sg * (POP + OPEN * (1.0 - math.exp(-tau / 0.25))))
    c0 = M0 @ (about_lug(sg * POP) @ cl[side])                   # the tumble's centre: the half's centre on the break frame
    sp = v0.length; u = v0 / max(sp, 1e-6)
    s = math.log(1.0 + sp * DRAG * tau) / DRAG
    D = (u * s + X * (sg * SPREAD * (1.0 - math.exp(-tau / 0.3))) - Z * (RECOIL * 0.3 * (1.0 - math.exp(-tau / 0.3)))
         - Vector((0.0, 0.0, 0.5 * SINK * tau * tau)))
    R = Matrix.Rotation(math.radians(TUMBLE[0 if side == 'a' else 1]) * (1.0 - math.exp(-tau / 0.35)), 4, X)
    return Matrix.Translation(c0 + D) @ R @ Matrix.Translation(-c0) @ M0 @ Op


def _break_keys(W, f0, f1):
    U = W.get('under')
    if not isinstance(U, dict) or 'shackle_a' not in U:
        print('act_under: no shackle halves in the UNDER set, s16 keeps the whole shackle'); return
    if not (f0 < BREAK <= f1): return
    TL = W['TL']; sh = U['shackle']; pb = U['pin_b']; halves = (('a', U['shackle_a']), ('b', U['shackle_b']))
    Q = UA.shackle_matrix(BREAK).inverted() @ UA.pin_matrix('b', BREAK)     # the nut half in the shackle's frame (in lug b)
    prev = {}

    def put(o, M, f):
        l, q, s = M.decompose()
        if o.name in prev and prev[o.name].dot(q) < 0: q = -q
        prev[o.name] = q
        TL.loc(o, f, tuple(l)); TL.quat(o, f, q); TL.scale(o, f, tuple(s))
    for f in range(f0, f1 + 1):
        TL.hide(sh, f, f >= BREAK)
        for side, o in halves:
            TL.hide(o, f, f < BREAK)
            put(o, half_matrix(W, side, f) if f >= BREAK else UA.shackle_matrix(f), f)
        if f >= BREAK: put(pb, half_matrix(W, 'b', f) @ Q, f)
    try: _break_fx(W)
    except Exception as ex:
        import traceback; traceback.print_exc(); print('act_under: break FX failed', ex)


def _break_fx(W):
    """the snap: a white glint on the crack (4 frames, riding between the crack ends) and a burst of bubbles left in the water."""
    fxm = W.get('fx_mod')
    if fxm is None:
        import fx as fxm
    C = W['C'].get('FX')
    if C is None or W.get('_s16_break_fx'): return
    W['_s16_break_fx'] = True
    import under as UW
    from mathutils import Vector
    crown = Vector((0.0, 0.0, UW.PIN_DROP + UW.SH_RB))
    def mid(f): return (half_matrix(W, 'a', f) @ crown + half_matrix(W, 'b', f) @ crown) * 0.5
    p0 = mid(BREAK)
    k = fxm.kira('FX_uw_break_kira', tuple(p0), 2.4, coll=C, seed=641, inner='#ffffff', outer='#bdf3ff')
    fxm.flicker(k, [BREAK], pattern=(1.0, 0.4), step=2)
    for f in range(BREAK - 1, BREAK + 6):
        k.location = tuple(mid(max(f, BREAK))); k.keyframe_insert('location', frame=f)
    fxm._interp(k, 'CONSTANT', ('location',))
    fxm.bubbles(tuple(p0), f0=BREAK, dur=36, coll=C, seed=642, count=40, radius=1.6, size=0.45, rise=6.0, name='FX_uw_break_bubbles')


# ---------------------------------------------------------------------------------------------------------------------------- QA
def _allow_under(a, b):
    na, nb = a.name, b.name
    s = {na, nb}
    if 'UNDER_shackle' in s and any(n.startswith('CHAIN_079') for n in s): return True        # designed interlock (bow / last link)
    return False


QA_ALLOW = {'s06': _allow_under, 's14': _allow_under, 's15': _allow_under, 's16': _allow_under}
