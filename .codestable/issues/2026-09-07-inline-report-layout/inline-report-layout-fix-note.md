---
doc_type: issue-fix-note
issue: inline-report-layout
date: 2026-09-07
tags: [frontend, prototype, field-reporting]
---

## 问题与原因
用户截图显示行内报工平铺四个输入框，数量预览与工时提示独占整行，补充信息和提交操作分别占行，缺少功能分区且留白松散。主表最右列只有图标而没有表头，入口含义不明确。

## 修复
- `前端设计/ui_kits/workbench/field-report-form.js:23`：行内表单分为产出数量、实际起止、工时核对三个区域，预览信息回到对应区域；历史更正弹窗沿用原布局。
- `前端设计/ui_kits/workbench/field-reporting.css:267`：固定数量区宽度，增加细分隔线；收起的补充信息与完工提交共用底栏，展开后各占整行；收回旧外围内缩并适配窄屏及触摸控件。
- `前端设计/ui_kits/workbench/field-report-views.js:54`：最右列表头增加“报工”。`index.html` 更新对应资源版本。未改数据模型、报工计算、导入、日期组件或后端。

## 验证与边界
布局与响应式 CSS 合同 37 项、行内数量交互 62 项、报工回归 67 项、原导航及值班台回归 149 项均通过；浅深色 4064 处文字检查通过，最低对比度 4.58:1。测试为 JSDOM 原入口及 CSS 检查，浏览器本地文件访问受限，未做截图或像素验收；未运行后端整仓门禁，不构成 clean-worktree proof。

原型目录仍被 `.gitignore` 忽略，修改前备份及 SHA-256 清单保存在 `/Users/lurenxing/.codex/visualizations/2026/09/07/01a079ea-544f-73f0-aef0-d63b087bb017/workbench-before-report-zones/`。本轮另新增 `tests/field-report-layout.cjs`，扩充 `tests/field-report-contrast.cjs` 覆盖分区标题和提示；全部改动未提交，保留原有暂存与其他未提交内容。
