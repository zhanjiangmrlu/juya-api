# 测试OSS权限核对 — 2026-10-17

用户已在账号文件的RAM访问控制下补充完整、独立的AccessKey ID/Secret。密钥仅用于本地进程及ECS根用户私密检查文件，不进入Git、普通日志或聊天。

使用新凭证从本机及ECS访问juya-test，公网Endpoint为https://oss-cn-shenzhen.aliyuncs.com。ListObjectsV2、ListObjectVersions、ListMultipartUploads均返回403 AccessDenied，EC0003-00000001；不能把失败结果中的零长度列表当作空桶。可选的juya前缀Bucket发现也被oss:ListBuckets拒绝；运行和清理不要求开放此账号级权限。

官方说明：此错误可能与凭证或对目标Bucket/Object的授权有关，不能仅凭英文not belong to you断定Bucket归属错误。[错误说明](https://www.alibabacloud.com/help/tc/oss/user-guide/0003-00000001)。请核对真实Bucket名称、地域及该RAM用户对资源的授权；若juya-test实际是目录，应提供所属Bucket及目录前缀。

[oss-rebuild-policy.json](../../deploy/oss-rebuild-policy.json)现仅覆盖juya-test及其对象，包含重置需要的版本/分片列举删除，以及运行需要的对象读写。未授予其他Bucket、账号级ListBuckets或RAM管理权限。由有权限的账号绑定给所提供AccessKey所属用户后再实测；未自动扩大RAM权限。

动作名称依据[OSS授权映射](https://www.alibabacloud.com/help/en/oss/user-guide/authorization-syntax-and-elements)和[Bucket ACL权限](https://www.alibabacloud.com/help/en/oss/developer-reference/getbucketacl)。ECS到当前深圳内网Endpoint实测不通，外网Endpoint可到达并返回明确403；不能在授权修复后仍沿用未经连通验证的内网地址。当前两套新业务API尚未启用。

按用户最新范围，只推进测试juya-test；生产juya的素材清理与新应用发布暂不处理。
