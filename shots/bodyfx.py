# ANCHOR - water islands drawn on the mech's body (06.11). A piece of FX water whose whole outline on screen is the mech's
# armour - a crest billow torn off a plume, a rim bead hanging on the pauldron, the last lace of a dissolving sheet, a drop -
# reads as a hole in the armour or a white sticker on it, not as water in front of it: s33 f1635-1647 and s34 f1693 a white
# oval on the pauldron, s34 f1702 a white crescent on a yellow plate, f1716-1717 white flecks on the thigh, f1719-1720 a white
# streak down the leg.
# The check (maskscan.py: the material-id pass of every frame of the mech's FX shots, rendered as the final render keys
# them; maskana.py: every connected piece of FX water whose outline is >= 75 % armour and which is nearer than that armour;
# islprobe.py: camera rays through the piece's pixels name the object, the element and the polygon whose surface sits at the
# pass's depth; islcut.py) writes bodyfx.json:
#   cut  - drops (they never dissolve): the element is not drawn in the drawings that show it as an island - like the drops of
#          bodydrops.py it passes behind the body, the outline it would draw lies all on the armour
#   melt - billows (beads, crests, surge billows: the whole element) and jet tubes (the rings the hit polygons touch +-1,
#          all round the tube, +-2 at half weight): the dissolve window (vertex d0/d1, s) is pulled forward so it has run into
#          lace and is gone by the island's first frame (by the shot's first frame when the island opens the shot) - never
#          later than before, and over >= 3 drawings, so nothing pops
#   erase - sheets (one big open mesh near the lens: a vertex melt took whole columns of water with it, 06.11): spots in the
#          water material itself (fx._erase): object props er<i>c/r/t, a dp-space ball round the hit points, pixel-exact
# {"cut": {object: {"m", "n", "el": {element: {"ref": [frame, cx, cy, cz], "frames": [...]}}}},
#  "melt": {object: {"nv", "m", "spots": [{"f": kill frame, "e": element or -1, "whole": 0/1, "rings": 0/1, "polys": [...],
#                                          "ref": [frame, cx, cy, cz] or null, "frames": [island frames]}]}},
#  "erase": {object: [{"c": [dp x, y, z], "r": dp radius, "f": kill frame, "frames": [...]}]},
#  "behind": {object: {"m", "n", "el": {element: {"ref": [frame, cx, cy, cz] or null, "win": [first frame, last frame]}}}}}
#   behind - (06.11) jets, crests and beads that go THROUGH the armour (the crown splashes were made without the body: a
#          column slicing the pauldron, the head inside a column, a ball sunk in the pauldron, s32-s34; the seam check
#          seamana2.py finds them): over its window (whole shots, so the layering never flips mid-shot) the element passes
#          behind the mech - vertex attrs bh0/bh1 + the scene uniform bh_fr; fx._behind cuts it at the mech's matte
#          (out/matte: the mech alone and the mech with only solid things - sea, port, chain - in front of it, no FX surface;
#          such 'fx-clear' mattes fit any list whose windows lie in their frames, a window frame without one is STALE MATTE)
# ref: the element's centre (object space) in the drawing shown at that frame when the check ran; an effect changed since then
# is reported STALE instead of being cut blindly.
#   clear_body_islands(W)   (film.key_shots calls it after bodydrops.clear_body_drops)
import os, json, hashlib
import numpy as np
import lenscull as LC

MATTE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', 'matte')

JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bodyfx.json')
TOL = 1e-3                    # m: the element's centre now vs at the check
DMIN = 0.375                  # s: the melt runs over at least 3 drawings (on threes)
SPREAD = 0.5                  # s: a spot's rim dissolves up to this much after its centre
R0, R1 = 0.3, 0.75            # dp units: full melt within R0 of the polygons hit, none past R1 (the lace noise's features ~0.6)


def _block_at(dr, f):
    cur = None
    for fa, i in dr:
        if fa <= f: cur = i
        else: break
    return cur


def _t_at(o, f):
    import stage as ST
    for fc in ST.fcurves(o):
        if fc.data_path == '["t"]': return float(fc.evaluate(f))
    return None


def _blocks(o, nv, m):
    key = o.data.shape_keys
    blocks = [None] if key is None or len(key.key_blocks) < 2 else list(range(len(key.key_blocks)))
    data = {}
    for i in blocks:
        V = np.empty(nv * 3, np.float32)
        (o.data.vertices if i is None else key.key_blocks[i].data).foreach_get('co', V)
        data[i] = V.reshape(nv // m, m, 3) if m else V.reshape(nv, 3)
    return data


def _ref_ok(o, data, dr, e, ref, log):
    f = int(ref[0]); i = _block_at(dr, f)
    if i not in data or e >= len(data[i]): log('BODYFX STALE %s[%d]: frame %d not drawn' % (o.name, e, f)); return False
    c = data[i][e].astype(np.float64).mean(0)
    if float(np.abs(c - np.array(ref[1:4])).max()) > TOL:
        log('BODYFX STALE %s[%d]: centre at f%d %s, the check saw %s' % (o.name, e, f, np.round(c, 3).tolist(), ref[1:4])); return False
    return True


def _cut(spec, log):
    import bpy
    tot_e = tot_b = stale = objs = 0
    for name, d in sorted(spec.items()):
        o = bpy.data.objects.get(name)
        if o is None: log('BODYFX STALE %s: no such object' % name); stale += len(d['el']); continue
        m = int(d['m']); nv = len(o.data.vertices); n = nv // m if m else 0
        if not m or nv % m or n != int(d['n']):
            log('BODYFX STALE %s: %d vertices, the check had %d x %d' % (name, nv, d['n'], m)); stale += len(d['el']); continue
        dr = LC._drawings(o, nv); data = _blocks(o, nv, m); key = o.data.shape_keys
        cut = {}
        for es, rec in d['el'].items():
            e = int(es)
            if not _ref_ok(o, data, dr, e, rec['ref'], log): stale += 1; continue
            for g in rec['frames']:
                b = _block_at(dr, int(g))
                if b in data: cut.setdefault(b, set()).add(e)
            tot_e += 1
        if not cut: continue
        for i, es in cut.items():
            V = data[i]; ix = np.array(sorted(es), int)
            V[ix] = V[ix].mean(1, keepdims=True)
            src = o.data.vertices if i is None else key.key_blocks[i].data
            src.foreach_set('co', V.ravel())
            if i == 0: o.data.vertices.foreach_set('co', V.ravel())
            tot_b += len(ix)
        o.data.update()
        objs += 1
    return tot_e, tot_b, objs, stale


def _get(me, name, nv, vec=False):
    a = me.attributes.get(name)
    if a is None or a.domain != 'POINT': return None
    A = np.empty(nv * (3 if vec else 1), np.float32)
    a.data.foreach_get('vector' if vec else 'value', A)
    return A.reshape(nv, 3) if vec else A


def _melt(spec, log):
    import bpy
    tot_s = tot_v = stale = objs = 0
    for name, d in sorted(spec.items()):
        o = bpy.data.objects.get(name)
        if o is None: log('BODYFX STALE %s: no such object' % name); stale += len(d['spots']); continue
        me = o.data; nv = len(me.vertices); m = int(d.get('m') or 0)
        if nv != int(d['nv']) or (m and nv % m):
            log('BODYFX STALE %s: %d vertices, the check had %d' % (name, nv, d['nv'])); stale += len(d['spots']); continue
        D0 = _get(me, 'd0', nv); D1 = _get(me, 'd1', nv); DP = _get(me, 'dp', nv, True)
        if D0 is None or D1 is None or DP is None:
            log('BODYFX STALE %s: no d0/d1/dp attributes' % name); stale += len(d['spots']); continue
        dr = LC._drawings(o, nv) if m else None
        data = _blocks(o, nv, m) if m else None
        tube = name.endswith('_jets')
        changed = np.zeros(nv, bool)
        for s in d['spots']:
            tk = _t_at(o, int(s['f']))
            if tk is None: log('BODYFX STALE %s: no t curve' % name); stale += 1; continue
            e = int(s['e'])
            if e >= 0 and m and s.get('ref') and not _ref_ok(o, data, dr, e, s['ref'], log): stale += 1; continue
            cand = np.arange(e * m, (e + 1) * m) if (e >= 0 and m) else np.arange(nv)
            if s['whole']:
                ix = cand; w = np.ones(len(ix))
            elif s.get('rings') and tube and e >= 0 and m:
                # a jet tube (fx._jet_tubes): per jet nring rings of 'sides' vertices + tip + tail; the rings the hit polygons
                # touch +-1 go whole (all round: the tube is a closed mass), +-2 at half weight
                if any(int(p) >= len(me.polygons) for p in s['polys']):
                    log('BODYFX STALE %s: polygon out of range' % name); stale += 1; continue
                f0 = me.polygons[0].vertices
                sides = int(f0[2]) - 1 if len(f0) == 3 else 0
                nring = (m - 2) // sides if sides > 0 else 0
                if sides < 3 or nring < 2 or nring * sides + 2 != m:
                    log('BODYFX STALE %s: not a jet tube layout (m %d, sides %d)' % (name, m, sides)); stale += 1; continue
                rs = set()
                for p in s['polys']:
                    for v in me.polygons[int(p)].vertices:
                        lv = int(v) - e * m
                        if not 0 <= lv < m: continue
                        rs.add(lv // sides if lv < nring * sides else (0 if lv == nring * sides else nring - 1))
                if not rs: log('BODYFX STALE %s[%d]: hit polygons not on that jet' % (name, e)); stale += 1; continue
                lo, hi = min(rs), max(rs)
                wr = np.zeros(nring)
                for i in range(nring):
                    if lo - 1 <= i <= hi + 1: wr[i] = 1.0
                    elif lo - 2 <= i <= hi + 2: wr[i] = 0.5
                wl = np.concatenate([np.repeat(wr, sides), [wr[0], wr[nring - 1]]])
                ix = cand[wl > 0]; w = wl[wl > 0]
            else:
                if any(int(p) >= len(me.polygons) for p in s['polys']):
                    log('BODYFX STALE %s: polygon out of range' % name); stale += 1; continue
                seeds = sorted({int(v) for p in s['polys'] for v in me.polygons[int(p)].vertices})
                if tube: dist = np.abs(DP[cand, 2][:, None] - DP[seeds, 2][None, :]).min(1)
                else: dist = np.linalg.norm(DP[cand][:, None, :] - DP[seeds][None, :, :], axis=2).min(1)
                w = np.clip((R1 - dist) / (R1 - R0), 0.0, 1.0)
                ix = cand[w > 0]; w = w[w > 0]
            if not len(ix): continue
            tkill = tk - 1e-3 + (1.0 - w) * SPREAD
            D1[ix] = np.minimum(D1[ix], tkill)
            D0[ix] = np.minimum(D0[ix], D1[ix] - DMIN)
            changed[ix] = True; tot_s += 1
        if not changed.any(): continue
        me.attributes['d0'].data.foreach_set('value', D0); me.attributes['d1'].data.foreach_set('value', D1)
        me.update()
        tot_v += int(changed.sum()); objs += 1
    return tot_s, tot_v, objs, stale


def _erase(spec, log):
    """sheets: fx water material erasers (fx._erase): object props er<i>c (dp centre), er<i>r (dp radius), er<i>t (the
    object's own t at the kill frame)."""
    import bpy
    try:
        import fx
        K = int(getattr(fx, 'ERASERS', 0))
    except Exception: K = 0
    tot = stale = objs = 0
    for name, ers in sorted(spec.items()):
        o = bpy.data.objects.get(name)
        if o is None: log('BODYFX STALE %s: no such object' % name); stale += len(ers); continue
        if not K: log('BODYFX STALE %s: the water material has no erasers' % name); stale += len(ers); continue
        if o.data is None or o.data.attributes.get('dp') is None:
            log('BODYFX STALE %s: no dp attribute' % name); stale += len(ers); continue
        n = 0
        for x in ers[:K]:
            tk = _t_at(o, int(x['f']))
            if tk is None: log('BODYFX STALE %s: no t curve' % name); stale += 1; continue
            o['er%dc' % n] = tuple(float(v) for v in x['c']); o['er%dr' % n] = float(x['r']); o['er%dt' % n] = float(tk) - 1e-3
            n += 1
        if len(ers) > K: log('BODYFX %s: %d erasers, the material has %d' % (name, len(ers), K)); stale += len(ers) - K
        tot += n; objs += 1 if n else 0
    return tot, objs, stale


def behind_hash(bh):
    return hashlib.sha1(json.dumps(bh, sort_keys=True).encode('utf-8')).hexdigest()[:16]


def behind_frames(bh):
    fs = set()
    for d in bh.values():
        for rec in d['el'].values(): fs.update(range(int(rec['win'][0]), int(rec['win'][1]) + 1))
    return sorted(fs)


def _behind(spec, log, sc):
    """vertex attrs bh0/bh1 = the element's window (frames, +-0.5) on every vertex of the element; the scene uniform bh_fr =
    the frame (keyed on every frame round the windows, CONSTANT); the matte list checked against this one."""
    import bpy
    tot = stale = objs = 0
    for name, d in sorted(spec.items()):
        o = bpy.data.objects.get(name)
        if o is None: log('BODYFX STALE %s: no such object' % name); stale += len(d['el']); continue
        me = o.data; nv = len(me.vertices); m = int(d['m'])
        if not m or nv % m or nv // m != int(d['n']):
            log('BODYFX STALE %s: %d vertices, the check had %d x %d' % (name, nv, d['n'], m)); stale += len(d['el']); continue
        mats = sorted({s.material.name for s in o.material_slots if s.material})
        if not mats or any(not hasattr(bpy.data.materials[x].node_tree, 'nodes') or
                           not any(n.bl_idname == 'ShaderNodeAttribute' and n.attribute_name == 'bh0' for n in bpy.data.materials[x].node_tree.nodes) for x in mats):
            log('BODYFX STALE %s: material %s has no behind window' % (name, mats)); stale += len(d['el']); continue
        dr = LC._drawings(o, nv); data = _blocks(o, nv, m)
        B0 = _get(me, 'bh0', nv); B1 = _get(me, 'bh1', nv)
        if B0 is None: B0 = np.zeros(nv, np.float32)
        if B1 is None: B1 = np.zeros(nv, np.float32)
        n = 0
        for es, rec in sorted(d['el'].items(), key=lambda kv: int(kv[0])):
            e = int(es)
            if e >= nv // m: log('BODYFX STALE %s[%d]: no such element' % (name, e)); stale += 1; continue
            if rec.get('ref') and not _ref_ok(o, data, dr, e, rec['ref'], log): stale += 1; continue
            B0[e * m:(e + 1) * m] = float(rec['win'][0]) - 0.5; B1[e * m:(e + 1) * m] = float(rec['win'][1]) + 0.5; n += 1
        if not n: continue
        for k, arr in (('bh0', B0), ('bh1', B1)):
            a = me.attributes.get(k) or me.attributes.new(k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', arr)
        me.update()
        tot += n; objs += 1
    fs = behind_frames(spec)
    if fs:
        import stage as ST
        for f in range(fs[0] - 2, fs[-1] + 3):
            sc['bh_fr'] = float(f); sc.keyframe_insert('["bh_fr"]', frame=f)
        for fc in ST.fcurves(sc):
            if fc.data_path == '["bh_fr"]':
                for k in fc.keyframe_points: k.interpolation = 'CONSTANT'
        mj = os.path.join(MATTE_DIR, 'spec.json')
        have = json.load(open(mj)) if os.path.exists(mj) else {}
        if have.get('mode') == 'fx-clear':
            miss = sorted(set(fs) - set(have.get('list', [])))
            if miss:
                log('BODYFX STALE MATTE: %d window frames have no matte (%d..%d) - render the mattes for them' % (len(miss), miss[0], miss[-1]))
                stale += 1
            else: log('BODYFX behind mattes cover the windows (fx-clear, list %s, frames %d-%d)' % (behind_hash(spec), fs[0], fs[-1]))
        elif have.get('hash') != behind_hash(spec):
            log('BODYFX STALE MATTE: out/matte was rendered for list %s, this list is %s - render the mattes again'
                % (have.get('hash'), behind_hash(spec))); stale += 1
        else: log('BODYFX behind mattes match the list (%s, frames %d-%d)' % (have.get('hash'), fs[0], fs[-1]))
    return tot, objs, stale


def clear_body_islands(W, log=print):
    if not os.path.exists(JS): log('BODYFX no list (%s)' % JS); return 0
    spec = json.load(open(JS, encoding='utf-8'))
    ce, cb, co, cs = _cut(spec.get('cut', {}), log)
    ms, mv, mo, mst = _melt(spec.get('melt', {}), log)
    es, eo, est = _erase(spec.get('erase', {}), log)
    bs, bo, bst = _behind(spec.get('behind', {}), log, W['sc'])
    log('BODYFX total: cut %d drops in %d objects (%d element-drawings); melt %d spots in %d objects (%d vertices); '
        'erase %d spots in %d objects; behind %d elements in %d objects; %d stale' % (ce, co, cb, ms, mo, mv, es, eo, bs, bo, cs + mst + est + bst))
    return ce + ms + es + bs
