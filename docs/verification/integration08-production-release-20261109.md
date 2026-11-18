# 整合08生产后端升级与游客验收（2026-11-09）

按用户本次明确授权，先停写并备份生产数据库，再升级0026，最后发布远程release后端。生产切换完成于北京时间 **2026-11-09 15:17:57**；游客首页及列表公网复验通过，现有数据保留。此前“test合并release未部署”的记录属于合并时状态。

## 源码与发布

生产固定源码 **`b36fc5a5e758adbb3333cebec25700ba04142b99`**，为用户合并test后的真实release提交；替换此前生产`b2744ec`。官方[CI 42573453878](https://github.com/zhanjiangmrlu/juya-api/actions/runs/42573453878)真实MySQL／Redis **763通过、3项SQLite专属跳过**，quality及两个Linux/amd64镜像构建均成功。官方归档摘要、源码／角色／平台与镜像身份经原生发布器校验；沿用现有生产配置、词典覆盖和运行网络。

| 发布目标 | 当前release ID | 结果 |
| --- | --- | --- |
| 管理API、Worker、dispatcher | `20261109T070232-b36fc5a5e758-b89f29` | 3服务healthy |
| 小程序API、Worker、dispatcher | `20261109T070624-b36fc5a5e758-5f7f9e` | 3服务healthy，真实词典闸门通过 |
| 独立听读Worker | 同管理镜像 | healthy，原配置仅切换镜像 |

7服务均运行固定b36源码，restarts为0且无OOM。原生current／previous指针保留本版和此前b274版；测试、基础设施等其余12容器的完整元数据不变。本轮没有更新管理前端或发布CLI。

## 备份、迁移与数据保留

先对生产业务路径临时停写，优雅停止7个API／任务服务，确认无待执行业务及听读任务后执行一致性备份。数据库和原运行配置在服务器及本机各保留一份，权限0600；两端SHA-256一致、gzip完整性及SQL完成标记通过，原56张表（含Alembic版本表）均在备份中。确认本机副本后才执行迁移；未做恢复演练。

- 服务器目录：`/root/juya-rebuild/ci-images/integration08-production-20261109/backups/`
- 本机目录：`/Users/lubi/Desktop/juya/.private/integration08-production-20261109/backups/`
- 数据库：`juya_production-before-0026.sql.gz`，43,955,492字节；SHA-256 `de27aec5b58654bb01f46106e9a0a9b2321ca84912774f8c270e6115ce9678c1`。
- 配置：`production-runtime-config.tar.gz`，2,672字节；SHA-256 `faa20bce55119b94c51f9d72195bbdd4d0f8ea1c36b698a9ddbc1558cf0c3a65`。

生产库由 **0025→0026，contract仍为3**。0026新增笔记版本表及可空字段；迁移后、服务发布后、公网验证后三次比较，**55张原业务表全部原字段、行数及逐行数据摘要一致**。新增笔记表为空，新增可空字段均为空；没有用测试数据填充生产，没有修改免费名单、账号、授权或学习结果，没有降级／恢复数据库。

临时维护配置已移除，Nginx配置逐字节恢复原状，私有维护探测令牌已删除。

## 公网游客验收

恢复正常流量后，从本机直接发起普通HTTPS请求，无登录Cookie、无维护放行头，结果如下：

| 检查 | 结果 |
| --- | --- |
| 双API `/health/ready` | 200 |
| `/api/mini/v1/listening/home` | 200；统计、授权和继续学习为空 |
| `/api/mini/v1/cards?limit=2` | 200；游客个人state为空 |
| `/api/mini/v1/cards?has_study_note=true&limit=2` | 200；当前生产无已发布笔记，正常空列表 |
| `/api/mini/v1/listening/articles?limit=2` | 200；正常返回列表 |
| `/api/mini/v1/me/statistics` | 401；个人数据仍要求登录 |
| mini域名的admin会话路径 | 404；角色隔离保持 |
| 无效Bearer访问游客首页 | 401；无效身份不会静默降为游客 |

生产现有词汇10条、听读481条，首页3个分类，均为既有生产内容。未创建验收账号或写入学习数据。无密钥机器回执见[JSON](integration08-production-release-20261109.json)。

本轮只完成后端和公网接口验收，未新增微信真机扫码验收。已有生产小程序 **1.0.2／102** 可继续使用；本轮没有重复打包／上传，体验版仍由用户手动切换。
