#!/usr/bin/env python3
"""Orphaned photo cleanup — plan section 6 hardening.

`/api/identify` (see `app.routers.species`) saves the uploaded photo to
PHOTOS_DIR immediately, before the user has picked a candidate and confirmed
the add-plant flow. If they close the tab or otherwise abandon that flow, the
file is never referenced by a `Plant.photo_path` and just sits there forever.

This script deletes files in PHOTOS_DIR that are BOTH:
  - unreferenced by any `Plant.photo_path` (or `Species.reference_image_path`,
    reserved for a possible future locally-cached reference image — treating
    it as referenced too costs nothing and avoids a nasty surprise later), and
  - older than --min-age-hours (default 24h).

The age check is the safety net that satisfies "never delete a photo actively
used by the app": a freshly-uploaded, not-yet-confirmed photo is unreferenced
by definition, but it stays untouched for a full day so the user has plenty
of time to finish (or come back to) the add-plant flow before it's swept up.

Usage:
    python -m scripts.cleanup_orphan_photos [--dry-run] [--min-age-hours 24]
"""

import argparse
import datetime as dt
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import create_db_engine, init_db, session_scope
from app.models.orm import Plant, Species
from app.services.thumbnails import thumbnails_dir


def _referenced_photo_ids(session: Session) -> set[str]:
    plant_paths = session.scalars(select(Plant.photo_path)).all()
    species_paths = session.scalars(
        select(Species.reference_image_path).where(Species.reference_image_path.is_not(None))
    ).all()
    return {Path(p).name for p in [*plant_paths, *species_paths] if p}


def _find_orphan_files(
    directory: Path,
    *,
    referenced: set[str],
    key_fn,
    min_age_hours: int,
    now: dt.datetime,
) -> list[Path]:
    if not directory.is_dir():
        return []

    cutoff = now - dt.timedelta(hours=min_age_hours)
    orphans = []
    for file_path in sorted(directory.iterdir()):
        if not file_path.is_file() or key_fn(file_path) in referenced:
            continue
        mtime = dt.datetime.fromtimestamp(file_path.stat().st_mtime, tz=dt.timezone.utc)
        if mtime < cutoff:
            orphans.append(file_path)
    return orphans


def find_orphan_photos(
    *,
    photos_dir: Path,
    referenced: set[str],
    min_age_hours: int,
    now: dt.datetime,
) -> list[Path]:
    """Lists files under `photos_dir` (plus its `thumbnails/` subdirectory —
    see app.services.thumbnails) that aren't in `referenced` and are older
    than `min_age_hours` relative to `now`. Never raises/deletes anything
    itself — pure listing, so callers can dry-run it safely.

    Thumbnails are matched by filename *stem* rather than exact name: a
    thumbnail is always re-encoded as `<stem>.jpg` regardless of the
    original's extension (see thumbnail_filename), so comparing full names
    against `referenced` would never match and every thumbnail would look
    orphaned even while its original photo is still in use.
    """
    photos_dir = Path(photos_dir)
    if not photos_dir.is_dir():
        return []

    referenced_stems = {Path(name).stem for name in referenced}
    orphans = _find_orphan_files(
        photos_dir, referenced=referenced, key_fn=lambda p: p.name, min_age_hours=min_age_hours, now=now
    )
    orphans += _find_orphan_files(
        thumbnails_dir(photos_dir),
        referenced=referenced_stems,
        key_fn=lambda p: p.stem,
        min_age_hours=min_age_hours,
        now=now,
    )
    return orphans


def run_cleanup(
    *,
    db_path: Path,
    photos_dir: Path,
    min_age_hours: int = 24,
    dry_run: bool = False,
    now: dt.datetime | None = None,
) -> list[Path]:
    now = now or dt.datetime.now(dt.timezone.utc)
    db_path = Path(db_path)
    photos_dir = Path(photos_dir)

    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)
    with session_scope(engine) as session:
        referenced = _referenced_photo_ids(session)

    orphans = find_orphan_photos(photos_dir=photos_dir, referenced=referenced, min_age_hours=min_age_hours, now=now)

    if not dry_run:
        for file_path in orphans:
            file_path.unlink(missing_ok=True)

    return orphans


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete orphaned plant photos with no DB reference.")
    parser.add_argument(
        "--min-age-hours",
        type=int,
        default=24,
        help="Only delete unreferenced photos older than this many hours (default: 24) — "
        "gives an abandoned add-plant flow plenty of time to be resumed before its photo is swept up",
    )
    parser.add_argument("--dry-run", action="store_true", help="List what would be deleted without deleting it")
    args = parser.parse_args()

    settings = Settings()
    orphans = run_cleanup(
        db_path=Path(settings.db_path),
        photos_dir=Path(settings.photos_dir),
        min_age_hours=args.min_age_hours,
        dry_run=args.dry_run,
    )

    verb = "Would delete" if args.dry_run else "Deleted"
    print(f"{verb} {len(orphans)} orphaned photo(s){':' if orphans else ''}")
    for file_path in orphans:
        print(f"  {file_path}")


if __name__ == "__main__":
    main()
