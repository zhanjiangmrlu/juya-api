# 整合07三仓整体审查与修复

2026-11-06，分任务独立审查通过后，另一名审查者对三仓完整改动进行只读整体审查。范围基线：API `b2744ec`、后台`c81aa8e`、小程序`d0a92de`；首次整体审查头分别为`ab68061`、`d3a746c`、`26ff466`。使用增量Word T322—T355、实施计划、实际契约和三仓完整差异，关键疑点用隔离SQLite／真实HTTP及组件重放核实。

初次发现3项Important、2项Minor；集中修复的定向复审另发现1项文件名显示Minor，随后用一行源码与针对测试收尾。六项均经原审查者核对为**ADDRESSED**，最终规格符合性及代码质量结论通过，无遗留Critical／Important／Minor。

| 发现 | 修复与核对 |
| --- | --- |
| PDF票据可由非签发会话兑现 | 仅study_note用途要求当前请求Bearer匹配签发会话，继续检查当前发布、版本和授权。授权A的GET／HEAD／Range为200／200／206；匿名、无权B、同账号另一会话均401。旧图片／音频无头读取仍200／200／206 |
| 无PDF旧ZIP核对与保存继承不一致 | 核对与worker共用目标决策投影，展示有效A及待处理C、原因和可发布状态；本包候选仍隔离，省略不写成附件动作。覆盖切换／清除／切回目标及实际落盘，后台淘汰旧目标轮询回执 |
| 本地拒绝C后重试误用有效B | 分离本地拒绝文件、有效回退和上传结果；空／超限／后缀错误显示C及实际原因，不提供继续查询旧B的入口。显式取消恢复B，重选有效件才解除阻断 |
| 旧Tab下拉迟到重置新Tab滚动 | 捕获发起栏、账号和浏览代次；换栏、隐藏、销毁、账号重置作废旧回调。覆盖A→B成功／失败及A→B→A，保留当前滚动510 |
| 异常退出遗留私有PDF | 下一次合法下载前只清扫本功能严格命名的孤儿，排除活动下载和打开文件；失败／取消／释放清理活动登记。SDK测试含孤儿、无关文件、活动文件，不等同真机杀进程验收 |
| 本地拒绝C后改选包内D仍显示C名 | 确认包内D后清本地selected；remember保留取消快照。实际单选测试确认显示D、set(D, previous B)，取消回C错误和有效B |

回归位于API `tests/test_study_notes.py`、`tests/test_study_notes_contract.py`；后台`tests/unit/features/scenes/scene-study-note.spec.ts`；小程序`tests/unit/features/learning/learning-list.spec.ts`、`tests/unit/sub-packages/scenes/study-note-platform.spec.ts`。每项先复现失败再修复转绿，具体最终完整计数、提交与设备边界见[总验收记录](study-notes-20261106.md)。

审查没有以H5／SDK端口模拟关闭iOS／Android微信PDF、耳机、系统面板或真实身份交换待验项；亦未核验全套静态PNG、完整主Word与Figma历史备份。没有操作远程环境或发布。
