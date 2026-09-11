---
name: using-superpowers
description: >
  旧 superpowers 风格会话总控技能。自 2026-04-27 起，本仓库默认入口已切换为
  CodeStable；本技能只在用户明确要求旧流程、续作旧 `.limcode` 任务，或排查旧
  流程记录时使用。
---

# 在 limcode 中使用 superpowers

> **迁移状态**：本仓库已经切换到 CodeStable。新任务默认从 `cs` / `cs-onboard`
> / `cs-*` 技能分流，不再默认进入本技能。本文件保留用于旧任务回溯和旧流程兼容。

> **定位**：这是 `obra/superpowers` 的 limcode 适配版总控技能。
> **目标**：把“先判断方法、再行动”的纪律放在所有任务前面，避免直接跳进写代码。

如果你是被上层代理明确派来执行一个**已经边界清晰的单个子任务**的子代理，默认跳过本技能；除非上层明确要求你重新做技能判断。

## 宿主降级路径（没有 `.limcode/rules/` 也照样执行）

如果当前宿主没有自动加载 `.limcode/rules/`，仍按下面规则执行，不得等待额外注入：

- 把根目录 `AGENTS.md` 与本文件一起视为会话起步约束
- 仍以 `.limcode/skills/`、`.limcode/rules/`、`.limcode/subagents/`、`.limcode/agents/` 为事实源；其中 `.limcode/subagents/` 负责 LimCode 原生子代理模板，`.limcode/agents/` 负责角色正文源文件；`.cursor/` 只作兼容发现入口
- 如果技能没有注册进专用技能入口，就直接读取 `.limcode/skills/<技能名>/SKILL.md`
- 只有旧宿主只扫描 `.cursor/` 时，才从 `.cursor` 兼容入口发现技能；实际执行与落盘仍以 `.limcode` 正文为准
- design / plan / review / 审计取舍报告 的落盘约定不因宿主能力差异而改变
- **不要把“规则目录没自动加载”当成跳过技能判断的理由**

## 绝对规则

只有用户明确选择旧流程，或继续已有旧任务确实需要时才读取对应旧技能。普通新任务使用当前项目流程，不因轻微关联而加载所有可能相关技能。

允许先做必要澄清和定向只读检查来判断任务。只加载本轮实际需要的技能，不为微弱关联扩大读取范围。

## 指令优先级

当多条规则冲突时，按下面顺序执行：

1. **平台安全和当前工具约束** —— 技能不得覆盖。
2. **本轮用户明确要求** —— 决定任务目标、范围和是否执行旧流程。
3. **适用项目规则与技能方法** —— 只补充对应范围，历史习惯不覆盖当前要求。

如果用户明确说“不用测试先行”或“不要写 design / plan”，按用户要求执行，但要明确说明这会偏离标准工作流。

## 在 limcode 中如何取用技能

优先顺序如下：

1. **优先走 limcode 的技能调用入口**。
2. 如果当前运行接口还没有把目标技能注册进专用技能入口，就**直接读取对应文件**：
   - `.limcode/skills/<技能名>/SKILL.md`
3. **不要凭记忆执行技能。** 技能会演进；每次都以当前文件内容为准。

## 标准执行顺序

只有本轮明确选择完整旧流程时，按这个顺序判断：

1. **这是不是要先走流程型技能？**
   - 新功能 / 行为变更 → `brainstorming`
   - BUG / 测试失败 / 异常行为 → `systematic-debugging`
2. **设计是否已经批准？**
   - 没批准 → 不能进入写代码
   - 已批准 → 进入 `writing-plans`
3. **是否已经有 plan？**
   - 有，并且用户或适用规则允许委派、当前工具支持子代理协作 → `subagent-driven-development`
   - 有，但当前环境不适合子代理或用户要求当前会话直接执行 → `executing-plans`
4. **进入实现后**
   - 写任何生产代码前 → `test-driven-development`
   - 完成任务或重要里程碑后 → `requesting-code-review`
5. **工作收尾**
   - 全部任务完成 → `finishing-a-development-branch`

## 技能优先级

多个技能都可能适用时，按这个顺序：

1. **流程型技能优先**
   - `brainstorming`
   - `systematic-debugging`
   - `writing-plans`
2. **实现型技能其次**
   - `test-driven-development`
   - `subagent-driven-development`
   - `executing-plans`
3. **校验与收尾技能最后**
   - `requesting-code-review`
   - `finishing-a-development-branch`

## 技能路由表

| 场景 | 必用技能 | 升级 / 补充技能 |
|---|---|---|
| 新功能、需求变更、行为修改 | `brainstorming` | 复杂设计可升级 `feature-design` |
| BUG、失败用例、异常行为 | `systematic-debugging` | 复杂排查可升级 `deep-investigate` |
| design 已批准，需要拆执行步骤 | `writing-plans` | — |
| 已有 plan，要在当前会话逐项执行 | `subagent-driven-development` 或 `executing-plans` | 实现中必须套 `test-driven-development` |
| 实现过程中每个任务 / 重要改动后 | `requesting-code-review` | 大范围改动可升级 `aps-deep-review` |
| 改动后快检 | `aps-post-change-check` | — |
| 文档联动更新 | `aps-dev-doc-backfill` | — |
| 提交流程 | `git-commit-safe-workflow` | — |
| 分支 / 工作树收尾 | `finishing-a-development-branch` | 可与 `using-git-worktrees` 配套 |

## 执行协议

### 1. 先宣布

调用技能后，先明确告诉用户：

> 我正在使用 `<技能名>` 来处理这个任务。

### 2. 如果技能带检查清单

就把清单写成待办，再按顺序执行。不要只“读过”不“执行”。

### 3. 严格遵循技能

- **刚性技能**：不能擅自弱化纪律
  - `systematic-debugging`
  - `test-driven-development`
- **弹性技能**：可以根据上下文调细节，但不能改核心顺序
  - `brainstorming`
  - `writing-plans`
  - `requesting-code-review`
  - `finishing-a-development-branch`

## 执行边界

- 记录与现场不一致时重新核实，不凭历史内容直接执行。
- 已授权的实现连续推进；关键取舍和范围扩大再确认。
- 验证强度按实际风险确定，不虚报完成或绕过适用的测试要求。
- 未选择本旧流程时，不用它要求其他任务追加设计、委派或阶段报告。

## 与现有项目技能的关系

本技能是**总控入口**，不是替代现有项目技能。

- `feature-design`：比 `brainstorming` 更强调三轮对抗式设计，适合复杂功能
- `deep-investigate`：比 `systematic-debugging` 更强调独立验证，适合复杂 BUG
- `aps-deep-review`：比 `requesting-code-review` 更重，适合跨层、大改动
- `aps-post-change-check`：实现后的快检收口
- `aps-dev-doc-backfill`：文档回填
- `git-commit-safe-workflow`：提交安全流程

**原则**：新任务使用当前 CodeStable 入口；旧任务只读取续作需要的旧技能。项目专用约束在对应范围内适用，不叠加两套完整流程。

## 最终要求

只在明确适用时使用本流程；不得把本文件当作所有新任务都必须先读取的入口。
