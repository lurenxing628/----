---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-system-page-polish
status: "completed-with-validation-limit"
summary: "系统诊断、分页和维护恢复的呈现及保守状态边界实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- system
- ui
roadmap: workbench-ui-refinement
roadmap_item: wbui-system-page-polish
created: '2026-09-12'
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 系统管理界面验收

1. **接口契约**：未修改 SystemMaintenanceAPI、SystemMaintenanceWorkspace、Python 维护状态机、领域 DTO、数据库或备份恢复逻辑。系统 Pager 显式只接 10/25/50；恢复页普通链接仍访问既有 `/workbench?view=system`，不解除维护守卫。新增依赖为 WorkbenchFormat、WorkbenchReferences、WorkbenchListControls、WorkbenchDensity 与 `styles/37-system.css`。
2. **行为与决策**：正式概况自检默认折叠，诊断改称“导出诊断文件”。UTC checkedAt 用 instant（上海 00:30Z → 08:30）；factory_local 用 dateTime。维护编号、原请求与错误码默认折叠，查询输入仍保留原请求原值。未读取到 host 或 host 读取失败均显示“无法读取维护状态”；已确认停止和重启要求仍明确显示。SystemLive 密度订阅统一 WorkbenchDensity，不保存第二份偏好。
3. **验收场景**：最终源码 `test_system_maintenance_widgets.py` + `test_du_system_restore_contract.py` 为 **2 passed / 27.51s**。其中 Chrome 109 隔离组件覆盖 **95 case、4 个视口/主题组合、41 张截图**，页面错误、外连、原生弹窗均为 0；新增 1280×720 自检折叠/时区和读取失败保守锁定检查。另 `test_du_system_restore_view.py` 与状态合同 **6 passed / 4.33s**；真实冷/热恢复浏览器 **12 passed / 22.49s**；临时 Flask 配置保存/回读 **5 passed**。后者同批早期组件测试曾因改名中的标签超时，恢复原可访问名后组件已单独通过，未将失败日志冒充全通过。深色备份表和暂停恢复页已目视核对。范围内 `git diff --check` 通过。
4. **术语与可访问性**：分页保留“每页数量”“上一页”“下一页”可访问名称；备份、日志及冷维护记录表有 caption/列 scope；禁用原因可内联显示。自检使用原生 details/summary。现场备份文件名和必要操作语义保持可见；技术编号可展开完整核对。
5. **架构归并**：新增外部 CSS 和公共组件消费属于本次统一 UI 层，架构、构建顺序的共同路径由主线程统一回写；本分支没有引入后端架构变更。维护只读响应仍来自 `workbench_system_restore_view.recovery_response`，只改其 Jinja 模板。
6. **Requirement 回写**：本项属于既有系统管理呈现质量，不新增领域能力；全路线图公共 UI requirement 由主线程统一归并，不独立重复建立系统业务需求。
7. **Roadmap 回写**：本分支实现/针对性检查完成；items 与主文档由主线程统一维护。未将最终 built-workbench 验收标成通过。
8. **Attention 候选**：无新增长期规则。保留现有只读恢复、Win7/Python 3.8 和完整软件重启约束。
9. **遗留与证据边界**：此处使用既有静态基座加当前源码覆盖，不是最终生产 build_id；源与 CSS 哈希、结果路径见 `wbui-system-page-polish-evidence.json`。统一构建、1280×720/1366×768/1920×1080 实际工作台和总门禁待主线程。管理样例 SMOverview 自检折叠已移交原型导入 owner，在原型源完成后统一 import，不直接改生成的 prototype。没有运行 git add/commit；工作区原有调度优化等未提交改动不属于本分支。

受影响工作区为 system 及 cold/warm 维护恢复页面。最终版本至少重跑：系统首屏自检展开、诊断下载载荷、系统分页筛选、配置保存回读、恢复 pending/terminal/read-error、返回工作台继续受维护守卫约束。

## 集成反馈补验

首轮全站 DOM 检查发现自检 DataTable 没有输出 caption/scope，已将正式 SystemLive 自检改为本地语义 table（caption、3 个 `scope="col"`、检查名称 `scope="row"`），不用运行时补 DOM。追加这三条浏览器断言后，最终源覆盖探针 **95 case 全通过、41 张截图、0 页面错误/外连/原生弹窗**；结果为 `/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-system-caption-source-vtuf3k8n/system-maintenance-ui-result.json`。复验使用先前临时后端 DTO；当前 pytest 工厂收集遇到其他调度分支的 `native_multi_start_calendar_snapshot` ImportError，未改动该分支。两轮测试装配问题（新增 caption 造成旧宽泛文本选择器重复匹配、统一构建后剔除共享依赖破坏旧消费者加载）已修正，最终源覆盖保留完整静态依赖图，再顺序覆盖待测系统源码。

原型导入 owner 已完成 SMOverview 自检的设计源修改和 `import --update`，并提供 Chrome 109 浅/深色收起与 Enter 展开通过的验证；正式自检仍独立使用 WorkbenchFormat.instant。此补验不替代主线程最终 build_id 与整站门禁。
