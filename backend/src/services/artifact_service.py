from __future__ import annotations

from pathlib import Path

from src.app.config import Settings
from src.app.errors import AppError


class ArtifactService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _component(value: str, label: str) -> str:
        name = Path(value).name
        if not value or name != value or value in {".", ".."}:
            raise AppError(f"Invalid {label}", status_code=400)
        return name

    def project_dir(self, project_id: str) -> Path:
        project_id = self._component(project_id, "project id")
        path = (self.settings.data_dir / project_id).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_source_path(self, project_id: str, stored_path: str) -> Path:
        path = Path(stored_path).expanduser()
        if path.is_absolute():
            return path.resolve()
        uploaded = self.project_dir(project_id) / "source" / path.name
        if uploaded.is_file():
            return uploaded.resolve()
        return path.resolve()

    def proxy_path(self, project_id: str) -> Path:
        path = self.project_dir(project_id) / "proxy" / "proxy_720p.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def frames_dir(self, project_id: str) -> Path:
        return self._dir(project_id, "frames")

    def crops_dir(self, project_id: str, tracklet_id: str) -> Path:
        tracklet_id = self._component(tracklet_id, "tracklet id")
        path = self._dir(project_id, "crops") / tracklet_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def masks_dir(self, project_id: str, click_id: str) -> Path:
        click_id = self._component(click_id, "click id")
        path = self._dir(project_id, "masks") / click_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def exports_dir(self, project_id: str) -> Path:
        return self._dir(project_id, "exports")

    def create_export_path(self, project_id: str, output_id: str) -> Path:
        output_id = self._component(output_id, "output id")
        return self.exports_dir(project_id) / f"{output_id}.mp4"

    def evidence_dir(self, project_id: str) -> Path:
        return self._dir(project_id, "evidence")

    def create_evidence_path(self, project_id: str, artifact_name: str) -> Path:
        name = self._component(artifact_name, "evidence artifact name")
        return self.evidence_dir(project_id) / name

    def resolve_evidence_path(self, project_id: str, artifact_name: str) -> Path:
        path = self.create_evidence_path(project_id, artifact_name)
        evidence_root = self.evidence_dir(project_id).resolve()
        resolved = path.resolve()
        if evidence_root not in resolved.parents and resolved != evidence_root:
            raise AppError("Invalid evidence artifact path", status_code=400)
        if not resolved.exists() or not resolved.is_file():
            raise AppError("Evidence media not found", status_code=404)
        return resolved

    def evidence_media_uri(self, project_id: str, artifact_name: str) -> str:
        return f"/projects/{project_id}/evidence-media/{artifact_name}"

    def _dir(self, project_id: str, name: str) -> Path:
        path = self.project_dir(project_id) / name
        path.mkdir(parents=True, exist_ok=True)
        return path
