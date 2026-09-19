# STATE — live progress tracker

**Purpose:** survive interruption. If you are resuming (any agent, any harness), read
this file first, then `PLAN.md`. Update the status table as you go — a stale status here
is worse than none.

**Last updated:** 2026-09-19 · by Claude Opus 5 · after capturing Veo ground truth

---

## Resume in 60 seconds

1. `PLAN.md` — the roadmap and the reasoning. `context.md` — environment + traps.
   `OPUS2.md` — the 9 defects already closed and how they were verified.
2. **Ground truth is now on disk** at `benchmarks/raw/` (see below). It does **not**
   need re-capturing unless the match changes.
3. Check blockers below before touching gpu-box.
4. `bash scripts/local/verify.sh all` should print `pass=8 fail=0 skip=0`. If it
   doesn't, something regressed — fix that before new work.

---

## Blockers

| Blocker | Impact | Who clears it |
| :-- | :-- | :-- |
| **Tailscale SSH to gpu-box expired** | All Track 1 (GPU) work blocked. `scripts/remote/doctor.sh` will fail with a timeout | **User** — visit the re-auth URL Tailscale prints |
| Veo Bearer token is ephemeral (~minutes) | Only matters if ground truth needs re-capturing; it does not right now | Re-run the capture procedure in `PLAN.md` |

Track 2 (frontend/UI) is **not** blocked by either.

---

## Ground truth captured (2026-09-19)

Pulled from Veo's own API in an authenticated browser session. **This replaces the old
13-event benchmark, whose second-half timestamps were wrong by up to 752 s.**

| File | Contents |
| :-- | :-- |
| `benchmarks/raw/veo_events_447.csv` | **447 events** — `video_time_ms, period_id, period_time_ms, event_type, team, player_jersey, outcome, x, z`. 14 types. 334 carry a jersey, 355 carry pitch coords |
| `benchmarks/raw/veo_highlights_31.csv` | 31 AI highlight clips (goal / shot_on_goal), clip-start seconds |

Verified on disk: type histogram matches the API exactly; 6 goals in both files.

**Time base (measured, exact, linear):** period 1 `video = period_time + 562`;
period 2 `video = period_time + 3674`. Kickoff 562.3; H1 ends 2879.3; halftime 795 s;
H2 starts 3674.4; last event 6132.1. Halves are 2317.0 s and 2457.7 s — **not 2400**.

**Do not re-derive these from match-clock strings.** That is exactly how the old
benchmark went wrong.

---

## Work package status

Legend: ☐ not started · ◐ in progress · ☑ done & verified · ⊘ blocked · ✗ abandoned

### Cross-cutting (do first, cheap, no GPU)

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| X1 | Delete surviving `pass_strings` fabrication (`cv_engine.py:551-554`) and `or 20.0` thirds fallbacks (`:544-549`) | ☐ | Seed was fixed; pipeline was not |
| X2 | Add probe `d10` — no invented analytics literal anywhere | ☐ | Currently nothing covers `pass_strings` |
| X3 | `PitchRadar` must draw nothing for an undetected ball | ☐ | Today it dims to 30% but still draws at coasted coords |

### Track 1 — GPU pipeline (⊘ blocked on Tailscale re-auth)

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| G0 | Rebuild `benchmarks/veo_reference.json` from the 447-event dump; fix `scripts/config.env` time base; decode Veo's x/z convention | ◐ | Raw data captured ☑; JSON rebuild + config fix pending |
| G1 | **Measure ball-detection recall** on a 10-min slice — the go/no-go gate | ☐ | Nothing downstream is trustworthy until this number exists |
| G2 | Mosaic homography + confidence gate, validated on the 71 restart coords | ☐ | |
| G3 | Tier A detectors (7 types) | ☐ | |
| G4 | Possession HMM → Tier B (4 types + Pass count) | ☐ | Conditional on G1 gate |
| G5 | Scoring harness (macro-F1, chance baseline, parity count, period split) | ☐ | `scripts/local/score-benchmark.py` does not exist yet |
| G6 | Ingest artifacts → `analysis_mode="ml"` | ☐ | `ml_ingest.py` does not exist yet |
| G7 | Jersey recognition | ☐ | Last. Unlocks 0 event types. Honest ceiling ~25-40% vs Veo's 75% |

### Track 2 — UI / route parity (not blocked)

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| U1 | Hash router; wire the 6 existing drawers to Veo's routes; real deep-link Share | ☐ | Panels already exist, map 1:1 — this is wiring |
| U2 | Jersey numbers only, never invented names; jersey bar from `lineup` not 17 literals | ☐ | Veo shows `Player ` blank when unresolved |
| U3 | Events drawer shows **all 15 types with per-type status** (`detected (n)` / `not attempted` / `gate not met`) | ☐ | Needs a capability manifest in the data model |
| U4 | Singular stat labels; derived rows as disabled buttons; per-event seek/clip actions | ☐ | |

---

## Done already (do not redo)

- 9 defects closed and verified — `verify.sh all` → `pass=8 fail=0 skip=0`, 35 tests.
  Full record in `OPUS2.md`.
- gpu-box provisioned: torch 2.11.0+cu128, CUDA 12.8, 4× H100, uv-managed CPython 3.12.
  `scripts/remote/provision.sh` is idempotent (re-run → `cached`, exit 10).
- Match video uploaded to `/workspace/aifp/media/video.mp4`, **sha256 verified**
  (`ef7552326b0ab24e...`), 185,003 frames, decodes on the box.
- `scripts/` built: doctor, provision, push-video (resumable), push-code, job-status,
  pull-artifacts, restore, verify, plus the agent dispatch wrapper.
- Veo ground truth captured (above).

---

## Decisions already made (don't relitigate)

- **Both tracks in parallel**; UI is file-disjoint from GPU work.
- **Done bar:** everything honestly reachable; explicitly excluding what we cannot do.
- **Jersey recognition: yes**, but sequenced last.
- `/workspace` is a 64 GB tmpfs — ephemeral by design; `restore.sh` rebuilds it.
- `cv_engine.py` is **frozen** as the `demo` fallback. Do not extend it.

---

## Open questions for the user

- **Ask Veo for the panorama export** of this match. The current file is the
  ball-following crop, which forces per-frame homography — the single most expensive
  layer (G2). A static panorama collapses it to a one-time 8-point calibration.
- Team sheet / roster as a product input, so jersey recognition is a closed-set problem
  rather than open OCR (and so we don't launder Veo's labels into our own prior).
