"""Tests for app.routers.photos: serving lazily-generated plant-photo
thumbnails, falling back to the full photo when needed — memory-friendliness
hardening (see TODO.md)."""

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings


def _make_photo(path: Path, *, size=(800, 600)) -> None:
    img = Image.new("RGB", size, color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())


def test_should_serve_a_downscaled_thumbnail_for_an_existing_photo(client: TestClient, settings: Settings) -> None:
    photos_dir = Path(settings.photos_dir)
    _make_photo(photos_dir / "plant.jpg", size=(1280, 960))

    response = client.get("/photos/thumbnails/plant.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(response.content)) as img:
        assert max(img.size) <= 160


def test_should_404_when_the_original_photo_does_not_exist(client: TestClient) -> None:
    response = client.get("/photos/thumbnails/nope.jpg")

    assert response.status_code == 404


def test_should_reject_path_traversal_attempts(client: TestClient, settings: Settings) -> None:
    secret = Path(settings.photos_dir).parent / "secret.txt"
    secret.write_text("do not serve me")

    response = client.get("/photos/thumbnails/..%2Fsecret.txt")

    assert response.status_code == 404


def test_should_fall_back_to_the_full_photo_when_thumbnail_generation_fails(
    client: TestClient, settings: Settings
) -> None:
    photos_dir = Path(settings.photos_dir)
    photos_dir.mkdir(parents=True, exist_ok=True)
    (photos_dir / "corrupt.jpg").write_bytes(b"not-actually-a-jpeg")

    response = client.get("/photos/thumbnails/corrupt.jpg")

    assert response.status_code == 200
    assert response.content == b"not-actually-a-jpeg"
