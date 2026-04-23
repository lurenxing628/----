## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [x] 校验三份审计文件的结构与主张范围  `#review-1`
- [x] 逐条复核高风险源码链路  `#review-2`
- [x] 补充现有回归脚本断言级证据  `#review-3`
- [ ] 形成详细审核结论与修正建议  `#review-4`
<!-- LIMCODE_TODO_LIST_END -->

# 静默回退审计文件复核计划

## 目标
对以下三份文件进行事实复核：
- `audit/2026-03/20260331_core_静默回退_inventory_methods.csv`
- `audit/2026-03/20260331_core_静默回退_inventory.json`
- `audit/2026-03/20260331_core_静默回退审计.md`

## 复核原则
1. 逐条对照源码，不凭直觉。
2. 对文档中的关键断言，至少给出源码位置与行为链说明。
3. 能找到现有回归/冒烟脚本时，补充“脚本断言级证据”。
4. 明确区分：
   - 代码事实为真
   - 代码事实基本为真但表述过度
   - 代码事实为真但风险分级需调整
   - 当前证据不足，需要运行时验证

## 复核步骤
### 1. 主清单结构校验
- 校验 CSV 与 JSON 的条目数量、编号范围、字段口径是否一致。
- 校验 `line_start/line_end/line_range_text` 与源码定义范围是否大体对应。

### 2. 高风险条目源码复核
优先复核以下高风险链路：
- `RouteParser.parse`
- `ExternalGroupService._apply_separate_mode`
- `load_machine_downtimes`
- `extend_downtime_map_for_resource_pool`
- `build_resource_pool`
- `_safe_load_schedule_map`
- `dispatch_sgs`
- `auto_assign_internal_resources`
- `build_dispatch_key`
- `normalize_seed_results`
- `_run_schedule_impl`
- `schedule_summary` 观测链

### 3. 中低风险条目抽样核验
- `_helpers.py`
- `enum_normalizers.py`
- `config_snapshot.py`
- `system_config_service.py`
- `calendar*.py`
- `gantt_*.py`
- `database.py` / `backup.py` / `transaction.py` / `manager.py`

### 4. 现有脚本/回归测试证据复核
重点阅读：
- `tests/regression_scheduler_analysis_observability.py`
- `tests/regression_sgs_scoring_fallback_unscorable.py`
- `tests/regression_seed_results_drop_duplicate_op_id_and_bad_time.py`
- `tests/regression_auto_assign_empty_resource_pool.py`

### 5. 输出审核结论
按以下维度给出结论：
- 台账准确性
- 代码行为准确性
- 风险定性准确性
- 表述是否过度
- 仍待运行时验证的点

## 预期输出
- 一份详细中文审核意见，包含：
  - 已证实为真的条目
  - 需要修正的条目
  - 审计报告中“描述正确但措辞过重/过轻”的部分
  - 建议补做的运行时验证脚本清单
