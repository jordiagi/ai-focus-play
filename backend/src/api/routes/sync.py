from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.src.services.cloudflare_sync import cloudflare_sync_service

router = APIRouter(prefix="/api/matches/{match_id}/sync", tags=["sync"])


class SyncRequest(BaseModel):
    metadata_only: bool = False


@router.get("/summary")
def get_sync_summary(match_id: str) -> Dict[str, Any]:
    """Inspect local match assets and return file sizes and sync readiness."""
    res = cloudflare_sync_service.get_match_summary(match_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.get("/status")
def get_sync_status(match_id: str) -> Dict[str, Any]:
    """Return the live progress or status of match sync to Cloudflare."""
    return cloudflare_sync_service.get_status(match_id)


@router.post("")
def trigger_match_sync(match_id: str, req: Optional[SyncRequest] = None) -> Dict[str, Any]:
    """Trigger an asynchronous sync of match assets and metadata to Cloudflare R2."""
    meta_only = req.metadata_only if req else False
    return cloudflare_sync_service.trigger_sync(match_id, metadata_only=meta_only)
