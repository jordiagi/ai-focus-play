## Package: P7 — the frontend has no tests, and the honesty rules now live there

Owner:        codex / gpt-5.6-sol
Files OWNED:  `frontend/package.json`, `frontend/vitest.config.ts` (NEW), `frontend/src/test/**` (the directory exists and is empty), and new `*.test.tsx` files only
Files READ:   everything under `frontend/src/`, `specs/complete-veo-parity/spec.md`, `specs/complete-veo-parity/wp-5.md`
Out of scope: **every existing `.tsx` / `.ts` source file under `frontend/src/components/` and `frontend/src/services/`.** You are adding tests, not changing behaviour. If a test fails because the component is wrong, **leave the failing test and report it** — do not edit the component to make your test pass. That inversion is how a test suite becomes decoration.

### Why this package exists

Measured 2026-09-23: the frontend is 16 files and ~3,800 lines with **zero tests and
no test framework installed**. `package.json` has no vitest, no jest, no testing-library
and no test script. `frontend/src/test/` exists and is empty.

That mattered less when the frontend only displayed numbers. It matters now, because
the project's central rule is enforced *in the UI*: an undetected ball draws nothing,
an unmeasured stat renders an em-dash, a player with no jersey renders `Player ` with
a blank, and an unavailable capability shows its measured reason. Every one of those
is a behaviour that a careless refactor silently removes, and nothing would catch it.

The backend already holds this line — `backend/tests/unit/test_analytics_consistency.py`
asserts no invented player names server-side. The frontend has no equivalent.

### Contract

1. Install and configure **vitest** + **@testing-library/react** + **jsdom** as
   devDependencies, with a `"test"` script in `package.json`. Keep the existing
   `build` and `lint` scripts working exactly as they are.
2. Write tests for the **honesty invariants**, not for styling. At minimum:
   - `PitchRadar` renders **no ball element** when `ball.detected === false`, and shows
     its "Ball not detected" caption. Assert the absence, not just the caption.
   - The stats table renders an em-dash for a `null` stat and a real number for a
     non-null one (`renderStatValue`).
   - Derived metrics (`Passes completed`, `Possession %`, `Possession won`) render as
     **disabled** controls.
   - No invented player name is ever rendered: a player with an unknown jersey shows
     Veo's blank-number convention, not a fabricated name. Assert that the strings
     "Eric Jordi", "Diego Morales" and "Julian Vance" appear nowhere in the rendered
     output for any fixture you build.
   - The Analytics drawer renders its **honest empty state** — not a blank panel —
     when the analytics prop is `null`, which is what an ML-analysed match produces.
   - Stat labels are singular (`Goal`, not `Goals`).
3. **Build your own fixtures.** Do not import `benchmarks/raw/veo_events_447.csv` or
   any artifact under `backend/.local/`. That file is the scoreboard this project is
   scored against; loading it into a test as sample data is exactly the confusion the
   spec forbids. Hand-write small literal fixtures in the test files.
4. Tests must pass with **no network access** and must not require the backend to be
   running. Mock the API module where a component fetches.

### A note on what a good test is here

Asserting that a component renders *something* is close to worthless. Every test in
this package should be able to fail: it should assert the specific honest behaviour,
such that deleting the behaviour turns the test red. Where you can, prove that — write
the test, break the component locally, confirm the test fails, restore the component.
Report at least one invariant you verified this way.

### Acceptance — run it and paste the real output

```sh
cd /home/ai/workspaces/users/jordi/ai-focus-play/frontend
npm run test -- --run
npm run build
npm run lint
```

**Expected output:**
- `npm run test -- --run` reports **at least 8 passing tests, 0 failing** (or names
  precisely which component behaviour is genuinely wrong, if one is)
- `npm run build` exits 0
- `npm run lint` shows no new errors beyond the known pre-existing
  `set-state-in-effect` warning at `App.tsx:86`

### Report

Return JSON only:
```json
{"package":"P7-frontend-tests","status":"complete|partial|blocked",
 "files_changed":["..."],"test_count":0,
 "acceptance_command":"...","acceptance_output":"<real, pasted>",
 "invariant_proved_by_breaking":"<which one, and what the failure looked like>",
 "component_bugs_found":["..."],"deviations":["..."],"not_done":["..."]}
```
