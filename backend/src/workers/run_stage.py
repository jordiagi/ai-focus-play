from __future__ import annotations

import argparse
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from src.app.config import get_settings
from src.app.logging import configure_logging, log_event
from src.storage.db import Database
from src.storage.job_repository import JobRepository


Stage = Callable[["StageContext", dict[str, Any]], None]


@dataclass
class StageContext:
    job_id: str
    repository: JobRepository
    parent_pid: int | None = None
    _cancelled: bool = field(default=False, init=False)
    _interrupted: bool = field(default=False, init=False)

    @property
    def interrupted(self) -> bool:
        parent_gone = self.parent_pid is not None and os.getppid() != self.parent_pid
        return self._interrupted or parent_gone

    @property
    def cancelled(self) -> bool:
        return self._cancelled or self.interrupted

    def request_cancel(self) -> None:
        self._cancelled = True

    def request_resume(self) -> None:
        self._interrupted = True

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None:
        self.repository.update_progress(
            self.job_id,
            progress_pct=progress_pct,
            progress_message=message,
            checkpoint=checkpoint,
        )
        log_event(
            "job_checkpoint",
            job_id=self.job_id,
            progress_pct=progress_pct,
            checkpoint=_checkpoint_summary(checkpoint),
        )


def sleep_demo(context: StageContext, params: dict[str, Any]) -> None:
    duration_s = max(0.01, float(params.get("duration_s", 1.0)))
    steps = max(1, int(params.get("steps", 10)))
    completed = int(context.repository.get(context.job_id).checkpoint.get("completed_steps", 0))
    for step in range(completed + 1, steps + 1):
        if context.cancelled:
            return
        time.sleep(duration_s / steps)
        context.update(
            100.0 * step / steps,
            f"Demonstrating background work — {step} of {steps} steps",
            {"completed_steps": step},
        )


STAGE_REGISTRY: dict[str, Stage] = {"sleep_demo": sleep_demo}


def _checkpoint_summary(checkpoint: dict | None) -> dict[str, Any] | None:
    if checkpoint is None:
        return None
    return {
        "keys": sorted(checkpoint),
        "item_counts": {
            key: len(value)
            for key, value in checkpoint.items()
            if isinstance(value, (dict, list))
        },
    }


def _load_builtin_stages() -> None:
    from src.services.pipeline.assemble_candidates_stage import run_assemble_candidates_stage
    from src.services.pipeline.detect_track_stage import run_detect_track_stage
    from src.services.pipeline.embed_cluster_stage import run_embed_cluster_stage
    from src.services.pipeline.export_stage import run_export_stage
    from src.services.pipeline.jersey_ocr_stage import run_jersey_ocr_stage
    from src.services.pipeline.proxy_stage import run_proxy_stage
    from src.services.pipeline.sam2_refine_stage import run_sam2_refine_stage

    STAGE_REGISTRY["proxy"] = run_proxy_stage
    STAGE_REGISTRY["detect_track"] = run_detect_track_stage
    STAGE_REGISTRY["embed_cluster"] = run_embed_cluster_stage
    STAGE_REGISTRY["jersey_ocr"] = run_jersey_ocr_stage
    STAGE_REGISTRY["assemble_candidates"] = run_assemble_candidates_stage
    STAGE_REGISTRY["sam2_refine"] = run_sam2_refine_stage
    STAGE_REGISTRY["export"] = run_export_stage


_load_builtin_stages()


def register_stage(name: str, stage: Stage) -> None:
    STAGE_REGISTRY[name] = stage


def run(job_id: str) -> int:
    settings = get_settings()
    repository = JobRepository(Database(settings.db_path))
    try:
        job = repository.get(job_id)
    except KeyError:
        return 2
    stage = STAGE_REGISTRY.get(job.stage)
    if stage is None:
        repository.mark_failed(job_id, f"The {job.stage} step is not available. Your data is safe — tap Retry after updating the app.")
        return 2
    parent_pid_value = os.getenv("AI_FOCUS_PARENT_PID")
    context = StageContext(
        job_id,
        repository,
        parent_pid=int(parent_pid_value) if parent_pid_value else None,
    )

    def handle_signal(signum: int, *_: object) -> None:
        if signum == signal.SIGINT and context.parent_pid is not None:
            context.request_resume()
        else:
            context.request_cancel()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    try:
        stage(context, job.params)
        if context.interrupted:
            log_event(
                "job_interrupted_for_resume",
                job_id=job_id,
                stage=job.stage,
                checkpoint=_checkpoint_summary(repository.get(job_id).checkpoint),
            )
            return 3
        if context.cancelled:
            repository.cancel(job_id)
            return 0
        repository.mark_succeeded(job_id)
        log_event("job_finished", job_id=job_id, stage=job.stage)
        return 0
    except BaseException as exc:
        repository.mark_failed(
            job_id,
            "Something went wrong while watching the match. Your video is fine — "
            "tap Retry to pick up where we left off.",
        )
        log_event("job_failed", job_id=job_id, stage=job.stage, error=repr(exc))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    configure_logging()
    return run(args.job_id)


if __name__ == "__main__":
    raise SystemExit(main())
