#!/usr/bin/env python3
"""G1 — measure ball-detection rate on a slice of the real match.

This is the go/no-go gate for the whole possession-derived half of the roadmap
(Pass / Interception / Tackle / Loose ball / Dribble, plus Possession% and
Passes completed). The gate was declared BEFORE measuring, in PLAN.md:

    ball detected in >=70% of in-play sampled frames,
    median gap <=0.4 s,
    >=85% of possession transitions with >=3 attributed samples on both sides

The third clause needs a possession model that does not exist yet, so this job
measures the first two and reports them honestly whatever they are. It does not
decide anything; it produces the number the decision is made on.

Deliberately compares two configurations, because the difference IS the finding:
  * full-frame inference at imgsz -- what the Colab notebook effectively did
  * tiled inference over the pitch region -- the ball is 8-15 px in a 1080p
    frame, so tiling is the single change most likely to matter

Writes coverage.json. Ships the number even when the number is bad.
"""
import argparse, json, math, os, subprocess, sys, time
from pathlib import Path


def extract_frames(video, out_dir, t0, t1, fps):
    """Decode a slice to JPEGs. CPU decode is ~750 fps on 8 cores, so this is free."""
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("*.jpg"))
    if existing:
        return existing
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t0), "-i", str(video),
           "-t", str(t1 - t0), "-vf", f"fps={fps}", "-q:v", "3",
           str(out_dir / "%06d.jpg")]
    subprocess.run(cmd, check=True)
    return sorted(out_dir.glob("*.jpg"))


def tiles_for(w, h, pitch_top_frac, nx, ny, overlap):
    """Overlapping tiles over the pitch region (crowd/sky above is wasted compute)."""
    top = int(h * pitch_top_frac)
    ph = h - top
    tw, th = w // nx, ph // ny
    ox, oy = int(tw * overlap), int(th * overlap)
    out = []
    for iy in range(ny):
        for ix in range(nx):
            x0 = max(0, ix * tw - ox); y0 = max(top, top + iy * th - oy)
            x1 = min(w, (ix + 1) * tw + ox); y1 = min(h, top + (iy + 1) * th + oy)
            out.append((x0, y0, x1, y1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--model", default="yolo11x.pt")
    ap.add_argument("--conf", type=float, default=0.05)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--tile-imgsz", type=int, default=640)
    ap.add_argument("--nx", type=int, default=3)
    ap.add_argument("--ny", type=int, default=2)
    ap.add_argument("--overlap", type=float, default=0.15)
    ap.add_argument("--pitch-top", type=float, default=0.22,
                    help="fraction of frame height above the pitch (crowd/sky)")
    ap.add_argument("--frames-dir", default="/workspace/aifp/frames/g1")
    ap.add_argument("--out", default="/workspace/aifp/out/coverage.json")
    ap.add_argument("--device", default="0")
    ap.add_argument("--batch", type=int, default=32)
    a = ap.parse_args()

    import torch
    from ultralytics import YOLO
    import numpy as np
    import cv2

    dev = f"cuda:{a.device}" if torch.cuda.is_available() else "cpu"
    if dev.startswith("cuda"):
        # Good neighbour: Ollama holds ~25 GB/GPU on this box for qwen3.8 + mistral.
        torch.cuda.set_per_process_memory_fraction(0.30, int(a.device))

    t_start = time.time()
    frames = extract_frames(Path(a.video), Path(a.frames_dir), a.t0, a.t1, a.fps)
    t_decode = time.time() - t_start
    if not frames:
        print("no frames extracted", file=sys.stderr); return 1

    model = YOLO(a.model)
    BALL = 32  # COCO 'sports ball'
    h, w = cv2.imread(str(frames[0])).shape[:2]
    tiles = tiles_for(w, h, a.pitch_top, a.nx, a.ny, a.overlap)

    def run_full(paths):
        hits = []
        for i in range(0, len(paths), a.batch):
            chunk = [str(p) for p in paths[i:i + a.batch]]
            for r in model.predict(chunk, imgsz=a.imgsz, conf=a.conf, classes=[BALL],
                                   device=dev, half=True, verbose=False):
                c = r.boxes.conf.cpu().numpy() if r.boxes is not None else np.array([])
                hits.append(float(c.max()) if c.size else 0.0)
        return hits

    def run_tiled(paths):
        hits = []
        for p in paths:
            img = cv2.imread(str(p))
            crops = [img[y0:y1, x0:x1] for (x0, y0, x1, y1) in tiles]
            best = 0.0
            for i in range(0, len(crops), a.batch):
                for r in model.predict(crops[i:i + a.batch], imgsz=a.tile_imgsz,
                                       conf=a.conf, classes=[BALL], device=dev,
                                       half=True, verbose=False):
                    c = r.boxes.conf.cpu().numpy() if r.boxes is not None else np.array([])
                    if c.size:
                        best = max(best, float(c.max()))
            hits.append(best)
        return hits

    results = {}
    for name, fn in (("full_frame", run_full), ("tiled", run_tiled)):
        t0 = time.time()
        conf = fn(frames)
        elapsed = time.time() - t0
        det = [c > 0 for c in conf]
        rate = sum(det) / len(det)
        # gap lengths, in seconds, between consecutive detections
        gaps, run = [], 0
        for d in det:
            if d:
                if run: gaps.append(run / a.fps)
                run = 0
            else:
                run += 1
        if run: gaps.append(run / a.fps)
        gaps_sorted = sorted(gaps)
        med = gaps_sorted[len(gaps_sorted) // 2] if gaps_sorted else 0.0
        results[name] = {
            "detection_rate": round(rate, 4),
            "frames": len(det),
            "detected": int(sum(det)),
            "median_gap_s": round(med, 3),
            "max_gap_s": round(max(gaps), 3) if gaps else 0.0,
            "n_gaps": len(gaps),
            "mean_conf_when_detected": round(
                float(np.mean([c for c in conf if c > 0])) if any(det) else 0.0, 4),
            "seconds": round(elapsed, 1),
            "fps_throughput": round(len(det) / elapsed, 1) if elapsed else None,
        }

    gate = {
        "declared_before_measuring": True,
        "requires": {"detection_rate": ">=0.70", "median_gap_s": "<=0.4"},
        "tiled_passes": (results["tiled"]["detection_rate"] >= 0.70
                         and results["tiled"]["median_gap_s"] <= 0.4),
        "note": ("The third gate clause (>=85% of possession transitions with >=3 "
                 "attributed samples each side) needs a possession model that does not "
                 "exist yet and is NOT evaluated here."),
    }
    doc = {
        "job": "G1 ball-detection measurement",
        "video": a.video, "slice_s": [a.t0, a.t1], "sample_fps": a.fps,
        "model": a.model, "conf": a.conf,
        "full_frame_imgsz": a.imgsz, "tile_imgsz": a.tile_imgsz,
        "tiles": f"{a.nx}x{a.ny} overlap {a.overlap} above y={a.pitch_top:.2f}h",
        "device": dev, "decode_seconds": round(t_decode, 1),
        "results": results, "gate": gate,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
