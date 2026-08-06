# Implementation Plan: Real Player Evidence

**Branch**: `003-real-player-evidence` | **Date**: 2026-05-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-real-player-evidence/spec.md`

## Summary

Replace the current synthetic three-card player evidence behavior with a real video-backed evidence workflow. The backend will extract timestamped frame and short-clip artifacts from the selected source video, associate those artifacts with candidate player identities and jersey/color cue metadata, and prevent player confirmation or reel generation unless the selected candidate is backed by real media from the project source. The frontend will render actual evidence media with progress/no-result/failure states instead of placeholder cards.

## Technical Context

**Language/Version**: Python 3.11-compatible backend codebase and TypeScript 5.x frontend codebase  
**Primary Dependencies**: FastAPI, Pydantic, React, Vite, Vitest, pytest, FFmpeg/FFprobe for real frame/clip extraction, existing project/source/export services  
**Storage**: Existing JSON metadata store plus project-scoped evidence artifacts under the local ephemeral data directory; source videos remain under `video/` and are not copied permanently; remote work remains job-scoped and cleaned up  
**Testing**: Backend pytest unit/contract/integration coverage; frontend Vitest component/flow coverage; manual visual validation on at least one real local soccer video  
**Target Platform**: Local macOS browser workflow with FFmpeg installed; existing remote Ubuntu GPU path remains available for heavier future evidence matching but is not required for the baseline real-media artifact extraction  
**Project Type**: Web application with backend API, frontend UI, and worker/service seams for video analysis  
**Observability**: User-visible evidence request states plus structured backend events for evidence search start, extracted samples, candidate generation, no-result, confirmation, rejection, and failures  
**Performance Goals**: Evidence request should begin processing immediately and expose progress; initial candidate media should be produced without scanning the full two-hour video frame-by-frame; long videos must avoid blocking the UI without feedback  
**Constraints**: No selectable fake evidence; every candidate must reference real media from the selected source; reel generation stays blocked until a real evidence-backed candidate is confirmed; generated artifacts remain project-scoped and disposable  
**Scale/Scope**: One project, one selected video, one jersey-number evidence request, and one confirmed target identity at a time for v1

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
specs/003-real-player-evidence/
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
│   ├── storage/
│   └── workers/
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

**Structure Decision**: Keep the existing backend/frontend split and extend the current player-evidence service, API route, metadata models, and guided Step 2 UI. The feature does not require a new deployable service or persistent database migration, but it does require a project-scoped evidence artifact directory and a clear detector/matcher seam so future GPU-backed matching can improve candidate ranking without changing the UI contract.

## Phase 0: Research

- Capture real-media extraction, candidate identity grouping, jersey/color matching boundaries, artifact storage, UI rendering, and validation decisions in [research.md](./research.md).
- Resolve all planning unknowns without adding user-facing clarification markers.

## Phase 1: Design & Contracts

- Define evidence requests, samples, candidate identities, confirmation state, and reel linkage in [data-model.md](./data-model.md).
- Define API updates for player evidence requests, candidate listing, evidence media, confirmation, and gated exports in [contracts/api.yaml](./contracts/api.yaml).
- Define the Step 2 frontend behavior for loading, real media display, candidate comparison, no-result, and confirmation gating in [contracts/ui-flow.md](./contracts/ui-flow.md).
- Document local setup, FFmpeg expectations, and manual real-video validation in [quickstart.md](./quickstart.md).
- Update `AGENTS.md` to point future work at this plan.

## Post-Design Constitution Check

- [x] Stories remain separable into real evidence generation, candidate comparison, and selected-identity reel generation.
- [x] Verification includes automated anti-placeholder coverage plus manual real-footage review for identity accuracy.
- [x] Observability requirements are represented as request states, backend events, progress messages, and failure/no-result paths.
- [x] Documentation and quickstart changes are included for local evidence extraction and real-video validation.
- [x] Complexity is limited to extending existing services/contracts and adding project-scoped artifacts; no new deployable service or permanent storage system is introduced.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
