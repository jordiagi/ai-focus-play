# Research: Simplified Guided Video Workflow

## Decision: Replace the setup wizard with three primary steps

**Decision**: The frontend will present source selection, player confirmation, and reel generation as the only primary steps.

**Rationale**: The user explicitly identified the current workflow as unintuitive and objected to manual match-window entry. Three steps map directly to the user's mental model: choose the match, prove the player, then extract the reel.

**Alternatives considered**:
- Keep separate match-window and target-player steps: rejected because manual start/end times are not part of the desired standard flow.
- Use a single-page advanced form: rejected because it hides the required order and makes player verification feel optional.

## Decision: Discover local videos from the trusted `video/` folder

**Decision**: The backend will expose a list of local video sources under the repository execution `video/` folder, and the frontend will offer those sources in a dropdown.

**Rationale**: The user already stores real match videos there and asked for a dropdown because the application can access the folder. Treating this folder as the local trust boundary supports simple selection while avoiding arbitrary filesystem access.

**Alternatives considered**:
- Browser file picker only: rejected because it does not leverage existing server-side access to the `video/` folder.
- Arbitrary local path input: rejected because it is unsafe and harder to validate.
- Uploading the file into app storage first: rejected for large 2-hour soccer videos and the project's temporary-storage constraint.

## Decision: Define display name as the readable source label

**Decision**: A display name is the user-facing label shown for a video source. For local files it is derived from the filename; for YouTube it is derived from the title when available. Similar or duplicate names must be disambiguated with context.

**Rationale**: The user asked what display name means, which indicates the interface should make this explicit and avoid exposing raw paths as the primary label.

**Alternatives considered**:
- Use only full paths: rejected because full paths are noisy and not user-friendly.
- Force users to type a name: rejected because it adds unnecessary setup friction.

## Decision: Accept only YouTube links or relative paths under `video/`

**Decision**: Manual source entry will accept supported YouTube links and relative local paths that resolve under `video/`. Absolute paths and path traversal outside `video/` are rejected.

**Rationale**: This meets the user's requested source types while preventing accidental access to unrelated local files.

**Alternatives considered**:
- Support all HTTP URLs: rejected for v1 because the user specifically called out YouTube and local video sources.
- Support absolute paths: rejected because it weakens the project-local boundary and complicates operator expectations.

## Decision: Infer match window automatically and surface uncertainty

**Decision**: The standard workflow will not ask for start and end times. The backend will represent an inferred match portion with confidence and a user-visible uncertainty state.

**Rationale**: The user explicitly said manual window selection should not be required. Match inference can be simple initially and improve over time, but the UX contract should remove the manual requirement now.

**Alternatives considered**:
- Keep manual start/end fields as required setup: rejected by the feature request.
- Hide the existing match-window fields without modeling inference: rejected because downstream analysis and progress need a clear state.
- Ask for manual times only when inference fails: deferred; the v1 fallback is to communicate uncertainty and remain review-safe rather than reintroduce required timing inputs.

## Decision: Confirm player through uncropped evidence before extraction

**Decision**: The application will present uncropped candidate-player evidence after the user enters a jersey number and before extraction can begin.

**Rationale**: The user wants to verify the software has detected the correct player first. Uncropped frames preserve jersey number context, body shape, team color, and cleats, matching the user's human identification process.

**Alternatives considered**:
- Cropped player-only thumbnails: rejected because they may remove jersey number and surrounding context.
- Skip confirmation when confidence is high: rejected because the user asked for confirmation and 90% accuracy matters.

## Decision: Record identity cues from confirmed evidence

**Decision**: After confirmation, the system records jersey number, team/jersey color, body appearance, and cleat appearance when visible as a confirmed player identity profile.

**Rationale**: The user described these visual cues as the way a human identifies the player. Capturing them in the model gives the second extraction pass explicit reviewable context.

**Alternatives considered**:
- Store only the jersey number: rejected because jersey numbers can be obscured, duplicated, or confused across teams.
- Require users to manually type all cues: rejected because the request says the software should infer these cues after confirmation.

## Decision: Preserve current stack and add contract surfaces only where needed

**Decision**: Keep the existing FastAPI/React/Vite structure and extend it with source discovery, source validation, match inference status, candidate evidence, and confirmation endpoints or payloads.

**Rationale**: The project already has working project, source, target-player, analysis, review, and export foundations. The feature is a UX and workflow redesign, not a platform rewrite.

**Alternatives considered**:
- Replace the frontend framework or backend architecture: rejected as unnecessary scope and not requested.
- Build a separate desktop app: rejected because the existing browser workflow already matches the project direction.
