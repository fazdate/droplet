"""Tests for scripts.backup: nightly SQLite + photos backup — plan phase 6."""

import sqlite3
import tarfile
from pathlib import Path

from scripts.backup import prune_old_backups, run_backup


def _make_sqlite_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO t (id) VALUES (1)")
    conn.commit()
    conn.close()


def test_should_create_timestamped_backup_archive(tmp_path) -> None:
    db_path = tmp_path / "droplet.sqlite3"
    _make_sqlite_db(db_path)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    (photos_dir / "a.jpg").write_bytes(b"fake-photo")
    backup_dir = tmp_path / "backups"

    archive_path = run_backup(db_path=db_path, photos_dir=photos_dir, backup_dir=backup_dir, now_label="20260817-0300")

    assert archive_path.exists()
    assert archive_path.name == "droplet-backup-20260817-0300.tar.gz"
    with tarfile.open(archive_path) as tar:
        names = tar.getnames()
        assert any(name.endswith("droplet.sqlite3") for name in names)
        assert any(name.endswith("a.jpg") for name in names)


def test_should_produce_a_restorable_sqlite_copy(tmp_path) -> None:
    db_path = tmp_path / "droplet.sqlite3"
    _make_sqlite_db(db_path)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    backup_dir = tmp_path / "backups"

    archive_path = run_backup(db_path=db_path, photos_dir=photos_dir, backup_dir=backup_dir, now_label="x")

    extract_dir = tmp_path / "extracted"
    with tarfile.open(archive_path) as tar:
        tar.extractall(extract_dir, filter="data")

    restored_db = next(extract_dir.rglob("droplet.sqlite3"))
    conn = sqlite3.connect(restored_db)
    rows = conn.execute("SELECT id FROM t").fetchall()
    assert rows == [(1,)]


def test_should_skip_photos_when_dir_is_empty_or_missing(tmp_path) -> None:
    db_path = tmp_path / "droplet.sqlite3"
    _make_sqlite_db(db_path)
    backup_dir = tmp_path / "backups"

    archive_path = run_backup(
        db_path=db_path, photos_dir=tmp_path / "does-not-exist", backup_dir=backup_dir, now_label="x"
    )

    assert archive_path.exists()


def test_should_prune_backups_older_than_keep_count(tmp_path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    names = [f"droplet-backup-{i:02d}.tar.gz" for i in range(5)]
    for name in names:
        (backup_dir / name).write_bytes(b"x")

    prune_old_backups(backup_dir, keep=3)

    remaining = sorted(p.name for p in backup_dir.glob("*.tar.gz"))
    assert remaining == names[-3:]


def test_should_not_prune_when_fewer_backups_than_keep_count(tmp_path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "droplet-backup-1.tar.gz").write_bytes(b"x")

    prune_old_backups(backup_dir, keep=5)

    assert len(list(backup_dir.glob("*.tar.gz"))) == 1
