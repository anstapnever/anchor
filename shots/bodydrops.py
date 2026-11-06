# ANCHOR - drops drawn over the mech's body (06.11). A drawn drop (white teardrop, ink outline) in front of the mech a few
# metres off its armour reads as a thorn or a stud growing out of it, not as water: s32 f1609-1613 had four white cones on the
# orange knee (the land crown's drops, slow at the top of their arc), s33 white specks on the forearm at the grab, s25 drops
# shed off the knee hung under it like fangs.
# The scan (bodyscan2.py: build + key as the final render, then camera rays through 7 points of every drop element - centre,
# head, tail, 4 sides - against the evaluated mech meshes of every frame of every MECH shot, with the water line, the FX water
# masses, the chain, the port and everything else the shot renders as occluders) lists, per element, the frames in which the
# first surface right behind it is the mech. In each drawing that shows such a frame the element is not drawn (collapsed to its
# centre in that key block): the drop passes BEHIND the body - it leaves at the silhouette and comes back on the far side, as if
# the mech stood in front of it - so it never sits on the armour and nothing vanishes in open air.
# bodydrops.json keeps, per object, the element count and per element one reference frame and screen point (recomputed here
# from the keys, no depsgraph needed: an effect changed since the scan is reported STALE instead of being cut blindly) and the
# frames over the body.
#   clear_body_drops(W)   (film.key_shots calls it after lenscull.shrink_near_drops)
import os, json
import numpy as np
import lenscull as LC

JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bodydrops.json')
TOL = 1.0                     # px: the scan's screen point vs the one recomputed here


def _block_at(dr, f):
    """the key block shown at frame f: the last drawing that starts at or before f."""
    cur = None
    for fa, i in dr:
        if fa <= f: cur = i
        else: break
    return cur


def clear_body_drops(W, log=print):
    if not os.path.exists(JS): log('BODYDROPS no list (%s)' % JS); return 0
    spec = json.load(open(JS, encoding='utf-8'))['drop']
    cams = LC._cams(W)
    import bpy
    tot_e = tot_b = stale = objs = 0
    for name, d in sorted(spec.items()):
        o = bpy.data.objects.get(name)
        if o is None: log('BODYDROPS STALE %s: no such object' % name); stale += len(d['el']); continue
        nv = len(o.data.vertices); n = nv // LC.M_TPL
        if nv % LC.M_TPL or n != int(d['n']):
            log('BODYDROPS STALE %s: %d elements, the scan had %d' % (name, n, d['n'])); stale += len(d['el']); continue
        dr = LC._drawings(o, nv); key = o.data.shape_keys
        Mw = np.array(LC._world(o)); A = Mw[:3, :3]; t = Mw[:3, 3]
        blocks = [None] if key is None or len(key.key_blocks) < 2 else list(range(len(key.key_blocks)))
        data = {}
        for i in blocks:
            V = np.empty(nv * 3, np.float32)
            (o.data.vertices if i is None else key.key_blocks[i].data).foreach_get('co', V)
            data[i] = V.reshape(n, LC.M_TPL, 3)
        cut = {}                                   # key block -> elements not drawn in it
        for es, rec in d['el'].items():
            e = int(es); f, sx, sy = rec['ref']; f = int(f)
            i = _block_at(dr, f)
            if f not in cams or i not in data: log('BODYDROPS STALE %s[%d]: frame %d not keyed' % (name, e, f)); stale += 1; continue
            c = data[i][e].astype(np.float64).mean(0) @ A.T + t
            P, R, fpx = cams[f]
            v = (c - P) @ R; dep = -v[2]
            if dep <= 0.05: log('BODYDROPS STALE %s[%d]: behind the lens at f%d' % (name, e, f)); stale += 1; continue
            qx = v[0] / dep * fpx; qy = v[1] / dep * fpx
            if abs(qx - sx) > TOL or abs(qy - sy) > TOL:
                log('BODYDROPS STALE %s[%d]: at f%d (%.1f, %.1f), the scan saw (%.1f, %.1f)' % (name, e, f, qx, qy, sx, sy))
                stale += 1; continue
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
    log('BODYDROPS total: %d elements in %d objects kept off the body (%d element-drawings), %d stale' % (tot_e, objs, tot_b, stale))
    return tot_e
