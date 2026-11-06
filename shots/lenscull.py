# ANCHOR — drops at the lens (06.11). A drawn droplet that passes a few metres from the shot's camera grows into a big white
# cone with a hard light/shade split (falling, its tail points up): the "ice cones" of s26 f1259 were drops shed off the hip
# 28 m out and a crown's drop 15 m out, under a 22 mm lens. After every shot is keyed, every element of every drop flipbook is
# measured on screen through the camera of each frame it is drawn in (that frame's drawing, only while the object shows and
# the frame's shot renders its set). Each drawing (key block) gets its own factor per element: an element whose bounding
# radius would pass R_MAX px in the frames that drawing is shown is scaled about its own centre down to R_MAX there, so on
# screen a drop flying at the lens grows up to R_MAX and stops growing (its screen size stays continuous: no popping), while
# the same drop far off, in the other drawings, keeps its size (the first pass used one factor for an element's whole life
# and thinned whole splashes, s08's bow spray to dots, for one close pass).
#   shrink_near_drops(W, sets_of_frame)   (film.key_shots calls it after the keys are written)
import re
import numpy as np
from mathutils import Quaternion

R_MAX = 24.0                 # px: bounding radius of one drop element (drawn length ~48 px at 1080p): a drawn drop up to
                             # this reads as a drop; the lens cones were r 50-180 px (12 px also shrank s34's cascade)
NEAR = 0.6                   # m: an element this close to the lens (inside the clip sphere) counts as filling the frame
M_TPL = 162                  # vertices of one tpl_drop element (icosphere sub 3)
PAT = re.compile(r'(drops(\d\d)?$|^FX_am_shed_|_rust\d\d$)')
DEBUG = re.compile(r'^(FX_am_step_49_60_R_drops|FX_am_shed_hipR_5|FX_s08_boat0_bowdrops)$')   # names that print the trail
WPX, HPX = 1920.0, 1080.0


def _fc(idb, path, index=0):
    """the F-curve animating idb.path[index]: the ID's own slot first (5.x layered actions), then any channelbag, then the
    legacy action.fcurves (the same walk as stage.fcurves, which the flipbooks' CONSTANT keys rely on)."""
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None: return None
    act = ad.action; fcs = []
    try: fcs = list(act.fcurves)
    except AttributeError:
        slot = getattr(ad, 'action_slot', None)
        for layer in act.layers:
            for strip in layer.strips:
                own = None
                if slot is not None:
                    try: own = strip.channelbag(slot)
                    except Exception: own = None
                bags = ([own] if own is not None else []) + [cb for cb in strip.channelbags if cb != own]
                for cb in bags: fcs += list(cb.fcurves)
    for fc in fcs:
        if fc.data_path == path and fc.array_index == index: return fc
    return None


def _cams(W):
    """frame -> (camera position, camera rotation matrix (columns: right, up, back), focal length in px), from the keys."""
    d = W['TL'].d; cam = W['cam']
    L = [d.get((cam, 'location', i), {}) for i in range(3)]
    Q = [d.get((cam, 'rotation_quaternion', i), {}) for i in range(4)]
    F = d.get((cam.data, 'lens', -1), {})
    sw = float(cam.data.sensor_width)
    out = {}
    for f in L[0]:
        if all(f in L[i] for i in range(3)) and all(f in Q[i] for i in range(4)) and f in F:
            R = np.array(Quaternion([Q[i][f] for i in range(4)]).normalized().to_matrix())
            out[int(f)] = (np.array([L[i][f] for i in range(3)]), R, F[f] / sw * WPX)
    return out


def _drawings(o, nv):
    """[(first frame, key block index or None)] in frame order; None: the mesh itself (a single drawing)."""
    key = o.data.shape_keys
    if key is None or len(key.key_blocks) < 2: return [(-10 ** 6, None)]
    fc = _fc(key, 'eval_time')
    if fc is None: return [(-10 ** 6, 0)]
    pos = {round(kb.frame, 3): i for i, kb in enumerate(key.key_blocks)}
    dr = sorted((int(round(k.co[0])), pos.get(round(k.co[1], 3))) for k in fc.keyframe_points)
    return [(f, i) for f, i in dr if i is not None]


def _world(o):
    """the object's world matrix from its own transform (and its parents'): the FX are created while the shots are keyed and
    no depsgraph update has run since, so o.matrix_world is still the identity (the first pass measured every drop at the
    world origin and shrank none)."""
    M = o.matrix_basis.copy()
    if o.parent is not None: M = _world(o.parent) @ o.matrix_parent_inverse @ M
    return M


def _shown(o, f0, f1):
    """frames in [f0, f1) the object is not hidden (its hide_render keys)."""
    hf = _fc(o, 'hide_render')
    if hf is None: return [f for f in range(f0, f1) if not o.hide_render]
    return [f for f in range(f0, f1) if hf.evaluate(f) < 0.5]


def shrink_near_drops(W, sets_of_frame, r_max=R_MAX, log=print):
    cams = _cams(W)
    if not cams: log('LENSCULL no camera keys'); return 0
    f_first, f_last = min(cams), max(cams)
    home = {}
    for k, c in W['C'].items():
        for o in c.all_objects: home.setdefault(o.name, set()).add(k)
    tot_o = tot_e = tot_s = tot_d = 0; seen = set(); rep = []; W['lenscull'] = rep
    for k, c in W['C'].items():
        for o in c.all_objects:
            if o.type != 'MESH' or o.name in seen or not PAT.search(o.name): continue
            seen.add(o.name)
            nv = len(o.data.vertices)
            if nv == 0 or nv % M_TPL: continue
            n = nv // M_TPL; sets = home.get(o.name, {k})
            try: dr = _drawings(o, nv)
            except Exception as ex: log('LENSCULL %s: drawings failed %r' % (o.name, ex)); continue
            key = o.data.shape_keys
            Mw = np.array(_world(o)); A = Mw[:3, :3]; t = Mw[:3, 3]
            sca = float(np.max(np.linalg.norm(A, axis=0)))
            geo = {}

            def get(i):
                if i not in geo:
                    V = np.empty(nv * 3, np.float32)
                    (o.data.vertices if i is None else key.key_blocks[i].data).foreach_get('co', V)
                    V = V.reshape(n, M_TPL, 3).astype(np.float64)
                    cc = V.mean(1); r = np.linalg.norm(V - cc[:, None, :], axis=2).max(1) * sca
                    geo[i] = (cc @ A.T + t, r)
                return geo[i]
            # per drawing (key block): each element's worst screen radius over the frames that block is shown in
            rblk = {}; fblk = {}
            for j, (fa, i) in enumerate(dr):
                fb = dr[j + 1][0] if j + 1 < len(dr) else f_last + 1
                fa = max(fa, f_first)
                if fb <= fa: continue
                fs = [f for f in _shown(o, fa, fb) if f in cams and (sets_of_frame.get(f, set()) & sets)]
                if not fs: continue
                cw, r = get(i); alive = r > 1e-5
                rm = rblk.setdefault(i, np.zeros(n)); fm = fblk.setdefault(i, np.zeros(n, int))
                for f in fs:
                    P, R, fpx = cams[f]
                    v = (cw - P) @ R                                  # camera space: x right, y up, -z forward
                    dep = -v[:, 2]; front = dep > 0.05
                    dd = np.where(front, dep, 1.0)
                    rpx = r / dd * fpx; sx = v[:, 0] / dd * fpx; sy = v[:, 1] / dd * fpx
                    inside = front & (np.abs(sx) < WPX / 2 + rpx) & (np.abs(sy) < HPX / 2 + rpx)
                    near = np.linalg.norm(v, axis=1) < r + NEAR
                    val = np.where(alive & near, 1e4, np.where(alive & inside, rpx, 0.0))
                    up = val > rm; rm[up] = val[up]; fm[up] = f
            tot_o += 1; tot_e += n
            if not rblk: continue
            sblk = {i: np.where(rm > r_max, r_max / np.maximum(rm, 1e-9), 1.0) for i, rm in rblk.items()}
            hit = np.zeros(n, bool)
            for s in sblk.values(): hit |= s < 1.0
            ns = int(hit.sum()); nd = sum(int((s < 1.0).any()) for s in sblk.values())
            worst = max(rblk, key=lambda i: float(rblk[i].max())); w = int(np.argmax(rblk[worst]))
            if DEBUG.search(o.name):
                log('LENSCULL dbg %s: n %d drawings %d blocks measured %d, worst %.1f px at f%d (block %s), elements over %d px: %d' % (
                    o.name, n, len(dr), len(rblk), rblk[worst][w], fblk[worst][w], worst, r_max, ns))
            tot_s += ns; tot_d += nd
            if not ns: continue
            for i, s in sblk.items():
                if not (s < 1.0).any(): continue
                src = o.data.vertices if i is None else key.key_blocks[i].data
                V = np.empty(nv * 3, np.float32); src.foreach_get('co', V); V = V.reshape(n, M_TPL, 3).astype(np.float64)
                cc = V.mean(1, keepdims=True)
                V = (cc + (V - cc) * s[:, None, None]).astype(np.float32).ravel()
                src.foreach_set('co', V)
                if i == 0: o.data.vertices.foreach_set('co', V)
            o.data.update()
            log('LENSCULL %s: %d/%d elements capped in %d/%d drawings, worst %.0f px at f%d (x%.2f there)' % (
                o.name, ns, n, nd, len(rblk), rblk[worst][w], fblk[worst][w], sblk[worst][w]))
            rep.append((o.name, ns, n, float(rblk[worst][w]), int(fblk[worst][w]), float(sblk[worst][w])))
    log('LENSCULL total: %d drop objects, %d elements, %d capped in %d drawings (r_max %.0f px)' % (tot_o, tot_e, tot_s, tot_d, r_max))
    return tot_s
