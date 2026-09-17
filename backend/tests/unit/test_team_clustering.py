import cv2
import numpy as np
import pytest
from backend.src.services.pipeline.cv_engine import SoccerCVEngine

def test_team_kit_chroma_clustering():
    """Red and Blue player torso crops separate cleanly into distinct clusters in Lab chroma space."""
    engine = SoccerCVEngine()

    # Green background (BGR: [34, 139, 34])
    h, w = 100, 100
    green_bg = np.zeros((h, w, 3), dtype=np.uint8)
    green_bg[:] = [34, 139, 34]

    samples = []
    # 6 Red jerseys (BGR: [20, 20, 220])
    for _ in range(6):
        patch = green_bg.copy()
        patch[20:80, 20:80] = [20, 20, 220]
        chroma = engine._extract_torso_chroma(patch, 20, 20, 60, 60)
        assert chroma is not None
        samples.append((chroma, "red"))

    # 6 Blue jerseys (BGR: [220, 40, 20])
    for _ in range(6):
        patch = green_bg.copy()
        patch[20:80, 20:80] = [220, 40, 20]
        chroma = engine._extract_torso_chroma(patch, 20, 20, 60, 60)
        assert chroma is not None
        samples.append((chroma, "blue"))

    chroma_pts = np.float32([s[0] for s in samples])
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(chroma_pts, 2, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

    red_labels = labels[:6].flatten()
    blue_labels = labels[6:].flatten()

    # All reds should have the same cluster id, and all blues should have the opposite cluster id
    assert len(set(red_labels)) == 1
    assert len(set(blue_labels)) == 1
    assert red_labels[0] != blue_labels[0]
