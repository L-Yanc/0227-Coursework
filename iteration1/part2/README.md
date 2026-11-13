# part 2 - network depth on its own

Depth Anything V2 large on every frame, indoor model for fr3 and room0, outdoor for KITTI. Run on skate-l (RTX 4070). Depth factors: fr3 5000, room0 6553.5, KITTI 256.

- scores_fr3.csv, scores_room0.csv - per frame: AbsRel and delta<1.25 (metric and shape only), median_scale (true / predicted), median_depth, time
- scores_kitti.csv - per frame time and depth (KITTI has no true depth)
- summaries.txt - whole-sequence scores, and scores at ORB keypoints for nearest / bilinear / median
- part2_stability.png - median_scale along the sequence
- sigma_fr3.png, sigma_room0.png - sigma_d against the real error at keypoints
- sigma_fr3_keypoints.npz, sigma_room0_keypoints.npz - every keypoint: frame, u, v, d_pred, d_true, per-frame scale, gradient

Main numbers:
- fr3: metric AbsRel 0.16, shape only 0.06, median scale 0.89 (network about 12% too long), 0.27 s per frame
- room0: metric AbsRel 0.37, shape only 0.04, median scale 0.74 (about 35% too long), 0.37 s per frame
- KITTI: median depth 20.6 m (8 to 36 m per frame), 0.74 s per frame
- at keypoints the shape error is about 40% higher than over the whole image. nearest, bilinear and median are within 0.01 of each other, B uses median 5x5
- stability: fr3's scale goes from 0.65 to 1.15 along the sequence (only 0.7% frame to frame), room0 stays between 0.70 and 0.82
- worst fr3 frames: 1007 (scale 0.65) and 2022 (1.15), both close-ups
- sigma_d: the depth gradient works (the least trusted fifth of keypoints has 5 to 13x the error of the most trusted fifth). a fixed relative sigma doesn't

For Part 4: the keypoint npz files and scores_*.csv. The depth maps aren't here (too big), make them with the command in code/README.md
