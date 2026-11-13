# adds B (+ the point log) to pyslam/slam/local_mapping.py (run from the pyslam folder)
p = "pyslam/slam/local_mapping.py"
s = open(p).read()
assert "pred_depth" not in s, "B is already in"

imp = "from pyslam.utilities.geom_triangulation import triangulate_normalized_points\n"
assert s.count(imp) == 1, "import line not found"
s = s.replace(imp, imp + "from pyslam.depth_estimation import pred_depth\n")

old = "new_pts_count, _, list_added_points = self.map.add_points("
n = s.count(old)
assert n >= 1, "add_points call not found"
s = s.replace(old, "new_pts_count, added_mask, list_added_points = self.map.add_points(")

old = "                self.local_mapping_core.add_points(list_added_points)\n"
assert s.count(old) == n, f"{s.count(old)} add_points(list_added_points) lines but {n} add_points calls"
s = s.replace(old, old + (
    "                if pred_depth.on():  # B: net depth for the matches with too little parallax\n"
    "                    list_b = pred_depth.fill_gaps(self.map, self.kf_cur, kf, idxs_cur, idxs, pts3d,\n"
    "                                                  added_mask, self.far_points_threshold)\n"
    "                    total_new_pts += len(list_b)\n"
    "                    self.local_mapping_core.add_points(list_b)\n"
))
open(p, "w").write(s)
print(f"B added to {p} ({n} place(s))")
