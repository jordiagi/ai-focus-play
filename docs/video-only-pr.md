# PR draft: Video-only inference boundary and local CPU pilot

Raw recordings currently receive statistics from sparse tracking, fixed geometry, and external match metadata. This change introduces a separate experimental `video_only` artifact-ingestion path that excludes reference enrichment, validates declared input provenance, and leaves unmeasured analytics unavailable. It preserves manual content and rejects enriched/scored records; the CLI requires a separate database.

Local tools now inventory Veo/Marc/BCC sources, prepare hashed dense clips, and run CPU-only people/ball detection with explicit local checkpoints, class checks and frame-count validation. The roadmap, agent handoff, task queue, dependency lock and portable pilot evidence support resuming the work with another agent. This is a foundation for video-only analysis; it does not claim accurate event detection yet.

Validation: full local backend suite 198 passed; published remote-base focused integration suite 62 passed, 1 skipped. Clean-checkout full tests still have seven existing failures requiring private gitignored media/detections; the same failures reproduce before this change. Real three-source clips contain 200 frames each at 10 fps. General YOLO11n ball-candidate presence is too low to support possession/pass analytics; see the session evidence and next task.

Published branch: `feat/video-only-local-pilot-review`. Existing unpublished local match-import commits are excluded. No media, event labels or private archive URLs are included.

GitHub CLI is unauthenticated on this machine. After authentication, create the PR with:

```bash
gh pr create --repo jordiagi/ai-focus-play --base main --head feat/video-only-local-pilot-review --title 'Add video-only inference boundary and local CPU pilot' --body-file docs/video-only-pr.md
```
