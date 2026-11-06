# ANCHOR — the story state of the world as functions of film time t (seconds). Every shot reads these so continuity holds.
import math
import numpy as np

T = {   # beats (s)
    'storm_seen': 14.0, 'collar_taut': 20.0, 'strike1': 24.6, 'discharge': 25.8, 'shackle_hot': 28.0, 'pin_shear': 30.6,
    'whip': 31.6, 'burst': 33.6, 'lurch': 35.4, 'crystals': 37.6, 'crane_hit': 42.5, 'mech_wet': 44.2, 'strike2': 45.9,
    'eyes_on': 47.9, 'rise': 49.0, 'stand': 52.0, 'step': 53.2, 'run0': 55.0, 'leap': 64.0, 'land': 65.9, 'grab': 69.2,
    'taut': 70.2, 'wind0': 76.4, 'wind1': 78.4, 'spout_pass': 79.4, 'slack': 81.0, 'open': 82.0, 'gull_back': 86.9, 'dim': 88.6,
}

COLLAR_REST = np.array((-180.0, 60.0, 320.0))
ANCHOR = np.array((-100.0, 150.0, -52.0))
LIGHTHOUSE = np.array((-700.0, -168.0, 0.0))
DOCK_SEAT = np.array((-460.0, 585.0, -14.0))


def sstep(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
def rng(t, a, b): return min(1.0, max(0.0, (t - a) / (b - a)))


def storm(t):
    """0 clear .. 1 full storm overhead."""
    if t < 14.0: return 0.0
    if t < 30.0: return 0.15 + 0.85 * sstep(rng(t, 14.0, 30.0))
    if t < 80.6: return 1.0
    return 1.0 - sstep(rng(t, 80.6, 85.0)) * 0.92


CITY_PATH = [  # (t, x, y, z) of the collar point
    (0.0, -180.0, 60.0, 320.0), (33.6, -180.0, 60.0, 320.0), (37.4, -215.0, 120.0, 352.0), (42.5, -300.0, 215.0, 356.0),
    (49.0, -390.0, 120.0, 358.0), (55.0, -450.0, 20.0, 360.0), (61.0, -560.0, -150.0, 362.0), (66.0, -640.0, -290.0, 362.0),
    (69.2, -680.0, -350.0, 362.0), (72.0, -705.0, -392.0, 360.0), (76.0, -700.0, -400.0, 358.0), (79.4, -690.0, -395.0, 356.0),
    (82.0, -650.0, -360.0, 352.0), (90.0, -630.0, -340.0, 350.0),
]


def city_pos(t):
    P = CITY_PATH
    if t <= P[0][0]: return np.array(P[0][1:])
    for a, b in zip(P, P[1:]):
        if a[0] <= t <= b[0]:
            u = sstep((t - a[0]) / (b[0] - a[0]))
            return np.array(a[1:]) + (np.array(b[1:]) - np.array(a[1:])) * u
    return np.array(P[-1][1:])


def city_tilt(t):
    """(rx, ry, rz) degrees: still at rest, a lurch when the chain lets go, wobble while drifting, a pull when caught, level at the end."""
    rx = ry = rz = 0.0
    if t > 33.6:
        k = sstep(rng(t, 33.6, 36.0)) * (1.0 - 0.75 * sstep(rng(t, 38.0, 44.0)))
        rx += -7.0 * k; ry += 4.0 * k
        w = sstep(rng(t, 36.0, 40.0)) * (1.0 - sstep(rng(t, 80.6, 84.0)))
        rx += 1.6 * math.sin(t * 0.9) * w; ry += 1.2 * math.sin(t * 0.7 + 1.0) * w
        rz += -6.0 * sstep(rng(t, 37.0, 70.0))
    if t > 69.2:
        k = sstep(rng(t, 69.2, 71.0)) * (1.0 - sstep(rng(t, 80.6, 84.0)))
        rx += 5.0 * k
    return np.array((rx, ry, rz))


def spout_pos(t):
    a = np.array((-3500.0, -2500.0)); b = np.array((-1500.0, -1100.0)); c = np.array((-760.0, -680.0)); d = np.array((-150.0, -900.0))
    if t < 22.0: return None
    if t < 60.0: u = sstep(rng(t, 22.0, 60.0)); p = a + (b - a) * u
    elif t < 79.4: u = rng(t, 60.0, 79.4); p = b + (c - b) * u
    else: u = sstep(rng(t, 79.4, 90.0)); p = c + (d - c) * u
    return np.array((p[0], p[1], 0.0))


def sun(t):
    """(azimuth, elevation, colour hex) — a low morning sun from the east, a touch higher and whiter after the storm."""
    if t < 82.0: return 95.0, 17.0, '#ffe6c6'
    u = sstep(rng(t, 82.0, 86.0))
    return 95.0, 17.0 + 3.0 * u, '#ffeccc'


def eyes(t):
    if t < T['eyes_on']: return 0.0
    if t < T['eyes_on'] + 0.5:     # boot flicker on threes
        k = int((t - T['eyes_on']) * 8) % 2
        return 0.35 + 0.65 * k
    if 72.0 <= t < 73.6: return 0.6 + 0.4 * (int(t * 12) % 3 != 0)
    if t >= T['dim']: return max(0.0, 1.0 - (t - T['dim']) / 1.2)
    return 1.0
