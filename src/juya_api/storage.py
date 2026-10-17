"""Private object storage; no public or long-lived download URLs."""

import os
from pathlib import PurePosixPath

import alibabacloud_oss_v2 as oss  # type: ignore[import-untyped]

from .errors import DomainError


class ObjectStorage:
    def __init__(self, settings):
        self.settings = settings
        self.client = None
        if settings.storage_backend == "oss":
            self.client = oss.Client(
                oss.Config(
                    region=settings.oss_region,
                    endpoint=settings.oss_endpoint,
                    credentials_provider=oss.credentials.StaticCredentialsProvider(
                        settings.oss_access_key_id, settings.oss_access_key_secret
                    ),
                    connect_timeout=5,
                    readwrite_timeout=30,
                    retry_max_attempts=2,
                )
            )

    def path(self, key: str):
        """Reject untrusted path traversal even for internally stored object references."""
        path = PurePosixPath(key)
        if path.is_absolute() or ".." in path.parts or "\\" in key:
            raise DomainError(404, "media_missing", "素材不可用")
        return self.settings.media_root / key

    def put(self, key: str, data: bytes, content_type: str):
        """Store immutable content under a server-generated key."""
        if self.client:
            try:
                self.client.put_object(
                    oss.PutObjectRequest(
                        bucket=self.settings.oss_bucket,
                        key=key,
                        body=data,
                        content_type=content_type,
                        cache_control="no-store",
                        object_acl="private",
                    )
                )
            except Exception:
                raise DomainError(503, "storage_unavailable", "素材保存失败，请重试") from None
        else:
            path = self.path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".uploading")
            temporary.write_bytes(data)
            os.replace(temporary, path)

    def read(self, key: str) -> bytes:
        """Read bounded task input; public delivery uses streaming instead."""
        if self.client:
            try:
                response = self.client.get_object(
                    oss.GetObjectRequest(bucket=self.settings.oss_bucket, key=key)
                )
                try:
                    return response.body.read()
                finally:
                    response.body.close()
            except Exception:
                raise DomainError(503, "storage_unavailable", "素材暂不可用") from None
        try:
            return self.path(key).read_bytes()
        except FileNotFoundError:
            raise DomainError(404, "media_missing", "素材不可用") from None

    def stream(self, key: str, start: int, end: int):
        """Open the upstream before returning a response so storage failures stay typed."""
        try:
            if self.client:
                source = self.client.get_object(
                    oss.GetObjectRequest(
                        bucket=self.settings.oss_bucket,
                        key=key,
                        range_header=f"bytes={start}-{end}",
                    )
                ).body
            else:
                source = self.path(key).open("rb")
                source.seek(start)
        except Exception:
            raise DomainError(503, "storage_unavailable", "素材暂不可用") from None

        def chunks():
            remaining = end - start + 1
            try:
                while remaining > 0:
                    data = source.read(min(64 * 1024, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
            finally:
                source.close()

        return chunks()
