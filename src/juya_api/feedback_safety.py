"""Real HTTPS content-safety boundary; only a final explicit allow may proceed."""

from urllib.parse import urlsplit

import httpx

from .errors import DomainError


class FeedbackSafetyGateway:
    def __init__(self, settings, *, client=None):
        self.settings, self.client = settings, client

    def _check(self, kind, **payload):
        endpoint = self.settings.feedback_safety_url.rstrip("/")
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not self.settings.feedback_safety_token
        ):
            raise DomainError(
                503, "content_safety_unavailable", "内容安全检查暂不可用，请保留输入后重试"
            )
        headers = {"Authorization": "Bearer " + self.settings.feedback_safety_token}
        try:
            if self.client is None:
                with httpx.Client(timeout=10, follow_redirects=False) as client:
                    response = client.post(endpoint + "/" + kind, headers=headers, **payload)
            else:
                response = self.client.post(
                    endpoint + "/" + kind,
                    headers=headers,
                    timeout=10,
                    follow_redirects=False,
                    **payload,
                )
            if response.status_code != 200:
                raise ValueError("incomplete check")
            result = response.json()
            decision = result.get("decision") if isinstance(result, dict) else None
        except (httpx.HTTPError, ValueError, TypeError):
            raise DomainError(
                503, "content_safety_unavailable", "内容安全检查暂不可用，请保留输入后重试"
            ) from None
        if decision == "reject":
            raise DomainError(422, "content_rejected", "内容未通过安全检查，请修改后重试")
        if decision != "allow":
            raise DomainError(
                503, "content_safety_unavailable", "内容安全检查尚未完成，请保留输入后重试"
            )

    def check_text(self, text: str, correlation_id: str):
        self._check("text", json={"correlation_id": correlation_id, "content": text})

    def check_image(self, data: bytes, content_type: str, correlation_id: str):
        self._check(
            "image",
            files={"file": ("screenshot", data, content_type)},
            data={"correlation_id": correlation_id},
        )
