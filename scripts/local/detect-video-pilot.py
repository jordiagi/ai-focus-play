#!/usr/bin/env python3
"""Detect people and ball candidates in a prepared local clip, on CPU only.

Requires an explicit existing local checkpoint and an optional Ultralytics runtime.
Outputs object detections, not events, team assignments or match analytics.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def local_path(value):
    value = str(value)
    if not value.strip() or "://" in value or value.startswith(("http:", "https:", "file:", "ssh:", "ftp:")):
        raise ValueError("expected a local filesystem path, not a URL")
    return Path(value).expanduser().resolve()


def load_model(weights):
    # Imports are lazy so validation/tests work without inference dependencies.
    try:
        import torch
        import ultralytics
        from ultralytics import YOLO
    except ImportError as exc:
        raise ValueError("install torch and ultralytics in a local inference environment first") from exc
    torch.set_num_threads(2)
    return YOLO(str(weights)), {"ultralytics": ultralytics.__version__, "torch": torch.__version__}


def detect_pilot(pilot, weights, out, imgsz=640, conf=.25):
    pilot = local_path(pilot)
    weights = local_path(weights)
    # Check the user-supplied path before resolving it, including dangling links.
    if Path(out).expanduser().is_symlink():
        raise ValueError("output directory must be new; refusing overwrite")
    output = local_path(out)
    if not weights.is_file() or weights.suffix.lower() != ".pt":
        raise ValueError("--weights requires an existing local .pt checkpoint; downloads are disabled")
    if output.exists() or output.is_symlink():
        raise ValueError("output directory must be new; refusing overwrite")
    if not isinstance(imgsz, int) or imgsz <= 0 or not math.isfinite(conf) or not 0 <= conf <= 1:
        raise ValueError("imgsz must be positive and confidence must lie in [0, 1]")
    clip = pilot / "clip.mp4"
    prep_path = pilot / "pilot_manifest.json"
    if not clip.is_file() or not prep_path.is_file():
        raise ValueError("pilot requires clip.mp4 and pilot_manifest.json")
    prep = json.loads(prep_path.read_text())
    provenance = prep.get("input_provenance", {})
    if (prep.get("artifact_type") != "video_pilot_preparation" or
            prep.get("inference_performed") is not False or
            provenance.get("mode") != "video_only" or provenance.get("evaluation_labels_used") is not False):
        raise ValueError("pilot manifest must attest video-only preparation without inference or evaluation labels")
    source_hash = provenance.get("video_sha256", "")
    if not isinstance(source_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", source_hash):
        raise ValueError("invalid source video SHA256 attestation")
    clip_hash = sha256_file(clip)
    if clip_hash != prep.get("clip", {}).get("sha256"):
        raise ValueError("clip hash differs from preparation manifest")
    sampling = prep.get("sampling", {})
    try:
        start, fps, duration = (float(sampling.get(key, float("nan"))) for key in ("start_s", "fps", "duration_s"))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid pilot sampling values") from exc
    if not all(math.isfinite(value) for value in (start, fps, duration)) or start < 0 or fps <= 0 or duration <= 0:
        raise ValueError("pilot sampling must specify finite source start, positive fps and duration")
    model_hash = sha256_file(weights)
    model, versions = load_model(weights)
    names = getattr(model, "names", None)
    try:
        class_names = {index: names[index] for index in (0, 32)}
    except (TypeError, KeyError, IndexError) as exc:
        raise ValueError("checkpoint must map class 0 to person and class 32 to sports ball") from exc
    if class_names != {0: "person", 32: "sports ball"}:
        raise ValueError("checkpoint must map class 0 to person and class 32 to sports ball")
    expected_frames = duration * fps
    if not math.isfinite(expected_frames):
        raise ValueError("invalid expected sampling frame count")
    config = {"device": "cpu", "threads": 2, "imgsz": imgsz, "conf": conf,
              "classes": [0, 32], "stream": True, "save": False, "verbose": False}
    started = time.perf_counter()
    players, ball = [], []
    person_count = ball_count = frames_with_ball = 0
    for index, result in enumerate(model.predict(source=str(clip), **{k: v for k, v in config.items() if k != "threads"})):
        timestamp = start + index / fps
        height, width = result.orig_shape
        people, candidates = [], []
        if result.boxes is not None:
            coordinates = result.boxes.xyxy.cpu().tolist()
            confidences = result.boxes.conf.cpu().tolist()
            classes = result.boxes.cls.cpu().tolist()
            for box, confidence, class_id in zip(coordinates, confidences, classes):
                box = [float(value) for value in box]
                if int(class_id) == 0:
                    people.append({"box": box, "conf": float(confidence)})
                elif int(class_id) == 32:
                    x1, y1, x2, y2 = box
                    candidates.append([(x1 + x2) / 2, (y1 + y2) / 2,
                                       max(x2 - x1, y2 - y1), float(confidence)])
        players.append({"t": timestamp, "w": int(width), "h": int(height), "boxes": people})
        ball.append({"t": timestamp, "c": candidates})
        person_count += len(people)
        ball_count += len(candidates)
        frames_with_ball += bool(candidates)
    elapsed = time.perf_counter() - started
    if not players:
        raise ValueError("model returned no decoded frames")
    if abs(len(players) - expected_frames) > 1 + 1e-9:
        raise ValueError(f"decoded frame count {len(players)} differs from expected {expected_frames:g}; "
                         "source-clock timestamps cannot be trusted")
    object_provenance = {"mode": "video_only", "evaluation_labels_used": False,
                         "video_sha256": source_hash, "clip_sha256": clip_hash,
                         "attestation": "producer_attested_not_independent_isolation_proof"}
    manifest = {"schema_version": 1, "artifact_type": "video_pilot_object_detections",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "input_provenance": object_provenance, "pilot_manifest_sha256": sha256_file(prep_path),
                "model": {"path": str(weights), "sha256": model_hash, "versions": versions,
                          "class_names": class_names},
                "config": config, "sampling": sampling,
                "counts": {"frames": len(players), "person_detections": person_count,
                           "ball_candidates": ball_count, "frames_with_ball_candidate": frames_with_ball},
                "frame_integrity": {"expected_frames": expected_frames,
                                    "actual_frames": len(players), "tolerance_frames": 1},
                "performance": {"predict_decode_wall_s": elapsed,
                                "frames_per_second": len(players) / elapsed if elapsed > 0 else None},
                "limitations": ["Object candidates only; no tracking, teams, player identity, geometry or events.",
                                "Candidate presence and throughput are not accuracy measurements.",
                                "Source SHA256 is attested by preparation; clip SHA256 was verified here."],
                "outputs": ["players_detections.json", "ball_candidates.json"]}
    output.mkdir(parents=True, exist_ok=False)
    artifacts = {"players_detections.json": {"job": "local CPU person detection", "frames": len(players),
                                            "persons": person_count, "input_provenance": object_provenance,
                                            "detections": players},
                 "ball_candidates.json": {"job": "local CPU ball candidates", "frames": len(ball),
                                          "frames_with_candidate": frames_with_ball,
                                          "input_provenance": object_provenance, "detections": ball},
                 "detection_manifest.json": manifest}
    for filename, data in artifacts.items():
        with (output / filename).open("x") as stream:
            stream.write(json.dumps(data, indent=2, allow_nan=False) + "\n")
    return output / "detection_manifest.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=.25)
    args = parser.parse_args(argv)
    try:
        manifest = detect_pilot(args.pilot, args.weights, args.out, args.imgsz, args.conf)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f"pilot detection failed: {exc}\n")
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
