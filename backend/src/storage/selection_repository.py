from __future__ import annotations

from src.domain.models.selection import AppearanceSegment, UserClick
from src.storage.db import Database


class SelectionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save_click(self, click: UserClick) -> UserClick:
        values = click.to_dict()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_clicks(
                    click_id, project_id, ts, x_norm, y_norm, label, status,
                    resolved_tracklet_id, sam2_job_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(click_id) DO UPDATE SET
                    status = excluded.status,
                    resolved_tracklet_id = excluded.resolved_tracklet_id,
                    sam2_job_id = excluded.sam2_job_id
                """,
                tuple(values.values()),
            )
        return click

    def list_clicks(self, project_id: str, status: str | None = None) -> list[UserClick]:
        sql = "SELECT * FROM user_clicks WHERE project_id = ?"
        params: list[object] = [project_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at"
        with self.database.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [UserClick(**dict(row)) for row in rows]

    def get_click(self, click_id: str) -> UserClick:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_clicks WHERE click_id = ?", (click_id,)
            ).fetchone()
        if row is None:
            raise KeyError(click_id)
        return UserClick(**dict(row))

    def update_click_status(
        self,
        click_id: str,
        status: str,
        *,
        resolved_tracklet_id: str | None = None,
        sam2_job_id: str | None = None,
    ) -> UserClick:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE user_clicks
                SET status = ?, resolved_tracklet_id = COALESCE(?, resolved_tracklet_id),
                    sam2_job_id = COALESCE(?, sam2_job_id)
                WHERE click_id = ?
                """,
                (status, resolved_tracklet_id, sam2_job_id, click_id),
            )
            row = connection.execute(
                "SELECT * FROM user_clicks WHERE click_id = ?", (click_id,)
            ).fetchone()
        if row is None:
            raise KeyError(click_id)
        return UserClick(**dict(row))

    def replace_segments(
        self, project_id: str, segments: list[AppearanceSegment]
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM appearance_segments WHERE project_id = ?", (project_id,)
            )
            connection.executemany(
                "INSERT INTO appearance_segments VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.segment_id,
                        item.project_id,
                        item.cluster_id,
                        item.start_ts,
                        item.end_ts,
                        item.score,
                        int(item.included),
                    )
                    for item in segments
                ],
            )

    def list_segments(self, project_id: str) -> list[AppearanceSegment]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM appearance_segments WHERE project_id = ? ORDER BY start_ts",
                (project_id,),
            ).fetchall()
        return [
            AppearanceSegment(**{**dict(row), "included": bool(row["included"])})
            for row in rows
        ]
