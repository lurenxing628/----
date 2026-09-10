---
doc_type: feature-acceptance
feature: workbench-preflight
status: partial
summary: AM 独占预检块实现与局部验收通过，主壳接线及运行生命周期仍属后续范围
tags: [workbench, preflight, verification]
---

# 本块结论

AM 本轮指定写集实现已完成；不是排产受理/候选持久生命周期完成。接口小块在完整测试结束前已分别交给主代理，AJ 唯一执行投影已实际联调。

## 交付文件

- 模型：`core/models/workbench_preflight.py`。
- 服务：`core/services/workbench/preflight.py`、`preflight_checks.py`、`preflight_dependencies.py`、`preflight_execution.py`、`preflight_facts.py`、`preflight_result.py`。
- 路由：`web/routes/workbench/preflight.py`，提供 `register_preflight_routes(bp)` 和后续事务内重验用的 `resolve_preflight_input(conn,input_ref)`。
- 前端：`frontend/workbench/app/PreflightContract.js`、`PreflightAPI.js`、`PreflightControls.jsx`、`PreflightBatchPicker.jsx`、`PreflightWorkspace.jsx`。
- 验证：`tests/workbench/test_preflight_api.py`、`test_preflight_ledger.py`、`test_preflight_capacity.py`、`test_preflight_browser.py`、`test_preflight_support.py`、`preflight_browser_probe.cjs`。
- 本 feature 的 design/checklist/acceptance；后续 run 方法与既有函数证据见 design。

## 实测

运行命令：

```text
.venv/bin/python -m pytest tests/workbench/test_preflight_api.py tests/workbench/test_preflight_ledger.py tests/workbench/test_preflight_capacity.py tests/workbench/test_preflight_browser.py -q -s
38 passed in 9.69s
```

28项API/原事实测试、8项AJ实际台账联调、1项5000真实批次容量、1项四组合真实浏览器流程。并以替换 `BatchOperation.from_row` 为抛错函数的方式，证明已安装ledger时原始NULL检查也不依赖该旧模型。

浏览器证据目录：

```text
/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-preflight-browser-rlzc0l5p/
```

- `preflight-browser.json`：Chrome 109.0.5414.46；1920-light / 1920-dark / 1392-light / 1392-dark 全部通过；32张截图、48次API请求，其中4次为明确的500错误注入。page errors与外部请求均为0。源文件SHA-256在报告中记录并在测试结束核对。
- `sqlite-proof.json`：临时 `preflight.sqlite` 共49张表逐行内容相同，before/after total_changes均269，检查覆盖成功、空范围、筛选空、失效引用、读取错误。
- 统一日期弹层/下拉、规则检查grid同高、根padding0/max-width:none、无`.plana`样板祖先、跨页选择保留、5000引用POST而非URL、5001引用拒绝均有断言。四组检查页面及日期弹层截图已目视核对。
- `tools.quality_gate_scan.scan_complexity_entries` 与 `scan_oversize_entries` 对本轮模型/服务/路由返回空列表。最初超阈值函数按职责拆分后重跑通过，没有修改门禁阈值或基线。

## 证据边界

1. Flask测试是本块注册函数独立挂载的真实临时应用，不是完整生产启动器；主壳入口、全局请求钩子、主构建包由主代理继续集成与验证。
2. 本轮没有读取生产DB，没有构建正式资产、提交代码或修改既有scheduler/config/schema/plan/batch/ledger/sharedtransport/main/build/global __init__。所有本轮文件仍是未提交内容；已有dirty/staged与他人并行修改保持原样。
3. 未跑整仓门禁：本工作区存在多方并行的大量dirty/staged修改，且本轮写集与禁build边界不覆盖全局集成。这里只提供定点测试、局部结构扫描和组件接真实API的证据，不是clean-worktree proof，也不是Win7真机验收。
4. 日历仍not_evaluated；自动分配只确认待补资源字段，不证明有可用组合。运行按钮完整保留但按真实能力禁用，不调用旧正式run，不生成版本或假进度。
5. `input_ref` 是短期内存绑定，不是持久受理回执。worker、run查询/恢复、候选集持久化及正式采用分离仍未实施，不能通过改一个前端disabled开启。
