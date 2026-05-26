---
doc_type: feature-acceptance
feature: 2026-05-27-candidate-summary-delta-cards
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: candidate-summary-delta-cards
created: 2026-05-27
---

# 代表三方案摘要卡和总指标差值验收

## 验收结论

已完成。

本阶段把排产优化分析页的方案对比区域从“推荐结论 + 表格”增强成“推荐结论 + 三张摘要卡 + 表格”。三张卡固定对应正式采用方案、原算法代表方案、重点工序优先代表方案，并且每项指标都只和正式采用方案做对比。用户看到的是中文大白话，例如“比正式采用方案多了 3 小时”“和正式采用方案基本持平”“暂无数据”，不是程序里的内部字段或评分串。

## 已落地范围

- ViewModel 给候选方案行补上 `weighted_tardiness_hours`，用于加权拖期展示。
- 新增 `summary_cards` 展示数据，只包含模板需要的中文展示字段。
- 摘要卡展示失败工序、超期批次、总拖期、加权拖期、总工期、换型次数。
- 差异固定以正式采用方案为基准，不提供任意两方案对比参数。
- 模板把摘要卡放在推荐结论卡后、方案表格前，复用本地已有样式。
- 新增/扩展回归测试，覆盖三张卡数量、顺序、缺数据、内部字段不外露、非代表候选不进入摘要卡、模板字段白名单。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_graph_auto_selection_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_analysis_candidates.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_candidate_analysis_contract.py`
- `.venv/bin/python -m ruff check --force-exclude -- web/viewmodels/scheduler_analysis_candidates.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_candidate_analysis_contract.py`

## 子代理复审

- 调查阶段使用 4 个子代理分别检查了候选摘要数据来源、模板和用户文案、测试覆盖缺口、CodeStable 依赖和提交隔离。
- 实现后继续使用多名子代理做对抗性审核，重点检查三张卡是否只覆盖代表方案、差值是否固定相对正式采用方案、模板是否只读取公开字段、是否误把后续执行事件草稿混入本阶段。

## 未做

- 不展示全部 3/5/7 档候选明细。
- 不做任意两个候选方案自由比较。
- 不做批次级影响清单或资源级变化清单。
- 不新增导出。
- 不改排程算法。
- 不改数据库、迁移或现场执行事件。
