#!/usr/bin/env python3
"""Prepare an offline sampled video clip and its provenance, without inference.

Example: python scripts/local/prepare-video-pilot.py --video match.mp4 \
    --start 600 --duration 20 --fps 10 --out /tmp/match-pilot
The output directory must be new. No labels, periods or model weights are read.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess


def source_path(value):
    value = str(value)
    if not value.strip() or "://" in value or value.startswith(("http:", "https:", "file:", "ftp:", "ssh:")):
        raise ValueError("--video must be a local filesystem path, not a URL")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"source video is not a local file: {path}")
    return path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def probe_source(path):
    executable = shutil.which("ffprobe")
    if not executable:
        raise ValueError("ffprobe is required for local video validation")
    command = [executable, "-v", "error", "-protocol_whitelist", "file",
               "-select_streams", "v:0", "-show_entries",
               "format=duration:stream=codec_name,width,height,avg_frame_rate",
               "-of", "json", str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
    metadata = json.loads(completed.stdout)
    duration = float(metadata.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration <= 0 or not metadata.get("streams"):
        raise ValueError("source must contain a video stream and a finite positive duration")
    return metadata, duration


def prepare_pilot(video, start, duration, fps, out):
    source = source_path(video)
    if not all(math.isfinite(value) for value in (start, duration, fps)):
        raise ValueError("start, duration and fps must be finite")
    if start < 0 or duration <= 0 or fps <= 0:
        raise ValueError("start must be nonnegative; duration and fps must be positive")
    output = Path(out).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"refusing to overwrite existing output directory: {output}")
    metadata, source_duration = probe_source(source)
    if start + duration > source_duration:
        raise ValueError(f"requested clip ends at {start + duration}s, past source duration {source_duration}s")
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("ffmpeg is required for local clip preparation")
    source_hash = sha256_file(source)
    output.mkdir(parents=True, exist_ok=False)
    clip = output / "clip.mp4"
    # Explicit software encoder and two CPU threads; no remote or GPU execution.
    filters = f"scale=w='trunc(min(1280,iw)/2)*2':h=-2,fps={fps:g}"
    command = [executable, "-nostdin", "-n", "-v", "error", "-ss", f"{start:g}",
               "-protocol_whitelist", "file", "-i", str(source), "-t", f"{duration:g}",
               "-map", "0:v:0", "-an", "-vf", filters, "-c:v", "libx264", "-threads", "2",
               "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", str(clip)]
    subprocess.run(command, capture_output=True, text=True, check=True)
    if not clip.is_file() or clip.stat().st_size == 0:
        raise ValueError("ffmpeg did not produce a nonempty clip")
    manifest = {
        "schema_version": 1,
        "artifact_type": "video_pilot_preparation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inference_performed": False,
        "input_provenance": {"mode": "video_only", "evaluation_labels_used": False,
                             "video_sha256": source_hash, "video_path": str(source)},
        "source_metadata": metadata,
        "sampling": {"start_s": start, "duration_s": duration, "fps": fps, "max_width": 1280},
        "compute": {"mode": "local_cpu", "encoder": "libx264", "threads": 2},
        "command": command,
        "clip": {"path": str(clip), "sha256": sha256_file(clip), "size_bytes": clip.stat().st_size},
    }
    manifest_path = output / "pilot_manifest.json"
    with manifest_path.open("x") as stream:
        stream.write(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return manifest_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--fps", type=float, default=10)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest_path = prepare_pilot(args.video, args.start, args.duration, args.fps, args.out)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"pilot preparation failed: {exc}\n")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
