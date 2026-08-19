"""Tests for app.services.photo_storage: saving uploaded photos to disk."""

from app.services.photo_storage import save_upload


def test_should_save_bytes_and_return_relative_photo_id(tmp_path) -> None:
    photo_id = save_upload(tmp_path, original_filename="my photo.JPG", content=b"fake-bytes")

    assert photo_id.endswith(".jpg")
    saved_path = tmp_path / photo_id
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"fake-bytes"


def test_should_generate_unique_filenames_for_repeated_uploads(tmp_path) -> None:
    id1 = save_upload(tmp_path, original_filename="a.jpg", content=b"one")
    id2 = save_upload(tmp_path, original_filename="a.jpg", content=b"two")

    assert id1 != id2
    assert (tmp_path / id1).read_bytes() == b"one"
    assert (tmp_path / id2).read_bytes() == b"two"


def test_should_default_extension_when_filename_has_none(tmp_path) -> None:
    photo_id = save_upload(tmp_path, original_filename="upload", content=b"x")

    assert photo_id.endswith(".jpg")


def test_should_create_photos_dir_if_missing(tmp_path) -> None:
    nested = tmp_path / "nested" / "photos"

    save_upload(nested, original_filename="a.jpg", content=b"x")

    assert nested.is_dir()
