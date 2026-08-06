# Data Model: Simplified Guided Video Workflow

## Guided Project

**Purpose**: Tracks the simplified three-step user workflow for one video source, one target player, and one or more reel outputs.

**Fields**:
- `project_id`: Stable identifier
- `workflow_step`: `choose_source | confirm_player | generate_reels | complete`
- `status`: `draft | source_validating | source_ready | match_inference_uncertain | awaiting_player_confirmation | player_confirmed | extracting | ready_for_export | exporting | completed | failed | canceled`
- `source_id`: Reference to the selected `VideoSource`
- `inferred_match_portion_id`: Reference to the current inferred match portion
- `target_player_request_id`: Reference to user-entered player intent
- `player_identity_profile_id`: Reference to confirmed identity cues
- `verification_threshold`: Required accuracy threshold, default 0.90
- `failure_reason`: Optional user-visible failure summary

**Relationships**:
- Owns one active `VideoSource`
- Owns zero or one `InferredMatchPortion`
- Owns zero or one active `TargetPlayerRequest`
- Owns zero or one confirmed `PlayerIdentityProfile`
- Owns many `CandidatePlayerEvidence` records
- Owns many `ReelRequest` and output records

**Validation Rules**:
- `workflow_step` cannot advance to `confirm_player` until a valid source exists.
- `workflow_step` cannot advance to `generate_reels` until a player identity profile is confirmed.
- Extraction and export requests are rejected unless the player has been confirmed from evidence.

## Video Source

**Purpose**: Represents a user-selectable match video source.

**Fields**:
- `source_id`: Stable identifier
- `source_type`: `discovered_local | relative_local_path | youtube`
- `display_name`: User-facing label shown in source controls
- `source_reference`: Relative path, discovered local reference, or YouTube URL
- `relative_path`: Local path relative to the `video/` folder when applicable
- `duration_seconds`: Parsed or estimated source duration
- `file_size_bytes`: Local file size when available
- `last_modified_at`: Local timestamp when available
- `validation_status`: `available | unavailable | unsupported | outside_video_folder | invalid_link`
- `validation_message`: Plain-language explanation when validation fails

**Validation Rules**:
- Accepted local paths must resolve inside the configured `video/` folder.
- Absolute paths and path traversal outside `video/` are invalid.
- Display names must be readable and disambiguated when duplicates exist.
- YouTube sources must be recognizable as supported video links before analysis setup continues.

## Source Catalog Item

**Purpose**: A dropdown option for a discovered local video.

**Fields**:
- `catalog_id`: Stable identifier for the discovered option
- `display_name`: Readable dropdown label
- `relative_path`: Path under the `video/` folder
- `duration_seconds`: Parsed or estimated duration
- `file_size_bytes`: File size when available
- `last_modified_at`: Timestamp when available
- `details`: Short helper text for distinguishing similar videos

**Validation Rules**:
- Catalog items must only represent files under the `video/` folder.
- Duplicate display names must include distinguishing details.

## Inferred Match Portion

**Purpose**: Describes the automatically inferred playable match span.

**Fields**:
- `inferred_match_portion_id`: Stable identifier
- `start_seconds`: Inferred start offset
- `end_seconds`: Inferred end offset
- `confidence`: `high | medium | low`
- `summary`: User-visible explanation of what was inferred
- `uncertainty_reasons`: List of reasons confidence is not high

**Validation Rules**:
- The user is not required to manually enter start or end seconds in the standard flow.
- Low-confidence inference must be visible to the user before player confirmation continues.
- `end_seconds` must be greater than or equal to `start_seconds`.

## Target Player Request

**Purpose**: Stores the user intent before player identity is confirmed.

**Fields**:
- `target_player_request_id`: Stable identifier
- `jersey_number`: User-entered jersey number
- `optional_team_hint`: Optional team or color note
- `request_status`: `pending_evidence | candidates_ready | needs_clearer_input | canceled`

**Validation Rules**:
- Jersey number is required before candidate evidence is requested.
- Optional hints can improve candidate ranking but cannot replace user confirmation.

## Candidate Player Evidence

**Purpose**: Presents uncropped visual proof for a possible target player.

**Fields**:
- `candidate_id`: Stable identifier
- `project_id`: Parent project
- `jersey_number`: Detected or requested jersey number
- `confidence`: Numeric or labeled confidence summary
- `frame_time_seconds`: Source frame offset
- `uncropped_image_uri`: Reviewable image reference
- `cue_summary`: Human-readable summary of visible cues
- `visible_cues`: Set containing any of `jersey_number`, `jersey_color`, `body_shape`, `cleats`, `team_context`
- `review_state`: `candidate | confirmed | rejected | insufficient`

**Validation Rules**:
- Evidence shown to the user must be uncropped or wide enough to include surrounding body context.
- At least three candidate evidence samples should be shown when the jersey number is visible and enough frames are available.
- Rejected candidates cannot unlock extraction.

## Player Identity Profile

**Purpose**: Records the confirmed identity cues used for final extraction.

**Fields**:
- `player_identity_profile_id`: Stable identifier
- `confirmed_candidate_ids`: Evidence records approved by the user
- `jersey_number`: Confirmed jersey number
- `jersey_color`: Inferred jersey or team color when visible
- `body_shape_summary`: Inferred body appearance description when visible
- `cleat_summary`: Inferred cleat color or type when visible
- `confidence_status`: `confirmed | review_needed`
- `confirmed_at`: Timestamp

**Validation Rules**:
- Confirmation requires explicit user approval of candidate evidence.
- The profile must include the jersey number and at least one additional visible cue when available.
- If supporting cues are not visible, the profile must state that the evidence is limited.

## Reel Request

**Purpose**: Captures the user's requested output after player confirmation.

**Fields**:
- `reel_request_id`: Stable identifier
- `output_profile`: `short_highlight | medium_best_plays`
- `target_marker`: Boolean marker overlay choice
- `request_status`: `pending | extracting | ready | failed`

**Validation Rules**:
- Reel requests are accepted only after the player identity profile is confirmed.
- Marker overlay is optional and must not change the confirmed player identity.

## State Transitions

### Guided Project

```text
draft
  -> source_validating
  -> source_ready
  -> awaiting_player_confirmation
  -> player_confirmed
  -> extracting
  -> ready_for_export
  -> exporting
  -> completed

source_ready -> match_inference_uncertain -> awaiting_player_confirmation
awaiting_player_confirmation -> source_ready
awaiting_player_confirmation -> failed
Any active state -> canceled
Any active state -> failed
```

### Candidate Player Evidence

```text
candidate -> confirmed
candidate -> rejected
candidate -> insufficient
insufficient -> rejected
```

### Reel Request

```text
pending -> extracting -> ready
pending -> failed
extracting -> failed
```
