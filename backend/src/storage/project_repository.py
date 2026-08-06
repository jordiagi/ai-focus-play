from __future__ import annotations

from src.domain.models.project import AnalysisProject, utcnow
from src.storage.db import Database


class ProjectRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save_project(self, project: AnalysisProject) -> AnalysisProject:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO projects(
                    project_id, name, status, source_id, jersey_hint,
                    target_cluster_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    name = excluded.name,
                    status = excluded.status,
                    source_id = excluded.source_id,
                    jersey_hint = excluded.jersey_hint,
                    target_cluster_id = excluded.target_cluster_id,
                    updated_at = excluded.updated_at
                """,
                (
                    project.project_id,
                    project.name,
                    project.status,
                    project.source_id,
                    project.jersey_hint,
                    project.target_cluster_id,
                    project.created_at,
                    project.updated_at,
                ),
            )
        return project

    create = save_project

    def get_project(self, project_id: str) -> AnalysisProject:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        if row is None:
            raise KeyError(project_id)
        return AnalysisProject.from_dict(dict(row))

    get = get_project

    def list_projects(self) -> list[AnalysisProject]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [AnalysisProject.from_dict(dict(row)) for row in rows]

    list = list_projects

    def update_status(self, project_id: str, status: str) -> AnalysisProject:
        return self._update(project_id, status=status)

    def set_source(self, project_id: str, source_id: str | None) -> AnalysisProject:
        return self._update(project_id, source_id=source_id)

    def set_jersey_hint(
        self, project_id: str, jersey_hint: str | None
    ) -> AnalysisProject:
        return self._update(project_id, jersey_hint=jersey_hint)

    def set_target_cluster(
        self, project_id: str, cluster_id: str | None
    ) -> AnalysisProject:
        status = "target_confirmed" if cluster_id else "awaiting_target_selection"
        return self._update(
            project_id, target_cluster_id=cluster_id, status=status
        )

    def delete(self, project_id: str) -> None:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM projects WHERE project_id = ?", (project_id,)
            )
        if cursor.rowcount == 0:
            raise KeyError(project_id)

    def _update(self, project_id: str, **changes: object) -> AnalysisProject:
        allowed = {"name", "status", "source_id", "jersey_hint", "target_cluster_id"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported project fields: {sorted(unknown)}")
        if not changes:
            return self.get_project(project_id)
        changes["updated_at"] = utcnow()
        assignments = ", ".join(f"{name} = ?" for name in changes)
        values = [*changes.values(), project_id]
        with self.database.connect() as connection:
            cursor = connection.execute(
                f"UPDATE projects SET {assignments} WHERE project_id = ?", values
            )
        if cursor.rowcount == 0:
            raise KeyError(project_id)
        return self.get_project(project_id)
