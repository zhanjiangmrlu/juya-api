# 第二批：正文查词与原词发音接口

2026-10-22，整合03／修订15，保持 schema 最低版本0014。本批无迁移。仅新增小程序角色接口；管理员预览不调用这些接口。

## 正文引用

所有查词与发音请求使用同一对象：

```json
{"version_id":"当前发布版本ID","word":"went","line_id":"当前对话行ID","start":3,"end":7}
```

start／end为JavaScript UTF-16左闭右开位置，必须精确等于一条当前已发布英文对话中的完整词项；word大小写及撇号保留原文。例如`😀 went`中went为3—7。服务端独立扫描，拒绝纯标点、部分词、跨词、伪造行、失效版本及下线卡。POST不接受text等额外参数。

与小程序共用的正则（JS gi；Python re.I | re.ASCII）：

```text
(?:[A-Za-z]+\.){2,}|(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)\.|[A-Za-z]+(?:['’\-][A-Za-z]+)*
```

若匹配紧邻ASCII `[A-Za-z0-9_]`，该项无效，避免从abc123或abc_foo选取局部。U.S.／e.g.／Ph.D.／Dr.包括句点；today.只选today；don't／Let’s／take-away为完整词。Python须显式限定ASCII大小写，避免将JS不识别的İ／ı／ſ／K作为英文词项。

## 接口与结果

- GET `/api/mini/v1/cards/{id}/dictionary`：以上字段作为查询参数；本人有效会话必需。仅查询，不创建发音任务或学习成绩。
- POST `/api/mini/v1/cards/{id}/dictionary/pronunciation`：以上对象作为JSON，另需`Idempotency-Key`，复用原发音任务、缓存、预算、冷却和重试。
- GET 同一发音路径：以上字段作为查询参数，轮询既有SpeechState；GET不生成云任务。

查词结果：

```json
{"word":"went","lemma":"go","phonetic":"","source":"dictionary","definitions":[{"part_of_speech":"v.","meaning":"去"}],"speech_text":"went","provider":"操作方配置的数据来源"}
```

source为context／dictionary／missing。仅唯一且精确匹配line_id／start／end／quote的非空已确认词义使用context；不会按同拼写猜配，也不会使用另一处释义。context的provider为context。无已确认释义才使用词典；真实查无词条返回missing与空definitions。词典未配置、不可读取或数据无效返回503 `dictionary_unavailable`；可用的本篇释义继续返回，不被可选词典失败阻断。

lemma仅来自授权数据明确forms映射。原词缺IPA时返回空字符串，不以原形IPA替代。speech_text通常为点击原词；只有唯一精确来源的词汇英文与点击拼写一致时，才可使用管理员明确确认的pronunciation_text（例如read→red），并把点击拼写和实际朗读文字一起纳入缓存。go来源对应went时不会用go朗读或IPA替代went。不可确认的发音返回空speech_text，发音接口明确失败。

SpeechState沿用`state/job_id/error_code/url/retry_after`。ready时签发5分钟用途独立的加密grant：`/api/mini/v1/dictionary-pronunciation/{credential}`。每次音频GET／HEAD重新检查原会话仍有效、当前卡片和版本、完整词项引用、实际读音缓存和资源状态。原生音频不能附请求头时可使用grant；若带Authorization，必须与grant所属会话相符。退出、过期、停用及换版撤销访问。现有词汇grant不能当作正文grant使用。

## 本地数据配置

设置`JUYA_DICTIONARY_PATH`为操作方提供的本地JSON路径。默认无数据，不捆绑测试词汇，不采购服务。工厂支持注入实现`lookup(word)->LexicalResult`的网关，测试替身不作为真实覆盖证明。

JSON结构：

```json
{
  "provider":"实际数据来源",
  "license":"经操作方核对的授权说明或标识",
  "entries":{
    "go":{"phonetic":"/ɡəʊ/","definitions":[{"part_of_speech":"v.","meaning":"去"}]}
  },
  "forms":{"went":"go"}
}
```

此处仅为结构示例，不构成生产词典。每个词条必须有至少一条非空meaning；phonetic与part_of_speech可省略为空。forms可省略；只接受明确映射，目标必须存在于entries。索引大小写不敏感，重复大小写索引拒绝；无规则变形猜测。文件最大64MiB。文件签名变化时原子校验并重建大小写索引，平时单词查询使用缓存索引，不逐次扫描词库；新文件非法时明确失败，不继续冒充旧词库有效。

provider／license为操作方声明的元信息校验，不代替法律授权核对。实际数据来源、覆盖率、词形与原词IPA覆盖，以及腾讯云实际读音／双端播放仍需独立真实验收。
