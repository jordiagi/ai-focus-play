#!/usr/bin/env python3
"""Score saved ball candidates against an independent, private frame audit.

Evaluation only: this tool never performs inference. Uncertain/occluded frames
are excluded; candidate presence is reported separately from actual accuracy.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re


def timestamp(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("timestamps must be finite and nonnegative")
    return round(value, 6)


def candidates_for(frame):
    if "c" in frame:
        return frame["c"]
    if "candidates" in frame:
        return [[c["cx"], c["cy"], c["size"], c["conf"]] for c in frame["candidates"]]
    raise ValueError("prediction frame has no recognized candidate container")


def score(predictions, audit, tolerance_px=6.0):
    if not math.isfinite(tolerance_px) or tolerance_px <= 0:
        raise ValueError("tolerance_px must be finite and positive")
    provenance = predictions.get("input_provenance", {})
    clip_hash = provenance.get("clip_sha256")
    if not isinstance(clip_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", clip_hash) or audit.get("clip_sha256") != clip_hash:
        raise ValueError("audit and predictions must identify the same clip SHA256")
    by_time = {}
    for frame in predictions.get("detections", []):
        key = timestamp(frame["t"])
        if key in by_time:
            raise ValueError("duplicate prediction timestamps")
        by_time[key] = candidates_for(frame)
    tp = fp = fn = evaluated = excluded = 0
    seen = set()
    distances = []
    for frame in audit.get("frames", []):
        key = timestamp(frame["t"])
        if key in seen:
            raise ValueError("duplicate audit timestamps")
        seen.add(key)
        if key not in by_time:
            raise ValueError("audit timestamp missing from saved predictions")
        status = frame.get("status")
        if status in ("uncertain", "occluded"):
            excluded += 1
            continue
        if status not in ("visible", "not_visible"):
            raise ValueError("audit status must be visible, not_visible, uncertain or occluded")
        candidates = by_time[key]
        if any(len(c) < 4 or not all(math.isfinite(float(v)) for v in c[:4]) for c in candidates):
            raise ValueError("invalid ball candidates")
        evaluated += 1
        if status == "not_visible":
            if frame.get("center") is not None:
                raise ValueError("not_visible frame cannot have a ball center")
            fp += len(candidates)
            continue
        center = frame.get("center")
        if not isinstance(center, list) or len(center) != 2 or not all(math.isfinite(float(v)) for v in center):
            raise ValueError("visible audit requires a finite [x, y] center")
        center = [float(v) for v in center]
        nearest = min((math.hypot(float(c[0])-center[0], float(c[1])-center[1]) for c in candidates), default=math.inf)
        matched = nearest <= tolerance_px
        tp += int(matched)
        fn += int(not matched)
        fp += len(candidates) - int(matched)
        if matched:
            distances.append(nearest)
    return {
        "measurement": "independent_frame_audit",
        "clip_sha256": clip_hash, "tolerance_px": tolerance_px,
        "evaluated_frames": evaluated, "excluded_frames": excluded,
        "audited_frame_fraction": evaluated / len(by_time) if by_time else 0,
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "precision": tp/(tp+fp) if tp+fp else None,
        "recall": tp/(tp+fn) if tp+fn else None,
        "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        "mean_matched_center_error_px": sum(distances)/len(distances) if distances else None,
        "limitations": "Scores only explicitly audited frames; not full-match or event accuracy.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--tolerance-px", type=float, default=6)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    pred_bytes, audit_bytes = args.predictions.read_bytes(), args.audit.read_bytes()
    report = score(json.loads(pred_bytes), json.loads(audit_bytes), args.tolerance_px)
    report["predictions_sha256"] = hashlib.sha256(pred_bytes).hexdigest()
    report["audit_sha256"] = hashlib.sha256(audit_bytes).hexdigest()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.out:
        with args.out.open("x") as stream:
            stream.write(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
