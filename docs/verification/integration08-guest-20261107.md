# 整合08游客体验本地实施与验收

2026-11-07。本轮按用户批准方案，仅本地隔离开发和验收，无推送、部署、微信上传或远程迁移。原test目录、业务账号、配置、素材与数据库保留。需求源及SHA见docs/handoff/revision17/requirement-reference.json；计划见docs/superpowers/plans/2026-11-07-integration08-guest.md。

## API结果

功能提交32dfa4e。已完成可选身份读取、空个人字段、游客场景与听读集合、当前安全摘要、免费受控媒体/PDF、预置词汇发音。个人读写、管理员与正文点词保留鉴权。新增独立300秒public票据，不创建游客账号、会话、学习事实或个人Operation；未新增迁移，schema0026/contract3。

完整SQLite713通过/53条件跳过。真实独立MySQL8.4.13与Redis7.4整套760通过/6跳过，499.76秒；跳过为3项SQLite专用、3项需要Node的Swagger脚本。补齐Node路径后定向Swagger完整5项通过，覆盖原3项脚本跳过。两个环境数字不相加为通过率。ruff检查/格式、mypy、OpenAPI生成及diff检查均通过。

MySQL使用本轮新初始化且仅Unix socket监听的juya_verify，Redis使用新临时26389端口，不连接旧业务实例；验证后已核对datadir并关闭这两项临时服务。测试日志留在本计划ignored控制目录。外部TTS使用测试Provider，不能冒充腾讯云真实验收。

独立审查32dfa4e相对885bfa3：规格符合、质量通过，无Critical/Important/Minor发现。审查覆盖匿名与私有身份、摘要/历史归属、实时资源版本和权限复核、预置发音与worker服务归属。接口接入说明见docs/implementation/integration08-guest-contract.md。

## 后台结果

隔离工作树178bcea同步生成契约，两个听读摘要state声明改为可空，无业务页面修改。62文件310项完整单测、check/typecheck/build通过。生成JSON格式差异已按Prettier修正。详细记录位于juya-admin/docs/verification/integration08-guest-contract-20261107.md。

## 小程序与整体验收

小程序实施及浏览器联调进行中。本节在本轮最终交付前按实际结果更新，不以API或原626项基线代替新增游客流程完成。

本地浏览器使用独立SQLite、真实HTTP/媒体与合成微信交换夹具；不读业务账密。真实微信身份、iOS/Android原生PDF、蓝牙及系统播放面板须另列真机证据，未实测不能标完成。Figma原型及需求中的示例人数、篇数与PDF文件名不作为运行默认值。
