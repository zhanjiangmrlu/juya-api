# 整合06／修订17测试发布 · 2026-11-01

用户授权提交远程 test、部署测试环境并仅上传小程序包；体验版由用户手动切换。本次没有发布生产环境、提交微信审核或切换体验版。

| 交付物 | 固定源码提交 | 结果 |
| --- | --- | --- |
| 管理 API、Worker、dispatcher | f46f2d4ab3f12cdc5bcad75acbbdfaa69ac06b87 | 已部署，测试 ready 通过 |
| 小程序 API、Worker、dispatcher | f46f2d4ab3f12cdc5bcad75acbbdfaa69ac06b87 | 已部署，测试 ready 通过 |
| 听读 Worker | f46f2d4ab3f12cdc5bcad75acbbdfaa69ac06b87 | 同一镜像、健康运行 |
| 管理后台 | b9aa4b382edc0b3bba61ec80cef2da2defc5814e | 已部署，站点与构建包哈希一致 |
| 微信小程序 | ca6bb37bda749650ba32c5b41c4ed05a900e0f5a | 官方 CLI 上传 1.5.0-r17.06.1101 成功，体验版未切换 |

入口：[测试后台](https://test-admin.juyayingyu.com)、[管理 API 就绪](https://test-admin-api.juyayingyu.com/health/ready)、[小程序 API 就绪](https://test-api.juyayingyu.com/health/ready)。小程序包固定测试 API 和既有 AppID，排除本地验收登录及私有项目配置；实际主包 1039107B，总包 1327242B。

## 数据与验证

- 测试库 juya_test 在停止两角色 API、dispatcher 和 Worker 写入后备份，再通过原生发布器显式迁移 0023→0024；code contract=3。备份 6367672B，SHA-256 `6fef2fdd064c8e55f22d9ad5c0b7981160a2cd3afe102a0e1ccd1a26f2d2f3a3`；未自动恢复或降级数据库。
- 迁移边界全部原有表行数及主键身份摘要一致；文章均有直接分类。旧实际免费名单逐 ID 保留：场景 10 张、听读 0 篇，未猜测或重设运营规则。
- 本地发布前 API 542 通过／40 外部条件跳过，后台 237、小程序 427 通过，静态检查、测试构建及微信分包检查通过。[API CI](https://github.com/zhanjiangmrlu/juya-api/actions/runs/41268378520) 真实 MySQL／Redis 共579项通过／3项跳过，两个 Linux/amd64 镜像构建与运行校验均通过，CI 产物及原生发布包校验后使用。
- 磁盘预算不足时，仅清理两份与已安装测试版本逐文件校验一致的旧传输归档，共499157457B；已安装保留版本、数据库备份和素材保留。重新核验预算通过后才开始服务切换。
- 测试共 7 个服务为固定源码提交、healthy、重启 0、无 OOM。生产及其他基础设施容器身份、镜像、启动时间和健康状态保持。
- 两公网 ready、匿名鉴权、角色隔离及运行中 OpenAPI 与源码契约一致。现有测试管理员登录、分类／文章／免费汇总／卡片／用户只读接口通过，验证会话退出；未修改运营内容、授权或成绩。
- 测试后台公网 index、入口 JS 及安装目录文件哈希与固定发布包一致；1440／960 视口实际验证场景和听读操作栏 13px／22.75px、14px 间距及免费开关加粗。此前确认的红色与悬停透明度保留。

这是发布及上述实际检查的记录，不代表真实词库、完整云发音／ASR、微信真机或全部设计画板验收通过。旧本地交付证据继续保留，后续代码及配置以本次发布记录区分。

原始私密发布记录、备份位置与上传回执不入 Git；安全汇总见同名 JSON。三个原工作目录及本地热更新环境保留。0024 不提供有损降级，旧 code contract 不能直接接管新库。
