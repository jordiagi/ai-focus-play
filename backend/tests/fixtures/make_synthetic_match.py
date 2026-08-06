from __future__ import annotations

import json
import subprocess
from pathlib import Path


def make_synthetic_match(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / "synthetic_match.mp4"
    truth_path = output_dir / "synthetic_match.json"
    if not video_path.exists():
        filter_graph = (
            "[1:v]drawbox=x=12:y=25:w=21:h=5:color=white:t=fill,"
            "drawbox=x=12:y=52:w=21:h=5:color=white:t=fill,"
            "drawbox=x=12:y=79:w=21:h=5:color=white:t=fill,"
            "drawbox=x=12:y=25:w=5:h=59:color=white:t=fill,"
            "drawbox=x=28:y=25:w=5:h=59:color=white:t=fill[p1];"
            "[2:v]drawbox=x=12:y=28:w=5:h=56:color=white:t=fill,"
            "drawbox=x=28:y=28:w=5:h=56:color=white:t=fill[p2];"
            "[0:v][p1]overlay=x='40+20*t':y=100:eval=frame[tmp];"
            "[tmp][p2]overlay=x='520-18*t':y=150:eval=frame[out]"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x2f6f3e:s=640x360:r=10:d=10",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=45x110:r=10:d=10",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=45x110:r=10:d=10",
                "-filter_complex",
                filter_graph,
                "-map",
                "[out]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-t",
                "10",
                str(video_path),
            ],
            check=True,
            capture_output=True,
        )
    frames = []
    for index in range(100):
        ts = index / 10
        frames.append(
            {
                "frame_index": index,
                "ts": ts,
                "detections": [
                    {
                        "identity_id": "home-8",
                        "number": "8",
                        "x": (40 + 20 * ts) / 640,
                        "y": 100 / 360,
                        "w": 45 / 640,
                        "h": 110 / 360,
                        "confidence": 0.99,
                    },
                    {
                        "identity_id": "away-11",
                        "number": "11",
                        "x": (520 - 18 * ts) / 640,
                        "y": 150 / 360,
                        "w": 45 / 640,
                        "h": 110 / 360,
                        "confidence": 0.99,
                    },
                ],
            }
        )
    truth_path.write_text(
        json.dumps(
            {
                "duration_s": 10.0,
                "fps": 10.0,
                "width": 640,
                "height": 360,
                "frames": frames,
            },
            indent=2,
        )
    )
    return video_path, truth_path
