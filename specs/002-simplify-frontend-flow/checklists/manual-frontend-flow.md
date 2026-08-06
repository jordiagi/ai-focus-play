# Manual Frontend Flow Checklist: Simplified Guided Video Workflow

**Purpose**: Track human visual review that cannot be fully automated  
**Created**: 2026-05-11  
**Feature**: [spec.md](../spec.md)

## Manual Review

- [ ] Open the frontend and confirm the first visible decision is video source selection.
- [ ] Select a real local video from the `video/` dropdown and confirm no manual match-window fields are required.
- [ ] Enter the target jersey number and confirm uncropped evidence is understandable to a human reviewer.
- [ ] Reject at least one incorrect candidate and confirm extraction stays blocked.
- [ ] Confirm the intended player and verify jersey color, body shape, or cleat cues are recorded when visible.
- [ ] Generate short, medium, and target-marker outputs and visually confirm they focus on the confirmed player.

## Notes

- These checks require a human reviewing real soccer footage; automated tests cannot honestly certify player identity accuracy.
