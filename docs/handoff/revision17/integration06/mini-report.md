# Task 3 小程序实施报告

工作树：`/Users/lubi/Desktop/juya/.worktrees/revision17-integration06/juya-miniapp`。范围仅小程序，未推送、未部署、未修改现有业务运行目录或数据。本地提交：`4cea55979dafc5acc70418a85f1fdce3d5d029e7`（`feat(listening): 实现分类直达文章与预置词汇学习`）。

## 实现

- 首页入口展示「雅思词汇 / IELTS Vocabulary」、约3,700词固定简介与开始学习，仍进入原场景列表；主题听读三组固定介绍与开始听读按当前Figma更新，统计来自真实Home接口，未全局替换场景业务名称。
- 新增 `use-listening-catalog.ts`，复用 `useSceneList`，直接请求 `/listening/articles?category_id=&page=&limit=`。全部顺序采用服务端结果；继续学习始终取独立Home目标，不随分类筛选。详情返回刷新全部已加载页、保留分类和滚动位置；加载更多失败保留现有行，重试原页。
- 保留64px分类按钮、44px触区、三列面板、最高65vh与内部滚动；名称使用 `name_en || name`，允许长名称换行，分类数量不硬编码。新增独立分类进度组件展示真实已学/总数及受限摘要；文章使用真实受控缩略图。文章卡、收藏、记录辅助名改为category_name，并同时展示受限状态及已有学习记录。
- 旧topic页只请求历史 `/listening/topics` 映射真实category_id，再redirect分类文章；读取失败展示可重试错误，不猜分类。`/next`继续复用冻结队列凭证，并使用服务端category_id末篇返回所属分类；完成区文案改分类，不回绕或客户端猜下一篇。
- 新增 `listening-vocabulary.vue`，位于全文译文之后、5表达之前；空词汇全隐藏。按稳定id展示同拼写不同义项，英文和音标20px、释义和原句16px，source.quote原句及按Unicode code point起点确定的段号，缺音标/释义不占位。
- 预置词发音使用真实GET/POST `/articles/{id}/words/{word_id}/pronunciation` 与SpeechState，action为 `listening.word:{article_id}:{word_id}`。复用共享双音轨控制器，暂停全文与高亮尾迹，保持原始进度/倍速；切词/手动全文续播/离页会取消旧发音意图与迟到结果，旧轮次不再轮询或播放；失败在原词条重试。没有单句播放、任意正文音频绕过或静态产品Mock。
- 进入、前台返回、动作、每30秒及权限到期复核。新增每次权限快照重新安排到期复核、正文查词前复核、媒体/预置词接口明确401/403/404立即停音清私有内容，409重新核对版本。失去can_lookup时仍保留can_learn允许的预置词音；正文查词继续单独要求can_lookup，失败不当作免费。
- 从同级API `openapi/mini.json`复制后执行 `pnpm generate:api`；类型全部来自生成声明，未手写修改生成DTO。最后一次快照对API源JSON语义比对相同；已同步API最终重导出的source_hint追加字段，mini正文只使用已确认的source.quote。

## RED → GREEN 证据

- 首轮新增行为用例先RED：两项 `model.pronounceVocabulary is not a function`；三项直达文章/来源恢复用例仍为旧主题列表、未请求新分类文章接口。
- 首页/旧topic兼容用例先RED：首页仍为场景学习旧简介；旧topic仍请求 `/topics/{id}/articles`而非历史映射redirect。实现后绿色。
- 发音权限拒绝用例先RED：POST 403后仍保留article；增加受控资源拒绝清理后绿色。
- 查词前授权复核和新到期边界两项先RED：grant失效仍准备查词、重新收到expires_at后未到期复核；实现后绿色。
- 受限文章保留已学状态用例先RED：原受限分支遮掉完成记录；状态分开展示后绿色。
- 其他回归覆盖免费预置音、同词多义原句、音标缺项、原位重试、切词迟到取消、离页取消、30秒权限复核、版本进度和倍速、详情替换保留列表来源、失败下一页原页重试及全部已加载页恢复。

## 检查与构建

2026-11-01新鲜运行：

- `pnpm check`：format/lint/stylelint/vue-tsc全部通过
- `pnpm test --maxWorkers=2`：93文件，424测试全部通过
- 本地环境 `VITE_API_BASE_URL=http://127.0.0.1:8002 VITE_STATIC_ASSET_BASE_URL='' VITE_REMOTE_FONTS=false pnpm build:h5`：通过
- 同样显式本地变量 `pnpm build:mp-weixin:test`：通过，18页面/三Tab/主入口可达共享音频控制器检查均通过
- 微信主包source=1,064,895B，20%转换预算=1,277,874B，剩余819,278B，要求保留102,400B，预算通过
- `git diff --check`通过
- 测试既有 `app-page.spec.ts`存在原生scroll-view解析Vue warning，但未产生失败；构建有uni-app升级提示，本任务未改依赖

## Figma与资源

已读取figma-design-to-code技能；使用授权Primary、既有session `a4718984-5649-41ef-86d8-562313eee61c`。取得M01 `45:4897`、词汇行 `183:6807`、文章卡 `182:7689`的design_context及截图，参考真实尺寸与颜色。M03整页context超时后改为metadata定位小节点；没有把Figma截图作为产品资产。

背景沿用现有home-watercolor及BG02/BG03外置策略，字体沿用项目DM Sans/Fraunces/Noto Sans SC映射和既有资源；首页/文章卡的已有图标继续精确复用。新增speaker是工具返回的精确20×20 SVG，保存 `src/static/listening/r17-vocabulary-speaker.svg`，无临时Figma URL运行依赖；矢量资源不虚称3x位图。没有新增大栅格图进入微信包。

## 待Task 4/外部验收

本任务测试是组件/组合逻辑/共享请求边界回归，不冒充真实后端或真机端到端验收。controller按Task4继续真实HTTP三端流程、375/390截图对比及多分类视觉验收；真实云词库/TTS/ASR和微信身份/设备前后台、原生发音、手势需另验。未使用远程测试后端或新增H5登录绕过。

## 评审修正 round 1（2026-11-01）

提交：`3ff23558fc3e1b238991a3de346bc35917019108`，`fix(listening): 会话变化时同步重置分类与文章列表`；原head为`4cea55979dafc5acc70418a85f1fdce3d5d029e7`。工作树干净，未推送。

- Important分类重置缺陷已确认：原reset只清空可见category并reset旧list，但其request闭包仍绑定c2。新增 `tests/unit/features/listening/use-listening-catalog.spec.ts`，真实执行catalog+scene-list组合逻辑，网络/会话为受控边界；分别覆盖会话失效和账号切换后重新load，验证可见分类、段内滚动、实际请求及文章数据始终为全部文章，再次select全部也不会遗留c2结果。
- RED：两项分类测试均收到 `/api/mini/v1/listening/articles?page=1&limit=3&category_id=c2`，与期望不含category_id不符。修复将reset改为dispose旧list并createList('')，同步失效旧请求及筛选闭包。
- Important免费发音证明缺口已修正：先增加发音后can_lookup仍false的断言，旧测试RED（实际true）；随后将服务端detail/summary快照从进入到发音始终设为 `can_learn=true,is_free=true,can_lookup=false`，取消仅修改前端状态的做法。断言仍false、仍免费、已执行summary复核、未请求dictionary，并确认实际POST预置词受控发音接口和词音播放/全文暂停。
- GREEN：定向两文件18测试通过；`pnpm check`四项全通过；完整`pnpm test --maxWorkers=2`为94文件426测试全部通过；`git diff --check`通过。本轮仅组合逻辑和测试修正，不修改视觉/契约/构建配置，真实HTTP及视觉由controller继续执行。
- RED日志：`/tmp/integration06-mini-review-round1-red.log`；定向GREEN、完整套件、check分别为同前缀 `green.log`、`suite.log`、`check.log`。

## API冻结契约说明同步（2026-11-01）

API冻结提交 `f5d9ffd6d9cac1284930254f5511475816cbc281` 后，语义比对仅发现 `/paths/api/mini/v1/pronunciation/{credential}/get/description` 一条接口说明变化。重新复制OpenAPI、执行 `pnpm generate:api` 并按项目Prettier格式化；生成声明仅对应注释改变，无DTO或产品实现变化。`pnpm format:check`、`pnpm typecheck`、`git diff --check`均通过，mini OpenAPI与API源JSON语义完全相同；本次未重复与文档变更无关的全套行为测试/构建。

本地小提交：`7ebc1694a095ede20ed309556bac4960300e6d6f`，`docs(listening): 同步受控发音票据契约说明`。工作树干净，未推送。

## T318 权限失效锁定提示修正（2026-11-01）

父进程真实HTTP验收及375/390截图确认关闭免费后正文与词汇会清除，但提示误走加载失败分支。只读核对发现：authorize收到新summary的 `can_learn=false,reason=learning_authorization_required` 后清除article，却保留进入时 `can_learn=true,reason=null` 的旧summary，导致已有「此篇需学习授权」UI未触发。

局部修正：只在服务端明确锁定时保留本次安全summary，以真实reason显示「此篇需学习授权」；锁定AppState保留安全标题、分类返回入口，并接入原有重新加载操作。网络读取失败仍沿用加载失败分支，不增加购买、联系或其他流程。

RED：新增组合逻辑行为测试确认关闭权限后summary仍错误为 `can_learn=true,reason=null`；GREEN：新断言确认article清除、最新权限reason、安全标题/category_id保留、未提交完成请求。3个相关测试文件22用例与 `pnpm check` 全通过，`git diff --check`通过；本轮按controller范围仅定向验证，父进程统一执行最终H5/微信构建与截图复核。

提交：`ca6bb37bda749650ba32c5b41c4ed05a900e0f5a`，`fix(listening): 权限失效后展示学习授权提示`。工作树干净，未推送。RED/GREEN/check日志位于 `/tmp/integration06-mini-locked-{red,green,check}.log`。

## Controller最终复验

最终ca6bb37源码：完整94文件427测试通过（16.41s），H5/微信构建通过，主包1065068B、20%转换1278082B、余819070B。真实375/390 HTTP浏览器首页/分类直达/词汇/11长分类面板及关闭免费30秒清正文并显示学习授权已复验。云和设备边界不变。
