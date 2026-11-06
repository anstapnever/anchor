# ANCHOR — shot QA on the real, keyed, evaluated geometry. A shot does not render until its report says PASS.
#   called by film.py:  blender -b -P shots/film.py -- qa s21,s22        -> out/qa/<sid>.json + 'QA <sid> PASS|FAIL ...'
# Checks, on EVERY frame of the shot (FR=lo-hi env narrows it; QA_STEP=n samples every n-th frame):
#   1 movers vs the set: every mesh that moves (mech parts + overgrowth, chain links, boats, crane A parts, lighthouse parts, city
#     loose parts) against every visible static mesh it comes near (AABB, then BVH triangle overlap). Designed contacts are allowed by
#     predicates (mech.qa_allow, the gripped link in the palm, a foot in the sea is not a mesh contact, ...).
#   2 movers vs movers: mech self (qa_allow), mech vs chain (except the held link vs the gripping hand), chain vs chain (non-adjacent
#     links; adjacent links interlock by design).
#   3 camera: never inside a closed mesh, nearest surface >= NEAR_MIN, above the sea (not in UNDER shots) / below it (UNDER shots),
#     never inside the city rock (tested in the city's local frame).
#   4 smoothness: camera speed/acceleration spikes, teleports of any animated mover (frame-to-frame jump vs its neighbours).
#     Animation on twos is judged on twos: a drawing held one frame on each side (exact holds, with the next or previous drawing 2
#     frames away) is a 2-frame jump and is compared with the drawings before and after it, not with the holds. Each run of
#     visible frames is judged on its own (hidden -> shown again somewhere else is a visibility change, not a teleport).
# Allowances specific to a shot: a module may define QA_ALLOW = {sid: callable(a, b) -> bool} next to its shot functions,
# QA_POST = {sid: callable(a, b) -> bool}: asked only AFTER a and b's triangles really cross (costly measured tests, e.g. the
# crossing lies under the opaque sea); a pair it passes is listed under 'post_allowed' in the report instead of failing; and
# QA_SNAPS = {sid: [dict(f=frame or (lo, hi), obj='fnmatch pattern', max=metres, why='...'), ...]}: designed snaps (a jolt,
# a shudder). A teleport passes only on that frame, for a matching object and up to `max` m; it is listed under 'designed' in
# the report instead of failing. A larger jump fails ('over the designed cap'); entries that matched nothing are listed as
# 'unused_snaps' (the animation changed: review the list).
import bpy, math, json, os, time, fnmatch
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

EPS_HOLD = 1e-3         # m: a mover that moved less than this between two frames is holding its drawing. (1e-4 was below float32
                        # precision 735 m from the origin: the gull's exact world holds on its nest read as 0.1-mm moves there, so
                        # s42's flight on twos was judged on ones and failed as 'teleports'. 1 mm is still far under a pixel.)

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'out', 'qa'); os.makedirs(OUT, exist_ok=True)
NEAR_MIN = 0.6          # metres from the lens to the nearest surface (clip_start is 0.1 on CAM)
SEA_MARGIN = 1.2        # the camera stays this far above the mean sea (waves) in air shots


def _mesh_world(o, dg):
    ev = o.evaluated_get(dg)
    try: me = ev.to_mesh()
    except Exception: return None
    if me is None or len(me.polygons) == 0:
        try: ev.to_mesh_clear()
        except Exception: pass
        return None
    Mw = ev.matrix_world.copy()
    V = [Mw @ v.co for v in me.vertices]; F = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    lo = Vector((min(v.x for v in V), min(v.y for v in V), min(v.z for v in V)))
    hi = Vector((max(v.x for v in V), max(v.y for v in V), max(v.z for v in V)))
    return BVHTree.FromPolygons(V, F, all_triangles=False, epsilon=0.0), lo, hi


def _hit(a, b, pad=0.0):
    """AABB test on (obj, bvh, lo, hi) entries."""
    return all(a[2][i] - pad <= b[3][i] and b[2][i] - pad <= a[3][i] for i in range(3))


def _hidden_now(o, hidden_colls):
    if o.hide_render: return True
    for c in o.users_collection:
        if c.name in hidden_colls: return True
    return False


def _all_hidden_colls(W):
    out = set()
    def walk(c, hid):
        hid = hid or c.hide_render
        if hid: out.add(c.name)
        for ch in c.children: walk(ch, hid)
    walk(W['sc'].collection, False)
    return out


def _movers(W):
    """(name -> kind) of every mesh that moves in the film."""
    mv = {}
    m = W.get('mech')
    if isinstance(m, dict):
        for o in m.get('meshes', []):
            if o.type == 'MESH': mv[o.name] = 'mech'
        for k in ('gull', 'chick'):
            g = m.get(k)
            if isinstance(g, dict):
                for o in g.values():
                    if hasattr(o, 'type') and o.type == 'MESH': mv[o.name] = 'bird'
                    if hasattr(o, 'children_recursive'):
                        for c in o.children_recursive:
                            if c.type == 'MESH': mv[c.name] = 'bird'
            elif g is not None and hasattr(g, 'type'):
                for c in [g] + list(g.children_recursive):
                    if c.type == 'MESH': mv[c.name] = 'bird'
    for o in W.get('chain', []): mv[o.name] = 'chain'
    p = W.get('port')
    if isinstance(p, dict):
        for b in p.get('boats', []) or []:
            for c in [b] + list(b.children_recursive):
                if c.type == 'MESH': mv[c.name] = 'boat'
        ca = p.get('craneA') or {}
        for k, o in ca.items():
            for c in ([o] if hasattr(o, 'type') else []) + (list(o.children_recursive) if hasattr(o, 'children_recursive') else []):
                if c.type == 'MESH': mv[c.name] = 'crane'
        lh = p.get('lighthouse') or {}
        for k in ('base', 'mid', 'top', 'lamp'):
            o = lh.get(k)
            if o is not None:
                for c in [o] + list(o.children_recursive):
                    if c.type == 'MESH' and 'beam' not in c.name.lower(): mv[c.name] = 'lh'
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.get('qa_mover'): mv[o.name] = str(o.get('qa_mover'))
    return mv


def _allow_default(W):
    mech_mod = W.get('mech_mod')
    def allow(a, b, kinds):
        ka, kb = kinds.get(a.name), kinds.get(b.name)
        if ka == 'mech' and kb == 'mech' and mech_mod is not None:
            import mechanim as _MA
            return _MA.allow(a, b)
        if 'fx' in (str(a.get('qa_kind', '')), str(b.get('qa_kind', ''))): return True
        if a.name.startswith('FX_') or b.name.startswith('FX_'): return True
        if {ka, kb} == {'chain'}:
            ia, ib = a.get('link_i'), b.get('link_i')
            if ia is None:
                try: ia = int(a.name.split('_')[1]); ib = int(b.name.split('_')[1])
                except Exception: return False
            return abs(int(ia) - int(ib)) <= 1          # interlocked neighbours
        for x, y in ((a, b), (b, a)):
            if y.name in str(x.get('touch', '')).split(','): return True
        return False
    return allow


def run(W, sid, f0, f1):
    sc = W['sc']; t_start = time.time()
    if os.environ.get('FR'):
        lo, hi = [int(x) for x in os.environ['FR'].split('-')]; f0 = max(f0, lo); f1 = min(f1, hi)
    step = int(os.environ.get('QA_STEP', '1'))
    kinds = _movers(W)
    mod_allow = None; snaps = []; mod_post = None
    try:
        import film
        m, _ = film.shot_fn(sid)
        if m is not None and hasattr(m, 'QA_ALLOW'): mod_allow = m.QA_ALLOW.get(sid)
        if m is not None and hasattr(m, 'QA_SNAPS'): snaps = list(m.QA_SNAPS.get(sid) or [])
        if m is not None and hasattr(m, 'QA_POST'): mod_post = m.QA_POST.get(sid)
    except Exception: pass
    allow0 = _allow_default(W)
    def allow(a, b):
        if allow0(a, b, kinds): return True
        return bool(mod_allow and mod_allow(a, b))
    under = 'UNDER' in next(s for s in __import__('film').SHOTS if s[0] == sid)[3].split()
    hidden_colls = _all_hidden_colls(W)
    # static meshes: everything visible that is not a mover, the sky dome, the sea, clouds, FX or the city (tested in its frame)
    city = W.get('city'); city_objs = set()
    if isinstance(city, dict):
        city_objs = {o.name for o in city.get('objs', [])} | {o.name for o in city['root'].children_recursive}
    skip_static = ('SKY', 'SEA', 'CLOUD', 'FX_', 'UNDER_ray', 'UNDER_snow', 'UNDER_surface', 'UNDER_backdrop', 'UNDER_fish', 'PORT_sea')
    sc.frame_set(f0); dg = bpy.context.evaluated_depsgraph_get()
    statics = {}
    for o in sc.objects:
        if o.type != 'MESH' or o.name in kinds or o.name in city_objs: continue
        if o.name.upper().startswith(skip_static) or o.name.startswith(skip_static): continue
        if _hidden_now(o, hidden_colls): continue
        if o.get('qa_kind') == 'fx': continue
        r = _mesh_world(o, dg)
        if r: statics[o.name] = (o,) + r
    # the city in its own frame (camera test only)
    city_tree = None
    if isinstance(city, dict) and not city['root'].hide_render and not _hidden_now(city['root'], hidden_colls):
        Ri = city['root'].matrix_world.inverted(); V = []; F = []
        for o in city.get('objs', []):
            if o.type != 'MESH' or o.hide_render: continue
            ev = o.evaluated_get(dg); me = ev.to_mesh()
            if me is None: continue
            Ml = Ri @ ev.matrix_world; b = len(V)
            V.extend(Ml @ v.co for v in me.vertices); F.extend(tuple(b + i for i in p.vertices) for p in me.polygons)
            ev.to_mesh_clear()
        if F: city_tree = BVHTree.FromPolygons(V, F, all_triangles=False, epsilon=0.0)
    print('QA %s statics %d movers %d (%.1fs)' % (sid, len(statics), len(kinds), time.time() - t_start))
    G = 40.0; grid = {}
    for sn, s in statics.items():
        for gx in range(int(math.floor(s[2].x / G)), int(math.floor(s[3].x / G)) + 1):
            for gy in range(int(math.floor(s[2].y / G)), int(math.floor(s[3].y / G)) + 1):
                grid.setdefault((gx, gy), []).append(sn)
    def near_statics(lo, hi, pad=0.1):
        out = set()
        for gx in range(int(math.floor((lo.x - pad) / G)), int(math.floor((hi.x + pad) / G)) + 1):
            for gy in range(int(math.floor((lo.y - pad) / G)), int(math.floor((hi.y + pad) / G)) + 1):
                out.update(grid.get((gx, gy), ()))
        return out
    bad = {}; cam_bad = []; cam_path = []; mover_paths = {}; post_ok = {}
    cam = W['cam']
    for f in range(f0, f1 + 1, step):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
        mv = {}
        for nm, kd in kinds.items():
            o = bpy.data.objects.get(nm)
            if o is None or _hidden_now(o, hidden_colls): continue
            r = _mesh_world(o, dg)
            if r: mv[nm] = (o,) + r
        for nm, (o, *_rest) in list(mv.items()):
            if kinds[nm] in ('mech', 'chain', 'boat', 'crane', 'bird'):
                mover_paths.setdefault(nm, []).append((f, tuple(o.matrix_world.translation)))
        # 1 + 2: movers vs statics, movers vs movers
        names = sorted(mv)
        for i, an in enumerate(names):
            a = mv[an]
            for sn in near_statics(a[2], a[3]):
                s = statics[sn]
                if not _hit(a, s, 0.05): continue
                if allow(a[0], s[0]): continue
                if a[1].overlap(s[1]):
                    if mod_post and mod_post(a[0], s[0]): post_ok.setdefault((an, sn), []).append(f)
                    else: bad.setdefault((an, sn), []).append(f)
            for bn in names[i + 1:]:
                b = mv[bn]
                if not _hit(a, b, 0.05): continue
                if allow(a[0], b[0]): continue
                if a[1].overlap(b[1]):
                    if mod_post and mod_post(a[0], b[0]): post_ok.setdefault((an, bn), []).append(f)
                    else: bad.setdefault((an, bn), []).append(f)
        # 3: camera
        cp = cam.matrix_world.translation.copy(); cam_path.append((f, tuple(cp), tuple(cam.matrix_world.to_quaternion())))
        dmin = 1e9; who = None
        cand = [(n_, statics[n_]) for n_ in near_statics(cp - Vector((50, 50, 50)), cp + Vector((50, 50, 50)))] + list(mv.items())
        for nm, s in cand:
            lo, hi = s[2], s[3]
            if not (lo.x - 50 < cp.x < hi.x + 50 and lo.y - 50 < cp.y < hi.y + 50 and lo.z - 50 < cp.z < hi.z + 50): continue
            loc, nrm, idx, d = s[1].find_nearest(cp)
            if loc is not None and d < dmin: dmin, who = d, nm
            if loc is not None and d < 25.0:
                inside = (cp - loc).dot(nrm) < 0 if nrm is not None else False
                if inside:
                    # parity test along +Z to confirm (open meshes give false 'inside')
                    n = 0; p = cp.copy()
                    for _ in range(64):
                        h = s[1].ray_cast(p + Vector((0, 0, 1e-3)), Vector((0, 0, 1)), 1e5)
                        if h[0] is None: break
                        n += 1; p = h[0]
                    if n % 2 == 1: cam_bad.append((f, 'inside', nm, round(d, 2)))
        if city_tree is not None:
            pl = city['root'].matrix_world.inverted() @ cp
            loc, nrm, idx, d = city_tree.find_nearest(pl)
            if loc is not None and d < dmin: dmin, who = d, 'CITY'
            if loc is not None and d < 25.0 and (pl - loc).dot(nrm) < 0:
                n = 0; p = pl.copy()
                for _ in range(64):
                    h = city_tree.ray_cast(p + Vector((0, 0, 1e-3)), Vector((0, 0, 1)), 1e5)
                    if h[0] is None: break
                    n += 1; p = h[0]
                if n % 2 == 1: cam_bad.append((f, 'inside', 'CITY', round(d, 2)))
        if dmin < NEAR_MIN: cam_bad.append((f, 'near', who, round(dmin, 2)))
        if not under and cp.z < SEA_MARGIN: cam_bad.append((f, 'below_sea', None, round(cp.z, 2)))
        if under and cp.z > -1.5: cam_bad.append((f, 'above_surface_in_under_shot', None, round(cp.z, 2)))
    # 4: smoothness
    jerks = []
    if len(cam_path) >= 5:
        P = np.array([p for _, p, _ in cam_path]); v = np.diff(P, axis=0); a = np.diff(v, axis=0); am = np.linalg.norm(a, axis=1)
        med = float(np.median(am)) + 1e-3
        for i, x in enumerate(am):
            if x > max(6.0 * med, 0.35 * step * step): jerks.append(('cam_acc', cam_path[i + 1][0], round(float(x), 3), round(med, 3)))
        Q = [Vector(q) for _, _, q in cam_path]
        ang = [math.degrees(2 * math.acos(min(1.0, abs(Q[i].dot(Q[i + 1]))))) for i in range(len(Q) - 1)]
        if len(ang) > 3:
            da = np.abs(np.diff(ang)); medr = float(np.median(da)) + 0.05
            for i, x in enumerate(da):
                if x > max(6.0 * medr, 1.2 * step): jerks.append(('cam_rot', cam_path[i + 1][0], round(float(x), 2), round(medr, 2)))
    def snap_of(fr_, nm):
        for k, e in enumerate(snaps):
            ef = e.get('f'); lo, hi = (int(ef[0]), int(ef[1])) if isinstance(ef, (list, tuple)) else (int(ef), int(ef))
            if lo <= fr_ <= hi and fnmatch.fnmatchcase(nm, e.get('obj', '*')): return k
        return None
    designed = []; snap_hit = set(); twos = {}
    for nm, pts in mover_paths.items():
        runs = []; cur = []
        for fr_, p in pts:
            if cur and fr_ - cur[-1][0] != step: runs.append(cur); cur = []
            cur.append((fr_, p))
        if cur: runs.append(cur)
        for rn in runs:
            if len(rn) < 5: continue
            P = np.array([p for _, p in rn]); v = np.linalg.norm(np.diff(P, axis=0), axis=1)
            med = float(np.median(v)) + 0.02
            act = v[v > EPS_HOLD]; med2 = (float(np.median(act)) if len(act) else 0.0) + 0.02
            for i in range(1, len(v) - 1):
                fr_ = rn[i + 1][0]
                hit = v[i] > 4.0 * max(v[i - 1], v[i + 1], med) and v[i] > 0.6 * step
                if hit and step == 1 and v[i - 1] <= EPS_HOLD and v[i + 1] <= EPS_HOLD:
                    nb2 = [float(v[j]) for j in (i - 2, i + 2) if 0 <= j < len(v)]
                    if any(x > EPS_HOLD for x in nb2):                       # on twos: one 2-frame drawing among its own kind
                        # 2.5 x the larger neighbouring drawing tolerates the same extra jump as 4 x on ones (3 frame-steps)
                        twos[nm] = twos.get(nm, 0) + 1
                        hit = v[i] > 2.5 * max(nb2 + [med2]) and v[i] > 1.2
                elif (not hit and step == 1 and 2 <= i <= len(v) - 3 and v[i - 2] <= EPS_HOLD and v[i + 2] <= EPS_HOLD
                      and min(v[i - 1], v[i + 1]) > EPS_HOLD):
                    # the hold slot of a cadence on twos: the drawing must hold; jumping further than the drawings round it breaks it
                    hit = v[i] > 0.6 and v[i] > 1.25 * max(v[i - 1], v[i + 1])
                if not hit: continue
                k = snap_of(fr_, nm)
                if k is not None:
                    cap = snaps[k].get('max')
                    if cap is None or v[i] <= cap:
                        snap_hit.add(k); designed.append(('snap', fr_, nm, round(float(v[i]), 2), snaps[k].get('why', ''))); continue
                    jerks.append(('teleport', fr_, nm, round(float(v[i]), 2), 'over the designed cap %.2f' % cap)); continue
                jerks.append(('teleport', fr_, nm, round(float(v[i]), 2)))
    unused = [e for k, e in enumerate(snaps) if k not in snap_hit]
    rep = dict(shot=sid, frames=[f0, f1], step=step, overlaps=[dict(a=k[0], b=k[1], n=len(v), frames=[v[0], v[-1]]) for k, v in sorted(bad.items())],
               camera=cam_bad[:200], n_camera=len(cam_bad), smooth=jerks[:200], n_smooth=len(jerks), designed=designed[:200],
               n_designed=len(designed), on_twos=twos, unused_snaps=unused, secs=round(time.time() - t_start, 1),
               post_allowed=[dict(a=k[0], b=k[1], n=len(v), frames=[v[0], v[-1]]) for k, v in sorted(post_ok.items())])
    ok = not bad and not cam_bad and not jerks
    rep['pass'] = ok
    json.dump(rep, open(os.path.join(OUT, '%s.json' % sid), 'w'), indent=1)
    print('QA %s %s overlaps %d camera %d smooth %d designed %d (%.0fs)' % (sid, 'PASS' if ok else 'FAIL', len(bad), len(cam_bad), len(jerks), len(designed), rep['secs']))
    for k, v in sorted(bad.items())[:30]: print('   overlap', k[0], k[1], 'frames', v[0], '..', v[-1], 'n', len(v))
    for c in cam_bad[:20]: print('   camera', c)
    for j in jerks[:20]: print('   smooth', j)
    if twos: print('   judged on twos:', ', '.join('%s %d' % kv for kv in sorted(twos.items())))
    for d in designed[:30]: print('   designed', d)
    for e in unused: print('   unused snap entry', e)
    return rep
