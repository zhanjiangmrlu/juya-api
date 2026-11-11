# CHG0041 本地接口与隐私契约

本轮仅现有 test 分支本地增量，无推送、部署、OSS或微信上传。最低 schema0028，代码 contract3。0028只新增 free_access_batches、free_access_batch_items，不改既有业务表。逐项免费接口及发布/删除原本页十条规则保持。

## 跨页免费

管理端统一使用 POST `/api/admin/v1/free-access-batches/preview`，正文 content_type(scene/listening)、ids(稳定ID完整集合，去重)、is_free。预览无业务写入，回完整名称、发布version、免费修订号、pending适用项及skipped完整原因；返回绑定管理员、类型、目标及完整名单的加密preview_token。已发布名称取不可变发布版本，非待发布草稿。

确认 POST `/api/admin/v1/free-access-batches`，携 Idempotency-Key，正文 preview_token及预览中全部pending items。遗漏、扩大或篡改适用集合均409；无适用项拒绝。原skip只写跳过回执。受理使用既有Operation与Job同事务，GET `/api/admin/v1/operations/{key}`恢复丢失响应，GET `/api/admin/v1/free-access-batches/{id}`查询逐项进度与完整历史。

管理worker复用原dispatcher每轮50条任务调度，非选择容量。管理员→Job→目录→对象锁序；逐项事务及savepoint隔离异常，执行时复核管理员、发布/删除/分类权限、发布version和free_revision。只改is_free/free_revision与策略revision；AccessHistory前后状态均含batch_id，与成功明细同事务。租约过期不能写，重投跳过已有终态；多次中断耗尽则剩余项明确failed，终态成功+跳过+失败等于原选择总数。

重试须重新preview原明确failed子集，人工确认后 POST `/api/admin/v1/free-access-batches/{id}/retry`。原目标和类型必须相同，不能带成功或跳过项；新子批次关联parent_id，原记录不变。未知仅查询原Operation/任务，明确operation_unknown后才复用原key、原冻结正文，不能换key整批重发。

当前权限每请求复核，关闭免费后旧正文/音频/图片/PDF票据也按原规则拒绝；学习授权与成绩、收藏、打卡、进度不变，不自动补位免费内容。已下载字节不能承诺回收。

## 统计

真实客户端统计能力固定false、collecting固定false；旧analytics_client_transport_enabled不能启用、不能伪accepted或新建事件收据。隔离测试注入receiver继续验证五事件、可信身份、业务成功回执和持久去重。客户端设置page_path加入同一白名单。

新完整披露为 `src/juya_api/policies/chg0041-20261111-v2.json`：terms沿用原版本，privacy/analytics为chg0041-20261111-v2。明确本版不装载SDK2.8.0（设备型号/自动会话不符合范围），仅允许五事件及最小引用，不缓存未来补报；旧scope不继承新许可。后续环境发布时应明确将JUYA_PRIVACY_DOCUMENTS_PATH指向新bundle，本轮不修改原私有配置或远程服务。

## 本地验证

完整SQLite768通过/57环境条件跳过；真实独立socket MySQL juya_verify821通过/4跳过（3条SQLite专用、1条Redis条件）。新增回归包含33项完整集合、冻结/幂等/失败子集、监听已发布名称、分类权限变化、租约过期和耗尽、逐项异常隔离、旧媒体票据撤权；0028原表逐行快照及metadata parity通过。ruff/mypy通过。详细执行证据与三仓后续验收在本轮SDD报告及交接补充。
