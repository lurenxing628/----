---
doc_type: audit-index
audit: 2026-09-20-foundation-boundary-review
scope: 基础边界治理路线图（97850695..b227f3a2，29 个提交）的对抗复审——仓储不裁决 / SQL 排水 / 工作台与排产分包 / schema 单一事实源 / 门禁基线；三条只读子代理轨 + 主代理修复与复验
created: 2026-09-20
status: closed
total_findings: 21
subagents_used: 3
verified_by: 主代理定向测试（每个修复提交单独跑定向用例，累计约 4200 例）+ pyright 门禁 0 错 + sync_debt_ledger check 通过；未跑全量门禁（用户明令）
---

# 基础边界治理对抗复审（2026-09-20）

## 复审方式

三条只读 Fable 5.1 子代理轨并行：R1 定向复审（已知合同与修复点）、R2 盲审 A（数据流 / SQL 排水 / schema）、R3 盲审 B（导入期 / 冻结打包 / 门禁与注册表）。主代理汇总后按严重度修复，每组修复单独提交并跑定向测试；随后再派一轮定向复审只看修复。

## 发现与处置

| # | 轨 | 级别 | 发现 | 处置 | 提交 |
|---|---|---|---|---|---|
| 1 | R1/R3 | blocker | pyright 门禁 HEAD 41 错 / 基线 0 错：仓储返回 Optional 后服务层直接下标，`workbench_outsourcing.reject` 缺 NoReturn | 补 NoReturn 与显式 None 裁决 7 处；pyright 归零 | ab7ebd94 |
| 2 | R1 | blocker | `scripts/sync_debt_ledger.py check` 因 factory.py 行号漂移而红 | 受控 `refresh --mode refresh-auto-fields` | 97ac0ae1 |
| 3 | R2 | blocker | 工艺就绪度 `except (RuntimeError, sqlite3.DatabaseError)` 接不住仓储翻译后的 AppError，降级分支失效变 500 | 补 AppError；新增经真实仓储注入 OperationalError 的回归测试 | da7278ca |
| 4 | R3 | major | config.py 搬到 web/bootstrap/app_config.py 后 31 个分组 input_file_scopes 失效，6 个分组在日常门禁增量选组时被静默跳过 | 作用域改到 app_config；合同测试锁住 31 个分组 | 97ac0ae1 |
| 5 | R1/R3 | major | `.codestable/semantics` 语义雷达套件仍 import 已删的 core.infrastructure.errors | 改 core.errors；目录加进错误合同扫描根 | 97ac0ae1 |
| 6 | R2 | major | 四处整表读取从逐行迭代变成 fetchall（历史 Schedule 全版本、日历、指纹整表、回执目录） | BaseRepository.iter_rows；四个方法流式产出；仓储测试锁"不是 list" | 3316638d |
| 7 | R2 | major | `_canonical_sql` 列序不比较后，存档行仍按本模块 DDL 列序解码，迁移链库的存档会静默错位；`--` 注释剥离不认引号 | 按存档 DDL 文本取物理列序（不执行存档 SQL）；引号感知去注释；5 个合同用例 | 0577a3a1 |
| 8 | R2 | major | 六个上提的拒绝码全仓零测试引用 | 24 个策略层用例逐 raise 点锁码 / 状态 / 文案 | 9f8a4172 |
| 9 | R1 | major | move_modules 行号映射用 str.splitlines，换页符 / U+2028 会写坏文件 | 只按 \n 切行；写盘前 ast.parse，失败整批放弃 | 0351ab84 |
| 10 | R1 | major | move_modules globs 替换不看语法上下文，非列表位置会变元组 / SyntaxError | 只在 list/tuple 元素位置替换，其它位置阻断 --apply | 0351ab84 |
| 11 | R1 | major | move_modules 新建子包会遮蔽同名未搬模块 | Plan 校验拒绝 | 0351ab84 |
| 12 | R1 | major | 决策文档"facts/ 业务裁决一律不进"与代码相反 | 改为"只读事实 + 对事实的薄裁决 + 纯助手，写操作不进"并写明理由 | 文档提交 |
| 13 | R3 | minor | 死代码孤岛基线漂移（含本轮搬迁 11 条 quick 误报） | 按 ratchet 决策受控 --refresh | 97ac0ae1 |
| 14 | R3 | minor | 簇分层测试 `_targets` 不认 `import a.b as c` | 补分支 + 单测 | 0351ab84 |
| 15 | R3 | minor | 排产子包间无方向表，已有少量反向边 | 路线图 §4.5 写明"暂不约束方向"，留待另立 | 文档提交 |
| 16 | R1/R3 | minor/nit | 决策文档数字失真（141/385、233 模块、7 个垫片、database_bootstrap 措辞）；ARCHITECTURE / service-scheduler / desktop / .limcode / AGENTS 示例残留旧路径；冻结锚与冻结合同 docstring 过期；pyright gate include 根 config.py | 全部修正（AGENTS.md 为 skip-worktree，仅本地改） | 文档提交 / 97ac0ae1 |
| 17 | R3 | nit | 恢复宿主键名裸字符串；runtime_host 接缝无直接单测 | 改用 RESTORE_HOST_EXTENSION；新增 3 例 | 97ac0ae1 |
| 18 | R2 | minor | `execution_ledger_adapter` 直接读 `repo.clock()` 绕过 `revision_clock()` 裁决 | 改走 `revision_clock()` | 文档提交同批 |
| 19 | R1 | minor | 两处拒绝顺序边缘差异（read_events 先算字节再查行数；append_handling 先查大小） | 码 / 状态不变，仅极端场景文案先后不同，记录不改 | — |
| 20 | R2 | minor | `gantt/adjustment_publish_service.py:109` 嵌套 begin_immediate 静默降级；写语句 rowcount 未核对 | 基线即如此、无生产调用方，不在本轮范围，记录 | — |
| 21 | R3 | minor | `legacy_blueprints ⇄ manual_page ⇄ system_runtime` 新增一条延迟环（正向副作用：说明书页模块在冻结包里由不可达变可达） | 加载顺序正确、环基线只比硬环；未加合同，记录 | — |

## 未做 / 证据不足

- 全量门禁、`tests/workbench` 全目录、三个拒绝 xdist 的算法矩阵测试：按用户明令未跑。
- Windows 打包机真实 PyInstaller Analysis：本机无 PyInstaller，冻结可达性只做了 AST 近似（R3）。
- `.limcode/contracts/ownership_matrix*.json`、`开发文档/` 阶段留痕里的旧路径：历史契约与阶段记录，未改。
