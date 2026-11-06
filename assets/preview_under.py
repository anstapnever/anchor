# UNDER preview: the underwater set in the shared environment + a stand-in chain (preview only; the real chain is the lead's
# assets/chain.py), QA (real-geometry overlaps), triangle count, build time, then the underwater views through PV.shoot.
#   blender -b -P assets/preview_under.py -- 50 16 [build]
#   (a third argument 'build' stops after the build + QA, no render)
import bpy, bmesh, sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, 'kit'), HERE):
    if p not in sys.path: sys.path.insert(0, p)
from mathutils import Vector, Matrix
import preview as PV, look as LK, env as EV, stage as ST, qa as QA
import under as UW

ARGS = PV.args()
BUILD_ONLY = len(ARGS) > 2 and ARGS[2] == 'build'


def chain_standin(coll, n=10):
    """Stud-link chain hanging straight up from the shackle bow: 8.4 m links of 1.4 m bar (preview stand-in)."""
    mat = UW.ucel('M_UNDER_prevchain', lambda nb: UW._iron(nb, 1.3, 0.9), ink=1.0, spec=0.4, rim=0.4, deep=0.6, vary=0.05)
    d = 1.4; W = 3.6 * d; r = W / 2 - d / 2; hs = (8.4 - W) / 2
    X = UW.S_MAT.col[0].xyz.normalized(); Y = UW.S_MAT.col[1].xyz.normalized(); out = []
    for k in range(n):
        c = Vector((UW.BOW.x, UW.BOW.y, UW.BOW.z + UW.BOW_IN - 0.04 - d / 2 + hs + r + 5.56 * k)); w = Y if k % 2 == 0 else X; nrm = w.cross(UW.UP)   # 4 cm play per contact
        cl = []
        for i in range(12): cl.append((r, -hs + 2 * hs * i / 12))
        for i in range(16): a = math.pi * i / 16; cl.append((r * math.cos(a), hs + r * math.sin(a)))
        for i in range(12): cl.append((-r, hs - 2 * hs * i / 12))
        for i in range(16): a = math.pi + math.pi * i / 16; cl.append((r * math.cos(a), -hs + r * math.sin(a)))
        pts = [c + w * u + UW.UP * v for u, v in cl]; rings = []
        for i, p in enumerate(pts):
            t = (pts[(i + 1) % len(pts)] - pts[i - 1]).normalized(); b = t.cross(nrm)
            rings.append(UW.circle(p, nrm, b, d / 2, 12))
        bm = bmesh.new(); UW.bridge(bm, rings, True, True)
        UW.tube(bm, [c - w * (r - 0.6), c + w * (r - 0.6)], 0.38, seg=10)
        UW.clean(bm)
        o = UW.mkobj('UNDER_prev_chain_%d' % k, bm, mat, coll, 'chain', smooth=True)
        out.append(o)
    return out


sc, W = PV.setup('morning', sun=(95.0, 16.0), sea=True)
sun = bpy.data.objects['SUN']
try: sc.eevee.shadow_pool_size = '1024'          # the kelp forests overflow the default 512 MB shadow pool
except Exception as ex: print('shadow pool', ex)
UW.set_water(sc, sun_obj=sun)
t0 = time.time()
U = UW.build()
t_build = time.time() - t0
print('UNDER build %.1f s (inside build %.1f s)' % (t_build, U['time']))
chain = chain_standin(U['root'])

# ---------------------------------------------------------------- animation for the views (one view = one frame)
NV = 9
for f in range(1, NV + 1):
    sc['seaT'] = 3.0 + 1.7 * f; sc.keyframe_insert('["seaT"]', frame=f)
    U['shackle']['heat'] = 1.0 if f == 5 else 0.0; U['shackle'].keyframe_insert('["heat"]', frame=f)
ST.set_interp(U['shackle'], 'CONSTANT')
F = U['fish']
UW.animate_school(F['chain'], 1, NV, mode='flee', flee_from=tuple(UW.BOW), flee_frame=5, lead=0.7, step=1)
for k in ('kelp', 'reef', 'grouper'): UW.animate_school(F[k], 1, NV, step=1)
sc.frame_set(1)

# ---------------------------------------------------------------- QA
objs = [o for o in U['root'].all_objects if o.type == 'MESH']
tris = UW.count_tris(objs)
print('UNDER objects %d, triangles %d (stand-in chain included: %d)' % (len(objs), tris, UW.count_tris(chain)))
kinds = {}
for o in objs: kinds[o.get('uw_kind', '?')] = kinds.get(o.get('uw_kind', '?'), 0) + 1
print('UNDER kinds', sorted(kinds.items()))
t1 = time.time()
bad = QA.overlaps(objs, allow=UW.qa_allow)
print('QA overlaps (%.1f s): %d pairs' % (time.time() - t1, len(bad)))
for b in sorted(bad, key=lambda x: -x[2])[:60]: print('  OVERLAP', b)
hero = [U[k] for k in ('anchor', 'shackle', 'pin_a', 'pin_b')] + chain
print('QA hero (no allowances):', QA.overlaps(hero))
print('QA coplanar hero:', QA.coplanar(hero + [U['boat'], U['boat_parts']]))
def bed_gap(o):
    ws = [o.matrix_world @ v.co for v in o.data.vertices]
    g = [w.z - UW.seabed_z(w.x, w.y) for w in ws]
    return min(g), sum(1 for x in g if x < 0) / len(g)
for k in ('anchor', 'shackle', 'pin_a', 'pin_b', 'boat'):
    mn, fr = bed_gap(U[k]); print('BED %-8s lowest point %.2f m above the bed, %.0f%% of verts below it' % (k, mn, fr * 100))
sc.frame_set(5)
print('QA heat frame, fish vs world:', [b for b in QA.overlaps(F['chain'], objs, allow=UW.qa_allow) if b[2] > 0][:20])
sc.frame_set(1)

if not BUILD_ONLY:
    V = Vector; UPv = UW.UP; L = UW.LAT; HD = UW.H; PIN = UW.PIN; HEAD = UW.HEAD
    mid = (HEAD + PIN) * 0.5
    bed = lambda x, y: UW.seabed_z(x, y)
    lift = lambda p, h: V((p.x, p.y, max(p.z, UW.seabed_z(p.x, p.y) + h)))
    bz = bed(-57.0, 192.0); kz = bed(-62.0, 266.0); kz2 = bed(-58.0, 304.0); uz = bed(-146.0, 286.0)
    views = [
        (tuple(mid + L * 38.0 - HD * 4.0 + UPv * 3.0), tuple(mid + UPv * 7.0 - HD * 2.0), 20.0),        # 06 the anchor wide, chain rising
        (tuple(PIN - L * 12.0 + HD * 11.0 + UPv * 1.2), tuple(PIN - L * 0.5 + UPv * 3.4), 30.0),       # 15 shackle + pin macro
        ((-62.0, 266.0, kz + 3.0), (-58.0, 304.0, kz2 + 9.0), 22.0),                                   # kelp forest + snappers
        ((-146.0, 286.0, uz + 2.0), (-140.0, 292.0, 0.0), 18.0),                                       # looking up from the kelp floor
        (tuple(PIN + HD * 14.0 - L * 5.0 + UPv * 5.0), tuple(UW.BOW - UPv * 1.5), 30.0),               # 14 heat = 1, fish flee
        (tuple(lift(mid - L * 48.0 + HD * 10.0 + UPv * 16.0, 5.0)), tuple(mid + UPv * 2.0), 24.0),     # the trench, anchor side-on
        ((-45.0, 177.0, bz + 2.6), (-57.0, 192.0, bz + 1.2), 26.0),                                    # the sunken boat
        (tuple(HEAD + V((12.0, -20.0, 6.0))), tuple(HEAD + UW.FDIR * 5.0 + UPv * 1.0), 24.0),         # crown, flukes in the furrow, coral
        ((-20.0, 200.0, -30.0), (-300.0, 200.0, -36.0), 24.0),                                         # far fog / horizon check
    ]
    for v in views: print('VIEW', [round(x, 1) for x in v[0]], [round(x, 1) for x in v[1]], v[2], 'bed under cam %.1f' % bed(v[0][0], v[0][1]))
    PV.shoot(sc, 'under', views, params={'haze_max': 0.0, 'under': 0.0, 'vignette': 0.2})
    print('UNDER preview done')
