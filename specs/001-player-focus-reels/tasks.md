# Tasks: Player Focus Reels

**Input**: Design documents from `/specs/001-player-focus-reels/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.yaml, quickstart.md

**Verification**: Every user story includes verification tasks. Automated coverage is required for API and workflow behavior that can regress in code, and manual validation tasks are included for player-identification accuracy and remote cleanup behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`)
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the backend/frontend workspace and baseline tooling from the implementation plan.

- [X] T001 Create backend and frontend directory skeleton with placeholder packages in `backend/src/.gitkeep`, `backend/tests/.gitkeep`, `frontend/src/.gitkeep`, and `frontend/tests/.gitkeep`
- [X] T002 Initialize backend Python project and virtualenv-oriented dependency manifest in `backend/pyproject.toml`
- [X] T003 [P] Initialize frontend React/Vite project manifest in `frontend/package.json`
- [X] T004 [P] Add repository-level developer environment examples in `.env.example`, `backend/.env.example`, and `frontend/.env.example`
- [X] T005 [P] Add backend and frontend README setup notes aligned with quickstart in `backend/README.md` and `frontend/README.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the core application shell, shared domain model, job orchestration, storage, and observability required by all stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create backend application settings, dependency wiring, and startup entrypoint in `backend/src/app/config.py`, `backend/src/app/dependencies.py`, and `backend/src/app/main.py`
- [X] T007 [P] Create shared API schemas and enumerations from the contract and data model in `backend/src/api/schemas/projects.py`, `backend/src/api/schemas/detections.py`, and `backend/src/api/schemas/exports.py`
- [X] T008 [P] Implement core domain entities for projects, sources, players, detections, reviews, and outputs in `backend/src/domain/models/project.py`, `backend/src/domain/models/source.py`, `backend/src/domain/models/player.py`, `backend/src/domain/models/detection.py`, `backend/src/domain/models/review.py`, and `backend/src/domain/models/output.py`
- [X] T009 Implement lightweight metadata persistence and repository interfaces in `backend/src/storage/database.py`, `backend/src/storage/project_repository.py`, and `backend/src/storage/job_repository.py`
- [X] T010 [P] Implement structured logging, job progress events, and shared error handling in `backend/src/app/logging.py`, `backend/src/app/errors.py`, and `backend/src/api/middleware/error_handling.py`
- [X] T011 [P] Implement worker runner abstraction for local and SSH-triggered remote execution in `backend/src/workers/base.py`, `backend/src/workers/local_runner.py`, and `backend/src/workers/remote_runner.py`
- [X] T012 Implement temporary artifact lifecycle management and cleanup services in `backend/src/services/artifact_service.py` and `backend/src/services/cleanup_service.py`
- [X] T013 [P] Create frontend application shell, router, and shared API client in `frontend/src/app/App.tsx`, `frontend/src/app/router.tsx`, and `frontend/src/services/apiClient.ts`
- [X] T014 [P] Add shared frontend workflow state store and common status components in `frontend/src/features/projects/projectStore.ts`, `frontend/src/components/StepLayout.tsx`, and `frontend/src/components/StatusBanner.tsx`
- [X] T015 Add foundational automated coverage for config, repositories, and runner selection in `backend/tests/unit/test_config.py`, `backend/tests/unit/test_project_repository.py`, and `backend/tests/unit/test_runner_selection.py`

**Checkpoint**: Foundation ready; user story implementation can now begin in priority order or in parallel if staffed.

---

## Phase 3: User Story 1 - Select Source And Confirm Target Player (Priority: P1) 🎯 MVP

**Goal**: Let the user create a project, attach a video source, define the match window, enter target-player cues, and confirm the player through a guided UI.

**Independent Test**: Start a project from a local file or supported link, trim the active match window to exclude non-match footage, define target-player cues, and verify the project reaches a confirmed-player state without invoking review or export workflows.

### Verification for User Story 1

- [X] T016 [P] [US1] Add contract tests for project creation, source attach, match window, and target-player endpoints in `backend/tests/contract/test_projects_api.py`
- [X] T017 [P] [US1] Add backend integration test for guided intake and player-confirmation workflow in `backend/tests/integration/test_project_intake_flow.py`
- [X] T018 [P] [US1] Add frontend workflow test for the source and player setup steps in `frontend/tests/project-intake-flow.test.tsx`

### Implementation for User Story 1

- [X] T019 [P] [US1] Implement source intake service for upload and external-link staging in `backend/src/services/source_service.py`
- [X] T020 [P] [US1] Implement player-profile confirmation service and validation rules in `backend/src/services/player_profile_service.py`
- [X] T021 [US1] Implement project, source, match-window, and target-player API routes in `backend/src/api/routes/projects.py`
- [X] T022 [P] [US1] Implement frontend source-selection and match-window step UI in `frontend/src/features/projects/SourceStep.tsx` and `frontend/src/features/projects/MatchWindowStep.tsx`
- [X] T023 [P] [US1] Implement frontend target-player cue entry and confirmation step UI in `frontend/src/features/projects/TargetPlayerStep.tsx`
- [X] T024 [US1] Wire the guided project-setup flow and backend mutations in `frontend/src/features/projects/ProjectWizardPage.tsx` and `frontend/src/services/projects.ts`
- [X] T025 [US1] Add source-intake and player-confirmation observability hooks in `backend/src/services/source_service.py` and `backend/src/services/player_profile_service.py`

**Checkpoint**: User Story 1 should now support the complete MVP intake and player-confirmation flow independently.

---

## Phase 4: User Story 2 - Review And Verify Player Tracking Accuracy (Priority: P2)

**Goal**: Run player analysis, surface candidate detections, let the user review ambiguous detections, and compute verification status against the 90% threshold.

**Independent Test**: From a confirmed project, launch analysis in local or remote mode, list detections, review ambiguous detections, and confirm the project transitions to ready-for-export only when accepted detections satisfy the verification threshold.

### Verification for User Story 2

- [X] T026 [P] [US2] Add contract tests for analysis start, detection listing, and review decision endpoints in `backend/tests/contract/test_review_api.py`
- [X] T027 [P] [US2] Add backend integration test for analysis, review, and verification-threshold transitions in `backend/tests/integration/test_review_workflow.py`
- [X] T028 [P] [US2] Add frontend test for detection review and verification-status updates in `frontend/tests/review-workflow.test.tsx`
- [X] T029 [US2] Add manual accuracy validation checklist for labeled sample review in `specs/001-player-focus-reels/checklists/manual-review.md`

### Implementation for User Story 2

- [X] T030 [P] [US2] Implement analysis orchestration service and job-state transitions in `backend/src/services/analysis_service.py`
- [X] T031 [P] [US2] Implement multi-cue detection pipeline interfaces and threshold evaluation in `backend/src/services/detection_service.py`
- [X] T032 [P] [US2] Implement review-decision application and verification-score calculation in `backend/src/services/review_service.py`
- [X] T033 [US2] Implement analysis and review API routes in `backend/src/api/routes/analysis.py` and `backend/src/api/routes/reviews.py`
- [X] T034 [P] [US2] Implement frontend analysis status, detection queue, and review actions in `frontend/src/features/review/AnalysisStatusPanel.tsx`, `frontend/src/features/review/DetectionReviewQueue.tsx`, and `frontend/src/features/review/ReviewDecisionBar.tsx`
- [X] T035 [US2] Wire review workflow data fetching and mutations in `frontend/src/features/review/ReviewPage.tsx` and `frontend/src/services/reviews.ts`
- [X] T036 [US2] Add analysis-stage and review-stage logging plus operator diagnostics in `backend/src/services/analysis_service.py` and `backend/src/services/review_service.py`

**Checkpoint**: User Story 2 should now support independently testable analysis, review, and verification behavior on top of the confirmed project flow.

---

## Phase 5: User Story 3 - Generate Shareable Focus Reels (Priority: P3)

**Goal**: Generate short and medium target-player reels, optionally overlay the identified player, and expose downloadable 1080p MP4 exports.

**Independent Test**: From a verified project, request both supported reel profiles, monitor export progress, download the finished files, and confirm that overlay-enabled exports visibly mark the target player while failed or blocked jobs remain clearly labeled.

### Verification for User Story 3

- [X] T037 [P] [US3] Add contract tests for export creation and export status endpoints in `backend/tests/contract/test_exports_api.py`
- [X] T038 [P] [US3] Add backend integration test for reel generation and blocked export behavior below threshold in `backend/tests/integration/test_export_workflow.py`
- [X] T039 [P] [US3] Add frontend test for export requests, progress display, and download readiness in `frontend/tests/export-workflow.test.tsx`
- [X] T040 [US3] Add manual export validation checklist for 1080p MP4 and overlay review in `specs/001-player-focus-reels/checklists/manual-export.md`

### Implementation for User Story 3

- [X] T041 [P] [US3] Implement highlight-selection and timeline assembly service in `backend/src/services/highlight_service.py`
- [X] T042 [P] [US3] Implement MP4 rendering and overlay composition service in `backend/src/services/export_service.py`
- [X] T043 [US3] Implement export API routes and verification-status enforcement in `backend/src/api/routes/exports.py`
- [X] T044 [P] [US3] Implement frontend export request form and output list UI in `frontend/src/features/exports/ExportRequestPanel.tsx` and `frontend/src/features/exports/OutputList.tsx`
- [X] T045 [US3] Wire export workflow interactions and download states in `frontend/src/features/exports/ExportsPage.tsx` and `frontend/src/services/exports.ts`
- [X] T046 [US3] Add export-stage logging, failure reporting, and download metadata handling in `backend/src/services/export_service.py` and `backend/src/storage/job_repository.py`

**Checkpoint**: All three user stories should now be independently functional, with export behavior gated by the verification workflow.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Tighten documentation, cleanup behavior, and end-to-end validation across the full feature.

- [X] T047 [P] Add end-to-end quickstart validation notes and finalized operator runbook details in `specs/001-player-focus-reels/quickstart.md`
- [X] T048 [P] Add remote cleanup verification test doubles and unit coverage for artifact expiration in `backend/tests/unit/test_cleanup_service.py`
- [X] T049 Run end-to-end local and remote workflow validation and document outcomes in `specs/001-player-focus-reels/checklists/final-validation.md`
- [X] T050 Confirm final observability coverage across intake, analysis, review, export, and cleanup in `backend/src/app/logging.py` and `specs/001-player-focus-reels/plan.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion; delivers the MVP.
- **User Story 2 (Phase 4)**: Depends on User Story 1 because analysis requires a confirmed project and player profile.
- **User Story 3 (Phase 5)**: Depends on User Story 2 because verified exports require reviewed detections and threshold evaluation.
- **Polish (Phase 6)**: Depends on completion of the stories being shipped.

### User Story Dependencies

- **US1**: No dependency on later stories; independently valuable and shippable as the initial guided intake flow.
- **US2**: Depends on US1’s confirmed-project flow but remains independently testable once a project exists.
- **US3**: Depends on US2’s verification outputs but remains independently testable once a project is verified.

### Within Each User Story

- Verification tasks come before implementation.
- Backend services come before API route integration.
- Frontend step components come before page wiring.
- Observability and diagnostics must land with the story, not afterward.

### Parallel Opportunities

- Setup tasks `T003` to `T005` can run in parallel after `T002`.
- Foundational tasks `T007`, `T008`, `T010`, `T011`, `T013`, and `T014` can run in parallel once `T006` starts the application structure.
- In US1, `T019`, `T020`, `T022`, and `T023` can run in parallel after verification tasks are written.
- In US2, `T030`, `T031`, `T032`, and `T034` can run in parallel after verification tasks are written.
- In US3, `T041`, `T042`, and `T044` can run in parallel after verification tasks are written.

---

## Parallel Example: User Story 1

```bash
# Launch verification tasks for User Story 1 together
Task: "Add contract tests for project creation, source attach, match window, and target-player endpoints in backend/tests/contract/test_projects_api.py"
Task: "Add backend integration test for guided intake and player-confirmation workflow in backend/tests/integration/test_project_intake_flow.py"
Task: "Add frontend workflow test for the source and player setup steps in frontend/tests/project-intake-flow.test.tsx"

# Launch implementation tasks for User Story 1 together
Task: "Implement source intake service for upload and external-link staging in backend/src/services/source_service.py"
Task: "Implement player-profile confirmation service and validation rules in backend/src/services/player_profile_service.py"
Task: "Implement frontend source-selection and match-window step UI in frontend/src/features/projects/SourceStep.tsx and frontend/src/features/projects/MatchWindowStep.tsx"
Task: "Implement frontend target-player cue entry and confirmation step UI in frontend/src/features/projects/TargetPlayerStep.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Stop and validate the guided intake flow independently before starting analysis and export work.

### Incremental Delivery

1. Deliver the project-setup and player-confirmation MVP from US1.
2. Add automated and manual review capabilities from US2.
3. Add verified export generation from US3.
4. Finish with cleanup, observability, and end-to-end validation polish.

### Parallel Team Strategy

1. One developer owns backend foundation and worker abstractions.
2. One developer owns frontend workflow shells and shared state.
3. After foundation is complete, developers can split by story layer:
   - Backend analysis/review/export services
   - Frontend setup/review/export experiences
   - Verification and manual validation artifacts

---

## Notes

- All tasks follow the required checklist format with IDs, optional `[P]` markers, required `[US#]` labels for story work, and exact file paths.
- Manual validation is explicitly included where player-identity accuracy and rendered-video quality are not practical to fully automate.
- Suggested MVP scope: Phase 3 / User Story 1 only.
