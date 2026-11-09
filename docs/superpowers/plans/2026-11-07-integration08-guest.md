# 整合08游客体验实施计划

目标：按用户批准方案，在既有整合07基础上完成CHG0038游客体验与按需登录，仅本地开发和验收。
需求真源：/Users/lubi/Desktop/juya/句芽英语V1.5-整合08-修订17-开发完整交付版-20261106.docx，SHA256 11bf68100627426011557494f7cc634cd96978194f9efed1c5d5f353a340d4bd。
设计：Figma yVnE9TCSoRS5sv4vAuxsBX，当前导航277:5040；游客首页45:4897，场景45:4984，笔记303:5040，听读45:5089/274:5192/45:5589，场景详情9:348，受限274:5727，提示274:5883，记录45:6764，账号45:7106，登录9:328。

## Global Constraints

- 本地隔离开发；不推送、部署、微信上传、远程迁移；保留原账号、配置、素材和业务数据
- 默认schema0026/contract3，不新增数据库迁移；管理员与个人读写继续强鉴权
- 游客不创建User/MiniSession/ReadingStart/学习进度/收藏/完成/打卡或个人Operation
- 游客只能读取当前发布未删除免费内容；受限仅摘要；正文任意点词要求有效学习授权，登录不授予学习授权
- 原水彩布局、三Tab、R2线条Tab、字体及资源复用；保留整合07 PDF独立版本与发布事务
- 本地手动验收用指定账号资料内统一管理员；测试只用隔离夹具；敏感资料不输出不入Git
- Git标题 type(scope): 中文说明；源码风格按AGENTS.md；不在Git复制需求全文

## Review Focus

1. 免费关闭/下线/删除/版本撤换后旧资源GET HEAD Range不能绕过
2. 游客预置词汇发音不能变为任意文本TTS或正文查词
3. 401只能匿名重查公共读一次，不能重放写操作
4. A账号→游客→B账号的迟到回调、PDF文件、队列和个人显示隔离
5. 登录返回不得自动播放/打开PDF/收藏/完成/打卡或迁移游客进度

### Task 1: API游客内容及受控资源

负责API源码、测试、OpenAPI及契约文档；前端由Task2修改。
- 复用现有读取接口增加optional_learner：无Authorization为None，非空无效/过期凭据401；个人/admin接口保留原依赖
- cards/listening home/categories/articles/detail/当前发布summary支持guest；state/statistics/progress/authorization/continue_learning/queue_token等个人字段为null；保持登录响应语义
- 游客cards默认全部published，显式uncompleted也规范为published；notes全量有效发布PDF；同一集合过滤计数排序分页；不查个人学习表，不写ReadingStart，guest mark_started永不写
- 受限detail403；复用当前已发布安全摘要；旧个人历史summary仍本人归属鉴权；摘要不得含正文、预置原句或PDF元信息
- public资源票据独立格式和用途白名单，300秒，绑定scene/listening/id/body或note版本/media或word；复用加密与代理，不改MediaTicket非空用户约束；旧私有票据失败禁止回退public
- summary只可已发布缩略图；正文音频/原图/PDF/预置发音每次签发与GET HEAD Range重验发布免费及当前版本，no-store，不暴露永久存储地址
- private票据和同会话Bearer PDF原规则保留；正文dictionary仍learner+有效授权
- 预置词汇仅word_id+发布版本定位，复用共享缓存、去重、冷却；抽离不依赖User的发音任务准备；Job owner_kind=mini owner_id=public-pronunciation，经现有mini-worker，不创建用户或个人Operation
- RED先写真实HTTP/数据库测试，GREEN实现；无个人事实增长、免费/受限、非法身份、摘要白名单、伪造引用、票据版本/权限撤销、私有鉴权覆盖
- 运行静态检查、API完整SQLite回归；真实MySQL/Redis若环境可用在专用隔离库测，未验如实记录；生成OpenAPI并提供接口接入说明
- 提交当前任务修改，报告RED/GREEN命令、结果、兼容决定、未验证项

### Task 2: 小程序游客与按需登录

依赖Task1生成mini OpenAPI与接口接入说明，负责小程序源码/测试/生成契约。
- contentRequest允许匿名或有效会话，private request仍强鉴权；401清个人态，只公共读匿名重试一次；不得重放POST和账号写入
- account.restore无token不请求本人API；游客/恢复中/登录态代际隔离，禁止旧响应污染；页面浏览去掉ensure门槛
- 首页/场景双Tab/听读/详情显示真实发布免费内容及受限摘要；guest全部场景为published，无个人统计及已学假数据；记录/账号游客说明态保留三Tab、登录、继续浏览、隐私
- guest阅读/译文/倍速仅本次内存，不写本人进度、不创建服务器来源队列；登录后真实账号数据优先，不自动上传guest快照
- 收藏/完成/打卡/本人资料/反馈触发登录后可保存学习记录和收藏提示，登录或继续浏览；U00主动进入，隐私默认未勾选
- navigateTo保栈，来源快照含page/type/id/tab/category/scroll/translation/audio位置倍速及版本；登录前先取快照再清身份，单次移交；取消失败原位，不循环；成功重读权限，mark_started=false只读恢复，无自动播放/PDF/收藏/完成/打卡
- 来源失效场景回原Tab、听读回有效分类或全部、最后home；已完成不强插待学；用户再次主动操作时才建当前身份来源队列
- PDF下载按公私票据决定Authorization，无token也可合法public；guest epoch或account+card+noteversion隔离文件，下载前后重验，先暂停全部音频，返回手动续播
- 主动退出停播/取消异步/清个人资料/队列/输入/文件/恢复目标回guest home；会话过期清个人态重查，免费guest继续/受限摘要，不强跳登录
- 分享完整小程序按接收者身份免费guest直开，朋友圈browse_only保留平台安全承接
- 复用Vue3 script setup/箭头函数/注释/SCSS/既有组件资源；先RED测试后实现，全部单测/静态检查/H5与微信本地构建，勿运行上传脚本

### Task 3: 三端联调与验收交接

- 对Task1/2逐项审查修复，后台原免费开关/发布/PDF/ZIP回归，不改后台业务或CLI
- T01—379逐项追踪：原用例按整合08修订，重点T356—379及旧T01/T13/T148—151/T160/T168/T182—183/T324/T341/T347
- API隔离SQLite/MySQL/Redis、前端单测/静态检查/构建、本地浏览器；iOS/Android PDF、蓝牙/系统面板、前后台、分享须设备实测，无法完成明确待验
- 更新真实需求引用、配套commit、接口契约、进度和HANDOFF；不复制需求全文，不将历史证据冒充本轮通过
