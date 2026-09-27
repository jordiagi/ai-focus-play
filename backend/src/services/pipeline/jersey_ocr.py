"""Back-of-Shirt Digit OCR and Jersey Voting Engine (WP G10 / P2).

Extracts and recognizes player jersey digits from upper-torso back crops
using multi-scale normalized athletic font correlation and temporal vote aggregation.
Strictly adheres to the U-2 Honesty Policy: returns None when confidence is insufficient.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("JerseyDigitOCR")


class JerseyDigitOCR:
    """Optical Character Recognition for soccer jersey back-of-shirt digits."""

    def __init__(self, target_digit_size: Tuple[int, int] = (24, 40)):
        self.target_size = target_digit_size
        self.templates = self._generate_canonical_templates()

    def _generate_canonical_templates(self) -> Dict[str, np.ndarray]:
        """Generate normalized athletic font templates for digits 0-9."""
        templates: Dict[str, np.ndarray] = {}
        for d in "0123456789":
            canvas = np.zeros((50, 40), dtype=np.uint8)
            cv2.putText(canvas, d, (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 255, 3, cv2.LINE_AA)
            cnts, _ = cv2.findContours(canvas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if cnts:
                x, y, w, h = cv2.boundingRect(cnts[0])
                glyph = canvas[y : y + h, x : x + w]
                templates[d] = cv2.resize(glyph, self.target_size)
            else:
                templates[d] = cv2.resize(canvas, self.target_size)
        return templates

    @staticmethod
    def extract_torso_crop(frame_img: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """Extract upper-center torso back crop from player bounding box [x1, y1, x2, y2]."""
        if frame_img is None or len(bbox) < 4:
            return None
        h_frame, w_frame = frame_img.shape[:2]
        x1, y1, x2, y2 = bbox[:4]

        # Constrain to frame boundaries
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(w_frame, int(x2)), min(h_frame, int(y2))
        bw = x2 - x1
        bh = y2 - y1

        if bw < 12 or bh < 24:
            return None

        # Torso back region: upper 15% to 55% vertically, central 60% horizontally
        t_y1 = int(y1 + 0.15 * bh)
        t_y2 = int(y1 + 0.55 * bh)
        t_x1 = int(x1 + 0.20 * bw)
        t_x2 = int(x2 - 0.20 * bw)

        if t_y2 <= t_y1 or t_x2 <= t_x1:
            return None

        crop = frame_img[t_y1:t_y2, t_x1:t_x2]
        return crop if crop.size > 0 else None

    def recognize_crop(self, crop: np.ndarray) -> Tuple[Optional[str], float]:
        """Recognize 1 or 2 digit jersey number from torso crop image.
        
        Returns (jersey_number_str, confidence) or (None, 0.0).
        """
        if crop is None or crop.size == 0:
            return None, 0.0

        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop

        # CLAHE local contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)

        # Otsu thresholding
        _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh_inv = cv2.bitwise_not(thresh)

        best_number: Optional[str] = None
        best_score = -1.0

        # Evaluate both white-on-dark and dark-on-white polarities
        for bin_img in (thresh, thresh_inv):
            cnts, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            h_crop, w_crop = bin_img.shape[:2]
            char_boxes: List[Tuple[int, int, int, int]] = []

            for c in cnts:
                x, y, w, h = cv2.boundingRect(c)
                # Digit character geometric filters
                if (0.15 * h_crop <= h <= 0.85 * h_crop and
                    0.08 * w_crop <= w <= 0.70 * w_crop and
                    (h / max(1, w)) >= 0.75):
                    char_boxes.append((x, y, w, h))

            if not char_boxes or len(char_boxes) > 2:
                continue

            # Sort character blobs from left to right
            char_boxes.sort(key=lambda b: b[0])

            digits: List[str] = []
            scores: List[float] = []

            for x, y, w, h in char_boxes:
                roi = bin_img[y : y + h, x : x + w]
                resized = cv2.resize(roi, self.target_size)

                best_digit = None
                best_d_score = -1.0
                for d, tmpl in self.templates.items():
                    res = cv2.matchTemplate(resized, tmpl, cv2.TM_CCOEFF_NORMED)
                    s = float(res[0][0])
                    if s > best_d_score:
                        best_d_score = s
                        best_digit = d

                if best_digit and best_d_score >= 0.50:
                    digits.append(best_digit)
                    scores.append(best_d_score)

            if digits and len(digits) == len(char_boxes):
                avg_score = float(np.mean(scores))
                if avg_score > best_score:
                    best_score = avg_score
                    best_number = "".join(digits)

        if best_number and best_score >= 0.60:
            return best_number, round(best_score, 3)

        return None, 0.0


class JerseyVoteAggregator:
    """Accumulates multi-frame jersey observations across tracklets with optional roster prior."""

    def __init__(
        self,
        min_votes: int = 3,
        min_confidence: float = 0.65,
        roster_whitelist: Optional[List[str]] = None,
        player_names: Optional[Dict[str, str]] = None,
    ):
        self.min_votes = min_votes
        self.min_confidence = min_confidence
        self.roster_whitelist = set(str(j).strip() for j in roster_whitelist) if roster_whitelist else None
        self.player_names = {str(k).strip(): v for k, v in player_names.items()} if player_names else {}
        # track_id -> jersey_number -> cumulative score / vote count
        self.votes: Dict[int, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    def add_observation(self, track_id: int, jersey: Optional[str], confidence: float):
        """Register an OCR observation for a tracklet, applying roster whitelist prior."""
        if not jersey or confidence < self.min_confidence:
            return

        clean_j = str(jersey).strip()
        # If roster whitelist is active, give valid numbers a 15% prior boost and suppress outliers
        if self.roster_whitelist is not None:
            if clean_j not in self.roster_whitelist:
                if confidence < 0.82:
                    return
            else:
                confidence = min(1.0, confidence * 1.15)

        self.votes[track_id][clean_j].append(confidence)

    def get_consensus(self, track_id: int) -> Optional[str]:
        """Return the consensus jersey number if confidence threshold is met."""
        if track_id not in self.votes:
            return None

        candidates = self.votes[track_id]
        if not candidates:
            return None

        # Rank candidates by (vote_count, mean_confidence)
        ranked = []
        for jersey, scores in candidates.items():
            if len(scores) >= self.min_votes:
                ranked.append((jersey, len(scores), float(np.mean(scores))))

        if not ranked:
            return None

        # Prioritize candidates in roster whitelist if available
        if self.roster_whitelist:
            whitelisted = [r for r in ranked if r[0] in self.roster_whitelist]
            if whitelisted:
                ranked = whitelisted

        ranked.sort(key=lambda r: (r[1], r[2]), reverse=True)
        best_jersey, count, mean_conf = ranked[0]

        logger.debug(
            f"Track {track_id} consensus jersey {best_jersey} (votes={count}, conf={mean_conf:.2f})"
        )
        return best_jersey

    def get_player_name(self, jersey: Optional[str]) -> Optional[str]:
        """Look up player name from roster for a given jersey number."""
        if not jersey:
            return None
        return self.player_names.get(str(jersey).strip())
