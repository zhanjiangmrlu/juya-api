"""CI archives are selected by role, source commit and config identity, without Docker locally."""

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest


def script():
    path = Path(__file__).resolve().parents[1] / "deploy/write-image-artifact.py"
    spec = importlib.util.spec_from_file_location("image_artifact", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def image_archive(path, project="juya-admin-api", commit="a" * 40):
    config = json.dumps(
        {
            "os": "linux",
            "architecture": "amd64",
            "config": {
                "Labels": {
                    "org.opencontainers.image.title": project,
                    "org.opencontainers.image.revision": commit,
                }
            },
        }
    ).encode()
    digest = hashlib.sha256(config).hexdigest()
    entries = {
        digest + ".json": config,
        "manifest.json": json.dumps(
            [{"Config": digest + ".json", "RepoTags": [project + ":" + commit], "Layers": []}]
        ).encode(),
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, data in entries.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
    return "sha256:" + digest


def test_ci_image_manifest_matches_exact_role_commit_and_saved_bytes(tmp_path):
    archive = tmp_path / "image.tar.gz"
    identity = image_archive(archive)
    value = script().write_metadata(
        archive, "juya-admin-api", "a" * 40, "juya-admin-api:" + ("a" * 40), identity
    )
    assert value["image_id"] == identity
    assert value["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert json.loads((tmp_path / "image.json").read_text()) == value
    with pytest.raises(ValueError):
        script().write_metadata(
            archive, "juya-miniapp-api", "a" * 40, "juya-miniapp-api:" + ("a" * 40), identity
        )
    with pytest.raises(ValueError):
        script().write_metadata(
            archive, "juya-admin-api", "b" * 40, "juya-admin-api:" + ("b" * 40), identity
        )
    with pytest.raises(ValueError):
        script().write_metadata(
            archive,
            "juya-admin-api",
            "a" * 40,
            "juya-admin-api:" + ("a" * 40),
            "sha256:" + ("0" * 64),
        )
