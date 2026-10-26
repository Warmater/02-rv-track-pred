"""VoD three-frame teaching pipeline: inspect -> align -> visualize -> model tensors.

Run from anywhere: python vod_data_lab/preprocess.py
No detection/tracking/prediction model is trained here. Labels are used only for
inspection/visualization and are NOT embedded in inference inputs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parent / "数据集" / "view-of-delft-dataset-main" / "view-of-delft-dataset-main" / "example_set"
IDS = ("00549", "01047", "01201")
TARGET_SIZE = (484, 304)  # exactly 1/4 of VoD example images
MAX_POINTS = 512
BEV_X = (0.0, 50.0)  # forward in LiDAR frame, metres
BEV_Y = (-25.0, 25.0)  # left/right in LiDAR frame, metres
BEV_RES = 0.25


def load_bin(path: Path, width: int) -> np.ndarray:
    raw = np.fromfile(path, dtype="<f4")
    if raw.size % width:
        raise ValueError(f"{path}: float count {raw.size} is not divisible by {width}")
    arr = raw.reshape(-1, width)
    if not np.isfinite(arr).all():
        raise ValueError(f"{path}: contains NaN/Inf")
    return arr


def load_calib(path: Path) -> tuple[np.ndarray, np.ndarray]:
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, values = line.partition(":")
        if sep and values.strip():
            fields[key] = np.fromstring(values, sep=" ", dtype=np.float64)
    p = fields["P2"].reshape(3, 4)
    rect = fields["R0_rect"].reshape(3, 3)
    tr = np.eye(4, dtype=np.float64)
    tr[:3, :] = fields["Tr_velo_to_cam"].reshape(3, 4)
    r4 = np.eye(4, dtype=np.float64)
    r4[:3, :3] = rect
    return p, r4 @ tr  # sensor xyz -> rectified camera xyz


def transform(xyz: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    homo = np.concatenate((xyz.astype(np.float64), np.ones((len(xyz), 1))), axis=1)
    return (homo @ matrix.T)[:, :3]


def project(xyz_cam: np.ndarray, p: np.ndarray, size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Return float pixel coordinates and validity; never divide by nonpositive depth."""
    width, height = size
    homo = np.concatenate((xyz_cam, np.ones((len(xyz_cam), 1))), axis=1)
    uvw = homo @ p.T
    z = uvw[:, 2]
    front = z > 1e-6
    uv = np.full((len(xyz_cam), 2), np.nan)
    uv[front] = uvw[front, :2] / z[front, None]
    valid = front & (uv[:, 0] >= 0) & (uv[:, 0] < width) & (uv[:, 1] >= 0) & (uv[:, 1] < height)
    return uv, valid


def load_labels(path: Path) -> list[dict]:
    labels = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(labels, list):
        raise ValueError(f"{path}: expected a list")
    return labels


def load_kitti_boxes(path: Path) -> list[tuple[str, tuple[float, float, float, float]]]:
    # The provided KITTI 2D boxes are projections of 3D boxes, not manual 2D labels.
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cols = line.split()
        if len(cols) >= 8:
            boxes.append((cols[0], tuple(map(float, cols[4:8]))))
    return boxes


def load_pose(path: Path) -> dict[str, np.ndarray]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        for key, values in obj.items():
            result[key] = np.asarray(values, dtype=np.float64).reshape(4, 4)
    return result


def bev_counts(xyz_lidar: np.ndarray) -> np.ndarray:
    """Spatial bins only. This is a sensor-space occupancy feature, not camera BEV."""
    nx = int((BEV_X[1] - BEV_X[0]) / BEV_RES)
    ny = int((BEV_Y[1] - BEV_Y[0]) / BEV_RES)
    ix = np.floor((xyz_lidar[:, 0] - BEV_X[0]) / BEV_RES).astype(np.int32)
    iy = np.floor((xyz_lidar[:, 1] - BEV_Y[0]) / BEV_RES).astype(np.int32)
    good = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
    counts = np.zeros((nx, ny), dtype=np.uint16)
    np.add.at(counts, (ix[good], iy[good]), 1)
    return counts


def save_overlay(image: Image.Image, uv: np.ndarray, valid: np.ndarray, radar: np.ndarray,
                 boxes: list, path: Path) -> None:
    view = image.copy()
    draw = ImageDraw.Draw(view)
    for name, (x1, y1, x2, y2) in boxes:
        draw.rectangle((x1, y1, x2, y2), outline=(0, 255, 80), width=3)
        draw.text((x1, max(0, y1 - 14)), name, fill=(0, 255, 80))
    for idx in np.flatnonzero(valid):
        u, v = uv[idx]
        # compensated radial velocity: blue approaching/negative, red receding/positive
        speed = float(np.clip(radar[idx, 5] / 10, -1, 1))
        color = (int(255 * max(speed, 0)), 230 - int(100 * abs(speed)), int(255 * max(-speed, 0)))
        draw.ellipse((u - 4, v - 4, u + 4, v + 4), fill=color)
    view.thumbnail((968, 608))
    view.save(path)


def save_bev(counts: np.ndarray, labels: list[dict], path: Path) -> None:
    # Image rows go from far to near; image columns from negative y to positive y.
    heat = np.minimum(counts.astype(np.float32) * 95, 255).astype(np.uint8)
    rgb = np.zeros((*heat.shape, 3), dtype=np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = heat // 3, heat, heat
    img = Image.fromarray(rgb[::-1], "RGB").resize((800, 800), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(img)
    for metre in range(0, 51, 10):
        py = int((50 - metre) / 50 * 799)
        draw.line((0, py, 799, py), fill=(38, 38, 38), width=1)
        draw.text((5, max(0, py - 13)), f"x={metre}m", fill=(180, 180, 180))
    for metre in range(-20, 21, 10):
        px = int((metre + 25) / 50 * 799)
        draw.line((px, 0, px, 799), fill=(38, 38, 38), width=1)
        draw.text((px + 3, 3), f"y={metre}m", fill=(180, 180, 180))
    for obj in labels:
        c = obj["geometry"]["center"]  # JSON centers are in LiDAR xyz
        x, y = c["x"], c["y"]
        if BEV_X[0] <= x < BEV_X[1] and BEV_Y[0] <= y < BEV_Y[1]:
            px = (y - BEV_Y[0]) / (BEV_Y[1] - BEV_Y[0]) * 800
            py = (BEV_X[1] - x) / (BEV_X[1] - BEV_X[0]) * 800
            draw.ellipse((px - 5, py - 5, px + 5, py + 5), outline=(255, 225, 0), width=2)
    img.save(path)


def process(data: Path, output: Path, ids: tuple[str, ...], max_points: int = MAX_POINTS) -> dict:
    if max_points < 1:
        raise ValueError("max_points must be positive")
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    id_sets = {}
    for frame_id in ids:
        radar_root = data / "radar" / "training"
        lidar_root = data / "lidar" / "training"
        image = Image.open(radar_root / "image_2" / f"{frame_id}.jpg").convert("RGB")
        radar = load_bin(radar_root / "velodyne" / f"{frame_id}.bin", 7)
        lidar = load_bin(lidar_root / "velodyne" / f"{frame_id}.bin", 4)
        p, t_cam_radar = load_calib(radar_root / "calib" / f"{frame_id}.txt")
        _, t_cam_lidar = load_calib(lidar_root / "calib" / f"{frame_id}.txt")
        pose = load_pose(radar_root / "pose" / f"{frame_id}.json")
        labels = load_labels(radar_root / "label_2" / f"{frame_id}.json")
        boxes = load_kitti_boxes(lidar_root / "label_2" / f"{frame_id}.txt")
        if not np.allclose(p[:, :3], load_calib(lidar_root / "calib" / f"{frame_id}.txt")[0][:, :3]):
            raise ValueError(f"{frame_id}: camera intrinsics disagree")
        if not np.allclose(t_cam_radar[:3, :3].T @ t_cam_radar[:3, :3], np.eye(3), atol=1e-3):
            raise ValueError(f"{frame_id}: radar rotation is not orthogonal")
        radar_cam = transform(radar[:, :3], t_cam_radar)
        uv, valid = project(radar_cam, p, image.size)
        t_lidar_radar = np.linalg.inv(t_cam_lidar) @ t_cam_radar
        radar_lidar = transform(radar[:, :3], t_lidar_radar)
        counts = bev_counts(radar_lidar)
        save_overlay(image, uv, valid, radar, boxes, output / f"{frame_id}_overlay.png")
        save_bev(counts, labels, output / f"{frame_id}_radar_bev.png")

        # Model-ready example: image CHW, unnormalized uint8; sparse radar in LiDAR xyz.
        # A learned fusion model can encode image/radar separately, then sample camera
        # features at uv_full and fuse via concat/attention in one common coordinate frame.
        small = image.resize(TARGET_SIZE, Image.Resampling.BILINEAR)
        image_chw = np.asarray(small, dtype=np.uint8).transpose(2, 0, 1)
        features = np.zeros((max_points, 7), dtype=np.float32)
        uv_scaled = np.zeros((max_points, 2), dtype=np.float32)
        point_mask = np.zeros(max_points, dtype=bool)
        pixel_mask = np.zeros(max_points, dtype=bool)
        n = min(len(radar), max_points)
        chosen = np.linspace(0, len(radar) - 1, n, dtype=np.int64) if n else np.empty(0, dtype=np.int64)
        features[:n, :3] = radar_lidar[chosen].astype(np.float32)
        features[:n, 3:] = radar[chosen, 3:7]
        uv_scaled[:n] = np.nan_to_num(uv[chosen] * np.array(TARGET_SIZE) / np.array(image.size), nan=0).astype(np.float32)
        point_mask[:n] = True
        pixel_mask[:n] = valid[chosen]
        # A minimal, explicit point-to-pixel fusion example. RGB is sampled only
        # where geometric projection is valid; learned models normally sample
        # CNN feature maps instead of raw RGB and model alignment uncertainty.
        fused = np.zeros((max_points, 10), dtype=np.float32)
        fused[:, :7] = features
        source_rgb = np.asarray(image, dtype=np.uint8)
        good_indices = np.flatnonzero(pixel_mask)
        pixels = np.rint(uv[chosen[good_indices]]).astype(np.int32)
        pixels[:, 0] = np.clip(pixels[:, 0], 0, image.width - 1)
        pixels[:, 1] = np.clip(pixels[:, 1], 0, image.height - 1)
        fused[good_indices, 7:] = source_rgb[pixels[:, 1], pixels[:, 0]] / 255.0
        p_small = p.copy()
        p_small[0] *= TARGET_SIZE[0] / image.width
        p_small[1] *= TARGET_SIZE[1] / image.height
        np.savez_compressed(
            output / f"{frame_id}_model_input.npz",
            image_chw=image_chw, radar_lidar_features=features,
            fused_radar_rgb=fused,
            radar_point_mask=point_mask, radar_uv=uv_scaled, radar_in_image_mask=pixel_mask,
            projection_resized=p_small.astype(np.float32),
            T_camera_radar=t_cam_radar.astype(np.float32),
            T_camera_lidar=t_cam_lidar.astype(np.float32),
            radar_bev_count=counts,
        )
        id_sets[frame_id] = {o["objectId"] for o in labels}
        summary = {
            "frame": frame_id, "image_wh": list(image.size),
            "radar_points": len(radar), "radar_projected_in_image": int(valid.sum()),
            "radar_points_in_model": n, "radar_points_dropped_by_cap": len(radar) - n,
            "radar_time_ids": dict(sorted(Counter(str(int(x)) for x in radar[:, 6]).items())),
            "lidar_points": len(lidar), "labels": len(labels),
            "classes": dict(sorted(Counter(o["className"] for o in labels).items())),
            "radar_bev_occupied_cells": int((counts > 0).sum()),
            "pose_keys": sorted(pose), "model_image_chw": list(image_chw.shape),
            "model_radar_features": list(features.shape), "model_fused_features": list(fused.shape),
            "model_feature_order":
                ["x_lidar_m", "y_lidar_m", "z_lidar_m", "RCS", "v_r", "v_r_compensated", "time_id"],
            "fused_extra_features": ["sampled_R_0to1", "sampled_G_0to1", "sampled_B_0to1"],
        }
        summaries.append(summary)
    overlaps = {f"{a}-{b}": len(id_sets[a] & id_sets[b]) for i, a in enumerate(ids) for b in ids[i + 1:]}
    result = {"source": str(data.resolve()), "frames": summaries,
              "cross_frame_object_id_overlaps": overlaps,
              "note": "Sparse nonadjacent examples; no measured frame delta or tracking/prediction metric."}
    (output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="VoD example_set directory")
    parser.add_argument("--output", type=Path, default=HERE / "results")
    parser.add_argument("--frames", nargs="+", default=list(IDS))
    parser.add_argument("--max-points", type=int, default=MAX_POINTS)
    args = parser.parse_args()
    result = process(args.data, args.output, tuple(args.frames), args.max_points)
    print(json.dumps(result, ensure_ascii=False, indent=2))
