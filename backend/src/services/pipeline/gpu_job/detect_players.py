#!/usr/bin/env python3
"""D-B step 1 (remote) — player positions, for deriving the pitch WITHOUT metres.

D-B ships Tier A event detection in pixel space, which needs the pitch region and a
few zones. The standing rule is that zones are **derived, not drawn** -- no manual
annotation -- and calibration has failed five times, so they cannot come from metres
either.

Players are the answer: they are confined to the pitch, they cover it over 103 minutes,
and detecting them needs no labels of ours. Aggregated into panorama space (where
`frame -> panorama` is already solved) their occupancy outlines the playing surface,
and its density structure marks the goal mouths and the centre.

This job only produces the detections. The mapping and the aggregation happen locally
in `mosaic/build_occupancy_map.py`, because the panorama and the per-frame cameras live
there.

Samples only IN-PLAY time by default -- during the 795 s halftime the pitch is empty and
the people on it are warming up in one corner, which would bias the map.

Writes status.json in the run directory so `scripts/remote/job-status.sh` can poll it.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--weights", default="/opt/PnLCalib/yolo11x.pt")
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--imgsz", type=int, default=1536)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="0")
    ap.add_argument("--frames-dir", default="/workspace/aifp/frames/players")
    # in-play spans, measured from Veo's own API (see scripts/config.env)
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

    status(state="starting", t=time.time())

    span1 = a.p1[1] - a.p1[0]
    span2 = a.p2[1] - a.p2[0]
    n1 = int(round(a.n * span1 / (span1 + span2)))
    n2 = a.n - n1
    times = ([a.p1[0] + (i + 0.5) * span1 / n1 for i in range(n1)] +
             [a.p2[0] + (i + 0.5) * span2 / n2 for i in range(n2)])

    fdir = Path(a.frames_dir)
    fdir.mkdir(parents=True, exist_ok=True)
    paths = []
    status(state="extracting", n=len(times))
    for k, t in enumerate(times):
        p = fdir / f"{int(round(t * 1000)):08d}.jpg"
        if not p.exists():
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t),
                            "-i", a.video, "-frames:v", "1", "-q:v", "2", str(p)],
                           check=True)
        paths.append((t, str(p)))
        if k % 50 == 0:
            status(state="extracting", done=k, n=len(times))

    from ultralytics import YOLO
    model = YOLO(a.weights)
    status(state="detecting", done=0, n=len(paths))

    out, t_start = [], time.time()
    for i in range(0, len(paths), a.batch):
        chunk = paths[i:i + a.batch]
        res = model.predict([c[1] for c in chunk], imgsz=a.imgsz, conf=a.conf,
                            classes=[0], device=a.device, verbose=False)
        for (t, _), r in zip(chunk, res):
            b = r.boxes
            xy = b.xyxy.cpu().numpy().tolist() if b is not None else []
            cf = b.conf.cpu().numpy().tolist() if b is not None else []
            out.append({"t": round(t, 3),
                        "w": int(r.orig_shape[1]), "h": int(r.orig_shape[0]),
                        "boxes": [[round(v, 1) for v in box] + [round(c, 3)]
                                  for box, c in zip(xy, cf)]})
        status(state="detecting", done=min(i + a.batch, len(paths)), n=len(paths),
               elapsed=round(time.time() - t_start, 1))

    npers = sum(len(o["boxes"]) for o in out)
    doc = {"job": "D-B step 1: player detections",
           "weights": a.weights, "imgsz": a.imgsz, "conf": a.conf,
           "frames": len(out), "persons": npers,
           "persons_per_frame_median": sorted(len(o["boxes"]) for o in out)[len(out) // 2],
           "in_play_spans": [a.p1, a.p2],
           "seconds": round(time.time() - t_start, 1),
           "detections": out}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc))
    status(state="done", frames=len(out), persons=npers,
           seconds=round(time.time() - t_start, 1), out=a.out)
    print(json.dumps({k: v for k, v in doc.items() if k != "detections"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
