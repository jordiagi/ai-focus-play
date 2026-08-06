# Manual Real Evidence Checklist: Real Player Evidence

**Purpose**: Track visual validation that cannot be honestly certified by automated tests  
**Created**: 2026-05-11  
**Feature**: [spec.md](../spec.md)

## Real Video Review

- [ ] Open the guided frontend and select `video/video.mp4` from the local dropdown.
- [ ] Enter jersey number `8` and click `Show player evidence`.
- [ ] Confirm every selectable candidate displays real media from `/projects/{project_id}/evidence-media/...`.
- [ ] Confirm no gradient placeholder card or fake `/player-candidates/*.jpg` URI appears.
- [ ] Visually inspect the evidence and record whether jersey number `8` is visible.
- [ ] Confirm or reject candidates based on visual evidence and verify Step 3 remains locked until confirmation.
- [ ] Generate a reel after confirmation and visually check that output focuses on the confirmed player.

## Notes

- Automated tests verify real media artifacts, API traceability, and export gating.
- Human visual review is still required to certify player identity accuracy on actual match footage.
- Backend-only smoke on 2026-05-11 used `video/video.mp4`, jersey `8`, one evidence sample, and a temporary `/private/tmp/ai-focus-play-manual-*` data directory that was removed after the run. Result: `candidates_ready`, `origin=source_video`, timestamp `1064.299`, thumbnail served with HTTP 200.
