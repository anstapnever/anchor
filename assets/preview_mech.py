# MECH preview: unit 07 in the shared environment, one frame per view.
#   blender -b -P assets/preview_mech.py -- 50 16            all views -> out/preview/mech/
#   blender -b -P assets/preview_mech.py -- 50 16 v=3,5      only those views -> out/preview/mech_sub/
#   blender -b -P assets/preview_mech.py -- 50 16 qa         build + QA per pose only (no render)
# Stage: the standing mech on a concrete pad at the origin; dry dock 3 as a 100 x 200 m box with 18 m walls (floor z -14, north wall face
# y 600) with the sleeping mech placed as the lead places it: root (-460, 600 - SLEEP_WALL, -14), facing -Y. The sea is hidden in dock frames.
import bpy, sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'kit')); sys.path.insert(0, HERE)
from mathutils import Vector, Matrix
import look as LK, env as EV, preview as PV, qa as QA
import mech

A = PV.args()
sc, W = PV.setup(preset='morning', sun=(95, 16))
t0 = time.time()
M = mech.build(W)
print('BUILD_S %.2f  TRIS %d' % (time.time() - t0, M['tris']))
objs = [o for o in M['meshes'] if o.type == 'MESH']
vines = {o.name for o in M['vines']}

if 'qa' in A[2:]:
    for nm, p in mech.POSES.items():
        mech.set_pose(M, p); bpy.context.view_layer.update()
        bad = QA.overlaps(objs if nm == 'sleep' else [o for o in objs if o.name not in vines], allow=mech.qa_allow)
        print('QA', nm, len(bad), bad[:6])
    sys.exit(0)


# ---------------------------------------------------------------------------------------------------------------- set dressing
def box(name, x0, x1, y0, y1, z0, z1, mat):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(name); me.from_pydata(v, [], f); me.materials.append(mat)
    o = bpy.data.objects.new(name, me); W.objects.link(o); return o


concrete = LK.cel('M_prev_concrete', '#b8b0a2', vary=0.12, vscale=0.05, grime=0.6, scuff=0.3, wscale=0.08, algae=0.3)
wallm = LK.cel('M_prev_dockwall', '#a59c8c', vary=0.14, vscale=0.06, grime=0.7, algae=0.5, waterline=0.4, wscale=0.08)
steel = LK.cel('M_prev_chain', '#6e4f3c', spec=0.6, rim=0.55, vary=0.1, vscale=0.5, grime=0.5, scuff=0.7, rust=0.9, wscale=0.6)
pad = box('PREV_pad', -70, 70, -70, 70, -3.0, 1.5, concrete)
DX, DY, FL = -460.0, 600.0, -14.0            # dock: north wall face y = 600, floor z = -14, walls 18 m (top z = +4)
dock = [box('PREV_dock_floor', DX - 50, DX + 50, DY - 200, DY, FL - 2, FL, concrete),
        box('PREV_dock_wallN', DX - 54, DX + 54, DY, DY + 4, FL - 2, FL + 18, wallm),
        box('PREV_dock_wallW', DX - 54, DX - 50, DY - 200, DY, FL - 2, FL + 18, wallm),
        box('PREV_dock_wallE', DX + 50, DX + 54, DY - 200, DY, FL - 2, FL + 18, wallm),
        box('PREV_dock_wallS', DX - 54, DX + 54, DY - 204, DY - 200, FL - 2, FL + 18, wallm),
        box('PREV_quayN', DX - 160, DX + 160, DY + 4, DY + 120, FL - 2, FL + 18, concrete),
        box('PREV_quayW', DX - 160, DX - 54, DY - 320, DY + 4, FL - 2, FL + 18, concrete),
        box('PREV_quayE', DX + 54, DX + 160, DY - 320, DY + 4, FL - 2, FL + 18, concrete),
        box('PREV_quayS', DX - 54, DX + 54, DY - 320, DY - 204, FL - 2, FL + 18, concrete)]


def link_obj(name, L=8.4, Wd=5.0, d=1.4, nu=72, nv=16):
    r = d / 2; R = (Wd - d) / 2; S = (L - Wd) / 2; per = 4 * S + 2 * math.pi * R; V = []; F = []
    for i in range(nu):
        s = per * i / nu
        if s < 2 * S: p = Vector((-S + s, R, 0)); t = Vector((1, 0, 0))
        elif s < 2 * S + math.pi * R: a = (s - 2 * S) / R; p = Vector((S + R * math.sin(a), R * math.cos(a), 0)); t = Vector((math.cos(a), -math.sin(a), 0))
        elif s < 4 * S + math.pi * R: q = s - 2 * S - math.pi * R; p = Vector((S - q, -R, 0)); t = Vector((-1, 0, 0))
        else: a = (s - 4 * S - math.pi * R) / R; p = Vector((-S - R * math.sin(a), -R * math.cos(a), 0)); t = Vector((-math.cos(a), math.sin(a), 0))
        n = Vector((0, 0, 1)).cross(t).normalized()
        for j in range(nv):
            b = 2 * math.pi * j / nv; V.append(tuple(p + n * (r * math.cos(b)) + Vector((0, 0, r * math.sin(b)))))
    for i in range(nu):
        for j in range(nv):
            i2 = (i + 1) % nu; j2 = (j + 1) % nv; F.append((i * nv + j, i2 * nv + j, i2 * nv + j2, i * nv + j2))
    me = bpy.data.meshes.new(name); me.from_pydata(V, [], F); me.materials.append(steel); me.shade_smooth()
    o = bpy.data.objects.new(name, me); W.objects.link(o); return o, R


NCH = 18
chain = [link_obj('PREV_link%02d' % i)[0] for i in range(NCH)]; LR = (5.0 - 1.4) / 2; PITCH = 8.4 - 2 * 1.4


def link_m(c, X, P):
    """A link centred at c, its long axis X, its plane spanned by X and P."""
    X = X.normalized(); P = (P - X * P.dot(X)).normalized()
    Ml = Matrix.Identity(4); Ml.col[0][:3] = X; Ml.col[1][:3] = P; Ml.col[2][:3] = X.cross(P); Ml.translation = c; return Ml


def grip_link(side):
    """The link's long bar in the hand: bar centre at palm (0, GRIP_Y, GRIP_Z), bar along palm X, link plane = palm X/Z (away from the palm).
    Returns (link centre, palm X, palm Z)."""
    Pw = mech._wm(M['parts']['palm' + side]); R3 = Pw.to_3x3(); X = R3.col[0]; Z = R3.col[2]
    c = Pw @ Vector((0, mech.GRIP_Y, mech.GRIP_Z))
    return c + Z * LR, X, Z


def chain_through_hands():
    """Link matrices: the gripped links in both hands, an even number of links between them, 5 more past the L (high) hand toward the
    load, 4 past the R (low) hand; the planes alternate, the gripped planes are matched (the even links turn between them)."""
    cR, XR, ZR = grip_link('R'); cL, XL, ZL = grip_link('L')
    a = (cL - cR); d = a.length; a.normalize(); n = max(2, 2 * round(d / (2 * PITCH))); step = d / n
    def plane_at(k):      # interpolate the gripped plane normal about the chain axis
        z0 = (ZR - a * ZR.dot(a)).normalized(); z1 = (ZL - a * ZL.dot(a)).normalized()
        ang = math.atan2(a.dot(z0.cross(z1)), z0.dot(z1)); u = min(max(k / n, 0.0), 1.0)
        z = Matrix.Rotation(ang * u, 3, a) @ z0
        return z if k % 2 == 0 else a.cross(z)
    out = []
    for k in range(-4, n + 6):
        if k == 0: out.append(link_m(cR, XR, ZR))             # the gripped links keep the exact grip frame
        elif k == n: out.append(link_m(cL, XL, ZL))
        else: out.append(link_m(cR + a * (step * k), a, plane_at(k)))
    return out[:NCH]


# ---------------------------------------------------------------------------------------------------------------- views
STAND = (0.0, 0.0, 1.5, 0.0)
SLEEP = (DX, DY - mech.SLEEP_WALL, FL, 0.0)
# (name, pose, root, props(eyes, beacon, lamps), vines?, dock?, link?, camera (pos, target, lens) or a callable -> it)
VIEWS = [
    ('front 3/4 standing', 'stand', STAND, (1.0, 1.0, 1.0), False, False, False, ((80, -127, 30), (0, 0, 47), 28)),
    ('back 3/4 standing', 'stand', STAND, (1.0, 1.0, 1.0), False, False, False, ((-88, 122, 40), (0, 2, 47), 28)),
    ('head macro, nest (shot 05)', 'sleep', SLEEP, (0.0, 0.0, 0.0), True, True, False, 'macro'),
    ('sleeping in dock 3', 'sleep', SLEEP, (0.0, 0.0, 0.0), True, True, False, ((DX + 40, DY - 105, 30), (DX - 2, DY - 22, 2), 26)),
    ('hand gripping a chain link', 'pull', STAND, (1.0, 1.0, 1.0), False, False, 'grip', 'hand'),
    ('hero low angle', 'stand', STAND, (1.0, 1.0, 1.0), False, False, False, ((40, -70, 3.0), (0, -2, 40), 18)),
    ('crouch', 'crouch', STAND, (1.0, 1.0, 1.0), False, False, False, ((70, -100, 25), (0, -8, 38), 28)),
    ('reach', 'reach', STAND, (1.0, 1.0, 1.0), False, False, False, ((92, -135, 32), (-4, -6, 49), 28)),
    ('pull', 'pull', STAND, (1.0, 1.0, 1.0), False, False, 'chain', ((-62, -128, 22), (-4, -8, 40), 28)),
]
sel = None
for a in A[2:]:
    if a.startswith('v='): sel = [int(x) for x in a[2:].split(',')]
views = [v for i, v in enumerate(VIEWS) if sel is None or i + 1 in sel]
sea = bpy.data.objects.get('SEA')
growth = [o for o in M['meshes'] if o.name in vines]
cams = []
for f, (nm, pose, root, props, show_vines, in_dock, show_link, cam) in enumerate(views, start=1):
    p = dict(mech.POSES[pose]); p['root'] = root
    mech.set_pose(M, p); mech.set_props(M, *props); mech.key_pose(M, f)
    for k in ('eyes', 'beacon', 'lamps'):
        for o in M['props'][k]: o.keyframe_insert('["%s"]' % k, frame=f)
    for o in growth: o.hide_render = not show_vines; o.keyframe_insert('hide_render', frame=f)
    if sea: sea.hide_render = in_dock; sea.keyframe_insert('hide_render', frame=f)
    pad.hide_render = in_dock; pad.keyframe_insert('hide_render', frame=f)
    mats = []
    if show_link == 'grip': c0, X0, Z0 = grip_link('R'); mats = [link_m(c0, X0, Z0)]
    elif show_link == 'chain': mats = chain_through_hands()
    for i, o in enumerate(chain):
        o.hide_render = i >= len(mats)
        if i < len(mats): o.matrix_world = mats[i]
        o.keyframe_insert('hide_render', frame=f); o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
    if show_link == 'chain':    # report links that cut into the mech (a preview prop: they are not part of the mech QA)
        bpy.context.view_layer.update()
        hits = QA.overlaps([o for o in objs if o.name not in vines] + [o for o in chain if not o.hide_render], allow=mech.qa_allow)
        print('CHAIN overlaps', sorted({(h[0], h[1]) for h in hits if 'PREV_link' in h[0] + h[1]})[:16])
    if cam == 'macro':      # the lead's shot-05 setup: in front of the face, off to its right side, a little above the nest
        h = mech._wm(M['joints']['head']); c = (h @ M['nest'].matrix_basis).translation
        fw = h.to_3x3() @ Vector((0, -1, 0)); fw.z = 0.0; fw.normalize(); side = fw.cross(Vector((0, 0, 1)))
        tgt = c + Vector((0, 0, -1.6)) + fw * 1.5
        cam = (tuple(tgt + fw * 21.0 + side * 8.0 + Vector((0, 0, 9.0))), tuple(tgt), 50)
    elif cam == 'hand':     # from the fingertip side: the link face-on through the fist (first unblocked candidate)
        bpy.context.view_layer.update()
        Pw = mech._wm(M['parts']['palmR']); R3 = Pw.to_3x3(); c = Pw @ Vector((0, mech.GRIP_Y, mech.GRIP_Z))
        T, _ = mech._bvh_of([o for o in objs if o.name not in vines])
        cam = None
        for d in ((-0.35, 0.8, 0.5), (-0.5, 0.6, -0.6), (0.35, 0.8, 0.5), (-0.8, 0.2, 0.55)):
            d = (R3 @ Vector(d)).normalized()
            if T.ray_cast(c + d * 6.0, d, 14.0)[0] is None:
                cam = (tuple(c + d * 18.0), tuple(c + R3 @ Vector((0, 0, 1.2))), 35); print('HAND CAM dir', tuple(round(x, 2) for x in d)); break
        if cam is None: cam = (tuple(c + Vector((-12.0, -17.0, 6.0))), tuple(c), 32)
    cams.append(cam)
for o in [M['root']] + list(M['joints'].values()):
    if o.animation_data and o.animation_data.action:
        import stage as ST; ST.set_interp(o, 'CONSTANT')
name = 'mech' if sel is None else 'mech_sub'
PV.shoot(sc, name, cams)
print('VIEWS', [v[0] for v in views])
