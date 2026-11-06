# ANCHOR — the mech lab (lead): stills of the baked performance at chosen moments from chosen views, in the real port set
# (ENV + PORT + MECH, optionally CHAIN), post-processed, plus a labelled contact sheet.
#   blender -b -P shots/mechlab.py -- 49.0,49.5,50.0 side,front [spp] [res%] [tag] [dist]
#   views: side (from the mech's left), right, front, back, q (front-left 3/4), qb (back-left 3/4), top, low (low front-left)
# Each (moment, view) is keyed onto its own spare frame (3001+), so one render pass gives the whole sheet.
import sys, os, math, time, json, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'): sys.path.insert(0, os.path.join(ROOT, p))
import bpy
import numpy as np
import film, common as CM, mechanim as MA, stage as ST, env as EV
PY = os.environ.get('ANCHOR_PY', 'python')   # Python 3.13 with numpy + opencv, outside Blender

A = sys.argv[sys.argv.index('--') + 1:]
times = [float(x) for x in A[0].split(',')]
views = A[1].split(',') if len(A) > 1 else ['side']
spp = int(A[2]) if len(A) > 2 else 8; res = int(A[3]) if len(A) > 3 else 30
tag = A[4] if len(A) > 4 else 'lab'; dist = float(A[5]) if len(A) > 5 else 170.0
need = {'ENV', 'PORT', 'MECH'} | ({'CHAIN'} if os.environ.get('LAB_CHAIN') else set())
W = film.build(spp, res, need)
sc = W['sc']
VIEW = {'side': (90.0, 10.0), 'right': (-90.0, 10.0), 'front': (0.0, 10.0), 'back': (180.0, 10.0), 'q': (40.0, 16.0), 'qb': (140.0, 16.0),
        'top': (20.0, 62.0), 'low': (30.0, -4.0)}
jobs = []
L = 3001
for t in times:
    for v in views:
        jobs.append((L, t, v)); L += 1
src = {j[0]: MA.fr(j[1]) for j in jobs}
for (Lf, t, v) in jobs:
    MA.key_range(W, Lf, Lf, src=lambda f: src[f])
    m = MA.mat('root', t); yaw = math.atan2(m[1, 0], m[0, 0])          # root's X axis = the mech's left
    c = MA.point('pelvis', t) + np.array((0.0, 0.0, 6.0))
    az, el = VIEW[v]
    fwd = np.array((math.sin(yaw), -math.cos(yaw), 0.0)); left = np.array((math.cos(yaw), math.sin(yaw), 0.0))
    d = fwd * math.cos(math.radians(az)) + left * math.sin(math.radians(az))
    pos = c + d * dist * math.cos(math.radians(el)) + np.array((0.0, 0.0, dist * math.sin(math.radians(el))))
    if v == 'low': pos[2] = max(pos[2], 2.0)
    CM.base(W, Lf, Lf, lambda tt, pos=pos, c=c: (pos, c, 35.0, 0.0))
n = W['TL'].flush(); print('lab keys', n)
for k, c in W['C'].items():
    c.hide_render = k not in need
if not os.environ.get('LAB_FULL'):     # the lab looks at the mech: the yard, sheds, cranes and town would only block the views
    for c in bpy.data.collections:
        if c.name in ('PORT_yard', 'PORT_buildings', 'PORT_cranes', 'PORT_town'): c.hide_render = True
raw = os.path.join(ROOT, 'out', 'lab', tag, 'raw'); dst = os.path.join(ROOT, 'out', 'lab', tag, 'post')
os.makedirs(raw, exist_ok=True); os.makedirs(dst, exist_ok=True)
EV.compositor(sc, raw)
ST.render_range(sc, raw, jobs[0][0], jobs[-1][0], 'mechlab')
spec = {'default': {}, 'ranges': []}
pj = os.path.join(ROOT, 'out', 'lab', tag, 'post_%d.json' % os.getpid()); json.dump(spec, open(pj, 'w'))
subprocess.run([PY, os.path.join(ROOT, 'kit', 'post.py'), raw, dst, str(jobs[0][0]), str(jobs[-1][0]), pj, '6'])
json.dump([[j[0], j[1], j[2]] for j in jobs], open(os.path.join(ROOT, 'out', 'lab', tag, 'jobs.json'), 'w'))
# contact sheet
import_ok = True
code = r'''
import cv2, json, sys, os, numpy as np
d = sys.argv[1]; jobs = json.load(open(os.path.join(d, 'jobs.json')))
ims = []
for (f, t, v) in jobs:
    p = os.path.join(d, 'post', 'f%04d.png' % f); im = cv2.imread(p)
    if im is None: continue
    cv2.putText(im, '%.2f %s' % (t, v), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3); cv2.putText(im, '%.2f %s' % (t, v), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
    ims.append(im)
nv = int(sys.argv[2]); rows = [ims[i:i + nv] for i in range(0, len(ims), nv)]
h, w = ims[0].shape[:2]
rows = [np.hstack(r + [np.zeros((h, w, 3), np.uint8)] * (nv - len(r))) for r in rows]
sheet = np.vstack(rows)
s = min(1.0, 2400.0 / sheet.shape[1]); sheet = cv2.resize(sheet, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
cv2.imwrite(os.path.join(d, 'sheet.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
'''
cp = os.path.join(ROOT, 'out', 'lab', tag, '_sheet.py'); open(cp, 'w').write(code)
subprocess.run([PY, cp, os.path.join(ROOT, 'out', 'lab', tag), str(len(views))])
print('LAB DONE', tag, len(jobs))
