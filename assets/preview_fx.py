# FX preview: blender -b -P assets/preview_fx.py -- [res%] [spp] [groups: sky,water,heat,under]
#   sky   -> out/preview/fx_sky    storm wall from the port and from the city, a bolt over the sea (strike + fade), the waterspout
#   water -> out/preview/fx_water  crown splash round an 8 m pillar (4 moments + low angle), splash wall (3 moments), foam/trail/debris
#   heat  -> out/preview/fx_heat   steam puffs, sparks
#   under -> out/preview/fx_under  silt burst, bubbles
# One rendered frame per view. Animated FX are shown at chosen moments by building one instance per moment and showing it
# only on its own preview frame (only_on).
import sys, os, math, time, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, 'kit'), HERE):
    if p not in sys.path: sys.path.insert(0, p)
import bpy, bmesh
import look as LK, env as EV, preview as PV, qa as QA
import fx as FX

A = PV.args()
GROUPS = A[2].split(',') if len(A) > 2 else ['sky', 'water', 'heat', 'under']
REPORT = {}
PARAMS = dict(haze_dist=7000.0, haze_max=0.35, haze=(0.75, 0.86, 1.0))


def only_on(objs, frame, n):
    """visible on preview frame `frame` only (overrides the FX's own hide keys on frames 0..n+1)."""
    objs = objs if isinstance(objs, (list, tuple)) else [objs]
    for o in objs:
        for f in range(0, n + 2):
            for a in ('hide_render', 'hide_viewport'):
                setattr(o, a, f != frame); o.keyframe_insert(a, frame=f)


def keyprop(idb, name, vals, n):
    """vals {frame: value}, everything else 0; CONSTANT."""
    for f in range(0, n + 2):
        v = vals.get(f, 0.0)
        idb[name] = v; idb.keyframe_insert('["%s"]' % name, frame=f)
    FX._interp(idb, 'CONSTANT', ('["%s"]' % name,))


def flatten(x):
    out = []
    for v in (x if isinstance(x, (list, tuple)) else [x]):
        if isinstance(v, dict): out += flatten(list(v.values()))
        elif isinstance(v, (list, tuple)): out += flatten(v)
        elif isinstance(v, bpy.types.Object): out.append(v)
    return out


def qa_frame(sc, tag, frame, objs, others=None, allow=None):
    sc.frame_set(frame)
    objs = [o for o in flatten(objs) if o.type == 'MESH']
    t0 = time.time(); bad = QA.overlaps(objs, others, allow)
    REPORT.setdefault('qa', []).append((tag, frame, bad, round(time.time() - t0, 1)))
    print('QA', tag, frame, bad)


def pillar(c, r=4.0, top=40.0, bottom=-12.0):
    m = LK.cel('M_pv_steel', '#4b5163', ink=1.0, spec=0.5, rust=0.5, scuff=0.4, wscale=0.5)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=r, radius2=r, depth=top - bottom)
    o = EV.bm_obj('PV_pillar', bm, m, c, smooth=True); o.location = (0, 0, (top + bottom) / 2)
    return o


def remove_west_ring(az0=196.0, az1=344.0):
    n = 0
    for o in list(bpy.data.objects):
        if o.name.startswith('CLOUD_ring'):
            x, y = o.location.x, o.location.y
            if o.data and len(o.data.vertices):
                import numpy as np
                co = np.zeros(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3).mean(0)
                x, y = co[0] + o.location.x, co[1] + o.location.y
            az = math.degrees(math.atan2(x, y)) % 360
            if az0 <= az <= az1: bpy.data.objects.remove(o); n += 1
    return n


# ======================================================================================================================== sky
def group_sky():
    sc, W = PV.setup('storm', sun=(95, 16), storm=0.7)
    print('removed west ring clouds:', remove_west_ring())
    for nm in ('CU0', 'CU1', 'CU2'):      # the preview's near cumulus in the north-west would stand in front of the storm
        if nm in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[nm])
    C = EV.coll('FX_PV', None)
    t0 = time.time(); B = FX.build(C); tb = time.time() - t0
    S, Wsp = B['storm'], B['spout']
    REPORT['build_s'] = round(tb, 2)
    N = 8
    FX.spout_spin(Wsp, 1, N + 1, speed=3.0)
    # the storm's inner flash on frame 2 (view from the city) + one of its bolts
    for o in (S['mass'], S['shelf']):
        keyprop(o, 'fl1', {2: 1.0, 8: 0.6}, N)
    cell = S['cells'][9]
    for o in (S['mass'], S['shelf']):
        o['fp1'] = tuple(cell); o.keyframe_insert('["fp1"]', frame=1)
    FX.flicker(S['bolts'][1], [2], pattern=(1.0,), step=1)
    FX.flicker(S['bolts'][2], [8], pattern=(0.7,), step=1)
    # a bolt over the sea, strike (3) and fade (4)
    b = FX.bolt('FX_pv_bolt', (-1900, 60, 950), (-1820, 170, 0), seed=11, branches=5, width=1.0, coll=C)
    FX.flicker(b, [3], pattern=(1.0, 0.55), step=1)
    keyprop(sc, 'flash', {2: 0.12, 3: 0.3, 4: 0.12, 8: 0.1}, N)
    views = [((0, 300, 20), (-8000, 300, 1124), 24.0),            # 1 storm from the port
             ((-200, 0, 560), (-8000, 0, 1500), 28.0),            # 2 storm from the city rim, inner flash + bolt
             ((0, 300, 20), (-1850, 150, 430), 35.0),             # 3 bolt over the sea: strike
             ((0, 300, 20), (-1850, 150, 430), 35.0),             # 4 bolt: fade (branches gone)
             ((0, 300, 20), (-2300, -1700, 420), 35.0),           # 5 waterspout wide from the port
             ((-200, 0, 560), (-2300, -1700, 450), 35.0),         # 6 waterspout from the city height
             ((-1650, -1150, 40), (-2300, -1700, 330), 24.0),     # 7 waterspout medium (~850 m)
             ((300, 600, 60), (-8000, -2500, 1300), 20.0)]        # 8 storm + spout, wide, flash
    qa_frame(sc, 'storm+spout', 2, [S, Wsp])
    qa_frame(sc, 'spout_vs_sea', 5, [Wsp], [bpy.data.objects['SEA']], allow=lambda a, b: 'funnel' in a.name + b.name or 'skirt' in a.name + b.name)
    REPORT['coplanar_sky'] = QA.coplanar([Wsp['foam'], bpy.data.objects['SEA']])
    p = dict(PARAMS); p.update(haze=(0.66, 0.68, 0.86), haze_dist=8000.0, haze_max=0.3)
    PV.shoot(sc, 'fx_sky', views, params=p)


# ======================================================================================================================== water
def group_water():
    sc, W = PV.setup('morning', sun=(95, 16))
    C = EV.coll('FX_PV', None)
    pil = pillar(C)
    N = 10
    t0 = time.time()
    crowns = []
    for v, m in ((1, 12), (2, 30), (3, 48), (4, 69), (5, 30)):
        cr = FX.splash_crown((0, 0, 0), 4.0, 36.0, f0=v - m, dur=None, coll=C, seed=5, name='FX_crown%d' % v)
        only_on(cr, v, N); crowns.append(cr)
    walls = []
    for v, m in ((6, 18), (7, 45), (8, 90)):
        wl = FX.splash_wall((-160, 450, 0), (160, 450, 0), 150.0, f0=v - m, dur=None, coll=C, seed=8, name='FX_wall%d' % v)
        only_on(wl, v, N); walls.append(wl)
    misc = []
    v = 9
    misc += [FX.foam_ring((300, -300, 0), 4.0, 40.0, f0=v - 21, dur=60, coll=C, seed=2, band=0.55, fill=0.6)]
    misc += FX.spray_trail([(150, -330), (220, -350), (290, -330), (360, -360), (430, -340)], f0=v - 30, dur=48, coll=C, seed=4, size=6.0)
    misc += [FX.droplets((320, -280, 0), f0=v - 9, dur=36, coll=C, seed=6, count=60, speed=22.0, size=0.45, spread=0.6)]
    misc += FX.debris((270, -270, 0), f0=v - 21, dur=60, coll=C, seed=9, count=24, speed=30.0)
    only_on(misc, v, N)
    far = [FX.foam_ring((-1300, 600, 0), 6.0, 45.0, f0=10 - 24, dur=60, coll=C, seed=3, band=0.55, fill=0.6, name='FX_farfoam'),
           FX.foam_ring((-600, 300, 0), 5.0, 35.0, f0=10 - 24, dur=60, coll=C, seed=4, band=0.55, fill=0.6, name='FX_farfoam2')]
    only_on(far, 10, N)
    REPORT['build_water_s'] = round(time.time() - t0, 2)
    views = [((75, -80, 10), (0, 0, 18), 35.0),          # 1-4 crown at 0.5 / 1.25 / 2.0 / 2.9 s (dur 3.7 s)
             ((75, -80, 10), (0, 0, 18), 35.0),
             ((75, -80, 10), (0, 0, 18), 35.0),
             ((75, -80, 10), (0, 0, 18), 35.0),
             ((26, -24, 3), (0, 0, 22), 24.0),           # 5 crown low and close at 1.25 s
             ((40, 30, 25), (0, 450, 80), 28.0),         # 6-8 splash wall 150 m at 0.75 / 1.9 / 3.75 s (dur 6 s)
             ((40, 30, 25), (0, 450, 80), 28.0),
             ((40, 30, 25), (0, 450, 80), 28.0),
             ((330, -470, 60), (300, -310, 4), 35.0),    # 9 foam ring, spray trail, droplets, debris
             ((-200, 0, 560), (-1000, 450, 0), 35.0)]    # 10 far foam rings from the city height (z-fight test)
    qa_frame(sc, 'crown', 2, crowns[1])
    qa_frame(sc, 'crown_vs_pillar', 2, crowns[1], [pil])
    qa_frame(sc, 'wall', 7, walls[1])
    sc.frame_set(9)
    REPORT['coplanar_water'] = QA.coplanar([o for o in flatten(misc) if 'foam' in o.name or 'wake' in o.name] + [bpy.data.objects['SEA']])
    PV.shoot(sc, 'fx_water', views, params=PARAMS)


# ======================================================================================================================== heat
def group_heat():
    sc, W = PV.setup('storm', sun=(95, 16), storm=0.55)
    C = EV.coll('FX_PV', None)
    m = LK.cel('M_pv_steel2', '#4b5163', ink=1.0, spec=0.5, rust=0.6, scuff=0.4, wscale=0.6)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    blk = EV.bm_obj('PV_block', bm, m, C); blk.scale = (10, 10, 8); blk.location = (0, 0, 4)
    N = 6
    st = []
    for v, mm in ((1, 9), (2, 24), (3, 42)):
        s = FX.steam((0, 0, 8.3), f0=v - mm, dur=66, coll=C, seed=3, count=9, size=1.8, speed=7.0, life=1.5, wind=(2.0, 0.5, 0.0), name='FX_steam%d' % v)
        only_on(s, v, N); st.append(s)
    sp = []
    for v, mm in ((4, 0), (5, 6), (6, 15)):
        s = FX.sparks((5.2, 0, 6.0), f0=v - mm, dur=24, coll=C, seed=7, count=50, speed=16.0, direction=(1, 0, 0.6), spread=0.75, size=1.0, name='FX_sparks%d' % v)
        only_on(s, v, N); sp.append(s)
        if mm > 0: only_on(s[1:], -5, N)
    views = [((18, -22, 9), (0, 0, 11), 35.0), ((18, -22, 9), (0, 0, 11), 35.0), ((18, -22, 9), (0, 0, 11), 35.0),
             ((22, -16, 7), (6, 0, 6.5), 35.0), ((22, -16, 7), (6, 0, 6.5), 35.0), ((22, -16, 7), (6, 0, 6.5), 35.0)]
    PV.shoot(sc, 'fx_heat', views, params=PARAMS)


# ======================================================================================================================== under
def group_under():
    sc, W = PV.setup('morning', sun=(95, 16), clouds=False)
    C = EV.coll('FX_PV', None)
    m = LK.cel('M_pv_sand', '#b9a582', ink=1.0, vary=0.12, vscale=0.05, grime=0.4, wscale=0.2)
    bed = EV.mesh_obj('PV_bed', [(-400, -400, -52), (400, -400, -52), (400, 400, -52), (-400, 400, -52)], [(0, 1, 2, 3)], m, C)
    rk = LK.cel('M_pv_rock', '#6c6a7a', ink=1.0, vary=0.1, grime=0.5, wscale=0.4)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=6.0)
    rock = EV.bm_obj('PV_rock', bm, rk, C); rock.location = (-22, 18, -52); rock.scale = (1.4, 1.0, 0.6)
    N = 3
    for v, mm in ((1, 9), (2, 30), (3, 54)):
        s = FX.silt((0, 0, -52), f0=v - mm, dur=72, coll=C, seed=4, radius=30.0, height=14.0, count=36, name='FX_silt%d' % v)
        b = FX.bubbles((10, -6, -51), f0=v - mm, dur=72, coll=C, seed=5, count=60, radius=5.0, size=0.5, rise=4.0, top=0.0, name='FX_bub%d' % v)
        only_on([s, b], v, N)
    views = [((0, -75, -40), (0, 0, -46), 28.0), ((0, -75, -40), (0, 0, -46), 28.0), ((0, -75, -40), (0, 0, -46), 28.0)]
    # kit/post.py decodes depth from the A png, which env.compositor writes through the sRGB view transform: the decoded depth
    # is ~8-15x too far here (true 28 m -> 445, 75 m -> 589). under_dist 1400 on that scale ~ a 90-120 m visibility. (Reported.)
    p = dict(PARAMS); p.update(under=1.0, under_dist=1400.0, haze_max=0.0)
    PV.shoot(sc, 'fx_under', views, params=p)


T0 = time.time()
for g in GROUPS:
    t0 = time.time(); globals()['group_' + g](); REPORT['time_' + g] = round(time.time() - t0, 1)
REPORT['total'] = round(time.time() - T0, 1)
os.makedirs(os.path.join(ROOT, 'out', 'preview', 'fx_report'), exist_ok=True)
json.dump(REPORT, open(os.path.join(ROOT, 'out', 'preview', 'fx_report', 'report_%s.json' % '_'.join(GROUPS)), 'w'), indent=1, default=str)
print('REPORT', json.dumps(REPORT, default=str))
