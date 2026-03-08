# APS Windsurf Rules 索引

本目录承接 `.cursor/rules` 的项目约束，作为 Windsurf 侧的 rule 层入口；规则正文已镜像到当前目录，`.cursor/rules/` 保留为上游来源，这里给出适用范围与执行摘要，避免只剩 workflow 而丢失项目边界。

## 使用原则

- 遇到 workflow / skill 与 rule 冲突时，以 rule 为准
- 全局规则优先，专项规则按文件类型与操作场景触发
- 需要原始细节时，优先阅读当前目录中的对应 `.mdc` 文件

## 规则清单

| Rule | 来源 | 适用方式 | 重点 |
| --- | --- | --- | --- |
| `architecture-invariants` | `architecture-invariants.mdc` | 全局硬约束 | 分层边界、Schema 协议、ADR |
| `change-scope-protocol` | `change-scope-protocol.mdc` | 全局硬约束 | 影响域声明、联动更新、禁止静默改动 |
| `code-quality-gate` | `code-quality-gate.mdc` | Python 改动时必看 | lint、复杂度、异常/类型/边界 |
| `git-commit-guardrails` | `git-commit-guardrails.mdc` | Git 提交时必看 | UTF-8 提交、门禁、历史重写保护 |
| `interface-patterns` | `interface-patterns.mdc` | Route / Service / Repository / Model 改动时必看 | 分层模板与返回约定 |
| `templates-quality` | `templates-quality.mdc` | HTML / Jinja 模板改动时必看 | 展示边界、安全与表单规范 |

## `architecture-invariants`

- **正文**：`architecture-invariants.mdc`
- **适用**：全局硬约束
- **核心约束**
  - 调用方向遵守 `web/routes`（可调 `web/viewmodels`） -> `core/services` -> `data/repositories` -> 数据库
  - Route 禁止导入 Repository 或直接执行 SQL；ViewModel 只做展示数据整理；Service 只做业务逻辑与事务协调
  - Schema 变更必须走迁移，并检查模板、调用方、文档等联动项
  - 关键技术选型调整前，先补 ADR 或等价决策记录

## `change-scope-protocol`

- **正文**：`change-scope-protocol.mdc`
- **适用**：全局硬约束
- **核心约束**
  - 一次变更只解决一个明确目标，避免顺手改无关问题
  - 改动前先声明影响域，明确会触达哪些模块、接口、文档与数据结构
  - 变更 Route、Schema、Service 返回值、枚举、ScheduleConfig、Excel 模板或用户文案时，必须做联动检查
  - 禁止静默改动：重要行为、返回结构或用户可见内容变化要留痕

## `code-quality-gate`

- **正文**：`code-quality-gate.mdc`
- **适用**：Python 改动时必看
- **核心约束**
  - 控制函数长度、文件大小、嵌套深度与圈复杂度
  - 禁止 `import *`、静默吞异常、无上下文的 `type: ignore` / `noqa`、模块级可变全局状态
  - 公开函数补齐类型注解，业务异常使用 `AppError` 体系
  - 主动覆盖空输入、`None`、解析失败、无结果、边界值等非 Happy-Path 情况

## `git-commit-guardrails`

- **正文**：`git-commit-guardrails.mdc`
- **适用**：Git 提交时必看
- **核心约束**
  - 仅在用户明确要求时执行 `git commit`
  - 提交信息必须中文并说明“为什么改”
  - 在 PowerShell 下统一使用 `UTF-8 文件 + git commit -F`，避免命令行内联中文正文
  - 提交前检查 `git status`、`git diff --cached`、`git log -1`；重写历史前先建备份分支

## `interface-patterns`

- **正文**：`interface-patterns.mdc`
- **适用**：Route / Service / Repository / Model 改动时必看
- **核心约束**
  - Service 内部创建 Repository，外部只传 `conn`；跨 Service 调用复用同一连接
  - Repository 继承 `BaseRepository`，CRUD 命名统一，查询集合为空时返回 `[]` 而不是 `None`
  - Model 保持纯 `@dataclass`，只做 `from_row()` / `to_dict()` 转换
  - Route 页面函数以 `_page` 结尾、数据接口以 `_data` 结尾，通过 `g.db` 创建 Service，JSON API 使用统一响应工具

## `templates-quality`

- **正文**：`templates-quality.mdc`
- **适用**：HTML / Jinja 模板改动时必看
- **核心约束**
  - 模板只负责展示，不做业务逻辑、复杂计算或深层条件判断
  - 禁止对用户输入使用 `| safe`
  - 静态资源统一通过 `url_for('static', ...)` 引用
  - 所有用户可见文案使用中文；修改数据的表单使用 `POST`，敏感操作带确认提示
