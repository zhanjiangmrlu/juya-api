# 修订15外部依赖核对

日期：2026-10-22；仅只读源码及官方资料核对，未采购、调用付费服务或更改实际账号配置

## 通用词典

基线7.7未指定或授权采购供应商。按已确认方案提供可替换适配层和有明确授权元信息的本地数据入口；本篇确认释义不依赖通用词典。无数据、服务失败、真正查无词条分别处理；不生成假释义，不以测试样例宣称完整覆盖

通用词形映射使用真实数据的明确映射，不猜原形；显示原词并按原词发音。真实授权数据、覆盖率及用量条件仍待落实。测试替身只能证明接口边界、语境匹配和异常恢复

## 反馈内容安全

现状：用户身份仅保存AppID和OpenID的HMAC摘要；业务会话默认七天。摘要不可还原成OpenID；管理员是独立后台身份。现有代码未提供内容安全网关、微信后台token缓存及媒体安全回调

官方资料核对：

- [msgSecCheck](https://developers.weixin.qq.com/miniprogram/dev/server/API/sec-center/sec-check/api_msgseccheck.html)：2.0服务端同步文本检查，version=2、原始openid和scene必填，要求用户近两小时访问；pass/risky/review必须分开，接口调用成功不等于检查通过
- [mediaCheckAsync](https://developers.weixin.qq.com/miniprogram/dev/server/API/sec-center/sec-check/api_mediacheckasync.html)：同样需要原始openid和近两小时访问；首次只表示接收，需按trace_id关联异步推送结果，不能把errcode=0当内容通过
- [旧imgSecCheck](https://developers.weixin.qq.com/miniprogram/dev/framework/security.imgSecCheck.html)：旧1.0已停止维护，不用它绕开2.0的身份及异步流程
- [消息推送配置](https://developers.weixin.qq.com/miniprogram/dev/framework/server-ability/message-push.html)：若直接接入微信媒体检查，需要真实回调验签、解密、AppID检查与重复通知处理

当前官方页面没有列出仅企业主体限制，不能凭此断言句芽实际AppID已有权限；真实主体权限、额度、白名单及微信版本仍须另行核验

本轮采用已批准的真实HTTPS安全网关边界，暂不新增可还原OpenID。原因：既有摘要无法回填；新增密文身份也不能代替近两小时访问条件，且不能用用户OpenID冒充独立管理员回复身份

网关必须连接真实检查能力并覆盖用户与管理员提交；仅代理微信2.0接口仍受原始OpenID和访问限制，不能声称已解决。只传本次必要文字／已解码去元数据图片和检查关联标识，不传用户联系方式或业务会话。未配置、超时、异常、待复核或未取得最终结果均不能作为通过

正式验收所需：真实服务与数据处理约定、配置、权限、文字／图片检查结果、失败重试及必要回调。当前只允许验证严格适配和失败保留输入，不将此记为真实内容安全已完成

## 原生分享预核对

- [微信官方 API typings](https://github.com/wechat-miniprogram/api-typings/blob/master/types/wx/lib.wx.page.d.ts)：好友回调使用 title/path/imageUrl，封面5:4；朋友圈使用 title/query/imageUrl，封面1:1，没有独立 description 字段。平台字段不接受发送者业务身份
- [腾讯官方单页说明](https://cloud.tencent.com/document/product/1301/107818)：朋友圈单页不等于启动完整小程序，只承接分享页；相关平台限制应真实验证。该页关于微搭全托管授权等要求属于微搭产品，不能推断为本项目通用限制
- 2026-10-22可读取官方 typings／腾讯说明，微信直接文档页本次读取失败；不能据旧类型注释断言当前 iOS 能力。开发按能力检测与安全摘要承接，实际 AppID、基础库及 iOS／Android 真机另验
- 已定位当前设计资源 assets/brand-share.png 和 brand-share-square.png，后续批4复用品牌图；场景图生成等比展示副本，不改原图、不暴露原私有媒体地址
