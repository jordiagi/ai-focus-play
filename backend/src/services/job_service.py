from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.app.config import Settings
from src.app.logging import log_event
from src.domain.models.pipeline import PipelineJob
from src.storage.db import Database
from src.storage.job_repository import JobRepository


class JobService:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        *,
        recover_running: bool = True,
    ) -> None:
        self.database = database
        self.settings = settings
        self._db_path = database.path.expanduser().resolve()
        self._data_dir = settings.data_dir.expanduser().resolve()
        self._video_root = settings.video_root.expanduser().resolve()
        self.repository = JobRepository(database)
        self._processes: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        if recover_running:
            self.recover_interrupted()

    def enqueue(
        self,
        project_id: str,
        stage: str,
        params: dict[str, Any] | None = None,
    ) -> PipelineJob:
        job = PipelineJob(
            job_id=str(uuid4()),
            project_id=project_id,
            stage=stage,
            params_json=json.dumps(params or {}),
        )
        self.repository.create(job)
        log_event("job_queued", job_id=job.job_id, project_id=project_id, stage=stage)
        return job

    def enqueue_chain(
        self, project_id: str, stages: list[str]
    ) -> list[PipelineJob]:
        return [self.enqueue(project_id, stage) for stage in stages]

    def claim_next(self) -> PipelineJob | None:
        job = self.repository.claim_next()
        if job:
            log_event(
                "job_started", job_id=job.job_id, project_id=job.project_id, stage=job.stage
            )
        return job

    def start_next(self) -> PipelineJob | None:
        with self._lock:
            job = self.claim_next()
            if job is None:
                return None
            process = self._spawn(job)
            self._processes[job.job_id] = process
            threading.Thread(
                target=self._watch,
                args=(job.job_id, process),
                daemon=True,
                name=f"job-{job.job_id}",
            ).start()
            return job

    def cancel(self, job_id: str) -> PipelineJob:
        job = self.repository.cancel(job_id)
        process = self._processes.get(job_id)
        if process and process.poll() is None:
            process.terminate()
        log_event("job_cancelled", job_id=job_id, stage=job.stage)
        return self.repository.get(job_id)

    def recover_interrupted(self) -> list[PipelineJob]:
        jobs = self.repository.requeue_running()
        for job in jobs:
            log_event(
                "job_requeued_from_checkpoint",
                job_id=job.job_id,
                stage=job.stage,
                checkpoint=_checkpoint_summary(job.checkpoint),
            )
        return jobs

    def process_for(self, job_id: str) -> subprocess.Popen | None:
        return self._processes.get(job_id)

    def _spawn(self, job: PipelineJob) -> subprocess.Popen:
        env = {
            **os.environ,
            "AI_FOCUS_DB_PATH": str(self._db_path),
            "AI_FOCUS_DATA_DIR": str(self._data_dir),
            "AI_FOCUS_VIDEO_ROOT": str(self._video_root),
            "AI_FOCUS_PARENT_PID": str(os.getpid()),
        }
        return subprocess.Popen(
            [sys.executable, "-m", "src.workers.run_stage", "--job-id", job.job_id],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
        )

    def _watch(self, job_id: str, process: subprocess.Popen) -> None:
        return_code = process.wait()
        try:
            try:
                current = self.repository.get(job_id)
            except KeyError:
                log_event("job_removed_before_worker_exit", job_id=job_id)
            else:
                if return_code != 0 and current.status == "running":
                    self.repository.mark_failed(
                        job_id,
                        "Something went wrong while watching the match. Your video is fine — "
                        "tap Retry to pick up where we left off.",
                    )
                    log_event("job_failed", job_id=job_id, return_code=return_code)
        finally:
            self._processes.pop(job_id, None)
        self.start_next()


def _checkpoint_summary(checkpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        "keys": sorted(checkpoint),
        "item_counts": {
            key: len(value)
            for key, value in checkpoint.items()
            if isinstance(value, (dict, list))
        },
    }
