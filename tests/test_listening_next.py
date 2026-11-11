"""听读下一篇的冻结队列、免费优先与当前权限回归"""

import pytest

from tests.test_integration06 import A, M, article, category, free, publish
from tests.test_learning_access import change, user_id
from tests.test_listening import post


@pytest.mark.usefixtures("legacy_learning_features")
def test_next_queue_uses_free_first_order_without_changing_admin_order(admin, mini):
    """学习队列应与免费优先列表一致，并保留管理端的组内排序"""
    owner = category(admin)
    locked, first, following = [publish(admin, article(admin, owner["id"])) for _ in range(3)]
    free(admin, first)
    free(admin, following)
    change(admin, user_id(mini), "grant")
    detail = mini.get(M + f"/articles/{following['id']}").json()
    response = mini.get(
        M + f"/articles/{following['id']}/next", params={"queue_token": detail["queue_token"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["article"] is not None
    assert response.json()["article"]["id"] == locked["id"]
    assert mini.get(M + f"/articles/{following['id']}/next").json()["article"]["id"] == locked["id"]
    order = admin.get(A + "/order", params={"scope": "category", "category_id": owner["id"]})
    assert order.json()["article_ids"] == [locked["id"], first["id"], following["id"]]


@pytest.mark.parametrize("grant_active", [False, True])
@pytest.mark.usefixtures("legacy_learning_features")
def test_frozen_next_rechecks_access_and_skips_locked_article(admin, mini, grant_active):
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
    response = mini.get(M + f"/articles/{first['id']}/next", params={"queue_token": token})
    assert response.status_code == 200, response.text
    expected = middle if grant_active else following
    assert response.json()["article"]["id"] == expected["id"]
    assert response.json()["ended"] is False
    assert mini.get(M + f"/articles/{middle['id']}").status_code == (200 if grant_active else 403)


def test_next_ends_without_wrapping_or_crossing_category(admin, mini):
    """本分类后续全部受限时正常结束，不回绕也不跨分类寻找免费文章"""
    owner = category(admin)
    first, locked = [publish(admin, article(admin, owner["id"])) for _ in range(2)]
    other = publish(admin, article(admin, category(admin, "其他")["id"]))
    free(admin, first)
    free(admin, other)
    token = mini.get(M + f"/articles/{first['id']}").json()["queue_token"]
    response = mini.get(M + f"/articles/{first['id']}/next", params={"queue_token": token})
    assert response.status_code == 200, response.text
    assert response.json() == {"article": None, "ended": True, "category_id": owner["id"]}
    assert mini.get(M + f"/articles/{locked['id']}").status_code == 403


def test_next_queue_cannot_be_reused_by_another_user(admin, mini, system):
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
    response = mini.get(
        M + f"/articles/{first['id']}/next",
        params={"queue_token": token},
        headers={"Authorization": "Bearer " + login.json()["access_token"]},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "access_preview_expired"
