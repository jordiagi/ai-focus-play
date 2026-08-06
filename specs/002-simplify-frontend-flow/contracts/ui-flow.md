# UI Contract: Simplified Guided Video Workflow

## Primary Navigation

The application presents one guided page with three primary steps:

1. Choose video
2. Confirm player
3. Generate reels

The user should always see the current step, completed steps, the next required action, and any blocking issue in plain language.

## Step 1: Choose Video

**Primary goal**: Select a valid video source before any player or export controls appear.

**Required controls**:
- Dropdown of discovered videos from the local `video/` folder.
- YouTube link entry.
- Relative local path entry with helper text explaining that paths must stay under `video/`.
- Primary action: continue with selected source.

**Required states**:
- Empty video folder: show that no local videos were found and keep YouTube/relative path entry available.
- Invalid YouTube link: show a plain-language validation message.
- Absolute or outside-folder path: block continue and explain the accepted path rule.
- Source accepted: advance to player confirmation and show inferred match status.

**Display name behavior**:
- The dropdown label is the display name.
- Display names should be short and readable.
- Details such as duration, file size, modified date, or relative location may appear as secondary text.

## Step 2: Confirm Player

**Primary goal**: Let the user verify the target player before extraction starts.

**Required controls**:
- Jersey number input.
- Optional team/color hint input.
- Candidate evidence panel with uncropped frame evidence.
- Actions for confirm, reject, request another candidate, and restart player setup.

**Required states**:
- No jersey number: block candidate search and ask for jersey number.
- Evidence loading: explain that candidate frames are being found.
- Candidate found: show uncropped evidence, cue summary, and confidence state.
- Insufficient evidence: explain why confirmation is unsafe and offer retry/restart.
- Candidate rejected: keep extraction locked and show next available candidate when possible.
- Candidate confirmed: lock identity cues and advance to reel generation.

## Step 3: Generate Reels

**Primary goal**: Generate only after player confirmation.

**Required controls**:
- Short highlight option.
- Medium best-plays option.
- Target marker toggle.
- Primary action: generate selected reel.

**Required states**:
- Player not confirmed: block generation and link back to confirmation.
- Extraction running: show user-visible progress stage and expected next step.
- Export ready: show downloadable output status and selected output profile.
- Export failed: show retry guidance and a user-visible reason.

## Visual Direction

- Use a professional, editorial visual hierarchy with strong section titles, clear helper text, and a single primary action per step.
- Avoid showing technical fields unless they directly answer a user question.
- Avoid the old manual match-window controls in the standard guided flow.
- Keep advanced or diagnostic details visually secondary to the current user decision.

## Verification Scenarios

- A user selects a local dropdown video and reaches player confirmation without entering times.
- A user enters a relative path under `video/` and reaches player confirmation.
- A user enters an invalid outside-folder path and sees a blocking explanation.
- A user enters a jersey number, reviews uncropped evidence, rejects one candidate, and confirms another.
- A user attempts to generate a reel before player confirmation and is blocked.
- A user confirms a player and generates short, medium, and marked-player outputs.
