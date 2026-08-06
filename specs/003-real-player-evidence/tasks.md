# Tasks: Real Player Evidence

**Input**: Design documents from `/specs/003-real-player-evidence/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Verification**: Automated tests are required because OR-002 requires checks that selectable evidence is not placeholder media. Manual validation is also required because OR-003 and OR-004 require real-video visual review.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and does not depend on incomplete tasks.
- **[Story]**: User story label for traceability.
- Every task includes an exact file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the existing backend/frontend project for real video evidence artifacts.

- [X] T001 Confirm FFmpeg/FFprobe local evidence prerequisites and troubleshooting notes in `specs/003-real-player-evidence/quickstart.md`
- [X] T002 [P] Add evidence artifact configuration defaults and examples in `backend/src/app/config.py` and `backend/.env.example`
- [X] T003 [P] Add evidence media contract examples for real thumbnails and clips in `specs/003-real-player-evidence/contracts/api.yaml` and `specs/003-real-player-evidence/contracts/ui-flow.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared artifact and cleanup infrastructure that all user stories depend on.

**Critical**: No user story work should begin until this phase is complete.

- [X] T004 Add project-scoped evidence artifact path helpers to `backend/src/services/artifact_service.py`
- [X] T005 [P] Add cleanup coverage for generated evidence artifacts in `backend/src/services/cleanup_service.py` and `backend/tests/unit/test_cleanup_service.py`
- [X] T006 [P] Add backend dependency wiring placeholders for evidence artifact services in `backend/src/app/dependencies.py`

**Checkpoint**: Evidence artifacts have a safe project-scoped location and lifecycle.

---

## Phase 3: User Story 1 - Show Real Video Evidence (Priority: P1)

**Goal**: Replace synthetic Step 2 evidence with real media extracted from the selected source video.

**Independent Test**: Select a local MP4, enter jersey number `8`, request evidence, and verify every selectable item includes a real media URI, a source timestamp, and no placeholder candidate content.

### Verification for User Story 1

- [X] T007 [P] [US1] Add unit tests for frame and short-clip extraction from a synthetic MP4 in `backend/tests/unit/test_evidence_artifact_service.py`
- [X] T008 [P] [US1] Add contract tests that `/projects/{project_id}/player-candidates` returns real `origin`, `media_uri`, `thumbnail_uri`, and timestamp fields with no placeholder URIs in `backend/tests/contract/test_real_player_evidence_api.py`
- [X] T009 [P] [US1] Add integration test for local source selection through evidence artifact creation and evidence media serving in `backend/tests/integration/test_real_player_evidence_flow.py`
- [X] T010 [P] [US1] Add frontend test that `CandidateEvidencePanel` renders actual image or video media and no gradient placeholder card in `frontend/src/features/projects/CandidateEvidencePanel.test.tsx`

### Implementation for User Story 1

- [X] T011 [US1] Extend `EvidenceSample`, `TargetPlayerRequest`, and `CandidatePlayerEvidence` data fields in `backend/src/domain/models/player.py`
- [X] T012 [US1] Persist evidence samples and clear stale unconfirmed evidence for reruns in `backend/src/storage/database.py` and `backend/src/storage/project_repository.py`
- [X] T013 [US1] Implement FFmpeg-backed frame and short-clip extraction in `backend/src/services/evidence_artifact_service.py`
- [X] T014 [US1] Add project-scoped evidence media serving endpoint with path traversal protection in `backend/src/api/routes/projects.py`
- [X] T015 [US1] Replace synthetic candidate generation with real source-video artifact generation and no-placeholder/no-result behavior in `backend/src/services/player_evidence_service.py`
- [X] T016 [US1] Update backend response schemas and frontend guided types for evidence samples, request status, and candidate media fields in `backend/src/api/schemas/projects.py` and `frontend/src/features/projects/guidedTypes.ts`
- [X] T017 [US1] Render real evidence thumbnails or clips, timestamps, and source-video status in `frontend/src/features/projects/CandidateEvidencePanel.tsx`
- [X] T018 [US1] Show loading, no-result, and failure states around real evidence requests in `frontend/src/features/projects/PlayerConfirmationStep.tsx`
- [X] T019 [US1] Emit structured events for evidence search start, samples extracted, candidates ready, no candidates, and failures in `backend/src/services/player_evidence_service.py`

**Checkpoint**: User Story 1 is complete when fake evidence is removed and Step 2 displays only real source-video evidence or an honest no-result/failure state.

---

## Phase 4: User Story 2 - Compare Candidate Player Identities (Priority: P2)

**Goal**: Let the user compare candidate identities grouped from real evidence and reject incorrect or insufficient candidates without unlocking reel generation.

**Independent Test**: Use a video or synthetic fixture with multiple candidate appearances, request evidence, reject one candidate, and verify another candidate can remain selectable while Step 3 stays locked.

### Verification for User Story 2

- [X] T020 [P] [US2] Add unit tests for jersey/color cue status and candidate grouping behavior in `backend/tests/unit/test_player_candidate_matcher.py`
- [X] T021 [P] [US2] Add contract tests for `evidence_count`, `samples`, `match_reasons`, `review_warning`, and response status fields in `backend/tests/contract/test_candidate_identity_api.py`
- [X] T022 [P] [US2] Add frontend interaction tests for multi-sample candidate selection, rejection, warnings, and rerun controls in `frontend/src/features/projects/PlayerConfirmationStep.test.tsx`

### Implementation for User Story 2

- [X] T023 [US2] Create a transparent jersey/color matching boundary with cue status outputs in `backend/src/services/player_candidate_matcher.py`
- [X] T024 [US2] Aggregate real evidence samples into candidate identities with `evidence_count`, `inferred_team_color`, `match_reasons`, and `review_warning` in `backend/src/services/player_evidence_service.py`
- [X] T025 [US2] Make new evidence requests supersede prior unconfirmed candidates and samples for the same project in `backend/src/services/player_evidence_service.py`
- [X] T026 [US2] Preserve rejected and insufficient candidate states while keeping extraction locked in `backend/src/services/player_confirmation_service.py`
- [X] T027 [US2] Return candidate list `status`, `message`, and identity-shaped `items` from `/projects/{project_id}/player-candidates` in `backend/src/api/routes/projects.py`
- [X] T028 [US2] Update frontend candidate identity types and project service parsing for nested samples and status responses in `frontend/src/features/projects/guidedTypes.ts` and `frontend/src/services/projects.ts`
- [X] T029 [US2] Display candidate-level evidence count, match reasons, warnings, and multiple samples in `frontend/src/features/projects/CandidateEvidencePanel.tsx`
- [X] T030 [US2] Advance selection to the next available candidate after rejection and keep rerun controls visible in `frontend/src/features/projects/PlayerConfirmationStep.tsx`

**Checkpoint**: User Story 2 is complete when users can compare real evidence-backed identities, reject candidates, and continue review without unlocking Step 3.

---

## Phase 5: User Story 3 - Generate Reels From the Selected Identity (Priority: P3)

**Goal**: Ensure reel outputs are generated only from the candidate identity confirmed from real evidence and remain traceable to that evidence.

**Independent Test**: Confirm one real evidence-backed candidate, generate a reel, and verify exports are blocked without confirmation and linked to the confirmed identity when allowed.

### Verification for User Story 3

- [X] T031 [P] [US3] Add contract tests that exports reject projects without a real evidence-backed identity and accept confirmed identities in `backend/tests/contract/test_evidence_backed_exports_api.py`
- [X] T032 [P] [US3] Add integration test from candidate confirmation through export creation with identity and evidence trace assertions in `backend/tests/integration/test_evidence_backed_export_flow.py`
- [X] T033 [P] [US3] Add frontend test that `ReelGenerationStep` stays locked until `player_identity_profile` exists and shows confirmed identity summary after confirmation in `frontend/src/features/projects/ReelGenerationStep.test.tsx`

### Implementation for User Story 3

- [X] T034 [US3] Extend confirmed identity trace fields such as `approved_sample_ids` and confirmed candidate metadata in `backend/src/domain/models/player.py`
- [X] T035 [US3] Build confirmed player identity only from candidates with valid real evidence samples in `backend/src/services/player_confirmation_service.py`
- [X] T036 [US3] Require `player_identity_profile_id` and preserve confirmed identity trace during export creation in `backend/src/services/export_service.py` and `backend/src/domain/models/output.py`
- [X] T037 [US3] Update export request/response schema and route behavior for evidence-backed identity gating in `backend/src/api/schemas/exports.py` and `backend/src/api/routes/exports.py`
- [X] T038 [US3] Display confirmed identity and supporting evidence summary before enabling reel controls in `frontend/src/features/projects/ReelGenerationStep.tsx`
- [X] T039 [US3] Preserve identity-linked export request behavior in `frontend/src/services/exports.ts` and `frontend/src/features/exports/ExportRequestPanel.tsx`
- [X] T040 [US3] Emit structured export gating and identity trace events in `backend/src/services/export_service.py`

**Checkpoint**: User Story 3 is complete when exports cannot start without a confirmed real evidence-backed player identity and generated outputs remain traceable to that identity.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and manual review required for this feature.

- [X] T041 [P] Create manual real-video validation checklist in `specs/003-real-player-evidence/checklists/manual-real-evidence.md`
- [X] T042 [P] Create final automated validation checklist in `specs/003-real-player-evidence/checklists/final-validation.md`
- [X] T043 Run backend unit, contract, and integration tests and record results in `specs/003-real-player-evidence/checklists/final-validation.md`
- [X] T044 Run frontend tests and production build and record results in `specs/003-real-player-evidence/checklists/final-validation.md`
- [X] T045 Perform the manual `video/video.mp4` Step 2 evidence workflow and record real-media findings in `specs/003-real-player-evidence/checklists/manual-real-evidence.md`
- [X] T046 Update operator notes for real evidence artifacts, cleanup, and known limitations in `backend/README.md` and `specs/003-real-player-evidence/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; delivers the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and can reuse US1 evidence artifacts; independently verifiable through candidate grouping and rejection.
- **User Story 3 (Phase 5)**: Depends on a confirmed candidate identity from US1/US2 behavior; independently verifiable through export gating.
- **Polish (Phase 6)**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1 - Show Real Video Evidence**: MVP; no dependency on US2 or US3.
- **US2 - Compare Candidate Player Identities**: Builds on the real sample model from US1 but can be validated without export generation.
- **US3 - Generate Reels From the Selected Identity**: Requires confirmed real evidence-backed identity and validates final export gating.

### Within Each User Story

- Verification tasks come before implementation tasks.
- Models and persistence come before services.
- Services come before API routes.
- Backend contract behavior comes before frontend integration.
- Frontend rendering comes after response types are updated.

---

## Parallel Opportunities

- T002 and T003 can run in parallel after T001.
- T005 and T006 can run in parallel after T004 is understood.
- US1 verification tasks T007, T008, T009, and T010 can be created in parallel.
- US2 verification tasks T020, T021, and T022 can be created in parallel.
- US3 verification tasks T031, T032, and T033 can be created in parallel.
- Frontend tasks can proceed in parallel with backend tests once the API contract fields are stable.

---

## Parallel Example: User Story 1

```bash
Task: "T007 [US1] Add unit tests for frame and short-clip extraction in backend/tests/unit/test_evidence_artifact_service.py"
Task: "T008 [US1] Add contract tests for real evidence candidate fields in backend/tests/contract/test_real_player_evidence_api.py"
Task: "T009 [US1] Add integration test for local source through evidence media serving in backend/tests/integration/test_real_player_evidence_flow.py"
Task: "T010 [US1] Add frontend media rendering test in frontend/src/features/projects/CandidateEvidencePanel.test.tsx"
```

## Parallel Example: User Story 2

```bash
Task: "T020 [US2] Add matcher unit tests in backend/tests/unit/test_player_candidate_matcher.py"
Task: "T021 [US2] Add candidate identity contract tests in backend/tests/contract/test_candidate_identity_api.py"
Task: "T022 [US2] Add frontend multi-candidate interaction tests in frontend/src/features/projects/PlayerConfirmationStep.test.tsx"
```

## Parallel Example: User Story 3

```bash
Task: "T031 [US3] Add evidence-backed export contract tests in backend/tests/contract/test_evidence_backed_exports_api.py"
Task: "T032 [US3] Add identity-to-export integration tests in backend/tests/integration/test_evidence_backed_export_flow.py"
Task: "T033 [US3] Add ReelGenerationStep gate tests in frontend/src/features/projects/ReelGenerationStep.test.tsx"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for US1 only.
3. Stop and validate that Step 2 never shows synthetic evidence and either shows real media from the selected video or an honest no-result/failure state.

### Incremental Delivery

1. Deliver US1 to remove fake evidence and establish real media artifacts.
2. Deliver US2 to support candidate identity comparison and rejection without export generation.
3. Deliver US3 to ensure reel generation uses the selected evidence-backed identity.
4. Complete Phase 6 to record automated and manual validation.

### Implementation Notes

- Do not add selectable fallback candidates when extraction or matching fails.
- It is acceptable for the first implementation to mark jersey/color cue status as `unknown` when no reliable detector exists, but the returned media must still come from the selected source video.
- Manual validation on real soccer footage remains required before claiming player identity accuracy.
