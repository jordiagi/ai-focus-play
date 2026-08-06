# Frontend

React + TypeScript (Vite) UI for the three-step guided workflow: **Add video → Find
your player → Build the reel**. All user-facing copy is plain language — no model names,
raw stage ids, or bare confidence numbers.

```bash
cd frontend
npm install
npm run dev        # Vite dev server, proxies API calls to the backend
npm test           # Vitest
npx tsc --noEmit   # type-check
```

## Structure

- `src/features/projects/ProjectWizardPage.tsx` — wizard shell; derives the active step
  from project status + analysis state, restores the active project from localStorage,
  and resumes progress polling on reload.
- Step 1 `VideoSourceStep` → Step 2 `FindPlayerStep` (composes `AnalysisProgressCard`,
  `FrameClickSelector`, jersey-hint field, `IdentityEvidenceStrip`) → Step 3
  `ReelGenerationStep` (embeds `CoverageTimeline`).
- `CoverageTimeline.tsx` — segment bar, per-segment preview popover, include/exclude,
  "Not them", and the mass-removal "start over" escape hatch.
- `src/services/` — thin `apiClient` wrappers: `projects.ts` (frames, clicks, candidates,
  target, timeline), `exports.ts` (create/list/download reels), `sources.ts`.
- Shared types in `src/features/projects/guidedTypes.ts`.

The backend must be running (see `../backend/README.md`); the dev server proxies to it.
