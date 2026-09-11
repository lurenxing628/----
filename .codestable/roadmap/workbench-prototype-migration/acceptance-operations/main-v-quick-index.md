# F 待 Main 查看：首批代表图和补图清单

补图已完成：固定 source18/build16，4 个独立用例 PASS，20 张补图。[新增图索引](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/visual-supplement-index.md)可直接逐图查看；[完整状态清单](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/main-v-state-map.md)另列 32 张旧独立状态及 5 张尚未查看的 delta 代表。下文保留先交付的首批 6 图和当时精确缺图 ID。

本文件仅映射可见状态，不签署 V，不修改 228 个 action 分母。现有图的 SHA-256 已于本轮逐图核验；未被 Main 查看过的图仍为待审。滚动视口不是全页。

## Main 已签记录

- `../round2-main-v-F-matrix4.json`：原 28 图，仅按该记录中的精确文件引用。
- `../round2-main-v-F-delta.json`：26 图；文件 SHA-256 `64dfe3e2d1c8cdc5f1e529ebf2117d85d68a647b768e30b1f37edcdfa4468a93` 已核验。只覆盖其列明的 26 图及可见场景，不能替代旧 V。delta 的 index 20 是 pending 配置状态下的备份详情，不能冒充 index 23 的普通可操作详情。

## 先看这 6 张现有图

这 6 图均来自 `F13-copy-matrix4`：source `/private/tmp/aps-final-operations-F.TQejHX/F13-source10`，source aggregate `1f9acb1bbdebd53696be4f696b1da3e14f0051515f2927139bae46a5b5906d0f`；build `1417717b6ecfdc897da2af9b5d0302a13f3617ab1ad37b696343df8c9d758c46`，manifest SHA-256 `2bc9704cab900f87760f1d9168597a7b566ef1cf8c77e5cf0a83263e6b336439`。

1. [处置表单，1392/light](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/delivery-following-form.png)：`WBP-DASH-003.edit-status/edit-owner/edit-deadline/edit-action/edit-remark/submit/cancel`、`WBP-DASH-004.edit-completed-at/edit-evidence-ref/edit-completion-result/close` 的字段及操作布局；不代表错误或重开原因框。SHA-256 `a6fb885c28cc31d47027c0f27e8d27ac2632d0016ccbce0662a9be0c25c47548`。
2. [待排批次与齐套，1392/light](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/pending-batches-and-readiness.png)：`WBP-DASH-001.metric-pending`、`WBP-DASH-012.batch/quantity/due-date/ready-status/ready-date/constraints` 的可见表格与约束区；不声称未选中对象的约束详情已看。SHA-256 `90bc1acf6212dcbea0f1929357d96db9779fca578dfe92f3f67157422c2c6e2a`。
3. [外协新增预览，1392/light](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/create-preview.png)：`WBP-DASH-010.preview/save/cancel` 的预览确认布局。SHA-256 `eecc6e4cd2a0d55c31835221a01f11e25d7d8f2e65c3e4a895730a686ac1ad80`。
4. [外协更正预览，1392/light](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/correction-preview.png)：`WBP-DASH-010.correct/preview` 的旧值与新值比较布局；回厂预览可作为同组件文案/值变化的 alternate，不自动标已看。SHA-256 `0b148f4fb3846804d149913bc216bf200a62ab6a51f4fd9914c4bc0195597b6c`。
5. [配置结果未知，1392/light](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/system-config-unknown.png)：`WBP-SYS-018.unknown-result/lookup`、`WBP-SYS-019.pending/unverified` 的原请求保留及只读操作布局。SHA-256 `9d85f31d4c47bbc8b095eacd281749bdc365eea681faf94e04f448569c86c635`。
6. [系统概况与完整 8 项自检，1920/light](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/system-overview.png)：`WBP-SYS-001.metric-page/metric-source/metric-database/metric-backup`、`WBP-SYS-002.row-backups/row-logs/row-config`、`WBP-SYS-003.check-runtime/check-scripts/check-ui/check-icons/check-styles/check-model/check-download/check-theme/rerun/timestamp`、`WBP-SYS-004.download-json` 的可见控件；payload 校验仍是 B/K/P，不由图片证明。SHA-256 `e91e77b24d4a4bebb2a8298d928ed9fafa267365e5c07b4f7abf1bdabfad8e04`。

## 本轮最小补图目标

以下是现有 209 图中未找到完整可见状态的 action ID，不是新增 action，不要求每 action 四张图。只在固定 source18/build16 上创建独立测试和 evidence；旧 source/build/截图及产品均不修改。

- 处置错误：`WBP-DASH-003.reject-invalid`、`WBP-DASH-003.retain-failed-draft`、`WBP-DASH-004.reject-incomplete`。
- 重开原因框及必填错误：`WBP-DASH-005.open-reopen`、`WBP-DASH-005.require-reason`、`WBP-DASH-005.confirm-reopen`、`WBP-DASH-005.cancel-reopen`。
- 执行偏差明细与两个真实落点：`WBP-DASH-008.deviation-table`、`WBP-DASH-008.actual-comparison-navigation`、`WBP-DASH-008.field-report-navigation`。
- 无独立候选提示：`WBP-DASH-014.no-independent-candidate`。
- 外协编辑表单及校验区：`WBP-DASH-009.open-registration`、`WBP-DASH-010.reject-missing-sent`、`WBP-DASH-010.reject-missing-planned`、`WBP-DASH-010.reject-reverse`、`WBP-DASH-010.reject-future-sent`、`WBP-DASH-010.reject-future-return`、`WBP-DASH-010.reject-state-time`。同组件错误提示共用代表布局，保留各分支既有 K。
- 创建/删除备份确认框：`WBP-SYS-008.create`、`WBP-SYS-010.confirm`、`WBP-SYS-010.cancel`；仅打开和取消，不执行创建/删除。
- 配置错误及放弃确认框：`WBP-SYS-017.invalid-fields`、`WBP-SYS-017.discard-confirm`、`WBP-SYS-017.discard-cancel`。
- 展开规则正文：`WBP-SYS-019.scope`、`WBP-SYS-019.request-trigger`、`WBP-SYS-019.skipped`。
- 非紧凑行高：`WBP-SYS-015.compact` 的关闭状态。
- 筛选后空表：`WBP-DASH-002.status-new`、`WBP-DASH-002.status-verification`、`WBP-DASH-002.status-closed`；同一空表组件用一张真实空结果代表，不声称三张都看过。

完整索引已保留每张图的 source/build/path/hash、可见范围、共用理由和未覆盖部分。宽窄、深浅使用已有真实四组合及本轮最小补充组合，不追加四图乘 action 的新门槛。最终 V 由 Main 实际看图签署。
