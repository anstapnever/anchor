# ANCHOR — helpers every shot uses: the camera path, per-frame uniforms (sun, storm, sea clock, lightning flash), the city's drift,
# the chain (from the bake), the persistent storm wall + waterspout, and small animation tools. Times are film seconds
# (t = (frame - 1) / 24). Everything is a pure function of t, so any shot keys exactly what its neighbours key (continuity).
# The story state lives in story.py (beats, city path, chain end, palm, spout); the chain itself in out/track/chain.npy.
import math, os, sys
import numpy as np
import bpy
from mathutils import Vector, Quaternion, Euler, Matrix
import look as LK, env as EV, timeline as T, chain as CH
import story as S
import grip as GR

FPS = 24
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def tof(f): return (f - 1) / FPS


def frames(f0, f1): return range(f0, f1 + 1)


# ---------------------------------------------------------------------------------------------------------------------- lightning
# Every flash of the film (t, strength): the two story strikes and the storm's distant flashes. The scene 'flash' uniform and
# the storm wall's inner flashes use this one list, so a flash seen in one shot is the flash of the neighbouring shots too.
STRIKES = [(24.4, 1.0), (45.6, 1.0)]
AMBIENT = [(15.1, 0.25), (16.9, 0.3), (19.3, 0.35), (21.7, 0.35), (23.2, 0.4), (27.1, 0.35), (29.6, 0.3), (36.4, 0.35),
           (40.6, 0.4), (43.9, 0.35), (48.9, 0.3), (51.4, 0.35), (54.2, 0.3), (58.3, 0.4), (60.9, 0.35), (64.2, 0.6),
           (66.8, 0.3), (71.3, 0.35), (74.5, 0.3), (77.2, 0.35), (79.4, 0.3)]
FLASHES = sorted(STRIKES + AMBIENT)


def sky_deck(t):
    """1 while the storm deck covers the whole sky dome (env.sky: every heading in the storm tones, not only the west): from
    the first strike (24.4, the cut s11|s12, under its white-out) to the release (82.0, the cut s39|s40, the clouds tear
    open). Both edges sit on cuts, so no shot sees the sky change without its cause."""
    return 1.0 if S.T['strike1'] - 1e-6 <= t < S.T['open'] - 1e-6 else 0.0


def flash_at(t, flashes=None):
    """lightning brightness 0..1 at t: strike, a re-strike, fade (on threes)."""
    fl = 0.0
    for (ts, k) in (FLASHES if flashes is None else flashes):
        dt = t - ts
        if -0.01 <= dt < 0.6:
            ff = int(dt * 8)
            fl = max(fl, k * {0: 1.0, 1: 0.35, 2: 0.85, 3: 0.3, 4: 0.15}.get(ff, 0.0))
    return fl


# ---------------------------------------------------------------------------------------------------------------------------- base
def base(W, f0, f1, cam_fn, flashes=None, storm_bias=0.0, sky_storm=None, extra=None, local_flash=0.0):
    """Keys, for every frame of the shot: camera (cam_fn(t) -> pos, tgt, lens, roll), the sky dome + sea camera uniform,
    the sun, the storm, the sea clock, the lightning flash (FLASHES unless a shot passes its own list), the persistent FX.
    local_flash: extra gain on the flash uniform for shots right under a strike."""
    TL = W['TL']; sc = W['sc']; cam = W['cam']; sky = W['sky']; sun = W['sun']
    prev_q = None
    for f in frames(f0, f1):
        t = tof(f)
        pos, tgt, lens, roll = cam_fn(t)
        q = T.look_quat(pos, tgt, roll)
        if prev_q is not None and prev_q.dot(q) < 0: q = -q
        prev_q = q
        TL.loc(cam, f, tuple(pos)); TL.quat(cam, f, q); TL.set(cam.data, 'lens', f, lens)
        TL.loc(sky, f, tuple(pos)); TL.prop(sc, 'camP', f, tuple(pos))
        az, el, col = S.sun(t); d = EV.sun_dir(az, el)
        TL.quat(sun, f, (-d).to_track_quat('-Z', 'Y')); TL.prop(sc, 'sunD', f, tuple(d)); TL.prop(sc, 'sunC', f, LK.srgb(col)[:3])
        st = min(1.0, max(0.0, S.storm(t) + storm_bias))
        TL.prop(sc, 'skyStorm', f, st if sky_storm is None else sky_storm)
        TL.prop(sc, 'skyDeck', f, sky_deck(t))
        TL.prop(sc, 'cloudStorm', f, st)
        TL.prop(sc, 'seaT', f, t)
        TL.prop(sc, 'seaRough', f, st)
        TL.prop(sc, 'wet', f, st)
        TL.prop(sc, 'skyDrift', f, t * 0.02)
        TL.prop(sc, 'flash', f, min(1.0, flash_at(t, flashes) * (1.0 + local_flash)))
        # storm light: the key dims a little and cools, the shade goes deeper violet
        TL.prop(sc, 'skyC', f, LK.srgb('#9fc0ff')[:3] if st < 0.01 else tuple(np.array(LK.srgb('#9fc0ff')[:3]) * (1 - st) + np.array(LK.srgb('#8c8fd8')[:3]) * st))
        TL.prop(sc, 'shadeC', f, tuple(np.array(LK.srgb('#9da3d6')[:3]) * (1 - st) + np.array(LK.srgb('#7f82c4')[:3]) * st))
        if extra: extra(f, t)
    world_fx(W, f0, f1, flashes)


def cam_keys(keys, shake_amp=0.0, shake_freq=6.0, seed=1):
    """keys: [(t, pos, tgt, lens, roll)] -> cam_fn(t) on a Catmull-Rom spline, with an optional hand-held shake."""
    P = [(k[0], k[1]) for k in keys]; G = [(k[0], k[2]) for k in keys]
    Lk = [(k[0], (k[3],)) for k in keys]; Rk = [(k[0], (k[4] if len(k) > 4 else 0.0,)) for k in keys]
    def fn(t):
        pos = T.catmull(P, t); tgt = T.catmull(G, t); lens = float(T.catmull(Lk, t)[0]); roll = float(T.catmull(Rk, t)[0])
        if shake_amp:
            sh = T.shake(t, shake_amp, shake_freq, seed); d = np.linalg.norm(tgt - pos)
            tgt = tgt + sh * d * 0.004
        return pos, tgt, lens, roll
    return fn


def impact_shake(t, events, amp=1.0):
    """events [(t0, strength)] -> decaying shake offset (unit vector-ish * amp)."""
    off = np.zeros(3)
    for (t0, k) in events:
        dt = t - t0
        if 0 <= dt < 1.2:
            e = math.exp(-dt * 5.0) * k * amp
            off += np.array((math.sin(dt * 47.0), math.cos(dt * 41.0), math.sin(dt * 37.0 + 1.0))) * e
    return off


# ---------------------------------------------------------------------------------------------------------------- persistent FX
SPOUT_T = (22.0, 86.0)            # the waterspout exists from its touch-down (s11 animates the forming) until it dies out


def _fx_objs(root):
    return [o for o in [root] + list(root.children_recursive) if o.type != 'EMPTY']


def world_fx(W, f0, f1, flashes=None):
    """the storm wall (hidden before storm_seen, inner flashes on the film's flash list) and the waterspout (at story.spout_pos,
    spinning continuously from SPOUT_T[0], hidden outside SPOUT_T). Shots with special behaviour (s11: the forming) key over it
    afterwards (the Store keeps the last value set for a frame)."""
    fx = W.get('fx')
    if not fx: return
    TL = W['TL']
    st = fx.get('storm')
    if st:
        objs = _fx_objs(st['root'])
        for f in frames(f0, f1):
            t = tof(f); hid = t < S.T['storm_seen'] - 0.01
            for o in objs: TL.hide(o, f, hid)
            for o in (st.get('mass'), st.get('shelf')):
                if o is not None and 'fl1' in o.keys():
                    TL.prop(o, 'fl1', f, flash_at(t, flashes)); TL.prop(o, 'fl2', f, 0.7 * flash_at(t + 0.37, flashes))
    sp = fx.get('spout')
    if sp:
        objs = _fx_objs(sp['root'])
        for f in frames(f0, f1):
            t = tof(f); p = S.spout_pos(t)
            vis = p is not None and SPOUT_T[0] <= t <= SPOUT_T[1]
            if p is not None: TL.loc(sp['root'], f, (float(p[0]), float(p[1]), 0.0))
            TL.prop(sp['root'], 'twist', f, 1.6 * max(0.0, t - SPOUT_T[0]))
            for o in objs: TL.hide(o, f, not vis)


# ---------------------------------------------------------------------------------------------------------------------------- city
def city_key(W, f0, f1, offset=None, life=True):
    """CITY_root on story.city_pos / city_tilt for every frame (the root = the collar ring's centre = the chain's pin), then the
    city's own life (citylife.city_life: sails, bell, vanes, laundry, falls, crystals, lamps, tiles, rivets) when available."""
    c = W.get('city')
    if not c: return
    root = c['root'] if isinstance(c, dict) else c
    TL = W['TL']
    for f in frames(f0, f1):
        t = tof(f)
        p = S.city_pos(t); r = S.city_tilt(t)
        TL.loc(root, f, tuple(p)); TL.eul(root, f, tuple(math.radians(x) for x in r))
    if life:
        try: import citylife
        except ModuleNotFoundError: return
        citylife.city_life(W, f0, f1)


def city_matrix(t):
    """4x4 world matrix of CITY_root at t (numpy)."""
    R = S.rot_xyz(S.city_tilt(t)); M = np.eye(4); M[:3, :3] = R; M[:3, 3] = S.city_pos(t); return M


def city_collar(t):
    """the chain's top joint (joint 0) at t."""
    return S.collar(t)


# ---------------------------------------------------------------------------------------------------------------------------- chain
_CHAIN = {}


def chain_joints(f):
    """the baked chain at frame f: 81 joints (0 = the top at the city's pin, 80 = the end: anchor shackle / free end / palm)."""
    if 'J' not in _CHAIN: _CHAIN['J'] = np.load(os.path.join(ROOT, 'out', 'track', 'chain.npy'))
    J = _CHAIN['J']; return J[min(max(int(f), 1), len(J) - 1)].astype(float)


def chain_heat(t, n=80):
    """per-link glow 0..1: the strike lights the top links (24.4), the discharge runs down link by link (25.8 .. 27.4), the
    bottom links stay hot with the shackle (27.4 .. 30.0) and cool after the pin shears (30.0 .. 31.6)."""
    h = np.zeros(n); i = np.arange(n)
    t1 = S.T['strike1']; t2 = S.T['discharge']
    if t1 <= t < t2 + 0.4:
        h = np.maximum(h, np.exp(-i / 3.0) * (1.0 - S.sstep(S.rng(t, t1 + 0.6, t2 + 0.4))) * (0.6 + 0.4 * (int(t * 16) % 2)))
    if t2 <= t < 31.6:
        kf = (n + 4) * S.sstep(S.rng(t, t2, 27.4)) - 2.0
        h = np.maximum(h, np.exp(-((i - kf) / 2.6) ** 2))
        passed = np.clip((kf - i) / 6.0, 0.0, 1.0) * 0.18 * (1.0 - S.sstep(S.rng(t, 27.4, 28.4)))
        h = np.maximum(h, passed)
        bot = np.exp(-(n - 1 - i) / 2.5) * S.sstep(S.rng(t, 27.0, 27.6)) * (1.0 - S.sstep(S.rng(t, S.T['pin_shear'], 31.6)))
        h = np.maximum(h, bot * 0.85)
    return np.clip(h, 0.0, 1.0)


def chain_key(W, f0, f1, heat=True):
    """every link of the chain on the bake for frames f0..f1: the first link's plane vertical through the chain (its pin axis
    horizontal in the city's frame, perpendicular to the pull) and the city's lug (CITY_lug, axis Z) yawed to carry that pin."""
    if 'chain' not in W: return
    links = W['chain']; TL = W['TL']; c = W.get('city') if isinstance(W.get('city'), dict) else None
    lug = c.get('lug') if c else None
    prev = [None]
    for f in frames(f0, f1):
        t = tof(f); J = chain_joints(f)
        R = S.rot_xyz(S.city_tilt(t)); up = R @ np.array((0.0, 0.0, 1.0))
        chain_pose(W, f, J, math.pi / 2, chain_heat(t, len(links)) if heat else None, up_hint=tuple(up), twist=GR.chain_twist(f))
        if lug is not None:
            d = R.T @ (J[1] - J[0]); nl = np.cross(d, np.array((0.0, 0.0, 1.0)))
            if np.linalg.norm(nl[:2]) > 0.02 * np.linalg.norm(d):
                a = math.atan2(nl[1], nl[0])
                ref = prev[0] if prev[0] is not None else math.radians(132.0)
                while a - ref > math.pi / 2: a -= math.pi
                while a - ref < -math.pi / 2: a += math.pi
                prev[0] = a
            TL.eul(lug, f, (0.0, 0.0, prev[0] if prev[0] is not None else math.radians(132.0)))


def chain_pose(W, f, joints, roll0=0.0, heat=None, up_hint=(0.0, 0.0, 1.0), twist=None):
    links = W['chain']; TL = W['TL']
    C, qs = CH.frames_along(joints, roll0, up_hint, twist)
    n = min(len(links), len(C))
    for i in range(len(links)):
        o = links[i]
        if i < n:
            q = qs[i]
            pq = W.setdefault('_chainq', {}).get(i)
            if pq is not None and pq.dot(q) < 0: q = -q
            W['_chainq'][i] = q
            c = np.asarray(C[i], float)
            if i == len(links) - 1 and i == len(C) - 1:          # the end link: off its joints' midpoint by grip.end_shift; from
                Tl = np.asarray(joints[i + 1], float) - np.asarray(joints[i], float); Tl = Tl / max(np.linalg.norm(Tl), 1e-9)
                tf = tof(f); c = c + Tl * GR.end_shift(tf)              # grip.SWAP_T the long grip link (shape key 'grip')
                sk = o.data.shape_keys
                if sk is not None and 'grip' in sk.key_blocks:
                    TL.set(sk, 'key_blocks["grip"].value', f, 1.0 if tf >= GR.SWAP_T - 1e-6 else 0.0)
            TL.loc(o, f, tuple(c)); TL.quat(o, f, q); TL.hide(o, f, False)
        else:
            TL.hide(o, f, True)
        if heat is not None: TL.prop(o, 'heat', f, float(heat[i]) if i < len(heat) else 0.0)


def chain_rest(t, n=81, sway=1.0):
    """(legacy name) the baked chain at time t."""
    return chain_joints(int(round(t * FPS)) + 1)


# ---------------------------------------------------------------------------------------------------------------------------- misc
def key_vis(W, objs, f, visible):
    for o in objs: W['TL'].hide(o, f, not visible)
