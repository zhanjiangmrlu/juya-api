# 2026-11-04 生产应用发布与小程序 1.0.0

用户明确授权四仓 `test` 合并 `release`、应用部署生产；小程序使用生产配置、版本号 `1.0.0`，体验版由用户手动切换。

## 固定版本

| 交付物 | 源码 | 验证 |
| --- | --- | --- |
| API release 分支 | `f8ea65625320387adea63c87a8b35201cd2129e4` | 包含本次全部 test 提交 |
| 双角色 API 与七个生产服务 | `00a4c1101b6413dd9a8d230f9cf82c8610464c45` | 复用完整真实 MySQL/Redis CI 成功的固定镜像；与 release 仅文档不同 |
| 管理后台 | `351c862ac0dd94acd5ebc5e43e24f66492db2f15` | 生产构建与公网文件哈希核对 |
| 小程序 | `90aca3a1ac786f2ff7f15edaef0915fe076b78d5` | test 快进合并后，仅设置 manifest 版本 `1.0.0 / 100` |
| 发布 CLI / 工作台 | `45ff9c0c8f0cf4d41cf9365b31b9d35d9e38f68f` | test/release/线上原已一致，核验健康，无需重复重启 |

没有改写已推送历史；本地 API、后台、小程序工作目录仍保留 test 分支及原私有配置，release 引用与远程同步。

## 检查与产物

- 本次隔离目录重新运行：API Ruff/format/mypy 通过，完整 SQLite 581通过/43条件跳过；后台 check 与59文件273测试通过；小程序 check 与96文件470测试通过；CLI Node64通过、引擎276通过/10条件跳过及 Ruff 通过
- API 使用 [CI 41665251214](https://github.com/zhanjiangmrlu/juya-api/actions/runs/41665251214) 的两角色 Linux/amd64 官方镜像；重新查询 quality/两镜像任务均 success，核对官方 ZIP digest、归档 SHA、源码/角色/平台及实际镜像身份。该 CI 完整真实 MySQL/Redis 为621通过/3跳过，详见此前性能发布 CI 记录
- 管理后台生产 API 固定 `https://admin-api.juyayingyu.com`；小程序 API 固定 `https://api.juyayingyu.com`，静态资源固定该生产域名 `/miniapp/static`。构建中关闭 Mock/本地登录，核对无测试 API 或本机接口地址
- 小程序 manifest `versionName=1.0.0`、`versionCode=100`，官方 CLI 上传版本 `1.0.0`。18页面/三Tab、共享音频入口与主包预算均通过。官方编译总包1,760,551B，主包1,465,869B
- 本机 ZIP SHA-256：`8ae8f2c034067a1b4bd2387bb8e18feccf85cf7d9ad6a5cde3d0bbfeebe10003`。构建、上传时排除开发者工具私有配置；没有切换体验版、提交微信审核或发布微信正式版

## 生产静态资源

先发布六个内容哈希 WebP/JPEG 变体到原生产静态根目录；逐一公网200、SHA-256、MIME与一年 immutable 缓存通过。旧PNG、字体及其他原资源摘要不变，测试 Nginx 配置摘要不变。未改变 OSS ACL/桶策略、复制测试业务内容或删除原图。

Nginx 使用六个精确路径 location，保留原前缀规则。首次校验在平滑重载旧 worker 尚未退出时读到旧一小时缓存策略，发布脚本恢复了原配置；随后改为有上限的缓存策略就绪轮询，最终六个请求均符合新策略。

## 服务与数据库

生产服务全部就绪时间为北京时间 **2026-11-04T08:52:36.391029+08:00**。双API、四个配套Worker/dispatcher及独立听读Worker共7个服务 healthy、重启0、无OOM，全部为表中固定 API 源码。管理后台公网HTML、入口脚本及安装目录完整文件哈希匹配。

生产库前后均 `0024 / contract 3`，本次不执行迁移、降级或备份恢复。测试及基础设施等其余12容器的ID、镜像、启动时间、状态、健康、重启与OOM逐项一致；最终仍19容器。

实际使用指定生产管理员验证登录、Secure/HttpOnly Cookie、生产后台CORS凭据许可、会话/分类/文章/用户/统计/反馈查询200；未认证会话401、跨角色认证路径404。随后关闭本次验证会话。

真实Chrome无Mock浏览器登录并打开 `/users`、`/statistics`、`/feedback`、`/listening`，对应标题可见、真实API200、JavaScript错误0；未编辑业务内容或用户资料。生产双API、两测试API、后台及发布工作台公网健康通过。

成功发布后调用原生保留机制，三个生产发布目标均保留当前及1个历史版本，没有清理数据库、备份或业务素材。完整无密钥回执见[同名JSON](production-release-20261104.json)。

## 验证边界

浏览器/API健康、权限隔离、静态哈希与自动化检查不能代替真实微信身份下的真机首屏/首播延迟、录音同步、TTS/ASR与所有学习业务完整验收。本次没有在真实学习账号上写入学习事实或成绩。凭据、会话、签名下载地址及原始运维日志仅留私有目录，不入 Git。
