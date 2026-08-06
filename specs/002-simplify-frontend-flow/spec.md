# Feature Specification: Simplified Guided Video Workflow

**Feature Branch**: `002-simplify-frontend-flow`  
**Created**: 2026-05-11  
**Status**: Draft  
**Input**: User description: "Rewrite the frontend so it is professional looking and simple to use. Start with video selection from a YouTube link or a relative local path under the video folder, offer a dropdown for discovered videos, remove manual start/end video window entry, combine player setup with jersey-number confirmation, show uncropped jersey-number evidence, and infer jersey color, body shape, and cleat details after the user confirms the player."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose a Video Source First (Priority: P1)

As a scout or parent preparing a reel, I want the first screen to ask only for the match video source so I can start without understanding technical project setup.

**Why this priority**: The current workflow is blocked by confusing setup steps. A clear source-selection start is required before any player review or reel generation can succeed.

**Independent Test**: A user can open the application, choose a video from the discovered video list or provide a supported source, and continue without entering match start or end times.

**Acceptance Scenarios**:

1. **Given** videos exist in the local video folder, **When** the user opens the first step, **Then** the user sees a dropdown of available videos with readable display names and enough detail to distinguish similar videos.
2. **Given** the user has a YouTube match link, **When** the user enters the link and continues, **Then** the source is accepted for analysis setup without requiring a local path.
3. **Given** the user enters a local path, **When** the path is relative and points under the video folder, **Then** the source is accepted.
4. **Given** the user enters an absolute path or a path outside the video folder, **When** the user attempts to continue, **Then** the application rejects the source with a plain-language explanation.

---

### User Story 2 - Confirm the Target Player From Evidence (Priority: P2)

As a user creating a player-focused reel, I want to provide the player's jersey number and confirm the correct player from uncropped visual evidence before the application extracts plays.

**Why this priority**: Player identity accuracy is the core value of the product. The user must verify the software has found the intended player before any highlight reel is generated.

**Independent Test**: After choosing a video source, a user can enter the target jersey number, review uncropped candidate evidence that shows the player in context, and either confirm the player or reject the candidate.

**Acceptance Scenarios**:

1. **Given** a source video has been selected, **When** the user enters the target player's jersey number and continues, **Then** the application presents candidate player evidence before extraction begins.
2. **Given** a candidate player is detected, **When** the evidence is shown, **Then** the user sees uncropped frame evidence that includes the jersey number area and surrounding body context.
3. **Given** the candidate is the intended player, **When** the user confirms the player, **Then** the player identity is locked for extraction and the application records visible identity cues from the approved evidence.
4. **Given** the candidate is not the intended player, **When** the user rejects the candidate, **Then** the application offers another candidate or asks for clearer input without starting extraction.

---

### User Story 3 - Generate Reels Only After Player Confirmation (Priority: P3)

As a user, I want the application to run the final extraction only after I confirm the player, then offer simple export choices for short, medium, and marked-player outputs.

**Why this priority**: Export quality depends on the confirmed player identity. Clear output choices matter, but they should come after source and player confirmation are complete.

**Independent Test**: A user cannot start reel extraction until a player is confirmed, and once confirmed can choose output length and whether to visually mark the player.

**Acceptance Scenarios**:

1. **Given** the user has not confirmed a target player, **When** the user attempts to generate a reel, **Then** the application prevents extraction and directs the user back to player confirmation.
2. **Given** the user has confirmed the target player, **When** the user proceeds to output selection, **Then** the application offers clear choices for a short highlight, a medium best-plays reel, and an option to mark the identified player.
3. **Given** extraction is running, **When** the user watches progress, **Then** the application explains the current stage in plain language and keeps the next expected action clear.

### Edge Cases

- The local video folder is empty or unavailable.
- Two or more discovered videos have similar names or duplicate display names.
- A YouTube link is private, unavailable, age restricted, or not a valid video source.
- The selected video includes warmups, halftime footage, post-game clips, or non-match footage.
- The match period cannot be inferred with high confidence.
- The target jersey number is missing, obscured, duplicated, or worn by multiple players across teams.
- Team colors are visually similar, change during warmups, or are distorted by lighting.
- Cleats or body shape are not visible enough to support identity confirmation.
- The user confirms the wrong player and needs to restart player confirmation before extraction.
- Long videos take enough time that users need progress feedback and safe cancellation or retry options.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST present the workflow as no more than three primary steps: choose source, confirm player, and generate reels.
- **FR-002**: The first step MUST focus on video source selection and MUST NOT ask the user to identify the player or choose export settings before a valid source is selected.
- **FR-003**: Users MUST be able to choose a discovered local video from a dropdown populated from the video folder where the application is run.
- **FR-004**: Users MUST be able to provide a YouTube link as an alternative video source.
- **FR-005**: Users MUST be able to provide a relative local path only when it stays under the video folder.
- **FR-006**: The application MUST reject absolute local paths and paths outside the video folder with a clear explanation.
- **FR-007**: Each discovered source MUST have a display name, defined as the readable label shown to the user in source-selection controls.
- **FR-008**: Display names MUST be understandable without reading a full file path and MUST include additional context when needed to distinguish duplicate or similar sources.
- **FR-009**: The user MUST NOT be required to manually enter match start or end times to continue through the guided workflow.
- **FR-010**: The application MUST infer the relevant match portion automatically and communicate when the inferred match portion is uncertain.
- **FR-011**: The player confirmation step MUST collect or confirm the target jersey number before showing candidate evidence.
- **FR-012**: The application MUST show uncropped candidate-player evidence before allowing final extraction.
- **FR-013**: Candidate evidence MUST include enough surrounding visual context for a human to judge jersey number, team color, body shape, and cleat appearance when visible.
- **FR-014**: The user MUST be able to confirm the candidate, reject the candidate, request another candidate when available, or restart player setup.
- **FR-015**: The application MUST NOT start player-focused extraction until the user confirms the target player from visual evidence.
- **FR-016**: After confirmation, the application MUST record the identity cues visible in the approved evidence, including jersey number, jersey/team color, body appearance, and cleat color or type when visible.
- **FR-017**: When the evidence is insufficient to support a confident identity decision, the application MUST say so and ask the user for review instead of presenting the candidate as verified.
- **FR-018**: The reel generation step MUST offer clear choices for short highlight, medium best-plays output, and whether to visually mark the identified player.
- **FR-019**: The application MUST use plain-language labels, clear primary actions, and a professional visual hierarchy so users can tell what to do next on each step.
- **FR-020**: The application MUST preserve the user's ability to recover from mistakes by changing the source or redoing player confirmation before extraction.

### Operational & Observability Requirements

- **OR-001**: The application MUST expose user-visible states for source validation, match inference, candidate evidence generation, player confirmation, extraction, and export readiness.
- **OR-002**: The project documentation MUST explain how local video discovery works, what display names mean, and which local paths are accepted.
- **OR-003**: Verification MUST include a usability walkthrough with at least one local video, one unavailable or invalid source, one confirmed player, one rejected candidate, and one generated reel.
- **OR-004**: Verification MUST include manual visual review for player identity because the final correctness of a target-player match depends on human confirmation.

### Key Entities

- **Video Source**: A user-selectable source for the match video, including source type, readable display name, source reference, basic distinguishing details, and validation status.
- **Display Name**: The user-facing label for a video source, derived from the source title or filename and expanded when needed to avoid ambiguity.
- **Inferred Match Portion**: The automatically identified span of the source that appears to contain the playable match, including confidence and user-visible uncertainty status.
- **Target Player Request**: The user's intended player information, including jersey number and any optional notes such as team color.
- **Candidate Player Evidence**: Uncropped visual samples and summary cues that help the user decide whether a detected player is the intended player.
- **Player Identity Profile**: The confirmed identity cues recorded from approved evidence, including jersey number, team color, body appearance, cleat appearance when visible, and confirmation decision.
- **Reel Request**: The user's selected output type after player confirmation, including desired reel length and whether the player should be visually marked.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of first-time users can select a valid video source and reach player confirmation in under 2 minutes without assistance.
- **SC-002**: 100% of accepted manually entered local paths are relative paths under the video folder.
- **SC-003**: Users are required to enter 0 manual match start or end times during the standard guided workflow.
- **SC-004**: For videos where the target jersey number is visible, users see at least 3 uncropped candidate evidence samples before confirming the player.
- **SC-005**: In 100% of standard workflow attempts, player-focused extraction cannot start until the target player has been confirmed.
- **SC-006**: At least 90% of approved player confirmations record jersey/team color and at least one additional visual cue, such as body appearance or cleat appearance, when visible.
- **SC-007**: At least 90% of usability review participants rate the workflow as clear and professional and can identify the next action at every step.
- **SC-008**: Users can reject an incorrect player candidate and return to candidate review or player setup in one action.

## Assumptions

- The feature remains scoped to soccer match videos and one target player per reel project.
- The local video folder is the trusted folder for selectable local sources.
- A display name for a local video is derived from the filename by default; a display name for a YouTube source is derived from the video title when available.
- If display names are duplicated, the application adds distinguishing context such as duration, date-like filename details, or relative location.
- If match portion inference is uncertain, the default fallback is to explain the uncertainty and continue with review-safe behavior rather than asking users to manually enter start and end times.
- Jersey number is the primary user-entered identity clue; team color, body appearance, and cleat appearance are supporting cues derived from confirmed evidence when visible.
- Human confirmation remains required before final extraction because visual identity can be ambiguous in real soccer footage.
