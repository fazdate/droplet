"""Tests for scripts.cleanup_orphan_photos: deleting unreferenced plant photos
— plan section 6 hardening (photo storage growth / orphan cleanup)."""

import datetime as dt

from sqlalchemy.orm import Session

from app.db import create_db_engine, init_db
from app.models.orm import Plant, Room, Species
from scripts.cleanup_orphan_photos import find_orphan_photos, run_cleanup

NOW = dt.datetime(2026, 8, 18, 12, 0, tzinfo=dt.timezone.utc)


def _seed_plant(engine, *, photo_path: str) -> None:
    with Session(engine) as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Ocimum basilicum", watering_interval_days=4, source="manual")
        session.add_all([room, species])
        session.flush()
        session.add(
            Plant(
                nickname="Basil",
                room_id=room.id,
                species_id=species.id,
                photo_path=photo_path,
                created_at=NOW,
            )
        )
        session.commit()


def _touch(path, *, age_hours: float) -> None:
    path.write_bytes(b"fake-photo")
    stamp = (NOW - dt.timedelta(hours=age_hours)).timestamp()
    import os

    os.utime(path, (stamp, stamp))


def test_should_find_unreferenced_photo_older_than_min_age(tmp_path) -> None:
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    orphan = photos_dir / "orphan.jpg"
    _touch(orphan, age_hours=48)

    orphans = find_orphan_photos(photos_dir=photos_dir, referenced=set(), min_age_hours=24, now=NOW)

    assert orphans == [orphan]


def test_should_not_flag_referenced_photo_as_orphan(tmp_path) -> None:
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    used = photos_dir / "used.jpg"
    _touch(used, age_hours=48)

    orphans = find_orphan_photos(photos_dir=photos_dir, referenced={"used.jpg"}, min_age_hours=24, now=NOW)

    assert orphans == []


def test_should_not_flag_recently_uploaded_photo_as_orphan(tmp_path) -> None:
    """A photo from an in-progress/abandoned identify call is unreferenced by
    definition until the user confirms a plant — the age grace period is what
    keeps it from being deleted out from under them mid-flow."""
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    fresh = photos_dir / "fresh.jpg"
    _touch(fresh, age_hours=1)

    orphans = find_orphan_photos(photos_dir=photos_dir, referenced=set(), min_age_hours=24, now=NOW)

    assert orphans == []


def test_should_return_empty_list_when_photos_dir_missing(tmp_path) -> None:
    orphans = find_orphan_photos(
        photos_dir=tmp_path / "does-not-exist", referenced=set(), min_age_hours=24, now=NOW
    )

    assert orphans == []


def test_should_delete_orphan_but_keep_referenced_and_recent_photos(tmp_path) -> None:
    db_path = tmp_path / "droplet.sqlite3"
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)
    _seed_plant(engine, photo_path="used.jpg")

    used = photos_dir / "used.jpg"
    _touch(used, age_hours=48)
    old_orphan = photos_dir / "old-orphan.jpg"
    _touch(old_orphan, age_hours=48)
    fresh_orphan = photos_dir / "fresh-orphan.jpg"
    _touch(fresh_orphan, age_hours=1)

    deleted = run_cleanup(db_path=db_path, photos_dir=photos_dir, min_age_hours=24, now=NOW)

    assert deleted == [old_orphan]
    assert used.exists()
    assert fresh_orphan.exists()
    assert not old_orphan.exists()


def test_should_not_delete_anything_in_dry_run_mode(tmp_path) -> None:
    db_path = tmp_path / "droplet.sqlite3"
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)

    old_orphan = photos_dir / "old-orphan.jpg"
    _touch(old_orphan, age_hours=48)

    deleted = run_cleanup(db_path=db_path, photos_dir=photos_dir, min_age_hours=24, dry_run=True, now=NOW)

    assert deleted == [old_orphan]
    assert old_orphan.exists()


def test_should_treat_species_reference_image_path_as_referenced(tmp_path) -> None:
    """reference_image_path isn't populated by the current code path, but
    treating it as referenced defensively costs nothing and avoids deleting a
    file a future change might rely on."""
    db_path = tmp_path / "droplet.sqlite3"
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)
    with Session(engine) as session:
        species = Species(
            scientific_name="Ocimum basilicum",
            watering_interval_days=4,
            source="manual",
            reference_image_path="reference.jpg",
        )
        session.add(species)
        session.commit()

    reference = photos_dir / "reference.jpg"
    _touch(reference, age_hours=48)

    deleted = run_cleanup(db_path=db_path, photos_dir=photos_dir, min_age_hours=24, now=NOW)

    assert deleted == []
    assert reference.exists()


def test_should_find_orphan_thumbnail_whose_original_is_unreferenced(tmp_path) -> None:
    """Thumbnails (see app.services.thumbnails) are cached under
    photos_dir/thumbnails/<stem>.jpg — an orphaned original's thumbnail
    should be swept up too, or it'd leak on disk forever."""
    photos_dir = tmp_path / "photos"
    thumbs_dir = photos_dir / "thumbnails"
    thumbs_dir.mkdir(parents=True)
    orphan_thumb = thumbs_dir / "orphan.jpg"
    _touch(orphan_thumb, age_hours=48)

    orphans = find_orphan_photos(photos_dir=photos_dir, referenced=set(), min_age_hours=24, now=NOW)

    assert orphans == [orphan_thumb]


def test_should_not_flag_thumbnail_as_orphan_when_its_original_is_referenced(tmp_path) -> None:
    """The thumbnail is always re-encoded as `<stem>.jpg`, which may differ
    from the referenced original's own extension (e.g. a `.png` upload has a
    `.jpg` thumbnail) — matching must be by stem, not exact filename."""
    photos_dir = tmp_path / "photos"
    thumbs_dir = photos_dir / "thumbnails"
    thumbs_dir.mkdir(parents=True)
    thumb = thumbs_dir / "used.jpg"
    _touch(thumb, age_hours=48)

    orphans = find_orphan_photos(photos_dir=photos_dir, referenced={"used.png"}, min_age_hours=24, now=NOW)

    assert orphans == []


def test_should_delete_orphan_thumbnail_via_run_cleanup(tmp_path) -> None:
    db_path = tmp_path / "droplet.sqlite3"
    photos_dir = tmp_path / "photos"
    thumbs_dir = photos_dir / "thumbnails"
    thumbs_dir.mkdir(parents=True)

    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)
    _seed_plant(engine, photo_path="used.jpg")

    used_thumb = thumbs_dir / "used.jpg"
    _touch(used_thumb, age_hours=48)
    orphan_thumb = thumbs_dir / "orphan.jpg"
    _touch(orphan_thumb, age_hours=48)

    deleted = run_cleanup(db_path=db_path, photos_dir=photos_dir, min_age_hours=24, now=NOW)

    assert deleted == [orphan_thumb]
    assert used_thumb.exists()
    assert not orphan_thumb.exists()
