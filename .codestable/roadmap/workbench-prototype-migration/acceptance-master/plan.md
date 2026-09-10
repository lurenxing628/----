# 任务 C：动作分母与执行计划

- 范围：`master-data` 41 族、`batches` 17 族，共 58 族；首次展开 **599 个原子动作**，详见 `actions.json`。这不是 599 项通过。后续发现遗漏只追加，不删除失败或缩小分母。
- 冻结 planning SHA-256：`0cad8e05a5adbadacf0c2ecef1e56f38bb4c97e6948c1dc5a2fc847bcec1ffb2`。不修改 planning 文件。
- Main 追加的 `WBP-SH-006..009` 本域真实浏览器验收另列 `shared-actions.json`，50 个补充动作；不占用或替换原 599 项，也不承接 SH001..005。
- 写入仅限本目录及 `tests/workbench/test_final_master*.py`、`final_master*.cjs`、`final_master*_support.py`。共享产品、Git、schema、DTO、构建入口和统一正式性能测量均归 Main。
- 当前没有可调用的子代理消息接口；用本记录及阶段汇报向 Main 交付，不派生任务或代理。

## 验收顺序

1. 用真实产品工厂和 `LiveRunServer` 建私有 fixture；只在新建私有根目录内读写 SQLite、日志、锁、备份。完整离线 build 到该目录，不读取旧预览数据库，不发布 `static/workbench`。
2. 先补当前已确认缺口：主数据总览旧浏览器证据是 mock HTTP + 独立组件，不能作为全站 K/B。通过真实侧栏进入主数据总览，验证筛选、分页、详情、维护跳转、CSV、刷新和停机重开。
3. 资源/工艺/批次真实原子动作执行。重点是创建/修改/删除或归档、关联、工艺三步、三种批次导入、复制、下载内容、失败/锁定/冲突和原数据保留。已有 backend/Chrome 证据只在实现和测试源码哈希匹配时逐项复用，明确旧运行日期与理由。
4. 各链保存 B/K/P 实证和 1920x1080、1392x924 深浅四组合截图。K 分开记录 `fill` 与逐键 `pressSequentially`，不得互称。V 仅收集，待 Main 审视后才能置 passed。
5. 停止私有服务、完整保留证据、交付中文 path:line 与命令/结果/源哈希。测试写集自检及定点测试由 C 执行；正式完整门禁、测试注册和归档由 Main 统一运行。

## 证据与失败规则

- 每个动作分别保持 B/K/V/P 状态；纯 UI、不适用持久化等须在该动作写明原因。任何 family 通过都不能自动传播到子动作。
- 真实 API 请求必须对应本轮服务日志、SQLite 结果；浏览器不能 route.fulfill 伪造成功数据。可做显式失败注入，但故障证据与正常路径分开。
- 以全表快照、原有主键行、schema、外键和完整性检查证明保留；“数据库还能打开”不构成保留证明。
- 发现产品缺陷先交 Main 最小 path:line 修法与复现；未获具体写集批准不修改产品。
- 只运行局部验收，不运行 5000 正式性能测量；接到暂停后完成当前测试，停止启动新重任务。

## 已知证据边界

- `tests/workbench/test_master_overview_browser.py` 明确写明 mock HTTP；历史 35 场景、16 图只能证明组件，不能充当真实工厂全站验证。
- 历史资源记录载有多次不同 build；必须逐文件核验，不据文档中的 passed 字样推断当前通过。
- 既有大量 dirty 和唯一 staged `tests/gate_meta/test_frozen_bundle_contract.py` 保留；不 git add/commit/reset/checkout，不清缓存，不动已有源码归档和指定旧预览。

## 第一段即时交接

- 账本合同：`env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-final-master-c-pycache CHECKUP_CALLGRAPH=/tmp/aps-final-master-c-callgraph .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/workbench/test_final_master_manifest.py`，1 passed / 0.88 秒。
- 私有完整构建两次尚未进入浏览器：`/private/tmp/aps-workbench-live-gzdztu65/full-build.log` 和 `/private/tmp/aps-workbench-live-xjt9o7xi/full-build.log` 均报 `Unresolved script globals in workbench/app/WorkbenchNavigation.js: scrollX, scrollY`。已交 Main 处理其构建合同，不修改本域产品。
- 定位：`WorkbenchNavigation.js:35,75` 读 `window.scrollX/scrollY`；`scripts/workbench/asset_sources.py:143` 浏览器内建符号表当前不含这两项。第二次后读取 HEAD 为 `c0097278`，navigation 源 SHA-256 为 `344e94887045b8b8465fdd5d9dca0d5d50db1289aab76bbccf689c12b6911fab`。
- 可重跑：同上隔离环境前缀，`.venv/bin/python -B -m tests.workbench.test_final_master_acceptance --phase inspect`；成功后 `--phase overview`。`--phase resources` 使用完整真实入口重跑原资源浏览器流程，仍以其实际结果为准，不自动扩展成全部原子动作通过。
- 失败根目录保留，锁已由真实宿主释放；尚无产品数据库连接，隔离违规为 0。Main 19:23+08 的 Git hook 短暂 stash 窗口已知，后续出现瞬时读源漂移先保留重跑，不误判为产品问题。
