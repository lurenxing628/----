---
doc_type: issue-fix
issue: 2026-09-08-material-finite-quantities
path: fast-track
fix_date: 2026-09-08
tags: [material, R40, sqlite, finite, rollback]
---

# R40 物料库存非有限数量修复

## 范围与现场

- 按本轮授权直接局部修复；单主线程、无子代理，无 git add / commit / push，不访问或清洗真实业务库。
- 起步已读 AGENTS.md、.codestable/attention.md、.codestable/reference/system-overview.md、项目版 .limcode/skills/cs-issue-fix/SKILL.md，并检索 compound 相关记录。
- 起步 git status --short 显示大量他人的 staged / unstaged / untracked 内容。两个目标产品文件、原 material 回归测试当时无 diff，新测试和本目录当时不存在。
- 本轮只写下面四份文件，全部保持未提交；未修改共享 strict_parse、Material 模型、前端、安装打包、公共台账、测试注册或门禁基线。
- 已运行 symbol_locator 的 whereis / callers / callees 查询 _norm_float、create、update。该版本 callers / callees 只接受裸函数名；类限定名和 --at 查询失败后改用裸名。静态快照为 2026-09-08 02:33，Repository 调用存在 ambiguous / 未含 tests 盲区，因此另读当前源码和测试确认，不将“无 confident 边”当作无调用。
- 当前调用链：MaterialService.create/update -> _norm_float -> MaterialRepository.create/update -> BaseRepository.execute；get/list/list_page 经 Repository 读取和 Material.from_row 映射。

## 根因

- 起始 material_service.py:32-41 的 _norm_float 仅做 float() 与最小值比较。NaN 比较不会触发小于零；正无穷以及 float('1e309') 也会通过。
- 起始 material_repo.py:48-62 的 create 对 Material 实例直接 float(m.stock_qty or 0.0) 后写入，update:64-98 同样只有 float()。Repository 的字典创建原本已经通过 Material.from_row 拒绝非空非有限值，本次保留该既有路径。
- SQLite 参数绑定会将浮点 NaN 变为 NULL；Materials.stock_qty 允许 NULL。共享模型将空值读为 0.0，因而写入成功会掩盖丢失；无穷和非空坏文本则在模型读取时抛缺少物料定位的 ValueError。
- 首版 192 项新合同测试先运行于未改产品代码，实测 95 failed / 97 passed。其中含写入未拒绝、负无穷错误分类不精确，以及读取异常缺少定位的失败，不将全部失败都算作独立缺陷。

## 本轮文件

1. core/services/material/material_service.py:33-44：float 转换后、最小值比较前增加 math.isfinite；非有限值抛 ValidationError，field 仍为“库存数量”。空值和有限负数规则不变。
2. data/repositories/material_repo.py:12-36、42-112：文件内两个 material 专属 helper。创建实例和更新参数在 SQL 前检查有限数，非法写入仍为 ValueError；get/list 的模型解析失败转为 DB_INTEGRITY_ERROR，中文消息带物料编号，details / internal_details 带表、字段、编号与 repr 原值，保留 cause。
3. tests/material/test_material_finite_quantity_contract.py：独立新测试，最终 209 项；旧 test_material_repo_stock_qty_loud_contract.py 未改。
4. 本 fix-note。

## 精确合同

| 边界 | 修复后行为 |
| --- | --- |
| Service.create/update 库存输入 | 拒绝浮点与文本 NaN、正负无穷、大小写及空白变体、1e309/-1e309、Decimal 非有限值；普通非法数字继续拒绝 |
| Repository.create(Material) / update | 数字转换后检查有限性；整条 INSERT / UPDATE 执行前拒绝，无其他字段部分写入 |
| Repository.create(dict) | 继续由 Material.from_row 解析与拒绝坏值，后续入库也经过有限性检查 |
| 合法有限值 | 整数、小数、数字文本、Decimal、科学计数、0、-0.0、最大有限 float 文本与最小正 subnormal 文本均保持可用，不新增业务上限 |
| 创建空值 | Service 的缺省/None/空串/纯空白为 0；Repository 字典同原模型。Material 实例的 None/空串仍写 0，但纯空白仍拒绝，保留原差异 |
| 更新空值 | 未传、None、空串、纯空白均不改库存，其他合法字段仍可更新 |
| 有限负数 | Service 仍拒绝；Repository 旁路与读取原本允许，本轮不额外新增非负规则 |
| 读取坏数量 | Repository.get/list 及 Service.get/list/list_page 遇到实际选中的非空坏值就明确失败，不返回伪造的 0，不跳过坏行，不返回半份列表 |
| 分页与过滤 | 只检查实际读取的行；count/exists 不解析数量，不扫描分页或过滤以外的坏行 |
| 事务 | 继续使用原 TransactionManager；Repository 不自行 commit。非法参数不触发写 SQL；外层未捕获错误整体回滚，调用方捕获校验失败后原有未提交工作仍保留；操作日志写入失败仍回滚物料及同事务日志 |

## 实测结果

环境：macOS，仓库 .venv/bin/python 为 Python 3.8.10，SQLite 3.35.5；未安装或升级依赖，未做 Win7 真机验证。

| 验证 | 结果 |
| --- | --- |
| 首版新测试运行于旧产品代码 | 95 failed, 97 passed in 0.64s |
| 首轮修复及相关回归 | 223 passed in 1.84s |
| 最终独立新测试 | 209 passed in 1.18s |
| 最终合并回归，命令如下 | 243 passed in 2.77s |
| 三份产品/测试文件的 Ruff | All checks passed |
| quality_gate_scan.scan_oversize_entries / scan_complexity_entries，同三份文件 | oversize=[]，complexity=[] |
| 两份 tracked 产品文件 git diff --check | 通过 |
| 暂存 diff 的 SHA-256，修改前与修复后核对 | 均为 952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d |

```bash
.venv/bin/python -m pytest -q tests/material tests/models_domain/test_models_numeric_parse_hybrid_safe.py tests/models_domain/test_strict_parse_blank_required.py tests/models_domain/test_number_utils_facade_delegates_strict_parse.py tests/scheduler_analysis/test_batch_list_pushdown_contract.py tests/excel_data_io/test_batch_material_default_ready.py tests/excel_data_io/test_reports_material_weekplan_pages_smoke.py tests/migration_db/test_transaction_savepoint_nested.py tests/app_runtime/test_app_error_route_contract.py
.venv/bin/python -m ruff check core/services/material/material_service.py data/repositories/material_repo.py tests/material/test_material_finite_quantity_contract.py
```

新测试使用 tmp_path 下的独立 SQLite 文件，页面测试使用项目 db_path/app_client 临时库。非法写入前后比较全部物料行、total_changes 和事务状态；脏读同时比较数据库文件完整 bytes。浮点 NaN 的真实 SQLite 绑定确实变为 NULL，另用返回行注入覆盖“行对象仍包含实际 NaN”的解析路径，两者不混称真实存储场景。

现有页面 HTML/JSON 在普通编号 M002 上均实测 HTTP 409、明确库存错误和物料编号，业务日志包含 Materials、stock_qty、原值 NaN。未编辑任何页面或全局错误处理文件。

## 限制与剩余边界

- 历史 NaN 若已被 SQLite 转为 NULL，无法与合法空值区分。为保持原空值合同，NULL/空串/纯空白仍读为 0.0，不声称可识别或恢复已丢失来源。本轮没有自动清洗或数据迁移。
- 后端异常、结构化详情和业务日志保留精确编号。现有 web/error_boundary.py 会把下划线等内部键形状文本替换为通用提示，已直接核验 M_002 的可见消息仍被替换，但 backend message / internal_details 保持完整；本轮不越界修改该共享显示合同，因此不承诺任意编号都原样显示在页面。
- 本次只修 Materials.stock_qty。BatchMaterials.required_qty/available_qty、其他模块数量、直接裸 SQL、schema 约束及直接 Material.from_row 的公共语义均不改。显式以合法值更新旧坏库存仍是正常业务写入，不是自动修复。
- 未运行完整 scripts/run_quality_gate.py：该入口会清理并重写共享 QualityGate 证据、日志、回执及测试债务产物，超出本轮限定写集；当前大量 dirty 且未提交也无法形成 clean-worktree proof。局部测试、静态检查和页面请求实测不等于完整门禁。
- 新测试由 pytest 默认发现，未加入必跑注册表，未更新 R40 公共台账状态。四份本轮文件均未提交；已有 staged / unstaged / untracked 改动未由本轮回退、清理或覆盖。
