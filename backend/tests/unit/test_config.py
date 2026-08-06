from src.app.config import get_settings


def test_settings_creates_paths() -> None:
    settings = get_settings()
    assert settings.data_dir.exists()


def test_settings_reads_pipeline_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(tmp_path / "metadata" / "app.db"))
    monkeypatch.setenv("ANALYSIS_FPS", "4.0")

    settings = get_settings()

    assert settings.data_dir == tmp_path / "data"
    assert settings.db_path == tmp_path / "metadata" / "app.db"
    assert settings.analysis_fps == 4.0
    assert settings.frames_cache_max == 500
    assert settings.data_dir.exists()
    assert settings.db_path.parent.exists()
