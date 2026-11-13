# adds E1 to pyslam/slam/initializer.py (run from the pyslam folder)
p = "pyslam/slam/initializer.py"
s = open(p).read()
old = "                depth_scale = desired_median_depth / median_depth\n"
new = old + (
    "                from pyslam.depth_estimation import pred_depth\n"
    "                if pred_depth.use(\"E1\"):  # E1: first map in the net's metres\n"
    "                    d = pred_depth.depth(pred_depth.ts_of(kf_cur))\n"
    "                    if d is not None:\n"
    "                        z, ok = pred_depth.trusted(d, kf_cur.kps[out.idxs_cur])\n"
    "                        if ok.sum() >= 10:\n"
    "                            depth_scale = float(np.median(z[ok])) / kf_cur.compute_points_median_depth(out.pts[ok])\n"
    "                            desired_median_depth = depth_scale * median_depth\n"
    "                            print(f\"E1: {ok.sum()} keypoints, median learned depth -> scale {depth_scale:.4f}\")\n"
)
assert s.count(old) == 1, f"expected the line once, found it {s.count(old)} times"
assert "pred_depth" not in s, "E1 is already in"
open(p, "w").write(s.replace(old, new))
print("E1 added to", p)
