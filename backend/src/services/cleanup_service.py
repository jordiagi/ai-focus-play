from __future__ import annotations

import shutil
from pathlib import Path

from src.app.config import Settings


class CleanupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def cleanup_project_artifacts(self, project_id: str) -> bool:
        target = self.settings.data_dir / project_id
        if target.exists():
            shutil.rmtree(target)
        return True

    def cleanup_project(self, project_id: str) -> bool:
        return self.cleanup_project_artifacts(project_id)

    def cleanup_evidence_artifacts(self, project_id: str) -> bool:
        target = self.settings.data_dir / project_id / "evidence"
        if target.exists():
            shutil.rmtree(target)
        return True

    def cleanup_path(self, path: Path) -> bool:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        return True
