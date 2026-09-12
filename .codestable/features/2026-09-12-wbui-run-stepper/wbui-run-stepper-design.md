---
doc_type: feature-design
slug: wbui-run-stepper
status: approved
created: 2026-09-12
feature: 2026-09-12-wbui-run-stepper
roadmap: workbench-ui-refinement
roadmap_item: wbui-run-stepper
summary: 执行排产流程与呈现整改
tags:
- workbench
- ui
---

# 执行排产流程与呈现整改

用户已批准 UI 路线图并行实施。本项只消费现有前端 DTO，不改排产计算、正式采用、请求重放与未知结果的业务边界。

- 排产页显示“选批次与窗口 → 检查 → 计算”步骤条。选择有效范围前主操作引导选批；范围有效后检查为主操作；检查通过后计算为主操作。已核实检查的参数发生变化时，立即失效并明确提示重检。
- 批次选择器增加交期、优先级，继续使用批次 API 的 20/50/100 档位。排产历史保持原有 10/20/50 档位，候选目录保持自身分页合同。
- 运行阶段直接消费 queued/computing/awaiting_reconciliation/finished，中文显示并按服务端时间给出已耗时。页面不可见时暂停计时刷新，不据耗时推断完成或可行性。
- 候选预览仅“采用方案”是主操作；所有确认、pending 恢复和原请求键核实流程保留。内部引用收进 details.wb-ref，无障碍名称以批次和工序描述替代哈希。
- 各域内嵌样式迁入 styles/34-run.css，统一字号、层级和颜色令牌。表格使用内部滚动预算、caption/scope；候选虚拟明细提供真实表头语义，Canvas 保留全量键盘选择并处理空轨道。
- 复用 WorkbenchFormat、WorkbenchListControls、WorkbenchReference；修改源文件后由主线程统一构建并作浏览器/整仓验收。

验证：新增运行步骤状态/阶段耗时合同；运行现有 preflight/run job/candidate/adoption/history 相关测试或适用子集。静态合同与源码行为验证不冒充当前构建截图或 clean-worktree proof。
