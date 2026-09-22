#!/usr/bin/env python3
"""D-B step 14 (remote) — players at chosen times, with a shirt-colour descriptor.

Throw-in team needs **possession** -- who touched the ball last -- and both cheaper cues
are measured dead: team is ~50/50 in every (end, period) cell, and post-throw ball
direction is a coin flip (17/35). Possession needs players assigned to sides, which
needs shirt colour.

Two things make this cheaper than it sounds:

* **The kits are white against dark navy on uniform green turf** -- viewed, not assumed.
  About as separable as a kit pair gets.
* **No registration is needed.** `ball5.json` holds ball candidates in *frame*
  coordinates, so detecting players on those same frames puts ball and players in one
  space already. The panorama is not involved.

Differences from `detect_players.py`, which sampled 600 evenly-spaced in-play frames to
build the occupancy cloud:

* times come from a **file**, so the frames are the ones events actually happen at
* every box carries a **shirt patch descriptor** -- median BGR / Lab / HSV over the
  upper torso, plus the patch's own spread so a box that is half grass can be rejected

The patch is the upper torso rather than the whole box: a full-box average is mostly
shorts, socks and grass, and at this distance a player is ~20 px tall, so the shirt is
only a few rows. `--shirt-band` and `--shirt-inset` control it.

Writes status.json in the run directory so `scripts/remote/job-status.sh` can poll it.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

import numpy as np


def shirt_descriptor(img, box, band, inset):
    """Median colour of the upper-torso patch, plus how uniform that patch is."""
    import cv2
    x1, y1, x2, y2 = box[:4]
    w, h = x2 - x1, y2 - y1
    if w < 2 or h < 4:
        return None
    ya = int(round(y1 + band[0] * h))
    yb = int(round(y1 + band[1] * h))
    xa = int(round(x1 + inset * w))
    xb = int(round(x2 - inset * w))
    ya, yb = max(ya, 0), min(yb, img.shape[0])
    xa, xb = max(xa, 0), min(xb, img.shape[1])
    if yb - ya < 1 or xb - xa < 1:
        return None
    patch = img[ya:yb, xa:xb]
    if patch.size == 0:
        return None
    bgr = np.median(patch.reshape(-1, 3), axis=0)
    px = np.uint8([[bgr]])
    lab = cv2.cvtColor(px, cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    hsv = cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0].astype(float)
    # spread: a patch that is half grass, half shirt is not a shirt colour
    spread = float(np.median(np.abs(patch.reshape(-1, 3) - bgr).sum(axis=1)))
    return {"bgr": [round(float(v), 1) for v in bgr],
            "lab": [round(float(v), 1) for v in lab],
            "hsv": [round(float(v), 1) for v in hsv],
            "spread": round(spread, 1), "px": int(patch.shape[0] * patch.shape[1])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--times", required=True, help="JSON list of video-time seconds")
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--weights", default="/opt/PnLCalib/yolo11x.pt")
    ap.add_argument("--imgsz", type=int, default=1536)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="0")
    ap.add_argument("--frames-dir", default="/workspace/aifp/frames/colour")
    ap.add_argument("--shirt-band", type=float, nargs=2, default=[0.15, 0.45],
                    help="vertical band of the box to sample, as fractions of height")
    ap.add_argument("--shirt-inset", type=float, default=0.20,
                    help="horizontal inset each side, as a fraction of width")
    a = ap.parse_args()

    import cv2
    run = Path(a.run_dir) if a.run_dir else None
    if run:
        run.mkdir(parents=True, exist_ok=True)
        (run / "pid").write_text(str(os.getpid()))

    def status(**kw):
        if run:
            (run / "status.json").write_text(json.dumps(kw))

    times = sorted(set(round(float(t), 2) for t in json.loads(Path(a.times).read_text())))
    status(state="starting", n=len(times), t=time.time())

    fdir = Path(a.frames_dir)
    fdir.mkdir(parents=True, exist_ok=True)
    paths, t0 = [], time.time()
    for k, t in enumerate(times):
        p = fdir / f"{int(round(t * 1000)):08d}.jpg"
        if not p.exists():
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t),
                            "-i", a.video, "-frames:v", "1", "-q:v", "2", str(p)],
                           check=True)
        if p.exists():
            paths.append((t, str(p)))
        if k % 25 == 0:
            status(state="extracting", done=k, n=len(times),
                   elapsed=round(time.time() - t0, 1))

    from ultralytics import YOLO
    model = YOLO(a.weights)
    status(state="detecting", done=0, n=len(paths))

    out, t_start = [], time.time()
    for i in range(0, len(paths), a.batch):
        chunk = paths[i:i + a.batch]
        res = model.predict([c[1] for c in chunk], imgsz=a.imgsz, conf=a.conf,
                            classes=[0], device=a.device, verbose=False)
        for (t, path), r in zip(chunk, res):
            b = r.boxes
            xy = b.xyxy.cpu().numpy().tolist() if b is not None else []
            cf = b.conf.cpu().numpy().tolist() if b is not None else []
            img = cv2.imread(path)
            boxes = []
            for box, c in zip(xy, cf):
                d = shirt_descriptor(img, box, a.shirt_band, a.shirt_inset) if img is not None else None
                boxes.append({"box": [round(v, 1) for v in box], "conf": round(c, 3),
                              "shirt": d})
            out.append({"t": round(t, 3), "w": int(r.orig_shape[1]),
                        "h": int(r.orig_shape[0]), "boxes": boxes})
        status(state="detecting", done=min(i + a.batch, len(paths)), n=len(paths),
               elapsed=round(time.time() - t_start, 1))

    npers = sum(len(o["boxes"]) for o in out)
    doc = {"job": "D-B step 14: players with shirt colour, at chosen times",
           "weights": a.weights, "imgsz": a.imgsz, "conf": a.conf,
           "shirt_band": a.shirt_band, "shirt_inset": a.shirt_inset,
           "frames": len(out), "persons": npers,
           "persons_per_frame_median": (sorted(len(o["boxes"]) for o in out)[len(out) // 2]
                                        if out else 0),
           "with_shirt": sum(1 for o in out for b in o["boxes"] if b["shirt"]),
           "seconds": round(time.time() - t_start, 1),
           "detections": out}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc))
    status(state="done", frames=len(out), persons=npers, out=a.out,
           seconds=round(time.time() - t_start, 1))
    print(json.dumps({k: v for k, v in doc.items() if k != "detections"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
