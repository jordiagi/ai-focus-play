from pathlib import Path

from src.app.config import Settings
from src.services.artifact_service import ArtifactService


def test_pipeline_artifact_paths_are_project_scoped(tmp_path: Path) -> None:
    service = ArtifactService(
        Settings(data_dir=tmp_path / "data", db_path=tmp_path / "app.db")
    )

    assert service.proxy_path("p1") == tmp_path / "data" / "p1" / "proxy" / "proxy_720p.mp4"
    assert service.frames_dir("p1").is_dir()
    assert service.crops_dir("p1", "tracklet-1").is_dir()
    assert service.masks_dir("p1", "click-1").is_dir()
    assert service.exports_dir("p1").is_dir()
