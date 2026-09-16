---
doc_type: issue-fix-note
status: fixed
date: 2026-09-14
title: 执行排产页面分区与间距调整
---

## 范围

用户确认实施页面视觉调整，并明确保留七项“未检查”状态。只修改排产页面布局和对应现有浏览器验证，没有改排产规则、接口、业务数据或计算流程。

## 根因与修改

- 原内容区没有独立底色，规则行和检查行统一至少78px，未检查时显得灰且松散。
- `frontend/workbench/app/PreflightWorkspace.jsx` 增加排产范围、规则与检查两个语义分区，原候选排产区保留。七项统计的内容、顺序和初始状态不变。
- `frontend/workbench/app/styles/34-run.css` 设置三个白底区域、细边界、紧凑间距。规则行收紧到56px，检查行至少62px，提示文字按内容占高。没有操作按钮的检查项使用整行宽度。
- 单选项改为独立边界，选中项显示浅蓝背景、蓝色文字和边线，去掉组合控件额外外框。键盘聚焦提示保留。
- 候选排产区在初始状态保持一行，实测58px高；有预览、记录或错误时继续按原内容自然展开。
- 当前步骤的主按钮逻辑原本正确，继续保留，并验证选批次后检查按钮变蓝。

## 验证

- 已先执行 symbol-locator；Python定位工具未收录JSX组件，随后通过源码与实际页面核对组件结构和样式影响范围。仅恢复该工具生成的8份callgraph元数据，起步时这些文件没有修改。
- `.venv/bin/python scripts/workbench/build.py` 通过，Chrome109、260份资产；最终build_id：`b9f4e65a550bfd4af09f68ab03b48a72d3af4677c1ae977bdad9638f22ff9770`。
- `tests/workbench/test_run_job_widgets.py` 通过，覆盖候选排产预览、计算记录等原有流程及4个窗口宽度/主题组合。
- `tests/workbench/test_preflight_browser.py` 最终通过（9.41s），覆盖1920px和1392px、浅色和深色。旧断言要求左右每行等高，与本次按内容收紧布局不符；改为核对列头对齐、各列行不重叠、文字不裁切，并保留无横向溢出、控件宽度及业务交互校验。
- 真实页面确认三块区域白底、1px边界，七个“未检查”均在；规则选中提示蓝色，当前页面无横向溢出。临时选择一批后检查按钮为蓝色，之后已清除临时选择。
- 未在真实数据库启动排产；回归测试使用隔离数据库。git diff --check通过。
- 按用户要求未跑质量门禁、未提交；保留前面所有未提交修改与备份。

## 文件

产品源码：`PreflightWorkspace.jsx`、`styles/34-run.css`；生成资源：对应static JS/CSS、asset-manifest.json；测试：`preflight_browser_probe.cjs`；本记录。

实际页面截图：`/tmp/aps-run-design-audit-20260914/03-run-updated.png`。
