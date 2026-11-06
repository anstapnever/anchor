# mattecomb.py : out/matte/rawP + rawR (matte.py) -> out/matte/m<frame>.png, the file fx._behind and post.mech_sil read:
#   R = the R pass alpha (the mech as the nearest surface), G = frame % 256, B = frame // 256 (checked against the frame in the
#   shader and in post), A = the P pass alpha (the mech's own silhouette); black frames in the gaps between windows and one
#   black pad before and after (frames outside the sequence read the pads). spec.json = the hash of the list they were made for.
# R is taken from the R pass COLOUR, not its alpha: the mech emits white, so its premultiplied light (linear colour x alpha) is
#   exactly the part of the mech that reaches the camera. The alpha is not: a dithered holdout over the empty background leaves
#   black pixels with alpha 0.1-0.5 in Eevee (06.11, the city's waterfalls in s26: up to 8654 px a frame read as 'mech').
# spec.json: 'mode' ('fx-clear': no FX surface occludes the mech in R, the mattes fit any behind list) and 'list', the frames.
# Checks: every frame present, R never above P (R is P less what stands in front of the mech); frames without the mech noted.
import os, json, glob, sys
import numpy as np, cv2
M = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', 'matte') + os.sep
rs = json.load(open(M + 'raw_spec.json')); frames = rs['frames']; fs = set(frames)
P0 = cv2.imread(M + 'rawP/p%04d.png' % frames[0], cv2.IMREAD_UNCHANGED); H, W = P0.shape[:2]
bad = []; rows = []


def srgb_inv(c):
    c = c.astype(np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def mech_light(R):
    """the mech's share of the pixel from the R pass: linear colour (Standard view = sRGB curve on straight colour) x alpha"""
    return srgb_inv(R[..., :3]).max(-1) * (R[..., 3].astype(np.float32) / 255.0)


def pack(f, P, R):
    out = np.zeros((H, W, 4), np.uint8); out[..., 3] = P[..., 3]
    out[..., 2] = np.clip(np.round(np.minimum(mech_light(R), P[..., 3].astype(np.float32) / 255.0) * 255.0), 0, 255).astype(np.uint8)
    out[..., 1] = f % 256; out[..., 0] = f // 256
    return out


for f in frames:
    P = cv2.imread(M + 'rawP/p%04d.png' % f, cv2.IMREAD_UNCHANGED); R = cv2.imread(M + 'rawR/r%04d.png' % f, cv2.IMREAD_UNCHANGED)
    if P is None or R is None or P.ndim != 3 or P.shape[2] != 4 or R.shape != P.shape: bad.append((f, 'missing or not RGBA')); continue
    a, r = P[..., 3].astype(np.int16), np.round(mech_light(R) * 255.0).astype(np.int16)
    over = int(((r - a) > 25).sum())
    if over > 50: bad.append((f, 'R above P on %d px' % over))
    if (a > 127).sum() < 200: print('  note: f%d the mech is (nearly) out of frame (%d px)' % (f, int((a > 127).sum())))
    rows.append((f, float((a > 127).mean()), float((r > 127).mean()), over))
if bad:
    print('MATTECOMB FAILED', bad[:20]); sys.exit(1)
for p in glob.glob(M + 'm[0-9][0-9][0-9][0-9].png'): os.remove(p)
z = np.zeros((H, W, 4), np.uint8)
for f in range(frames[0] - 1, frames[-1] + 2):
    if f in fs:
        out = pack(f, cv2.imread(M + 'rawP/p%04d.png' % f, cv2.IMREAD_UNCHANGED), cv2.imread(M + 'rawR/r%04d.png' % f, cv2.IMREAD_UNCHANGED))
    else: out = z
    cv2.imwrite(M + 'm%04d.png' % f, out)
json.dump({'mode': rs.get('mode', 'holdout-all'), 'hash': rs['hash'], 'frames': [frames[0], frames[-1]], 'n': len(frames), 'list': frames},
          open(M + 'spec.json', 'w'))
print('MATTECOMB ok: %d mattes + %d black, m%04d..m%04d, list %s' % (len(fs), frames[-1] - frames[0] + 3 - len(fs), frames[0] - 1, frames[-1] + 1, rs['hash']))
for k in range(0, len(rows), max(1, len(rows) // 24)):
    f, pa, ra, over = rows[k]
    print('  f%d  mech silhouette %.1f %%  nearest %.1f %%  R>P px %d' % (f, pa * 100, ra * 100, over))
