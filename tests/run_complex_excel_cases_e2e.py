from __future__ import annotations

"""
复杂排产 Excel 用例 + 全流程 E2E 验证（本脚本会“自己运行 + 自检离谱结果”）。

特点：
- 不依赖启动真实 Web Server：用 Flask test_client 走与 UI 等价的导入/排产/导出链路。
- 每个 case 使用独立临时 DB（不污染仓库 db/ logs/ backups/ templates_excel）。
- 生成并落地 Excel 输入文件到 evidence/ComplexExcelCases/<case>/input/，便于手工复现。
- 排产后做 sanity checks：时间合法、资源不冲突、避开停机、merged 外协组一致性等。

运行示例：
  python tests/run_complex_excel_cases_e2e.py --out evidence/ComplexExcelCases --repeat 3
"""

import argparse
import io
import json
import os
import random
import re
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from excel_preview_confirm_helpers import build_confirm_payload

# 确保仓库根目录在 sys.path（允许直接 python tests/xxx.py 运行）
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# -------------------------
# 通用工具
# -------------------------


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_text(path: str, text: str) -> None:
    _ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_bytes(path: str, data: bytes) -> None:
    _ensure_dir(os.path.dirname(path) or ".")
    with open(path, "wb") as f:
        f.write(data)


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _today_start_dt() -> datetime:
    """对齐系统默认：从“明天 08:00”开始排产。"""
    tomorrow = date.today() + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, 8, 0, 0)


# -------------------------
# Excel 生成/导入
# -------------------------


def _make_xlsx_bytes(headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> io.BytesIO:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(list(headers))
    for r in rows:
        ws.append([r.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _save_xlsx(path: str, headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    buf = _make_xlsx_bytes(headers, rows)
    _write_bytes(path, buf.getvalue())


def _extract_raw_rows_json(html: str) -> str:
    m = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("未能从预览页面提取 raw_rows_json（确认导入需要该字段）")
    raw = m.group(1)
    # textarea 里可能带有 HTML 转义，这里做最小反转义
    raw = raw.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    return raw.strip()


def _extract_preview_baseline(html: str) -> str:
    m = re.search(r'<input[^>]+name="preview_baseline"[^>]+value="([^"]*)"', html, re.S)
    if not m:
        return ""
    v = m.group(1)
    v = v.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    return v.strip()


def _post_excel_import(
    *,
    client,
    preview_url: str,
    confirm_url: str,
    headers: Sequence[str],
    rows: Sequence[Dict[str, Any]],
    filename: str,
    mode: str = "overwrite",
    preview_extra: Optional[Dict[str, Any]] = None,
    confirm_extra: Optional[Dict[str, Any]] = None,
    confirm_hidden_fields: Optional[Sequence[str]] = None,
    save_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    走 UI 等价链路：
    - POST preview（上传 xlsx）
    - 从 HTML 提取 raw_rows_json
    - POST confirm（提交 raw_rows_json）
    """
    if save_path:
        _save_xlsx(save_path, headers=headers, rows=rows)
    buf = _make_xlsx_bytes(headers, rows)
    preview_data = {"mode": mode, "file": (buf, filename)}
    if preview_extra:
        preview_data.update(preview_extra)
    resp = client.post(
        preview_url,
        data=preview_data,
        content_type="multipart/form-data",
    )
    if resp.status_code != 200:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"preview 失败：{preview_url} code={resp.status_code} body={body[:500]}")
    html = resp.data.decode("utf-8", errors="ignore")
    # 严格：预览阶段出现 ERROR 行，则确认导入一定会被拒绝（各模块遵循同一交互规范）
    # 注意：base.html 中包含 `.badge-error` CSS，因此这里必须匹配“真正渲染出的 ERROR badge”。
    if '<span class="badge badge-error">ERROR</span>' in html:
        # 尝试提取少量错误提示（不保证模板结构 100% 稳定，因此做 best-effort）
        samples: List[str] = []
        try:
            msgs = re.findall(r'<span class="badge badge-error">ERROR</span>.*?<td class="error"[^>]*>(.*?)</td>', html, re.S)
            for m in msgs[:5]:
                # 去掉可能的 HTML tag
                s = re.sub(r"<[^>]+>", "", m).strip()
                if s:
                    samples.append(s)
        except Exception:
            samples = []
        sample_text = ("；".join(samples)) if samples else ""
        raise RuntimeError(f"preview 存在 ERROR 行，导入会被拒绝：{preview_url}{('；示例：' + sample_text) if sample_text else ''}")
    resp2 = client.post(
        confirm_url,
        data=build_confirm_payload(
            html,
            mode=mode,
            filename=filename,
            context=preview_url,
            confirm_extra=confirm_extra,
            confirm_hidden_fields=confirm_hidden_fields,
        ),
        follow_redirects=True,
    )
    if resp2.status_code != 200:
        body = resp2.data.decode("utf-8", errors="ignore") if getattr(resp2, "data", None) else ""
        raise RuntimeError(f"confirm 失败：{confirm_url} code={resp2.status_code} body={body[:500]}")
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" in html2:
        raise RuntimeError(f"confirm 被拒绝：{confirm_url}（页面提示“导入被拒绝”，请检查预览错误）")
    return {"preview_resp": resp, "confirm_resp": resp2}


# -------------------------
# 测试 App（避免 config.py 环境变量“仅导入时生效”的限制）
# -------------------------


def create_test_app(*, repo_root: str, db_path: str, log_dir: str, backup_dir: str, template_dir: str):
    """
    以最小副作用创建 Flask app：
    - 不依赖 config.py 的 env 读取（避免多 case 同进程时无法切 DB）
    - 不加载插件（与业务核心无关；避免污染全局状态）
    - 保留：错误处理、UI overlay、蓝图路由、每请求 DB 连接、OperationLogs
    """
    from flask import Flask, g, request

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.common.excel_templates import ensure_excel_templates
    from web.error_handlers import register_error_handlers
    from web.routes.dashboard import bp as dashboard_bp
    from web.routes.equipment import bp as equipment_bp
    from web.routes.excel_demo import bp as excel_demo_bp
    from web.routes.material import bp as material_bp
    from web.routes.personnel import bp as personnel_bp
    from web.routes.process import bp as process_bp
    from web.routes.reports import bp as reports_bp
    from web.routes.scheduler import bp as scheduler_bp
    from web.routes.system import bp as system_bp
    from web.ui_mode import init_ui_mode

    static_dir = os.path.join(repo_root, "static")
    templates_dir = os.path.join(repo_root, "templates")
    app = Flask(__name__, static_folder=static_dir, template_folder=templates_dir)
    app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "aps-e2e-key",
            "DATABASE_PATH": db_path,
            "LOG_DIR": log_dir,
            "BACKUP_DIR": backup_dir,
            "EXCEL_TEMPLATE_DIR": template_dir,
        }
    )

    # 与正式 app.create_app() 对齐：JSON 输出过滤器（确保中文可读）
    def tojson_zh(value, indent: int = 2):
        # 返回普通字符串，让 Jinja autoescape 生效（避免 XSS 反模式：Markup(json.dumps(...))）
        return json.dumps(value, ensure_ascii=False, indent=indent, default=str)

    app.jinja_env.filters["tojson_zh"] = tojson_zh

    _ensure_dir(os.path.dirname(db_path) or ".")
    _ensure_dir(log_dir)
    _ensure_dir(backup_dir)
    _ensure_dir(template_dir)

    # UI overlay（V1/V2）
    init_ui_mode(app, repo_root)

    # Excel 模板兜底（确保模板目录具备交付文件）
    ensure_excel_templates(template_dir)

    # DB schema
    ensure_schema(db_path, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=backup_dir)

    # 每请求 DB
    @app.before_request
    def _open_db():
        try:
            if request.path and str(request.path).startswith("/static"):
                return
        except Exception:
            pass
        if "db" not in g:
            g.db = get_connection(app.config["DATABASE_PATH"])
            g.op_logger = OperationLogger(g.db, logger=getattr(app, "logger", None))

    @app.teardown_appcontext
    def _close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    register_error_handlers(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(excel_demo_bp, url_prefix="/excel-demo")
    app.register_blueprint(personnel_bp, url_prefix="/personnel")
    app.register_blueprint(equipment_bp, url_prefix="/equipment")
    app.register_blueprint(process_bp, url_prefix="/process")
    app.register_blueprint(scheduler_bp, url_prefix="/scheduler")
    app.register_blueprint(material_bp, url_prefix="/material")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(system_bp, url_prefix="/system")

    return app


# -------------------------
# Case 设计（数据生成 + 运行参数）
# -------------------------


@dataclass
class CaseSpec:
    case_id: str
    title: str
    desc: str


def _base_op_types() -> List[Dict[str, Any]]:
    """
    工种名必须与工艺路线字符串中的中文名一致（RouteParser 以 name 匹配）。
    """
    return [
        {"工种ID": "OT_TURN", "工种名称": "车削", "归属": "internal"},
        {"工种ID": "OT_MILL", "工种名称": "铣削", "归属": "internal"},
        {"工种ID": "OT_GRIND", "工种名称": "磨削", "归属": "internal"},
        {"工种ID": "OT_DRILL", "工种名称": "钻孔", "归属": "internal"},
        {"工种ID": "OT_ASM", "工种名称": "装配", "归属": "internal"},
        {"工种ID": "OT_QA", "工种名称": "检验", "归属": "internal"},
        {"工种ID": "OT_EXT_PRINT", "工种名称": "标印", "归属": "external"},
        {"工种ID": "OT_EXT_PLATE", "工种名称": "表处理", "归属": "external"},
    ]


def _default_headers() -> Dict[str, List[str]]:
    return {
        "op_types": ["工种ID", "工种名称", "归属"],
        "suppliers": ["供应商ID", "名称", "对应工种", "默认周期", "状态"],
        "machines": ["设备编号", "设备名称", "工种", "状态"],
        "operators": ["工号", "姓名", "状态", "备注"],
        "links": ["工号", "设备编号", "技能等级", "主操设备"],
        "routes": ["图号", "名称", "工艺路线字符串"],
        "calendar": ["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
        "batches": ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
    }


def _build_case_specs() -> List[CaseSpec]:
    return [
        CaseSpec(
            case_id="Case01",
            title="资源耦合+停机+日历约束",
            desc="高耦合人机+多段停机+日历效率/禁排，验证避让与跨日推进。",
        ),
        CaseSpec(
            case_id="Case02",
            title="外协组 merged + separate 混用",
            desc="连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。",
        ),
        CaseSpec(
            case_id="Case03",
            title="auto-assign+技能/主操+SGS 派工（greedy vs improve）",
            desc="内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。",
        ),
        CaseSpec(
            case_id="Case04",
            title="冻结窗口插单回归",
            desc="先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。",
        ),
        CaseSpec(
            case_id="Case05",
            title="资源极稀疏+密集停机+禁排日多",
            desc="极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。",
        ),
        CaseSpec(
            case_id="Case06",
            title="超紧交期+高负荷+多外协merged",
            desc="due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。",
        ),
    ]


# -------------------------
# 数据生成：每个 case 一个函数（只返回 Excel 行；模板/组/停机等后处理在 runner 内完成）
# -------------------------


def _gen_machines(rnd: random.Random, *, op_type_names: List[str], per_type: int, inactive_ratio: float = 0.0) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ot in op_type_names:
        for i in range(1, int(per_type) + 1):
            mid = f"MC_{ot}_{i:02d}"
            status = "active"
            if inactive_ratio > 0 and rnd.random() < inactive_ratio:
                status = rnd.choice(["inactive", "maintain"])
            rows.append({"设备编号": mid, "设备名称": f"{ot}设备{i}", "工种": ot, "状态": status})
    return rows


def _gen_operators(rnd: random.Random, *, count: int, inactive_ratio: float = 0.0) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i in range(1, int(count) + 1):
        oid = f"OP{i:03d}"
        status = "active"
        if inactive_ratio > 0 and rnd.random() < inactive_ratio:
            status = "inactive"
        rows.append({"工号": oid, "姓名": f"操作员{i:03d}", "状态": status, "备注": None})
    return rows


def _gen_operator_machine_links(
    rnd: random.Random,
    *,
    operator_ids: List[str],
    machine_ids: List[str],
    per_machine_ops: int,
    primary_ratio: float,
) -> List[Dict[str, Any]]:
    """
    注意：人员设备关联的 Excel 导入是“严格模式”，且约束：
    - 同一人员最多 1 条主操设备（is_primary=yes）。
    因此这里必须确保每个 operator_id 只会被标记 0~1 次主操。
    """
    rows: List[Dict[str, Any]] = []
    used_pairs = set()

    # 先生成覆盖：每台机器至少 N 人（全部先置主操=no）
    for mid in machine_ids:
        cand = rnd.sample(operator_ids, k=min(int(per_machine_ops), len(operator_ids)))
        for oid in cand:
            key = (oid, mid)
            if key in used_pairs:
                continue
            used_pairs.add(key)
            rows.append(
                {
                    "工号": oid,
                    "设备编号": mid,
                    "技能等级": rnd.choices(["beginner", "normal", "expert"], weights=[1, 4, 2], k=1)[0],
                    "主操设备": "no",
                }
            )

    # 再加一些交叉覆盖（增强耦合；仍保持主操=no）
    extra = int(len(machine_ids) * 0.6)
    for _ in range(extra):
        oid = rnd.choice(operator_ids)
        mid = rnd.choice(machine_ids)
        key = (oid, mid)
        if key in used_pairs:
            continue
        used_pairs.add(key)
        rows.append({"工号": oid, "设备编号": mid, "技能等级": "normal", "主操设备": "no"})

    # 最后统一分配主操：每个 operator 最多 1 条 yes
    by_op: Dict[str, List[int]] = {}
    for idx, r in enumerate(rows):
        oid = str(r.get("工号") or "").strip()
        if not oid:
            continue
        by_op.setdefault(oid, []).append(idx)
    for oid, idxs in by_op.items():
        if not idxs:
            continue
        if rnd.random() < float(primary_ratio):
            pick_idx = rnd.choice(idxs)
            rows[pick_idx]["主操设备"] = "yes"

    return rows


def _ensure_at_least_one_active_operator(operators_rows: List[Dict[str, Any]]) -> None:
    """
    可排产性兜底：保证至少存在 1 个 active 人员（避免资源池为空）。
    """
    if any(str(r.get("状态") or "").strip() == "active" for r in operators_rows):
        return
    if operators_rows:
        operators_rows[0]["状态"] = "active"


def _ensure_active_machine_per_op_type(machines_rows: List[Dict[str, Any]], op_type_names: List[str]) -> None:
    """
    可排产性兜底：保证每个 internal 工种至少 1 台 active 设备（避免 auto-assign 无候选）。
    """
    for ot in op_type_names:
        same = [m for m in machines_rows if str(m.get("工种") or "").strip() == str(ot).strip()]
        if not same:
            continue
        if any(str(m.get("状态") or "").strip() == "active" for m in same):
            continue
        # 若该工种全部被随机成 inactive/maintain：强制把第一台拉活
        same[0]["状态"] = "active"


def _ensure_links_cover_active_machines(
    *,
    links_rows: List[Dict[str, Any]],
    operator_ids_active: List[str],
    machine_ids_active: List[str],
    rnd: random.Random,
) -> None:
    """
    可排产性兜底：每台 active 设备至少 1 个 active 人员资质关联。
    - 只补齐缺口，不增加已有机器的关联密度
    - 补齐行的主操设备固定为 no（避免违反“每人最多 1 主操”）
    """
    if not operator_ids_active or not machine_ids_active:
        return

    linked_machines = {str(r.get("设备编号") or "").strip() for r in links_rows if str(r.get("设备编号") or "").strip()}
    used_pairs = {(str(r.get("工号") or "").strip(), str(r.get("设备编号") or "").strip()) for r in links_rows}

    for mid in machine_ids_active:
        mid2 = str(mid).strip()
        if not mid2:
            continue
        if mid2 in linked_machines:
            continue
        oid = rnd.choice(operator_ids_active)
        pair = (oid, mid2)
        if pair in used_pairs:
            continue
        links_rows.append({"工号": oid, "设备编号": mid2, "技能等级": "normal", "主操设备": "no"})
        used_pairs.add(pair)
        linked_machines.add(mid2)


def _gen_suppliers(rnd: random.Random, *, ext_op_type_names: List[str], per_type: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    sid = 1
    for ot in ext_op_type_names:
        for _ in range(int(per_type)):
            rows.append(
                {
                    "供应商ID": f"S{sid:03d}",
                    "名称": f"{ot}供应商{sid:03d}",
                    "对应工种": ot,
                    "默认周期": float(round(rnd.uniform(1.0, 4.0), 2)),
                    "状态": "active",
                }
            )
            sid += 1
    return rows


def _route_str(ops: List[Tuple[int, str]], *, sep: str = "→") -> str:
    # 用分隔符测试预处理能力：RouteParser 会移除 →/-/> 等
    return sep.join([f"{seq}{name}" for seq, name in ops])


def _gen_routes_case01(rnd: random.Random) -> List[Dict[str, Any]]:
    parts = []
    for i in range(1, 7):
        pn = f"P_C1_{i:02d}"
        # 10 道：内部为主，夹 1 道外协（单工序组）
        ops: List[Tuple[int, str]] = [
            (5, "车削"),
            (10, "铣削"),
            (15, "钻孔"),
            (20, "磨削"),
            (25, rnd.choice(["标印", "表处理"])),
            (30, "检验"),
            (35, "装配"),
            (40, "铣削"),
            (45, "检验"),
            (50, "装配"),
        ]
        parts.append({"图号": pn, "名称": f"零件C1-{i:02d}", "工艺路线字符串": _route_str(ops, sep=" -> ")})
    return parts


def _gen_routes_case02(rnd: random.Random) -> List[Dict[str, Any]]:
    parts = []
    for i in range(1, 6):
        pn = f"P_C2_{i:02d}"
        # 连续外协段：标印+表处理（形成长度 2 外协组）
        ops: List[Tuple[int, str]] = [
            (5, "车削"),
            (10, "铣削"),
            (20, "标印"),
            (25, "表处理"),
            (30, "检验"),
            (35, "装配"),
            (40, "磨削"),
            (45, "检验"),
        ]
        parts.append({"图号": pn, "名称": f"零件C2-{i:02d}", "工艺路线字符串": _route_str(ops, sep="，")})
    # 再加一个“多段外协”零件：中间外协 3 连（更像真实外协链）
    pn = "P_C2_99"
    ops2: List[Tuple[int, str]] = [
        (5, "车削"),
        (10, "标印"),
        (12, "表处理"),
        (15, "标印"),
        (20, "铣削"),
        (25, "检验"),
    ]
    parts.append({"图号": pn, "名称": "零件C2-99", "工艺路线字符串": _route_str(ops2, sep="→")})
    return parts


def _gen_routes_case03(rnd: random.Random) -> List[Dict[str, Any]]:
    parts = []
    for i in range(1, 9):
        pn = f"P_C3_{i:02d}"
        ops: List[Tuple[int, str]] = [
            (5, rnd.choice(["车削", "铣削"])),
            (10, rnd.choice(["铣削", "钻孔"])),
            (15, rnd.choice(["磨削", "检验"])),
            (20, rnd.choice(["标印", "表处理"])),
            (25, rnd.choice(["装配", "检验"])),
            (30, rnd.choice(["铣削", "磨削"])),
        ]
        parts.append({"图号": pn, "名称": f"零件C3-{i:02d}", "工艺路线字符串": _route_str(ops, sep=" - ")})
    return parts


def _gen_routes_case04() -> List[Dict[str, Any]]:
    # 冻结窗口：需要排程跨度覆盖多天，且第二次插单能影响后续
    pn = "P_C4_01"
    ops: List[Tuple[int, str]] = [
        (5, "车削"),
        (10, "铣削"),
        (15, "钻孔"),
        (20, "检验"),
        (25, "装配"),
        (30, "磨削"),
        (35, "检验"),
    ]
    return [{"图号": pn, "名称": "零件C4-01", "工艺路线字符串": _route_str(ops, sep="→")}]


def _gen_routes_case05(rnd: random.Random) -> List[Dict[str, Any]]:
    """
    极端：资源极稀疏 + 停机密集 + 禁排日多
    - 以较长内部链为主，夹 1 道外协（单外协，不强依赖 merged）
    - 内部工种覆盖 6 类，便于“每种工种 1 台设备”时形成强约束
    """
    parts: List[Dict[str, Any]] = []
    for i in range(1, 5):
        pn = f"P_C5_{i:02d}"
        ext = rnd.choice(["标印", "表处理"])
        ops: List[Tuple[int, str]] = [
            (5, "车削"),
            (10, "铣削"),
            (15, "钻孔"),
            (20, "车削"),
            (25, "磨削"),
            (30, ext),
            (35, "检验"),
            (40, "装配"),
            (45, "铣削"),
            (50, "检验"),
            (55, "装配"),
            (60, "检验"),
        ]
        parts.append({"图号": pn, "名称": f"零件C5-{i:02d}", "工艺路线字符串": _route_str(ops, sep=" -> ")})
    return parts


def _gen_routes_case06(rnd: random.Random) -> List[Dict[str, Any]]:
    """
    极端：超紧交期 + 高负荷 + 多外协 merged
    - 每个零件含 2 段连续外协（形成 2 个 external group），后续会对多数组设为 merged(total_days)
    - 内部工序数量也偏多，用于制造高负荷
    """
    parts: List[Dict[str, Any]] = []
    for i in range(1, 6):
        pn = f"P_C6_{i:02d}"
        # 两段外协连续组：10-12、30-34
        ops: List[Tuple[int, str]] = [
            (5, "车削"),
            (10, "标印"),
            (12, "表处理"),
            (20, "铣削"),
            (30, "标印"),
            (32, "表处理"),
            (34, "标印"),
            (40, "钻孔"),
            (45, "磨削"),
            (50, "检验"),
            (55, "装配"),
            (60, "检验"),
        ]
        # 分隔符多样化，覆盖 RouteParser 的“清洗/分割”逻辑
        sep = rnd.choice(["→", " - ", "，"])
        parts.append({"图号": pn, "名称": f"零件C6-{i:02d}", "工艺路线字符串": _route_str(ops, sep=sep)})
    return parts


def _gen_calendar(
    rnd: random.Random,
    *,
    start_date: date,
    days: int,
    holiday_ratio: float = 0.08,
    normal_forbidden_ratio: float = 0.10,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i in range(int(days)):
        d = start_date + timedelta(days=i)
        # 周末默认不可排产
        if d.weekday() >= 5:
            rows.append(
                {
                    "日期": d.isoformat(),
                    "类型": "weekend",
                    "可用工时": 0,
                    "效率": 1.0,
                    "允许普通件": "no",
                    "允许急件": "no",
                    "说明": "周末",
                }
            )
            continue

        # 随机节假日（全部禁排）
        if rnd.random() < holiday_ratio:
            rows.append(
                {
                    "日期": d.isoformat(),
                    "类型": "holiday",
                    "可用工时": 0,
                    "效率": 1.0,
                    "允许普通件": "no",
                    "允许急件": "no",
                    "说明": "节假日（合成）",
                }
            )
            continue

        # 工作日：效率波动
        eff = float(round(rnd.uniform(0.75, 1.0), 3))
        # 部分工作日仅允许急件（模拟“仅加急窗口”）
        allow_normal = "no" if rnd.random() < normal_forbidden_ratio else "yes"
        rows.append(
            {
                "日期": d.isoformat(),
                "类型": "workday",
                "可用工时": 8,
                "效率": eff,
                "允许普通件": allow_normal,
                "允许急件": "yes",
                "说明": "工作日",
            }
        )
    return rows


def _gen_batches(
    rnd: random.Random,
    *,
    part_nos: List[str],
    start_dt: datetime,
    batch_prefix: str,
    per_part: Tuple[int, int],
    qty_range: Tuple[int, int],
    due_days_range: Tuple[int, int],
    include_ready_date: bool = True,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    idx = 1
    for pn in part_nos:
        cnt = rnd.randint(int(per_part[0]), int(per_part[1]))
        for _ in range(cnt):
            bid = f"{batch_prefix}{idx:04d}"
            idx += 1
            qty = rnd.randint(int(qty_range[0]), int(qty_range[1]))
            pr = rnd.random()
            if pr < 0.12:
                priority = "critical"
            elif pr < 0.35:
                priority = "urgent"
            else:
                priority = "normal"

            due = (start_dt.date() + timedelta(days=rnd.randint(int(due_days_range[0]), int(due_days_range[1])))).isoformat()
            ready_date = (start_dt.date() - timedelta(days=rnd.randint(0, 2))).isoformat()
            row = {
                "批次号": bid,
                "图号": pn,
                "数量": qty,
                "交期": due,
                "优先级": priority,
                "齐套": "yes",
                "齐套日期": ready_date if include_ready_date else None,
                "备注": None,
            }
            rows.append(row)
    return rows


# -------------------------
# Runner：导入→模板后处理→排产→sanity→落地证据
# -------------------------


def _set_config(conn, *, auto_assign: str, dispatch_mode: str, dispatch_rule: str, algo_mode: str, objective: str, time_budget: int) -> None:
    from core.services.scheduler.config_service import ConfigService

    cfg = ConfigService(conn)
    cfg.ensure_defaults()
    cfg.set_strategy("weighted")
    cfg.set_weights(0.4, 0.5, 0.1, require_sum_1=True)
    cfg.set_auto_assign_enabled(auto_assign)
    cfg.set_dispatch(dispatch_mode, dispatch_rule)
    cfg.set_algo_mode(algo_mode)
    cfg.set_objective(objective)
    cfg.set_time_budget_seconds(int(time_budget))
    cfg.set_freeze_window("no", 0)


def _enable_freeze_window(conn, *, days: int) -> None:
    from core.services.scheduler.config_service import ConfigService

    cfg = ConfigService(conn)
    cfg.ensure_defaults()
    cfg.set_freeze_window("yes", int(days))


def _update_template_hours(conn, *, part_no: str, internal_hours: Dict[int, Tuple[float, float]]) -> None:
    """
    internal_hours: seq -> (setup_hours, unit_hours)
    """
    from core.services.process.part_service import PartService

    svc = PartService(conn)
    for seq, (sh, uh) in internal_hours.items():
        svc.update_internal_hours(part_no=part_no, seq=int(seq), setup_hours=float(sh), unit_hours=float(uh))


def _set_some_groups_merged(conn, *, part_no: str, total_days_by_group: Dict[str, float]) -> None:
    from core.services.process.external_group_service import ExternalGroupService

    svc = ExternalGroupService(conn)
    for gid, td in total_days_by_group.items():
        svc.set_merge_mode(group_id=gid, merge_mode="merged", total_days=float(td))


def _create_downtimes(conn, *, machine_ids: List[str], start_dt: datetime, rnd: random.Random, ratio: float) -> None:
    from core.services.equipment.machine_downtime_service import MachineDowntimeService

    svc = MachineDowntimeService(conn)
    mids = list(machine_ids)
    if not mids:
        return
    pick = rnd.sample(mids, k=max(1, int(len(mids) * float(ratio))))
    for mid in pick:
        used_slots: set = set()
        seg_cnt = rnd.randint(1, 2)
        if float(ratio) >= 0.8:
            seg_cnt = rnd.randint(3, 6)
        elif float(ratio) >= 0.4:
            seg_cnt = rnd.randint(2, 4)
        for _ in range(seg_cnt):
            # 避免重叠：尽量让每个段落落在不同 (day, hour) 槽
            for _try in range(20):
                day = rnd.randint(0, 10)
                hour = rnd.choice([9, 10, 13, 15, 16])
                key = (day, hour)
                if key in used_slots:
                    continue
                used_slots.add(key)
                st = start_dt + timedelta(days=day, hours=hour)
                et = st + timedelta(hours=rnd.choice([2, 3, 4]))
                try:
                    svc.create(
                        machine_id=mid,
                        start_time=_fmt_dt(st),
                        end_time=_fmt_dt(et),
                        reason_code="maintenance",
                        reason_detail="E2E合成停机",
                    )
                except Exception:
                    # 重叠/校验失败：换一个槽重试
                    continue
                break


def _load_schedule_rows(conn, *, version: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          s.version,
          s.op_id,
          bo.op_code,
          bo.batch_id,
          bo.seq,
          bo.source,
          s.machine_id,
          s.operator_id,
          s.start_time,
          s.end_time,
          b.part_no,
          b.priority,
          b.due_date,
          po.ext_group_id,
          eg.merge_mode AS group_merge_mode,
          eg.total_days AS group_total_days
        FROM Schedule s
        JOIN BatchOperations bo ON bo.id = s.op_id
        JOIN Batches b ON b.batch_id = bo.batch_id
        LEFT JOIN PartOperations po ON po.part_no = b.part_no AND po.seq = bo.seq
        LEFT JOIN ExternalGroups eg ON eg.group_id = po.ext_group_id
        WHERE s.version = ?
        ORDER BY s.start_time, s.op_id
        """,
        (int(version),),
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        out.append(d)
    return out


def _sanity_check(
    conn,
    *,
    version: int,
    start_dt: datetime,
    selected_batch_ids: List[str],
) -> List[str]:
    """
    返回问题列表（空=通过）。
    """
    issues: List[str] = []

    # 1) 行数：应覆盖全部工序
    placeholders = ",".join(["?"] * len(selected_batch_ids))
    sql = f"SELECT COUNT(1) AS c FROM BatchOperations WHERE batch_id IN ({placeholders})"
    total_ops = conn.execute(sql, tuple(selected_batch_ids)).fetchone()["c"]
    sch_cnt = conn.execute("SELECT COUNT(1) AS c FROM Schedule WHERE version=?", (int(version),)).fetchone()["c"]
    if int(sch_cnt) != int(total_ops):
        issues.append(f"Schedule 行数不匹配：scheduled={sch_cnt} expected_ops={total_ops}")

    rows = _load_schedule_rows(conn, version=int(version))
    if not rows:
        issues.append("Schedule 为空（无任何排程结果）")
        return issues

    # 2) 时间合法
    min_start = None
    max_end = None
    for r in rows:
        st = _parse_dt(r.get("start_time"))
        et = _parse_dt(r.get("end_time"))
        if not st or not et:
            issues.append(f"任务时间为空：op_id={r.get('op_id')} op_code={r.get('op_code')}")
            continue
        if et <= st:
            issues.append(f"任务时间不合法（end<=start）：op_code={r.get('op_code')} start={st} end={et}")
        if st < start_dt - timedelta(seconds=1):
            issues.append(f"任务早于 start_dt：op_code={r.get('op_code')} start={st} start_dt={start_dt}")
        if min_start is None or st < min_start:
            min_start = st
        if max_end is None or et > max_end:
            max_end = et

    if min_start and max_end:
        if max_end > start_dt + timedelta(days=365):
            issues.append(f"排程跨度异常：max_end={max_end}（超过 start_dt+365d）")

    # 3) internal 资源字段必须存在
    for r in rows:
        if str(r.get("source") or "").strip() != "internal":
            continue
        if not str(r.get("machine_id") or "").strip() or not str(r.get("operator_id") or "").strip():
            issues.append(f"内部工序缺少资源：op_code={r.get('op_code')} machine_id={r.get('machine_id')} operator_id={r.get('operator_id')}")

    # 4) 资源冲突（设备/人员）
    def _check_conflicts(key: str) -> None:
        groups: Dict[str, List[Tuple[datetime, datetime, str]]] = {}
        for r in rows:
            rid = str(r.get(key) or "").strip()
            if not rid:
                continue
            st = _parse_dt(r.get("start_time"))
            et = _parse_dt(r.get("end_time"))
            if not st or not et:
                continue
            groups.setdefault(rid, []).append((st, et, str(r.get("op_code") or r.get("op_id"))))
        for rid, items in groups.items():
            items.sort(key=lambda x: (x[0], x[1]))
            prev = None
            for st, et, code in items:
                if prev is None:
                    prev = (st, et, code)
                    continue
                pst, pet, pcode = prev
                if st < pet - timedelta(seconds=0):  # 允许端点相接
                    issues.append(f"{key} 资源冲突：{rid} {pcode}({pst}~{pet}) 与 {code}({st}~{et}) 重叠")
                    break
                prev = (st, et, code)

    _check_conflicts("machine_id")
    _check_conflicts("operator_id")

    # 5) 停机避让
    dt_rows = conn.execute(
        "SELECT machine_id, start_time, end_time FROM MachineDowntimes WHERE status='active'"
    ).fetchall()
    dt_map: Dict[str, List[Tuple[datetime, datetime]]] = {}
    for d in dt_rows:
        mid = str(d["machine_id"] or "").strip()
        st = _parse_dt(d["start_time"])
        et = _parse_dt(d["end_time"])
        if not mid or not st or not et or et <= st:
            continue
        dt_map.setdefault(mid, []).append((st, et))
    for mid in dt_map:
        dt_map[mid].sort(key=lambda x: x[0])

    for r in rows:
        if str(r.get("source") or "").strip() != "internal":
            continue
        mid = str(r.get("machine_id") or "").strip()
        if not mid:
            continue
        st = _parse_dt(r.get("start_time"))
        et = _parse_dt(r.get("end_time"))
        if not st or not et:
            continue
        for dst, det in dt_map.get(mid, []):
            if et <= dst or st >= det:
                continue
            issues.append(f"停机避让失败：machine={mid} op_code={r.get('op_code')} task=({st}~{et}) downtime=({dst}~{det})")
            break

    # 6) merged 外协组一致性（同 batch_id + ext_group_id 应同起止）
    merged_groups: Dict[Tuple[str, str], List[Tuple[str, datetime, datetime]]] = {}
    for r in rows:
        if str(r.get("source") or "").strip() != "external":
            continue
        if str(r.get("group_merge_mode") or "").strip() != "merged":
            continue
        gid = str(r.get("ext_group_id") or "").strip()
        bid = str(r.get("batch_id") or "").strip()
        if not gid or not bid:
            continue
        st = _parse_dt(r.get("start_time"))
        et = _parse_dt(r.get("end_time"))
        if not st or not et:
            continue
        merged_groups.setdefault((bid, gid), []).append((str(r.get("op_code") or ""), st, et))
    for (bid, gid), items in merged_groups.items():
        if not items:
            continue
        ref_st, ref_et = items[0][1], items[0][2]
        for code, st, et in items[1:]:
            if st != ref_st or et != ref_et:
                issues.append(f"merged 外协组不一致：batch={bid} group={gid} ref=({ref_st}~{ref_et}) but {code}=({st}~{et})")
                break

    return issues


def _latest_version(conn) -> Optional[int]:
    row = conn.execute("SELECT version FROM ScheduleHistory ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    try:
        return int(row["version"])
    except Exception:
        return None


def _read_history_summary(conn, *, version: int) -> Dict[str, Any]:
    row = conn.execute("SELECT result_status, result_summary FROM ScheduleHistory WHERE version=?", (int(version),)).fetchone()
    if not row:
        return {}
    out = {"result_status": row["result_status"], "result_summary": None}
    try:
        out["result_summary"] = json.loads(row["result_summary"] or "{}")
    except Exception:
        out["result_summary"] = None
    return out


def _parse_detail_json(detail: Any) -> Dict[str, Any]:
    if detail is None:
        return {}
    try:
        return json.loads(detail) if detail else {}
    except Exception:
        return {}


def _oplog_latest(conn, *, module: str, action: str, target_type: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT id, detail
        FROM OperationLogs
        WHERE module=? AND action=? AND target_type=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (str(module), str(action), str(target_type)),
    ).fetchone()
    if not row:
        return None
    return {"id": int(row["id"]), "detail": _parse_detail_json(row["detail"])}


def _check_oplog_keys(conn, *, module: str, action: str, target_type: str, required_keys: List[str]) -> Optional[str]:
    row = _oplog_latest(conn, module=module, action=action, target_type=target_type)
    if not row:
        return f"缺少 OperationLogs：{module}/{action}/{target_type}"
    d = row.get("detail") or {}
    missing = [k for k in required_keys if k not in d]
    if missing:
        return f"OperationLogs.detail 缺少键：{module}/{action}/{target_type} missing={missing} log_id={row.get('id')}"
    return None


def run_one_case(*, case: CaseSpec, out_base: str, repeat_idx: int, base_seed: int) -> Dict[str, Any]:
    """
    返回结构化结果（供聚合写 MD）。
    """
    repo_root = find_repo_root()
    headers = _default_headers()
    start_dt = _today_start_dt()

    # case 独立临时环境
    tmpdir = tempfile.mkdtemp(prefix=f"aps_complex_{case.case_id.lower()}_{repeat_idx}_")
    test_db = os.path.join(tmpdir, "aps.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")

    app = create_test_app(repo_root=repo_root, db_path=test_db, log_dir=test_logs, backup_dir=test_backups, template_dir=test_templates)
    client = app.test_client()

    # evidence 输出
    case_dir = os.path.join(out_base, case.case_id, f"run_{repeat_idx:02d}")
    input_dir = os.path.join(case_dir, "input")
    output_dir = os.path.join(case_dir, "output")
    _ensure_dir(input_dir)
    _ensure_dir(output_dir)

    # 可复现随机种子：同一 (base_seed, case_id, repeat_idx) 应产生完全一致的数据与流程
    case_hash = sum([ord(c) for c in str(case.case_id)]) % 100000
    seed = int(base_seed) + int(case_hash) * 1000 + int(repeat_idx)
    rnd = random.Random(seed)

    # -------------------------
    # 1) 生成 Excel 行
    # -------------------------
    op_types_rows = _base_op_types()
    internal_names = [r["工种名称"] for r in op_types_rows if r["归属"] == "internal"]
    external_names = [r["工种名称"] for r in op_types_rows if r["归属"] == "external"]

    supplier_per_type = 3 if case.case_id == "Case06" else 2
    suppliers_rows = _gen_suppliers(rnd, ext_op_type_names=external_names, per_type=supplier_per_type)

    # 资源规模/稀疏度：按 case 调整
    if case.case_id == "Case04":
        machine_per_type = 2
        machine_inactive_ratio = 0.12
        operator_count = 18
        operator_inactive_ratio = 0.0
        per_machine_ops = 4
        primary_ratio = 0.05
    elif case.case_id == "Case05":
        # 极稀疏：每个工种 1 台设备；每台设备仅 1 个资质人员（强耦合）
        machine_per_type = 1
        machine_inactive_ratio = 0.05
        operator_count = 10
        operator_inactive_ratio = 0.0
        per_machine_ops = 1
        primary_ratio = 0.25
    elif case.case_id == "Case01":
        machine_per_type = 3
        machine_inactive_ratio = 0.12
        operator_count = 24
        operator_inactive_ratio = 0.0
        per_machine_ops = 2
        primary_ratio = 0.05
    elif case.case_id == "Case03":
        machine_per_type = 3
        machine_inactive_ratio = 0.12
        operator_count = 24
        operator_inactive_ratio = 0.10
        per_machine_ops = 4
        primary_ratio = 0.10
    elif case.case_id == "Case06":
        machine_per_type = 3
        machine_inactive_ratio = 0.12
        operator_count = 24
        operator_inactive_ratio = 0.05
        per_machine_ops = 4
        primary_ratio = 0.08
    else:
        # Case02
        machine_per_type = 3
        machine_inactive_ratio = 0.12
        operator_count = 18
        operator_inactive_ratio = 0.0
        per_machine_ops = 4
        primary_ratio = 0.05

    machines_rows = _gen_machines(rnd, op_type_names=internal_names, per_type=machine_per_type, inactive_ratio=machine_inactive_ratio)
    operators_rows = _gen_operators(rnd, count=operator_count, inactive_ratio=operator_inactive_ratio)

    # 可排产性兜底：避免随机生成导致资源池为空/工种无可用设备
    _ensure_active_machine_per_op_type(machines_rows, internal_names)
    _ensure_at_least_one_active_operator(operators_rows)

    operator_ids = [str(r["工号"]) for r in operators_rows if str(r.get("状态") or "") == "active"]
    machine_ids_active = [str(r["设备编号"]) for r in machines_rows if str(r.get("状态") or "") == "active"]

    links_rows = _gen_operator_machine_links(
        rnd,
        operator_ids=operator_ids,
        machine_ids=machine_ids_active,
        per_machine_ops=per_machine_ops,
        primary_ratio=primary_ratio,
    )
    _ensure_links_cover_active_machines(
        links_rows=links_rows,
        operator_ids_active=operator_ids,
        machine_ids_active=machine_ids_active,
        rnd=rnd,
    )

    if case.case_id == "Case01":
        routes_rows = _gen_routes_case01(rnd)
        calendar_rows = _gen_calendar(rnd, start_date=(start_dt.date() - timedelta(days=3)), days=45, holiday_ratio=0.10, normal_forbidden_ratio=0.18)
        batches_rows = _gen_batches(
            rnd,
            part_nos=[r["图号"] for r in routes_rows],
            start_dt=start_dt,
            batch_prefix="B1_",
            per_part=(3, 6),
            qty_range=(20, 120),
            due_days_range=(8, 25),
        )
    elif case.case_id == "Case02":
        routes_rows = _gen_routes_case02(rnd)
        calendar_rows = _gen_calendar(rnd, start_date=(start_dt.date() - timedelta(days=3)), days=60, holiday_ratio=0.06, normal_forbidden_ratio=0.10)
        batches_rows = _gen_batches(
            rnd,
            part_nos=[r["图号"] for r in routes_rows],
            start_dt=start_dt,
            batch_prefix="B2_",
            per_part=(4, 7),
            qty_range=(10, 80),
            due_days_range=(10, 28),
        )
    elif case.case_id == "Case03":
        routes_rows = _gen_routes_case03(rnd)
        calendar_rows = _gen_calendar(rnd, start_date=(start_dt.date() - timedelta(days=3)), days=60, holiday_ratio=0.06, normal_forbidden_ratio=0.08)
        batches_rows = _gen_batches(
            rnd,
            part_nos=[r["图号"] for r in routes_rows],
            start_dt=start_dt,
            batch_prefix="B3_",
            per_part=(5, 9),
            qty_range=(30, 180),
            due_days_range=(10, 35),
        )
    elif case.case_id == "Case04":
        routes_rows = _gen_routes_case04()
        calendar_rows = _gen_calendar(rnd, start_date=(start_dt.date() - timedelta(days=3)), days=80, holiday_ratio=0.05, normal_forbidden_ratio=0.10)
        batches_rows = _gen_batches(
            rnd,
            part_nos=[r["图号"] for r in routes_rows],
            start_dt=start_dt,
            batch_prefix="B4_",
            per_part=(10, 12),
            qty_range=(40, 160),
            due_days_range=(12, 40),
        )
    elif case.case_id == "Case05":
        routes_rows = _gen_routes_case05(rnd)
        calendar_rows = _gen_calendar(
            rnd,
            start_date=(start_dt.date() - timedelta(days=3)),
            days=90,
            holiday_ratio=0.18,
            normal_forbidden_ratio=0.60,
        )
        batches_rows = _gen_batches(
            rnd,
            part_nos=[r["图号"] for r in routes_rows],
            start_dt=start_dt,
            batch_prefix="B5_",
            per_part=(8, 12),
            qty_range=(80, 260),
            due_days_range=(6, 18),
        )
    else:
        # Case06
        routes_rows = _gen_routes_case06(rnd)
        calendar_rows = _gen_calendar(
            rnd,
            start_date=(start_dt.date() - timedelta(days=3)),
            days=90,
            holiday_ratio=0.06,
            normal_forbidden_ratio=0.20,
        )
        batches_rows = _gen_batches(
            rnd,
            part_nos=[r["图号"] for r in routes_rows],
            start_dt=start_dt,
            batch_prefix="B6_",
            per_part=(10, 15),
            qty_range=(80, 240),
            due_days_range=(1, 5),
        )

    # -------------------------
    # 2) Excel 导入（走 UI 链路）
    # -------------------------
    _post_excel_import(
        client=client,
        preview_url="/process/excel/op-types/preview",
        confirm_url="/process/excel/op-types/confirm",
        headers=headers["op_types"],
        rows=op_types_rows,
        filename="工种配置.xlsx",
        save_path=os.path.join(input_dir, "工种配置.xlsx"),
    )
    _post_excel_import(
        client=client,
        preview_url="/process/excel/suppliers/preview",
        confirm_url="/process/excel/suppliers/confirm",
        headers=headers["suppliers"],
        rows=suppliers_rows,
        filename="供应商配置.xlsx",
        save_path=os.path.join(input_dir, "供应商配置.xlsx"),
    )
    _post_excel_import(
        client=client,
        preview_url="/equipment/excel/machines/preview",
        confirm_url="/equipment/excel/machines/confirm",
        headers=headers["machines"],
        rows=machines_rows,
        filename="设备信息.xlsx",
        save_path=os.path.join(input_dir, "设备信息.xlsx"),
    )
    _post_excel_import(
        client=client,
        preview_url="/personnel/excel/operators/preview",
        confirm_url="/personnel/excel/operators/confirm",
        headers=headers["operators"],
        rows=operators_rows,
        filename="人员基本信息.xlsx",
        save_path=os.path.join(input_dir, "人员基本信息.xlsx"),
    )
    _post_excel_import(
        client=client,
        preview_url="/personnel/excel/links/preview",
        confirm_url="/personnel/excel/links/confirm",
        headers=headers["links"],
        rows=links_rows,
        filename="人员设备关联.xlsx",
        save_path=os.path.join(input_dir, "人员设备关联.xlsx"),
    )
    _post_excel_import(
        client=client,
        preview_url="/process/excel/routes/preview",
        confirm_url="/process/excel/routes/confirm",
        headers=headers["routes"],
        rows=routes_rows,
        filename="零件工艺路线.xlsx",
        save_path=os.path.join(input_dir, "零件工艺路线.xlsx"),
    )
    _post_excel_import(
        client=client,
        preview_url="/scheduler/excel/calendar/preview",
        confirm_url="/scheduler/excel/calendar/confirm",
        headers=headers["calendar"],
        rows=calendar_rows,
        filename="工作日历.xlsx",
        save_path=os.path.join(input_dir, "工作日历.xlsx"),
    )

    # -------------------------
    # 3) 模板后处理（工时、外协 merged、停机）
    # -------------------------
    from core.infrastructure.database import get_connection

    conn = get_connection(test_db)
    try:
        # 3.1 工时：给所有 internal 工序设置非零（避免 0 时长任务）
        for r in routes_rows:
            pn = str(r["图号"]).strip()
            # 读取模板工序（找 internal seq）
            ops = conn.execute(
                "SELECT seq, source, op_type_name FROM PartOperations WHERE part_no=? AND status='active' ORDER BY seq",
                (pn,),
            ).fetchall()
            internal_hours: Dict[int, Tuple[float, float]] = {}
            for op in ops:
                if str(op["source"] or "").strip() != "internal":
                    continue
                seq = int(op["seq"])
                name = str(op["op_type_name"] or "").strip()
                # 工时模型：按工种给不同强度（小时）
                if name in ("车削",):
                    sh, uh = (0.6, 0.03)
                elif name in ("铣削",):
                    sh, uh = (0.5, 0.028)
                elif name in ("磨削",):
                    sh, uh = (0.4, 0.022)
                elif name in ("钻孔",):
                    sh, uh = (0.3, 0.018)
                elif name in ("装配",):
                    sh, uh = (0.25, 0.012)
                else:  # 检验等
                    sh, uh = (0.2, 0.010)
                # 不同 case 的强度调整：让跨度/压力更贴近目标覆盖点
                scale = 1.0
                if case.case_id in ("Case01", "Case04"):
                    scale = 1.15
                elif case.case_id == "Case05":
                    scale = 1.35
                elif case.case_id == "Case06":
                    scale = 1.20
                uh = float(uh) * float(scale)
                internal_hours[int(seq)] = (float(sh), float(uh))
            _update_template_hours(conn, part_no=pn, internal_hours=internal_hours)

        # 3.2 外协 merged：Case02（混用）/ Case06（大量 merged）
        if case.case_id == "Case02":
            for r in routes_rows:
                pn = str(r["图号"]).strip()
                # 选取该零件的第一个外协组（通常就是连续外协段），设为 merged
                groups = conn.execute(
                    "SELECT group_id, start_seq, end_seq FROM ExternalGroups WHERE part_no=? ORDER BY start_seq",
                    (pn,),
                ).fetchall()
                if not groups:
                    continue
                # 让一半零件 merged，一半 separate（混用）
                if rnd.random() < 0.55:
                    gid = str(groups[0]["group_id"])
                    td = float(round(rnd.uniform(2.0, 6.0), 2))
                    _set_some_groups_merged(conn, part_no=pn, total_days_by_group={gid: td})
        elif case.case_id == "Case06":
            for r in routes_rows:
                pn = str(r["图号"]).strip()
                groups = conn.execute(
                    "SELECT group_id, start_seq, end_seq FROM ExternalGroups WHERE part_no=? ORDER BY start_seq",
                    (pn,),
                ).fetchall()
                if not groups:
                    continue
                # 尽量保证每个零件至少 1 个 merged 组，且多数外协组为 merged（高覆盖）
                picked: Dict[str, float] = {}
                for g in groups:
                    gid = str(g["group_id"])
                    if rnd.random() < 0.80:
                        picked[gid] = float(round(rnd.uniform(3.0, 12.0), 2))
                if not picked:
                    gid0 = str(groups[0]["group_id"])
                    picked[gid0] = float(round(rnd.uniform(3.0, 12.0), 2))
                _set_some_groups_merged(conn, part_no=pn, total_days_by_group=picked)

        # 3.3 停机：按 case 调整密度
        if case.case_id == "Case01":
            _create_downtimes(conn, machine_ids=machine_ids_active, start_dt=start_dt, rnd=rnd, ratio=0.18)
        elif case.case_id == "Case03":
            _create_downtimes(conn, machine_ids=machine_ids_active, start_dt=start_dt, rnd=rnd, ratio=0.12)
        elif case.case_id == "Case05":
            # 密集停机：对大多数设备施加更多停机段
            _create_downtimes(conn, machine_ids=machine_ids_active, start_dt=start_dt, rnd=rnd, ratio=0.90)
        elif case.case_id == "Case06":
            # 轻量停机：主要覆盖“高负荷 + 外协”下的避让路径
            _create_downtimes(conn, machine_ids=machine_ids_active, start_dt=start_dt, rnd=rnd, ratio=0.20)

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # -------------------------
    # 4) 批次导入（自动生成工序）
    # -------------------------
    _post_excel_import(
        client=client,
        preview_url="/scheduler/excel/batches/preview",
        confirm_url="/scheduler/excel/batches/confirm",
        headers=headers["batches"],
        rows=batches_rows,
        filename="批次信息.xlsx",
        preview_extra={"auto_generate_ops": "1"},
        confirm_hidden_fields=["auto_generate_ops"],
        save_path=os.path.join(input_dir, "批次信息.xlsx"),
    )

    # -------------------------
    # 5) 排产（多轮/对比）+ sanity checks
    # -------------------------
    conn = get_connection(test_db)
    run_summaries: List[Dict[str, Any]] = []
    issues_all: List[str] = []
    try:
        batch_ids_all = [str(r["批次号"]).strip() for r in batches_rows]

        if case.case_id == "Case03":
            # greedy vs improve（SGS）
            for algo_mode in ("greedy", "improve"):
                _set_config(
                    conn,
                    auto_assign="yes",
                    dispatch_mode="sgs",
                    dispatch_rule="slack",
                    algo_mode=algo_mode,
                    objective="min_tardiness",
                    time_budget=(15 if algo_mode == "improve" else 5),
                )
                conn.commit()
                # 走 web 路由执行排产
                resp = client.post(
                    "/scheduler/run",
                    data={"batch_ids": batch_ids_all, "start_dt": _fmt_dt(start_dt)},
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"/scheduler/run 返回 {resp.status_code}")
                ver = _latest_version(conn)
                if not ver:
                    raise RuntimeError("未写入 ScheduleHistory（无法获取 version）")
                hist = _read_history_summary(conn, version=ver)
                sanity_issues = _sanity_check(conn, version=ver, start_dt=start_dt, selected_batch_ids=batch_ids_all)
                run_summaries.append({"algo_mode": algo_mode, "version": ver, "history": hist, "sanity_issues": sanity_issues})
                issues_all.extend([f"[{algo_mode}] {x}" for x in sanity_issues])
        elif case.case_id == "Case04":
            # 冻结窗口插单：两次排产
            _set_config(
                conn,
                auto_assign="yes",
                dispatch_mode="batch_order",
                dispatch_rule="slack",
                algo_mode="greedy",
                objective="min_overdue",
                time_budget=5,
            )
            conn.commit()
            # 第一次：只排前半批次
            first_batches = batch_ids_all[: max(1, int(len(batch_ids_all) * 0.55))]
            resp = client.post("/scheduler/run", data={"batch_ids": first_batches, "start_dt": _fmt_dt(start_dt)}, follow_redirects=True)
            if resp.status_code != 200:
                raise RuntimeError(f"第一次 /scheduler/run 返回 {resp.status_code}")
            v1 = _latest_version(conn)
            if not v1:
                raise RuntimeError("第一次未写入 ScheduleHistory（无法获取 version）")
            issues_v1 = _sanity_check(conn, version=v1, start_dt=start_dt, selected_batch_ids=first_batches)
            if issues_v1:
                issues_all.extend([f"[v1] {x}" for x in issues_v1])

            # 插单：导入一批特急/超近交期（追加批次号，避免覆盖）
            insert_rows: List[Dict[str, Any]] = []
            for i in range(1, 6):
                insert_rows.append(
                    {
                        "批次号": f"INS_{i:03d}",
                        "图号": routes_rows[0]["图号"],
                        "数量": rnd.randint(60, 140),
                        "交期": (start_dt.date() + timedelta(days=rnd.randint(3, 6))).isoformat(),
                        "优先级": "critical",
                        "齐套": "yes",
                        "齐套日期": (start_dt.date() - timedelta(days=1)).isoformat(),
                        "备注": "插单",
                    }
                )
            _post_excel_import(
                client=client,
                preview_url="/scheduler/excel/batches/preview",
                confirm_url="/scheduler/excel/batches/confirm",
                headers=headers["batches"],
                rows=insert_rows,
                filename="插单批次.xlsx",
                preview_extra={"auto_generate_ops": "1"},
                confirm_hidden_fields=["auto_generate_ops"],
                save_path=os.path.join(input_dir, "插单批次.xlsx"),
            )

            # 第二次：开启冻结窗口，排“原批次+插单”
            _enable_freeze_window(conn, days=3)
            conn.commit()
            second_batches = list(first_batches) + [r["批次号"] for r in insert_rows]
            resp = client.post("/scheduler/run", data={"batch_ids": second_batches, "start_dt": _fmt_dt(start_dt)}, follow_redirects=True)
            if resp.status_code != 200:
                raise RuntimeError(f"第二次 /scheduler/run 返回 {resp.status_code}")
            v2 = _latest_version(conn)
            if not v2 or int(v2) <= int(v1):
                raise RuntimeError(f"第二次 version 异常：v1={v1} v2={v2}")
            issues_v2 = _sanity_check(conn, version=v2, start_dt=start_dt, selected_batch_ids=second_batches)
            issues_all.extend([f"[v2] {x}" for x in issues_v2])

            # 冻结一致性：窗口内被冻结 op 的时间应与 v1 一致
            from core.services.scheduler.config_service import ConfigService
            from core.services.scheduler.freeze_window import build_freeze_window_seed
            from core.services.scheduler.schedule_service import ScheduleService

            cfg = ConfigService(conn).get_snapshot()
            svc = ScheduleService(conn)
            ops = []
            for bid in second_batches:
                ops.extend(svc.op_repo.list_by_batch(bid))
            frozen_op_ids, _, _ = build_freeze_window_seed(svc, cfg=cfg, prev_version=int(v1), start_dt=start_dt, operations=ops)
            if frozen_op_ids:
                # 对比两版 Schedule
                mismatch = 0
                for oid in list(sorted(frozen_op_ids))[:2000]:
                    r1 = conn.execute("SELECT start_time, end_time FROM Schedule WHERE version=? AND op_id=?", (int(v1), int(oid))).fetchone()
                    r2 = conn.execute("SELECT start_time, end_time FROM Schedule WHERE version=? AND op_id=?", (int(v2), int(oid))).fetchone()
                    if not r1 or not r2:
                        continue
                    if str(r1["start_time"]) != str(r2["start_time"]) or str(r1["end_time"]) != str(r2["end_time"]):
                        mismatch += 1
                        if mismatch <= 5:
                            issues_all.append(f"[freeze] op_id={oid} v1=({r1['start_time']}~{r1['end_time']}) v2=({r2['start_time']}~{r2['end_time']})")
                if mismatch:
                    issues_all.append(f"[freeze] 冻结窗口内排程不一致：mismatch={mismatch}")

            run_summaries.append({"algo_mode": "greedy", "version": v1, "history": _read_history_summary(conn, version=v1), "sanity_issues": issues_v1})
            run_summaries.append({"algo_mode": "greedy+freeze", "version": v2, "history": _read_history_summary(conn, version=v2), "sanity_issues": issues_v2})
        else:
            # Case01/02：单次（可扩展多策略）
            auto_assign = "yes"
            dispatch_mode = "batch_order"
            _set_config(conn, auto_assign=auto_assign, dispatch_mode=dispatch_mode, dispatch_rule="slack", algo_mode="greedy", objective="min_overdue", time_budget=5)
            conn.commit()
            resp = client.post("/scheduler/run", data={"batch_ids": batch_ids_all, "start_dt": _fmt_dt(start_dt)}, follow_redirects=True)
            if resp.status_code != 200:
                raise RuntimeError(f"/scheduler/run 返回 {resp.status_code}")
            ver = _latest_version(conn)
            if not ver:
                raise RuntimeError("未写入 ScheduleHistory（无法获取 version）")
            hist = _read_history_summary(conn, version=ver)
            sanity_issues = _sanity_check(conn, version=ver, start_dt=start_dt, selected_batch_ids=batch_ids_all)
            run_summaries.append({"algo_mode": "greedy", "version": ver, "history": hist, "sanity_issues": sanity_issues})
            issues_all.extend(sanity_issues)

        # 走一遍甘特/周计划导出（抽检）
        latest = _latest_version(conn)
        if latest:
            # week_start 取排程起始时间，确保命中
            min_start = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (int(latest),)).fetchone()["st"]
            week_start = str(min_start)[:10] if min_start else start_dt.date().isoformat()

            gantt = client.get(f"/scheduler/gantt/data?view=machine&week_start={week_start}&version={int(latest)}")
            if gantt.status_code != 200:
                issues_all.append(f"甘特数据接口返回非200：{gantt.status_code}")
            else:
                _write_bytes(os.path.join(output_dir, f"gantt_machine_v{latest}.json"), gantt.data)

            wp = client.get(f"/scheduler/week-plan/export?week_start={week_start}&version={int(latest)}")
            if wp.status_code != 200:
                issues_all.append(f"周计划导出返回非200：{wp.status_code}")
            else:
                _write_bytes(os.path.join(output_dir, f"week_plan_v{latest}.xlsx"), wp.data)

            # 报表中心：页面可访问（抽检）
            reports_checks = [
                ("GET /reports/", "/reports/"),
                ("GET /reports/overdue", f"/reports/overdue?version={int(latest)}"),
                ("GET /reports/utilization", f"/reports/utilization?version={int(latest)}&start_date={week_start}&end_date={week_start}"),
                ("GET /reports/downtime", f"/reports/downtime?version={int(latest)}&start_date={week_start}&end_date={week_start}"),
            ]
            for name, url in reports_checks:
                rr = client.get(url)
                if rr.status_code != 200:
                    issues_all.append(f"报表页不可访问：{name} status={rr.status_code}")

            # 留痕抽检：关键 Excel import + 排产（OperationLogs.detail 键名）
            import_keys = [
                "filename",
                "mode",
                "time_cost_ms",
                "total_rows",
                "new_count",
                "update_count",
                "skip_count",
                "error_count",
                "errors_sample",
            ]
            schedule_keys = [
                "version",
                "strategy",
                "batch_ids",
                "batch_count",
                "op_count",
                "scheduled_ops",
                "failed_ops",
                "result_status",
                "time_cost_ms",
            ]
            checks = [
                ("process", "import", "op_type", import_keys),
                ("process", "import", "supplier", import_keys),
                ("equipment", "import", "machine", import_keys),
                ("personnel", "import", "operator", import_keys),
                ("personnel", "import", "operator_machine", import_keys),
                ("process", "import", "part_route", import_keys),
                ("scheduler", "import", "calendar", import_keys),
                ("scheduler", "import", "batch", import_keys),
                ("scheduler", "schedule", "schedule", schedule_keys),
            ]
            for m, act, tt, keys in checks:
                err = _check_oplog_keys(conn, module=m, action=act, target_type=tt, required_keys=keys)
                if err:
                    issues_all.append(err)

    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 汇总输出（case/run 自己的 json）
    result_obj = {
        "case_id": case.case_id,
        "title": case.title,
        "repeat_idx": int(repeat_idx),
        "base_seed": int(base_seed),
        "seed": int(seed),
        "tmpdir": tmpdir,
        "db": test_db,
        "start_dt": _fmt_dt(start_dt),
        "input_dir": input_dir,
        "output_dir": output_dir,
        "runs": run_summaries,
        "issues": issues_all,
    }
    _write_text(os.path.join(case_dir, "result.json"), json.dumps(result_obj, ensure_ascii=False, indent=2, default=str))
    return result_obj


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=os.path.join("evidence", "ComplexExcelCases"), help="证据输出目录（会在其下按 case/run 归档）")
    p.add_argument("--repeat", type=int, default=1, help="每个 case 重复运行次数（用于稳定性回归）")
    p.add_argument(
        "--cases",
        "--only",
        dest="cases",
        default=None,
        help="仅运行指定 case（逗号分隔），例如：Case05,Case06",
    )
    p.add_argument("--seed", type=int, default=1000, help="基准随机种子（用于复现；默认 1000）")
    args = p.parse_args(argv)

    repo_root = find_repo_root()
    out_base = os.path.join(repo_root, str(args.out))
    _ensure_dir(out_base)

    cases = _build_case_specs()
    if args.cases:
        wanted = [x.strip() for x in str(args.cases).split(",") if x.strip()]
        wanted_set = set(wanted)
        cases = [c for c in cases if c.case_id in wanted_set]
        if not cases:
            raise RuntimeError(f"--cases 未命中任何 case：{wanted}")
    report_lines: List[str] = []
    report_lines.append("# 复杂排产 Excel Cases 全流程验证报告")
    report_lines.append("")
    report_lines.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"- repeat：{int(args.repeat)}")
    report_lines.append(f"- seed：{int(args.seed)}")
    if args.cases:
        report_lines.append(f"- cases：{str(args.cases)}")
    report_lines.append("")
    report_lines.append("## Sanity 检查项（自动判定“离谱结果”）")
    report_lines.append("")
    report_lines.append("- **Schedule 覆盖率**：`Schedule(version)` 行数必须等于所选批次 `BatchOperations` 总数（不允许漏排/少排）。")
    report_lines.append("- **时间合法性**：每条任务必须满足 `start_time < end_time`，且不得早于本次 `start_dt`。")
    report_lines.append("- **资源完整性**：internal 工序必须具备 `machine_id` + `operator_id`。")
    report_lines.append("- **资源不重叠**：同一设备/同一人员的任务区间不得重叠（允许端点相接）。")
    report_lines.append("- **停机避让**：internal 任务不得与 `MachineDowntimes(status=active)` 区间重叠。")
    report_lines.append("- **外协 merged 一致性**：同一批次同一外协组（merge_mode=merged）组内工序必须共享同一 `(start,end)`。")
    report_lines.append("- **跨度合理性**：若出现 `max_end > start_dt + 365d` 视为异常。")
    report_lines.append("- **页面可访问性**：抽检 `/scheduler/gantt/data`、`/scheduler/week-plan/export`、`/reports/*` 返回 200。")
    report_lines.append("- **留痕键名**：抽检关键 `OperationLogs` 记录的 `detail` 键名是否齐全（Excel import + 排产 schedule）。")
    report_lines.append("")

    failed = False
    all_results: List[Dict[str, Any]] = []

    for case in cases:
        report_lines.append(f"## {case.case_id} - {case.title}")
        report_lines.append("")
        report_lines.append(f"- 说明：{case.desc}")
        report_lines.append("")

        for r in range(int(args.repeat)):
            try:
                res = run_one_case(case=case, out_base=out_base, repeat_idx=r + 1, base_seed=int(args.seed))
                all_results.append(res)
                issues = res.get("issues") or []
                report_lines.append(f"### run_{r+1:02d}")
                report_lines.append(f"- 临时目录：`{res.get('tmpdir')}`")
                report_lines.append(f"- DB：`{res.get('db')}`")
                report_lines.append(f"- 输入：`{res.get('input_dir')}`")
                report_lines.append(f"- 输出：`{res.get('output_dir')}`")
                report_lines.append(f"- start_dt：`{res.get('start_dt')}`")
                report_lines.append(f"- 结果文件：`{os.path.join(res.get('case_id'), f'run_{r+1:02d}', 'result.json')}`（相对 --out 目录）")
                report_lines.append("")
                for rr in res.get("runs") or []:
                    ver = rr.get("version")
                    algo = rr.get("algo_mode")
                    hist = rr.get("history") or {}
                    rs = hist.get("result_summary") if isinstance(hist, dict) else None
                    counts = (rs.get("counts") or {}) if isinstance(rs, dict) else {}
                    overdue = ((rs.get("overdue_batches") or {}).get("count")) if isinstance(rs, dict) else None
                    tms = (rs.get("time_cost_ms")) if isinstance(rs, dict) else None
                    algo_meta = (rs.get("algo") or {}) if isinstance(rs, dict) else {}
                    obj = algo_meta.get("objective") if isinstance(algo_meta, dict) else None
                    tb = algo_meta.get("time_budget_seconds") if isinstance(algo_meta, dict) else None
                    best_score = algo_meta.get("best_score") if isinstance(algo_meta, dict) else None
                    metrics = algo_meta.get("metrics") if isinstance(algo_meta, dict) else None

                    report_lines.append(
                        f"- 排产：algo={algo} version={ver} result_status={hist.get('result_status')} "
                        f"ops={counts.get('scheduled_ops')}/{counts.get('op_count')} failed={counts.get('failed_ops')} "
                        f"overdue={overdue} time_cost_ms={tms} objective={obj} budget_s={tb}"
                    )
                    if isinstance(best_score, list) and best_score:
                        report_lines.append(f"  - best_score：{best_score}")
                    if isinstance(metrics, dict):
                        # 只展示高信号指标，避免报告过长
                        report_lines.append(
                            "  - metrics："
                            f"overdue_count={metrics.get('overdue_count')} "
                            f"tardiness_h={metrics.get('total_tardiness_hours')} "
                            f"makespan_h={metrics.get('makespan_hours')} "
                            f"changeover={metrics.get('changeover_count')} "
                            f"machine_util_avg={metrics.get('machine_util_avg')} "
                            f"operator_util_avg={metrics.get('operator_util_avg')} "
                            f"machine_load_cv={metrics.get('machine_load_cv')} "
                            f"operator_load_cv={metrics.get('operator_load_cv')}"
                        )
                if issues:
                    failed = True
                    report_lines.append("")
                    report_lines.append(f"- **sanity：不通过（{len(issues)} 条）**")
                    for x in issues[:40]:
                        report_lines.append(f"  - {x}")
                    if len(issues) > 40:
                        report_lines.append(f"  - ...（剩余 {len(issues)-40} 条见 `result.json`）")
                else:
                    report_lines.append("- **sanity：通过**")
                report_lines.append("")
            except Exception as e:
                failed = True
                report_lines.append(f"### run_{r+1:02d}")
                report_lines.append(f"- **执行失败**：{e}")
                report_lines.append("")
                report_lines.append("```")
                report_lines.append(traceback.format_exc())
                report_lines.append("```")
                report_lines.append("")

    report_path = os.path.join(out_base, "complex_cases_report.md")
    _write_text(report_path, "\n".join(report_lines) + "\n")

    # 额外留一份聚合 JSON，便于机器分析
    _write_text(os.path.join(out_base, "complex_cases_summary.json"), json.dumps(all_results, ensure_ascii=False, indent=2, default=str))

    print(report_path)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

