# 深度审查审阅报告

- 时间：2026-04-22
- 范围：当前工作区非甘特改动 + 提交 24f4c93e9660cf920fb7b71426ade459d32a6006 之后的工作区演进
- 方法：根因深挖 + 对抗审查 + 主代理源码复核

## 事实摘要

1. 读取链会把 active_preset_reason 行缺失判定为 provenance_missing。
2. save_page_config 的 hidden repair 放行条件只检查 current_active_preset 是否非空。
3. bootstrap_active_provenance_if_pristine 只在 active_preset 行缺失时才介入，不要求 active_preset_reason 完整。
4. analysis route 已经传 selected_summary_display，analysis 模板当前没有 warning 区块。
5. week_plan 和 history 已经消费 warning_total / warnings_preview，说明共享显示态没坏。
6. quality gate 会执行固定 guard suite，但 analysis 真模板 observability 回归当前不在 guard suite。
7. 本轮没有发现比 config provenance 更强的新 blocker。

## 结论与取舍

### 必须改

- 配置 provenance completeness 合同不一致
  - 判断：P1
  - 证据：读链、保存链、bootstrap、rejected path 对同一半残缺 provenance 的解释不一致。
  - 风险：系统已知 provenance 不完整，但保存后仍可能把状态重分类为命名方案 hidden repair；这是事实链自相矛盾，不是单纯提示文案问题。
  - 建议：统一 completeness 判定，并把保存链 hidden repair gate 改成基于 completeness，而不是基于 active_preset 是否存在。

### 建议同批修

- analysis 页 warning 可见性闭环
  - 判断：P2
  - 证据：route 已传、builder 已产出、模板未消费。
  - 风险：用户在主诊断页低估版本风险，尤其是有 warning 但无 error 的场景。
  - 建议：补模板 warning 区块，并补真模板回归。

- quality gate 与 analysis 真实显示契约绑定
  - 判断：P2
  - 证据：analysis route contract 已进 gate，但 analysis observability 真模板回归未进 gate。
  - 风险：同类漏显问题继续穿过 CI。
  - 建议：把 analysis observability 回归纳入 guard suite，并补 gate 自检。

### 可后置处理

- maintenance 检测 fail-open / fail-closed 语义错位
  - 判断：设计债
  - 证据：factory 按 fail-closed 写了分支，但 backup 层当前吞异常返回 False。

- error.html 重复展示相关字段
  - 判断：低优先级可见性问题
  - 证据：模板会先输出一次 field_label，再在 details 仅含 field 时输出第二次。

## 建议实施顺序

1. 先补 config completeness 交叉回归和 analysis 真模板 warning 回归。
2. 再修 config provenance 主链。
3. 然后把 analysis observability 回归接入 gate。
4. 最后落 analysis warning 展示改动并跑定向回归。

## 合入建议

不建议按现状合入。

只要 provenance completeness 主链还没统一，这批改动就仍有 blocker。analysis warning 和 gate coverage 建议同批收口，因为它们能显著降低同类问题的再次漏过概率。