# LimCode 原生子代理说明

本目录用于保存**LimCode 原生子代理**的项目级模板与安装口径。

## 先说结论

当前 LimCode 的原生子代理不是从 `.limcode/agents/` 自动扫描出来的。

根据 LimCode 源码，原生子代理由以下几部分共同驱动：

- `subagents` 工具
- `SubAgentRegistry`
- 默认执行器
- 设置项 `limcode.toolsConfig.subagents`

这意味着：

- `.limcode/agents/*.md` 是**角色正文源文件**
- `limcode.toolsConfig.subagents` 才是**原生注册配置**
- 项目级常见落点是 `.vscode/settings.json`

## 这和 LimCode 数据目录有什么区别

LimCode 的数据存储目录（例如自定义 `storagePath` 下的 `skills/`、`conversations/`、`checkpoints/` 等）主要承载：

- 技能目录
- 对话记录
- 检查点
- 差异文件
- 依赖缓存

**它不是原生子代理注册入口。**

原生子代理仍然要写进：

- 工作区 `.vscode/settings.json`
- 或用户全局 VS Code 设置中的 `limcode.toolsConfig.subagents`

## 推荐的首版四件套

建议先只注册这 4 个：

1. `aps-plan-implementer` → `APS 实施子代理`
2. `aps-spec-reviewer` → `APS 符合性审查子代理`
3. `aps-code-quality-reviewer` → `APS 质量审查子代理`
4. `aps-code-reviewer` → `APS 整体验收子代理`

原因：

- 一个负责单任务实现
- 两个负责任务级两阶段审查
- 一个负责阶段末整体验收
- 先把单链路跑顺，再考虑扩更多专项子代理

## 第二批专项件

按需再注册：

- `aps-deep-investigate-worker`
- `aps-independent-auditor`
- `aps-doc-scan`

这些更适合复杂排查、对抗审和大文档扫描，不建议一开始就和首版四件套混在一起全部启用。

## 安装方式

### 方式一：项目级工作区设置

把 `.limcode/subagents/limcode-subagents.template.jsonc` 里的片段复制到：

- `.vscode/settings.json`

然后补齐：

- `channel.channelId`
- 可选 `channel.modelId`
- `enabled`

### 方式二：全局 VS Code 设置

把同样的 `subagents` 配置写进你自己的全局设置：

- `limcode.toolsConfig.subagents`

## 必填项说明

每个原生子代理至少要有：

- `type`
- `name`
- `description`
- `systemPrompt`
- `channel.channelId`
- `tools`
- `enabled`

其中最关键的是：

- `channel.channelId`

这是你的 LimCode 渠道配置 ID，仓库里无法替你猜出，所以模板默认只提供占位值，并保持 `enabled: false`。

## 默认建议

### 并发上限

建议先用：

- `maxConcurrentAgents = 1`

原因：

- 同一分支上的多个实现型子代理并发写文件风险高
- 先把串行链路跑顺，比追求并发更重要

### 工具策略

- 实施子代理：允许读、搜、改文件、跑命令
- 审查子代理：尽量只给只读类工具
- 独立审核类子代理：默认只读

## 与 `.limcode/agents/` 的关系

`.limcode/agents/` 保存的是角色正文源文件，主要用途是：

1. 作为原生子代理 `systemPrompt` 的维护来源
2. 在还没注册原生子代理时，作为宿主通用子代理或主代理降级执行的提示词正文

因此后续统一口径应是：

- **原生注册** → `limcode.toolsConfig.subagents`
- **角色正文源文件** → `.limcode/agents/*.md`

## 相关文件

- 原生配置模板：`.limcode/subagents/limcode-subagents.template.jsonc`
- 角色正文源文件索引：`.limcode/agents/README.md`
- 共享兼容门禁：`.limcode/skills/_shared/subagent-compat.md`
- 调度技能：`.limcode/skills/subagent-driven-development/SKILL.md`

## 最终要求

如果后续文档里提到“优先使用某个子代理”：

- 在 LimCode 原生语境下，默认指**已经注册到 `limcode.toolsConfig.subagents` 的子代理**
- 如果尚未注册，才回退到 `.limcode/agents/*.md` 角色正文源文件
