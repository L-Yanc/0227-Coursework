#!/usr/bin/env python3
"""COMP0227 CW1 Part 2: a depth, an uncertainty and a validity flag for every SLAM keypoint.

At run time SLAM has only the predicted depth map, so the uncertainty uses only features computed
from it at each ORB keypoint:
  log d, (log d)^2   the predicted depth (step 5a: error is lowest at 1-3 m, higher nearer and farther),
  log spread         (max - min) / d of the predicted depth in a small window: large at depth edges,
                     where step 5a found the error doubles,
  border             1 if the keypoint is in the outer band of the image (5a: border is worse).
Model (fitted once, on the FIRST half of a sequence, against the true depth):
  local relative error  sigma_local = exp(w . features + c)
      w: least squares of log(|e| + 0.005) on the features; c: chosen so that 68% of the training
      keypoints have |e| <= sigma_local (the one-sigma coverage of a Gaussian),
      e = relative error after removing each frame's scale (the scale is a separate problem);
  scale term            sigma_scale = half the 16-84% spread of the per-frame scale (training half),
                        what is left if ONE scale is used for the whole map (--scale-sigma to set it,
                        e.g. 0.03 for a per-keyframe scale, step 5b);
  total                 sigma_rel = sqrt(sigma_local^2 + sigma_scale^2),  sigma_m = sigma_rel * d,
                        and in map units sigma_map = sigma_m / s  (metres = s x map units);
  valid                 min_depth < d < max_depth and sigma_rel <= --max-sigma.
Validated on the SECOND half: does the error grow with sigma (rank correlation, bins), is the
coverage right, and does dropping the least certain keypoints cut the error?
Ground truth only fits and checks the model; deploying it needs only the predicted map.

Example (TUM):
  pixi run -e depth-cpu python scripts/part2/part2_keypoint_uncertainty.py \
      --seq data/tum/rgbd_dataset_freiburg3_long_office_household --name dav2b \
      --factor 5000 --step 5 --out results/part2/tum_dav2b_uncertainty
For Part 3 (no ground truth needed):
  from part2_keypoint_uncertainty import load_model, depth_sigma_at_keypoints
  model = load_model("results/part2/tum_dav2b_uncertainty/model.json")
  d_m, sigma_m, valid, sigma_rel = depth_sigma_at_keypoints(pred_depth_m, keypoints_uv, model)
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

FEATURE_NAMES = ["constant", "log d", "(log d)^2", "log spread", "border"]


# ---------------------------------------------------------------- the deployable part
def bilinear(depth, kps):
    """Bilinear depth at (u, v), ignoring pixels without depth (as depth_sampling.py 'bilinear')."""
    h, w = depth.shape
    u, v = kps[:, 0], kps[:, 1]
    u0 = np.clip(np.floor(u).astype(int), 0, w - 1)
    v0 = np.clip(np.floor(v).astype(int), 0, h - 1)
    u1, v1 = np.clip(u0 + 1, 0, w - 1), np.clip(v0 + 1, 0, h - 1)
    fu, fv = np.clip(u - u0, 0, 1), np.clip(v - v0, 0, 1)
    d = np.stack([depth[v0, u0], depth[v0, u1], depth[v1, u0], depth[v1, u1]], 1)
    wt = np.stack([(1 - fu) * (1 - fv), fu * (1 - fv), (1 - fu) * fv, fu * fv], 1)
    wt = np.where(d > 0, wt, 0.0)
    tot = wt.sum(1)
    out = np.zeros(len(kps))
    ok = tot > 1e-12
    out[ok] = (wt[ok] * d[ok]).sum(1) / tot[ok]
    return out


def local_spread(pred, window):
    """(max - min) / depth of the predicted depth in a window x window neighbourhood, per pixel."""
    k = np.ones((window, window), np.uint8)
    p = pred.astype(np.float32)
    return (cv2.dilate(p, k) - cv2.erode(p, k)) / np.maximum(p, 1e-3)


def features(d, spread, kps, shape, border_frac):
    h, w = shape
    u, v = kps[:, 0], kps[:, 1]
    dist = np.minimum.reduce([u, v, w - 1 - u, h - 1 - v])
    ld = np.log(np.maximum(d, 1e-3))
    return np.stack([np.ones_like(ld), ld, ld ** 2, np.log(spread + 0.005),
                     (dist < border_frac * min(w, h)).astype(float)], 1)


def load_model(path):
    with open(path) as f:
        return json.load(f)


def depth_sigma_at_keypoints(pred, kps, model):
    """pred: predicted depth (H, W) in metres; kps: (N, 2) array of (u, v).
    Returns depth_m, sigma_m, valid, sigma_rel, each of shape (N,)."""
    kps = np.asarray(kps, dtype=np.float64).reshape(-1, 2)
    d = bilinear(np.asarray(pred, dtype=np.float64), kps)
    spread_map = local_spread(pred, model["window"])
    h, w = pred.shape
    ui = np.clip(np.rint(kps[:, 0]).astype(int), 0, w - 1)
    vi = np.clip(np.rint(kps[:, 1]).astype(int), 0, h - 1)
    X = features(d, spread_map[vi, ui], kps, pred.shape, model["border_frac"])
    s_local = np.exp(X @ np.array(model["weights"]) + model["calibration"])
    s_rel = np.sqrt(s_local ** 2 + model["scale_sigma"] ** 2)
    valid = (d > model["min_depth"]) & (d < model["max_depth"]) & (s_rel <= model["max_sigma"])
    return d, s_rel * d, valid, s_rel


# ---------------------------------------------------------------- data
def read_list(path):
    rows = []
    with open(path) as f:
        for line in f:
            if not line.startswith("#") and len(line.split()) >= 4:
                rows.append(line.split()[:4])
    return rows


def load_depth(path, factor):
    d = cv2.imread(path, cv2.IMREAD_ANYDEPTH)
    if d is None:
        raise FileNotFoundError(path)
    return d.astype(np.float64) / factor


def collect(a):
    """Per keypoint of every --step-th frame: features, predicted and true depth, frame scale."""
    gt_rows = read_list(os.path.join(a.seq, "associations.txt"))
    pp = os.path.join(a.seq, f"associations_{a.name}.txt")
    if not os.path.exists(pp):
        sys.exit(f"{pp} not found: run depth-prediction --save {a.name} on the whole sequence first")
    pred_of = {r[1]: r[3] for r in read_list(pp)}
    orb = cv2.ORB_create(nfeatures=a.nfeatures, scaleFactor=1.2, nlevels=8)
    pf = a.pred_factor or a.factor
    out = {k: [] for k in ("frame", "time", "u", "v", "d", "gt", "X", "s_frame")}
    rows = [(i, r) for i, r in enumerate(gt_rows) if r[1] in pred_of][:: a.step]
    for n, (i, r) in enumerate(rows):
        img = cv2.imread(os.path.join(a.seq, r[1]), cv2.IMREAD_GRAYSCALE)
        gt = load_depth(os.path.join(a.seq, r[3]), a.factor)
        pred = load_depth(os.path.join(a.seq, pred_of[r[1]]), pf)
        if pred.shape != gt.shape:
            pred = cv2.resize(pred, (gt.shape[1], gt.shape[0]), interpolation=cv2.INTER_NEAREST)
        ok = (gt > a.min_depth) & (gt < a.max_depth) & (pred > 0)
        if ok.sum() < 100 or img is None:
            continue
        s_frame = float(np.median(gt[ok] / pred[ok]))  # oracle, only to separate scale from local error
        kp = orb.detect(img, None)
        if not kp:
            continue
        kps = np.array([k.pt for k in kp], dtype=np.float64)
        d = bilinear(pred, kps)
        g = bilinear(np.where((gt > a.min_depth) & (gt < a.max_depth), gt, 0.0), kps)
        sp = local_spread(pred, a.window)
        ui = np.clip(np.rint(kps[:, 0]).astype(int), 0, gt.shape[1] - 1)
        vi = np.clip(np.rint(kps[:, 1]).astype(int), 0, gt.shape[0] - 1)
        X = features(d, sp[vi, ui], kps, gt.shape, a.border)
        m = len(kps)
        out["frame"].append(np.full(m, i))
        out["time"].append(np.full(m, float(r[0])))
        out["u"].append(kps[:, 0])
        out["v"].append(kps[:, 1])
        out["d"].append(d)
        out["gt"].append(g)
        out["X"].append(X)
        out["s_frame"].append(np.full(m, s_frame))
        if (n + 1) % 100 == 0:
            print(f"  {n + 1}/{len(rows)} frames")
    if not out["d"]:
        sys.exit("no frames with keypoints and depth")
    return {k: (np.concatenate(v) if k != "X" else np.vstack(v)) for k, v in out.items()}


# ---------------------------------------------------------------- checks
def ranks(x):
    r = np.empty(len(x))
    r[np.argsort(x, kind="stable")] = np.arange(len(x))
    return r


def evaluate(sig, err, rng):
    """How well sigma (relative) describes |relative error|."""
    res = {"keypoints": int(len(err)),
           "spearman": float(np.corrcoef(ranks(sig), ranks(err))[0, 1]),
           "within_1sigma": float(np.mean(err <= sig)), "within_2sigma": float(np.mean(err <= 2 * sig)),
           "absrel_all": float(np.mean(err))}
    for frac in (0.1, 0.2, 0.5):
        k = int(round(len(err) * (1 - frac)))
        res[f"absrel_drop{int(frac * 100)}_by_sigma"] = float(np.mean(err[np.argsort(sig)][:k]))
        res[f"absrel_drop{int(frac * 100)}_oracle"] = float(np.mean(np.sort(err)[:k]))
        res[f"absrel_drop{int(frac * 100)}_random"] = float(np.mean(err[rng.permutation(len(err))[:k]]))
    edges = np.quantile(sig, np.linspace(0, 1, 6))
    b = np.clip(np.searchsorted(edges, sig, side="right") - 1, 0, 4)
    res["bins"] = [{"sigma_median": float(np.median(sig[b == k])), "error_median": float(np.median(err[b == k])),
                    "error_p68": float(np.quantile(err[b == k], 0.68)), "n": int(np.sum(b == k))} for k in range(5)]
    return res


def plot(results, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for key, lab, col in (("local", "local (frame scale removed)", "tab:blue"), ("total", "total (one scale for the map)", "tab:orange")):
        bins = results[key]["bins"]
        ax[0].plot([b["sigma_median"] for b in bins], [b["error_p68"] for b in bins], "o-", color=col, label=lab)
    lim = max(max(b["sigma_median"], b["error_p68"]) for k in ("local", "total") for b in results[k]["bins"]) * 1.1
    ax[0].plot([0, lim], [0, lim], color="0.5", lw=0.8, ls="--", label="ideal")
    ax[0].set_xlabel("predicted sigma (relative), bin median")
    ax[0].set_ylabel("68th percentile of actual |error|")
    ax[0].set_title("calibration, held-out half")
    ax[0].legend(fontsize=8)
    r = results["local"]
    fr = [0, 10, 20, 50]
    for key, lab, col in (("by_sigma", "drop least certain", "tab:blue"), ("oracle", "drop worst (oracle)", "0.3"), ("random", "drop at random", "0.7")):
        ax[1].plot(fr, [r["absrel_all"]] + [r[f"absrel_drop{f}_{key}"] for f in fr[1:]], "o-", color=col, label=lab)
    ax[1].set_xlabel("% of keypoints dropped")
    ax[1].set_ylabel("AbsRel of the rest (frame scale removed)")
    ax[1].set_title("does sigma pick the bad keypoints?")
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seq", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--factor", type=float, default=5000.0, help="depth PNG units per metre (TUM 5000, Replica 6553.5)")
    ap.add_argument("--pred-factor", type=float)
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--nfeatures", type=int, default=1000, help="ORB keypoints per frame")
    ap.add_argument("--window", type=int, default=5, help="window of the depth spread (odd)")
    ap.add_argument("--border", type=float, default=0.1, help="border band, fraction of the shorter side")
    ap.add_argument("--min-depth", type=float, default=0.1)
    ap.add_argument("--max-depth", type=float, default=10.0)
    ap.add_argument("--max-sigma", type=float, default=0.3, help="keypoints with sigma_rel above this are invalid")
    ap.add_argument("--scale-sigma", type=float, help="relative scale uncertainty (default: from the training half)")
    ap.add_argument("--model", help="use this model.json instead of fitting (e.g. TUM's model on Replica)")
    ap.add_argument("--features", default="logd,logd2,spread,border",
                    help="features to fit (the constant is always used), from logd, logd2, spread, border; "
                         "e.g. 'spread,border' for a model to use on another camera or scene (KITTI)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(0)

    D = collect(a)
    has_gt = (D["gt"] > 0) & (D["d"] > 0)
    frames = np.unique(D["frame"])
    train = np.isin(D["frame"], frames[: len(frames) // 2])
    e_local = np.abs(D["d"] * D["s_frame"] / np.where(D["gt"] > 0, D["gt"], 1) - 1)
    fs_train = np.array([D["s_frame"][D["frame"] == f][0] for f in frames[: len(frames) // 2]])
    s_global = float(np.median(fs_train))
    e_total = np.abs(D["d"] * s_global / np.where(D["gt"] > 0, D["gt"], 1) - 1)

    if a.model:
        model = load_model(a.model)
        print(f"model from {a.model} (not refitted)")
    else:
        fit = train & has_gt
        names = {"logd": 1, "logd2": 2, "spread": 3, "border": 4}
        bad = [f for f in a.features.split(",") if f and f not in names]
        if bad:
            sys.exit(f"unknown --features {bad}; choose from {list(names)}")
        cols = [0] + sorted(names[f] for f in a.features.split(",") if f)
        X, y = D["X"][fit], np.log(e_local[fit] + 0.005)
        w = np.zeros(X.shape[1])
        w[cols] = np.linalg.lstsq(X[:, cols], y, rcond=None)[0]  # unused features keep weight 0
        c = float(np.log(np.quantile(e_local[fit] / np.exp(X @ w), 0.6827)))
        q16, q84 = np.quantile(fs_train / s_global, [0.16, 0.84])
        scale_sigma = a.scale_sigma if a.scale_sigma is not None else float((q84 - q16) / 2)
        model = {"weights": w.tolist(), "feature_names": FEATURE_NAMES, "features_fitted": a.features, "calibration": c,
                 "scale_sigma": scale_sigma, "window": a.window, "border_frac": a.border,
                 "min_depth": a.min_depth, "max_depth": a.max_depth, "max_sigma": a.max_sigma,
                 "fitted_on": {"sequence": a.seq, "name": a.name, "frames": int(len(frames) // 2),
                               "keypoints": int(fit.sum()), "s_global_oracle": s_global},
                 "units": "sigma_m = sigma_rel * depth_m; in map units divide by s (metres = s x map units)"}
        with open(os.path.join(a.out, "model.json"), "w") as f:
            json.dump(model, f, indent=2)

    s_local = np.exp(D["X"] @ np.array(model["weights"]) + model["calibration"])
    s_rel = np.sqrt(s_local ** 2 + model["scale_sigma"] ** 2)
    valid = (D["d"] > model["min_depth"]) & (D["d"] < model["max_depth"]) & (s_rel <= model["max_sigma"])
    test = (~train if not a.model else np.ones_like(train)) & has_gt
    results = {"local": evaluate(s_local[test], e_local[test], rng),
               "total": evaluate(s_rel[test], e_total[test], rng),
               "valid_fraction": float(valid[D["d"] > 0].mean()),
               "absrel_local_valid": float(e_local[test & valid].mean()),
               "absrel_local_invalid": float(e_local[test & ~valid].mean()) if (test & ~valid).any() else None,
               "keypoints_with_gt_fraction": float(has_gt.mean())}
    with open(os.path.join(a.out, "validation.json"), "w") as f:
        json.dump(results, f, indent=2)
    np.savez_compressed(os.path.join(a.out, "keypoints.npz"), frame=D["frame"], time=D["time"], u=D["u"], v=D["v"],
                        depth_m=D["d"], sigma_m=s_rel * D["d"], sigma_rel=s_rel, valid=valid, gt_m=D["gt"])
    plot(results, os.path.join(a.out, "uncertainty.png"))

    print(f"\n{len(frames)} frames, {len(D['d'])} keypoints ({has_gt.mean():.0%} with true depth); "
          f"{'fit on first half, checked on second' if not a.model else 'checked on all frames'}")
    print("sigma_local = exp(" + " ".join(f"{wi:+.3f}*[{n}]" for wi, n in zip(model["weights"], FEATURE_NAMES))
          + f" {model['calibration']:+.3f});  scale term {model['scale_sigma']:.3f}")
    for key, lab in (("local", "local, frame scale removed"), ("total", "total, one scale for the map")):
        r = results[key]
        print(f"\n[{lab}]  keypoints {r['keypoints']}, rank corr(sigma, |err|) {r['spearman']:.2f}, "
              f"within 1 sigma {r['within_1sigma']:.0%} (target 68%), within 2 sigma {r['within_2sigma']:.0%}")
        print(f"  AbsRel all {r['absrel_all']:.3f}; drop 20% by sigma {r['absrel_drop20_by_sigma']:.3f} "
              f"(oracle {r['absrel_drop20_oracle']:.3f}, random {r['absrel_drop20_random']:.3f}); "
              f"drop 50% by sigma {r['absrel_drop50_by_sigma']:.3f}")
        print("  sigma bins (median sigma -> median |err|, 68% |err|): " + ", ".join(
            f"{b['sigma_median']:.3f}->{b['error_median']:.3f}/{b['error_p68']:.3f}" for b in r["bins"]))
    inv = results["absrel_local_invalid"]
    print(f"\nvalid (sigma_rel <= {model['max_sigma']}): {results['valid_fraction']:.0%} of keypoints; "
          f"local AbsRel valid {results['absrel_local_valid']:.3f}, invalid {inv if inv is None else round(inv, 3)}")
    print(f"written to {a.out}: model.json, validation.json, keypoints.npz, uncertainty.png")


if __name__ == "__main__":
    main()
