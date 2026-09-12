# 分析与详情域实施记录

## 批准方案与最小合同

- 依据 `implementation-20260912.md` 的已批准修订，修改 Dashboard / MasterOverview 消费层；Report / Review / Calibration 由并行子代理独占，另记 `reports-review.md`。
- 值班台条目和主数据详情消费 `WorkbenchDetailPanel`，父容器两列；条目切换用 `detailKey` 聚焦，关闭保留列表筛选并恢复触发按钮焦点。
- 值班台来源使用结构化字段树，完整来源仍可核对；引用与规则码只在 `details.wb-ref` 内出现。不改源 DTO、领域计数、时间含义和写入请求。
- 值班台分页遵守服务端 1–100，保留恢复上下文中的既有 size；主数据列表支持 20/50/100，详情固定 10。缺失来源与当前过滤无结果分别说明，0 不替代未知。
- 应用 CSS 接管原 Dashboard / MasterOverview 样式；1280 下指标卡换行、筛选不裁切、表格内部纵横滚动且固定操作列，详情不压坏主体。
- 合同测试先锁结构化来源保留零值/未知/数组、引用折叠、分页原值传递和详情关闭回调，再编译及关联 API/浏览器验证。

## 执行与验证

- 已读取项目注意事项、体系总览、`cs-feat` 和本轮并行合同。
- `symbol_locator whereis/callers DashboardWorkspace` 未找到 JS 定义；已用 `rg` 核对 JSX 消费链。
- 没有提交或修改他人暂存内容。全应用最终 build_id 与总门禁由主线程统一集成补齐。

## 已实现

- Dashboard / MasterOverview 消费共享详情、空态、分页、格式化和编号折叠；两份 Styles 的静态 CSS 迁入 `styles/36-analysis.css`，保留空组件导出以兼容原加载器。
- 值班台 `DashboardEvidence.jsx` 按字段和数组呈现完整来源，保留 null/0/false 及所有原引用；检查来源相同的无正式计划提示只显示一次，各来源状态保留在折叠区。
- 主数据和风险清单直接使用有高度预算的 `wb-table-frame` 作为唯一滚动框；表头、关键列、操作列固定。主数据筛选行在 1280 宽度换行，取消原型容器限宽对 1920 的影响。
- 详情使用共享 `detailKey` 和触发按钮焦点恢复。主数据默认自动预览首条时 `autoFocus=false`，不抢走标题与指标首屏；用户点击、明确导航与关联定位仍移入焦点。页签保留 Alt/Ctrl/Meta 浏览器快捷键。
- 值班台分析时间轴增加完整工序定位下拉，键盘可定位虚拟视窗外的工序；提示文本保留业务编号并收起内部引用。

## 验证证据

- `node tests/workbench/analysis_ui_contract.cjs` 通过：结构化来源的零/未知/引用完整性，无裸 JSON pre，分页恢复 size=2、主数据档位与详情固定 10、详情关闭与条目 key、重复来源提示去重、浏览器返回修饰键直通。
- 关联原领域合同：主数据读取/边界、值班台读取/产能/候选/命令，**65 passed（14.69 秒）**。
- `PYTHONPATH=. .venv/bin/python tests/workbench/test_master_overview_browser.py /tmp/aps-wbui-analysis-master-final2`：Chrome **109.0.5414.46**，**71 场景 / 32 张截图 / 0 页面异常**，源码 SHA 校验通过。覆盖 1920×1080、1392×924、1366×768、1280×720 的浅深主题、精确关联导航、全范围导出、失败不替换结果，以及自动预览保留首屏、详情聚焦/Esc 归还、操作列可见。
- `DASHBOARD_UI_OUTPUT=/tmp/aps-wbui-analysis-dashboard-final .venv/bin/python -m pytest tests/workbench/test_dashboard_widgets.py -q`：**2 passed（86.39 秒）**。原完整 4 组交互、8 项边界、4 次重启、原回执与事务证明，以及新增 1366×768/1280×720 浅深主题 4 个只读详情场景通过，源码 SHA 校验通过。
- `DASHBOARD_EXTERNAL_UI_OUTPUT=/tmp/aps-wbui-analysis-dashboard-external-final .venv/bin/python -m pytest tests/workbench/test_dashboard_external_handling_widgets.py -q`：**3 passed（82.86 秒）**。外协处置原完整 4 组交互、9 项边界、20 个拒绝断言、旧完成证据保留、默认编号收起且展开完整可查，源码 SHA 校验通过。
- `tests/workbench/test_dashboard_ui_refinement.py` 单独重跑 1280/1366 只读详情矩阵：**1 passed（7.95 秒）**；工序标题在视口内、操作列右边界不越框、Esc 焦点归还、所有 GET 的数据库表保持不变。此快速入口避免为几何验收重复完整处置写入链。
- `node tests/workbench-app-styles.cjs` 当前全应用样式检查通过，`violations=[]`。本域 `git diff --check` 通过。

## 证据边界与交接

- 原浏览器探针已更新真实源依赖、共享分页含量词文案及结构化详情定位；原领域身份、回执、导出、修订值与事务断言未放宽。编号由“必须常显”改为“默认收起，展开后完整核对”。
- 早期回归曾因共享文件并发变更在最终源 SHA 检查失败，另有外部算法文件改写时的临时 ImportError。上面的最终完整回归已重新通过，未跳过或降低这些断言。
- 交接时再次核对发现这些通过之后 `WorkbenchFormat.js` 又有新改动；本域自有源保持不变。因此三份通过记录绑定其运行时源哈希，主线程最终冻结后需重跑对应受影响浏览器，不能将旧哈希记录冒充当前全部源码证明。
- 浏览器探针直接编译当前业务源并附当前 CSS 哈希，使用主线程统一构建的基础资源；这证明本域当前源，不替代全应用最终构建证据与质量门禁，也不是 clean-worktree proof。
- 报表/复盘/工时校准的独立实现、合法档位、现场零/未知边界和最终证据见 `reports-review.md`。
- 状态：本域实现与针对性验收完成，待主线程全应用终验。工作区保留原调度优化暂存与未暂存内容，未执行 git add/commit。

## 全门禁反馈：旧甘特与资源派工夹具适配

- 根据 `final54-daily-gate.log` 的定向交接，只修改测试夹具和随批准界面合同变化的旧展示期待；不改产品或 registry。
- `gantt_current_runtime.cjs` 补加载真实 `WorkbenchFormat` / `WorkbenchTerms` / `WorkbenchReferences` / `WorkbenchControls` / `WorkbenchListControls`；`useId` 和 provider/context 模拟保留真实 React 元素展开，不允许原始 HTML。
- `h.gantt` 明确传递响应 `meta.as_of`，合成 fixture 使用固定工厂本地时点；不为产品添加时间回退，不改任务几何。`h.styles()` 读取资源清单登记的两份甘特 CSS，原 CSS 断言不再从已迁空的 `PlanLayout` 组件取样式。
- `h.text()` 按浏览器原生 closed details 的可见性只读 summary；完整节点继续保留在 `h.walk()`。新增合同同时锁住默认错误不显示技术内容、展开后原诊断仍完整存在，不能靠删内容通过测试。
- 第一轮完整目录 333 项：328 passed / 5 failed。五项仅是旧展示期待：合并风险图例现分开、null 统一“未知”、小时数固定小数位。定点同步后仍保留身份、原始数据、未知不等于零、错误不泄漏、只读和几何断言，并增加完整图例色块检查。
- 最终命令 `.venv/bin/python -m pytest tests/gantt tests/resource_dispatch/test_resource_dispatch_workbench_lane_contract.py -q -n 4 --tb=short`：**334 passed（83.69 秒）**，退出码 0。最后输出保存于 `/tmp/aps-wbui-implementation-20260912/gantt-fixture-targeted-result.txt`；10 个测试/支持文件的 `git diff --check` 通过。
- 这轮是已有 dirty 工作区上的定点验收，不是全仓 clean proof。没有修改产品、登记表或暂存状态。
