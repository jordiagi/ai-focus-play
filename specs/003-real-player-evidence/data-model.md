# Data Model: Real Player Evidence

## Evidence Search Request

Represents the user's request to find real video evidence for a jersey number in the selected source.

**Fields**:
- `target_player_request_id`: Stable request identifier.
- `project_id`: Owning project.
- `source_id`: Source video used for evidence extraction.
- `jersey_number`: User-entered target number.
- `optional_team_hint`: Optional team/color hint from the user.
- `request_status`: `pending_evidence`, `processing`, `candidates_ready`, `no_candidates`, or `failed`.
- `progress_message`: User-visible explanation of the current state.
- `created_at`, `updated_at`: Request timestamps.
- `failure_reason`: Plain-language reason when the request fails.

**Validation rules**:
- A project must have an attached source before a request can be created.
- `jersey_number` must be non-empty after trimming.
- A new request for the same project supersedes previous unconfirmed candidates for that project.

## Evidence Sample

Represents one real frame or short clip extracted from the selected source video.

**Fields**:
- `evidence_sample_id`: Stable sample identifier.
- `project_id`: Owning project.
- `source_id`: Source video from which the sample was extracted.
- `candidate_id`: Candidate identity this sample supports.
- `sample_type`: `frame` or `clip`.
- `timestamp_seconds`: Representative source timestamp.
- `start_seconds`, `end_seconds`: Source span for clips or frame context.
- `media_uri`: Backend-served URI for the frame or clip artifact.
- `thumbnail_uri`: Backend-served URI for the preview image.
- `artifact_path`: Internal project-scoped artifact path.
- `origin`: `source_video`.
- `jersey_number_status`: `matched`, `not_matched`, `unknown`, or `not_visible`.
- `jersey_color_status`: `matched`, `not_matched`, `unknown`, or `not_visible`.
- `visible_cues`: Visible cue labels such as `jersey_number`, `jersey_color`, `body_shape`, `cleats`, and `team_context`.
- `cue_summary`: Plain-language summary of what the user can inspect.

**Validation rules**:
- `origin` must be `source_video` for any sample shown to the user.
- `media_uri` must refer to an artifact generated for the same `project_id`.
- Samples with missing artifacts must not be returned as selectable evidence.
- Source timestamps must fall within the selected or inferred match portion when that portion is known.

## Candidate Player Identity

Represents a possible target player assembled from one or more evidence samples.

**Fields**:
- `candidate_id`: Stable candidate identifier.
- `project_id`: Owning project.
- `target_player_request_id`: Evidence request that produced the candidate.
- `jersey_number`: Requested jersey number.
- `inferred_team_color`: Team color inferred from samples when available.
- `confidence`: Ranking score from available matching and cue signals.
- `review_state`: `candidate`, `confirmed`, `rejected`, or `insufficient`.
- `evidence_count`: Number of supporting real samples.
- `sample_ids`: Supporting evidence sample identifiers.
- `visible_cues`: Aggregated visible cue labels.
- `cue_summary`: Plain-language summary for the candidate.
- `match_reasons`: Human-readable reasons the candidate is relevant.
- `review_warning`: Explanation when number/color evidence is weak or unknown.

**Validation rules**:
- A candidate must have at least one valid `EvidenceSample` before it can be returned.
- A candidate cannot be confirmed after it has been rejected.
- Only one candidate per project can be confirmed at a time.

## Confirmed Player Identity

Represents the user-approved target player used by extraction and exports.

**Fields**:
- `player_identity_profile_id`: Stable confirmed identity identifier.
- `project_id`: Owning project.
- `confirmed_candidate_ids`: Candidate identities approved by the user.
- `approved_sample_ids`: Evidence samples used for confirmation.
- `jersey_number`: Confirmed target number.
- `jersey_color`: Confirmed or inferred team color.
- `body_shape_summary`: Summary from visible evidence or `not visible`.
- `cleat_summary`: Summary from visible evidence or `not visible`.
- `confidence_status`: `confirmed` or `review_needed`.
- `confirmed_at`: Timestamp of user confirmation.

**Validation rules**:
- Confirmation requires a candidate from the same project with real source-video evidence.
- Confirmation must update the project workflow to `generate_reels`.
- Confirmation must preserve traceability back to supporting sample IDs.

## Reel Output Request

Represents a request to generate a reel from the confirmed identity.

**Fields**:
- `project_id`: Owning project.
- `player_identity_profile_id`: Confirmed identity used as the target.
- `output_profile`: `short_highlight` or `medium_best_plays`.
- `overlay_mode`: `none` or `target_marker`.
- `requested_at`: Request timestamp.

**Validation rules**:
- Reel generation is blocked unless `player_identity_profile_id` is present and confirmed.
- The output request must retain the confirmed identity link for audit and manual review.

## State Transitions

```text
source_ready
  -> awaiting_player_confirmation
  -> evidence_processing
  -> awaiting_player_confirmation with candidates_ready
  -> player_confirmed
  -> generate_reels
  -> ready_for_export
```

Failure and no-result paths:

```text
evidence_processing -> awaiting_player_confirmation with no_candidates
evidence_processing -> awaiting_player_confirmation with failed
candidate -> rejected
candidate -> insufficient
candidate -> confirmed
```
