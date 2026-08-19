"""Tests for app.services.thumbnails: lazy, disk-cached plant-photo
thumbnails — memory-friendliness hardening (see TODO.md)."""

import io

from PIL import Image

from app.services.thumbnails import get_or_create_thumbnail, thumbnail_filename, thumbnails_dir


def _make_photo(path, *, size=(800, 600), fmt="JPEG", mode="RGB") -> None:
    img = Image.new(mode, size, color="green")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    path.write_bytes(buf.getvalue())


def test_should_generate_and_cache_a_downscaled_thumbnail(tmp_path) -> None:
    photo_id = "abc123.jpg"
    _make_photo(tmp_path / photo_id, size=(1280, 960))

    thumb_path = get_or_create_thumbnail(tmp_path, photo_id)

    assert thumb_path is not None
    assert thumb_path.exists()
    assert thumb_path == thumbnails_dir(tmp_path) / thumbnail_filename(photo_id)
    with Image.open(thumb_path) as thumb:
        assert max(thumb.size) <= 160


def test_should_reuse_cached_thumbnail_on_second_call(tmp_path) -> None:
    photo_id = "abc123.jpg"
    _make_photo(tmp_path / photo_id)

    first = get_or_create_thumbnail(tmp_path, photo_id)
    first_mtime = first.stat().st_mtime_ns
    second = get_or_create_thumbnail(tmp_path, photo_id)

    assert second == first
    assert second.stat().st_mtime_ns == first_mtime


def test_should_not_upscale_an_already_small_photo(tmp_path) -> None:
    photo_id = "small.jpg"
    _make_photo(tmp_path / photo_id, size=(40, 30))

    thumb_path = get_or_create_thumbnail(tmp_path, photo_id)

    with Image.open(thumb_path) as thumb:
        assert thumb.size == (40, 30)


def test_should_force_jpeg_output_regardless_of_source_format(tmp_path) -> None:
    photo_id = "pic.png"
    _make_photo(tmp_path / photo_id, fmt="PNG", mode="RGBA")

    thumb_path = get_or_create_thumbnail(tmp_path, photo_id)

    assert thumb_path.suffix == ".jpg"
    with Image.open(thumb_path) as thumb:
        assert thumb.format == "JPEG"


def test_should_return_none_when_source_photo_missing(tmp_path) -> None:
    thumb_path = get_or_create_thumbnail(tmp_path, "does-not-exist.jpg")

    assert thumb_path is None


def test_should_return_none_when_source_is_not_a_decodable_image(tmp_path) -> None:
    photo_id = "corrupt.jpg"
    (tmp_path / photo_id).write_bytes(b"not-actually-a-jpeg")

    thumb_path = get_or_create_thumbnail(tmp_path, photo_id)

    assert thumb_path is None
