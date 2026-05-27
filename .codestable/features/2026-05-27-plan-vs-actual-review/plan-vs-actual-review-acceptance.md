---
doc_type: feature-acceptance
feature: 2026-05-27-plan-vs-actual-review
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: plan-vs-actual-review
accepted_at: 2026-05-27
---

# 计划和现场实际复盘视图验收

## 1. 接口契约核对

- 已新增 `GET /reports/execution-review` 和 `GET /reports/execution-review/export`。
- 未新增 `/scheduler/execution-review`。
- 复盘页第一版只查看“正式采用方案”，实际开始、实际结束、实际资源、暂停时长和异常信息都来自执行状态读模型。
- 导出文件名、工作表名和列名使用 roadmap 固定中文格式。

## 2. 行为核对

- 页面支持按版本、日期范围和批次筛选。
- 页面明细显示计划开始、实际开始、开工偏差、计划结束、实际结束、完工偏差、暂停时长、异常信息、计划资源、实际资源和现场反馈状态。
- 没有现场反馈时，页面和导出都显示“暂无现场反馈”。
- 测试锁住了 `Schedule` 计划行前后不变，避免把实际时间或实际资源写回计划行。
- 报表导航到复盘页时只保留 `version/date_from/date_to/batch_id`，不会把 `plan_role/scenario_id` 带进复盘页。

## 3. 对抗性审核闭环

- 初轮只读调查 4 个 SubAgent：
  - `019e69fa-94e1-77d2-b3c3-f4b2063b9d3c`：报表路由、页面入口、手册入口；结论 OK。
  - `019e69fa-bd36-7670-985b-0bb0d260cbbe`：报表数据和 Excel 导出链路；结论 OK。
  - `019e69fa-ec80-7d83-b66b-29d95cbcf6b4`：执行事件和执行状态读模型；结论 OK。
  - `019e69fb-1b22-76d3-9858-10131ac4523f`：测试夹具和回归写法；结论 OK。
- 第一轮整阶段对抗审查 4 个 SubAgent：
  - `019e6a0b-98d0-7140-b567-46b04248be11`：后端和导出，0 阻塞。
  - `019e6a0b-d615-7491-8c0d-ba50daa5512a`：路由、页面和手册，0 阻塞。
  - `019e6a0c-0fa4-7c90-8599-e12838bf854e`：测试证明力，5 个阻塞；已补跨版本按 `op_id` 读现场事实、导出摘要、入口边界、`Schedule` 不变性和 `write_only` 导出测试。
  - `019e6a0c-47aa-7c93-9e79-6ed886aa8f7a`：跨文件一致性，2 个流程收口阻塞；本验收阶段回写。
- 第二轮整阶段复审 4 个 SubAgent：
  - `019e6a14-b331-7182-b1de-d85865dccb42`：后端和导出，0 阻塞。
  - `019e6a14-fbb7-74d1-bd56-f45b860925d8`：路由、页面和手册，0 阻塞。
  - `019e6a15-3889-7a71-8f43-a2292677fea3`：测试证明力，2 个阻塞；已补日期筛选反例和计划结束断言。
  - `019e6a15-6d49-79d1-bdfc-0203cee6fb78`：跨契约一致性，1 个阻塞；已修复复盘导航不再携带 `plan_role/scenario_id`。
- 第三轮精准复审 3 个 SubAgent：
  - `019e6a1d-f12d-7f81-ac02-872ff985fec0`：整体实现和测试，0 阻塞。
  - `019e6a1e-257d-7cf1-b115-9a53053cce23`：测试证明力，0 阻塞。
  - `019e6a1e-55d0-7b23-8ef6-08080f457fd5`：跨文件一致性，0 阻塞。

最终阻塞项数量：0。

## 4. 验证记录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_plan_vs_actual_review.py tests/regression_operation_execution_event_foundation.py tests/regression_frontend_offline_static_assets.py`：14 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/report/report_engine.py core/services/report/exporters/xlsx.py core/services/report/exporters/__init__.py web/routes/reports.py tests/regression_plan_vs_actual_review.py`：通过。
- YAML 校验、Python 3.8 语法扫描和 `git diff --check` 在最终收口门禁中复跑。

## 5. 文档和路线图回写

- `plan-vs-actual-review-checklist.yaml` 已标记为 done。
- `aps-three-gap-directions-items.yaml` 第 12 项已标记为 done。
- `aps-three-gap-directions-roadmap.md` 第 12 项已同步为 done。
- 架构文档已补充复盘页不携带模拟预览参数的例外口径。

## 6. 遗留

- 未做真实 Win7 x64 / Chrome 109 实机验证；本项通过离线静态资源回归和 Python 3.8 语法扫描约束兼容性。
