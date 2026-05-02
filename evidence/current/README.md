# 当前有效证据入口

本目录只记录“当前可代表主分支或当前阶段分支状态”的证明入口。

## 当前有效证明

- 阶段六完成后，以最近一次 `python scripts/run_quality_gate.py --require-clean-worktree` 的输出为完整质量证明。
- full-test-debt 状态以 `python tools/check_full_test_debt.py` 为准。
- 技术债治理台账以 `python scripts/sync_debt_ledger.py check` 为准。

## 非当前证明

以下目录只作为历史材料，不代表当前通过状态：

- `../Phase0_to_Phase5/`
- `../Phase0_to_Phase6/`
- `../Phase5/`
- `../Phase6/`
- `../Phase7/`
- `../Phase8/`
- `../Phase9/`
- `../Phase10/`

## 更新规则

1. 每次阶段收口只更新本 README 的“当前有效证明”。
2. 不把失败日志伪装成通过证明。
3. 失败证据只放到 `../failures/` 或历史目录，并在文件名中写清失败。
4. 不直接提交完整 `logs/` 目录。
