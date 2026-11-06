import sys, os, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'kit')); sys.path.insert(0, os.path.join(ROOT, 'assets'))
import bpy, numpy as np, look as LK, env as EV, preview as PV, qa as QA, chain as CH
sc, W = PV.setup('morning', sun=(95, 18))
C = EV.coll('CHAIN')
links = CH.build(C, 12, 4)
# straight then bending at increasing angles: check interlock clearance per bend angle
res = {}
for deg in (0, 15, 25, 32, 38, 45):
    nodes = []; p = np.array((0.0, 0.0, 40.0)); d = np.array((1.0, 0.0, 0.0)); a = math.radians(deg)
    for i in range(13):
        nodes.append(p.copy()); ang = a * (i // 1) * 0.0
        if i >= 5: d = np.array((math.cos(a * (i - 4)), 0.0, -math.sin(a * (i - 4))))
        p = p + d * CH.PITCH
    CH.pose(links, nodes, key=False); bpy.context.view_layer.update()
    bad = QA.overlaps(links)
    res[deg] = [(x, y, n) for x, y, n in bad]
    print('BEND', deg, 'overlaps', len(bad), bad[:3])
# hang a catenary for the picture
nodes = CH.catenary((-30, 0, 75), (20, 10, 30), 12 * CH.PITCH, 13)
CH.pose(links, nodes, key=False)
print('max bend in catenary', CH.bend_report(nodes))
PV.shoot(sc, 'chaintest', [((-45, -40, 70), (0, 10, 60), 40.0), ((10, -25, 40), (0, 10, 40), 50.0)])
