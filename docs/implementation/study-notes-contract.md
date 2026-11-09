# 整合07 学习笔记实际接口契约

2026-11-06，API test，本地实现。数据库新增0026，最低schema0026，兼容contract3；不能直接启动于0025库。本轮不执行业务库或远程迁移。

## 1. 上传与管理员编辑

复用 `POST /api/admin/v1/media?kind=study_note`，multipart `file`，管理员会话、CSRF与Idempotency-Key沿用现有规则。返回 `MediaMetadata`，首次通常 `state=processing`，必须轮询 `GET /api/admin/v1/media/{id}/status` 至ready。失败提供error/error_code，可使用原重试接口。真实PDF格式、页树、内容流与加密可读性由pypdf校验，上传成功不等于可用。`GET /api/admin/v1/media/configuration` 新增 `study_note_limit_bytes`（默认20971520，可配置）。空文件/超限上传为413。非PDF、损坏、加密不可读为异步failed，error_code分别见下表。文件只通过认证的 `GET /api/admin/v1/media/{id}` 受控预览，支持Blob与Range，不写用户学习事实。

`POST /api/admin/v1/cards`、`PUT /api/admin/v1/cards/{id}` 和 `PATCH /api/admin/v1/imports/{batch_id}/items/{item_id}` 在原请求顶层增加可选 `study_note`：

```json
{"action":"set","media_id":"已上传的PDF媒体ID"}
```

动作：`keep` 保留（并取消当前待处理替换）、`set` 选择一份PDF、`remove` 明确不添加/移除、`unresolved` 待选择。只有set携带media_id。 `set`及`unresolved`还可选传`previous_media_id`：管理员已校验ready但尚未保存的有效B，随后选择待处理或失败C时，一个请求`{"action":"set","media_id":"C","previous_media_id":"B"}`会原子保存有效B及pending C。省略previous_media_id沿用原服务端推导；明确提供必须是非空ID、当前管理员可合法引用的ready PDF，不接受null、foreign、未就绪、失败、非PDF或不存在引用；keep/remove携带该字段一律422。ZIP同时校验当前包/目录来源；明确目标卡已合法绑定的历史附件（可来自旧包）允许保留，管理员单独上传补充允许，其他包/目录的PDF不能借fallback串入。目标清空/切换且省略笔记操作时，仍按最终目标重验完整保留状态；后台worker保存也会重验。单独上传须有明确AdminMediaSource来源证明，删除ZIP来源记录不会使其PDF变为手动上传。保存后重开仍为B＋C，取消C恢复B；当前发布附件A保持到发布确认成功。请求省略或null表示不改当前草稿决策；不得为兼容旧包自动发送remove。旧ZIP不含PDF时保留更新目标的原草稿笔记；新卡仍为空。保存允许processing/failed/unresolved候选；预览及发布要求PDFready，或明确remove/keep取消待处理附件。

`CardView` 新增：

- `study_note: StudyNoteDraft`：`action`、`attachment: MediaMetadata|null`（当前有效编辑附件）、`pending_attachment: MediaMetadata|null`（未就绪替换）、`can_publish:boolean`、`candidates: StudyNoteCandidate[]`。
- `published_study_note: StudyNoteMetadata|null`：当前发布附件，与草稿分开。
- StudyNoteCandidate包含 `file_id,name,size,media_id,state,error_code,parent_id`，其中media_id允许null（包内超限等失败）。来源目录使用ImportItem现有 `source_zip_id/source_zip_name/source_folder`，候选不得跨包或跨目录关联；单独上传的补充PDF允许选择。
- StudyNoteMetadata：`version_id,media_id,filename,size,state`，state固定ready。`version_id`是独立笔记版本，与正文的current_version_id不同。

`POST .../preview` 返回的 `CardPreview.study_note` 为候选StudyNoteDraft；`GET .../published` 返回 `PublishedPreview.study_note` 为已发布StudyNoteMetadata或null。预览指纹绑定正文与笔记动作，替换/移除只有发布事务成功才对用户生效。只改笔记不更新正文版本、排序、阅读位置、音频进度或TTS；目录修订会更新。发布与编辑仍使用原draft_revision/preview_id/幂等契约。

## 2. ZIP核对

仅场景ZIP支持可选PDF；不扩展听读或独立DOCX笔记匹配。每个包实例parent_id与完整目录隔离：唯一PDF自动set，多份为unresolved，零份保留keep。核对结果 `ImportItemView.study_note` 与CardView同型。确认更新目标后，核对附件、待处理件、issues与发布资格均按目标草稿和本项决策计算；候选列表仅来自当前包／目录。切换或清除目标会重新计算，继承结果不写入暂存决策。选定一份用set，选择不添加用remove。无效、超限、多候选均可保存待处理草稿，不能发布；修正或明确移除后继续。保存收据及dedupe包括笔记内容、有效回退PDF内容及动作，按字节而非上传ID识别，重复提交仍沿用原逐项幂等。同正文、同图片与音频字节的ZIP只更换PDF时，保存会复用目标等价正文，保持正文行ID、原媒体ID、正文版本与阅读位置。

## 3. 用户列表与详情

现有 `GET /api/mini/v1/cards` 新增：

| 参数 | 语义 |
| --- | --- |
| scope=uncompleted | 默认；当前发布、未删除且本人未完成 |
| scope=published | 当前全部发布、未删除，包含本人已完成 |
| has_study_note（省略） | 不限制笔记 |
| has_study_note=true | 当前发布版绑定有效PDF |
| has_study_note=false | 当前无有效发布PDF |

全部场景使用默认参数；含学习笔记使用 `scope=published&has_study_note=true`。过滤、count与排序均在数据库分页前完成，保留现有免费优先和人工顺序，超出页数返回最后有效页（无结果page=1,total=0）。每项新增 `has_study_note:boolean`；原 `state.completed` 用于“已学／可复习”。列表不会返回文件名、media_id、笔记版本或下载地址；受限卡仍仅安全摘要。总数用total，累计已学仍用原statistics。MySQL场景列表的总数、有效页、行及笔记标志使用同一事务读取快照；后续请求重新读取当前集合。

`GET /api/mini/v1/cards/{id}?mark_started=false` 经过当前授权后新增 `study_note: StudyNoteMetadata|null`。笔记打开/重试刷新必须mark_started=false，避免写ReadingStart；单独申请票据及下载不写任何开始/完成/打卡/进度。正文version_id保持原意义。

详情新增可选`require_study_note=false`（默认）。笔记来源实际进入正文/下一张时传`require_study_note=true`，合法成员仍沿用原`mark_started=true`默认规则写一次ReadingStart，不新增PDF开始事件。服务端在同一事务持有用户、目录及当前卡片/PDF的合理锁，按当前发布/删除/权限和共享published_note有效谓词检查后才插入开始记录；有效PDF已移除或不可用返回`409 study_note_unavailable`，没有新增ReadingStart。当前无权限、下线/删除继续按原403/410处理。`require_study_note=true&mark_started=false`为资格探测/只读刷新，不写学习事实。默认false、普通learning无PDF详情完整保留旧语义；正文版本校验不变，PDF-only替换仍用独立笔记版本。


## 4. 下载票据与队列

复用 `GET /api/mini/v1/cards/{card_id}/media/{media_id}/url?purpose=study_note&study_note_version_id={note.version_id}`，返回原ResourceURL（相对url、expires_at）。笔记用途无需正文version_id；必须携带独立study_note_version_id。每次申请与访问票据均重验会话、卡片发布/删除、免费或有效授权、当前PDF媒体及独立笔记版本。笔记兑现请求必须携带签发会话的Authorization Bearer，匿名、其他用户或同账号另一会话均返回401。GET、HEAD及Range全部相同；替换/移除后旧票据409 study_note_changed。无公开永久链接；客户端每次重试应刷新元数据/权限并重新获取票据，临时文件按账号+卡片+独立笔记版本隔离。

原 `POST /api/mini/v1/learning-queues` 的source新增 `learning_notes`，创建请求仍为 `{source,card_id}`。快照包含已学，顺序与笔记列表一致，每项实时校验发布PDF与权限；PDF失效不移位、不循环、不跨来源。`learning`仍按待学集合，不要求PDF。learning_notes结束始终round_complete，不套free_uncompleted终止语义；客户端回对应Tab列表刷新。队列条目的available只是该次查询资格；learning_notes推进至候选正文时，最终详情GET还必须传require_study_note=true（实际进入保留mark_started默认true）。若在队列查询后移除PDF，最终GET以study_note_unavailable拒绝且无新开始，客户端可跳至后续合法项或返回来源。只读探测不能替代最终原子准入；普通learning不加该要求。

## 5. 前端接入次序

从API `openapi/admin.json`、`openapi/mini.json` 同步生成类型。保留编辑revision、未知收据恢复与迟到上传取消逻辑；文件upload100%只说明上传完成。草稿预览读取candidate attachment，已发布效果读取published_study_note；用户入口使用获权详情study_note。后台不调用mini学习接口。


## 6. Task1b兼容补足与实际失败原因

本增量补足已批准的有效/待处理附件并存能力；无新route、reader、依赖或数据库迁移。请求仅新增可选previous_media_id，返回的StudyNoteDraft仍使用attachment/pending_attachment；ImportFileView与StudyNoteCandidate新增可空error，提供与媒体状态一致的安全中文原因。原error_code仍为开放字符串。

| error_code | 实际原因与中文提示 |
| --- | --- |
| study_note_format_invalid | 文件实际格式不是PDF，请选择PDF文件 |
| study_note_invalid | PDF文件结构损坏或内容无法读取，请更换完整PDF（保留旧损坏码） |
| study_note_encrypted | PDF已加密且无法打开，请解除密码保护后重新上传 |
| study_note_empty | PDF文件为空，请重新选择 |
| study_note_limit | PDF文件超过当前大小限制，请压缩或更换文件 |

手动上传空/超限在接收时返回413及对应code/message；ZIP相应文件保留failed核对状态与上述原因，仍可保存待处理草稿。媒体status、导入文件/candidate的error及导入issues使用相同具体原因；不返回解密底层异常或密钥。非法previous引用返回422 study_note_previous_invalid，跨包/目录为既有422 import_media_source，模型不允许的previous形态为422 invalid_request。
