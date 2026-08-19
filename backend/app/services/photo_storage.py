"""Photo upload storage — plan section 4.4 (photo in, done)."""

import uuid
from pathlib import Path


def save_upload(photos_dir: Path, *, original_filename: str, content: bytes) -> str:
    """Saves `content` under a generated unique filename inside `photos_dir`
    and returns the photo_id (== filename, relative to photos_dir)."""
    photos_dir = Path(photos_dir)
    photos_dir.mkdir(parents=True, exist_ok=True)

    suffix = (Path(original_filename).suffix or ".jpg").lower()
    photo_id = f"{uuid.uuid4().hex}{suffix}"
    (photos_dir / photo_id).write_bytes(content)
    return photo_id
