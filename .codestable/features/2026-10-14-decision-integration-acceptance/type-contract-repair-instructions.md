# Gate04 类型契约修复施工稿

主对话于2026-10-14据第四次完整门禁原始123条诊断、源码及调用链确定。实施对话负责按本稿修改和验证；主对话复核差异与最终运行。原始失败材料保留在 `evidence/decision-integration-acceptance/2026-10-14/full-gate/attempt04-v4/`。前三轮未执行Pyright，第四轮未进入全量pytest。

## 1. 范围与共同规则

- 在真实生产者声明数据形态，在已有判断处表达可空收窄。异构业务DTO允许明确的 `Dict[str, Any]`；不把路由字符串、数值、完整性证据整体改成Any。
- 保留现有未知值、严格布尔／整数区别、公开字段、错误状态、事务、来源缓存、读取时机和数值精度。不加空字典、零值或默认标签来代替缺失资料。
- 不修改Pyright、Ruff、循环基线、门禁配置；不使用ignore。下面列出的局部cast各有已核实的上游不变量，仅表达跨函数或SQL保证，不增加运行时兜底。
- Python3.8：使用typing内的Dict/List/Union/Optional/Literal/TypedDict/overload，避免PEP604与NotRequired。
- 7份共同模块搬移及候选源提取的独立比较仍然有效。本稿对其中delivery_completeness新增的类型声明另行核对，不重做全套搬移比较。

## 2. 混合字段DTO由建立处声明

1. `facts/resource_projection.py` 的资源cell建立处（现234行）：局部 `result: Dict[str, Any]`，保留全部字段和可空旗标。449/452/453行原非空判断、int转换和输出不变。
2. `facts/resource_summary.py:100`：局部 `result: Dict[str, Any]`。113行改为对同一次 `_known` 结果过滤，保留114行整数sum及空集合规则：

   ```python
   known_counts = [value for value in (_known(row, field, work_available) for row in rows)
                   if value is not None]
   ```

3. `facts/preparation_projection.py::project_operation_effort`：返回 `Dict[str, Any]`；分支前声明同型 `result`，缺runtime分支用 `{field: None for field in _FIELDS}` 进行有上下文类型的初始化，另一分支照原字段读取。保持后续update和unknown计算。`run/decision_preparation.py`、`trial/preparation.py`继续直接扩展共同返回值，不逐调用cast，也不新建一套投影类型。
4. `run/decision_impact.py::_arrangement` 的多段初始result（现95行）声明 `Dict[str, Any]`，原segments与data_gaps完全保留。
5. `facts/candidate_baseline.py::AdmissionBaseline` 加类属性声明 `source_state: Dict[str, Any]`。`run/candidate_baseline.py`现142行真实赋值及后续读取顺序保持；不初始化空字典。
6. `run/decision_resources.py::coverage` 现196行改为 `official_tasks = self._official["tasks"] if details else []`；原details循环遍历official_tasks。保留正式投影原预取位置，details=False时仍不取投影。

## 3. 日志、归档解码与写入上下文

### 日志来源类型

`core/services/system/runtime_log_reader.py` 声明三个真实结构：

- `LogEntry(TypedDict)`：head/body/level均为str。
- `LogOrigin(TypedDict)`：device/inode/offset均为int。
- `LogEntryWithOrigin(LogEntry)`：必有 `_origin: LogOrigin`。

`_build_entry`返回LogEntry。`read_log_entries_tail`用三个重载表达include_origin=False默认返回List[LogEntry]、True返回List[LogEntryWithOrigin]、普通bool返回两种List联合。实现返回类型同该联合；保留FileNotFoundError→[]及所有读取异常。读取后先建立原entries；`if origin is not None`分支用带类型的列表推导式 `{**entry, "_origin": {...}}` 构造并返回来源条目，其他情况返回entries。origin仍取同一打开文件的os.fstat，offset仍为region[-1]。不增加第二次stat或默认身份。

`facts/system_reads.py`原字符串截取、时间解析和 `_origin` 读取复用这个准确契约，无需改写业务逻辑。

### 命令原意图

`data/repositories/workbench_command_repo.py::input_content`返回 `Optional[str]`。旧trial.create分支的admission解码后，先确认document为字典；非法外层抛 `ValueError("已保存的试调受理资料结构不完整。")`。随后绑定 `intent = document.get("input")`，沿用 `type(intent) is dict` 后content_text(intent)。合法字典缺input仍按原路径返回None；其余action恢复、回放、冲突和缺原意图行为保持。

### 写上下文

`web/routes/workbench/write_context.py::validate_write_context`将解码异常处理与已存在的结构／作用域校验分开表达。先按原ValueError/TypeError转stale，再直接用if分支确认binding为dict，绑定actions局部值并确认list后做成员判断；其余version严格int且等于2、source、subject_ref检查保持。结构或作用域不符统一沿用原“本页数据和这次操作对不上……”拒绝文案；快照缺失或same不符沿用messages.STALE。删除原把字典收窄藏在valid布尔别名里的写法。token解析、15分钟期限、命令回放先于guard及same原内容比较保持。

`core/models/workbench_command.py::validate_request_key`仅把输入参数注解从str改为object，返回仍str；原isinstance与正则就是共同校验边界。`facts/system_journal.py`不增加第二套检查。

## 4. 既有前置条件的准确表达

- `facts/delivery_completeness.py::deferred_operation_evidence`：在 `issues != ["deferred_operation_evidence_missing"]` 返回分支之后，局部 `payload = cast(Dict[str, Any], payload)`。此唯一issue由 `_archived_deferred` 已确认payload为dict且material_policy为stage产生；补一行说明这一关系。原来源读取与异常语义不变。
- `run/decision_recommendation.py::_support`：tasks分支对 `_drill(...)` 结果作局部 `cast(Dict[str, Any], ...)`，注明before调用已由operations排除不可用基准，其他调用before=False。保留通用 `_drill` 的Optional契约与其他使用处的未知状态；不新加assert或回退。
- `trial/base.py`：validate_manifest后成功取得候选的同一位置，将receipt局部cast为 `Dict[str, Any]`。注释已有候选通过manifest意味着回执存在；原queued/running无收据的底层Optional契约保持。
- `scheduler/run/schedule_candidate_selection.py`：分支前声明 `selected: Any`，沿用此入口既有 `candidates: Sequence[Any]`、`selected_plan: Any`及 `_build_selection(selected: Any)` 的鸭子对象契约，原三分支赋值保持。原稿具体CandidatePlan的cast取消：健康条件只证明非空，没有证明具体实现类。接受分支的非空关系仍来自 `_balanced_assessment` 与 `_health_eligible_critical_best` 的同一健康条件，不新加候选选择规则或fallback。容差计算改为 `reference if tolerance is None else reference + tolerance if key == "overdue_count" else reference * (1.0 + tolerance)`；保持所有limit与比较顺序。
- `scheduler/run/operation_effort.py::_seed_effort`：`source: str = op.source`，生产入口已提供必需来源。保持其他参数和op.id处理，不为这一项扩展整个对象类型改造。
- `scheduler/run/optimizer/process_evidence.py::_snapshot`：evaluation_scope原条件写为 `verified and completion is not None and known`；与known现有定义相同，其他点值、覆盖、segment与采样不变。

## 5. 可选标签键

- `facts/candidate_process.py::_objective` 的name、`facts/candidate_projection.py::algorithm_facts` 的mode/strategy、`facts/run_policy.py` 的objective：各标签读取用 `mapping.get(key) if key is not None else None`。保留原未知值和特殊min_changeover文案。
- `run/decision_selection_explanation.py` 的decisive_step和health state各先绑定局部变量。非空时查询映射及原默认值，空时直接返回同一默认值；原两句默认文案“按保存的比较顺序选出”“未记录”保持。不把未知键写成空串或补造业务名称。

## 6. 历史读取

### catalog与容量

- `history/catalog.py::_invalid`声明 `-> NoReturn`。它始终抛WorkbenchCommandRejected；由此 `_object`已存在的缺payload检查真实收窄，无需额外检查。
- `data/repositories/workbench_history_catalog_repo.py::capacity`声明 `-> Dict[str, Dict[str, int]]`。原每条聚合SQL用 `self.fetchall(...)[0]`取得唯一聚合行：无GROUP BY的COUNT/SUM/MAX聚合总返回一行，COALESCE已保障数值。保持SQL及读取次数；此处直接表达查询的真实形态，去掉原稿cast，不过滤None、补0或改BaseRepository的通用契约。

### 条件

- `history/conditions.py`现297行把relevant_links推导式改为同顺序普通循环：绑定 `qualification = qualifications.get(row["operator_id"])`，沿用原资源／active条件，并在 `qualification is None or machine_types[...] & supported & qualification` 内复用该值。None继续表示未声明技能限制，空集合语义保持。
- 现585行明确 `_compare(production[0], production[1], _CATEGORIES)`。两个来源已在上方固定构建，不通过动态星号让类型器猜参数数量。
- `history/conditions_source.py::_trial`将同一个已赋值saved作为参数传给 `_trial_unplanned(source, saved)` 与 `_trial_input(admission, saved)`，两处 `.get`读取参数。其他来源的self.saved=None保持，不创建空记录；来源path字符串保持。

### 指标

- `history/metrics.py::_numeric`声明 `Optional[Union[int, float]]`，将 `type(value) in (int, float)`改为两个精确type判断或OR。仍排除bool及number返回的显示字符串；不改变历史大整数未知策略。
- `_quantity`先用独立变量 `measured`保存所有可空数，再以新变量known保存 `if value is not None`过滤后的字典；subtotal、unknown、covered_refs与空集合结果保持。
- `_window`先设days=None，在原 `if not absolute` 分支内再取 `query.get("resource_window_days", 7)`。原timedelta只在此分支使用，绝对窗口days仍None。既有异常处理不变。
- 现343行：counts_known完全检查后，只在其True分支把counts局部视作 `List[List[int]]`再按原列sum。保留全量非空检查和totals=None分支，不过滤缺值后冒充完整计数。这个cast的证据就是紧邻的all非空判断及_count返回Optional[int]。
- elapsed_seconds的除法从准确_numeric获得数值，无需在消费处补转换。

## 7. HTTP原参数与共同分页

`web/routes/workbench/run_decision.py::_query`保持真实字符串字典；可明确 `Dict[str, str]`，不在路由重复解析。把现有接受HTTP字符串的服务入口和紧接其后的共同投影参数声明为 `Union[int, str]`：

- decision_queries：read_decision_details、decision_details的page/size。
- decision_completion_queries：read_completion_batches、completion_batches的page/size。
- decision_process：read_process_details、process_details的page/size。
- decision_preparation_queries：read_preparation_details、preparation_details的page/size。
- decision_resources：read_resource_details、resource_details的page/size/heatmap_page/heatmap_size。
- decision_export：read_decision_export的page/size。

decision_resources的read_resource_details、normalize_resource_filters的pressure_threshold声明 `Union[float, str]`。归一后仍为float，原拒绝bool、非有限、范围错误的逻辑保持。`_page`及热图原分页检查继续是唯一解析位置。只沿上述现有传递链补正确注解，不另建查询适配器／泛型框架。

## 8. 已确认的归档工时计算缺陷

`facts/operation_effort_evidence.py::archived_standard_effort`现51—55行：number为公开显示将大整数变成十进制str，随后setup+unit*target会类型失败或字符串运算。保留原setup/unit显示字段，另以局部setup_number/unit_number把number返回的str恢复为int，其余数值或None原样保留；total只对这两个数值按原internal／非空／target精确int条件计算。使用精确int恢复，不float化，不改变公共number对其他消费者的行为。

在现有准备工时测试文件追加一个紧凑用例，直接证明大整数setup/unit和小整数target得到正确算术总量、原显示值保持且缺失仍未知。一个真实bug用例即可，无需参数矩阵或新测试文件。旧trial.create非法外层为明确格式错误，在现有命令／试调原意图用例中补一个原断言路径；复用现有fixtures，不为它建服务或数据集。

## 9. 验证与交接

用户随后再次明确：继续本方案，避免为类型检查堆强转和兜底；主对话亲自核对代码及实际运行，完整门禁通过后再推进。上文局部cast仅限已有明确跨函数证明的四处，不能扩展为通用处理；主对话逐处审查，优先保留简洁、真实的数据流。SQL聚合已直接表达唯一结果行，候选选择沿用原鸭子对象契约，两处均不再使用cast。

1. 保留attempt04原始失败。修改后只跑上述新增真实缺陷用例及这次失败的Pyright配置用于收敛；新增诊断若来自准确契约向下传播，沿本稿同一职责修正并在交接列明，业务语义缺口回主对话确定。
2. 本批冻结后继续原完整dirty Gate：`.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --no-resume --no-long-gate-cache`。它包含Ruff、两种循环扫描、两组类型检查及原全量测试；不先另跑一遍日常全矩阵。通过已有步骤的证据按原覆盖复用，不删除失败记录。
3. 不新增测试框架、不重跑20k性能矩阵、不重做已验收UI或原始导出。本批正常范围数值和事务语义保持；归档大整数实际缺陷用例单独说明。
4. 最终模块冻结后，按上一施工稿完成一次原隔离DB上的正常实例冷启动、身份核实和受影响候选／正式／历史只读检查。主对话随后亲自验收；不写业务库、不重排、不实际采用。
5. 2秒目标与Win7实机状态按实际记录，门禁通过不替代它们；A未验收前不提交推送，B／C依赖不变。

## 10. Gate05工具类型检查的单一根因

第五轮已通过第12步产品Pyright，在第13步 `pyrightconfig.tools.json` 报6条，均为 `tools/long_gate_fingerprint.py::diff_fingerprint_components` 现922—929行对before/after的可空推断。现代码先对一次get作isinstance，又用第二次get作为值，类型器无法将两次调用关联；真实输入是保存的组件字典。

仅把现913—914两条读取展开为局部值的原条件收窄：

```python
before = previous.get("components")
if not isinstance(before, dict):
    before = {}
after = current.get("components")
if not isinstance(after, dict):
    after = {}
```

这是把原已存在的非字典处理作用到同一次读取值，所有content_equal、files比较、组件排序与原因文案保持；不新增cast、额外兜底、摘要或比较层，不修改其他工具函数／检查配置。保留attempt05原失败材料；本次失败的tools类型配置确认清零后，继续原完整dirty门禁，无需为局部绑定新增用例或先跑一套工具测试矩阵。

## 11. Gate06台账自动行号同步

第六轮已通过两组Pyright及第14步Python3.8范围检查，第15步 `scripts/sync_debt_ledger.py check` 报既有回退条目的line_start与当前代码不符。主对话亲读校验器、自动刷新实现及当前代码，再对现有台账的内存副本调用既有refresh_auto_fields预览，未写台账：实际只有12条旧记录的line_start／line_end／last_verified_at，加顶层updated_at，共37个自动字段变化；handler_signature／handler_context、旧永久ID与摘要值、人工治理字段、接受风险、数量和门槛均未变化。8项entrypoint位置后移3行，另4项位置前移1行。预览原件为 `evidence/decision-stage-acceptance/stage-08/debt-ledger-auto-field-preview.json`。

由实施对话执行现有唯一写入口 `.venv/bin/python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`，只同步 `开发文档/技术债务治理台账.md` 既有自动事实。保留attempt06失败原件，对照上述37字段范围核实实际diff；若出现内容／身份／人工判断或条目集合变化，保留证据交主对话核对。不要使用scan-startup-baseline，不新增条目、接受风险或放宽门槛，不手写结构块，也不改扫描器。随后用已有check确认同步，继续原完整dirty Gate；不为行号漂移新增测试或另建台账工具。


## 12. 实际提交钩子入口修复

A提交实际触发`.pre-commit-config.yaml`中的`python tools/git_hook_checks.py`后，两个pre-commit入口均在导入阶段失败：原入口fallback加载顶层`git_hook_cache`，其新增的`from tools.long_gate_schema`又无法找到repo根目录。Ruff尚未执行，Git提交未产生；README已由pre-commit恢复且主对话逐bytes核实。原日志`evidence/decision-stage-acceptance/stage-08/a-git-preparation/commit.log`保留。

具体实现只改宿主入口和现有host测试：

1. 在`tools/git_hook_checks.py`标准库导入之后、任何项目导入之前建立原`REPO_ROOT = Path(__file__).resolve().parents[1]`；与现有`run_quality_gate.py`等直接CLI一致，仅当`str(REPO_ROOT)`不在sys.path时加入。随后统一使用`from tools import git_hook_cache`及`from tools.git_hook_blocked_paths import ...`。删除原ImportError的顶层模块fallback和下方重复REPO_ROOT赋值，保持现有函数/CLI/项目venv重执行语义。
2. `_daily_gate_module`删除已由入口完成的repo_root/sys.path三行，保留原延迟`from scripts import run_daily_quality_gate`及返回。入口统一保证包路径，各子功能沿同一模块身份工作。
3. 在现有`tools/host_tests/test_gate_runner_and_hooks_content.py`新增一个紧凑真实CLI回归：从tmp_path作为cwd，以sys.executable执行绝对路径`tools/git_hook_checks.py --help`；复制当前环境并移除PYTHONPATH，检查exit0及原check-staged-artifacts/run-quality-gate子命令出现。它只验证真实CLI导入和parser，不运行门禁、不读取/改写业务数据。不要mock导入或改pre-commit配置绕开失败。
4. 运行该现有host文件（原两项加新一项）和受影响两文件Ruff；只交原结果。主对话随后更新本轮明确index路径并重试真实commit，以真实pre-commit/commit-msg钩子证明入口已接通。完整pytest、前端构建、正常冷启和Windows均不重跑；此宿主入口修复不影响已通过产品行为。

本次新增一条真实CLI回归、零新测试文件。Git操作始终由主对话完成。原失败与延期事实保持。
