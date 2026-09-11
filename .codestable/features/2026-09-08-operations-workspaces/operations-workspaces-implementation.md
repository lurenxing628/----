---
doc_type: feature-implementation
feature: operations-workspaces
status: implemented-awaiting-user-review
date: 2026-09-08
summary: 三个工作台已接入静态入口，数据与交互局部验证通过，等待用户现场验收
tags: [prototype, reports, master-data, system, verification]
---

# 实现与交付记录

## 页面成果
- 执行复盘·报表中心：两个子视图，当前报工、复杂和密集样例分离；同源计算工序完成、偏差关注、记录完整性和已报工时。四种报表为工序、报工记录、设备工时、人员工时。搜索/过滤/排序先于汇总和分页；CSV 导出筛选全量，未知值与 0 分开。工序详情保留原表行、独立报工分页，可回到对应批次的现场记录或同一来源的实际甘特。
- 主数据总览：首次直达初始化唯一基础资料会话，47 个初始实体条目、16 个待维护项、12 个相关实体、39 对已确认关联均由实际样例计算。八个数据域、待维护项/实体两类清单、字段与关系详情、定位维护、CSV；修改和未保存草稿随原生会话保留。1392 宽度详情下置，选择后聚焦详情并可返回原清单按钮。
- 系统管理：概况、备份恢复、运行日志、配置四页签；当前环境和独立管理样例分离。本地检查、当前诊断 JSON、筛选全量样例日志 CSV、日志详情和分页、配置校验预览、主题联动。正式备份/恢复/删除/保存配置/诊断 ZIP 无服务时不可执行。
- 三页使用既有指标条、表格和主题颜色。数据操作靠右，筛选单独组织；非计划页不再展示无关的五月 v3 胶囊。报表跳转独立甘特样例时不再带“正式 v15”假身份。

## 代码边界
| 责任 | 文件 |
| --- | --- |
| 报表计算与视图 | `前端设计/ui_kits/workbench/report-workbench-model.js`、`ReportsScreen.jsx`、`report-workbench.css` |
| 主数据计算与视图 | `master-data-overview.js`、`MasterDataOverview.jsx`、`master-data-overview.css`（同目录） |
| 原生会话快照与维护定位 | `plana-logic.js`、`ProcessNative.jsx`（同目录） |
| 系统计算与视图 | `system-workbench-model.js`、`SystemManagementScreen.jsx`、`system-workbench.css`（同目录） |
| 挂载及窄屏壳层 | `index.html`、`app.jsx`、`AppShell.jsx`、`operations-workspaces.css`（同目录） |
| 报表到甘特的上下文 | `FieldGanttScreen.jsx` 只增加初始来源/批次筛选与来源切换通知；未改图表样式、布局算法或关键链算法 |
| 离线运行资源 | `assets/vendor/`：原 React 18.3.1、ReactDOM 18.3.1、Babel 7.29.0，字节与原 SRI 完全相同，附许可证 |

不修改生产后端、数据库、调度算法、全局设计系统和既有报工模型。三个子代理实际创建成功并已关闭，分别负责报表模型/后台能力、主数据、系统管理；报表界面最终由主代理接手完成，无未完成代理遗留。

## 软件能力核对
| 能力 | 当前源码证据 | 本版处理 |
| --- | --- | --- |
| 正式执行复盘 | `core/services/report/execution_review.py:229` | 固定正式采用身份；原型只读样例，未宣称正式接线 |
| 资源利用率 | `core/services/report/report_engine.py:386`、`core/services/report/utilization.py:95` | 需要日历产能，零产能无比率；本版只展示已报工时 |
| 超期批次、停机影响 | `core/services/report/report_engine.py:170`、`:492` | 报表目录说明已有能力和缺失输入，不生成占位 KPI |
| 零件/工艺/工种 | `core/services/process/part_service.py:367`、`part_operation_query_service.py:26`、`op_type_service.py:60` | 检查当前已加载字段，不把字段齐全称为全局排产就绪 |
| 设备/人员/物料/供应商/日历 | `core/services/equipment/machine_service.py:105`、`personnel/operator_service.py:70`、`material/material_service.py:43`、`process/supplier_service.py:89`、`scheduler/calendar_admin.py:274` | 总览按现有实体关系组织，不增加未实现的 ERP 域 |
| 健康与备份恢复 | `web/routes/system_health.py:16`、`system_backup.py:112`、`system_backup_actions.py:16` | 页面依赖可用不等于数据库健康；危险操作未执行 |
| 两类日志与配置 | `web/routes/system_runtime_logs.py:40`、`system_logs.py:31`、`core/services/system/system_config_service.py:95`、`system_maintenance_service.py:81` | 分开日志来源，沿用配置范围，正确表述请求触发维护 |

使用过实际符号 `whereis/callers` 并复核源码；JS `ReportsScreen` 不在 Python 定位快照中，采用本地文件及入口查证。静态调用图不冒充全量运行时依赖证明。外部参考及采用范围见同目录 design 文件。

## 验证
依赖：本机 `.qa-dom/node_modules` 的 React/Babel/JSDOM，入口运行脚本已改成相同字节的本地资源。所有页面测试读取真实 `index.html`，JSDOM 禁止网络；下载用 Blob 捕获核对，不冒充浏览器已保存文件。

| 检查 | 结果 |
| --- | --- |
| 报表模型与 CSV，`report-workbench-model.cjs` / `report-workbench-csv.cjs` | 55 tests；子代理另验证 UTC、America/Los_Angeles |
| 报表真实入口，`report-workbench-ui.cjs` | 42 checks，3 个 CSV payload；160 工序、140 报工、单工序 55 次报工分页、同源跳转 |
| 主数据模型 / DOM / 会话 | 38 + 67 + 51 checks；首次直达、草稿与保存值隔离、长名分页、空来源和导出 |
| 系统模型 / DOM | 104 + 140 checks，10,000 条记录测试、4 个导出 payload，0 网络请求 |
| 三工作台真实入口与两主题 | 178 checks，首次读取、维护定位、详情返回、主题和数据边界 |
| 十二入口共享样式 | 1497 checks，1338 项文字对比度检查，最低 4.76:1 |
| 业务组件与圆角 | 153 + 486 checks |
| 既有报工入口 | 74 checks；自动完工 9 tests |
| 既有当前关键链 / 复杂甘特 / 工具栏与截止标记 | 177 + 492 + 4940 checks |
| 本地入口资源、JS/JSX 语法、许可证与原始 SRI | 198 checks |

旧样式测试中写死五月 KPI、演示导出 toast 与旧报表结构的断言，已随明确变更替换为当前同源数据与真实导出合同；保留全局 DS 不替换、主题对比度、圆角和其余页面回归。

## 待验与保留边界
- 用户现场观感验收尚未完成。此前真实浏览器访问被拒绝，本轮未绕过；没有截图或像素证明。窄屏断点、结构和对比度验证不等于真实布局验收。
- 仍是 file 原型，不是正式软件前端迁移。批次交期、完整资源日历、停机台账、生产事件、备份和日志接口没有接入；不计算无法支持的利用率、准时交付率、OEE、成本或良率。
- 基础资料原有 DOM-only 临时增删不等于写入源数组，切换子页仍可能恢复；页面明确标注。人员设备操作关系、批次物料需求与正式外协分组未加载。没有扩大为基础资料完整 CRUD 重构。
- 未跑整仓质量门禁；本轮为原型定点模型/DOM/CSS/入口验证，不构成 clean-worktree proof。
- 工作区已有大量修改保留，原暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行未动。没有提交或推送；前端目录仍被 Git ignore，本记录为未跟踪新文件。
- 不自动刷新用户浏览器，避免清空当前报工草稿。页面内修改是会话数据，刷新文件仍会重新初始化。
