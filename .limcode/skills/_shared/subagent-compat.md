# 子代理兼容门禁（共享）

本文件用于统一所有涉及子代理的技能与角色约束，避免在多个技能正文里重复维护。

## 核心分层

### 第一优先：LimCode 原生已注册子代理

- 真正的原生注册入口：`limcode.toolsConfig.subagents`
- 项目级模板与安装口径：
  - `.limcode/subagents/README.md`
  - `.limcode/subagents/limcode-subagents.template.jsonc`
- 如果当前 LimCode `subagents` 工具里已经能看到目标子代理，就应优先直接调用它

### 第二优先：角色正文源文件

- `.limcode/agents/*.md`
- 这些文件**不是** LimCode 自动扫描的原生注册目录
- 它们是角色正文源与回退提示词来源

### 第三优先：宿主通用子代理

只有在第一优先不可用、且宿主确实支持通用子代理时才使用。

### 第四优先：主代理降级执行

如果连宿主通用子代理都不可用：

- 明确告诉用户当前限制
- 由主代理按对应角色正文的清单与输出格式手工执行

## 唯一原则

- 优先使用 LimCode 原生已注册子代理
- 只有在原生子代理尚未注册时，才读取 `.limcode/agents/*.md` 作为角色正文源
- 回退到宿主通用子代理时，必须：
  - 保持只读语义（如果该角色本应只读）
  - 默认不显式覆盖主模型继承，除非用户本轮明确指定模型 / 推理强度，或具体技能写明更强约束
  - 在提示中完整内联目标角色的职责、约束、输入要求和输出格式

## 模型与推理强度约束

- 默认策略：子代理继承主代理模型与推理强度，不为了省成本静默降级。
- 显式指定优先：如果用户本轮明确指定子代理模型 / 推理强度，或具体技能写明专用模型约束，必须按显式要求执行。
- 深度审查、独立审核、对抗审核类子代理的项目默认要求是：`gpt-5.5`，reasoning effort 为 `xhigh`。
- 如果宿主通用子代理工具支持 `model` / `reasoning_effort` 字段，调度时必须显式传入上述值。
- 如果使用 LimCode 原生子代理，应在 `limcode.toolsConfig.subagents` 的渠道配置中绑定等价的 GPT-5.5 / xhigh 能力；仓库模板不能替用户猜真实 `channel.channelId`。
- 如果当前宿主无法提供 GPT-5.5 / xhigh，必须在最终输出中明确说明实际使用的模型与限制，禁止静默降级。

## 禁止事项

- 禁止把 `.limcode/agents/` 误称为 LimCode 原生子代理自动扫描目录
- 禁止用浏览器型、命令型、快速探索型子代理冒充独立审核员
- 禁止为了省成本把关键审查角色静默降级为明显更弱的路径
- 禁止在没有说明限制的情况下，谎称“已继承主模型”

## 适用对象

- `feature-design`
- `deep-investigate`
- `subagent-driven-development`
- `requesting-code-review`
- 以及所有依赖 `subagents` 工具或 `.limcode/agents/*.md` 角色正文的流程

## 写法要求

技能正文不要再重复拷贝整段宿主兼容说明。

正确做法：

1. 在技能正文里只写“遵循共享兼容门禁”
2. 引用本文件路径
3. 只在该技能特有的地方补充差异规则
4. 当技能提到 `.limcode/agents/*.md` 时，要明确那是“角色正文源文件”而不是“原生注册目录”

## 角色正文源文件清单

- `.limcode/agents/code-reviewer.md`
- `.limcode/agents/independent-auditor.md`
- `.limcode/agents/deep-investigate-worker.md`
- `.limcode/agents/plan-implementer.md`
- `.limcode/agents/spec-reviewer.md`
- `.limcode/agents/code-quality-reviewer.md`
- `.limcode/agents/aps_doc_scan.md`

## 额外说明

- 本文件是“共享门禁”，不是单独技能。
- 任何技能如果写了与本文件冲突的子代理兼容规则，以本文件为准，除非该技能明确说明自己为什么必须例外。
