# 锚点漂移备忘（2026-06-05 晚 · 入库提交之后）

> 执行批次（ROOT→A→B→C→D）前必读的增量备忘。本文记录「phase4 分析定稿之后、产物入库推送之时」工作区发生的全部代码改动对债务锚点的影响。核验人：owner 会话 2026-06-05 晚，逐锚点 grep 回盘。

## 一、基线澄清（最重要）

phase4 四层分析（含全部 dossier 对抗核验附录）是在**已包含工作台 item8 + 复审修复全部改动的工作区**上做的（证据：R08.md:41、LB05.md:182 明确记录"工作区有未提交改动"并按其回盘）。这些改动后被原样提交为 `6759b0f9`。**因此提交本身 = 分析基线，零漂移。**

已抽验逐字命中的锚点（2026-06-05 晚复核）：R09 context.py:28（调用 :96/:97/:107/:258/:271/:272）、viewmodel:33（调用 :257/:258/:353）、收口点 operation_execution_scope.py:9、R15 provider `if not text` :87、R54 collar build_workbench_plan_context :187、LB08 scheduler_public_errors.py:167、R24 禁区行 helpers.py :101/:127/:144。

## 二、分析后真实增量：3 个门禁修复提交（3e2d4678 / e1eccacd / 9983f3d3）

### ⚠️ 1. R09/R08 区域：tokens 模块换了地址（唯一路径级漂移）

- `core/services/scheduler/resource_dispatch_execution_tokens.py` → **`core/models/resource_dispatch_execution_tokens.py`**（git mv 100% 同体，函数体零改动；起因：viewmodel import 它违反"viewmodel 只许 core.models*"门禁）。
- 受影响引用（按旧路径 grep 会落空）：`_layer2_residual.md:37`（R09 Optional-5 清单）、`dossiers/_newdebt_parse-except.md:44`（`:13-18 _positive_int_text` wrap re-raise，行号仍准、目录已变）、`dossiers/R08.md:148`。
- **对 R09 修法零影响**：该副本本就是"已收编 wrap re-raise"终态，不在待收编面里；待收编三处（service:24 / viewmodel:33 / persistence_errors:13）全部未动。利好：wrap 副本现与收口点同住 core/models，收编 import 拓扑更扁平。
- 同步改的 3 个 import 点：viewmodel:23、context.py:13、regression_operation_execution_event_sequence_contract.py:17（均为单行替换+ruff 排序，未位移 `_positive_int` 锚点，已验证）。

### 2. LB02/LB05/R62 宿主 execution_review.py：行号整体上移 ~17，语义零损

- 删除 `_public_report_datetime`（原 :75-89，item8 新增的中文时间格式化，自带"时间记录异常"静默兜底）+ `_display_time` 恢复 ISO 口径（复审回退，详见提交 9983f3d3）。
- **五处 ROLE_ADOPTED 硬钉一字未碰**，新坐标 = dossier 记录过的"今晨"坐标：`:58`（不变）/ `:163` / `:174` / `:204` / `:219`（dossier 旧值 :180-181/:191-192/:221/:236）。签名 `execution_review` :209→**:192**，xlsx :247→**:230**，`get_execution_state_for_scopes` :206→**:189**；R62 锚 `_execution_review_row` →**:284** 起、`_resource_pair_payload` →**:392** 起。
- 被删函数不在任何债务登记内（LB05.md:182 仅将其列入"工作区非注释改动"盘点）；删除属灵魂线正向（少一个静默兜底），并缩小了承重宿主附近的逻辑改动面。G05 批次单元（补注释）修法不变。

### 3. R43：wrapper 契约测试 +12 行（零影响）

- `regression_scheduler_wrapper_import_order_contract.py` 注入隔离 `APS_DB_PATH`（修测试对宿主机本地库的依赖）。dossier 钉的 :12-22/:63/:83 整体下移 ~12 行。R43 裁定执行时**整文件删除**，此漂移随之消灭。

### 4. 零债务交集改动

`scheduler_analysis_trends.py`（build_trend_rows 拆分）、`scheduler_week_plan_response.py`（导出文件名口径回退）、`tools/quality_gate_shared.py`、`regression_scheduler_candidate_week_plan_contract.py`——四者均不在任何 dossier 锚点中（已 grep 验证）。

## 三、对执行批次的指令

1. **38 项 owner 裁定、批次序（ROOT→A→B→C→D）、H 边、原子簇划分全部不变。**
2. R09 单元执行时，Optional-5 清单中 tokens 副本按新路径 `core/models/resource_dispatch_execution_tokens.py` 回盘。
3. G05（LB02/LB05 注释）按符号定位五硬钉，行号用本文 §二.2 新坐标起步、仍须现场 grep。
4. 其余一切照旧：档案行号一律视为待复核，动手前独立 grep 回盘。

## 四、另一处环境事实（非债务，防误判）

本地 `db/aps.db` 是"SchemaVersion=19 但表结构停在旧契约"的半截迁移活标本，会被 v19 fail-fast 契约拦住应用启动——**这是护栏正确行为**。执行批次跑回归时若见 `MigrationContractError`，用隔离 `APS_DB_PATH` 或重建本地库，**禁止放宽迁移契约**。
