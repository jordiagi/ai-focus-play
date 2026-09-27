"""Federation Match Sheet (Acta) Ingestion and Reconciliation Engine.

Provides:
- Tier 1 HTTP ingestion and local fixture registry for official federation match sheets (actas).
- Schema modeling for match lineups, scorers, yellow/red cards, and substitutions.
- Option A strict reconciliation: reconciles autonomous ML/CV analytics with official federation ground truth.
- Player identification lookup: maps jersey numbers to real roster player names for jersey OCR reinforcement.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.src.domain.models.match import Event, Highlight, Match, PlayerRoster

logger = logging.getLogger("FederationActa")

REPO_ROOT = Path(__file__).resolve().parents[4]
RAW_BENCHMARKS = REPO_ROOT / "benchmarks/raw"


class PlayerSheet(BaseModel):
    jersey: str
    name: str
    position: str = "MID"  # "GK", "DEF", "MID", "FWD"
    is_starter: bool = True
    is_captain: bool = False
    is_player_of_match: bool = False


class GoalSheet(BaseModel):
    minute: int
    team: str  # "home" | "away"
    scorer: str
    jersey: Optional[str] = None
    detail: Optional[str] = None


class CardSheet(BaseModel):
    minute: int
    team: str  # "home" | "away"
    player: str
    jersey: Optional[str] = None
    card: str = "yellow"  # "yellow" | "red"


class SubSheet(BaseModel):
    minute: int
    team: str  # "home" | "away"
    player_in: str
    jersey_in: Optional[str] = None
    player_out: str
    jersey_out: Optional[str] = None


class MatchSheet(BaseModel):
    federation: str  # e.g. "FCF", "ECNL"
    competition: Optional[str] = None
    matchday: Optional[int] = None
    season: Optional[str] = None
    date: str
    match_code: Optional[str] = None
    source_url: Optional[str] = None
    home_name: str
    home_score: int = 0
    home_coach: Optional[str] = None
    home_lineup: List[PlayerSheet] = []
    away_name: str
    away_score: int = 0
    away_coach: Optional[str] = None
    away_lineup: List[PlayerSheet] = []
    goals: List[GoalSheet] = []
    cards: List[CardSheet] = []
    substitutions: List[SubSheet] = []
    incidents: List[Dict[str, Any]] = []

    def get_valid_jerseys(self, team: str) -> List[str]:
        """Return list of valid jersey numbers for a team side ('home' or 'away')."""
        lineup = self.home_lineup if team == "home" else self.away_lineup
        return [p.jersey for p in lineup]

    def get_player(self, team: str, jersey: str) -> Optional[PlayerSheet]:
        """Lookup player by team side and jersey number."""
        clean_j = str(jersey).strip()
        lineup = self.home_lineup if team == "home" else self.away_lineup
        for p in lineup:
            if str(p.jersey).strip() == clean_j:
                return p
        return None


def strip_accents(text: str) -> str:
    """Strip accents and diacritics for robust entity matching (e.g. Turó -> turo)."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()


def normalize_date(d: Optional[str]) -> Optional[str]:
    """Normalize date strings (e.g. 'Sep 20, 2026', '2026-09-20', '20260920') to YYYY-MM-DD."""
    if not d:
        return None
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%b %d, %Y", "%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(d.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return d.strip()


class FederationActaService:
    """Manages fetching, caching, and reconciliation of federation match sheets."""

    def __init__(self, fixtures_dir: Optional[Path] = None):
        self.fixtures_dir = fixtures_dir or RAW_BENCHMARKS
        self._cached_sheets: Dict[str, MatchSheet] = {}
        self._load_local_fixtures()

    def _load_local_fixtures(self):
        """Preload bundled official fixtures from benchmarks/raw."""
        if not self.fixtures_dir.exists():
            return

        for p in self.fixtures_dir.glob("*_acta.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    sheet = self._parse_raw_sheet(raw)
                    if sheet:
                        self._cached_sheets[p.stem] = sheet
                        logger.info(f"Loaded official acta fixture: {p.stem} ({sheet.home_name} vs {sheet.away_name})")
            except Exception as e:
                logger.warning(f"Failed to load acta fixture {p.name}: {e}")

    @staticmethod
    def _parse_raw_sheet(data: Dict[str, Any]) -> Optional[MatchSheet]:
        """Parse raw JSON dict into typed MatchSheet."""
        try:
            home_data = data.get("home_team", {})
            away_data = data.get("away_team", {})

            home_lineup = [PlayerSheet(**p) for p in home_data.get("lineup", [])]
            away_lineup = [PlayerSheet(**p) for p in away_data.get("lineup", [])]

            goals = [GoalSheet(**g) for g in data.get("goals", [])]
            cards = [CardSheet(**c) for c in data.get("cards", [])]
            subs = [SubSheet(**s) for s in data.get("substitutions", [])]

            return MatchSheet(
                federation=data.get("federation", "Unknown"),
                competition=data.get("competition"),
                matchday=data.get("matchday"),
                season=data.get("season"),
                date=data.get("date", ""),
                match_code=data.get("match_code"),
                source_url=data.get("source_url"),
                home_name=home_data.get("name", "Home Team"),
                home_score=int(home_data.get("score", 0)),
                home_coach=home_data.get("coach"),
                home_lineup=home_lineup,
                away_name=away_data.get("name", "Away Team"),
                away_score=int(away_data.get("score", 0)),
                away_coach=away_data.get("coach"),
                away_lineup=away_lineup,
                goals=goals,
                cards=cards,
                substitutions=subs,
                incidents=data.get("incidents", []),
            )
        except Exception as e:
            logger.error(f"Error parsing raw match sheet: {e}")
            return None

    def fetch_acta_from_url(self, url: str, timeout: int = 5) -> Optional[MatchSheet]:
        """Tier 1: Direct HTTP fetch and parse of federation URL."""
        if not url:
            return None

        # Check local cache first
        for sheet in self._cached_sheets.values():
            if sheet.source_url and sheet.source_url.rstrip("/") == url.rstrip("/"):
                return sheet

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/json,application/xhtml+xml",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read().decode("utf-8", errors="replace")
                if "application/json" in content_type:
                    return self._parse_raw_sheet(json.loads(data))
                # For HTML responses, basic extraction or Tier 2 browser hook
                logger.info(f"Retrieved HTML from {url} ({len(data)} chars). Tier 2 browser harness hook ready.")
        except urllib.error.HTTPError as e:
            logger.warning(f"Tier 1 fetch failed for {url}: HTTP {e.code}")
        except Exception as e:
            logger.warning(f"Tier 1 fetch failed for {url}: {e}")

        return None

    def resolve_acta_for_match(
        self,
        home_team: str,
        away_team: str,
        date: Optional[str] = None,
        federation_url: Optional[str] = None,
    ) -> Optional[MatchSheet]:
        """Find match sheet by matching teams, date, or federation URL."""
        # 1. Try URL lookup if provided
        if federation_url:
            sheet = self.fetch_acta_from_url(federation_url)
            if sheet:
                return sheet

        # 2. Token match against cached sheets with accent & date normalization
        h_norm = strip_accents(home_team)
        a_norm = strip_accents(away_team)
        norm_date = normalize_date(date)

        for sheet in self._cached_sheets.values():
            sh_home = strip_accents(sheet.home_name)
            sh_away = strip_accents(sheet.away_name)
            sh_date = normalize_date(sheet.date)

            # Check bidirectional team containment
            match_home = any(t in h_norm for t in sh_home.split()) or any(t in sh_home for t in h_norm.split())
            match_away = any(t in a_norm for t in sh_away.split()) or any(t in sh_away for t in a_norm.split())

            if (match_home and match_away) or (
                # inverted sides
                any(t in a_norm for t in sh_home.split()) and any(t in h_norm for t in sh_away.split())
            ):
                if norm_date and sh_date and norm_date != sh_date:
                    continue
                return sheet

        return None

    def reconcile_match(
        self,
        match: Match,
        sheet: MatchSheet,
        video_start_offset: float = 0.0,
        p2_start_offset: Optional[float] = None,
    ) -> Tuple[Match, List[Event], List[Highlight]]:
        """Option A: Reconcile match score, lineups, cards, subs, and incidents with official acta ground truth."""
        # 1. Strict score reconciliation
        match.home_score = sheet.home_score
        match.away_score = sheet.away_score

        def calc_timestamp(minute: int) -> float:
            if p2_start_offset is not None and minute > 45:
                return p2_start_offset + ((minute - 45) * 60.0)
            return video_start_offset + (minute * 60.0)

        # 2. Lineup population with real player names & jersey numbers
        reconciled_lineup: List[PlayerRoster] = []
        for p in sheet.home_lineup:
            reconciled_lineup.append(
                PlayerRoster(
                    jersey=p.jersey,
                    name=p.name,
                    position=p.position,
                    is_starter=p.is_starter,
                    is_captain=p.is_captain,
                    is_player_of_match=p.is_player_of_match,
                    minutes_played=None,
                )
            )
        for p in sheet.away_lineup:
            reconciled_lineup.append(
                PlayerRoster(
                    jersey=p.jersey,
                    name=p.name,
                    position=p.position,
                    is_starter=p.is_starter,
                    is_captain=p.is_captain,
                    is_player_of_match=p.is_player_of_match,
                    minutes_played=None,
                )
            )
        if reconciled_lineup:
            match.lineup = reconciled_lineup

        # 3. Generate reconciled Events and Highlights
        reconciled_events: List[Event] = []
        reconciled_highlights: List[Highlight] = []

        # Goals
        for idx, g in enumerate(sheet.goals):
            ts = calc_timestamp(g.minute)
            team_side = g.team
            team_name = sheet.home_name if team_side == "home" else sheet.away_name
            period = 1 if g.minute <= 45 else 2

            ev = Event(
                match_id=match.id,
                timestamp=ts,
                period=period,
                event_type="Goal",
                team=team_side,
                player_jersey=g.jersey,
                player_name=g.scorer,
                description=f"Goal ({team_name}): {g.scorer} (#{g.jersey or ''}) at {g.minute}'",
                confidence=1.0,
            )
            reconciled_events.append(ev)

            hl = Highlight(
                match_id=match.id,
                title=f"Goal: {g.scorer} ({g.minute}')",
                event_type="goal",
                start_time=max(0.0, ts - 10.0),
                end_time=ts + 8.0,
                period=period,
                team=team_side,
                player_jersey=g.jersey,
                player_name=g.scorer,
                is_ai_detected=True,
                tags=["goal", "acta_verified", team_side],
            )
            reconciled_highlights.append(hl)

        # Yellow / Red Cards
        for c in sheet.cards:
            ts = calc_timestamp(c.minute)
            team_side = c.team
            period = 1 if c.minute <= 45 else 2
            card_label = "Red card" if c.card.lower() == "red" else "Yellow card"

            ev = Event(
                match_id=match.id,
                timestamp=ts,
                period=period,
                event_type=card_label,
                team=team_side,
                player_jersey=c.jersey,
                player_name=c.player,
                description=f"{card_label}: {c.player} (#{c.jersey or ''}) at {c.minute}'",
                confidence=1.0,
            )
            reconciled_events.append(ev)

            hl = Highlight(
                match_id=match.id,
                title=f"{card_label}: {c.player} ({c.minute}')",
                event_type="card",
                start_time=max(0.0, ts - 6.0),
                end_time=ts + 6.0,
                period=period,
                team=team_side,
                player_jersey=c.jersey,
                player_name=c.player,
                is_ai_detected=True,
                tags=[c.card.lower(), "card", "acta_verified"],
            )
            reconciled_highlights.append(hl)

        # Substitutions
        for s in sheet.substitutions:
            ts = calc_timestamp(s.minute)
            team_side = s.team
            period = 1 if s.minute <= 45 else 2

            ev = Event(
                match_id=match.id,
                timestamp=ts,
                period=period,
                event_type="Substitution",
                team=team_side,
                player_jersey=s.jersey_in,
                player_name=s.player_in,
                description=f"Substitution ({team_side}): IN {s.player_in} (#{s.jersey_in or ''}), OUT {s.player_out} (#{s.jersey_out or ''}) at {s.minute}'",
                confidence=1.0,
            )
            reconciled_events.append(ev)

        # Incidents (e.g. penalty missed)
        for inc in sheet.incidents:
            min_val = int(inc.get("minute", 0))
            ts = calc_timestamp(min_val)
            team_side = inc.get("team", "home")
            itype = str(inc.get("type", "incident"))
            p_name = inc.get("player")
            p_jersey = str(inc.get("jersey", "")) if inc.get("jersey") else None
            period = 1 if min_val <= 45 else 2

            ev_display = "Penalty missed" if "missed" in itype else ("Penalty" if "penalty" in itype else itype.replace("_", " ").title())
            desc = f"{ev_display} ({team_side}): {p_name or 'Player'} (#{p_jersey or ''}) at {min_val}'"
            reconciled_events.append(
                Event(
                    match_id=match.id,
                    timestamp=ts,
                    period=period,
                    event_type=ev_display,
                    team=team_side,
                    player_jersey=p_jersey,
                    player_name=p_name,
                    description=desc,
                    confidence=1.0,
                )
            )
            reconciled_highlights.append(
                Highlight(
                    match_id=match.id,
                    title=f"{ev_display}: {p_name} ({min_val}')",
                    event_type="shot" if "penalty" in itype else "custom",
                    start_time=max(0.0, ts - 8.0),
                    end_time=ts + 8.0,
                    period=period,
                    team=team_side,
                    player_jersey=p_jersey,
                    player_name=p_name,
                    is_ai_detected=True,
                    tags=[itype, "acta_verified"],
                )
            )

        # Update event capabilities count for Goal
        if match.event_capabilities and "Goal" in match.event_capabilities:
            total_goals = len(sheet.goals)
            match.event_capabilities["Goal"].count = total_goals

        return match, reconciled_events, reconciled_highlights


# Global singleton
acta_service = FederationActaService()
