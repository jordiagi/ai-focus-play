# scripts/

Recurrent steps, so nobody re-derives them. **Read this table, not the scripts.**

Config lives in **`config.env` only** (`config.local.env` overrides it, gitignored).
No script hardcodes a host or path.

## Contract

Every script prints **at most 3 lines**, the last being `RESULT: k=v k=v`.
**Exit codes are the API** — branch on the code, not the prose:

| Code | Meaning |
| :-- | :-- |
| `0` | done |
| `10` | cached / no-op (not an error) |
| `20` | remote unreachable |
| `30` | verification failed |
| `1` | usage or unexpected error |

## Remote (gpu-box)

| Command | Does | Typical |
| :-- | :-- | :-- |
| `bash scripts/remote/doctor.sh` | One JSON line: GPUs + free VRAM, tmpfs, venv/torch, video sha, last job. **Run this first, always.** | ~2 s |
| `bash scripts/remote/provision.sh` | Bare container → working GPU env. Idempotent | cold 5-8 min, warm ~90 s |
| `bash scripts/remote/push-video.sh` | Ship the match video. Resumable, sha-verified, atomic | ~21 min cold, instant cached |
| `bash scripts/remote/push-code.sh [--dirty]` | Ship `backend/src`, `benchmarks`, `scripts` | ~3 s |
| `bash scripts/remote/run-job.sh [--t0 S] [--t1 S]` | Launch an analysis run; returns `job_id` | returns immediately |
| `bash scripts/remote/job-status.sh [job_id] [--tail N]` | One JSON line of progress | ~2 s |
| `bash scripts/remote/pull-artifacts.sh [job_id]` | Bring parquet/JSON home. **Refuses >200 MB** | ~30 s |
| `bash scripts/remote/restore.sh` | **After a container restart wiped tmpfs**: provision + code + video, one command | ~90 s + video |

## Local

| Command | Does |
| :-- | :-- |
| `bash scripts/local/dev.sh up\|down\|status` | uvicorn + vite with pidfiles |
| `bash scripts/local/verify.sh [d1..d8\|all]` | Every adversarial defect probe, PASS/FAIL table |
| `bash scripts/local/reseed.sh --force` | Reset + reseed `veo.db` (needed: `_seed_if_empty` returns early when any match exists) |
| `python scripts/local/ingest-artifacts.py --job ID --match ID` | parquet → radar frames + events |
| `python scripts/local/score-benchmark.py --job ID` | Score against `benchmarks/veo_reference.json` |

## Things that will bite you on gpu-box

- **`/workspace` is a 64 GB tmpfs. A container restart wipes it — including the
  video.** `restore.sh` is the recovery. `/opt` is the overlay and keeps the caches.
- **`/tmp` is on the overlay and persists.** `TMPDIR` is pointed into `/workspace`;
  don't undo that or temp files leak onto the shared box.
- **Never call bare `pip`** — it is bound to Python 3.11 while `python3` is 3.10, and
  `python3 -m pip` does not exist. Use the venv at `/workspace/aifp/.venv`.
- **torch must be a cu12x wheel.** Driver 575.57.08 is CUDA 12.9; cu13 wheels fail at
  `torch.cuda.init()`.
- **The GPUs are shared.** Ollama holds `mistral` (43 GB) + `qwen3.8` (51 GB) resident,
  and `qwen3.8` is what `opencode` talks to. Budget ≤40 GB/GPU and never OOM the box.
  Don't run opencode-heavy delegation during a saturating GPU pass.
- **The link is 2.8 MB/s, DERP-relayed.** Let the box download its own packages; only
  the video and a tiny code tarball should cross it.
