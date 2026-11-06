# ANCHOR — the chain (lead). Stud-link anchor chain: link 8.4 m long, 5.0 m wide, bar 1.4 m, a stud across the middle.
# Interlocked links sit 5.6 m apart (the inner length), each turned 90 deg about the chain axis from the one before.
#   links = build(coll, n)                      -> list of link objects (linked duplicates of one mesh), link 0 at the top (city)
#   sim = Sim(nodes0) ; sim.step(...)           -> position-based rope: inextensible, bending-limited, gravity/drag/buoyancy, colliders, pins
#   pose(links, nodes, frame, key=True)         -> places every link along the node polyline (centres = nodes) and keys it
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix, Quaternion
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'kit'))
import look as LK, env as EV

L_OUT, W_OUT, BAR = 8.4, 5.0, 1.4
PITCH = L_OUT - 2 * BAR - 0.35     # 5.25 m between interlocked link centres (0.35 m play: clean up to a 25 deg bend per joint)
END_EXT = 0.5                      # the end link (the last one, studless, the hand's grip): 2 * END_EXT longer, all of it on the
                                   # side of the link before it (its free / shackle end stays where a common link's would be)
END_EXT2 = 2.100                    # the end link from shots/grip.SWAP_T on (the chain is in no shot 61.0 .. 67.2): the long grip link the
                                   # left fist holds, its centre shots/grip.END_SHIFT2 toward its free end, so the fist (5.1 m wide) sits on
                                   # its straight side clear of link 78, which hooks the link's inner end (the chain's usual 0.35 m play).
                                   # Same topology as the END_EXT link: a shape key 'grip' on the end link, keyed 0 -> 1 at the swap by
                                   # shots/common.chain_pose (keep shots/grip.END_EXT2 equal to this).


def link_mesh(name='CHAIN_link', seg=56, ring=14, stud=True, ext=0.0):
    """Stadium torus swept by a circle of radius BAR/2, plus the stud (flared ends). Long axis X, width Y, thickness Z.
    stud=False, ext: the end link (no stud, the straight sides 2 * ext longer)."""
    r = BAR / 2; a = (L_OUT - W_OUT) / 2 + ext; R = (W_OUT - BAR) / 2
    # path: param s in [0, perimeter)
    per = 4 * a + 2 * math.pi * R
    def path(s):
        s = s % per
        if s < 2 * a: return Vector((-a + s, -R, 0)), Vector((1, 0, 0))
        s -= 2 * a
        if s < math.pi * R:
            th = -math.pi / 2 + s / R; return Vector((a + R * math.cos(th), R * math.sin(th), 0)), Vector((-math.sin(th), math.cos(th), 0))
        s -= math.pi * R
        if s < 2 * a: return Vector((a - s, R, 0)), Vector((-1, 0, 0))
        s -= 2 * a
        th = math.pi / 2 + s / R; return Vector((-a + R * math.cos(th), R * math.sin(th), 0)), Vector((-math.sin(th), math.cos(th), 0))
    bm = bmesh.new(); rows = []
    for i in range(seg):
        # distribute more samples on the curved ends
        s = per * i / seg
        p, t = path(s); nrm = Vector((0, 0, 1)).cross(t).normalized()   # in-plane normal (pointing in/out)
        row = []
        for j in range(ring):
            ang = 2 * math.pi * j / ring
            q = p + (nrm * math.cos(ang) + Vector((0, 0, 1)) * math.sin(ang)) * r
            row.append(bm.verts.new(q))
        rows.append(row)
    for i in range(seg):
        for j in range(ring):
            a0 = rows[i][j]; a1 = rows[i][(j + 1) % ring]; b0 = rows[(i + 1) % seg][j]; b1 = rows[(i + 1) % seg][(j + 1) % ring]
            bm.faces.new((a0, b0, b1, a1))
    if not stud:
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.shade_smooth(); return me
    # the stud: a bar across the middle (along Y), slightly waisted, ends flared into the inner faces of the sides
    inner = R - r
    sr = 0.42; nseg = 16; zs = []
    prof = [(-inner - 0.25, sr * 1.55), (-inner * 0.7, sr * 1.15), (-inner * 0.2, sr), (inner * 0.2, sr), (inner * 0.7, sr * 1.15), (inner + 0.25, sr * 1.55)]
    srows = []
    for (y, rr) in prof:
        row = [bm.verts.new((rr * math.cos(2 * math.pi * k / nseg), y, rr * math.sin(2 * math.pi * k / nseg) * 0.9)) for k in range(nseg)]
        srows.append(row)
    for i in range(len(srows) - 1):
        for k in range(nseg):
            bm.faces.new((srows[i][k], srows[i][(k + 1) % nseg], srows[i + 1][(k + 1) % nseg], srows[i + 1][k]))
    bm.faces.new(list(reversed(srows[0]))); bm.faces.new(srows[-1])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.shade_smooth(); return me


def materials():
    if 'M_chain_air' in bpy.data.materials:
        return bpy.data.materials['M_chain_air'], bpy.data.materials['M_chain_sea']
    def air(nb):
        P = nb.coord('Object')
        base = nb.rgb('#4b4352')
        # forged iron: dark violet-grey, big hard-edged rust continents, orange fresh rust at their rims, pitting, polished wear
        n1 = nb.noise(nb.vmath('SCALE', P, scale=0.32), 1.0, 4.0, 0.62, 0.4, w=nb.objattr('seed'))
        rust = nb.smooth(n1, 0.5, 0.515); rim = nb.mul(nb.smooth(n1, 0.47, 0.485), nb.sub(1.0, rust))
        col = nb.mixc(base, nb.rgb('#8a4a2c'), rust)
        col = nb.mixc(col, nb.rgb('#c2672f'), nb.mul(rim, 0.85))
        pit = nb.voronoi(nb.vmath('SCALE', P, scale=2.6), 1.0, 'F1')
        col = nb.mixc(col, nb.cmul(col, '#6d6280'), nb.mul(nb.smooth(pit, 0.09, 0.05), 0.8))
        streak = nb.noise(nb.vmath('MULTIPLY', P, (0.25, 0.25, 2.2)), 1.0, 3.0, 0.6, 0.0)
        col = nb.mixc(col, nb.rgb('#7c7486'), nb.mul(nb.smooth(streak, 0.66, 0.69), nb.sub(1.0, rust)))
        return col
    def sea(nb):
        P = nb.coord('Object')
        base = nb.rgb('#4a3f3a')
        n1 = nb.noise(nb.vmath('SCALE', P, scale=0.3), 1.0, 4.0, 0.62, 0.4, w=nb.objattr('seed'))
        col = nb.mixc(base, nb.rgb('#7d4a2e'), nb.smooth(n1, 0.45, 0.47))
        alg = nb.noise(nb.vmath('SCALE', P, scale=0.55), 1.0, 3.0, 0.6, 0.2, w=nb.add(nb.objattr('seed'), 3.0))
        col = nb.mixc(col, nb.rgb('#56703c'), nb.smooth(alg, 0.5, 0.52))
        col = nb.mixc(col, nb.rgb('#3c5233'), nb.smooth(alg, 0.62, 0.635))
        # barnacle crust: clusters of pale cones (voronoi cells) in patches
        cells = nb.voronoi(nb.vmath('SCALE', P, scale=3.4), 1.0, 'F1')
        patch = nb.smooth(nb.noise(nb.vmath('SCALE', P, scale=0.45), 1.0, 2.0, 0.5, 0.0, w=nb.add(nb.objattr('seed'), 7.0)), 0.48, 0.5)
        crust = nb.mul(nb.smooth(cells, 0.3, 0.22), patch)
        col = nb.mixc(col, nb.rgb('#ddd5bf'), crust)
        col = nb.mixc(col, nb.rgb('#8f8778'), nb.mul(nb.smooth(cells, 0.12, 0.06), patch))
        return col
    air_m = LK.cel('M_chain_air', air, spec=0.55, rim=0.45, vary=0.06, vscale=0.4, wscale=0.9)
    sea_m = LK.cel('M_chain_sea', sea, spec=0.3, rim=0.35, vary=0.06, vscale=0.4, wscale=0.9)
    # heat glow (the discharge, the red-hot shackle end): patch the emission colour of both through the objattr
    for m in (air_m, sea_m):
        nt = m.node_tree; em = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeEmission'][0]
        src = em.inputs['Color'].links[0].from_socket
        nb = LK.NB.__new__(LK.NB); nb.m = m; nb.nt = nt; nb.N = nt.nodes; nb.L = nt.links; nb._geo = None; nb._tc = None; nb._attrs = {}
        h = nb.objattr('heat')
        hot = nb.ramp(h, [(0.0, '#7a2414'), (0.35, '#e0441e'), (0.7, '#ff9f34'), (1.0, '#fff6d0')], 'LINEAR')
        k = nb.smooth(h, 0.02, 0.3)
        out = nb.mixc(src, nb.cscale(hot, 1.6), k)
        nt.links.new(out, em.inputs['Color'])
        aov = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputAOV' and n.aov_name == 'glow'][0]
        nt.links.new(nb.mul(k, 0.9), aov.inputs['Value'])
    return air_m, sea_m


def build(coll, n=76, n_sea=12):
    """n links; the last n_sea (bottom, by the anchor) wear the sea crust."""
    me = link_mesh(); air_m, sea_m = materials()
    me_sea = me.copy(); me_sea.name = 'CHAIN_link_sea'
    me.materials.append(air_m); me_sea.materials.append(sea_m)
    me_end = link_mesh('CHAIN_link_end', 64, 14, stud=False, ext=END_EXT); me_end.materials.append(sea_m if n_sea > 0 else air_m)
    links = []
    for i in range(n):
        o = bpy.data.objects.new('CHAIN_%03d' % i, me_end if i == n - 1 else (me_sea if i >= n - n_sea else me))
        coll.objects.link(o); o['heat'] = 0.0; o['seed'] = (i * 7.31) % 50.0; o.rotation_mode = 'QUATERNION'
        links.append(o)
    _grip_key(links[-1])
    return links


def _grip_key(o):
    """shape key 'grip' on the end link: the END_EXT2 link (same vertex order as the END_EXT one)."""
    me = o.data
    if me.shape_keys is not None and 'grip' in me.shape_keys.key_blocks: return
    m2 = link_mesh('CHAIN_link_end_grip', 64, 14, stud=False, ext=END_EXT2)
    assert len(m2.vertices) == len(me.vertices)
    if me.shape_keys is None: o.shape_key_add(name='Basis', from_mix=False)
    k = o.shape_key_add(name='grip', from_mix=False)
    for i, v in enumerate(m2.vertices): k.data[i].co = v.co
    k.value = 0.0
    bpy.data.meshes.remove(m2)


# ------------------------------------------------------------------------------------------------------------------------------- placement
def frames_along(joints, roll0=0.0, up_hint=(0.0, 0.0, 1.0), twist=None):
    """Links sit on the SEGMENTS between joint nodes (the interlock points): centre = midpoint, X = segment direction,
    Y = transported normal turned 90 deg every other link (+ twist[i] rad when given). Returns (centres, quaternions)."""
    J = np.asarray(joints, float); n = len(J) - 1
    T = J[1:] - J[:-1]; T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    C = (J[1:] + J[:-1]) * 0.5
    up = np.array(up_hint, float)
    nrm = np.cross(T[0], up)
    if np.linalg.norm(nrm) < 1e-3: nrm = np.cross(T[0], np.array((1.0, 0, 0)))
    nrm /= np.linalg.norm(nrm)
    out = []
    for i in range(n):
        if i > 0:
            nrm = nrm - T[i] * np.dot(nrm, T[i]); ln = np.linalg.norm(nrm)
            if ln < 1e-6: nrm = np.cross(T[i], up); ln = np.linalg.norm(nrm)
            nrm /= ln
        ang = roll0 + (math.pi / 2 if i % 2 else 0.0) + (0.0 if twist is None else float(twist[i]))
        b = np.cross(T[i], nrm)
        w = nrm * math.cos(ang) + b * math.sin(ang)
        z = np.cross(T[i], w)
        M = Matrix(((T[i][0], w[0], z[0]), (T[i][1], w[1], z[1]), (T[i][2], w[2], z[2])))
        out.append(M.to_quaternion())
    return C, out


def pose(links, joints, frame=None, roll0=0.0, key=True):
    """joints: len(links)+1 points spaced PITCH apart (joint 0 = the top, at the city)."""
    C, qs = frames_along(joints, roll0)
    for o, p, q in zip(links, C, qs):
        o.location = Vector(p); o.rotation_quaternion = q
        if key and frame is not None:
            o.keyframe_insert('location', frame=frame); o.keyframe_insert('rotation_quaternion', frame=frame)


# ------------------------------------------------------------------------------------------------------------------------------- shapes
def catenary(p0, p1, length, n):
    """n nodes from p0 to p1 hanging under gravity with the given total length (solved by relaxation)."""
    p0 = np.array(p0, float); p1 = np.array(p1, float)
    P = np.linspace(p0, p1, n)
    seg = length / (n - 1)
    # start sagged, then relax with the PBD solver (gravity only, ends pinned)
    s = Sim(P, seg); s.pins = {0: p0, n - 1: p1}
    for _ in range(600): s.step(1 / 24, substeps=4, g=9.8, drag_air=2.0, drag_water=2.0)
    return s.P.copy()


class Sim:
    """Position-based chain: inextensible segments, a bend limit between consecutive segments, gravity, air/water drag, buoyancy,
    a seabed height function, sphere/capsule colliders, pins (index -> position, may be animated by the caller every frame)."""
    def __init__(s, P, seg=PITCH):
        s.P = np.array(P, float); s.prev = s.P.copy(); s.seg = seg; s.pins = {}; s.colliders = []; s.bed = None
        s.max_bend = math.radians(21.0); s.wind = np.zeros(3)

    def step(s, dt, substeps=8, g=9.8, drag_air=0.05, drag_water=1.6, buoy=0.13, iters=12, water_z=0.0):
        h = dt / substeps
        for _ in range(substeps):
            V = (s.P - s.prev)
            wet = s.P[:, 2] < water_z
            damp = np.where(wet, math.exp(-drag_water * h), math.exp(-drag_air * h))[:, None]
            acc = np.zeros_like(s.P); acc[:, 2] -= g * np.where(wet, 1.0 - buoy, 1.0)
            acc += s.wind[None, :] * (~wet)[:, None]
            s.prev = s.P.copy()
            s.P = s.P + V * damp + acc * h * h
            for _ in range(iters):
                s._lengths(); s._bend(); s._collide(); s._pin()
            s._lengths(); s._pin()

    def _pin(s):
        for i, p in s.pins.items():
            if p is not None: s.P[i] = p

    def _lengths(s):
        P = s.P; n = len(P)
        w = np.ones(n);
        for i in s.pins: w[i] = 0.0
        for par in (0, 1):
            i = np.arange(par, n - 1, 2)
            d = P[i + 1] - P[i]; ln = np.linalg.norm(d, axis=1, keepdims=True); ln = np.maximum(ln, 1e-9)
            corr = (ln - s.seg) / ln * d
            wi = w[i][:, None]; wj = w[i + 1][:, None]; ws = np.maximum(wi + wj, 1e-9)
            P[i] += corr * wi / ws; P[i + 1] -= corr * wj / ws

    def _bend(s):
        P = s.P; n = len(P)
        if n < 3: return
        a = P[1:-1] - P[:-2]; b = P[2:] - P[1:-1]
        na = np.linalg.norm(a, axis=1); nb_ = np.linalg.norm(b, axis=1)
        cosang = np.sum(a * b, axis=1) / np.maximum(na * nb_, 1e-9)
        lim = math.cos(s.max_bend)
        bad = np.where(cosang < lim)[0]
        for k in bad:   # straighten: move the middle node toward the midpoint of its neighbours
            i = k + 1
            if i in s.pins: continue
            mid = (P[i - 1] + P[i + 1]) * 0.5
            P[i] += (mid - P[i]) * 0.35

    def _collide(s):
        P = s.P
        if s.bed is not None:
            z = s.bed(P[:, 0], P[:, 1]) + BAR * 0.5
            m = P[:, 2] < z; P[m, 2] = z[m]
        for c in s.colliders:
            kind = c[0]
            if kind == 'sphere':
                _, ctr, rad = c; d = P - np.asarray(ctr); ln = np.linalg.norm(d, axis=1); m = ln < rad
                if m.any(): P[m] = np.asarray(ctr) + d[m] / np.maximum(ln[m, None], 1e-9) * rad
            elif kind == 'vcyl':   # vertical cylinder (x, y, r, z0, z1)
                _, cx, cy, rad, z0, z1 = c
                d = P[:, :2] - np.array((cx, cy)); ln = np.linalg.norm(d, axis=1)
                m = (ln < rad) & (P[:, 2] > z0) & (P[:, 2] < z1)
                if m.any(): P[m, :2] = np.array((cx, cy)) + d[m] / np.maximum(ln[m, None], 1e-9) * rad


def bend_report(nodes):
    P = np.asarray(nodes); a = P[1:-1] - P[:-2]; b = P[2:] - P[1:-1]
    c = np.sum(a * b, axis=1) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-9)
    return math.degrees(math.acos(max(-1.0, min(1.0, float(c.min())))))
