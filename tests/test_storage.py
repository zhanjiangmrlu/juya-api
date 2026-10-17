"""Exercise the installed OSS SDK stream contract, including bounded delivery and close."""

import io
from types import SimpleNamespace

import pytest
import requests
from alibabacloud_oss_v2.io_utils import StreamBodyReader
from alibabacloud_oss_v2.transport.requests_client import _RequestsHttpResponseImpl

from juya_api.storage import ObjectStorage


@pytest.mark.parametrize("size", [100, 150000])
def test_oss_sdk_body_streams_bounded_chunks_and_closes(size):
    payload = b"x" * size
    response = requests.Response()
    response.raw = io.BytesIO(payload)
    body = StreamBodyReader(
        _RequestsHttpResponseImpl(request=None, block_size=8192, internal_response=response)
    )
    settings = SimpleNamespace(storage_backend="local", oss_bucket="unit-test-bucket")
    storage = ObjectStorage(settings)
    captured = []

    def get_object(request):
        captured.append(request)
        return SimpleNamespace(body=body)

    storage.client = SimpleNamespace(get_object=get_object)
    chunks = list(storage.stream("controlled/object", 7, size + 6))
    assert b"".join(chunks) == payload
    assert all(len(chunk) <= 65536 for chunk in chunks)
    assert captured[0].range_header == f"bytes=7-{size + 6}"
    assert body.is_closed


def test_oss_sdk_body_closes_when_consumer_stops_early():
    response = requests.Response()
    response.raw = io.BytesIO(b"x" * 150000)
    body = StreamBodyReader(
        _RequestsHttpResponseImpl(request=None, block_size=8192, internal_response=response)
    )
    storage = ObjectStorage(SimpleNamespace(storage_backend="local", oss_bucket="unit-test"))
    storage.client = SimpleNamespace(get_object=lambda request: SimpleNamespace(body=body))
    stream = storage.stream("controlled/object", 0, 149999)
    assert len(next(stream)) <= 65536
    stream.close()
    assert body.is_closed
