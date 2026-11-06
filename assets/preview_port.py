# PORT preview: builds the port into the shared environment and renders the views the port plays in.
#   blender -b -P assets/preview_port.py -- 50 16            all views -> out/preview/port/
#   blender -b -P assets/preview_port.py -- 50 16 qa         build + QA + triangle count only (no render; add 'render' to also render)
#   blender -b -P assets/preview_port.py -- 50 16 v=1,4      only those views -> out/preview/port_sub/
#   ... ink=1.0                                                   build(far_ink=1.0): ink weight of the far town/trees/hills
import bpy, sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'kit')); sys.path.insert(0, HERE)
import look as LK, env as EV, preview as PV, stage as ST
import port

A = PV.args(); MODE = 'qa' if ('qa' in A[2:] and 'render' not in A[2:]) else 'render'
sc, W = PV.setup(preset='morning', sun=(95, 16))
t0 = time.time()
opts = {}
for a in A[2:]:
    if a.startswith('ink='): opts['far_ink'] = float(a[4:])
P = port.build(None, **opts)
print('BUILD_S %.1f' % (time.time() - t0))
objs = port.all_objects(P)
print('OBJECTS %d  MESH %d' % (len(objs), sum(o.type == 'MESH' for o in objs)))
print('TRIS %d' % port.ntris(objs))
for k, v in P['info'].items(): print('INFO', k, v)
for k, v in sorted(LK.REG.items(), key=lambda kv: kv[1]['mid']): print('MID %d %s ink %.2f' % (v['mid'], k, v['ink']))

# views: (name, pos, target, lens[, roll])
VIEWS = [
    ('04 wide port at dawn', (-200.0, 50.0, 120.0), (-430.0, 470.0, 6.0), 26.0),
    ('21 crane A from the water', (-292.0, 318.0, 9.0), (-372.0, 402.0, 34.0), 22.0),
    ('08 boats past the lighthouse', (-598.0, -236.0, 7.0), (-695.0, -172.0, 24.0), 30.0),
    ('30 breakwater low near the tip', (-694.0, -127.0, 7.0), (-703.0, 120.0, 12.0), 22.0),
    ('37 lighthouse close', (-646.0, -122.0, 12.0), (-700.0, -168.0, 34.0), 24.0),
    ('dock 3 from the rim', (-404.0, 612.0, 13.0), (-468.0, 486.0, -9.0), 22.0),
    ('20 lighthouse foreground, port behind', (-770.0, -275.0, 22.0), (-520.0, 230.0, 30.0), 30.0),
    ('crane A from the quay', (-326.0, 401.5, 6.2), (-372.0, 420.0, 40.0), 20.0),
]
sel = None
for a in A[2:]:
    if a.startswith('v='): sel = [int(x) for x in a[2:].split(',')]
views = [v for i, v in enumerate(VIEWS) if sel is None or i + 1 in sel]

# staging per frame (one frame per view): boats racing past the lighthouse in shot 08, the lighthouse cracked and tilted in 37
LH = P['lighthouse']; boats = P['boats']
home = [(b.location.copy(), b.rotation_euler.copy()) for b in boats]
RACE = [((-658.0, -218.0), 18.0, 3.0), ((-635.4, -180.1), 24.0, -2.5), ((-739.8, -214.4), 12.0, 2.0)]
for f, v in enumerate(views, start=1):
    race = v[0].startswith('08'); bend = v[0].startswith('37')
    for i, b in enumerate(boats):
        if race and i < len(RACE):
            (x, y), yaw, roll = RACE[i]; b.location = (x, y, home[i][0].z); b.rotation_euler = (math.radians(roll), math.radians(-1.5), math.radians(yaw))
        else:
            b.location = home[i][0]; b.rotation_euler = home[i][1]
        b.keyframe_insert('location', frame=f); b.keyframe_insert('rotation_euler', frame=f)
    # tilt 4 deg toward the south-west about the tower foot (z 27)
    t = math.radians(4.0) if bend else 0.0
    LH['mid'].rotation_euler = (t * math.sin(math.radians(45.0)), -t * math.cos(math.radians(45.0)), 0.0)
    LH['mid'].keyframe_insert('rotation_euler', frame=f)
    port.set_crack(P, 0.65 if bend else 0.0, frame=f)
    port.set_beam(P, 1.0 if bend else 0.0, frame=f)
    # crane A hoist test in its quay view: spreader 8 m lower (the ropes follow by driver)
    sp = P['craneA']['spreader']; sp.location.z = port.SPREADER_Z - (8.0 if v[0].startswith('crane A from the quay') else 0.0)
    sp.keyframe_insert('location', index=2, frame=f)
for o in boats + [LH['mid'], LH['base'], LH['top'], LH['lamp'], P['craneA']['spreader']]:
    if o.animation_data and o.animation_data.action: ST.set_interp(o, 'CONSTANT')

if 'qa' in A[2:]:
    t1 = time.time(); r = port.qa(P)
    print('QA_S %.1f  objects %d tiles %d' % (time.time() - t1, r['n_objects'], r['n_tiles']))
    print('QA_PAIRS %d' % len(r['pairs']))
    for k, n in r['pairs'][:60]: print('  PAIR', k[0], k[1], n)
    print('QA_BOATS_GROUND', r['boats_vs_ground'][:20])
    print('QA_TETRA_CAP', len(r['tetra_vs_cap']), r['tetra_vs_cap'][:20])
    if MODE == 'qa': sys.exit(0)

name = 'port' if sel is None else 'port_sub'
for i, v in enumerate(views): print('VIEW f%04d' % (i + 1), v[0])
PV.shoot(sc, name, [tuple(v[1:]) for v in views])
print('DONE', name)
