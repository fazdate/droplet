#!/usr/bin/env python3
"""Nightly SQLite + photos backup — plan phase 6.

Usage:
    python -m scripts.backup

Uses SQLite's online backup API (safe against a concurrently-running app —
no need to stop the service first) and tars the result together with the
photos directory into a single timestamped archive. Run this from cron, or
point your existing host-level backup job at BACKUP_DIR instead if you prefer
retention outside the app.
"""

import argparse
import datetime as dt
import sqlite3
import tarfile
from pathlib import Path

from app.config import Settings


def _backup_sqlite_file(db_path: Path, dest_path: Path) -> None:
    """Uses sqlite3's backup API so a concurrently-running app doesn't corrupt
    the copy (unlike a plain file copy against a WAL-mode DB)."""
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(dest_path)
    with dest:
        source.backup(dest)
    source.close()
    dest.close()


def run_backup(*, db_path: Path, photos_dir: Path, backup_dir: Path, now_label: str) -> Path:
    db_path = Path(db_path)
    photos_dir = Path(photos_dir)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    archive_path = backup_dir / f"droplet-backup-{now_label}.tar.gz"

    staging_db = backup_dir / f".staging-{now_label}.sqlite3"
    _backup_sqlite_file(db_path, staging_db)

    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(staging_db, arcname="droplet.sqlite3")
            if photos_dir.is_dir():
                tar.add(photos_dir, arcname="photos")
    finally:
        staging_db.unlink(missing_ok=True)

    return archive_path


def prune_old_backups(backup_dir: Path, keep: int) -> None:
    archives = sorted(Path(backup_dir).glob("droplet-backup-*.tar.gz"), key=lambda p: p.name)
    for stale in archives[:-keep] if keep > 0 else archives:
        stale.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the watering app's SQLite DB + photos.")
    parser.add_argument("--backup-dir", default="/backups/droplet", help="Where to write the archive")
    parser.add_argument("--keep", type=int, default=14, help="Number of most recent archives to retain")
    args = parser.parse_args()

    settings = Settings()
    now_label = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")

    archive_path = run_backup(
        db_path=Path(settings.db_path),
        photos_dir=Path(settings.photos_dir),
        backup_dir=Path(args.backup_dir),
        now_label=now_label,
    )
    prune_old_backups(Path(args.backup_dir), keep=args.keep)
    print(f"Backup written to {archive_path}")


if __name__ == "__main__":
    main()
