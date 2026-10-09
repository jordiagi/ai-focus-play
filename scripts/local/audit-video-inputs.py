#!/usr/bin/env python3
"""Inventory local benchmark inputs without running inference or contacting services.

Registry paths are repository-relative, matching benchmarks/matches.json. Guidance
listed here is available evidence, not proof that a particular prediction used it.
Example: python scripts/local/audit-video-inputs.py --out /tmp/video-audit.json
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess


REPO = Path(__file__).resolve().parents[2]
TIMESTAMP_KEYS = ("t", "timestamp_s", "video_s", "time_s", "timestamp")


def local_path(value, root=REPO):
    """Accept filesystem paths only; ffprobe must never open a network URL."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or "://" in value:
        raise ValueError("expected a nonempty local filesystem path")
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def path_status(value, root=REPO):
    try:
        path = local_path(value, root)
    except ValueError as exc:
        return {"path": value, "available": False, "error": str(exc)}
    return {"path": str(path) if path else None, "available": bool(path and path.is_file())}


def probe_video(value, root=REPO):
    result = path_status(value, root)
    if not result["available"]:
        result["probe_status"] = "missing_or_invalid_video"
        return result
    result["size_bytes"] = Path(result["path"]).stat().st_size
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        result["probe_status"] = "ffprobe_unavailable"
        return result
    # Only metadata is decoded. -protocol_whitelist prevents indirect URL access.
    command = [ffprobe, "-v", "error", "-protocol_whitelist", "file", "-select_streams", "v:0",
               "-show_entries", "format=duration:stream=codec_name,width,height,r_frame_rate,avg_frame_rate",
               "-of", "json", result["path"]]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
        result["metadata"] = json.loads(completed.stdout)
        result["probe_status"] = "ok"
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        result.update(probe_status="error", error=str(exc))
    return result


def summarize_artifact(path):
    result = {"path": str(path), "kind": "players" if "player" in path.name.lower() else "ball"}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return dict(result, error=str(exc))
    rows = data if isinstance(data, list) else None
    if isinstance(data, dict):
        result["provenance"] = {key: data[key] for key in
                                ("job", "command", "video", "weights", "config", "source_meta", "in_play_spans")
                                if key in data}
        result["declared_frames"] = data.get("frames")
        for key in ("detections", "tracks", "frames", "points"):
            if isinstance(data.get(key), list):
                rows = data[key]
                result["row_container"] = key
                break
    rows = rows or []
    times, invalid, observations = [], 0, 0
    rows_with_observations = 0
    for row in rows:
        if not isinstance(row, dict):
            invalid += 1
            continue
        value = next((row[k] for k in TIMESTAMP_KEYS if k in row), None)
        try:
            timestamp = float(value)
            if isinstance(value, bool) or not math.isfinite(timestamp):
                raise ValueError("invalid timestamp")
            times.append(timestamp)
        except (TypeError, ValueError):
            invalid += 1
        count = 0
        if isinstance(row.get("boxes"), list):
            count = len(row["boxes"])
        elif isinstance(row.get("c"), list):
            count = len(row["c"])
        elif any(key in row for key in ("u", "x", "cx")):
            count = 1
        observations += count
        rows_with_observations += count > 0
    ordered = sorted(set(times))
    gaps = [b - a for a, b in zip(ordered, ordered[1:])]
    median = statistics.median(gaps) if gaps else None
    result.update(row_count=len(rows), observation_count=observations,
                  rows_with_observations=rows_with_observations,
                  invalid_timestamp_rows=invalid, timestamp_count=len(times),
                  unique_timestamp_count=len(ordered), duplicate_timestamp_count=len(times) - len(ordered),
                  first_timestamp_s=ordered[0] if ordered else None,
                  last_timestamp_s=ordered[-1] if ordered else None,
                  median_gap_s=median, max_gap_s=max(gaps) if gaps else None,
                  median_cadence_fps=1 / median if median else None)
    return result


def audit_match(entry, root=REPO):
    labels = {key: path_status(entry.get(key), root) for key in ("stats", "events")}
    guidance = {"calibration": path_status(entry.get("calib"), root),
                "periods": {"value": entry.get("periods"), "present": entry.get("periods") is not None},
                "own_side_p1": {"value": entry.get("own_side_p1"), "present": entry.get("own_side_p1") is not None}}
    result = {"id": entry.get("id"), "label": entry.get("label"),
              "video": probe_video(entry.get("video"), root),
              "declared_video_duration_s": entry.get("video_duration_s"),
              "labels": labels, "has_available_labels": any(v["available"] for v in labels.values()),
              "external_guidance": guidance,
              "guidance_usage": "availability_only_not_inference_usage", "artifacts": []}
    try:
        directory = local_path(entry.get("artifacts"), root)
    except ValueError as exc:
        result["artifact_error"] = str(exc)
        return result
    result["artifact_directory"] = str(directory) if directory else None
    result["artifact_directory_available"] = bool(directory and directory.is_dir())
    if result["artifact_directory_available"]:
        for path in sorted(directory.glob("*.json")):
            if "player" in path.name.lower() or "ball" in path.name.lower():
                result["artifacts"].append(summarize_artifact(path))
    return result


def audit_registry(registry, root=REPO):
    data = json.loads(Path(registry).read_text())
    return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "registry": str(Path(registry).resolve()), "path_root": str(root),
            "mode": "local_read_only_no_inference", "matches": [audit_match(e, root) for e in data["matches"]]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REPO / "benchmarks/video_only_matches.json")
    parser.add_argument("--out", type=Path, help="write JSON report; defaults to stdout")
    args = parser.parse_args(argv)
    report = json.dumps(audit_registry(args.registry), indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
