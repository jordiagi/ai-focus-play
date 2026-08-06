from pathlib import Path

import pytest

from src.domain.models.project import AnalysisProject
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository


def test_project_repository_crud_and_status_fields(tmp_path: Path) -> None:
    repo = ProjectRepository(Database(tmp_path / "app.db"))
    project = AnalysisProject(project_id="p1", name="Sunday match")

    repo.create(project)
    repo.set_jersey_hint("p1", "8")
    repo.set_source("p1", "source-1")
    repo.update_status("p1", "analyzing")

    stored = repo.get("p1")
    assert stored.name == "Sunday match"
    assert stored.jersey_hint == "8"
    assert stored.source_id == "source-1"
    assert stored.status == "analyzing"
    assert [item.project_id for item in repo.list()] == ["p1"]

    repo.delete("p1")
    with pytest.raises(KeyError):
        repo.get("p1")
