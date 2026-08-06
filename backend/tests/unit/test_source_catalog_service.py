from pathlib import Path

import pytest

from src.app.errors import AppError
from src.services.source_catalog_service import SourceCatalogService


def test_source_catalog_lists_local_videos_with_display_names(tmp_path: Path) -> None:
    video_root = tmp_path / "video"
    video_root.mkdir()
    (video_root / "Cup Final.mp4").write_text("video")

    items = SourceCatalogService(video_root).list_local_videos()

    assert len(items) == 1
    assert items[0].display_name == "Cup Final"
    assert items[0].relative_path == "Cup Final.mp4"
    assert "Cup Final.mp4" in items[0].details


def test_source_catalog_disambiguates_duplicate_display_names(tmp_path: Path) -> None:
    video_root = tmp_path / "video"
    (video_root / "field-a").mkdir(parents=True)
    (video_root / "field-b").mkdir()
    (video_root / "field-a" / "match.mp4").write_text("video")
    (video_root / "field-b" / "match.mp4").write_text("video")

    names = [item.display_name for item in SourceCatalogService(video_root).list_local_videos()]

    assert "match (field-a)" in names
    assert "match (field-b)" in names


def test_source_catalog_rejects_absolute_and_outside_paths(tmp_path: Path) -> None:
    video_root = tmp_path / "video"
    video_root.mkdir()
    service = SourceCatalogService(video_root)

    with pytest.raises(AppError):
      service.resolve_relative_video(str(tmp_path / "outside.mp4"))

    with pytest.raises(AppError):
      service.resolve_relative_video("../outside.mp4")


def test_source_catalog_accepts_relative_path_under_video_root(tmp_path: Path) -> None:
    video_root = tmp_path / "video"
    video_root.mkdir()
    (video_root / "match.mp4").write_text("video")

    resolved = SourceCatalogService(video_root).resolve_relative_video("match.mp4")

    assert resolved == video_root / "match.mp4"


def test_source_catalog_finds_project_video_root_from_backend_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".specify").mkdir()
    (tmp_path / "video").mkdir()
    (tmp_path / "video" / "match.mp4").write_text("video")
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    monkeypatch.chdir(backend_dir)

    items = SourceCatalogService(Path("video")).list_local_videos()
    resolved = SourceCatalogService(Path("video")).resolve_relative_video("video/match.mp4")

    assert items[0].relative_path == "match.mp4"
    assert resolved == tmp_path / "video" / "match.mp4"
