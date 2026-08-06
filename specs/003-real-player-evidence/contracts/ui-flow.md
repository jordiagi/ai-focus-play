# UI Contract: Real Player Evidence

## Scope

This contract replaces the Step 2 evidence panel behavior. Step 1 source selection and Step 3 reel controls remain in the guided workflow, but Step 3 stays locked until Step 2 confirms a real evidence-backed candidate identity.

## Step 2: Evidence Request

**Primary controls**:
- Jersey number input.
- Optional team/color hint input.
- Primary action: `Show player evidence`.

**Required behavior**:
- The action is disabled or blocked until a jersey number is present.
- When clicked, the UI shows that the selected video is being processed.
- The UI must not immediately show default candidate cards before the backend returns real evidence.

## Step 2: Processing State

**Required display**:
- Plain-language message that evidence is being extracted from the selected video.
- Progress stage from the project or candidate response when available.
- No confirm/reject buttons until at least one real candidate identity is available.

## Step 2: Candidate Identity List

**Required display for each candidate**:
- Actual thumbnail or playable clip rendered from `thumbnail_uri` or `media_uri`.
- Source timestamp in seconds or readable time format.
- Evidence count.
- Requested jersey number.
- Inferred team color when available.
- Cue summary and visible cue labels.
- Review warning when number/color confidence is weak or unknown.

**Required behavior**:
- Candidate selection chooses a candidate identity, not an isolated frame.
- A candidate with multiple samples should let the user inspect all samples.
- Placeholder gradients, static fake labels, or synthetic cards are not allowed.

**Example media card**:

- Preview: `<video src="/projects/p1/evidence-media/evidence-1-a1b2c3d4e5.mp4" poster="/projects/p1/evidence-media/evidence-1-a1b2c3d4e5.jpg" controls>`
- Timestamp label: `Source video at 1064.2s`
- Warning label: `Jersey number and color were not automatically verified; confirm visually from the real video evidence.`

## Step 2: No-Result and Failure States

**No-result behavior**:
- Show that no real evidence was found for the selected video and jersey number.
- Keep reel generation locked.
- Offer actions to change the jersey number, add or change team/color hint, or rerun evidence search.

**Failure behavior**:
- Show a plain-language reason when extraction fails.
- Keep reel generation locked.
- Offer retry when the source remains valid.

## Step 2: Decisions

**Confirm**:
- Enabled only when a candidate identity is selected.
- On success, advances the workflow to Step 3.
- Shows that the identity is locked for reel generation.

**Reject**:
- Marks the selected candidate as rejected.
- Keeps Step 3 locked.
- Moves the user to another available candidate when possible.

**Evidence insufficient**:
- Marks the selected candidate as insufficient.
- Keeps Step 3 locked.
- Encourages rerun, changed input, or manual review.

## Step 3 Gate

Step 3 may show output choices only after `player_identity_profile` exists and references a confirmed candidate. If the user navigates directly to Step 3 before confirmation, the UI must redirect or explain that real player evidence confirmation is required.

## Verification Scenarios

- Enter jersey number 8 for a selected local video and verify displayed evidence uses real media URIs from the backend.
- Confirm that no candidate card is shown when the backend returns `no_candidates`.
- Confirm that placeholder media does not appear in the DOM for candidate evidence.
- Reject one candidate and confirm another without unlocking Step 3 prematurely.
- Confirm a candidate and verify Step 3 unlocks with the confirmed identity summary visible.
