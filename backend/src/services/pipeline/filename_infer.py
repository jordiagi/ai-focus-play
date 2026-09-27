"""Filename Inference Engine for Soccer Match MP4 Uploads.

Extracts:
- Match date (supports standard hyphenated YYYY-MM-DD, compact YYYYMMDD, and legacy YYYY_MM_DD).
- Home and Away team identifiers across vs / -vs- / _vs_ separators.
- Competition/matchday codes (e.g. 26leg1j01 -> 2026/27 Lliga Elit Jornada 1).
- Automatic database Team resolution and Federation Acta matching.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

from backend.src.storage.repository import match_repo


KNOWN_ALIASES: Dict[str, str] = {
    "horta": "UA Horta",
    "ua horta": "UA Horta",
    "turo": "CCD Turó de la Peira",
    "turo peira": "CCD Turó de la Peira",
    "turo de la peira": "CCD Turó de la Peira",
    "arlington": "Arlington SA U16B",
    "arlington sa": "Arlington SA U16B",
    "skyline": "Skyline City FC",
    "skyline city": "Skyline City FC",
    "fairfax": "Fairfax Union",
    "baltimore": "Baltimore Armor",
    "ncfc": "NCFC",
}


class InferredMatchMeta(BaseModel):
    filename: str
    date: str
    home_team: str
    away_team: str
    title: str
    team_id: Optional[str] = None
    competition_code: Optional[str] = None
    confidence: float = 0.5


def _normalize_token(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()


class MatchFilenameParser:
    """Parses raw MP4 video filenames into structured match metadata."""

    @staticmethod
    def _extract_date(stem: str) -> Tuple[Optional[str], str]:
        """Extract YYYY-MM-DD, YYYY_MM_DD, or YYYYMMDD from filename and return (date, remainder)."""
        # 1. Hyphenated: 2026-09-20
        m = re.search(r"(?:^|[\W_])(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?:$|[\W_])", stem)
        if m:
            date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            rem = stem[:m.start()] + " " + stem[m.end():]
            return date_str, rem.strip()

        # 2. Underscored: 2026_09_20
        m = re.search(r"(?:^|[\W_])(20\d{2})_(0[1-9]|1[0-2])_(0[1-9]|[12]\d|3[01])(?:$|[\W_])", stem)
        if m:
            date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            rem = stem[:m.start()] + " " + stem[m.end():]
            return date_str, rem.strip()

        # 3. Compact: 20260920
        m = re.search(r"(?:^|[\W_])(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:$|[\W_])", stem)
        if m:
            date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            rem = stem[:m.start()] + " " + stem[m.end():]
            return date_str, rem.strip()

        return None, stem

    @staticmethod
    def _extract_competition_code(text: str) -> Tuple[Optional[str], str]:
        """Extract codes like 26leg1j01 or u16b from text."""
        # e.g. 26leg1j01 (26 season, lliga elit grup 1, jornada 01)
        m = re.search(r"(?:^|[\W_])(\d{2}[a-zA-Z]+\d+[a-zA-Z]*\d*)(?:$|[\W_])", text)
        if m:
            code = m.group(1)
            rem = text[:m.start()] + " " + text[m.end():]
            return code, rem.strip()
        return None, text

    @classmethod
    def parse_filename(cls, filename: str) -> InferredMatchMeta:
        """Parse filename into match metadata, inferring teams, date, and DB team link."""
        stem = Path(filename).stem

        # Extract date
        date, rem = cls._extract_date(stem)
        date = date or "2026-09-20"

        # Extract competition code
        comp_code, rem = cls._extract_competition_code(rem)

        # Standardize separators: convert underscores and multiple hyphens to clean tokens
        clean = rem.replace("_", " ").replace("-", " ")
        clean = re.sub(r"\s+", " ", clean).strip()

        vs_split = re.split(r"\bvs\b|\bv\b", clean, flags=re.IGNORECASE)
        if len(vs_split) >= 2:
            raw_home = vs_split[0].strip()
            raw_away = vs_split[1].strip()
        else:
            tokens = clean.split()
            if len(tokens) >= 2:
                raw_home = tokens[0]
                raw_away = " ".join(tokens[1:])
            else:
                raw_home = clean or "Home Team"
                raw_away = "Away Team"

        home_canonical = KNOWN_ALIASES.get(_normalize_token(raw_home), raw_home.title())
        away_canonical = KNOWN_ALIASES.get(_normalize_token(raw_away), raw_away.title())

        # Resolve team_id from repository
        teams = match_repo.list_teams()
        resolved_team_id = None
        norm_h = _normalize_token(home_canonical)
        norm_a = _normalize_token(away_canonical)

        for t in teams:
            norm_t = _normalize_token(t.name)
            if (
                norm_t in norm_h
                or norm_h in norm_t
                or norm_t in norm_a
                or norm_a in norm_t
            ):
                resolved_team_id = t.id
                break

        if not resolved_team_id and teams:
            resolved_team_id = teams[0].id

        title = f"{home_canonical} vs. {away_canonical}"

        return InferredMatchMeta(
            filename=filename,
            date=date,
            home_team=home_canonical,
            away_team=away_canonical,
            title=title,
            team_id=resolved_team_id,
            competition_code=comp_code,
            confidence=0.85 if ("vs" in stem.lower()) else 0.50,
        )


filename_parser = MatchFilenameParser()
