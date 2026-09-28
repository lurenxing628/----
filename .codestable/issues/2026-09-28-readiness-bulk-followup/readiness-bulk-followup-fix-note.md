---
doc_type: issue-fix-note
status: verified-related-scope
date: 2026-09-28
issue: readiness-bulk-followup
summary: 修复齐套开关与采用试排不一致、拆批批量删除预览漏检，以及复查发现的实际报工日期误拦截
---

# 齐套规则与批量删除遗漏修复

用户授权修复上一轮确认的两处问题，并要求修复后由一个 sub agent 沿原路径复查。主代理实施；唯一子代理 `readiness_bulk_followup_review` 只读复查，未修改仓库或派生其他子代理。

## 修复结果

| 问题 | 根因与处理 | 回归证据 |
|---|---|---|
| 关闭齐套检查后，普通批次候选排到齐套日前却不能采用，逐件工序仍等待齐套日 | `ScheduleRunState` 显式携带本次齐套开关，断点克隆保留该开关；逐件派工、候选采用和试排共同遵守保存的设置。原始齐套状态和日期不变。 | 普通/逐件、开启/关闭、候选/正式计划两种试排来源，共 8 种组合；逐件依赖与断点 4 种组合。 |
| 数量拆分历史在批量删除预览漏检 | 批量预览改为复用 `require_deletable`，与单条删除和文件替换预览一致。原批或子批有拆分历史时，在预览阶段返回明确原因。 | 原批与子批分别清除需求后，单独选择和混入可删除批次均在预览拒绝，数据库不变；正常批次批量删除仍通过。 |
| 子代理复查发现：先提前完成前序报工，再开启齐套检查续排，正式计划进入试排被旧实际日期阻断 | 试排原来对实际工序也检查当前齐套日期。现在只豁免已由报工校验建立的实际锚点，保持实际时间与资源不可改；没有实际事实的锁定工序不享受豁免。 | 普通/逐件两种完整路径：首次采用、前序报工、开启检查重新排产及采用、试排再次正式采用；实际前序仍保留 9 月 9 日，未完成后序从 9 月 15 日排。 |

开启齐套检查时，伪造提前候选或手动把试排任务调到齐套日前，仍明确阻断；覆盖普通和逐件两种任务。预检查原有“齐套日期晚于本次排产止日时跳过”的边界保留，见使用手册。未改前端组件或样式。

## 子代理复查

- 确认并复现上述第三项后，主代理修复；子代理原样重跑，候选采用成功，试排问题列表为空，保存后的采用预检通过。
- 重复拆分实测：100 → 40/60，再将 40 → 10/30，最终 60/30/10；需求、现货与分次到料总量守恒。
- 复制拆分子批保留用料工序绑定、清空到料且不继承拆分历史；清除复制批次需求后可正常批量删除。
- 静态核对工艺重建的用料绑定保护、多工种资源集合、日历文件复检、默认班次快照绑定；本次已覆盖路径未发现其他确认问题。

复查与复验原始证据保存在 [evidence/readiness-bulk-followup-20260928](../../../evidence/readiness-bulk-followup-20260928/)。原问题修复前工作区快照在 `/tmp/aps-readiness-bulk-fix-before-20260928.json` 与对应 `.tar.gz`。

## 验证

- 最终相关回归：**294 passed in 89.09s**，结果见 `final-related-tests.log`。
- 实际日期保护及齐套反例组：37 passed；断点日历视图回归：4 passed。与最终组有重叠，不相加。
- 首次扩大相关验证为 284 passed / 4 failed：四个失败均来自旧测试临时视图未包含新增 `periods_json` 字段，导致验证停在日历不可读。已补齐临时视图字段，保留原本“业务输入改变则断点签名必须失效”的断言；没有放宽产品校验。
- 修改文件 Ruff、产品文件局部 Pyright（0 errors、0 warnings）、Python 3.8 语法与定向 `git diff --check` 通过。
- 仅运行相关验证；未运行日常或完整门禁，未操作生产数据库，未提交、推送或发布。工作区保留已有改动，不声明 clean-worktree proof。没有新增浏览器验证，本次修改不涉及前端组件。

## 文件范围

- 产品：`core/algorithm_runtime/piece_input.py`、`run_state.py`；`core/algorithms/greedy/run_state_setup.py`；`core/services/workbench/run/candidate_adoption_constraints.py`、`piece_adoption.py`；`core/services/workbench/trial/validation.py`；`core/services/workbench/batch/bulk.py`。
- 测试：`tests/workbench/test_stage_adoption_regressions.py`、`test_batch_split_regressions.py`；`tests/algorithm/test_sgs_explicit_piece_scope.py`；`tests/resource_dispatch/test_sgs_decode_checkpoint_contract.py`。
- 说明：`static/docs/scheduler_manual.md` 与本记录。源码相对本轮起点的哈希清单见 `repair-scope.json`。
