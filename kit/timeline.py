# ANCHOR timeline: the whole film is one Blender scene on one global timeline (frames 1..2160, 24 fps).
# Shots key their own frame ranges into a store; flush() writes every channel once with foreach_set (CONSTANT keys, so a value
# holds until that channel is keyed again). Camera paths are Catmull-Rom splines through keys (full tangents when keys are dense).
import bpy, math
import numpy as np
from mathutils import Vector, Quaternion, Matrix, Euler

FPS = 24


def fr(t):
    """film time (s) -> first frame at or after it (frame 1 = t 0)."""
    return int(round(t * FPS)) + 1


class Store:
    def __init__(s): s.d = {}          # (idb, path, index) -> {frame: value}

    def set(s, idb, path, frame, value):
        if isinstance(value, (tuple, list, Vector, Quaternion, Euler)) or (hasattr(value, '__len__') and not isinstance(value, str)):
            for i, v in enumerate(value): s.d.setdefault((idb, path, i), {})[int(frame)] = float(v)
        else: s.d.setdefault((idb, path, -1), {})[int(frame)] = float(value)

    def loc(s, o, f, v): s.set(o, 'location', f, v)
    def quat(s, o, f, q):
        o.rotation_mode = 'QUATERNION'; s.set(o, 'rotation_quaternion', f, q)
    def eul(s, o, f, e):
        o.rotation_mode = 'XYZ'; s.set(o, 'rotation_euler', f, e)
    def scale(s, o, f, v): s.set(o, 'scale', f, v)
    def prop(s, idb, name, f, v): s.set(idb, '["%s"]' % name, f, v)
    def hide(s, o, f, hidden): s.set(o, 'hide_render', f, 1.0 if hidden else 0.0)

    def flush(s):
        from bpy_extras import anim_utils
        n_keys = 0
        # fix quaternion sign flips per channel group before writing
        for (idb, path, idx), kv in sorted(s.d.items(), key=lambda x: (id(x[0][0]), x[0][1], x[0][2])):
            frames = sorted(kv); vals = [kv[f] for f in frames]
            pidx = 0 if idx < 0 else idx
            try: idb.keyframe_insert(data_path=path, index=pidx if idx >= 0 else -1, frame=-10000)
            except TypeError: idb.keyframe_insert(data_path=path, frame=-10000)
            ad = idb.animation_data
            cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
            fc = cb.fcurves.find(path, index=pidx)
            if fc is None: fc = cb.fcurves.find(path, index=0)
            fc.keyframe_points.clear()
            n = len(frames); fc.keyframe_points.add(n)
            co = [0.0] * (2 * n)
            for i, (f, v) in enumerate(zip(frames, vals)): co[2 * i] = f; co[2 * i + 1] = v
            fc.keyframe_points.foreach_set('co', co)
            fc.keyframe_points.foreach_set('interpolation', [0] * n)   # CONSTANT
            fc.update(); n_keys += n
        return n_keys


def quat_fix(qs):
    """Keep consecutive quaternions in the same hemisphere."""
    out = []; prev = None
    for q in qs:
        q = Quaternion(q)
        if prev is not None and prev.dot(q) < 0: q = -q
        out.append(q); prev = q
    return out


# --------------------------------------------------------------------------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def smooth(x): x = clamp(x); return x * x * (3 - 2 * x)
def smoother(x): x = clamp(x); return x * x * x * (x * (x * 6 - 15) + 10)
def ease_in(x, p=2.0): return clamp(x) ** p
def ease_out(x, p=2.0): return 1 - (1 - clamp(x)) ** p
def lerp(a, b, u):
    if isinstance(a, (tuple, list, np.ndarray)): return tuple(x + (y - x) * u for x, y in zip(a, b))
    return a + (b - a) * u
def remap(t, t0, t1): return clamp((t - t0) / max(1e-9, t1 - t0))
def twos(f, f0): return f0 + ((f - f0) // 2) * 2
def threes(f, f0): return f0 + ((f - f0) // 3) * 3


# --------------------------------------------------------------------------------------------------------------------------------- splines
def catmull(keys, t, dims=None):
    """keys: [(t, (v...)), ...] sorted. Centripetal-ish Catmull-Rom with full tangents; clamps at the ends."""
    ts = [k[0] for k in keys]
    if t <= ts[0]: return np.array(keys[0][1], float)
    if t >= ts[-1]: return np.array(keys[-1][1], float)
    i = max(0, min(len(keys) - 2, np.searchsorted(ts, t, side='right') - 1))
    t0, p0 = keys[i]; t1, p1 = keys[i + 1]
    p0 = np.array(p0, float); p1 = np.array(p1, float)
    pm = np.array(keys[i - 1][1], float) if i > 0 else p0 - (p1 - p0)
    tm = keys[i - 1][0] if i > 0 else t0 - (t1 - t0)
    p2 = np.array(keys[i + 2][1], float) if i + 2 < len(keys) else p1 + (p1 - p0)
    t2 = keys[i + 2][0] if i + 2 < len(keys) else t1 + (t1 - t0)
    h = t1 - t0; s = (t - t0) / h
    m0 = (p1 - pm) / (t1 - tm) * h
    m1 = (p2 - p0) / (t2 - t0) * h
    s2 = s * s; s3 = s2 * s
    return (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * m1


def look_quat(pos, tgt, roll_deg=0.0):
    d = Vector(tgt) - Vector(pos)
    q = d.to_track_quat('-Z', 'Y')
    if roll_deg: q = q @ Euler((0, 0, math.radians(roll_deg))).to_quaternion()
    return q


def shake(t, amp, freq=7.0, seed=1):
    """Smooth hand-held / impact shake (metres or degrees), deterministic."""
    r = np.random.default_rng(seed)
    ph = r.uniform(0, 100, 6)
    return np.array([amp * (math.sin(t * freq * 1.0 + ph[0]) * 0.6 + math.sin(t * freq * 2.31 + ph[1]) * 0.4),
                     amp * (math.sin(t * freq * 1.13 + ph[2]) * 0.6 + math.sin(t * freq * 2.07 + ph[3]) * 0.4),
                     amp * (math.sin(t * freq * 0.91 + ph[4]) * 0.6 + math.sin(t * freq * 1.77 + ph[5]) * 0.4)])
