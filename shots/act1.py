# ANCHOR act 1 — the world (0-14 s): the floating city, its street, the dive down the chain, the port and the sleeping mech, the anchor.
import math
import numpy as np
import common as CM, world as WS, timeline as T

POST = {
    's01': dict(haze=(0.78, 0.86, 1.0), haze_dist=2600.0, haze_max=0.45, bloom=0.8),
    's02': dict(haze_dist=2000.0, haze_max=0.3),
    's03': dict(haze_dist=2100.0, haze_max=0.4),
    's04': dict(haze_dist=1800.0, haze_max=0.42),
    's05': dict(haze_dist=2000.0, haze_max=0.3, near=40.0),
    's06': dict(under=1.0, under_dist=70.0, under_col=(0.06, 0.45, 0.58), haze_max=0.0, bloom=1.0),
}


def chain_at_rest(W, f0, f1, sway=1.0):
    if 'chain' not in W: return
    for f in CM.frames(f0, f1):
        t = CM.tof(f)
        CM.chain_pose(W, f, CM.chain_rest(t, len(W['chain']) + 1, sway))


# ---------------------------------------------------------------------------------------------------------------------------- s01
def s01(W, f0, f1):
    """EST: High Harbor above scattered cumulus at sunrise; the camera arcs slowly; waterfalls; the chain going down."""
    c = WS.COLLAR_REST + np.array((0.0, 0.0, 120.0))
    K = [(CM.tof(f0), (330.0, -470.0, 400.0), tuple(c + (0, 0, 10)), 30.0, -1.5),
         (CM.tof(f1), (420.0, -360.0, 432.0), tuple(c + (0, 0, 22)), 30.5, -0.5)]
    CM.base(W, f0, f1, CM.cam_keys(K))
    CM.city_key(W, f0, f1)
    chain_at_rest(W, f0, f1)


# ---------------------------------------------------------------------------------------------------------------------------- s02
def s02(W, f0, f1):
    """CU street: windmill sails sweep past the lens, laundry flapping, the bell tower behind."""
    city = W.get('city') or {}
    view = city.get('street_view') if isinstance(city, dict) else None
    if view:   # (pos, tgt) offered by the CITY department, relative to the city root
        pos0 = np.array(view[0]); tgt0 = np.array(view[1])
    else:
        pos0 = WS.COLLAR_REST + np.array((40.0, -60.0, 212.0)); tgt0 = WS.COLLAR_REST + np.array((-40.0, 40.0, 214.0))
    off = WS.city_pos(0.0) - WS.COLLAR_REST
    K = [(CM.tof(f0), tuple(pos0 + off), tuple(tgt0 + off), 28.0, 0.0),
         (CM.tof(f1), tuple(pos0 + off + (3.0, 2.5, 0.6)), tuple(tgt0 + off + (2.0, 2.0, 0.0)), 28.0, 0.0)]
    CM.base(W, f0, f1, CM.cam_keys(K))
    CM.city_key(W, f0, f1)
    spin_city(W, f0, f1, speed=0.35)


def spin_city(W, f0, f1, speed=0.35, cloth=1.0):
    """Windmill sails turn (rev/s), laundry flaps, on twos."""
    city = W.get('city')
    if not isinstance(city, dict): return
    TL = W['TL']
    for i, s in enumerate(city.get('sails', [])):
        base = s.get('_base_rot') if hasattr(s, 'get') else None
        ax = s.get('spin_axis', 'Y') if hasattr(s, 'get') else 'Y'
        for f in CM.frames(f0, f1):
            t = CM.tof(T.twos(f, f0))
            a = (t * speed * (0.9 + 0.2 * ((i * 37) % 10) / 10.0) + i * 0.13) * 2 * math.pi
            r = list(s.rotation_euler)
            r['XYZ'.index(ax)] = a
            TL.eul(s, f, tuple(r))


# ---------------------------------------------------------------------------------------------------------------------------- s03
def s03(W, f0, f1):
    """The camera dives along the chain through the cloud layer; the links rush past; the port opens below."""
    t0, t1 = CM.tof(f0), CM.tof(f1)
    J = CM.chain_rest(t0, len(W['chain']) + 1 if 'chain' in W else 81, 1.0)
    def at_z(z):   # chain point at height z
        i = int(np.argmin(np.abs(J[:, 2] - z))); return J[i]
    def fn(t):
        u = T.smoother((t - t0) / (t1 - t0))
        z = 300.0 - 250.0 * u
        p = at_z(z) + np.array((22.0 - 6.0 * u, -16.0 + 4.0 * u, 0.0))
        tgt = at_z(max(-40.0, z - 140.0)) + np.array((0.0, 40.0 * u, 0.0))
        tgt = tgt + (np.array((-160.0, 300.0, -z * 0.5)) - tgt) * T.smooth((u - 0.55) / 0.45) * 0.55
        return p, tgt, 24.0, 8.0 * math.sin(u * 2.0)
    CM.base(W, f0, f1, fn)
    CM.city_key(W, f0, f1)
    chain_at_rest(W, f0, f1)


# ---------------------------------------------------------------------------------------------------------------------------- s04
def s04(W, f0, f1):
    """WIDE: the port at dawn — cranes, containers, dry dock 3 with the sleeping overgrown mech; the chain far off; the lighthouse."""
    K = [(CM.tof(f0), (-640.0, 150.0, 70.0), (-430.0, 560.0, 6.0), 28.0, 0.0),
         (CM.tof(f1), (-620.0, 185.0, 64.0), (-440.0, 565.0, 4.0), 29.0, 0.0)]
    CM.base(W, f0, f1, CM.cam_keys(K))
    CM.city_key(W, f0, f1)
    chain_at_rest(W, f0, f1)
    sleep_mech(W, f0, f1)


def sleep_mech(W, f0, f1, breathe=True):
    import mechanim as MA
    MA.key_range(W, f0, f1)


# ---------------------------------------------------------------------------------------------------------------------------- s05
def s05(W, f0, f1):
    """MACRO: the mech's head — the gull's nest with its chick, moss, the dark visor, the 07 stencil."""
    import mechanim as MA
    MA.key_range(W, f0, f1)
    def fn(t):
        h = MA.head_pos(W, t); fwd = MA.head_fwd(W, t)
        side = np.cross(fwd, np.array((0, 0, 1.0))); side /= max(np.linalg.norm(side), 1e-9)
        u = T.smooth((t - CM.tof(f0)) / (CM.tof(f1) - CM.tof(f0)))
        pos = h + fwd * 15.0 + side * (7.0 - 3.0 * u) + np.array((0, 0, 3.5 + 0.8 * u))
        return pos, h + np.array((0, 0, 3.0)), 45.0, 0.0
    CM.base(W, f0, f1, fn)


# ---------------------------------------------------------------------------------------------------------------------------- s06
def s06(W, f0, f1):
    """UNDERWATER: the coral-covered anchor, the shackle and its pin, fish schools, god rays, the chain rising toward the light."""
    a = WS.ANCHOR
    K = [(CM.tof(f0), tuple(a + (48.0, -42.0, 4.0)), tuple(a + (0.0, 0.0, 14.0)), 24.0, 0.0),
         (CM.tof(f1), tuple(a + (40.0, -52.0, 9.0)), tuple(a + (-6.0, 4.0, 24.0)), 24.0, 1.5)]
    CM.base(W, f0, f1, CM.cam_keys(K))
    chain_at_rest(W, f0, f1, sway=0.4)
    import underanim as UA
    UA.key_range(W, f0, f1, mode='calm')
