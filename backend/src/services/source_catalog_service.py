from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from src.app.errors import AppError
from src.domain.models.source import SourceCatalogItem

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi"}


class SourceCatalogService:
    def __init__(self, video_root: Path) -> None:
        self.video_root = video_root

    def list_local_videos(self) -> list[SourceCatalogItem]:
        root = self._root()
        if not root.exists():
            return []
        files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)
        names = Counter(path.name for path in files)
        return [self._catalog_item(path, names[path.name] > 1) for path in files]

    def resolve_relative_video(self, source_reference: str) -> Path:
        candidate = Path(source_reference).expanduser()
        if candidate.is_absolute():
            raise AppError("Local video paths must be relative and stay under the video folder", status_code=400)

        root = self._root()
        root_name = self.video_root.name
        if candidate.parts and candidate.parts[0] == root_name:
            resolved = (root.parent / candidate).resolve()
        else:
            resolved = (root / candidate).resolve()

        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise AppError("Local video paths must stay under the video folder", status_code=400) from exc
        if not resolved.exists():
            raise AppError("Local video was not found under the video folder", status_code=400)
        if resolved.suffix.lower() not in VIDEO_EXTENSIONS:
            raise AppError("Local source must be a supported video file", status_code=400)
        return resolved

    def relative_path_for(self, path: Path) -> str:
        return path.resolve().relative_to(self._root()).as_posix()

    def _root(self) -> Path:
        if self.video_root.is_absolute():
            return self.video_root.resolve()
        for base in (Path.cwd(), *Path.cwd().parents):
            candidate = (base / self.video_root).resolve()
            if (base / ".specify").exists() and candidate.exists():
                return candidate
        for base in Path(__file__).resolve().parents:
            candidate = (base / self.video_root).resolve()
            if (base / ".specify").exists() and candidate.exists():
                return candidate
        return (Path.cwd() / self.video_root).resolve()

    def _catalog_item(self, path: Path, duplicate_name: bool) -> SourceCatalogItem:
        stat = path.stat()
        relative_path = self.relative_path_for(path)
        display_name = path.stem.replace("_", " ").replace("-", " ").strip() or path.name
        if duplicate_name:
            display_name = f"{display_name} ({path.parent.name})"
        size_mb = stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
        return SourceCatalogItem(
            catalog_id=str(uuid5(NAMESPACE_URL, relative_path)),
            display_name=display_name,
            relative_path=relative_path,
            file_size_bytes=stat.st_size,
            last_modified_at=modified,
            details=f"{relative_path} · {size_mb:.1f} MB",
        )
