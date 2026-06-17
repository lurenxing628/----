# Finding 09：旧 APS 专项入口仍指向迁移前测试路径

- 优先级：P2
- 结论：`.limcode/skills/aps-*` 仍被项目允许作为 APS 专项参考入口，但其中多个脚本和文档已经不能直接运行。

## 根因

P6 期间测试目录做了大规模迁移，真实路径移动到了 `tests/_scripts_e2e/` 和 `tests/gate_meta/`。但 `.limcode/skills/aps-*` 里的历史脚本和说明仍写迁移前路径。

## 证据

- `.limcode/skills/aps-full-selftest/scripts/run_full_selftest.py:316-325`：仍跑 `tests/smoke_phase*.py`。
- `.limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py:47`：找不到 `tests/benchmark_fjsp.py` 就抛错。
- `.limcode/skills/aps-drift-detect/scripts/drift_detect.py:202`：仍跑 `tests/generate_conformance_report.py`。
- `.limcode/skills/aps-drift-detect/SKILL.md:18` 和 `.limcode/skills/aps-arch-audit/SKILL.md:15`：仍写 `tests/test_architecture_fitness.py`。
- 真实新路径包括：
  - `tests/_scripts_e2e/benchmark_fjsp.py`
  - `tests/_scripts_e2e/smoke_phase0_phase1.py` 到 `smoke_phase10_sgs_auto_assign.py`
  - `tests/gate_meta/generate_conformance_report.py`
  - `tests/gate_meta/test_architecture_fitness.py`

## 影响

- 这不是正式 CI 的直接阻塞，因为正式门禁入口是 `scripts/run_quality_gate.py`。
- 但 `AGENTS.md` 仍允许 APS 专项深审、门禁快检、文档联动参考 `.limcode/skills/aps-*`，所以这些入口会误导后续审查和自检。

## 建议

- 修正旧技能脚本路径。
- 如果不准备维护这些旧入口，就在技能说明里明确写“历史参考，不可直接运行”。
