# Finding 08：daily fast gate 允许 impact 两个 pytest 分支同时空跑

- 优先级：P2
- 结论：快速日常门禁可能在“本次有 impact 目标，但 parallel 和 serial 都没有收集到测试”时仍然通过。

## 根因

`scripts/run_daily_quality_gate.py` 对 impact parallel 和 impact serial 都设置了 `allow_no_tests=True`。主循环遇到 pytest exit code 5 时直接 `continue`，没有在最后检查“两组都空”是否合理。

大白话说：一个分支没测到用例可能正常，两个分支都没测到就应该警惕，但当前代码也当正常。

## 证据

- `scripts/run_daily_quality_gate.py:496-524`：注释说明 impact 两步允许 no-tests。
- `scripts/run_daily_quality_gate.py:525-541`：parallel 和 serial 两个命令都设置 `allow_no_tests=True`。
- `scripts/run_daily_quality_gate.py:667-681`：exit 5 且 allow 时直接跳过，最后打印 passed。
- `tests/gate_meta/test_run_daily_quality_gate.py` 只覆盖单个 impact 步为空，没有覆盖 `[0, 5, 5, 0]`。
- 子代理 D1 只读模拟：退出码 `[0, 5, 5, 0]` 最终 `returncode=0`，输出 `[daily-fast-gate] passed`。

## 影响

- 快速门禁可能给出“通过”，但实际本次 impact 测试一个也没跑。
- 这不等于最终 clean gate 失效，但会误导本地开发和 pre-push 快速判断。

## 建议

- 记录 parallel/serial 两个 impact pytest 的 no-tests 状态。
- 当 `impact_plan.target_paths` 非空且两步都 exit 5 时失败。
- 补 `[0, 5, 5, 0] -> 非 0` 的回归测试。
