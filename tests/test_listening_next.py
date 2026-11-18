"""听读下一篇的冻结队列、免费优先与当前权限回归"""

import pytest
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from tests.test_integration06 import A, M, article, category, free, publish
from tests.test_learning_access import change, user_id
from tests.test_listening import post


def next_response(mini, article_id, token, method, *, headers=None):
    """按 method 使用旧查询参数或新请求体传递 article_id 的冻结 token，headers 用于身份覆盖"""
    return mini.request(
        method,
        M + f"/articles/{article_id}/next",
        **(
            {"params": {"queue_token": token}}
            if method == "GET"
            else {"json": {"queue_token": token}}
        ),
        headers=headers,
    )


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.usefixtures("legacy_learning_features")
def test_next_queue_uses_free_first_order_without_changing_admin_order(admin, mini, method):
    """学习队列应与免费优先列表一致，并保留管理端的组内排序"""
    owner = category(admin)
    locked, first, following = [publish(admin, article(admin, owner["id"])) for _ in range(3)]
    free(admin, first)
    free(admin, following)
    change(admin, user_id(mini), "grant")
    detail = mini.get(M + f"/articles/{following['id']}").json()
    response = next_response(mini, following["id"], detail["queue_token"], method)
    assert response.status_code == 200, response.text
    assert response.json()["article"] is not None
    assert response.json()["article"]["id"] == locked["id"]
    assert mini.get(M + f"/articles/{following['id']}/next").json()["article"]["id"] == locked["id"]
    order = admin.get(A + "/order", params={"scope": "category", "category_id": owner["id"]})
    assert order.json()["article_ids"] == [locked["id"], first["id"], following["id"]]


@pytest.mark.parametrize("grant_active", [False, True])
@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.usefixtures("legacy_learning_features")
def test_frozen_next_rechecks_access_and_skips_locked_article(admin, mini, grant_active, method):
    """冻结顺序内后续免费资格变化后，逐篇复核权限，不扩权也不漏掉可读文章"""
    owner = category(admin)
    first, middle, following = [publish(admin, article(admin, owner["id"])) for _ in range(3)]
    for row in (first, middle, following):
        free(admin, row)
    token = mini.get(M + f"/articles/{first['id']}").json()["queue_token"]
    free(admin, middle, False)
    if grant_active:
        change(admin, user_id(mini), "grant")
    post(mini, M + f"/articles/{first['id']}/complete", {"version_id": first["version_id"]})
    # 普通下一篇允许复习已完成文章，首页继续学习才排除已完成
    post(
        mini,
        M + f"/articles/{following['id']}/complete",
        {"version_id": following["version_id"]},
    )
    response = next_response(mini, first["id"], token, method)
    assert response.status_code == 200, response.text
    expected = middle if grant_active else following
    assert response.json()["article"]["id"] == expected["id"]
    assert response.json()["ended"] is False
    assert mini.get(M + f"/articles/{middle['id']}").status_code == (200 if grant_active else 403)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_next_ends_without_wrapping_or_crossing_category(admin, mini, method):
    """本分类后续全部受限时正常结束，不回绕也不跨分类寻找免费文章"""
    owner = category(admin)
    first, locked = [publish(admin, article(admin, owner["id"])) for _ in range(2)]
    other = publish(admin, article(admin, category(admin, "其他")["id"]))
    free(admin, first)
    free(admin, other)
    token = mini.get(M + f"/articles/{first['id']}").json()["queue_token"]
    response = next_response(mini, first["id"], token, method)
    assert response.status_code == 200, response.text
    assert response.json() == {"article": None, "ended": True, "category_id": owner["id"]}
    assert mini.get(M + f"/articles/{locked['id']}").status_code == 403


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_next_queue_cannot_be_reused_by_another_user(admin, mini, system, method):
    """队列凭证仍绑定签发账号，不能用来绕过另一用户的访问检查"""
    first = publish(admin, article(admin, category(admin)["id"]))
    free(admin, first)
    token = mini.get(M + f"/articles/{first['id']}").json()["queue_token"]
    login = system["mini"].post(
        "/api/mini/v1/auth/wechat",
        json={"code": "bob:first", "consent_version": "2026-10-17", "consent": True},
        headers={"Idempotency-Key": "login-bob-listening-next-0001"},
    )
    assert login.status_code == 200, login.text
    response = next_response(
        mini,
        first["id"],
        token,
        method,
        headers={"Authorization": "Bearer " + login.json()["access_token"]},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "access_preview_expired"


def test_large_category_next_passes_request_line_limit_without_writing_completion(
    admin, mini, system
):
    """真实大分类凭据走正文，在 8KB 请求行网关后可连续读取且不新增学习完成事实"""
    from uuid import uuid4

    from sqlalchemy import func, select

    from juya_api.listening_models import ListeningArticle, ListeningCompletion

    owner = category(admin)
    first, following = [publish(admin, article(admin, owner["id"])) for _ in range(2)]
    for row in (first, following):
        free(admin, row)
    with system["sessions"].begin() as db:
        db.add_all(
            [
                ListeningArticle(id=str(uuid4()), category_id=owner["id"], payload={})
                for _ in range(400)
            ]
        )
    token = mini.get(M + f"/articles/{first['id']}").json()["queue_token"]
    assert len(token) > 8192

    async def gateway(scope, receive, send):
        """模拟生产网关请求行长度约束，scope/receive/send 为真实 ASGI 请求端口"""
        if len(scope.get("raw_path", b"") + scope.get("query_string", b"")) > 8192:
            await JSONResponse({}, status_code=414)(scope, receive, send)
        else:
            await mini.app(scope, receive, send)

    with TestClient(gateway, base_url="https://testserver", headers=dict(mini.headers)) as client:
        assert next_response(client, first["id"], token, "GET").status_code == 414
        for _ in range(2):
            response = next_response(client, first["id"], token, "POST")
            assert response.status_code == 200, response.text
            assert response.json()["article"]["id"] == following["id"]
            assert response.json()["ended"] is False
        assert next_response(client, following["id"], token, "POST").json()["ended"] is True
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(ListeningCompletion)) == 0


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("invalid", ["tampered", "expired", "category_changed"])
def test_next_rejects_invalid_queue(admin, mini, system, method, invalid):
    """method 两种传输方式均拒绝 invalid 指定的篡改、过期或跨分类队列"""
    from datetime import timedelta

    from juya_api.listening_models import ListeningArticle

    first = publish(admin, article(admin, category(admin)["id"]))
    free(admin, first)
    token = mini.get(M + f"/articles/{first['id']}").json()["queue_token"]
    if invalid == "tampered":
        token = "invalid-" + token
    elif invalid == "expired":
        system["time"][0] += timedelta(days=2)
    else:
        other = category(admin, "其他")
        with system["sessions"].begin() as db:
            db.get(ListeningArticle, first["id"]).category_id = other["id"]
    response = next_response(mini, first["id"], token, method)
    assert response.status_code == 409, response.text
    expected = (
        "listening_queue_changed" if invalid == "category_changed" else "access_preview_expired"
    )
    assert response.json()["error"]["code"] == expected


def test_next_body_requires_learner_and_valid_input(mini, system):
    """新只读 POST 仍需要学习账号，且拒绝非字符串队列正文"""
    path = M + "/articles/missing-article/next"
    assert system["mini"].post(path, json={}, headers={"Authorization": ""}).status_code == 401
    assert mini.post(path, json={"queue_token": []}).status_code == 422
