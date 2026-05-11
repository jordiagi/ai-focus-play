# Research: Player Focus Reels

## Decision: Use a Python web backend, browser frontend, and asynchronous worker pipeline

**Rationale**: The feature combines a user-facing guided workflow with compute-heavy video analysis. A Python backend is a strong fit for vision tooling and remote GPU execution, while a browser frontend keeps the workflow accessible on the local Mac without installing a native UI.

**Alternatives considered**:
- A desktop-only app was rejected because it complicates distribution and remote execution coordination.
- A notebook-first workflow was rejected because it does not satisfy the guided non-technical user experience.
- A fully synchronous backend was rejected because 2-hour video jobs need explicit long-running job handling.

## Decision: Run analysis through a worker runner abstraction that supports local execution and SSH-triggered remote execution

**Rationale**: The user has both an M4 Mac for local development and an Ubuntu box with 2 H100 GPUs. A runner abstraction lets the same project submit jobs locally for small tests and remotely for production-scale processing without changing the UI contract.

**Alternatives considered**:
- Local-only execution was rejected because full-match analysis may be too slow for practical use.
- Remote-only execution was rejected because local iteration and fallback should remain possible.
- A full queue platform was rejected for v1 because SSH-triggered worker execution is simpler and matches current infrastructure access.

## Decision: Keep source videos and derived working files ephemeral on processing hosts

**Rationale**: The user explicitly requires that nothing be stored permanently on the remote target. The design therefore treats uploaded/downloaded inputs, extracted frames, intermediate tracks, and rendered outputs as job-scoped temporary artifacts with cleanup on success, cancellation, or expiry.

**Alternatives considered**:
- Persistent remote object storage was rejected because it conflicts with the stated retention constraint.
- Shared long-term worker caches were rejected because they increase privacy and cleanup risk.

## Decision: Use a multi-cue player identity strategy rather than a single signal

**Rationale**: The feature must work on Veo, iPad, and similar recordings where jersey number visibility can vary. Combining team color, jersey number, motion continuity, body shape, accessories, and optional user-confirmed examples provides a more robust foundation than any single cue.

**Alternatives considered**:
- Jersey number only was rejected because numbers are often obscured or unreadable.
- Team color only was rejected because it cannot distinguish between teammates.
- Face recognition only was rejected because match footage often lacks reliable face crops.

## Decision: Require a review step for low-confidence detections before a reel can be marked verified

**Rationale**: The user wants 90% accuracy confidence. Human review is the practical control for ambiguous detections, and it aligns with the specification's requirement that verified reels not be produced from insufficiently trusted tracks.

**Alternatives considered**:
- Fully automatic verification was rejected because it would overstate confidence in ambiguous footage.
- Manual-only clipping was rejected because it would eliminate the efficiency gains of automated detection and tracking.

## Decision: Generate outputs from an event timeline built on accepted target-player detections

**Rationale**: A normalized event timeline provides a clean seam between analysis and export. Short and medium reels can be selected from the same accepted candidate set, and overlay exports can be rendered as a presentation option rather than a separate detection pass.

**Alternatives considered**:
- Directly clipping from raw detections without a normalized timeline was rejected because it makes review, ranking, and export logic harder to reason about.
- Producing only one reel type was rejected because the feature requires at least short and medium outputs.

## Decision: Expose explicit job, review, and export APIs

**Rationale**: The frontend needs deterministic state transitions across a multi-step workflow. Explicit contracts for project creation, source intake, player confirmation, review decisions, and exports support independent testing and future automation.

**Alternatives considered**:
- A single monolithic upload-and-wait endpoint was rejected because it hides job state and review boundaries.
- Tight coupling between frontend and worker internals was rejected because it would weaken testability and future maintainability.
