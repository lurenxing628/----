---
doc_type: issue-fix-note
status: fixed
date: 2026-09-14
title: 固定列聚焦框与计划说明补充修复
---

## 本轮范围

- 修复批次表格左右固定列遮住整行聚焦框。
- 将交付风险说明“当前工序安排已覆盖”改为“全部工序已安排”。此状态表示该批次全部工序安排齐全，非生产完工。
- 将前后序缺失提示改为“此计划未记录工序顺序。”，数据异常提示为“工序顺序数据不完整。”，详情备用提示为“暂无该工序的前后序信息。”。
- 用户随后提出值班台问题明细展开不好看，明确要求先给方案；该区域本轮没有修改。

## 根因和实施

原聚焦框画在 tbody tr 上，sticky 单元格的背景处于更高绘制层，遮住对应边线。21-table-frame.css 改为各单元格绘制内侧聚焦线，固定列原边界和滚动阴影与聚焦线组合；横向滚动后固定列补左边线。不提高整行层级，表头层级和数据操作保持原样。

文案源为 frontend/workbench/app/PlanDetailsUI.jsx 与 core/services/workbench/plan_process_order.py；同步相关现有测试断言。Python 业务判断和SQL不变。

## 验证

- 浏览器用键盘聚焦真实批次行，确认整行蓝色边框完整穿过左右固定列。
- 横向滚动 327px 后再次核对，左侧固定列补齐左边线，滚动阴影保留，行内容和操作列未被聚焦层遮挡。
- `.venv/bin/python -m pytest -q tests/workbench/test_final_planning_process_order.py tests/workbench/test_plan_delivery.py tests/workbench/test_final_planning_l5_contract.py`：62 passed in 5.24s。
- `.venv/bin/python -m pytest -q tests/workbench/test_shared_controls_widgets.py`：1 passed in 1.97s，包含11个Chrome109共享控件案例。
- `.venv/bin/python scripts/workbench/build.py` 通过；Chrome109，260份资产，build_id `546cd746f4affc07d7a6cfa266a621e3d204322daf851c1144e879f83d87ced1`。
- git diff --check通过。按用户要求未跑门禁、未提交；保留先前所有已授权修复及未提交内容。

## 变更文件

产品：21-table-frame.css、PlanDetailsUI.jsx、plan_process_order.py；构建：对应static CSS/JS与asset-manifest.json；测试：test_final_planning_process_order.py、test_final_planning_l5_contract.py；本记录。
