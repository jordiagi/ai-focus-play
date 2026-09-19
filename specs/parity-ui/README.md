# parity-ui — Track 2

Close the UI/route gap with the real Veo match page. **Frontend-mostly, no GPU, and
file-disjoint from the GPU pipeline work in Track 1.**

Ground truth for every label and behaviour in these packages is the real Veo app,
captured in `PLAN.md` ("What parity actually means") and in the a11y dumps under
`~/.gemini/antigravity/brain/ec49a13a-*/`. **Where those dumps disagree with `PLAN.md`,
prefer `PLAN.md`** — some snapshots in that directory are of OUR clone, not Veo.

## The rule that governs every package

> When a capability is not implemented, **show that it is not implemented.** An empty
> state, a dimmed `—`, or a "not detected" badge is a correct and useful answer. A
> plausible fabricated number is not.

Veo itself follows this: it renders `Player ` with a **blank** jersey number for players
it could not resolve, rather than inventing one. Match that behaviour, don't improve on it.

## Baseline before any work

`bash scripts/local/verify.sh all` → `pass=9 fail=0 skip=0`; `pytest` → 35 passed;
`npm run build` clean; `npm run lint` 1 pre-existing warning (`App.tsx:86`).

## Reporting contract

Return JSON, nothing else:

```json
{"status":"complete|partial|blocked",
 "files_changed":["..."],
 "acceptance_command":"...",
 "acceptance_output":"<pasted REAL output, not a summary>",
 "deviations":["..."],
 "not_done":["..."]}
```

`complete` with an unrun acceptance command is a false report. `partial` reported
accurately is worth more than `complete` reported fast.
