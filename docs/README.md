# docs —— 版本文档管理

本目录统一管理仓库的**版本相关文档**：各技能的规格（spec）及其历史版本、重大设计决策记录。

约定：

1. **spec 与技能目录分离**：`resources/skill/<name>/` 只放运行时资产（SKILL.md、scripts、tests、references）；设计与版本演进文档一律放这里。
2. **命名**：`<skill>-spec.md` 为当前生效规格，文件头部的「状态」行标注版本与日期；被新版本取代时，旧内容整体归档为 `<skill>-spec-v<旧版本>.md`，不删改历史文件。
3. **规格即版本**：每个 spec 文件对应一个能力版本（如 cu 2.1、bu 0.1），版本号语义与 SKILL.md/troubleshooting 中引用的版本一致。

## 索引

| 文件 | 内容 | 状态 |
|---|---|---|
| [browser-use-spec.md](browser-use-spec.md) | bu 0.1 规格：浏览器自动化技能（对标 ZCode browser-use 插件 0.4.2） | 草案，未实现 |
| [computer-use-spec.md](computer-use-spec.md) | cu 2.1 规格 + 2.2/2.3/2.4 增补（后台派发、ax state、region-px、open 三段式 + 看门狗 + 前台读数真值化）（从 `resources/skill/computer-use/SPEC.md` 归档） | 已实现（cu 2.4 已交付，e2e 见 §9） |
