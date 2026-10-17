# T01—T113验收映射（执行中）

本表把需求条目映射到代码与证据，**不是113项全部通过的声明**。自动测试和本地合成账号浏览器验证不能替代真实微信、生产OSS、全状态视觉及同机压测验收。原需求T90/T112的历史迁移要求按用户本轮指令改为全量清空重建。

后端测试位于本仓库`tests/`。前端测试和`docs/verification/core-loop.md`、`advanced-content.md`位于各自juya-admin/juya-miniapp仓库；这些文档保留截图和操作边界。测试文件简称省略.py/.spec.ts扩展名。

| 条目 | 操作 | 验收预期（本轮覆盖后） | 模块 | 已有证据入口 | 当前边界 |
| --- | --- | --- | --- | --- | --- |
| T01 | 首次进入无有效会话 | U00默认未同意，等待主动操作，不建业务账号、不返回个人学习数据 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T02 | 未同意点主按钮／仅看隐私 | 仅提示或打开说明，无登录调用，无建档，关闭回原位置 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T03 | 联系方式均为空的新用户主动登录 | 身份校验建档成功即进入U01，A05/A06可查并计A07，不要求补资料 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T04 | 已同意点击同意并登录 | wx.login凭证交服务端校验，可信身份映射稳定用户，界面无手机号授权及微信号备用表单 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T05 | 首次成功建档 | 默认头像与学习者，可选联系为空，注册时间固定；后台0学习合法 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T06 | 凭证／服务端失败或超时 | 留页重试或查结果，不假成功，不建游客学习，不因结果丢失重复创建 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T07 | 重复点击／并发登录／重试 | 同一AppID微信身份只生成一个账号，用户统计只计一次 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T08 | 老用户重新登录或同微信换设备 | 恢复原资料、注册时间、成绩和收藏，联系缺失不阻止 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T09 | 有效会话再次打开 | 校验复用，不重新创建账号或强制补资料 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T10 | U03失效后主动登录 | 回原卡重查收藏完成状态，不自动重播或重提旧操作；已下线转U05 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T11 | U09选填／修改手机号或微信号 | 基础格式校验，成功按字段记手填来源；无联系可返回，失败留输入和旧资料，已有值不能清空删除 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T12 | 不同微信身份填相同联系值 | 不合并、不互看数据，联系不是密码，退出不删服务器成绩 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T13 | 学习页初次成功加载 | 显示已学卡片、连续和累计打卡、今日状态及两导航 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T14 | 没有已发布卡但已有历史 | 列表空，原学习成绩仍保留，不强行归0 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T15 | 从学习、收藏、已学记录进入详情 | 使用同一详情并返回正确来源位置 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T16 | 进入场景详情 | 默认英文及收起的完整译文，不逐句插中文 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T17 | 显示译文 | 完整中文位于全部英文下方、词汇上方，人物与顺序正确 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T18 | 收起译文 | 无占位，不隐藏词汇／语块中文，不改变音频或成绩 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T19 | 播放中切译文、收藏、打开大图 | 相关状态互不干扰，返回原位置 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T20 | 退出详情再进入 | 译文恢复收起，真实完成／收藏保持 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T21 | 大图缩放或加载失败 | 原图完整，覆盖层内重试或关闭，不阻断文字 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T22 | 无语块、无音标 | 整块或对应行隐藏，无图片空位／演示数据 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T23 | 长词、长对话、较大字体 | 自然换行，无裁切、重叠或横向溢出 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T24 | 正文高亮点击 | 只视觉强调，无单句播放、查词或词汇收藏 | 详情/译文/大图/返回 | test_content、test_media；小程序scene-dialogue/scene-model/navigation；core-loop.md | 核心H5流程有证据；大图手势、字体与全状态待真机/视觉验收 |
| T25 | 上传词卡音频 | 只有完整对话音频上传，词汇／语块无文件上传控件 | 完整音频/受控词汇发音 | test_audio_decoding、test_media、test_pronunciation、test_queue_integration；两前端audio/pronunciation；audio-codecs.md | 服务端及本地播放有证据；原生暂停/拖动/防叠播待真机验收 |
| T26 | 整篇播放暂停继续拖动重播 | 只用完整文件，无切片和时间点依赖 | 完整音频/受控词汇发音 | test_audio_decoding、test_media、test_pronunciation、test_queue_integration；两前端audio/pronunciation；audio-codecs.md | 服务端及本地播放有证据；原生暂停/拖动/防叠播待真机验收 |
| T27 | 整篇中点击词汇 | 暂停整篇保留位置，词汇独立接口发音 | 完整音频/受控词汇发音 | test_audio_decoding、test_media、test_pronunciation、test_queue_integration；两前端audio/pronunciation；audio-codecs.md | 服务端及本地播放有证据；原生暂停/拖动/防叠播待真机验收 |
| T28 | 词汇结束再手动继续整篇 | 不自动续播，继续位置正确 | 完整音频/受控词汇发音 | test_audio_decoding、test_media、test_pronunciation、test_queue_integration；两前端audio/pronunciation；audio-codecs.md | 服务端及本地播放有证据；原生暂停/拖动/防叠播待真机验收 |
| T29 | 切换词汇或重复同词 | 停旧目标，同词从头，无叠播 | 完整音频/受控词汇发音 | test_audio_decoding、test_media、test_pronunciation、test_queue_integration；两前端audio/pronunciation；audio-codecs.md | 服务端及本地播放有证据；原生暂停/拖动/防叠播待真机验收 |
| T30 | 首次、再次与并发发音 | 腾讯云服务端缓存，同键合并，不重复计费合成成功任务 | 完整音频/受控词汇发音 | test_audio_decoding、test_media、test_pronunciation、test_queue_integration；两前端audio/pronunciation；audio-codecs.md | 服务端及本地播放有证据；原生暂停/拖动/防叠播待真机验收 |
| T31 | 发音／完整音频失败 | 原位有限重试，仍可看译文、收藏与完成 | 完整音频/受控词汇发音 | test_audio_decoding、test_media、test_pronunciation、test_queue_integration；两前端audio/pronunciation；audio-codecs.md | 服务端及本地播放有证据；原生暂停/拖动/防叠播待真机验收 |
| T32 | 离开详情／关闭后台预览 | 停止播放，后台不写真实学习记录 | 完整音频/受控词汇发音 | test_audio_decoding、test_media、test_pronunciation、test_queue_integration；两前端audio/pronunciation；audio-codecs.md | 服务端及本地播放有证据；原生暂停/拖动/防叠播待真机验收 |
| T33 | 首次点击已完成学习 | 本卡首次完成、已学＋1、当日学习与打卡一致成功 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T34 | 同日完成多张不同新卡 | 已学各加1，当天打卡只计一次 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T35 | 同日重复完成同卡 | 不重复增加卡数、当日不同卡数或天数 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T36 | 多设备并发完成同卡 | 服务端唯一键与事务防止重复 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T37 | 同卡隔日点击完成本次复习 | 已学总数不变，当日可打卡并更新最近学习 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T38 | 今天已完成卡片再进入 | 今日已完成按钮不可重复提交，其余功能可用 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T39 | 之前已完成、今天未完成 | 可完成本次复习，不把历史已学误当今日完成 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T40 | 第一次有有效学习日 | 累计打卡1，连续1，前后台口径一致 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T41 | 今天未打卡、昨天已打卡 | 显示昨天连续天数并标今日待打卡，未提前清零 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T42 | 连续日期今天完成 | 连续增加，累计有效日期增加一次 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T43 | 漏过完整一天后再完成 | 当前连续从1开始，累计与历史最长保留 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T44 | 只打开、播放、收藏或看译文 | 不自动计完成或打卡 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T45 | 未听完、不看译文直接主动完成 | 可成功，无隐藏学习时长前置 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T46 | 完成请求失败 | 不先增加任何成绩，保留重试 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T47 | 完成超时后查结果／重试 | 恢复唯一真实结果，三类记录不分裂 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T48 | 午夜前成功、午夜后重试同一操作 | 返回原日期结果，不额外补新一天 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T49 | 新一天刷新后重新复习 | 主动新操作计新日期，客户端不能回填历史天 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T50 | 客户端改时区／时间或离线后提交 | 用服务端北京时间接受日期，不补签 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T51 | 内容更新、取消收藏 | 完成不重置，不减少已学或打卡 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T52 | 卡片下线／删除 | 保留完成档案、总已学及有效日期，不能再新增停用卡完成 | 完成/每日学习/打卡/统计 | test_learning、test_timestamp_precision；小程序scene-model/operation-service；后台core-loop.md | 真实MySQL事务/并发/跨日有证据；完整客户端状态重放待验收 |
| T53 | 收藏整卡 | 左图右名称进入收藏列表，只有一条有效关联 | 整卡收藏/学习记录 | test_learning、test_content；小程序scene-model/statistics-navigation；core-loop.md | API与核心H5操作有证据；来源位置及异常组合待逐项验收 |
| T54 | 重复收藏与取消失败 | 幂等且状态真实，不显示假成功 | 整卡收藏/学习记录 | test_learning、test_content；小程序scene-model/statistics-navigation；core-loop.md | API与核心H5操作有证据；来源位置及异常组合待逐项验收 |
| T55 | 从收藏取消后返回 | 行移除，最后一张变空；学习成绩不变 | 整卡收藏/学习记录 | test_learning、test_content；小程序scene-model/statistics-navigation；core-loop.md | API与核心H5操作有证据；来源位置及异常组合待逐项验收 |
| T56 | 收藏后发布新版 | 同卡打开最新版，不重计完成，不保存词义快照 | 整卡收藏/学习记录 | test_learning、test_content；小程序scene-model/statistics-navigation；core-loop.md | API与核心H5操作有证据；来源位置及异常组合待逐项验收 |
| T57 | 收藏卡下线／删除 | 安全摘要与U05，可取消但不能新收藏或完成 | 整卡收藏/学习记录 | test_learning、test_content；小程序scene-model/statistics-navigation；core-loop.md | API与核心H5操作有证据；来源位置及异常组合待逐项验收 |
| T58 | U06已学列表 | 每卡一行，首次／最近学习真实，按最近学习倒序 | 整卡收藏/学习记录 | test_learning、test_content；小程序scene-model/statistics-navigation；core-loop.md | API与核心H5操作有证据；来源位置及异常组合待逐项验收 |
| T59 | U06打卡日期展开 | 当日不同卡片与总数一致，不按点击次数计 | 整卡收藏/学习记录 | test_learning、test_content；小程序scene-model/statistics-navigation；core-loop.md | API与核心H5操作有证据；来源位置及异常组合待逐项验收 |
| T60 | U06进入详情再返回 | 恢复标签、日期展开与位置；不可用来源不开放旧全文 | 整卡收藏/学习记录 | test_learning、test_content；小程序scene-model/statistics-navigation；core-loop.md | API与核心H5操作有证据；来源位置及异常组合待逐项验收 |
| T61 | 管理员登录进入后台 | 默认A02，有卡片管理、批量导入、用户管理、独立数据统计，无旧权益大屏 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T62 | 四组录入并保存不完整草稿 | 资料顺序明确，可保存；发布前定位必填问题 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T63 | 词汇唯一／多处／变形词定位 | 正确高亮，不填内部偏移；改来源后重新核对 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T64 | 预览及已发布查看效果 | 译文可切换，收藏／完成禁用；只读模式没有确认发布 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T65 | 编辑已发布卡保存候选 | 用户仍用原发布；重发整体切版，完成保留 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T66 | 单卡下线与重新发布 | 状态和入口正确，收藏／历史可恢复但成绩不变 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T67 | 删除草稿／已下线卡 | 确认后主列表移除，旧窗口不能继续发布 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T68 | 直接删除已发布卡 | 一次操作停止可学并标删除，无须先下线两次操作 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T69 | 删除卡片与用户已有成绩 | 保留用户卡数、日期及打卡，不级联删除 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T70 | 删除失败／并发版本变化／排序未保存 | 真实状态保留，重新核对；排序保存／取消与离页提示明确 | 管理/草稿/预览/发布/排序/删除 | test_content、test_ordering、test_publication_batches；后台editor-model/scene-reader/catalog-order/batch-publication；advanced-content.md | 核心闭环和高级操作有证据；修订12全状态与并发窗口重放待验收 |
| T71 | 无联系用户首次微信身份登录成功 | A05立即可查稳定用户及0学习，不等补资料或完成第一张卡 | 后台用户/联系查看/统一统计 | test_profiles、test_learning、test_auth；后台app/statistics-page；core-loop.md | API口径及核心后台查询有证据；全筛选/分页/异常组合待验收 |
| T72 | 搜索编号／昵称／已填联系 | 真实匹配，无联系仍可通过编号或昵称找到，空态可清条件 | 后台用户/联系查看/统一统计 | test_profiles、test_learning、test_auth；后台app/statistics-page；core-loop.md | API口径及核心后台查询有证据；全筛选/分页/异常组合待验收 |
| T73 | 今日注册和今日打卡分别／组合筛选 | 两组独立，前者用首次注册日期，后者用真实打卡日，不用登录时间替代 | 后台用户/联系查看/统一统计 | test_profiles、test_learning、test_auth；后台app/statistics-page；core-loop.md | API口径及核心后台查询有证据；全筛选/分页/异常组合待验收 |
| T74 | A05→A06→返回 | 搜索、两组筛选、分页与位置恢复；由统计进入可再返回A07 | 后台用户/联系查看/统一统计 | test_profiles、test_learning、test_auth；后台app/statistics-page；core-loop.md | API口径及核心后台查询有证据；全筛选/分页/异常组合待验收 |
| T75 | A06联系为空／手填／历史来源 | 空值正常，手填标未验证，未改历史来源保留；只有认证管理员可看完整联系 | 后台用户/联系查看/统一统计 | test_profiles、test_learning、test_auth；后台app/statistics-page；core-loop.md | API口径及核心后台查询有证据；全筛选/分页/异常组合待验收 |
| T76 | A06学习概况对比前端 | 卡数、连续、累计、最长与今日状态同源同口径 | 后台用户/联系查看/统一统计 | test_profiles、test_learning、test_auth；后台app/statistics-page；core-loop.md | API口径及核心后台查询有证据；全筛选/分页/异常组合待验收 |
| T77 | 后台已学／打卡预览 | 只读，不替用户新增收藏、完成或打卡 | 后台用户/联系查看/统一统计 | test_profiles、test_learning、test_auth；后台app/statistics-page；core-loop.md | API口径及核心后台查询有证据；全筛选/分页/异常组合待验收 |
| T78 | 资料／统计失败或用户无效 | 暂未获取与重试，不假0、不泄露他人资料和明文日志 | 后台用户/联系查看/统一统计 | test_profiles、test_learning、test_auth；后台app/statistics-page；core-loop.md | API口径及核心后台查询有证据；全筛选/分页/异常组合待验收 |
| T79 | 一文件夹一卡片ZIP | 图文整篇音频准确对应，只存草稿 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T80 | ZIP内混入多卡DOCX | 问题文件夹标错，要求拆分或换DOCX入口，不误共享素材 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T81 | 多篇DOCX和独立资料 | 标题分卡，明确同名候选核对，多候选手动选择 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T82 | 缺图／音频／释义／高亮或无语块 | 缺必需可留草稿，空语块正常；不要求词汇音频 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T83 | 上传包出现词汇音频文件 | 列未使用，不绑定，不生成词汇上传入口 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T84 | 重复已确认资料／同名不同资料 | 前者跳过，后者确认新增或更新，不静默合并 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T85 | 导入更新已有卡片 | 前后差异明确，仅存候选，发布前不改前端或完成状态 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T86 | 核对切卡／返回补文件／离页恢复 | 成功暂存可恢复，保存失败提示，不假称已存 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T87 | 保存与发布部分失败重试 | 只处理失败项，成功不重复，不混导入与上线 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T88 | 已删除目标收到陈旧导入更新 | 拒绝复活旧卡，要求重新核对为新对象或排除 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T89 | ZIP非法路径／类型／超限 | 拒绝问题资料，不越界解包或执行 | 可恢复导入/逐卡保存/发布 | test_imports、test_jobs、test_publication_batches；后台use-import-staging/import-workflow/scene-docx-import；advanced-content.md | 真实MySQL和本地Worker/浏览器有证据；生产OSS及全部失败组合待验收 |
| T90 | 旧账号和可靠完成迁移 | 清除测试与生产旧账号、成绩、内容、任务、旧素材及旧业务备份；无历史迁移，新数据从零开始 | 本次旧系统全量重置（覆盖原迁移条款） | test_reset；docs/implementation/progress.md精确资源清单 | 旧SQL/容器/本地备份已清除；旧OSS对象/版本/分片待授权后清理 |
| T91 | U07无联系／单手机／单微信／双联系 | 只读布局正确，无联系提示未填写及补充入口，缺单项不留空行，手机脱敏 | 个人资料/选填联系/未保存返回 | test_profiles、test_media、test_jobs；小程序contact-model/identity-model/use-unsaved-guard/media-processing | API、编辑H5、原生组件编译/事件测试通过；真实系统返回/上传待真机验收 |
| T92 | U08主动选头像、填昵称并保存 | U07/U01/A05/A06同步，原账号、注册时间、成绩和收藏不变 | 个人资料/选填联系/未保存返回 | test_profiles、test_media、test_jobs；小程序contact-model/identity-model/use-unsaved-guard/media-processing | API、编辑H5、原生组件编译/事件测试通过；真实系统返回/上传待真机验收 |
| T93 | U08取消、失败、上传未完成及未保存离开 | 旧有效资料保留，三种离开处理正确，失败不离开；不自动读微信头像昵称 | 个人资料/选填联系/未保存返回 | test_profiles、test_media、test_jobs；小程序contact-model/identity-model/use-unsaved-guard/media-processing | API、编辑H5、原生组件编译/事件测试通过；真实系统返回/上传待真机验收 |
| T94 | U09原本两项为空且直接返回 | 可正常返回U07学习；无变化无空提交，不强制留联系方式 | 个人资料/选填联系/未保存返回 | test_profiles、test_media、test_jobs；小程序contact-model/identity-model/use-unsaved-guard/media-processing | API、编辑H5、原生组件编译/事件测试通过；真实系统返回/上传待真机验收 |
| T95 | 联系新增／修改及已有值清空 | 变更字段标用户填写／未验证；未改历史来源保留；清空已有值就近拦截，无单独移除 | 个人资料/选填联系/未保存返回 | test_profiles、test_media、test_jobs；小程序contact-model/identity-model/use-unsaved-guard/media-processing | API、编辑H5、原生组件编译/事件测试通过；真实系统返回/上传待真机验收 |
| T96 | U09保存失败、超时、并发变化或未保存离开 | 原值与输入保留，先确认真实结果／重查核对；保存后离开仅在成功后执行，放弃不提交 | 个人资料/选填联系/未保存返回 | test_profiles、test_media、test_jobs；小程序contact-model/identity-model/use-unsaved-guard/media-processing | API、编辑H5、原生组件编译/事件测试通过；真实系统返回/上传待真机验收 |
| T97 | 首次进入A07／手动刷新 | 显示北京时间统计日期、更新时间及三指标，加载不用假0 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T98 | 首次注册且无联系、0学习 | 用户总数和今日新增各计一次，管理员不计入 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T99 | 重复登录、响应丢失后恢复、换设备、补联系或改昵称 | 不增加用户数，不改首次注册时间 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T100 | 点击用户总数 | A05清旧搜索和筛选，全部注册＋全部打卡；总数同口径，可返回A07 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T101 | 点击今日新增 | A05今日注册＋全部打卡，清旧搜索；不筛今日登录或今日打卡，可返回统计 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T102 | 点击已发布场景卡数 | A02清旧无关条件、仅已发布，列表同口径，可返回A07 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T103 | 保存草稿／导入草稿／保存已发布候选 | 不增加已发布数，前端继续当前发布版 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T104 | 发布、同卡再发布、下线、重发、删除 | 首次加1，同卡新版不重复加；下线减、重发恢复、删除已发布减，无旧窗口复活 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T105 | A07真实0／初次失败／旧值刷新失败 | 真实0可点击对应空态；失败暂未获取或旧快照暂未更新，有重试，不假0 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T106 | 北京时间00:00前后注册／跨日回前台 | 今日新增按服务端新日期重算，不沿用昨日数字；原账号再登录不计新增 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T107 | 指标与列表查询间新增用户或卡片状态变化 | 列表取最新，返回统计刷新，允许时间差并展示更新时间，不凑数 | A07/筛选联动/日期边界 | test_profiles、test_content、test_timestamp_precision；后台statistics-page/app；统计日期使用服务端 | API/组件及A07→A05/A02本地联动有证据；跨日回前台及刷新异常待完整重放 |
| T108 | 无联系方式用户收藏、完成及隔日复习 | 功能均可用，成绩与前后台一致，联系空值不是鉴权失败 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T109 | 从U00/U07开隐私说明再关闭 | 回真实来源及原位置，输入／勾选状态不被代改 | 隐私说明/来源恢复 | 小程序登录/只读资料/隐私说明组件；session-service/navigation | 实现及核心流程存在；来源滚动/勾选全组合待真机验收 |
| T110 | 退出再同身份登录 | 清客户端会话，恢复服务端学习收藏，无联系也可登录 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T111 | 客户端伪造OpenID或访问他人引用 | 服务端用微信凭证校验和本人会话拒绝越权，联系值不能取代身份 | 账号/会话/本人资料 | test_auth、test_auth_concurrency、test_profiles、test_learning；小程序session-service/navigation/operation-service | API及约束已验证；真实微信登录、换设备和故障流程待真机验收 |
| T112 | 历史账号缺联系或仅未核实联系 | 旧账号不迁移；重建后的账号无联系方式也可学习，联系方式不作为身份或合并依据 | 本次重置后无历史账号（覆盖迁移条款） | test_reset、test_auth、test_profiles | 不迁移旧账号；重建后无联系可学习，不按联系合并。旧OSS清理尚待完成 |
| T113 | 全文及后续原型同步核对 | 旧手机号必需／联系必填执行规则无残留，待同步项明确，未把文档当原型或真实接入完成 | 范围与需求同步 | AGENTS.md、已批准重建方案、各仓库实现及本验收表 | 两导航和联系选填已实现；设计全页核对、最终代码审查和实机接入仍待验收 |

## 上线门槛（仍需执行）

- 真实OSS权限恢复后，完成旧对象/历史版本/删除标记/分片清理并验证；新图片、完整音频与发音缓存真实读写及下线撤销。
- 两环境、两API及独立Worker同时运行；20并发混合学习＋一次批量导入，普通API P95≤500ms、错误率<1%、无OOM；云服务和媒体耗时另列。
- 小程序API持续接受请求及写入时，实际发布/回滚管理API，核验小程序容器身份与启动时间不变。
- 真机验证wx.login、媒体拖动/暂停/防叠播、大图手势、头像上传、原生三选择返回及位置恢复。
- 全页修订12视觉核对、最终代码审查、空数据上线及管理员初始化；本表逐项附最终执行结果后才能签收。
