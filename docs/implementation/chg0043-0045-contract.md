# CHG0043—0045 接口交接

管理接口共用管理员会话及现有 CSRF、Idempotency-Key 写入约定。类型枚举为 illustrated、intensive。

- GET /api/admin/v1/content-types/history?page=1&limit=20 返回 items、total、page、limit、total_pages、content_types_ready。每条含 card_id、name、current_version_id、study_note_version_id、draft_revision、draft_content_type、published_content_type、suggestion、warnings、snapshot。snapshot 为不透明版本摘要。
- POST /api/admin/v1/content-types/confirm 提交 {"items":[{"card_id":"…","snapshot":"…","content_type":"illustrated"}]}，返回 items，每条含 card_id、status（confirmed、skipped）、reason。核对列表包含所有有效发布，可用 unclassified_only=true 只取未归类。
- POST /api/admin/v1/content-types/enable 提交 {}，复核全部当前有效发布，返回 {"content_types_ready":true}。未通过返回 409 content_type_bindings_invalid。
- GET /api/mini/v1/cards?content_type=illustrated&scope=uncompleted&page=1&limit=20 返回 items、total、page、limit、published_total、type_published_total、content_types_ready 和原访问策略。未启用时显式类型请求返回 content_types_ready=false，items=[]，type_published_total=null。已启用后检测到配置异常的类型请求返回 503 content_type_bindings_invalid。无类型请求保留旧列表。
- POST /api/mini/v1/learning-queues 待学来源使用 {"source":"learning","card_id":"…","content_type":"intensive"}。创建和读取响应均增加 content_type。复习来源不传类型。
- POST /api/admin/v1/cards 及 PUT /api/admin/v1/cards/{id} 在 content 同层传 content_type，可为 null。更新时省略会保留现值。启用前后均可暂存无类型草稿；所有发布与预览入口始终拒绝无类型或附件冲突的草稿。CardView.content_type 为列表生效归属，draft_content_type 为编辑归属，published_content_type 为最近发布归属。
- GET /api/admin/v1/cards 可选 content_type；GET /api/admin/v1/listening/articles 可选 category_id。两者均返回 statistics、all_statistics、snapshot_at、total_pages。统计对象字段为 total、published、free、remaining。

## 候选分类及批次明细

- GET /api/admin/v1/imports/{batch_id} 的 items 及 PATCH /api/admin/v1/imports/{batch_id}/items/{item_id} 的返回值增加 content_type、type_origin（file、manual、override 或 null）和 type_raw（源文档原始分类文字数组）。PATCH 与既有 revision、selected、content 等同层接受 content_type；省略保留现值。已判重候选不可编辑，返回 409 import_duplicate。
- POST /api/admin/v1/imports/{batch_id}/content-types/preview 接受 {"items":[{"id":"…","revision":1}],"content_type":"illustrated","overwrite":false}。响应 {"count":1,"version":"…","items":[{"id":"…","revision":1,"old_type":null,"new_type":"illustrated","pdf_conflict":false}]}。只返回实际受影响的可编辑候选，默认只填空值。
- POST /api/admin/v1/imports/{batch_id}/content-types/apply 在相同请求体中增加 version 并提供 Idempotency-Key。成功返回完整 ImportBatchView。版本或选取范围变更返回 409 import_changed。
- GET /api/admin/v1/imports/{batch_id}/duplicates 和 GET /api/admin/v1/listening/imports/{batch_id}/duplicates 接受 page（默认1）和 limit（默认20，1至100），返回 items、total、page、limit、total_pages。每项有 candidate_id、source_name、source_path、title_zh、title_en、reason、target_kind、target_id、target_available。reason 取 existing_content、same_package 或 cross_package。target_kind 取 scene_card、scene_candidate、listening_article、listening_candidate；无法还原的历史目标为 unknown，target_id 可空。只有 target_available=true 才提供对应种类的打开入口。

场景批次响应增加 removed_count（本批累计人工移除卡片数）。GET /api/admin/v1/imports/{batch_id}/confirmation 增加 removed、failed（保存失败项）、failed_files（文件处理失败数）、package_count（ZIP包数）；原 duplicates 为可查明细总数，unreadable 为不可读候选数。

## 词汇编辑与来源

POST /api/admin/v1/vocabulary/sources/preview 接受 {"module":"scene","content":SceneContent} 或 {"module":"listening","content":ListeningPayload}。返回 module、vocabulary。只读预览复用导入和保存规则，需管理员会话及 CSRF。词条保留 id、english、meaning、source_hint；source 非空表示词形已定位，source_reason 描述未通过原因 source_hint_conflict、source_ambiguous、source_sense_conflict 或 source_unmatched。场景的 source.quote 是正文实际词形，start/end 是该 dialogue 行 UTF-16 半开区间。听读 source.word 是实际词形，word_start/word_end 是正文 Unicode 码点半开区间；quote 和 start/end 是原句与范围。

tests/fixtures/vocabulary-matching-v1.json 提供场景与听读适配层共用的匹配示例，包含正文原始词形及两种偏移。前端实时核对可直接调用来源预览，服务端导入、保存及发布复用同一规则。

## 完整分页参数及响应

| 接口 | 参数及默认值 | 完整响应顶层字段 |
| --- | --- | --- |
| GET /api/admin/v1/cards | status=all、content_type、search=""、batch_id、anchor_id、page=1、limit=10 | items、total、page、limit、statistics、all_statistics、snapshot_at、total_pages、learning_policy |
| GET /api/admin/v1/listening/articles | page=1、limit=20、topic_id、category_id、status、batch_id、q="" | items、total、page、limit、statistics、all_statistics、snapshot_at、total_pages |
| GET /api/mini/v1/cards | page=1、limit=20、scope=uncompleted、has_study_note、content_type | items、total、page、limit、content_types_ready、type_published_total、learning_access、free_uncompleted_total、published_total |
| POST /api/mini/v1/learning-queues | JSON 含 source、card_id，可传 content_type、day | 201 返回 id、content_type、source、total |
| GET /api/mini/v1/learning-queues/{queue_id} | offset=0、limit=20 | content_type、end_reason、items、total、offset、next_offset |
| GET /api/admin/v1/imports/{batch_id}/confirmation | 可选 item_ids | removed、failed、failed_files、package_count、version、count、incomplete、saved、duplicates、excluded、unreadable |

四项统计仅随分类变化，搜索、其他筛选或页码只影响 total。两管理列表返回有效页码，total_pages=0 时 page=1。POST /api/admin/v1/content-types/enable 可省略请求体。历史确认单项 reason 为 null、snapshot_changed 或 type_pdf_conflict。生成的完整字段类型见 [管理 OpenAPI](../../openapi/admin.json) 和 [小程序 OpenAPI](../../openapi/mini.json)。

场景词条的本句释义和音标分别选填。听读词表可空，若提供词条，发布前其释义须非空。候选文件有未知类型或多个类型时，批量预览和应用跳过该项，须单项核对。PATCH 提交相同类型保留 type_origin，从空值补选记 manual，改动已有类型记 override；原始 type_raw 保留。
