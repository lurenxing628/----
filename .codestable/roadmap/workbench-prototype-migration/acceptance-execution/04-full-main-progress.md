# E 完整入口当前进展

本次只更新已完成实施的事实与证据，不重开已修审计。旧 build 64b6 的六项差额不再作为当前待修清单；失败历史原样保留。69 族内部动作的 B/K/P 正在逐项映射，Main V 独立登记，不把一个成功动作扩大为整族通过。

## 当前固定来源

- 当前交接为 `08-b252-handoff.json` 的 sealed06：source aggregate `2d6c6f12a3b2496d791cd9eb6f846b4dd26260facc334d568a68166561cff1d5`，6532 files；完整资产 build `86bae55877b7574a7dbccad0a61c2f4b714a3105500908d614b531ae31f90a2e`，223 files / 315 inputs，Chrome 109。
- 当前证据底本 E03 指 `/private/tmp/aps-final-e-sealed-read-after-20260911-03/all-final-01`。06 与 03 的清单差异恰为两份 E 测试脚本，全部产品、模板、资产输入相同，见 `source-delta.json`。以下 E03 证据按同产品版本使用，不冒称在 06 再次完整重跑。
- E03 完整组实际为 **51 passed / 2 failed / 414.16s**；两项失败为旧 token 预期和未知 ref 测试写 history 的同步问题。修正测试后 E06 定向 **9 passed / 110.82s**，不能合写成一次完整组 53 passed。详细过程在 07。
- E03 `aps-workbench-live-e_qv_gk0/final-reports-proof.json` 已重新完成五专题、四目录、四状态和 56 个真实 CSV/XLSX 的原字节/SQL/身份/元数据核对及真实重启。Field 四表写入、Calibration 五表采用及旧行/原回执保留也通过当前完整入口。
- 产品、sealed source、manifest、资产已停止写入。Main 已独立核对 sealed06 与现行产品目录无差异，由 B 复制 6532+223 继续 252；B252 结果仍由 Main/B 给出。本任务不为统计重新抓 moving 产品。

## 早期构建历史

- Main 提供完整构建 `69ab1c53713a21acffe9810a3311ddf79538d4adeb1f86955ef272c0463372d8`：215 files、307 inputs。E 逐项校验后复制到 `/tmp/aps-final-e-stable.L5TV52/full-build`，完整主入口而非单挂组件。
- 其后 `frontend/workbench/app/PlanWorkspace.jsx` 于 `2026-09-10T12:39:44.892Z` 改变，旧指纹 `4b3b06b0abdc33737c7a3f06cf22f918e857b72cceeb42897384842697c4f8e6`，新指纹 `c8e8139f7a1b3215dfceced802cec04102e979dc95172b78b6b3850c9a58db9a`。307 个输入中当时仅此项变化。`retry-03.xml` 两项在 setup 明确失败，未启动浏览器、未跳过指纹检查。
- E 在新私有目录重新完整构建，未改共享产物或产品输入。`/tmp/aps-final-e-current-scope.QI7Wmx/build-proof.json`：build `64b6bfb181a1c4a04c2f3b218de1f8ad9c4a56b306fc3be19e0213899b0bfe77`，215 files、307 inputs，Chrome 109。
- 上述属于早期未解冻阶段；之后 Main 已逐项授权并完成 E 产品修复，见 02、05、06、07。早期构建不能当作当前源版本，也不是整仓 gate、clean HEAD 或 Main V。

## 早期运行历史

| 场景 | 真实结果 | 原始目录 |
|---|---|---|
| 初次完整组 | `7 passed, 3 failed / 162.51s`，三失败是测试预期或选择器错误；全部保留 | `/tmp/aps-final-e-stable.L5TV52/full-01.xml` |
| 13 列明确分件和旧 10 列唯一性 | 修正“计划未记录数量不能猜成批次数量”的测试预期后，指定文件用例通过；同组两项浏览器仍在推进 | `/tmp/aps-final-e-stable.L5TV52/retry-02.xml` |
| 五专题与四目录 | 完整入口 48 组操作、真实重启后 4 组；56 个 CSV/XLSX 与真实 HTTP 原始字节相同；SQL 对应 66 工序、27 逐次报工、6 旧事件、33 合计记录；28 条原修订保留 | `/tmp/aps-final-e-stable.L5TV52/aps-workbench-live-8wymqs72/final-reports-proof.json` |
| 现场新增、补齐、更正、剩余全部完工、分件文件重导、实际甘特 | 现有脚本所有操作及真实重启完成；仅四张允许写表变化；新增 4 条逐次记录和 6 条修订，旧行保留。最后因原型差额断言保持 failed | `/tmp/aps-final-e-current-scope.QI7Wmx/aps-workbench-live-ojg76jik/final-browser-proof.json` |
| 校准真实离群样本中位数、取消后重新预览、采用锁定、原回执恢复 | 样本 `[1,2,3,4,50]` 取中位数 3，不是平均数；只有五张采用白名单表变化；真实重启后回执原值相同。最后因两个原型差额断言保持 failed | `/tmp/aps-final-e-current-scope.QI7Wmx/aps-workbench-live-oamiyl0w/final-browser-proof.json` |
| 现场和校准只读历史恢复 | 独立用例真实侧栏、F5、后退、前进后退全部通过；现场保持页 2/size 10/展开任务；校准保持模板/样本/搜索/排序；全程 GET，数据库不变 | `/tmp/aps-final-e-current-scope.QI7Wmx/history-01.xml` 中两项 passed |

每次宿主关闭均正常 drain 并检查库外写入、资产与加载的 Python 文件不变。真实重启仅允许且要求新增一条 `plugins/load` 审计及相应 `sqlite_sequence` 增量，不是把日志表整个排除。

## 已修恢复缺陷

- 实际甘特：批次视图、选中工序、只看选中、详情、4x、水平位置 4014，F5 后选择和缩放仍在，但水平位置变成 1494。第二次独立运行复现。
- 证据：`/tmp/aps-final-e-current-scope.QI7Wmx/aps-workbench-live-0n4zomdy/final-history-fieldgantt.json` 中 `baseline.actual_view.position.left=4014`，`failure_state.actual.left=1494`，最终真实板宽 1630、scrollWidth 5644，可容纳原位置。
- 根因定位：`frontend/workbench/app/ActualGanttWorkspace.jsx` 初始 `position.width=1000`；数据到达的 layout effects 同一轮先排队 measure，再按旧 width 恢复 scrollLeft。浏览器当时最大值正是 `((1000-292)*4+292)-1630=1494`；随后真实 width 更新，但 `restore` 已被清空，未再次恢复。
- 此问题已按实测宽度就绪后消费 restore 修复。当前 E03 `aps-workbench-live-r_y_j093/final-history-fieldgantt.json` 保留 zoom 4、left 4014、原任务/报工/详情/只看选中，F5、侧栏、后退、前进再后退四项通过。旧失败留存，不再待解冻实施。
- 报表早期 End 滚动中间值问题是测试时序，当前完整入口已通过。后续四域 history 误恢复进程内 token 的真实问题也已修复并通过 E06：新进入/F5/明确刷新才新读，活动旧 token 仍 409，原 scope/page/永久对象不替换。两类问题不混算。

## 六项旧差额的当前事实

- FIELD-001 已补齐五指标和状态计数。E03 `aps-workbench-live-fnjp23dl/final-field-initial.json` 核对五指标、六种状态及 all 计数；按完整筛选 cohort 而非当前页统计，未知工时显示未知和已知小计。真实查询与统计还见 `test_final_execution_search.py`。
- FIELD-013 已实现当前 Workspace 内按原 task 保存草稿、收起重开、切对象恢复、取消只丢当前草稿。同一 Field 记录 `draft-navigation-and-explicit-cancel-boundary` 核对 task1=4、另一任务=1、回 task1=4、取消 task1 不丢另一任务、再开 task1 空白。sidebar/F5 不恢复写表单、不重放命令仍是批准合同，E06 另有未保存备注和未知命令的真实重启证明。
- FG-010 已显示自动/手动状态及当前刻度。`final_execution_actual.cjs` 实际核对放大进入手动、适应全部回自动、data-tick-step 随跨度变化及键盘水平滚动；对应 E03 Field 完整入口通过。这里不是两个独立的模式/刻度开关，A 的建议动作措辞不能凭空增加开关合同。
- FG-011 已覆盖真实原引擎可用链。E03 `aps-workbench-live-pjdnlczw/final-chain-proof.json` 覆盖工艺/设备/人员边与 0/30/30 分钟间隔、全局链、独立任务关联链、资源组目标链、节点定位、实/虚连线开关和真实重启。`test_final_execution_chain.py` 锁住完整原引擎输入及拒绝；混合共同/分件依赖仍保留明确不可用边界，不能推成所有输入都可算。
- CALIB-002 已有表头排序、真实 facets 筛选/清除、未知偏差排除、键盘 Shift+ArrowRight 和真实拖动列宽。E03 `aps-workbench-live-jxowptso/final-calibration-initial.json` 的 `table_controls` 有真实 DTO 与 before/keyboard/pointer 宽度，完整入口通过；另 8 项表 API 测试覆盖全量列值、零/未知、分页/导出及拒绝。
- CALIB-003 已将 P1 改为真实按钮，打开同一 part_ref 的统一零件详情并定位原 template_operation_ref，只读无维护提交能力，关闭后保留来源。证据为同一 Calibration 原记录的 `part-number-click-and-real-selected-sample-provenance`、`part_detail` 及 `1920-light-initial-calibration-original-part-readonly.png`。
- 采用后 **不离页** 用旧 token 导出仍真实 409；**离页后重新进入** 是新读取，原模板读回定额 3，原采用回执不变且不二次采用。E03 完整采用/五表白名单/回执重启通过，不能继续要求重新进入也必为 409。
- FIELD-018 的零跨度/正数量零工时/重叠事实另有合同对照项：真实 ledger 当前接受的事实不写成“拒绝已通过”，也不擅自加新校验。原子账保留实际结果和待 Main 确认的口径。
- 所有差额保留在固定 69 族内；最终状态必须按原子动作列出，不能把其中一个成功动作扩成整个能力族 passed，不能未经批准统一改 N/A。

## Main V 与缺图

Main 已实际查看 E06 16 张图，正常可见布局、四类活动 409 与视口内的 Field 未知 ref 错误得到范围有限的确认；按 Main 正式登记落到可适用动作，不整族扩张。

文件名 final 不是正常态证据：E06 的 1392 dark Field final 对应未知任务错误；Calibration/Reports/Review 的对应 final 也处于未知 ref 请求失败，只是错误详情在原视口下方。E03 `1392-dark-initial-field-viewport.png` 目视为加载态，不计正常五指标 V。

Main 指出的三项缺图已最小补齐：`/private/tmp/aps-final-e-visual-supplement-20260911-01/run/visual-index.json` 记录 reports/review/calib 三张新 1920 light 图的完整路径、SHA、真实错误文本、视口内坐标和只读证明。源仍是 sealed06；旧图、原快照、产品不变，只新建两个最小只读宿主且均正常退出。E 已目视确认错误可见，仍待 Main 批准，不自行记 V passed。

其他代表帧和精确缺图以截图索引为准。图片是加载态、错误不在视口、或只在其他主题出现时，不冒充所需场景的四状态 V。
