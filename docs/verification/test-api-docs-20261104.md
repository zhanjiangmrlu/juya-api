# 2026-11-04 测试环境接口文档开放

用户授权仅开放测试环境管理 API 和小程序 API 的接口文档。

- 管理 API Swagger：<https://test-admin-api.juyayingyu.com/docs>
- 小程序 API Swagger：<https://test-api.juyayingyu.com/docs>
- 两个域名的 `/openapi.json` 为各自运行服务的实时契约。

## 变更

仅在 `/etc/nginx/conf.d/juya-test-domains.conf` 的两个测试 API 虚拟主机新增 `/docs`、`/openapi.json`、`/docs/oauth2-redirect` 三个精确路径转发；保留其他已有规则。对应修改 `deploy/render-nginx.py`，只对 `test` 输出这些路径，生产渲染结果与修改前逐字节一致。没有更新应用镜像、重启容器或执行数据库操作。

配置于北京时间 2026-11-04 22:06 备份至服务器 `/root/juya-test-api-docs-20261104T140608Z/test-before.conf`，执行 `nginx -t` 成功后平滑加载。失败时安装脚本会恢复备份并重新校验、加载。

## 验证

- 修改前两个测试域名 `/docs` 均为 404；修改后三个文档相关精确路径均为 200。
- OpenAPI 的标题与角色匹配，管理 API 99 条路径均以 `/api/admin/v1/` 开头，小程序 API 70 条路径均以 `/api/mini/v1/` 开头，未混入另一角色接口。
- 未开放的 `/docs/not-a-route`、`/redoc` 仍为 404；未认证管理会话仍为 401。
- 生产两个域名 `/docs`、`/openapi.json` 仍为 404；测试、生产四个 API 的就绪检查均为 200。
- 除目标测试文件外，`/etc/nginx` 所有现有文件摘要一致；所有容器 ID、镜像、启动时间、重启次数一致。
- 浏览器验证工具超时，未完成浏览器渲染验收；公网 HTML、OpenAPI 和回调路径通过 HTTP 验证。未使用真实用户账号调用写接口。

回退时将上述备份恢复至原测试配置路径，执行 `nginx -t` 成功后 `systemctl reload nginx`。生产配置不参与替换。
