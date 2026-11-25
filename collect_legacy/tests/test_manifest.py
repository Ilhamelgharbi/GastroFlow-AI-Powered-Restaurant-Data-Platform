"""Fingerprint and manifest behaviour. Fill in once collect/manifest.py is written."""

import hashlib

import pytest

from collect.lib.manifest import Manifest, sha256_file


def test_sha256_is_stable_for_same_content(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_bytes(b"same content")
    second.write_bytes(b"same content")

    digest = hashlib.sha256(b"same content").hexdigest()
    assert sha256_file(first, chunk_size=3) == digest
    assert sha256_file(second, chunk_size=4) == digest

    second.write_bytes(b"changed content")
    assert sha256_file(second, chunk_size=4) != digest


def test_unchanged_file_is_detected(tmp_path):
    path = tmp_path / "logs" / "manifest.json"
    manifest = Manifest(path)
    manifest.record("orders", "digest-one")
    manifest.save()

    loaded = Manifest(path)
    assert loaded.is_unchanged("orders", "digest-one")
    assert not loaded.is_unchanged("orders", "digest-two")


def test_manifest_round_trip_preserves_metadata(tmp_path):
    path = tmp_path / "logs" / "manifest.json"
    manifest = Manifest(path)
    manifest.record(
        "orders",
        "abc123",
        bytes=42,
        gcs_uri="gs://bucket/raw/orders/orders.csv",
        run_id="20261123T101500Z",
    )
    manifest.save()

    loaded = Manifest(path)
    assert loaded.entries == manifest.entries
    assert loaded.entries["orders"]["uploaded_at"].endswith("Z")


def test_missing_manifest_starts_empty(tmp_path):
    manifest = Manifest(tmp_path / "missing.json")

    assert manifest.entries == {}


def test_corrupt_manifest_is_reported(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="must contain a JSON object"):
        Manifest(path)


def test_record_rejects_reserved_digest_metadata(tmp_path):
    manifest = Manifest(tmp_path / "manifest.json")

    with pytest.raises(ValueError, match="sha256.*reserved"):
        manifest.record("orders", "abc", sha256="override")
