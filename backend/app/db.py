"""Database engine/session helpers: SQLite WAL mode, bootstrap, scoped sessions."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.models.orm import Base


def create_db_engine(url: str) -> Engine:
    """Create a SQLAlchemy engine. For file-based SQLite, ensures the parent
    directory exists and turns on WAL mode (better concurrent read/write for
    the scheduler + web requests hitting the same file)."""
    if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
        db_file = url.removeprefix("sqlite:///")
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    _apply_schema_patches(engine)


def _apply_schema_patches(engine: Engine) -> None:
    """This project deliberately has no Alembic/migrations framework (see
    app.services.thumbnails' comment on backfill-free design) — `create_all`
    only creates missing *tables*, never new columns on ones that already
    exist. Columns added to the ORM after the initial deploy need a targeted,
    idempotent `ALTER TABLE` here instead, so already-provisioned SQLite
    files (real deployments, not just fresh test databases) pick them up."""
    inspector = inspect(engine)
    if "plant" in inspector.get_table_names():
        existing_plant_columns = {col["name"] for col in inspector.get_columns("plant")}
        if "nickname_is_custom" not in existing_plant_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE plant ADD COLUMN nickname_is_custom BOOLEAN NOT NULL DEFAULT 0"))

    if "room" in inspector.get_table_names():
        existing_room_columns = {col["name"] for col in inspector.get_columns("room")}
        room_column_ddl = {
            "temperature_entity_id": "VARCHAR",
            "humidity_entity_id": "VARCHAR",
            "climate_vpd_kpa": "FLOAT",
            "climate_temp_c": "FLOAT",
            "climate_humidity": "FLOAT",
            "climate_updated_at": "DATETIME",
        }
        for column_name, ddl_type in room_column_ddl.items():
            if column_name not in existing_room_columns:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE room ADD COLUMN {column_name} {ddl_type}"))

    if "species" in inspector.get_table_names():
        existing_species_columns = {col["name"] for col in inspector.get_columns("species")}
        if "care_language" not in existing_species_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE species ADD COLUMN care_language VARCHAR"))
        if "common_name_language" not in existing_species_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE species ADD COLUMN common_name_language VARCHAR"))

    if "species_common_name" in inspector.get_table_names() and "species" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT OR IGNORE INTO species_common_name (species_id, language, common_name)
                    SELECT id, COALESCE(common_name_language, care_language, 'en'), common_name
                    FROM species
                    WHERE common_name IS NOT NULL
                    """
                )
            )

    if "species_care_text" in inspector.get_table_names() and "species" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT OR IGNORE INTO species_care_text (species_id, language, light, soil, notes)
                    SELECT id, COALESCE(care_language, 'en'), light, soil, notes
                    FROM species
                    WHERE light IS NOT NULL OR soil IS NOT NULL OR notes IS NOT NULL
                    """
                )
            )


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Provide a transactional session: commits on success, rolls back on
    exception, always closes."""
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine)
