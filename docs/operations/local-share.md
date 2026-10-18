# 本地开发环境外网分享

适用于当前 Mac 工作区：`/Users/lubi/Desktop/juya`。云服务器只负责 HTTPS 和 SSH 转发；前端、两 API、Redis、Worker 和调度进程都在本机运行。

## 日常启停

首次检出后，在工作区根目录运行 `cp github-repos/juya-api/deploy/local-share ./local-share` 恢复启停入口；私密配置和本机依赖需单独准备。

在工作区根目录执行：

```sh
./local-share start
./local-share status
./local-share stop
```

`start` 检查端口与进程归属，复用同一配置下的自有进程；配置改变时重新启动自有进程。其他程序占用端口时停止启动，不强行释放端口。`status` 检查本地就绪、Redis、三个域名的 HTTPS 与 API 实例标记；未登录 API 返回 401 表示鉴权入口可达。API 域名根目录返回 404 是正常行为。

`stop` 只终止带本工具启动标记、且进程创建时间匹配的进程组，关闭隧道并取消自动重连。关闭终端不会自动停止服务；电脑休眠、关机或断网期间无法访问。需要长时间测试时请保持电脑唤醒。

## 入口和数据

| 入口 | 用途 | 本地目标 |
| --- | --- | --- |
| `https://dev-admin.juyayingyu.com` | 后台页面及同源管理请求 | 页面 4173，API 8001 |
| `https://dev-admin-api.juyayingyu.com/api/admin/v1/` | 独立管理 API | 8001 |
| `https://dev-api.juyayingyu.com/api/mini/v1/` | 小程序 API | 8002 |

后台沿用原本地管理员账号。首次访问外网域名需要重新登录。当前局域网 IP 可能随网络变化，`start` 会追加当前 en0 地址至本地允许来源。

用户已授权复制数据库与素材：分享配置使用 `.private/local-share/ui.sqlite`（0013）和 `.private/local-share/media/`。原 `.private/ui.sqlite`（0012）和原素材目录保留。两份数据从复制时起独立，分享环境的新写入不会自动合并回原库。不要用旧的本地启动脚本同时争用 4173、8001、8002。

私密配置、密钥、PID 与日志位于 `.private/local-share/`，权限仅限当前用户。Redis 7.4.11 监听回环 16379，并启用认证和持久化；本地 ffmpeg 位于 `.tools/ffmpeg/bin/`。分享启停不会自动执行数据库迁移或创建合成微信登录会话。

## 微信体验构建

```sh
cd .worktrees/juya-miniapp
pnpm build:mp-weixin:local-share
```

使用工作区 `.tools/node/bin` 中的 Node/pnpm。构建强制使用 `https://dev-api.juyayingyu.com`，输出到独立的 `dist/local-share/mp-weixin/`，与普通构建目录分开。将该目录导入微信开发者工具，确认 AppID 为当前句芽小程序，然后上传开发版本并在微信后台设为体验版。保持合法域名、TLS 与证书检查开启。

request、uploadFile、downloadFile 合法域名均需包含 `https://dev-api.juyayingyu.com`；真实微信登录所需 AppSecret 只保存在本地后端。正式构建仍使用原有生产配置。此次上传替换的是体验版代码，不执行正式发布。

已验证的本地分享上传版本为 `1.5.0-local.1018.2`。手机流量登录、卡片和音频的验收记录见 [本地分享验收记录](local-share-verification.md)。在微信后台版本管理中将此版本设为体验版后，再分发体验二维码。

后台代码修改可热更新；后端代码修改后执行 `stop`、`start` 重新加载；小程序代码修改后需重新构建、上传体验版。

## 排查与回退

- 503：先运行 `status`，检查电脑是否唤醒、本地服务与 SSH 隧道日志。
- 403：核对后台访问网址是否在允许来源中，登录后再试；不要关闭 CSRF。
- 上传后长期处理中：检查 Redis、Worker、调度进程及 ffmpeg。
- 小程序提示域名错误：确认导入的是独立分享目录，并检查微信合法域名。
- SSH 首次转发失败：检查远端回环 34173、38001、38002 是否空闲。已有连接断线后会自动重连。

云端开发配置为 `/etc/nginx/conf.d/juya-dev-local.conf`，证书名为 `juya-dev-local`，已配置 Certbot 续期与 Nginx 加载钩子。云端 SSH 用户 `juya-dev-tunnel` 仅允许指定回环端口的反向转发，不提供交互式 Shell。

回退：先停止本地分享，再禁用上述开发 Nginx 配置并执行 `nginx -t` 后平滑加载。初次配置备份目录为 `/root/juya-local-share-backup-20261018T142520Z`。测试及正式站点的配置无需替换。需要恢复原体验版时上传原来的构建。
