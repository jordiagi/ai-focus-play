# Feature Specification: Click-First Player Reels (Full Product Re-Spec)

**Feature Branch**: `005-click-first-player-reels`
**Created**: 2026-07-13
**Status**: Ready for implementation
**Supersedes**: specs 001–004. Those folders remain as historical record only. Where this
spec conflicts with any earlier spec, this spec wins. In particular it supersedes 004's
"user enters jersey number → candidates presented" identification flow and 004's
"not an automated jersey-number OCR system" non-goal (OCR is now in scope as a
supporting cue).

## Vision

AI Focus Play turns a broadcast soccer MP4 into a highlight reel focused on one player,
entirely on the user's own machine. The primary persona is a **parent or coach** who has
a recording of a match and wants every moment their kid (or one player) is on screen,
without CV knowledge, cloud accounts, or manual clip cutting.

The product promise, in the user's words:

> "I drop in the match video, click my kid once when I see them, and I get a reel of
> their moments. If it takes all night to process, fine — but it has to find the right
> kid and it has to be obvious how to use."

**Fixed constraints (user decisions):**

1. **Fully local.** Open-source models only. No hosted AI APIs; no frame ever leaves the
   machine.
2. **Click-first identification.** The user identifies their player by clicking them on a
   video frame. Jersey number entry is an optional supporting hint, never a required gate.
3. **Hardware target**: a single Apple Silicon Mac (developed/validated on an M4 Max,
   64 GB RAM) using PyTorch MPS with CPU fallback. Long processing times are acceptable —
   an overnight run for a full match is an explicitly supported mode.
4. **Accuracy and ease of use beat speed.** When a trade-off exists, spend more compute.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Click Your Player, Confirm With Evidence (Priority: P1)

As a parent, I want to scrub to any moment of the match, click my player once, and have
the app show me proof it knows who they are across the whole match, so I can confirm the
target without typing anything or understanding jersey numbers.

**Why this priority**: This is the product's core interaction and its main ease-of-use
differentiator. Every downstream feature (coverage, reels) depends on a correctly
identified player.

**Independent Test**: Upload a real match video, wait for analysis to complete, scrub to
a frame where the target player is visible, click them, and verify the app responds with
a bounding-box highlight plus an evidence strip of that same player's appearances from
across the match, which can be confirmed with one action.

**Acceptance Scenarios**:

1. **Given** analysis has completed for the uploaded video, **When** the user scrubs to
   any timestamp and clicks on a visible player, **Then** the app highlights that
   player's bounding box on the frame within 2 seconds and shows an evidence strip of
   8–12 real crops of the matched identity, deliberately spread across the match
   timeline (early / middle / late where available).
2. **Given** the evidence strip is displayed, **When** the user reviews it, **Then**
   every crop is real media from the selected video with a source timestamp, and the
   strip states in plain language when/how often the player was found (e.g. "Here they
   are at 4:12, 23:40, 61:05").
3. **Given** the user entered an optional jersey number hint and the analysis read
   numbers on the matched identity, **When** the evidence strip is shown, **Then** it
   states agreement ("We read #8 on them in 14 different moments") or shows a plain
   amber warning on mismatch ("Heads up: we read #11 on this player — double-check the
   crops").
4. **Given** the evidence strip shows the right player, **When** the user selects "Yes,
   that's them", **Then** the identity is confirmed and the wizard allows advancing to
   reel building.
5. **Given** a crop in the strip shows the wrong person, **When** the user marks it
   "Not them", **Then** that appearance is excluded, the exclusion is remembered as
   negative evidence, and the strip refreshes without the excluded appearances.
6. **Given** the user clicks a spot where no player is detected, **When** the click is
   processed, **Then** the app says so in plain language ("We don't see a player there —
   try clicking directly on their body") and nothing else changes.

---

### User Story 2 - Long Analysis That Respects the User (Priority: P2)

As a user, I want the heavy video analysis to run in the background with honest,
plain-language progress, survive app restarts and overnight runs, and let me click my
player even before it finishes, so a 2–3 hour processing job never feels broken or
wastes my time.

**Why this priority**: Full-match analysis on local hardware takes hours. Without
resumable jobs and staged readiness, every crash, sleep, or impatient user kills the
product experience.

**Independent Test**: Upload a full match, observe staged plain-language progress, kill
and restart the backend mid-analysis and verify it resumes from a checkpoint instead of
restarting, and click the player before analysis completes and verify the click is kept
as a pin that resolves automatically once analysis reaches that part of the match.

**Acceptance Scenarios**:

1. **Given** a video upload completes, **When** the user continues past Step 1, **Then**
   full-match analysis starts automatically in the background without any additional
   user action, and the UI states that processing may take a long time and that the user
   can start finding their player right away.
2. **Given** analysis is running, **When** the user views progress, **Then** stages are
   described in plain language (e.g. "Getting the video ready", "Watching the match — 38
   of 92 minutes", "Learning what each player looks like", "Reading jersey numbers")
   with real progress derived from actual work done — never fabricated percentages.
3. **Given** the backend process is killed or the machine sleeps mid-analysis, **When**
   the backend restarts, **Then** the analysis resumes from its last checkpoint without
   redoing completed stages, and the frontend reattaches to progress automatically when
   reopened.
4. **Given** analysis has not yet finished, **When** the user clicks a player on a
   frame, **Then** the click is accepted: if detections already exist near that
   timestamp the app matches it immediately; otherwise it is saved as a pin with
   feedback ("Got them — we'll match this player across the match as we finish
   watching") and resolves automatically without the user re-clicking.
5. **Given** an analysis stage fails, **When** the user views the project, **Then** the
   error is stated in plain language with the user's data confirmed safe and a single
   Retry action that resumes from the last checkpoint, not from zero.

---

### User Story 3 - Coverage Timeline, Corrections, and the Reel (Priority: P3)

As a user who has confirmed my player, I want to see where they appear across the match
on a simple timeline, fix mistakes (missed stretches, wrong-player segments), choose
what goes in, and render a downloadable reel focused on them.

**Why this priority**: This converts a confirmed identity into the actual deliverable —
the highlight reel — and provides the correction loop that makes imperfect CV output
acceptable.

**Independent Test**: After confirming a player, view the coverage timeline, preview a
segment, exclude one segment, mark one segment "Not them", add a missed appearance by
clicking the player in an uncovered stretch, then generate and download a reel and
verify it contains only the included segments with the target player.

**Acceptance Scenarios**:

1. **Given** an identity is confirmed, **When** the user reaches reel building, **Then**
   a coverage summary is shown ("Found them in 34 stretches — 12m 40s of the match")
   above a horizontal timeline of appearance segments.
2. **Given** the timeline is displayed, **When** the user clicks a segment, **Then** a
   preview (thumbnail + short clip) is available along with actions to leave the segment
   out of the reel or mark it "Not them".
3. **Given** the user marks a segment "Not them", **When** the correction is applied,
   **Then** the segment is removed from coverage, recorded as negative evidence, and the
   summary updates.
4. **Given** the coverage has a gap where the user knows the player was on the field,
   **When** the user scrubs into the gap and clicks the player, **Then** the new
   appearance is associated with the confirmed identity and coverage updates.
5. **Given** no identity has been confirmed, **When** the user attempts to generate a
   reel, **Then** generation is blocked with a plain-language explanation.
6. **Given** included segments exist, **When** the user picks an output profile and
   generates, **Then** a background render job produces an MP4 of the included segments
   in chronological order, with an optional target marker that follows the confirmed
   player's actual position frame-to-frame (not a fixed center box), downloadable from
   the exports list.

### Edge Cases

- The user clicks the referee, a coach, or a spectator: the evidence strip makes the
  mistake self-evident; one corrective click elsewhere replaces the selection.
- Two similar-looking players (same build, same number on both teams): the app surfaces
  ambiguity with an amber notice and shows the most confusable crops first for review.
- The player is rarely visible or the confirmed identity has very low coverage: the app
  states it honestly ("We only found them clearly for 1m 10s — the reel will be short")
  and invites more clicks; reel generation stays available (never a dead end).
- No jersey numbers are legible anywhere in the footage: the jersey hint field reports
  it neutrally ("We couldn't read jersey numbers in this footage — no problem, your
  click is what matters"); the click-first flow is unaffected.
- Footage too low-quality for reliable detection (players too small/blurry): an
  actionable notice explains the quality bar (720p+, players ≳50 px tall) while still
  allowing the user to try.
- The analysis job crashes or the machine restarts overnight: resume from checkpoint;
  never silently restart from zero; never lose the user's clicks or confirmation.
- The user confirms, then realizes many segments are wrong: after several "Not them"
  removals, offer a fresh start from a new click while keeping pipeline artifacts.
- Very long videos with warmups/halftime/post-game: coverage simply reflects where the
  player was actually found; no match-window configuration is required of the user.
- The user closes the browser or reopens the app days later: the project, its analysis
  state, and any confirmation are restored; polling reattaches automatically.

## Requirements *(mandatory)*

### Functional Requirements

**Identification & evidence**

- **FR-001**: The user MUST be able to identify the target player by clicking on them in
  a displayed video frame at any timestamp; a jersey number MUST never be required.
- **FR-002**: Click resolution MUST be computed against real detections from the actual
  selected video; hit-testing happens on the backend.
- **FR-003**: A resolved click MUST present an evidence strip of real crops of the
  matched identity from across the match (target 8–12, spread over time), each with a
  source timestamp; placeholder or synthetic media is forbidden (carried from 003).
- **FR-004**: The user MUST be able to confirm the matched identity with a single
  action, and to reject individual appearances ("Not them") as negative evidence that
  persists across re-clustering.
- **FR-005**: Additional positive clicks (before or after confirmation) MUST reinforce
  or extend the confirmed identity; clicks in unanalyzed regions MUST be stored as pins
  that resolve automatically when analysis reaches them.
- **FR-006**: An optional jersey number hint MUST be accepted at any time, used to rank
  candidates and cross-check the matched identity, and surfaced as plain-language
  agreement or mismatch — never as a blocker.

**Analysis pipeline**

- **FR-007**: Full-match analysis (detection, tracking, identity clustering, jersey
  reading) MUST start automatically once a source video is attached, and MUST run as
  background jobs that never block the API.
- **FR-008**: Analysis MUST use only local open-source models; no network calls to
  hosted inference APIs.
- **FR-009**: Every long-running stage MUST checkpoint its progress and be resumable
  after process death; resuming MUST NOT redo completed stages.
- **FR-010**: Progress MUST be real (derived from work completed, e.g. match minutes
  processed) and exposed via the API for the UI to poll; jobs MUST be cancellable.
- **FR-011**: The pipeline MUST group player appearances into identities (clusters of
  tracklets) such that a single confirmation covers the player's appearances across the
  whole match; appearances that overlap in time MUST never be merged into one identity.
- **FR-012**: When a click lands where no detection exists, or a coverage gap is
  reported, the system MUST support a bounded local refinement pass (mask propagation
  around the clicked moment) to recover the player — never a full-match re-run.

**Coverage & reels**

- **FR-013**: After confirmation, the system MUST derive appearance segments (merged,
  padded, scored) and present them as a coverage summary and timeline with per-segment
  preview and include/exclude control.
- **FR-014**: Reel generation MUST remain blocked until an evidence-backed identity is
  confirmed (carried from 003).
- **FR-015**: Reel rendering MUST produce an MP4 from the included segments in
  chronological order with selectable output profiles, and an optional target marker
  that tracks the player's real per-frame position.
- **FR-016**: Generated reels MUST remain traceable to the confirmed identity and its
  supporting evidence (carried from 003).

**Product & platform**

- **FR-017**: Metadata MUST be stored in a real embedded database (SQLite) capable of
  holding per-frame detections for a full match; the current whole-file JSON store MUST
  be replaced.
- **FR-018**: The wizard MUST have exactly three steps — "Add video", "Find your
  player", "Build the reel" — and all user-facing copy MUST be plain language: no model
  names, raw stage identifiers, or bare confidence numbers. Confidence is expressed as
  evidence ("read #8 in 14 moments").
- **FR-019**: Every failure message MUST state what happened in plain language, whether
  the user's data is safe, and exactly one recommended next action.
- **FR-020**: The legacy heuristic CV implementations (color-segmentation detection,
  IoU-only tracker, template-matching jersey OCR), the JSON datastore, the stub job
  runners, the remote-runner path, and the 001-era manual review queue MUST be deleted,
  not kept as fallbacks.

### Operational & Observability Requirements

- **OR-001**: A first-run setup command MUST download and verify all model weights, and
  a doctor command MUST report device (MPS/CPU), model presence, and FFmpeg
  availability.
- **OR-002**: Automated tests MUST run without ML model weights installed (fake model
  implementations behind stable interfaces); model-dependent smoke tests are a separate,
  locally run marker.
- **OR-003**: Structured log events MUST cover: job start/checkpoint/finish/failure per
  stage, click received/resolved/pinned, identity confirmed/adjusted, export
  start/finish.
- **OR-004**: Manual validation on at least one real match video (`video/video.mp4`)
  MUST be performed per the checklists before the feature is considered done.

### Key Entities

- **Source Video**: the uploaded/selected match file plus probed metadata and a 720p
  proxy used for all UI serving.
- **Pipeline Job**: one background stage run (proxy, detect/track, embed/cluster,
  jersey OCR, candidate assembly, refinement, export) with status, real progress, and a
  resume checkpoint.
- **Tracklet**: one continuous tracked appearance of one person (time span + per-frame
  boxes + sampled crops).
- **Identity Cluster**: a set of tracklets believed to be the same player (appearance
  embedding + kit color + jersey votes); the unit the user confirms.
- **User Click**: a positive or negative click at (timestamp, x, y), resolved to a
  tracklet/cluster immediately or held as a pin.
- **Appearance Segment**: a merged, padded time range where the confirmed player is on
  screen; the unit of the coverage timeline and reel assembly.
- **Reel Output**: a rendered MP4 tied to the confirmed identity, its profile, overlay
  mode, and the segments included.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 workflows require entering a jersey number to reach a confirmed
  identity.
- **SC-002**: On an analysis-complete frame, a click on a visibly detected player
  resolves to a highlighted selection in under 2 seconds.
- **SC-003**: 100% of evidence-strip items are real media from the selected video with
  source timestamps; 0 placeholder items (carried from 003).
- **SC-004**: Killing and restarting the backend during the detection stage loses at
  most the work since the last checkpoint (≤ ~1,000 frames) and requires no user
  reconfiguration to resume.
- **SC-005**: A full 90-minute 1080p match completes the automated analysis chain
  unattended on the target machine (expected 2–4 h; overnight acceptable).
- **SC-006**: In manual review of real footage, at least 90% of reel moments show the
  confirmed player (carried from 003), and spot checks at 5 timestamps show detection
  boxes on ≥90% of clearly visible players.
- **SC-007**: A "Not them" correction and a gap-filling click each take one user action
  and update coverage without restarting analysis.
- **SC-008**: A reviewer can trace any generated reel to the confirmed identity, its
  segments, and supporting evidence samples.

## Assumptions

- One project analyzes one source video with one confirmed target identity at a time.
- The input is broadcast-style or elevated sideline footage at 720p or better where
  players are typically ≳50 px tall; the app degrades honestly below that bar.
- FFmpeg/FFprobe are installed locally (existing prerequisite).
- The existing export/download flow (exports list, download endpoint) and the evidence
  media serving mechanics from 003 are sound and are extended, not redesigned.
- English-only UI copy for v1.
