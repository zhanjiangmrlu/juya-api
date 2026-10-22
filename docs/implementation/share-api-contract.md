# 修订15批4：公开分享边界与前后端约定

依据：基线34章、T179—T185及已确认六批实施方案。仅本地开发与验证，不推送、部署或上传体验版。

## 公开接口

- `GET /api/mini/v1/public/cards/{card_id}/share`，匿名可读，只返回当前有效发布版本的 `PublicSceneShare`
- `GET/HEAD /api/mini/v1/public/cards/{card_id}/share/images/{version_id}/{variant}`，`variant` 为 `friends` 或 `timeline`
- `PublicSceneShare` 字段严格限于 `card_id`、`version_id`、`name`、`title_en`（历史缺省为空串）、`images.friends.{url,width,height}`、`images.timeline.{url,width,height}`。固定尺寸分别600×480与600×600
- 不复用已认证详情DTO，不返回正文、音频、媒体ID、存储键、发送者身份、学习／收藏／反馈状态
- 两种封面实际准备成功后才返回摘要200；原始场景图等比容纳于展示副本，不裁切、不修改原资源，EXIF方向正确、透明底转浅底、真实静态图片解码并去元数据
- 每次GET／HEAD均先核查当前发布状态与版本；缓存不能绕过下线／删除／换版／素材失效检查。缓存有条数及总字节上限，不在磁盘复制私有原图
- 错误：未知404；下线／删除410；已换版409 `version_changed`；非法variant422；原图不可读／损坏或生成失败503 `share_image_unavailable`／`publication_unavailable`。不返回假封面或旧正文。响应 `Cache-Control: no-store`、`X-Content-Type-Options: nosniff`，不以304跳过校验
- 只注册小程序API，后台不提供公开分享路由；无需新增数据表，最低版本仍0015

## 原生分享及目标

- 只U01与有效U03开放好友／群、朋友圈菜单；个人页面隐藏，不能退回平台默认截图分享
- U01标题固定“句芽英语｜在真实场景里学英语”，复用设计资源 `brand-share.png`／`brand-share-square.png`
- U03标题由当前发布中英文生成；缺英文仅中文。图片来自上述公开副本，不用私有媒体grant，不泄露草稿
- 好友使用 `title/path/imageUrl`；朋友圈使用 `title/query/imageUrl`。没有独立description，不显示虚假分享成功；准备失败时保留明确错误和重试
- 接收参数仅目标类型与稳定card_id，不能携带来源队列、发送者会话或业务个人状态。登录恢复参数经过白名单处理；不保留外来queue或version参数
- 有效会话先确认接收者身份再取正文；无会话进入默认未勾选的U00，主动登录成功重查当前目标；失败留U00并保留安全目标，失效目标U05
- 分享单卡无来源队列，完成留U03显示“前往学习页”，无来源返回U01

## 朋友圈仅浏览模式

- 在应用启动和页面显示、任何鉴权／资料／音频初始化之前识别官方 `apiCategory='browseOnly'`，不能只用scene1154推断，也不能因本地已有会话绕过
- 该模式只请求公开安全摘要与封面；不恢复me／统计，不请求全文／音频／词典，不调用微信登录或完成／收藏／阅读写入
- U01展示品牌摘要，U03展示公开双标题和图；引导使用微信平台自身的完整小程序入口。没有官方证据支持脚本主动切完整模式，不能伪造打开成功
- 完整运行态再按安全目标恢复并检查身份。微信版本能力与iOS／Android原生入口须真机另验；H5和注入的平台模式测试只证明代码边界

官方资料与限制见同目录 `revision15-external-dependencies.md`。
