# Apply 后定向回归命令

以下仅是Main完成G05/17并授权退役后的命令清单，**本轮没有执行、没有起host**。不复用在跑的B目录，不改E sealed06、V4或原preview。

## 新底本要求

- Main指定新的 `ROOT=/private/tmp/aps-g-retirement-candidate-<unique>`，包含同一G05/E-D-F基准的 `baseline/`（不挂载/不删资产）与 `source/`（A+B后候选）、`harness/`及对应新manifest。完整构建用Main已核实的sealed06构建，不用V4旧bundle。
- harness使用现有 `legacy-retirement/factory-tests/*.py`。原V4 `FactoryCase` 会在factory之后再次安装dispatcher，**不能直接在已正式挂载的factory上运行**。仅在新ROOT中应用 [post-mount-harness.patch](post-mount-harness.patch)，旧SHA `e265ea8aa7c805920db5a73202422a891fb4ca84ade89bd8b617687bc1d4750a` → 新SHA `88c04451ad3850539dd8c969c49fc76ac9319e1aba1923c75ace412ab419df2e`。
- 该harness overlay只观察并委托真实factory的installer调用，以保存安装前函数身份；要求真实调用恰好一次且完整51项registry已安装。缺挂载直接失败，不替factory补装，不伪造flash；baseline必须未挂载。该调整目前只做过3.8语法解析，运行结果待实际回归。
- 用E/Main现行封存入口重新capture/check候选与baseline；保留全部事实源（包括正常conftest台账、两种原cycle baseline及必要文档）。C删除后重建manifest，不能继续使用包含已删文件的旧manifest或盲复用旧extra_paths。
- 每轮用新的run名，先检查source/hash/mode，保存前后manifest、harness SHA、结果/HTML/文件/DB回读和日志。正常conftest、原基线与失败断言不绕过。

## 源绑定与纯解析

在新的候选source目录中，使用原解释器；下列 `ROOT` 必须已由Main设置为上述新目录。

```bash
: "${ROOT:?请先指定新私有ROOT}"
PY=/Users/lurenxing/GitHub/----/.venv/bin/python
cd "$ROOT/source"
"$PY" -B "$ROOT/harness/source_binding.py" check "$ROOT/source" "$ROOT/candidate-manifest.json"
"$PY" -B "$ROOT/harness/source_binding.py" check "$ROOT/baseline" "$ROOT/baseline-manifest.json"
FACTORY_SOURCE_MANIFEST="$ROOT/candidate-manifest.json" "$PY" -B "$ROOT/harness/frozen_pytest_worker.py" "$ROOT/source" "$ROOT/runs/after-apply-unit" tests/workbench/test_final_navigation_boot.py tests/workbench/test_final_legacy_navigation.py tests/workbench/test_final_legacy_navigation_layering.py tests/workbench/test_final_legacy_report_dates.py tests/gate_meta/test_architecture_fitness.py::test_routes_do_not_execute_sql_directly tests/gate_meta/test_architecture_fitness.py::test_routes_do_not_import_repository tests/gate_meta/test_architecture_fitness.py::test_services_do_not_import_flask_request
PYTHONPATH="$ROOT/source" "$PY" -B -m tools.scan_import_cycles --fail-on-new-cycle
PYTHONPATH="$ROOT/source" "$PY" -B -m tools.scan_import_cycles --include-tests --fail-on-new-cycle
```

纯解析原V4为46项；含已存在的D-P003八项后，以上选择器预期54项，**这是预期，不是本轮已跑结果**。两种scanner需exit0且旧baseline hash不变。

## 真实旧入口与保留链

```bash
"$PY" -B "$ROOT/harness/run_factory_imports.py" "$ROOT" baseline --manifest baseline-manifest.json --run after-apply
"$PY" -B "$ROOT/harness/run_factory_imports.py" "$ROOT" candidate --manifest candidate-manifest.json --run after-apply
"$PY" -B "$ROOT/harness/run_factory_matrix.py" "$ROOT" baseline --manifest baseline-manifest.json --run after-apply
"$PY" -B "$ROOT/harness/run_factory_matrix.py" "$ROOT" candidate --manifest candidate-manifest.json --run after-apply
FACTORY_SOURCE_MANIFEST="$ROOT/baseline-manifest.json" "$PY" -B "$ROOT/harness/factory_report_worker.py" "$ROOT/baseline" "$ROOT/runs/after-apply-baseline-reports"
FACTORY_SOURCE_MANIFEST="$ROOT/candidate-manifest.json" "$PY" -B "$ROOT/harness/factory_report_worker.py" "$ROOT/source" "$ROOT/runs/after-apply-candidate-reports" --candidate
FACTORY_SOURCE_MANIFEST="$ROOT/candidate-manifest.json" "$PY" -B "$ROOT/harness/factory_messages_worker.py" "$ROOT/source" "$ROOT/runs/after-apply-message-normal" normal
FACTORY_SOURCE_MANIFEST="$ROOT/candidate-manifest.json" "$PY" -B "$ROOT/harness/factory_messages_worker.py" "$ROOT/source" "$ROOT/runs/after-apply-message-invalid" invalid-navigation
FACTORY_SOURCE_MANIFEST="$ROOT/candidate-manifest.json" "$PY" -B "$ROOT/harness/factory_messages_worker.py" "$ROOT/source" "$ROOT/runs/after-apply-message-assets" missing-assets
```

- 两侧12组实际preview/confirm、无效/旧基线拒绝、刷新、精确DB与新连接回读、模板/导出字节；这不是全部mode/replace组合。
- 每侧51页+39非页面GET/HEAD、113真实空表单POST；比较两份matrix原结果的endpoint/rule、POST状态/MIME/JSON与39非页面状态/MIME，不只看两个passed。113空表单不是113条完整业务交易。
- 实际打印两角色/原批次/范围/身份警示/备注/print动作，原md下载字节；三条真实提交→旧GET→canonical消息链与仅消费一次。
- C删除后更换为 `after-delete-*` run名，重跑候选组与源检查；baseline保持原样作对照。另逐一检查124路径缺席、56旧静态URL不可取、新资源/手册可取；用最终匹配构建定向验证受影响导航/确认/消息/打印表现。B252的退役前通过不能自动覆盖这些改变。
- 旧UI selector/模板断言的迁移仍按已有 [test-plan.md](../test-plan.md) 对应条目保留业务断言；本次未给它们虚构已修改payload或通过结果。Main最终选择相应门禁，不以删除测试/基线放宽代替处理。

## 证据边界

此文件只准备命令；A+B的mount新SHA、harness observer新SHA以及C删除后的运行均未验收。V4原结果、D-P003局部51passed、E最终9passed和B在跑252各自保留来源，不互相替代。完整质量门禁由Main在最终一致底本上安排；Win7/package/release本轮明确排除，不作为这里的阻断条件。
