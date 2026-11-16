# Vocabulary manual-source review

范围：API 相对 `0655d34`、admin 相对 `623d32d`、mini 相对 `f3821c5` 的当前工作区改动（含未跟踪测试），并核对 API `docs/superpowers/specs/2026-11-16-vocabulary-manual-source-design.md`。只读审阅源码；未重跑整套测试，未修改仓库。核对了当前 listening `selectSentence` 对非 server 模式的重复原句位置修正。

## Strengths

- 共享自动匹配与两种人工来源校验分离，合法未知词形不会再次经过自动词形规则而被清除
- 场景按 UTF-16 校验引用、范围与真实原文；听读独立按 Unicode 码点校验完整原句和选词范围，人工来源绑定词条英文
- 人工同词不同义保留独立条目；旧自动来源通过字段省略保持原形状，未增加数据库迁移
- 后台将待选原句放在独立 pending 状态，避免半成品来源进入严格契约，红色待人工补充提示和人工已确认文案覆盖编辑及汇总
- 新测试覆盖双模块实际保存／预览／发布、伪造和过期来源、emoji 坐标与后台人工操作

## Issues

### Critical

无

### Important

1. **所有格词形绕过既有歧义保护，自动确认无关词义**
   - 位置：`/Users/lubi/.codex/worktrees/chg0043-0045-api/juya-api/src/juya_api/vocabulary_matching.py:277`（与第 314–320 行可靠性判定交互）
   - 新规则先把实际词形 `saw's` / `saw’s` 去为 `saw`，因此可通过 `saw ∈ word_forms("see")` 产生候选；可靠性判定却继续对未去尾的 `saw's` 检查 `AMBIGUOUS`，不再命中已有 `saw` 保护
   - 真实影响：词条 `see / 看见`、正文 `The saw's blade is sharp.` 会自动确认并高亮名词“锯子的”，没有人工确认或来源提示即可通过来源规则。相同输入使用 `saw` 则正确保持 `source_ambiguous`。此问题同时影响场景及听读，违反不自动误配无关词与保留既有歧义保护的约束
   - 极小复现：只通过 Python `importlib` 加载共享匹配模块，执行 `matching_spans` + `resolve_words`。`saw` 得到 `source=None, source_reason=source_ambiguous`；`saw's` 与 `saw’s` 均得到有效自动来源
   - 建议：在自动可靠性判定中也检查规范化并去所有格后的词形（词条和实际候选两侧），保留已有明确位置、原句证据与合法人工来源的处理；新增双适配器直／弯引号回归，证明 `see` 不会无依据自动认成 `saw's`，且普通 `saw` 名词仍可按既有证据／人工流程确认

### Minor

无

## Declined to judge

- 本轮线上部署、OSS／微信上传及真机效果：本轮范围为本地修复，当前没有这次发布授权或发布改动，不把已有上次发布回执当成本轮验收
- 既有词形表对所有英语词性／语义的全面识别：超出本次有限修复范围；上述 finding 仅针对新增所有格规则破坏已存在的显式歧义保护

## Assessment

**Ready to merge? No — fix the Important issue first.**

人工来源的核心兜底链路及坐标校验符合设计，后台状态和展示改动也保持在需求范围。新增所有格规则存在可复现的无关词自动确认回归，修正并补针对性回归后可重新评估。
