#!/usr/bin/env python3
"""Generates colab_match_analysis.ipynb.

Editing notebook JSON by hand is miserable and merges badly, so the notebook is a
build artifact of this script. Change cells here, re-run, commit both.
"""
import json
from pathlib import Path

C = []


def md(src):
    C.append({"cell_type": "markdown", "metadata": {}, "source": src.strip().splitlines(True)})


def code(src):
    C.append({"cell_type": "code", "execution_count": None, "metadata": {},
              "outputs": [], "source": src.strip().splitlines(True)})


md("""
# Match analysis — checkpointed, resumable, free-tier safe

Runs YOLO + ByteTrack over the full match and writes **per-chunk checkpoints to Drive**.

**Why chunked:** Colab free disconnects after ~90 min idle and gives no runtime guarantee.
Every chunk is written to Drive as it finishes, so a disconnect costs you *one chunk*, not the run.
Re-running this notebook skips everything already done.

**Order:** run cells top to bottom. To resume after a disconnect, just run them all again.
""")

# ---------------------------------------------------------------- 1. runtime
md("## 1. Runtime check\n\nIf this reports no GPU, use Runtime → Change runtime type → GPU before continuing.")
code("""
import subprocess, sys
print(subprocess.run(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader"],
                     capture_output=True, text=True).stdout.strip() or "NO GPU - switch runtime type")
!pip -q install ultralytics lap >/dev/null 2>&1
import ultralytics; print("ultralytics", ultralytics.__version__)
""")

# ---------------------------------------------------------------- 2. config
md("## 2. Config and Drive\n\n`VIDEO_GLOB` searches Drive so you don't have to hardcode the path.")
code("""
from google.colab import drive
drive.mount('/content/drive')

from pathlib import Path
import os, json, time

VIDEO_GLOB  = "**/arlington*skyline*.mp4"     # adjust if you renamed it
DRIVE_ROOT  = Path("/content/drive/MyDrive")
OUT_DIR     = DRIVE_ROOT / "match_analysis"   # checkpoints land here
CHUNK_SEC   = 120                              # seconds of video per checkpoint
OVERLAP_SEC = 5                                # overlap so tracks survive chunk seams
SAMPLE_FPS  = 5                                # frames per second actually analysed
MODEL       = "yolo11n.pt"                     # n=nano. Bump to s/m if GPU allows.
CONF        = 0.25
IMGSZ       = 1280                             # players are small in a wide pitch shot

OUT_DIR.mkdir(parents=True, exist_ok=True)

matches = sorted(DRIVE_ROOT.glob(VIDEO_GLOB))
assert matches, f"No video matched {VIDEO_GLOB} under {DRIVE_ROOT}"
VIDEO = matches[0]
print("video:", VIDEO, f"({VIDEO.stat().st_size/1e9:.2f} GB)")
print("out:  ", OUT_DIR)
""")

# ---------------------------------------------------------------- 3. probe
md("## 3. Probe the video and plan chunks")
code("""
import cv2, math
cap = cv2.VideoCapture(str(VIDEO))
assert cap.isOpened(), "could not open video"
FPS      = cap.get(cv2.CAP_PROP_FPS)
NFRAMES  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H        = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
DURATION = NFRAMES / FPS
cap.release()

CHUNKS = []
t = 0.0
while t < DURATION:
    CHUNKS.append((len(CHUNKS), t, min(t + CHUNK_SEC, DURATION)))
    t += CHUNK_SEC

print(f"{W}x{H} @ {FPS:.2f}fps  {DURATION/60:.1f} min  {NFRAMES:,} frames")
print(f"{len(CHUNKS)} chunks of {CHUNK_SEC}s, analysing at {SAMPLE_FPS}fps "
      f"-> ~{int(DURATION*SAMPLE_FPS):,} frames total")
""")

# ---------------------------------------------------------------- 4. core
md("""
## 4. Detection + tracking, checkpointed

Each chunk writes `chunk_XXXX.jsonl` to Drive the moment it finishes. Already-present
chunks are skipped, so re-running resumes.

Track IDs are **chunk-local** — ByteTrack is reset per chunk. The `OVERLAP_SEC` window
lets a later step stitch identities across seams if needed. Don't treat a track id as
globally unique without doing that stitching.
""")
code("""
from ultralytics import YOLO
import numpy as np

model = YOLO(MODEL)
PERSON, BALL = 0, 32          # COCO class ids

def chunk_path(i): return OUT_DIR / f"chunk_{i:04d}.jsonl"

def process_chunk(idx, t0, t1):
    out = chunk_path(idx)
    if out.exists() and out.stat().st_size > 0:
        return "skip"

    cap = cv2.VideoCapture(str(VIDEO))
    start = max(0.0, t0 - (OVERLAP_SEC if idx else 0))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start * FPS))
    step = max(1, int(round(FPS / SAMPLE_FPS)))

    tmp, n = out.with_suffix(".part"), 0
    model.predictor = None                     # reset tracker state per chunk
    with open(tmp, "w") as fh:
        f = int(start * FPS)
        while f < int(t1 * FPS):
            ok, frame = cap.read()
            if not ok: break
            if (f - int(start*FPS)) % step == 0:
                r = model.track(frame, persist=True, conf=CONF, imgsz=IMGSZ,
                                classes=[PERSON, BALL], tracker="bytetrack.yaml",
                                verbose=False)[0]
                dets = []
                if r.boxes is not None and r.boxes.id is not None:
                    for b, cid, tid, cf in zip(r.boxes.xywh.cpu().numpy(),
                                               r.boxes.cls.cpu().numpy(),
                                               r.boxes.id.cpu().numpy(),
                                               r.boxes.conf.cpu().numpy()):
                        dets.append({"tid": int(tid), "cls": int(cid),
                                     "x": round(float(b[0]),1), "y": round(float(b[1]),1),
                                     "w": round(float(b[2]),1), "h": round(float(b[3]),1),
                                     "conf": round(float(cf),3)})
                fh.write(json.dumps({"t": round(f/FPS,3), "det": dets}) + "\\n")
                n += 1
            f += 1
    cap.release()
    tmp.rename(out)                            # atomic: a partial file is never mistaken for done
    return n

done = sum(1 for i,_,_ in CHUNKS if chunk_path(i).exists())
print(f"resuming: {done}/{len(CHUNKS)} chunks already complete")

t_start = time.time()
for idx, t0, t1 in CHUNKS:
    r = process_chunk(idx, t0, t1)
    if r != "skip":
        el = time.time() - t_start
        remaining = len(CHUNKS) - idx - 1
        print(f"chunk {idx:4d}/{len(CHUNKS)}  {r:5} frames  "
              f"elapsed {el/60:5.1f}m  eta {el/(idx+1)*remaining/60:5.1f}m", flush=True)
print("ALL CHUNKS COMPLETE")
""")

# ---------------------------------------------------------------- 5. consolidate
md("## 5. Consolidate\n\nMerges chunks into one table and drops the overlap duplicates.")
code("""
import pandas as pd

rows = []
for i,_,_ in CHUNKS:
    p = chunk_path(i)
    if not p.exists(): continue
    for line in p.read_text().splitlines():
        rec = json.loads(line)
        for d in rec["det"]:
            rows.append({"t": rec["t"], "chunk": i, **d})

df = pd.DataFrame(rows).drop_duplicates(subset=["t","tid","cls","x","y"])
df = df.sort_values("t").reset_index(drop=True)
df.to_parquet(OUT_DIR / "detections.parquet")
print(f"{len(df):,} detections  |  {df.t.min():.1f}s - {df.t.max():.1f}s")
print(df.cls.value_counts().rename({0:"person",32:"ball"}))
""")

# ---------------------------------------------------------------- 6. ball
md("""
## 6. Ball track

COCO `sports ball` on a wide pitch shot is a weak detector — expect gaps. Gaps are
kept as gaps. Interpolating across them would invent a trajectory, and every event
downstream would inherit the fiction.
""")
code("""
ball = df[df.cls == 32].sort_values("t")
ball = ball.loc[ball.groupby("t")["conf"].idxmax()]     # best candidate per frame
grid = pd.DataFrame({"t": sorted(df.t.unique())})
ball = grid.merge(ball[["t","x","y","conf"]], on="t", how="left")
ball["detected"] = ball.x.notna()
print(f"ball detected on {ball.detected.mean()*100:.1f}% of sampled frames")
ball.to_parquet(OUT_DIR / "ball.parquet")
""")

# ---------------------------------------------------------------- 7. score
md("""
## 7. Score against the Veo benchmark

Upload `benchmarks/veo_reference.json` from the repo to Drive first, or paste it in.

This reports hits **and** misses. A clean sweep here usually means the tolerance is
too loose or the benchmark was used for tuning — say so if it was.
""")
code("""
BENCH = OUT_DIR / "veo_reference.json"
if not BENCH.exists():
    print("No benchmark at", BENCH, "- upload it to score. Skipping.")
else:
    bench = json.loads(BENCH.read_text())
    attempts = bench["home_shot_map"]["attempts"]
    TOL = 30.0     # seconds; see scoring_protocol - 2nd-half offset carries +/-40s

    # Candidate attempts: sharp ball acceleration toward either goal mouth.
    b = ball.dropna(subset=["x","y"]).copy()
    b["dt"] = b.t.diff(); b["dx"] = b.x.diff(); b["dy"] = b.y.diff()
    b["speed_px"] = ((b.dx**2 + b.dy**2)**0.5) / b.dt.replace(0, float("nan"))
    thresh = b.speed_px.quantile(0.97)
    cands = b[b.speed_px > thresh].t.tolist()
    merged = [c for i,c in enumerate(cands) if i==0 or c - cands[i-1] > 10]

    print(f"{len(merged)} candidate attempts from ball motion (p97 speed)\\n")
    hits = 0
    for a in attempts:
        near = [c for c in merged if abs(c - a["video_s"]) <= TOL]
        ok = bool(near)
        hits += ok
        print(f"  {'HIT ' if ok else 'MISS'}  {a['type']:5} {a['t']} "
              f"(video {a['video_s']}s)" + (f"  <- cand {near[0]:.1f}s" if ok else ""))
    print(f"\\nrecall {hits}/{len(attempts)} = {hits/len(attempts)*100:.0f}%")
    fp = [c for c in merged if not any(abs(c-a['video_s'])<=TOL for a in attempts)]
    print(f"unmatched candidates (possible false positives OR away-side attempts "
          f"the benchmark cannot score): {len(fp)}")
""")

# ---------------------------------------------------------------- 8. export
md("## 8. Export\n\nEverything already lives in Drive. This just reports what's there.")
code("""
for p in sorted(OUT_DIR.iterdir()):
    if p.is_file() and not p.name.startswith("chunk_"):
        print(f"{p.name:28} {p.stat().st_size/1e6:8.2f} MB")
print(f"\\n{len(list(OUT_DIR.glob('chunk_*.jsonl')))} chunk files")
print("Download detections.parquet + ball.parquet for local ingest.")
""")

nb = {"cells": C, "nbformat": 4, "nbformat_minor": 0,
      "metadata": {"colab": {"provenance": [], "toc_visible": True},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"},
                   "accelerator": "GPU"}}

out = Path(__file__).parent / "colab_match_analysis.ipynb"
out.write_text(json.dumps(nb, indent=1))
print("wrote", out, f"({len(C)} cells)")
