# 所有格与人工来源修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现用户要求的所有格匹配、人工兜底与红色待核对提示。
**Architecture:** 共享自动规则与人工坐标校验分离，两个适配器保留各自坐标制；后台显式提交人工词条依据。
**Tech Stack:** Python/FastAPI/Pydantic、Vue3/Element Plus/SCSS、pytest/Vitest/Playwright。
**Spec:** docs/superpowers/specs/2026-11-16-vocabulary-manual-source-design.md

## Global Constraints

- 基于现有test隔离工作树；不改原业务数据、配置或生产
- 场景UTF-16、听读Unicode码点；人工片段必须来自当前正文并绑定当前词条
- 保留现有暂停开关、义项独立、原选填规则和导入判重语义

## Review Focus

- 弯引号/emoji坐标；反向所有格及无关词误配
- 人工未知词形保存预览发布后仍保留，非人工未知仍阻止
- 越界、伪造、正文变化、词条变化不能保留旧确认
- 自动预览不得吞掉听读待选词形原句状态
- 红色异常对比及手动通过文案不混称自动通过

### Task 1: 匹配与校验

Files: vocabulary_matching.py、content_service.py、content_contracts.py、listening_vocabulary.py、listening_contracts.py；tests/test_vocabulary_manual_sources.py。
Interface: 两种Source新增manual_english?: string|null；人工依据通过真实坐标校验，自动来源保持旧形状。
- [x] 先写失败测试：双适配所有格、未知人工保存/预览/发布、篡改及词条变更、同处两义人工独立
- [x] 执行pytest观察预期失败，再实现共享规则与双适配校验
- [x] 定向回归并导出OpenAPI至两前端，重生成类型

### Task 2: 后台人工操作与提示

Files: scene-word-source.vue、scene-content-form.vue、vocabulary-source-review.vue、listening-vocabulary-editor.vue、listening-vocabulary-model.ts、content-catalog-model.ts及相关测试。
- [x] 先写组件失败测试：人工来源标记、待核对红色、人工成功文案、听读原句未选词不被后台预览清理
- [x] 实现人工标记与红色提示；沿用原有选择器，不新增重复页面
- [x] 全量API及后台测试、静态检查、构建；小程序生成契约检查；浏览器核对真实选择及红色视觉
- [x] 独立审阅修复范围，记录验证和最终发布状态，交付

### 最新授权：合并远程test并发布测试

用户随后要求合并其他对话的test内容，改完直接部署测试；短暂暂停指示已被覆盖。

- [x] 完成修复、独立审阅与失败回归修正，保留原本地配置和数据
- [x] fetch核对远程test，将后台其他对话3e215b9组合到发布包；378测试/check/build及14项Chrome通过
- [x] 等官方CI43864923777完整1026/3及两个镜像成功，核对摘要和固定源码
- [x] 实际空间预算、精确重复缓存清理；原生预检、停写备份并下载本地核对SHA
- [x] 无schema变更部署7服务，维护内数据/权限/规则/健康校验通过，再恢复流量和finalize
- [x] 发布组合后台并核对78安装文件与51公网首页/JS SHA，归档最终回执
- [x] 小程序仅契约变化，原运行开发版保持，本轮不重复上传微信或OSS

所有完成依据与真实账号/真机未验边界见docs/verification/vocabulary-manual-source-20261116.md；纯文档更新不重新生成应用制品。
