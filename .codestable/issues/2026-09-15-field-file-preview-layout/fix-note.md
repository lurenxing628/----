---
doc_type: issue
slug: field-file-preview-layout
status: fixed
created: 2026-09-15
related_roadmap: workbench-manual-remediation
validation_status: source-checked-manual-pending
---

# 报工文件预览超出矮屏

手动验收代理在隔离实例 5002、1186 × 768 Chrome 窗口打开“现场记录 → 报工文件”，预检 18 行 XLSX（新增 1、空白 17）时发现：标题被裁到视口上方，取消和确认导入位于视口下方，鼠标无法点到；实际导入通过键盘 Tab 到确认按钮后完成。截图由该代理以内联 CUA 图像提供，未保存图片文件。

根因：`FieldFiles.jsx:26` 的正文只有 `.modal-b`。共用 `ResourceControls.Modal` 提供头、正文、尾的结构，但基础 `.plana .modal` 没有高度预算。工艺、批次等工作区已有专属 flex 限高规则，现场页缺少相同约束，长表格把整个居中的弹窗撑出视口。

修复仅在 `frontend/workbench/app/styles/35-field.css:50` 增加现场工作区直接子弹窗的规则：遮罩边距与弹窗最大高度使用相同 `--space-4`；弹窗列向 flex，头尾不收缩，正文允许收缩至 0 并滚动。共用表格的滚轮传递规则继续有效。没有修改 JSX、文件读取、预检、事务、确认条件、焦点管理或真实业务数据。

验证：新增样式段通过现有 `tests/workbench-app-styles.cjs` 的 `checkSource` 和变量检查，`git diff --check` 通过。完整 `35-field.css` 仍有本轮之前已存在的第 24 行 `!important` 放置规则违规；删除本轮新增段后违规列表完全相同，未将其算作本轮通过，也未扩大修改范围。

本次是局部样式检查，没有运行全门禁、全局构建或浏览器。需要主代理构建后在同一矮屏和长预览上手动确认标题、页脚保持可见，正文滚轮可到最后一行。
