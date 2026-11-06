# ANCHOR stage helpers: camera keys, per-frame uniforms that follow the camera, rendering a frame range through the GPU lock.
import bpy, os, math, json, time
from mathutils import Vector, Euler, Quaternion
import env as EV


def key_cam(cam, frame, pos, tgt, lens=None, roll=0.0):
    EV.look_at(cam, pos, tgt, roll)
    cam.keyframe_insert('location', frame=frame); cam.keyframe_insert('rotation_quaternion', frame=frame)
    if lens is not None: cam.data.lens = lens; cam.data.keyframe_insert('lens', frame=frame)


def follow_camera(sc, cam, f0, f1, sky=None):
    """Key the sea's camera-position uniform and keep the sky dome centred on the camera, every frame."""
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        p = cam.matrix_world.translation.copy()
        sc['camP'] = tuple(p); sc.keyframe_insert('["camP"]', frame=f)
        if sky is not None: sky.location = p; sky.keyframe_insert('location', frame=f)
    _linear(sc);
    if sky is not None: _linear(sky)


def _linear(idb):
    ad = idb.animation_data
    if not ad or not ad.action: return
    try:
        for fc in ad.action.fcurves:
            for k in fc.keyframe_points: k.interpolation = 'LINEAR'
    except AttributeError:
        for layer in ad.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        for k in fc.keyframe_points: k.interpolation = 'LINEAR'


def fcurves(idb):
    ad = idb.animation_data
    if not ad or not ad.action: return []
    try: return list(ad.action.fcurves)
    except AttributeError:
        out = []
        for layer in ad.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags: out += list(cb.fcurves)
        return out


def set_interp(idb, kind='LINEAR'):
    for fc in fcurves(idb):
        for k in fc.keyframe_points: k.interpolation = kind


def render_range(sc, outdir, f0, f1, tag='anchor', step=1):
    os.makedirs(outdir, exist_ok=True)
    comp = sc.compositing_node_group
    for n in comp.nodes:
        if n.bl_idname == 'CompositorNodeOutputFile': n.directory = outdir + os.sep; n.file_name = ''
    sc.render.filepath = os.path.join(outdir, 'f')
    sc.frame_start = f0; sc.frame_end = f1; sc.frame_step = step
    lk = EV.gpu_lock(tag); t0 = time.time()
    try: bpy.ops.render.render(animation=True)
    finally: EV.gpu_unlock(lk)
    print('rendered %d..%d in %.1fs' % (f0, f1, time.time() - t0))
