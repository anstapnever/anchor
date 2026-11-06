# ANCHOR — pops in the baked mech track (numpy, no Blender): every tracked part's world position and rotation, frame to frame.
# A frame pops when its deviation from the midpoint of its neighbours (|p[f] - (p[f-1] + p[f+1]) / 2|, i.e. half the acceleration)
# spikes over the local level (POP_K x the median of the 11 frames around it) and over an absolute floor; the same for the rotation
# (angle of the frame's rotation from the slerp midpoint of its neighbours). Only the frames of shots that show the mech count.
#   python shots/popcheck.py 1177-1522 [all]      (all: every frame, shown or not)
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import numpy as np

POP_K = 3.0
POS_FLOOR = 0.6          # m
ROT_FLOOR = 1.5          # deg
TRACK = os.path.join(ROOT, 'out', 'track', 'mech_track.npz')


def shown_frames():
    import re
    src = open(os.path.join(HERE, 'film.py'), encoding='utf-8').read()
    out = set()
    for sid, a, b, tags in re.findall(r"\('(s\d\d)', ([\d.]+), ([\d.]+), '([^']*)'\)", src):
        if 'MECH' in tags.split():
            f0 = int(round(float(a) * 24)) + 1; f1 = int(round(float(b) * 24))
            out.update(range(f0, f1 + 1))
    return out


def cut_frames():
    """frames next to a cut (first / last frame of every shot): their neighbour on the far side is never seen with them."""
    import re
    src = open(os.path.join(HERE, 'film.py'), encoding='utf-8').read()
    out = set()
    for sid, a, b, tags in re.findall(r"\('(s\d\d)', ([\d.]+), ([\d.]+), '([^']*)'\)", src):
        out.add(int(round(float(a) * 24)) + 1); out.add(int(round(float(b) * 24)))
    return out


def q_of(R):
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2; return np.array((0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s))
    i = int(np.argmax((R[0, 0], R[1, 1], R[2, 2])))
    if i == 0:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        return np.array(((R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s))
    if i == 1:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        return np.array(((R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s))
    s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
    return np.array(((R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s))


def qang(a, b):
    return math.degrees(2 * math.acos(min(1.0, abs(float(np.dot(a, b))))))


def run(f0, f1, all_frames=False):
    Z = np.load(TRACK, allow_pickle=True); W = Z['W']; names = [str(n) for n in Z['tracked']]
    show = None if all_frames else shown_frames()
    found = []
    for j, nm in enumerate(names):
        if nm in ('gull', 'chick', 'nest', 'steam_0', 'steam_1', 'steam_2'): continue
        P = W[f0 - 1:f1 + 2, j, :3, 3].astype(np.float64)            # frames f0-1 .. f1+1 (track index = frame)
        Q = [q_of(W[f, j, :3, :3].astype(np.float64)) for f in range(f0 - 1, f1 + 2)]
        dev = np.zeros(len(P)); rdv = np.zeros(len(P))
        for i in range(1, len(P) - 1):
            dev[i] = float(np.linalg.norm(P[i] - 0.5 * (P[i - 1] + P[i + 1])))
            qa, qb = Q[i - 1], Q[i + 1]
            if np.dot(qa, qb) < 0: qb = -qb
            qm = (qa + qb); qm /= np.linalg.norm(qm)
            rdv[i] = qang(Q[i], qm)
        for i in range(1, len(P) - 1):
            f = f0 - 1 + i
            if show is not None and f not in show: continue
            lo, hi = max(1, i - 5), min(len(P) - 1, i + 6)
            nb = np.r_[dev[lo:i], dev[i + 1:hi]]; rb = np.r_[rdv[lo:i], rdv[i + 1:hi]]
            if dev[i] > POS_FLOOR and dev[i] > POP_K * max(float(np.median(nb)), 0.05):
                found.append((f, nm, 'pos', round(dev[i], 2), round(float(np.median(nb)), 2)))
            if rdv[i] > ROT_FLOOR and rdv[i] > POP_K * max(float(np.median(rb)), 0.1):
                found.append((f, nm, 'rot', round(rdv[i], 2), round(float(np.median(rb)), 2)))
    found.sort()
    for x in found: print('POP f %d %-12s %s dev %.2f (around %.2f)' % x)
    print('POPCHECK %d..%d %s: %d pops' % (f0, f1, 'all frames' if all_frames else 'shown frames', len(found)))
    return found


if __name__ == '__main__':
    a, b = [int(x) for x in sys.argv[1].split('-')]
    run(a, b, len(sys.argv) > 2 and sys.argv[2] == 'all')
