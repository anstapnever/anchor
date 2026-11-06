import bpy
sc = bpy.context.scene
c = bpy.data.collections.new('X'); sc.collection.children.link(c)
c.hide_render = False
try:
    c.keyframe_insert('hide_render', frame=1); c.hide_render = True; c.keyframe_insert('hide_render', frame=5)
    sc.frame_set(3); print('HIDE f3', c.hide_render); sc.frame_set(6); print('HIDE f6', c.hide_render)
except Exception as e: print('ERR', e)
