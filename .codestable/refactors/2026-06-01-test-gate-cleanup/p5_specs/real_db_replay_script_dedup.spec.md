# P5.1 脚本去冗 spec：real_db_replay 簇（删 check/smoke，保 e2e）

> **类型**：脚本去冗（非 pytest 测试合并）。三文件均为 main-style 独立脚本，`if __name__ == "__main__": raise SystemExit(main())`，pytest 默认收集器对它们收集 0 项。
> **裁决**：删 `run_real_db_replay_check.py` + `run_real_db_replay_smoke.py`，保留 `run_real_db_replay_e2e.py`。
> **铁律对照**：本任务不是参数化合并断言，而是删两份重复脚本。保真口径 = 删除不得让任何 import / 门禁扫描契约 / regression 断点失去依赖；e2e 必须删兄弟后仍自足可跑。

---

## ① 成员文件（各行数）

| 文件 | 行数 | 形态 | 裁决 |
|---|---|---|---|
| `tests/run_real_db_replay_check.py` | 487 | main-style 脚本，`main()` + 无 `def test_` | **删** |
| `tests/run_real_db_replay_smoke.py` | 486 | main-style 脚本，`main()` + 无 `def test_` | **删** |
| `tests/run_real_db_replay_e2e.py` | 586 | main-style 脚本，`main()` + 无 `def test_` | **保留（load-bearing）** |

三者本质同一契约：复制 `db/aps.db` → 隔离副本 → 自动选批次 → `POST /scheduler/run` → 抽检 `/scheduler/gantt/data` + `/scheduler/week-plan/export` + `/reports/*` → 写 `summary.md` + JSON。差异仅在选批策略细节与 app 装配方式（见下）。

---

## ② 目标文件 + 命名理由

**目标 = 保留现有 `tests/run_real_db_replay_e2e.py`，不新建文件、不改其内容。** 这不是「三合一新建一个合并文件」，而是「删两份冗余兄弟、保留 load-bearing 的 e2e」。理由：e2e 是三者中唯一被代码 import 且被门禁扫描契约钉死的文件（见 ⑥），其 app 装配（`_create_test_app` 内联请求级 `g.services` 装配 + 白名单短路 `_open_db`）正是 regression 与 quality_gate 契约的锚点；check/smoke 用的是 `app.create_app()` 走正式工厂，不暴露被契约要求的 `_create_test_app`/`_open_db` 符号。

---

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

三文件均**无 `def test_*` 函数**，断言以脚本内 `raise RuntimeError` / `issues.append` + 退出码 `return 0/1` 的形式存在。下表按「校验点」而非「assert 语句」清点（脚本语义断言）。

### run_real_db_replay_check.py（删）— 校验点 8
- `_run_check` 选批为空：`raise RuntimeError("未能从 DB 中选出可排产批次（status 非 completed/cancelled 且有 BatchOperations）")`
- `POST /scheduler/run` 非 200：`raise RuntimeError(f"POST /scheduler/run 返回 {...}，期望 200；body={body[:500]}")`
- 无 ScheduleHistory：`raise RuntimeError("未写入 ScheduleHistory")`
- gantt 非 200：`raise RuntimeError(f"GET /scheduler/gantt/data 返回 {...}，期望 200")`
- week-plan 非 200：`raise RuntimeError(f"GET /scheduler/week-plan/export 返回 {...}，期望 200")`
- 源库不存在：`print(json.dumps({"ok": False, "summary": "FAIL", "block_reason": "源库不存在"}))` + `return 1`
- pass 判定链（main 内）：报表 `status_code != 200` → fail；`sch.get("result_status") != "success"` → `block_reason = f"result_status={...}，期望 success"`；`failed_ops != 0` → `block_reason = f"failed_ops={failed_ops}，期望 0"`；`not gantt_success` → `block_reason = "gantt_success=false"`
- 选批 SQL：`WHERE LOWER(COALESCE(b.status,'')) NOT IN ('completed','cancelled')`，`INNER JOIN BatchOperations`，默认 min 20 / max 50 / max_ops 1500

### run_real_db_replay_smoke.py（删）— 校验点 7
- `_run_replay` 选批为空：`raise RuntimeError("未能从 DB 中选出可排产批次（pending/scheduled/processing 均为空或无工序）")`
- `_assert_status("POST /scheduler/run (follow redirects)", resp, 200)` → 内部 `raise RuntimeError(f"{name} 返回 {...}，期望 {expect_code}；body={body[:500]}")`
- 无 ScheduleHistory：`raise RuntimeError("未写入 ScheduleHistory（无法获取 version）")`
- `_assert_status("GET /scheduler/gantt/data", gantt, 200)`
- `_assert_status("GET /scheduler/week-plan/export", wp, 200)`
- 报表抽检：**只记 status_code，不强断言**（注释：`只要能访问即可；不引入强断言避免因真实库差异误报`）
- 选批三级回退策略：`statuses_order = [["pending"], ["pending","scheduled","processing"], ["scheduled","processing"]]`，`LEFT JOIN`，默认 min 20 / max 50 / op_limit 2500，`--view machine|operator`，**main 末尾恒 `return 0`**（不因 issue 置非零退出）

### run_real_db_replay_e2e.py（保留）— 校验点 ≥10（最严，覆盖前两者全部语义且更强）
- 选批为空：`issues.append("未选到任何可排产批次（排除 completed/cancelled 后无 op_count>0 的批次）")`
- `/scheduler/run` 非 200：`issues.append(f"/scheduler/run 返回非200：{resp.status_code}")`；调用异常：`issues.append(f"/scheduler/run 调用异常：{e}")`
- 无 ScheduleHistory：`issues.append("未找到 ScheduleHistory（排产未落库或库结构异常）")`
- version 非整数：`issues.append(f"ScheduleHistory.version 非整数：{raw_version}")`
- **覆盖率强断言（仅 e2e 有）**：`if op_count and scheduled_ops != op_count: issues.append(f"排产覆盖率异常：scheduled_ops={scheduled_ops} op_count={op_count}")`
- **失败工序强断言**：`if failed_ops > 0: issues.append(f"排产存在失败工序：failed_ops={failed_ops}")`
- gantt 非 200 / `success=false` / `task_count<=0` 三态分别 `issues.append`，且 `checks["gantt_data"]["ok"] = ok2 and (task_count is not None and task_count > 0)`
- week-plan 非 200：`issues.append(f"/scheduler/week-plan/export 返回非200：{wp.status_code}")`
- 报表逐个 200 强断言（比 smoke 强）：`if not ok3: issues.append(f"报表页不可访问：{name} status={rr.status_code}")` + 异常分支
- 终判：`ok = len(issues) == 0`，`return 0 if ok else 1`；落 `result.json` + `summary.md`

**关键边界/坏值/None 摘录（确认 e2e 已全覆盖，删除无语义丢失）**：
- check 的 `failed_ops != 0` 严判 → e2e 有 `failed_ops > 0`（等价，e2e 还额外加覆盖率 `scheduled_ops != op_count`）✅
- check 的 `result_status != "success"` 严判 → e2e 记录 `result_status` 但**不**因其非 success 直接 fail（e2e 以 issues 列表的 counts/gantt/报表 200 为准）。**差异见 ⑩ 风险点 R1**。
- smoke 报表「只记 status_code 不强断言」是**弱化**版，e2e 是其强化超集 → 删 smoke 无损失 ✅
- None 处理：三者 `version is None` / `result_summary` 非 dict 均有兜底；e2e 额外显式 `raw_version is None: raise TypeError("version is None")` 后捕获记 issue，最稳 ✅

---

## ④ 共享 setup → 建议 fixture（对照 conftest）

**不适用 / 无改动。** 这三个是 main-style 脚本，不是 pytest 用例，**不经过 `tests/conftest.py` 的 fixture 体系**（`db_path`/`db_env`/`app_client`/`schema_conn`/`mem_conn`/`schema_path`/`repo_root` 全部不被它们引用）。它们各自内联 `_find_repo_root` / `_ensure_dir` / 自建副本 DB + 自起 app。保留的 e2e 维持现状，不重构去复用 conftest（超出本任务"删冗"范围，且 e2e 的 `_create_test_app` 是契约锚点不能动）。

**缺口**：无。删除 check/smoke 不产生任何 fixture 缺口。

---

## ⑤ 参数化方案

**不适用。** 本任务是删冗余脚本而非合并 pytest 用例，没有 `parametrize` 维度可收。三脚本的选批策略差异（check: `INNER JOIN` + 非 completed/cancelled；smoke: `LEFT JOIN` + 三级 pending 回退；e2e: `LEFT JOIN` + 排除 completed/cancelled）**不收进参数化**——保留的 e2e 用其自身策略即可，check/smoke 的策略随文件一并删除（无下游消费者，见 ⑥）。CLI 入参差异（check `--max-ops 1500` / smoke `--op-limit 2500` `--view` / e2e `--max-ops 2000`）同样随删除消失，e2e 保留自身默认值。

---

## ⑥ load-bearing import / importlib 引用（grep 实核）

全仓 `--include=*.py *.md *.json *.yaml *.sh *.cfg *.ini *.toml` 扫描结论：

### check / smoke：**零代码引用**，删除安全
匹配仅出现在文档与旧裁决归档，无任何 `.py` import：
- `.codestable/audits/.../dossiers/R32.md:96,117`（纯文档，列为"真库重放消费者，落地跑一遍确认"——弱关注非安全网）
- `.codestable/refactors/2026-06-01-test-gate-cleanup/` 下 `_CROSS_IMPACT_*.{md,json}` / `summary.json` / `L3_VERDICTS.md` / `PLAN.md`（本批次自己的裁决归档，已明文裁 check/smoke = MERGE→删）

→ **无 `.py` 文件 import / importlib 加载 check 或 smoke；无门禁扫描清单引用 check 或 smoke。**

### e2e：**load-bearing，三处硬依赖（保留它，删兄弟不碰这些）**
1. `tests/regression_request_service_test_factory_invariant.py:18` → `import run_real_db_replay_e2e as replay_mod`，:66 调 `replay_mod._create_test_app(...)`，测 `_open_db` before_request 不变量（g.services 缺失 RuntimeError / 装配失败关连接 close_calls==1 / 白名单短路）。
2. `tools/quality_gate_shared.py:217` → `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 含 `"tests/run_real_db_replay_e2e.py"`；:251 → `REQUEST_SERVICE_TARGET_SYMBOLS["tests/run_real_db_replay_e2e.py"] = ["_create_test_app", "_open_db"]`（门禁扫描契约要求该文件存在且含这两符号）。
3. `tests/regression_quality_gate_scan_contract.py:614` `assert "_open_db" in shared_mod.REQUEST_SERVICE_TARGET_SYMBOLS["tests/run_real_db_replay_e2e.py"]`；:619 `rel_path = "tests/run_real_db_replay_e2e.py"`。

### e2e 删兄弟后自足性：**确认自足**
`grep import tests/run_real_db_replay_e2e.py` 对 `replay_check`/`replay_smoke`/`run_real_db` 零命中 → e2e **不 import check/smoke 任何符号**，自身内联全部 helper（`_find_repo_root`/`_select_batches`/`_create_test_app`/`_latest_schedule_history`/`_min_start_date`/`main`）。删兄弟后 e2e 独立可跑。

### `test_no_residual_main_style_regression.py`：**不波及**
该守卫只 `TESTS_DIR.glob("regression_*.py")`（前缀 `regression_`），三个 `run_real_db_replay_*.py` 不匹配前缀 → 既不会因删 check/smoke 触发，也不会因保留 e2e 报"def main 无 def test_"假绿。

---

## ⑦ registry 影响（tools/test_registry_data.py）

**无。** `grep "real_db\|replay\|RealDbReplay" tools/test_registry_data.py` 零命中 → 该 registry 不收录这三个脚本（它们非 pytest 收集对象，本就不在 registry 治理范围）。删除 check/smoke **无须改任何 registry 条目**。

---

## ⑧ B-COMPAT pin（必须逐字保留禁去重的断言）

**无 B-pin。** 本任务删除的 check/smoke 不携带任何被 `_B_COMPAT_SAFEGUARDS.md` 红线钉死的快照/契约断言；保留的 e2e 不改动其任何断言文本，故无"逐字保留"压力。需逐字保留的是 ⑥ 列的三处 e2e 引用契约（文件名 + 符号名 `_create_test_app`/`_open_db`），但那属于"保留 e2e 现状"而非去重断言，删兄弟不触碰。

---

## ⑨ 断言条数对账

| 阶段 | 校验点合计 |
|---|---|
| 合并前：check(8) + smoke(7) + e2e(≥10) | 25（含跨文件重复） |
| 合并后：保留 e2e | ≥10 |
| **语义覆盖对账** | e2e 的校验点是 check ∪ smoke 的**语义超集**：check 独有的 `failed_ops!=0` / gantt 200 / week-plan 200 → e2e 全有且更强（加覆盖率断言）；smoke 报表"只记不强断言"是 e2e 的弱化版，删之无损。**唯一非超集项见 R1**。 |

注：脚本去冗的"对账"不是断言数相加守恒（25→10），而是**删除项的每条语义都能在保留项 e2e 中找到等价或更强校验**。已逐条核对：check/smoke 的全部 RuntimeError/issues 校验点在 e2e 均有对应或更严格版本，仅 `result_status=="success"` 严判一项 e2e 未直接复刻（见 R1，判定为可接受弱化）。

---

## ⑩ 风险 / 阻塞点

- **R1（低，可接受弱化，非阻塞）**：check 有 `result_status != "success"` 直接判 fail；e2e 记录 `result_status` 但不据此直接 fail（以 counts/gantt/报表 200 + `failed_ops>0` + 覆盖率为准）。实务上 `result_status != success` 几乎必然伴随 `failed_ops>0` 或覆盖率缺口，e2e 会经这些途径捕获。判定：删 check 不构成真实覆盖回退。若需绝对保真，可在落地时给 e2e 补一行 `if result_status != "success": issues.append(...)`——但这是**增强非必需**，本 spec 不强制（保持"不改 e2e 内容"原则）。
- **R2（文档订正，非阻塞）**：`R32.md` §11（:96/:117）写"落地时跑 run_real_db_replay_check/smoke 确认不误红"。删后该指引文件名失效。两文件用 raw `sqlite3.Connection.backup`（`_sqlite_backup_copy` :60-78），对 R32 的 `BackupManager` integrity_check 改动免疫（grep `integrity_check` 两文件零命中）。建议落地时把 R32 §11 文件名订正为 `run_real_db_replay_e2e.py`（e2e 经 `create_app` 走完整 backup 栈，覆盖更全）。**纯文档订正，不阻塞删除。**
- **R3（无）**：无 import 断裂风险（⑥ 已实核 check/smoke 零代码引用，e2e 自足）。
- **R4（无）**：无 registry/B-pin 风险（⑦⑧ 均为"无"）。

### 安全删除清单
```
git rm tests/run_real_db_replay_check.py
git rm tests/run_real_db_replay_smoke.py
# 保留 tests/run_real_db_replay_e2e.py，不改动
```

### 须同步处理的引用点
- **代码 / 门禁**：无。check/smoke 无任何 `.py` import、无门禁扫描清单引用，删除后 `quality_gate_shared.py` / `regression_quality_gate_scan_contract.py` / `regression_request_service_test_factory_invariant.py` 全部只依赖 e2e，不受影响。
- **文档（可选，非阻塞）**：`R32.md` §11 文件名 check/smoke → e2e（R2）。本批次自己的归档（`_CROSS_IMPACT_*`/`summary.json`/`L3_VERDICTS.md`/`PLAN.md`）是历史裁决记录，按惯例不回改。
