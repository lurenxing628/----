# APS Windsurf 配置总览

本目录按 `rule -> skill -> workflow` 三层承接 APS 的 Cursor 资产：`rule` 负责长期约束，`skill` 负责方法与资源入口，`workflow` 负责对话触发入口；为保证运行时可见性，`.cursor/rules` 与 `.cursor/skills` 已镜像到本目录。

## 目录分层

- `rules/README.md`
  - 承接 `.cursor/rules` 的 6 条项目规则
- `skills/README.md`
  - 承接 `.cursor/skills` 的 10 个技能索引与资源位置
- `workflows/README.md`
  - 11 个 Windsurf workflow 的使用导航，其中 10 个对应 cursor skill，`bug-hunt` 为新增补充

## 怎么用

- **先看 rule**
  - 当你准备改代码、改模板、改 schema、改提交流程时，先看对应规则
- **再看 skill**
  - 当你要做“架构审计 / 深度审查 / 漂移检测 / 全量自测 / Win7 打包”等专项工作时，先看 skill 索引，确认是否已有脚本、参考资料和输出口径
- **最后走 workflow**
  - 当你已经确定要执行哪套流程，或者要让助手在对话里直接按流程推进时，使用 `workflows/`

## 承接原则

- 不机械复制 Cursor 原文，优先保留结构化入口与源文件链接
- `.windsurf/rules/*.mdc` 与 `.windsurf/skills/**` 是运行时优先入口
- `.cursor/rules` 与 `.cursor/skills` 仍保留为上游来源，后续同步时以镜像更新为主
- workflow 中涉及脚本与说明时，优先引用 `.windsurf/skills/` 下的本地副本
- 后续如需进一步收敛，只考虑“单一来源 + 自动同步”，不再保留仅索引不落地的状态

## 当前映射结论

- `rules`：6 条 cursor rule 已在 `rules/README.md` 建立承接索引
- `skills`：10 个 cursor skill 已镜像到 `skills/`，并在 `skills/README.md` 建立到 workflow 的映射
- `workflows`：保留现有 11 个入口，其中 `bug-hunt` 是 Windsurf 原生补充项
