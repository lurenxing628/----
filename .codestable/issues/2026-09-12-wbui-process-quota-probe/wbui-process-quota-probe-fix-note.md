---
doc_type: issue-fix
slug: wbui-process-quota-probe
status: fixed
created: 2026-09-12
summary: 补齐工序工时浏览器探针的私有编译依赖，并按当前页面定位导入冲突提示。
tags: [workbench, browser-test, process-quota]
---

# 工序工时浏览器探针收口

`test_process_quota_widgets.py` 在等待校准详情样本组时失败。已有失败输出包含 React #130；测试私有源码清单遗漏了详情页现在使用的 `WorkbenchDetailPanel.jsx`，页面因缺少组件而无法渲染，并非样本分组被折叠。补齐该依赖及打开样本详情所需的 `ReportEvidence.jsx`，只修改 `process_quota_widgets_probe.cjs`，不改产品。

为直接验证此处的业务边界，每次采用前检查三个样本分组可见，并将 DOM 的 `sample_ref` 列表逐组与真实详情 API 对照。11 次检查均为有效样本 5、排除样本 0、未绑定样本 1；另保存首个详情的截图、HTML 和文本。

随后导入漂移场景的提示改为在对话框正文中定位，避免页面内重复提示造成严格定位失败；确认按钮使用当前确切名称，并保留禁用状态及禁用原因断言。原 409、`committed: false`、数据库、请求和采用后的数据校验均保留。

## 验证

- 原仓运行完整 `tests/workbench/test_process_quota_widgets.py`：**1 passed / 28.33s**，Chrome 109。
- 8 组场景、8 次刷新、19 个合同拒绝、原有 36 张截图全部完成；五类边界结果均通过，浏览器错误和外部请求均为空，服务确认停止。
- 使用当前源码私有编译与真实 HTTP/SQLite，67 个源码散列核验通过；这不是全局 build 或 clean-worktree proof。
- Node 语法检查及 diff 空白检查通过；未修改两个正在运行的验证副本，未暂存或提交 root 内容。

证据位于 `/tmp/aps-wbui-implementation-20260912/process-quota-probe-closure/`：`final-evidence.json`、`tests.log/xml`、窄范围 `scope.patch` 及 `evidence/calibration-detail.png/html/txt`。最终探针 SHA-256 为 `377ef40a81a5aa8b1697e0c2884bfbed2cab3d3e69a43d938643a2673dfc017b`。
