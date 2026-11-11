# CHG0040收紧与CHG0041本地验收

范围：V1.5整合08/设计修订17，T396—T439。三仓现有test增量，无推送、部署、上传OSS/微信、生产或原配置/业务库变更。最终提交与执行日志汇总见本轮SDD task-1-report.md。

API完整SQLite768通过/57条件跳过；独立socket真实MySQL juya_verify821通过/4跳过（3SQLite专用、1Redis），后补独立RedisDB15/Celery1通过，均停止私有实例。ruff/mypy95源文件通过。实际本地8292打开的browser.db已只读备份，仅私有副本0027→0028；58旧表/911行全部原列摘要不变，原文件SHA不变，仅新增批次/明细两表。

mini完整check、137文件826测试、H5/无上传微信local构建通过。20页/三Tab、主包source483801B、预留1516590B（要求102400B）。契约测试实际编译test+旧开关true、production+true/false三产物均无SDK UUID、友盟传输域名、旧开关密钥；隔离测试SDK审计替身不代表真实传输。

后台完整验证与最终总数见配套仓HANDOFF。Chrome隔离Mock HTTP测试两模块各33项/4页真实交互；另外真实临时SQLite完整Alembic0028、双API ready200、dispatcher/worker与后台/小程序H5真实联调2通过。Mock与真实证据区分如下。

## 逐项映射

|编号|实现及验证证据|状态与边界|
|---|---|---|
|T396|mini privacy-service、app-consent-dialog、原生mp-source-navigation冷启动测试|自动告知与登录/统计分离；本版SDK关闭|
|T397|privacy-service北京时间自然日展示/关闭/次日测试|通过，展示即记录，关闭不确认|
|T398|consent-coordinator启动消费、原生home回归|通过，普通返回不再自动提示|
|T399|API test_privacy确认/版本测试、mini必要版本变化回归|通过，terms沿用，privacy/analytics v2需当前确认|
|T400|mini微信空字符串storage回归、换号确认及API稳定身份测试|通过，不继承其他账号许可|
|T401|原生独立三选择登录测试、API独立许可|保存明确许可；真实统计固定未运行，不能声称已采集|
|T402|API necessary login/learning全量、mini仅登录回归|通过，拒绝统计不影响必要业务|
|T403|API test_guest_content正文/音频/原图/预置发音/PDF|通过，游客不创建业务用户|
|T404|test_guest_content、test_learning_access_boundaries|通过，学习授权与登录分别校验|
|T405|login-return、原生来源/进度/暂停回归，settings真实H5取消|通过，不重放原动作|
|T406|API稳定身份并发、mini登录返回原生回归|通过，登录不自动收藏/完成/打卡/播放；设置统计须再次选择|
|T407|app-consent-dialog失败保持、login-return取消、迟到代际测试|通过，未知/失败不假登录|
|T408|API隐私确认/偏好独立表、test_profiles/retired contacts|通过，无联系方式或自动头像昵称收集|
|T409|privacy-service本地撤回/失败/旧回调回归|通过，本版统计运行本已关闭|
|T410|session、privacy-service换号与退出隔离测试|通过，不因确认自动重新登录|
|T411|analytics-events/隔离receiver事件重试及持久去重|通过，产物关闭期间无队列/补报/额外收据|
|T412|API可信user/业务回执与成绩不变测试|通过，统计不反算成绩|
|T413|remote-font-build实际test/prod产物无SDK及传输域名；API旧开关503无收据|本轮真实SDK不运行；真机真实网络未验，不主张已收数|
|T414|真实18352匿名published v2全文与能力false；旧scope失效回归|通过，无需登录可读；新bundle供明确环境配置，未改原私有配置|
|T415|Figma10指定frame高保真/截图核对、复用水彩和控件、44px点击区|通过本地范围；原生Chrome125%待验|
|T416|两列表独立免费模式及原逐项FreeAccessControl|Mock/真实API联调通过|
|T417|use-cross-page-selection稳定ID/首选页、33项跨4页浏览器|通过，重复ID不增加计数|
|T418|composable与浏览器本页取消/回显交集|通过，不隐含全搜索结果|
|T419|路由queryKey、搜索/模块取消真实Chrome流程及受控条件|通过，page排除key，取消不改路由或选择|
|T420|独立freeIds和普通本页selected，进出清两集合|通过，原发布/删除规则不扩大|
|T421|API完整预览、Chrome33行滚动全名单|通过，发布/删除/分类权限/版本重读|
|T422|API已目标/草稿/删除/缺失跳过、执行权限变化失败|通过，跳过不能转适用|
|T423|API无适用409、确认按钮禁用；浏览器取消预览零写|通过，取消保留查询/选择/页码|
|T424|API并发同key/租约过期重投/版本冲突；后台提交和选择禁重复|真实MySQL与Chrome通过|
|T425|成功/跳过/失败合计，未知原Operation，失败子集重preview/retry|API/Mock流程通过；真实33项任务成功通过|
|T426|AccessHistory before/after+batch关联及事务；真实汇总重载|通过，只改免费字段和汇总revision|
|T427|API正文/图片/音频/PDF旧票据逐请求撤权，历史表回归；真实旧音频票据403|通过；已经下载的字节不承诺回收|
|T428|公开account/settings，游客和登录profile入口设置|unit/真实H5通过，不需登录|
|T429|普通两行设置、正式policy?kind全文，BG04复用|真实匿名API/H5通过|
|T430|既有首次/按需/原登录policy入口及日频三选择回归|通过，不改必要平台授权|
|T431|游客打开不登录，主动统计原位提示，取消原sheet|真实H5网络断言0 auth/wechat请求通过|
|T432|privacy-service撤回与必要业务/API全量|通过，不影响成绩/收藏/打卡|
|T433|safeTarget settings合法query、settings snapshot、旧无kind链接redirect|原生/单测/真实H5通过|
|T434|Figma高保真设置与10frame、既有AppPage/AppPrivacySheet/BG04|通过本地样式范围，未新增外部素材|
|T435|三仓本轮HANDOFF与本文件、主版本/设计17保持|本地交付；未远程发布|
|T436|实际Chrome复现旧17px/EP transform冲突；18px与勾号/半选线显式reset|矩阵8组合标记中心偏差均0|
|T437|52px固定列、44px点击区，header/row/toolbar中心测量|8组合中心差0；125%布局18→22.5px、44→55px|
|T438|unchecked/checked/indeterminate/disabled/focus截图；task pending禁选择|Mock Chrome状态与实际ID一致|
|T439|Chrome1440×1025、1911×837，100%及125%CSS layout矩阵10通过|原生Chrome125%未验：工具拒绝CUA原生App访问后已停止该会话|

## 视觉与联调证据

本轮工作区 `.superpowers/sdd/2026-11-11-chg0041/screenshots/` 保留35份文件：8组合ordinary/free-focus/disabled截图24份、中心JSON8份、真实H5设置/取消与真实API后台3份。中心测量等待ElementPlus状态变换动画完成，区分布局与屏幕CSS坐标；不是放宽偏差掩盖问题。

`/tmp/chg0041-admin-centers3.log`：10通过，含2个完整Mock工作流及8组合视觉/状态；`/tmp/chg0041-live-final.log`：2个真实API工作流通过。单测先观察RED的具体功能：preview404、legacy统计错误可用、发布名称误取草稿、逐项异常回滚兄弟项、租约耗尽留pending、选择composable/设置缺失、游客关闭sheet、取消失败重试丢结果入口、processing选择围栏；对应GREEN与完整回归均归档于SDD报告。

## 留待设备/发布环境验证

微信真机、真实友盟网络/接收没有执行；当前产物完全不装载SDK，不以收数为本轮完成条件。原生Chrome125%缩放未验证，125%证据仅CSS布局缩放。后续启用统计须换成经核验符合五类事件与最小引用的方案，重新确认实际披露/许可，不能恢复旧SDK开关。后续部署应明确配置新v2政策bundle，本轮原本地及远程配置/数据保留。
