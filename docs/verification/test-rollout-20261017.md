# 测试环境交付与实际验收 — 2026-10-17

当前范围按用户最新指令限定测试 juya-test。生产 OSS 清理和新应用发布暂缓；本记录不代表 T01—T113 或生产上线全部签收。

## 可访问内容与版本

- 后台：https://test-admin.juyayingyu.com
- 管理 API：https://test-admin-api.juyayingyu.com/health/ready
- 小程序 API：https://test-api.juyayingyu.com/health/ready
- 两 API 镜像提交5877416，分别独立发布；后台6add0ac，运维脚本f4c044c，小程序源代码abd7df5。
- [API修复CI](https://github.com/zhanjiangmrlu/juya-api/actions/runs/39025440990)与[运维CI](https://github.com/zhanjiangmrlu/juya-api/actions/runs/39025958407)均全部成功，包含真实MySQL8.4、Redis7.4、两角色镜像及隔离音频解码。
- 管理员登录信息保存在本机私密文件 `/Users/lubi/Desktop/juya/.private/test-admin-login.json` 和ECS `/etc/juya/rebuild/test/admin-login.json`，权限0600。文件和内容均不进入Git。

## 真实链路结果

实际CLI引擎分别执行两API和后台发布。SSH传送使用私密密码助手；本机现有SSH密钥尚未授权，未新增服务器登录密钥。前后台静态包校验、API readiness、不可变镜像/config/OCI图校验均通过。

新HTTPS配置通过ECS nginx -t后只替换测试vhost；首次私密切换助手错误地将渲染结果字典作为文本，未完成配置切换，后台发布校验失败并恢复原站点指针。修正助手、生成新发布编号后，后台HTML和哈希assets实际HTTPS验证成功。生产准备配置未修改。

真实OSS图片、缩略图及完整音频异步处理，草稿预览、发布、学习完成、持久幂等重放和前后台统一统计均通过。SDK的StreamBody.read(size)错误通过真实SDK类型回归复现并修复为有界迭代。真实图片/音频Range获取100字节成功；腾讯MP3实际返回4032字节，首次任务准备8.366秒，下载164.31ms（SSH回环验证）。HTTPS再次验证同一缓存成功；这些云端及媒体耗时不计入普通API压测。

实际HTTPS验证两类凭证不能互用，角色前缀隔离、CSRF/CORS预检、Cookie会话、HTML no-store和哈希assets immutable。下线时旧素材Range及新增学习返回410，陈旧预览409，新草稿发布后旧版本资源409；重新学习累计卡数不增加。退出后会话及已签发媒体引用401。旧H5返回410。

## 20并发学习与导入

| 项目 | 实测 |
| --- | --- |
| 并发合成学习用户 | 20 |
| 业务请求 | 420，全部200 |
| 客户端P95 | 402.44ms |
| 最大单次耗时 | 818.31ms |
| 错误率 | 0% |
| 同时20张DOCX导入 | 7.502秒，20张全部可读取 |
| 资源采样 | 41次，主机可用内存最低4.81GiB |
| 六应用容器 | 无OOM、自动重启0、均健康 |

这是直接请求测试HTTPS的有限负载实验，客户端每次操作间隔0.4秒，共3轮。初轮mini API0.3核、SSH隧道路径时P95为1690.89ms，未通过；调整资源配置后通过上述HTTPS复测。请求路径及资源同时变化，此数据不能单独归因于一项优化。

测试API交付配额admin0.4核/384MiB、mini0.8核/256MiB；两Worker0.5核、并发1，测试CPU shares256。该轮mini Worker256MiB曾触及cgroup上限，但oom/oom_kill均0；交付时放宽至384MiB，admin Worker512MiB。Worker探针超时30秒，避免低CPU配额冷启动误判。

生产应用尚未运行，因此本轮不替代原方案中测试、生产应用同时运行的压测，也不证明更高并发或长期负载。

## 独立发布和回滚

管理API5877416回滚至665820a，再以publish操作发布5877416。全过程小程序API、Worker、dispatcher的容器ID、镜像ID、启动时间和自动重启数保持不变；操作期间93次学习写入全部成功，无数据库迁移或恢复。另一次早期回滚/恢复演练124次写入也全部成功。

## 从空数据交付

旧测试OSS按精确清单清除801项旧对象版本，复查对象、历史版本/删除标记和分片为0。旧清单SHA256为446a66b80d7aab093058585608962ae8680c4f050edcf58d6e3b2cc49d557f2e。

验收后对照精确测试ID清单，停止测试写入，移除20个合成用户、3卡/4发布版本、60个完成档案、60个每日学习、20个打卡、60个收藏、2导入批次/40候选、任务/幂等/发音与旧测试会话，以及6个新建OSS对象。保留1个管理员和结构兼容标记。测试Redis在清理时清空，服务重新启动且全部健康，监控timer恢复。没有处理生产OSS或生产新应用。

验收清理清单SHA256：2dabcfdeac5956a7b6d3ecb28582066d265dd62ae9fc9236fcb58f06d269637e。清理后实际HTTPS确认用户0、卡片0、统计0，旧合成用户Token401，管理员仍可登录。最终交付复查没有重建业务样本。

## 监控与剩余验收

仅test的systemd监控timer已启用。实际SQL聚合可用，告警两次异常触发、去重和两次正常恢复均通过；未启用通知，未发送Feishu消息。

小程序通过实际juya-cli构建测试MP包，9页面/2底部导航检查通过，产物位于juya-miniapp/dist/build/mp-weixin。没有微信开发者工具或物理设备验收证据；真实微信登录、手机音频/拖动/防叠播、头像、大图及返回位置仍待真机验证。

部署后IAB自动化绑定多次超时，未完成线上页面视觉复验；应用原生访问工具明确不允许控制Codex应用，未绕过限制。此前本地浏览器对同一后台源提交的核心流程及异常状态证据保留，公共HTML/assets/鉴权/接口检查不能替代视觉验收。修订12全状态视觉、双环境同机压测、通知交付和生产发布保留为待签收项。

数值证据见test-rollout-evidence-20261017.json。没有将合成账号当作真实微信接入验收。
