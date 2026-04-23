# .limcode 迁移说明

本目录已从 `.cursor/` 迁移出当前仓库里**通用且仍有价值**的项目协作资产，便于后续统一放在 `.limcode/` 下维护。

## 当前状态（重要）

`.limcode/` 现已作为当前项目的事实源，按职责拆成四层：

- 技能：`.limcode/skills/`
- 规则：`.limcode/rules/`
- 原生子代理模板与安装口径：`.limcode/subagents/`
- 角色正文源文件：`.limcode/agents/`

其中需要特别区分：

- `.limcode/subagents/` 对应 **LimCode 原生子代理** 的项目模板与注入口径
- `.limcode/agents/` 保存的是**角色正文源文件**，不是 LimCode 自动扫描的原生注册目录

`.cursor/` 继续保留，但仅作为**旧宿主兼容层**，不再维护第二份完整正文。若 `.cursor` 与 `.limcode` 内容冲突，一律以 `.limcode` 为准。

## 已迁移

- `rules/`：架构不变量、变更范围协议、代码质量门禁、Git 提交门禁、接口设计模板
- `agents/`：角色正文源文件与回退提示词来源
- `subagents/`：LimCode 原生子代理模板、安装说明与后续扩展口径
- `hooks/`：复杂度门禁脚本
- `skills/`：全部 APS 项目技能文档与脚本
- `contracts/`：冻结契约与 ownership matrix
- `editor/cursor/`：Cursor 私有配置快照（仅作兼容参考，不作为 `.cursor/` 的活动配置目录）

新增：

- `skills/README.md`：技能总索引
- `rules/00-skill-bootstrap.mdc`：会话级技能引导自动注入（增强层，不是唯一依赖）
- `subagents/README.md`：LimCode 原生子代理说明
- `subagents/limcode-subagents.template.jsonc`：项目级子代理配置模板

## 迁移口径

- 为避免破坏现有 Cursor 工作流，本次采用**复制迁移**，未删除原 `.cursor/` 内容。
- 已对迁移文件中的内部路径引用做批量改写：`.cursor` → `.limcode`。
- 现有 `.limcode/plans/` 等内容保持不变。
- 后续若提到“原生子代理”，默认指 LimCode 的 `limcode.toolsConfig.subagents`；若提到“角色正文源文件”，默认指 `.limcode/agents/*.md`。

## 宿主层注入

当前项目优先通过以下两层完成会话级自动注入：

- 根目录 `AGENTS.md`
- `.limcode/rules/00-skill-bootstrap.mdc`

两者共同约定：先进入 `using-superpowers`，再按 `.limcode/skills/` 的技能体系分流。

如果宿主**不会自动加载** `.limcode/rules/00-skill-bootstrap.mdc`，仍以根目录 `AGENTS.md` + `.limcode/skills/using-superpowers/SKILL.md` 作为首要兜底起步路径；这不会把 `.cursor/` 重新升回事实源，只会让规则目录退回到增强层角色。

换句话说：`.limcode/rules/` 自动生效更好，但不是这套技能体系成立的唯一前提。

## 关于 LimCode 原生子代理

根据 LimCode 源码，原生子代理不是从 `.limcode/agents/` 自动扫描，而是通过：

- `subagents` 工具
- `SubAgentRegistry`
- `limcode.toolsConfig.subagents`

共同驱动。

因此项目级真正可落的原生注入位置是：

- `.vscode/settings.json`
- 或用户全局 VS Code 设置中的 `limcode.toolsConfig.subagents`

仓库中对应的模板与说明见：

- `.limcode/subagents/README.md`
- `.limcode/subagents/limcode-subagents.template.jsonc`

## 关于编辑器配置

以下两项仍然属于编辑器/运行环境相关配置，但考虑到你要求“把有用的都搬到 limcode 里”，这里额外保留一份快照：

- `.limcode/editor/cursor/settings.json`
- `.limcode/editor/cursor/mcp.json`

说明：
- 它们是**归档/参考副本**，不是 Cursor 自动生效位置。
- 真正让 Cursor 生效的仍然是原始 `.cursor/settings.json` 与 `.cursor/mcp.json`。
