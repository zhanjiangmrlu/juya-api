# 生产数据库迁移至阿里云 RDS MySQL

本手册用于将现有 `juya_production` 从 ECS 上的 MySQL 8.4 搬到 RDS MySQL 8.4。控制台配置由操作人完成；数据导入、结构升级及流量切换分阶段执行。应用发布不会自动搬迁数据库。

## 当前准备结果（2026-10-24）

- 四个交付仓库已建立精确命名的 `release` 分支。CLI 的 ECS 项目生产发布允许 `main` / `release`，测试只允许 `test`；微信包沿用现有独立构建流程。
- 源生产库有 29 张表，结构版本 `0010`；卡片、管理员、用户及任务等业务表均为空，只有迁移版本和系统计数初始化记录。
- 现有 ECS 上未发现生产 API、Worker、dispatcher 容器；测试角色及共享 MySQL 正在运行。这是读取时的状态，执行前必须复核。
- ECS 到目标 RDS 内网地址的 DNS 和 TCP 3306 已通过；尚未验证数据库账号登录、授权、导入及业务验收。
- 两生产角色的字段加密和查找密钥均存在且相同。迁移必须保留原值。

## 2026-10-25 准备更新

- 用户已确认创建 `juya_production`、迁移账号和应用账号；账号登录和实际授权仍需从容器网络验证。
- `release` 已合入最新 `test`，包含修订16学习授权及迁移 `0018`。RDS 地址配置和生产分支校验保留，两角色部署预检现在都要求至少 `0018`。
- 原有测试发布记录已保留。生产切换前需重新读取源库、容器、磁盘和目标空库状态，不能直接沿用前一天的快照。
- 密码由操作人填写本机权限 0600 的私密文件供登录核验，不能提交到仓库。配置就绪前不修改生产运行文件。

## 操作人在阿里云控制台完成

1. 进入广州地域的目标 RDS 实例，确认 MySQL 8.4、VPC 与 ECS 内网连接条件。保留内网地址，不需要为此次迁移申请公网地址。
2. 数据库管理 → 创建数据库：`juya_production`，字符集 `utf8mb4`。记录源库的默认排序规则并核对目标；导入文件中的表级排序规则应完整保留。
3. 账号管理 → 创建 `juya_production_migration` 高权限账号，用于本次导入及后续显式结构升级。若实例已有高权限账号，先确认既有账号用途，不删除或重置它；可由该账号为专用普通迁移账号授予本库所需权限。
4. 创建 `juya_production_app` 普通账号，只授权 `juya_production`，控制台先选“仅 DML”。该档包含额外权限，上线前用 `SHOW GRANTS` 核对并收敛至现有应用所需的 SELECT、INSERT、UPDATE、DELETE；禁止将高权限账号写入应用运行文件。
5. 白名单与安全组：核对 ECS 实际出站内网 IP 已放行。成功的 TCP 检查不代表账号登录成功；无需放行所有公网 IP。
6. 备份恢复 → 备份策略：建议每日低峰期备份，数据备份保留至少 7 天，开启日志备份或任意时间点恢复并保留至少 7 天。导入后手动创建一次全量备份，确认成功。
7. 两个账号使用不同密码。密码只进入密码管理器及权限受控的服务器配置，不进入聊天、Git、发布包、命令行参数或普通日志。

参考：[创建账号](https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/create-an-account-on-an-apsaradb-rds-for-mysql-instance)、[账号权限](https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/account-permissions)、[备份策略](https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/full-backup)。

## 切换前核对与备份

1. 记录目标实例、内网域名、端口、源库版本、排序规则、所有表的引擎、结构版本、逐表精确行数及校验摘要。记录在私密运维目录，不能只用 information_schema 的估算行数验收。
2. 使用专用账号从实际应用容器所在 Docker 网络测试 RDS 登录、`SELECT 1`、目标数据库及 `CURRENT_USER()`；同时核验应用账号不能访问测试库、不能修改表结构。只做 TCP 检查不足以通过此步骤。
3. 检查源库所有表均为 InnoDB，确认是否存在视图、触发器、存储过程或事件。下面的简化导出流程仅用于没有这些额外对象的现有库；如发现额外对象，先准备其权限、DEFINER 和单独迁移清单。
4. 确认维护窗口。若生产已启动，先阻断两 API 的写流量，停止两个 dispatcher 并排空/停止两个 Worker，最后停止两 API；核对没有其他生产写入者后再导出。空库也需防止备份后出现新写入。
5. 对 `/etc/juya/rebuild/production` 的原运行文件和 Compose 选择文件做权限受控的副本，记录原镜像及发布版本。保存原 `JUYA_FIELD_ENCRYPTION_KEY`、`JUYA_LOOKUP_KEY`，不要重新初始化基础设施或生成密钥。
6. 测试环境仍使用共享 MySQL；不得停止、删除该 MySQL、数据卷或测试服务。

## 导出和恢复

命令由部署者在 ECS 上执行，不是控制台步骤。先建立仅 root 可读的 `/root/juya-rds-migration`，目录权限 0700、文件权限 0600，并设置 `umask 077`。准备以下两个 MySQL 客户端选项文件，真实密码通过安全编辑器或交互输入写入，不能通过 shell 参数传入：

```ini
# source.cnf：源库可用于一致性导出的既有账号
[client]
host=mysql
port=3306
user=REPLACE_WITH_EXISTING_BACKUP_ACCOUNT
password=REPLACE_IN_PRIVATE_FILE
default-character-set=utf8mb4
```

```ini
# target.cnf：目标库专用迁移账号
[client]
host=REPLACE_WITH_VERIFIED_RDS_INTERNAL_HOST
port=3306
user=juya_production_migration
password=REPLACE_IN_PRIVATE_FILE
default-character-set=utf8mb4
```

不要把上述占位内容当作已经可运行的凭证文件。密码中的引号、反斜线等必须按 MySQL 选项文件语法转义。`MYSQL_CLIENT_IMAGE` 由部署者设为已验证、本机缓存的 MySQL 8.4 不可变镜像 ID，不能使用浮动标签。源库导出使用内部隔离网络 `juya-rebuild-database`；目标 RDS 登录检查和导入必须使用可出站的 `juya-rebuild-production` 网络，核验其归属、DNS、路由与实际出站 IP 后再继续。主机 TCP 检查不能替代容器网络检查。

只导出业务库，不导出 `mysql` 系统库、账号和全局授权：

```sh
umask 077
docker run --rm --pull=never --network juya-rebuild-database \
  --mount type=bind,src=/root/juya-rds-migration/source.cnf,dst=/run/mysql-client.cnf,readonly \
  "$MYSQL_CLIENT_IMAGE" mysqldump --defaults-extra-file=/run/mysql-client.cnf \
  --single-transaction --quick --hex-blob --no-tablespaces \
  --set-gtid-purged=OFF --column-statistics=0 --default-character-set=utf8mb4 \
  juya_production > /root/juya-rds-migration/source.sql
```

必须检查导出退出码为 0、文件非空并保存 SHA-256。业务冻结期间不要执行 DDL。目标必须是已确认空的 `juya_production`；不要对已有业务的目标库直接重放含 DROP TABLE 的转储：

```sh
docker run --rm -i --pull=never --network juya-rebuild-production \
  --mount type=bind,src=/root/juya-rds-migration/target.cnf,dst=/run/mysql-client.cnf,readonly \
  "$MYSQL_CLIENT_IMAGE" mysql --defaults-extra-file=/run/mysql-client.cnf \
  --protocol=TCP juya_production < /root/juya-rds-migration/source.sql
```

检查导入退出码，逐表对比行数、表结构、业务字段摘要和 `alembic_version`；在升级前应与源库一致。保留源库和转储文件。不要从测试库复制用户、会话或素材映射来填充生产库；测试内容晋升需要另行明确范围。

## 修改连接并升级结构

在两 API、Worker 和 dispatcher 均未运行/仍保持停写时，分别准备以下受控文件，暂不恢复流量：

| 文件 | 数据库账号 | 修改内容 |
| --- | --- | --- |
| `/etc/juya/rebuild/production/admin.env` | `juya_production_app` | RDS 连接、显式预期主机 |
| `/etc/juya/rebuild/production/mini.env` | `juya_production_app` | 同一 RDS 库、同一预期主机 |
| `/etc/juya/rebuild/production/migration.env` | `juya_production_migration` | RDS 迁移连接、同一预期主机 |

运行配置新增：

```dotenv
JUYA_EXPECTED_DATABASE_HOST=REPLACE_WITH_VERIFIED_RDS_INTERNAL_HOST
JUYA_DATABASE_URL=mysql+pymysql://juya_production_app:URL_ENCODED_PASSWORD@REPLACE_WITH_VERIFIED_RDS_INTERNAL_HOST:3306/juya_production?charset=utf8mb4
```

迁移文件仅把数据库账号/密码换为迁移账号。用 URL 编码处理密码特殊字符，不能直接拼接。其余生产字段加密/查找密钥、Redis、OSS、微信与 TTS 配置保持原值，文件权限保持 0600。预检默认只接受 `mysql`；切至 RDS 必须显式配置准确主机名，且仍只接受生产库和应用账号。

等待 `release` 分支 CI 的质量检查及两个角色镜像构建成功，下载与当前源码完整提交一致的 admin/mini 产物。CLI 使用已核验的 SSH 主机指纹及发布凭证；当前已有的密码诊断连接不等于 CLI 密钥认证已经可用，部署前需单独打通。

在 `juya-cli` 目录执行，`--workspace` 指向四仓库父目录，`--config` 指向权限受控的既有生产发布配置：

```sh
node bin/juya.cjs migrate --environment production --project juya-admin-api \
  --workspace /absolute/path/github-repos --config /absolute/path/private-release-config.json \
  --artifact /absolute/path/verified-admin-artifact
```

这一步通过迁移账号把恢复的 `0010` 升级到 `head`（当前 `0018`），不是导入数据。检查结构、约束和系统计数；既有管理员非空时不要重复初始化。当前空生产环境需要在升级后通过 `deploy/bootstrap-admin.py` 的安全标准输入流程创建首位管理员。

`0018` 新增的免费策略和学习授权默认未启用，不给已有用户自动赠送授权。生产 `JUYA_LEARNING_ACCESS_ACTIVATION_READY` 先保持 false；两角色及全部 Worker/dispatcher 都完成新版本验收后，再按修订16发布门禁单独开启管理侧就绪开关。免费数量 N 由管理员核对名单后设置，不能从测试配置猜测或复制。

## 发布与验收

1. 通过 CLI 分别发布生产 admin、mini，产物必须来自同一份后端提交。两角色及其 Worker/dispatcher 都要完成切换，不能出现一部分连接源库、另一部分连接 RDS。
2. 在容器内只输出数据库主机、库名、账号和版本等无密信息，确认三类进程的实际连接目标。检查两 API `/health/ready`、Worker 健康、dispatcher、Redis 和任务处理。
3. 保持业务流量关闭，验证管理员登录、卡片列表、受控图片/音频、微信登录，以及一组有明确清理范围的生产验收流程；再发布后台和小程序、恢复流量。模拟测试通过不能替代真实云服务验收。
4. 观察错误率、连接数、CPU/内存、慢 SQL 和任务积压，确认 RDS 导入后全量备份成功。按约定保留源库与转储，清理另行安排。

## 回退边界

- 恢复业务写入前：停掉已切换的生产进程，恢复原运行配置及原镜像；只有在原镜像与源库结构兼容时才恢复源库服务。源库为 `0010`，当前两角色部署预检要求 `0018`，不能把最新镜像直接指回旧结构后宣称回退成功。
- 恢复业务写入后：新数据已在 RDS，不能直接改回旧库。先冻结写入、保存两边快照，再制定增量对账/回迁方案，避免丢失学习、账号和任务数据。
- CLI 应用回滚不恢复数据库、运行配置或数据；也不运行 Alembic downgrade。恢复演练需单独验证。
