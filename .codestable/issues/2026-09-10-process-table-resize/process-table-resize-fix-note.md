---
doc_type: issue-fix
issue: 2026-09-10-process-table-resize
path: fast-track
fix_date: 2026-09-10
tags: [workbench, process-table, resize, browser, readonly]
---

# 工艺列宽拖动实宽修复

本次局部修复已通过完整工作台入口四组合验证。它是已提交 master 文件的新 G05 增量，不追认或修改 `4b418` 的旧证明，也不是最终 HEAD 的整仓门禁结论。

## 根因与改动

- 旧 `ProcessWorkspace.jsx:25` 的 `ProcessTable` 只设置目标列的声明宽度，同时让总表继续填满容器。共享 `ResourceTableHeader` 传来的却是实际像素宽度。
- 1920x1080 真实 trace：图号声明 160px、实宽 184.609375px，指针右移 24px；目标声明变成 209px，但实宽变成 230.796875px，其他五列也被挤窄。证据保留于 `/private/tmp/aps-workbench-live-qal9ktxp/final-master-controls.json` 的 `column_resize`。
- 改动仅在 `frontend/workbench/app/ProcessWorkspace.jsx` 的 `ProcessTable`：沿用同域 `ResourceTables` 模式，读取全部表头列当前实宽，包含选择列和操作列；固定每列及全表总宽度，再只改变指定列，最小值仍为 56px。
- 未改共享 Header、原 24px 拖动断言、排序/筛选业务、数据库、公共 API 或其他产品模块。原 `ResourceControls` / `ResourceTableFilter` 的 Main 修复保持原 SHA。
- 改前已检查 Git 状态；`symbol_locator whereis ProcessTable` 未找到 JSX 函数，随后实际核对本文件定义、调用位置和 `ResourceTableHeader` / `ResourceTables` 的像素约定。私有定位缓存未写回共享 callgraph；`compound/` 未找到相关已知边界。

## 实测

- 私有完整源码：`/private/tmp/aps-final-master-C-process-fix.Rx1tBZ/source`，3577 files。含 mode 清单的聚合 SHA：`268a712aa93737152a2c4c4747ad7780c89598b0fb604894e6441721e1fddb66`。
- 完整构建：`66b45a266409ca4d996bade37149f4044180fa5bbe9c8fb289e5912f9f87c79c`，222 files / 314 inputs，Chrome 109。
- 真实浏览器根：`/private/tmp/aps-workbench-live-jb7nijn7`。原 28 分母保持，28 passed / 0 failed；76 screenshots、1314 steps。新增列宽合同是原场景内部 11 项 × 四组合，共 44 项，全部通过，没有拿它们充当 44 个独立业务场景。
- 覆盖首次 24px 拖动时全部非目标列不变、ArrowRight 8px、Shift+ArrowRight 32px、ArrowLeft、Home 56px、最小值再向左不越界、重复正反向拖动、真实 pointer capture 中 Escape 取消、修改另一列。核对表总宽等于全列实宽总和，取消恢复 cursor/user-select 原状态。
- 1920x1080、1392x924 的 light/dark 均跑过。C 实际查看八张最小宽度/重复与取消后截图，未见列内容错叠、按钮溢出或页面横向溢出；这是 C 的视觉检查，不代替 Main 的最终 V 签认。
- Main 两处共享修复在同一全入口继续通过：原筛选菜单结果变短/变长后可继续勾选，内部 wheel 不关、外部独立 wheel 会关，祖先 overflow-anchor 原值/priority 恢复；批次新增关闭后原按钮自然恢复焦点；嵌套 Modal 背景锁及真实长正文滚动正常。
- 原业务 SQLite 行级前后相同，重启保留通过；服务 15704/16347 正常退出、隔离违规 0。分别加载 1106/1051 个项目模块，全部来自副本且哈希匹配；source_changes=[]。结束后再次检查全部 3577 文件通过。
- 非预期浏览器错误 0、外部请求 0。123 条只读取消单列保留；探针只增加精确 facet POST 的 `ERR_ABORTED` 分类。16 个独立负/正例确保写命令、其他 HTTP 方法、其他网络错误不被忽略。旧报告仍保留当时的分类，不反改成通过。
- 定点 Python 11 passed（含新增分类合同）；16 个 Node 分类检查通过。相关 CJS syntax checks、Ruff 通过；C 服务器 Pyright 为 0 errors / 0 warnings，未升级工具。

## 交接

- 产品改前 SHA：`b2287d8df2dfe8cc9dc5db6f742553698ad11cf567dadf9fba2601aec2fb9d3d`。
- 产品改后 SHA：`df4b057c2946043dc22d320509981826987867309e04231537d357734227654e`。
- `final-master-controls.json` SHA：`2a8af785e8f7470eaef6921fca3bbe29ff7dfb0fad40d796d7fe3ee26bf36755`；`final-master-result.json` SHA：`c1eec0ea22857b1a8acf26b98519a810d81033752d59a90e142f7be8e6802720`。
- 本轮测试写集：`final_master_controls.cjs`、`final_master_filter_controls.cjs`、`final_master_resize_trace.cjs`、`final_master_process_resize.cjs`、`final_master_probe_support.cjs`、`final_master_transport_contract.cjs`、`final_master_server_support.py`、`test_final_master_context.py`。较早同域 Modal/focus 测试继续复用。
- 没有 Git 写操作；由 Main 按 G05 范围归档。未动旧 53144 预览，未改历史失败报告的原始数据，未执行完整整仓质量门禁或 Win7 打包验收。
- 本轮 28 组包含 41 个明确 action IDs，不将其扩张为 C 的 50 项共享动作或 599 项领域动作全部验收完成。
