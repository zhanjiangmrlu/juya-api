# 第三批：问题反馈与持续沟通契约

2026-10-22，整合03／修订15第33章、T169—T178。迁移0015，两个API健康最低版本0015。小程序／后台继续独立鉴权，所有写操作使用现有Idempotency-Key（16—128字符）；后台写另需CSRF。

## 类型

- FeedbackCategory = content | pronunciation | display | function
- FeedbackStatus = pending | processing | needs_info | resolved
- FeedbackImage = `{id,state:'ready',url,content_type,width,height,size}`
- FeedbackEvent = `{id:int,actor:'user'|'admin',text:null|string,status:null|FeedbackStatus,images:FeedbackImage[],created_at}`
- FeedbackDetail = `{id,user_id,category,status,summary,source:'profile'|'scene',card_id:null|string,version_id:null|string,source_title:null|string,source_title_en:string,source_available:bool,source_unavailable_reason:null|'offline'|'deleted',created_at,updated_at,unread:bool,latest_event_id:int,events:FeedbackEvent[]}`
- FeedbackPage = `{items:FeedbackDetail[],total,page,limit}`，列表中的events固定为空数组
- FeedbackUnread = `{unread:bool,count:int}`，count为本人未读反馈条数，不含回复正文
- FeedbackReadReceipt = `{feedback_id,read_event_id:int}`，不返回可因重放过时的unread布尔值

事件ID为每条反馈从1开始的固定递增序号，排序以服务器接受顺序为准；时间戳UTC。文字每次trim后1—500 Unicode codepoints，前端使用Array.from计算，纯空白拒绝；每次0—3张图片，引用不能重复；补充次数不限。

## 两角色读取

以`/api/{mini|admin}/v1`为base：

- GET `/feedback?page=1&limit=10` → FeedbackPage；limit最大50。admin另支持`status?`四态及`search?`（反馈ID、用户内部编号、安全来源标题及原说明摘要），小程序仅返回本人
- GET `/feedback/unread` → FeedbackUnread
- GET `/feedback/{id}` → FeedbackDetail，包含完整有序时间线和新截图grant；读取不清未读
- PUT `/feedback/{id}/read`，JSON `{event_id:int}` → FeedbackReadReceipt；仅推进该角色本人游标至已存在事件，低水位不倒退，超出时间线拒绝，不改变处理状态

详情以主记录捕获的latest_event_id为快照水位，时间线及附件只包含不超过该水位的事件；读取期间接受的新事件留待下次详情和未读聚合读取，避免旧状态标题混入新时间线。

详情实际显示成功后才提交本次显示到的event_id。读标记成功／未知结果查实后重新GET unread；不要用旧读操作回执清除并发新事件或其他反馈红点。管理员与用户游标独立。仅开始processing且无文字时不产生用户未读；管理员新文字回复和要求补充产生未读。

## 用户写入

- POST `/api/mini/v1/feedback` → 201 FeedbackDetail

```json
{"category":"content","text":"说明","images":[],"source":"profile"}
```

scene来源必须另传当前已发布`card_id`与`version_id`；profile不传。保存提交时安全双标题，不读取未发布草稿。来源后来下线／删除保留时间线，只返回安全摘要，不开放旧全文或音频。

- POST `/api/mini/v1/feedback/{id}/messages`，JSON `{text,images?:string[]}` → FeedbackDetail；所有状态可追加，成功统一回pending
- POST `/api/mini/v1/feedback/images`，multipart `file` → 201 FeedbackImage；先单张上传，再提交ID引用；只有本人成功且尚未绑定图片可用于新事件，一张图只能绑定一次

## 管理员处理

POST `/api/admin/v1/feedback/{id}/messages` → FeedbackDetail：

```json
{"text":"请补充截图","status":"needs_info","expected_latest_event_id":1}
```

text／status至少一个；status仅允许processing／needs_info／resolved；processing可无文字，needs_info／resolved必须对应说明；纯回复不改变状态。expected_latest_event_id可选，传入且不一致返回409 feedback_changed，事件和状态均不写；保留输入、刷新后明确重试。未传expected的并发接受事件按服务器行锁顺序追加，不覆盖旧事件。管理员详情、截图读取和处理保留必要Audit，不记录文字、截图或联系方式正文。

## 私有截图

只接受实际可解码静态PNG／JPEG／WebP，沿用上传字节限制和20MP解码上限；去EXIF等元数据，最大2048边长压缩后私有保存。开启审核时，安全检查未完成不视为上传成功。附件不进入公开卡片／分享。

url为`/api/{role}/v1/feedback/images/{opaquegrant}`，5分钟会话／角色／用途绑定，每次下载复查当前会话、图片和所属反馈权限。原生image／previewImage可用grant不附Authorization；若带Authorization则必须匹配。后台必须同session cookie。私有响应no-store与nosniff。

GET `/api/{role}/v1/feedback/images/{image_id}/url` → FeedbackImage（新grant）；用户可续签本人成功未绑定图片，管理员只可续签已绑定可访问反馈的图片。GET detail也返回新grant。图片过期或读取失败只续签／重试，不重复上传成功项。

## 幂等、安全与配置

2026-10-24 验收修订：`Settings.feedback_safety_enabled`／`JUYA_FEEDBACK_SAFETY_ENABLED` 默认 `false`，统一跳过用户创建、追加、截图和管理员回复的外部审核调用；其余校验和安全边界保留。设置 `true` 才启用下述严格网关规则。无需修改请求契约，配置细节及新批次删除契约见 `v15-acceptance-api-contract.md`。

未知响应先GET现有`/api/{role}/v1/operations/{key}` → `{status:'succeeded',result:<本操作FeedbackDetail|FeedbackImage|FeedbackReadReceipt>}`。详情型旧回执为当时快照；恢复成功后GET detail刷新时间线与图片grant。已成功结果先恢复，后续安全网关失败不妨碍恢复；真正写入仍由operate重新校验指纹及归属并原子提交。反馈行锁分配事件序号并决定最终状态，独立已读游标不越过提交水位。

Settings配置`feedback_safety_url`／`feedback_safety_token`（环境JUYA_FEEDBACK_SAFETY_URL／TOKEN，密钥repr=False），真实HTTPS网关有界超时且不跟随重定向。POST `<url>/text` JSON `{correlation_id,content}`；POST `<url>/image` multipart `file`与`correlation_id`，图片已规范化；Bearer令牌只发给配置网关。关联标识为不包含身份明文的幂等摘要，不发送联系方式、业务会话或OpenID。

仅明确响应`{"decision":"allow"}`通过；reject→422 content_rejected；review／pending／未知／缺失／未配置／超时／异常→503 content_safety_unavailable，保留输入和已成功附件。此网关必须实际连接检查能力；配置存在和测试替身不构成真实内容安全验收。

工厂DI：`mini.create_app(...,feedback_safety=None)`及`admin.create_app(...,feedback_safety=None)`；适配器协议`check_text(text,correlation_id)->None`、`check_image(data,content_type,correlation_id)->None`，拒绝或失败raise DomainError。合成allow仅用于隔离验收，生产默认无配置明确失败。

反馈文字和原说明摘要加密保存；admin摘要搜索在授权状态范围流式解密匹配，不建立内容明文索引。真实云存储、内容安全、MySQL并发与真机截图流程须单独验收；不伪造保留期限或平台接入结果。
