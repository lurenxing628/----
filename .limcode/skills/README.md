# `.limcode/skills` 技能索引

本目录是当前仓库供 LimCode 直接读取的项目级技能目录。

从 2026-07-10 起，目录同时保存：

1. CodeStable 的项目内快照（`cs` / `cs-*`，共 27 个）。
2. 旧 superpowers 风格流程技能。
3. APS 项目专项技能。
4. 子代理与历史实施流程辅助。

## 默认入口

新任务优先走 CodeStable。当前 LimCode 的本地加载顺序是：

1. `.limcode/skills/<技能名>/SKILL.md`
2. `~/.codex/skills/<技能名>/SKILL.md`
3. `~/.agents/skills/<技能名>/SKILL.md`

项目内副本是实体目录，不是软链接；这样仓库可以固定一套经过 APS 适配的执行口径。复制来源、文件数和树哈希记录在 `CS-SNAPSHOT.json`。

## 本机工具解释器边界

CodeStable / LimCode 的维护、检索和体检脚本故意使用本机 Python 3.14，以获得更完整的工具/库支持和更好的本机执行效率；不要为了迁就 APS 运行时而把这些宿主工具降级成 Python 3.8 语法。当前可直接使用 `python` / `python3` / `python3.14`，它们均指向本机 CPython 3.14。

这不改变 APS 产品合同：`core/`、`web/`、`data/`、打包代码、项目测试和最终质量门禁仍须兼容 Python 3.8 与 Win7 x64。宿主工具不得被打进 APS 离线运行包。

### CodeStable 技能组

- 路由/接入：`cs`、`cs-onboard`
- 讨论/规划：`cs-brainstorm`、`cs-roadmap`、`cs-req`、`cs-arch`、`cs-decide`
- 新功能：`cs-feat`、`cs-feat-design`、`cs-feat-ff`、`cs-feat-impl`、`cs-feat-accept`
- 问题修复：`cs-issue`、`cs-issue-report`、`cs-issue-analyze`、`cs-issue-fix`
- 重构/审计：`cs-refactor`、`cs-refactor-ff`、`cs-audit`
- 探索/沉淀/文档：`cs-explore`、`cs-learn`、`cs-trick`、`cs-note`、`cs-guide`、`cs-libdoc`
- APS 专属：`cs-checkup`、`cs-semantic-radar`

`cs-checkup` 已按当前仓库重新验基线，项目副本包含本地 `reference.md`，不能用全局旧版本直接覆盖。

## 事实源边界

技能文件只定义“怎么做”，不取代项目事实源：

- 需求、架构、roadmap、feature、issue、refactor、audit、知识沉淀仍写入 `.codestable/`。
- `.limcode/skills/` 不保存业务现状和单次任务结论。
- `cs-checkup` 的机器基线位于 `.codestable/checkup/`。

## 旧技能仍可使用的场景

- 续作 `.limcode/plans/`、`.limcode/review/`、`.limcode/design/` 历史任务。
- APS 专项深审、门禁快检、文档联动时参考 `aps-*`。
- 子代理兼容与降级执行参考 `_shared/subagent-compat.md`。

新任务不要再默认从 `using-superpowers` 起步。

## 刷新 CodeStable 副本

共享源默认是 `~/.agents/skills/`。刷新前必须先比较差异，不能整组无脑覆盖：

```bash
diff -ru ~/.agents/skills/cs .limcode/skills/cs
# 其他 cs-* 同理
```

特别规则：

- `cs-checkup` 是 APS 本地适配版，保留项目路径、双水位线和 clean HEAD 基线口径。
- `cs-onboard` 包含 `.limcode/skills/cs-onboard/` 本地位置说明。
- 其余技能若与共享源不同，应先确认差异是上游更新还是项目适配，再决定合并。
