
import argparse
import glob
import math
import os
import re
import sys


def rotation_to_quaternion(R):
    trace = R[0][0] + R[1][1] + R[2][2]
    if trace > 0:
        s = 2.0 * math.sqrt(trace + 1.0)
        qw, qx, qy, qz = 0.25 * s, (R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = 2.0 * math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2])
        qw, qx, qy, qz = (R[2][1] - R[1][2]) / s, 0.25 * s, (R[0][1] + R[1][0]) / s, (R[0][2] + R[2][0]) / s
    elif R[1][1] > R[2][2]:
        s = 2.0 * math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2])
        qw, qx, qy, qz = (R[0][2] - R[2][0]) / s, (R[0][1] + R[1][0]) / s, 0.25 * s, (R[1][2] + R[2][1]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1])
        qw, qx, qy, qz = (R[1][0] - R[0][1]) / s, (R[0][2] + R[2][0]) / s, (R[1][2] + R[2][1]) / s, 0.25 * s
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    q = [qx / n, qy / n, qz / n, qw / n]
    return [-v for v in q] if q[3] < 0 else q


def frame_numbers(folder, prefix, ext):
    numbers = []
    for path in glob.glob(os.path.join(folder, f"{prefix}*.{ext}")):
        m = re.fullmatch(rf"{prefix}(\d+)\.{ext}", os.path.basename(path))
        if m:
            numbers.append(int(m.group(1)))
    return sorted(numbers)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scene", help="the Replica scene folder (with results/ and traj.txt)")
    parser.add_argument("out", help="the folder to write (created if needed)")
    parser.add_argument("--fps", type=float, default=25.0, help="frames per second for the timestamps (default 25)")
    args = parser.parse_args()

    scene = os.path.abspath(os.path.expanduser(args.scene))
    out = os.path.abspath(os.path.expanduser(args.out))
    images = os.path.join(scene, "results")
    rgb = frame_numbers(images, "frame", "jpg")
    depth = frame_numbers(images, "depth", "png")
    with open(os.path.join(scene, "traj.txt")) as f:
        poses = [[float(v) for v in line.split()] for line in f if line.strip()]

    if not rgb or rgb != depth or rgb != list(range(len(rgb))):
        sys.exit(f"expected frame000000.jpg.. and depth000000.png.. with the same numbers, 0 to N-1, in {images}")
    if len(poses) != len(rgb) or any(len(p) != 16 for p in poses):
        sys.exit(f"expected one line of 16 numbers per frame in traj.txt: {len(poses)} lines, {len(rgb)} frames")

    os.makedirs(out, exist_ok=True)
    link = os.path.join(out, "results")
    if not os.path.lexists(link):
        os.symlink(os.path.relpath(images, out), link)
    elif os.path.realpath(link) != os.path.realpath(images):
        sys.exit(f"{link} exists and is not a link to {images}")

    stamps = [f"{i / args.fps:.6f}" for i in rgb]
    header = f"# Replica {os.path.basename(scene)}, written by replica_to_tum.py; timestamps i / {args.fps:g}\n"
    with open(os.path.join(out, "rgb.txt"), "w") as f:
        f.write(header + "# timestamp filename\n")
        f.writelines(f"{t} results/frame{i:06d}.jpg\n" for t, i in zip(stamps, rgb))
    with open(os.path.join(out, "depth.txt"), "w") as f:
        f.write(header + "# timestamp filename\n")
        f.writelines(f"{t} results/depth{i:06d}.png\n" for t, i in zip(stamps, rgb))
    with open(os.path.join(out, "associations.txt"), "w") as f:
        f.writelines(f"{t} results/frame{i:06d}.jpg {t} results/depth{i:06d}.png\n" for t, i in zip(stamps, rgb))
    with open(os.path.join(out, "groundtruth.txt"), "w") as f:
        f.write(header + "# timestamp tx ty tz qx qy qz qw\n")
        for t, p in zip(stamps, poses):
            q = rotation_to_quaternion([p[0:3], p[4:7], p[8:11]])
            f.write(f"{t} {p[3]:.9f} {p[7]:.9f} {p[11]:.9f} " + " ".join(f"{v:.9f}" for v in q) + "\n")

    print(f"{len(rgb)} frames, {len(rgb) / args.fps:.1f} s at {args.fps:g} fps -> {out}")


if __name__ == "__main__":
    main()
