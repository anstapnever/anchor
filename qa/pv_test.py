import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'kit')); sys.path.insert(0, os.path.join(ROOT, 'assets'))
import bpy, bmesh, look as LK, env as EV, preview as PV, qa as QA
sc, W = PV.setup('morning', sun=(95, 16))
m = LK.cel('M_t', '#f2b705', grime=0.6, chips=0.6, wscale=0.3)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=20.0); o = EV.bm_obj('T', bm, m, W); o.location = (0, 0, 10)
print('QA', QA.overlaps([o]))
PV.shoot(sc, 'pvtest', [((-60, -60, 20), (0, 0, 10), 35.0), ((60, -50, 40), (0, 0, 10), 50.0)])
