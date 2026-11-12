# CHG0042 API 本地实施验收（2026-11-12）

本记录对应计划 Task 1。需求文件 SHA256：`a30ab44e011797addea0e064403953e4aec6f94a9aa2eeb489bc829578ec69e2`；产品范围以已确认设计为准：免费图文开放、音频/PDF 登录、学习授权及内置查词继续暂停。接口行为见 `docs/implementation/chg-0042-resource-login-contract.md`。

## 实施与 TDD

1. `tests/test_resource_login.py` 初始 9 项 RED：游客音频/PDF 与发音接口仍开放、旧 public 保护票据仍可兑换、权限 version 没有新策略。修正测试自身的 PDF 元数据字段后重新确认全部因产品缺失失败；`red.log` 是该次有效 RED。
2. 实施按服务端实际 kind 校验、删除游客发音签发/任务路径、旧 public 音频/PDF/词发音无条件失效及新权限策略后，初始矩阵 9 项 GREEN。
3. 补充原生播放器私票据的异身份矩阵：GET / HEAD / Range 在显式提供另一身份时仍成功，3 项 RED；增加显式 Bearer 会话匹配后新资源矩阵共 15 项 GREEN，同时无 Authorization 的有效会话绑定播放器交付仍成功，原会话过期逐次返回 401。
4. 补充真实有效管理员会话、另一有效 mini 会话、无 Bearer 前缀及听读原图兼容断言，资源矩阵 16 项在 SQLite 与隔离真实 MySQL 均通过。
5. 自查追加听读缩略图真实 kind 防御：原 thumbnail 直读返回 422、thumbnail-ticket 仍签发 200，2 项 RED；在两处解析后的真实素材上补充统一保护后，资源矩阵 18 项 GREEN。独立主体审查及该两处定点复核均未发现重要问题；审查本身没有冒充测试执行。
6. 原游客音频断言改为公开图片或登录后私票据预期，保留免费/过期/下线/删除/换版本及供应商去重/冷却回归；只有一项既有 public owner Worker 测试使用明确 legacy 数据夹具，验证历史已接受任务可正常收敛。没有 skip 或弱化游客资源防护矩阵。

## 验证结果

- 主体专项（新增矩阵 + guest / learning_pause / media / pronunciation / study_notes / listening）：98 通过、4 项 MySQL 条件跳过。此批在追加私票据异身份矩阵之前运行，不冒充最终全量。
- 最终受影响专项（资源矩阵、guest / listening / listening_boundaries / media）：85 通过（`final-focused.log`）。
- 隔离真实 MySQL 相关批次：184 通过、0 跳过（`api-mysql.log`，缩略图追加防御之前）。
- 隔离真实 MySQL 最终资源矩阵：18 通过（`resource-mysql.log`），包括真实 mini/admin 身份、原会话失效、GET/HEAD/Range、真实 kind、游客零新增任务和原图兼容。与前批重叠，不相加计总数。
- 首轮完整 SQLite：795 通过、57 条件跳过（`sqlite-full.log`）；该轮在缩略图追加防御之前，不替代最终完整结果。
- 最终完整 SQLite：**798 通过、57 环境条件跳过**（268.58 秒，`sqlite-final-full.log`）；最终源与全部 18 项新矩阵一并收集运行，exit 0。跳过项为环境专用检查，未新增 skip。
- 最终源代码 Ruff check、365 文件格式检查、96 源文件 mypy 及 `git diff --check` 全部通过。
- 双 OpenAPI 重新导出后字节无差异，无需下游重新生成类型。

测试及完整命令日志只保存在工作区 `.private/chg0042-implement-20261112/api/`。真实 MySQL 入口在执行前强断言 `DATABASE() = juya_verify`、专用 datadir 为 `.private/revision15-mysql/data`、端口 18216；测试夹具只重建该隔离库。

## 契约选择和边界

沿用会话绑定的私有音频票据作为原生播放器的可信凭据，不能要求其每次附加 Authorization；但原 mini 会话、当前发布/免费/版本逐次复核，显式附带身份必须匹配原会话。PDF 仍要求显式匹配身份。缺身份的新保护入口用 `unauthenticated`，已有无效身份用 `login_required`；两者均为 401，不重写原鉴权体系。

无迁移、推送、远程部署、OSS/微信上传、原配置和业务数据修改。独立审查与跨端集成由主任务记录。真实 iOS/Android 播放器、微信抓包及设备已下载文件的回收不作为 API 自动化已验证项；不承诺撤回用户已经保存的设备文件。
