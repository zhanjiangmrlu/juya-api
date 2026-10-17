# 新运行链路与部署验证

本记录对应重建分支。代码和配置已写入不等于生产服务已上线。

## 构建与发布边界

`Dockerfile`使用官方Python3.13.16固定摘要、冻结的uv.lock、非root运行用户及FFmpeg/FFprobe。`admin`、`mini`两个target使用相同共享源码，镜像分别标记角色与完整提交。CI先执行真实MySQL/Redis质量检查，再构建Linux/amd64镜像；私有workflow artifact包含 `image.tar.gz`、`image.json`，保留7天。没有向公共镜像仓库发布。

镜像 `<交付目标>:<完整提交>` 可原样从测试晋升生产。发布manifest仍明确绑定环境。`write-image-artifact.py`及CLI分别校验归档哈希、config ID、平台、角色和源提交，防止错误文件或另一角色产物进入发布链路。

`compose-admin.yml`只拥有admin-api、admin-worker、admin-dispatcher及显式migrate工具；`compose-mini.yml`只拥有mini-api、mini-worker、mini-dispatcher。数据库和两套Redis由 `compose-infra.yml`独立管理，应用发布使用外部网络，不拥有数据卷。

## 空环境准备顺序

1. 完成旧业务精确清理清单；OSS对象、历史版本、删除标记、未完成分片均需清理后验证，403不得视为空。
2. 在ECS上确认官方MySQL8.4与Redis7.4缓存镜像的完整config ID，显式运行 `initialize-infrastructure.py --mysql-image sha256:... --redis-image sha256:... --apply`。脚本限定 `/etc/juya/rebuild`，创建新命名的三个数据卷、无公开端口的基础设施、两套空数据库及各自app/migration账号。重试不更换密钥、不覆盖管理员或业务内容。
3. 服务端根目录权限0700，凭证清单0600。绑定到非root容器的Redis配置/密码文件可读，但所在主机目录为0700。不得复制这些文件到Git或发布归档。
4. 按 `.env.example` 分别创建test/production的admin.env、mini.env；同一环境共享必要字段加密/查找密钥，不同环境必须不同。使用不同数据库账号、Redis实例、OSS Bucket和会话密钥；小程序AppID保留。migration.env只将数据库连接换为本环境migration账号。运行文件归root所有、权限0600。
5. 从 `compose-test.env.example`、`compose-production.env.example`创建每角色的Compose选择文件，填写本角色runtime路径、API端口、资源限制、环境网络和经验证的 `JUYA_EXPECTED_OSS_BUCKET`。mini无需migration文件；admin明确指定独立migration.env。
6. 创建 `/opt/juya/rebuild/<环境>/<交付目标>` 独立发布根目录。CLI配置模板位于juya-cli仓库，测试使用test分支、生产使用main分支，禁止脏工作区发布。SSH必须匹配已核验的主机指纹；本机默认SSH密钥目前未被ECS授权，现有私密验证助手使用账号文件中的密码连接。
7. 先用juya-cli的显式migrate操作执行空库迁移，再通过admin镜像的 `deploy/bootstrap-admin.py` 从标准输入创建新管理员。只创建必要系统配置和管理员，不灌入旧内容。密码不通过命令行参数传递。
8. 用CLI分别发布两个API。runtime-preflight校验角色、数据库/Redis/OSS环境、实际SQL与Redis连通性及兼容结构。就绪检查要求最低0010及schema_contract=1；允许更新的兼容增量，不允许超出代码能力的结构契约。
9. 两API健康后发布新后台静态站点、安装已验证的HTTPS配置，退出旧H5用户界面。实际微信登录与小程序上传、真机验收单独执行。

管理员初始化示意（通过安全终端或私密stdin提供密码，不将密码写入本示例）：

```sh
docker compose --env-file /etc/juya/rebuild/test/compose-admin.env \
  -p juya-rebuild-test-admin -f /path/to/compose-admin.yml \
  run --rm -T --no-deps --entrypoint python admin-api \
  /app/deploy/bootstrap-admin.py --username admin
```

日常发布不自动备份、迁移、恢复数据库或重建基础设施。兼容迁移单独执行，应用回滚仅恢复所选API及其后台进程的镜像。备份/恢复属于独立运维操作，不能用全库恢复回滚单个API。

## 当前验证证据（2026-10-17）

| 验证 | 结果与边界 |
| --- | --- |
| 实际ECS Docker Compose解析 | test/production × admin/mini四种选择通过；仅本角色服务，API仅127.0.0.1；基础设施三个服务无公开端口 |
| 新schema readiness | 本地与真实MySQL通过：未迁移/旧结构拒绝，0010接受，0011兼容增量接受，契约2拒绝 |
| CI归档校验 | 角色、源提交、文件哈希与实际config ID不匹配均拒绝；使用人工构造归档，首轮CI因时间精度回归失败，修复后重建中 |
| juya-cli Node | macOS真实子进程与打包安装45项通过；包含四项菜单、共享源码映射、CI路径与显式迁移限制 |
| juya-cli Python引擎 | 154项通过；10项需要真实Docker或POSIX能力的本地场景明确跳过。替身验证发布事务、独立迁移、不自动DDL/备份及回滚恢复 |
| 真实角色队列 | Redis7.4/Celery实际Worker通过，错角色不接管，重复投递只产生一次效果 |
| 真实音频解码 | MP3/WAV/M4A/AAC通过，详见audio-codecs.md；使用隔离Linux验证运行时，尚非新生产镜像 |
| 空基础设施初始化 | 实际ECS启动并验证两空数据库、仅DML的应用账号、无公开端口；第二次执行保持全部凭证不变，应用账号可读取聚合连接数 |
| 新镜像、HTTPS、压测、独立发布演练 | 未完成，不作通过声明 |

## 资源预算与验收

ECS实测总内存约7.35GiB。MySQL上限1536MiB、两Redis128/192MiB；测试较低CPU优先级，测试API384/256MiB、Worker512/256MiB，生产API各448MiB、Worker768/384MiB，四个dispatcher各192MiB。上限合计约6080MiB，仍需实测常驻内存、峰值与系统开销。Worker并发1、prefetch1；镜像在CI或有Docker的本机构建。

最后验收必须在两环境同时运行时进行20并发混合学习，并运行一次批量导入；普通业务API P95≤500ms、错误率<1%、无OOM，云接口与媒体单独记录。小程序持续写入时独立发布、回滚管理API，核验小程序容器ID/启动时间不变、写入成功。尚未完成这些测试。

## 外部前提

- 已有OSS凭证对juya-test、juya返回AccessDenied；账号文件新增RAM登录字段尚无可用完整OSS key pair。不能用本地素材后端代替生产OSS。
- 用户已提供新仓库 `git@github.com:zhanjiangmrlu/juya-api.git` 并明确授权提交；准备推送重建分支并运行CI。
- 物理微信设备、合法线上域名/证书和小程序平台配置需按实际结果验收。原测试证书路径已核验，生产证书覆盖范围尚待检查。

## CI首轮失败与时间精度修复

首轮CI为107通过、1失败：MySQL的无小数秒DATETIME把任务接受时间向上舍入，导致立即投递查询可能看不到任务。确定性真实MySQL回归同时复现UTC15:59:59.999999（北京时间午夜前）被存成UTC16:00:00。此问题也影响注册日期边界，不能通过延长测试等待规避。

统一模型使用MySQL DATETIME(6)，兼容迁移0010保留微秒，读取最低结构版本改为0010，schema_contract仍为1。旧角色镜像可以继续读取扩展后的时间列。迁移不提供降低时间精度的数据回滚。

修复后，真实MySQL＋Redis/Celery的时间边界、空库迁移/模型一致性、就绪检查、实际Worker与SQL指标10项通过（45.67s）。本地全量106通过/7外部依赖跳过，Ruff/format/mypy44模块通过。修复前真实MySQL全量106通过/1Redis单独验证项跳过（572s），仍被CI发现了小数秒边界缺口；新增确定性用例永久保留。

MySQL的舍入行为依据：[官方小数秒说明](https://dev.mysql.com/doc/refman/8.0/en/fractional-seconds.html)。

## HTTPS与监控

`render-nginx.py`分别生成test/production四域名配置。API只代理本角色前缀，端口固定为本机18001/18002、28001/28002；Range/HEAD传给受控资源接口。后台使用CSP、HTML不存储、成功的哈希assets长期缓存；旧H5返回410。结构化访问日志只保留环境、服务、业务类别、方法、状态、耗时和request ID，不含路径、查询或用户资料；API默认错误日志关闭，错误监控使用安全结构化结果。Uvicorn关闭访问日志。

测试域名的真实证书、生成配置通过ECS `nginx -t`，未替换当前线上配置。证书有效期2026-10-10至2027-01-08，覆盖四个test域名。八个已确认test/production域名均解析到本ECS；生产证书准备继续执行。

`monitor.py`读取最近五分钟的安全日志，分开业务、云调用、媒体耗时；普通API达到20样本才判断P95/5xx比例。采集主机内存、CPU、磁盘、容器状态/OOM，以及SQL连接、积压年龄、过期任务租约、最近15分钟TTS失败率。告警连续两次异常才触发，连续两次正常才恢复，无数据不误报恢复；通知失败保留发件状态重试。告警仅包含固定信号码，不含用户资料。systemd service/timer默认无 `--notify`，启用通知需在完成上线演练后显式配置私密Feishu webhook文件。

ECS实际采集与故障→告警→去重→恢复演练通过，没有读取或发送Feishu webhook。SQL指标聚合已用真实MySQL验证；新应用就绪后才能验收完整采集与通知交付。目前未安装新HTTPS配置、未启用监控timer、未发送通知。

更新：生产证书已由既有ACME账号签发，有效期至2027-01-15，覆盖四个production域名。只安装了专属HTTP ACME/503准备配置，未启用新应用HTTPS代理。最终安装production.conf时须移除精确的 `/etc/nginx/conf.d/juya-rebuild-production-acme.conf`，避免重复80端口server_name；不得清理整目录。

第二轮CI112通过/1日志检查失败：实际Worker已完成任务，但默认启动横幅打印无密码测试Redis地址。新增全局quiet参数关闭横幅，保留日志检查；真实有密码及无密码Redis分别通过。无密码容器仅用于本机回环验证，已移除；生产Redis仍须认证。
