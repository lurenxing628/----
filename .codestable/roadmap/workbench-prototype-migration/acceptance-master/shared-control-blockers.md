# 共享控件验证与历史阻断

当前结果：`jb7nijn7` 完整入口四组合 28/28 passed；新工艺列宽 44 项内部合同全过。原两处共享故障与后续宽屏工艺列宽问题均有修复后实证。详见末节和 `2026-09-10-process-table-resize/process-table-resize-fix-note.md`。下文失败按时间保留，不代表当前状态；本轮不是最终 HEAD clean proof。

2026-09-10。C 仅提交因果证据和建议，没有改下面两个共享产品文件。

## 筛选结果变短误关弹层

- 产品路径：`frontend/workbench/app/ResourceTableFilter.jsx:72` 的 `scroll()`；当前 SHA-256 `f41d542a19b1534c88fbb2b3a001a3d6a72f58bcd29ce3a619eb877ab6779aef`。
- 实际构建 `1a3dcad847e14a7e995ebfe00f3d6f9d0e101ffd7081a6012ab86993e0629597`，完整入口，215 files / 307 inputs。
- 私有证据 `/private/tmp/aps-workbench-live-_6ynlvll/final-master-controls.json`，字段 `facet_after_empty`。观察器只记录事件、尺寸和连接状态，不改应用状态、不拦事件。
- 1920x1080 工艺两主题：取消全选前 `scrollTop=600.5, scrollHeight=3979, clientHeight=1080`；结果变成 0 行后 `scrollTop=238.5, scrollHeight=1318`。顺序为菜单内 checkbox 的 pointerdown、focusin、document scroll、menu-removed；没有 wheel、keydown 或外部点击。新滚动值恰是变短后的最大可滚动位置，存在 0.5px 的浏览器度量舍入。
- 1392x924 物料两主题：`597 -> 313`，高度 `2188 -> 1237`；工艺两主题 `710 -> 380`，高度 `4011 -> 1304`，同一因果链。
- `scrollPositions` 保存打开时的位置；`scroll()` 只排除了位置未变的延迟事件，其余一律 `close.current(false)`。它没有区分用户滚动和表格变短导致的强制夹位。
- 原有 `tests/workbench/resource_table_live_probe.cjs` 明确断言筛选后菜单不能被卸载。C 的测试继续保留这条断言，不重新打开菜单绕过。

建议在 `scroll()` 的“位置未变则返回”之后、`close.current(false)` 之前加入以下窄分支。不是把所有外部滚动都忽略：

```diff
         if (before && target.scrollLeft === before[0] && target.scrollTop === before[1]) return;
+        if (before) {
+          const left = Math.min(before[0], Math.max(0, target.scrollWidth - target.clientWidth));
+          const top = Math.min(before[1], Math.max(0, target.scrollHeight - target.clientHeight));
+          const clamped = left < before[0] - 1 || top < before[1] - 1;
+          if (clamped && Math.abs(target.scrollLeft - left) <= 1 && Math.abs(target.scrollTop - top) <= 1) {
+            scrollPositions.set(target, [target.scrollLeft, target.scrollTop]);
+            place();
+            return;
+          }
+        }
         close.current(false);
```

验证须同时保留：空结果后菜单不关、可继续勾选、真正外部滚动仍关、菜单内滚动不关、原锚点失效仍关。上面是待 Main 实施并验证的最小提案，不是已验证补丁。

## Modal 背景未锁滚动

- 产品路径：`frontend/workbench/app/ResourceControls.jsx:94` 的 `mountModal()` / `Modal()`；当前 SHA-256 `1718e2bdd9ebc3b71e729ae3173a1307c2120f24bded48a0f54ad034c87484dd`。
- 同一私有报告 `background_scroll`：新增物料模态内完成 Tab/Shift+Tab 后，鼠标放到遮罩 `(8,80)`，真实 wheel `dy=700`。1920 light 的 HTML scrollTop `0 -> 348`，dark `0 -> 239.5`；1392 light `544 -> 790`，dark `544 -> 781.5`。这些只是两帧内已观测的移动量，不是假定最终滚动距离。
- 当前 `mountModal` 只登记焦点与键盘事件，没有锁住文档背景滚动；固定定位的遮罩本身不会阻止滚轮滚动背景。
- 最小处理建议：沿用现有 `modalStack`，第一层挂载时保存 html/body 的原 inline overflow 值及 priority 并设为 hidden，最后一层卸载时精确恢复；嵌套层不得提前解锁。保持 modal 内部 `.scroll` 容器正常滚动，不采用每次 wheel 之后强行滚回去的补丁。
- 验证：四视口主题的遮罩 wheel、嵌套关闭后仍锁住、最后关闭后背景可滚动、原滚动位置与焦点恢复。

## 不混为产品缺陷

同轮批次日期场景在“取消后立刻读 activeElement”处失败，尚需给浏览器的既有异步焦点恢复一个实际完成检查。C 将只改测试为等待原按钮获得焦点，若仍失败再提交产品证据。不会主动 focus 原按钮伪造恢复成功。

本轮 24 个控件场景 10 passed / 14 failed，不能汇总成全部通过。原始截图、请求与 SQLite 保留证据都在私有根；V 仍由 Main 判断。

## 22:10 定点因果补证

- 私有根：`/private/tmp/aps-workbench-live-8fk_6dmz`，1920x1080 light 的 `process-headers` 单场景。原断言保留，1 case / 1 failed。
- 完整构建：`c7ff4904c04584a991c770e07a3fec0d2f79914f942a9cf43cb162242792badb`。本轮 `source_changes=[]`；`ResourceControls.jsx` 已是 Main 的 `996b7e3f5d3cb4614f5b969521c89e47ca31bbdd55a357972bdb6779a85ae59c`，`ResourceTableFilter.jsx` 仍为上述旧 SHA。
- `final-master-controls.json` 的 `facet_after_empty[0].observation`：`initial_owner`、每一条事件的 `owner` 和 `final_owner` 均为 `same_node=true`、`connected=true`、`disabled=false`；按真实 scopeTransform/signature 得到的 `derived_identity` 始终相同。这里记录的是真实 history scope 派生值，不是伪造的 React 内部状态。
- 精确顺序：14:10:26.843Z 菜单内 checkbox pointerdown/focusin/pointerup；.846Z 表格 `aria-busy=true` 且高度从 2750 变成 89；HTML 高度 3979 变成 1272，scrollTop `600.5 -> 192.5`；.849Z checkbox input/change；.850Z 列表真实 GET 发出；.858Z document scroll；.862Z `aria-expanded=false`、menu-removed；.866Z 返回 production 200、0 行。
- 结论收紧：这次首次夹位发生在 loading 清空旧列表时，早于 0 行响应，不仅是最终空结果变短。关闭前没有 wheel、keydown、外部 pointer 或锚点替换，不能归因于 owner.disabled 或 scope identity 变化。
- 自有服务 98999/99077 正常关闭；原业务数据不变，重启保留检查通过。本次只补测试观察与证据，没有改共享产品文件。

## 新夹位分支全入口复验

- 私有根：`/private/tmp/aps-workbench-live-dn3l0gce`；完整构建 `99e398d64c9470f2369e1170787e334b3523d39a114f2980a5ac414d92aa6feb`。共享列筛选 SHA `c4f1c48b5bd461feb1b14c5ffb3dc1374c5b29f4368da90a820ee08f4dcba3ab`；Modal SHA `996b7e3f5d3cb4614f5b969521c89e47ca31bbdd55a357972bdb6779a85ae59c`。
- 原 24 场景：14 passed / 10 failed。新增长弹窗 4 场景因测试使用了不存在的按钮名“维护班次配置”失败，实际产品名为“维护班次”；这一部分是测试缺陷，不认定为产品失败，修正后单列补跑。合计 28 cases / 14 failed、64 screenshots、1082 steps。
- Modal 四组合：16 次物料 X/取消/遮罩/Escape 关闭、4 次设备目录嵌套通过。每次记录 trusted wheel 和 300ms 内 compositor scroll 事件，背景位置全程不变；最后关闭原按钮同节点自然得到焦点、位置恢复、inline style 原值和 priority 保留，普通 wheel 恢复。未注入滚回脚本或假弹窗。
- 筛选 6 组失败：1920 两主题工艺 `600.5 -> 192.5 -> 238.5`；1392 两主题物料 `597 -> 308 -> 313`、工艺 `710 -> 380 -> 426`。第一段 loading 夹位已被新分支放过；第二段 loading 完成后文档高度分别增加 46/5/46px，发生同量正向 scroll 并关闭菜单。owner 始终同节点、connected、未 disabled，identity 不变，无新增 wheel、keydown 或外部 pointer。自动锚定为当前推断，未将推断写成原生调用栈实证。
- 批次日期 4 组失败：不是立即读取焦点；真实 `waitForFunction` 等待原按钮成为 activeElement 12 秒仍超时。完整日期操作已执行，原按钮未被测试主动 focus。下一轮增加 pointer/focus/disabled/挂载时序取证。
- `source_changes=[]`，`read_database_unchanged=true`、`restart_preservation.passed=true`。初次服务 696、重启服务 2408 均正常关闭；重启原数据浏览器探针返回码 0。没有因此宣称完整控件验收通过。

## 长弹窗补跑与批次焦点确证

- 私有根：`/private/tmp/aps-workbench-live-kc_s2vef`，同一完整构建 `99e398d64c9470f2369e1170787e334b3523d39a114f2980a5ac414d92aa6feb`，222 files / 314 inputs。`final-master-controls.json` SHA-256 `a06f5ead6213ca080b68eb9f5f10020cda0f7b4f4d4f0a36c5fc11863b460788`。
- 仅选择 `resource-long-modal-scroll,batch-native-date-and-focus`，四组合共 8 cases：长弹窗 4 passed；批次焦点 4 failed。16 screenshots、298 steps；原报告与上一轮失败截图均保留，不覆盖为通过。
- 长弹窗真实动作：基础资料人员 → 新增人员 → 维护班次 → 编辑 RT-SH → 轮换天数填 31 → 调整逐日规则。只生成未保存草稿，不插入假 DOM、不 mock API。真实弹窗体 scrollHeight=2376，1920 高度 690、1392 高度 601；四组内部 wheel 都使 scrollTop `0 -> 700`，全部背景滚动位置在全过程保持原值。
- 草稿关闭触发真实“放弃修改”确认；确认时仍锁背景，关闭子层后父层仍锁背景、父层原“维护班次”按钮自然恢复焦点，最后关闭恢复原“新增人员”按钮、位置和 inline 样式值/priority，并能继续普通背景 wheel。每步只读 SQLite 行级前后比较通过。
- 批次日期路径已去除原来用于键盘选日准备的 `day.focus()`，改为等待产品选择月份后自然聚焦到对应日期；弹窗取消后继续等待原按钮，仍 12 秒超时。测试没有任何主动 focus 恢复。
- `focus_restore[*].evidence.events` 四组一致：可信 pointerdown → 原“新增批次” focusin → pointerup → 同节点原按钮 disabled=true、focusout 到 BODY（此时 dialogs=[]）→ 批次号输入框 focusin。最后取消后 dialogs=[]、原按钮同节点/connected/disabled=false，但 activeElement 仍为 BODY。
- 代码证据：`BatchWorkspace.jsx` 的 `blocked` 含 `!!dialog`，新增按钮使用 `disabled={blocked || !data}`；共享 `ResourceControls.Modal` 直到挂载 effect 才保存 `document.activeElement`。真实先禁用再挂载时序会丢失原触发按钮，不能再解释为等待时间不足。C 未修产品源码，交 Main 决定最小修复位置。
- 补跑 source_changes 仅 `ActualGanttContract.js`、`ActualGanttControls.jsx`、`ActualGanttRows.jsx`、`ActualGanttWorkspace.jsx` 四个产品文件。冻结资产在两次服务中相同；manifest 内共享 SHA 仍精确为 `996b7e...` / `c4f1c48...`，但本轮不是全源码冻结证据。
- `final-master-result.json` SHA-256 `4738df723b7bfe682da1473408da49ba1753caabcc4e313474a5ad4ff279679e`；`read_database_unchanged=true`、`restart_preservation.passed=true`，自有服务 2893/3257 正常关闭、isolation_violations=[]。浏览器 unexpected errors=[]、external=[]。
- 追加测试文件：`final_master_modal_controls.cjs`、`final_master_focus_trace.cjs`；`final_master_controls.cjs` 接入原入口与新断言。3 个 CJS syntax check 通过，`test_final_master_manifest.py` / `test_final_master_guards.py` 共 9 passed（0.73s）。未改两处共享产品文件、未做 Git 写操作、未动 53144 旧预览。
- 当前退出边界：Modal 全 app 锁滚动合同已获四组合真实证据；原 24 控件组仍 14 passed / 10 failed，另加长弹窗 4 passed。筛选第二次自动滚动和批次原按钮丢失仍是阻断；V 留给 Main，不抹平为完整通过。

## 第二次共享修复的独立源码快照

- Main 新共享源码：`ResourceControls.jsx` SHA `1bed5a0d7e1afd6164064683e73d3998def9720c99e03ead1e49a360d40f6ac1`；`ResourceTableFilter.jsx` SHA `b6d6f18afaec9147b9d13422efcd9d4c622ce47aefbb308c3febea746537eb42`。C 均已独立核对原文件和构建 manifest。
- 使用 G 的 `legacy-retirement/factory-tests/source_binding.py` 清单及普通文件复制，得到私有完整源码 `/private/tmp/aps-final-master-C-sealed.mXZW7b/source`：3574 files、69560967 bytes；不是指向原树的源码 symlink。原树与副本逐文件 SHA 对照通过，含 mode 的清单 `source-bound.json` 聚合 SHA `24d3c58ab0fd8a1c27450ead687639b6be05f084d9078db06b82195fd2cf61ca`。
- C 服务器只在指定源码清单时复用 F 的 `final_operations_source_binding.source_binding()` 记录实际加载模块。第一轮服务加载 1106/1051 个项目模块，全部位于该副本且 SHA/mode 匹配，violations=[]；未偷偷回原 checkout import。测试数据仍是新建私有 SQLite，不复制生产数据库。
- 第一轮根 `/private/tmp/aps-workbench-live-imx9z9xb`，完整构建 `5aa7749ba83bb04f33532814293dd406c8e2047e4abdfaabbd4dc5c2f29b4918`。28 cases / 20 passed / 8 failed，68 screenshots、1226 steps。四组合的 8 处原筛选失败点全部保持原菜单且能继续勾选；观察到工艺 loading 后 scrollTop 保持 192.5（1920）或 380（1392），物料保持 308（1392），最终页面增加 46/5px 高度时没有第二次自动 scroll。4 组批次日期完整动作后的原按钮均自然重新获得焦点。
- 第一轮剩余 8 失败（按终态 stack 纠正中途的 4/4 分类）：6 个新增外部 wheel 检查在内部惯性滚动结束前就发下一手势，真实 wheel 的 target 已在 MAIN，浏览器却仍将惯性 scroll 交给选项容器；这是测试时序问题，之后等待末次真实滚动事件静默 300ms，不取消原外部滚动断言。另 2 个 1920 工艺列宽拖动超时，继续取证，不归到已消失的共享原故障。
- 该轮 `source_changes=[]`、原业务数据不变、重启保留通过；服务 7128/8979 正常退出。旧 `dn3l0gce`、`kc_s2vef` 失败报告保留。

## 表头定点取证

- 第二份副本 `/private/tmp/aps-final-master-C-controls2.2WRVGc/source` 复制上一完整源码，仅覆盖 3 个测试文件：`final_master_controls.cjs`、`final_master_filter_controls.cjs`、`final_master_resize_trace.cjs`。逐文件对照确认无产品差异，3575 files，聚合 SHA `c692aef695e0c2d42bbb2bbf1c99e1999a7eabd33e23062658c3943ff21596dc`。最初复制未完成时发起 capture 被 source drift 守卫拒绝，没有接受那次清单；等复制完成、重新覆盖测试并重做双清单核对后才启动。
- 定点根 `/private/tmp/aps-workbench-live-qal9ktxp`，1920 light 的资源/工艺表头：1 passed / 1 failed。资源新增内部/外部 wheel 全部通过：内部 scrollTop `0 -> 160` 不关原菜单；独立外部可信 wheel 使 document `0 -> 160` 并关闭菜单；所有原祖先 `overflow-anchor` 值/priority/computed 状态精确恢复。
- 新工艺列宽缺口：`column_resize` 中原图号 th 实宽 `184.609375`，ARIA 185，声明 160px。可信 pointer 从 x=523.875 移到 x=547.875，捕获始终正常，未 disabled/断开。目标声明变为 209px，但实宽变为 `230.796875`、ARIA 231，其他列从 `[50.77,219.23,136.15,450,219.25]` 被重新分配到 `[48.59,209.81,130.30,430.67,209.83]`。不是 RO 尚未更新或鼠标没有真正拖动。
- 根因代码范围：`ProcessWorkspace.jsx` 的 `ProcessTable` 只更新目标列声明宽度与 min-width，总表格仍填满容器；`ResourceTableHeader.useResize` 交付的是实测像素目标。两者约定不匹配。`ResourceTables.jsx:58` 已有“取所有列当前实宽，再固定全表总宽度”的可参考实现。该问题先前被筛选提前失败遮挡，不冒充这轮两个共享修复引入的回归；C 未擅自改产品。
- 定点轮 source_changes=[]，实际加载项目模块 1106/1051、来源违规 0；原数据与重启保留均通过，服务 10017/10189 正常关闭。
- 第二份副本完整根 `/private/tmp/aps-workbench-live-3tm8023s` 终态为 26 passed / 2 failed，仅 1920 两主题工艺列宽失败；1392 同一拖动断言通过。原两处共享故障的四组合原场景均不再复现。68 screenshots、1238 steps，source_changes=[]；服务 11097/11871 正常关闭，原数据/重启保留和实际模块来源检查通过。另有 58 条只读 facet POST 取消被旧探针误列 unexpected，原报告保留，后续测试精确区分并加负例。
- V：Main 已明确完成旧 `kc_s2vef` 四张长弹窗图的预检，仅属于那个图像快照，不覆盖新版 focus/filter 全部。

## 工艺列宽修复后的最终定点结果

- Main 授权后仅改 C 的 `ProcessWorkspace.jsx`，沿同域 `ResourceTables` 的全列实宽冻结策略修正；SHA 从 `b2287d8d...` 变为 `df4b057c2946043dc22d320509981826987867309e04231537d357734227654e`。这是新 G05 增量，旧 `4b418` 及其证明记录未动。
- 最终私有副本 `/private/tmp/aps-final-master-C-process-fix.Rx1tBZ/source` 与上一副本只有明确授权的 1 个产品文件及 6 个测试文件差异；3577 files，含 mode 聚合 SHA `268a712aa93737152a2c4c4747ad7780c89598b0fb604894e6441721e1fddb66`。没有把原 checkout 的其他并发改动混入此证明。
- 全入口新构建 `66b45a266409ca4d996bade37149f4044180fa5bbe9c8fb289e5912f9f87c79c`，222 files / 314 inputs；资产 manifest SHA `eea8e5cf840f61cca229f6fb792852002b57d00432a4084d5777f894e3ba0c9d`。
- `/private/tmp/aps-workbench-live-jb7nijn7/final-master-controls.json`：28 passed / 0 failed，76 screenshots、1314 steps；原 28 分母未改。新增 11 项列宽合同 × 四组合全部通过，涵盖全列初次冻结、键盘步进、56px 下限、重复与其他列拖动、Escape 取消、样式恢复。
- 原共享 SHA 保持 `ResourceControls=1bed5a0d...`、`ResourceTableFilter=b6d6f18a...`；原菜单空结果/恢复全选、真实内外 wheel、overflow-anchor 恢复，以及批次原按钮自然焦点恢复均在实际 app 复验通过。没有将重新打开菜单或主动 focus 当作恢复。
- `read_database_unchanged=true`、`restart_preservation.passed=true`、source_changes=[]；服务 15704/16347 正常退出。实际加载 1106/1051 个项目模块，源自该完整副本、SHA/mode 匹配、violations=[]；结束后全 3577 文件指纹复核通过。
- unexpected 浏览器错误 0、external=[]，预期只读取消 123 条单列。精确 POST 路由取消分类的 16 个 unit 检查通过，写命令或其他网络失败仍不能进入预期取消。Python 定点 11 passed（2.38s）；Ruff、CJS syntax 与服务器 Pyright 检查通过。
- C 已实际看过四组合的最小宽度/重复与取消后共八张图，无列内容错叠、按钮溢出或页面横向溢出。图片仍保留 Main 最终 V 签认边界；不把 C 检查写成 Main 已确认新版。
- 控件报告 SHA `2a8af785e8f7470eaef6921fca3bbe29ff7dfb0fad40d796d7fe3ee26bf36755`；整轮报告 SHA `c1eec0ea22857b1a8acf26b98519a810d81033752d59a90e142f7be8e6802720`。所有先前失败根保留。
- 修复记录：`.codestable/issues/2026-09-10-process-table-resize/process-table-resize-fix-note.md`。未做 Git 写操作、未动 53144，未宣布整仓 clean gate / 50 项共享动作 / 599 项领域动作完成。
