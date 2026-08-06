from __future__ import annotations

import json

from src.domain.models.pipeline import JobStatus, PipelineJob
from src.domain.models.project import utcnow
from src.storage.db import Database


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, job: PipelineJob) -> PipelineJob:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO pipeline_jobs(
                    job_id, project_id, stage, status, progress_pct,
                    progress_message, checkpoint_json, params_json, error,
                    created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.project_id,
                    str(job.stage),
                    str(job.status),
                    job.progress_pct,
                    job.progress_message,
                    job.checkpoint_json,
                    job.params_json,
                    job.error,
                    job.created_at,
                    job.started_at,
                    job.finished_at,
                ),
            )
        return job

    def get(self, job_id: str) -> PipelineJob:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM pipeline_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return PipelineJob(**dict(row))

    def list_for_project(self, project_id: str) -> list[PipelineJob]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM pipeline_jobs
                WHERE project_id = ? ORDER BY created_at, rowid
                """,
                (project_id,),
            ).fetchall()
        return [PipelineJob(**dict(row)) for row in rows]

    def claim_next(self) -> PipelineJob | None:
        with self.database.transaction(immediate=True) as connection:
            running = connection.execute(
                "SELECT 1 FROM pipeline_jobs WHERE status = 'running' LIMIT 1"
            ).fetchone()
            if running:
                return None
            row = connection.execute(
                """
                SELECT job_id FROM pipeline_jobs
                WHERE status = 'queued' ORDER BY created_at, rowid LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            started_at = utcnow()
            updated = connection.execute(
                """
                UPDATE pipeline_jobs SET status = 'running', started_at = ?,
                    finished_at = NULL, error = NULL
                WHERE job_id = ? AND status = 'queued'
                """,
                (started_at, row["job_id"]),
            )
            if updated.rowcount != 1:
                return None
            claimed = connection.execute(
                "SELECT * FROM pipeline_jobs WHERE job_id = ?", (row["job_id"],)
            ).fetchone()
        return PipelineJob(**dict(claimed))

    def update_progress(
        self,
        job_id: str,
        *,
        progress_pct: float,
        progress_message: str,
        checkpoint: dict | None = None,
    ) -> PipelineJob:
        checkpoint_json = json.dumps(checkpoint) if checkpoint is not None else None
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE pipeline_jobs
                SET progress_pct = ?, progress_message = ?,
                    checkpoint_json = COALESCE(?, checkpoint_json)
                WHERE job_id = ? AND status = 'running'
                """,
                (max(0.0, min(100.0, progress_pct)), progress_message, checkpoint_json, job_id),
            )
        if cursor.rowcount == 0:
            return self.get(job_id)
        return self.get(job_id)

    def mark_succeeded(self, job_id: str) -> PipelineJob:
        return self._finish(job_id, JobStatus.SUCCEEDED, error=None, progress_pct=100.0)

    def mark_failed(self, job_id: str, error: str) -> PipelineJob:
        return self._finish(job_id, JobStatus.FAILED, error=error)

    def cancel(self, job_id: str) -> PipelineJob:
        job = self.get(job_id)
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return job
        return self._finish(job_id, JobStatus.CANCELLED, error=None)

    def requeue_running(self) -> list[PipelineJob]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT job_id FROM pipeline_jobs WHERE status = 'running'"
            ).fetchall()
            connection.execute(
                """
                UPDATE pipeline_jobs SET status = 'queued', started_at = NULL,
                    finished_at = NULL, error = NULL
                WHERE status = 'running'
                """
            )
        return [self.get(row["job_id"]) for row in rows]

    def _finish(
        self,
        job_id: str,
        status: str,
        *,
        error: str | None,
        progress_pct: float | None = None,
    ) -> PipelineJob:
        assignments = "status = ?, error = ?, finished_at = ?"
        values: list[object] = [str(status), error, utcnow()]
        if progress_pct is not None:
            assignments += ", progress_pct = ?"
            values.append(progress_pct)
        values.append(job_id)
        with self.database.connect() as connection:
            cursor = connection.execute(
                f"UPDATE pipeline_jobs SET {assignments} WHERE job_id = ?", values
            )
        if cursor.rowcount == 0:
            raise KeyError(job_id)
        return self.get(job_id)
