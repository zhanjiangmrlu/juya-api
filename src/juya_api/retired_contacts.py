"""Keep retired personal contact data out of legacy durable responses."""

from .errors import DomainError
from .response_contracts import UserProfile


def clean_profile_result(value: dict) -> dict:
    """仅返回历史资料快照中当前允许的字段；value 为解密后的本人资料"""
    return UserProfile.model_validate(value).model_dump()


def clean_login_result(value: dict) -> dict:
    """清理登录回执的用户快照；value 为包含原令牌的解密登录结果"""
    return {**value, "user": clean_profile_result(value["user"])}


def clean_operation_result(action: str, value: dict) -> dict:
    """按业务用途清理历史回执；action 为原动作，value 为解密结果"""
    if action == "contact.save":
        raise DomainError(410, "contact_collection_disabled", "联系方式收集功能已停用")
    return clean_profile_result(value) if action == "profile.save" else value
