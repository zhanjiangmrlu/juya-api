# 整合08游客内容与资源接入

本轮复用整合07读取路径和 schema0026 / contract3；没有迁移，也没有游客账号或匿名个人记录。完整需求定位见 `docs/superpowers/plans/2026-11-07-integration08-guest.md`。本文件说明实际API兼容决定，前端类型以本轮 `openapi/mini.json` 生成结果为准。

## 身份和错误

公共读取不传 `Authorization` 即为游客。非空凭据必须为有效的 `Authorization: Bearer mini_…`；错误角色、格式、已退出或过期会话均返回401，不静默降级。客户端清理个人态后，可以对公共GET再匿名读一次；不得匿名重放写操作。公共资源票据自身是300秒的独立能力凭证，下载不要求会话。

本人资料、统计、状态、阅读同步、来源队列、完成、收藏、打卡、反馈和账号操作继续强鉴权。正文 dictionary 和正文点词发音继续要求本人会话及有效学习授权；免费和登录本身都不会赋予点词授权。个人历史摘要只向真实收藏/完成归属人开放。

## 既有内容路径

| 路径 | 游客行为 |
| --- | --- |
| `GET /api/mini/v1/cards` | 当前发布列表；默认及显式 `scope=uncompleted` 均按全部发布集合。保留免费优先、人工顺序、分页；`has_study_note=true` 在SQL分页前过滤当前有效发布PDF。 |
| `GET /api/mini/v1/cards/{id}` | 当前免费正文；受限403。`version_id` 仍拒绝旧版本，`require_study_note=true` 仍重验有效PDF。游客任何 `mark_started` 都不写 ReadingStart。 |
| `GET /api/mini/v1/cards/{id}/summary` | 当前发布安全摘要，受限也可；下线/删除仅原本人历史可读。无正文、词汇原句、PDF元信息和完整资源地址。 |
| `GET /api/mini/v1/listening/home` | 当前分类聚合及安全缩略图；没有个人统计和继续学习目标。 |
| `GET /api/mini/v1/listening/topics` | 兼容旧主题到分类映射；没有个人完成数。 |
| `GET /api/mini/v1/listening/articles` | 全部或 `category_id` 发布列表，排序/分页沿用；旧 `/topics/{id}/articles` 同样支持游客。 |
| `GET /api/mini/v1/listening/articles/{id}` | 当前免费正文；受限403；不建立服务器队列。 |
| `GET /api/mini/v1/listening/articles/{id}/summary` | 当前发布安全摘要，受限也可；不可公开历史、草稿、正文或预置词汇原句。 |

已有分享路径继续返回显示摘要和受控分享图片。分享不创建账号或学习记录。

个人字段表示：游客场景列表/详情/摘要 `state=null`；场景列表 `learning_access.authorization=null`、`free_uncompleted_total=null`；阅读位置 `reading_position=null`。游客听读 `state=null`、`progress=null`、`queue_token=null`；首页 `authorization=null`、`statistics=null`、`continue_learning=null`；分类/主题 `completed_articles=null`。访问判定 `access` 保留，免费时 `can_learn=true`、`can_lookup=false`，受限时 `can_learn=false`。客户端不能用零/false伪装本人已学情况。已登录请求继续返回真实个人对象/数值和既有授权语义。

## 图片、音频及PDF

场景仍用 `GET /api/mini/v1/cards/{card_id}/media/{media_id}/url`：

- `purpose=content&version_id=…`：当前免费正文音频/原图/缩略图，仅允许当前正文绑定的素材。
- `purpose=summary&version_id=…`：当前发布缩略图，受限也可；原图、音频、PDF不能用于摘要。
- `purpose=study_note&study_note_version_id=…`：当前免费、有效独立PDF版本；可同时传当前正文 `version_id`。正文detail的 `study_note.version_id/media_id` 是受控定位值。

听读继续用 `POST /api/mini/v1/listening/articles/{id}/media-ticket`，body `{version_id, media_id}`，保留 `Idempotency-Key` 长度16—128的既有要求；该接口不生成个人Operation。`GET …/{id}/thumbnail-ticket?version_id=…` 只签发发布缩略图，受限也可。原直接 Bearer 媒体和缩略图读取路径也支持匿名免费/安全缩略图，校验仍在服务端。

匿名签发统一返回 `{url, expires_at}`，URL为 `/api/mini/v1/public/resources/pub1_…`；有效期恰好300秒，内部用途和格式独立白名单，绑定scene/listening、内容ID、正文版本、素材，PDF另绑独立note版本，预置发音另绑word/cache引用。客户端按URL区分公开票据；不要解析加密内容，不要持久缓存。GET、HEAD、Range全部重新校验当前发布、未删除、免费标记和版本，`Cache-Control: no-store`。免费关闭、下线、删除、版本撤换或PDF撤换即拒绝旧地址；过期401，权限403，版本变动409，内容失效按原404/410。

已登录签发仍走原私有票据格式，不会自动转公开。原场景私有PDF下载仍必须发送**签发同一会话**Bearer；其他会话或不传Bearer均401。public PDF下载不加Authorization。私有票据失败禁止替换前缀或回退公开：如需继续游客免费体验，必须通过公共内容重新确认权限并重新签发。绝不返回永久存储地址。

## 预置词汇发音

复用 `GET/POST /api/mini/v1/cards/{id}/words/{word_id}/pronunciation` 和 `GET/POST /api/mini/v1/listening/articles/{id}/words/{word_id}/pronunciation`。GET query或POST body只使用 `{version_id}`；POST沿用 `Idempotency-Key`。不允许客户端提交文本、正文位置或草稿revision；当前已发布免费内容中的真实word_id才可使用。受限403，伪造word404，旧版本409，额外字段422。

响应沿用 `{state, job_id, error_code, url, retry_after}`：GET不启动任务；POST在共享 Pronunciation 缓存缺失时进入 processing，复用原去重、预算、失败冷却和任务租约。游客任务通过现有mini-worker执行 `tts.synthesize`，owner_kind=`mini`、owner_id=`public-pronunciation`，无需User或个人Operation。已登录用户可复用同一缓存。ready时url为上述public资源地址，GET/HEAD/Range再次验证当前免费、正文版本和预置词条；云词库/真实云TTS验收仍须单独进行，合成测试Provider不代表云服务通过。

## 前端行为约束

游客阅读位置、译文开关和倍速仅当前内存会话；不要调用本人进度/队列/统计接口。登录后重读真实权限与本人数据，不自动播放、打开PDF、收藏、完成、打卡，也不迁移游客进度。401仅公共GET匿名重查一次，不能重放POST。退出/过期/切换账号按身份代际丢弃迟到请求、播放器和本地PDF。匿名PDF的本地文件至少按游客代际+卡片+note版本隔离，已登录文件按账号+卡片+note版本隔离。
