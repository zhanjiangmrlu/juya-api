"""The real HTTPS boundary must distinguish a final allow from every other outcome."""

import httpx
import pytest


@pytest.mark.parametrize(
    "decision,status",
    [
        ("allow", None),
        ("reject", 422),
        ("review", 503),
        ("pending", 503),
        ("unknown", 503),
        (None, 503),
    ],
)
def test_https_safety_accepts_only_final_allow(system, decision, status):
    from juya_api.errors import DomainError
    from juya_api.feedback_safety import FeedbackSafetyGateway

    settings = system["settings"].model_copy(
        update={
            "feedback_safety_url": "https://checks.example.test/v1",
            "feedback_safety_token": "test-gateway-token",
        }
    )

    def upstream(request):
        assert request.url.host == "checks.example.test"
        assert request.headers["Authorization"] == "Bearer test-gateway-token"
        return httpx.Response(200, json={"decision": decision})

    with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
        gateway = FeedbackSafetyGateway(settings, client=client)
        for check in [
            lambda: gateway.check_text("说明", "opaque-operation-id"),
            lambda: gateway.check_image(b"normalized-image", "image/webp", "opaque-image-id"),
        ]:
            if status is None:
                check()
            else:
                with pytest.raises(DomainError) as error:
                    check()
                assert error.value.status == status


def test_safety_unconfigured_plain_http_redirect_timeout_and_malformed_all_fail_closed(system):
    from juya_api.errors import DomainError
    from juya_api.feedback_safety import FeedbackSafetyGateway

    for url in ["", "http://checks.example.test"]:
        gateway = FeedbackSafetyGateway(
            system["settings"].model_copy(
                update={"feedback_safety_url": url, "feedback_safety_token": "test"}
            )
        )
        with pytest.raises(DomainError, match="content_safety_unavailable"):
            gateway.check_text("说明", "opaque")

    def timeout(request):
        raise httpx.ReadTimeout("unavailable", request=request)

    for handler in [
        lambda _: httpx.Response(302, headers={"Location": "https://other.example.test"}),
        lambda _: httpx.Response(200, text="not json"),
        timeout,
    ]:
        settings = system["settings"].model_copy(
            update={
                "feedback_safety_url": "https://checks.example.test",
                "feedback_safety_token": "test",
            }
        )
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            gateway = FeedbackSafetyGateway(settings, client=client)
            with pytest.raises(DomainError, match="content_safety_unavailable"):
                gateway.check_text("说明", "opaque")
