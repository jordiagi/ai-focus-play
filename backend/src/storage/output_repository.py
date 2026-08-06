from __future__ import annotations

import json

from src.domain.models.output import ReelOutput
from src.storage.db import Database


class OutputRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(self, output: ReelOutput) -> ReelOutput:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO reel_outputs(
                    output_id, project_id, profile, overlay_mode, status, file_path,
                    duration_s, segment_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(output_id) DO UPDATE SET
                    status = excluded.status,
                    file_path = excluded.file_path,
                    duration_s = excluded.duration_s,
                    segment_ids_json = excluded.segment_ids_json
                """,
                (
                    output.output_id,
                    output.project_id,
                    output.profile,
                    output.overlay_mode,
                    output.status,
                    output.file_path,
                    output.duration_s,
                    json.dumps(output.segment_ids),
                    output.created_at,
                ),
            )
        return output

    def get(self, output_id: str) -> ReelOutput:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM reel_outputs WHERE output_id = ?", (output_id,)
            ).fetchone()
        if row is None:
            raise KeyError(output_id)
        return self._from_row(row)

    def list_for_project(self, project_id: str) -> list[ReelOutput]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reel_outputs WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: object) -> ReelOutput:
        payload = dict(row)
        payload["segment_ids"] = json.loads(payload.pop("segment_ids_json"))
        return ReelOutput(**payload)
