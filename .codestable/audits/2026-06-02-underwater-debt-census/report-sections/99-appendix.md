---

# 附录

## 附录 A · 六类病理定义(本次普查的统一尺子)

> 全 12 分区用同一把尺子,只报符合定义的真债,不报代码风格/命名美观/缺类型注解这类非债。

| 病理 | 名称 | 定义 | 典型反例 |
|---|---|---|---|
| **P1** | 写死常量假冒计算值 | 本应由解析/查询/计算得出的值,被写死的常量/字典/默认值替代,下游拿到假身份/假状态而非真实值 | execution_review 曾用 `ADOPTED_PLAN_RESOLUTION` 常量冒充真实 plan_resolution(已治) |
| **P2** | 承重的不对称(无注释保护) | 某处刻意和同类不一致(别处都传 X 就它禁传、别处都算它写死),这个不一致是故意的、承重的——删了/统一了会出安全事故,但代码里没有任何注释说明"我是故意的" | execution_review 禁带 plan_role/scenario_id 以拦截预览冒充正式复盘 |
| **P3** | 没做完的双实现/迁移残渣 | 同一职责两套实现(新旧并存)、shim 垫片、空目录、被绕过的旧路径,迁移做了一半停下 | 顶层 wrapper、gantt_plan_query 死 shim、双 ScheduleConfigSnapshot 栈 |
| **P4** | 躲过"不自欺"运动的静默兜底死角 | 项目有"坏数据不准静默兜底、宁可暴露错误"的灵魂原则,但仍有死角在 `except: pass` / `return 默认值` / `or 0` 把错误吞掉不暴露 | backup integrity_check 失败只 warning 不阻断 |
| **P5** | 同一概念的第 N 套私有实现 | 某个已有统一收口点的职责,在别处又被私自实现一遍(绕过收口点) | resource_dispatch 的第三套 scope 归一、boolean_normalize 双实现 |
| **P6** | 死参数/死面包屑/死代码 | 参数/函数/常量定义后无人真正消费(只在透传白名单里旅行、或零 caller),却散布多处造成"看起来在用"的假象 | plan_id 死面包屑、死读方法群、死参数 raw_value |

### 关于"失忆债"这个统称

本次普查的 6 类病理,本质是同一种债的不同表现形态:**代码在语法和结构上都正确,但某个概念的"真实含义"在不同地方悄悄分了岔,而没有任何单一权威来裁定哪个含义是对的。** 它不是架构债(结构 0 违规)、不是安全债(非攻击面),其载体不是代码缺陷,而是"丢失的共识"——LLM 当执行者、每个 session 无记忆这一生产方式的必然产物。还它的方式不是重构,是"立约":把丢的共识写回一个权威点,并给承重不对称贴上"别动"。

## 附录 B · 普查产物清单

| 产物 | 路径 | 内容 |
|---|---|---|
| 本报告(细颗粒度) | `.codestable/audits/2026-06-02-underwater-debt-census/REPORT.md` | 全部章节拼装 |
| 报告章节(可重拼) | `…/report-sections/*.md` | 各分区/横切独立 Markdown |
| 分区证据(机读) | `…/findings/_load_bearing.json` `_real_debt.json` | 承重护栏 + 真债结构化数据 |
| 调用图提取器 | `.codestable/checkup/scripts/callgraph_extract.py` | 可复跑(只读,Py3.8)重建调用图 |
| 工作台参数方言测绘 | `.codestable/audits/2026-06-02-workbench-param-dialect/README.md` | 起因:11 页参数方言 |

> ⚠️ 注:`DASHBOARD.md`/`CROSS-CHECK.md`/调用图产物目录(`.codestable/checkup/latest/callgraph/`)在生成期间被并发进程清理丢失,核心结论已并入本报告 §90/§91/§92;调用图可由 `callgraph_extract.py` 复跑重建。

### 调用图规模(基准 65870e47,复跑可重现)

| 指标 | 值 |
|---|---:|
| 函数节点 | 5874 |
| 调用边(总) | 22787 |
| 确信边 / 模糊边 | 7973 / 14814 |
| 动态未消解点 | 576 |
| 环 | 13 |
| 孤岛(零入零出) | 615 |
| 桥接点(articulation) | 772 |
| 高风险数据流路径 | 66 |
| 高扇入咽喉(fan_in≥5) | 60 |

- **§14 第三方复核产物**:`evidence/SemanticDebt/drift/drift-baseline.{json,md}`(drift 全扫 1606 findings)、`evidence/SemanticDebt/agent/drift-agent-brief.md`(triage 简报+A∩B 交叉核验+工具口径校准)、`evidence/SemanticDebt/agent/drift-mds-blindspot.json`(17 组审计盲区 MDS 明细)

## 附录 C · 未决裁断项(需 owner 拍板)

| # | 条目 | 分歧 | 待决 |
|---|---|---|---|
| 1 | `_positive_int` 可空簇该收到哪 | parse_finite_int 对垃圾 raise,契约不符;需新建 `parse_optional_positive_int`(垃圾→None) | **唯一"该收却无现成统一点"的债**——是否值得新增收口点 |
| 2 | `default_plan_resolution_dict` 键集 | 对抗验证称"今日侥幸对齐"但无 parity 测试 | 收口前必须先补 parity 测试坐实 |
| 3 | 双 ScheduleConfigSnapshot 栈 | "27 字段未漂移"依赖手工比对 | 收敛(service 栈复用 model 栈)前先补 parity 测试 |
| 4 | config/summary shim(5 个) | 已证 2 个非测试离线脚本在用 | Win7 离线只能证树内;删除前需确认无树外脚本消费 |
| 5 | `_normalize_critical_chain_result` | git status 标 `A`(未提交),可能是作者合并途中 | 落手前必须问在途作者 |
| 6 | common/number_utils.py | 是有意 delegation-facade(2026-06-01 KEEP/high 裁定)还是半截迁移 | 薄壳化须先重写 monkeypatch 测试 |
| 7 | ready_queue 全量版 | 差分测试基准 vs 遗忘残渣 | needs_adversarial 仍开放 |
| 8 | 延期诊断三件套 | 本分支 `aps-three-gap-directions` roadmap 在途契约 | 现阶段勿删,标在途 |
| 9 | 9 个 scheduler_*.py wrapper | roadmap 明示延期 | 现在动属抢跑,非债 |
| 10 | legacy 错误串往返桥 | P3 真债 vs 仍需兼容的过渡桥 | 改文案会静默失配,收敛前同步检查正则 |

## 附录 D · 置信度标注

**证据充分(可直接行动)**:P1=0、第一档死代码 grep 实证、8 处承重护栏代码实证、图×agent 12 文件双重命中互证。

**需补证(行动前坐实)**:default_plan_resolution_dict 键集"0 漂移"、双配置栈"27 字段未漂移"(均无 parity 测试)、config/summary shim 树外消费、`_normalize_critical_chain_result` 定性(未提交)。

**方法局限**:
- Pass-1 有 2–3 路 agent 因未调用 StructuredOutput 掉线(含关键的 core-models),已由 Pass-2 补扫闭环。
- 调用图调用消解保守:确信边只占 35%,动态调用(getattr/import_module)单列不画假边,故图的扇入扇出是下界。
- 数据流追踪已知噪声:repo/persistence/migration 层 `sensitive-identity→write` 系统性假阳性;config/预设/降级层 `hardcoded→render` 假阳性。
- 树外脚本(Win7 离线运维脚本)无法 grep,死代码判定仅限仓库树内。
- 报告生成期间遭遇并发进程清理 untracked 文件,中间产物经 agent 日志恢复,内容完整但调用图产物目录需复跑重建。
