---
doc_type: issue-fix-note
status: fixed
date: 2026-09-15
scope: master overview process guidance
---

# 资料总览工艺待维护说明

- 现场：5001 资料总览的工艺待维护项统一写“已有的归属和 0 工时都不算人工确认过”，非零工时也被错误泛称为 0；这段话没有说明可执行的下一步。
- 定位：`python3 -m tools.symbol_locator whereis _workflow_confirmation` 与 `callers _workflow_confirmation` 确认唯一产品调用为同模块 `_route`。
- 修复：`master_overview_process._workflow_confirmation` 按实际可进入的步骤分别提示保存工艺路线、保存工序归属、填写并保存工时定额，维护建议使用对应动作。旧模板的路线仍未保存时先说明保存路线，与原有导航目标一致；未保存的确认字段显示“待保存”。同一投影中真正为零的单件工时说明改为“请核对单件工时；确实为 0 时，在工时定额页按 0 保存。”
- 合同：保留 `workflow.ready`、各阶段确认状态及 `operation.zero_review` 判定；已确认的零工时不再报待维护，未确认的非零工时仍需完成原有流程。未改写工时、确认记录或业务数据库。
- 验证：新增 8 组旧模板/路线/归属/工时阶段 × 零/非零数据回归，并加强原有零工时断言，先复现 9 项失败；修复后这些 9 项加已确认零工时与导航合同 2 项，共 11 项定向测试通过（1.86 秒）。测试内核对读取前后数据库逐表数据一致。指定文件 `git diff --check` 通过；同一投影原有保护式文案精确检索无剩余。
- 范围与限制：仅修改 `core/services/workbench/master_overview_process.py` 与已有 `tests/workbench/test_master_overview_reads.py`。未构建、未操作浏览器、未改业务数据库、未跑全门禁或整仓测试；后端统一激活及真实页面复核由主任务安排。已有 dirty 改动保留，未提交。
