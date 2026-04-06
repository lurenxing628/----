# 改动后检查审阅报告（LLM）

- 时间：2026-04-05 20:20
- 触发原因：FAIL
- 范围说明：本次快检覆盖**当前整个未提交工作区**，不是只看刚才修的 `web/ui_mode.py`；因此结果里既包含本轮改动，也包含此前已存在的未提交修改。

## 证据

### 1. `git status --short` 摘要

当前共有 **50** 个已改动文件，包含：

- 入口：`app.py`、`app_new_ui.py`
- 排产核心：
  - `core/algorithms/greedy/config_adapter.py`
  - `core/algorithms/greedy/schedule_params.py`
  - `core/services/scheduler/config_snapshot.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_summary.py`
  - `core/services/scheduler/schedule_summary_assembly.py`
  - `core/services/scheduler/schedule_summary_types.py`（新增）
- 路由/UI：
  - `web/bootstrap/entrypoint.py`（新增）
  - `web/ui_mode.py`
  - 多个 `web/routes/*.py`
  - 多个 `web/viewmodels/page_manuals_*.py`
- 测试：
  - `tests/regression_config_snapshot_strict_numeric.py`
  - `tests/regression_scheduler_strict_mode_dispatch_flags.py`
  - `tests/test_ui_mode.py`
  - `tests/regression_process_excel_routes_extra_state_guard.py`（新增）
  - 以及多项其他测试文件
- 文档/证据：`static/docs/scheduler_manual.md`、`evidence/**`

### 2. `git diff --name-only` 结论

变更明显跨越：入口、排产核心、路由、页面说明、测试、文档，属于**跨模块脏工作区**。

### 3. 一键快检脚本输出摘要

脚本：`python .limcode/skills/aps-post-change-check/scripts/post_change_check.py`

结论：

- Ruff Lint：**FAIL**
- 架构分层合规：**PASS**
- 代码质量检查：**PASS**
- 圈复杂度检查：**WARN（5 个超标函数）**
- 联动更新提醒：**3 项**
- 总结：**FAIL - 请先修复上述问题**

关键输出片段：

```text
## Ruff Lint：FAIL
  app_new_ui.py:1:1: I001 [*] Import block is un-sorted or un-formatted
  core/services/scheduler/config_snapshot.py:78:31: B009 [*] Do not call `getattr` with a constant attribute value.
  tests/regression_runtime_lock_reloader_parent_skip.py:11:1: I001 [*] Import block is un-sorted or un-formatted
  tests/regression_schedule_params_read_failure_visible.py:1:1: I001 [*] Import block is un-sorted or un-formatted
  tests/regression_schedule_summary_freeze_state_contract.py:1:1: I001 [*] Import block is un-sorted or un-formatted
  web/routes/excel_demo.py:1:1: I001 [*] Import block is un-sorted or un-formatted
  web/ui_mode.py:1:1: I001 [*] Import block is un-sorted or un-formatted
```

```text
## 圈复杂度检查：WARN（5 个超标函数）
  core/algorithms/greedy/config_adapter.py:42 read_critical_schedule_config complexity=18 (rank C)
  core/algorithms/greedy/schedule_params.py:30 resolve_schedule_params complexity=50 (rank F)
  web/routes/process_excel_routes.py:197 excel_routes_confirm complexity=20 (rank C)
  web/routes/scheduler_batches.py:30 batches_page complexity=17 (rank C)
  web/bootstrap/entrypoint.py:140 app_main complexity=24 (rank D)
```

```text
## 联动更新提醒：3 项
  → 改了 route → 检查对应 template 是否需要同步；检查 面板与接口清单.md
  → 改了 scheduler 服务 → 检查速查表 ScheduleConfig 部分是否需要更新
  → 改了 Excel 相关代码 → 检查速查表 Excel 模板清单是否需要更新
```

### 4. 文件级直接证据

#### `web/ui_mode.py:1-6`

```python
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, Optional
from urllib.parse import urlsplit
```

这与 Ruff 的 `I001` 一致，属于导入块未格式化。

#### `core/services/scheduler/config_snapshot.py:71-78`

```python
def _read_repo_raw_value(key: str) -> Tuple[bool, Any]:
    repo_get = getattr(repo, "get", None)
    if callable(repo_get):
        record = repo_get(key)
        if record is None:
            return True, None
        if hasattr(record, "config_value"):
            return False, getattr(record, "config_value")
```

这里的 `getattr(record, "config_value")` 与 Ruff 报出的 `B009` 一致。

## 事实摘要（只基于证据）

1. 当前工作区存在 **50** 个未提交改动文件，范围明显超过本轮刚完成的修复点。
2. 快检脚本给出的唯一硬失败项是 **Ruff Lint**，共 **7** 项。
3. 这 7 项里，绝大多数是 `I001` 导入块格式问题；另有 **1 项** 是 `config_snapshot.py` 的 `B009`。
4. 架构分层合规未发现直接违反项。
5. 代码质量检查未发现新的裸字符串枚举或缺少 future annotations 问题。
6. 圈复杂度检查给出 **5 个超标函数**，其中 `resolve_schedule_params` 复杂度达到 **50**，但快检只证明“当前超标”，**不能单凭本次输出断言全部由本轮引入**。
7. 联动更新提醒命中 3 类：route、scheduler、Excel。

## 结论与取舍（LLM）

### 必须改（P1）

- [ ] 先清理 Ruff Lint 的 7 项问题
  - 原因：快检总结果当前为 FAIL，按当前门禁不宜直接收尾。
  - 最短路径：
    1. 先修 `web/ui_mode.py` 的导入排序；
    2. 再把 `core/services/scheduler/config_snapshot.py` 中 `getattr(record, "config_value")` 改成直接属性访问或先判类型后访问；
    3. 顺手统一剩余几处 `I001`。
  - 成本：S

### 建议改（P2）

- [ ] 对本轮直接触达文件优先做“小范围格式清扫”
  - 原因：当前 FAIL 里混有历史脏工作区问题；先把本轮直接影响的文件收干净，能显著降低后续噪声。
  - 建议优先级：`web/ui_mode.py`、`core/services/scheduler/config_snapshot.py`、`tests/regression_scheduler_strict_mode_dispatch_flags.py`、`tests/test_ui_mode.py`、`web/routes/process_excel_routes.py`
  - 成本：S

- [ ] 评估 `core/algorithms/greedy/schedule_params.py::resolve_schedule_params` 的复杂度治理是否要单开后续任务
  - 原因：复杂度 50 已经远超快检阈值；虽然不是本轮阻断语义修复的直接目标，但会持续增加维护成本。
  - 成本：M

- [ ] 补做联动文档确认
  - 原因：本次改动覆盖 scheduler、route、Excel；脚本已明确提醒。
  - 建议检查：
    - `开发文档/系统速查表.md`
    - `开发文档/面板与接口清单.md`
    - `static/docs/scheduler_manual.md`
  - 成本：S

### 不建议改 / 暂缓

- [x] 本轮不要因为复杂度告警而临时扩大重构范围
  - 原因：当前用户任务主目标是“静默回退收口与基线精修”；复杂度问题真实存在，但不是这次最短闭环路径。

- [x] 不要把整个 50 文件脏工作区一次性混成一个“全部修完再说”的大包
  - 原因：当前快检已经证明工作区是跨模块并行演进状态；应优先把**硬失败的 lint 项**与**本轮变更关联最强的问题**收掉。

## 成本与风险评估

- 预估总成本：S ~ M
- 回归风险：低
- 推荐策略：
  1. 先修 7 个 Ruff 问题；
  2. 再复跑快检；
  3. 然后决定是否把复杂度项纳入下一轮治理；
  4. 若准备合并当前整批跨模块修改，建议补一次深度 review。

## 建议下一步

1. 先修 Ruff 的 7 项硬失败。
2. 修完后重跑本快检。
3. 因为当前改动涉及 **3 个以上文件的跨模块变更**，建议升级做一次**深度 review**，确认引用链和联动面没有漏网。