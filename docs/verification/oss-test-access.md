# 测试 OSS 验证 — 2026-10-17

用户补齐完整 RAM 凭证及桶、对象授权后，juya-test 实际上传、读取、删除均已通过。凭证不进入 Git、日志或聊天。

- 地域 cn-shenzhen，私有 ACL，版本控制未启用。公网 Endpoint https://oss-cn-shenzhen.aliyuncs.com 已连通；当前 ECS 到该地域内网 Endpoint 不通。
- 精确清单列举旧对象/空版本号版本各801项、分片0项；按清单删除后，对象、历史版本/删除标记、分片均复查为0。
- 清单SHA256：446a66b80d7aab093058585608962ae8680c4f050edcf58d6e3b2cc49d557f2e。根用户清单和报告位于 /root/juya-rebuild/legacy-oss-test-reset-{manifest,report}.json。
- 清空验收后才创建联调素材；后续非零对象不代表旧数据残留。

授权文件仅覆盖juya-test及其对象，没有通过程序扩大RAM权限。真实API图片/缩略图/音频异步处理及卡片发布通过。Range联调发现SDK StreamBody.read不接受size参数；三个安装的真实SDK流类型回归先复现同一TypeError，再验证有界iter_bytes、完整分块和提前关闭。修复镜像的真实传输验收仍待完成。

按用户最新要求，生产juya的OSS清理和新应用发布暂不处理。

最终更新：5877416已部署，真实HTTPS图片/音频Range与腾讯MP3完整传输通过，下线、版本切换和退出撤销验证通过。全部联调结束后，精确删除6个新测试对象，juya-test再次为空。旧测试素材和本次合成素材均未带入交付数据。详见test-rollout-20261017.md。
