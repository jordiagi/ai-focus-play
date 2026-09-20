#!/usr/bin/env python3
"""D-B step 4 (remote) — ball CANDIDATES with positions, over the whole match.

G1 already settled the configuration and it is not the obvious one: full-frame
inference reaches 0.677 / 0.716 detection rate across the two halves and **fails the
0.70 gate on one of them**, while 3x2 tiling at imgsz 640 reaches 0.833 / 0.828 and
passes both. The ball is 8-15 px in a 1080p frame; tiling is the single change that
matters. This job reuses that measured configuration rather than re-deriving it.

The difference from `measure_ball.py` is that G1 only asked *was a candidate present*
and recorded the max confidence. Detection needs **where**, and it needs more than the
best guess: G1's own caveat is that `sports ball` at conf>0.05 fires on heads and line
markings too, so the top-1 candidate is not the ball. Keeping the top-K per frame is
what lets a later trajectory pass pick the track that moves like a ball instead of
trusting any single frame.

So: positions, top-K, with confidences, and NMS across the tile overlaps. No claim is
made here that any candidate IS the ball -- that is the next step's job, and it will be
scored.

In-play spans only, decoded in one ffmpeg pass per period (seeking per frame for
12k frames is what makes this slow).
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path


def tiles_for(w, h, pitch_top_frac, nx, ny, overlap):
    """G1's tiling, unchanged: overlapping tiles over the pitch region only."""
    top = int(h * pitch_top_frac)
    ph = h - top
    tw, th = w // nx, ph // ny
    ox, oy = int(tw * overlap), int(th * overlap)
    out = []
    for iy in range(ny):
        for ix in range(nx):
            x0 = max(0, ix * tw - ox)
            y0 = max(top, top + iy * th - oy)
            x1 = min(w, (ix + 1) * tw + ox)
            y1 = min(h, top + (iy + 1) * th + oy)
            out.append((x0, y0, x1, y1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--model", default="/opt/PnLCalib/yolo11x.pt")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--conf", type=float, default=0.05)
    ap.add_argument("--tile-imgsz", type=int, default=640)
    ap.add_argument("--nx", type=int, default=3)
    ap.add_argument("--ny", type=int, default=2)
    ap.add_argument("--overlap", type=float, default=0.15)
    ap.add_argument("--pitch-top", type=float, default=0.22)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--batch", type=int, default=48)
    ap.add_argument("--device", default="0")
    ap.add_argument("--frames-dir", default="/workspace/aifp/frames/ball")
    ap.add_argument("--p1", type=float, nargs=2, default=[562.3, 2879.3])
    ap.add_argument("--p2", type=float, nargs=2, default=[3674.4, 6132.1])
    a = ap.parse_args()

    run = Path(a.run_dir) if a.run_dir else None
    if run:
        run.mkdir(parents=True, exist_ok=True)
        (run / "pid").write_text(str(os.getpid()))

    def status(**kw):
        if run:
            (run / "status.json").write_text(json.dumps(kw))

    status(state="starting")
    import torch, cv2, numpy as np
    from ultralytics import YOLO

    dev = f"cuda:{a.device}" if torch.cuda.is_available() else "cpu"
    if dev.startswith("cuda"):
        torch.cuda.set_per_process_memory_fraction(0.30, int(a.device))

    fdir = Path(a.frames_dir)
    fdir.mkdir(parents=True, exist_ok=True)
    spans = [("p1", a.p1), ("p2", a.p2)]
    frames = []
    t_dec = time.time()
    for tag, (t0, t1) in spans:
        sub = fdir / tag
        sub.mkdir(exist_ok=True)
        if not any(sub.glob("*.jpg")):
            status(state="decoding", span=tag)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t0),
                            "-i", a.video, "-t", str(t1 - t0),
                            "-vf", f"fps={a.fps}", "-q:v", "3",
                            str(sub / "%06d.jpg")], check=True)
        for p in sorted(sub.glob("*.jpg")):
            i = int(p.stem) - 1
            frames.append((t0 + i / a.fps, str(p)))
    frames.sort()
    t_dec = time.time() - t_dec
    if not frames:
        print("no frames", file=sys.stderr)
        return 1

    model = YOLO(a.model)
    BALL = 32
    h, w = cv2.imread(frames[0][1]).shape[:2]
    tiles = tiles_for(w, h, a.pitch_top, a.nx, a.ny, a.overlap)
    status(state="detecting", done=0, n=len(frames), frames=len(frames))

    out = []
    t0 = time.time()
    # one frame's tiles form one batch: keeps peak memory flat and the mapping simple
    for k, (t, p) in enumerate(frames):
        img = cv2.imread(p)
        if img is None:
            continue
        crops = [img[y0:y1, x0:x1] for (x0, y0, x1, y1) in tiles]
        boxes, confs = [], []
        for i in range(0, len(crops), a.batch):
            sl = slice(i, i + a.batch)
            res = model.predict(crops[sl], imgsz=a.tile_imgsz, conf=a.conf,
                                classes=[BALL], device=dev, half=True, verbose=False)
            for (x0, y0, x1, y1), r in zip(tiles[sl], res):
                if r.boxes is None or len(r.boxes) == 0:
                    continue
                xy = r.boxes.xyxy.cpu().numpy()
                cf = r.boxes.conf.cpu().numpy()
                xy[:, [0, 2]] += x0
                xy[:, [1, 3]] += y0
                boxes.append(xy)
                confs.append(cf)
        cand = []
        if boxes:
            B = np.concatenate(boxes)
            Cf = np.concatenate(confs)
            keep = cv2.dnn.NMSBoxes(
                [[float(b[0]), float(b[1]), float(b[2] - b[0]), float(b[3] - b[1])]
                 for b in B], Cf.tolist(), a.conf, 0.45)
            idx = np.array(keep).ravel() if len(keep) else np.array([], int)
            order = idx[np.argsort(-Cf[idx])][:a.topk] if idx.size else idx
            for j in order:
                b = B[j]
                cand.append([round(float((b[0] + b[2]) / 2), 1),
                             round(float((b[1] + b[3]) / 2), 1),
                             round(float(b[2] - b[0]), 1),
                             round(float(Cf[j]), 4)])
        out.append({"t": round(t, 3), "c": cand})
        if k % 200 == 0:
            el = time.time() - t0
            status(state="detecting", done=k, n=len(frames),
                   elapsed=round(el, 1),
                   eta_s=round(el / max(k, 1) * (len(frames) - k), 1))

    any_c = sum(1 for o in out if o["c"])
    doc = {"job": "D-B step 4: ball candidates",
           "config": {"tiled": [a.nx, a.ny], "overlap": a.overlap,
                      "tile_imgsz": a.tile_imgsz, "conf": a.conf, "topk": a.topk,
                      "fps": a.fps, "frame_wh": [w, h]},
           "note": ("candidate presence is NOT ball correctness -- yolo 'sports ball' "
                    "at conf>0.05 also fires on heads and line markings (G1 caveat). "
                    "Trajectory association is a separate, scored step."),
           "frames": len(out),
           "frames_with_candidate": any_c,
           "candidate_rate": round(any_c / max(len(out), 1), 4),
           "decode_s": round(t_dec, 1), "detect_s": round(time.time() - t0, 1),
           "detections": out}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc))
    status(state="done", frames=len(out), candidate_rate=doc["candidate_rate"],
           detect_s=doc["detect_s"], out=a.out)
    print(json.dumps({k: v for k, v in doc.items() if k != "detections"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
