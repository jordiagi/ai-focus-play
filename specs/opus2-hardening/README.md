# opus2-hardening

Close the eight confirmed defects. Each package is **file-disjoint**: no two
packages may edit the same file. Acceptance is **executable** — a command and its
expected output, never "tests pass".

## The rule that governs every package

> When a capability is not implemented, **show that it is not implemented.** An empty
> state, a dimmed `—`, or a "not detected" badge is a correct and useful answer. A
> plausible fabricated number is not.

A fix that makes a number *self-consistent by inventing it* is worse than the bug.

## Baseline before any work (measured 2026-09-18)

`bash scripts/local/verify.sh all` → `pass=0 fail=6 skip=2`.

## Reporting contract

Return JSON, nothing else:

```json
{"status":"complete|partial|blocked",
 "files_changed":["..."],
 "acceptance_command":"...",
 "acceptance_output":"<pasted real output, not a summary>",
 "deviations":["..."],
 "not_done":["..."]}
```

`status: complete` with an unrun acceptance command is a false report and poisons
everything downstream. `partial` reported accurately is worth more than `complete`
reported fast.
