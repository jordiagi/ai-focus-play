import json
import logging
import sqlite3
from typing import List, Dict, Any, Optional
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, Text, ForeignKey, Index, event, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from backend.src.config import DB_PATH

logger = logging.getLogger("database")

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def _set_pragmas(dbapi_conn, _):
    """Enable WAL mode, normal synchronous durability, and foreign key enforcement."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class MatchDB(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    home_score = Column(Integer, default=0)
    away_score = Column(Integer, default=0)
    date = Column(String, nullable=False)
    duration_seconds = Column(Float, default=90.0)
    status = Column(String, default="ready")
    processing_step = Column(String, nullable=True)
    processing_progress = Column(Float, default=100.0)
    error_message = Column(String, nullable=True)
    video_url = Column(String, nullable=False)
    panoramic_url = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    views_count = Column(Integer, default=95)
    journal_notes = Column(Text, default="")
    analysis_mode = Column(String, default="heuristic")       # "demo" | "heuristic" | "ml"
    analysis_confidence = Column(String, default="low")       # "low" | "medium" | "high"
    created_at = Column(Float, nullable=False)

    highlights = relationship("HighlightDB", back_populates="match", cascade="all, delete-orphan")
    events = relationship("EventDB", back_populates="match", cascade="all, delete-orphan")
    drawings = relationship("DrawingDB", back_populates="match", cascade="all, delete-orphan")
    lineup = relationship("LineupPlayerDB", back_populates="match", cascade="all, delete-orphan")
    radar_frames = relationship("RadarFrameDB", back_populates="match", cascade="all, delete-orphan")
    analytics = relationship("AnalyticsDB", back_populates="match", cascade="all, delete-orphan", uselist=False)
    jobs = relationship("JobDB", back_populates="match", cascade="all, delete-orphan")

class HighlightDB(Base):
    __tablename__ = "highlights"

    id = Column(String, primary_key=True, index=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    period = Column(Integer, default=1)
    team = Column(String, default="home")
    player_jersey = Column(String, nullable=True)
    player_name = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    clip_url = Column(String, nullable=True)
    is_ai_detected = Column(Boolean, default=True)
    tags = Column(Text, default="[]")  # JSON string
    comments_count = Column(Integer, default=0)
    created_at = Column(Float, nullable=False)

    match = relationship("MatchDB", back_populates="highlights")

class EventDB(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False)
    period = Column(Integer, default=1)
    event_type = Column(String, nullable=False)
    team = Column(String, nullable=False)
    player_jersey = Column(String, nullable=True)
    player_name = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    pitch_x = Column(Float, default=52.5)
    pitch_y = Column(Float, default=34.0)
    confidence = Column(Float, default=0.8)

    match = relationship("MatchDB", back_populates="events")

class DrawingDB(Base):
    __tablename__ = "drawings"

    id = Column(String, primary_key=True, index=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False)
    tool_type = Column(String, nullable=False)
    color = Column(String, default="#00E676")
    coordinates = Column(Text, default="[]")  # JSON string
    text_label = Column(String, nullable=True)
    created_at = Column(Float, nullable=False)

    match = relationship("MatchDB", back_populates="drawings")

class LineupPlayerDB(Base):
    __tablename__ = "lineup_players"

    id = Column(String, primary_key=True, index=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False, index=True)
    jersey = Column(String, nullable=False)
    name = Column(String, nullable=False)
    position = Column(String, default="MID")
    is_starter = Column(Boolean, default=True)
    is_captain = Column(Boolean, default=False)
    is_player_of_match = Column(Boolean, default=False)
    minutes_played = Column(Integer, default=90)

    match = relationship("MatchDB", back_populates="lineup")

class RadarFrameDB(Base):
    __tablename__ = "radar_frames"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False)
    timestamp = Column(Float, nullable=False)
    data = Column(Text, nullable=False)  # JSON string of players & ball

    match = relationship("MatchDB", back_populates="radar_frames")

    __table_args__ = (
        Index("ix_radar_match_time", "match_id", "timestamp"),
    )

class AnalyticsDB(Base):
    __tablename__ = "analytics"

    match_id = Column(String, ForeignKey("matches.id"), primary_key=True)
    data = Column(Text, nullable=False)  # JSON string of AnalyticsData

    match = relationship("MatchDB", back_populates="analytics")

class ClubDB(Base):
    __tablename__ = "clubs"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    teams_count = Column(Integer, default=140)
    crest_url = Column(String, nullable=True)

class JobDB(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False, index=True)
    kind = Column(String, default="cv_analysis")
    status = Column(String, default="pending")  # pending, running, completed, failed, interrupted
    progress = Column(Float, default=0.0)
    step = Column(String, default="queued")
    started_at = Column(Float, nullable=True)
    finished_at = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)

    match = relationship("MatchDB", back_populates="jobs")

def init_db():
    Base.metadata.create_all(bind=engine)
    # Check for missing columns on existing tables (lightweight migration)
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(matches)"))
            columns = [row[1] for row in res.fetchall()]
            if "analysis_mode" not in columns:
                conn.execute(text("ALTER TABLE matches ADD COLUMN analysis_mode VARCHAR DEFAULT 'heuristic'"))
                conn.commit()
            if "analysis_confidence" not in columns:
                conn.execute(text("ALTER TABLE matches ADD COLUMN analysis_confidence VARCHAR DEFAULT 'low'"))
                conn.commit()
            
            # Check events table for confidence column
            res_ev = conn.execute(text("PRAGMA table_info(events)"))
            ev_columns = [row[1] for row in res_ev.fetchall()]
            if "confidence" not in ev_columns:
                conn.execute(text("ALTER TABLE events ADD COLUMN confidence FLOAT DEFAULT 0.8"))
                conn.commit()
    except Exception as e:
        logger.warning(f"Database migration check notice: {e}")

    logger.info(f"Initialized SQLite database at {DB_PATH}")
