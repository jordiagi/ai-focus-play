# Tiled ball candidate detector (T-010)

`scripts/local/detect-ball-tiles.py` is an offline, local-CPU CLI that looks for small-ball **candidates** on a prepared video-only pilot clip by running the detector on the full frame and on an overlapping tile grid. It uses no labels and no pitch/label-informed crop: tiles cover the whole frame.

## Design

- **Tile grid** (`tile_grid`): `nx*ny` row-major tiles, size `ceil(L / (n - (n-1)*overlap))` per axis (exact `Fraction` math), clamped to the frame. Origins are spread by integer floor so the first tile starts at 0 and the last ends exactly at the frame edge; stride never exceeds tile size, so every pixel is covered, including non-divisible dimensions. Deterministic; rejects `nx,ny<1`, `overlap` outside `[0,1)`, or more tiles than pixels.
- **Per frame**: images = full frame + tiles, sent to `model.predict(classes=[32], device="cpu", verbose=False, imgsz, conf)`. The full frame is always predicted alone; tiles are grouped by identical shape and chunked to at most `BATCH_SIZE=6` images per call (bounds CPU memory, keeps preprocessing independent of chunking; a 3x2 grid is 1 + 1 calls). Non-ball classes from the model are ignored; non-finite confidences/boxes abort the run (nothing is written).
- **Merge**: tile boxes are offset to frame coordinates and clipped; degenerate boxes dropped. Global greedy NMS (`NMS_IOU=0.5`, suppress when IoU is greater) sorts by confidence desc, then bbox coordinates, then source (`full` before tile index), so output is independent of input order. Then `TOP_K=20` per frame.
- **Candidate record**: `bbox` xyxy, `cx`, `cy`, `size` (max side), `conf`, `source` (`"full"` or tile index), `frame`, `t = start_s + frame/fps`. Each frame keeps its own `w`/`h`; all decoded frames must share one size.
- **Validation before any decode/inference**: same pilot-manifest checks as `detect-video-pilot.py` (artifact type, `inference_performed False`, `video_only`, `evaluation_labels_used False`, 64-hex source sha, clip sha vs manifest, finite positive sampling), plus refusal of symlinked pilot/clip/manifest/weights, booleans as sampling values, and non-object clip/sampling/provenance fields (ValueError, not AttributeError). Output must be new and not a symlink (dangling links checked before resolve); weights must be an existing local `.pt`; the loaded model must map class 32 to `sports ball`. Reuses `sha256_file`, `local_path`, `load_model` (torch threads 2); cv2 threads set to 2, imported lazily.
- **Status**: without `--max-frames`, `complete` only if `|actual-expected| <= 1`; otherwise the run fails and writes nothing. With `--max-frames N` (smoke test) the manifest is `partial` with `coverage.frames_processed/expected_frames` and `stream_exhausted`, unless the whole stream was consumed and the same integrity check holds, in which case it is `complete`; an exhausted stream that fails the check stays `partial` (`frame_integrity.holds` false).
- **Writing**: outputs are written (exclusive `open("x")`, `allow_nan=False`) into a temporary sibling directory `.<out>.tmp-*`, then renamed to `--out`; the temp dir is removed on any failure. The rename never replaces files, but a rare race with another process creating an empty `--out` directory in between is not excluded.

## Outputs (`--out`, new directory)

- `ball_candidates.json`: per-frame candidates. **Schema differs from `detect-video-pilot.py`'s `ball_candidates.json`** (that uses `detections[].c = [[cx, cy, size, conf]]`; this uses `detections[].candidates[]` objects with `bbox`, `source`, etc.), so it is not a drop-in replacement; consumers need an adapter.
- `detection_manifest.json`: `artifact_type video_pilot_tiled_ball_candidates`, input provenance, pilot manifest/clip/model sha256, config (tile grid, NMS, top-k, batch size), versions, counts (raw vs after NMS), coverage, frame integrity, performance, limitations.

## Limits

- Candidates only: no events, possession, tracking or accuracy claims. Counts are not precision/recall; more tiles can raise false positives as well as recall. A precision/recall audit on independent labels is still required.
- Cost is roughly `(1 + nx*ny)` times full-frame inference per frame on CPU; use `--max-frames` for smoke tests.
- Tiles are cut at native resolution and then letterboxed to `imgsz`; ball-sized objects split by tile borders are only partly mitigated by the overlap. NMS is IoU-only, so partial fragments of one ball cut at an interior tile border (small IoU with the full-frame box) may survive as separate candidates.
- Provenance is producer-attested, not independent isolation proof. Fake-runtime unit tests do not exercise real cv2/Ultralytics.

## Run

```bash
YOLO_CONFIG_DIR=/tmp/aifp-yolo MPLCONFIGDIR=/tmp/aifp-mpl \
backend/.local/inference-venv/bin/python scripts/local/detect-ball-tiles.py \
  --pilot backend/.local/artifacts/video-only-pilot/skyline-900 \
  --weights backend/.local/models/yolo11n.pt \
  --out /tmp/aifp-ball-tiles-skyline --nx 3 --ny 2 --overlap 0.15 --imgsz 640 --conf 0.25 \
  [--max-frames 20]

backend/.venv/bin/python -m pytest backend/tests/unit/test_ball_tiles.py -q
```
