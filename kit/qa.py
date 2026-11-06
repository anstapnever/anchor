# ANCHOR QA: real-geometry intersection tests inside Blender (evaluated meshes: modifiers, animation, instancing applied).
#   import qa; bad = qa.overlaps(objs)                      -> list of (nameA, nameB, n_triangle_pairs)
#   qa.coplanar(objs)                                       -> z-fight candidates: faces of different objects lying in the same plane, overlapping
#   qa.inside_count(a, b)                                   -> how many vertices of a are inside closed mesh b (penetration depth proxy)
# Allowed contacts are given as a predicate allow(a, b) -> True (e.g. a house standing in the terrain, a foot in the sea).
import bpy, bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _tree(o, dg):
    ev = o.evaluated_get(dg)
    try: me = ev.to_mesh()
    except Exception: return None, None
    if me is None or len(me.polygons) == 0:
        try: ev.to_mesh_clear()
        except Exception: pass
        return None, None
    M = o.matrix_world
    verts = [M @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    t = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    return t, (lo, hi, verts)


def _aabb_hit(a, b, pad=0.0):
    return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))


def overlaps(objs, others=None, allow=None, dg=None, pad=0.0, verbose=False):
    dg = dg or bpy.context.evaluated_depsgraph_get()
    objs = [o for o in objs if o.type in ('MESH', 'CURVE', 'FONT') and o.visible_get()]
    others = objs if others is None else [o for o in others if o.type in ('MESH', 'CURVE', 'FONT') and o.visible_get()]
    cache = {}
    def get(o):
        if o.name not in cache: cache[o.name] = _tree(o, dg)
        return cache[o.name]
    bad = []; seen = set()
    for a in objs:
        ta, ba = get(a)
        if ta is None: continue
        for b in others:
            if a is b: continue
            key = tuple(sorted((a.name, b.name)))
            if key in seen: continue
            seen.add(key)
            if allow and allow(a, b): continue
            tb, bb = get(b)
            if tb is None or not _aabb_hit(ba, bb, pad): continue
            pairs = ta.overlap(tb)
            if pairs:
                bad.append((a.name, b.name, len(pairs)))
                if verbose: print('OVERLAP', a.name, b.name, len(pairs))
    return bad


def inside_count(a, b, dg=None, step=1):
    """Vertices of a that lie inside the closed mesh b (ray parity along +Z and +X must agree)."""
    dg = dg or bpy.context.evaluated_depsgraph_get()
    tb, bb = _tree(b, dg); ta, ba = _tree(a, dg)
    if tb is None or ta is None: return 0
    n = 0
    for v in ba[2][::step]:
        if not (bb[0].x <= v.x <= bb[1].x and bb[0].y <= v.y <= bb[1].y and bb[0].z <= v.z <= bb[1].z): continue
        ins = True
        for d in (Vector((0, 0, 1)), Vector((1, 0, 0))):
            hits = 0; o = v.copy()
            for _ in range(64):
                loc, nrm, idx, dist = tb.ray_cast(o + d * 1e-4, d)
                if loc is None: break
                hits += 1; o = loc
            if hits % 2 == 0: ins = False; break
        n += ins
    return n


def coplanar(objs, dg=None, tol_d=0.02, tol_n=0.9995, min_area=0.01):
    """Faces of two different objects that share a plane and overlap in it: z-fighting candidates."""
    dg = dg or bpy.context.evaluated_depsgraph_get()
    faces = []
    for o in objs:
        if o.type != 'MESH' or not o.visible_get(): continue
        ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world; R = M.to_3x3().inverted().transposed()
        for p in me.polygons:
            if p.area * (M.to_scale().x * M.to_scale().y) < min_area: continue
            c = M @ p.center; n = (R @ p.normal).normalized()
            vs = [M @ me.vertices[i].co for i in p.vertices]
            faces.append((o.name, c, n, vs))
        ev.to_mesh_clear()
    # bucket by plane
    from collections import defaultdict
    buck = defaultdict(list)
    for f in faces:
        n = f[2]; d = n.dot(f[1])
        key = (round(n.x, 2), round(n.y, 2), round(n.z, 2), round(d / max(tol_d, 1e-6)))
        buck[key].append(f)
    hits = set()
    for key, fs in buck.items():
        names = set(f[0] for f in fs)
        if len(names) < 2: continue
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                a, b = fs[i], fs[j]
                if a[0] == b[0] or abs(a[2].dot(b[2])) < tol_n: continue
                if abs(a[2].dot(b[1] - a[1])) > tol_d: continue
                # overlap of bounding boxes in-plane
                lo_a = [min(v[k] for v in a[3]) for k in range(3)]; hi_a = [max(v[k] for v in a[3]) for k in range(3)]
                lo_b = [min(v[k] for v in b[3]) for k in range(3)]; hi_b = [max(v[k] for v in b[3]) for k in range(3)]
                if all(lo_a[k] - tol_d <= hi_b[k] and lo_b[k] - tol_d <= hi_a[k] for k in range(3)):
                    hits.add(tuple(sorted((a[0], b[0]))))
    return sorted(hits)
