"""Explicit protocol and analysis consent inputs, independent from credentials."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PrivacyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgreementConfirmation(PrivacyInput):
    confirmation_id: str = Field(min_length=16, max_length=64, title="协议确认标识")
    terms_version: str = Field(min_length=1, max_length=64, title="用户协议版本")
    privacy_version: str = Field(min_length=1, max_length=64, title="隐私指引版本")
    client_confirmed_at: datetime = Field(title="客户端明确确认时间")
    source: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$", title="确认来源")


class AnalyticsChoice(PrivacyInput):
    enabled: bool = Field(title="是否明确允许统计")
    scope_version: str = Field(max_length=64, title="统计披露版本")


class AnalyticsPreferenceInput(AnalyticsChoice):
    expected_revision: int = Field(ge=0, title="预期许可修订号")


class AnalyticsEventInput(PrivacyInput):
    event_id: str = Field(min_length=16, max_length=64, title="唯一事件标识")
    event: Literal[
        "page_enter", "content_open", "audio_play", "favorite_change", "learning_complete"
    ] = Field(title="统计事件类型")
    occurred_at: datetime = Field(title="事件发生时间")
    consent_revision: int = Field(ge=1, title="事件对应的许可修订号")
    properties: dict[str, str | int | float] = Field(
        default_factory=dict,
        max_length=8,
        title="必要事件引用",
        description="仅接受页面、内容及结果等白名单引用，不接受用户输入或身份凭据。",
    )
    operation_key: str | None = Field(
        default=None, min_length=16, max_length=128, title="业务成功回执键"
    )


class PolicyDocument(BaseModel):
    model_config = ConfigDict(title="已发布正式协议正文")
    kind: Literal["terms", "privacy", "analytics"] = Field(
        title="协议种类", description="用户协议、隐私指引或统计披露。"
    )
    version: str = Field(title="正文版本", description="实际发布的正文版本标识。")
    title: str = Field(title="正文标题", description="向用户展示的正式文档标题。")
    content: str = Field(title="正式正文", description="供匿名阅读的已发布全文，不包含演示替代稿。")


class PolicyCatalog(BaseModel):
    model_config = ConfigDict(title="公开协议目录")
    analytics_available: bool = Field(
        default=False,
        title="测试统计授权是否可用",
        description="仅完整披露且显式启用测试客户端SDK授权时为true；不代表当前设备已开始采集。",
    )
    mode: Literal["legacy", "published"] = Field(
        title="协议运行模式", description="材料不完整时保持legacy必要登录，不启用新协议确认。"
    )
    server_now: str = Field(
        title="服务端当前时间", description="服务端UTC时间，用于北京时间告知日期换算。"
    )
    documents: list[PolicyDocument] = Field(
        title="已发布文档", description="完整发布的文档列表；未配置时为空。"
    )


class AcceptedAgreement(BaseModel):
    model_config = ConfigDict(title="本人已确认协议")
    version: str = Field(title="已确认版本", description="用户明确接受的协议版本。")
    accepted_at: str = Field(title="服务端接受时间", description="服务端保存明确确认的时间。")
    source: str | None = Field(title="确认来源", description="明确确认发生的产品入口。")


class AgreementState(BaseModel):
    model_config = ConfigDict(title="本人协议确认状态")
    current: bool = Field(
        title="当前版本已确认", description="本人已确认当前发布的用户协议及隐私指引。"
    )
    accepted: dict[str, AcceptedAgreement] = Field(
        title="已确认记录", description="按协议种类列出本人确认记录。"
    )


class AnalyticsPreferenceView(BaseModel):
    model_config = ConfigDict(title="本人可选统计许可")
    enabled: bool = Field(
        title="当前有效许可", description="仅表示账号已明确同意当前统计范围，不代表采集运行。"
    )
    scope_version: str = Field(title="统计范围版本", description="账号最近允许的统计披露版本。")
    revision: int = Field(title="许可修订号", description="当前许可的并发更新和事件代次。")
    updated_at: str | None = Field(
        title="最后更新时间", description="最近一次许可变更的服务端时间；尚未设置为空。"
    )
    collecting: bool | None = Field(
        title="客户端采集运行状态",
        description="无许可或通道关闭为false；已获许可的客户端SDK运行状态服务端无法推断，返回null，由本机真实SDK状态展示。",
    )


class PrivacyState(BaseModel):
    model_config = ConfigDict(title="本人隐私状态")
    agreements: AgreementState = Field(
        title="本人协议状态", description="独立于会话的正式协议确认记录。"
    )
    analytics: AnalyticsPreferenceView = Field(
        title="独立统计许可", description="账号统计选择及实际采集运行状态。"
    )


class AnalyticsEventReceiptView(BaseModel):
    model_config = ConfigDict(title="事件接收收据")
    event_id: str = Field(title="事件标识", description="本次成功接收及去重的事件标识。")
    accepted: Literal[True] = Field(
        title="已接收", description="已在有效许可范围内持久接收；不表示友盟真实接收。"
    )
