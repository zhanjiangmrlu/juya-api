# 正文单词近秒播 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task

**Goal:** 发布后预生成正文单词音频，小程序进入场景预下载并跨弹窗复用
**Architecture:** 复用现有受控词典引用、Pronunciation 全局缓存及短期票据。后端分批异步预热，前端以页面为资源所有者；播放仍逐次联网验权
**Tech Stack:** Python / SQLAlchemy / MySQL / Celery；Vue3 / uni-app / TypeScript
**Spec:** 本聊天已批准的《正文单词近秒播优化》方案（2026-11-02）

## Global Constraints

- 不新增 HTTP 契约或数据库迁移，不自动部署、不操作远程环境
- 保留凭据、私有配置和业务数据；测试只使用临时库或 juya_verify
- Git 标题 type(scope): 中文说明；修改函数遵循各仓注释与命名要求
- 现有 test 检出中实施，保留已有依赖和本地运行路径；实施前已仅快进本地已有 origin/test 快照（API dcfff30、Mini 33078e4），避免遗漏整合06修复

## Review Focus

- 同形异音必须按实际读音隔离，不能仅按单词字符串合并
- 后台任务积压或重投不能拖慢主动点词
- 发布回滚、旧版本和旧配置不得遗留有效预热
- 弹窗关闭不释放页面缓存，离页和权限变化必须释放
- 预取不能自动播放，迟到响应不能使旧目标出声

## Task 1: 后端预热与优先处理

Files: pronunciation.py、dictionary.py、content_service.py、jobs.py、worker.py、对应 tests、补热脚本
Interfaces: 沿用现有 POST/GET dictionary/pronunciation；新增内部 pronunciation.prewarm / tts.prewarm job kinds

- [x] 先补失败测试：发布幂等/回滚、精确引用/异读音、过期跳过、预算、派发上限、提升竞争
- [x] 发布事务持久接受绑定 card/version/config 的幂等聚合任务；worker 分批按 controlled_target 规则创建共享子任务，单词失败不阻断其他词
- [x] 普通任务优先；每角色全局最多一个 admitted 未终态 tts.prewarm，使用 Job.result 内部标记与 SettingCounter 行锁闸门；重投仍共享该槽
- [x] 前台现有 POST 将未运行的预热任务替换为普通任务；已 running 继续共享，统一 actor→job→cache 行锁及重核
- [x] 补热命令默认 dry-run，execute 限定显式本地已发布卡片；保留预算和冷却
- [x] 运行相关测试、ruff、mypy，完整测试；登记未验证项

## Task 2: 小程序页面预加载与缓存

Files: dictionary-service.ts、use-scene-dictionary.ts、word-audio-preparation.ts、scenes/detail.vue、相关类型与测试
Interfaces: 保持服务端 HTTP 契约；内部增加页面级字典音频准备和优先级入口

- [x] 先补失败测试：全文引用、2并发/可见优先、前台提升、跨弹窗复用、权限/离页清理
- [x] 页面收集 dictionaryTokens 的精确引用，后台最多2项，visible优先其余按正文顺序；处理中不长期占满后台槽
- [x] 后台仅 GET，不触发生成；前台 GET missing/processing 时 POST 生成或提升，沿用现有轮询/下载/500ms回退及有限恢复
- [x] 打开弹窗即准备当前词，释义并行；关闭只取消其前台任务/播放，页面缓存保留4分钟；离页/隐藏/账号/版本/权限变化清理
- [x] 不自动播放；每次点喇叭仍联网验权，原有重点词与完整音频行为保持
- [x] Node22执行相关及完整测试、check、H5和微信构建

## Task 3: 集成检查与交付

- [x] 独立审查两个 diff，修复有效问题并重跑受影响验证
- [x] 记录真实执行命令、结果、工具链偏差和未完成真机验收
- [ ] 正常网络且云端/本地已准备后，目标点击到播放 P95≤500ms；iPhone/Android有声录屏确认实际出声，冷词和弱网单列

## Preflight

| Tasks | Shared boundary | Ruling |
| --- | --- | --- |
| 1 / 2 | 现有 GET/POST SpeechState | 不改 HTTP 契约；后台 GET-only，前台 POST 提升 |
| 1 | 事务/worker派发 | admitted 持久化；统一锁序；不新增schema |
| 2 | 页面与弹窗所有权 | 页面 dispose；弹窗只 cancelSelection |
| 1,2 / 3 | 验收 | 自动化和构建不代表真机500ms通过 |
