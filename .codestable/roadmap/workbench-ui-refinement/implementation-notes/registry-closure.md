# UI 验收登记补齐

本轮 UI 已有 7 条 required 合同；补齐 9 条独立 supplemental 测试，并通过 `test_registry.SUPPLEMENTAL_REGRESSION_GROUPS` 向真实环境指纹消费者接线。原 supplemental 序列和 owner 保留，原显式 opt-in 4 条目标不变；没有把浏览器验证升为默认必跑。

测试预期采用独立字面量 7/9 清单。历史 582/85 快照只剔除明确批准的 UI 两个新组、对应目标及 `test_quality_gate_output_normalization.py`，不自动吸收、排除或修正其他调度优化改动。完整枚举、原顺序、原 owner、缺项和重复拒绝继续验证。

广域 daily 还发现初始 HEAD 已跟踪的 `tests/workbench/test_final_master_domain_ledger.py` 漏登记。主线程核实其用途和初始提交后授权：按同类 `test_final_master_action_ledger.py` 归入既有 `workbench_browser`，仅在末尾追加，并写入独立 post-round1 清单。该测试继续不是 required，不改业务或验收绑定算法。

补齐前混合工作区 registry 回归为 1067 passed / 4 failed：其中历史 count/hash 受另外 26 条 optimizer 新增影响，完整枚举暴露上述漏项，tracked 断言拒绝 root 未暂存的新测试。未放宽 tracked，未调整 optimizer，未执行 root git add/commit。UI 定点一轮为 17 passed。

源版本同步到 UI-only 验证副本时，公共登记 7 个文件按完整字节同步；`test_registry_groups_workbench.py` 只同步这一条 supplemental 追加，保留隔离副本原有不含 optimizer 的 required 列表。另补副本漏掉的精确 `test_quality_gate_output_normalization.py` quality_gate owner 行，与该副本既有 required 清单对齐；root 对应 scheduler 登记源不作修改。

UI-only 登记回归第一段为 **1292 passed / 1 failed**，唯一失败是 `test_long_gate_manifest.py::test_required_groups_cover_required_registry` 仍把 required 组数写成 33；当前 UI 新组应为 34。随后将该合同扩充为独立 UI 7 条清单、原 9 组顺序、新组末位及唯一 owner 的精确预期，保留历史 582 的排除边界。root 文件原有 optimizer 预期完整保留；隔离副本分别应用仅含 UI 的同等补丁。

补验第二段完整运行 `tests/gate_meta/test_long_gate_manifest.py` 和 `tests/gate_meta/test_workbench_ui_registry.py`，结果为 **155 passed in 71.26s**。root 仅运行上述覆盖合同单例及 UI registry，结果为 **7 passed in 2.32s**。这两段是分段回归证据，不表述为同一条整仓命令全部通过，也不是 root clean-worktree proof。没有重复运行先前已通过的 1292 项。

日志分别为 `/tmp/aps-wbui-implementation-20260912/registry-ui-only-final.log`、`/tmp/aps-wbui-implementation-20260912/registry-ui-only-manifest-recheck.log` 和 `/tmp/aps-wbui-implementation-20260912/registry-root-ui-hunk-recheck.log`；同步方式与最终 SHA-256 记录于 `/tmp/aps-wbui-implementation-20260912/registry-ui-only-sync.json`。本次登记收口未修改产品代码或生成资产。
