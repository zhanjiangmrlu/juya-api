# 修订17 MacBook增量接续交接

交接日期：2026-10-28（北京时间）。用户明确要求提交、推送各仓库远程 **`test`**，在另一台MacBook继续。**MacBook上的四个项目此前都已运行，本次是在已有环境上增量接续。** 当前仍只使用本地数据库；推送源码不包含部署或远程迁移授权。

## 用户最新决定

- 保留Mac已有项目目录、运行配置、本地数据库和媒体、加密/lookup密钥、管理员与业务数据。
- 使用已有工具、容器和账号；按锁文件同步所需依赖，不重新初始化环境、建空库或创建管理员。
- 本次完整需求文档由用户另行同步到Mac，以用户同步的当前开发版为真源，不在Git重复存整份需求副本。版本和原文件SHA-256见[需求引用信息](docs/handoff/revision17/requirement-reference.json)。
- 本轮主要功能代码及R1—R7、契约UTF-8、S1批次更新补项已完成；真实云、设备及完整业务验收未完成。此前95%开发/85%可验收为工程估算，不是276条通过率。

## 四个现有仓库怎样更新

| 仓库 | 目标分支 | 本轮变化 |
| --- | --- | --- |
| `zhanjiangmrlu/juya-api` | `test` | 听读领域/接口/任务、0020—0022迁移、契约、测试及完整交接记录 |
| `zhanjiangmrlu/juya-admin` | `test` | 听读管理、导入恢复/更新、统计和复用播放器 |
| `zhanjiangmrlu/juya-miniapp` | `test` | 三Tab、主题听读、双类记录/收藏、进度与高亮 |
| `zhanjiangmrlu/juya-cli` | `test` | 本轮无代码改动，保留现有发布工具 |

分别进入Mac**已有的四个仓库目录**，先看`git status --short --branch`和`git log -1`。如有未提交修改，先自行提交/暂存保存；不要reset、清目录或强行覆盖。确认工作区已妥善保存后：

```zsh
git fetch origin
git switch test
git pull --ff-only origin test
```

如果不能快进或存在冲突，先检查双方提交，保留Mac已有工作；不要force pull/push。CLI没有本轮新提交，正常拉取其现有test即可。

两个前端与API必须一起更新，避免新客户端配旧契约。[本次配套版本](docs/handoff/revision17/repository-set.json)记录前端及CLI提交；API以包含该清单的test提交为准。依赖仍为Python3.13.x、Node22.22以上且小于23、pnpm11.25.0，继续使用Mac现有安装。按锁文件刷新依赖可复用现有缓存：API `uv sync --frozen`，前端各`pnpm install --frozen-lockfile`。不要升级依赖或锁文件。FFmpeg/FFprobe继续沿用原Mac路径。

## 需求、设计与实施证据

用户将同步`句芽英语-开发需求交接版-当前开发版.md`：V1.5整合04增补02、CHG-0027、修订17增补02、T01—T276。原Windows工作区约定它在API仓库相对`../../docs/需求文档/`；Mac实际路径以用户同步位置为准。若原文件哈希不同，先核对版本和业务变更，不能拿旧文档覆盖用户的新需求。

- [实施与验收决定](docs/handoff/revision17/source/开发方案/修订17-实施与验收.md)、[后端契约](docs/handoff/revision17/source/开发方案/修订17-后端契约.md)。
- [本地交付说明](docs/handoff/revision17/source/开发方案/修订17-本地交付说明.md)、[审查修复报告](docs/handoff/revision17/source/开发方案/修订17-审查修复报告.md)、[最终复审](docs/handoff/revision17/source/开发方案/修订17-修复复审.md)。
- [276条追踪](docs/handoff/revision17/source/开发方案/修订17-验收追踪.json)、[9张实际运行截图](docs/handoff/revision17/source/开发方案/验收截图/修订17)。
- Figma：[当前设计导航](https://www.figma.com/design/yVnE9TCSoRS5sv4vAuxsBX/Juya?node-id=48-5107)、[逐字/暂停状态](https://www.figma.com/design/yVnE9TCSoRS5sv4vAuxsBX/Juya?node-id=64-5079)、[53个具体画板](docs/handoff/revision17/source/开发方案/修订17-设计验收清单.md)。

`source`中的报告是Windows实施阶段冻结证据；“未提交/未推送”、Windows绝对路径和`.private`日志是当时状态，不是Mac当前状态。报告中的私密runner不随Git同步。后续在这套仓库内交接记录上继续登记新验证和决定，不重建多份方案。

## Mac本地库只做增量迁移

本次代码head为**0022**：0020新增13张听读表，0021隔离未发布主题改动，0022增加分类英文名和主题简介；S1无新迁移。Mac当前版本以实际库为准。

1. 核对Mac现有API配置确实连接本地库。分支名test不意味着使用远程测试数据库；本地数据库名和端口沿用Mac原配置，不改成Windows的13306/juya_local示例。
2. 先暂停本地API、旧worker和dispatcher写入，使用Mac已有备份方式备份**当前本地库**并确认备份可恢复，同时保留原媒体和加密配置。不要拿Windows较早0013/0020备份覆盖Mac现有数据。
3. 从API仓库执行下列片段：使用现有Settings读取配置，验证应用和迁移均指向同一个本地库，再显示当前版本并升级。不要运行downgrade、drop/create_all或测试清表夹具。

```zsh
uv run python - <<'PY'
import os
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from juya_api.config import Settings

settings = Settings()
application = make_url(settings.database_url)
migration_url = os.environ.get('JUYA_MIGRATION_DATABASE_URL') or settings.database_url
migration = make_url(migration_url)
local_hosts = {'127.0.0.1', 'localhost', '::1'}
assert settings.environment == 'local', 'Inspect the existing local environment configuration first'
assert application.host in local_hosts and migration.host in local_hosts
assert application.drivername.startswith('mysql') and migration.drivername.startswith('mysql')
assert application.database and application.database not in {'juya_verify', 'mysql', 'sys', 'information_schema', 'performance_schema'}, 'Use the existing business database'
normalize_host = lambda host: '127.0.0.1' if host == 'localhost' else host
assert (normalize_host(application.host), application.port or 3306, application.database) == (normalize_host(migration.host), migration.port or 3306, migration.database), 'Application and migration must target the same local database'
os.environ['JUYA_DATABASE_URL'] = settings.database_url
config = Config('alembic.ini')
command.current(config)
command.upgrade(config, 'head')
PY
```

`migrations/env.py`不自行载入.env，所以这里先调用Settings再传给Alembic。若你的原环境通过本地容器网关而不是loopback访问MySQL，先核对确实是Mac本机数据库，再按实际本地地址调整校验；不要直接删除校验连接远程。若现有schema不属于当前test迁移历史，先调查分支和版本，不强制降级。

本地HTTP仍需`JUYA_COOKIE_SECURE=false`；`JUYA_ALLOWED_ORIGINS`应包含Mac实际后台来源。现有密钥不要重生成。若需使用当前统一授权配置入口，核对本地`JUYA_LEARNING_ACCESS_ACTIVATION_READY=true`，不更改任何远程开关。两API和worker沿用同一配置、相同实际媒体目录；`JUYA_STORAGE_BACKEND=local`用于本轮本地素材。

## 重启已有进程及新增听读worker

本机端口沿用原约定（如Mac原来不同，使用原配置并同步前端代理）；下列为代码默认本地端口，各进程独立终端，从同一个API仓库目录运行：

```zsh
uv run uvicorn juya_api.admin:create_app --factory --host 127.0.0.1 --port 8001 --no-access-log
```

```zsh
uv run uvicorn juya_api.mini:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log
```

旧场景异步处理沿用原角色worker/dispatcher配置，实际入口仍为`juya_api.worker_main --pool solo`及`juya_api.dispatch`（角色`JUYA_WORKER_ROLE=admin|mini`）。**本次增加的独立听读worker不能省略，也不能由旧worker替代：**

```zsh
JUYA_ASR_SECRET_ID='' JUYA_ASR_SECRET_KEY='' uv run python -m juya_api.listening_worker
```

上例显式关闭云ASR。没有权限/配置时时间轴失败并正常听读降级；真实云验收时再明确接通。原MySQL、Redis、媒体及管理员继续使用，不初始化新账号。重启后检查两角色`/health/ready`为HTTP200且`environment=local`，再用原本地管理员登录。

## 前端与微信工具接续

后台在已有`juya-admin`目录运行：

```zsh
VITE_API_BASE_URL='' VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:8001 pnpm dev
```

默认`http://127.0.0.1:5173`。当前听读分类/主题、两种排序、免费M、草稿/发布、导入恢复/更新、删除和统计均使用真实本地API。不要为了预览而自动重置已有免费配置或发布内容。

小程序H5在已有`juya-miniapp`目录运行：

```zsh
VITE_API_BASE_URL='' VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:8002 VITE_STATIC_ASSET_BASE_URL='' VITE_REMOTE_FONTS=false pnpm dev:h5
```

默认`http://127.0.0.1:5174`。微信开发者工具包另开终端构建：

```zsh
VITE_API_BASE_URL=http://127.0.0.1:8002 VITE_STATIC_ASSET_BASE_URL='' VITE_REMOTE_FONTS=false pnpm build:mp-weixin:test
```

导入或重新打开`dist/build/mp-weixin`，沿用Mac原AppID和工具配置。H5空API前缀不能用于原生请求；版本化.env中远程API地址不能当成本地地址。127.0.0.1仅适用于Mac本机工具，手机真机按现有可访问地址/合法域名配置。源码拉取不会迁移Windows合成身份或登录Token，真实微信身份仍须实际验证。

## 提交前验证与后续待办

本次新鲜检查见[推送前验证记录](docs/handoff/revision17/pre-push-verification.md)：API完整SQLite **471通过/32跳过/15既有Windows平台失败**；后台完整**188**，小程序完整**383**，静态检查和构建通过。旧完整460/31/15、S1专项50/4、MySQL分批及浏览器均按各自范围记录，不能相加。所有Mac命令按真实入口核对，但这次未在Mac实跑，不能据此推断Mac平台检查已绿。

接续时优先：

1. 保存Mac现有工作，四仓更新test；备份并增量迁移原本地库，重启双API和独立听读worker，核对原数据保留和新功能可用。
2. 先复验后台新建/导入/更新原文章：选择目标和revision、核对差异、确认才更新原草稿；原发布版、收藏完成历史保持，同资料及同媒体不同上传ID应跳过。
3. 接通有授权词库/单词TTS。未配置词库时通用词典真实返回dictionary_unavailable，不可当成已接入。
4. 核对腾讯ASR权限。Windows真实TTS成功，但ASR返回AuthFailure.UnauthorizedOperation，真实录音时间轴和同步未验；开通后验证独立持久任务、词偏移、尾迹与暂停效果。
5. 微信真实身份/真机、图片手势、到期权限、长队列来源、系统回收恢复，再按用户同步需求的276条及53画板登记验收和必要修正。

API常规检查为`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy src`及`uv run pytest -q`。普通测试默认SQLite；真实MySQL只能使用专用**juya_verify**，夹具会清库，Redis用独立DB15。不得把测试URL指向Mac原业务库。两前端各`pnpm check`，后台`pnpm test`/`pnpm build`，Mini `pnpm test --maxWorkers=2`/H5/上述本地微信构建。

契约仍由API `uv run python scripts/export-openapi.py`导出UTF-8/LF，复制admin/mini JSON到对应前端，再各`pnpm generate:api`；不要手改生成类型。推送test会触发API现有CI/打包，配置没有自动部署步骤；两个前端main-only质量工作流不会因push test运行。不要预先声称CI通过。

Git本次不包含Windows数据库、媒体、账号、.env、.private、Token或依赖缓存；Mac继续使用自己已有的对应资料。不要复制Windows虚拟环境、缓存或旧密钥覆盖Mac。后续先读仓库AGENTS、本文件、用户同步的需求及最终复审，不重做已完成模块，也不把源码推送视为部署授权。
