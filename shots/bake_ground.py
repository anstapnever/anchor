# ANCHOR — the ground the mech walks on, as a height field ray-cast from the REAL set (PORT + the UNDER seabed), so every planted
# foot sits exactly on what is rendered (no sole sinking into a breakwater, a caisson or a tetrapod).
#   blender -b -P shots/bake_ground.py            -> out/track/ground.npz  (x0, y0, res, H[ny, nx] top surface z, K hit kind)
# Where no ray hits (outside the UNDER seabed mesh: x < -600 or y < -360) the seabed is UNDER.seabed_z (the mesh's own function).
import sys, os, time, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'): sys.path.insert(0, os.path.join(ROOT, p))
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

t0 = time.time()
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
import port as PT, under as UW

X0, X1, Y0, Y1, RES = -790.0, -390.0, -440.0, 620.0, 1.0
P = PT.build(None, tetrapods=True, cut_sea=False)
U = UW.build(None, kelp=False, grass=False, fish=False, snow=False, rays=False, surface=False, backdrop=False)
print('built %.1fs' % (time.time() - t0))


def top_parent(o):
    while o.parent is not None: o = o.parent
    return o


SKIP_TOP = ('PORT_boat',)
dg = bpy.context.evaluated_depsgraph_get()
V = []; F = []; own = []; kinds = []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    tp = top_parent(o).name
    if tp.startswith(SKIP_TOP) or o.name.startswith(SKIP_TOP): continue
    if o.hide_render: continue
    nm = o.name
    if nm.startswith('UNDER_') and any(k in nm for k in ('ray', 'snow', 'surface', 'backdrop', 'fish', 'kelp', 'grass')): continue
    if nm.startswith('PORT_sea') or nm in ('SEA',) or 'beam' in nm.lower(): continue
    ev = o.evaluated_get(dg); me = ev.to_mesh(); Mw = o.matrix_world.copy()
    bb = [Mw @ Vector(c) for c in o.bound_box]
    if max(v.x for v in bb) < X0 - 30 or min(v.x for v in bb) > X1 + 30 or max(v.y for v in bb) < Y0 - 30 or min(v.y for v in bb) > Y1 + 30:
        ev.to_mesh_clear(); continue
    b = len(V)
    V.extend(Mw @ v.co for v in me.vertices)
    k = len(kinds); kinds.append(nm)
    for p in me.polygons: F.append([b + i for i in p.vertices]); own.append(k)
    ev.to_mesh_clear()
print('faces', len(F), 'objects', len(kinds))
T = BVHTree.FromPolygons(V, F, all_triangles=False, epsilon=0.0)
nx = int(round((X1 - X0) / RES)) + 1; ny = int(round((Y1 - Y0) / RES)) + 1
H = np.zeros((ny, nx), np.float32); K = np.full((ny, nx), -1, np.int32)
down = Vector((0.0, 0.0, -1.0))
for j in range(ny):
    y = Y0 + j * RES
    for i in range(nx):
        x = X0 + i * RES
        loc, nrm, idx, d = T.ray_cast(Vector((x, y, 400.0)), down, 600.0)
        if loc is None:
            H[j, i] = UW.seabed_z(x, y); K[j, i] = -1
        else:      # a real surface (the dock floor at -14 lies below the analytic seabed's -11.5: the hit always wins)
            H[j, i] = loc.z; K[j, i] = own[idx]
out = os.path.join(ROOT, 'out', 'track', 'ground.npz')
np.savez_compressed(out, x0=X0, y0=Y0, res=RES, H=H, K=K, names=np.array(kinds))
print('ground', H.shape, 'z range %.1f .. %.1f' % (float(H.min()), float(H.max())), 'secs %.1f' % (time.time() - t0))
