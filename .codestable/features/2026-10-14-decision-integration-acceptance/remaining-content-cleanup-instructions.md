---
doc_type: implementation-instructions
feature: decision-integration-acceptance
status: in_progress
created: 2026-10-14
owner: main-conversation
summary: Windows实例合同接通与剩余主动摘要计算清理
---

# Windows实例合同与剩余摘要清理施工稿

主对话负责本稿及最终代码、运行验收；实施对话执行代码、必要验证和交接。以下位置已由主对话阅读核实。Windows接线修复已单独发出，本稿将其与剩余清理统一记录；界面、性能工作继续按各自施工稿推进。

## 1. 优先修复 Windows 启动器身份接线

`assets/aps-launcher.ps1:206-210/242-243`仍计算SHA256并要求`db_path_hash`及停止令牌摘要。`web/runtime_host.py`已返回`db_path`与独立随机`instance_id`。主对话实际读取原验收实例`51675/system/health`：PID7893、status=ok、contract_version=1，有db_path/instance_id，缺db_path_hash；runtime记录Schema40。这会让Windows启动器拒绝当前健康实例。`tests/app_runtime/test_launcher_startup.py:56-57`仍构造旧摘要响应，掩盖了两端断链。

- `web/bootstrap/entrypoint.py:configure_runtime_contract`在设置owner等配置后调用共同`runtime_identity(app)`，将该实例的同一个公开`instance_id`交给`write_runtime_contract_file`／`_runtime_contract_payload`保存。正常health和恢复状态503 health继续读取同一`app.extensions`身份。
- `web/bootstrap/launcher_contracts.py`的生产、读取及缺项处理一起更新。新合同必须带`instance_id`；旧合同缺项返回真实缺项状态。保持现有端点和合同版本的其他职责；停止令牌继续只用于既有停止授权。
- 路径规范化统一采用现有launcher的`os.path.normcase(os.path.abspath(raw))`语义，与PowerShell的`GetFullPath`及大小写处理一致。共同函数放`web/runtime_host.py`，`launcher_paths.py`旧入口委托它；去掉health单独`realpath`造成的第二套表示。
- PowerShell直接比较owner、PID、规范化数据库路径和合同中的instance_id，删除`Get-ApsIdentityHash`。实例编号独立生成，停止令牌不进入health或普通日志。旧摘要合同不触发摘要回退、自动停止或擅自接管其他实例。
- 更新已有启动用例的真实合同生产者与health接线；错误PID／实例／数据库／owner和恢复状态沿用现有关键覆盖。修正旧`db_path_hash`测试字段。宿主PowerShell与Win7实机分别记录实际执行状态。

## 2. 两个宿主准备脚本

用户明确要求去掉主动密码学计算，当前`content-contract.md`末段自行保留的发行方校验／SRI例外一并修正。Git已有对象ID、上游元数据和归档中已有摘要字符串可以保留原值；本项目不重新计算它们。

| 文件／入口 | 具体修改及保留职责 |
| --- | --- |
| `scripts/prepare_win7_offline.py:load_manifest/verify_file/prepare` | 删除hashlib、sha256计算及64位hex元数据校验。保留固定HTTPS地址、相对路径边界、重名检查、普通文件／非符号链接及文件尺寸检查。原manifest的上游摘要可作为历史元数据原样留存，检查通过文案准确表达“文件齐全且尺寸符合清单”。临时文件和原子替换沿用。 |
| `scripts/workbench/vendor_react.py:checked_payload/main` | 删除hashlib及只为摘要使用的base64。固定包名、18.3.1版本、MIT、精确registry/tarball地址和上游integrity元数据比较继续保留；下载后按现有tar解包、普通成员、包内name/version/license及许可证文字核对。manifest的integrity取已读取的上游元数据原值，结果状态改为准确的导入／来源核对含义。现有目标文件用原bytes比较并保留冲突处理，不另造摘要替代物。 |

本轮不实际下载安装Win7工具、不重导入vendor。使用本地微型文件和替代网络读取验证这两个修改入口，覆盖正常读取及原有尺寸／包身份拒绝即可；记录实际行为，复用现有可用用例，不新建校验框架。

## 3. CI缓存只用既有身份定位

`.github/workflows/quality.yml` restore／save的key保持完全一致，改为：

```yaml
key: quality-long-gate-v2-${{ runner.os }}-py38-ref-${{ github.ref }}-commit-${{ github.sha }}-run-${{ github.run_id }}-${{ github.run_attempt }}
restore-keys: |
  quality-long-gate-v2-${{ runner.os }}-py38-ref-${{ github.ref }}-
```

删除两组`hashFiles`表达式。Git既有commit、run身份只用于找候选缓存；是否有效由当前long v2／shared v4保存的原内容与真实环境比较决定。新前缀隔开旧缓存。复用已经实现的缓存内容核对入口；不增加第二套依赖清单或缓存判断。

## 4. 测试和证据helper按真实责任简化

| 文件 | 具体处理 |
| --- | --- |
| `tests/workbench/run_candidate_support.py:edit_capture` | 编辑facts_json只修改指定原字段，删除重新计算facts_hash的分支与无用import；旧摘要值原样保存。已有甘特历史资料变化用例继续验证真实变化。 |
| `tests/workbench/outsourcing_support.py`、`schema29_regression_support.py`、`dashboard_external_migration_support.py`、`frozen_business_seed_support.py` | 删除读取冻结SQL时的主动摘要计算。继续直接使用原v25—v30 SQL，不重新生成归档；保留已有Schema版本、DDL、外键、业务值及迁移前后比较。仅为摘要存在的参数／变量删除，版本选择保持明确。历史常量如保留须标为历史元数据，避免造成已执行摘要核验的含义。 |
| `tests/workbench/process_commands_support.py:profile_stage_scale` | installed_process_triggers已保存实际SQL，删除重复sha256字段。 |
| 同文件`profile_source_hashes/_profile_main` | 改为内存读取同一既有文件集合的原bytes并直接比较前后，helper与变量按内容职责命名。报告只存文件路径、整体是否相同及变更路径；不把源文件全文或秘密材料另存为证据。 |
| 同文件`profile_noop_confirmations` | `state()`用已有all_table_snapshot所得表数据的规范原内容直接比较；保留排除回执表的原职责。删除state_sha256输出，保留已经存在的all_nonreceipt_rows_unchanged结论及实际阶段记录。 |
| `tests/workbench/dashboard_external_migration_support.py:write_migration_evidence` | 删除database_sha256整组冗余字段；已有带类型的before／backup／after及DDL原件、精确相等检查保留。fixture_sha256若保留只标为既有归档元数据。 |

这些修改不授权重写历史数据库或冻结SQL，不为替换摘要重新制造迁移案例。复用当前对应迁移／甘特／工艺及启动关键用例；helper执行范围与新增用例数量分别记录。

## 5. 交接与主验收

同步`content-contract.md`、阶段8清单和必要交接，删除“发行方/SRI/CI主动计算为保留例外”的现行声明。确认实际产品、宿主脚本、测试helper、Windows启动器及workflow已无本项目主动摘要计算；第三方库代码、Git原身份、历史字段/归档字符串按真实职责区分。

主对话复核共同身份生产与两端消费者、关键路径规范化、脚本实际入口、CI原内容复用，以及冻结历史资料保持。Windows启动链通过后才关闭本P1；整轮界面、性能和第8整体门禁分别记录，已有效且未变的结果继续复用。

## 6. 宿主Jev客户端缓存（主对话追加裁定）

主对话核实`.codestable/tools/jev_client.py`仍由历史审计脚本`2026-09-19-doc-staleness-jev/scripts/run_doc_audit.py:33/241`和`2026-09-20-gate-failure-triage/scripts/triage.py:18/113`调用。保留工具、`JevClient`构造参数、ask返回值和stats形状；本轮不运行这些审计或调用外部API。

- 删除`hashlib`与摘要文件定位。继续使用调用方已有cache_dir，在其中用一个`responses.sqlite`保存原请求／响应：`responses(request_json TEXT PRIMARY KEY, response_json TEXT NOT NULL)`。request_json严格沿原`json.dumps(payload, sort_keys=True, ensure_ascii=False)`，payload仍完整包含state/model/questions；查询直接用原文等值。
- 命中时读取原response_json并照旧累计cache_hits；真实请求成功后保存完整原响应、照旧累计用量。连接仅服务短暂读／写并及时关闭，每次操作使用自己的连接；网络请求在数据库事务之外。沿已有线程锁管理必要的缓存读写和统计，避免在持锁时再次调用会取得同一锁的_account。
- 保留旧摘要命名的JSON文件原件；旧文件缺请求原文，无法对应新原文key，作为旧材料留存。无需遍历旧目录、重算摘要、迁移旧缓存或建立另一份索引清单。
- 固定API地址、授权头、已有错误／重试行为保持。API key不进入缓存key或响应记录。同步模块说明，使其准确描述原文缓存。
- 用临时cache_dir及本地替代HTTP响应核对相同请求命中、实际不同请求不混用、用量统计与失败不写成功缓存；不读取凭证、不向服务发送请求、不扩成宿主测试矩阵。

## 7. `.codestable`宿主及历史脚本的剩余计算

主对话已核对`source-regressions/archived-host-digest-inventory.json`的19份脚本及关键消费链。它们属于本轮主动计算清理范围；旧JSON／JSONL、报告、日志、SQL、数据库、压缩包、patch和冻结源码快照保持原路径原内容。本轮只改可执行脚本及必要直接消费者，不运行会覆盖历史输出的main入口、不重跑历史审计／性能矩阵，不调用外部API。

| 现有脚本组 | 确定改法 |
| --- | --- |
| `issues/2026-09-10-fe-static-integration/{capture_check,analyze_evidence}.py` | 源码及暂存diff前后直接在内存比较原bytes，保持新增／删除文件检测；报告写原路径、数量、变更路径和实际是否相同，不再写源码、stdout/stderr、baseline摘要。原日志及baseline路径已提供原件。 |
| `refactors/2026-09-08-sgs-probe-reuse/{verify,paired_measure,measure,summarize}.py`、`refactors/2026-09-19-sgs-decode-pruning-and-memo/measure.py`、`refactors/2026-09-08-optimizer-candidate-efficiency/benchmark_evidence.py` | 删除已有完整payload等值结论旁的重复payload摘要；真正检查前后来源稳定的函数改用原bytes内存比较，单次来源摘要附项删除。报告保留来源路径和真实变化结论。计时、计数、预算、结果相等口径和原输出文件保留。 |
| `roadmap/workbench-prototype-migration/capture-{source-baseline,current-source}.cjs` | 采样时在内存保留每文件原Buffer；源与解包文件逐字节比较，继续核对文件集合、类型、mode及Git状态／原patch。输出文件清单保留path/size/mode，删除文件、patch、archive摘要；已保存tar包、恢复目录和patch继续承担原件职责。 |
| `roadmap/workbench-prototype-migration/legacy-retirement/factory-tests/source_binding.py`及直接消费者 | 原files条目用path／bytes／mode／content_base64保存可逆原字节，现有manifest升为version 3，删除aggregate摘要。原跨进程来源核对继续逐项比较内容、路径、mode；旧仅摘要manifest保留历史用途，当前验证明确返回缺原内容格式，不重算或自动改写旧manifest。同步`source_guard.py`、`frozen_pytest_worker.py`、`run_factory_matrix.py`、`run_factory_imports.py`和现有`test_source_guard.py`；删除runner脚本摘要附项，保留实际runner路径与运行结果。 |
| 同factory目录`factory_runtime.py`、`factory_report_worker.py`及`draft-tests/build_candidate_manifest.py` | `business_state()`已经保存完整规范JSON，直接返回这份原文做既有前后判等；删除响应摘要，报告沿用已保存响应path/bytes/status。patch审阅继续保存完整patch和AST判断，删除前后摘要。消费方删除对sha256／aggregate_sha256的强取值，准确引用原件路径和实际比较结果。 |
| `roadmap/workbench-manual-remediation/execution-20260915/{production_activation_snapshot,isolated_activation_snapshot}.py` | 沿现有typeof、BLOB.hex、float.hex、列序生成完整类型化行；Counter按该规范原行JSON计数，输出`typed_row_content_counts`及原DDL、完整sqlite_master，保留重复次数和原Schema／外键／integrity检查。两脚本共享现有类型转换职责；删备份文件的重复摘要，保留路径和尺寸。原旧快照不改写。 |
| `checkup/scripts/codemap_extract.py`、`audits/2026-06-30-test-suite-redundancy/scripts/scan_tests.py` | 直接按完整normalized AST、exact_dump及skeleton原文分组，保持原成员、fid、阈值及排序。codemap目前只替换常量且仍保留变量名，本次保持真实口径，并把相关误述改准；不新增第二套编号或摘要。只用于输出附项且无消费者的hash字段删除。 |
| `audits/2026-09-20-gate-failure-triage/scripts/build_corpus.py` | 以完整(nodeid,longrepr)去重，继续首次来源优先；读取既有corpus的同内容→原ID映射，已存在记录沿用原ID。仅新内容使用独立顺序编号`failure-000001`等，编号与去重分开；从既有corpus及triage中的该前缀最大编号继续递增，不复用旧编号。旧hex ID原样保留。triage/render继续按记录ID关联，signature或截短文本不替代完整去重条件。当前旧corpus/triage/report均不执行重写。 |

验证限于Python3.8语法、Node语法、引用／字段消费核对，以及临时目录中的原bytes判等、带类型重复行、AST分组和新旧语料ID小样本；来源绑定沿现有`test_source_guard.py`核对真实内容变化与mode变化。无需新造历史数据或增加一组产品测试。遗留仅摘要报告作为历史记录说明其原格式，不补造原文。

### 第7节冻结后复核：固定来源缺失须保持读取失败

主对话亲自核对发现，`refactors/2026-09-08-sgs-probe-reuse/paired_measure.py:20`和`refactors/2026-09-08-optimizer-candidate-efficiency/benchmark_evidence.py:103`的source_contents加入`if path.is_file()`。对函数明确列出的固定来源，这会把首次采样前已缺失或变为目录的文件两次排除，仍得到sources_unchanged/stable=true，错误缩小实际来源范围。

删除这两个原bytes字典推导末尾的is_file过滤，直接读取已经选定的每条路径；文件缺失或类型错误交原read_bytes明确报出。相同组`verify.py:22`也删除这一过滤，保持同名函数职责一致；该main后续AST读取本已会拦住初始缺失，不另记第二个实际通过误判。动态glob继续按现有真实集合收集并比较新增／删除，不添加空值、跳过列表、路径迁移猜测或新校验框架。

仅用临时目录抽取这几个纯函数，核对正常原bytes、固定文件缺失及目录代替文件的真实异常，复用现有同尺寸修改／增删比较证据；不要运行历史benchmark/main或改写旧报告。其余已核实的source_binding v3、旧语料ID续号和Jev原请求SQLite职责保持。
