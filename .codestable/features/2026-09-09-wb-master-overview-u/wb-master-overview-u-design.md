---
doc_type: feature-design
feature: wb-master-overview-u
status: approved
created: 2026-09-09
summary: 代理U实现八域主数据总览，只读原始事实、精确关系定位及同范围导出
tags: [workbench, master-data, readonly]
roadmap_item: wb-master-overview
approval_basis: 本轮用户明确授权直接实现，主代理统一挂载与build
---

# 范围与依据

- 覆盖样板 WBP-MD-001..008，依据当前可达 MasterDataOverview.jsx / master-data-overview.js，不解析DOM，不搬不可达legacy选项。
- 八域为零件、工艺路线、工种、设备、人员、物料、供应商、显式全局日历。路线是拥有模板工序或非空原始路线的零件的派生视图，沿用该零件永久ref，靠domain区分；不在GET分配路线身份。
- 只写 master_overview* / MasterOverview* 专属代码、测试和本目录。共享入口、schema、main、build、__init__与其他代理文件只读。不commit/build/spawn；staged不动。

# 合同

- `register_master_overview_routes(bp)` 注册 `/api/workbench/v1/master-overview` 的 GET 列表、`/entities/<domain>/<ref>`详情、`/locate/<domain>/<ref>`关系定位、`/export`CSV。
- 查询采用单个JSON `scope`：view、domain、status、query、sort、direction、size、column_filters。分页参数`page`不改变范围；详情另用`section`和`detail_page`。未知/重复字段明确拒绝。
- 整个事实集合在同一SQLite事务中读取并指纹化。分页、详情、关系定位、导出都要求原snapshot_ref；列表第一页允许明确重新读取。内容或范围变更拒绝，不静默刷新。
- 关系定位先验证原scope/snapshot，再切到目标domain的实体全清单，返回目标真实页码和新scope/snapshot；按永久ref找，不按编号/名称。不是从当前页数组找对象。
- 详情字段包含source、value、state；0、空值、非法值分开。已检查仅表示本次明确检查项未见异常，不是整体健康或可排产证明。
- 缺来源时domain count=null；部分可读总数明确为已读取数量。关系的已知条数与完整条数分开。显式技能不等于设备授权；供应商旧单工种与显式能力取并集但核对类别；批次物料需求不当库存预留或齐套证明。
- CSV对全部筛选结果生成，不截当前页；含BOM、公式保护、规则/证据或状态/计数列，snapshot与行数通过响应头核验。

# 导航与集成

- `window.MasterOverviewWorkspace({onNavigate, initialContext})` 自建只读API；不需要主代理修改共享transport。
- 本轮协调后旧domain/node/entity_kind导航合同撤回，统一 `onNavigate('process', {source:'production', kind, entity_ref, category?, stage?, template_operation_ref?, template_external_group_ref?})`。kind=material/op_type/machine/operator/supplier/part，工种带真实category=internal/external。route用kind=part与零件永久ref；模板工序ref不冒充批次工序ref。
- 日历使用 `{source:'production', kind:'calendar', month:'YYYY-MM', date:'YYYY-MM-DD'}`，month按已存在显式日期取值，date作为精确日定位扩展；不补建日历配置。
- `onNavigate('batches', {entity_ref})`，不传batchIds。用户已确认批次入口接好。
- ResourceLive/ResourceWorkspace/ProcessWorkspace精确上下文由用户另派代理贯通；按kind/category选域，按ref读详情，按stage和模板ref定位。目标消失必须报错，不按同号重建记录替代。
- basedata自身initialContext支持`domain`+`entity_ref`精确定位，未知目标显式失败。
- 主代理后续挂载顺序：共享React/资源控件/transport -> MasterOverviewContract.js -> MasterOverviewAPI.js -> MasterOverviewStyles.jsx -> MasterOverviewTable.jsx -> MasterOverviewDetail.jsx -> MasterOverviewWorkspace.jsx；再注册路由/替换basedata入口，最后统一build。

# 验收

- 仅临时真实SQLite和独立mock浏览器。无生产数据读取/迁移/补配置。
- 后端覆盖真实八域、缺来源、坏引用、删除重建、0/未知、长中文、跨页/列筛选、CSV全量和无写入。
- Chrome109在1920x1080与1392x924的浅/深色测试、截图、溢出检查；独立编译仅在测试内存，不生成共享build。
- 全仓为已有dirty worktree；局部验证不称clean-worktree proof。共享挂载、整仓门禁和主构建由主代理完成。

# 交付源码清单

```text
core/models/workbench_master_overview.py
core/services/workbench/master_overview.py
core/services/workbench/master_overview_calendar.py
core/services/workbench/master_overview_facts.py
core/services/workbench/master_overview_graph.py
core/services/workbench/master_overview_process.py
core/services/workbench/master_overview_relations.py
core/services/workbench/master_overview_resources.py
web/routes/workbench/master_overview.py
frontend/workbench/app/MasterOverviewContract.js
frontend/workbench/app/MasterOverviewAPI.js
frontend/workbench/app/MasterOverviewStyles.jsx
frontend/workbench/app/MasterOverviewTable.jsx
frontend/workbench/app/MasterOverviewDetail.jsx
frontend/workbench/app/MasterOverviewWorkspace.jsx
tests/workbench/test_master_overview_support.py
tests/workbench/test_master_overview_reads.py
tests/workbench/test_master_overview_boundaries.py
tests/workbench/test_master_overview_browser.py
tests/workbench/test_master_overview_browser_harness.cjs
tests/workbench/test_master_overview_browser_probe.cjs
.codestable/features/2026-09-09-wb-master-overview-u/wb-master-overview-u-design.md
.codestable/features/2026-09-09-wb-master-overview-u/wb-master-overview-u-checklist.yaml
```

# 最终局部验证

- `.venv/bin/python -m pytest -q tests/workbench/test_master_overview_reads.py tests/workbench/test_master_overview_boundaries.py`：32 passed，实际Python 3.8、独立临时文件SQLite。
- `.venv/bin/python -m tests.workbench.test_master_overview_browser /tmp/aps-master-overview-u-delivery`：35场景全通过，16张截图；只在内存编译当前组件，未触发共享build。浏览器通过mock HTTP读取独立夹具，不能冒充生产数据库联调。
- `.venv/bin/python -m ruff check core/models/workbench_master_overview.py core/services/workbench/master_overview*.py web/routes/workbench/master_overview.py tests/workbench/test_master_overview*.py`：全部通过。
- `.venv/bin/python -m pyright --pythonversion 3.8 core/models/workbench_master_overview.py core/services/workbench/master_overview*.py web/routes/workbench/master_overview.py`：0 errors / 0 warnings；未升级工具或依赖。
- 规模案例：新增2500台设备，加原31台，共2531条设备全量CSV；工种关联2533项；末页和全部导出一致，读取SELECT数量小于80，不逐对象查询数据库。
- 证据目录：`/tmp/aps-master-overview-u-delivery/`。`master-overview-result.json`包含当前UI源码SHA-256、浏览器版本、逐场景结果、网络请求、几何测量、截图和下载记录。
- 代表截图：`1920x1080-dark-overview.png`、`1392x924-light-overview.png`；四个尺寸/主题组合另有实体导出、跨页关系定位与长中文路线截图。
- GET开启query_only验证，全部业务表和身份表前后逐行一致；未补配置、未分配持久身份。旧scope/ref、跨页及导出失效均明确拒绝。
- 同一批次同一物料的多条需求保留各条诊断，不合并丢证据；内部行号仅参与私有诊断散列，不进入public字段或导航。
- 无效日期、未知工种类别仍作为真实缺项展示，但target带unavailable_reason，不派发猜测导航。
- 已向代理Z同步唯一导航合同；没有设备组/班次catalogkind目标。kind/category、stage和模板ref的最终跨页面联调属于主代理与Z的接入步骤。
- 本轮23个新文件全部未暂存；原有staged文件未操作。不commit、不统一build、不新建代理。Win7真机、共享main挂载、真实目标页面导航与整仓质量门禁未运行。本证明仅覆盖上述局部测试，不是clean-worktree proof。

# 主代理接入顺序

1. 前置已有React、foundation图标/APSWorkbenchUI、resource-contract.js、ResourceControls.jsx、transport.js。
2. 六个UI按上方清单顺序加入正式build-order（当前可先pending_live）。没有新的CSS、库或运行时文件。
3. 由主代理在现有workbench blueprint调用register_master_overview_routes(bp)，不增加数据库迁移。
4. basedata挂载MasterOverviewWorkspace并传onNavigate、initialContext。导航采用第3节唯一合同，切换页后的精确定位由目标组件处理。
5. 主代理统一build，再做已集成临时库跨页联调和整仓门禁；U未修改这些共享入口。
