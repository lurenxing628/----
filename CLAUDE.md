# Claude 项目提示

本仓库的总规则仍以 `AGENTS.md` 为准：开始任务先读 `.codestable/attention.md` 和 `.codestable/reference/system-overview.md`，再按 CodeStable 流程分流。

## symbol-locator 函数定位工具

做实现、修复、改函数前，先用 `python3 -m tools.symbol_locator` 查位置和影响面，避免只凭记忆手翻文件。

| 用户话术 | 应运行 |
|---|---|
| `X 在哪` / `X 定义在哪` / `找下函数 X` | `python3 -m tools.symbol_locator whereis X` |
| `谁调用 X` / `X 被谁用` / `改 X 影响谁` / `动 X 前看波及` | `python3 -m tools.symbol_locator callers X` |
| `X 调了啥` / `X 依赖谁` | `python3 -m tools.symbol_locator callees X` |
| `X 的调用链` / `上下游` | `python3 -m tools.symbol_locator callers X` + `python3 -m tools.symbol_locator callees X` |
| `彻底` / `全量` / `精确` / `含 tests` | 在 `callers` 或 `callees` 后加 `--deep` |
| 句首 `定位:` / `用定位工具` / `上 sl` | 必须按语境选择上面的命令 |

常用例子：

```bash
python3 -m tools.symbol_locator whereis build_dispatch_key
python3 -m tools.symbol_locator callers resolve_plan
python3 -m tools.symbol_locator callers resolve_plan --deep
python3 -m tools.symbol_locator callees resolve_plan
python3 -m tools.symbol_locator whereis to_dict --at core/services/scheduler/calendar_admin.py:306
```
