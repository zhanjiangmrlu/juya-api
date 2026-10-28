# 2026-10-28 test分支交接提交前验证

目的：按用户新增授权保存、推送当前开发成果，供MacBook继续。它是开发进度交接，不是“全部验收完成”的声明。目标分支明确为各仓库`test`；不部署、不连接远程测试/生产库。

## 本次重新运行的检查

| 仓库 | 命令/范围 | 实际结果 |
| --- | --- | --- |
| API | 完整SQLite `python -m pytest -q`，非MySQL wrapper，临时隔离库＋已有FFmpeg | **471 passed / 32 skipped / 15 failed，342.30秒**；完整执行结束，exit1，未中断 |
| API | `ruff check .`、`ruff format --check .`、`mypy src/juya_api` | exit0；格式232文件、类型75源码 |
| 后台 | `pnpm check`、`pnpm test`、`pnpm build` | 全部exit0；**48文件188 passed，53.27秒** |
| 小程序 | `pnpm check`、`pnpm test --maxWorkers=2` | exit0；**80文件383 passed，40.73秒** |
| 小程序 | H5构建；进程级指定本地8002、空静态源、远程字体false的MP:test构建 | 均exit0；最终platform.js实际包含127.0.0.1:8002，无测试/生产API；18页面/三Tab、主包1018319B，20%估算1221983B、余875169B |
| 三个业务仓库 | `git diff --check` | exit0；API仅有Git autocrlf将来可能转换LF/CRLF的提示，不是契约编码失败 |

API15个失败标识已逐项与上一轮`revision17-review-full-sqlite.log`比较，集合完全相同，新增/移除均为空：Windows ZIP反斜杠测试造包转换1项、POSIX目录权限1项、Linux fcntl导入12项、`/proc/meminfo`路径1项。没有修改断言、隐藏失败或顺手做跨平台重构。32项跳过为真实MySQL/Redis限定测试，包括本补项新增MySQL并发项，不计通过。

对应私密本地日志（**不入Git，Mac不可直接读取**）：API`.private/revision17-handoff-{pytest,ruff,format,mypy,diff-check}.log`；前端各`node_modules/.cache/revision17-handoff-*.log`。本文件保存本次实际命令结算，不伪造Mac执行结果。API完整失败名称可对照[原实施报告](source/开发方案/修订17-后端实施报告.md)及[复审边界](source/开发方案/修订17-修复复审.md)。

## 本轮与历史验证的关系

- 之前的后端完整460/31/15、S1专项50/4、真实本地MySQL分批64及5项、S1的10+1项均是各自范围的实际证据，不能与本次471或相互简单相加。本次没有重跑完整MySQL套件。
- 此次后台188项已包含最后可读差异展示；之前187完整＋后续3项是历史阶段记录，不替代本次完整结果。
- 本地真实HTTP10项、受限图200/403/401、浏览器未知创建恢复、批次更新已有文章及对应截图见冻结报告；本次提交前没有据此声称真实微信身份或ASR通过。
- 实施/复审文档、追踪及9张截图归档入API仓库；完整需求由用户同步，仓库保存版本引用与SHA-256；常见秘密/私钥模式、暂存文件边界及跨机引用在最终stage后另做只读核对。凭据、`.env`、DB备份、媒体数据、会话和依赖缓存不入Git。

## Mac上仍须执行

Mac启动步骤按根`HANDOFF.md`的真实代码入口/Settings编写，本轮未在Mac运行。Mac上的`fcntl`是否可用、POSIX权限、监控路径、微信开发者工具及媒体行为都需实际验证；不得把Windows的平台归因自动转换为Mac通过。

真实腾讯ASR权限仍返回过`AuthFailure.UnauthorizedOperation`；真实录音词轴与同步、词库/单词TTS、微信真实身份/设备、53画板及276条完整业务验收仍未完成。此次用户要求推送当前开发成果，不以这些已登记边界虚报全部完成，也不把源码推送视为应用部署。
