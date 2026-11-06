# ANCHOR - the mech's mattes for the 'behind the mech' layering (shots/bodyfx.json 'behind' -> fx._behind, post.mech_sil).
# Built and keyed exactly as the final render (every set, every shot keyed; ANCHOR_MATTE=1: the marked water is simply not
# drawn inside its window). For every frame of the list's windows, two renders with a transparent film and the sets of the
# frame's shot, every material's colour swapped and its own alpha kept (read back through Shader-to-RGB):
#   P - the mech white, everything else transparent: the mech's own silhouette (post draws its outline from it)
#   R - the mech white, every FX surface (M_fx_*: all the water, spray, steam) transparent, everything else (sea, port, chain,
#       city) a holdout: where a marked piece must not be drawn (fx._behind cuts it there). The other FX water does not count
#       as an occluder (06.11, second pass): a marked jet passing in front of a crest that lies on the armour would stay drawn
#       over the body as a white island. Only the sea (the parts of the mech under it) and solid things in front of the mech
#       keep the marked water drawn. Since no FX surface counts, the mattes do not depend on the list: they stay valid for any
#       list whose windows lie in the rendered frames (spec.json 'mode': 'fx-clear').
# out/matte/rawP/p<frame>.png, rawR/r<frame>.png (alpha); mattecomb.py packs them into out/matte/m<frame>.png.
#   ANCHOR_MATTE=1 blender -b -P tools/matte.py -- [spp]
import sys, os, json, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('kit', 'assets', 'shots'):
    q = os.path.join(ROOT, p)
    if q not in sys.path: sys.path.insert(0, q)
import bpy
import film, bodyfx
import env as EV

assert os.environ.get('ANCHOR_MATTE') == '1', 'run with ANCHOR_MATTE=1'
A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
spp = int(A[0]) if A else 16
t0 = time.time()
spec = json.load(open(bodyfx.JS, encoding='utf-8')).get('behind', {})
frames = bodyfx.behind_frames(spec)
EXTRA = [s for s in os.environ.get('MATTE_SHOTS', '').split(',') if s.strip()]        # whole shots rendered beyond the windows
if EXTRA: frames = sorted(set(frames) | {f for sid in EXTRA for f in range(film.frames_of(sid)[0], film.frames_of(sid)[1] + 1)})
ONLY = [int(x) for x in os.environ.get('MATTE_ONLY', '').split(',') if x.strip()]      # a smoke test: these frames only
if ONLY: frames = [f for f in frames if f in ONLY]
print('MATTE list %s: %d elements, %d frames %d-%d' % (bodyfx.behind_hash(spec), sum(len(d['el']) for d in spec.values()), len(frames), frames[0], frames[-1]), flush=True)
W = film.build(spp, 100)
ids = [s[0] for s in film.SHOTS]
film.key_shots(W, ids)
print('built+keyed %.0fs' % (time.time() - t0), flush=True)
sc = W['sc']; D = bpy.data
# ---- which surfaces are the mech: objects of the MECH set whose materials are not FX
mech = [o for o in W["C"]["MECH"].all_objects if len(o.material_slots)]; mset = {o.name for o in mech}
use_m = set(); use_o = set()
for o in sc.objects:
    for s in o.material_slots:
        if s.material is None: continue
        if o.name in mset and not s.material.name.startswith('M_fx'): use_m.add(s.material)
        else: use_o.add(s.material)
shared = use_m & use_o
for o in mech:
    for s in o.material_slots:
        if s.material in shared:
            m2 = s.material.copy(); m2.name = s.material.name + '.matte'
            s.link = 'OBJECT'; s.material = m2; use_m.add(m2)
use_m -= shared
print('MATTE mech objects %d, mech materials %d (%d shared with other objects, copied), other materials %d'
      % (len(mech), len(use_m), len(shared), len([m for m in D.materials if m not in use_m])), flush=True)


def out_node(nt):
    outs = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
    act = [n for n in outs if n.is_active_output and n.target in ('ALL', 'EEVEE')] or [n for n in outs if n.target in ('ALL', 'EEVEE')]
    return act[0] if act else None


SW = {}                    # material -> {'P': socket, 'R': socket, 'out': output node}
for m in list(D.materials):
    if m.is_grease_pencil: continue
    if not m.use_nodes or m.node_tree is None: m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    o = out_node(nt)
    if o is None: o = N.new('ShaderNodeOutputMaterial')
    for l in list(o.inputs['Volume'].links): L.remove(l)
    src = o.inputs['Surface'].links[0].from_socket if o.inputs['Surface'].is_linked else None
    if src is not None:
        s2r = N.new('ShaderNodeShaderToRGB'); L.new(src, s2r.inputs[0]); a = s2r.outputs['Alpha']
    else: a = None
    tr = N.new('ShaderNodeBsdfTransparent')
    if m in use_m:
        em = N.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (1, 1, 1, 1); em.inputs['Strength'].default_value = 1.0
        mx = N.new('ShaderNodeMixShader'); L.new(tr.outputs[0], mx.inputs[1]); L.new(em.outputs[0], mx.inputs[2])
        if a is not None: L.new(a, mx.inputs['Fac'])
        else: mx.inputs['Fac'].default_value = 1.0
        SW[m] = {'P': mx.outputs[0], 'R': mx.outputs[0], 'out': o}
    else:
        ho = N.new('ShaderNodeHoldout'); mx = N.new('ShaderNodeMixShader'); L.new(tr.outputs[0], mx.inputs[1]); L.new(ho.outputs[0], mx.inputs[2])
        if a is not None: L.new(a, mx.inputs['Fac'])
        else: mx.inputs['Fac'].default_value = 1.0
        tp = N.new('ShaderNodeBsdfTransparent')
        SW[m] = {'P': tp.outputs[0], 'R': tp.outputs[0] if m.name.startswith('M_fx') else mx.outputs[0], 'out': o}
wd = D.worlds.new('MATTE_W'); wd.use_nodes = True
bg = wd.node_tree.nodes.get('Background')
if bg: bg.inputs['Strength'].default_value = 0.0
sc.world = wd
r = sc.render; r.film_transparent = True; r.use_compositing = False; r.use_sequencer = False
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGBA'; r.image_settings.color_depth = '8'
for k, v in (('use_shadows', False), ('use_volumetric_shadows', False), ('use_raytracing', False)):
    try: setattr(sc.eevee, k, v)
    except Exception as ex: print('skip', k, ex)
print('MATTE res %dx%d %d%% spp %d filter %.2f' % (r.resolution_x, r.resolution_y, r.resolution_percentage, sc.eevee.taa_render_samples, r.filter_size), flush=True)
shot_of = {}
for sid in ids:
    f0, f1 = film.frames_of(sid)
    for f in range(f0, f1 + 1): shot_of[f] = sid
runs = []                  # (shot, a, b) contiguous runs of frames within one shot
for f in frames:
    s = shot_of.get(f)
    if runs and runs[-1][0] == s and runs[-1][2] == f - 1: runs[-1][2] = f
    else: runs.append([s, f, f])
for ps in ('P', 'R'):
    for m, d in SW.items():
        L = m.node_tree.links
        for l in list(d['out'].inputs['Surface'].links): L.remove(l)
        L.new(d[ps], d['out'].inputs['Surface'])
    od = os.path.join(ROOT, 'out', 'matte', 'raw' + ps); os.makedirs(od, exist_ok=True)
    for sid, a, b in runs:
        film.apply_sets(W, sid)
        r.filepath = os.path.join(od, ps.lower()); sc.frame_start = a; sc.frame_end = b; sc.frame_step = 1
        lk = EV.gpu_lock('matte'); ts = time.time()
        try: bpy.ops.render.render(animation=True)
        finally: EV.gpu_unlock(lk)
        print('MATTE %s %s %d-%d %.0fs (%.1fs/frame)' % (ps, sid, a, b, time.time() - ts, (time.time() - ts) / (b - a + 1)), flush=True)
if not ONLY: json.dump({'mode': 'fx-clear', 'hash': bodyfx.behind_hash(spec), 'frames': frames}, open(os.path.join(ROOT, 'out', 'matte', 'raw_spec.json'), 'w'))
print('MATTE DONE %.0fs' % (time.time() - t0), flush=True)
