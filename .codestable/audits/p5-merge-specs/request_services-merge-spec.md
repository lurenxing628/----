# P5.1 MERGE SPEC — 簇 request_services (3 文件, ★REGISTRY)

> 行为保真红线:合并后断言条数必须 >= 各成员之和;去重仅限"逐字完全重复的同义断言"。
> 本簇含「失败传播」与「惰性构造」两种语义,断言禁混禁去重。

---

## ① 成员文件(各行数)

| 文件 | 行数 | test 函数数 | 语义维度 |
|---|---|---|---|
| `tests/regression_request_services_contract.py` | 83 | 3 | 公开契约:cached_property 集合 / 各服务 logger 传参 / 缓存幂等 / 未知属性 AttributeError |
| `tests/regression_request_services_failure_propagation.py` | 61 | 2 | 失败传播:AttributeError→RuntimeError 转换且不缓存失败 / 非 AttributeError 原样上抛且不缓存 |
| `tests/regression_request_services_lazy_construction.py` | 69 | 2 | 惰性构造:首次访问前不构造、不调 backend / 缓存 per-request / excel 用请求 logger 且 backend 仍惰性 |

被测对象统一:`import web.bootstrap.request_services as request_services_mod`(三文件完全一致的导入)。

---

## ② 目标合并文件名 + 命名理由

**`tests/regression_request_services_contract.py`**(保留为合并落点,吸收另两个)

理由:
- 三者同测 `RequestServices` 容器,`_contract` 是最泛、最稳定的命名,且已是 registry `QUALITY_GATE_GUARD_TESTS` 与分组 `target_paths` 的首位成员。
- 保留它=只需从 registry 三处各删 2 行(lazy/failure),不动 contract 行,改动面最小、对账最清晰。
- 备选「新起 `regression_request_services.py`」会迫使三处 registry 全删全加,徒增 B-pin 字符串漂移风险,不取。

---

## ③ 各文件 test 函数清单 + 断言条数 + 关键断言逐字摘录

### A. contract (3 函数, 8 条 assert)

**`test_request_services_contract_without_flask_request_context`** (4 条 + 1 raises)
- `assert public_cached_attrs == expected_attrs`(cached_property 名元组 == `REQUEST_SERVICES_PUBLIC_ATTRS`)
- `assert "__slots__" not in request_services_mod.RequestServices.__dict__`
- `assert services.batch_service is services.batch_service`(缓存幂等)
- `assert created == [("app-logger", "op-logger")]`(BatchService 收到 app_logger+op_logger)
- `with pytest.raises(AttributeError): getattr(services, "undefined_service")` ← **坏值/未知属性边界**

**`test_request_services_exposes_gantt_adjustment_validation_service`** (2 条)
- `assert services.gantt_adjustment_validation_service is services.gantt_adjustment_validation_service`
- `assert created == ["app-logger"]` ← ValidationService 仅收 logger(无 op_logger,签名 `__init__(self, _conn, logger=None, **_kwargs)`)

**`test_request_services_exposes_gantt_adjustment_publish_service`** (2 条)
- `assert services.gantt_adjustment_publish_service is services.gantt_adjustment_publish_service`
- `assert created == [("app-logger", "op-logger")]` ← PublishService 收 logger+op_logger

### B. failure_propagation (2 函数, 6 条 assert)

**`test_request_services_converts_attribute_error_and_does_not_cache_failure`** (4 条 + 1 raises) ← **核心:AttributeError 不能泄漏成属性缺失**
- `with pytest.raises(RuntimeError, match=r"RequestServices\.batch_service"):` ← **异常类型转换 + 正则 match,逐字 load-bearing**
- `assert "batch_service" not in services.__dict__`(失败不写缓存)
- `assert isinstance(recovered, _FlakyBatchService)`(第二次成功)
- `assert services.batch_service is recovered`(成功后才缓存)
- `assert calls["count"] == 2`(确实重试构造了第二次)

**`test_request_services_propagates_non_attribute_error_without_cache`** (3 条 + 1 raises) ← **核心:非 AttributeError 原样上抛,不转换**
- `with pytest.raises(ValueError, match="boom"):` ← **ValueError 不被吞/不转 RuntimeError,逐字**
- `assert calls["count"] == 1`(只构造一次,未重试)
- `assert "config_service" not in services.__dict__`

### C. lazy_construction (2 函数, 14 条 assert)

**`test_request_services_is_lazy_and_caches_per_request`** (8 条)
- 构造前:`assert created == []` / `assert backend_calls == []` / `assert "config_service" not in services.__dict__`
- 首次访问后:`assert first is second` / `assert created == [("config", "app-logger", "op-logger")]` / `assert backend_calls == []`(config 不触发 backend) / `assert "config_service" in services.__dict__`

**`test_request_services_excel_service_uses_request_logger_and_backend_is_still_lazy`** (8 条) ← **excel 专属:backend 惰性触发 + 关键字 backend= 传参**
- 构造前:`assert created == []` / `assert backend_calls == []` / `assert "excel_service" not in services.__dict__`
- 首次访问后:`assert first is second` / `assert backend_calls == ["called"]`(excel **触发** backend,与 config 相反) / `assert created == [("backend-token", "app-logger", "op-logger")]` / `assert "excel_service" in services.__dict__`
- 注:`_StubExcelService.__init__(self, *, backend, logger=None, op_logger=None, **_kwargs)` — backend 是 **keyword-only**,与其它服务的位置参 `_conn` 不同,**不可与 config 参数化混用**。

---

## ④ 共享 setup → 建议 fixture

三文件**无任何 DB/app 依赖**,被测对象是纯内存的 `RequestServices(db=object(), app_logger="app-logger", op_logger="op-logger", get_excel_backend=lambda: ...)`。

- **不需要 conftest 的 db_path / app_client / schema_conn 等任何 fixture**(本簇是纯单元级,object() 占位即可)。
- 共享样板仅为 `db=object(), app_logger="app-logger", op_logger="op-logger"` 三个常量入参。建议抽一个**本文件内的轻量工厂** `_make_services(monkeypatch, *, get_excel_backend=...)`,而非进 conftest(此模式仅本簇用,进 conftest 反而污染全局)。
- `monkeypatch` 全部用 pytest 内置,无缺口。
- **缺口:无**。conftest 现有 fixture 均与本簇无关,无需新增。

---

## ⑤ 参数化方案

**只把同质的"各服务 logger 传参 + 缓存幂等"维度参数化;失败传播与惰性差异禁混。**

可参数化(contract 的三个 expose 类 + 隐含的 batch):差异维度 = (服务名 attr, monkeypatch 目标类名, 构造期望 created 形态)。但三者 stub 签名不一(validation 只收 logger / publish+batch 收 logger+op_logger),`created` 形态不同 → parametrize 需把"期望 created"也作为参数。

建议保守参数化边界:
- **可合**:三个 `test_request_services_exposes_*` + contract 内 batch 段的"缓存幂等 + logger 传参"→ 1 个 `@pytest.mark.parametrize` 覆盖 (attr_name, stub_class, expected_created)。
- **禁合,各自独立保留**:
  - `__slots__ not in` + `public_cached_attrs == expected_attrs`(契约元数据,非按服务循环)→ 留独立函数。
  - 未知属性 `pytest.raises(AttributeError)`(坏值边界)→ 留独立。
  - failure_propagation 两函数(异常语义:转换 vs 原样)→ **整体保留,禁参数化**(两者 raises 的异常类型/match/calls 计数/重试语义全不同)。
  - lazy 两函数(config 不触发 backend vs excel 触发 backend,且 excel 是 keyword-only backend)→ **整体保留,禁参数化**(backend_calls 期望相反:`[]` vs `["called"]`,是行为对立面,合并即丢边界)。

> 即:参数化收益仅限 contract 内 3-4 个高度同构的 expose 段;其余 8 个语义独立函数原样平移。

---

## ⑥ load-bearing import / importlib 引用(grep 核实)

grep 全仓(`*.py/*.yaml/*.yml/*.toml/*.cfg/*.ini`)对三个文件名的引用,**除自身外**命中如下,全部是**字符串路径登记**(无 `import`/`importlib`,删原文件不会触发 import 报错,但会触发 registry 断言失败):

1. `tools/test_registry_data.py:136-138` — `QUALITY_GATE_GUARD_TESTS` 元组成员(见⑦)
2. `tools/test_registry_groups_misc.py:60-62` — `request_services_runtime_error_boundary` 分组 `target_paths`(见⑦)
3. `tests/test_run_quality_gate.py:680-682` — 硬编码断言列表,逐条 `assert high_value_path in module.REQUIRED_TEST_ARGS`(见⑦)
4. `tools/quality_gate_ledger.py:167` — **仅 markdown 文档字符串中的说明文字**(SP04 批次说明),提及 lazy/failure 两文件名。非可执行登记,但合并删文件后该说明会指向不存在的文件 → 见⑩风险。

派生链(决定改 registry 后哪些自动联动):
- `scripts/run_quality_gate.py:92` `REQUIRED_TEST_ARGS = list(iter_quality_gate_required_tests())` ← 由 registry 的 `QUALITY_GATE_REQUIRED_TESTS`(= SELFTEST + `*QUALITY_GATE_GUARD_TESTS`)动态生成。**改 test_registry_data 后 REQUIRED_TEST_ARGS 自动少两项**,因此 `test_run_quality_gate.py` 硬编码断言列表**必须同步删两项**,否则断言失败。

---

## ⑦ registry 影响:tools/test_registry_data.py + 联动条目("旧 → 新")

合并后落点保留 contract,删除 lazy 与 failure_propagation 两个物理文件 → 三处登记**各删这 2 行**,保留 contract 行不动。

### 7.1 `tools/test_registry_data.py`(★必改,QUALITY_GATE_GUARD_TESTS,行 136-138)
```
旧:
    "tests/regression_request_services_contract.py",
    "tests/regression_request_services_lazy_construction.py",        ← 删
    "tests/regression_request_services_failure_propagation.py",      ← 删
新:
    "tests/regression_request_services_contract.py",
```
净变化:**删 2 条目**(保留 contract)。

### 7.2 `tools/test_registry_groups_misc.py`(★必改,group `request_services_runtime_error_boundary` 的 target_paths,行 60-62)
```
旧:
    "tests/regression_request_services_contract.py",
    "tests/regression_request_services_lazy_construction.py",        ← 删
    "tests/regression_request_services_failure_propagation.py",      ← 删
新:
    "tests/regression_request_services_contract.py",
```
净变化:**删 2 条目**。

### 7.3 `tests/test_run_quality_gate.py`(★必改,硬编码断言列表,行 680-682)
```
旧:
    "tests/regression_request_services_contract.py",
    "tests/regression_request_services_lazy_construction.py",        ← 删
    "tests/regression_request_services_failure_propagation.py",      ← 删
新:
    "tests/regression_request_services_contract.py",
```
净变化:**删 2 条目**(否则 `assert high_value_path in REQUIRED_TEST_ARGS` 因 REQUIRED_TEST_ARGS 已少两项而失败)。

> **registry_entries_to_update 计数:3 个文件、共删 6 行字符串(每处 2 行)**。合并后 contract 仍登记,新增的参数化/平移函数随文件被收录,无需新增条目。

---

## ⑧ B-COMPAT pin:必须逐字保留、禁去重的断言

以下断言是行为契约的红线,**合并后必须逐字保留,禁止以"看起来重复"为由去重或合并**:

1. `with pytest.raises(RuntimeError, match=r"RequestServices\.batch_service"):`
   — AttributeError→RuntimeError 转换 + 服务名出现在消息中(failure_propagation)。
2. `with pytest.raises(ValueError, match="boom"):` + 紧随的 `assert calls["count"] == 1`
   — 非 AttributeError 原样上抛、且**不重试**(failure_propagation),与下面第 4 条的 `count == 2` 是对立语义,禁合。
3. `assert "batch_service" not in services.__dict__` / `assert "config_service" not in services.__dict__`
   — 失败不写缓存。两处分属 batch / config 不同服务,**非重复,均保留**。
4. `assert calls["count"] == 2`(failure_propagation 转换分支重试成功)vs `assert calls["count"] == 1`(非 AttributeError 分支不重试)— 对立,禁去重。
5. `assert backend_calls == []`(config_service 不触发 backend)vs `assert backend_calls == ["called"]`(excel_service 触发 backend)
   — lazy 的两个对立面,**绝对禁合并/去重**(去掉任一即丢失"excel 才拉 backend、config 不拉"的边界)。
6. `with pytest.raises(AttributeError): getattr(services, "undefined_service")`
   — 未知服务的坏值边界(contract),保留。
7. `assert created == ["app-logger"]`(validation 仅 logger)vs `assert created == [("app-logger", "op-logger")]`(batch/publish)
   — 服务签名差异,参数化时须作为 expected 参数区分,禁折叠成同一期望。

> **bcompat_pins 计数:7 组逐字断言/断言对**。

---

## ⑨ 断言条数对账

| 来源 | assert 行(含 pytest.raises 上下文管理) |
|---|---|
| contract | 8（4+1raises / 2 / 2;其中 raises 计 1) |
| failure_propagation | 6（含 2 个 raises) |
| lazy_construction | 14 |
| **合并前总和** | **28** |

**合并后预期:>= 28 条**(行为保真下限)。

- 参数化仅"折叠书写"contract 内 3-4 个同构 expose 段,**运行期断言实例数不减**(parametrize 每个 param case 仍各跑一遍 2 条 → 实例总数不变甚至因覆盖 batch 段而 >=)。
- 8 个语义独立函数(contract 元数据 2 段 + failure 2 + lazy 2 + 未知属性 1)原样平移,断言一条不删。
- **结论:after >= before(28),满足红线。** 若实现者选择不参数化、纯三文件拼接,则精确 = 28。

---

## ⑩ 风险 / 阻塞点

- **[阻塞-中] registry 三处必须原子同步**:删 `test_registry_data.py` 的 GUARD_TESTS 两行会令 `REQUIRED_TEST_ARGS` 动态少两项,而 `test_run_quality_gate.py:680-682` 是**硬编码**断言列表 —— 二者不同步删,`assert ... in REQUIRED_TEST_ARGS` 必失败。`groups_misc.target_paths` 不同步删则该 group 指向不存在文件,可能触发其它 registry 完整性守卫。**三处必须同一提交内一起改。**
- **[风险-低] quality_gate_ledger.py:167 文档漂移**:该处仅 markdown 说明文字提及 lazy/failure 两文件名(SP04 批次说明),合并删文件后说明指向不存在文件。非可执行、不致断,但属文档失真;建议同提交内把该句改为指向合并落点 contract,或标注"已并入 contract"。**不计入 registry_entries(它不是登记数据),单独列为收尾项。**
- **[红线-语义] 失败传播 vs 惰性 禁混**:`calls["count"]==2`↔`==1`、`backend_calls==[]`↔`["called"]` 是成对对立断言,任何"看起来重复就去重"都会抹掉行为边界。已在⑧逐字钉死。
- **[风险-低] excel 的 keyword-only backend**:`_StubExcelService(*, backend, ...)` 与其它服务位置参 `_conn` 签名不同,若强行把 excel 拉进 config 的参数化会因传参方式不符而构造失败 —— ⑤已明确 lazy 两函数禁参数化。
- **[无] import 断裂风险**:全仓无 `import`/`importlib` 直接引用这三个测试模块,删文件不会引发 ImportError;唯一影响面是上述字符串登记。
