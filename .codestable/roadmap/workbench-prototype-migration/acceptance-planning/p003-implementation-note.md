# D-P003 实现与冻结验证

- 结论：冻结工艺前后序和“调整此工序”已接入真实完整入口，四组合通过。原总账记录 124 / 146、22 项未运行；随后在定点核对剩余 ANA 合同时发现 `WBP-ANA-001.metrics` 的旧断言未覆盖完整四指标，另列证据不足，当前完整合同证据最多支持 123 项、待验证 23 项。原账本保留；差额与最小 Main V 索引见 `main-v-p003-minimum.md`，不代表 37 族全部完成。
- 授权：Main 已批准最小协议并注册新叶；G 的 `navigation_boot.py` 独立接纳 `task_origin`。D 未修改 shared navigation、Main factory、写命令字段或数据库 schema，也未执行 Git 写操作。

## 产品改动

- `core/services/workbench/plan_process_order.py`：在调用方读取事务内核验原采用审计、受理快照或保存场景的冻结关系，以及完整永久任务身份。缺少证据返回明确 unavailable，绝不改用当前 BOM；关系和核验事实进入原 workspace fingerprint。
- `plan_projection.py` 复用原审计读取为 `read_adopted_source()`；`plan_workspace_dto.py` 增加必填 `projections.process_order`，保留整份计划关系，不随显示时间切片截断。
- `PlanProcessOrder.js` 与 `PlanContract.js` 严格核验投影；`PlanDetailsUI.jsx` 显示前后序，`PlanWorkspace.jsx` / `PlanGantt.jsx` 仅按永久引用定位，范围外关系须用户点击后重读同一完整计划。
- `SchedulingWorkspace.jsx` 传递原 plan / operation / task 三项引用和只读显示范围；`TrialContract.js`、`TrialCatalog.jsx`、`TrialWorkspace.jsx` 限制来源并用真实 `base.plan_ref + operation_ref + source_task_ref` 唯一映射到新草稿 task_ref，未匹配不开放该草稿写操作。`task_origin` 不进入 create/change/save/adopt 请求。
- 原 Plan mock fixture 明确声明缺少冻结关系，而不是产品补默认值；独立 frontend source 列表均在 `PlanContract.js` 之前加载新叶，保留原断言。

## 同源证据

- 当前已验收私有源码：`/private/tmp/aps-final-d-source-p003-Z3GYfe/source`，3,941 文件；manifest aggregate `36fdf014043289cdcf552872a6d40b65bd91ffb179208ca9f0b9f4c45bfdcdba`。源于最初固定源码，后两版只叠加 D 的测试修正，不混入后续 moving Main。
- 完整 canonical build：`9f54333a9b8abe65cddfa918920607536199439739d4ea0603ef84a18d60a8dd`，223 产物、315 输入；使用真实入口 main，目标 Chromium 109。构建在第一版源码完成，其产品字节与当前冻结副本相同，后续测试复核全部输入与输出 SHA。
- 沿用 G 的 `source_binding.py/source_guard.py`，harness 也复制到私有目录。逐文件内容与模式复核；全部 repo 模块、namespace 和自定义插件别名都不得回读原 checkout；原 `.venv` 仅提供显式第三方依赖。每个进程均留下 `final_planning_source-{first,restart}.json`。
- 主链四根目录：`ja4vco32`、`8pn4gd67`、`exypgb0l`、`ry59xgim`；只读：`r3aq1z0g`、`xdozbga3`、`ouzb4vpo`、`d5l_hb_m`；预检：`dlpypn2a`、`3iqdx52f`、`lily14_d`、`yn0_jm4k`。均位于上述私有根目录的 `aps-workbench-live-<名称>` 下，顺序为 1920/light、1920/dark、1392/light、1392/dark。
- 每个主链：110 主动作 + 7 新进程动作；真实受管 worker、13 道任务（含 4 个零时长点）、4 候选、仅两次正式采用生成 v5/v6，77 张业务表原有行保留。所有主机正常退出，锁释放，无源码漂移或隔离违规；预检与只读组所有业务表完全不变。
- 同源总账：`evidence-matrix-p003.json`，SHA `0dbb9ab950858026949ecf3ceeff2fd13999f7e6e720ad5fac3f6ec326c81392`。1,094 个被实际加载的产品 Python 文件跨全部样本 SHA 一致；没有把旧不同构建证据混入。

## 验证结果

| 范围 | 实测 | JUnit |
| --- | --- | --- |
| 新后端投影 + 相邻计划 API/transport/projections | 72 passed | `/tmp/aps-final-d-p003-contracts3.xml` |
| 真实 DTO 的客户端来源/关系边界 | 1 passed，39 断言 | `/tmp/aps-final-d-p003-origin.xml` |
| 旧 Plan / Trial / fixture / 甘特模型 | 8 passed | `/tmp/aps-final-d-p003-fixtures.xml` |
| point/piece/采用基线/试调采用等消费者 | 70 passed | `/tmp/aps-final-d-p003-consumers2.xml` |
| 同源完整入口 3 组 x 4 组合 | 12 passed，225.13 秒 | `/tmp/aps-final-d-p003-matrix.xml` |

- 原正式 source_task_ref 与草稿 task_ref 不相等；创建保持完整 13 项；搜索 `item-B` 只改变显示。刷新用 Main 的 `history.state` 规范恢复；显式 `nav` 地址另通过 G parser，二者没有被混为一种 URL 写法。
- 定点 Pyright：0 errors / 0 warnings；所改 Python 与测试辅助 Ruff 通过。冻结副本生产扫描 1,261 模块、含测试扫描 2,683 模块，解析失败 0，相对原基线无新增硬环或圈内边。原有目录环仍在，未刷新任何基线。
- 保留开发失败：第一个零时长单元夹具缺受管采用前置条件，保存场景旧夹具会移动错误链节点，均改用既有真实夹具后通过；完整入口 R1 是 Chromium 109 datetime 填值格式，R2 是误把 history context 当成 URL 参数，均只修测试并保留全部原失败日志。

## 边界

- P003 的正向新建、刷新、显式入口、冻结关系、切片外定位均已完成；已有草稿选择及更多负向 UI 分支作为后续增量继续补，不反向冒充已验证。
- 22 个其余原子动作继续处理。采用记录页签、四指标及取舍等缺项须对照原合同，不能把其他页面相似内容或“未评估”文字改记通过。
- 本批是 dirty 主工作区上的私有固定源码证明，不是 clean-worktree proof、全质量门禁、Win7 实机、5000 性能或发布证明。旧预览、生产库、Main 的共享导航/静态产物和 Git stage 均未由 D 改动。
