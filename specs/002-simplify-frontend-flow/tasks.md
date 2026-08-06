# Tasks: Simplified Guided Video Workflow

**Input**: Design documents from `/specs/002-simplify-frontend-flow/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Verification**: Every user story includes automated verification tasks first. Manual validation is added only where human visual judgment is required for player identity.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it edits different files and does not depend on incomplete tasks.
- **[Story]**: Maps task to a user story: [US1], [US2], [US3].
- Every task includes exact file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align project pointers and prepare shared files for the simplified guided workflow.

- [x] T001 Verify the active feature pointer and plan context reference in `.specify/feature.json` and `AGENTS.md`
- [x] T002 [P] Add video-root configuration defaults for local discovery in `backend/src/app/config.py`
- [x] T003 [P] Add shared frontend workflow type definitions in `frontend/src/features/projects/guidedTypes.ts`
- [x] T004 [P] Add shared guided workflow shell component for the three-step layout in `frontend/src/components/GuidedWorkflowShell.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain, schema, and routing foundations required before user story work.

**Critical**: No user story work should begin until this phase is complete.

- [x] T005 Extend project workflow/status fields for choose-source, confirm-player, and generate-reels states in `backend/src/domain/models/project.py`
- [x] T006 [P] Extend video source and source catalog domain models for display names, relative paths, validation status, and details in `backend/src/domain/models/source.py`
- [x] T007 [P] Add guided workflow response schemas for project state, progress, match inference, and validation errors in `backend/src/api/schemas/guided.py`
- [x] T008 [P] Add source catalog request/response schemas for discovered local videos in `backend/src/api/schemas/sources.py`
- [x] T009 Update repository serialization to preserve new workflow, source, match inference, and identity fields in `backend/src/storage/project_repository.py`
- [x] T010 Register the planned source routes and guided schemas in `backend/src/app/main.py` and `backend/src/api/routes/__init__.py`
- [x] T011 [P] Add frontend API client helpers for guided project state normalization in `frontend/src/services/projects.ts`

**Checkpoint**: Foundation ready; user story implementation can start.

---

## Phase 3: User Story 1 - Choose a Video Source First (Priority: P1) MVP

**Goal**: The first screen asks only for video source selection, supports discovered local videos, YouTube links, and relative paths under `video/`, and never requires manual start/end times.

**Independent Test**: A user can select a discovered local video or valid source entry, continue to player confirmation, and see a clear rejection for absolute or outside-folder paths without entering match times.

### Verification for User Story 1

- [x] T012 [P] [US1] Add contract tests for `GET /sources/local` and `POST /projects/{projectId}/source` source validation in `backend/tests/contract/test_source_catalog_api.py`
- [x] T013 [P] [US1] Add unit tests for local video discovery, display-name disambiguation, and path containment in `backend/tests/unit/test_source_catalog_service.py`
- [x] T014 [P] [US1] Add integration test for source-first setup with no manual match-window request in `backend/tests/integration/test_simplified_source_flow.py`
- [x] T015 [P] [US1] Add frontend flow test for dropdown source selection, YouTube entry, relative path entry, and outside-folder rejection in `frontend/tests/simplified-source-flow.test.tsx`

### Implementation for User Story 1

- [x] T016 [P] [US1] Implement local video discovery and display-name disambiguation in `backend/src/services/source_catalog_service.py`
- [x] T017 [P] [US1] Implement automatic match-portion inference with confidence and uncertainty summary in `backend/src/services/match_inference_service.py`
- [x] T018 [US1] Add the `GET /sources/local` route for discovered local videos in `backend/src/api/routes/sources.py`
- [x] T019 [US1] Update project source selection schemas for `discovered_local`, `relative_local_path`, and `youtube` sources in `backend/src/api/schemas/projects.py`
- [x] T020 [US1] Update source selection service behavior to reject absolute paths and paths outside `video/` in `backend/src/services/source_service.py`
- [x] T021 [US1] Update project source route behavior to infer match portion and advance to player confirmation without manual window entry in `backend/src/api/routes/projects.py`
- [x] T022 [P] [US1] Add frontend local-source catalog API client in `frontend/src/services/sources.ts`
- [x] T023 [US1] Replace the old source form with dropdown, YouTube link, and relative path controls in `frontend/src/features/projects/VideoSourceStep.tsx`
- [x] T024 [US1] Remove standard-flow manual match-window requirements from the guided setup page in `frontend/src/features/projects/ProjectWizardPage.tsx`
- [x] T025 [US1] Wire the new source-first screen into the app shell and router in `frontend/src/app/App.tsx` and `frontend/src/app/router.tsx`

**Checkpoint**: User Story 1 is independently functional and can be demoed as the MVP.

---

## Phase 4: User Story 2 - Confirm the Target Player From Evidence (Priority: P2)

**Goal**: The user enters a jersey number, reviews uncropped candidate evidence, confirms or rejects candidates, and locks identity cues before extraction can begin.

**Independent Test**: After a valid source is selected, a user can request candidate evidence by jersey number, reject one candidate, confirm another, and see jersey/team color, body appearance, or cleat cues recorded when visible.

### Verification for User Story 2

- [x] T026 [P] [US2] Add contract tests for `POST /projects/{projectId}/player-request`, `GET /projects/{projectId}/player-candidates`, and `POST /projects/{projectId}/player-confirmation` in `backend/tests/contract/test_player_confirmation_api.py`
- [x] T027 [P] [US2] Add unit tests for candidate evidence generation, visible cue summaries, rejection, and identity profile confirmation in `backend/tests/unit/test_player_evidence_service.py`
- [x] T028 [P] [US2] Add integration test for jersey-number request, rejected candidate, confirmed candidate, and extraction unlock state in `backend/tests/integration/test_player_confirmation_flow.py`
- [x] T029 [P] [US2] Add frontend flow test for jersey number entry, uncropped evidence display, reject action, confirm action, and identity cue summary in `frontend/tests/player-confirmation-flow.test.tsx`

### Implementation for User Story 2

- [x] T030 [US2] Extend player domain models with target player request, candidate evidence, and confirmed identity profile records in `backend/src/domain/models/player.py`
- [x] T031 [P] [US2] Implement candidate evidence generation and uncropped evidence placeholders in `backend/src/services/player_evidence_service.py`
- [x] T032 [P] [US2] Implement player confirmation and identity cue recording service in `backend/src/services/player_confirmation_service.py`
- [x] T033 [US2] Update repository storage for candidate evidence and confirmed identity profiles in `backend/src/storage/project_repository.py`
- [x] T034 [US2] Add player request, candidate listing, and confirmation endpoints in `backend/src/api/routes/projects.py`
- [x] T035 [US2] Add player request and confirmation schemas to guided project responses in `backend/src/api/schemas/projects.py`
- [x] T036 [P] [US2] Add frontend service methods for player request, candidate list, and confirmation in `frontend/src/services/projects.ts`
- [x] T037 [P] [US2] Implement uncropped candidate evidence review panel in `frontend/src/features/projects/CandidateEvidencePanel.tsx`
- [x] T038 [US2] Implement jersey-number player confirmation step with confirm, reject, retry, and restart actions in `frontend/src/features/projects/PlayerConfirmationStep.tsx`
- [x] T039 [US2] Gate guided workflow progression on confirmed player evidence in `frontend/src/features/projects/ProjectWizardPage.tsx`

**Checkpoint**: User Stories 1 and 2 work independently; extraction remains blocked until player confirmation.

---

## Phase 5: User Story 3 - Generate Reels Only After Player Confirmation (Priority: P3)

**Goal**: Reel generation is available only after player confirmation and offers short, medium, and target-marker output choices with clear progress.

**Independent Test**: A user cannot generate a reel before confirmation, can request short and medium reels after confirmation, can enable the target marker, and sees progress or failure messages in plain language.

### Verification for User Story 3

- [x] T040 [P] [US3] Add contract tests for export rejection before confirmation and accepted guided reel requests after confirmation in `backend/tests/contract/test_guided_exports_api.py`
- [x] T041 [P] [US3] Add integration test for confirmed-player short, medium, and target-marker export flow in `backend/tests/integration/test_guided_export_flow.py`
- [x] T042 [P] [US3] Add frontend flow test for blocked pre-confirmation generation and post-confirmation short, medium, and marker options in `frontend/tests/generate-reels-flow.test.tsx`

### Implementation for User Story 3

- [x] T043 [US3] Update export schemas for guided reel request profile, target marker, and blocked-state responses in `backend/src/api/schemas/exports.py`
- [x] T044 [US3] Update export API gating so unconfirmed players cannot request reels in `backend/src/api/routes/exports.py`
- [x] T045 [US3] Update export service to use confirmed identity profile cues and target marker option in `backend/src/services/export_service.py`
- [x] T046 [P] [US3] Add frontend export service support for guided reel generation payloads in `frontend/src/services/exports.ts`
- [x] T047 [US3] Implement the generate-reels step with short, medium, and target-marker choices in `frontend/src/features/projects/ReelGenerationStep.tsx`
- [x] T048 [US3] Integrate reel generation progress and ready/failed output messaging into the guided page in `frontend/src/features/projects/ProjectWizardPage.tsx`

**Checkpoint**: All user stories are independently functional and the full guided workflow is complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete workflow, update documentation, and record manual review requirements.

- [x] T049 [P] Update quickstart validation notes with any implementation-specific command or workflow changes in `specs/002-simplify-frontend-flow/quickstart.md`
- [x] T050 [P] Add manual frontend/player identity validation checklist in `specs/002-simplify-frontend-flow/checklists/manual-frontend-flow.md`
- [x] T051 [P] Add final automated validation checklist for backend tests, frontend tests, compile, and build in `specs/002-simplify-frontend-flow/checklists/final-validation.md`
- [x] T052 Run backend automated validation and record results in `specs/002-simplify-frontend-flow/checklists/final-validation.md`
- [x] T053 Run frontend automated validation and record results in `specs/002-simplify-frontend-flow/checklists/final-validation.md`
- [ ] T054 Run the quickstart workflow manually with at least one local video and record player-identity review results in `specs/002-simplify-frontend-flow/checklists/manual-frontend-flow.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundation and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundation and can use US1 source state for the full flow, but its backend candidate/confirmation work remains independently testable with seeded projects.
- **User Story 3 (Phase 5)**: Depends on Foundation and confirmed identity state from US2 for the full flow, but its export gating can be contract-tested with seeded project states.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 - Choose a Video Source First**: Start after Phase 2; no dependency on US2 or US3.
- **US2 - Confirm the Target Player From Evidence**: Start after Phase 2; integrates with US1 for end-to-end UX but can be tested with prepared source-ready projects.
- **US3 - Generate Reels Only After Player Confirmation**: Start after Phase 2; requires confirmed player state for successful export tests and must reject unconfirmed projects.

### Within Each User Story

- Verification tasks come before implementation tasks.
- Contract and unit tests can be written in parallel when they touch different files.
- Domain models and schemas precede service implementation.
- Services precede route/UI integration.
- Frontend components integrate after service clients exist.
- Each checkpoint should pass before moving to the next priority story.

---

## Parallel Execution Examples

### User Story 1

```bash
Task: "T012 Contract tests in backend/tests/contract/test_source_catalog_api.py"
Task: "T013 Unit tests in backend/tests/unit/test_source_catalog_service.py"
Task: "T015 Frontend flow test in frontend/tests/simplified-source-flow.test.tsx"
Task: "T016 Source catalog service in backend/src/services/source_catalog_service.py"
Task: "T017 Match inference service in backend/src/services/match_inference_service.py"
```

### User Story 2

```bash
Task: "T026 Contract tests in backend/tests/contract/test_player_confirmation_api.py"
Task: "T027 Unit tests in backend/tests/unit/test_player_evidence_service.py"
Task: "T029 Frontend flow test in frontend/tests/player-confirmation-flow.test.tsx"
Task: "T031 Player evidence service in backend/src/services/player_evidence_service.py"
Task: "T037 Candidate evidence panel in frontend/src/features/projects/CandidateEvidencePanel.tsx"
```

### User Story 3

```bash
Task: "T040 Contract tests in backend/tests/contract/test_guided_exports_api.py"
Task: "T041 Integration tests in backend/tests/integration/test_guided_export_flow.py"
Task: "T042 Frontend flow test in frontend/tests/generate-reels-flow.test.tsx"
Task: "T046 Frontend export service in frontend/src/services/exports.ts"
```

---

## Implementation Strategy

### MVP First: User Story 1 Only

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for source-first selection.
3. Stop and validate that users can choose a discovered local video, YouTube link, or safe relative path without entering match times.
4. Demo the new first step before implementing player confirmation.

### Incremental Delivery

1. Deliver US1 to remove the confusing setup and manual match-window requirement.
2. Add US2 so users can confirm the target player from uncropped evidence.
3. Add US3 so exports are generated only after the player is confirmed.
4. Run Phase 6 validation after the selected story set is complete.

### Parallel Team Strategy

1. Complete Setup and Foundation together.
2. Split by story where possible: one engineer on source selection, one on player confirmation, one on export gating.
3. Keep shared files such as `backend/src/api/routes/projects.py`, `backend/src/storage/project_repository.py`, and `frontend/src/features/projects/ProjectWizardPage.tsx` serialized to avoid merge conflicts.

## Notes

- [P] tasks must not edit the same file as another in-flight task.
- Every task is traceable to a spec requirement, design artifact, or validation need.
- Manual player identity validation remains required because visual correctness cannot be fully automated.
- Commit after each completed phase or logical task group.
