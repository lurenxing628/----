---
doc_type: audit-finding
audit: 2026-06-30-test-suite-redundancy
finding_id: "maintainability-04"
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 04:已核实的"假阳性"清单——存档防误删

## 速答

扫描器报"结构近似重复"的 81 组里,约一半实读后判为 **KEEP(假阳性)**:它们看着像,实则被测对象 / 边界 / 契约确实不同,合并或删除都会损失覆盖。本条把这些**显式记录下来**,防止后续任何人(包括 AI)按"AST 相同 / 结构相似"的扫描结果盲删。

## 关键证据(分类)

### A. 跨文件 / 跨模块同型断言巧合(被测函数根本不同)

- `tests/models_domain/test_normalize_text.py:9 / :15` ↔ `tests/scheduler_graph/test_id_policy.py:108`、`tests/web_pages/test_scheduler_plan_role_arg_contract.py:17` — 三处都是"几条 `assert 函数(x)==值`",但被测分别是纯函数 `normalize_text`、剥前缀的 `display_id`、需 Flask 请求上下文的取参器 `get_plan_role_arg`。**纯骨架巧合 → KEEP**。
- `tests/scheduler_graph/` 的 "import 不连带 networkx" 守卫族(`test_input_adapter.py:257`、`test_nx_runtime.py:13`、`test_precedence_builder.py:239`、`test_metrics_topology.py:41`、`test_validators.py:74` 等)— 每条贴着自己被测模块、守各自的惰性依赖契约,抽公共 helper 反降 locality → KEEP。
- `tests/algorithm/test_optimizer_compare_algorithms_contract.py` ↔ `test_optimizer_smtwt_compare_algorithms_contract.py` 的 invalid/short/failed score 成对用例 — 调用**不同 helper**(`_comparison` vs `comparison`),断言文本巧合一致 → KEEP。
- `tests/candidate/test_scheduler_candidate_reports_contract.py:525` 组里混入的 `tests/gantt/test_gantt_default_version_span.py:149 test_gantt_page_data_url_is_scopeless` 与 `result_status_label` vs `_plan_role_label` — 被测函数 / 断言完全不同的 SKEL 误命中 → KEEP。

### B. 同文件但语义对立 / parametrize 契约不同(EXACT/SKEL 误判)

- `tests/scheduler_graph/test_graph_types.py:82 / :102` — parametrize 装饰器不同(空标识符 vs 非整数),测两套校验 → KEEP(见 finding-02)。
- `tests/schedule/route_view/test_route_version_normalizers_contract.py:71 / :104` — `has_history` 取值相反(无历史 vs 有历史),**文件内已有中文注释明写"绝不可折叠"** → KEEP。
- `tests/gate_meta/test_architecture_fitness.py:83 / :96`、`tests/config/test_config_service_component_contract.py:301 / :405` 等架构 fitness — 扫不同目录、不同正则、不同分层规则,逐条具名是为失败时精确定位 → KEEP。
- 各模块大量"对立分支"组(如 `candidate` health 阈值相邻台阶 score 0 vs 1、`schedule` 降级脱敏 resource_pool vs freeze_window、`scheduler_graph` balanced 越级 vs 拒绝越级)— 断言相反或期望不同 → KEEP。

### C. 新旧 UI 并存(瘦身正解 ≠ 删)

- `tests/app_runtime/test_startup_host_portfile.py` ↔ `test_startup_host_portfile_new_ui.py` — 两个真实并存入口的端到端契约。若嫌两文件辅助函数重复,**正解是把共享的 `_wait_for_*` / `_run_case` 骨架抽到 `conftest.py` 共用 helper,而不是删测试**。

### D. 覆盖重叠、可选去重(保守仍 KEEP)

- `tests/scheduler_graph/test_analysis_service.py:183`(单模块 networkx 守卫)被 `test_scheduler_graph_lazy_runtime_contract.py:13`(一次性导入 12 个子模块的全量守卫)**功能覆盖**。若要极致精简可考虑删单模块版(省 ~18 行),但单模块版定位失败更直观,本审计保守判 KEEP、仅标注重叠。

## 影响

无。本条是"护栏":明确这些组**不是冗余**,避免未来按扫描噪音误删导致覆盖回退。

## 修复方向

无需动作。唯一可选项是 C 类的"抽 conftest 共享 helper"(行为不变),以及 D 类的覆盖去重——都属可做可不做。

## 建议动作

默认无动作、仅存档;若执行 C 类 helper 抽取,走 `cs-refactor`。
