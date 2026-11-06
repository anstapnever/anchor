# Department preview harness: the shared environment + your asset + N camera views -> rendered, post-processed stills and a contact sheet.
#   in your preview script (run with blender -b -P assets/preview_x.py -- [res%] [spp]):
#       import preview as PV
#       sc, W = PV.setup(preset='morning', sun=(95, 16))
#       ... build your asset into W (or your own collection) ...
#       PV.shoot(sc, 'mech', [((x,y,z), (tx,ty,tz), lens), ...])          # writes out/preview/mech/post/fNNNN.png + sheet.jpg
import bpy, sys, os, math, subprocess, random
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PY = os.environ.get('ANCHOR_PY', 'python')   # Python 3.13 with numpy + opencv, outside Blender
sys.path.insert(0, HERE)
import look as LK, env as EV, stage as ST


def args():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def setup(preset='morning', sun=(95.0, 16.0), sea=True, clouds=True, res=None, spp=None, storm=0.0):
    a = args()
    res = res or (int(a[0]) if a else 50); spp = spp or (int(a[1]) if len(a) > 1 else 16)
    sc = EV.reset(); EV.render_setup(sc, spp, res)
    W = EV.coll('WORLD')
    s = EV.sun(sc, az=sun[0], el=sun[1], c=W)
    LK.set_uniforms(sc, sunD=tuple(EV.sun_dir(*sun)), sunC='#ffe6c6', skyC='#9fc0ff')
    sky = EV.sky(sc, preset, c=W); sc['skyStorm'] = storm; sc['cloudStorm'] = storm
    if sea: EV.sea(sc, c=W)
    if clouds:
        cm = EV.cloud_mat(); EV.cloud_ring(sc, cm, W, dist=9000, n=14)
        R = random.Random(3)
        for i in range(6):
            a_ = math.radians(-70 + i * 28); d = R.uniform(1800, 3400)
            EV.cumulus('CU%d' % i, (math.sin(a_) * d, math.cos(a_) * d, 260), R.uniform(250, 520), R.uniform(180, 380), seed=40 + i, mat=cm, c=W)
    sc['_sky'] = sky.name
    return sc, W


def shoot(sc, name, views, post=True, params=None):
    """views: list of (pos, target, lens[, roll]). One frame per view."""
    cam = EV.camera('CAM', views[0][2])
    for i, v in enumerate(views):
        ST.key_cam(cam, i + 1, v[0], v[1], v[2], v[3] if len(v) > 3 else 0.0)
    ST.set_interp(cam, 'CONSTANT'); ST.set_interp(cam.data, 'CONSTANT')
    sky = bpy.data.objects.get(sc.get('_sky', 'SKY'))
    ST.follow_camera(sc, cam, 1, len(views), sky)
    ST.set_interp(sc, 'CONSTANT')
    raw = os.path.join(ROOT, 'out', 'preview', name, 'raw'); pst = os.path.join(ROOT, 'out', 'preview', name, 'post')
    EV.compositor(sc, raw)
    ST.render_range(sc, raw, 1, len(views), 'prev-' + name)
    if post:
        spec = os.path.join(ROOT, 'out', 'preview', name, 'post.json')
        import json; json.dump({'default': params or {}}, open(spec, 'w'))
        subprocess.run([PY, os.path.join(HERE, 'post.py'), raw, pst, '1', str(len(views)), spec, '4'])
        sheet(pst, len(views), os.path.join(ROOT, 'out', 'preview', name, 'sheet.jpg'))


def sheet(pst, n, out):
    subprocess.run([PY, '-c', '''
import cv2, numpy as np, sys
pst, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ims = [cv2.imread(pst + "/f%04d.png" % (i + 1)) for i in range(n)]
ims = [cv2.resize(i, (640, 360)) for i in ims if i is not None]
while len(ims) % 2: ims.append(np.zeros_like(ims[0]))
rows = [np.hstack(ims[i:i + 2]) for i in range(0, len(ims), 2)]
cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
''', pst, str(n), out])
