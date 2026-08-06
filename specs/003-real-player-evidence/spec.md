# Feature Specification: Real Player Evidence

**Feature Branch**: `003-real-player-evidence`  
**Created**: 2026-05-11  
**Status**: Draft  
**Input**: User description: "Step 2: after I enter jersey number 8 and click show player evidence, I expect the software to process the actual video and find real video examples showing evidence of the player ID. It should show a series of player IDs that match jersey color and number. From the selected player, it should generate the reel outputs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Show Real Video Evidence (Priority: P1)

As a user confirming the target player, I want the evidence results to come from the actual selected video so I can trust that the player candidates are real and relevant to my match.

**Why this priority**: The player confirmation step is only useful if it inspects the real source footage. Synthetic or placeholder items can cause the user to approve the wrong player and make every generated reel unreliable.

**Independent Test**: Select a local match video, enter jersey number 8, request player evidence, and verify that every displayed evidence item is a real frame sequence or clip from that selected video with a source timestamp.

**Acceptance Scenarios**:

1. **Given** a valid source video has been selected, **When** the user enters jersey number 8 and asks to show player evidence, **Then** the application analyzes the selected video before presenting selectable player evidence.
2. **Given** evidence results are shown, **When** the user reviews each item, **Then** every item includes real visual media from the selected video rather than synthetic, placeholder, or static mock content.
3. **Given** a candidate match is found, **When** the evidence is displayed, **Then** the preview shows enough uncropped context for the user to judge jersey number, jersey color, body shape, and cleat cues when visible.

---

### User Story 2 - Compare Candidate Player Identities (Priority: P2)

As a user, I want to compare multiple candidate player identities that match the requested jersey number and team color so I can choose the intended player even when several players or teams have similar numbers.

**Why this priority**: Soccer videos often include duplicated jersey numbers across teams, partially obscured numbers, warmups, substitutes, and camera movement. The software must support human confirmation rather than treating the first detected number as correct.

**Independent Test**: Use a video where the requested number appears multiple times or on both teams, request evidence, and confirm that candidates are grouped or labeled so the user can choose one identity and reject others.

**Acceptance Scenarios**:

1. **Given** multiple players may match the requested number, **When** evidence is generated, **Then** the application presents a series of candidate identities with their supporting evidence and visible cues.
2. **Given** a candidate identity is shown, **When** the user inspects it, **Then** the application indicates whether the candidate matched the requested jersey number, inferred team color, and other visible identity cues.
3. **Given** a candidate is not the intended player, **When** the user rejects it, **Then** the application keeps reel generation blocked and allows the user to review another candidate or rerun evidence search.

---

### User Story 3 - Generate Reels From the Selected Identity (Priority: P3)

As a user, I want the reel outputs to be generated from the player identity I selected from real evidence, not only from the jersey number, so the final video focuses on the correct player.

**Why this priority**: Jersey number alone is not enough to maintain identity across a full match. The selected candidate must become the basis for the final reel extraction.

**Independent Test**: Confirm one candidate identity from real evidence, generate a reel, and verify that extraction starts only after confirmation and uses the confirmed identity as the target.

**Acceptance Scenarios**:

1. **Given** no player candidate has been confirmed, **When** the user attempts to generate reel outputs, **Then** the application blocks generation and asks the user to confirm a real evidence-backed player identity first.
2. **Given** the user confirms a candidate identity, **When** the user starts reel generation, **Then** the application uses the selected identity and its recorded cues as the target for output creation.
3. **Given** reel generation completes, **When** the user reviews the output options, **Then** the short, medium, and marked-player outputs are tied to the confirmed player identity.

### Edge Cases

- The selected video is long, starts with warmups, or includes post-game footage before or after the match.
- The requested jersey number is not visible often enough to provide reliable evidence.
- The same jersey number appears on both teams or in warmup footage with different jersey colors.
- Jersey numbers are blurred, occluded, folded, small in frame, or visible only for a few frames.
- Team colors are similar, lighting changes, or compression artifacts make color inference unreliable.
- Cleats, body shape, or other supporting cues are not visible in enough evidence samples.
- The user enters a jersey number that does not appear in the selected video.
- The evidence search takes enough time that the user needs progress feedback and a safe retry path.
- The user confirms the wrong candidate and needs to restart player confirmation before generating outputs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST process the actual selected source video when the user requests player evidence.
- **FR-002**: The application MUST NOT present synthetic, placeholder, or static mock items as selectable player evidence.
- **FR-003**: Each selectable evidence item MUST include a real visual sample from the selected video and the source timestamp where it was found.
- **FR-004**: Evidence samples MUST be uncropped or wide enough for a human to inspect jersey number, jersey/team color, body shape, and cleat cues when visible.
- **FR-005**: The evidence search MUST use the user-entered jersey number as a primary filter or ranking signal.
- **FR-006**: The evidence search MUST use jersey/team color as a matching or grouping signal when color can be inferred from the video.
- **FR-007**: The application MUST present candidate player identities, not only isolated frames, when multiple matching appearances appear to belong to the same player.
- **FR-008**: Candidate identities MUST show their supporting evidence count, visible identity cues, and confidence or review status in plain language.
- **FR-009**: The user MUST be able to select one candidate identity as the target player before reel generation starts.
- **FR-010**: The user MUST be able to reject an incorrect candidate identity and continue reviewing other candidates or rerun evidence search.
- **FR-011**: If no real evidence can be found, the application MUST state that clearly and MUST NOT allow the user to confirm a fake or unverified candidate.
- **FR-012**: Reel generation MUST remain blocked until the user confirms a candidate identity backed by real video evidence.
- **FR-013**: Reel generation MUST use the selected candidate identity and its recorded cues, not jersey number alone, as the target-player definition.
- **FR-014**: The application MUST preserve the connection between evidence samples, the confirmed player identity, and generated reel outputs for review.
- **FR-015**: The evidence workflow MUST provide user-visible progress, completion, no-result, and failure states.
- **FR-016**: The evidence workflow MUST allow the user to rerun the search after changing the jersey number or selected source.

### Operational & Observability Requirements

- **OR-001**: The application MUST record whether each displayed candidate was produced from real video evidence and include enough metadata to diagnose missing or low-quality evidence.
- **OR-002**: Verification MUST include an automated or scripted check that evidence responses do not return placeholder media for selectable candidates.
- **OR-003**: Verification MUST include manual review on at least one real local soccer video to confirm that evidence thumbnails or clips match the selected source video and timestamp.
- **OR-004**: Verification MUST include a manual end-to-end review where a selected candidate identity is used to generate reel outputs.

### Key Entities

- **Evidence Search Request**: The user's request to find player evidence from a selected source video, including source reference, jersey number, and search status.
- **Evidence Sample**: A real visual sample from the selected video, including timestamp, preview media, visible cues, and whether the jersey number or color is readable.
- **Candidate Player Identity**: A proposed target player assembled from one or more evidence samples that appear to show the same player.
- **Confirmed Player Identity**: The candidate selected by the user as the intended player, including approved evidence samples and recorded identity cues.
- **Reel Output Request**: A request to generate short, medium, or marked-player outputs using the confirmed player identity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of selectable evidence items shown in Step 2 originate from the selected source video and include a source timestamp.
- **SC-002**: 0 selectable evidence items use placeholder, synthetic, or static mock player media.
- **SC-003**: For videos where at least three matching appearances are visible, the user sees at least three real evidence samples before confirming a player.
- **SC-004**: For videos with multiple plausible matches, the user can compare candidate identities and select or reject each one without starting reel generation.
- **SC-005**: In 100% of standard workflows, reel generation cannot start until a real evidence-backed candidate identity has been confirmed.
- **SC-006**: In manual review of real match footage, at least 90% of accepted reel moments focus on the confirmed player identity.
- **SC-007**: A reviewer can trace every generated reel back to the confirmed player identity and at least one supporting real evidence sample.

## Assumptions

- The selected video is already available through the source-selection workflow before Step 2 begins.
- Jersey number is the primary user-provided clue; jersey/team color and visual appearance are supporting cues inferred from real video evidence.
- When the same jersey number appears on both teams, jersey/team color is required to distinguish candidate identities whenever it is visible.
- Human confirmation remains required before reel generation because real soccer footage can be ambiguous.
- If evidence quality is insufficient, the correct behavior is to report the limitation and block confirmation rather than fabricate a candidate.
