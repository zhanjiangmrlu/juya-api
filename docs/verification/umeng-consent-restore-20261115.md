# 友盟测试统计授权恢复（2026-11-15）

在原test分支恢复仅测试环境显式配置＋umeng-20261115-v3完整新版披露的客户端SDK授权。collecting已允许且通道可用返回null，未允许或通道关闭为false；accepted仅代表事件授权，非友盟接收。生产配置仍拒绝通道，无schema/迁移或业务数据变化。

新增测试覆盖旧披露不可开启、新版公开材料、手动许可前关闭、开启后接受、关闭后403和旧许可失效。定向20项SQLite及独立已核验juya_verify MySQL20项通过；完整SQLite796通过/60条件跳过，Swagger补跑5通过；ruff/format/mypy通过。小程序真实SDK及实际编译模块验证见配套仓库docs/verification/umeng-consent-restore-20261115.md。

部署时测试环境需JUYA_ANALYTICS_CLIENT_TRANSPORT_ENABLED=true，并将JUYA_PRIVACY_DOCUMENTS_PATH指向src/juya_api/policies/umeng-20261115-v3.json。本轮未推送、部署、上传或修改原服务/业务库，生产未改；真机及友盟实际接收未验。
