# ANCHOR — the film runner. Builds the whole world once, lets every shot key its frame range on the global timeline, then renders,
# checks or previews any set of shots. Shot visibility (which sets render) is applied per shot right before its frames render.
#   blender -b -P shots/film.py -- render s01,s02 [spp] [res%]        full frames of those shots -> out/frames (+ post)
#   blender -b -P shots/film.py -- stills s01,s05 [spp] [res%]        first/middle/last frame of each shot -> out/stills
#   blender -b -P shots/film.py -- qa s01-s43                         intersections, camera, smoothness reports -> qa/
#   (shot lists: comma separated, ranges like s20-s25, or 'all'; frames override: FR=lo-hi env)
import sys, os, json, time, math, importlib, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'): sys.path.insert(0, os.path.join(ROOT, p))
import bpy
import look as LK, env as EV, stage as ST, timeline as TLM, chain as CH, story as S
PY = os.environ.get('ANCHOR_PY', 'python')   # Python 3.13 with numpy + opencv, outside Blender

SHOTS = [  # id, t0, t1, sets that render
    ('s01', 0.0, 3.0, 'ENV CITY CHAIN PORT'), ('s02', 3.0, 4.6, 'ENV CITY'), ('s03', 4.6, 7.4, 'ENV CITY CHAIN PORT'),
    ('s04', 7.4, 9.6, 'ENV PORT MECH CHAIN CITY'), ('s05', 9.6, 11.2, 'ENV MECH PORT'), ('s06', 11.2, 14.0, 'UNDER CHAIN'),
    ('s07', 14.0, 16.4, 'ENV CITY FX'), ('s08', 16.4, 18.4, 'ENV PORT FX CHAIN CITY'), ('s09', 18.4, 20.0, 'ENV CITY FX'),
    ('s10', 20.0, 22.0, 'ENV CITY CHAIN FX'), ('s11', 22.0, 24.4, 'ENV FX CITY CHAIN'), ('s12', 24.4, 25.8, 'ENV CITY CHAIN FX'),
    ('s13', 25.8, 28.0, 'ENV CHAIN FX CITY'), ('s14', 28.0, 30.0, 'UNDER CHAIN FX'), ('s15', 30.0, 31.6, 'UNDER CHAIN FX'),
    ('s16', 31.6, 33.2, 'UNDER CHAIN FX'), ('s17', 33.2, 35.2, 'ENV CHAIN FX PORT CITY'), ('s18', 35.2, 37.4, 'ENV CITY FX'),
    ('s19', 37.4, 39.0, 'ENV CITY CHAIN'), ('s20', 39.0, 42.0, 'ENV CITY CHAIN PORT FX'), ('s21', 42.0, 44.0, 'ENV PORT CHAIN FX MECH'),
    ('s22', 44.0, 45.6, 'ENV MECH PORT FX'), ('s23', 45.6, 47.4, 'ENV MECH PORT FX'), ('s24', 47.4, 49.0, 'ENV MECH'),
    ('s25', 49.0, 52.4, 'ENV MECH PORT FX'), ('s26', 52.4, 55.0, 'ENV MECH PORT FX CITY CHAIN'), ('s27', 55.0, 57.4, 'ENV MECH PORT FX'),
    ('s28', 57.4, 59.0, 'ENV MECH PORT FX'), ('s29', 59.0, 61.0, 'ENV CITY CHAIN FX'), ('s30', 61.0, 63.4, 'ENV MECH PORT FX'),
    ('s31', 63.4, 65.4, 'ENV MECH FX PORT'), ('s32', 65.4, 67.2, 'ENV MECH FX'), ('s33', 67.2, 70.0, 'ENV MECH CHAIN FX'),
    ('s34', 70.0, 72.0, 'ENV MECH CHAIN FX'), ('s35', 72.0, 73.6, 'ENV MECH FX'), ('s36', 73.6, 76.0, 'ENV CITY CHAIN FX'),
    ('s37', 76.0, 78.6, 'ENV MECH PORT CHAIN FX'), ('s38', 78.6, 80.6, 'ENV CITY FX CHAIN'), ('s39', 80.6, 82.0, 'ENV CHAIN CITY MECH PORT'),
    ('s40', 82.0, 84.4, 'ENV CITY CHAIN'), ('s41', 84.4, 86.4, 'ENV MECH PORT CHAIN CITY'), ('s42', 86.4, 88.2, 'ENV MECH'),
    ('s43', 88.2, 90.0, 'ENV MECH'),
]
SETS = ('ENV', 'CITY', 'PORT', 'MECH', 'UNDER', 'CHAIN', 'FX')


def frames_of(sid):
    for s, t0, t1, _ in SHOTS:
        if s == sid: return TLM.fr(t0), TLM.fr(t1) - 1
    raise KeyError(sid)


def parse(spec):
    ids = [s[0] for s in SHOTS]
    if spec == 'all': return ids
    out = []
    for part in spec.split(','):
        if '-' in part:
            a, b = part.split('-'); out += ids[ids.index(a):ids.index(b) + 1]
        else: out.append(part)
    return out


def build(spp=16, res=100, need=None):
    """need: set of set names to build (default all)."""
    need = set(need or SETS)
    sc = EV.reset(); EV.render_setup(sc, spp, res)
    W = {'sc': sc, 'TL': TLM.Store()}
    C = {k: EV.coll(k) for k in SETS}; W['C'] = C
    az, el, col = S.sun(0.0)
    W['sun'] = EV.sun(sc, az, el, col, C['ENV'])
    LK.set_uniforms(sc, sunD=tuple(EV.sun_dir(az, el)), sunC=col, skyC='#9fc0ff')
    W['sky'] = EV.sky(sc, 'morning', c=C['ENV']); sc['cloudStorm'] = 0.0
    W['sea'] = EV.sea(sc, c=C['ENV'])
    W['cloudmat'] = EV.cloud_mat()
    W['ring'] = EV.cloud_ring(sc, W['cloudmat'], C['ENV'])
    # a scattered cumulus layer at 170-300 m round the bay: the city floats above it, the chain dives through it
    import random as _r
    R = _r.Random(91); W['low'] = []
    spots = [(-420, -80), (180, -60), (-260, -420), (60, 420), (-620, 260), (320, 260), (-30, -260), (-880, -120), (520, -320), (-180, 700), (700, 60), (-1100, 300)]
    for i, (x, y) in enumerate(spots):
        w = R.uniform(140, 300); h = R.uniform(70, 150)
        W['low'].append(EV.cumulus('CLOUD_low%02d' % i, (x, y, R.uniform(170, 250)), w, h, puff=w * 0.16, seed=300 + i, mat=W['cloudmat'], c=C['ENV']))
    W['cam'] = EV.camera('CAM', 35.0, C['ENV'])
    t0 = time.time()
    if 'CHAIN' in need: W['chain'] = CH.build(C['CHAIN'], 80, 12)
    for name, mod in (('CITY', 'city'), ('PORT', 'port'), ('MECH', 'mech'), ('UNDER', 'under'), ('FX', 'fx')):
        if name not in need: continue
        try:
            m = importlib.import_module(mod); W[mod + '_mod'] = m
            if name == 'CITY': W['city'] = m.build(C[name], far_ink=dict(d0=140.0, d1=650.0, k=0.3))
            elif name == 'FX': W['fx'] = m.build(C[name])          # the persistent storm wall + waterspout; the rest per shot
            elif name == 'UNDER': W['under'] = m.build(C[name])
            else: W[mod] = m.build(C[name])
            print('built', name, '%.1fs' % (time.time() - t0)); t0 = time.time()
        except Exception as ex:
            import traceback; traceback.print_exc(); print('BUILD FAILED', name, ex); raise
    return W


ACTS = ['act_sky', 'act_under', 'act_port', 'act_mech', 'act1']      # first module defining a shot wins (owners: see SHOT_OWNER)


def shot_fn(sid):
    for a in ACTS:
        try: m = importlib.import_module(a)
        except ModuleNotFoundError: continue
        if hasattr(m, sid): return m, getattr(m, sid)
    return None, None


def key_shots(W, ids):
    for sid in ids:
        f0, f1 = frames_of(sid)
        m, fn = shot_fn(sid)
        if fn is None: print('no shot', sid); continue
        t0 = time.time(); fn(W, f0, f1); print('keyed', sid, f0, f1, '%.1fs' % (time.time() - t0))
    n = W['TL'].flush(); print('keys', n)
    # drops passing near a shot's lens are scaled down to fine droplets (s26's ice cones, 06.11): needs every camera key
    import lenscull
    sets_of = {}
    for s, a, b, sets in SHOTS:
        fa, fb = frames_of(s)
        for f in range(fa, fb + 1): sets_of[f] = set(sets.split())
    lenscull.shrink_near_drops(W, sets_of)
    # drops drawn over the mech's body read as thorns or studs on its armour (s32 f1612, 06.11): every element the camera-ray
    # scan saw over the body is not drawn in the drawings that show it there - it passes behind the body (shots/bodydrops.json)
    import bodydrops
    bodydrops.clear_body_drops(W)
    # a piece of water whose whole outline is armour (a crest billow, a rim bead, dissolving lace) reads as a hole or a white
    # sticker on the body (s34 f1693, f1716, 06.11): those elements are not drawn in those drawings (shots/bodyfx.json)
    import bodyfx
    bodyfx.clear_body_islands(W)


def apply_sets(W, sid):
    sets = next(s for s in SHOTS if s[0] == sid)[3].split()
    for k, c in W['C'].items():
        c.hide_render = k not in sets
        for o in c.all_objects: o.hide_viewport = k not in sets   # keeps depsgraph light, QA sees what renders


def post_params(sid):
    m, fn = shot_fn(sid)
    return getattr(m, 'POST', {}).get(sid, {}) if m else {}


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    mode = a[0]; ids = parse(a[1] if len(a) > 1 else 'all')
    spp = int(a[2]) if len(a) > 2 else (24 if mode == 'render' else 16); res = int(a[3]) if len(a) > 3 else 100
    # KEYALL=1: build every set and key EVERY shot, then render/check only `ids`. A shot's own FX can outlive it (s22's surge
    # runs into s23), so a frame must not depend on which shots share its run: the final render and its re-runs use KEYALL.
    kids = [s[0] for s in SHOTS] if os.environ.get('KEYALL') == '1' else ids
    need = set()
    for sid in kids: need |= set(next(s for s in SHOTS if s[0] == sid)[3].split())
    W = build(spp, res, need)
    key_shots(W, kids)
    sc = W['sc']
    sub = {'render': 'frames', 'stills': 'stills', 'qa': 'qa_frames'}.get(mode, 'tmp')
    raw = os.path.join(ROOT, 'out', sub)
    EV.compositor(sc, raw)
    spec = {'default': {}, 'ranges': []}
    for sid in ids:
        f0, f1 = frames_of(sid); apply_sets(W, sid)
        P = post_params(sid); spec['ranges'].append([f0, f1, P])
        if mode == 'render':
            lo, hi = f0, f1
            if os.environ.get('FR'): lo, hi = [int(x) for x in os.environ['FR'].split('-')]; lo = max(lo, f0); hi = min(hi, f1)
            if lo <= hi: ST.render_range(sc, raw, lo, hi, 'film-' + sid)
        elif mode == 'stills':
            for f in sorted(set((f0, (f0 + f1) // 2, f1))): ST.render_range(sc, raw, f, f, 'still-' + sid)
        elif mode == 'qa':
            import qa_film; qa_film.run(W, sid, f0, f1)
    pj = os.path.join(ROOT, 'out', 'post_%s_%d.json' % (sub, os.getpid()))          # per run: concurrent runs never share a spec
    json.dump(spec, open(pj, 'w'), indent=0)
    if mode in ('render', 'stills'):
        dst = os.path.join(ROOT, 'out', 'final' if mode == 'render' else 'stills_post')
        for sid in ids:
            f0, f1 = frames_of(sid)
            if mode == 'stills':
                for f in sorted(set((f0, (f0 + f1) // 2, f1))):
                    subprocess.run([PY, os.path.join(ROOT, 'kit', 'post.py'), raw, dst, str(f), str(f), pj, '1'])
            else:
                subprocess.run([PY, os.path.join(ROOT, 'kit', 'post.py'), raw, dst, str(f0), str(f1), pj, '8'])
    print('FILM DONE', mode, ids)
