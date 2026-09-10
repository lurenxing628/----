# EQ 分件真实主页面验收

日期：2026-09-10。范围仅为本测试的隔离主页面及分件业务链，不是全站验收。

## 当前结论

- ES 展示修复、ET 日期表示修复及 EW 汇合前序标识修复集成后，最终统一执行 `5 passed in 72.85s`。
- 覆盖四种宽度/主题组合，加一组 1392-dark 长中文/长连续 ID；所有浏览器均为 1000px 视口高度。
- 三个共同汇合前序按钮现在分别显示原分件 ID，已逐一真实点击，确认仍导航到对应分件的 30 工序。长标签按钮内部不裁切、不横向越界，长详情使用原有滚动区域。
- 此次限定范围内未留产品 blocker。修复前错量、无分件、`piece_raw_changed` 和三个前序同名的红证据均保留；没有通过猜件号或替换业务请求使测试变绿。EQ 未修改产品。

## 重复执行

从 `/Users/lurenxing/GitHub/----` 执行：

```bash
.venv/bin/python -B -m pytest -q -s --confcutdir=tests/workbench tests/workbench/test_piece_main_browser.py --tb=short
PIECE_MAIN_ALL_THEMES=1 .venv/bin/python -B -m pytest -q -s --confcutdir=tests/workbench tests/workbench/test_piece_main_browser.py --tb=short
PIECE_MAIN_ALL_THEMES=1 PIECE_MAIN_LONG_IDS=1 .venv/bin/python -B -m pytest -q -s --confcutdir=tests/workbench tests/workbench/test_piece_main_browser.py --tb=short
```

默认按 `1920-light`、`1392-dark` 顺序执行；`PIECE_MAIN_ALL_THEMES=1` 再增加 `1920-dark`、`1392-light`；`PIECE_MAIN_LONG_IDS=1` 追加真实长业务身份案例。

测试输出 `PIECE_MAIN_ARTIFACTS` 是每次独占且保留的临时根。它不在 pytest 的自动轮换目录里。每次生成新 SQLite、新静态资源、新随机端口；服务在测试退出时关闭，不是长期 preview。

## 真实路径

- 服务使用现有 `run_live_server.LiveRunServer`，仅更换测试自己的种子及临时构建回调；真实 factory、runtime lock、managed worker 和 HTTP 路由没有替身。
- 私有编译严格使用原 `main.jsx` 和 `build-order.json` 的顺序；不调用全局 build、不修改 registry/schema、共享控件或产品文件。
- 浏览器使用 `test_live_browser.runtime_tools()` 返回的 Node/Chromium 109。本轮实测 `109.0.5414.46`。
- 业务写入全部来自浏览器选批、表单和确认按钮；仅初始化 fixture 使用后端写种子。服务端全部 POST 与浏览器日志逐条对应。
- DTO 通过被动 `fetch`/`Response.clone()` 观察留证，原请求及原响应对象不变，无 route/mock/retry 或额外请求。仅对明确取消的只读请求单独留证；写失败、其他网络失败及完整响应取证错误仍判失败。

## 已验证内容

- B1：共同 10 → 三件各自 20/30 → 共同 40；同批同序 `item-A/B/C` 按实际业务身份选择，不猜 ordinal 或 opaque ref。
- B1 整批量 3；共同工序目标量 3、工时 0.75h；每件目标量 1、工时 0.25h。B2 目标量 1、工时 0.5h，与 B1 争用 M1/O1。
- 4 份真实 worker 候选、正式 v5/v6 都逐行核对完整身份、工时、扇出/汇合前后时间及设备/人员不重叠。
- 原 v4 的共同 10 已有完整真实报工；浏览器不可调整它，v5/v6 继承原时间、原资源和执行锁。
- 浏览器正式采用 v5，从 v5 创建试调，把共同 40 调至 `2026-09-09T13:00:00`，保存独立场景后采用 v6。
- 场景重读/刷新仍回同一来源；返回 v5 时 tasks 不变；原运行、候选采用 key、场景采用 key 的核实不新增写请求或正式版本。
- 共同 40 的三个前序链接具有不同的原分件文字，点击分别回到正确的 30 序；长中文与 120 个连续英文字符的原 ID 不被改写、推算或替换。截图文件中的 identity-1/2/3 仅为文件编号，实际动作始终按原业务 ID 定位。
- 候选/正式/试调甘特有真实非空像素/时间条，无外层水平溢出；实际核对截图。补充组合还保存 `*_viewport.png`，避免长截图中 fixed header 的捕获位置误解。
- 77 表不增减；只允许运行、正式、试调、身份/回执/审计台账追加及明确时钟递增。旧 Batches/BatchOperations、非空报工与修订、非空历史候选/场景来源和原回执逐行保留。
- 旧 `OperationExecutionEvents` 在本 fixture 中为 0 行，不冒充非空旧事件覆盖；非空执行保护证据来自原报工/修订。
- 所有 SQLite 连接受独占根路径保护；退出后新只读连接做 `integrity_check`/`foreign_key_check`。无外部请求、无产品 pageerror/console error；冻结 assets 未变、runtime 和 HTTP 已关闭。

## 稳定证据

临时根共同前缀：`/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/`。

| 证据 | 根目录或文件 |
| --- | --- |
| 修复前 1920-light | `aps-workbench-live-peybwzlw` |
| 修复前 1392-dark | `aps-workbench-live-pry_b101` |
| 最终 1920-light | `aps-workbench-live-igtwgwcr` |
| 最终 1392-dark | `aps-workbench-live-r_hxo8d6` |
| 最终 1920-dark | `aps-workbench-live-vx7sciez` |
| 最终 1392-light | `aps-workbench-live-idc1qctx` |
| 最终 1392-dark 长 ID | `aps-workbench-live-4ytjfhfv` |
| 前序链接修复前红证据 | `aps-workbench-live-x7zhdesh` |
| 最终 5 项 JUnit | `/tmp/piece_main_final-xuQY5v/piece_main_final_with_dependencies.xml` |
| 前序链接红断言 JUnit | `/tmp/piece_main_final-xuQY5v/piece_main_predecessor_red.xml` |

每个根内：`piece_main_result.json` 总结果、`piece_main_browser.json` 实际 DTO/动作/截图、`piece_main_retention.json` 逐表与排程证明、`business-before.json`/`business-after.json` 原行、`piece_main_build.json` 来源 SHA-256、`server-ready.json`/`server-final.json` 隔离与关闭证据。

## 边界

- EQ 仅新增 `test_piece_main_browser.py` 和 `piece_main_*`；没有 stage/commit，没有访问旧 preview 或用户库。
- 本轮不验证 pieces 零工时、全部外协组合或全站模块；原 Point/末点合同未修改。
- 测试注册按分工未动，留主线收口。未跑全仓质量门禁：并行 dirty worktree，完整门禁还会写共享产物。以上是局部真实验证，不是 clean-worktree proof。
- 新增 Python 文件的 Ruff 与 Python 3.8.10 兼容语法扫描通过；新增 CJS 的 `node --check` 通过。没有声称这些局部检查等于全仓门禁。
