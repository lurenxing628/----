---
doc_type: issue-fix
status: fixed
date: 2026-10-12
---

# Codex hook 明确授权放行

原 `pre_tool_use_policy.py` 对强推等命令固定返回 `deny`，提示用户确认后仍走同一条拒绝路径；`UserPromptSubmit` 只补充项目导航，未记录授权。本会话已多次明确授权强推到 `main`，实际命令仍被拒绝。

两个入口现共用 `.codex/hooks/authorization.py`：真实用户输入生成当前仓库、当前会话的授权，普通后续消息沿用；明确撤销和只读限制收回授权。强推核对目标分支和 `git remote get-url --push --all` 的实际推送地址。其他受保护操作按用户明确给出的整条命令核对，强推授权不会放行同一 shell 命令里的删除操作。提问、否定、引用、示例、助手和工具消息不生成授权。

授权状态放在当前 worktree 的 Git 目录中。首次接入已有会话时，核对 transcript 的 `session_meta.id/cwd`，仅按顺序处理现场确认的 `response_item/type=message/role=user/input_text` 格式；授权更新失败时清除旧授权，避免撤销失败后仍放行。使用的稳定 hook 输入和返回字段来自 [OpenAI Hooks 文档](https://learn.chatgpt.com/docs/hooks)；已有会话 transcript 的格式单独由适配代码和测试约束。

`.codex/hooks.json` 与三个 Python 源文件纳入版本管理，本机 `config.toml` 保持本地配置。回归移入 `tests/app_runtime/test_codex_hook_authorization.py`，在统一登记表的运行时职责组登记，开发文档同步使用方式。

实际验证：

- 使用 hook 的实际解释器 `/usr/bin/python3` 执行 8 项行为测试，通过。覆盖授权保留和撤销、同会话/仓库/远端/分支隔离、不同强推形式、真实消息回放、推送地址变化、否定和提问、混合命令及具体命令授权。
- 改动 Python 文件 `ruff check` 通过，`git diff --check` 通过。
- 本会话通过真实 PreToolUse 执行 `git push --force-with-lease=refs/heads/main:8818cf366657a17195d0b3684a0b73ffdc6a3f21 --dry-run origin HEAD:refs/heads/main`，返回 `Everything up-to-date`；由 hook 从已有真实用户记录生成的授权只有 `refs/heads/main`，未新增人工授权状态。

正式提交与强推按本会话用户授权执行，推送前日常门禁由既有 Git hook 运行，最终远端提交核对见交付结果。
