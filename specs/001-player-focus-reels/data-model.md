# Data Model: Player Focus Reels

## Analysis Project

**Purpose**: Top-level container for one source video, one target player, one guided workflow, and one or more generated reel outputs.

**Fields**:
- `project_id`: Stable identifier
- `created_at`: Creation timestamp
- `updated_at`: Last modification timestamp
- `status`: `draft | ingesting | ready_for_player_confirmation | analyzing | review_required | ready_for_export | exporting | completed | failed | canceled`
- `source_id`: Reference to the active video source
- `target_player_profile_id`: Reference to the selected player profile
- `match_window_start`: Selected match start offset
- `match_window_end`: Selected match end offset
- `verification_threshold`: Required review threshold, default 0.90
- `processing_mode`: `local | remote`
- `failure_reason`: Optional user-visible failure summary

**Relationships**:
- Owns one `VideoSource`
- Owns one `TargetPlayerProfile`
- Owns many `PlayerDetections`
- Owns many `ReviewDecisions`
- Owns many `FocusReelOutputs`

## Video Source

**Purpose**: Represents the uploaded file or supported external link used as input.

**Fields**:
- `source_id`: Stable identifier
- `source_type`: `upload | external_link`
- `display_name`: User-facing source label
- `original_uri`: Input reference
- `duration_seconds`: Parsed source duration
- `access_status`: `pending | available | unavailable | unsupported`
- `ingest_status`: `pending | downloading | staging | ready | failed`
- `cleanup_status`: `pending | complete | failed`

**Validation Rules**:
- Must resolve to a readable video before analysis begins
- Must retain enough metadata to reproduce operator-visible failures

## TargetPlayerProfile

**Purpose**: Stores the user-confirmed definition of the player of interest.

**Fields**:
- `target_player_profile_id`: Stable identifier
- `team_side`: `home | away | unknown`
- `team_color_notes`: Freeform description of jersey colors
- `jersey_number`: Optional string
- `appearance_notes`: Freeform description of body shape, cleats, accessories, or movement cues
- `reference_frames`: Optional set of user-confirmed frame references
- `confirmation_status`: `unconfirmed | confirmed | revised`

**Validation Rules**:
- At least one identifying cue must be present before confirmation
- Confirmation must occur before verified export

## Player Detection

**Purpose**: Candidate or accepted appearance of the target player during the match window.

**Fields**:
- `detection_id`: Stable identifier
- `project_id`: Parent reference
- `start_time_seconds`: Start offset
- `end_time_seconds`: End offset
- `frame_region`: Bounding region or equivalent target location
- `team_match_confidence`: Confidence that the player belongs to the selected team
- `identity_confidence`: Confidence that the player matches the target profile
- `review_state`: `auto_accepted | needs_review | approved | rejected`
- `visual_cues_used`: Captured cue summary

**Validation Rules**:
- `end_time_seconds` must be greater than or equal to `start_time_seconds`
- Rejected detections cannot be used in verified exports

## Review Decision

**Purpose**: Records a human decision on ambiguous detections.

**Fields**:
- `review_decision_id`: Stable identifier
- `detection_id`: Target detection
- `decision`: `approve | reject | defer`
- `reviewed_at`: Timestamp
- `reviewer_note`: Optional comment

**Validation Rules**:
- Only detections in `needs_review` state can receive a new decision
- The latest non-deferred decision controls export eligibility

## Focus Reel Output

**Purpose**: Represents a generated deliverable for the confirmed target player.

**Fields**:
- `output_id`: Stable identifier
- `project_id`: Parent reference
- `output_profile`: `short_highlight | medium_best_plays`
- `overlay_mode`: `none | target_marker`
- `export_status`: `pending | rendering | ready | failed`
- `resolution`: Target output resolution, initially `1080p`
- `file_format`: Target container, initially `mp4`
- `verification_status`: `unverified | verified | blocked`
- `download_uri`: Optional user-facing retrieval reference

**Validation Rules**:
- `verification_status` cannot be `verified` unless project verification threshold is met
- A ready output must have a download reference

## State Transitions

### Analysis Project

```text
draft
  -> ingesting
  -> ready_for_player_confirmation
  -> analyzing
  -> review_required
  -> ready_for_export
  -> exporting
  -> completed

Any active state -> failed
Any active state -> canceled
```

### Player Detection

```text
needs_review -> approved
needs_review -> rejected
needs_review -> defer
auto_accepted -> approved
```

### Focus Reel Output

```text
pending -> rendering -> ready
pending -> failed
rendering -> failed
```
