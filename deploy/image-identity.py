"""Inspect a single Docker save archive without extracting or invoking Docker."""

import hashlib
import json
import re
import sys
import tarfile
from pathlib import PurePosixPath


def inspect_archive(path, image, expected=None):
    metadata = {}
    total = 0
    seen = set()
    try:
        with tarfile.open(path, "r|*") as archive:
            for member in archive:
                name = member.name.rstrip("/")
                relative = PurePosixPath(name)
                if (
                    not name
                    or "\\" in name
                    or relative.is_absolute()
                    or any(part in (".", "..", "") for part in name.split("/"))
                    or name in seen
                    or len(seen) >= 100_000
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("unsafe image archive entry")
                seen.add(name)
                if (
                    member.isfile()
                    and member.size <= 1024 * 1024
                    and (name.endswith(".json") or name.startswith("blobs/sha256/"))
                ):
                    total += member.size
                    if total > 32 * 1024 * 1024:
                        raise ValueError("image metadata exceeds safe limit")
                    metadata[name] = archive.extractfile(member).read()
        records = json.loads(metadata["manifest.json"])
        if len(records) != 1 or records[0].get("RepoTags") != [image]:
            raise ValueError("image archive tag mismatch")
        config_path = records[0]["Config"]
        raw = metadata[config_path]
        digest = hashlib.sha256(raw).hexdigest()
        identity = "sha256:" + digest
        if config_path not in (digest + ".json", "blobs/sha256/" + digest):
            raise ValueError("image config digest mismatch")
        config = json.loads(raw)
        if (config.get("os"), config.get("architecture")) != ("linux", "amd64"):
            raise ValueError("image must target Linux/amd64")
        if expected is not None and identity != expected:
            raise ValueError("image identity mismatch")
        return identity, config.get("config", {}).get("Labels", {})
    except (OSError, KeyError, TypeError, AttributeError, tarfile.TarError) as error:
        raise ValueError("image archive identity verification failed") from error


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3 or not re.fullmatch(r"[a-z0-9._-]+:[a-f0-9]{40}", sys.argv[2]):
            raise ValueError("archive path and immutable image tag required")
        print(inspect_archive(sys.argv[1], sys.argv[2])[0])
    except ValueError:
        sys.exit("image archive identity verification failed")
