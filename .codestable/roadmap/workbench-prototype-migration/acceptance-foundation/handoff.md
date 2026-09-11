---
doc_type: acceptance-evidence
status: snapshot-passed
date: 2026-09-10
scope: B-owned Main foundation, full loaded 64b6 snapshot only
---

# B Foundation 交接

## 结论

- 已完成并通过同一加载快照的 92/92 cases：56 首屏、16 交互、16 故障、4 原页跨宿主重启。108 张截图，156 次正常 production response；正常阶段错误 0，外部请求 0。
- 真实键盘输入的四组合全部通过。20 次输入事件依次为 C、CA、CAT、CAT-、CAT-B，每次原 input 仍 connected/focused，甘特始终 1 份。
- 自有宿主 PID 77281 正常停止后，新 PID 77652 在同一 `http://127.0.0.1:53263` 启动；browser PID 77285 和 4 个原 page/context 保活，未新建页面代替重启检查。两个宿主均 return 0、closed、pending=[]、释放锁，资产无变化、隔离违规为空。
- 两进程内只读前后全部业务行相等。跨启动 75 张表完全不变，只追加 1 条 plugins/load 正常启动审计并调整对应 sqlite_sequence，原行完整保留。
- 已通知 Main 释放 F 的已有文件 integration。本轮 B host/browser 均结束；没有触碰旧 53144 宿主。

## 快照身份

| 项目 | 值 |
|---|---|
| 根目录 | `/private/tmp/aps-final-foundation-B.xYPahs/aps-workbench-live-2y19rdw0` |
| Main 预构建源 | `/tmp/aps-round2-keyfix-build.gT7e6l/static/workbench` |
| build_id | `64b6bfb181a1c4a04c2f3b218de1f8ad9c4a56b306fc3be19e0213899b0bfe77` |
| manifest SHA-256 | `74fe03d0d4ab2115d1c06c0c4649d524efc52dcddd8ff8f14c9ba2d2c9a2aa91` |
| PlanWorkspace 源 SHA-256 | `c8e8139f7a1b3215dfceced802cec04102e979dc95172b78b6b3850c9a58db9a` |
| 资产 / 输入 / 模板 | 215 / 307 / 3，模板独立分账 |
| 浏览器 | macOS Chromium 109.0.5414.46，不是原生 Win7 现场验收 |
| 源码守护 | 1494 条产品树及 B probe 路径，前后差异 [] |
| Python 输入 | 初始进程已加载本地路径 1445、重启进程 1321；各自变动 []，共同 1321 条路径变动 [] |
| 证据边界 | `unchanged_snapshot_not_final_HEAD`，`final_head_bound=false` |

复制时逐资产校验字节数、SHA-256，manifest 按原字节保留；307 项输入在 runner 和两次原 Mainhost 启动时严格校验，并在释放通知前重新核对。产品树守护不包含的 5 个构建工具输入单独列于 `build-input-evidence.json`，未以 undefined 相等冒充源码哈希证明。Mainhost 没有修改或放宽校验。

## 因果与修订

1. 旧 69ab 中断尝试中，5 个真实字符键事件已发生，但输入最后只剩 B，正文含 6 份全局时间轴。307 项构建输入与新 64b6 对比，唯一变化为 PlanWorkspace.jsx，旧 SHA 为 `4b3b06b0abdc33737c7a3f06cf22f918e857b72cceeb42897384842697c4f8e6`。
2. D 将同层分析表和甘特的三处 key 区分后，当前同版本 Chromium 的四组合逐键、焦点、单一 DOM 检查通过，详见 `key-causality.json`。B 没有修改产品代码。
3. 同 64b6 的采证修订轮 `aps-workbench-live-a7lb04zv` 仍保留 complete=false：55/56 首屏、16/16 故障，4 次重启均已执行，但滚动断言失败；92 cases 共 13 个失败，另有字体采集错误。没有把这轮改成通过。
4. B 修正的是测试：给“交付风险”限定真实 plan-actions；等待实际生产响应；真实滚轮停止 180ms 后同时核对 window/main 位置和 history；15MB 字体通过同一浏览器响应的 CDP 32MiB 缓存取字节。没有 fill、写 history 或另行 fetch 字体来替代用户行为/浏览器响应。修订后的全新 fixture 完整重跑通过。

## 证据分账

- `snapshot-evidence.json`：总结果、进程、运行时、隔离、数据保留、原始文件 SHA-256。
- `normal-evidence.json`：76 个正常用例、真实输入、16 次恢复前后对照、鼠标滚动、字体实际响应；原始 API 文件索引在已散列的 browser report 中。
- `fault-evidence.json`：16 次实际命中、原/注入散列、故障时及恢复后图片。不是业务成功证据。
- `template-evidence.json`：index、recovery、unavailable 三个模板的源/私有副本和两个宿主冻结散列。
- `python-input-evidence.json`：两宿主加载路径计数、变化及完整逐路径散列表的文件/JSON pointer。
- `build-input-evidence.json`：307 项实际 manifest 输入、校验阶段、源码差异和守护范围。
- `key-causality.json`：旧/新快照唯一输入差异及逐键证据。
- `screenshots.md`：56 首屏及注入/恢复、输入/新宿主恢复的原图索引。
- `post-verification.json`：2532/2532 正常完成资产响应都有实际散列记录，含 12 次字体响应；232 份正常/故障原始 API 文件、108 张图片及 4 次渲染注入的原脚本散列复核通过。

## 验证与剩余

- 4 项预构建单元测试通过；3 Python 文件 Ruff/Pyright 通过；4 CJS 语法检查通过；完整真实矩阵由 CLI 执行并返回 0。没有把 CLI 运行冒充 pytest 全文件执行，也没有运行整仓 full gate。
- 通过结果只覆盖已加载 64b6 完整应用快照。本次 source_changes=[]，因此没有需要豁免的 F/G 新叶差异；若出现差异，仍须逐文件分辨是否授权新增、未加载，不笼统排除目录。
- 快照通过不代表 F/G 新增叶、F13、各域全业务工作流、最终 HEAD、整仓 clean proof 或原生 Win7 验收通过。产品后续集成和最终稳定 HEAD 验证由 Main 继续。
- 56 首屏已全部做自动像素和 Main 几何检查；B 人工抽检四组合各一张首屏及两张故障图。Main/V 的逐页视觉终审尚未被本报告代签。
- B 新增的 3 Python、4 CJS 和本目录证据未提交；保留其他人的既有修改和暂存。Mainhost、capacity、全局 build 和产品源码不在本轮写集。
