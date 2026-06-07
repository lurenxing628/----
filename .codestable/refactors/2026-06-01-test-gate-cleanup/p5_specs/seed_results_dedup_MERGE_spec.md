# P5.1 MERGE spec — 簇 `seed_results_dedup`（4 文件，干净）

> 行为保真铁律：合并后断言条数必须 >= 合并前各文件之和；去重仅限"逐字完全重复的同义断言"。
> 本簇结论：**干净可合并，但有一处真陷阱——桩接口签名不一致，禁止"统一成一个桩"**（见 §10 风险）。

---

## ① 成员文件（各行数）

| # | 文件 | 行数 | 测的畸形场景 |
|---|------|------|------|
| F1 | `tests/regression_seed_results_dedup.py` | 138 | 重复 op_id 去重（seed 工序仅出现 1 次），时间回填 |
| F2 | `tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py` | 152 | 重复 op_id + 坏时间（end<=start）剔除 + warning 透出 |
| F3 | `tests/regression_seed_results_freeze_missing_resource.py` | 160 | 冻结种子缺一项资源维度（缺 operator_id / 缺 machine_id）仍冻结现有资源 |
| F4 | `tests/regression_seed_results_invalid_op_id_dedup.py` | 163 | op_id<=0（=0）经 op_code 或 (batch_id,seq) 匹配回填真实 id |
| | **合计** | **613** | |

四种场景**确实走同一入口** `GreedyScheduler(calendar_service=...).schedule(operations, batches, start_dt, seed_results, dispatch_mode, dispatch_rule="slack")`，差异只在 `seed_results` 的畸形构造与桩签名 —— 满足"按输入畸形类型参数化"的前提。

---

## ② 目标合并文件名 + 命名理由

**`tests/regression_seed_results_sanitize_contract.py`**

理由：四个文件共同守护的是"seed_results 注入时的清洗/净化契约"——去重、坏时间剔除、半残资源冻结、无效 op_id 回填，统称 sanitize。沿用仓库 `regression_*_contract.py` 既有命名风格（见 registry 中 `regression_optimizer_seed_results_contract.py` 等）。不复用任何旧文件名，避免与现存 `regression_optimizer_seed_results_contract.py`（不同被测，是 optimizer 层）混淆。

---

## ③ 每文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

### F1 `test_seed_results_dedup`（1 个函数，内层 `for mode in ("batch_order","sgs")`）
单次 mode 迭代内 **8 条 assert**，×2 mode = 实跑 16 次断言执行：
1. `assert used_params.get("dispatch_mode") == mode`
2. `assert op_ids.count(1) == 1`  — seed 工序只出现 1 次
3. `assert set(op_ids) == {1, 2}`
4. `assert len(results) == 2`
5. `assert summary.total_ops == 2`
6. `assert summary.scheduled_ops == 2`
7. `assert summary.failed_ops == 0`
8. `assert op2 is not None` / `assert op2.start_time is not None` / `assert op2.start_time >= seed_end`（这一组语义上 3 条，源码合并计为末段 3 条）
- seed_end = start_dt + 1h；op_type_name 全 None

### F2 `test_seed_results_drop_duplicate_op_id_and_bad_time`（1 个函数，单 mode=batch_order）
**11 条 assert**：
1. `assert op_ids.count(1) == 1`  — 重复 seed 去重
2. `assert set(op_ids) == {1, 2}`
3. `assert len(results) == 2`
4. `assert summary.total_ops == 2`
5. `assert summary.scheduled_ops == 2`
6. `assert summary.failed_ops == 0`
7. **（坏值/边界·必保）** `assert "重复工序编号" in warn_text` — 逐字中文 warning
8. **（坏值/边界·必保）** `assert "开始时间不早于结束时间" in warn_text` — 逐字中文 warning（坏时间 end<=start）
9. `assert op2_res is not None and op2_res.start_time is not None`
10. `assert op2_res.start_time >= seed_end`
- **关键畸形构造（必保逐字）**：seed_results 三条 = op_id=1 两条（完全相同）+ op_id=2 一条 `start_time=seed_end, end_time=seed_end  # bad time`（end<=start）
- 此文件 op1/op2 的 `op_type_id="OT01", op_type_name="车削"`（与 F1/F4 的 None 不同，是真实差异，需进 parametrize 或独立保留）

### F3 `test_seed_results_freeze_missing_resource`（1 个函数，内层 `for mode` × 2 个 case）
单 mode 迭代内 Case A + Case B 各约 5 条 assert，单 mode = **10 条**，×2 mode = 20 次执行：
- Case A：`seed_machine_id="M1", seed_operator_id=None`（缺人员），op `machine_id="M1", operator_id="O2"` →冻结设备
  1. `assert used_params.get("dispatch_mode") == mode`
  2. `assert summary.failed_ops == 0`
  3. `assert op2 is not None`
  4. `assert op2.start_time is not None`
  5. `assert op2.start_time >= seed_end`（缺 operator_id 仍冻结 machine=M1）
- Case B：`seed_machine_id=None, seed_operator_id="O1"`（缺设备），op `machine_id="M2", operator_id="O1"` →冻结人员
  6-10. 同上 5 条，断言 `seed 缺 machine_id 时仍应冻结 operator=O1`
- seed_end = start_dt + 1h；**用两个 batch（B001 seed / B002 待排）**，与 F1/F2/F4 的单 batch 不同

### F4 `test_seed_results_invalid_op_id_dedup`（1 个函数，内层 `for mode` × `for (tag,seed_op_code,seed_seq)`）
单内层迭代 **8 条 assert**，× 2 mode × 2 tag = 4 次迭代 = 32 次执行：
1. `assert used_params.get("dispatch_mode") == mode`
2. **（坏值·必保）** `assert all(x > 0 for x in op_ids)` — 不产出 op_id<=0
3. `assert set(op_ids) == {1, 2}`
4. `assert len(results) == 2`
5. `assert summary.total_ops == 2`
6. `assert summary.scheduled_ops == 2`
7. `assert summary.failed_ops == 0`
8. `assert op2 is not None` / `op2.start_time is not None` / `op2.start_time >= seed_end`
- **关键畸形构造（必保逐字）**：seed `op_id=0`（无效），两种匹配路径：`("by_op_code","OP1",1)` 与 `("by_batch_seq","",1)`（空 op_code，靠 batch_id+seq 回填）
- **seed_end = start_dt + 2h**（注释：故意给更长时间用于区分"复用 seed"与"重排 op1(1h)"）—— 与 F1/F2/F3 的 1h 不同，是 load-bearing 差异

---

## ④ 共享 setup → 建议 fixture（复用 conftest 哪个 / 缺口）

- **conftest 无可复用项**：本簇四文件均为**纯内存算法测试**，不碰 DB / app / sqlite（grep 已核实零命中 `db_path/db_env/app_client/schema_conn/mem_conn/sqlite/flask`）。conftest 的 7 个 fixture（db_path/db_env/app_client/schema_conn/mem_conn/schema_path/repo_root）**全部用不上**。conftest 的两个 autouse fixture（`_isolate_os_environ` / `_isolate_factory_exit_backup_globals`）会自动生效，无需引用。
- **本簇内部共享 setup**（建议收进合并文件内的本地 helper / fixture，不进 conftest，因仅本文件用）：
  - `_StubCalendarService`：**存在两种签名变体**（见 §10），不可强行合一。建议保留**两个**桩类：`_StubCalendarService4`（F1/F2 用，方法签名仅 `priority/operator_id`）与 `_StubCalendarService5`（F3/F4 用，含 `machine_id` 参数）。或更稳妥：直接保留各 case 原桩，靠 parametrize 传入桩工厂。
  - `_make_batch(batch_id)` / `_make_op(...)`：四文件的 SimpleNamespace 字段集完全一致，可抽一个本地工厂；但 op_type_id/op_type_name 在 F2 非 None，须作为参数。

---

## ⑤ 参数化方案（差异收进 parametrize 的维度）

建议**保留 4 个独立 test 函数**（各自语义清晰、内层循环已是天然参数化），用 `@pytest.mark.parametrize` 仅把"已存在的内层 for"显式化，**不强行四合一**。理由：四种畸形的桩签名、batch 数、seed_end、op_type 字段、断言集（warning/op_id>0 等独有断言）都不同，硬塞进单一 parametrize 会丢断言或引入分支地狱，违反保真铁律。

落地形态二选一：
- **方案 A（推荐，低风险）**：四个 test 函数原样搬入同一文件，仅去重共享的 dataclass 桩（保留两个签名变体）和 batch/op 工厂。断言一条不动。这是最保真的"物理合并"。
- **方案 B（参数化收口，中风险）**：把 F1 的内层 `for mode` 提为 `@pytest.mark.parametrize("mode", ["batch_order","sgs"])`；F3 同理 + case 维度；F4 提 mode×tag 二维。**但 F2 的 warning 双断言、F4 的 `all(x>0)` 断言是该 case 独有，必须留在对应函数内，不可并入公共参数化**。

参数化维度归纳（仅供方案 B 收口时参考，**差异不可丢**）：
| 维度 | F1 | F2 | F3 | F4 |
|------|----|----|----|----|
| dispatch_mode | batch_order/sgs | batch_order | batch_order/sgs | batch_order/sgs |
| 桩签名 | 4-arg | 4-arg | 5-arg(含machine_id) | 5-arg |
| batch 数 | 1 | 1 | 2(B001/B002) | 1 |
| seed_end | +1h | +1h | +1h | **+2h** |
| seed 畸形 | 无(基准) | 重复+坏时间 | 缺资源维度 | op_id=0 回填 |
| 独有断言 | — | warning×2 | 跨batch冻结 | all(op_id>0) |

---

## ⑥ load-bearing import / importlib 引用

**无外部引用，删原 4 文件不会断任何东西。** grep 全仓（*.py/*.yaml/*.yml/*.json/*.toml/*.cfg/*.ini）对四个模块名的命中**只有** `.codestable/refactors/2026-06-01-test-gate-cleanup/summary.json` 一处归档列表（非可执行引用）。无 `import`、无 `importlib`、无 pytest `--deselect` 路径耦合。被测对象 `from core.algorithms import GreedyScheduler, ScheduleResult` 已核实存在（`core/algorithms/__init__.py:13` & `:15`）。

---

## ⑦ registry 影响（tools/test_registry_data.py）

**无。** registry（318 行）对四个文件名零命中（grep `seed_results_dedup/drop_duplicate_op_id/freeze_missing_resource/invalid_op_id_dedup` 全空；`seed` 仅命中无关的 `regression_optimizer_seed_results_contract.py` / `regression_optimizer_seed_boundary_contract.py`）。四文件不在任何门禁清单（QUALITY_GATE_*），靠 pytest 目录收集运行。合并后无需改 registry。
> 旧→新：无。

---

## ⑧ B-COMPAT pin（必须逐字保留禁去重的断言）

源码中**无显式 B-COMPAT/B-pin 标记**（grep 零命中）。但按本簇语义，以下断言是"畸形→预期清洗结果"的逐字契约，**禁去重、禁改写**（事实性 pin，保真铁律覆盖）：

- **B-pin-1（F2 坏时间 warning，中文逐字）**：`assert "开始时间不早于结束时间" in warn_text`
- **B-pin-2（F2 重复编号 warning，中文逐字）**：`assert "重复工序编号" in warn_text`
- **B-pin-3（F4 无效 op_id 不外泄）**：`assert all(x > 0 for x in op_ids)`
- **B-pin-4（F4 双匹配路径，禁合并为单路径）**：tuple `(("by_op_code","OP1",1), ("by_batch_seq","",1))` 两条都必须跑——空 op_code 走 (batch_id,seq) 回填是独立分支。
- **B-pin-5（F4 区分复用 vs 重排的时间锚）**：F4 的 `seed_end = start_dt + timedelta(hours=2)` 不可被统一改成 1h（注释明示：用于区分"复用 seed"与"重排 op1(1h)"，改 1h 会让断言失去鉴别力）。
- **B-pin-6（F3 半残资源双 case）**：Case A（缺 operator_id，冻 machine）与 Case B（缺 machine_id，冻 operator）两条都必须跑，且各自的 op 资源构造（A: op_operator_id="O2"；B: op_machine_id="M2"）禁改——改了就测不到"按现有维度冻结"。

合并时这 6 项逐字保留即满足禁去重红线。

---

## ⑨ 断言条数对账（前总和 → 后预期）

按"源码中 assert 语句条数"（单次循环体内、含末段拆 None/>=seed_end 的多句）：

| 文件 | 源码 assert 语句数（单循环体） | 实跑展开次数（×循环维度） |
|------|------|------|
| F1 | 10（含末段 op2/start_time/>= 三句） | 10 × 2 mode = 20 |
| F2 | 11 | 11 × 1 = 11 |
| F3 | 10（A 5 + B 5） | 10 × 2 mode = 20 |
| F4 | 10（含末段三句） | 10 × 2 mode × 2 tag = 40 |
| **合计源码** | **41** | **实跑 91** |

- **合并前源码 assert 总和 = 41 条**
- **合并后预期 = 41 条（方案 A 物理搬运，一条不删）**；若走方案 B 显式 parametrize，源码 assert 行数可能略降（循环体不变，去掉的只是 `for` 语句），但**实跑展开次数 91 必须 >= 91 不变**。
- 对账结论：**41 >= 41 ✓**（实跑 91 >= 91 ✓）。无任何"逐字完全重复的同义断言"可删——四文件的同形断言（如 `summary.failed_ops==0`）作用在不同畸形输入上，语义不同，**保留**。

---

## ⑩ 风险 / 阻塞点

1. **【真陷阱·必须避坑】`_StubCalendarService` 签名不一致，禁止统一成一个桩。**
   - F1/F2 的桩方法签名是 `adjust_to_working_time(self, dt, priority=None, operator_id=None)`、`add_working_hours(self, dt, hours, priority=None, operator_id=None)`、`add_calendar_days(self, dt, days)`——**无 machine_id 参数**。
   - F3/F4 的桩方法签名**多了 `machine_id` 关键字参数**，且 `add_calendar_days` 也带 machine_id/operator_id。
   - 这反映 GreedyScheduler 在不同 seed 路径下对 calendar_service 的调用方式不同。若合并时图省事用单一桩（比如都用 5-arg 版给 F1/F2），**可能掩盖 F1/F2 路径本不传 machine_id 的契约**，属于行为漂移。结论：**保留两个桩类**（或参数化传桩工厂），不焊死。
   - 同理，`add_calendar_days` 在 F1/F2 是 2 参数（dt,days），F3/F4 是 4 参数——也不可统一。

2. **batch 数差异**：F3 用两个 batch（B001 种子 / B002 待排，验证跨 batch 资源冻结），其余单 batch。合并后 F3 的 `_build_batches()` 须独立保留，不可与单 batch 工厂混用。

3. **op_type 字段差异**：F2 的 op1/op2 带 `op_type_id="OT01", op_type_name="车削"`，其余为 None。若抽公共 op 工厂，须把这两个字段做成参数（默认 None，F2 传入），否则改变 F2 的输入语义。

4. **无阻塞性风险**：无 load-bearing import、无 registry 条目、无显式 B-COMPAT pin、无同名 test 函数跨文件冲突（grep 已核实四个函数名仅各自一处定义）。合并是纯物理可行的。

5. **建议落地优先选方案 A（物理搬运 + 仅去重无歧义的工厂）**，把参数化收口（方案 B）留到合并稳定后单独迭代——降低一次性改动风险，符合"行为保真优先"。
