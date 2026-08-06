from __future__ import annotations

from src.domain.models.video import SourceVideo
from src.storage.db import Database


class SourceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(self, source: SourceVideo) -> SourceVideo:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO source_videos(
                    source_id, project_id, file_path, original_filename,
                    content_hash, duration_s, fps, width, height, codec,
                    proxy_path, proxy_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    file_path = excluded.file_path,
                    original_filename = excluded.original_filename,
                    content_hash = excluded.content_hash,
                    duration_s = excluded.duration_s,
                    fps = excluded.fps,
                    width = excluded.width,
                    height = excluded.height,
                    codec = excluded.codec,
                    proxy_path = excluded.proxy_path,
                    proxy_status = excluded.proxy_status
                """,
                (
                    source.source_id,
                    source.project_id,
                    source.file_path,
                    source.original_filename,
                    source.content_hash,
                    source.duration_s,
                    source.fps,
                    source.width,
                    source.height,
                    source.codec,
                    source.proxy_path,
                    source.proxy_status,
                    source.created_at,
                ),
            )
        return source

    insert = save

    def get(self, source_id: str) -> SourceVideo:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_videos WHERE source_id = ?", (source_id,)
            ).fetchone()
        if row is None:
            raise KeyError(source_id)
        return SourceVideo.from_dict(dict(row))

    def get_for_project(self, project_id: str) -> SourceVideo | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_videos WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return SourceVideo.from_dict(dict(row)) if row else None

    def update_proxy(
        self,
        source_id: str,
        *,
        proxy_path: str | None,
        proxy_status: str,
    ) -> SourceVideo:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "UPDATE source_videos SET proxy_path = ?, proxy_status = ? WHERE source_id = ?",
                (proxy_path, proxy_status, source_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(source_id)
        return self.get(source_id)
