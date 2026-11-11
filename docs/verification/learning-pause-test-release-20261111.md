# 学习授权暂停：测试发布与小程序上传

2026-11-11，按用户本轮明确授权，API 与小程序代码已推送远程 test；测试双 API、Worker/dispatcher 与独立听读 Worker 共7服务已部署并全部健康。微信测试开发版 **1.5.0-test.20261111.170119** 已由标准命令上传，官方 CLI 成功回执已核对。**体验版未切换，由用户手动操作**；未提审或正式发布，生产及原本地业务服务保持。

| 目标 | 固定源码/版本 | 验证 |
| --- | --- | --- |
| 测试双 API 及7服务 | `81f877673d42aa616d8f0e3f29f331f5333834f0` | healthy，重启0，无OOM |
| 小程序源码 | `1dfa0d39e33afa23614ec59f7200da377d519b19` | 远程 test 同步；实际上传包为该功能源码 |
| 微信开发版本 | `1.5.0-test.20261111.170119` | 官方上传成功，20页/3Tab，体验版手动切换 |
| 管理后台网页 | 沿用本轮改动前资源 | 本轮无后台前端代码改动，不另行发布 |

测试 API：[管理端就绪](https://test-admin-api.juyayingyu.com/health/ready)、[小程序端就绪](https://test-api.juyayingyu.com/health/ready)。[完整无密钥回执](learning-pause-test-release-20261111.json)。后续发布记录提交仅修改文档，不改变上述已部署/上传的固定功能源码。

## 官方门禁与发布

[官方 CI 42985382145](https://github.com/zhanjiangmrlu/juya-api/actions/runs/42985382145)真实 MySQL/Redis 全量 **834通过、3条SQLite专用跳过**，格式/ruff/mypy、OpenAPI导出一致性和双Linux/amd64镜像通过。服务器验证官方 artifact ZIP摘要、image.json/实际镜像身份与固定提交，原生发布引擎预检查全部通过后，才执行测试发布与既有保留策略；不执行全局 prune。

首次CI42982353053为832通过/3跳过/2失败：两项仅真实MySQL运行的保留查词并发测试漏了显式 legacy_learning_features 夹具，接口正确返回lookup_unavailable。隔离MySQL先复现2失败，再仅补齐两项测试装饰器（81f8776），预热并发与暂停策略26项通过、本地完整780通过/57条件跳过，最终官方全量通过。没有为旧测试重新开放产品查词或授权。

本地GitHub22端口连接中断，使用任务级SSH443完成推送，未改全局SSH配置。服务器传输采用指定账号来源的验证连接方式；发布与回滚由现有45ff9c0原生引擎执行。

## 数据与环境保留

发布前完成juya_test一致性备份并核对结束标记与SHA256。本轮**无迁移、无权限数据清理、无运行时政策配置变更**；schema0028/contract3保持，原60张业务表全部原字段、行数及摘要不变，学习授权记录保留。

19个原容器中仅7个测试目标更新；其余12个容器ID、镜像、启动时间、健康、重启和OOM元数据均与基线一致。生产配置、数据和服务未操作。

## 公网和运行时核验

双ready200且环境test；个人/隐私/批次接口匿名401，跨角色路由404。运行OpenAPI与固定源码语义一致，正式政策目录仍为published，terms沿用原版本、privacy/analytics为chg0041-20261111-v2，analytics_available=false且实际receiver为None。

实际镜像授权增权/内置查词开关均false；对测试库现有1个有效授权账号及游客共完成4项只读免费内容权限核验，不创建账号、不改原免费标记。公网目录场景15条、听读11条当前均标记免费，免费详情200、can_lookup=false；因此没有伪造真实非免费403样本，非免费拒绝、旧票据和恢复行为由隔离MySQL/官方CI覆盖。

## 微信测试包

执行一次标准 `pnpm release:mp-weixin:test`：隔离构建、测试OSS同步和公网资源核验、官方CLI上传均通过。测试资源新增0、复用13；20页/3Tab、设置页已注册；主包source486748B，预留20%转换后584098B，剩余1513054B，满足102400B预留要求。

实际目录 `dist/test-release/d34c6831-013d-4d63-a258-1ba407383644`，result.json/官方upload-info.json一致。仅测试API，无生产API或友盟网络域名，包含getUpdateManager/onUpdateReady；未更改生产manifest或正式版本记录。无新增埋点，桌面sample.txt未修改。

iOS/Android系统选词菜单、实际微信新版下载/重启仍需真机验收；本次构建与上传不冒充这些结果。恢复开关见本轮实现说明和小程序docs/operations/learning-features.md。
