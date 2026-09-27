import os
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from backend.src.config import (
    REPO_ROOT, MEDIA_DIR, CLOUD_EXPORT_DIR,
    CF_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY,
    CF_R2_BUCKET_NAME, CF_PUBLIC_BASE_URL, CF_R2_CUSTOM_DOMAIN
)
from backend.src.storage.repository import match_repo

logger = logging.getLogger("cloudflare_sync")


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class CloudflareSyncService:
    def __init__(self):
        self._lock = threading.Lock()
        self._sync_states: Dict[str, Dict[str, Any]] = {}

    def is_configured(self) -> bool:
        """Check if Cloudflare R2 credentials are fully configured."""
        return bool(CF_ACCOUNT_ID and CF_R2_ACCESS_KEY_ID and CF_R2_SECRET_ACCESS_KEY)

    def get_public_url(self, match_id: str) -> str:
        """Construct the canonical public viewer URL for a match."""
        base = CF_PUBLIC_BASE_URL or "https://focusplay.pages.dev"
        return f"{base}/?match={match_id}"

    def get_match_summary(self, match_id: str) -> Dict[str, Any]:
        """Inspect match media and metadata, returning asset breakdown and sync readiness."""
        match = match_repo.get_match(match_id)
        if not match:
            return {"error": f"Match '{match_id}' not found"}

        # Full video
        video_info = {
            "url": match.video_url,
            "filename": "",
            "size_bytes": 0,
            "formatted_size": "0 B",
            "exists": False,
        }
        if match.video_url:
            clean_name = match.video_url.replace("/media/", "").lstrip("/")
            local_path = (MEDIA_DIR / clean_name).resolve()
            video_info["filename"] = local_path.name
            if local_path.exists() and local_path.is_file():
                video_info["exists"] = True
                video_info["size_bytes"] = local_path.stat().st_size
                video_info["formatted_size"] = _format_size(video_info["size_bytes"])

        # Highlight clips
        highlights = match_repo.get_highlights(match_id)
        clips_info: List[Dict[str, Any]] = []
        unique_media_paths = set()
        if video_info["exists"]:
            clean_name = match.video_url.replace("/media/", "").lstrip("/")
            unique_media_paths.add(str((MEDIA_DIR / clean_name).resolve()))

        total_clips_size = 0
        for h in highlights:
            if h.clip_url:
                c_name = h.clip_url.replace("/media/", "").lstrip("/")
                c_path = (MEDIA_DIR / c_name).resolve()
                c_size = c_path.stat().st_size if c_path.exists() else 0
                is_standalone_clip = str(c_path) not in unique_media_paths
                if is_standalone_clip and c_path.exists():
                    total_clips_size += c_size
                    unique_media_paths.add(str(c_path))

                clips_info.append({
                    "id": h.id,
                    "title": h.title,
                    "filename": c_path.name,
                    "size_bytes": c_size,
                    "formatted_size": _format_size(c_size),
                    "exists": c_path.exists(),
                    "is_standalone_clip": is_standalone_clip,
                })

        # Thumbnail
        thumb_info = {
            "url": match.thumbnail_url,
            "filename": "",
            "size_bytes": 0,
            "exists": False,
        }
        if match.thumbnail_url:
            t_name = match.thumbnail_url.replace("/media/", "").lstrip("/")
            t_path = (MEDIA_DIR / t_name).resolve()
            thumb_info["filename"] = t_path.name
            if t_path.exists() and t_path.is_file():
                thumb_info["exists"] = True
                thumb_info["size_bytes"] = t_path.stat().st_size
                unique_media_paths.add(str(t_path))

        events = match_repo.get_events(match_id)
        radar_frames = match_repo.get_radar_frames(match_id)
        analytics = match_repo.get_analytics(match_id)
        drawings = match_repo.get_drawings(match_id)

        # Sum unique file sizes only
        total_bytes = 0
        for p_str in unique_media_paths:
            try:
                p = Path(p_str)
                if p.exists() and p.is_file():
                    total_bytes += p.stat().st_size
            except Exception:
                pass

        status = self.get_status(match_id)

        return {
            "match_id": match.id,
            "title": match.title,
            "date": match.date,
            "duration_seconds": match.duration_seconds,
            "is_configured": self.is_configured(),
            "bucket_name": CF_R2_BUCKET_NAME,
            "public_base_url": CF_PUBLIC_BASE_URL,
            "public_url": self.get_public_url(match.id),
            "video": video_info,
            "clips": {
                "count": len(clips_info),
                "total_size_bytes": total_clips_size,
                "formatted_size": _format_size(total_clips_size),
                "items": clips_info,
            },
            "thumbnail": thumb_info,
            "metadata": {
                "events_count": len(events),
                "highlights_count": len(highlights),
                "radar_frames_count": len(radar_frames),
                "has_analytics": analytics is not None,
                "drawings_count": len(drawings),
            },
            "total_media_size_bytes": total_bytes,
            "formatted_total_media_size": _format_size(total_bytes),
            "status": status,
        }

    def get_status(self, match_id: str) -> Dict[str, Any]:
        """Return the current sync status for a match."""
        with self._lock:
            state = self._sync_states.get(match_id)
            if state:
                return dict(state)
            return {
                "match_id": match_id,
                "status": "idle",
                "progress_percent": 0.0,
                "current_file": None,
                "completed_files": 0,
                "total_files": 0,
                "uploaded_bytes": 0,
                "total_bytes": 0,
                "public_url": self.get_public_url(match_id),
                "error": None,
                "updated_at": 0,
                "last_synced_at": None,
            }

    def _set_status(self, match_id: str, **kwargs):
        with self._lock:
            if match_id not in self._sync_states:
                self._sync_states[match_id] = {
                    "match_id": match_id,
                    "status": "idle",
                    "progress_percent": 0.0,
                    "current_file": None,
                    "completed_files": 0,
                    "total_files": 0,
                    "uploaded_bytes": 0,
                    "total_bytes": 0,
                    "public_url": self.get_public_url(match_id),
                    "error": None,
                    "updated_at": time.time(),
                    "last_synced_at": None,
                }
            self._sync_states[match_id].update(kwargs)
            self._sync_states[match_id]["updated_at"] = time.time()

    def export_match_json_bundle(self, match_id: str, out_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Export all match data to clean JSON payloads (in memory and optional directory)."""
        match = match_repo.get_match(match_id)
        if not match:
            raise ValueError(f"Match '{match_id}' not found")

        events = match_repo.get_events(match_id)
        highlights = match_repo.get_highlights(match_id)
        radar_frames = match_repo.get_radar_frames(match_id)
        analytics = match_repo.get_analytics(match_id)
        drawings = match_repo.get_drawings(match_id)
        team = match_repo.get_team(match.team_id) if match.team_id else None

        bundle = {
            "match.json": match.model_dump(),
            "events.json": [e.model_dump() for e in events],
            "highlights.json": [h.model_dump() for h in highlights],
            "radar.json": [r.model_dump() for r in radar_frames],
            "analytics.json": analytics.model_dump() if analytics else None,
            "drawings.json": [d.model_dump() for d in drawings],
            "team.json": team.model_dump() if team else None,
        }

        # Also prepare the matches catalog
        all_matches = match_repo.list_matches()
        bundle["index.json"] = [m.model_dump() for m in all_matches]

        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in bundle.items():
                if content is not None:
                    p = out_dir / filename
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)

        return bundle

    def _get_s3_client(self):
        """Create a boto3 S3 client configured for Cloudflare R2."""
        import boto3
        from botocore.config import Config

        endpoint = f"https://{CF_ACCOUNT_ID}.r2.cloudflarestorage.com"
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=CF_R2_ACCESS_KEY_ID,
            aws_secret_access_key=CF_R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            region_name="auto",
        )

    def trigger_sync(self, match_id: str, metadata_only: bool = False) -> Dict[str, Any]:
        """Trigger an asynchronous sync job in a background thread."""
        current = self.get_status(match_id)
        if current.get("status") == "syncing":
            return {"status": "already_syncing", "message": "Sync is already in progress"}

        thread = threading.Thread(
            target=self._run_sync,
            args=(match_id, metadata_only),
            daemon=True,
            name=f"cf-sync-{match_id}"
        )
        thread.start()
        return {"status": "started", "message": "Cloudflare sync started"}

    def _run_sync(self, match_id: str, metadata_only: bool = False):
        try:
            self._set_status(
                match_id,
                status="syncing",
                progress_percent=0.0,
                error=None,
                current_file="Preparing match bundle...",
            )

            # Step 1: Export JSON bundles locally
            match_export_dir = CLOUD_EXPORT_DIR / match_id
            bundle = self.export_match_json_bundle(match_id, out_dir=match_export_dir)

            if not self.is_configured():
                # Dry-run / local export completed
                logger.info(f"Cloudflare credentials not set; exported bundle to {match_export_dir}")
                self._set_status(
                    match_id,
                    status="needs_credentials",
                    progress_percent=100.0,
                    current_file="Exported locally (CF credentials needed)",
                    completed_files=len(bundle),
                    total_files=len(bundle),
                    public_url=self.get_public_url(match_id),
                    error="Cloudflare credentials not configured in scripts/config.local.env.",
                    last_synced_at=time.time(),
                )
                return

            s3 = self._get_s3_client()
            bucket = CF_R2_BUCKET_NAME

            # Step 2: Plan upload queue
            upload_queue: List[Dict[str, Any]] = []

            # Add JSON metadata files to queue
            for fname, content in bundle.items():
                if content is None:
                    continue
                data_bytes = json.dumps(content, ensure_ascii=False).encode("utf-8")
                key = f"matches/{match_id}/{fname}" if fname != "index.json" else "matches/index.json"
                upload_queue.append({
                    "type": "bytes",
                    "key": key,
                    "data": data_bytes,
                    "content_type": "application/json",
                    "size": len(data_bytes),
                    "label": f"JSON: {fname}",
                })

            if not metadata_only:
                summary = self.get_match_summary(match_id)
                queued_keys = set()

                # Full Video (priority)
                video = summary.get("video", {})
                if video.get("exists"):
                    v_path = (MEDIA_DIR / video["filename"]).resolve()
                    v_key = f"media/{v_path.name}"
                    upload_queue.append({
                        "type": "file",
                        "path": v_path,
                        "key": v_key,
                        "content_type": "video/mp4",
                        "size": v_path.stat().st_size,
                        "label": f"Match Video: {v_path.name}",
                    })
                    queued_keys.add(v_key)

                # Thumbnail
                thumb = summary.get("thumbnail", {})
                if thumb.get("exists"):
                    t_path = (MEDIA_DIR / thumb["filename"]).resolve()
                    t_key = f"media/{t_path.name}"
                    if t_key not in queued_keys:
                        upload_queue.append({
                            "type": "file",
                            "path": t_path,
                            "key": t_key,
                            "content_type": "image/jpeg",
                            "size": t_path.stat().st_size,
                            "label": f"Thumbnail: {t_path.name}",
                        })
                        queued_keys.add(t_key)

                # Highlight Clips (only standalone clips not already queued)
                clips = summary.get("clips", {}).get("items", [])
                for c in clips:
                    if c.get("exists"):
                        c_path = (MEDIA_DIR / c["filename"]).resolve()
                        c_key = f"media/{c_path.name}"
                        if c_key not in queued_keys:
                            upload_queue.append({
                                "type": "file",
                                "path": c_path,
                                "key": c_key,
                                "content_type": "video/mp4",
                                "size": c_path.stat().st_size,
                                "label": f"Clip: {c_path.name}",
                            })
                            queued_keys.add(c_key)

            total_bytes = sum(item["size"] for item in upload_queue)
            total_files = len(upload_queue)
            uploaded_bytes = 0
            completed_files = 0

            self._set_status(
                match_id,
                total_files=total_files,
                total_bytes=total_bytes,
                completed_files=0,
                uploaded_bytes=0,
            )

            # Step 3: Execute uploads with differential check
            from boto3.s3.transfer import TransferConfig

            transfer_config = TransferConfig(
                multipart_threshold=16 * 1024 * 1024,
                multipart_chunksize=16 * 1024 * 1024,
                max_concurrency=4,
            )

            for item in upload_queue:
                self._set_status(match_id, current_file=item["label"])

                if item["type"] == "bytes":
                    s3.put_object(
                        Bucket=bucket,
                        Key=item["key"],
                        Body=item["data"],
                        ContentType=item["content_type"],
                        CacheControl="public, max-age=60, s-maxage=300",
                    )
                    uploaded_bytes += item["size"]
                elif item["type"] == "file":
                    file_path = item["path"]
                    file_size = item["size"]

                    # Differential check: check if already exists on R2 with same size
                    already_uploaded = False
                    try:
                        resp = s3.head_object(Bucket=bucket, Key=item["key"])
                        if resp.get("ContentLength") == file_size:
                            already_uploaded = True
                    except Exception:
                        pass

                    if already_uploaded:
                        logger.info(f"Skipping already-uploaded file: {item['key']}")
                        uploaded_bytes += file_size
                    else:
                        file_uploaded = [0]

                        def progress_cb(chunk_bytes, current_item=item, item_file_size=file_size):
                            file_uploaded[0] += chunk_bytes
                            current_total = uploaded_bytes + file_uploaded[0]
                            pct = round((current_total / max(total_bytes, 1)) * 100, 1)
                            self._set_status(
                                match_id,
                                uploaded_bytes=min(current_total, total_bytes),
                                progress_percent=min(pct, 99.9),
                            )

                        s3.upload_file(
                            Filename=str(file_path),
                            Bucket=bucket,
                            Key=item["key"],
                            Config=transfer_config,
                            Callback=progress_cb,
                            ExtraArgs={
                                "ContentType": item["content_type"],
                                "CacheControl": "public, max-age=86400",
                            },
                        )
                        uploaded_bytes += file_size

                completed_files += 1
                pct = round((uploaded_bytes / max(total_bytes, 1)) * 100, 1)
                self._set_status(
                    match_id,
                    completed_files=completed_files,
                    uploaded_bytes=uploaded_bytes,
                    progress_percent=min(pct, 100.0),
                )

            # Finished
            self._set_status(
                match_id,
                status="completed",
                progress_percent=100.0,
                current_file="All assets synced successfully",
                last_synced_at=time.time(),
                public_url=self.get_public_url(match_id),
                error=None,
            )
            logger.info(f"Sync complete for match {match_id}. Public URL: {self.get_public_url(match_id)}")

        except Exception as e:
            logger.error(f"Sync failed for match {match_id}: {e}", exc_info=True)
            self._set_status(
                match_id,
                status="failed",
                error=str(e),
                current_file="Sync failed",
            )


# Global singleton instance
cloudflare_sync_service = CloudflareSyncService()
