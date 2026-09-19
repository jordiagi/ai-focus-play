# WP-2 — Honest analysis labels and a streaming highlight export (defects 4, 6)

## Problems (reproduced)

1. **The synthetic fallback is labelled as real analysis.** `matches.py:100-105`
   sets `analysis_mode="heuristic"`, `analysis_confidence="medium"`
   **unconditionally** after every run. But `cv_engine.process_video` silently falls
   back to `_generate_fallback_tracking` — pure sine-wave players — when the video
   cannot be decoded (`cv_engine.py:110`) or fewer than 6 frames were sampled
   (`cv_engine.py:267-268`). Fabricated data therefore ships labelled
   `heuristic`/`medium`. The allowed vocabulary is `demo|heuristic|ml` and
   `low|medium|high`; the fallback is `demo`/`low`.
2. **The highlight zip substitutes the whole match video for missing clips**
   (`matches.py:310-319`) and buffers the entire archive in RAM via `io.BytesIO`
   (`matches.py:309`). The user downloads files named as highlights that are not
   highlights, and with the real 6172 s match seeded this builds a multi-GB zip in
   memory.

## Files OWNED
- `backend/src/api/routes/matches.py`
- `backend/tests/unit/test_export_zip.py`  (new)

## Files READ (do not edit)
`backend/src/services/pipeline/cv_engine.py`, `backend/src/storage/repository.py`,
`backend/src/app/main.py`

## Contract

**Mode contract (fixed; do not renegotiate).** `process_video` keeps its exact
4-tuple return — `matches.py:78` unpacks it and WP-3 owns that file. Read the mode
the engine reports via:

```python
meta = getattr(cv_engine, "last_run_meta", {}) or {}
mode = meta.get("mode", "demo")
confidence = meta.get("confidence", "low")
```

The **safe default is `("demo","low")`**: if the engine tells us nothing, we must
claim nothing. This works whether or not WP-3 has landed yet.

- Never hardcode `analysis_mode = "heuristic"`.
- Highlight export: stream the archive (do not build it in memory), and **never
  substitute a different file for a missing clip**. A missing clip is omitted, and
  the response includes a manifest entry recording that it was unavailable.

## Acceptance (run it; paste real output)
```
bash scripts/local/verify.sh d4
backend/.venv/bin/python -m pytest backend/tests -q
```
`d4` must end `RESULT: pass=1 fail=0 skip=0`; pytest must not regress.

Write `backend/tests/unit/test_export_zip.py` proving:
- no zip member is byte-identical to `demo_match.mp4` or any full match video;
- a missing clip produces an omission plus a manifest note, not a substitution;
- the export does not hold the whole archive in memory (assert on a streaming
  response type and/or bounded peak memory);
- **both label branches**: a forced fallback run reports `demo`/`low`, and a run
  where the engine reports a real mode is **not** relabelled `demo`.

## Out of scope
Other defects. Do not add read-only guards here — WP-1 implements those as
middleware in `main.py`, and duplicating them in this file will conflict.
