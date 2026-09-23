## Package: P5 — UI parity axis A, and the blank-panel defect

Owner:        agy / gemini-3.8-flash-high
Files OWNED:  everything under `frontend/src/`, plus `frontend/package.json` only if you must add a dependency (prefer not to — see below)
Files READ:   `PLAN.md:121-153` (the real-Veo behaviour list), `specs/complete-veo-parity/spec.md` (§5 binds you), `backend/src/domain/models/match.py`, `backend/src/services/pipeline/ml_ingest.py`
Out of scope: **every backend file, every spec, `STATE.md`, `PLAN.md`.** Other agents are editing the backend concurrently. Do not run backend commands other than to read source.

### Baseline, measured 2026-09-23

`npm run build` is clean (1891 modules). 16 files, 3,758 lines. **Zero frontend
tests and no test framework installed.** Hash routing, singular stat labels, disabled
derived metrics, jersey-only naming and the `PitchRadar` ball-not-detected state are
all already implemented and correct — **do not touch them, do not "improve" them.**

### The rule that outranks everything in this package

> When a capability is not implemented, **show that it is not implemented.** An empty
> state, a dimmed `—`, or a "not detected" badge is a correct and useful answer. A
> plausible fabricated number is not.

A control that pretends to work is a fabrication in UI form. A slider that filters
nothing, a chart drawn from an empty array as if it were flat data, a "0" where the
truth is "never measured" — all three fail this package.

### The six items

**1. The blank Analytics panel — the real defect.**
`SidebarTabs.tsx:295` guards the whole Analytics Studio body on `analytics &&`.
For an ML-analysed match `ml_ingest.py` drops the analytics row, the API returns 404,
`api.ts:117-122` turns that into `null`, and the drawer body renders **nothing at
all** — no message, no reason. It reads as a broken app, not as an honest absence.

Render an explicit empty state when `analytics` is `null`: say that this match was
analysed by the ML pipeline, that the stats table is produced by a different
pipeline, and that mixing the two would misattribute one's numbers to the other.
Keep it short and plain. This is the highest-value item in the package.

**2. Accordions, with Veo's six sections and Veo's labels.**
Veo's analytics drawer is six collapsible accordions:
`Stats`, `Shot map`, `Pass location`, `Possession location`, `Pass strings`, `Heat map`.
Today there are four always-open cards, two of them mislabelled: the stats table is
headed "Match Comparison" and the pass-location panel is headed "Thirds Breakdown".

Implement real collapse/expand (correct `aria-expanded`, keyboard-operable), rename
the two mislabelled sections to Veo's names, and add the two missing sections.

**3. `Possession location` — new section.**
`AnalyticsData.possession_locations` exists in the type (`types/index.ts:112-115`) and
is populated by the heuristic engine. Render it exactly the way `Pass location`
renders its thirds. When the object is empty, render the section's unavailable state
(item 6) — **do not render three zeros.**

**4. `Heat map` — new section, honestly empty.**
`heatmaps` is declared in the type and is **never populated by anything**. There is no
player position data in metres; `STATE.md` records five measured calibration failures.

So: add the section, and have it state that it is unavailable because no metric pitch
coordinates exist. **Do not add the dual-thumb second-range slider.** `PLAN.md` notes
Veo has one, but a slider that filters an empty dataset is theatre — it invites the
user to believe data is being filtered. Add the control only if you also have data for
it to filter, which you do not. Note this decision in your report's `deviations`.

**5. The per-event "video add" action.**
Veo's event rows carry two actions: seek (implemented, `SidebarTabs.tsx:285`) and
"video add", which promotes the event to a clip. **No backend endpoint for clip
creation exists.** Render the button, `disabled`, with a `title` naming why — the same
pattern this codebase already uses for the derived stat rows
(`SidebarTabs.tsx:352-354`). Do not wire it to anything. Do not fake an optimistic
local insert.

**6. A shared unavailable-state component.**
Items 1, 3 and 4 all need "this is not available, and here is the measured reason".
Write it once and reuse it. It takes a reason string and renders it visibly — not as
a tooltip only, and never as a zero.

Additionally, if you are confident it is a one-line change: `Header.tsx:22-30` builds
a share URL with `?match=<id>` but **drops the hash route**, so sharing while a drawer
is open loses the panel. Include `window.location.hash` in the shared URL. If this
turns out to be more than a few lines, skip it and say so in `not_done`.

### Constraints

- **Add no dependency** unless genuinely unavoidable. React 19, Tailwind 4 and
  lucide-react are present; accordions and disabled buttons need nothing more.
- The backend contract does not change in this package. Read the types, do not
  invent new API fields, and do not assume a field exists because it would be
  convenient. A future package may add `provenance` and `unavailable` to
  `AnalyticsData` — **do not depend on them; they are not there yet.**
- Do not touch `PitchRadar.tsx`'s ball-not-detected logic, the jersey-only rendering
  in `PlayerMomentsBar.tsx`, or the `renderStatValue` em-dash helper. They are correct.

### Acceptance — run it and paste the real output

```sh
cd /home/ai/workspaces/users/jordi/ai-focus-play/frontend
npm run build
npm run lint
grep -c "aria-expanded" src/components/Sidebar/SidebarTabs.tsx
grep -o "Possession location\|Heat map\|Pass location\|Pass strings\|Shot map" src/components/Sidebar/SidebarTabs.tsx | sort -u
```

**Expected output:**
- `npm run build` exits 0
- `npm run lint` reports **no new** errors (one pre-existing `set-state-in-effect`
  warning at `App.tsx:86` is known and may remain — do not fix it, it is not yours)
- the `aria-expanded` count is **6 or more**
- the final grep lists **all five** of `Heat map`, `Pass location`, `Pass strings`,
  `Possession location`, `Shot map`

### Report

Return JSON only:
```json
{"package":"P5-ui","status":"complete|partial|blocked",
 "files_changed":["..."],"acceptance_command":"...","acceptance_output":"<real, pasted>",
 "items":{"1_blank_panel":"done|not done","2_accordions":"...","3_possession_location":"...",
          "4_heatmap":"...","5_video_add_disabled":"...","6_unavailable_component":"...",
          "7_share_hash":"..."},
 "deviations":["..."],"not_done":["..."]}
```
