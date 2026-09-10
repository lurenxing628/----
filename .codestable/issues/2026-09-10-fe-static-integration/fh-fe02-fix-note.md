# FH / FE-02 修复交接

- 范围：仅 dispatch-plan.json 的 FE-02 十二个产品文件及专属测试；无 stage、commit、全局构建或现有 preview 操作。
- 工作区原本大量 dirty，十二个产品文件原本均为未跟踪文件；未回退他人内容。不构成 clean-worktree proof。
- 本轮修改前副本：`/tmp/fh-fe02-1m0e1l/before/`。最终可复核证据已归档到同目录 `fh-fe02-evidence/`，包含修改前/第一片/最终 pyright JSON、产品差异、结构扫描、JUnit XML、文件哈希和验证清单。
- `symbol_locator` 已查定义和调用；SCIP 深索引为 2026-07-12，不能当本次新文件的精确全量证据，补用现行静态图和实际引用。多进程重建静态图发生过读取竞态，后续查询串行执行；不改定位工具。

## 第一片：快照对象边界与拒绝终止

- `reject`、历史 `invalid`、采用 `_invalid` 标注真实 `NoReturn`，保持原异常、错误码和状态。
- 通用 `load` 仍允许合法标量；`load_object` / `require_object` 以真实类型检查收窄持久对象，不使用 cast、Any、ignore 或配置豁免。
- repository 对对象列、任务列表、逐行对象和重复明细明确拒绝；原指纹、持久明细比较、事务、回执和版本保护保留。
- 历史 admission 的 input/baseline/source 在使用前检查为对象，缺失 admission 行明确拒绝。
- 定点 pyright 使用原 `pyrightconfig.gate.json`，十二文件修改前真实复现 108 errors，第一片后 10 errors。
- 定点运行 FE-02 六个 regression 文件及专属测试：109 passed in 24.85s；第一片修改文件 ruff 通过。

## FD 注册交接

- 新增 `tests/workbench/test_fe02_trial_static_contract.py`，请 FD 注册为 workbench 必跑回归。本代理未修改 registry。
- 最终专属文件共 49 个用例，覆盖合法 SQLite 嵌套值与非有限 REAL 无损往返、指纹、对象拒绝、畸形持久对象、读取零写入、回调缺失、raw 参数契约、候选缺表、容量与普通批次前序边界。
- 本次结束前未发现 FD 已注册该文件的证据，注册仍待 FD 接手；不把交接写成已注册。

## 第二片：已检查值与事实绑定

- 授权方法返回刚检查通过的原回调，预览和采用使用同一回调对象；保留缺失回调、未接入集成、point 渲染未接入的拒绝。
- 缺少计划身份明确拒绝；候选原始 `PartOperations` / `ExternalGroups` 表缺失明确报 `trial_base_incomplete`，不使用当前事实替代。
- raw repo 的 `params=None` 按基类契约表示无参数，位置参数和命名参数不变；容量只有分子/分母均有证据且分母大于零才计算比率。
- 仅在 `trial_base.py` 内按职责提取 `_attach_original_context` 和 `_batch_predecessors`；保留原始执行事实、工艺、外协绑定及 pieces 专用前序路径。
- 原 `_predecessors` 复杂度 17 拆为 8/10；缺表拒绝一度使 `prepare_base` 达到 17，提取原始事实绑定后为 5/13。没有删分支或压缩行数。

## 最终验证

- Python：仓库 `.venv/bin/python`，真实版本 3.8.10。未升级依赖、运行时或外部资源；未在真实 Win7 设备运行，不能声称 Win7 实机验证。
- 原 `pyrightconfig.gate.json` + FE-02 十二文件：修改前 108 errors，第一片后 10，最终 0；没有修改配置、添加 Any/cast/ignore 豁免。
- 十二个产品文件及专属测试 ruff 通过；调用项目 `scan_complexity_entries` / `scan_oversize_entries`：均无超限。
- 最终版本 15 个定点测试文件：202 passed in 48.89s。包含派工六个 regression 文件、专属测试，以及 trial lifecycle/edges/validation/adoption boundaries 和真实 point/pieces 链。
- `test_ea_zero_duration_chain.py`、`test_piece_chain_end_to_end.py`、`test_piece_chain_execution.py`、`test_piece_chain_boundaries.py` 均通过；覆盖 point 保持零时长、pieces 单件数量、正式采用后创建/修改/保存/再采用、重开数据库、原 refs、旧场景/旧正式计划、幂等重放和事务回滚。
- 最终回归前后十二个产品文件及专属测试的 SHA-256 一致，详见 `fh-fe02-evidence/verification.json`。只是 dirty 局部验证；未执行全仓质量门禁、浏览器全页测试、长容量或全局构建。

## 产品改动清单

- `core/models/workbench_trial.py`
- `core/models/workbench_trial_codec.py`
- `core/services/workbench/trial_adoption.py`
- `core/services/workbench/trial_adoption_history_evidence.py`
- `core/services/workbench/trial_adoption_storage.py`
- `core/services/workbench/trial_base.py`
- `core/services/workbench/trial_capacity.py`
- `data/repositories/workbench_trial_raw_repo.py`
- `data/repositories/workbench_trial_repo.py`

`core/services/workbench/trial.py`、`core/services/workbench/trial_adoption_history.py`、`web/routes/workbench/trial_adoption_history.py` 的错误随根因修复消除，本轮未改其字节。

## 阶段状态

- FE-02 产品修复和定点验证已完成；没有剩余 FE-02 pyright 红项。
- 新增测试的 FD 注册仍是交接待办。其他簇/其他新诊断只保留原待办，不进入下一轮。
- 本轮九个产品文件、一个新增专属测试和交接证据均未 stage/commit。保留原工作区全部已有改动；此处停止。
