---
doc_type: audit-index
audit: 2026-06-13-post-ad6cfff-commit-review
scope: ad6cfff9398ae0341255deb516f8f74aae22630c 及之后 APS 前端融合相关提交的深度提交审查
created: 2026-06-13
status: resolved
total_findings: 11
open_findings: 0
resolved_findings: 11
resolved_at: 2026-06-13
---

# ad6cfff 之后提交深度审查报告

## 范围

本轮审查的主范围是 `ad6cfff9398ae0341255deb516f8f74aae22630c..505ea0511b1580f1974a890d8791d50cb92586c8`，共 30 个提交。审查期间当前分支后来又新增了 2 个提交：

- `c4ea9b280722c9195d2b63dd3eb0dcd158b0ce0d`：修正视图模型类型检查。
- `7056500b03380fa0be81247f24c6a040a41ca4a6`：同步周派工单打印路由速查。

这两个新增提交不在 30-agent 阵列里，但本报告做了轻量补充核查：`c4ea9b28` 是两个展示字段的类型收口，`7056500b` 是速查文档补 1 行路由，没有额外发现阻塞问题。

## 审查方式

- 使用 CodeStable `cs-audit` 口径，只发现问题，不在本轮直接修代码。
- 按用户授权分两批启动 SubAgent：第一批 16 个，第二批 14 个，合计 30 个，基本做到一个提交一个 agent。
- 对照 `.codestable/roadmap/aps-frontend-fusion/`、相关 feature 设计/验收文档、当前代码和测试。
- 使用项目里的 NetworkX 调用图工具辅助看引用链：
  - `.codestable/checkup/scripts/callgraph_extract.py`
  - `.codestable/checkup/latest/callgraph/`
  - `docs/_panorama_data/callgraph_fresh/`
- 对新文件或调用图暂未覆盖的链路，用 `rg`、AST/源码阅读和提交 diff 补证。

## 总评

这批提交整体是在补 APS 前端融合路线图，方向是对的：运行日志、基线截图、CSS token、词表唯一字源、计划上下文胶囊、手拼链接收编、周计划增强、甘特执行态和甘特控件都在向“前端可用、词表集中、链接不乱、证据可追”推进。

真正的问题不在“完全没做”，而在几类反复出现的边界：

- 有些链路只修了下载包或某个入口，页面入口没有同步修，像运行日志软链接。
- 有些工具看起来会失败，但其实还可能把半成品当成功，像 UI 基线截图。
- 有些地方为了用户体验做了 fallback，但 fallback 之后仍生成可点击链接，用户会以为自己还在看原来的方案。
- 有些“唯一字源”或“路线图闭环”只做了主要路径，旁路字典、验收回写和文档同步还留着旧尾巴。
- 甘特的筛选状态有两套来源：后端 URL 预筛和前端本地筛选，导致“清筛选”与“负荷条带”可能不同步。

按严重度看，本轮没有 P0；发现 P1 8 条，P2 3 条。P1 建议先修，因为它们会造成安全边界、用户误读、结果误判或关键页面数据不一致。

## 发现清单

| # | 性质 | 严重度 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|
| 1 | security | P1 | high | 运行日志页面仍可能读取软链接日志 | [finding-01.md](finding-01.md) |
| 2 | maintainability | P1 | high | UI 基线截图脚本仍可能把坏页面或半截结果记成功 | [finding-02.md](finding-02.md) |
| 3 | bug | P1 | high | 未知排产状态仍可能被汇总数量推成“成功” | [finding-03.md](finding-03.md) |
| 4 | maintainability | P1 | high | 版本下拉框仍有第二套状态文案，复合标签会被压扁 | [finding-04.md](finding-04.md) |
| 5 | bug | P1 | high | 预览/参考方案缺明细时仍会生成 adopted 甘特链接 | [finding-05.md](finding-05.md) |
| 6 | bug | P1 | high | 报表页查看旧版本时计划上下文胶囊可能显示空值 | [finding-06.md](finding-06.md) |
| 7 | bug | P1 | medium | 周派工单打印会把“外协”开头的真实设备名并入外协兜底页 | [finding-07.md](finding-07.md) |
| 8 | bug | P1 | high | 甘特 URL 预筛、清筛选和负荷条带使用的数据范围不一致 | [finding-08.md](finding-08.md) |
| 9 | maintainability | P2 | medium | CSS token 守卫只锁住部分入口，暗色块和裸 hex 证据仍偏弱 | [finding-09.md](finding-09.md) |
| 10 | arch-drift | P2 | high | 部分验收和文档没有把路线图闭环、页面说明、测试说明同步干净 | [finding-10.md](finding-10.md) |
| 11 | maintainability | P2 | medium | 备份提示和前台压测脚本的失败边界仍不够清楚 | [finding-11.md](finding-11.md) |

## 按维度分布

| 性质 | P0 | P1 | P2 | 合计 |
|---|---:|---:|---:|---:|
| bug | 0 | 5 | 0 | 5 |
| security | 0 | 1 | 0 | 1 |
| performance | 0 | 0 | 0 | 0 |
| maintainability | 0 | 2 | 2 | 4 |
| arch-drift | 0 | 0 | 1 | 1 |
| **合计** | **0** | **8** | **3** | **11** |

## 提交对照

| 提交 | 审查结论 |
|---|---|
| `ad6cfff9` | 诊断包软链接风险后续已修，但页面查看日志链路仍需补同等保护，见 Finding 01。 |
| `e86c9c59` | 运行日志页面/诊断包/错误页接门；诊断包拒绝软链接，页面链路遗漏，见 Finding 01。 |
| `b3415f9f` | 运行日志 filter 抽取本身未发现阻塞问题。 |
| `53b6281d` | 运行日志验收闭环有路线图 feature 指针缺口，归入 Finding 10。 |
| `9ba36852` | 基线准备设计方向成立，但后续截图基线守卫仍需 fail-loud，见 Finding 02。 |
| `9a680aac` | 基线截图三件套落地，但成功判定仍偏宽，见 Finding 02。 |
| `5e98670c` | 修过 load 等待与落点校验，但仍没有 HTTP/DOM 级页面正确性校验，见 Finding 02。 |
| `dce22bb5` | Chrome 探测变纯探测函数是好方向，但 Python 入口没有看 failure_kind，见 Finding 02。 |
| `9e26faa7` | 基线验收闭环有路线图 feature 指针和 clean proof 证据缺口，归入 Finding 10。 |
| `dd12e754` | token 设计方向成立，守卫仍有边界，见 Finding 09。 |
| `a1400013` | 曾引入 `--ui-shadow-md` 值错误，后续已由 `d47794e2` 修复；剩余是守卫强度问题，见 Finding 09。 |
| `d47794e2` | shadow-md 回归已修。 |
| `6d16dc55` | token 守卫加强有效，但暗色块和 bare hex 仍有空隙，见 Finding 09。 |
| `b7e3c930` | token 验收有 clean proof / 路线图闭环证据不完整问题，归入 Finding 10。 |
| `ddf080da` | 词表设计文档本身无阻塞问题。 |
| `dc76eb86` | 词表唯一字源落地，但未知状态和版本下拉仍有问题，见 Finding 03/04。 |
| `8d136d6d` | 追加守卫有价值，但没有覆盖“未知状态 + 成功数量”的组合，见 Finding 03。 |
| `ab50f74d` | 词表验收闭环里仍有第二套文案表和路线图闭环缺口，见 Finding 04/10。 |
| `b08bc0ab` | 备份健康提示只读扫描方向正确，未发现阻塞问题。 |
| `7cd4f291` | 手拼链接收编主方向正确，但 fallback_to_adopted 仍会生成误导链接，见 Finding 05。 |
| `ba9a049c` | design 签名同步实现签名，未发现阻塞问题。 |
| `69194630` | 计划上下文胶囊发布点有旧版本空值问题，见 Finding 06。 |
| `682fdabd` | 周计划增强实现方向成立，但页面文案/旧 smoke 仍停在 7 列，见 Finding 10。 |
| `19b17629` | 周派工单打印落地，但“外协”前缀分组有误判风险，见 Finding 07。 |
| `04ee59b1` | 甘特执行事实可视化未发现阻塞问题。 |
| `7a83c970` | 链路巡检功能可用，但左/右方向空结果文案有旧尾巴，归入 Finding 10。 |
| `7300e10b` | 甘特小修包主要问题已修，仍有后端 URL 精确匹配和前端宽松匹配不一致的边界，归入 Finding 08。 |
| `03535ae5` | 甘特负荷条带落地，但没有跟当前筛选同步，见 Finding 08。 |
| `3474016d` | 甘特控件重排后，URL 预筛数据无法真正清回全量，见 Finding 08。 |
| `505ea051` | 备份失败提示和前台压测入口补得有价值，但失败边界仍需再收紧，见 Finding 11。 |
| `c4ea9b28` | 轻量补查：类型收口改动本身未发现新增阻塞问题。 |
| `7056500b` | 轻量补查：速查表补路由，未发现新增阻塞问题。 |

## 已被后续提交修掉的历史问题

- `ad6cfff9` 引入的诊断包软链接泄露，后续 `e86c9c59` 已在诊断包链路修掉；但页面查看日志链路还没同步修，仍是 Finding 01。
- `a1400013` 引入的 `--ui-shadow-md` 错值，后续 `d47794e2` 已修。
- `b3415f9f` 的运行日志 filter 抽取、`ba9a049c` 的 design 签名同步、`b08bc0ab` 的备份健康提示、`04ee59b1` 的甘特执行事实可视化，当前未发现阻塞问题。

## 下一步建议

- **第一批先开 cs-issue 修 P1**：Finding 01、03、05、06、07、08。它们直接影响安全边界、用户是否看错方案、结果是否误判、页面数据是否一致。
- **第二批补工具和守卫**：Finding 02、04、09。它们不一定马上让用户出错，但会让后续回归测试或“唯一字源”保护网变虚。
- **第三批补文档/路线图闭环**：Finding 10、11。它们适合和下一次 acceptance 或小修一起收口，避免后续维护者被旧文档带偏。

## 验证记录

- 本轮审查过程中，子代理对部分提交跑了局部测试，覆盖 CSS token、甘特链路、甘特控件、周计划、周派工单、词表语义等。
- 主线程没有跑全量 `scripts/run_quality_gate.py`。
- 本报告落盘前工作区是干净的；本轮只新增本审计文档，没有改业务代码。

## 修复与复审回写（2026-06-13）

11 条全部处理。逐条结论（接受/部分接受/降级理由）：

| # | 性质 | 处理 | 关键改动 |
|---|---|---|---|
| 1 | security | 接受（定级降 P2） | runtime_log_reader 读原语 + security.py 写侧均加 islink 拦截（写侧不跟随软链接写穿）；补页面链路测试 + Windows skip |
| 2 | maintainability | 部分接受（剔除 profile 那条，定级降 P2） | 截图工具加 Chrome failure_kind + 结果路径集合相等 + HTTP200 + 应用外壳三信号校验 |
| 3 | bug | 接受（真 P1） | derive_completion_status 未知 result_status 诚实降级 unknown，simulated/别名/空值不误伤；显示层兜底改 unknown |
| 4 | maintainability | 接受 | 删第二套词表 _VERSION_OPTION_STATUS_LABELS，下拉框用统一复合标签；4 处旧压扁断言改正 |
| 5 | bug | 部分接受（主诉不成立，降 P3） | 主诉「fallback 链接伪装原方案」经复核不成立（effective_role 已诚实改 adopted、URL/标签同步）；仅采纳次诉——宽 except 拆窄 + 补 logger |
| 6 | bug | 接受（定级降 P2） | reports_index_context limit=1→30 与子页对齐，旧版本号进首页胶囊能查到对应行 |
| 7 | bug | 接受（定级降 P3，例子有偏） | week_plan_print_sheet 改精确形态匹配替代 startswith("外协")；真实触发条件是设备编号而非名称 |
| 8 | bug | 接受（定级降 P2） | 甘特数据接口恒返回全量、批次/资源筛选纯前端（清筛选可回全量）；负荷条带定位为全局容量概览 |
| 9 | maintainability | 接受 | 暗色块退役色断言 + per-file 退役色冻结表（修匹配漏 8 位 alpha 变体的缺陷） |
| 10 | arch-drift | 接受 | items.yaml 4 处 feature 回填 + 周计划文案/smoke 8 列 + 链路巡检方向文案 |
| 11 | maintainability | 接受 | 备份写入异常补 (OperationalError, OSError) 分支转中文（ProgrammingError 仍透传）；压测脚本 --force 守卫 templates_excel |

对抗审核（按指令全程 Codex --fresh + UltraCode workflow 双轨循环）：
- Codex 第一轮：2 BLOCK（#1 写侧跟随软链接、#11 sqlite3.Error 过宽吞编程错误）→ 已修。
- UltraCode 第一轮：1 BLOCK（#9 退役色正则漏 8 位 alpha 变体）→ 已修；其余 PASS。
- UltraCode 第二轮：3 BLOCK 全部确认闭环、5 项测试均「有效」（非 vacuous）；采纳其 2 处非阻塞加固（备份测试钉死 PROPAGATE_EXCEPTIONS、baseline 集合比对防 None 崩溃）。
- Codex 第三轮（收尾确认）：三处收尾改动全部「已闭环、测试真有效、无新引入问题、可合入」；采纳其建议补 `_count_retired_hex` helper 级单测（直接断言 8 位 alpha 变体计入，不依赖生产 CSS 恰有样本）。
- 门禁连带：ensure_secret_key 改动使写回退重分类（observable_degrade→cleanup_best_effort），已同步静默回退台账；reports_page_support.py 修回 ≤500 行。
- 遗留（非阻塞，不做）：`ensure_secret_key` 的 islink→remove→open 非原子，极端并发有 TOCTOU 理论风险——启动期单进程读写自身密钥文件场景已足够，不引入过度防御。
- 验证：新增/改动测试本地全绿；daily quality gate 绿（ruff full + impact pytest 1712+221+5 passed）。最终 full gate（--require-clean-worktree）待提交时跑。
