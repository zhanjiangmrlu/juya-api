# CHG0043—0045 最终修复限定复审

三仓冻结 HEAD 已核对。API 为 `143fd385b382a51504be90d9cd8e5cb2d6bf0cd4`，后台为 `7446218001c5da66e162497e21280dfbfeac7bf9`，小程序为 `46d9b7e2d64e73aed0a38f3a53e06128fc135e97`。审阅对应的三个完整修复包、修复简报、实现报告及定点回归证据。

## 逐项裁决

- **I1 ADDRESSED。** 小程序 `src/sub-packages/scenes/detail.vue:1376` 在首次发送完成前按账号保存原请求。列表自动进入、登录返回及换栏均进入只读查询。显式恢复按钮位于 `src/pages/learning/index.vue:215`，仅为点击时的一个完成操作授权重试，随后枚举的新操作只查回执。`src/services/operation-service.ts:119` 在本人原键查询返回 operation_unknown 后重验身份及记录。存在冻结正文时使用原键、原路径、原版本；旧记录缺少正文时，显式查询得到404才解除本地阻塞并提示重新打开卡片。网络不确定时保留操作，旧版本明确失败后刷新真实列表。成功回执按动作及原键清理，只有首次消费才通知。检查了六种冷启动分支的页面断言和并发同动作新键回归；独立进程日志及持久 Chrome 资料冷启动的请求序列与代码一致。
- **I2 ADDRESSED。** 后台 `src/features/scenes/scene-type-history.vue:170` 对 invalid_pdf 展示异常说明，其余依据服务端已验证的 suggestion 展示附件状态。未附加、正常发布、保留移除指针、异常引用四种回归分别断言附件和建议的配对。历史快照中的版本指针仍参与原并发核验。
- **I3 ADDRESSED。** API `src/juya_api/vocabulary_matching.py:215` 保留 dye、singe 的词尾 e，分词分别为 dyeing 和 singeing。共享夹具包含正反向、正确和错误搭配。听读实际应用的编辑和发布回归在 `tests/test_chg0044_matching.py:291` 验证错误搭配返回422，正确搭配可发布。该变更局限在已识别的两个词，原有 die、sing、hop、hope 及复合词分支保留。
- **Minor ADDRESSED。** 后台历史确认窗在 `src/features/scenes/scene-type-history.vue:86`、同文件第235行共用关闭清理。确认前取消、Escape、关闭按钮均能解冻选择；请求未返回或结果未知时保留原操作。两条定点 Chrome 回归核对了重新勾选，以及中断后只有再次明确确认才重发相同键及正文。

## New breakage

本修复范围内未发现新增 Critical、Important 或 Minor。共享操作服务的新清理条件同时比对原键与动作，已有成功回执的迟到响应不会删除同一卡片的后续操作。后台继续由管理员确认归类，建议只供展示。

## Out of scope

没有新增范围外问题。实现者的浏览器冷启动验证使用真实 Chrome 和隔离 HTTP Mock；真实微信设备、目标测试环境及最终 SHA 官方全量 MySQL/Redis 仍属后续验收。本次限定复审核对已有源码、回归断言和运行证据，未重复运行整套测试。

## Ready to merge

**Yes.** 三个 Important 及相邻 Minor 全部关闭，修复波通过限定复审。可进入用户已授权的配套 test 集成及部署流程。
