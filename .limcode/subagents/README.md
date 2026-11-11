# 旧 LimCode 原生子代理配置

仅在用户明确配置旧 LimCode 宿主时使用。普通 Codex 任务直接采用当前宿主子代理工具。

`.limcode/agents/*.md` 是角色正文源；原生注册入口是 `limcode.toolsConfig.subagents`，由对应宿主的工作区或用户设置维护。本目录模板不证明当前已注册或已加载。

`limcode-subagents.template.jsonc` 提供四种可选角色，默认全部停用；配置时核对宿主支持的字段、工具名、真实 channelId 和模型。不要替用户猜渠道或擅自启用。只启用实际需要的角色，不要求四者按固定顺序串联。

任务范围、继承策略和验证按根目录 AGENTS.md；适配方法见 `.limcode/skills/_shared/subagent-compat.md`。角色有变化时同步模板摘要，角色与模板不得增加自动修复或循环审查授权。
