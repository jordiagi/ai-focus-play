"""Unit tests for the per-clip comment threads endpoint (WP-6 / P6-comments).

comments.py is not registered on the main app yet (that is the integrator's job --
see the router_registration_line in the WP-6 report), so this module mounts the
router on a throwaway FastAPI app of its own, following the same TestClient pattern
as test_backend.py. It reuses the session-wide throwaway sqlite database that
backend/tests/conftest.py points AIFP_DB_PATH at (set at import time, before
backend.src.config is ever imported), so it never touches backend/.local/data/veo.db.

Importing backend.src.app.main pulls in backend.src.storage.repository, whose
module-level `match_repo = MatchRepository()` calls init_db() (creating the
`comments` table declared in database.py) and seeds the demo match/highlights the
first time it runs in this test process. Each test then creates its own throwaway
highlight row directly via the database module (not through any HTTP endpoint --
the highlights API belongs to another agent) so tests never depend on run order or
on each other's leftover comments.
"""
import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Importing main triggers backend.src.storage.repository's module-level
# match_repo = MatchRepository(), which calls init_db() and seeds the demo match.
import backend.src.app.main  # noqa: F401
from backend.src.api.routes import comments
from backend.src.storage.database import SessionLocal, HighlightDB, MatchDB, CommentDB


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(comments.router)
    return TestClient(app)


@pytest.fixture
def demo_match_id():
    with SessionLocal() as db:
        row = db.query(MatchDB).first()
        assert row is not None, "no seeded match found -- demo seed did not run"
        return row.id


@pytest.fixture
def highlight(demo_match_id):
    """A fresh, isolated highlight row with no comments, owned entirely by this test."""
    row = HighlightDB(
        id=f"test-highlight-{uuid.uuid4()}",
        match_id=demo_match_id,
        title="Test highlight for comment threads",
        event_type="goal",
        start_time=0.0,
        end_time=5.0,
        comments_count=0,
        created_at=time.time(),
    )
    with SessionLocal() as db:
        db.add(row)
        db.commit()
        db.refresh(row)
        highlight_id = row.id
    yield highlight_id
    with SessionLocal() as db:
        db.query(CommentDB).filter(CommentDB.highlight_id == highlight_id).delete()
        db.query(HighlightDB).filter(HighlightDB.id == highlight_id).delete()
        db.commit()


def _comments_count(highlight_id):
    with SessionLocal() as db:
        row = db.query(HighlightDB).filter(HighlightDB.id == highlight_id).first()
        return row.comments_count


def test_empty_thread_returns_empty_list(client, highlight):
    res = client.get(f"/api/highlights/{highlight}/comments")
    assert res.status_code == 200
    assert res.json() == []


def test_created_comment_is_returned_by_list(client, highlight):
    create_res = client.post(
        f"/api/highlights/{highlight}/comments",
        json={"author": "Coach", "body": "Great run down the wing"},
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["highlight_id"] == highlight
    assert created["author"] == "Coach"
    assert created["body"] == "Great run down the wing"
    assert "id" in created and created["id"]

    list_res = client.get(f"/api/highlights/{highlight}/comments")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert items[0]["body"] == "Great run down the wing"


def test_ordering_is_oldest_first(client, highlight):
    first = client.post(
        f"/api/highlights/{highlight}/comments",
        json={"author": "A", "body": "first"},
    ).json()
    second = client.post(
        f"/api/highlights/{highlight}/comments",
        json={"author": "B", "body": "second"},
    ).json()
    third = client.post(
        f"/api/highlights/{highlight}/comments",
        json={"author": "C", "body": "third"},
    ).json()

    res = client.get(f"/api/highlights/{highlight}/comments")
    assert res.status_code == 200
    items = res.json()
    assert [c["id"] for c in items] == [first["id"], second["id"], third["id"]]
    assert [c["body"] for c in items] == ["first", "second", "third"]


def test_delete_removes_comment(client, highlight):
    created = client.post(
        f"/api/highlights/{highlight}/comments",
        json={"author": "Coach", "body": "to be deleted"},
    ).json()

    del_res = client.delete(f"/api/highlights/{highlight}/comments/{created['id']}")
    assert del_res.status_code == 200

    list_res = client.get(f"/api/highlights/{highlight}/comments")
    assert list_res.status_code == 200
    assert list_res.json() == []


def test_comment_on_unknown_highlight_is_404():
    app = FastAPI()
    app.include_router(comments.router)
    client = TestClient(app)

    unknown = f"no-such-highlight-{uuid.uuid4()}"

    get_res = client.get(f"/api/highlights/{unknown}/comments")
    assert get_res.status_code == 404

    post_res = client.post(
        f"/api/highlights/{unknown}/comments",
        json={"author": "Coach", "body": "hello"},
    )
    assert post_res.status_code == 404

    del_res = client.delete(f"/api/highlights/{unknown}/comments/{uuid.uuid4()}")
    assert del_res.status_code == 404


def test_comments_count_reflects_real_row_count_on_create_and_delete(client, highlight):
    assert _comments_count(highlight) == 0

    c1 = client.post(
        f"/api/highlights/{highlight}/comments",
        json={"author": "Coach", "body": "one"},
    ).json()
    assert _comments_count(highlight) == 1

    c2 = client.post(
        f"/api/highlights/{highlight}/comments",
        json={"author": "Coach", "body": "two"},
    ).json()
    assert _comments_count(highlight) == 2

    with SessionLocal() as db:
        actual_rows = (
            db.query(CommentDB).filter(CommentDB.highlight_id == highlight).count()
        )
    assert actual_rows == 2
    assert _comments_count(highlight) == actual_rows

    client.delete(f"/api/highlights/{highlight}/comments/{c1['id']}")
    assert _comments_count(highlight) == 1

    client.delete(f"/api/highlights/{highlight}/comments/{c2['id']}")
    assert _comments_count(highlight) == 0

    with SessionLocal() as db:
        actual_rows = (
            db.query(CommentDB).filter(CommentDB.highlight_id == highlight).count()
        )
    assert actual_rows == 0
