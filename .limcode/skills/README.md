# `.limcode/skills` 总索引

本目录是当前项目技能体系的**唯一事实源**。

- `using-superpowers`：会话总控入口
- `brainstorming`：通用 design 流程
- `feature-design`：复杂功能的三轮对抗式设计
- `writing-plans`：把 design 拆成可执行 plan
- `systematic-debugging`：通用根因排查
- `deep-investigate`：复杂问题的三轮对抗式排查
- `test-driven-development`：测试先行
- `requesting-code-review`：任务级代码审查
- `subagent-driven-development`：子代理驱动实施
- `executing-plans`：当前会话按 plan 实施
- `using-git-worktrees`：隔离工作区
- `finishing-a-development-branch`：开发收尾
- `aps-*`：APS 项目专项技能

## 落盘约定

- design：`.limcode/design/`
- plan：`.limcode/plans/`
- review：`.limcode/review/`
- 审计取舍报告：`audit/YYYY-MM/`

## 兼容说明

- `.limcode/` 是唯一事实源。
- `.limcode/rules/` 中的会话引导规则属于**增强层**，不是这套技能体系成立的唯一依赖。
- `.cursor/` 只保留兼容入口，供仍扫描 `.cursor` 的旧宿主使用。
- 如 `.cursor` 与 `.limcode` 内容冲突，一律以 `.limcode` 为准。

如果当前宿主**不会自动加载** `.limcode/rules/00-skill-bootstrap.mdc`，仍按下面口径执行：

- 以根目录 `AGENTS.md` + `.limcode/skills/using-superpowers/SKILL.md` 作为首要起步路径。
- 仍先进入 `using-superpowers`，再按 `.limcode/skills/` 技能体系分流。
- 如果目标技能尚未注册到专用技能入口，就直接读取 `.limcode/skills/<技能名>/SKILL.md`。
- 这不会把 `.cursor/` 重新升回事实源；`.cursor/` 仍只承担旧宿主兼容发现入口。

换句话说：

- `.limcode/rules/` 能自动生效更好。
- 即使它不自动生效，`.limcode` 技能体系也仍然成立。

## 配套子代理

- LimCode 原生子代理模板与安装口径见：`.limcode/subagents/README.md`
- 角色正文源文件见：`.limcode/agents/README.md`

## 子代理兼容规则

见：`.limcode/skills/_shared/subagent-compat.md`
