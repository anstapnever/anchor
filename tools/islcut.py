# islcut.py <probe.json>[,<probe.json>...] [write] [--shots s33,s34] : from the probes' hits, the list shots/bodyfx.json
#   cut   - drops (they never dissolve): the element is not drawn in the drawings that show it as an island (it passes behind
#           the body, as bodydrops.py does)
#   melt  - billows (beads, crests, surge: the whole element) and jet tubes (the rings round the polygons hit, all round the
#           tube: a closed mass seen through its own hole would stay): the dissolve window is pulled forward, gone by the
#           island's first frame (by the shot's first frame when the island opens the shot)
#   erase - sheets (one big open mesh: a vertex melt eats far more than the piece): a dp-space spot in the water material
#           (fx._erase, pixel-exact), centred on the hit points' dp, radius from their spread, gone by the island's first frame
# Kept on purpose (listed): the s22 crown (rises in the mech's lap, grows into one column in front of it), the s22 wall's foam
# band washing over the legs (M_fx_wake, by design), foam rings on the sea, hits on the mech itself, pieces bigger than AMAX
# (a water mass), jet slivers under JMIN px, sheet bits under SMIN px.
# Several probes merge (the first base, later ones add islands of later rescans); --shots limits a probe to those shots.
# --hide=name:e:fa-fb[+fc-fd],... : a billow (bead, crest) not drawn in the drawings shown over those frames - a 'cut' like a
#   drop's, for a compact white blob on the armour that a melt cannot clear without its lace or what it covered showing
#   (s33 f1615, f1637, s34 f1695, 06.11); the ref is the element's centre from a probe hit.
import sys, os, json, collections, re, math
args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = {a.split('=')[0]: a.split('=')[1] for a in sys.argv[1:] if a.startswith('--') and '=' in a}
AMAX = 6000.0; JMIN = 100.0; SMIN = 100.0
SKIP = set(tuple(x.split(':')) for x in opt.get('--skip', '').split(',') if x)    # name:element melts left out
SHOTS = [('s21', 1009, 1056), ('s22', 1057, 1094), ('s23', 1095, 1138), ('s24', 1139, 1176), ('s25', 1177, 1258), ('s26', 1259, 1320),
         ('s27', 1321, 1378), ('s28', 1379, 1416), ('s30', 1465, 1522), ('s31', 1523, 1570), ('s32', 1571, 1613), ('s33', 1614, 1680),
         ('s34', 1681, 1728), ('s35', 1729, 1766), ('s37', 1825, 1886)]
OPEN = 4
KEEP = re.compile(r'^(FX_s22_crown_(crests|beads|jets)|FX_s22_front_foam|MECH_)|_foam$')
ER_MAX = 8; ER_GAP = 0.25; ER_MARGIN = 0.05; ER_MIN = 0.12


def shot_of(f):
    for s, a, b in SHOTS:
        if a <= f <= b: return s, a
    return '?', f


probes = []
for k, p in enumerate(args[0].split(',')):
    P = json.load(open(p)); lim = None
    key = '--shots%d' % k
    if key in opt: lim = set(opt[key].split(','))
    only = set(opt['--only%d' % k].split(',')) if ('--only%d' % k) in opt else {'drops', 'whole', 'rings', 'sheet'}
    probes.append((P, lim, only))
cut = {}; whole = {}; rings = {}; sheet = collections.defaultdict(list); kept = collections.defaultdict(set); unk = []; big = []
nv = {}; small = collections.defaultdict(set)
for P, lim, only in probes:
    sc2 = float(P.get('scale', 1.0)) ** 2; nv.update(P['nv'])
    big_el = set()
    for r in P['islands']:
        if r['area'] * sc2 > AMAX:
            for s in r['samples']:
                if s['hit'] and s['hit'][1] is not None: big_el.add((s['hit'][0], s['hit'][1]))
    for r in sorted(P['islands'], key=lambda r: r['f']):
        sh, s0 = shot_of(r['f'])
        if lim is not None and sh not in lim: continue
        a1080 = r['area'] * sc2
        if a1080 > AMAX: big.append((r['f'], int(a1080))); continue
        hs = [s['hit'] for s in r['samples'] if s['hit']]
        if not hs: unk.append((r['f'], r['c'], r['area'])); continue
        f = r['f']; fk = s0 if f - s0 <= OPEN else f
        for h in hs:
            name, e, poly, mat, z, cen, m = h[:7]; dpx = h[7] if len(h) > 7 else None
            if KEEP.search(name) or (name, e) in big_el: kept[name].add(f); continue
            if e is not None and re.search(r'_drops\d*$', name):
                if 'drops' not in only: continue
                d = cut.setdefault(name, {'m': int(m), 'n': int(P['nv'][name]) // int(m), 'el': {}})
                rec = d['el'].setdefault(str(e), {'ref': [f] + list(cen), 'frames': []})
                if f not in rec['frames']: rec['frames'].append(f)
            elif e is not None and not name.endswith('_jets'):
                if 'whole' not in only or (name, str(e)) in SKIP: continue
                kk = (name, e)
                if kk not in whole or fk < whole[kk]['f']:
                    old = whole.get(kk, {}).get('frames', [])
                    whole[kk] = {'f': fk, 'ref': [f] + list(cen), 'm': int(m), 'frames': old}
                if f not in whole[kk]['frames']: whole[kk]['frames'].append(f)
            elif e is not None:
                if 'rings' not in only: continue
                if a1080 < JMIN: small[name].add(f); continue
                kk = (name, e, fk)
                sp = rings.setdefault(kk, {'f': fk, 'e': e, 'm': int(m), 'polys': set(), 'ref': [f] + list(cen), 'frames': set()})
                sp['polys'].add(int(poly)); sp['frames'].add(f)
            else:
                if 'sheet' not in only: continue
                if a1080 < SMIN: small[name].add(f); continue
                if dpx is None: unk.append((r['f'], name, 'no dp')); continue
                sheet[name].append((fk, f, dpx))
# sheets: the hit points clustered in dp space (one cluster = one lace piece over its frames) -> erasers
erase = {}
for name, pts in sorted(sheet.items()):
    cl = []
    for fk, f, p in sorted(pts):
        for c in cl:
            if min(math.dist(p, q) for q in c['p']) < ER_GAP: c['p'].append(p); c['f'] = min(c['f'], fk); c['frames'].add(f); break
        else: cl.append({'p': [p], 'f': fk, 'frames': {f}})
    # merge clusters that grew into each other
    merged = True
    while merged:
        merged = False
        for i in range(len(cl)):
            for j in range(i + 1, len(cl)):
                if min(math.dist(p, q) for p in cl[i]['p'] for q in cl[j]['p']) < ER_GAP:
                    cl[i]['p'] += cl[j]['p']; cl[i]['f'] = min(cl[i]['f'], cl[j]['f']); cl[i]['frames'] |= cl[j]['frames']; del cl[j]; merged = True; break
            if merged: break
    ers = []
    for c in sorted(cl, key=lambda c: -len(c['p'])):
        ctr = [sum(p[i] for p in c['p']) / len(c['p']) for i in range(3)]
        spread = max(math.dist(p, ctr) for p in c['p'])
        r = max(ER_MIN, (spread + ER_MARGIN) / 0.7)
        ers.append({'c': [round(x, 4) for x in ctr], 'r': round(r, 4), 'f': c['f'], 'frames': sorted(c['frames']), 'n': len(c['p'])})
    if len(ers) > ER_MAX: print('!! %s: %d erasers, only %d fit - the smallest dropped' % (name, len(ers), ER_MAX))
    erase[name] = ers[:ER_MAX]
melt = {}
for (name, e), w in sorted(whole.items()):
    d = melt.setdefault(name, {'nv': int(nv[name]), 'm': w['m'], 'spots': []})
    d['spots'].append({'f': w['f'], 'e': int(e), 'whole': 1, 'polys': [], 'ref': w['ref'], 'frames': sorted(w['frames'])})
for (name, e, fk), sp in sorted(rings.items()):
    d = melt.setdefault(name, {'nv': int(nv[name]), 'm': sp['m'], 'spots': []})
    d['spots'].append({'f': sp['f'], 'e': int(sp['e']), 'whole': 0, 'rings': 1, 'polys': sorted(sp['polys']), 'ref': sp['ref'], 'frames': sorted(sp['frames'])})
print('CUT (drops, not drawn while over the body):')
for name, d in sorted(cut.items()):
    print('  %-34s %s' % (name, {e: rec['frames'] for e, rec in sorted(d['el'].items(), key=lambda kv: int(kv[0]))}))
print('MELT:')
for name, d in sorted(melt.items()):
    for s in d['spots']:
        print('  %-34s el %-4d %-6s kill f%d  island frames %s%s' % (name, s['e'], 'whole' if s['whole'] else 'rings', s['f'], s['frames'],
                                                             ('  polys %s' % s['polys'][:8]) if s['polys'] else ''))
print('ERASE (sheets):')
for name, ers in sorted(erase.items()):
    for x in ers: print('  %-34s c %s r %.3f kill f%d frames %s (%d pts)' % (name, x['c'], x['r'], x['f'], x['frames'], x['n']))
print('KEPT:')
for name, fs in sorted(kept.items()): print('  %-34s frames %s' % (name, sorted(fs)))
print('SMALL (kept, under the size limits):')
for name, fs in sorted(small.items()): print('  %-34s frames %s' % (name, sorted(fs)))
if unk: print('no hit:', unk[:30])
print('big:', big)
HIDE = [x for x in opt.get('--hide', '').split(',') if x]
for hx in HIDE:
    name, e, rng = hx.split(':'); e = int(e)
    fr = []
    for part in rng.split('+'):
        a, b = [int(v) for v in part.split('-')] if '-' in part else (int(part), int(part))
        fr += list(range(a, b + 1))
    ref = None
    for P, lim, only in probes:
        for r in sorted(P['islands'], key=lambda r: r['f']):
            for smp in r['samples']:
                h = smp['hit']
                if h and h[0] == name and h[1] == e and ref is None: ref = [r['f']] + list(h[5]); m = int(h[6])
    if ref is None: print('!! hide %s[%d]: no probe hit, no ref - left out' % (name, e)); continue
    d = cut.setdefault(name, {'m': m, 'n': int(nv[name]) // m, 'el': {}})
    rec = d['el'].setdefault(str(e), {'ref': ref, 'frames': []})
    for f in fr:
        if f not in rec['frames']: rec['frames'].append(f)
    print('HIDE %-34s el %-4d frames %d-%d (ref f%d)' % (name, e, min(fr), max(fr), ref[0]))
if 'write' in args:
    for d in cut.values():
        for rec in d['el'].values(): rec['frames'].sort()
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shots', 'bodyfx.json')
    json.dump({'cut': cut, 'melt': melt, 'erase': erase}, open(p, 'w', encoding='utf-8'), indent=0, sort_keys=True)
    print('written', p, 'cut', sum(len(d['el']) for d in cut.values()), 'drops in', len(cut), 'objects; melt',
          sum(len(d['spots']) for d in melt.values()), 'spots in', len(melt), 'objects; erase', sum(len(v) for v in erase.values()),
          'spots in', len(erase), 'objects')
