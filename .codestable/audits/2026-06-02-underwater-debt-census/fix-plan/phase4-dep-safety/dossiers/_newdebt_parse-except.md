# 新引入债扫描 · 解析/数字/收口/except 兜底

- 基线: `b08162cd`
- 当前 HEAD: `c2aa7501`(工作区在此基础上有 resource-dispatch 执行车道重构改动)
- 范围: `git diff b08162cd -- core web data` 的新增行(+ 开头)
- 聚焦: 新宽 except / 新静默 return None|0 兜底 / 新拷贝私有 helper / 新承重不对称无注释
- 铁律: 只读不改; 行号一律 rg/grep 回盘真实 file:line。

---

## 一句话结论

**没有发现"新埋的 P4 静默兜底"。** 传闻中的 "≈12 处新宽 except + ≥4 处 return None" 经逐条回盘:
- 真·新增的宽 except 只有 **4 处**, 其中 3 处是旧债原样搬家(extract-method, 行为不变), 1 处是新文件但属于"loud raise / 已观测降级"合规模式。
- 真·新增的 `return None`/`return 0` 几乎全部是 **合规的可观测降级或受控 sentinel**(配 collector/raise/Optional 签名), 不是静默吞坏值。
- 唯一值得进修复清单的真问题是 **R09 收口不彻底**: 重构新建了规范收口点 `parse_positive_execution_int`, 3 个新文件正确收口, 但 **2 个 baseline 旧 `_positive_int` 内联副本没被收编** —— 这是重构新造出的"收口不对称"(代码是旧的, 不对称是新的)。
- 1 处新承重 sentinel(`_event_id_for_revision` 的 `return 0`)建议补"我是故意的"注释。

下文逐条给 file:line + 片段 + 定性。

---

## 待 owner 裁断 (owner_pending)

本次扫描不给终态修法/不分配执行批次, 仅透依赖与爆炸半径; 收编与补注释的具体落点交 owner 裁断。

---

## 真问题 (建议纳入修复清单)

### N1 · R09 收口不对称: 2 个 baseline 旧 `_positive_int` 内联副本未收编到新收口点

重构在 **新文件** `core/models/operation_execution_scope.py:9` 建立了规范收口点:

```python
def parse_positive_execution_int(value: Any, field: str) -> int:
    ...  # bool/非数字/<=0 一律 raise ValueError(loud)
```

- 该收口点是 **本次重构新增**(baseline 无此模块), 语义=R09 批准的"垃圾/非正→报错", 是 loud 的(对 None 包装层才转 None)。
- **正确收口的 3 个新文件**(都 import 并 wrap 它, 合规):
  - `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_context.py:28-33` `_positive_int` → wrap 后 `except ValueError: return None`(R09 批准的 optional 语义, 调用方 `_ensure_feedback_target_in_query:109` 显式判 None 再 raise)
  - `core/services/scheduler/operation_execution_scope_read.py:21-26` `_positive_int` → wrap 后 return None(同上)
  - `core/services/scheduler/resource_dispatch_execution_tokens.py:13-18` `_positive_int_text` → wrap 后 **re-raise**(loud)
- **未收编的 2 个 baseline 旧内联副本**(没 import 收口点, 自己 `int(value)`):
  - `web/viewmodels/scheduler_resource_dispatch_execution.py:33`: `_positive_int` 内联 `try int(value) except (TypeError,ValueError): return None; return parsed if parsed>0 else None`
  - `core/services/scheduler/resource_dispatch_execution_service.py:24`: 同上逐字内联
- **回盘核对**: 这两份在 baseline `b08162cd` 已逐字存在(`git show b08162cd:<file> | grep _positive_int` 证实), 收口点模块在 baseline 不存在。所以"重复代码是旧的, 但'有了收口点却不收编'这个不对称是本次重构新造的"。
- **定性**: 不是新 P4 静默兜底(两份内联本身行为正确, 也是 optional→None 语义); 是 **R09 收口债的新暴露面**。修法=把这 2 处改成 import + wrap `parse_positive_execution_int`(收到"已存在"的统一点, 不新建模块, 符合收口铁律)。
- **"第4抄"问题的明确回答**: 已知线索担心的 context 文件 **不是第 4 个裸抄** —— 它 wrap 了收口点(合规)。真正没收编的是 viewmodel + execution_service 这 2 个 **旧** 内联副本。
- 爆炸半径: 低。收编只换实现不换签名(都 `-> Optional[int]`, 垃圾→None 语义一致); 但 viewmodel 第 257-258 行有 `_positive_int(...) or 0` 用法, 收编时需保 None 语义不变(收口点抛错被 wrap 转 None, 与原 `int()` 失败转 None 行为等价, 无回归)。

### N2 · 新承重 sentinel 缺注释: `_event_id_for_revision` 的 `return 0`

`core/models/operation_execution_event.py:156-163`(整块 `validate_operation_execution_event_sequence` 校验机是 **本次新增**, baseline 无):

```python
def _event_id_for_revision(event: Any, *, index: int, total: int) -> int:
    raw = _event_field(event, "id")
    value = parse_int(raw, default=None)
    if value is not None and value > 0:
        return value
    if index < total:
        raise ValueError(f"id is required before following event at {_event_identity(event)}")
    return 0   # <-- 仅末位事件(后面无事件需引用其 id)才允许缺 id
```

- **定性**: 这是 **新承重逻辑** —— `return 0` 只在 `index == total`(序列末位)时成立, 非末位缺 id 会 loud raise。该 0 会进 `previous_event_id` 用于下一条的 `previous_state_revision` 拼接, 是承重的。
- 不是静默兜底(非末位已 raise), 但 "末位可缺 id" 这个不对称没有注释, 后续 LLM 容易误删 `if index < total: raise` 而把 0 透传成普遍兜底。
- 建议: 按承重铁律补"我是故意的"中文注释(说明末位事件无后继、其 id 不参与下游 revision 拼接, 故允许 0; 非末位必须有 id), 并绑 parity/契约测试钉住"非末位缺 id 必抛错"。**不删、不统一、不加形参。**
- 同文件 `_event_field:121-127` 的 `except (KeyError,TypeError,IndexError): return None` 是 attr-or-subscript 多态取字段的"字段不存在"sentinel, 下游 `_event_positive_int`/`_required_contract_text` 对 None 一律 raise, 不是静默吞错; 无需动。

---

## 已澄清: 旧债搬家 (非新债, 不进新债清单)

### C1 · `_parse_execution_time` 静默 return None —— R15 残留, 确认是旧债非新埋

`core/services/scheduler/execution_fact_provider.py:85-95`:

```python
def _parse_execution_time(value: Optional[str]) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None   # <-- 有值但 3 种格式都解析失败时静默吞成 None
```

- 已知线索点名"疑似 R15 未收口残留(坏值 return None 静默)" —— **确认属实, 且确认是旧债不是新埋**: `git show b08162cd:.../execution_fact_provider.py` 显示该 helper 在 baseline 逐字存在(diff 中该区块 0 个 + 行)。文件虽 +103 行被改, 但这个 helper 未动。
- **定性**: 真·静默兜底(末行 `return None` 把"非空但解析不了"的坏时间戳吞成 None, 无降级标记/无日志/无 raise), 违背灵魂线。但它是 **R15 旧债**, 不归本次"新引入债"扫描的修复清单 —— 应回写到 R15 registry 条目, 由 R15 收口处理。
- 提示: 修 R15 时这是真收口点之一(loud raise 或补可观测降级标记, 区分"空值→None"与"坏值→报错")。

### C2 · `resource_dispatch_overdue.py` 整文件 —— extract-method 搬家, 行为逐字不变

`core/services/scheduler/resource_dispatch_overdue.py`(**新文件**)含 1 处 `except Exception as exc`(:37)+ 4 处 `return None`(:34/:43/:54/:63/:70)。

- 回盘: baseline `core/services/scheduler/resource_dispatch_support.py:26-95`(`git show b08162cd:...`)已有 **逐字相同** 的 `extract_overdue_batch_ids_with_meta`, 含同样的 `except Exception as exc` 与同样的 meta 降级写法。
- **定性**: 旧逻辑拆模块搬家 + 切小 helper, 行为不变。且每个 `return None` 都配 `_mark_overdue_degraded(meta, reason=..., message=...)` 写 `degraded/reason/message` —— 是 **可观测降级**(灵魂线明确许可的替代 loud raise 方案), `except Exception` 也把 `exc.__class__.__name__` 记进 reason。不是静默吞错。
- 不进新债清单。(若 owner 想顺手收窄 `except Exception`→`except (json.JSONDecodeError, TypeError, ValueError)`, 那是旧债优化, 另立条目。)

### C3 · `gantt_range.py:33` `except Exception as e` —— extract-method 搬家, loud re-raise

`core/services/scheduler/gantt_range.py:30-33` `_normalize_offset_weeks`:

```python
try:
    return int(offset_weeks)
except Exception as e:
    raise ValidationError("周偏移填写不对，请填写整数。", field="offset_weeks") from e
```

- 回盘: baseline `gantt_range.py:64-66`(在 `resolve_week_range` 内联)已有逐字相同的 `int(offset_weeks)` + `except Exception as e: raise ValidationError(...) from e`。本次只是抽成 `_normalize_offset_weeks` 函数。diff 证实是 `-`(旧内联)→`+`(新函数)的纯搬运。
- **定性**: loud re-raise(转 `ValidationError` 带 `from e`), 不是静默吞错。`except Exception` 偏宽(`int()` 只会抛 TypeError/ValueError), 但这是 baseline 带过来的旧写法, 非新债。不进清单。

### C4 · `scheduler_resource_dispatch_execution_routes.py` 新增 2 处 `except Exception:` —— 路由边界 catch-all, 已 log

`web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:123` 与 `:155`(by-task 变体)是本次新增的 2 处:

```python
except Exception:
    current_app.logger.exception("现场记录加载失败")  # / "填写实际情况失败"
    return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "...请稍后重试。")), 500
```

- **定性**: HTTP 路由边界的 catch-all, **每处都 `current_app.logger.exception(...)` 落日志** + 返回结构化 `ErrorCode.UNKNOWN_ERROR` + 500。是 loud(可观测)的边界兜底, 不是静默吞错。
- 这 2 处是同文件 op_id 变体(:90/:139, baseline 已存在)的逐字克隆, 遵循本文件既有惯例。不是新埋的 P4。不进清单。

### C5 · `operation_execution_event_data_contract.py` 多处 except —— 数据质量检查器, except 即报告

`core/infrastructure/operation_execution_event_data_contract.py`(**新文件**)的 `except sqlite3.Error`(:148/:190/:217)、`except ValueError`(:144/:169)等:

- **定性**: 这是 DB 数据质量巡检模块, 每个 except 都把错误 **转成 issue 字符串上报**(`bad_data_check_error: ...`/`bad_sequence_check_error: ...`/`bad_data: ...id=...`)。except 类型也窄。是 loud-report 模式, 检查器的正确写法。不是兜底。不进清单。

### C6 · `scheduler_analysis_candidate_helpers.py` 新 `(value, failed)` 双通道 —— 保留可观测性, 非静默

`web/viewmodels/scheduler_analysis_candidate_helpers.py:127-191`(本次新增):

- `_coerce_candidate_metric:166` 用 `Tuple[Optional[Any], bool]` 双通道区分 "解析失败 `(None, True)`" vs "缺值 `(None, False)`"; `_candidate_metric_parse_failed:132` 把 `failed` 暴露给下游。
- **定性**: 这是"保留坏数据可观测性"的正向写法(与静默吞错相反)。`_metric_number:156`/`return None`/`_format_metric_value`→`"暂无数据"` 是显示层 viewmodel 的合法 None→无数据 UI 语义。新代码且合规。不进清单。

---

## 其余已核但无问题的新 `return None`(受控 sentinel, 列举备查)

- `core/services/scheduler/resource_dispatch_actual_record_service.py:148/:153` `actual_payload_replay_state_revision -> Optional[str]`: None="非完整回放/无匹配幂等事件", Optional 签名 + 调用方处理。幂等回放查找的合法 not-found。
- `core/services/scheduler/run/schedule_execution_persistence_guard.py:21-24` `_scope_from_fact -> Optional[OperationExecutionScope]`: None="fact 缺 identity 无法建 scope" 的守卫 sentinel, 调用方决策。
- `core/services/scheduler/gantt_week_plan.py:26-27/:30-31` 坏时间行 `return None` 配 `_record_bad_time_row(collector,...)` + `_week_plan_empty_reason` 暴露 `_BAD_TIME_EMPTY_REASON`: 可观测降级, 非静默。

---

## 分层红线自检

本扫描只读, 未引入任何 import; 新文件的 import 方向均为 web→core / core.services→core.models(合规), 未见 core.algorithms→core.services 或 core.models→core.services。0 新增跨层违规(就本聚焦涉及的文件而言)。
