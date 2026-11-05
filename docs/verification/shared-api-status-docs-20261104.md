# 2026-11-04 Swagger 公共状态码与成功响应展示

用户要求公共状态码集中说明，每个接口仅展示请求成功的返回。范围延续为测试管理端和小程序端，生产环境不动。

## 实现与验证

源码为 `d47dd21a726299351ac17e4c2436ece53d1f7665`，已推送 `test`。Swagger 页面读取实时 `/openapi.json`，复制为展示副本，在顶部追加公共状态码和统一错误返回格式，各操作仅保留 2xx 成功响应。原始契约、成功响应结构、错误处理及鉴权不变；实际调试收到的错误仍正常显示。

本地 FastAPI 与测试静态页面共用 `swagger_docs.py`；`deploy/export-swagger-docs.py` 可重现两份 HTML。页面独立发布，不需要替换业务 API 镜像。生产文档保持关闭。

- Ruff、格式、mypy 通过；两份契约导出零差异。
- 页面脚本与契约专项 **12 通过**；通过 Node 实际执行页面脚本，覆盖全部操作、原始对象不被修改、206 成功响应头及默认错误响应的处理。全量 SQLite 回归 **595 通过、45 条件跳过**。
- 独立审阅无未解决 P1/P2。该次上线仅使用生成的文档 HTML，没有部署后续 CI 构建的 API 镜像。

## 公网与浏览器验收

- [管理端文档](https://test-admin-api.juyayingyu.com/docs)：124 个操作只展示成功响应，公共说明只出现一次。
- [小程序文档](https://test-api.juyayingyu.com/docs)：75 个操作只展示成功响应，公共说明只出现一次。
- 独立从公网下载两页 HTML 和对应规范，执行实际页面 JavaScript，验证上述 199 个操作及原始规范未变。两页 HTML 与源码生成字节相等。
- Chrome 实际刷新管理端文档，公共状态码表与统一错误格式正常渲染；展开用户截图中的词汇发音 GET 接口，Responses 仅有 200 和成功结果结构，未再逐接口列出错误响应。未执行 Try it out 或业务写操作。
- 两份 `/openapi.json` 字节摘要前后相等；OAuth 回调 200，未开放路径 404，四个 API 健康检查 200，生产两个域名的 `/docs` 与 `/openapi.json` 仍为 404。

## 发布边界

仅将测试 Nginx 两个 `/docs` 精确路径切换至 `/opt/juya/rebuild/test/api-docs/current/{role}.html`；其余代理路径及安全响应头保留。内容地址目录校验后原子切换链接和配置，通过 `nginx -t` 后平滑加载；安装失败会恢复配置及旧链接。UTF-8、缓存重验证、ETag 条件 GET 304 均通过。

全部 19 个容器的 ID、镜像、启动时间、健康、重启和 OOM 状态保持一致；其他全部 Nginx 配置摘要不变。安装前测试数据库已由其他任务升级至 `0025`，本轮保持该实际基线不变，没有迁移或业务数据操作。

配置备份：`/root/juya-rebuild/docs/shared-api-status-docs-20261104-20261104T153037Z/test-before.conf`。完整私有回执保存在工作区 `.private/shared-api-status-docs-20261104/`，不归档凭据。
