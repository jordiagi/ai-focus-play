# Manual Validation Checklist: Click-First Player Reels

Run on real footage (`video/video.mp4`) with the `ml` extra installed and models
downloaded. Record date, video, and result notes inline for every item. This checklist
satisfies OR-004 and the [MANUAL CHECKPOINT] tasks T038, T056, T068, T075.

**Executed by**: ____________  **Date**: ____________  **Video**: ____________

## A. Setup & ingest

- [ ] `python -m src.ml.doctor` reports MPS device, all four models present, ffmpeg OK
- [ ] Upload the video in Step 1; metadata (duration/resolution/fps) displays correctly
- [ ] Analysis starts automatically; the overnight-expectation copy is shown
- [ ] Uploading a non-video file shows the plain-language validation error

## B. Analysis progress & resilience (T038 / US2)

- [ ] Progress card shows plain-language stages; "Watching the match" reports minutes
      watched (e.g. "38 of 92 minutes") that advance in real time
- [x] Kill the backend process mid detect_track; restart it; the job resumes from its
      checkpoint (progress does not restart near zero) — human approved T038 on 2026-07-16
- [ ] Reload the browser mid-analysis: the project, step, and progress polling restore
      automatically
- [x] At 5 spot-check timestamps with players clearly visible, the scrubber overlay
      shows boxes on ≥90% of visibly on-screen players — human approved T038 on 2026-07-16
- [ ] Cancel a queued/running job from the API; status becomes `cancelled`

## C. Click & confirm (T056 / US1)

**Human gate approved 2026-07-17.** Validation exposed two correction cases retained
for follow-up: readable `#38` contamination at 31:19 (reprocessed and separated), and
an OCR-ineligible one-frame blue-kit false positive at 28:44.5 (visible through the
evidence/"Not them" correction path). The user instructed implementation to proceed.

- [ ] While analysis is still running, click the target player in an unanalyzed stretch:
      pinned feedback appears; the pin resolves automatically later without re-clicking
- [ ] After analysis, click the target player: box highlight in < 2 s, evidence strip
      appears with 8–12 real crops spread across the match, each with a timestamp
- [ ] The crops genuinely show the same player (human judgment) — note errors: ______
- [ ] Enter the player's jersey number as hint: agreement line appears ("We read #N on
      them in M moments") — or the neutral no-readable-numbers copy if applicable
- [ ] Enter a WRONG jersey number: amber mismatch warning appears
- [ ] Click empty grass: "We don't see a player there" toast; nothing else changes
- [ ] Click the referee: evidence strip makes the mistake obvious; clicking the real
      player elsewhere replaces the selection
- [ ] Mark one wrong crop "Not them": strip refreshes without that appearance
- [ ] Confirm "Yes, that's them": coverage summary appears with stretch count and total
      time; Step 3 unlocks

## D. Refinement & corrections (US1/US3)

- [ ] Find a coverage gap where the player was on the field; scrub in and click them:
      refinement runs (bounded, minutes not hours) and coverage extends
- [ ] Click a player the detector missed entirely (small/partially occluded):
      "Taking a closer look…" → appearance added, or honest no-player result
- [ ] In the coverage timeline, "Not them" on a segment removes it and updates the summary

## E. Timeline & reel (T068 / US3)

- [ ] Coverage timeline shows segments over the match duration; clicking one gives a
      thumbnail + playable preview clip of the right moment
- [ ] Exclude a segment; the summary line updates ("… N in the reel")
- [ ] Attempting export before confirmation (fresh project) is blocked with the
      normative copy
- [ ] Generate with target marker ON: render job shows progress; the finished MP4
      contains only included segments in order; the marker follows the player, not a
      fixed center box — % of reel moments showing the confirmed player (target ≥90%): ______
- [ ] Download works from the exports list; the output is traceable to the confirmed
      identity (segments recorded on the output)

## F. Overnight scenario (T075)

- [ ] Start analysis on a full-length match in the evening; let the machine sleep
      naturally; verify next morning the chain completed or resumed to completion
      without user action — total wall time: ______

## G. Honesty checks

- [ ] No placeholder/synthetic media anywhere in evidence, timeline, or previews
- [ ] No model names, raw stage ids, or bare confidence percentages in any UI copy
- [ ] Every failure encountered during this run stated: what happened, data safety, one
      next action — list any violations: ______

**Overall result**: PASS / FAIL — defects filed as tasks: ____________
