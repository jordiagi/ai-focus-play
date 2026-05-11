<!--
Sync Impact Report
- Version change: N/A -> 1.0.0
- Modified principles:
  - Template Principle 1 -> I. Spec-Driven Changes
  - Template Principle 2 -> II. Independently Verifiable User Value
  - Template Principle 3 -> III. Verification Before Merge
  - Template Principle 4 -> IV. Observability and Operability
  - Template Principle 5 -> V. Minimal, Reversible Delivery
- Added sections:
  - Delivery Standards
  - Workflow & Review
- Removed sections: None
- Templates requiring updates:
  - ✅ updated: .specify/templates/plan-template.md
  - ✅ updated: .specify/templates/spec-template.md
  - ✅ updated: .specify/templates/tasks-template.md
  - ⚠ pending: .specify/templates/commands/*.md (directory not present in this repository)
- Follow-up TODOs: None
-->
# AI Focus Play Constitution

## Core Principles

### I. Spec-Driven Changes
Every non-trivial change MUST begin with current specification artifacts. Work MUST
trace from `spec.md` to `plan.md` to `tasks.md`, and implementation MUST map back
to explicit user stories, requirements, or defect reports. If scope changes during
delivery, the governing artifacts MUST be updated before code continues.

Rationale: This repository uses Spec Kit workflows. The artifacts are not optional
notes; they are the control surface that keeps scope, intent, and implementation
aligned.

### II. Independently Verifiable User Value
Each user story MUST deliver a standalone slice of user value and MUST define an
independent verification path. Plans and tasks MUST preserve this independence so
teams can implement, validate, and if needed ship increments without depending on
unfinished lower-priority stories.

Rationale: Independent slices reduce coordination risk, keep MVP delivery honest,
and make progress measurable.

### III. Verification Before Merge
Every change MUST define its verification approach before implementation starts.
Automated tests MUST be added or updated when behavior can regress in code.
When automation is not feasible, the feature artifacts MUST record manual
validation steps and the reason automation was not practical. Bug fixes MUST
include a reproducible failure description and SHOULD add a regression guard when
the failure can recur.

Rationale: Verification is a design input, not a cleanup step. Making it explicit
early prevents untestable features and weak handoffs.

### IV. Observability and Operability
User-visible, stateful, or integration-affecting behavior MUST provide enough
diagnostic signal to explain failures without local guesswork. That signal may
include structured logs, clear error messages, state transition records, health
checks, or other context-appropriate instrumentation. Any operator-facing setup,
configuration, or runtime assumptions MUST be documented in the feature artifacts
and validated in quickstart or equivalent usage steps.

Rationale: Features that cannot be understood in operation are incomplete, even if
they appear to work locally.

### V. Minimal, Reversible Delivery
Changes MUST be as small as possible while still satisfying the approved scope.
New dependencies, abstractions, data migrations, or breaking changes MUST be
justified in the implementation plan's complexity tracking. Documentation,
templates, and guidance affected by a change MUST be updated in the same unit of
work so the repository remains internally consistent.

Rationale: Small, reversible changes are easier to review, test, diagnose, and
undo when assumptions fail.

## Delivery Standards

- Feature specifications MUST include measurable success criteria, explicit edge
  cases, and any unresolved items marked as `NEEDS CLARIFICATION`.
- Plans MUST record technical context, constitution gates, structure decisions,
  and any complexity justification required by these principles.
- Task lists MUST include exact file paths, preserve user-story grouping, and
  include verification work for every story.
- Quickstart or equivalent execution guidance MUST be updated whenever setup,
  runtime behavior, or verification steps change.

## Workflow & Review

- Before implementation, the Constitution Check in `plan.md` MUST pass or record a
  specific justified exception in Complexity Tracking.
- During implementation, work MUST remain traceable to a story or requirement; do
  not introduce speculative scope.
- Before merge, reviewers MUST verify:
  - verification evidence exists and matches the changed behavior,
  - observability and operator impacts are addressed,
  - docs/templates affected by the change were updated,
  - any exceptions to this constitution are explicit and approved.

## Governance

This constitution supersedes conflicting local process notes for delivery work in
this repository. Amendments MUST be made through an explicit constitution update
that also updates dependent templates and guidance in the same change.

Versioning policy for this constitution follows semantic versioning:
- MAJOR: Removal or incompatible redefinition of a principle or governance rule.
- MINOR: Addition of a principle or material expansion of binding guidance.
- PATCH: Clarifications, wording improvements, or non-semantic refinements.

Compliance review is mandatory at plan creation, task generation, code review, and
before merge. Any unresolved constitution conflict blocks delivery until the
artifacts or the constitution itself are amended explicitly.

**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
