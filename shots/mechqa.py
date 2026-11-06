# ANCHOR — QA of the mech track alone (lead): the baked performance keyed in the real port + seabed (ENV, PORT, UNDER, MECH,
# optionally CHAIN with LAB_CHAIN=1), every frame (or every QA_STEP-th): mech parts vs the set, mech self-overlaps (mech.qa_allow),
# knee bends outside the rig's range. Camera checks are the shots' business (qa_film).
#   blender -b -P shots/mechqa.py -- 1177-1522 [tag]          -> out/qa/mech_<tag>.json
import sys, os, math, time, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'): sys.path.insert(0, os.path.join(ROOT, p))
import bpy
import numpy as np
from mathutils import Vector
import film, mechanim as MA, qa_film as QF

A = sys.argv[sys.argv.index('--') + 1:]
f0, f1 = (int(x) for x in A[0].split('-'))
tag = A[1] if len(A) > 1 else '%d_%d' % (f0, f1)
step = int(os.environ.get('QA_STEP', '1'))
need = {'ENV', 'PORT', 'MECH', 'UNDER'} | ({'CHAIN'} if os.environ.get('LAB_CHAIN') else set())
W = film.build(4, 10, need)
sc = W['sc']; t0 = time.time()
MA.key_range(W, f0, f1)
if 'chain' in W:
    import common as CM
    CM.chain_key(W, f0, f1, heat=False)
W['TL'].flush()
kinds_all = QF._movers(W)
kinds = {k: v for k, v in kinds_all.items() if v in ('mech', 'bird') or (v == 'chain' and 'chain' in W)}
allow0 = QF._allow_default(W)
def allow(a, b): return allow0(a, b, kinds)
hidden = QF._all_hidden_colls(W)
skip_static = ('SKY', 'SEA', 'CLOUD', 'FX_', 'UNDER_ray', 'UNDER_snow', 'UNDER_surface', 'UNDER_backdrop', 'UNDER_fish', 'PORT_sea')
sc.frame_set(f0); dg = bpy.context.evaluated_depsgraph_get()
statics = {}
for o in sc.objects:
    if o.type != 'MESH' or o.name in kinds_all: continue
    if o.name.startswith(skip_static) or o.name.upper().startswith(skip_static): continue
    if o.hide_render or QF._hidden_now(o, hidden): continue
    if o.get('qa_kind') == 'fx': continue
    r = QF._mesh_world(o, dg)
    if r: statics[o.name] = (o,) + r
G = 40.0; grid = {}
for sn, s in statics.items():
    for gx in range(int(math.floor(s[2].x / G)), int(math.floor(s[3].x / G)) + 1):
        for gy in range(int(math.floor(s[2].y / G)), int(math.floor(s[3].y / G)) + 1):
            grid.setdefault((gx, gy), []).append(sn)
def near(lo, hi, pad=0.1):
    out = set()
    for gx in range(int(math.floor((lo.x - pad) / G)), int(math.floor((hi.x + pad) / G)) + 1):
        for gy in range(int(math.floor((lo.y - pad) / G)), int(math.floor((hi.y + pad) / G)) + 1):
            out.update(grid.get((gx, gy), ()))
    return out
print('MECHQA statics %d movers %d (%.1fs)' % (len(statics), len(kinds), time.time() - t0), flush=True)
bad = {}
for f in range(f0, f1 + 1, step):
    sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
    mv = {}
    for nm in kinds:
        o = bpy.data.objects.get(nm)
        if o is None or o.hide_render or QF._hidden_now(o, hidden): continue
        r = QF._mesh_world(o, dg)
        if r: mv[nm] = (o,) + r
    names = sorted(mv)
    for i, an in enumerate(names):
        a = mv[an]
        for sn in near(a[2], a[3]):
            s = statics[sn]
            if not QF._hit(a, s, 0.05) or allow(a[0], s[0]): continue
            if a[1].overlap(s[1]): bad.setdefault((an, sn), []).append(f)
        for bn in names[i + 1:]:
            b = mv[bn]
            if not QF._hit(a, b, 0.05) or allow(a[0], b[0]): continue
            if a[1].overlap(b[1]): bad.setdefault((an, bn), []).append(f)
    if (f - f0) % 48 == 0: print('  f %d  pairs %d  %.0fs' % (f, len(bad), time.time() - t0), flush=True)
# knee range from the track
TR = MA.load(); names = list(TR['names']); knee = []
for sd in ('L', 'R'):
    k = next(i for i, n in enumerate(names) if str(n).endswith('knee' + sd))
    a = np.degrees(TR['rot'][f0:f1 + 1, k, 0])
    for i, x in enumerate(a):
        if x > 101.0 or x < -9.0: knee.append((f0 + i, sd, round(float(x), 1)))
rep = dict(frames=[f0, f1], step=step, overlaps=[dict(a=k[0], b=k[1], n=len(v), frames=v[:40]) for k, v in sorted(bad.items())],
           knee=knee[:300], n_knee=len(knee), secs=round(time.time() - t0, 1))
os.makedirs(os.path.join(ROOT, 'out', 'qa'), exist_ok=True)
json.dump(rep, open(os.path.join(ROOT, 'out', 'qa', 'mech_%s.json' % tag), 'w'), indent=1)
print('MECHQA %s overlaps %d knee %d (%.0fs)' % (tag, len(bad), len(knee), rep['secs']))
for k, v in sorted(bad.items(), key=lambda kv: kv[1][0]): print('   overlap', k[0], k[1], 'frames', v[0], '..', v[-1], 'n', len(v))
for k in knee[:20]: print('   knee', k)
