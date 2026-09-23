## Package: P6 — per-clip comment threads (backend only)

Owner:        opencode / unsloth/qwen3.8 (zero-cost capacity)
Priority:     **lowest in this spec.** It is real Veo parity but adds no analysis
              capability. If it cannot be done cleanly, report `blocked` and stop —
              that is a correct outcome, not a failure.
Files OWNED:  `backend/src/api/routes/comments.py` (NEW), `backend/tests/unit/test_comments.py` (NEW), and **append-only** edits to `backend/src/storage/database.py`
Files READ:   `backend/src/api/routes/matches.py`, `backend/src/storage/repository.py`, `backend/src/domain/models/match.py`, `backend/src/app/main.py`
Out of scope: everything else. Do **not** edit `main.py`, `matches.py`, `repository.py`, `match.py`, `ml_ingest.py`, `scripts/local/verify.py`, or anything under `frontend/`. Several agents are editing this repo right now; touching a file you do not own destroys their work.

### The gap

Real Veo gives every highlight clip its own comment thread at
`#/highlights/<uuid>/comments/`. `frontend/src/types/index.ts:32` already declares
`comments_count: number` on `Highlight`, and nothing anywhere produces or serves it.

### Contract

1. **Append** one SQLAlchemy model to `backend/src/storage/database.py`, following the
   style of the existing `HighlightDB` / `EventDB` classes already in that file:
   a comment row with an id, the highlight id it belongs to, an author string, the
   body text, and a created-at timestamp. Add it at the end of the file next to the
   other model classes. **Change no existing class.**
2. Create `backend/src/api/routes/comments.py` with its own `APIRouter` exposing:
   - list the comments on a highlight, oldest first
   - create a comment on a highlight
   - delete a comment by id
   A request naming a highlight that does not exist must return **404**, not an empty
   list. An empty thread on a real highlight returns `[]` and **200**.
3. **Do not register the router.** The integrator adds the one line to `main.py`.
   Say in your report exactly which line to add.
4. Create `backend/tests/unit/test_comments.py` covering, at minimum: an empty thread
   returns `[]`, a created comment is returned by the subsequent list call, ordering
   is oldest-first, deleting removes it, and a comment on an unknown highlight is a
   404. Use the same test style and fixtures as the existing files in
   `backend/tests/unit/`.

### The honesty rule applies here too

`comments_count` must be a **real count from the table**. Do not seed demo comments,
do not default it to a plausible-looking number, and do not invent author names. If
you cannot serve a real count without editing a file you do not own, leave the count
alone and say so — a missing count is honest, an invented one is not.

### Acceptance — run it and paste the real output

```sh
cd /home/ai/workspaces/users/jordi/ai-focus-play
backend/.venv/bin/python -m pytest backend/tests/unit/test_comments.py -q
backend/.venv/bin/python -m pytest backend/tests -q 2>&1 | tail -3
```

**Expected output:** the first command passes with at least 5 tests and 0 failures;
the second reports **at least 36 passed and 0 failed** (36 is the pre-existing count —
your new tests add to it; if any pre-existing test now fails, you broke something you
do not own and must revert it).

### Report

Return JSON only:
```json
{"package":"P6-comments","status":"complete|partial|blocked",
 "files_changed":["..."],"router_registration_line":"<the exact line for main.py>",
 "acceptance_command":"...","acceptance_output":"<real, pasted>",
 "deviations":["..."],"not_done":["..."]}
```
