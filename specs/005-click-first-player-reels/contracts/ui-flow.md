# UI Flow Contract: Click-First Player Reels

**Input**: [spec.md](../spec.md), [api.yaml](./api.yaml)
**Scope**: Screen-by-screen behavioral contract for the frontend. Implementation must
satisfy every "MUST" here. Copy strings are normative unless marked (example).

## Global rules

- The wizard has exactly three steps, labeled **"Add video" → "Find your player" →
  "Build the reel"** (update `guidedStepLabels` in the wizard shell).
- All copy is plain language: no model names (never "SAM 2", "RT-DETR"), no raw stage
  ids, no bare confidence percentages. Confidence is expressed as evidence counts
  ("We read #8 on them in 14 different moments").
- Placeholder/synthetic media is forbidden anywhere a user makes a decision (carried
  from 003): evidence crops, previews, and thumbnails MUST be real project media served
  from `/projects/{id}/evidence-media/…`.
- Failure messages MUST state: what happened, that the user's data is safe (when true),
  and exactly one recommended action.
- On app load, the frontend MUST restore the active `project_id` from localStorage,
  fetch `GET /projects/{id}`, route to the correct step, and resume polling if any job
  is queued/running. Copy near progress: *"It's safe to close this window — analysis
  keeps running as long as the app is running."*
- Polling: `GET /projects/{id}/jobs` every 2 s while any job is queued/running; stop
  when idle.

## Component map (old → new)

| Component (under `frontend/src/`) | Fate |
|---|---|
| `features/projects/ProjectWizardPage.tsx` | Keep; step derivation now includes project.status + analysis state; restores project from localStorage |
| `components/GuidedWorkflowShell.tsx` | Keep; labels change only |
| `features/projects/VideoSourceStep.tsx` | Keep; add auto-start messaging (below) |
| `features/projects/TargetPlayerStep.tsx` | **Delete** (jersey number becomes a small optional field in Step 2) |
| `features/projects/MatchWindowStep.tsx`, `SourceStep.tsx` | **Delete** (dead legacy) |
| `features/projects/PlayerConfirmationStep.tsx` | **Replace with** `FindPlayerStep.tsx` |
| `features/projects/CandidateEvidencePanel.tsx` | **Evolve into** `IdentityEvidenceStrip.tsx` (media rendering carries over) |
| — | **New** `features/projects/FrameClickSelector.tsx` |
| — | **New** `features/projects/AnalysisProgressCard.tsx` |
| — | **New** `features/projects/CoverageTimeline.tsx` |
| `features/projects/ReelGenerationStep.tsx` | Keep; embed CoverageTimeline above existing controls |
| `features/exports/ExportsPage.tsx` | Keep unchanged |
| `features/review/*` (ReviewPage, DetectionReviewQueue, ReviewDecisionBar, AnalysisStatusPanel) | **Delete** (001-era review queue) |
| `features/projects/guidedTypes.ts` | Extend: `AnalysisStage`, `PipelineJob`, `PlayerClick`, `IdentityCandidate`, `CoverageSegment` |
| `features/projects/projectStore.ts` | Extend: persist `projectId` to localStorage |
| `services/projects.ts` | Extend: `getJobs`, `postClick`, `getClicks`, `getCandidates`, `confirmTarget`, `adjustTarget`, `getTimeline`, `patchSegment`, `putJerseyHint` |
| `services/sources.ts` | Keep; point at `POST /projects/{id}/source` |

## Step 1 — Add video

Behavior is today's `VideoSourceStep` (file picker + drag-drop + metadata display) with
two changes:

1. On successful attach, analysis auto-starts (the backend queues the chain; no user
   action). The continue area MUST show:
   > "We'll watch the whole match — this can take a while (it's fine to leave it
   > overnight). You can start finding your player right away."
2. Validation failure copy (example): *"That file doesn't look like a playable video.
   Your file wasn't changed — try re-exporting it as MP4."*

Advancing to Step 2 MUST NOT wait for any analysis stage.

## Step 2 — Find your player (`FindPlayerStep.tsx`)

Layout, top to bottom:

### 2a. `AnalysisProgressCard`

- Renders the `analysis.stages` from `GET /projects/{id}` + polling, mapped to plain
  language:

  | stage | label |
  |---|---|
  | proxy | "Getting the video ready" |
  | detect_track | "Watching the match" — progress MUST read as match minutes: *"38 of 92 minutes"* |
  | embed_cluster | "Learning what each player looks like" |
  | jersey_ocr | "Reading jersey numbers" |
  | assemble_candidates | "Lining up who we found" |
  | (all succeeded) | "Ready — every moment is searchable" |

- While running, the card MUST include: *"You don't have to wait — click your player
  now and we'll match them as we go."*
- Collapsible once all stages succeed. Failed stage → error copy + single **Retry**
  button calling `POST /projects/{id}/pipeline/run` (resumes from checkpoint):
  > "Something went wrong while watching the match. Your video is fine — tap Retry to
  > pick up where we left off."

### 2b. `FrameClickSelector`

- **Frame display**: `<img src="/projects/{id}/frame?t={t}">`. No `<video>` element.
  Debounce frame fetches ~200 ms after scrub stops. If 409 (proxy not ready), show the
  copy from api.yaml in place of the frame.
- **Scrub bar**: styled `<input type="range">` over `[0, duration_s]`, mm:ss label.
  Keyboard: ←/→ ±5 s, Shift+←/→ ±30 s.
- **Hints above the bar** (thin tick marks, no filmstrip in v1):
  - Before confirmation, if a jersey hint is set and OCR hits exist: ticks at
    jersey-vote timestamps labeled "likely moments".
  - After confirmation: ticks/spans show the confirmed player's coverage instead.
  - Otherwise: no hints — it's just a scrubber.
- **Overlay boxes**: fetch `GET /frame-detections?t=` with each displayed frame; render
  absolutely-positioned divs from normalized boxes (scale by rendered img size). Faint
  outline on hover for all boxes (shows what's clickable); selected player gets a
  solid border: green = matched, amber = pinned/refining.
- **Click**: capture normalized (x, y) → `POST /projects/{id}/clicks` with
  `label: "positive"`. Handle each resolution:
  - `tracklet` → highlight box green; load evidence strip for `cluster_id`
    (message while loading: *"Locked on. Matching them across the rest of the match…"*
    if clustering is still running).
  - `pinned` → amber box at click point; show the pinned message from api.yaml; a pin
    badge appears and clears automatically when a later poll shows the click resolved.
  - `sam2_queued` → amber box; *"Taking a closer look at that moment…"*; poll jobs.
  - `no_player_here` → toast with the api.yaml message; nothing else changes.
- **Prompt copy** above the viewer:
  > "Scrub to any moment where you can see your player clearly, then click them."

### 2c. Jersey hint field (small, beside/below the viewer)

- Label: *"Jersey number (optional) — helps us double-check."*
- `PUT /projects/{id}/jersey-hint` on change. Never blocks or gates anything.
- If jersey_ocr finished with zero legible readings anywhere:
  *"We couldn't read jersey numbers in this footage — no problem, your click is what
  matters."* (neutral tone, not a warning)

### 2d. `IdentityEvidenceStrip` (appears after a click resolves to a cluster)

- Header: *"We think this is your player."* plus timestamp line, e.g.
  *"Here they are at 4:12, 23:40, 61:05…"*
- 8–12 crops from `GET /candidates?cluster_id=`, spread across the match, each with
  timestamp caption and a small **"Not them"** action →
  `POST /target/adjust {remove_tracklet_ids: […]}` → strip refreshes.
- The crop from the clicked tracklet appears first. Crops show the complete detected
  player body and enlarge on pointer hover or keyboard focus; activating one opens the
  same enlarged view for touch and keyboard users.
- 1–2 short preview clips when available (reuse existing evidence media rendering).
- Jersey cross-check line (when hint set and readings exist):
  agree → *"We read #8 on them in 14 different moments."*
  disagree (amber) → *"Heads up: we read #11 on this player. Double-check the crops."*
- Ambiguity banner (two clusters share the number / low separation, amber):
  *"There may be two players who look alike. Check the crops carefully — if any aren't
  your player, tap 'Not them'."* Most confusable crops shown first.
- Primary action: **"Yes, that's them"** → `POST /projects/{id}/target`.
- Secondary text: *"Not sure? Scrub somewhere else and click them again."* Additional
  positive clicks are always allowed and reinforce the identity.

### 2e. Post-confirmation coverage summary (inline, below the strip)

- *"Found them in 34 stretches — 12m 40s of the match."*
- Gap nudge when the largest gap > 10 min:
  *"We didn't see them clearly between 20:00 and 35:00. If they were on the field,
  scrub there and click them to fill the gap."*
- Low-coverage honesty (total < 3 min):
  *"We only found them clearly for 1m 10s. The reel will be short. You can scrub and
  click them in more moments to help us."*
- Button: **"Continue to build the reel"** → Step 3.

## Step 3 — Build the reel

### 3a. `CoverageTimeline` (top of step)

- One horizontal bar over `[0, duration_s]` rendered with plain divs.
- Segments from `GET /timeline`: green = included, gray = excluded, amber =
  low-score *"double-check this one"*.
- Click a segment → popover: thumbnail, `start–end` range, ▶ preview (serves
  `preview_clip_uri`), toggle **"Leave out of reel"** (`PATCH /timeline/{segment_id}`),
  and **"Not them"** (`POST /target/adjust {remove_tracklet_ids}` for the segment's
  tracklets; segment disappears).
- Summary line: *"34 stretches · 12m 40s total · 31 in the reel."*
- Mass-removal escape hatch: if the user removes > 40% of segments via "Not them":
  *"A lot of these weren't your player. Want to start the match-up over from a fresh
  click?"* → `DELETE /projects/{id}/target` → back to Step 2 with pipeline artifacts
  intact.
- **Non-goals for v1**: drag-to-adjust in/out points, zooming, multi-cluster coloring.

### 3b. Reel controls (existing `ReelGenerationStep`, kept)

- Profile selector (short highlight / medium best plays / full appearances) and target
  marker toggle → `POST /projects/{id}/exports`.
- Gating unchanged: controls disabled until `project.status == target_confirmed`, with
  the 409 copy from api.yaml if forced.
- Render progress reuses the jobs polling pattern (*"Cutting 34 clips… stitching…
  done"* — example staging).
- Outputs list + download unchanged (`ExportsPage`).

## Failure & edge copy table (normative)

| Situation | Copy / behavior |
|---|---|
| Click on empty area | *"We don't see a player there — try clicking directly on their body."* |
| Clicked ref/coach (user sees wrong crops) | Strip self-evidences; secondary text already covers: click again elsewhere. One corrective click replaces the working selection. |
| Analysis crash | *"Something went wrong while watching the match. Your video is fine — tap Retry to pick up where we left off."* Resume from checkpoint. |
| Low-quality footage (detection density below threshold after detect_track) | *"This footage is too blurry or far away for us to find players reliably. Best results come from 720p or better where players look at least thumb-sized. You can still try clicking, but expect gaps."* Non-blocking. |
| Proxy not ready when scrubbing | *"We're still getting the video ready — try again in a moment."* |
| No legible jersey numbers | Neutral copy in §2c. |
| Coverage very low | Honest copy in §2e; never a dead end. |

## Verification scenarios (frontend tests must cover)

1. Wizard renders three steps with the new labels; Step 3 disabled until confirmation.
2. FrameClickSelector: scrub debounces frame fetches; click posts normalized coords;
   each of the four click resolutions renders its specified feedback.
3. IdentityEvidenceStrip: renders only real media URIs (no placeholder assets); "Not
   them" triggers adjust + refresh; jersey agree/disagree lines render per fixture.
4. AnalysisProgressCard: maps stages to the exact plain-language labels; shows
   minutes-watched formatting; Retry calls pipeline/run.
5. CoverageTimeline: include/exclude toggling patches the segment and updates the
   summary line; "Not them" removes the segment.
6. App reload with a stored project id restores step and resumes polling (mock).
