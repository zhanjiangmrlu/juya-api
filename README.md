# 句芽英语统一后端

统一业务模块与数据库，独立交付管理 API 和微信小程序 API。按需求基线20261017、修订12和已批准的全量重建方案实现。原业务数据不迁移。

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

[部署与验证记录](docs/verification/deployment.md)说明镜像、空库初始化、显式迁移和逐服务发布。[实施进度](docs/implementation/progress.md)记录已完成证据及仍需验收的外部条件。
