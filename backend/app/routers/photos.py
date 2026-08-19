"""Serves lazily-generated, disk-cached plant-photo thumbnails — see
app.services.thumbnails for the "why" (memory-friendliness hardening,
TODO.md)."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import Settings
from app.deps import get_settings
from app.services.thumbnails import get_or_create_thumbnail

router = APIRouter(tags=["photos"])


@router.get("/photos/thumbnails/{photo_id}")
def get_photo_thumbnail(photo_id: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    # FastAPI's `{photo_id}` path param never contains "/", but guard against
    # ".."/dotfile tricks anyway since it flows straight into a filesystem
    # path below.
    if photo_id != Path(photo_id).name or photo_id.startswith("."):
        raise HTTPException(status_code=404)

    photos_dir = Path(settings.photos_dir)
    original = photos_dir / photo_id
    if not original.is_file():
        raise HTTPException(status_code=404)

    thumb_path = get_or_create_thumbnail(photos_dir, photo_id)
    if thumb_path is not None:
        return FileResponse(thumb_path, media_type="image/jpeg")
    # Thumbnail generation failed (e.g. unsupported/corrupt source) — the
    # frontend's <img> just ends up showing the full photo instead; see
    # render.ts's error-fallback listener.
    return FileResponse(original)
