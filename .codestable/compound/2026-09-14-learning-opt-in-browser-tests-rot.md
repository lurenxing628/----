---
doc_type: learning
track: pitfall
date: 2026-09-14
slug: opt-in-browser-tests-rot
component: tests/workbench 浏览器验收探针；tools/test_registry_groups_workbench.py opt-in 分组
severity: medium
tags: [workbench, browser-probe, opt-in, test-rot, quality-gate]
---

# opt-in 浏览器测试没人跑就会悄悄腐烂

## 1. 问题

`workbench_browser_opt_in` 分组里的真机测试靠 `ED_RUN_BROWSER=1` 之类的环境开关才执行。日常门禁与全量门禁只收集后报 skipped，注册表也写明「skipped collection is not execution」。2026-09-13 界面重做（`1a7a75c6`）换掉了共享分页器、给全部表格加了无障碍隐藏标题，同日的探针同步提交（`5bbb49d0`，236 个文件）没有跑这些 opt-in 测试，两处期望就此失效，直到 2026-09-14 手动打开开关才发现。

## 2. 症状

- `test_el_material_browser`：`el_material_actions.cjs` 精确等一个内容为 `第 2 / 2 页` 的元素，而共享分页器把摘要渲染成一句 `共 25 项 · 第 2 / 2 页`，15 秒超时。
- `test_ed_material_process_browser`：`ed_material_process_visual.cjs` 把 `overflow: hidden` 且文字超出自身盒子的节点记为「文字被裁切」，`.wb-visually-hidden` 的隐藏表格标题（1×1 像素）必然命中；断言在用例中途抛出，弹窗留在页面上，后面 17 个用例被弹窗拦截点击或被锁定命令禁用控件而级联失败（28 例中 20 例失败，其中只有 3 例是真正的断言）。

补跑后又连续暴露出三层过期假设，每层都要再跑一轮 6 分钟才看得到：取消已修改表单会先弹「离开前确认」；`?view=process` 会恢复上次节点和上次打开的详情弹窗（产能链瓷贴因此是 disabled）；共享分页器的每页选项与空态标题文案都换了。裁切检查在跳过隐藏文字后还抓到一处真问题：工序汇总表工时列表头被裁掉约 4px。

打开整条通道后其余 8 项里又倒下 3 项，模式一样：组件夹具手写的脚本清单没跟上新增全局模块（`WorkbenchTerms`、`WorkbenchFormat`）；探针把令牌颜色写成字面量；用 16 B/s 限速等 200 响应头这种依赖时序的网络模拟随着响应头变长就超时；数据库变更白名单没收录批次写入新产生的派生表。其中一条是真产品缺陷：全部表格框的 `overscroll-behavior: contain` 让弹窗里的表格吞掉滚轮，弹窗正文再也滚不到底部按钮。

## 3. 没用的做法

- 只看日常门禁「全绿」：这些测试是 skipped，不是 passed。
- 只信同日的「探针已同步」提交：改了 236 个文件也不代表跑过 opt-in 项。
- 在脏工作区上直接判断是本轮引入：要先在 HEAD 干净工作树复跑同批用例（两项在 HEAD 上同样失败、原因一致，才能确认是既有失败）。

## 4. 解法

- 探针按新结构匹配：整句读取 `.wb-pager .wb-pager-summary` 再精确比较，不再假设页码是独立元素。
- 裁切检查跳过屏幕阅读器专用文字：`.wb-visually-hidden` 或计算样式 `clip: rect(0px, 0px, 0px, 0px)` 的节点被裁切是设计意图。
- 用例失败后收尾：`ed_material_process_probe.cjs` 定义 `recover`，按 Escape 关掉残留弹窗，关不掉就刷新页面，避免一个断言拖垮整批。
- 补一条执行通道：`scripts/run_workbench_opt_in_browser.py` 解析各测试文件里的开关并全部打开，跳过不算通过（退出码 3），报告落 JSON。

## 5. 为什么有效

失败的根源不是某个断言写错，而是「有测试但没有执行路径」。给执行路径加上「跳过即失败」的判定，腐烂会在下一次跑通道时立刻暴露，而不是等到有人碰巧打开开关。

## 6. 预防

- 工作台界面改动后、以及每周至少一次，跑 `scripts/run_workbench_opt_in_browser.py`；改共享控件（分页器、表格框、弹窗）时必跑。
- 新写视觉检查时，先决定如何对待无障碍隐藏文字和 `text-overflow: ellipsis` 这类「设计上就会裁切」的节点。
- 多用例串行的浏览器探针，运行器必须在失败后恢复到已知状态（关弹窗或刷新），否则失败计数会失真。
- 补跑长期没跑的探针时，先把探针里的中文期望文本批量 grep 一遍源码，能一次抓出大半过期文案，比一轮轮实跑省时间；动态拼接的标签和夹具数据会误报，需要人眼过滤。
- 组件夹具不要手写源码文件清单；按 `build-order.json` 的 live 顺序算「被挂载组件读到的每个 `window.*` 归属文件」的闭包（本次 11 → 29 个文件），新增基础模块时才不会静默漏掉。
- 探针里的颜色、文案、接口路径都应指向单一来源（令牌、组件文案常量、契约），而不是复制字面量。
- 模拟「服务器已提交但浏览器没收到」用 CDP `Fetch` 在响应阶段断连，不要靠限速等响应头。
- 数据库变更白名单按「行的所有者是否属于本次夹具实体」判定，而不是枚举表名；派生表增加时只需补一条所有者回溯路径。
