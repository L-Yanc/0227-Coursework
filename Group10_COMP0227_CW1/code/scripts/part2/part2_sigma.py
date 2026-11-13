# Part 2: does sigma_d (how unsure the net is at a keypoint) actually predict the real error?
# usage (from $P): python part2_sigma.py SEQ_FOLDER FACTOR NAME [--step 10] [--out out_prefix]
#   SEQ_FOLDER has associations.txt (true depth) and associations_<NAME>.txt (predicted depth)
import argparse
import os

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pyslam.depth_estimation.depth_sampling import depth_at_keypoints

p = argparse.ArgumentParser()
p.add_argument("seq")
p.add_argument("factor", type=float)
p.add_argument("name")
p.add_argument("--step", type=int, default=10)
p.add_argument("--nkp", type=int, default=1000)
p.add_argument("--out", default="sigma")
a = p.parse_args()


def read_assoc(path):  # rgb file -> depth file
    out = {}
    for line in open(path):
        f = line.split()
        if len(f) >= 4 and not line.startswith("#"):
            out[f[1]] = f[3]
    return out


true = read_assoc(os.path.join(a.seq, "associations.txt"))
pred = read_assoc(os.path.join(a.seq, f"associations_{a.name}.txt"))
frames = [r for r in pred if r in true][:: a.step]
orb = cv2.ORB_create(nfeatures=a.nkp)

rows = []  # frame, u, v, d_pred, d_true, frame scale, grad
for i, rgb in enumerate(frames):
    img = cv2.imread(os.path.join(a.seq, rgb), cv2.IMREAD_GRAYSCALE)
    dp = cv2.imread(os.path.join(a.seq, pred[rgb]), cv2.IMREAD_UNCHANGED).astype(np.float64) / a.factor
    dt = cv2.imread(os.path.join(a.seq, true[rgb]), cv2.IMREAD_UNCHANGED).astype(np.float64) / a.factor
    kps = orb.detect(img, None)
    if not kps:
        continue
    uv = np.array([k.pt for k in kps])
    zp = depth_at_keypoints(dp, uv, "median", 5)
    zt = depth_at_keypoints(dt, uv, "median", 5)
    ok = (zp > 0) & (zt > 0)
    if ok.sum() < 20:
        continue
    s = np.median(zt[ok] / zp[ok])  # shape only: fix this frame's scale first
    # depth gradient of the prediction, worst value in a 5x5 window around the keypoint
    g = np.hypot(cv2.Sobel(dp, cv2.CV_64F, 1, 0, ksize=3), cv2.Sobel(dp, cv2.CV_64F, 0, 1, ksize=3)) / 8
    g = cv2.dilate(g, np.ones((5, 5), np.uint8))
    gk = depth_at_keypoints(g, uv, "nearest")
    rows.append(np.column_stack([np.full(ok.sum(), i), uv[ok], zp[ok], zt[ok], np.full(ok.sum(), s), gk[ok]]))

R = np.vstack(rows)
fr, u, v, zp, zt, s, grad = R.T
err_abs = np.abs(s * zp - zt)  # metres, after the frame's scale
err_rel = err_abs / zt
eps = np.median(err_rel)  # the fixed relative error, measured
cands = {
    "fixed eps*d": eps * s * zp,  # sigma_d = eps * d_hat
    "gradient": grad * s,  # |grad d_hat| near the keypoint, in m per pixel
    "gradient/d": grad / zp,  # same but relative
}


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return np.corrcoef(rx, ry)[0, 1]


print(f"{a.seq}: {len(frames)} frames (every {a.step}), {len(zp)} keypoints, eps (median rel err) = {eps:.3f}")
print(f"{'sigma_d':12} {'rank corr abs err':>17} {'rank corr rel err':>17}   median rel err in 5 bins of sigma_d (low -> high)")
fig, axes = plt.subplots(1, len(cands), figsize=(5 * len(cands), 4))
for ax, (name, sig) in zip(axes, cands.items()):
    edges = np.quantile(sig, np.linspace(0, 1, 6))
    b = np.clip(np.searchsorted(edges, sig, side="right") - 1, 0, 4)
    med = [np.median(err_rel[b == k]) for k in range(5)]
    print(f"{name:12} {spearman(sig, err_abs):17.2f} {spearman(sig, err_rel):17.2f}   " + " ".join(f"{m:.3f}" for m in med))
    sub = np.random.default_rng(0).choice(len(sig), min(5000, len(sig)), replace=False)
    ax.scatter(sig[sub], err_abs[sub], s=2, alpha=0.3)
    mid = [np.median(sig[b == k]) for k in range(5)]
    ax.plot(mid, [np.median(err_abs[b == k]) for k in range(5)], "r-o", label="median per bin")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(f"sigma_d: {name}")
    ax.set_ylabel("actual error (m, scale fixed)")
    ax.legend()
fig.tight_layout()
fig.savefig(a.out + ".png", dpi=120)
np.savez_compressed(a.out + "_keypoints.npz", frame=fr, u=u, v=v, d_pred=zp, d_true=zt, scale=s, grad=grad)
print("saved", a.out + ".png", "and", a.out + "_keypoints.npz")
