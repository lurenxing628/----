---
doc_type: issue-fix-note
status: fixed
date: 2026-09-14
title: 值班台外协问题明细改为紧凑表格
---

## 本轮范围

用户认可内嵌表格方案后，将值班台展开的问题明细由项目符号列表改为紧凑表格。默认收起，同一原因只说明一次；外协工序显示“工序编号、工序名称”两列，表头加五行的高度，其余内部滚动。没有增加抽屉或无实际作用的操作按钮。

用户随后询问概览卡片两行之间是否需要横线、批次进度条的颜色。这两项本轮只解释和建议，未修改：建议横线与已有竖线同色同粗；现有进度条底槽由浏览器绘制，已完成部分使用 --ui-success（#16a34a），0/4 时未显示绿色填充。

## 实施

- `core/services/workbench/dashboard_external.py`：外协未登记工序的问题条目增加可选 operation 对象，分别传递已有 business_code 与 label。没有拆解拼接文本，没有增加查询或修改数据库。
- `frontend/workbench/app/DashboardContract.js`：校验新增可选工序明细字段；非工序问题仍使用原有 subject。
- `frontend/workbench/app/DashboardPanels.jsx`：按原因分组的表格；工序两列，其他来源为“相关记录”单列。所有条目保留，默认折叠。
- `frontend/workbench/app/styles/36-analysis.css`：32px 行高、192px 滚动容器、固定表头、细横线分行，长内容省略并保留 title。
- 已同步构建 static 资源和 manifest。

## 验证

- `.venv/bin/python scripts/workbench/build.py` 通过，Chrome109、260份资产；build_id 为 `61c9697f7660f75694a070128af9a314af27b2c273f767edcc577f071748e6d6`。
- 定向测试涵盖 `test_ui_refinement_reports_review.py`、`test_dashboard_external_reads.py`、`test_dashboard_external_identity.py`、`test_workbench_visual_controls.py`，共40项最终通过。首次39项通过，新增折叠测试误把 Chromium 的隐藏布局矩形当成可见内容；改为检查折叠状态及实际占用高度后，该项重跑通过（2.37s）。
- 后端测试核对编号、名称及原缺失状态；前端测试涵盖带括号的独立字段、相同原因只显示一次、通用记录保留、10行两列、默认折叠、五行可视区、底部记录可达。
- 真实 localhost 页面核对：默认折叠高度约52px；展开后容器192px、行高32px、10行两列、scrollHeight352px；内部滚动到160px后第10条底部与容器底部重合，表头顶部与容器顶部重合。
- 生产模式本地服务已重新启动，监听127.0.0.1:5000。
- Ruff与git diff --check通过。按用户要求未跑质量门禁，未提交。保留之前所有未提交修改及启动修复备份。
