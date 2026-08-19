"""On-demand thumbnail generation for plant-tile photos — memory-friendliness
hardening (see TODO.md "taking a first picture of a plant nothing happens").

The plant list only ever displays a photo at a 64x64 CSS-pixel tile (see
frontend/src/style.css .plant-tile img), but it was loading/decoding the full
client-resized upload (up to 1280px on its longest side) for every plant,
every time the list re-rendered. On a phone already under memory pressure —
e.g. while the native Camera app is open for another capture — a backgrounded
tab's own resident memory (including decoded image bitmaps) makes it a more
likely candidate for Android's low-memory tab discard/reload behaviour, which
is what silently breaks the add-plant flow (see TODO.md notes above).

Thumbnails are generated lazily on first request and cached to disk (see
app.routers.photos) rather than eagerly at upload time, so plants added
before this existed still get a small thumbnail without a backfill/migration
step.
"""

import logging
from pathlib import Path

from PIL import Image, UnidentifiedImageError

LOG = logging.getLogger(__name__)

THUMBNAIL_MAX_DIMENSION = 160
THUMBNAIL_JPEG_QUALITY = 70
THUMBNAILS_SUBDIR = "thumbnails"


def thumbnails_dir(photos_dir: Path) -> Path:
    return Path(photos_dir) / THUMBNAILS_SUBDIR


def thumbnail_filename(photo_id: str) -> str:
    """Thumbnails are always re-encoded as JPEG (regardless of the source
    format) so the cached filename always uses a `.jpg` suffix, distinct from
    `photo_id` which keeps whatever extension the original upload had."""
    return f"{Path(photo_id).stem}.jpg"


def get_or_create_thumbnail(photos_dir: Path, photo_id: str) -> Path | None:
    """Returns the on-disk path to `photo_id`'s thumbnail, generating and
    caching it first if it doesn't exist yet. Returns None (caller should
    fall back to serving the full photo) if the source can't be opened or
    decoded by Pillow — a thumbnail is a nice-to-have optimization, never a
    hard dependency for viewing a plant's photo."""
    photos_dir = Path(photos_dir)
    source = photos_dir / photo_id
    thumb_path = thumbnails_dir(photos_dir) / thumbnail_filename(photo_id)

    if thumb_path.is_file():
        return thumb_path
    if not source.is_file():
        return None

    try:
        with Image.open(source) as img:
            rgb = img.convert("RGB")
            rgb.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION))
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            rgb.save(thumb_path, format="JPEG", quality=THUMBNAIL_JPEG_QUALITY)
    except (OSError, UnidentifiedImageError):
        LOG.warning("Could not generate thumbnail for %s; serving full photo instead", photo_id, exc_info=True)
        return None

    return thumb_path
