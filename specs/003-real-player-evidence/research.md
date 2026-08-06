# Research: Real Player Evidence

## Decision: Generate evidence artifacts from the selected video with FFmpeg

**Rationale**: The immediate defect is that Step 2 shows fake candidate media. FFmpeg is already part of the project assumptions and local environment, can extract timestamped frames and short clips from MP4 sources, and avoids adding a heavy ML dependency before the real-media contract is correct.

**Alternatives considered**:
- Keeping the current synthetic candidates was rejected because it directly violates the feature requirement.
- Adding a full detector stack as the first change was rejected because it would combine media plumbing, UI contract, model selection, and accuracy tuning in one large change.
- Copying or transcoding the entire source video was rejected because evidence only needs small review artifacts and source videos should not be duplicated permanently.

## Decision: Store evidence as project-scoped disposable artifacts

**Rationale**: The user must see real thumbnails or clips, so metadata alone is insufficient. Evidence artifacts should live under the existing project data directory, be linked from candidate records, and remain disposable with the rest of project artifacts.

**Alternatives considered**:
- Embedding media as base64 in JSON was rejected because previews and clips can be large.
- Serving media from the source video path directly was rejected because the UI needs stable, review-sized artifacts and should not expose arbitrary filesystem paths.
- Permanent shared evidence storage was rejected because the project already treats media artifacts as temporary.

## Decision: Represent candidate player identities separately from evidence samples

**Rationale**: The user wants a series of player identities that match jersey number and color, not isolated unrelated frames. A candidate identity can aggregate multiple evidence samples, visible cues, score details, and review state while still preserving every source timestamp.

**Alternatives considered**:
- Returning only three frame records was rejected because it cannot express multiple samples for the same player or compare candidate identities.
- Confirming a jersey number without candidate identity state was rejected because reel generation must target the selected player, not the number alone.

## Decision: Use a transparent matching boundary for jersey number and jersey color

**Rationale**: The current code cannot honestly read jersey numbers from real soccer footage. The new workflow must still pass the requested jersey number and optional color hint into a matcher boundary, record whether number/color cues were detected, inferred, or unknown, and avoid marking weak evidence as verified. If matching is unavailable or insufficient, the system should show no-result or review-needed real media rather than fabricate confidence.

**Alternatives considered**:
- Claiming jersey-number matches without detection evidence was rejected because it would repeat the current trust problem.
- Blocking the entire feature until a production-grade jersey OCR model exists was rejected because real media evidence and human confirmation are valuable immediately.
- Hardcoding jersey-color or body-shape descriptions was rejected because those cues must come from the selected evidence.

## Decision: Keep confirmation as the accuracy gate

**Rationale**: Even with real media extraction, soccer footage can contain duplicated numbers, occlusion, and ambiguous team colors. Human confirmation must remain the point where a candidate becomes the target identity for reel generation.

**Alternatives considered**:
- Automatically confirming the highest-ranked candidate was rejected because it can select the wrong player.
- Allowing exports without evidence-backed confirmation was rejected because it violates the gated workflow and undermines scouting output quality.

## Decision: Frontend renders actual media and explicit evidence states

**Rationale**: The user needs to inspect real examples. Step 2 must therefore show real thumbnails or playable clips, timestamps, cue status, evidence counts, and clear progress/no-result/failure messages.

**Alternatives considered**:
- Keeping gradient placeholder cards was rejected because it hides whether video processing occurred.
- Showing only text cue summaries was rejected because player identity is a visual decision.
