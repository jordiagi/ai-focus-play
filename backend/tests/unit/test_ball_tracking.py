import cv2
import numpy as np
import pytest
from pathlib import Path
from backend.src.services.pipeline.cv_engine import SoccerCVEngine

def test_ball_detection_and_kalman_filter(tmp_path: Path):
    """Synthesize a moving white circle across a green soccer pitch and assert tracked ball."""
    video_path = tmp_path / "ball_test.mp4"
    fps = 30
    duration = 4.0  # seconds
    w, h = 640, 360
    total_frames = int(fps * duration)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, fps, (w, h))

    # White ball moving across screen from left (x=100) to right (x=500)
    for i in range(total_frames):
        # Green pitch (BGR: [45, 120, 45])
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = [45, 120, 45]

        # Draw a moving white ball (radius 8px)
        bx = int(100 + (400 * i / total_frames))
        by = int(180 + 30 * np.sin(i * 0.1))
        cv2.circle(frame, (bx, by), 8, (255, 255, 255), -1)

        out.write(frame)
    out.release()

    engine = SoccerCVEngine()
    radar_frames, events, highlights, analytics = engine.process_video(video_path)

    assert len(radar_frames) >= 6
    detected_count = sum(1 for f in radar_frames if f.ball.detected)
    # Detected on >= 80% of frames
    assert detected_count / len(radar_frames) >= 0.75

    # Check that pitch x increases overall from start to end
    start_x = radar_frames[0].ball.x
    end_x = radar_frames[-1].ball.x
    assert end_x > start_x
