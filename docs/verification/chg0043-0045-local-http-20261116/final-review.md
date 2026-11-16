# CHG0043—0045 三仓整分支最终审阅

审阅范围为 API `82a4362..8f3f25c`（业务冻结于 `904afb4`）、后台 `97bd6ea..cea5772`、小程序 `56ded7b..6e618b1`。对照用户 Word、设计、计划、接口交接、三仓完整审阅包、既有复审处置和52项台账，重点追踪跨仓请求、迁移旧状态、来源匹配及身份切换。以下路径以标注仓库为根。

## Strengths

- 类型有独立的不可变版本。发布共用预览指纹，事务中一起绑定正文、附件和类型。只改分类或附件保留正文版本与排序。迁移0029以可空扩展保存旧数据，旧发布卡须按管理员所见快照确认，启用前另行核验当前发布集合。
- 管理双列表在一致读事务内按同一归属表达式查询行和四项统计，搜索、页码与分类总数职责清楚。有发布版时保留发布归属，后台另示草稿拟改分类。页码回退及改筛选的迟到请求有代次检查，跨页免费选择绑定稳定ID。
- 重复明细关联批次、源路径、候选和命中目标，兼容旧听读摘要与已跳过记录。目标移除后仍可保留跳过事实。归类批量预览展示稳定候选与受影响范围，未知原始分类须单项处理。
- 待学列表与队列在服务端按类型和本人完成记录筛选。复习沿用原来源语义。小程序分开保存两类页范围，按身份及请求代次接纳结果。两份前端OpenAPI与后端分别解析比较均完全相等，包括 paths 和 schemas。
- 已有真实HTTP夹具覆盖管理分页、游客双栏、ZIP到发布、PDF冲突及听读词形；修复前后的自动化、最新业务专项与官方CI的证据范围写得清楚。

## Critical

无。

## Important

### I1　完成请求未到服务端时，冷启动后的本人待学列表无法恢复（T460）

**触发。** 使用正常详情操作完成一张卡，网络失败使 POST 未到服务端。关闭小程序进程、重新打开同一账号，从首页进入待学列表。后台查询该原键始终返回 `404 operation_unknown`（API `src/juya_api/operation_api.py:29`）。此时没有可取回的成功回执。

**证据。** 小程序 `src/sub-packages/scenes/detail.vue:1371` 发起完成时只传 `version_id`，未启用已有的冻结正文持久化。原键/路径在请求发出前存储，原正文默认只在内存（`src/services/operation-service.ts:185`）。进程重启后查无回执时，即便显式调用默认允许重试的 recover，也因缺少冻结正文而直接抛错（同文件 `:119`）。列表的两栏均先只读查询（`src/pages/learning/index.vue:78`），唯一的恢复按钮再次执行同一只读刷新（同文件 `:448`）。新的列表组件没有可供用户返回原详情的可信卡片快照。

**定点复现。** 实际加载冻结版本的 createOperationService、ApiError 和存储常量，通过内存端口模拟请求未送达并保留本人存储，重新构造实例模拟冷启动。连续两次只读 recover 和一次显式默认 recover 均得到 operation_unknown，调用顺序为 POST、GET、GET、GET，pending 仍为 true，持久化 frozenRequest 为 false。两个分类均无法开始读取。此问题与上一轮修复的“POST已提交后先查回执”是两种不同结果，上一轮修复应保留。

**修正与验收。** 按本人隔离持久保存这类无自由文本的原完成请求（原路径、原键、原正文版本）。自动返回与登录恢复继续只读。对查无回执提供用户可达的显式恢复操作，查询后才能按原键处理；还要给已存在、缺冻结正文的历史 pending 留出可恢复路径。覆盖持久存储+新进程无列表快照、原请求从未成功、曾成功但响应丢失、当前卡已改版及切号隔离。成功回执只消费一次，确定失败允许列表重新读取，网络尚不确定时保留原操作。

### I2　历史核对页把已经明确移除的 PDF 展示为有效发布 PDF（T475）

**触发。** 一张曾有 PDF 的发布卡由管理员移除 PDF 并发布，打开历史核对页。对已归类的卡取消“仅未归类”即可查看该状态。0029前已做过同样操作的旧卡在默认待核对列表也会遇到。

**证据。** API `src/juya_api/study_notes.py:333` 为明确移除也写笔记版本，media_id 为空但版本ID有效。`src/juya_api/content_types.py:143` 从有效资源生成建议，并另外保留指针ID供快照核验。后台 `src/features/scenes/scene-type-history.vue:157` 却直接用该ID判断“有效发布PDF”。正常移除不会产生 invalid_pdf 告警。对本轮真实HTTP合成库只读查询，实际有 **2张** 未删除的已发布图解卡同时满足当前笔记版本存在、所属卡正确、media_id为空。核对行会同时显示“有效发布PDF”和“建议图解词汇”。损坏的非空引用也会同时显示“有效发布PDF”和异常提示。

**影响与修正。** 此处是管理员对历史真实内容明确归类的主要依据，错误信息可诱使管理员选择精读并反复被后端拒绝。后端仍能阻止错配。展示应消费服务器验证过的有效附件状态，区分无有效附件和异常引用，保留原指针用于并发核验。测试包含从未设置、可用、明确移除和异常引用，并核对建议与附件文案。

### I3　以 e 结尾的派生规则把其他常用词的进行时绑定给错误词条（T481、T484—T486）

**触发与结果。** 使用资料词 dye（染色），正文为 “The plant is dying.”，没有提供原句。两模块均自动绑定 dying，听读词汇发布校验返回零错误。换成正确正文 “She is dyeing the fabric.”，两模块反而无来源。资料词 singe（烧焦）与正文 singing/singeing 遇到同一问题。用 die→dying、sing→singing 做对照则正常。

**证据。** API `src/juya_api/vocabulary_matching.py:213` 统一去末尾 e 再加 ing，双向词形比较直接信任这一候选。以上六个例子均以冻结 HEAD 的真实 resolved_scene、resolve_vocabulary_sources 和 vocabulary_errors 直接复现。错误来源可通过词汇发布校验，和界面是否显示手动校对无关。用户会看到“染色”绑定 dying 或“烧焦”绑定 singing。

**修正与验收。** 限定保留 e 的可靠形式，排除错误拼法，两组词分别验证正向和反向，以及至少一条经过发布校验的错配反例。保留现有 go/do 复合词、双写规则、资料释义与合法重叠行为。

## Minor

历史确认子弹窗的“取消”会解除冻结的待确认操作，右上角关闭和 Escape 只改变 confirmOpen。后台 `src/features/scenes/scene-type-history.vue:147` 因 pending 继续禁用勾选与类型选择。触发方式为勾一行、打开确认、按 Escape、尝试改选。可以再次打开再点“取消”恢复。统一无在途写请求时的关闭处理即可。不影响已确认事务。

## Declined to judge

- 场景释义、音标原本选填；听读若提供词条则须填释义。按原文与已记录的I3撤回结论，未把场景空释义计入问题。
- 合法重叠词组、人工选定且可验证的两处独立位置属于原有行为。同义多处采用首个可靠位置，不能从坐标交叠单独判定错误；本审未要求穷举英语词典。
- 分类别计数与同类型队列就绪之前显示准备中，以及分类来源变化要求重进，符合既定发布顺序。复习仍使用收藏、记录或日期来源，未要求加待学过滤。
- 已有账号存在未知完成时暂缓两栏的自动刷新是既有明确决定，本审未要求自动写完成。I1仅针对服务端确无回执、进程重启丢失原正文后用户也无恢复路径。
- 历史确认只对当前有效发布生效，真实卡的明确归类属于目标环境管理员操作。未用合成库核对替代线上确认。生产归类、历史成绩/素材清理不在本轮。
- 学习授权、内置查词和动态听读高亮留在暂停状态，未将恢复这些能力列为要求。
- 真机微信/iOS/Android、测试环境部署、最终SHA官方MySQL/Redis全量及回滚验证属后续环境证据。已核对本地真实HTTP日志与归档范围，未将设备缺失、CSS缩放、第三方服务或已有浏览器/jsdom提示判为分支缺陷。

## 可重放的局部验证

命令只读取源码或隔离的合成 SQLite，操作恢复例使用内存端口。本轮运行输出如下。

### I1

```sh
cd /Users/lubi/.codex/worktrees/chg0043-0045-miniapp/juya-miniapp
/Users/lubi/Desktop/juya/.tools/node-v22.23.3-darwin-arm64/bin/node <<'JS'
const ts = require('typescript'), fs = require('node:fs')
function load(file, deps) {
  const s = ts.transpileModule(fs.readFileSync(file,'utf8'), {
    compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}
  }).outputText
  const exp = {}
  new Function('require','exports',s)(p => deps[p], exp)
  return exp
}
const errors = load('src/services/errors.ts', {})
const constants = load('src/shared/constants/http.ts', {})
const {createOperationService} = load('src/services/operation-service.ts', {
  './errors': errors, '@/shared/constants/http': constants
})
const storage = new Map(), methods = []
const ports = {
  key: () => 'fixture-key',
  session: {
    userId: () => 'fixture-user',
    request: async (path, options) => {
      methods.push(options?.method || 'GET')
      if (options?.method === 'POST') throw new errors.ApiError('network_unknown','lost')
      throw new errors.ApiError('operation_unknown','no receipt',404)
    }
  },
  storage: {
    get: k => structuredClone(storage.get(k)),
    set: (k,v) => storage.set(k,structuredClone(v))
  }
}
;(async () => {
  let service = createOperationService(ports)
  try {
    await service.run('complete:card','/api/mini/v1/cards/card/complete','POST',{version_id:'v1'})
  } catch {}
  service = createOperationService(ports)
  const action = service.pendingActions('complete:')[0]
  for (const mode of [{retry:false},{retry:false},{}]) {
    try { await service.recover(action,mode) }
    catch (e) { console.log('recovery', mode, e.code) }
  }
  console.log('pendingAfterColdRestart', service.pending(action), 'requestMethods', methods,
    'frozenBodyPersisted', Boolean([...storage.values()][0]?.[0]?.frozenRequest))
})()
JS
```

```text
recovery { retry: false } operation_unknown
recovery { retry: false } operation_unknown
recovery {} operation_unknown
pendingAfterColdRestart true requestMethods [ 'POST', 'GET', 'GET', 'GET' ] frozenBodyPersisted false
```

### I2

```sh
cd /Users/lubi/.codex/worktrees/chg0043-0045-api/juya-api
python3 - <<'PY'
import sqlite3
from pathlib import Path
db = Path(Path('/tmp/juya-chg0043-live-location').read_text().strip())/'test.db'
conn = sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)
print('removed_pdf_with_active_version_pointer', conn.execute("""
  SELECT COUNT(*) FROM cards c JOIN card_study_note_versions n
    ON c.current_study_note_version_id=n.id AND c.id=n.card_id
  WHERE c.status='published' AND c.published_content_type='illustrated'
    AND c.deleted_at IS NULL AND n.media_id IS NULL
""").fetchone()[0])
PY
rg -n "row.study_note_version_id \?" /Users/lubi/.codex/worktrees/chg0043-0045-admin/juya-admin/src/features/scenes/scene-type-history.vue
```

```text
removed_pdf_with_active_version_pointer 2
157:            >{{ row.study_note_version_id ? '有效发布PDF' : '无有效发布PDF' }}
```

### I3

```sh
cd /Users/lubi/.codex/worktrees/chg0043-0045-api/juya-api
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from juya_api.content_service import resolved_scene
from juya_api.listening_vocabulary import resolve_vocabulary_sources, vocabulary_errors
cases = [('dye','The plant is dying.'),('dye','She is dyeing the fabric.'),
         ('singe','They are singing together.'),('singe','The heat is singeing the paper.'),
         ('die','The plant is dying.'),('sing','They are singing together.')]
for term, sentence in cases:
    word = {'id':'w','english':term,'meaning':
            {'dye':'染色','singe':'烧焦','die':'死去','sing':'唱歌'}[term]}
    scene = resolved_scene({'dialogue':[{'id':'l','english':sentence}],
                            'vocabulary':[word.copy()]})['vocabulary'][0]
    hearing = {'body_en':sentence,'vocabulary':[word.copy()]}
    resolve_vocabulary_sources(hearing)
    result = hearing['vocabulary'][0]
    print(term,sentence,'scene',scene.get('source') and scene['source']['quote'],
          'listening',result.get('source') and result['source']['word'],
          'hearing_vocabulary_errors',len(vocabulary_errors(hearing)))
PY
```

```text
dye The plant is dying. scene dying listening dying hearing_vocabulary_errors 0
dye She is dyeing the fabric. scene None listening None hearing_vocabulary_errors 1
singe They are singing together. scene singing listening singing hearing_vocabulary_errors 0
singe The heat is singeing the paper. scene None listening None hearing_vocabulary_errors 1
die The plant is dying. scene dying listening dying hearing_vocabulary_errors 0
sing They are singing together. scene singing listening singing hearing_vocabulary_errors 0
```

## Recommendations

三项 Important 集中修复后，限定复审核对冷启动显式恢复、历史附件状态及两组词形对照，并更新对应验收台账。复用已有真实 MySQL 业务专项和三仓联调证据；最终推送 SHA 的官方 CI、目标环境迁移与真机状态各自记录。

## Ready to merge

**With fixes.** 建议先闭环 I1—​I3，再进入已授权的测试部署。未改动三仓源码、索引或分支，未部署、推送或写入业务数据。
