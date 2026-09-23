import time
import uuid
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.src.config import READ_ONLY
from backend.src.storage.database import SessionLocal, CommentDB, HighlightDB

router = APIRouter(prefix="/api/highlights", tags=["comments"])


class CreateCommentRequest(BaseModel):
    author: str
    body: str


class CommentOut(BaseModel):
    id: str
    highlight_id: str
    author: str
    body: str
    created_at: float


def _require_highlight(db, highlight_id: str) -> None:
    found = db.query(HighlightDB).filter(HighlightDB.id == highlight_id).first()
    if not found:
        raise HTTPException(status_code=404, detail="Highlight not found")


def _bump_count(highlight_id: str, delta: int) -> None:
    with SessionLocal() as db:
        h = db.query(HighlightDB).filter(HighlightDB.id == highlight_id).first()
        if h is None:
            return
        current = h.comments_count if h.comments_count is not None else 0
        h.comments_count = max(0, current + delta)
        db.commit()


@router.get("/{highlight_id}/comments", response_model=List[CommentOut])
def list_comments(highlight_id: str):
    with SessionLocal() as db:
        _require_highlight(db, highlight_id)
        rows = (
            db.query(CommentDB)
            .filter(CommentDB.highlight_id == highlight_id)
            .order_by(CommentDB.created_at.asc(), CommentDB.id.asc())
            .all()
        )
        return [
            CommentOut(
                id=r.id,
                highlight_id=r.highlight_id,
                author=r.author,
                body=r.body,
                created_at=r.created_at,
            )
            for r in rows
        ]


@router.post("/{highlight_id}/comments", response_model=CommentOut, status_code=201)
def create_comment(highlight_id: str, req: CreateCommentRequest):
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="Read-only mode: Creating or writing new clips is disabled.")
    now = time.time()
    with SessionLocal() as db:
        _require_highlight(db, highlight_id)
        row = CommentDB(
            id=str(uuid.uuid4()),
            highlight_id=highlight_id,
            author=req.author,
            body=req.body,
            created_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        out = CommentOut(
            id=row.id,
            highlight_id=row.highlight_id,
            author=row.author,
            body=row.body,
            created_at=row.created_at,
        )
    _bump_count(highlight_id, +1)
    return out


@router.delete("/{highlight_id}/comments/{comment_id}")
def delete_comment(highlight_id: str, comment_id: str):
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="Read-only mode: Deleting clips is disabled.")
    with SessionLocal() as db:
        _require_highlight(db, highlight_id)
        row = (
            db.query(CommentDB)
            .filter(CommentDB.id == comment_id, CommentDB.highlight_id == highlight_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Comment not found")
        db.delete(row)
        db.commit()
    _bump_count(highlight_id, -1)
    return {"status": "success"}
