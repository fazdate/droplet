"""Tests for app.db engine/session helpers."""

from sqlalchemy import inspect

from app.db import create_db_engine, init_db, session_scope


def test_should_enable_wal_mode_on_sqlite_engine(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite3"
    engine = create_db_engine(f"sqlite:///{db_path}")

    with engine.connect() as conn:
        mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()

    assert mode == "wal"


def test_should_create_all_tables_on_init(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite3"
    engine = create_db_engine(f"sqlite:///{db_path}")

    init_db(engine)

    tables = set(inspect(engine).get_table_names())
    assert {"room", "species", "plant", "watering_event", "settings"} <= tables


def test_should_create_parent_directory_for_file_based_sqlite(tmp_path) -> None:
    nested_path = tmp_path / "nested" / "dir" / "test.sqlite3"

    create_db_engine(f"sqlite:///{nested_path}")

    assert nested_path.parent.is_dir()


def test_session_scope_should_commit_on_success(tmp_path) -> None:
    from app.models.orm import Room

    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    init_db(engine)

    with session_scope(engine) as session:
        session.add(Room(name="Living room"))

    with session_scope(engine) as session:
        assert session.query(Room).filter_by(name="Living room").count() == 1


def test_session_scope_should_rollback_on_error(tmp_path) -> None:
    from app.models.orm import Room

    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    init_db(engine)

    try:
        with session_scope(engine) as session:
            session.add(Room(name="Kitchen"))
            raise ValueError("boom")
    except ValueError:
        pass

    with session_scope(engine) as session:
        assert session.query(Room).filter_by(name="Kitchen").count() == 0


def test_should_backfill_nickname_is_custom_column_on_pre_existing_database(tmp_path) -> None:
    """Simulates a real deployment's SQLite file created before the
    `nickname_is_custom` column existed: `create_all` alone would leave the
    already-existing `plant` table without it, so `init_db` must patch it in
    via `ALTER TABLE` instead (see app.db._apply_schema_patches)."""
    from app.models.orm import Plant

    db_path = tmp_path / "test.sqlite3"
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)

    # Simulate the "before this column existed" state, including a
    # pre-existing row, using raw SQL (the ORM model already expects the
    # column, so it can't be used to write to the old-shaped table).
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE plant DROP COLUMN nickname_is_custom")
        conn.exec_driver_sql("INSERT INTO room (name, sort_order) VALUES ('Kitchen', 0)")
        conn.exec_driver_sql(
            "INSERT INTO species (scientific_name, watering_interval_days, seasonal_profile, source, created_at) "
            "VALUES ('Basil', 4, 'temperate', 'manual', '2026-01-01 00:00:00')"
        )
        conn.exec_driver_sql(
            "INSERT INTO plant (nickname, species_id, room_id, photo_path, seasonal_adjust_enabled, created_at) "
            "VALUES ('Basil', 1, 1, 'p.jpg', 1, '2026-01-01 00:00:00')"
        )

    # Re-running init_db (as happens on every app startup) should add the
    # missing column back without losing the pre-existing row.
    init_db(engine)

    with session_scope(engine) as session:
        plant = session.query(Plant).filter_by(nickname="Basil").one()
        assert plant.nickname_is_custom is False


def test_should_backfill_climate_columns_on_pre_existing_room_table(tmp_path) -> None:
    """Simulates a real deployment's SQLite file created before the climate
    columns existed (CLIMATE_CADENCE_PLAN.md) — init_db must patch them in via
    ALTER TABLE, same as the nickname_is_custom backfill above."""
    from app.models.orm import Room

    db_path = tmp_path / "test.sqlite3"
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)

    with engine.begin() as conn:
        for column in (
            "temperature_entity_id",
            "humidity_entity_id",
            "climate_vpd_kpa",
            "climate_temp_c",
            "climate_humidity",
            "climate_updated_at",
        ):
            conn.exec_driver_sql(f"ALTER TABLE room DROP COLUMN {column}")
        conn.exec_driver_sql("INSERT INTO room (name, sort_order) VALUES ('Kitchen', 0)")

    init_db(engine)

    with session_scope(engine) as session:
        room = session.query(Room).filter_by(name="Kitchen").one()
        assert room.temperature_entity_id is None
        assert room.humidity_entity_id is None
        assert room.climate_vpd_kpa is None
        assert room.climate_updated_at is None
