# Implementation Plan: Player Focus Reels

**Branch**: `001-player-focus-reels` | **Date**: 2026-05-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-player-focus-reels/spec.md`

## Summary

Build a guided web application that ingests a soccer match video from local upload or a supported link, lets the user confirm the match window and target player, runs multi-cue player tracking and review, and exports verified 1080p MP4 focus reels. The implementation will use a Python backend with GPU-capable analysis workers, a lightweight browser UI for the step-by-step workflow, temporary workspace storage only, and explicit job/review/export APIs.

## Technical Context

**Language/Version**: Python 3.11 for backend and workers; TypeScript 5.x for frontend  
**Primary Dependencies**: FastAPI, Pydantic, Uvicorn, React, Vite, OpenCV, FFmpeg, PyTorch, yt-dlp, a tracker/detector stack, and an HTTP client for worker orchestration  
**Storage**: Local ephemeral files for active jobs, lightweight relational metadata store for projects/jobs/review decisions, and structured JSON logs  
**Testing**: `pytest` for backend/unit/integration coverage, contract validation for API schema, frontend component and flow tests, and manual accuracy-review test scripts for player verification  
**Target Platform**: Local macOS development on Apple Silicon and remote Ubuntu GPU execution over SSH  
**Project Type**: Web application with backend API, frontend UI, and asynchronous analysis workers  
**Observability**: Structured application logs, job lifecycle events, worker execution logs, error payloads, and per-stage progress reporting  
**Performance Goals**: Accept and process typical 2-hour match recordings, provide visible progress during long-running stages, and complete verified 1080p reel export without user restarts for normal jobs  
**Constraints**: No permanent retention on temporary GPU hosts, must support user review before verified export, must handle ambiguous visual identity cases, and must keep the workflow simple for non-technical users  
**Scale/Scope**: v1 supports soccer only, one target player per project, one source video per project, local and single-remote processing modes, and a small number of concurrent operator-driven jobs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Scope traces to explicit user stories, requirements, or defect reports.
- [x] Each user story remains independently implementable and independently verifiable.
- [x] Verification approach is defined before implementation, including automated tests or documented manual validation where automation is not practical.
- [x] Observability, operator impact, and quickstart/runtime documentation changes are captured in the plan.
- [x] Added complexity, dependencies, migrations, or breaking changes are justified, or none are introduced.

## Project Structure

### Documentation (this feature)

```text
specs/001-player-focus-reels/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api.yaml
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   ├── domain/
│   ├── services/
│   ├── workers/
│   ├── storage/
│   └── integrations/
└── tests/
    ├── contract/
    ├── integration/
    └── unit/

frontend/
├── src/
│   ├── app/
│   ├── components/
│   ├── features/
│   └── services/
└── tests/

video/
└── sample inputs and temporary local artifacts kept outside committed source
```

**Structure Decision**: Use a web-application split with `backend/` and `frontend/` because the feature requires a guided browser workflow plus long-running video-analysis services. Keep analysis workers inside the backend codebase initially to avoid introducing a second deployable service before it is necessary.

## Phase 0: Research

- Capture stack and architecture choices in [research.md](./research.md).
- Resolve identity-verification, temporary-storage, remote-execution, and export-pipeline decisions before implementation.

## Phase 1: Design & Contracts

- Define entities, state transitions, and validation rules in [data-model.md](./data-model.md).
- Define the initial HTTP contract in [contracts/api.yaml](./contracts/api.yaml).
- Document local setup, remote execution assumptions, and manual validation steps in [quickstart.md](./quickstart.md).
- Update `AGENTS.md` so future work pulls context from this plan.

## Post-Design Constitution Check

- [x] Stories remain separable into intake/player selection, review/verification, and export delivery slices.
- [x] Verification work includes automated API and workflow coverage plus manual player-accuracy review.
- [x] Observability requirements are represented in job states, progress events, and error handling.
- [x] Complexity is contained to a single backend, single frontend, and pluggable worker runner abstraction.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
