# ANCHOR - the material-id pass of every frame of the mech's FX shots, rendered cheap (1 sample, half size, crisp pixel
# filter) exactly as the final render builds and keys them, for maskana.py: any piece of FX water whose outline is all mech
# armour (a puff, a crest billow, dissolving lace drawn over the body reads as a hole or a white sticker on it).
# Also dumps the material registry (name -> mid) and which materials the MECH and FX collections use.
#   blender -b -P tools/maskscan.py -- <tag> <res%> <shot,shot,...>
import sys, os, json, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'):
    q = os.path.join(ROOT, p)
    if q not in sys.path: sys.path.insert(0, q)
import bpy
import film
import env as EV, stage as ST, look as LK

A = sys.argv[sys.argv.index('--') + 1:]
tag = A[0]; res = int(A[1]); shots = [s for s in A[2].split(',') if s.strip()]
t0 = time.time()
W = film.build(1, res)
ids = [s[0] for s in film.SHOTS]
film.key_shots(W, ids)
print('built+keyed %.0fs' % (time.time() - t0), flush=True)
sc = W['sc']
try: sc.render.filter_size = 0.0
except Exception as ex: print('filter_size', ex)
print('filter_size', sc.render.filter_size, 'spp', sc.eevee.taa_render_samples, 'res', sc.render.resolution_percentage, flush=True)
out = os.path.join(ROOT, 'out', 'check', tag); raw = os.path.join(out, 'raw')
os.makedirs(raw, exist_ok=True)
cats = {'reg': {k: v['mid'] for k, v in LK.REG.items()}, 'coll': {}}
for k, c in W['C'].items():
    d = {}
    for o in c.all_objects:
        if o.type != 'MESH' or o.data is None: continue
        for m in o.data.materials:
            if m is not None: d.setdefault(m.name, []).append(o.name)
    cats['coll'][k] = {m: sorted(v)[:6] + (['... %d' % len(v)] if len(v) > 6 else []) for m, v in d.items()}
json.dump(cats, open(os.path.join(out, 'cats.json'), 'w'), indent=0)
print('registry', len(cats['reg']), 'materials; per collection', {k: len(v) for k, v in cats['coll'].items()}, flush=True)
EV.compositor(sc, raw)
for sid in shots:
    f0, f1 = film.frames_of(sid)
    film.apply_sets(W, sid)
    ts = time.time()
    ST.render_range(sc, raw, f0, f1, 'mask-' + tag)
    print('MASK shot %s %d-%d %.0fs (%.1fs/frame)' % (sid, f0, f1, time.time() - ts, (time.time() - ts) / (f1 - f0 + 1)), flush=True)
print('MASK DONE %.0fs' % (time.time() - t0), flush=True)
