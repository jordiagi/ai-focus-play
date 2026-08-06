from pathlib import Path

from src.app.config import get_settings
from src.services.cleanup_service import CleanupService


def test_cleanup_path(tmp_path: Path) -> None:
    target = tmp_path / "temp.txt"
    target.write_text("x")
    service = CleanupService(get_settings())
    assert service.cleanup_path(target)
    assert not target.exists()

