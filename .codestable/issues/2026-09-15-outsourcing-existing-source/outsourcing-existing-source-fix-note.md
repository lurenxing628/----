---
doc_type: issue-fix-note
status: fixed
date: 2026-09-15
title: 旧外协工序在正常登记时确认当前来源
roadmap_item: wbfix-outsourcing-existing-source
---

## 根因与修改

旧工序的 `WorkbenchOutsourcingOperationOrigins.batch_ref` 可以为空；这表示没有出生时的批次证据，不表示当前工序没有所属批次。原外协来源读取把两者等同，导致当前批次、零件和供应商关系完整的旧工序也不可登记。

- 保留旧来源表及逐条 lineage 记录，任何查询或登记均不补写历史出生事件、不回填旧空值。
- 按出生记录、首次登记确认、当前完整关系的顺序解析来源。已有出生或登记关系与当前批次实例不同，拒绝继续绑定；同编号替换不能复用旧预览或旧登记。
- 尚无登记且当前批次、零件、供应商、工序成员完整时，普通预检返回 `source_resolution.basis=current_relation`，展示图号和具体批次。确认按钮同时完成登记和关系确认，不增加复核框或旧数据专用步骤。
- 新增独立 `WorkbenchOutsourcingSourceConfirmations` 追加表，保存工序、批次永久引用和首次外协事实引用。时间、人员、原因、源快照复用首次事实。外协单、全部成员、事实、来源确认、命令回执共用既有事务；任一步失败全部回滚。
- 来源解析方式仅进入公开说明和快照，不进入稳定 `source.identity`。首次登记后解析方式改变为 `registration_confirmation`，更正/回厂仍识别为同一登记。
- 新工序继续使用出生记录，四字段 target 输入合同不变；历史登记 DTO 缺少新增可选投影时仍能显示原历史。

## 文件分工

- `core/infrastructure/workbench_outsourcing_source_schema.py`：独立追加结构、严格合同检查、事务安装、首次登记归属和永久记录触发器。
- `data/repositories/workbench_outsourcing_source_binding.py`：来源优先级与已确认事实关联核验。
- `data/repositories/workbench_outsourcing_source_repo.py`、`workbench_outsourcing_repo.py`：完整来源读取、稳定 identity、目标投影与同事务追加。
- `frontend/workbench/app/OutsourcingContract.js`、`OutsourcingControls.jsx`：投影校验、批次/图号/供应商/成员可见，无额外复核入口。
- 新旧来源、界面、图号、值班台测试及对应隔离 fixture：同步“未登记”与“来源缺失”的业务区别。

公共 v32 迁移、`schema.sql` 和当前版本合同挂载由总任务的 schema 集成组负责。旧 v30 fixture 保持原 DDL；当前服务面对缺少新增结构的旧库明确返回 unavailable，不在查询时临时安装或偷偷兼容。

## 验证

所有写入在 pytest 临时数据库；未打开或迁移真实业务数据库，未生成 `static/workbench/`，未提交 Git。

已通过的独立测试组（存在重复覆盖，不累加成独立测试总数）：

- 外协 schema、facts、atomic、identity、api：89 passed。
- 新旧来源、当前图号投影：48 passed；之后补充混合组、同号替换及第二成员写入失败场景。
- 外协新来源、工厂接口、原界面探针：43 passed，包含真实 Chromium 109 表单操作，未进行全局 build。
- 最终扩大验证：旧来源和新来源双路径的 Chromium 109、图号投影、值班台统计及快照测试共 106 passed in 261.69s。
- 最后补充“不能引用另一登记的首次事实”及失败后同键重试后，新来源专项 21 passed in 19.61s。
- Ruff 定向检查、6 个核心新增/变更文件的 Python 3.8 语法解析通过。

界面探针覆盖 1392×924、1920×1080 和深浅主题，检查批次/图号/供应商/成员展示、普通确认保存、回厂更正、丢回执查询、跨重开恢复、过时预览和失败回滚。新旧两种来源都不出现额外确认复选框。旧来源模式逐表比较确认 origins 与 lineage 未改变，并核对来源确认条数等于实际登记成员数。

最终扩大验证命令：

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_outsourcing_widgets.py \
  tests/workbench/test_outsourcing_legacy_source.py \
  tests/workbench/test_outsourcing_targets_labels.py \
  tests/workbench/test_dashboard_external_reads.py \
  tests/workbench/test_dashboard_external_identity.py \
  tests/workbench/test_dashboard_external_snapshot.py
.venv/bin/python -m pytest -q tests/workbench/test_outsourcing_legacy_source.py
```

最初扩大组遇到两个旧合同断言失败：v30 缺新增结构仍要求 loaded、缺出生信息仍要求来源缺口。已分别改为明确 unavailable（不动 frozen DDL）、完整当前关系可登记但未登记风险保持未知；上述最终组已复测通过。浏览器证据保存在 pytest 临时目录，测试内完成读取与逐项验证；临时目录会被并行测试清理，不把临时路径作为长期交付链接。

工作区起步已有大量改动。本记录仅证明本子任务的当前工作区定向验证；最终构建、完整质量门禁、真实页面全量手动复验由主任务统一完成，不声称 clean-worktree proof。
