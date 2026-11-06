# ANCHOR — the harbour shots (HARBOR department): s08, s17, s20, s21, s22, s23, s24.
# The port's own life (crane A, Dock 3 flood, boats, lighthouse, crane-hit FX) is keyed by portlife.port_life; the chain by
# common.chain_key (the bake), the city by common.city_key, the mech + gull by mechanim.key_range. Here: cameras, shot FX,
# per-shot post, designed contacts.
import math
import numpy as np
import common as CM, story as S
import portlife as PL

FPS = 24
STORM_POST = dict(haze=(0.74, 0.78, 0.94), haze_dist=2200.0, haze_max=0.38, bloom=0.95, rain=0.4, rain_angle=-26.0)
POST = {                                      # rain / haze in step with the SKY department's storm shots (s09..s19)
    's08': dict(STORM_POST, haze_dist=2600.0, haze_max=0.35, rain=0.1),
    's17': dict(STORM_POST),
    's20': dict(STORM_POST, haze_dist=2400.0),
    's21': dict(STORM_POST, bloom=1.05, rain=0.45),
    's22': dict(STORM_POST, haze_max=0.32, bloom=1.0, rain=0.45),
    's23': dict(STORM_POST, haze_max=0.32, bloom=1.25, rain=0.45),
    's24': dict(STORM_POST, haze_max=0.15, bloom=1.3, vignette=0.24, rain=0.3),
}


def _v(x): return np.array(x, float)
def fr(t): return int(round(t * FPS)) + 1


def _fx():
    import fx as FXM
    return FXM


def _want(W, name):
    done = W.setdefault('_ap_fx', set())
    if name in done: return False
    done.add(name); return True


def shake_fn(cam_fn, events, amp_deg=1.2, w=18.0, k=4.5):
    """wrap a cam_fn with drawn impact shakes: events [(t0, strength)] -> a decaying low-frequency wobble of the aim
    (rotation only, so the QA's camera acceleration stays clean)."""
    def fn(t):
        pos, tgt, lens, roll = cam_fn(t)
        d = tgt - pos; L = float(np.linalg.norm(d)); f = d / max(L, 1e-6)
        side = np.cross(f, (0.0, 0.0, 1.0)); n = np.linalg.norm(side)
        side = side / n if n > 1e-6 else np.array((1.0, 0.0, 0.0)); up = np.cross(side, f)
        ax = ay = rr = 0.0
        for t0, s in events:
            tau = t - t0
            if 0.0 <= tau < 1.5:
                e = s * math.exp(-k * tau) * min(1.0, tau / 0.05)
                ax += e * math.sin(w * tau); ay += e * math.sin(0.83 * w * tau + 1.1); rr += e * math.sin(0.7 * w * tau + 2.0)
        a = math.radians(amp_deg)
        tgt = tgt + (side * ax + up * ay) * L * math.tan(a)
        return pos, tgt, lens, roll + rr * amp_deg * 0.8
    return fn


def _keys_fn(K, shake=0.0, events=None, amp=1.2):
    fn = CM.cam_keys(K, shake_amp=shake)
    return shake_fn(fn, events, amp) if events else fn


# ---------------------------------------------------------------------------------------------------------------------------- s08
def s08(W, f0, f1):
    """The fishing fleet races home past the lighthouse ahead of the storm: low on the swell, the lead boats slam through the
    waves toward the lens throwing spray, the lighthouse and its sweeping beam behind them, the storm wall closing in."""
    t0, t1 = CM.tof(f0), CM.tof(f1)
    K = [(t0, (-583.0, -253.5, 3.0), (-662.0, -236.0, 10.0), 28.0, -2.0),
         (t0 + 0.5 * (t1 - t0), (-585.0, -254.5, 3.4), (-648.0, -236.0, 9.0), 28.0, 0.0),
         (t1, (-588.0, -256.0, 3.2), (-628.0, -235.0, 7.5), 28.0, 2.0)]
    CM.base(W, f0, f1, _keys_fn(K, shake=0.5), storm_bias=0.15)
    CM.city_key(W, f0, f1); CM.chain_key(W, f0, f1)
    PL.port_life(W, f0, f1)
    if _want(W, 's08_spray'):
        FXM = _fx(); C = W['C']['FX']; boats = W['port']['boats']
        fa = f0 - 6; n = int(math.ceil((f1 + 3 - fa) / 3.0))
        for i in range(5):
            L = float(boats[i].get('length', 18.0)); pts = []
            for k in range(n + 1):                                   # bow positions on a 3-frame grid; the trail head
                (x, y, z), (r, p, yaw) = PL.boat_pose(i, CM.tof(fa + 3 * k))         # runs them at constant speed
                pts.append((x + math.cos(yaw) * (L * 0.5 - 1.5), y + math.sin(yaw) * (L * 0.5 - 1.5)))
            FXM.spray_trail(pts, f0=fa, dur=3 * n, coll=C, seed=801 + i, size=4.5 + 0.4 * L / 10.0, skip=0.42,
                            name='FX_s08_boat%d' % i)


# ---------------------------------------------------------------------------------------------------------------------------- s17
def s17(W, f0, f1):
    """The chain tears out of the bay: a wall of spray stands along it (it ripped up from the waterline toward the end in the
    last 0.6 s) and the freed end bursts out of it, flies 44 m up toward the camera's left and starts to fall back."""
    t0, t1 = CM.tof(f0), CM.tof(f1)
    K = [(t0, (-80.0, 0.0, 8.0), (-134.0, 118.0, 34.0), 22.0, 1.0),
         (t0 + 0.5 * (t1 - t0), (-83.0, 2.0, 8.6), (-133.0, 118.0, 40.0), 22.0, 0.3),
         (t1, (-86.0, 4.0, 9.2), (-137.0, 114.0, 31.0), 22.0, -0.5)]
    CM.base(W, f0, f1, _keys_fn(K, shake=0.6, events=[(33.22, 1.0)], amp=0.9))
    CM.city_key(W, f0, f1); CM.chain_key(W, f0, f1)
    PL.port_life(W, f0, f1)
    if _want(W, 's17_burst'):
        FXM = _fx(); C = W['C']['FX']
        fb = fr(S.T['burst'])
        fw = fr(32.6)
        dw = FXM._auto_dur(26.0); dc = FXM._auto_dur(26.0)          # heavy drawn timing for their size (fx's own rule)
        FXM.splash_wall((-152.0, 99.0, 0.0), (-116.0, 135.0, 0.0), height=26.0, f0=fw, dur=dw, coll=C, seed=1701,
                        zip=(fb - fw) / float(dw), drops=200, name='FX_s17_wall')
        FXM.splash_crown((-118.2, 132.9, 0.0), radius=6.0, height=26.0, f0=fb, dur=dc, coll=C, seed=1702, jets=9, drops=90,
                         name='FX_s17_crown')


# ---------------------------------------------------------------------------------------------------------------------------- s20
def s20(W, f0, f1):
    """WIDE: the city drifts off over the harbour (screen left), dragging its chain; the freed end skips across the water in a
    trail of spray toward the cranes; the lighthouse stands in the foreground under the city, its beam sweeping; the camera
    trucks left with the city (parallax on the lighthouse)."""
    t0, t1 = CM.tof(f0), CM.tof(f1)
    K = [(t0, (-812.0, -266.0, 16.0), (-470.0, 280.0, 250.0), 20.0, -1.0),        # path moved (-12, +14) m from the first cut:
         (t0 + 0.5 * (t1 - t0), (-816.0, -257.0, 17.5), (-485.0, 290.0, 250.0), 20.0, -0.5),    # the chain now stays >= 55 px
         (t1, (-820.0, -248.0, 19.0), (-500.0, 300.0, 250.0), 20.0, 0.0)]          # (full res) clear of the tower; it ran behind the lantern
    CM.base(W, f0, f1, _keys_fn(K, shake=0.35))
    CM.city_key(W, f0, f1); CM.chain_key(W, f0, f1)
    PL.port_life(W, f0, f1)
    _end_trail(W)


def _end_trail(W):
    """the chain end skipping over the water 38.9..41.4 (the bake's skips every ~0.59 s), as one spray trail."""
    if not _want(W, 'end_trail'): return
    FXM = _fx(); C = W['C']['FX']
    fa, fb = 935, 1000
    pts = []
    for f in range(fa, fb + 1, 2):
        J = CM.chain_joints(f); pts.append((float(J[80][0]), float(J[80][1])))
    out = FXM.spray_trail(pts, f0=fa, dur=fb - fa, coll=C, seed=2001, size=9.0, skip=0.593, name='FX_end_trail')
    # the wake ends at the cut to s21 (06.11): its age runs off the head, which stops with the trail's last drawing (998), so
    # the foam froze dense in front of s21's lens and was switched off mid-shot at 1049 (a pop); s21 starts without it
    fc = fr(42.0)
    for o in (out or []):
        if o is not None and o.name.startswith('FX_end_trail_wake'):
            for a in ('hide_render', 'hide_viewport'):
                setattr(o, a, True); o.keyframe_insert(a, frame=fc)
            print('act_port: FX_end_trail_wake hidden from', fc)


# ---------------------------------------------------------------------------------------------------------------------------- s21
def s21(W, f0, f1):
    """The chain end smashes crane A: the box on its spreader is flung into the bay, the west leg buckles, the whole crane
    topples seaward and its boom slams into the water; the wave runs on and hits the dock gate."""
    t0, t1 = CM.tof(f0), CM.tof(f1)
    K = [(t0, (-286.0, 368.0, 10.0), (-372.0, 380.0, 24.0), 24.0, -1.0),
         (t0 + 0.45 * (t1 - t0), (-290.0, 365.0, 10.5), (-376.0, 372.0, 18.0), 24.0, 0.0),
         (t1, (-294.0, 362.0, 11.0), (-380.0, 366.0, 12.0), 24.0, 0.5)]
    ev = [(42.0, 1.0), (43.0, 1.0), (43.2, 0.6)]
    CM.base(W, f0, f1, _keys_fn(K, shake=0.4, events=ev, amp=1.3), local_flash=0.0)
    CM.chain_key(W, f0, f1)
    PL.port_life(W, f0, f1)
    _mech(W, f0, f1)


def _mech(W, f0, f1):
    try:
        import mechanim as MA
        MA.key_range(W, f0, f1)
    except Exception as ex:
        import traceback; traceback.print_exc(); print('act_port: mech keys failed', ex)


# ---------------------------------------------------------------------------------------------------------------------------- s22
def s22(W, f0, f1):
    """The surge runs up the flooded dock and explodes against the sleeping mech: the front breaks over its legs, a crown of
    water stands up in its lap and crashes over its head, debris is flung up out of it toward the lens; the gull bolts off
    its nest."""
    import mechanim as MA
    t0, t1 = CM.tof(f0), CM.tof(f1)
    h = MA.point('head', t0); ch = MA.point('chest', t0)
    K = [(t0, tuple(h + _v((40.0, -88.0, 3.5))), tuple(h + _v((2.0, -11.0, -4.5))), 28.0, -1.0),
         (t0 + 0.5 * (t1 - t0), tuple(h + _v((38.5, -85.0, 4.5))), tuple(h + _v((2.0, -10.0, -1.5))), 28.0, 0.0),
         (t1, tuple(h + _v((37.0, -82.0, 5.5))), tuple(h + _v((2.0, -9.0, 1.5))), 28.0, 0.5)]
    CM.base(W, f0, f1, _keys_fn(K, shake=0.5, events=[(44.0, 0.8), (44.1, 1.0)], amp=1.2))
    PL.port_life(W, f0, f1)
    _mech(W, f0, f1)
    if _want(W, 's22_surge'):
        # sized on the mech's real footprint (legs out in the dock to y 536, lap at y ~576, face at z ~21, antenna tip z 40):
        # the mech stays readable (FX hide <= 40 % of it at the peak, was 87 %) and the strike shot (s23, from 45.6) opens with
        # its tails below the frame (FX cover 11 % of s23 at 1095 -> 0 by 1110, was 77-100 %). Heavy drawn timing (fx auto).
        FXM = _fx(); C = W['C']['FX']
        zf = PL.FLOOD_Z1
        wall = FXM.splash_wall((-490.0, 556.0, zf), (-438.0, 556.0, zf), height=16.0, f0=fr(43.95), dur=None, coll=C, seed=2201,
                        zip=0.1, drops=110, name='FX_s22_front')
        crown = FXM.splash_crown((float(ch[0]), 574.0, zf), radius=9.0, height=24.0, f0=fr(44.05), dur=None, coll=C, seed=2202, jets=10,
                         drops=90, name='FX_s22_crown')
        # the strike (s23) cuts on its flash at 45.6: the standing water ends there (wall: sheet, plumes, crests; crown: sheet,
        # jets, beads, crests). With the foam-crowned plumes (06.11) they stood as a white column over the head's left half
        # through the strike's first frames (check3 f1100); the low surge, the drops and the foam carry on into s23
        fcut = fr(S.T['strike2'])
        for o in list(wall[:3]) + list(crown[:4]):
            for a in ('hide_render', 'hide_viewport'):
                setattr(o, a, True); o.keyframe_insert(a, frame=fcut)
        # out of the gap between the shins, up and back toward the lens: >= 1.8 m clear of the mech, >= 21 m of both lenses,
        # every piece lands in the flood (hidden below it) by 1135, before its end (no mid-air pops; checked on the keyed
        # drawings). delay: launches spread over 0.24 s (fx's default 0.15 x dur would park pieces at the source for 0.6 s)
        FXM.debris((float(ch[0]), 552.0, zf + 2.0), f0=fr(44.1), dur=96, coll=C, seed=2203, count=14,
                   kinds=('plank', 'container', 'beam'), speed=20.0, spread=0.3, direction=(0.0, -0.35, 0.94), size=1.0,
                   delay=0.06, z_floor=zf - 0.5, name='FX_s22_debris')


# ---------------------------------------------------------------------------------------------------------------------------- s23
def s23(W, f0, f1):
    """Lightning strikes the sleeping mech's antenna: the bolt, the star at the tip, sparks raining off the head, the
    charge crawling down into it."""
    import mechanim as MA
    t0, t1 = CM.tof(f0), CM.tof(f1)
    # the strike point: the red tip light (the 1 m needle over it is ~2 px thin here: a bolt ending on it read as floating
    # over the antenna), its top in the head's frame (head-local antenna_tip (-2.2, 2.2, 20.6) = the needle's top)
    BALL = (-2.2, 2.2, 19.5)
    tip = MA.point('head', S.T['strike2'], BALL); h = MA.point('head', t0)
    K = [(t0, tuple(h + _v((30.0, -44.7, -6.5))), tuple(h + _v((0.0, -2.7, 13.0))), 26.0, 2.0),    # opens high on the strike
         (t0 + 0.5 * (t1 - t0), tuple(h + _v((27.0, -40.7, -6.0))), tuple(h + _v((0.0, -2.2, 9.0))), 26.0, 1.0),   # (more sky,
         (t1, tuple(h + _v((24.0, -36.7, -5.5))), tuple(h + _v((0.0, -1.7, 6.0))), 26.0, 0.0)]     # a longer bolt), settles on the head
    CM.base(W, f0, f1, _keys_fn(K, shake=0.4, events=[(S.T['strike2'], 1.0)], amp=1.4), local_flash=0.3)
    PL.port_life(W, f0, f1)
    _mech(W, f0, f1)
    if _want(W, 's23_bolt'):
        FXM = _fx(); C = W['C']['FX']; fs = fr(S.T['strike2'])
        # the frame shows only the lowest ~16 m of the bolt (tip to the top edge): a 765 m bolt drew there as one straight 5 m
        # pillar (its finest kinks are 24 m apart). 222 m long: kinks every ~7 m (+-3 m), ~2 m thick at the tip (radius
        # 0.7 x 0.0035 x L x width); its top end stays far above the frame
        top = tip + _v((-20.0, 25.0, 220.0))
        # star=False: the bolt's own star (0.1 x length x width) would sit over the tip around the lens' sight line; the
        # strike's star is the 9 m kira on the tip below
        b = FXM.bolt('FX_s23_bolt', tuple(top), tuple(tip), seed=2301, branches=5, width=1.8, coll=C, star=False, taper=0.8)
        FXM.flicker(b, [fs], pattern=(1.0, 0.25, 1.0, 0.7, 0.4, 0.2))
        k = FXM.kira('FX_s23_kira', tuple(tip), 9.0, coll=C, seed=2302)
        FXM.flicker(k, [fs], pattern=(1.0, 0.6, 1.0, 0.6, 0.3))
        # the charge crawling down the 19 m mast into the head (bolt radius is 0.0035 x length x width: width 4 -> 0.27 m, ~7 px)
        a2 = FXM.bolt('FX_s23_arc', tuple(tip), tuple(h + _v((0.0, 0.0, 2.0))), seed=2303, branches=3, width=4.0, coll=C, star=False)
        FXM.flicker(a2, [fs + 3, fs + 18, fs + 31], pattern=(1.0, 0.5, 0.9, 0.3))    # it keeps crackling (audio: 45.6-47.3)
        # the jolt (mechanim, 45.62: the head snaps back, the mast tip moves 2.2 m = 34 px in one frame, settling by ~1106) runs
        # through the frame while these are lit: bolt end, star and arc ride the tip's offset from its 45.6 pose (on ones)
        for o in (b, k, a2):
            base = o.location.copy()
            for f in range(fs - 1, fs + 46):
                d = MA.point('head', CM.tof(f), BALL) - tip
                o.location = (base[0] + d[0], base[1] + d[1], base[2] + d[2]); o.keyframe_insert('location', frame=f)
            FXM._interp(o, 'CONSTANT', ('location',))
        FXM.sparks(tuple(tip), f0=fs, dur=30, coll=C, seed=2304, count=70, speed=18.0, direction=(0, 0, 1), spread=0.95, size=1.2,
                   gravity=12.0, name='FX_s23_sparks')
        # the struck head steams: puffs vent off the dome round the mast foot (dome top 8.2 m over the head point, measured; the
        # source 0.5 m under it) and drift off left in the wind (the first cut put the source 5 m inside the head)
        # wisps, not one 4 m puff parked on the nest (it read as a white cap on the head): smaller, rising faster, torn off
        # left by the wind
        # (still read as a white cap at 1.6 m: now small quick wisps, torn apart from a third of their life)
        FXM.steam(tuple(h + _v((0.0, -1.5, 7.7))), f0=fs + 2, dur=36, coll=C, seed=2305, count=14, size=0.85, speed=9.0,
                  direction=(-0.25, 0.0, 1.0), wind=(-6.0, 0.0, 0.0), life=0.85, tear=0.3, name='FX_s23_steam')


# ---------------------------------------------------------------------------------------------------------------------------- s24
# the visor in its own tracked frame (MA.mat('visor') == MECH_visor.matrix_world, scale 1; measured on the evaluated mesh):
# the two eye lights sit at local (+-1.81, -4.88, 3.25); the glass faces local (0, -0.777, 0.629) (forward and up, symmetric)
EYES_MID = np.array((0.0, -4.882, 3.254))
VIS_N = np.array((0.0, -0.777, 0.629)); VIS_UP = np.array((0.0, 0.629, 0.777)); VIS_X = np.array((1.0, 0.0, 0.0))


def s24(W, f0, f1):
    """EXTREME CU, straight into the visor: both eyes fill the frame (45-47 mm at 6.4 -> 5.4 m, a hair below the eye line);
    behind the rain-streaked glass the eyes flicker and power on; the head twitches at the boot (48.2) and starts to lift
    (48.6..): the camera stays put in the world (placed in the head's frame at the shot's start, slow push in) and its aim
    follows the eyes with a 3-frame lag, so the lift reads. Free space checked on the real meshes: >= 3 m to any mech part."""
    import mechanim as MA
    M0 = MA.mat('visor', CM.tof(f0)); R0 = M0[:3, :3]; P0 = M0[:3, 3]
    tl = EYES_MID + VIS_UP * 0.05

    def cam(t):
        u = min(1.0, max(0.0, (t - CM.tof(f0)) / max(1e-6, CM.tof(f1) - CM.tof(f0)))); u = u * u * (3.0 - 2.0 * u)
        pl = EYES_MID + VIS_N * (6.4 - 1.0 * u) + VIS_UP * (-0.45 + 0.1 * u) + VIS_X * (0.3 - 0.15 * u)
        aim = np.zeros(3)
        for k in range(3):
            M = MA.mat('visor', t - k / CM.FPS); aim += M[:3, :3] @ tl + M[:3, 3]
        return R0 @ pl + P0, aim / 3.0, 45.0 + 2.0 * u, 0.0
    # the far flash 48.9 is back in this shot (it had been pushed to the cut into s25 while the visor's glow covered the whole
    # glass and bloomed white under it; mech.py's visor now glows only in the eye lights and the flash skips them)
    CM.base(W, f0, f1, _shaky(cam, 0.2))
    _mech(W, f0, f1)


def _shaky(cam_fn, amp):
    """a faint hand-held drift on the aim (same scale as cam_keys' shake)."""
    import timeline as TLm
    def fn(t):
        pos, tgt, lens, roll = cam_fn(t)
        return pos, tgt + TLm.shake(t, amp, 6.0, 24) * np.linalg.norm(tgt - pos) * 0.004, lens, roll
    return fn


# ---------------------------------------------------------------------------------------------------------------------------- QA
def _frame():
    return __import__('bpy').context.scene.frame_current


UNDER_SEA = 0.6    # m: an overlap whose every crossing triangle lies this far under the sea surface is hidden by the opaque water


def under_sea(a, b, margin=UNDER_SEA):
    """True when a and b cross only under the water: for every crossing polygon pair of their evaluated meshes (BVH overlap) the
    crossing lies inside BOTH polygons, so its height is at most the lower of the two polygons' highest vertices (taken relative to
    the local sea surface: a tall dock-wall quad does not count, the small finger face it crosses does); every pair must sit
    `margin` under the surface (measured, not the bounding boxes: a finger crossing the dock above the water still fails)."""
    import bpy
    from mathutils.bvhtree import BVHTree
    import mechplan as MP
    dg = bpy.context.evaluated_depsgraph_get(); t = CM.tof(_frame()); got = []
    for o in (a, b):
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        if me is None or len(me.polygons) == 0:
            ev.to_mesh_clear(); return False
        Mw = ev.matrix_world; V = [Mw @ v.co for v in me.vertices]; F = [tuple(pp.vertices) for pp in me.polygons]
        ev.to_mesh_clear(); got.append((V, F, BVHTree.FromPolygons(V, F, all_triangles=False, epsilon=0.0)))
    pairs = got[0][2].overlap(got[1][2])
    if not pairs: return True
    rel = ({}, {})
    def top(side, k):
        r = rel[side].get(k)
        if r is None:
            V, F = got[side][0], got[side][1]
            r = max(V[vi].z - MP.water_z(V[vi].x, V[vi].y, t) for vi in F[k]); rel[side][k] = r
        return r
    for (i, j) in pairs:
        if min(top(0, i), top(1, j)) > -margin: return False
    return True


def _part(o):
    """(rig, part) of a port mover: crane A's pieces, a boat's hull / deckhouse, the lighthouse sections."""
    n = o.name
    if n.startswith('PORT_craneA_'): return 'craneA', n[len('PORT_craneA_'):]
    if n.startswith('PORT_boat_'):
        i, _, k = n[len('PORT_boat_'):].partition('_'); return 'boat' + i, k
    if n.startswith('LH_'): return 'LH', n[3:]
    return None, None


_JOINTS = {('legs', 'boom'), ('boom', 'trolley'), ('trolley', 'cab'), ('boom', 'cab'), ('trolley', 'ropes'), ('ropes', 'spreader'),
           ('spreader', 'box'), ('hull', 'top'), ('base', 'mid'), ('mid', 'top'), ('top', 'lamp')}


def _designed_joint(a, b):
    """designed contacts inside one port rig: crane A's hinge, the trolley on the boom rails, the cab under the trolley, the ropes
    into trolley and headblock, the box on its twistlocks; a boat's hull and its deckhouse; the lighthouse's sleeved sections.
    (The flung unit against the legs / boom / trolley is NOT allowed.)"""
    ra, pa = _part(a); rb, pb = _part(b)
    if ra is None or ra != rb: return False
    return (pa, pb) in _JOINTS or (pb, pa) in _JOINTS


def _allow_port(a, b):
    if _designed_joint(a, b): return True
    s = {a.name, b.name}
    if s == {'LH_base', 'PORT_bw_cap'}: return True          # the lighthouse stands on the breakwater cap (its base never moves)
    if s == {'PORT_craneA_legs', 'PORT_craneA_trolley'}:     # parked at work (YT0) its frame grazes the portal's seaward handrail
        return PL.trolley_y(CM.tof(_frame())) > -6.0         # (asset clash, reported); clear once it runs out past -5.3 (1032)
    if 'MECH_chest' in s and (s & {'PORT_dock', 'PORT_terrain'}) and _frame() <= (1190 if 'PORT_dock' in s else 1187):
        return True     # asleep (to 49.0): the backpack rests on the north quay top (mech.POSES sleep; a 0.2 m graze, no vertex inside),
                        # then lifts off it as the mech rises (probe 06.11: the dock <= 0.03 m to 1190, the slope 0.24 -> 0.08 m to 1187)
    return False


def _allow_s20(a, b):
    if _allow_port(a, b): return True
    s = {a.name, b.name}
    if 'PORT_craneA_boom' in s and any(n[:9] in ('CHAIN_064', 'CHAIN_065', 'CHAIN_066', 'CHAIN_067', 'CHAIN_068', 'CHAIN_069') for n in s):
        return 979 <= _frame() <= 991   # the bake sweeps links 65..68 through crane A's boom at 40.8..41.2 s (reported to the lead:
                                        # the bake needs the boom as a collider); here ~750 m off, the boom is ~70 px wide
    return False


def _allow_s21(a, b):
    if _allow_port(a, b): return True
    s = {a.name, b.name}
    if any(n.startswith('CHAIN_0') for n in s) and (s & {'PORT_craneA_spreader', 'PORT_craneA_box'}):
        return _frame() <= 1016                              # the smash itself (frames 1009..1016)
    return False


QA_ALLOW = {'s08': _allow_port, 's17': _allow_port, 's20': _allow_s20, 's21': _allow_s21, 's22': _allow_port, 's23': _allow_port,
            's24': _allow_port}

# designed snaps (qa_film): each passes only on its frame, for those parts, up to `max` m (the measured jump + ~30 %); a bigger
# jump, another frame or another part still fails. The gull's flight on twos (s22) needs no entry: qa_film judges it on twos.
_JOLT = 'mechanim T_JOLT 45.62: the lightning jolt snaps the head (mast, nest, moss) and the fingers back in 0.05 s'
_BOOT = 'mechanim T_BOOT 48.2: the boot shudder throws the head forward in 0.06 s'
QA_SNAPS = {
    's23': [dict(f=1097, obj='MECH_tiplight', max=2.6, why=_JOLT),                # measured 2.02 m (the mast tip, 19 m up)
            dict(f=1097, obj='MECH_antenna', max=1.25, why=_JOLT),                 # 0.94
            dict(f=1097, obj='MECH_nest', max=1.3, why=_JOLT),                     # 0.98
            dict(f=1097, obj='MECH_chick', max=1.3, why=_JOLT),                    # 1.00
            dict(f=1097, obj='MECH_moss_crown', max=1.25, why=_JOLT),              # 0.94
            dict(f=1097, obj='MECH_moss_brow', max=1.3, why=_JOLT),                # 0.98
            dict(f=1097, obj='MECH_finger[LR][0-2]_1', max=1.0, why=_JOLT),        # 0.67 .. 0.75
            dict(f=1097, obj='MECH_finger[LR][0-2]_2', max=2.3, why=_JOLT)],       # 1.51 .. 1.78
    's24': [dict(f=1159, obj='MECH_tiplight', max=1.2, why=_BOOT)],                # 0.93
}
