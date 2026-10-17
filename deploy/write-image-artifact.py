"""Bind a CI image archive to its exact role, commit and immutable config ID."""

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


def write_metadata(archive, project, commit, image_ref, image_id):
    if (
        project not in ("juya-admin-api", "juya-miniapp-api")
        or not re.fullmatch(r"[a-f0-9]{40}", commit)
        or image_ref != project + ":" + commit
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id)
    ):
        raise ValueError("invalid image metadata")
    spec = importlib.util.spec_from_file_location(
        "image_identity", Path(__file__).with_name("image-identity.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    identity, labels = module.inspect_archive(archive, image_ref, image_id)
    if (
        labels.get("org.opencontainers.image.title") != project
        or labels.get("org.opencontainers.image.revision") != commit
    ):
        raise ValueError("image source labels mismatch")
    digest = hashlib.sha256()
    with Path(archive).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    value = {
        "schema_version": 1,
        "project": project,
        "commit": commit,
        "image_ref": image_ref,
        "image_id": identity,
        "archive_sha256": digest.hexdigest(),
    }
    Path(archive).with_name("image.json").write_text(
        json.dumps(value, indent=2) + "\n", encoding="utf-8"
    )
    return value


if __name__ == "__main__":
    try:
        if len(sys.argv) != 6:
            raise ValueError("archive, project, commit, tag and config ID required")
        write_metadata(*sys.argv[1:])
    except (ValueError, OSError):
        sys.exit("image artifact validation failed")
