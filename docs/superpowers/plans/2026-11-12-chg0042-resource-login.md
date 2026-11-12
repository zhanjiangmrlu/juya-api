# CHG0042 按需登录实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 游客免费图文不受阻，音频、预置发音和PDF须主动点击后登录

**Architecture:** 复用可信mini会话、私有资源票据和来源恢复。撤销自动登录告知及游客受保护资源预取，旧公开音频/PDF票据失效，图片仍公开。

**Tech Stack:** FastAPI/SQLAlchemy、Vue/uni-app/TypeScript/SCSS

**Spec:** `docs/superpowers/specs/2026-11-12-chg0042-on-demand-resource-login-design.md`，用户已确认并要求在test实施

## Global Constraints

- test本地开发；无推送、部署、上传、生产/共享数据操作；无迁移
- 授权/内置查词/动态高亮暂停不恢复；静态色带、系统选词、更新提示保持
- 原免费名单、账号、成绩、收藏与进度保留；真实SDK硬关闭，无新增分析事件
- 新/改函数按各仓AGENTS注释，Python snake_case / 前端 kebab-case，提交type(scope): 中文说明

## Review Focus

- 旧公开票据、伪造purpose、HEAD/Range不能绕过音频/PDF身份校验（任务1）
- 游客发音GET/POST均不得创建供应商任务或泄漏缓存音频（任务1）
- 首次、次日、分享、前后台、政策加载失败不能自动提示或登录（任务2）
- 登录后恢复、取消/超时/失效/换号不得自动播放/打开PDF或补交游客成绩（任务2）
- 免费正文与原图不能因资源401而被整体锁住，旧缓存不能续用（任务1/2）

## Task 1 API资源保护

Files: `src/juya_api/{public_resources,media_api,media_permissions,listening_api,listening_media,listening_pronunciation,pronunciation,access_service,listening_service}.py`及实际发音路由；`tests/test_guest_content.py`、`tests/test_learning_pause.py`和新增资源登录矩阵测试

Consumes: 现有optional/required mini身份与权限；Produces: 既有路由在音频/PDF/发音无身份时401，旧public票据拒绝，免费图文仍200；响应字段尽量保持，不新增capability体系

- [ ] 先写并运行RED：游客免费图文/PDF入口元数据保留，音频/PDF/发音签发及GET/HEAD/Range拒绝；旧票据拒绝且无副作用
- [ ] 按真实媒体kind和当前mini会话统一校验；维持免费/发布/版本校验；旧public protected grants废止，图片有效
- [ ] 权限version追加资源登录策略；调整原guest音频测试为明确旧功能夹具或新预期，不削弱矩阵
- [ ] 运行专项、全量SQLite及独立MySQL相关测试，ruff/format/mypy/OpenAPI；如契约未变不人为重生成
- [ ] 提交API实现，独立复核并处理重要发现

## Task 2 小程序按需触发与恢复

Files: `src/App.vue`、`src/pages/home/index.vue`、`src/services/{consent-coordinator,privacy-service,login-prompt}.ts`、`src/components/{app-login-prompt,app-consent-dialog}/`、`src/shared/{enums,constants}/privacy.ts`、`src/sub-packages/scenes/{detail.vue,study-note.ts}`、`src/sub-packages/listening/use-listening-article.ts`及现有音频/恢复模块

Consumes: 任务1既有路由401语义，既有公开免费详情元数据；Produces: 新音频/PDF登录来源，主动提示且无游客预取，登录后只读恢复和二次点击执行

- [ ] 先写RED：首页全部进入路径无自动提示，政策失败不降级伪同意；游客音频/词发音/PDF点击前零请求
- [ ] 去掉自动告知调用链和每日判断用途，保留历史确认和设置入口；主动入口按需加载正式政策，失败可重试/浏览
- [ ] 添加全文音频/预置发音/PDF来源，复用弹窗视觉，修正“游客可播放”旧文案；SDK保持硬关闭
- [ ] 游客不建自动音频准备任务，不预取/设置src；登录后恢复不自动执行旧操作；401停止/清理保护资源但保留图文及来源
- [ ] 测取消/迟到/失效/换号/政策返回/二次点击、静态色带与宽度保持；全量test/check、H5及无上传微信构建/meta/预算
- [ ] 提交小程序实现，独立复核并处理重要发现

## Task 3 集成与交付

- [ ] API/小程序接口边界组合回归，检查实际微信产物无自动登录/游客预取路径、无SDK上报域名
- [ ] 后台check/test/build保持跨页免费与选择框规则，不造业务数据；记录浏览器/缩放与真机尚未验证的边界
- [ ] 全分支独立审查，修复重要问题并做针对性RED/GREEN与相关回归
- [ ] 更新HANDOFF/验收记录及需求SHA；提交本地test，不推送。报告所有真实结果与待真机项
