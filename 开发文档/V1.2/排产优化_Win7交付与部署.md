# 排产优化 — Win7 交付与部署

> 归属版本：v1.3.0 | 最后修改：2026-03-12
>
> 总览入口：[APS测试系统_排产优化完整方案.md](APS测试系统_排产优化完整方案.md)
>
> 当前仓库现行交付口径（v1.3.x）：采用“双包交付（`APS_Main_Setup.exe` + `APS_Chrome109_Runtime.exe`）”。若本文中的目标态/历史口径与现状冲突，以仓库根目录的 `installer/README_WIN7_INSTALLER.md` 与 `DELIVERY_WIN7.md` 为准。

## 文档目的

覆盖 Win7 SP1 x64 单机部署的完整交付链：兼容性基线、PyInstaller 打包、运行库依赖、旧技术栈生命周期、运维启停与留痕落盘。

## 当前现行实现补充（v1.3.x）

当前仓库已落地的安装边界，与本文部分“目标态/待接入”条目不同：

- 安装形态：管理员统一安装双包。
- 程序目录：机器级共享。
- 数据目录：机器级共享（默认 `C:\ProgramData\APS\shared-data`）。
- 浏览器 Profile：每用户独立（`%LOCALAPPDATA%\APS\Chrome109Profile`）。
- 运行模型：共享同一套业务数据，但仅允许**单活用户**；第二个账户会被明确阻止进入。

因此，阅读本文时请按以下优先级理解：

1. 当前仓库实现与 `installer/README_WIN7_INSTALLER.md`
2. `DELIVERY_WIN7.md`
3. 本文中的目标态/待接入条目

## 本文边界

- **覆盖**：Win7 兼容交付基线（第 7 章）、旧技术栈生命周期与替代路径、部署与运维（第 11 章，含启动/停止、留痕、result_summary 体积约束、版本回退）。
- **不覆盖**：算法设计（见 [排产优化_核心算法.md](排产优化_核心算法.md)）、测试用例（见 [排产优化_测试验证方案.md](排产优化_测试验证方案.md)）。
- **事实来源**：主文档第 7 章 + 第 11 章合并。
- **合并理由**：两章面向同一读者群（部署人员），Win7 基线讲环境前提，部署运维讲启动/留痕/兜底，合并形成完整交付指引。

## 7. Win7兼容交付基线

> 状态：目标态基线，待接入（仅描述目标交付要求，不代表当前仓库已实现）。

本章用于定义 v2.0 的 Win7 目标交付基线，不代表当前仓库已全部接入。

### 7.1 当前仓库现状与差距（截至 v1.x）

当前仓库与本章目标态之间的主要差距如下：

- 当前运行依赖仍是 Flask/openpyxl 口径，未接入 Numba 运行依赖（见 `requirements.txt`）。
- 当前仓库尚无 `.spec` 打包基线文件（后续需补齐并纳入证据链）。
- 仓库中暂无 `runtime_hook.py` 与 `NUMBA_CACHE_DIR` 回退落地文件。
- 仍以 Web UI 为主线，尚未引入新 UI 运行时依赖。
- 现有证据链以 Web/Greedy 路径为主（见 `evidence/Phase7/smoke_phase7_report.md`、`evidence/Phase10/smoke_phase10_report.md`、`evidence/FullSelfTest/full_selftest_report.md`）。

以上差距项对应的证据索引见 12.3.1。

**旧技术栈生命周期与替代路径（v1.3.0 新增）**：

本项目选择 Python 3.8 / Numba 0.53.1 / NumPy 1.20.3 是 Win7 兼容性的工程现实选择，不等于长期维护无风险：

| 依赖 | EOL 状态 | 已知安全债务 | 替代路径 |
|------|----------|-------------|----------|
| Python 3.8 | 2024-10 EOL | 不再获得安全补丁 | Win7 退役后迁移到 Python 3.10+ |
| NumPy 1.20.3 | 已停维 | CVE-2021-33430、CVE-2021-34141（内网可接受） | 随 Python 升级同步升级 |
| Numba 0.53.1 | 已停维 | 需固定 llvmlite 0.36.0 | 随 Python 升级迁移到 Numba 0.57+ |
| PyInstaller 4.10 | Win7 非官方支持 | 官方声明 Win8+ | 迁移到 PyInstaller 5.x 或 6.x |

**结论**：当前选型在 Win7 目标机的生命周期内可维护（预计 2-3 年）。Win7 退役后必须同步升级技术栈，建议在 ADR 中记录替代计划触发条件。

> 口径说明：本章后续条目均为"目标交付基线（待接入）"，用于实施前对齐，不作为当前仓库"已上线能力"依据。

### 7.2 目标机要求（交付前提）

```
硬前提（必须满足）：
├── 操作系统: Windows 7 SP1 x64
├── 处理器: x64架构（不支持x86/32位）
├── 内存: 至少4GB RAM
├── 磁盘: 至少1GB可用空间（含缓存与日志）
├── 权限: 非管理员也可写缓存目录
└── 补丁: 建议安装以下更新
    ├── KB2999226 (Universal CRT) - 必须
    ├── KB2670838 (Platform Update) - 推荐
    └── KB2533623 (安全更新) - 推荐
```

### 7.3 目标依赖基线（待接入）

```
# requirements_win7_final.txt（目标基线草案）
numpy==1.20.3                  # 与 numba 0.53.1 的历史兼容基线；numpy 1.21 在 #7175 暴露已知问题，后续由 #7176 路线修复
numba==0.53.1                  # 项目 Win7 现场的候选历史基线（非"当前仓库已接入"）
llvmlite==0.36.0               # 与 numba 0.53.x 的配对版本
pyinstaller==4.10              # 项目 Win7 现场实测基线；官方支持口径为 Win8+，Win7 属非官方兼容
pip>=24.0                      # 开发/打包环境建议基线；Python 3.8 可用上限为 pip 24.3.1
```

外部口径依据见 12.3.2（pip 元数据、Numba 兼容议题、PyInstaller 官方 README）。

### 7.4 离线包与 wheel 仓准备（待接入后执行）

```bash
# prepare_offline_packages.sh
pip download \
    --only-binary=:all: \
    --platform win_amd64 \
    --python-version 38 \
    numpy==1.20.3 numba==0.53.1 llvmlite==0.36.0 \
    pyinstaller==4.10 \
    -d ./packages
```

目标交付要求：
- 安装包携带完整 `packages/` 离线仓；
- 首次安装不依赖互联网；
- 依赖清单与 wheel 文件哈希可追溯留档。

**pip 版本说明**：开发与打包环境建议 pip >=24.0（Python 3.8 最高可用 pip 24.3.1）。若现场网络策略复杂，建议使用 wheel 离线升级：`python -m pip install --no-index pip-24.3.1-py3-none-any.whl`。

### 7.5 缓存目录回退策略（目标行为，待接入）

`NUMBA_CACHE_DIR` 建议按顺序尝试：

1. `C:\Users\Public\SchedulerCache\Numba`
2. `C:\ProgramData\SchedulerCache\Numba`
3. `%LOCALAPPDATA%\SchedulerCache\Numba`

目标行为说明：
- 每一层执行"可写性探测（创建-写入-删除）"；
- 首个可写路径即锁定并写入运行日志；
- 若全部失败，切换纯 Python 模式并给出明确提示。

### 7.6 PyInstaller 运行时钩子示例（待接入，非现状）

```python
# runtime_hook.py
import os
from pathlib import Path

def pick_cache_dir():
    candidates = [
        Path(r"C:\Users\Public\SchedulerCache\Numba"),
        Path(r"C:\ProgramData\SchedulerCache\Numba"),
        Path(os.environ.get("LOCALAPPDATA", r"C:\Temp")) / "SchedulerCache" / "Numba",
    ]
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_test"
            probe.write_text("ok", encoding="ascii")
            probe.unlink()
            return str(p)
        except Exception:
            continue
    return ""

cache_dir = pick_cache_dir()
if cache_dir:
    os.environ["NUMBA_CACHE_DIR"] = cache_dir
os.environ.setdefault("NUMBA_NUM_THREADS", "1")  # Win7单机策略
os.environ.setdefault("OMP_NUM_THREADS", "1")
```

### 7.7 首次 JIT 预热与失败回退（目标行为，待接入）

建议目标：
- 启动后展示阶段进度（模型加载 -> 样例解码 -> 缓存写入）；
- 失败自动重试（建议 2 次）；
- 仍失败则切换纯 Python 执行并提示"性能受限但可继续排产"。

### 7.8 杀软与安全策略（交付建议）

- 安装指引给出白名单建议：程序目录、缓存目录、日志目录；
- 记录"缓存写入失败/被拦截"事件，便于现场排障；
- 离线交付包附 `环境自检工具`，用于检查补丁、权限、路径和依赖。

---

---

## 11. 部署与运维

### 11.1 首次启动体验

```python
# first_run.py
from pathlib import Path
from enum import IntEnum

class WarmupStatus(IntEnum):
    NOT_FIRST_RUN = 0
    WARMUP_OK = 1
    WARMUP_FAILED_FALLBACK = 2

def check_first_run(cache_dir: str) -> WarmupStatus:
    """检查是否首次运行，返回枚举状态"""
    flag_file = Path(cache_dir) / ".first_run"
    
    if flag_file.exists():
        return WarmupStatus.NOT_FIRST_RUN
    
    print("首次运行，正在进行初始化...")
    print("这可能需要几分钟时间，请耐心等待...")
    
    instance = create_test_instance()
    fast_decoder = FastDecoder(instance)
    accurate_decoder = AccurateDecoder(instance)
    encoding = DualLayerEncoding(instance.n_jobs, instance.job_op_count)
    encoding.random_initialize()
    
    for retry in range(2):
        try:
            start = time.time()
            _ = fast_decoder.decode_eval(encoding, frozen_ctx=None)
            _ = accurate_decoder.decode_full(encoding, frozen_ctx=None)
            elapsed = time.time() - start
            print(f"初始化完成，耗时{elapsed:.1f}秒")
            flag_file.write_text(f"Initialized at {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="ascii")
            return WarmupStatus.WARMUP_OK
        except Exception as e:
            print(f"预热失败，第{retry + 1}次重试: {e}")
    
    enable_python_fallback_mode()
    return WarmupStatus.WARMUP_FAILED_FALLBACK
```

### 11.2 数据质量检查

```python
def validate_data(instance: DRCJSSPInstance) -> Tuple[bool, List[str]]:
    """数据质量检查"""
    errors = []
    
    for op_idx in range(instance.n_operations):
        # 检查兼容机器
        if not np.any(instance.machine_op_compatible[:, op_idx] == 1):
            errors.append(f"工序{op_idx}无兼容机器")
        
        # 检查兼容工人
        if not np.any(instance.worker_op_compatible[:, op_idx] == 1):
            errors.append(f"工序{op_idx}无兼容工人")
        
        # 检查加工时长（机器相关）
        for m in range(instance.n_machines):
            p = instance.proc_time[op_idx] if instance.proc_time.ndim == 1 else instance.proc_time[m, op_idx]
            if instance.machine_op_compatible[m, op_idx] == 1 and p <= 0:
                errors.append(f"机器{m}工序{op_idx}加工时长无效")
        
        # v1.x 口径：技能不参与时长计算，能力信息仅用于 pair_rank 排序
    
    # 检查 pair_rank（排序元信息）合法性（示意）
    # 要求：rank 非负；对每个兼容人机对都可给出稳定 rank 值
    # 具体数据来源与映射规则见 resource_pool_builder._skill_rank
    
    # 检查family映射
    for j in range(instance.n_jobs):
        family = instance.job_to_family[j]
        if family < 0 or family >= instance.n_families:
            errors.append(f"工件{j}的family映射越界")
    
    # 检查日历不可用区间（按优先级分集合；MAX_UNAVAIL 上限、排序、重叠）
    # 说明：unavail 区间的构造规则见 5.1.1；这里仅做结构合法性门禁，防止"静默截断/乱序"导致误排。
    for p in (instance.PRIORITY_NORMAL, instance.PRIORITY_URGENT):
        p_name = "normal" if p == instance.PRIORITY_NORMAL else "urgent"
        for m in range(instance.n_machines):
            n = int(instance.machine_unavail_count_by_priority[p, m])
            if n < 0 or n > int(instance.MAX_UNAVAIL):
                errors.append(f"机器{m}({p_name})不可用区间数异常：{n}（MAX_UNAVAIL={instance.MAX_UNAVAIL}）")
                continue
            prev_end = np.int64(-1)
            for i in range(n):
                s = np.int64(instance.machine_unavail_by_priority[p, m, i, 0])
                e = np.int64(instance.machine_unavail_by_priority[p, m, i, 1])
                if e <= s:
                    errors.append(f"机器{m}({p_name})不可用区间[{i}]非法：[{s},{e})")
                    continue
                if s < prev_end:
                    errors.append(f"机器{m}({p_name})不可用区间乱序或重叠：prev_end={prev_end}, cur=[{s},{e})")
                if e > prev_end:
                    prev_end = e

        for w in range(instance.n_workers):
            n = int(instance.worker_unavail_count_by_priority[p, w])
            if n < 0 or n > int(instance.MAX_UNAVAIL):
                errors.append(f"工人{w}({p_name})不可用区间数异常：{n}（MAX_UNAVAIL={instance.MAX_UNAVAIL}）")
                continue
            prev_end = np.int64(-1)
            for i in range(n):
                s = np.int64(instance.worker_unavail_by_priority[p, w, i, 0])
                e = np.int64(instance.worker_unavail_by_priority[p, w, i, 1])
                if e <= s:
                    errors.append(f"工人{w}({p_name})不可用区间[{i}]非法：[{s},{e})")
                    continue
                if s < prev_end:
                    errors.append(f"工人{w}({p_name})不可用区间乱序或重叠：prev_end={prev_end}, cur=[{s},{e})")
                if e > prev_end:
                    prev_end = e
    
    return len(errors) == 0, errors
```

### 11.3 异常兜底

```python
class SafeOptimizer:
    """安全优化器（带回退机制）"""
    
    def optimize(self, encoding, time_budget=30.0):
        try:
            # 主流程：IG/TS + 双解码
            full_schedule = hybrid_optimizer.solve(encoding, time_budget=time_budget)
            return full_schedule
        except Exception as e:
            # 异常回退到FastDecode，确保仍可产出结果
            print(f"优化异常，回退到FastDecode: {e}")
            eval_result = fast_decoder.decode_eval(encoding, frozen_ctx=current_frozen_ctx)
            if not eval_result.feasible:
                return diagnose_infeasible(current_frozen_ctx, request=None)
            return build_publishable_schedule_from_eval(eval_result)
```

### 11.4 留痕、日志与可审计性（最小集）

不新增业务功能前提下，排产系统仍需要具备"可追溯、可复现、可解释"的最小留痕能力，避免现场出现"算出了结果但说不清为什么/改了什么"的争议。

#### 11.4.1 最小留痕项（建议必须落盘）

- **输入范围**：本次排产选中的批次 ID 列表（或其哈希）、批次数/工序数、起算时间 `start_dt`、排产截止 `end_date`、数据库 `SchemaVersion`。
- **参数快照**：排序策略与参数、派工方式/规则、目标函数名称、时间预算、是否启用冻结窗口与天数、是否启用自动分配资源等。
- **参数持久化约束（新增）**：v2.0 新增参数（如 `TOPK_MAX`、`D_RATIO`、`ACCURATE_EVAL_INTERVAL`、温度调度与降级阈值）必须与发布版本绑定落盘；推荐"`ScheduleConfig` 存默认值 + `ScheduleHistory.result_summary` 存本次生效快照"的双轨方案。
- **随机性**：随机种子（若使用伪随机扰动），以及迭代/重启次数；建议把种子与 `version` 绑定，确保同输入可复现。
- **硬约束启用状态**：至少记录 precedence / calendar / machine+operator 冲突 / 停机避让 / 冻结窗口 等是否生效；若某约束因加载失败而降级，必须显式标记降级原因。
- **结果摘要**：`result_status`（success/partial/failed）、scheduled_ops/failed_ops、关键指标（L1~L4 或等价目标向量）、超期批次清单（采样）、warnings/errors（采样）。
- **边界声明（新增）**：当本次排产未纳入材料约束优化（`Materials/BatchMaterials` 仅用于上游校验）时，必须在结果摘要输出 `MATERIAL_CONSTRAINT_NOT_OPTIMIZED=true`。
- **无可行解诊断上下文**：触发失败的工序/资源/时间窗、不可行类型（冻结/日历/停机/兼容性/Top-K 截断等）、建议动作（放宽软冻结/合并停机/补齐资源等）。

**`result_summary` 体积边界与裁剪策略（v1.3.0 新增）**：

`ScheduleHistory.result_summary` 以 JSON 存储于 SQLite TEXT 字段。大规模问题（>200 工序）下，若不限制体积，可能导致数据库膨胀和查询性能退化。

- **体积上限**：单条 `result_summary` 的 JSON 序列化后不超过 512KB。
- **超限裁剪策略**：优先裁剪 `improvement_trace`（搜索轨迹）和 `warnings`（采样而非全量），保留 `parameters`、`hard_constraints`、`objective_summary`、`degradation_chain` 等核心字段。
- **裁剪标记**：裁剪后在 JSON 中标记 `"summary_truncated": true` 和 `"original_size_bytes": N`。
- **禁止行为**：禁止因体积裁剪而删除 `degradation_chain` 或 `degrade_reason` 等降级审计信息。

#### 11.4.2 落盘位置（对齐现有实现）

- **ScheduleHistory（DB）**：`ScheduleHistory.result_summary` 存储结构化 JSON（含：策略、参数、hard_constraints、降级信息、attempts/improvement_trace 等），并与 `version/created_by` 关联。
- **ScheduleConfig（DB）**：用于持久化系统默认参数与安全阈值（含 v2 新参数默认值）；发布时实际生效值仍以 `ScheduleHistory.result_summary` 快照为准，避免"默认值漂移"导致不可复现。
- **OperationLogs（DB）**：事务后写入 `OperationLogs` 作为操作留痕（避免 logger 内部 commit 破坏原子性），用于追踪"谁在何时发起排产/模拟"。
- **Schedule（DB）**：最终排程明细落在 `Schedule` 表，作为回溯与冻结窗口 seed 的数据源。
- **Excel 导入审计**：Excel 导入/导出应记录文件名、模式、耗时、错误采样（现有实现已具备审计入口，需在交付指引中明确查看方式）。

---
