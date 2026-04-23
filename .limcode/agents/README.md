# `.limcode/agents` 角色正文源文件索引

本目录保存的是当前项目的**角色正文源文件**。

它们的职责是：

1. 作为 LimCode 原生子代理 `systemPrompt` 的项目维护来源
2. 在宿主尚未注册原生子代理时，作为宿主通用子代理或主代理降级执行时的完整提示词正文
3. 作为 `.cursor/agents/` 兼容入口真正指向的正文来源

**重要：本目录不是 LimCode 会自动扫描注册的原生子代理目录。**

真正的 LimCode 原生子代理注册入口是：

- `limcode.toolsConfig.subagents`
- 项目级常见落点：`.vscode/settings.json`
- 项目模板与安装口径见：`.limcode/subagents/README.md`
- 示例模板见：`.limcode/subagents/limcode-subagents.template.jsonc`

## 首版推荐四件套

当前最推荐的首版通用子代理链只包含 4 个角色正文：

1. `plan-implementer.md`：单任务实现
2. `spec-reviewer.md`：第一轮需求符合性审查
3. `code-quality-reviewer.md`：第二轮代码质量审查
4. `code-reviewer.md`：阶段末 / 合并前整体验收

这 4 个已经足够支撑：

- 按 `plan` 逐任务实施
- 每个任务后做两阶段审查
- 阶段末再做一轮整体收口

**在没有真实跑顺这 4 个之前，不要继续扩更多通用子代理。**

## 第二批专项角色

下列文件保留给专项流程，不属于首版通用四件套：

- `deep-investigate-worker.md`：复杂排查的调查角色
- `independent-auditor.md`：独立审计 / 对抗式复核
- `aps_doc_scan.md`：文档扫描与信息提取

## 与 LimCode 原生子代理的关系

建议映射如下：

| 角色正文源文件 | 建议的原生子代理 type | 建议显示名 |
|---|---|---|
| `plan-implementer.md` | `aps-plan-implementer` | `APS 实施子代理` |
| `spec-reviewer.md` | `aps-spec-reviewer` | `APS 符合性审查子代理` |
| `code-quality-reviewer.md` | `aps-code-quality-reviewer` | `APS 质量审查子代理` |
| `code-reviewer.md` | `aps-code-reviewer` | `APS 整体验收子代理` |
| `deep-investigate-worker.md` | `aps-deep-investigate-worker` | `APS 调查子代理` |
| `independent-auditor.md` | `aps-independent-auditor` | `APS 独立审核子代理` |
| `aps_doc_scan.md` | `aps-doc-scan` | `APS 文档扫描子代理` |

## 推荐注入顺序

### 第一优先：LimCode 原生已注册子代理

如果用户已经把模板写入：

- `.vscode/settings.json`
- 或全局 VS Code 设置里的 `limcode.toolsConfig.subagents`

那么执行时应优先直接调用原生子代理。

### 第二优先：宿主通用子代理

如果当前宿主支持通用子代理，但还**没有注册** LimCode 原生子代理：

- 先读取本目录下对应角色正文源文件
- 把角色、硬约束、输入要求、输出格式**完整内联**给宿主通用子代理
- 保持只读语义（如果该角色本应只读）
- 默认继承主模型，不要静默降级到明显更弱的路径

### 第三优先：主代理降级执行

如果既没有 LimCode 原生子代理，也没有宿主通用子代理：

- 明确告诉用户当前限制
- 由主代理按目标角色正文中的清单、边界和输出格式手工执行
- 仍然不能跳过两阶段审查的顺序要求

## 默认调度顺序

在 `subagent-driven-development` 中，默认顺序如下：

1. 主代理读取一次完整 `plan`
2. 主代理把“当前任务全文 + 文件范围 + 验证命令 + design / plan 片段”交给实现角色
3. 实现角色返回结构化结果
4. 若状态可继续，进入符合性审查角色
5. 第一轮通过后，进入质量审查角色
6. 任务全部完成或阶段性完成后，再由整体验收角色做收口

## 与技能体系的关系

- 总控入口：`.limcode/skills/using-superpowers/SKILL.md`
- 调度入口：`.limcode/skills/subagent-driven-development/SKILL.md`
- 原生子代理模板：`.limcode/subagents/README.md`
- 兼容门禁：`.limcode/skills/_shared/subagent-compat.md`

如果这些位置与某个角色正文文件发生冲突：

1. 先以**当前角色正文文件**的角色边界和输出格式为准
2. 再以共享兼容门禁处理宿主回退
3. 再由调度技能决定何时调用该角色

## 最终要求

- `.limcode/agents/` 是角色正文源文件目录，不是 LimCode 自动扫描目录
- `.limcode/subagents/` 是原生子代理模板与安装口径目录
- `.cursor/agents/` 只保留兼容入口，不再维护第二份主定义
- 先把首版四件套跑顺，再考虑扩更多角色
