# Look-dev test: sky, sun, sea, cumulus, a weathered yellow machine block, a stone pier. Renders 1 frame + post.
#   blender -b -P kit/test_look.py -- [res%] [spp]
import bpy, sys, os, math, random, bmesh
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import look as LK, env as EV, stage as ST
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
res = int(args[0]) if args else 50; spp = int(args[1]) if len(args) > 1 else 16
sc = EV.reset(); EV.render_setup(sc, spp, res)
W = EV.coll('WORLD')
sun = EV.sun(sc, az=95, el=16, color='#ffe9cc', c=W)
LK.set_uniforms(sc, sunD=tuple(EV.sun_dir(95, 16)), sunC='#ffe2c0', skyC='#9fc0ff')
sky = EV.sky(sc, 'morning', c=W)
sea = EV.sea(sc, c=W)
cm = EV.cloud_mat()
EV.cloud_ring(sc, cm, W, dist=9000, n=14)
R = random.Random(3)
for i in range(7):
    a = math.radians(-60 + i * 22); d = R.uniform(1500, 3200)
    EV.cumulus('CU%d' % i, (math.sin(a) * d, math.cos(a) * d, 260), R.uniform(250, 520), R.uniform(180, 380), seed=40 + i, mat=cm, c=W)
# a weathered yellow machine block with hazard stripes
yel = LK.cel('M_yellow', '#f2b705', spec=0.6, grime=0.8, scuff=0.6, chips=0.8, rust=0.7, wscale=0.25)
haz = LK.cel('M_hazard', lambda nb: nb.stripes(nb.rgb('#f2b705'), nb.rgb('#1d1a24'), 0.18, axis=(0.7, 0.0, 0.7)), spec=0.4, grime=0.6, chips=0.6, wscale=0.25)
dark = LK.cel('M_steel', '#4b5163', spec=0.8, grime=0.5, scuff=0.8, wscale=0.25)
stone = LK.cel('M_stone', '#c9c2b4', paint=0.6, grime=0.6, algae=1.0, waterline=0.4, wscale=0.4, vary=0.12, vscale=0.08)
def box(name, size, loc, m, bev=0.4, rot=(0, 0, 0)):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    o = EV.bm_obj(name, bm, m, W); o.location = loc; o.rotation_euler = rot
    if bev: b = o.modifiers.new('bev', 'BEVEL'); b.width = bev; b.segments = 2; b.limit_method = 'ANGLE'
    return o
box('torso', (16, 10, 14), (0, 0, 22), yel, 0.8)
box('stripe', (16.2, 10.2, 2.4), (0, 0, 14.5), haz, 0.3)
box('hip', (10, 8, 6), (0, 0, 11), dark, 0.5)
box('legL', (4, 4, 12), (-4, 0, 3), yel, 0.4); box('legR', (4, 4, 12), (4, 0, 3), yel, 0.4)
box('pier', (60, 12, 6), (0, 25, 1.0), stone, 0.6)
for i in range(6): box('bollard%d' % i, (1.2, 1.2, 1.6), (-25 + i * 10, 20.5, 4.8), dark, 0.2)
cam = EV.camera('CAM', 28.0, W)
ST.key_cam(cam, 1, (-38, -60, 12), (4, 10, 20))
ST.follow_camera(sc, cam, 1, 1, sky)
EV.compositor(sc, os.path.join(HERE, '..', 'out', 'look'))
ST.render_range(sc, os.path.join(HERE, '..', 'out', 'look'), 1, 1, 'lookdev')
LK.save_registry(os.path.join(HERE, '..', 'out', 'look', 'reg.json'))
