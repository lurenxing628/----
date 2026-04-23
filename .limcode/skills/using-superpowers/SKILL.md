---
name: using-superpowers
description: >
  会话总控技能：在任何回复、澄清问题或动手之前，先判断是否需要调用其他技能。
  适用于所有会话起点，以及用户要求“按 superpowers 的方式协作”的场景。
---

# 在 limcode 中使用 superpowers

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

如果你觉得某个技能**哪怕只有 1% 的可能适用**，你都必须先调用它，然后才能做任何回复或动作。

- 这条规则适用于：
  - 正式回答
  - 澄清问题
  - 搜代码
  - 看文件
  - 改文件
  - 跑命令
  - 写 design / plan / review
- “我先问一句再决定”也不行。
- “我先看两眼代码再决定”也不行。
- “这事太简单了，不需要技能”也不行。

**只要技能适用，你就没有选择权，必须先用。**

## 指令优先级

当多条规则冲突时，按下面顺序执行：

1. **用户明确要求** —— 最高优先级
2. **技能规则** —— 覆盖默认习惯
3. **默认系统行为** —— 最低优先级

如果用户明确说“不用测试先行”或“不要写 design / plan”，按用户要求执行，但要明确说明这会偏离标准工作流。

## 在 limcode 中如何取用技能

优先顺序如下：

1. **优先走 limcode 的技能调用入口**。
2. 如果当前运行接口还没有把目标技能注册进专用技能入口，就**直接读取对应文件**：
   - `.limcode/skills/<技能名>/SKILL.md`
3. **不要凭记忆执行技能。** 技能会演进；每次都以当前文件内容为准。

## 标准执行顺序

收到任何任务后，按这个顺序判断：

1. **这是不是要先走流程型技能？**
   - 新功能 / 行为变更 → `brainstorming`
   - BUG / 测试失败 / 异常行为 → `systematic-debugging`
2. **设计是否已经批准？**
   - 没批准 → 不能进入写代码
   - 已批准 → 进入 `writing-plans`
3. **是否已经有 plan？**
   - 有，并且当前环境适合子代理协作 → `subagent-driven-development`
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

## 红旗信号

出现下面这些想法时，说明你在给自己找借口，必须停下并先查技能：

| 借口 | 真实情况 |
|---|---|
| “这只是个小问题” | 小问题一样需要方法。 |
| “我先问一句再说” | 澄清问题前也要先判断技能。 |
| “我先扫一眼代码” | 怎么扫、扫到哪一步，本来就该由技能决定。 |
| “我记得这个技能内容” | 技能会变化，不能靠记忆。 |
| “先做这一小步不影响” | 失控就是从“先做一点点”开始的。 |
| “我知道这是什么意思” | 知道概念 ≠ 真的按技能执行。 |
| “先修了再补测试” | 这是典型反模式。 |
| “先出补丁，后面再 review” | 应该先按流程验证，再推进。 |

## 与现有项目技能的关系

本技能是**总控入口**，不是替代现有项目技能。

- `feature-design`：比 `brainstorming` 更强调三轮对抗式设计，适合复杂功能
- `deep-investigate`：比 `systematic-debugging` 更强调独立验证，适合复杂 BUG
- `aps-deep-review`：比 `requesting-code-review` 更重，适合跨层、大改动
- `aps-post-change-check`：实现后的快检收口
- `aps-dev-doc-backfill`：文档回填
- `git-commit-safe-workflow`：提交安全流程

**原则**：先用通用 superpowers 流程；当任务明显更适合项目专用技能时，升级到项目专用技能。

## 最终要求

**先判断有没有技能，再回复。**

如果一个技能适用，而你没有先调用它，那么后续所有动作都算偏离流程。