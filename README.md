# 句芽英语统一后端

统一业务模块与数据库，独立交付管理 API 和微信小程序 API。当前按V1.5整合04增补02、修订17增量实现，保留原场景及学习历史，新增主题听读。

**换MacBook继续开发先读[交接文档](HANDOFF.md)**：远程代码分支为`test`，继续使用Mac原有四项目环境和本地数据库；需求由用户同步，版本引用、设计链接、实施/复审、截图和未验事项已入库。原全量重建及线上运维记录保留为历史，不代表本次授权发布。

- Python3.13、FastAPI、SQLAlchemy2、Alembic、MySQL8.4、Redis、Celery、私有OSS
- 管理入口：`juya_api.admin:create_app`，接口前缀 `/api/admin/v1`，Cookie会话与CSRF
- 小程序入口：`juya_api.mini:create_app`，接口前缀 `/api/mini/v1`，可撤销业务Token
- 稳定卡片、编辑草稿、不可变发布版本分离；学习完成、每日学习及打卡同事务提交
- 素材异步校验，受控资源与短期授权在每次请求时检查归属、版本及上下线状态
- 任务状态持久化，两个角色使用独立队列、Worker和补偿调度进程

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
```

默认测试使用隔离的SQLite和外部网关替身。真实MySQL验证必须显式设置 `JUYA_TEST_DATABASE_URL`，数据库名称只能为 `juya_verify`，测试会清空该验证库。真实队列验证使用单独的 `JUYA_TEST_REDIS_URL`。测试配置和替身不代表生产云服务已经验收。

独立接口契约位于 `openapi/admin.json`、`openapi/mini.json`，通过 `uv run python scripts/export-openapi.py` 生成。两个前端各自生成TypeScript类型。

后台管理员登录会话默认固定有效30天，服务端会话和浏览器Cookie使用同一到期时长，不随访问自动续期。`JUYA_ADMIN_SESSION_HOURS`以小时为单位，默认720；调整后重新登录才会获得新的有效期，既有会话保留签发时的到期时间。主动退出立即撤销会话。

固定用户编号要求迁移至0019：已有用户按注册时间、UUID升序补号，新注册事务分配后续编号，后台显示Juya001且保留UUID关联。新版本双API及Worker就绪检查均要求0019；该迁移要求停止旧注册写进程后执行，具体顺序见[用户编号迁移说明](docs/operations/user-number-migration.md)。

V1.5验收修复契约见 `docs/implementation/v15-acceptance-api-contract.md`。管理员服务及Worker要求迁移至0017（导入批次软删除）；迁移保持旧列集INSERT兼容，但删除入口启用前应停止或排空旧管理员写进程。反馈外部审核默认关闭（`JUYA_FEEDBACK_SAFETY_ENABLED=false`）；设为true后须配置HTTPS安全网关及令牌，只有明确最终allow通过，其他业务和权限校验始终保留。

[部署与验证记录](docs/verification/deployment.md)说明镜像、空库初始化、显式迁移和逐服务发布。[实施进度](docs/implementation/progress.md)记录已完成证据及仍需验收的外部条件。

生产迁往 RDS 的控制台设置、数据备份、导入校验、连接切换与回退边界见 [RDS 迁移手册](docs/operations/rds-production-migration.md)。RDS 运行文件须显式设置 `JUYA_EXPECTED_DATABASE_HOST`，默认值 `mysql` 保持现有容器数据库部署兼容。
