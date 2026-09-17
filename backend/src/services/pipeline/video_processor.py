import os
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("video_processor")

from backend.src.config import MEDIA_DIR

class VideoProcessor:
    @staticmethod
    def get_video_metadata(video_path: Path) -> Dict[str, Any]:
        """Runs ffprobe to extract duration, resolution, fps."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate,duration",
            "-of", "json",
            str(video_path)
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            info = json.loads(res.stdout)
            streams = [s for s in info.get("streams", []) if "width" in s]
            duration = float(info.get("format", {}).get("duration", 0.0))
            width = 1920
            height = 1080
            fps = 30.0

            if streams:
                s = streams[0]
                width = int(s.get("width", 1920))
                height = int(s.get("height", 1080))
                fps_parts = s.get("r_frame_rate", "30/1").split("/")
                if len(fps_parts) == 2 and float(fps_parts[1]) > 0:
                    fps = float(fps_parts[0]) / float(fps_parts[1])
                if duration == 0.0 and "duration" in s:
                    duration = float(s["duration"])

            return {
                "duration": duration,
                "width": width,
                "height": height,
                "fps": fps
            }
        except Exception as e:
            logger.error(f"Failed to probe video {video_path}: {e}")
            raise ValueError(f"Failed to probe video {video_path}: {e}")

    @staticmethod
    def extract_thumbnail(video_path: Path, output_path: Path, time_sec: float = 5.0) -> bool:
        """Extracts a single frame as JPEG thumbnail."""
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(time_sec),
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path)
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except Exception as e:
            logger.error(f"Thumbnail extraction failed: {e}")
            return False

    @staticmethod
    def cut_clip(video_path: Path, output_path: Path, start_time: float, end_time: float) -> bool:
        """Cuts a video clip using fast stream copy."""
        duration = max(1.0, end_time - start_time)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(duration),
            "-c", "copy",
            str(output_path)
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except Exception:
            # Fallback with re-encode if stream copy fails at keyframe boundaries
            cmd_reencode = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-i", str(video_path),
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                str(output_path)
            ]
            try:
                subprocess.run(cmd_reencode, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                return True
            except Exception as err:
                logger.error(f"Clip cut failed: {err}")
                return False

    @staticmethod
    def generate_demo_soccer_video(output_path: Path, duration: int = 90):
        """Generates a synthetic soccer match animation with pitch, players, ball, and clock."""
        if output_path.exists() and output_path.stat().st_size > 1000:
            return

        logger.info(f"Generating synthetic soccer match video to {output_path}...")
        # FFmpeg lavfi filter creating green pitch, center circle, penalty boxes, moving players (dots) and moving ball
        # With high quality 1080p output
        filter_complex = (
            f"color=c=#2e7d32:s=1920x1080:d={duration}[bg];"
            # Pitch white lines: center line, center circle, boxes
            "[bg]drawbox=x=80:y=60:w=1760:h=960:color=white@0.8:t=4,"
            "drawbox=x=958:y=60:w=4:h=960:color=white@0.8:t=fill,"
            "drawbox=x=80:y=280:w=300:h=520:color=white@0.8:t=4,"
            "drawbox=x=1540:y=280:w=300:h=520:color=white@0.8:t=4,"
            # Scoreboard overlay
            "drawbox=x=80:y=20:w=420:h=40:color=black@0.7:t=fill,"
            "drawtext=text='ARL 3 - 3 SKY':x=90:y=30:fontsize=24:fontcolor=white:box=0,"
            "drawtext=text='%{eif\\:trunc(t/60)\\:d\\:2}\\:%{eif\\:mod(t\\,60)\\:d\\:2}':x=380:y=30:fontsize=24:fontcolor=#00E676:box=0,"
            # Moving ball (white circle)
            "drawbox=x='960+600*sin(t*0.2)':y='540+300*cos(t*0.15)':w=18:h=18:color=white:t=fill,"
            # Home team player 10 (yellow dot)
            "drawbox=x='920+500*sin(t*0.2+0.5)':y='520+260*cos(t*0.15+0.5)':w=26:h=26:color=#FFD700:t=fill,"
            # Away defender (blue dot)
            "drawbox=x='1000+520*sin(t*0.2-0.4)':y='550+280*cos(t*0.15-0.3)':w=26:h=26:color=#2979FF:t=fill"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo",
            "-filter_complex", filter_complex,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-t", str(duration),
            str(output_path)
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            logger.info("Demo soccer video generated successfully.")
        except Exception as e:
            logger.error(f"Failed to generate demo soccer video: {e}")
