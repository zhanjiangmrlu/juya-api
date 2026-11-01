# Task 2 · 整合06 Element Plus 后台实施报告

状态：实现及完整本地验证完成；本地提交 `6f39ccc`（`feat(listening): 整合分类词汇核对与逐项免费管理`），最终浏览器视觉证据由 controller 汇总。

工作树：`/Users/lubi/Desktop/juya/.worktrees/revision17-integration06/juya-admin`。仅本地实现，不推送、不部署、不迁移生产、不读取账号密钥。无子 agent／额外评审 agent。

## 实现范围

1. 两个 Element Plus Tab：文章／分类。移除主题、免费数字、全局免费排序入口及其旧写入弹窗；历史管理路由分别重定向到分类或文章。
2. 分类新增／编辑、当前页选择和逐项删除反馈、带完整版本集合的分类排序；只维护分类内文章顺序。保留稳定身份和版本引用。
3. 文章与场景逐行免费控制，使用各自 `free_revision`；独立 pending／失败／未知状态，未知先查原操作回执，再按原 key／body 恢复。成功／冲突读取真实对象及全量只读汇总，保留筛选、分页、勾选、滚动；列表刷新不卸载其他行的未知操作。
4. 编辑／导入／发布版预览直接使用 category 契约；草稿迁类不改变发布版预览归属。
5. 共用 Element Plus 重点词汇维护模块：稳定 id、不同义项独立、添加／删除／排序、当前正文原句和实际词形选择、来源确认与有效性校验。Unicode 码点位置、完整原句和 ASCII 英文词边界与 API 一致。空词汇仍可发布，阅读预览整个词汇区隐藏。
6. 复用 `useWordPronunciation`、`loadPronunciation` 及现有音频焦点，仅按已保存文章 revision／发布 version_id 或批次 revision／词条 ID 请求受控单词音频。未保存修改禁试听，切词／离开停止，失败原位重试，不写用户学习成绩。
7. DOCX 帮助／模板入口／核对说明统一：唯一中文 H1，英文标题／分类元信息，正文／译文／5 组语块 H2；选填重点词汇四列表，兼容旧无词汇和旧主题字段。候选显示词汇数、来源问题，保留 `source_hint` 原句；无有效来源不计为合格发布项。
8. 保留批次恢复、目标版本绑定与差异、fingerprint／revision、双出口、成功项不重做、仅原失败项重试；补齐候选暂存未知回执恢复，原未知 PUT 不重复发送。
9. 同步 API 的 `openapi/admin.json`，执行 `pnpm generate:api`，未手写生成契约。

## TDD 证据

均执行目标 Vitest 命令观察实际断言失败后实现／修复，再观察绿色结果；最早的新组件 import 缺失不计作有效 RED。

- `free-access-control.spec.ts`：初始点击无写请求、无未知查询、无错误恢复 3 个断言失败；实现后 3 通过。核对只写本行、PUT 免费版本、未知先查 receipt、冲突恢复真实状态。
- `listening-vocabulary-model.spec.ts`：初始未返回 Unicode 原句／词形、未要求词形确认失败；补充唯一精确词无需确认、多来源须确认，以及完整句界／非法英文 RED；最后 4 通过。
- `listening-vocabulary-editor.spec.ts`：添加未发出更新、无来源状态失败；实现增删排序稳定身份后通过。新增 DOCX `source_hint` 不显示的 RED，显示原句后通过，合计 3 通过。
- `listening-content-form.spec.ts`：旧主题表单不能接受直接分类，且缺词汇编辑；改为直接分类／共用词汇模块后通过。
- `listening-settings.spec.ts`：分类篇序未请求 `scope=category&category_id=` 的 RED；实现后与未知分类保存、当前页批删、引用反馈、排序一共 6 通过。
- `listening-list-page.spec.ts`：旧主题／全局／数字入口仍存在的 RED；改成两 Tab／逐行免费后通过。真实浏览器发现 Select 默认英文及满行后新增 RED（实际 `SelectSelect`），改中文占位／空值语义后 7 通过。
- `listening-docx-import.spec.ts`：`category_id` 确认后未带入的 RED；改后通过，同时验证原音频／原图保留。
- `listening-preview-panel.spec.ts`：有词汇时未展示词汇区的 RED；改后无词隐藏／两义项显示通过。
- `listening-model.spec.ts`：无 source 的 complete 候选被误计 publishable 的 RED；加词汇合法性后通过。
- `listening-import-page.spec.ts`：未知候选暂存被重复 PUT（实际 2 次、期望 1 次）的 RED；原 receipt 恢复后通过。原成功项不重做、仅失败、批次分页、目标更新等回归保留，合计 6 通过。
- 场景列表：旧数字入口／缺逐项按钮的 RED；修后 11 通过。补需学习授权状态标签 RED→GREEN。
- 发布版预览：改为发布分类 fixture 后旧 topic 读取与名称推导失败；直接发布分类和独立目录失败降级后 3 通过。

## 视觉依据及真实验证边界

已读取 `figma-design-to-code`；沿用既有 session／Primary，从当前 Figma 小节点取得高保真上下文和截图：A25 词汇卡 `191:4847`、A01 Tab `182:12255`／汇总 `182:12261`／工具条 `182:12272`、A02 分类表 `182:12812`。初始 root metadata Transport closed 后只请求具体小节点，未整页超时重试。

复用项目 token、布局和现有精确资源；词汇确认 SVG 为 15×15，搜索 SVG 为 16×16，下载至版本化本地 assets，不引用临时 Figma URL。A01 工具条最终搜索 258×40、分类／状态各 142×40、10px 间距，窄屏自动换行；汇总白底／67px／24px 数字与 Tab 15px。

controller 已报告隔离真实 HTTP 浏览器：管理员登录→分类列表→ZIP→词汇核对→暂存→发布→开启免费闭环通过，新增文章 1 篇、词汇 2 条。初次真实截图发现来源确认提示过严，以及 Select 英文／满宽问题，均追加 RED→GREEN 后修正。最终 1440／960 截图以 controller 的 Task4 证据为准。

新增 `tests/e2e/integration06-live.spec.ts` 支持显式本地 fixture／storageState；本 agent 未独立执行该浏览器 spec，不将该文件存在计作通过。4 份依赖旧主题／M 契约 live 文件明确历史停用，避免继续运行过时验收。

真实云词库／发音／ASR、微信真机不在本任务已验范围；受控单词发音复用本仓既有取消／焦点测试能力，最终真实云音频由 Task4 单列。无静态 mock 产品行为。

## 完整检查

- `pnpm check`：通过，包含 Prettier／ESLint／Stylelint／vue-tsc／tsc
- `pnpm test`：56 文件、233 测试通过，28.07s；无 Unhandled Error
- `pnpm build`：通过，766ms
- `git diff --check`：通过
- OpenAPI 与同级 API 最后导出语义同步，执行生成命令；无手写生成类型

唯一保留提示为既有 jsdom `HTMLMediaElement.pause()` 未实现；未新增测试失败或未处理异常。

## 主要文件

- `src/features/learning-access/free-access-control.vue` 及行为测试
- `src/features/listening/listening-vocabulary-{model.ts,editor.vue}`／`src/composables/use-listening-pronunciation.ts`
- `listening-content-form.vue`／`listening-reader.vue`／`listening-preview-panel.vue`
- `listening-settings.vue`／`listening-catalog-list.vue`／编辑、导入、列表及发布预览页面
- 场景列表、路由、项目 token 样式、2 个精确 SVG 资产
- OpenAPI／生成类型、HANDOFF／整合06交接、新 live 测试及历史入口隔离


提交后 `git status --short` 为空，48 个文件纳入本地提交，未推送。提交钩子 ESLint／Stylelint／Prettier 全部通过。

## 后续真实浏览器复验与测试就绪修复

controller 已确认最终 `admin-list-final-1440.png`／`admin-list-final-960.png` 中两个筛选框均为142px、中文状态且位置正确，并曾运行本次真实 HTTP live spec，1 passed（3.0s）。

固定最终 API 重启后的再次执行暴露测试就绪竞争：导入页 `onMounted` 读取目录和可恢复批次期间，上传按钮及文件 input 都正确 disabled；Playwright `setInputFiles` 没有等待启用，直接触发 change 后被上传 handler 的 busy 守卫忽略。正常用户无法点击该禁用按钮，未发现产品事件在可操作状态丢失。

小提交 `c1357ff`（`test(e2e): 等待导入控件就绪后上传资料`）仅对 DOCX／ZIP 两处上传加入 `await expect(input).toBeEnabled()` 后再 `setInputFiles`，未加 sleep 或修改 timeout／产品逻辑。目标文件 Prettier／ESLint、`git diff --check` 与提交钩子通过；最终真实 live 由 controller 复跑，不重复无关全套或构建。

## Controller固定代码复验

c1357ff仅补测试输入就绪等待；最终实际Chrome live 1 passed（2.4s）。首次重验目标离开当前页、第二次输入禁用尚未就绪均属验收fixture/readiness问题，修正数据选择及显式等待后通过；没有绕过产品上传guard。
