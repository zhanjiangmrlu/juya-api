# CHG0042 音频与学习笔记按需登录契约

2026-11-12，本地 test 实施；需求与用户已确认范围见 `docs/superpowers/specs/2026-11-12-chg0042-on-demand-resource-login-design.md`。无需数据库迁移，OpenAPI 响应字段与路由保持兼容。

## 免费图文与资源的边界

- 场景及听读列表、摘要、当前已发布免费详情继续匿名可读。`access.can_learn` 仍表示免费图文可学，不表示游客可以播放音频。已发布有效 PDF 的 `study_note` 元数据继续公开，以显示入口；没有公开 PDF URL。
- 场景 `/cards/{card_id}/media/{media_id}/url` 和听读 `/listening/articles/{article_id}/media-ticket` 按解析后的真实素材 kind 校验：只有 `image` / `thumbnail` 可给游客签发 public 票据；音频、播放衍生件、PDF 和发音等受保护类型需要可信 mini 登录。purpose 或客户端声称的素材类型不能替代服务端归属和实际 kind 校验。
- 听读 `/listening/articles/{article_id}/media/{media_id}` 的 GET / HEAD / Range 也对真实类型执行同样规则，不能绕过签发入口直接下载音频。
- 场景及听读预置词发音 POST、GET 在无身份时返回 401 / `unauthenticated`，拒绝发生在发音缓存、持久回执、供应商任务创建之前；不再使用游客服务 owner 创建任务。此前已接受的 legacy 服务 owner 任务仍能正常收敛，不清理历史数据。

## 错误与私有交付

新受保护入口缺少身份返回 401 / `unauthenticated`；显式提供无效、过期或跨角色凭证保留既有 401 / `login_required` 语义。小程序应处理两种 401。有效 mini 身份仍逐次检查当前免费、发布、版本及附件归属；非免费继续 403 / `content_not_open`。未发布、删除、版本变化和附件变化保留原有错误。

音频及预置发音继续使用有效 mini 会话绑定的短期私票据。原生播放器可不携带 Authorization，但每次 GET / HEAD / Range 都检查票据绑定的原会话仍有效及当前资源权限；显式携带 Authorization 时必须使用原 mini 会话的标准 Bearer 凭证，不能借其他账号或管理员身份兑换。PDF 保持既有规则：交付必须携带匹配原 mini 会话的 Authorization。退出、会话过期、免费关闭、下线、删除或版本更换后旧私票据不能再获取新资源。

## 旧 public 票据撤销

`/public/resources/{credential}` 不再兑换任何音频、PDF、预置发音；即使尚未到期或请求附带有效 mini 身份也返回 401 / `public_resource_expired`，必须重新走登录后私票据入口。`word` / `study_note` purpose 直接失效；其他 purpose 仍检查引用及最终解析素材的真实 kind，因此伪造 content / summary 也不能交付受保护素材。图片、原图、缩略图的旧 public 票据仍有效，并逐次复核当前免费、发布及版本规则。

## 权限缓存与恢复

两个模块的权限 `version` 均增加 `resource-login1` 策略段，与旧本地权限缓存隔离。学习授权和内置查词开关继续为 false；本轮不恢复授权访问或内置查词，不改变免费名单，不新增统计事件。

本轮只修改本地代码和隔离测试夹具；不推送、部署、上传微信或操作原业务库。回退应回退本轮代码提交并清理客户端受保护资源缓存；无数据库回滚或数据修复步骤。旧游客资源开放行为只有经新的产品授权后才可恢复。
