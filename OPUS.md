# OPUS.md — Improvement Plan for the Veo Clone (`ai-focus-play`)

**Audience:** the coding agent (Gemini) that will implement these changes.

**Intent source:** the Antigravity artifacts at
`~/.gemini/antigravity/brain/47cd424a-0ece-43cc-ad7f-3b180a26c17c/` —
`implementation_plan.md` (the architecture promised) and `walkthrough.md` (the
capabilities claimed as delivered).

**This document is the delta between those claims and the code that actually exists.**
Every finding below was verified by reading the repository. File and line references are
accurate as of the SQLite + read-only refactor (`backend/src/storage/database.py` present,
`frontend/src/components/BurgerMenu.tsx` present, ~4,790 lines of app code).

> If a line number below no longer matches, the surrounding code has moved — search for the
> quoted snippet instead. The finding is still valid unless the quoted code is gone.

---

## How to use this document

1. Work **top to bottom**. P0 → P1 → P2 → P3. Do not start a P1 until every P0 is done.
2. Each task gives **Evidence** (file:line proving it), **Do this** (the concrete change),
   and **Verify** (how to prove it is fixed).
3. Do not refactor anything not named in a task. Do not rename or move files except where
   a task says so explicitly.
4. Run that task's verification before moving on.
5. The demo match `demo-arlington-skyline` must keep working throughout.

### Ground rules

- Backend: FastAPI, run from the **repo root** as `uvicorn backend.src.app.main:app`
  (imports are absolute `from backend.src...`). Keep it that way.
- Frontend: React 19 + Vite 8 + Tailwind 4. Vite proxies `/api` and `/media` to
  `127.0.0.1:8000` (`frontend/vite.config.ts`). Keep the proxy.
- Storage: SQLite via SQLAlchemy at `backend/.local/data/veo.db`
  (`backend/src/storage/database.py`).
- Python env: `backend/.venv`. `ffmpeg` / `ffprobe` at `/usr/bin/`.
- Tests: `backend/.venv/bin/python -m pytest backend/tests -q` from the repo root.
  Currently **8 passed**.

---

## Section 0 — What actually exists today

| Area | File | Lines | Reality |
| :-- | :-- | --: | :-- |
| CV "engine" | `backend/src/services/pipeline/cv_engine.py` | 419 | **Unchanged by the refactor.** Contour blobs + hardcoded events. No tracking, no ReID, no OCR, no ball detection. |
| Video utils | `backend/src/services/pipeline/video_processor.py` | 148 | Genuinely works: ffprobe, thumbnail, stream-copy clip cut, synthetic demo video. |
| REST API | `backend/src/api/routes/matches.py` | 258 | Works, but read-only mode contradicts the upload pipeline (**P0-1**). |
| DB schema | `backend/src/storage/database.py` | 143 | 8 tables. Missing indexes (**P2-2**). |
| Repository | `backend/src/storage/repository.py` | 465 | SQLAlchemy sessions. Loads all radar frames at once (**P2-1**). |
| Player | `frontend/src/components/VideoPlayer/VideoPlayer.tsx` | 427 | Real controls, real telestrator, real pan/zoom, real floating radar. |
| Sidebar | `frontend/src/components/Sidebar/SidebarTabs.tsx` | 455 | Drawer renders; some actions are `alert()` stubs. |
| Radar | `frontend/src/components/PitchRadar/PitchRadar.tsx` | 326 | Real SVG pitch, trails, tactical lines, rotate. |
| Upload UI | `frontend/src/components/UploadModal.tsx` | 190 | **Orphaned — imported by nothing** (**P0-1**). |

**~4,790 lines total.** The UI shell is genuinely good and the SQLite layer is a real
improvement. The intelligence layer underneath is not real, and the read-only refactor
left the write paths half-disconnected. That is what this plan fixes.

> `walkthrough.md` states as delivered: *"2D Pitch Radar tracks player positions
> synchronously with video playback"*, *"Live ball tracking dot"*, *"Jersey number
> detection to associate track IDs"*, *"Team jersey color clustering (HSV/Lab space)"*.
> **None of those four are true in the code.** P1-1 through P1-3 address exactly that gap.

---

# P0 — Broken right now

## P0-1. Read-only mode broke the upload pipeline; the upload UI is orphaned

The read-only refactor disabled writes at the repository layer but left the upload path
calling them. **Every upload now fails.**

**Evidence:**
- `backend/src/storage/repository.py:117-119`:
  ```python
  def add_highlight(self, highlight: Highlight):
      # Enforce read-only constraint as explicitly requested by user
      raise PermissionError("Read-only mode: Creating or writing new clips is disabled.")
  ```
- `backend/src/api/routes/matches.py:94` — inside `process_uploaded_video_task`, still:
  ```python
  match_repo.add_highlight(h)
  ```
  So the background task runs the whole CV pipeline, saves radar frames and events, then
  raises `PermissionError` on the first highlight. The `except` at `:104-108` catches it
  and sets `status="error"`. The user waits through a full analysis and gets a failure.
- `POST /api/matches/upload` (`matches.py:126`) is still registered and still accepts files.
- `frontend/src/App.tsx:90` — the header's upload button is now
  `onClick={() => alert('Read-Only Mode: Uploading or creating new match clips is disabled.')}`
- `frontend/src/components/UploadModal.tsx` (190 lines) is imported by **nothing**.

So: the backend accepts uploads that are guaranteed to fail, the frontend has a working
upload modal that is unreachable, and the button that would open it shows an `alert`.

**Do this — pick ONE and make the whole stack agree with it:**

**Option A — read-only is the intended product.** Then be consistent:
1. Delete `POST /api/matches/upload`, `process_uploaded_video_task`, and the unused
   imports it drags in (`shutil`, `BackgroundTasks`, `cv_engine`, `UploadFile`, `File`, `Form`).
2. Delete `frontend/src/components/UploadModal.tsx`.
3. Replace the `alert` at `App.tsx:90` with a disabled button carrying a `title`
   explaining why, or remove the control from `Header.tsx` entirely.
4. Say so in the API: `GET /api/capabilities` returning `{"read_only": true}`, and have the
   frontend hide every write affordance from that flag rather than hardcoding.

**Option B — uploads should work (recommended; it is the product's whole premise).** Then:
1. Replace the blanket `PermissionError` with a real flag:
   ```python
   # backend/src/config.py
   READ_ONLY = os.getenv("AIFP_READ_ONLY", "0") == "1"
   ```
   Guard the **HTTP layer** with it (`matches.py:188`, `:192` → 403 when `READ_ONLY`), and
   leave the repository able to write. Authorization belongs in the route, not in the
   storage layer — the pipeline is not a user.
2. Give the repository an internal write path the pipeline uses:
   `add_highlight(highlight, *, internal: bool = False)`, refusing only when
   `READ_ONLY and not internal`.
3. Re-wire `UploadModal` into `App.tsx` behind the capabilities flag.

**Verify:** with the chosen option, `POST /api/matches/upload` either returns 405/404
cleanly (A) or produces a match that reaches `status="ready"` with highlights (B). Add a
test for whichever you chose — there is currently **no test that touches the upload path
at all**, which is why 8/8 pass while it is broken.

---

## P0-2. `currentTime` in `App.tsx` is dead state

**Evidence:** `frontend/src/App.tsx:21` declares
`const [currentTime, setCurrentTime] = useState(0);`
Grep the file: the only other `currentTime` hits are `:145` and `:153`, both
`v.currentTime = …` on a DOM element — a different thing. **`setCurrentTime` is never
called and `currentTime` is never read.** It is a dead variable that `oxlint` should be
flagging.

The underlying cause: `VideoPlayer` keeps playback time in its own state
(`VideoPlayer.tsx`, `handleTimeUpdate`) and has no `onTimeUpdate` prop, so `App` has no
way to know the playhead position. Consequently `SidebarDrawer` cannot highlight the
current moment, and nothing outside the player can react to playback.

**Do this:**
1. Add to `VideoPlayerProps` (`VideoPlayer.tsx:13`):
   ```ts
   onTimeUpdate?: (time: number) => void;
   onDurationChange?: (duration: number) => void;
   ```
2. Call them from `handleTimeUpdate`, `handleLoadedMetadata`, and `seekTo` (so seeks
   propagate immediately rather than waiting for the next `timeupdate` tick).
3. **Throttle.** `timeupdate` fires ~4x/sec and lifting it re-renders the tree. Only emit
   when the value moved ≥ 0.1s:
   ```ts
   const lastSentRef = useRef(0);
   if (Math.abs(t - lastSentRef.current) >= 0.1) { lastSentRef.current = t; onTimeUpdate?.(t); }
   ```
4. Pass `onTimeUpdate={setCurrentTime}` in `App.tsx` and thread `currentTime` into
   `SidebarDrawer` so the Events and Highlights lists can mark the active entry.

**Verify:** play the demo; the sidebar's current event highlights and advances. Then
delete the `currentTime` state and confirm TypeScript errors — proving it is now load-bearing.

---

## P0-3. Seeking scrapes the DOM instead of using the player

**Evidence:** `App.tsx:142-157`:
```ts
onSeek={(time) => { const v = document.querySelector('video'); if (v) { v.currentTime = time; } }}
onPlayAllHighlights={() => {
  const v = document.querySelector('video');
  if (v) { v.currentTime = highlights[0].start_time; v.play(); }
}}
```
`document.querySelector('video')` grabs the *first* video in the document — wrong the
moment a second `<video>` exists (a clip preview, an ad, a thumbnail preview). It also
bypasses React entirely, so the player's own `currentTime` state only catches up on the
next `timeupdate` event, and `v.play()`'s rejected promise is unhandled.

**Do this:**
1. In `VideoPlayer.tsx`, export a handle and wrap with `forwardRef` + `useImperativeHandle`:
   ```ts
   export interface PlayerHandle {
     seekTo: (t: number) => void;
     play: () => Promise<void>;
     pause: () => void;
     playHighlightReel: (highlights: Highlight[]) => void;
   }
   ```
2. Hold `const playerRef = useRef<PlayerHandle>(null)` in `App.tsx` and replace both
   handlers with `playerRef.current?.…`.
3. **Delete every `document.querySelector` from `App.tsx`.**

**Verify:** highlight cards and "Play all" still seek correctly, and
`grep -c "document.querySelector" frontend/src/App.tsx` returns 0.

---

## P0-4. "Play all" plays one clip then runs forever

**Evidence:** `App.tsx:149-157` seeks to `highlights[0].start_time` and calls `play()`.
There is no logic to stop at `end_time` or advance to the next highlight. It is a
seek-to-first-highlight button labelled "Play all". `walkthrough.md` claims
*"Plays an automated highlight reel continuously."*

**Do this** — implement `playHighlightReel` in `VideoPlayer.tsx`:
1. State: `reelQueue: Highlight[] | null` and `reelIndex: number`.
2. `playHighlightReel(hs)` sorts by `start_time`, stores the queue, seeks to the first
   `start_time`, plays.
3. In `handleTimeUpdate`, when a reel is active and `t >= reelQueue[reelIndex].end_time`:
   advance and seek to the next clip, or stop and clear the queue after the last one.
4. Show a reel indicator — `Clip 2 / 5 — Goal - 10 Eric Jordi` — with a **Stop reel** button.
5. Clear the reel on any manual seek so the user can escape it.

**Verify:** "Play all" on the demo visits all 5 highlight windows in order and stops.

---

## P0-5. Goal confetti fires ~6 times per goal

**Evidence:** `VideoPlayer.tsx:67-78`. The effect depends on `[currentTime, events]` and
fires whenever `Math.abs(e.timestamp - currentTime) < 0.8`. `timeupdate` runs ~4x/sec, so
the 1.6-second window triggers roughly six consecutive bursts per goal, and re-triggers on
every scrub across it.

**Do this:**
```ts
const celebratedRef = useRef<Set<string>>(new Set());
useEffect(() => {
  const goal = events.find(e =>
    e.event_type.toLowerCase() === 'goal' &&
    currentTime >= e.timestamp && currentTime < e.timestamp + 0.8
  );
  if (goal && !celebratedRef.current.has(goal.id)) {
    celebratedRef.current.add(goal.id);
    confetti({ particleCount: 120, spread: 70, origin: { y: 0.7 } });
  }
}, [currentTime, events]);
```
Clear the set when `match.id` changes. Skip confetti entirely when
`window.matchMedia('(prefers-reduced-motion: reduce)').matches`.

**Verify:** play across the 18s goal — exactly one burst. Scrub back and forth — no repeat.

---

## P0-6. The scoreboard is hardcoded to "ARL" and "SKY"

**Evidence:** `VideoPlayer.tsx:227` and `:231` render the literal strings `ARL` and `SKY`.
Any other match — the BurgerMenu advertises a club switcher over "140 Teams" — displays
Arlington vs Skyline regardless of the actual teams.

**Do this:** derive the abbreviation from the real names:
```ts
const abbr = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase().slice(0, 3)
  || name.slice(0, 3).toUpperCase();
```
Use `abbr(match.home_team)` / `abbr(match.away_team)`, full name in a `title`. Keep the
gold/blue colors.

**Verify:** switch matches in the burger menu — the scoreboard follows the selection.

---

## P0-7. The match video is set to `loop`

**Evidence:** `VideoPlayer.tsx:296` — `loop` on the `<video>`. A match analysis tool must
not silently restart at 00:00 at the final whistle, and it makes the P0-4 reel wrap
unpredictably.

**Do this:** remove `loop`; add `onEnded` that pauses and shows a
"Match ended — Replay / Jump to first highlight" overlay.

**Verify:** let the 90s demo run to the end — it stops and shows the overlay.

---

## P0-8. Absolute `/home/ai/...` paths in three files

**Evidence:**
- `backend/src/storage/database.py:12` — `DB_DIR = Path("/home/ai/workspaces/users/jordi/ai-focus-play/backend/.local/data")`
- `backend/src/storage/repository.py` — same prefix (pre-refactor `DATA_DIR`)
- `backend/src/services/pipeline/video_processor.py:10` — same prefix for `MEDIA_DIR`

The app cannot run on another machine, in a container, or from another checkout path.
The refactor added a **third** copy of the hardcoded prefix rather than removing it.

**Do this** — create `backend/src/config.py` as the single source:
```python
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("AIFP_DATA_DIR", REPO_ROOT / "backend" / ".local" / "data"))
MEDIA_DIR = Path(os.getenv("AIFP_MEDIA_DIR", REPO_ROOT / "backend" / ".local" / "media"))
DB_PATH = DATA_DIR / "veo.db"
MAX_UPLOAD_BYTES = int(os.getenv("AIFP_MAX_UPLOAD_BYTES", 8 * 1024 * 1024 * 1024))
READ_ONLY = os.getenv("AIFP_READ_ONLY", "0") == "1"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
```
Import from it everywhere; delete all three hardcoded constants. Keep re-exporting
`MEDIA_DIR` from `video_processor` so existing imports keep working, or update them.

**Verify:** `cp -r` the repo to `/tmp/aifp-copy`, run the tests from there, and they pass.

---

# P1 — The CV pipeline is not what the documents claim

`implementation_plan.md` promises YOLOv11 + ByteTrack, HSV/Lab kit clustering, jersey OCR,
and ball-trajectory event spotting. `cv_engine.py` implements none of it, and the SQLite
refactor did not touch the file — **every line reference below is current.**

## P1-0. Decide and declare the analysis mode (do this first)

The code presents fabricated output as AI analysis. Fix the honesty before the accuracy.

**Do this:**
1. Add to `Match` (`backend/src/domain/models/match.py`) and to `MatchDB`
   (`backend/src/storage/database.py`):
   ```python
   analysis_mode: str = "heuristic"   # "heuristic" | "demo" | "ml"
   analysis_confidence: str = "low"   # "low" | "medium" | "high"
   ```
   The schema is created with `Base.metadata.create_all` (`database.py:141`), which does
   **not** alter existing tables — ship a small migration that `ALTER TABLE`s the columns
   in if absent, or delete and reseed `veo.db`.
2. `demo` for the seeded `demo-arlington-skyline` and anything from
   `_generate_fallback_tracking`; `heuristic` when the contour pipeline ran on real frames.
3. Render a badge next to the match title in `Header.tsx`:
   - `demo` → amber "Demo data — not from this video"
   - `heuristic` → grey "Heuristic analysis — positions approximate"
   - `ml` → green "AI analysis"
4. Show the same badge at the top of the Analytics drawer. Those possession, pass and
   tackle numbers are fiction (see P1-4) and must not read as measurements.

**Verify:** the demo match shows an amber badge in the header and on the Analytics drawer.

---

## P1-1. Ball position is a sine wave, not a detection

**Evidence:** `cv_engine.py:158-159`:
```python
ball_x = 52.5 + 30.0 * math.sin(current_time * 0.2)
ball_y = 34.0 + 18.0 * math.cos(current_time * 0.18)
```
The frame is decoded, then discarded, and the "ball" is a Lissajous curve. Same at `:384`
in `_generate_fallback_tracking`. `walkthrough.md` advertises "Live ball tracking dot".

**Do this (heuristic tier — no model download):**
1. Detect candidates per sampled frame on the non-field mask already computed at
   `cv_engine.py:126`: contours with `20 < area < 400` (at `scale=0.5`), circularity
   `4*pi*area/perimeter**2 > 0.6`, high HSV value. Take the best-scoring one.
2. Smooth with a constant-velocity Kalman filter (`cv2.KalmanFilter(4, 2)`, state
   `[x, y, vx, vy]`). Predict every sampled frame; correct only on a real candidate.
3. After > 2.0s with no candidate, mark the frame's ball `detected=False` rather than
   inventing a position.
4. Add `detected: bool = True` to `RadarBall` in `models/match.py` **and** to `RadarBall`
   in `frontend/src/types/index.ts`. Render an undetected ball at 30% opacity, no trail.
5. **Delete the sine fallback from the real-video path.** It may remain only inside
   `_generate_fallback_tracking`, which must set `analysis_mode="demo"`.

**Verify:** add `backend/tests/unit/test_ball_tracking.py` — synthesize a 5-second clip
with one white circle moving in a straight line (`cv2.VideoWriter`), assert recovered
pitch-x increases monotonically and `detected` is true on ≥ 80% of frames.

---

## P1-2. Team assignment is a global brightness threshold

**Evidence:** `cv_engine.py:137-138`:
```python
mean_val = np.mean(player_roi)
team = "home" if mean_val > 110 else "away"
```
A fixed threshold on mean BGR across the whole player box. It collapses to one team when
the sun moves, when both kits are mid-tone, or when exposure shifts.
`implementation_plan.md` promised "Team jersey color clustering (HSV/Lab space)".

**Do this:**
1. Use the **torso** only — vertically `y + 0.2h` to `y + 0.6h`, horizontally the middle
   60%. Legs and grass contaminate the full box.
2. Convert to Lab, mask out grass-green HSV pixels, take the **median** `(a, b)` chroma
   pair (median, not mean — robust to shadow and the ball).
3. Pool these vectors across the first 60 sampled frames, then `cv2.kmeans` with `K=3`
   (home, away, referee/GK).
4. Store the centers on the engine and classify later frames by nearest center. Assign the
   two largest clusters to home/away; home is the cluster with lower mean pitch-x during
   the first 10% of the match, unless overridden.
5. Add `POST /api/matches/{id}/teams/swap` to flip `team` on every stored radar frame and
   event, plus a "Swap teams" button in the Analytics drawer, so a coach can correct it.

**Verify:** `backend/tests/unit/test_team_clustering.py` — synthesize 6 red and 6 blue
rectangles on green; assert each color lands in its own cluster (≤ 1 misassignment).

---

## P1-3. There is no tracking — identities reshuffle every frame

**Evidence:** `cv_engine.py:143-152`. `p_id` is a counter restarting at `1` on every
sampled frame, in whatever order `cv2.findContours` returns blobs.
`RadarPlayer.id = p_id` and `jersey = str(p_id) if p_id <= 11 else str(p_id - 11)`
(`:148`). "Player #3" is a different human in every frame. And `:151`:
```python
speed=round(float(np.random.uniform(1.0, 5.0)), 1)
```
The speed readout is **literally a random number generator.**

**What this breaks in the product:**
- Radar dots teleport and swap jersey labels twice a second.
- **Player Moments** — the flagship feature, given its own pill bar
  (`frontend/src/components/PlayerMomentsBar.tsx`) and toolbar slot — is meaningless on
  uploaded video: it filters on an arbitrary contour ordinal.
- `PitchRadar` trails connect unrelated players.

**Do this:**
1. New file `backend/src/services/pipeline/tracker.py`:
   - Tracks as `{id, x, y, vx, vy, team, misses, hits}` in **pitch meters**, not pixels —
     you already have the homography, and metric space is scale-stable.
   - Per frame: predict by `(vx, vy) * dt`, then solve assignment with
     `scipy.optimize.linear_sum_assignment` (**scipy is already installed** in
     `backend/.venv`). Cost = Euclidean metres; reject pairings over **4.0 m** (nobody
     covers more in one 0.5s sample).
   - Unmatched detections spawn a track after 3 consecutive hits; unmatched tracks die
     after 6 consecutive misses. IDs are stable and monotonic.
2. Use the tracker's stable `id` in place of the per-frame `p_id`.
3. `speed = hypot(vx, vy)` clamped to `[0, 12]` m/s. **Delete `np.random.uniform`.**
4. **Do not fabricate jersey numbers.** Set `jersey=None` unless a number was really read.
   Render unnumbered dots as plain colored circles with the track id on hover.
5. Populate the Player Moments pill bar from tracks that genuinely have a jersey. When none
   do, show "Jersey numbers not detected for this match — showing tracked players" and list
   track IDs. Note the bar currently renders `match.lineup` — the **roster**, not detections
   — so it always shows a full jersey list even for a video where nothing was detected.

**Verify:** `backend/tests/unit/test_tracker.py` — two players walking past each other over
10 frames keep their IDs through the crossing and no ID is reused. Visually: radar dots
move continuously instead of teleporting.

---

## P1-4. Match statistics are hardcoded constants that contradict the events

**Evidence:** `cv_engine.py:340-352`. `_calculate_analytics` takes `radar_frames` and
position lists, then returns literals:
```python
home_stats=TeamStats(goals=1, shots=6, attempts=8, corners=4, free_kicks=5,
                     throw_ins=14, fouls=6, penalties=0, tackles=26,
                     passes_completed=142, possession_percent=52.0, ...)
```
Meanwhile `_extract_match_events` in the same file (`:209-300`) emits **two** goals for
that same match. The Analytics drawer shows `goals=1` while the Events drawer lists two
goals, for one video.

The shot map (`:355-360`) is pinned to absolute timestamps `15.0, 32.0, 48.0, 64.0`
regardless of duration — upload a 20-second clip and it claims a shot at 64 seconds.

Only `pass_locations` / `possession_locations` derive from real positions (`:320-336`),
and even those fall back to literals via `or 15.0` when a third computes to exactly `0.0`.

**Do this — every stat must be either computed or absent:**
1. **Derivable now:** `possession_percent`, `possession_minutes`, the thirds breakdowns,
   and `goals` (count the Goal events actually emitted).
   **Not derivable without real event detection:** `passes_completed`, `tackles`, `fouls`,
   `throw_ins`, `free_kicks`, `penalties`, `possession_won`, `pass_strings`. Make these
   `Optional[int]` and set them to `None`.
2. Render `None` in the Analytics drawer as a dimmed `—` with tooltip "Not measured —
   requires event detection". **Never as `0`, never as an invented number.**
3. Possession, honestly: per radar frame find the nearest player to the ball; if that
   distance is < 3.0 m credit that player's team one frame, else credit neither (loose
   ball). `possession_percent` is the share of *credited* frames;
   `possession_minutes = credited / sample_fps / 60`.
4. Build the shot map from the emitted events — keep `event_type in {"Shot", "Goal"}` and
   map each to a `ShotRecord` with that event's real `timestamp`, `pitch_x`, `pitch_y`,
   `team`. `is_inside_box` geometrically: `x > 88.5` (or `x < 16.5`) and `13.84 < y < 54.16`.
   **Delete the four literal `ShotRecord`s.**
5. `TeamStats.goals` must equal `len([e for e in events if e.event_type == "Goal" and e.team == side])`.
   The two drawers must never disagree again.

**Verify:** `backend/tests/unit/test_analytics_consistency.py` — for any generated match,
`analytics.home_stats.goals == len(home Goal events)`,
`len(shot_map) == len(Shot events) + len(Goal events)`, and every
`ShotRecord.timestamp <= match.duration_seconds`.

---

## P1-5. Events are generated at fixed percentages of the duration

**Evidence:** `cv_engine.py:209`:
```python
t_samples = [duration * 0.2, duration * 0.45, duration * 0.7, duration * 0.85]
```
Every video produces exactly: a kickoff at 1.0s, a home goal at 20%, a saved shot at 45%,
an away goal at 70%, a corner at 85% — with f-string descriptions naming jerseys #10, #14,
#9, #8. Upload footage of an empty pitch and the system reports a 1-1 draw with a corner kick.

**Do this — Option A first, it is what makes the pipeline honest:**

**Option A (heuristic spotting, ships this week).** Rewrite `_extract_match_events` around
the tracked ball from P1-1:
- **Kickoff:** first frame with the ball within 3 m of the centre spot *and* both teams in
  their own halves.
- **Shot:** ball speed > 12 m/s, velocity vector pointing at a goal mouth, entering the
  penalty area within 2 s.
- **Goal:** a shot, then the ball crossing `x < 0` or `x > 105` between the posts, then
  ≥ 3 s before it returns to the centre circle.
- **Corner / throw-in:** ball leaves the pitch bounds, then re-enters within 2 m of a
  corner arc, or from a touchline.
- Add `confidence: float` to `Event` and surface it in the Events drawer.
- **Emit nothing when nothing is detected.** An empty event list for a video with no soccer
  in it is the correct output and is far better than four fabricated goals.

**Option B (real models, later).** Add `ultralytics`, download a soccer-tuned YOLO
checkpoint to `backend/.local/models/`, run detection at 5 FPS, gate behind
`AIFP_ENABLE_ML=1` so the app still starts without weights, set `analysis_mode="ml"`.
Keep Option A as the fallback. **Do not start B before A works.**

**Verify:** run against `backend/.local/media/demo_match.mp4` — the synthetic ffmpeg
animation with an orbiting white dot and no goals. The event list must be short and mostly
empty, not a five-event match report. Then run on real footage and confirm the kickoff is found.

---

# P2 — Architecture and robustness

## P2-1. The radar endpoint ships the entire match to the browser

**Evidence:** `repository.py:221-224`:
```python
db_frames = db.query(RadarFrameDB).filter(RadarFrameDB.match_id == match_id)\
              .order_by(RadarFrameDB.timestamp.asc()).all()
return [RadarFrame(**json.loads(f.data)) for f in db_frames]
```
Every frame, every time, each one `json.loads`-ed individually. `matches.py:165-175`
returns the whole list when `time` is absent, and `api.ts` calls it with no `time`
(`App.tsx:54`), storing it all in React state.

The demo is 90 seconds → 180 rows. A real 90-minute match at 2 FPS is **10,800 rows**,
roughly **18 MB of JSON** parsed on match select, per match switch. Moving to SQLite did
not fix this — it moved the same full-scan into a query.

Then `VideoPlayer.tsx` runs a linear `reduce` **and** a `filter` over that array on every
`currentTime` change, ~4x/sec.

**Do this:**
1. `GET /api/matches/{id}/radar/window?start={s}&end={s}` → `WHERE timestamp BETWEEN ? AND ?`.
   This is the payoff of having moved to SQL; take it.
2. Add `GET /api/matches/{id}/radar/meta` → `{sample_fps, duration, frame_count}`.
3. Frontend: keep a sliding ~90-second window, prefetching the next chunk at 70% of the
   current one and evicting far chunks.
4. Replace the linear scans with binary search. Frames are sorted by `timestamp`. Write one
   shared `frontend/src/hooks/useRadarFrame.ts` doing `lowerBound(frames, t)` and returning
   `{ currentFrame, historyFrames }`.
5. Shrink the wire format: emit players as `[id, teamCode, x, y, speed]` tuples behind
   `?format=compact` and rehydrate client-side (~60% smaller).

**Verify:** seed a 90-minute radar dataset, load it, and confirm the initial payload is
< 1 MB with no frame drops during playback.

---

## P2-2. The SQLite schema has no index for its hottest query

**Evidence:** `database.py:113-122`. `RadarFrameDB` indexes only the autoincrement `id`.
`match_id` is a plain `ForeignKey` column with `index=False`, and `timestamp` is unindexed.
Every radar read is `WHERE match_id = ? ORDER BY timestamp` — a full table scan plus a sort
over what will be the largest table in the database by two orders of magnitude.

Related issues in the same layer:
- `engine = create_engine(..., connect_args={"check_same_thread": False})` (`:18`) with
  **no WAL pragma**. In rollback-journal mode a write locks the whole database, so an
  analysis run blocks every concurrent read.
- `save_radar_frames` (`repository.py:226-235`) deletes and re-inserts row by row with
  `db.add` in a Python loop — for 10,800 frames use `bulk_save_objects` or
  `executemany`, inside one transaction.
- `AnalyticsDB` and `ClubDB` have **no** `cascade="all, delete-orphan"` relationship
  (`database.py:124-136`), so `delete_match` leaves orphaned analytics rows forever.

**Do this:**
1. Add `Index("ix_radar_match_time", RadarFrameDB.match_id, RadarFrameDB.timestamp)`.
   Index `match_id` on `HighlightDB`, `EventDB`, `DrawingDB`, `LineupPlayerDB` too.
2. Enable WAL and sane durability on connect:
   ```python
   @event.listens_for(engine, "connect")
   def _set_pragmas(dbapi_conn, _):
       cur = dbapi_conn.cursor()
       cur.execute("PRAGMA journal_mode=WAL")
       cur.execute("PRAGMA synchronous=NORMAL")
       cur.execute("PRAGMA foreign_keys=ON")
       cur.close()
   ```
   Note `foreign_keys` is **OFF by default in SQLite** — the `ForeignKey` declarations in
   `database.py` are currently not enforced at all.
3. Bulk-insert radar frames in one transaction.
4. Give `AnalyticsDB` a cascading relationship, or delete its rows explicitly in
   `delete_match`.
5. Add a migration path. `create_all` never alters existing tables, so every schema change
   in this plan silently no-ops against an existing `veo.db`. Either adopt Alembic or write
   an explicit `migrate()` that checks `PRAGMA table_info` and `ALTER TABLE`s.

**Verify:** `EXPLAIN QUERY PLAN` on the radar query reports `USING INDEX ix_radar_match_time`
rather than `SCAN`. Time a 10,000-frame insert before and after the bulk change.

---

## P2-3. Uploads block the event loop and are unvalidated

*(Applies if you chose Option B in P0-1. If you chose Option A, delete the route instead.)*

**Evidence:** `matches.py:144-145`:
```python
with open(dest_path, "wb") as buffer:
    shutil.copyfileobj(file.file, buffer)
```
Synchronous copy inside an `async def` handler — for a multi-gigabyte match this blocks the
**entire** asyncio event loop for the whole upload, stalling every other request.

No validation at all: no size cap, no content-type check, no magic bytes.
`ext = Path(file.filename or "match.mp4").suffix` (`:141`) puts an attacker-controlled
suffix into a filesystem path. The UUID prefix prevents traversal, but a `.html` or `.svg`
suffix served back from the `/media` StaticFiles mount (`main.py:50`) is stored XSS on the
same origin.

**Do this:**
1. Stream off the event loop:
   ```python
   import anyio
   async with await anyio.open_file(dest_path, "wb") as f:
       total = 0
       while chunk := await file.read(1024 * 1024):
           total += len(chunk)
           if total > MAX_UPLOAD_BYTES:
               dest_path.unlink(missing_ok=True)
               raise HTTPException(413, "File exceeds maximum upload size")
           await f.write(chunk)
   ```
2. Whitelist extensions `{.mp4, .mov, .mkv, .webm, .m4v}` case-folded; 415 otherwise.
3. Probe before queueing analysis. Note `get_video_metadata` currently **swallows failures**
   and returns a fake `{"duration": 90.0, "width": 1920, ...}` on any exception
   (`video_processor.py:57-59`) — make it raise, and let the caller mark the match
   `status="error"` and clean up the file.
4. Serve media with `X-Content-Type-Options: nosniff`.

**Verify:** a 1-byte `evil.mp4` produces a readable error and is cleaned up; polling
`GET /api/matches` stays responsive throughout a large upload.

---

## P2-4. A 30-60 minute CV job runs in `BackgroundTasks`

**Evidence:** `matches.py:162` — `background_tasks.add_task(process_uploaded_video_task, ...)`.
Starlette runs this in the shared threadpool of the same process, and
`implementation_plan.md` itself estimates 30-60 minutes per match on CPU. The job dies
silently on restart (the dev server runs `reload=True`, `main.py:64`), a second upload
competes for the same threadpool, and there is no cancellation, retry, or queue view.

**Do this:**
1. `backend/src/domain/models/job.py` with
   `{id, match_id, kind, status, progress, step, started_at, finished_at, error, attempts}`,
   persisted as its own table.
2. Run jobs on a dedicated `ThreadPoolExecutor(max_workers=1)` owned by the app lifespan
   (`main.py:19-31`) — a real queue with serialized execution and a cancel handle. Better:
   a separate process so CV work cannot starve the API.
3. On startup mark `running` jobs as `interrupted` and offer **Resume analysis** rather than
   leaving a match stuck at 47% forever.
4. Add `GET /api/jobs` and `DELETE /api/jobs/{id}`.
5. Replace polling with SSE at `GET /api/matches/{id}/progress`.
   Note the current `App.tsx` has **no polling at all** — the progress `useEffect` was
   dropped in the refactor, so an uploaded match never leaves "processing" in the UI until
   a manual reload. Whichever path you choose, restore live progress.

**Verify:** start an upload, `Ctrl-C` the backend, restart. The match shows
"Analysis interrupted — Resume", not a permanent spinner.

---

## P2-5. CORS is configured in a combination browsers reject

**Evidence:** `main.py:42-48` — `allow_origins=["*"]` together with
`allow_credentials=True`. Per the Fetch spec a wildcard origin is invalid with
credentials; browsers refuse the response. It appears to work only because the Vite proxy
makes everything same-origin, so CORS never engages — a trap for the first real deployment.

**Do this:** read origins from an env var defaulting to
`["http://127.0.0.1:5173", "http://localhost:5173"]`, and set `allow_credentials=False`
until real auth exists. Never ship `*` with credentials.

---

## P2-6. Deleting a match leaks every file it owns

**Evidence:** `repository.py:84-89`. `delete_match` deletes the `MatchDB` row and relies on
ORM cascades. It never touches `MEDIA_DIR`: the source video, `{match_id}_thumb.jpg`, and
every `clip_{highlight.id}.mp4` survive forever.

**Do this:** in `DELETE /api/matches/{id}`, collect the file paths **before** deleting the
rows, then unlink each inside try/except. Guard every unlink with
`path.resolve().is_relative_to(MEDIA_DIR.resolve())` so a crafted `video_url` can never
delete outside the media directory. Log what was removed.

**Verify:** note `du -sh backend/.local`, upload, delete, confirm the size returns.

---

## P2-7. The test suite tests seed data, and one test cannot fail

**Evidence:** `backend/tests/unit/test_backend.py` — 8 tests, all passing. Six assert facts
about the hardcoded seed (`assert demo["home_score"] == 3`). They will keep passing no
matter how badly the pipeline breaks — which is exactly what happened: **8/8 pass right
now while the upload path is entirely broken (P0-1).**

`test_homography_projection` is structurally incapable of failing:
```python
x_m, y_m = engine.project_point_to_pitch(H, 960, 540)
assert 0.0 <= x_m <= PITCH_LENGTH
assert 0.0 <= y_m <= PITCH_WIDTH
```
`project_point_to_pitch` ends with `np.clip(dst, 0.0, PITCH_LENGTH)` (`cv_engine.py:52-54`).
The function clips to exactly the range asserted. It is a tautology.

`test_drawing_crud` writes to the **real** `veo.db` through the module-level singleton
(`repository.py`, `match_repo = MatchRepository()`), leaving residue in developer data.

**Do this:**
1. Make the homography test assert **known correspondences**: the four source corners
   (`cv_engine.py:30-35`) must map to `(0,0)`, `(105,0)`, `(105,68)`, `(0,68)` within 0.5 m,
   and the image centre near the pitch centre. To test out-of-bounds behaviour at all,
   change `project_point_to_pitch` to return `(x, y, in_bounds)` instead of silently
   clipping, and update its two call sites.
2. Isolate the repository: point `AIFP_DATA_DIR` / `AIFP_MEDIA_DIR` (from P0-8) at
   `tmp_path` and construct the repository per test. This needs `match_repo` to become a
   lazy `get_repository()` accessor — do that and update the import sites.
3. **Add an upload-path test.** A test that posts a small real video and asserts the match
   reaches `status="ready"` would have caught P0-1 immediately.
4. Add the pipeline tests named above: `test_ball_tracking.py`, `test_tracker.py`,
   `test_team_clustering.py`, `test_analytics_consistency.py`.
5. Add frontend tests — there are currently **zero** and no runner installed. Add `vitest`
   + `@testing-library/react`; cover the P0-2 time propagation, the P2-1 radar hook, and
   the P0-4 reel advance.

**Verify:** both suites pass; then transpose x and y in `project_point_to_pitch` and confirm
the homography test now **fails**.

---

## P2-8. The project is not under version control, and has no dependency manifest

**Evidence:** `.git/` exists but holds only empty `hooks/` and `info/` —
`git rev-parse --is-inside-work-tree` returns `fatal: not a git repository`. There is no
history for ~4,790 lines. Given that this codebase is being edited by more than one agent
concurrently, the absence of version control is the largest process risk in the project.

There is also **no `backend/requirements.txt`** — `backend/` contains only `src` and `tests`,
so the Python dependency set (now including SQLAlchemy) exists nowhere but in `.venv`.

**Do this:**
1. `git init`; root `.gitignore` covering `backend/.venv/`, `__pycache__/`, `*.pyc`,
   `.pytest_cache/`, `node_modules/`, `frontend/dist/`, `backend/.local/`, `.DS_Store`.
2. Initial commit before any further edits.
3. Write `backend/requirements.txt` pinning what is installed: `fastapi`, `uvicorn`,
   `python-multipart`, `sqlalchemy`, `opencv-python-headless`, `numpy`, `scipy`,
   `pydantic`, `pytest`, `httpx`.
4. `frontend/package.json:2` still reads `"name": "temp-vite"` — rename it.
5. Write a real root `README.md`. `frontend/README.md` is the untouched Vite template.

---

# P3 — UX, detail correctness, accessibility

## P3-1. Errors are swallowed; stubs remain

`App.tsx` catches into `console.error` at `:41` and `:63` — a failed match load and a failed
detail fetch both look like an empty library. `api.ts` is worse: `getHighlights`,
`getEvents`, `getRadarFrames`, `getDrawings` all `return []` on a non-OK response
(lines 29, 51, 61, 72), making "server down" indistinguishable from "no highlights".

Remaining `alert()` stubs:
- `App.tsx:90` — upload (see P0-1)
- `Header.tsx:106` — "Compiling highlight clips into export package…" (**nothing is exported**)
- `BurgerMenu.tsx:134` — "No new notifications or mentions."
- `BurgerMenu.tsx:176` — "Veo Knowledge Base: Support & Documentation is active."
- `Sidebar/RightToolbar.tsx` — two more `alert()` calls in the tool rail

**Do this:** make `api.ts` throw a typed `ApiError { status, message, url }` and never mask
a failure with `[]`. Add a small `ToastProvider` context (no library) and surface errors
with a retry where retrying makes sense. Distinguish "No highlights yet" from
"Couldn't load highlights — Retry". Add a React error boundary around the workspace.
For each `alert`: implement it, or remove the control. A **Download all** that really
works is a backend endpoint streaming a `zipfile` of the existing `clip_*.mp4` files —
that one is worth building.

## P3-2. Match switching races

`selectMatch` (`App.tsx:47-65`) fires five parallel fetches with no cancellation. Click
match A then B quickly and A's slower responses can land after B's, painting B's header
with A's highlights. Thread an `AbortController` through every `api.*` call, abort the
previous controller in `selectMatch`, ignore `AbortError`, and guard each `setState` with
a `requestIdRef` check.

## P3-3. Pan/zoom is laggy, unbounded, and sticks

- `VideoPlayer.tsx:297` — the `<video>` carries `transition-transform duration-75`, so every
  `mousemove` during a drag is animated, adding 75 ms of lag to a direct-manipulation
  gesture. Disable the transition while panning.
- `panX`/`panY` are unbounded. The user can drag the video off-screen with no way back.
  Clamp so ≥ 25% stays visible and add a visible **Reset view** button.
- `onMouseUp` is bound only to the inner div (`:219`) — release outside the element and
  `isPanning` stays `true`, so the video then follows the cursor with no button held. Use
  Pointer Events with `setPointerCapture`, or a `window`-level `pointerup`.
- `handleWheel` calls `e.preventDefault()` (`:191`) in a React synthetic handler on a
  passive listener — React 19 warns and the scroll is not reliably blocked. Attach a
  non-passive `wheel` listener via `useEffect` + `addEventListener(..., { passive: false })`.

## P3-4. The keyboard handler re-registers four times a second

`VideoPlayer.tsx:80-…` — the effect depends on mutable playback values and does
`addEventListener` / `removeEventListener` on `window`. Since `currentTime` changes ~4x/sec,
the listener is torn down and rebuilt ~4x/sec for the whole session. Put the mutable values
in refs and give the effect an empty dependency array. Also gate `Space` so it does not
fire while the burger menu or a drawer input has focus.

## P3-5. `togglePlay` double-manages state and ignores a rejected promise

`togglePlay` calls `play()`/`pause()` **and** `setIsPlaying(!isPlaying)`, while the
`onPlay`/`onPause` handlers set the same state — two writers, guaranteed to desync.
`play()` returns a promise that rejects under autoplay policy, unhandled, leaving the UI
showing "playing" over a paused video. Let the media events be the only writer; `await` the
play promise in a try/catch that surfaces a toast.

## P3-6. Dead code and unfinished claims

- `frontend/src/components/UploadModal.tsx` (190 lines) — imported by nothing (P0-1).
- `GET /api/matches/{id}/player-moments` (`matches.py:201`) is implemented and **never
  called** — `api.ts` has no method for it. Either use it (it is the right home for
  server-side filtering once matches get long) or delete it.
- `frontend/src/App.css` (184 lines) — leftover Vite template (`.counter`, `.hero`). The app
  is entirely Tailwind. Delete it and its import.
- `frontend/src/assets/react.svg`, `vite.svg`, `hero.png` — template leftovers.
- `AnalyticsData.heatmaps` exists in the Pydantic model (`match.py:104-107`) and the TS type
  (`types/index.ts:119-122`), is always `{"home": [], "away": []}`, and is never rendered.
  `implementation_plan.md` Phase 4 lists "2D pitch heatmaps with time-interval slider" as a
  deliverable — with real tracked positions from P1-3 you can bin into a 20×13 grid,
  normalize, and overlay on the existing `PitchRadar`. Build it or drop the field.
- `PlayerRoster.minutes_played` exists on the model but the UI hardcodes `'90 mins played'`.
  Use the field.
- `Match.panoramic_url` is always set to the same value as `video_url`
  (`matches.py:153-154`), so the "Interactive 180°" toggle switches between two identical
  sources — it is a CSS pan over a flat video, not a panoramic projection.
  `implementation_plan.md` specifies a WebGL/Three.js spherical projection. Build it, or
  **rename the control to "Pan & Zoom"**, which is what it honestly does.
- `ClubDB` (`database.py:131-136`) is seeded and queried for the burger menu's
  "Arlington Soccer · 140 Teams" card, but there is exactly one club and no switcher
  backend. Either implement club switching or label the card as static.

## P3-7. Accessibility

Every control in the player, toolbar and burger menu is an icon-only `<button>` with a
`title` and no `aria-label`. The video surface toggles playback from an `onClick` on a plain
`<div>` — not focusable, no role, no keyboard path. The radar SVG has no `role="img"` or
description. Colour is the only channel distinguishing home from away.

**Do this:** `aria-label` on every icon button; `role="button"`, `tabIndex={0}` and an
Enter/Space `onKeyDown` on the video surface; `role="img"` plus `<title>`/`<desc>` on the
radar SVG; a shape or pattern difference between home and away dots; visible
`:focus-visible` rings that survive the Tailwind reset; honour `prefers-reduced-motion`.
The `RightToolbar` rail and `BurgerMenu` drawer also need focus trapping and `Escape` to
close — neither currently has it.

## P3-8. Narrow viewports

`App.tsx:85` is `flex-col h-screen w-screen overflow-hidden`, with the drawer and the fixed
right rail competing for width. Below ~900 px the video region collapses. Make the drawer a
full-width slide-over under `lg`, collapse the rail to a single menu button, and let the
video keep its aspect ratio.

---

# Suggested order of work

| Step | Tasks | Why |
| :-- | :-- | :-- |
| 1 | **P0-1** | The stack currently contradicts itself. Nothing else matters until upload-vs-read-only is decided. |
| 2 | P2-8 | Version control **before** more edits — this repo has concurrent writers. |
| 3 | P0-8 | Portability; also unblocks the test isolation in P2-7. |
| 4 | P0-2, P0-3, P0-5, P0-6, P0-7 | Small, visible, low-risk player fixes. |
| 5 | P1-0 | Stop presenting fabricated output as analysis. |
| 6 | P0-4 | Finish the half-built reel. |
| 7 | P2-2, P2-6 | Schema indexes, pragmas, migrations, file cleanup. |
| 8 | P1-1, P1-3, P1-2 | Real ball, real tracks, real teams — **in that order**. |
| 9 | P1-4, P1-5 | Stats and events grounded in the tracks from step 8. |
| 10 | P2-1, P2-3, P2-4 | Scale: radar windowing, safe uploads, a real job queue. |
| 11 | P2-7 | Lock it in with tests that can actually fail. |
| 12 | P3-* | Polish. |

**Do not** attempt P1-4 or P1-5 before P1-1 and P1-3. Statistics and event detection both
depend on a real ball trajectory and stable player identities; building them on the
sine-wave ball would only produce a more elaborate fiction.

---

# Definition of done

- [ ] `backend/.venv/bin/python -m pytest backend/tests -q` passes, **including a test that
      exercises the upload path**.
- [ ] `cd frontend && npm run build` succeeds with no TypeScript errors.
- [ ] `cd frontend && npm run lint` is clean.
- [ ] The demo match `demo-arlington-skyline` still loads and plays.
- [ ] No `alert()` remains in `frontend/src/`.
- [ ] No absolute `/home/` path remains in `backend/src/`.
- [ ] No `document.querySelector` remains in `frontend/src/App.tsx`.
- [ ] No orphaned component files remain (`UploadModal.tsx` either wired up or deleted).
- [ ] Every number in the Analytics drawer is either computed from the video or rendered as
      `—` with an explanatory tooltip. No literal stat constants survive in `cv_engine.py`.
- [ ] Every capability described in `walkthrough.md` is either true of the code, or the
      description has been corrected.

## The rule that matters most

When a capability is not implemented, **show that it is not implemented.** An empty state,
a dimmed `—`, or a "not detected" badge is a correct and useful answer. A plausible
fabricated number is not — a coach making a substitution on the basis of an invented
possession statistic is the worst outcome this product can produce. Every task in P1 exists
to enforce that rule.
