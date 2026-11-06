import sys, os, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'kit')); sys.path.insert(0, os.path.join(ROOT, 'assets'))
import bpy, numpy as np, env as EV, qa as QA, chain as CH
sc = EV.reset(); C = EV.coll('CHAIN')
for play in (0.15, 0.35, 0.6):
    pitch = CH.L_OUT - 2 * CH.BAR - play
    links = CH.build(C, 6, 0)
    for roll in (0.0, 90.0):
        ok = 0
        for deg in range(0, 80, 5):
            a = math.radians(deg); nodes = []; p = np.array((0.0, 0.0, 0.0))
            for i in range(7):
                nodes.append(p.copy()); d = np.array((math.cos(a * max(0, i - 2)), 0.0, -math.sin(a * max(0, i - 2))))
                p = p + d * pitch
            CH.pose(links, nodes, key=False, roll0=math.radians(roll)); bpy.context.view_layer.update()
            if QA.overlaps(links): break
            ok = deg
        print('PLAY', play, 'ROLL', roll, 'max clean bend', ok)
    for o in links: bpy.data.objects.remove(o)
