---
doc_type: issue
status: fixed
date: 2026-09-10
owner: EE
scope: authorized-frontend-components-only
---

# EE 零时长前端组件交付

## 结论与边界

- 候选、正式、试调甘特的点组件已实现，并用真实临时 SQLite、真实引擎、现有读取/试调路由和 Chromium 109 验证。
- 本记录的 fixed 仅指 EE 授权组件；不是全主页面联合接入完成，也不是可以打开 public 点采用。
- public `point_rendering_enabled` 未改。测试建数复用 EA 内部采用 factory 显式开启点证明，HTTP host 未注册采用入口或增加开关。
- 没有修改 `main.jsx`、全局构建脚本/清单、静态发布目录、theme、全局控件、registry 或 backend。没有 stage / commit；原暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 保留。
- 原工作区大量脏改保留；工具按项目要求运行 symbol_locator，前端函数不在其 Python 静态图内，因此实际前端调用面以当前源码核对。索引自动刷新不作为本轮产品交付。

## 共享 Point 接口

三文件 API 已同步 EK 任务 `01a089c3-d65b-7cf2-8912-546fe9988179`，当前稳定，EK 只读复用。

| 文件 | 接口 | 约束 |
| --- | --- | --- |
| `frontend/workbench/app/PointContract.js` | `window.PointContract.fields / isPoint / arrangement / overlaps` | 四个点条件缺一不可；日期是否合法仍由消费合同验证；不从裸相等时间猜测点。显式范围左闭右开。 |
| `frontend/workbench/app/PointGanttModel.js` | `bounds / tracks / visible / hit / paint / hitSize` | 输入时间坐标为毫秒；24px 命中区、同轨至少 28px 间距；`tracks` 输入已筛出的点 `{task,start,end}`，task 需稳定 task_ref 或 row_ref。 |
| `frontend/workbench/app/PointGantt.jsx` | `window.PointGantt.Styles / Marker` | Marker props 为 `{task,x,top=12,title,selected,tone,onSelect,onHover,...dataAttributes}`；x 是命中框中心，可为像素数或 CSS 百分比；hover 传事件或 null。 |

- `arrangement(row, owner)` 的 owner 只用于试调原安排/历史缺少重复点字段的情况，必须是同一任务的已验证点。它不能充当跨任务证据。
- `bounds` 仅给显示时间轴留白，不改 DTO、任务起止时间或业务跨度。
- `candidateRows(model,width)` 是候选基线组合后的点轨重排，不供 Actual 强行复用。
- Marker 自动输出 `data-point-ref=task.task_ref || task.row_ref` 与 `data-point-at=task.start`。试调原安排传独立的渲染视图，保留原时间；原始 DTO 不改。

### 主线加载顺序

1. `PointContract.js` 放在 `PlanContract.js` 前。
2. `PointGanttModel.js`、`PointGantt.jsx` 放在 `PlanGanttModel.js` 前；React 已先加载。
3. 这样也早于 RunCandidate、Trial、Actual 的消费模块。
4. 本轮没有改 build-order。旧独立测试 host 的硬编码 source 列表也须由主线补齐新依赖，不能把未加载 helper 的旧 harness 当成新版集成。

## 实施要点

- `PlanContract.js:116`：仅合法点增加明确字段白名单；完整读取保留最后一点，显式筛选严格执行半开范围。
- `PlanContract.js:306`：`plan_span.end` 可能本身就是末尾点。显式范围恰好止于该时间，不再错误声称覆盖全计划。
- `TrialContract.js:45`：当前点必须显式标记；原安排及变更历史绑定本任务点身份，saved scenario 的历史通过 source_task_ref 核对。
- `PlanGanttModel.js:60`、`RunCandidateModel.js:46`：点专属显示轨，不与普通区间共同参与重叠拆轨或冲突颜色计算。分轨使用 O(n log n) 堆，随视窗宽度/缩放重算。
- `RunCandidateGantt.jsx:4`、`PlanGantt.jsx:16`、`TrialGantt.jsx:39`：固定命中区菱形，不伪造最小时长；保留悬浮、选择、原/当前安排和详情。
- `PlanGanttCanvas.jsx:26`：canvas 点按像素命中，普通条仍用实际宽度；概览中的点单独画标记，不塞入占用直方图。
- `PlanDetailsUI.jsx:35`、`TrialDetails.jsx:56`、`RunCandidateGantt.jsx:121`：展示时间点与 0 h / 不占用资源。正式点详情不把同一设备的整份计划占用冒充本点占用。

## 真实验证

运行环境：仓库 `.venv/bin/python` 为 Python 3.8.10；浏览器为指定路径的 Chromium `109.0.5414.46`。只用本地已有 Node、React、Babel、Playwright 和样板样式。

```bash
.venv/bin/python -m pytest -q -s tests/workbench/test_point_frontend.py --basetemp=/tmp/ee-point-frontend-20260910-final --junitxml=/tmp/ee-point-frontend-20260910-final.xml
.venv/bin/python -m pytest -q tests/workbench/test_ea_zero_duration_chain.py tests/workbench/test_ea_zero_duration_boundaries.py tests/workbench/test_ea_zero_duration_constraints.py --junitxml=/tmp/ee-point-backend-regression-20260910.xml
.venv/bin/python -m ruff check tests/workbench/test_point_frontend.py tests/workbench/point_frontend_support.py
git diff --check
```

| 实测 | 结果 |
| --- | --- |
| EE 新测试 | 2 passed；内含 2,101 + 2,132 = 4,233 项合同/布局断言 |
| 真实数据规模 | 全点 12 道；混合 12 点 + 100 条真实正时长安排；不是静态字符串检查 |
| 后端链 | 引擎 -> 候选落盘 -> 内部采用 -> 正式读取 -> 试调移动/保存 -> 内部再采用 -> 新连接现有 HTTP 路由读取 |
| Chrome109 | 1920x1080、1392x924，各 light/dark，候选/正式/试调三视图；24 张截图、120 项记录交互 |
| 鼠标键盘 | 实际输入搜索、hover、距中心 10px 点击、Enter 选择、缩放及重新定位、普通 canvas 像素与点击 |
| 实际写入 | 8 次浏览器经原 TrialAPI 和现有路由保存点移动；operation_ref/task_ref 不变、start=end、duration_seconds=0、occupies_resources=false |
| 时间边界 | 全点零宽跨度；完整计划末点；左边界包含、右边界排除；原安排独立时间属性 |
| 统计边界 | 点占用/重叠为零；正常条仍保留；未人为增加夜间或日历外占用；所有渲染/筛选不改变 DTO |
| 局部静态 | 两个 Python 文件 ruff 通过；git diff --check 通过；所有交付源码低于 500 行 |

浏览器使用现有 AppShell 与真实组件组合的 **EE 隔离 host**，不是 `main.jsx`。正式和试调走本轮真实合同；候选从真实路由取 DTO 直接交组件，未伪称旧 RunCandidateAPI 已接受点。构建仅编译所需当前源文件到测试临时目录，其他样板资源只读复制并校验原 manifest 哈希。监听随机本地端口，明确排除 52392/58448/64612；全部测试服务和浏览器已退出。

浏览器原始证据：

- `/tmp/ee-point-frontend-20260910-final/test_real_point_contracts_layo0/ee-point-browser/`：全点。
- `/tmp/ee-point-frontend-20260910-final/test_real_point_contracts_layo1/ee-point-browser/`：混合/正常 canvas。
- 各目录包含临时编译文件、build-evidence.json、脱敏 DTO、browser-result.json、12 张截图。记录的 viewport 是指定尺寸；截图采用 fullPage 保留滚动区上下文。
- 本目录另存测试 XML、浏览器结果与文件 SHA-256。write token 仅为临时 test token，归档 DTO 中已脱敏。

## 主线仍需处理

1. `frontend/workbench/app/RunCandidateAPI.js:78/86/91/106` 的旧字段白名单、严格正区间、span 和左边界规则仍会拒绝点，属于 EE 写集外，本轮已报告但未修改。
2. `frontend/workbench/app/RunBaselineAPI.js:30` 的候选点字段与 interval 检查未接；候选初始计划对照不算本轮联合验证通过。
3. ActualGantt / Field 的点读取、合同和标记由 EK 独占实施，EE 没有验证或代改该写集。
4. 主线统一 helper 加载顺序、测试 registry、硬编码测试 host 依赖和真正 `main.jsx` 联合验证后，才决定宿主 flag 是否打开。
5. 未在 Win7 实机打包/运行；未做 10,000 点容量门禁；未在真实浏览器触发超过 70 个同轨可见点的 DenseRow 点分支。该分支的像素几何有定向模型断言，不能替代该浏览器容量证明。

## 门禁与未提交现场

- 执行了 `scripts/run_quality_gate.py --fast-precheck`，失败为当时快照 40 项 EE 写集外的导入顺序/格式问题，日志单独归档；没有改其他代理文件。
- 没有全量 clean gate，没有 clean-worktree proof。当前结果为 dirty worktree 下的定向组件与后端回归证明。
- 本轮明确源码写集见 `ee-write-set.json`，对应内容哈希见 `final-file-hashes.json`。已有大量未提交/未跟踪文件未清理，本轮也未提交。
