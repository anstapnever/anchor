import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'kit'))
import bpy, look as LK, env as EV, preview as PV
sc, W = PV.setup('morning', sun=(95, 16))
sc['seaT'] = 10.0
PV.shoot(sc, 'envtest', [((0, 0, 300), (-3000, -400, 0), 30.0), ((0, 0, 15), (3000, 300, 200), 35.0), ((0, -200, 550), (-600, -900, 0), 35.0), ((0, 0, 6), (0, 3000, 30), 28.0)],
         params={'haze_dist': 7000.0, 'haze_max': 0.35, 'haze': (0.75, 0.86, 1.0)})
