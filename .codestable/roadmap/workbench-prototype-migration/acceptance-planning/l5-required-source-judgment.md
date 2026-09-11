# L5 必交缺口定点判断

**结论：2 组产品缺口，4 个 K 仅缺实测。** 本轮未改产品；12 份关键源码与固定 `ana-7Pj1pV/source` 一致。未重审已过 141 项；旧状态仍为 K 141/146、P 57/31/58，旧绑定不回写。

| 必交项 | 源判断 / 必要补验 |
| --- | --- |
| RUN007.no-result | 代码已有：`RunJobControls.jsx:57` 明示无候选，`run_worker.py:95` 持久保存失败。用真实受理后事实漂移触发 worker 失败，再读原运行/F5，不伪造运行行。 |
| GANTT002.conflict-track | 代码已有：`PlanGanttModel.js:52,93` 依据占用投影分轨/着色。用正式表真实 0.25h 重叠，核对 API、两条 DOM 轨道和 F5。 |
| DELAY004.conflicts | **产品缺口**：`PlanWorkspace.jsx:115`、`PlanDetailsUI.jsx:96` 只有汇总表，重叠 h 不能代替明细。最小修改这两文件：仅延期页显示同一占用快照的资源、起止、并行数及问题/未知边界；不编造延期根因，不改后端。 |
| TRIAL007.stale-conflict | 代码已有：`trial_adoption_validation.py:67`、`trial_adoption.py:70` 提交内重查，`TrialAdoptionState.js:119` 保留原请求。另一真页面新预检/运行/采用后提交旧场景，须 409、全表+schema 不变、F5 原 key/原因保留。 |
| TRIAL011.export-failure | 代码已有：`TrialControls.jsx:44` 捕获异常。一次调用向**原生** `URL.createObjectURL` 传无效参数，由 Chromium 抛 TypeError；恢复 API 后显式重试并核对 CSV。不是断网或合成 Error。 |
| Trial 五组 LS 状态 | **产品缺口**：`TrialGantt.jsx:18` 四字段仅内存；`TrialResults.jsx:19` 经 `TrialAdoptionHistoryState.js:4` 只写 history.state，且草稿不保存。最小修改：新增 `TrialViewState.js`，接 `TrialGantt.jsx`、`TrialResults.jsx`；按原草稿/场景隔离，校验字段并显式报错。Main 接 build-order/fixture；不存写凭证、不删既有历史恢复。 |

## P 的七组边界
严格分组原交接 `P.unverified_required` 的 58 项；以下是复用/补验安排，**不是改判 passed**。字段来自原 ANA 索引指向的 action/preflight 记录。

| 分组 / 项数 | 既有证据与有限补验 |
| --- | --- |
| RUN 输入 · 9 | 复用 `preflight_return` 原选择/日期；余下共用一组输入状态 F5/返回 probe，不跑 9 次排产。 |
| RUN 原记录 · 3 | 复用 `restored_run_ref`、原运行表及 new-PID 原行；只补无结果 fixture。 |
| PLAN/候选/延期/甘特读取 · 22 | 复用 `first_official`、`second_official`、`candidate_scope_recovery` 和选中/搜索恢复；未绑定范围/定位合一组只读 probe，冲突明细复用真实重叠 fixture。 |
| Trial 原内容 · 12 | 复用 `original_draft`、`scenario`、`discarded_draft` 和 new-PID 原引用/行；合一组原草稿/场景恢复 probe。 |
| 回执/拒绝/存储失败 · 5 | 复用原请求区间/回执、`candidate_native_storage`、`trial_native_storage`；仅场景 stale 补两页 probe，不借草稿 stale-write 代替。 |
| Trial LS · 6 | 四个甘特动作加 tabs/keyboard；修复后合一组身份隔离、F5、新页面及存储拒绝 probe。 |
| CSV · 1 | 复用 `candidate_download` 的原引用、任务和实际文件 SHA，不另起导出轮次。 |

- **已测接入**：`ana-tested-tests-allowlist.json` 共 13 文件（原列 4 + 必需 9），固定 ANA 源；SHA `26704ec3f4fb3932e16e2fafd818518faced0e68c7ea7628401f796a1c876e64`。
- **待执行增量**：`l5-required-probes-pending.json` 列 7 测试文件路径/SHA；入口 `tests/workbench/test_final_planning_required.py`，两场景 × 四组合，只补四个 K。Python/Node 语法和 Ruff 通过；**pytest、构建、应用均未启动**，不混入已测白名单。
- 两组产品修复待 Main 确认最小路径后集中实施；共享恢复补验并入统一冻结窗口。未改 H 四组、旧证明或原库，未暂存/提交。
