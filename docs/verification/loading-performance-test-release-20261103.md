# 列表性能测试 API 发布记录（20261103 批次）

实际完成时间：**北京时间 2026-11-04 00:05:34**（UTC 2026-11-03 16:05:34）。公网与身份复核时间为北京时间 00:07:14。文件名保留 11 月 3 日启动的任务批次，不能将实际发布时间写成 11 月 3 日北京时间。

按用户批准的测试验证计划，仅发布测试 `juya-miniapp-api` 的 `mini-api`、`mini-worker`、`mini-dispatcher`，固定源码 **`00a4c1101b6413dd9a8d230f9cf82c8610464c45`**。测试 admin 三服务及独立 listening-worker 保留原版本；生产、基础设施和隔离验证容器等其余 **16 个容器的 ID、镜像、启动时间、状态、健康、重启及 OOM 字段逐项一致**。未执行迁移、改写业务数据、改动 ACL 或配置。

## 来源与 CI

性能实现为 `7c6c2e2`；随后仅增加质量检查时间余量的 `9549640`，以及同步四处既有接口说明并前置契约检查的 `00a4c11`。四处 description 源自父提交 `e6b393b`，本次生成同步不改变路径、参数、响应或 schema。质量阶段仍运行完整真实 MySQL/Redis 测试，没有绕过或转为 SQLite。

最终 [CI run 41665251214](https://github.com/zhanjiangmrlu/juya-api/actions/runs/41665251214) 的契约、质量及两角色镜像全部成功；真实 MySQL/Redis 为 **621 通过 / 3 跳过，1140.18 秒**。前两轮超时及契约说明差异的证据和最终官方产物摘要见[CI 记录](listening-performance-test-ci-20261103.json)。完整 CI 日志留在服务器私有暂存，不纳入 Git。

| 身份 | 固定值 |
| --- | --- |
| 官方 mini artifact | `13247596150`，249810272 字节 |
| ZIP SHA-256 | `780b3261b7ac5618e890198234d4b7074eafa654b644a444563921112930310f` |
| 镜像归档 SHA-256 | `accfde9f221195c15df6da24bad49f28603a0cf8488bea286e53fcef1d8a372a` |
| 官方镜像 config ID | `sha256:b4726e3b61a64528f3e5523fae510aec7ea6a8e3ab6259045f56a4055a0e7792` |
| 运行 OCI ID | `sha256:f1e9be944b81d113ada2fa222244759da11509daecb3586cdfa2e4b50be0c535` |
| 原生发布包 SHA-256 | `db2e918f1c71a8214b68decd5255a554f9a97cb7c88486a18853293507a1fafe` |
| 镜像标签 | `juya-miniapp-api:00a4c1101b6413dd9a8d230f9cf82c8610464c45` |
| 平台 / source label | `linux/amd64` / `00a4c1101b6413dd9a8d230f9cf82c8610464c45` |

官方 config ID 与运行 OCI ID 是同一已验证归档的两种身份。原生 engine `_image_identity` 校验 config 摘要及 OCI 图关系，确认运行 ID 属于该归档的允许集合；额外复核运行镜像 title/source 标签及平台，未仅凭可变 tag 认定身份。

## 发布与恢复边界

复用服务器已部署的 Juya CLI `45ff9c0` 原生 engine，未修改工作台配置或发布引擎，未使用历史迁移任务的 monkeypatch。服务器直接从 GitHub 获取官方 artifact，禁止自动携带 Authorization 跨域跳转，取得 302 签名地址后用无认证头的新请求下载；令牌只在服务器内存读取，未离开服务器或进入记录。

官方 ZIP digest、精确双文件白名单、镜像归档 hash、角色/source/架构、精确 SHA 的干净 `test` 源码及原生 bundle/Compose 全部校验后，stage 复核 19 个容器完全不变。沿用现有 test runtime 文件和 dictionary override，运行原生环境/数据库/broker/OSS 配置兼容闸门；先停 dispatcher、优雅排空 worker、停 API，再启动新 API，校验真实 readiness 和词典 readiness 后启动后台进程并等待稳定健康。

原生公网失败恢复流程保留，本次未触发回滚。公网检查成功后执行原生 finalize，保留：

- 当前：`20261103T160259-00a4c1101b64-19fc8b`，源码 `00a4c11`。
- 上一版：`20261102T131650-c690358d12e8-ce0148`，源码 `c690358`。
- 依既定保留规则移除超额旧 mini 版本 `20261101T034259-f46f2d4ab3f1-4196d5` 及其精确镜像引用，无全局 prune；finalize 无 warning。

## 实际验收

| 公网只读请求 | 实际结果 |
| --- | --- |
| `GET https://test-api.juyayingyu.com/health/ready` | 200；`ready / mini / test` |
| 匿名 `GET /api/mini/v1/listening/articles?page=1&limit=3` | 401；`login_required` |
| `GET /api/admin/v1/auth/session`（mini 域名） | 404；公网返回 HTML，不假定错误响应一定为 JSON |

UTC 16:10:33（北京时间 00:10:33）再次复核：mini 三服务仍 healthy、重启 0，其余 16 容器完整元数据仍相同。

只读查询测试库元数据前后均为 `0024 / contract 3`。发布 profile 不含 migration 服务，本次没有迁移、降级、备份恢复、队列清空、业务资料写入或运行配置变更。

| 更新服务 | 新容器 ID 前缀 | 启动时间（UTC） | 健康 / 重启 |
| --- | --- | --- | --- |
| mini-api | `35afa26d1a7a` | `2026-11-03T16:04:43.666783047Z` | healthy / 0 |
| mini-dispatcher | `7a5fa3322ec8` | `2026-11-03T16:05:00.608425088Z` | healthy / 0 |
| mini-worker | `47c0c14cdfd5` | `2026-11-03T16:05:00.300291126Z` | healthy / 0 |

以下 16 个容器发布前后完整元数据一致；完整 ID、镜像及前后快照见[无秘密发布回执](loading-performance-test-release-20261103.json)。

| 受保护容器 | ID 前缀 | 启动时间（UTC，前后相同） | 对比 |
| --- | --- | --- | --- |
| juya-rebuild-infra-mysql-1 | `e14bba01092b` | `2026-10-17T09:19:47.351876659Z` | 一致 |
| juya-rebuild-infra-redis-production-1 | `7c43f23bf66e` | `2026-10-17T09:19:47.059895136Z` | 一致 |
| juya-rebuild-infra-redis-test-1 | `cd7c067ddef5` | `2026-10-17T09:19:46.660800632Z` | 一致 |
| juya-rebuild-mysql-verify | `3a1b26ac8238` | `2026-10-17T04:18:07.806800241Z` | 一致 |
| juya-rebuild-production-admin-admin-api-1 | `b6db46a0b248` | `2026-11-03T03:05:40.319629667Z` | 一致 |
| juya-rebuild-production-admin-admin-dispatcher-1 | `1d6d4c27823a` | `2026-11-02T16:02:20.88876377Z` | 一致 |
| juya-rebuild-production-admin-admin-worker-1 | `8acc247cef5a` | `2026-11-02T16:02:21.295773032Z` | 一致 |
| juya-rebuild-production-listening-listening-worker-1 | `10633a168686` | `2026-11-02T16:03:56.585287119Z` | 一致 |
| juya-rebuild-production-mini-mini-api-1 | `00713957535c` | `2026-11-02T16:03:04.265884351Z` | 一致 |
| juya-rebuild-production-mini-mini-dispatcher-1 | `e0d28edfd54c` | `2026-11-02T16:03:20.718443992Z` | 一致 |
| juya-rebuild-production-mini-mini-worker-1 | `c195913ad03b` | `2026-11-02T16:03:21.170938496Z` | 一致 |
| juya-rebuild-redis-verify | `dcf8010e84d1` | `2026-10-17T07:14:22.451493712Z` | 一致 |
| juya-rebuild-test-admin-admin-api-1 | `98f79c6f52c6` | `2026-11-02T13:21:12.41881641Z` | 一致 |
| juya-rebuild-test-admin-admin-dispatcher-1 | `f05c70b57422` | `2026-11-02T13:21:29.816843033Z` | 一致 |
| juya-rebuild-test-admin-admin-worker-1 | `65a575ecb9b4` | `2026-11-02T13:21:29.561825174Z` | 一致 |
| juya-rebuild-test-listening-listening-worker-1 | `4f40735677cc` | `2026-11-02T13:24:23.807981477Z` | 一致 |

## 验证限制

本次发布 smoke 未使用真实学习者身份，没有在真实账号上验收完整首屏、学习操作或音频播放。621 项真实 MySQL/Redis通过、SQL-count 回归、服务健康与匿名权限隔离不能代替微信真机首屏及音频端到端延迟/P95 验收；这些项目继续待验。生产服务及测试其余四个应用服务保持原版本，本记录不代表它们已部署本轮源码。
