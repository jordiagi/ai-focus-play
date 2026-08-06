# Implementation Plan: Simplified Guided Video Workflow

**Branch**: `002-simplify-frontend-flow` | **Date**: 2026-05-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-simplify-frontend-flow/spec.md`

## Summary

Rewrite the guided frontend into a professional three-step workflow: choose a video source, confirm the target player from uncropped evidence, then generate reels. The implementation will reuse the existing backend/frontend split while adding source discovery, safe local-path validation, automatic match-window inference states, candidate evidence review, and confirmed identity cues before export.

## Technical Context

**Language/Version**: Python 3.11-compatible backend codebase and TypeScript 5.x frontend codebase  
**Primary Dependencies**: FastAPI, Pydantic, React, Vite, Vitest, FFmpeg/FFprobe for source metadata, existing analysis/export services  
**Storage**: Existing ephemeral project metadata and artifact workspace; local videos remain under the `video/` folder and are not copied permanently  
**Testing**: Backend pytest unit/contract/integration coverage; frontend Vitest flow coverage; manual visual validation for player identity evidence  
**Target Platform**: Local macOS development and browser UI, with existing remote Ubuntu GPU execution path preserved for analysis-heavy jobs  
**Project Type**: Web application with backend API, frontend UI, and asynchronous analysis/export workers  
**Observability**: User-visible workflow states, structured backend events for source discovery/validation, match inference, candidate evidence, confirmation, extraction, export readiness, and failures  
**Performance Goals**: Source selection and validation should feel immediate for discovered local videos; first-time users should reach player confirmation in under 2 minutes; long-running inference and extraction must show progress  
**Constraints**: Standard workflow must not require manual match start/end entry; local paths must stay under `video/`; extraction must be blocked until the player is confirmed from evidence; human review remains required for final identity certainty  
**Scale/Scope**: One project, one source video, one target player, one guided browser session at a time for v1; supports local discovered videos, relative local paths, and YouTube links

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Scope traces to explicit user stories, requirements, or defect reports.
- [x] Each user story remains independently implementable and independently verifiable.
- [x] Verification approach is defined before implementation, including automated tests
      or documented manual validation where automation is not practical.
- [x] Observability, operator impact, and quickstart/runtime documentation changes
      are captured in the plan.
- [x] Added complexity, dependencies, migrations, or breaking changes are justified,
      or none are introduced.

## Project Structure

### Documentation (this feature)

```text
specs/002-simplify-frontend-flow/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.yaml
│   └── ui-flow.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   ├── routes/
│   │   └── schemas/
│   ├── domain/
│   │   └── models/
│   ├── services/
│   └── storage/
└── tests/
    ├── contract/
    ├── integration/
    └── unit/

frontend/
├── src/
│   ├── app/
│   ├── components/
│   ├── features/
│   │   ├── exports/
│   │   ├── projects/
│   │   └── review/
│   └── services/
└── tests/

video/
└── local selectable match videos, ignored by git
```

**Structure Decision**: Keep the existing web-application split. The feature changes the guided workflow and API contract surfaces but does not require another deployable service, database migration system, or separate worker application.

## Phase 0: Research

- Capture frontend workflow, source discovery, local-path safety, match inference fallback, player evidence, and visual identity cue decisions in [research.md](./research.md).
- Resolve all planning unknowns without adding new user-facing clarification markers.

## Phase 1: Design & Contracts

- Define workflow entities, validation rules, and state transitions in [data-model.md](./data-model.md).
- Define source discovery, guided project setup, candidate evidence, player confirmation, and export readiness contracts in [contracts/api.yaml](./contracts/api.yaml).
- Define the three-step UI behavior contract in [contracts/ui-flow.md](./contracts/ui-flow.md).
- Document local operation and validation scenarios in [quickstart.md](./quickstart.md).
- Update `AGENTS.md` to point future work at this plan.

## Post-Design Constitution Check

- [x] Stories remain separable into source selection, player confirmation, and gated reel generation.
- [x] Verification includes automated source/path/workflow coverage plus explicit manual visual identity validation.
- [x] Observability requirements are represented as user-visible stages and backend event expectations.
- [x] Documentation and quickstart changes are included for local video discovery, display names, and accepted paths.
- [x] No new deployable services, persistent storage systems, migrations, or breaking platform requirements are introduced.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
