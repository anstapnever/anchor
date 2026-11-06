# CITY preview: builds High Harbor into the shared environment and renders the views the city plays in.
#   blender -b -P assets/preview_city.py -- 50 16            all views -> out/preview/city/
#   blender -b -P assets/preview_city.py -- 50 16 qa         build + QA + triangle count only (no render)
#   blender -b -P assets/preview_city.py -- 50 16 v=2,7      only those views -> out/preview/city_sub/
#   ... nochain                                                     without the lead's chain hanging from the lug
import bpy, sys, os, math, time, random
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'kit')); sys.path.insert(0, HERE)
import look as LK, env as EV, preview as PV, stage as ST, qa as QA
from mathutils import Vector
import numpy as np
import city

A = PV.args(); FLAGS = A[2:]
MODE = 'qa' if 'qa' in FLAGS else 'render'
sc, W = PV.setup(preset='morning', sun=(95, 16))

# ---- scattered cumulus below and around the island (the island floats above them in shot 01)
cm = bpy.data.materials.get('M_cloud') or EV.cloud_mat()
O = Vector(city.ORIGIN)
for i, (dx, dy, z, w, h) in enumerate([(430, -390, 165, 230, 115), (660, 120, 140, 270, 150), (-540, -270, 185, 250, 125),
                                        (-300, -680, 150, 310, 165), (210, -820, 115, 270, 140), (-780, 260, 160, 230, 120),
                                        (90, 720, 210, 210, 105), (330, 380, 230, 120, 55), (-260, -470, 240, 110, 50),
                                        (520, -120, 260, 95, 45)]):
    EV.cumulus('CITY_CU%d' % i, (O.x + dx, O.y + dy, z), w, h, seed=70 + i, mat=cm, c=W)

# ---- the city
t0 = time.time()
C = city.build(None)
print('BUILD_S %.1f' % (time.time() - t0))
print('TRIS %d' % C['tris'])
print('COUNTS houses %d trees %d ledge_trees %d cloth %d tiles %d falls %d crystals %d vanes %d sails %d gardens %d rivets %d' % (
    len(C['houses']), len(C['trees']), len(C['ledge_trees']), len(C['cloth']), len(C['tiles']), len(C['falls']), len(C['crystals']),
    len(C['vanes']), len(C['sails']), len(C['gardens']), len(C['rivets'])))
info = C['info']
for k in ('rim_z', 'plaza', 'campanile', 'campanile_top', 'bell_pivot', 'church', 'watertower', 'rock_bottom', 'neck_r'):
    print('INFO', k, info[k])
print('INFO mill yards with washing', sum(1 for m in info['mills'] if m.get('yard')), 'of', len(info['mills']))
bpy.context.view_layer.update()
W_ = lambda p: O + Vector(p)                      # root-local -> world (the root is not rotated at rest)

# ---- the lead's chain (read-only use of assets/chain.py): hangs straight down from the lug pin to the seabed
links = []
if 'nochain' not in FLAGS:
    import chain as CH
    cc = bpy.data.collections.new('CHAIN'); sc.collection.children.link(cc)
    links = CH.build(cc, n=72, n_sea=12)
    pin = C['chain_top'].matrix_world.translation.copy()
    J = [pin + Vector((0.0, 0.0, 0.775 - CH.PITCH * k)) for k in range(len(links) + 1)]
    CH.pose(links, [tuple(j) for j in J], frame=None, roll0=math.radians(180.0 - city.LUG_YAW), key=False)
    print('CHAIN top link at', tuple(round(v, 2) for v in links[0].location), 'pin', tuple(round(v, 2) for v in pin))

# ---- QA
bpy.context.view_layer.update()
t = time.time()
bad = QA.overlaps(C['objs'], allow=C['qa_allow'])
print('QA_OVERLAPS %d (%.1f s)' % (len(bad), time.time() - t))
for b in bad[:40]: print('   ', b)
if links:
    under = [C['lug'], C['collar']] + C['rivets'] + C['crystals']
    cb = QA.overlaps(links[:4], under)
    print('QA_CHAIN_vs_COLLAR', cb)
for nm, objs in (('plaza/streets/canals', ['CITY_plaza', 'CITY_streets', 'CITY_canals', 'CITY_water', 'CITY_bridges']),
                 ('collar', ['CITY_collar', 'CITY_lug'] + [o.name for o in C['rivets']]),
                 ('campanile', ['CITY_campanile', 'CITY_bell', 'CITY_clapper', 'CITY_church']),
                 ('watertower/mills', ['CITY_watertower'] + [o.name for o in C['mills']])):
    ob = [bpy.data.objects[n] for n in objs if n in bpy.data.objects]
    print('QA_COPLANAR', nm, QA.coplanar(ob))
# moving parts: the bell through its swing and the sails through a quarter turn must not hit anything new
def pairs(a, b):
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get(); T = []
    for o in (a, b):
        ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
        T.append(BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])); ev.to_mesh_clear()
    return len(T[0].overlap(T[1]))
bell = C['bell']; camp = C['campanile']; r0 = bell.rotation_euler.copy()
res = []
for ang in (0, 20, 40, 60, 75, -40, -75):
    bell.rotation_euler = (r0.x, r0.y + math.radians(ang), r0.z); bpy.context.view_layer.update()
    res.append((ang, pairs(bell, camp), pairs(C['clapper'], camp)))
bell.rotation_euler = r0; bpy.context.view_layer.update()
print('QA_BELL_SWING (deg, bell x tower pairs, clapper x tower pairs)', res)
res = []
for i, sv in enumerate(C['sails']):
    r1 = sv.rotation_euler.copy(); mx = 0
    for k in range(6):
        sv.rotation_euler = (r1.x, r1.y + math.radians(15 * k), r1.z); bpy.context.view_layer.update()
        mx = max(mx, pairs(sv, C['mills'][i]))
    sv.rotation_euler = r1; res.append(mx)
bpy.context.view_layer.update()
print('QA_SAILS_vs_MILL max pairs over a quarter turn (axle contact only)', res)
if MODE == 'qa':
    sys.exit(0)

# ---- views (world coordinates)
dg = bpy.context.evaluated_depsgraph_get()
def hit(p, q):
    d = q - p; L = d.length
    ok, loc, nrm, idx, ob, mx = sc.ray_cast(dg, p, d.normalized(), distance=L)
    return (ob, (loc - p).length) if ok else (None, L)

views = []
# 01 establishing: 600 m out to the south-east, ~100 m above the rim, the island above scattered cumulus, falls and chain below
c0 = W_((0.0, 0.0, 215.0))
views.append(('01 establishing', tuple(c0 + Vector((300.0, -520.0, 100.0))), tuple(c0 + Vector((0.0, 0.0, -80.0))), 30.0))

# 02 street close-up at 2 m: a windmill's sails sweeping across the near frame, laundry over the street, the bell tower behind
ctx = C['ctx']; camp_b = W_((info['campanile'][0], info['campanile'][1], info['bell_pivot']))
lines_w = [(W_(a), W_(b)) for a, b in info['lines']]
UP = Vector((0, 0, 1))
def basis(aim):
    rt = aim.cross(UP).normalized(); up = rt.cross(aim).normalized(); return rt, up
def openness(P, aim, lens, n=(7, 4), near=6.0):
    rt, up = basis(aim); tx = 18.0 / lens; ty = tx * 9 / 16; k = 0; tot = 0
    for i in range(n[0]):
        for j in range(n[1]):
            u = (i / (n[0] - 1) * 2 - 1) * 0.9; v = (j / (n[1] - 1) * 2 - 1) * 0.9
            dr = (aim + rt * (u * tx) + up * (v * ty)).normalized()
            ok, loc, nrm, idx, ob, mx = sc.ray_cast(dg, P, dr, distance=near)
            k += ok; tot += 1
    return k / tot
def in_frame(P, aim, lens, Q, margin=0.85):
    rt, up = basis(aim); d = Q - P; z = d.dot(aim)
    if z <= 0: return False
    tx = 18.0 / lens; ty = tx * 9 / 16
    return abs(d.dot(rt) / z) < tx * margin and abs(d.dot(up) / z) < ty * margin
best = None; LENS2 = 20.0
camp_t = W_((info['campanile'][0], info['campanile'][1], info['campanile_top']))
def cands02():
    for st in ctx.streets:
        for s_ in np.arange(0.0, st.L, 1.5):
            p2 = st.at(float(s_))[0]; z = float(st.z_at(float(s_)))
            yield W_((float(p2[0]), float(p2[1]), z + 2.0)), 0.0
    for m in info['mills']:                                   # open ground round the mills, 2 m above it, nothing overhead
        for r_ in np.arange(9.0, 31.0, 2.0):
            for a_ in np.arange(0.0, 360.0, 8.0):
                x = m['c'][0] + r_ * math.cos(math.radians(a_)); y = m['c'][1] + r_ * math.sin(math.radians(a_))
                if math.hypot(x, y) > float(city.r_outline(math.atan2(y, x))) - 2.0: continue
                P = W_((x, y, city.gz(ctx, x, y) + 2.0))
                if hit(P + Vector((0, 0, 40.0)), P)[0] is not None: continue
                if any(hit(P, P + Vector(dv_) * 0.8)[0] is not None for dv_ in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, -1))): continue
                yield P, 2.0                                          # off-street: slight penalty
C02 = list(cands02())
print('VIEW02 candidates', len(C02))
def search02(LB0, LB1, a0, a1, opmax):
    best = None
    for P, pen in C02:
        if True:
            dB = camp_b - P; LB = dB.length
            if not LB0 < LB < LB1: continue
            hB = Vector((dB.x, dB.y, 0.0)).normalized()
            for mi, m in enumerate(info['mills']):
                H = W_(m['hub']); dH = H - P; LH = dH.length
                if not 13.0 < LH < 26.0: continue
                hH = Vector((dH.x, dH.y, 0.0)).normalized(); ang = hH.angle(hB)
                if not math.radians(a0) < ang < math.radians(a1): continue
                yaw = (hB * 0.72 + hH * 0.28).normalized()
                el = 0.55 * math.atan2((camp_b.z + camp_t.z) / 2 - P.z, LB) + 0.45 * math.atan2(H.z - P.z, Vector((dH.x, dH.y, 0.0)).length)
                el = min(max(el, math.radians(4.0)), math.radians(17.0))
                aim = (yaw * math.cos(el) + UP * math.sin(el)).normalized()
                if not (in_frame(P, aim, LENS2, camp_t, 0.9) and in_frame(P, aim, LENS2, camp_b, 0.85) and in_frame(P, aim, LENS2, H, 0.9)): continue
                ob, dd_ = hit(P, H)
                if ob is not None and not ob.name.startswith(('CITY_sails', 'CITY_mill', 'CITY_hub')): continue
                vis = 0
                for dz in (-2.0, 1.0, 4.0):
                    ob2, dd2 = hit(P, camp_b + Vector((0, 0, dz)))
                    vis += ob2 is None or ob2.name.startswith(('CITY_campanile', 'CITY_bell', 'CITY_sails', 'CITY_cloth', 'CITY_lines', 'CITY_clapper'))
                if vis < 2: continue
                op = openness(P, aim, LENS2)
                if op > opmax: continue
                nl = 0                                                    # washing lines in frame and actually visible (2 of 3 points)
                for a_, b_ in lines_w:
                    mm = (a_ + b_) / 2
                    if not (4.0 < (mm - P).length < 32.0 and in_frame(P, aim, LENS2, mm, 0.9)): continue
                    vis_ = 0
                    for t_ in (0.25, 0.5, 0.75):
                        m_ = a_.lerp(b_, t_) - Vector((0, 0, 0.45)); ob3, d3 = hit(P, m_)
                        vis_ += ob3 is None or ob3.name.startswith(('CITY_cloth', 'CITY_lines')) or d3 > (m_ - P).length - 0.6
                    nl += vis_ >= 2
                sc_ = pen + abs(LH - 18.0) * 0.5 + abs(math.degrees(ang) - 22.0) * 0.12 + op * 15.0 - min(nl, 2) * 6.0
                if best is None or sc_ < best[0]: best = (sc_, P.copy(), aim, mi, LH, math.degrees(ang), op, nl, LB)
    return best
best = search02(70.0, 260.0, 12.0, 36.0, 0.15) or search02(45.0, 300.0, 8.0, 44.0, 0.3)
if best:
    _, P, aim, mi, dist, ang, op, nl, LB = best
    print('VIEW02 mill %d hub %.1f m ang %.1f open %.2f lines %d bell %.0f m pitch %.1f' % (mi, dist, ang, op, nl, LB, math.degrees(math.asin(aim.z))))
    views.append(('02 street, sails, bell tower', tuple(P), tuple(P + aim * 50.0), LENS2))
else:
    print('VIEW02 no clean street position found')

# 07 from the rim: along the railing, a rooftop weather vane on one side, the western sea and horizon on the other
vane_h = [v for v in C['vanes'] if v.parent is not None and v.parent.name.startswith('CITY_house')] or C['vanes']
best = None
for v in vane_h:
    Vw = v.matrix_world.translation.copy(); sv_ = v.matrix_world.to_scale()[2]
    tops = [Vw + Vector((0.0, 0.0, h_ * sv_)) for h_ in (0.8, 1.25, 1.6)]     # cross arms, arrow and rooster, the finial
    Vt = tops[1]; thv = math.atan2(Vw.y - O.y, Vw.x - O.x)
    for dth in (-0.3, -0.24, -0.2, -0.16, -0.12, -0.08, 0.08, 0.12, 0.16, 0.2, 0.24, 0.3):
        thc = thv + dth; rr = float(city.r_outline(thc)) - 2.3
        q = (rr * math.cos(thc), rr * math.sin(thc)); zg = city.gz(ctx, q[0], q[1])
        P = W_((q[0], q[1], zg + 1.65))
        out_ = Vector((math.cos(thc), math.sin(thc), 0.0))
        dv = (Vt - P); dvh = Vector((dv.x, dv.y, 0.0)).normalized()
        aim = (dvh * math.cos(math.radians(28)) + out_ * math.sin(math.radians(28))).normalized()
        aim = (aim + Vector((0, 0, 0.12))).normalized()
        if not in_frame(P, aim, 20.0, Vt, 0.9): continue
        vis = 0
        for T_ in tops:
            ob, d_ = hit(P, T_)
            vis += ob is None or ob == v or d_ > (T_ - P).length - 0.25
        if vis < 2: continue
        op = openness(P, aim, 20.0, near=3.0)
        if op > 0.15: continue
        west = -aim.x
        sc_ = -west * 3.0 + op * 10.0 + abs(dv.length - 22.0) * 0.08
        if best is None or sc_ < best[0]: best = (sc_, P.copy(), aim, v.name, dv.length, op)
if best:
    _, P, aim, vn, dist, op = best
    print('VIEW07 vane %s dist %.1f open %.2f aim %s' % (vn, dist, op, tuple(round(x, 2) for x in aim)))
    views.append(('07 rim looking west', tuple(P), tuple(P + aim * 60.0), 20.0))
else:
    print('VIEW07 fallback: westmost lookout')
    lk = min(info['lookouts'], key=lambda l: l['d'][0])
    d = Vector((lk['d'][0], lk['d'][1], 0.0)); P = W_((lk['p'][0], lk['p'][1], lk['z'])) + d * 0.5 + Vector((0, 0, 1.65))
    views.append(('07 rim looking west', tuple(P), tuple(P + d * 400.0 + Vector((0, 0, -30.0))), 22.0))

# 19 under the city: the collar, the lug, the chain top and the crown of crystals, looking up into the stone sky
views.append(('19 under the city', tuple(O + Vector((30.0, -38.0, -52.0))), tuple(O + Vector((0.0, 0.0, 24.0))), 24.0))

# 36 from the harbour looking up at the city like a stone sky
views.append(('36 from the sea, looking up', (-330.0, 470.0, 24.0), tuple(O + Vector((0.0, 0.0, 95.0))), 24.0))

# waterfall three-quarter from the sunny side: the spout, the curtain with its veil, the spray and the mist cloud
fl = max(info['falls'], key=lambda f: f['dir'][0])
S = W_(fl['start']); dd = Vector((fl['dir'][0], fl['dir'][1], 0.0)).normalized(); sd = Vector((-dd.y, dd.x, 0.0))
sunv = Vector((math.sin(math.radians(95.0)), math.cos(math.radians(95.0)), 0.0))
if sd.dot(sunv) < 0: sd = -sd
vdir = (sd * 0.8 + dd).normalized()
views.append(('falls three-quarter', tuple(S + vdir * 370.0 + Vector((0, 0, -135.0))), tuple(S + dd * 20.0 + Vector((0, 0, -135.0))), 20.0))

# bell tower mid shot from the sunny side, at belfry height, head-on enough to see the bell through the east arch
bell = C['bell']; bc = sum((bell.matrix_world @ Vector(c) for c in bell.bound_box), Vector()) / 8.0
camv = None
for a_deg in (-10, -6, -14, -2, -18, 4, -24):
    for hz in (5.0, 4.0, 3.0, 2.0, 1.0, -0.6):           # from above the belfry: the town fills the background
        a = math.radians(a_deg); P = Vector((bc.x + math.cos(a) * 38.0, bc.y + math.sin(a) * 38.0, bc.z + hz))
        vis = 0
        for dz in (-0.45, 0.0, 0.45):
            ob, d_ = hit(P, bc + Vector((0, 0, dz)))
            vis += ob is not None and ob.name in ('CITY_bell', 'CITY_clapper')
        if vis >= 2: camv = (P, a_deg, hz); break
    if camv: break
if camv is None: camv = (Vector((bc.x + 38.0, bc.y, bc.z - 0.6)), 0, -0.6)
print('VIEW_CAMP angle %d dz %.1f' % (camv[1], camv[2]))
views.append(('campanile mid shot', tuple(camv[0]), tuple(bc + Vector((0, 0, 0.5))), 35.0))

# the cliff: strata, ledges with trees, roots and a crystal cluster (away from the falls)
def fall_clear(th): return min(abs(math.remainder(th - math.atan2(f['start'][1], f['start'][0]), math.tau)) for f in info['falls']) > 0.5
cands = [c for c in info['crystals'] if 85.0 < c['p'][2] < 150.0 and fall_clear(math.atan2(c['p'][1], c['p'][0]))]
cr = max(cands, key=lambda c: c['size']) if cands else info['crystals'][0]
pc = Vector(cr['p']); rad = Vector((pc.x, pc.y, 0.0)).normalized()
views.append(('cliff with ledges and crystals', tuple(W_(pc) + rad * 85.0 + Vector((0, 0, -12.0))), tuple(W_(pc) + Vector((0, 0, 8.0))), 28.0))

# washing over a street: the street point that sees the most laundry lines ahead (shots 02 and 09)
def line_vis(P, a_, b_):
    k = 0
    for t_ in (0.25, 0.5, 0.75):
        m_ = a_.lerp(b_, t_) - Vector((0, 0, 0.45)); ob3, d3 = hit(P, m_)
        k += ob3 is None or ob3.name.startswith(('CITY_cloth', 'CITY_lines')) or d3 > (m_ - P).length - 0.6
    return k >= 2
bestL = None
for st in ctx.streets:
    for s_ in np.arange(2.0, st.L - 2.0, 3.0):
        p2, T2 = st.at(float(s_))[:2]; z = float(st.z_at(float(s_)))
        P = W_((float(p2[0]), float(p2[1]), z + 1.8))
        for sgn in (1.0, -1.0):
            aim = (Vector((float(T2[0]) * sgn, float(T2[1]) * sgn, 0.0)).normalized() + Vector((0, 0, 0.22))).normalized()
            near_ = [(a_, b_) for a_, b_ in lines_w if 3.0 < ((a_ + b_) / 2 - P).length < 30.0 and in_frame(P, aim, 20.0, (a_ + b_) / 2, 0.9)]
            if len(near_) < (bestL[0] if bestL else 1): continue
            nl = sum(1 for a_, b_ in near_ if line_vis(P, a_, b_))
            if nl and (bestL is None or nl > bestL[0]) and openness(P, aim, 20.0, near=4.0) <= 0.2: bestL = (nl, P.copy(), aim)
if bestL:
    print('VIEW_LAUNDRY lines %d' % bestL[0])
    views.append(('laundry over a street', tuple(bestL[1]), tuple(bestL[1] + bestL[2] * 30.0), 20.0))

sel = None
for a_ in FLAGS:
    if a_.startswith('v='): sel = [int(x) for x in a_[2:].split(',')]
vv = [v for i, v in enumerate(views) if sel is None or i + 1 in sel]
for i, v in enumerate(vv, start=1): print('VIEW f%04d %s pos %s tgt %s lens %.0f' % (i, v[0], tuple(round(x, 1) for x in v[1]), tuple(round(x, 1) for x in v[2]), v[3]))
PV.shoot(sc, 'city' if sel is None else 'city_sub', [v[1:] for v in vv])
print('DONE')
