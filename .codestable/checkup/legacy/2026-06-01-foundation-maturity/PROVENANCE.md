# 历史基线来源与使用限制

本目录是 2026-06-01 首次地基体检的**历史对比样本**，不是当前系统事实。

## 来源

这些文件当时没有进入正式提交，只存在于 Git stash：

- stash merge commit：`cb79bf9577268869c48fcd69f4012a729ab7eb91`
- untracked 文件树：`725cca792aedc8571d8210bdc5b4b41ac83e2800`
- stash 基于：`b08162cd6c1edc1c9ce4f5ab43f0381740457ba8`
- 报告声明的决定考古水位线：`65870e4786f3fea1e45c259e9d209ee6e1598a31`

2026-07-10 重建 Checkup 基线时，从上述 untracked 文件树逐文件恢复：

- `README.md`
- `foundation-maturity-audit.md`
- `decision-log.md`
- `module_findings/*.json`（14 个旧分区结果）

## 使用限制

- 只能用于趋势对比、历史决定追溯和下一轮考古起点。
- 旧报告中的路径、模块数、行数、schema 版本、健康评分和“当前”字样都可能过期。
- `decision-log.md` 没有恢复到 `.codestable/architecture/`，因为它只覆盖到 2026-06-01；把它放回当前架构目录会冒充现状。
- 从旧水位线到 2026-07-01 代码基线还有 332 个提交未逐个考古，完成前不得推进决定水位线。
