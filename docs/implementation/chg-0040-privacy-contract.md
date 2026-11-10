# CHG-0040 协议与独立统计许可契约

本轮只交付能力及隔离验收。真实分析接收始终关闭；没有SDK转发器或第三方上报接口，不以旧本地友盟选择视为新账号许可。

## 正式材料与必要登录

默认GET `/api/mini/v1/privacy/policies`返回`mode=legacy`、UTC `server_now`、空`documents`。原必要登录的`consent=true/consent_version`保持可用，旧同意仍只保存为wechat_login，不补记新协议。

`JUYA_PRIVACY_DOCUMENTS_PATH`可指向私有UTF-8 JSON文档列表，每项为`kind/version/title/content`；kind为terms、privacy、analytics。只有terms及privacy完整、版本非空且种类不重复时才进入published。analytics缺失时仍不允许统计。没有内置演示正文回退。正文匿名GET `/privacy/policies/{kind}?version=...`可读，缺失/旧版本404；服务只读取配置中的当前文档，不伪造历史全文。

published登录需要`agreement_confirmation`：confirmation_id、terms_version、privacy_version、client_confirmed_at、source。校验在微信兑换前执行；服务端accepted_at独立于客户端确认时间。可信身份兑换后，唯一账号/目的/确认编号安全关联同意记录。重复确认内容不一致409。旧字段保留用于兼容legacy；published不能只靠旧boolean取得当前同意。

登录可附`analytics_choice={enabled,scope_version}`。披露版本过期时仍完成有效必要登录，但统计保持关闭。登录幂等指纹冻结完整请求；未知结果不能换正文复用原键，应确认原结果后独立更新许可。

## 本人协议和许可

- GET `/me/privacy`：`agreements={current,accepted}`，accepted按terms/privacy列出version/accepted_at/source；`analytics={enabled,scope_version,revision,updated_at,collecting}`
- POST `/me/agreements`：当前协议确认，使用Idempotency-Key，返回agreements对象
- PUT `/me/analytics-preference`：`{enabled,scope_version,expected_revision}`加Idempotency-Key，直接返回analytics对象

许可按稳定账号保存，初值false/revision0。有效enabled要求当前统计披露匹配且必要协议仍有效；collecting本期恒false。关闭不要求当前披露，但仍校验本人、修订号和幂等键。每次新变更递增revision；同键重试返回原收据不重复更新，同键不同正文409。并发修订号过期返回analytics_revision_conflict，读取最新状态后重新确认再提交。单个请求的事务与账号锁隔离许可、事件及原业务操作。

## 五类事件

POST `/analytics/events`输入event_id、event、occurred_at、consent_revision、properties，可附仅用于服务端核实的operation_key。event仅允许page_enter/content_open/audio_play/favorite_change/learning_complete。客户端不能提交user_id。

实际构造的API中analytics_receiver固定None，接口鉴权后返回503/analytics_unavailable，不写事件数据，不存在通过环境变量开启的路径。隔离测试直接注入内存接收器，事件按可信账号/当前协议/统计版本/revision/时间范围校验，唯一账号+event_id去重，相同事件键不同正文409。事务提交后才通知内存接收器，接收器异常不改写已提交结果；operation_key不交接收器。该测试适配不代表友盟收数。

页面事件只接受注册页面白名单page_path，不含query或其他输入。其他事件只接受必要的content_type/content_id/version_id/audio_kind/favorite；音频种类full/word，收藏结果0/1。内容引用重新检查发布和学习权限。收藏/完成要求当前账号对应动作成功回执，且业务成功不早于当前许可开启时间；校验不会反向执行收藏、完成或变更成绩。

## 数据扩展与兼容

0027增加consents可空确认元数据和账号许可、事件收据两表，不迁移旧许可、不清理旧业务事实。迁移可重试，旧列集INSERT继续兼容，contract3不变；新代码最低schema27。回退部署兼容旧contract3代码，迁移不提供销毁同意历史的降级操作。实际迁移仅按本地/发布授权分别执行，本轮未操作原业务库或远程库。
