# D-P001..004 修复与验证

## 结论

- Main 2026-09-10 22:19 的授权已执行：P001、P002、P004 完成修复及真实入口验证；P003 现有只读/导航协议不足，精确最小提案见 p003-minimum-protocol.md，等待 Main 确认后接入。
- 原冻结分母保持 37 族 / 146 动作。旧 evidence-matrix.json 只记录历史四组合 78 动作；最新主链同源四组合为 evidence-matrix-current.json 的 115 动作，预检另有 evidence-preflight-current.json 的 5 动作。二者不是同一整站构建，不能合并成当前 HEAD 全站通过。
- 产品只改本域五个前端文件，没有改 Main shared navigation、G05 build-order、算法、runtime、数据库 schema 或生产库。没有新增前端叶文件需要注册。

## 根因与改动

| 项目 | 根因与修复位置 |
| --- | --- |
| P001 返回预检 | `frontend/workbench/app/PreflightWorkspace.jsx:38` 发布严格六项 C.input 快照；`:65` 离页先 invalidate。只保留用户输入，result/input_ref/write_context/token 不进入历史上下文，返回不自动重试。 |
| P002 仅变更 | `frontend/workbench/app/PlanGanttModel.js:65` 使用已核实 baseline.change 的 operation_ref 集合；`PlanGantt.jsx:99` 无基线时禁用并显示原因。完整计划时间轴和实际冲突证据不因显示过滤缩小。 |
| P002 展开/收起 | `PlanGantt.jsx:32`、`PlanLayout.jsx:105` 接实际视口工作区，保持原 zoom；可按钮收起或 Escape，退出恢复滚动和焦点；使用现有离线 Lucide 图标。 |
| 原失败集合的悬停 | `PlanGantt.jsx:53` 拆分显示条件重置与滚动核对。原事件次序为 mouseenter 后 scroll，原 effect 清掉仍位于同一任务的提示；现按鼠标下 task_ref 与基线身份核对。没有去掉 tooltip 断言。 |
| P004 打印 | `TrialWorkspace.jsx:22` scoped beforeprint/afterprint。临时 light，随后恢复原 data-theme（含原本不存在的情况），卸载移除监听。没有持久偏好写入，没有新打印按钮。 |

## 产品指纹

| 文件 | SHA-256 |
| --- | --- |
| PreflightWorkspace.jsx | `2cc743a3f79dc7037f536186ada74c76f4db14a06636285a24257abc16d14c29` |
| PlanGanttModel.js | `57d86aa11b330b87924634eaaf71e6bfdacfd53ae90a0d7aa9e5518fa0099b3d` |
| PlanGantt.jsx | `502c31441a7389e7ffe531d5f85b2611bb12afdb462a056e67076c9f3ae5b1a5` |
| PlanLayout.jsx | `6953a53ee7824e20c6f2a22007e8e468c1b653a74cbda15744f3a43573cb977b` |
| TrialWorkspace.jsx | `2f60104105ad06ebaf3617ae1291a1d39de08363fd743eb7ce293433ed7e0eab` |

## 已完成验证

统一使用 `.venv/bin/python` 3.8.10、私有 PYTHONPYCACHEPREFIX、PYTHONDONTWRITEBYTECODE=1、私有 SQLite/日志/资源构建。完整入口采用真实 factory、受管 worker、Chrome 109 和实际点击/输入；没有业务 API mock。

- P001 原失败独立用例：`pytest tests/workbench/test_final_planning_preflight_return.py`，`1 passed in 8.68s`；JUnit `/tmp/aps-final-d-p001-fix.xml`，根 `aps-workbench-live-x6d1pxar`。逐项核对六项历史输入与 normalized_input，旧结果消失，返回仅 GET。
- 新模型及冻结分母：`pytest tests/workbench/test_final_planning_gantt.py tests/workbench/test_final_planning_contracts.py`，`3 passed in 0.96s`；JUnit `/tmp/aps-final-d-p002-model.xml`。模型用例明确不是完整入口 K。
- 本域综合回归：`pytest tests/workbench/test_plan_ui.py tests/workbench/test_preflight_browser.py tests/workbench/test_trial_widgets.py tests/workbench/test_final_planning_gantt.py tests/workbench/test_final_planning_contracts.py tests/workbench/test_final_planning_delivery.py`，`20 passed in 138.83s`；JUnit `/tmp/aps-final-d-p001-p004-regression.xml`。
- 其中 Plan UI：Chrome 109，51 用例、509 断言、31 截图；预检实际 API/私有 SQLite 四组合；Trial full 86 checks、exports 10 checks，各四组合。组件/API 回归不冒充全站链路证明。
- Ruff 所有 D final_planning Python 文件通过；11 个 CJS 完整语法解析、10 个 Python 文件经 3.8 AST 解析通过。D 未跑 Main 负责的完整质量门禁。

## 完整入口快照

共同前端构建 `cdb4412c207f0f393f832e63ee762785ceb2161bbc5f2236d0010af54b42c012`，222 个构建文件、314 个输入。私有根前缀均为 `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-`。

| 组合 | 私有根后缀 | 结果 |
| --- | --- | --- |
| 1392 dark | 2h9jvqyf | `1 passed, 3 deselected in 53.58s`，JUnit `/tmp/aps-final-d-p002-dark.xml` |
| 1920 light | douh5aod | 108 主链 + 7 新进程动作、独立 SQLite oracle、正常停机和各阶段源检查通过 |
| 1920 dark | 00opebn3 | 同上 |
| 1392 light | cdhty7i4 | 浏览器主链/重启链均通过，但运行期间 E 域已加载的校准 Python 源码改变；严格断言失败，不计入完整通过 |

- 两次采用仍只生成 v5/v6；完整 13 道安排、共同/分件、4 个零时长点、正工时、已执行及锁冻结保持，77 个表的原数据保留，其他请求不改正式计划，新进程读取不写业务表。
- 1392 dark 原生 `Page.printToPDF` 产生 trusted beforeprint/afterprint：light 后回到原 dark；整个 localStorage 逐项一致。`2h9jvqyf/screenshots/final-planning-native-print.pdf` 为 Chromium/Skia m109 的 3 页 PDF；首张渲染确认浅色。这里只验证冻结要求的主题时序，不表示纸张分页布局已由 Main V 验收。
- 悬停诊断保留在 `5t81hdhf/final_planning_hover-detail.json`，只读事件记录确认次序；临时探针代码已移除。
- `/tmp/aps-final-d-p001-p004-matrix.xml` 的真实合计是 `1 failed, 2 passed in 197.50s`，不能写成四组合全通过。之后复用 cdb 构建又因 E 域 `CalibrationAPI.js` 哈希改变而在启动前失败；没有放宽检查。后续完成结果如下。

## 本阶段最终证据（2026-09-10 23:08）

### 主链四组合

- 新前端构建 `94cbcc13fe35c829102219182d16233a19e75aa1b1cf34eed2f551f9ce3107f7`；实际加载产品 Python 跨样本并集 1092 文件，所有共用路径 SHA 一致，整体 digest `0cea08a23306af563d5f9c1b17186ec7cce4d609097cd453ca81614e52f3c8d6`。
- 1920 light：`f7woj4dm`；1920 dark：`2kcrcemq`；1392 light：`oo3dl2zn`；1392 dark：`5fuauy0s`。四组均有完整 result.json、两个不同进程、正常停机、全部 SQLite oracle 及源检查通过。
- 每组 108 主链 + 7 新进程动作，115 个不同动作。账本 `evidence-matrix-current.json` 的 SHA 为 `cd2d54b5d14a3b0571d1c77dc5faf9e397dcc6f1467bab15a5ded7dd19f2fdc7`；K 115 passed / 31 not_run，V 115 pending_main_review，独立 P 9 passed。35 族有动作证据，不等于 35 族全部通过。
- 实际命令入口：`.venv/bin/python -m pytest -q -s -x -o cache_dir=/tmp/aps-final-d-pytest-cache --basetemp=/tmp/aps-final-d-p001-p004-current --junitxml=/tmp/aps-final-d-p001-p004-current.xml tests/workbench/test_final_planning_browser.py tests/workbench/test_final_planning_readonly.py tests/workbench/test_final_planning_preflight_return.py`，带上述私有字节码环境。
- 这条完整命令真实合计 `1 failed, 7 passed in 344.15s`：四个主链及前三个只读用例通过，第四个只读期间 `ActualGanttControls.jsx` 改变，触发严格源码检查；预检尚未执行。不能把整个命令写成全绿。

### 预检四组合

- 独立前端构建 `b7b4f7c2241d948af6ae121f9940aaccba477ae26b8341b6393cee139e4491cb`；1920 light：`58vtidos`；1920 dark：`hff06hgh`；1392 light：`22jx4s1_`；1392 dark：`b7m4gj4y`。
- 四组每组 5 个动作和 77 张业务表完整不变均通过；各组真实主题已通过 UI 设置/核对。`evidence-preflight-current.json` SHA `c6269d6d2dfedf9b69bdd55db3cebc14be23d15517e2fb5fb2b5e768114ab967`。该账本只收录 5 项，不表示其他账本中已执行的 115 项未做过。
- 实际命令入口：`.venv/bin/python -m pytest -q -s -x -o cache_dir=/tmp/aps-final-d-pytest-cache --basetemp=/tmp/aps-final-d-boundaries-current --junitxml=/tmp/aps-final-d-boundaries-current.xml tests/workbench/test_final_planning_readonly.py tests/workbench/test_final_planning_preflight_return.py -k '1392-dark or not invalid_plan_and_incomplete_batch'`，真实结果 `5 passed, 3 deselected in 44.02s`，含一个只读 1392 dark 用例与四个预检用例。

### 只读边界与构建差异

- 两个原子为无效 plan_ref 拒绝且刷新不切换来源、完整批次未排时风险为 unknown。1920 light `xsln8u_s`、1920 dark `f6i2cpbt`、1392 light `h2ybsoo6`、1392 dark `q1xyhc2h` 各自完整入口用例均通过，各自 77 表逐项不变。
- 但这些只读样本涉及两个前端构建，且共享 Python 路径 `core/services/scheduler/gantt_critical_chain.py` 的 SHA 不同。跨样本源检查拒绝合并，所以这里只保留各次运行证据，不生成“同源四组合通过”账本。
- 94cb 与 b7b 的前端输入差异是 ActualGanttControls.jsx；之后 FieldWorkspace.jsx 又改变，重用 b7b 的一次只读补测在启动前失败（`raopxh5r`，`/tmp/aps-final-d-readonly-complete.xml`）。没有覆盖并行改动，没有删断言或放宽哈希门禁。
- 本轮 D 未新增产品叶文件。Main 的 `tools/test_registry_groups_workbench.py:947` 已登记 D final_planning Python 用例，含新 gantt 测试；D 未编辑共享 registry。

## 保留与剩余

- Git 归 Main；D 没有 add/commit/reset/checkout、清理缓存或改动旧 preview 53144。既有 dirty/staged/untracked 内容保留；最后只读检查 staged 为空，本域五个产品文件及新增测试/文档仍为 untracked。
- P003 的协议确认、其后的具体 UI 与身份链测试仍未完成。尚有 24 个完整入口原子未单独编写和执行；另有上述不同构建的边界证据没有混入主链账本。Main V 待终审；不以本域回归或单组通过替代全站终验、clean-worktree proof、5000 性能证明或发布证明。
