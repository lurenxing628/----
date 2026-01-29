import io
import json
import os
import tempfile
import time
import traceback


def find_repo_root():
    """
    约定：用户机器常见路径为 D:\\Github\\<项目>，且根目录包含 app.py 与 schema.sql。
    为了兼容本地/CI/不同目录结构，增加 fallback：使用当前 tests/ 的上一级作为 repo_root。
    """
    # 1) 优先：tests/ 的上一级目录（脚本与代码同仓库时最可靠）
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root

    # 2) 兼容：按既有约定扫描 D:\Github
    base = r"D:\Github"
    try:
        if os.path.isdir(base):
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if not os.path.isdir(p):
                    continue
                if os.path.exists(os.path.join(p, "app.py")) and os.path.exists(os.path.join(p, "schema.sql")):
                    return p
    except Exception:
        pass

    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def write_report(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase0+Phase1 冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{os.sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    # 为测试使用临时目录（避免污染真实 db/logs/backups）
    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_")
    test_db = os.path.join(tmpdir, "aps_test.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    # 确保可以 import 项目模块
    os.sys.path.insert(0, repo_root)

    # 0) 依赖版本（用于留痕）
    import flask
    import openpyxl

    lines.append(f"- Flask：{getattr(flask, '__version__', 'unknown')}")
    lines.append(f"- openpyxl：{getattr(openpyxl, '__version__', 'unknown')}")
    lines.append("")
    lines.append("## 0. 测试环境与目录")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")
    lines.append(f"- 测试日志目录：`{test_logs}`")
    lines.append(f"- 测试备份目录：`{test_backups}`")

    # 1) Schema 初始化与“无资源锁”证明
    from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
        lines.append("")
        lines.append("## 1. Schema 检查")
        lines.append(f"- 表数量：{len(tables)}")
        lines.append(f"- 是否存在 SchemaVersion：{'SchemaVersion' in tables}")
        lines.append(f"- 是否存在 OperationLogs：{'OperationLogs' in tables}")
        lines.append(f"- 是否存在 ResourceLocks：{'ResourceLocks' in tables}")
        if "ResourceLocks" in tables:
            raise RuntimeError("发现 ResourceLocks 表：V1 明确不应存在")
        if "SchemaVersion" not in tables:
            raise RuntimeError("缺少 SchemaVersion 表：无法进行版本化迁移/回滚")
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        v = int(row[0]) if row else 0
        lines.append(f"- SchemaVersion.version：{v}")
        if v < CURRENT_SCHEMA_VERSION:
            raise RuntimeError(f"SchemaVersion.version 异常：{v}（期望 >= {CURRENT_SCHEMA_VERSION}）")
    finally:
        conn.close()

    # 1.1) 迁移机制验证（构造“旧库”缺列场景，确认：迁移前备份 + 缺列补齐 + SchemaVersion 升级）
    lines.append("")
    lines.append("## 1.1 Schema 迁移机制（缺列补齐 + 迁移前备份）")

    import sqlite3

    old_db = os.path.join(tmpdir, "aps_old_schema.db")
    migrate_backups = os.path.join(tmpdir, "backups_migrate")
    os.makedirs(migrate_backups, exist_ok=True)

    # 构造最小旧表：故意缺少 Batches.ready_date / Machines.category
    conn0 = sqlite3.connect(old_db)
    try:
        conn0.executescript(
            """
            PRAGMA foreign_keys = OFF;
            CREATE TABLE Batches (
                batch_id        TEXT PRIMARY KEY,
                part_no         TEXT NOT NULL,
                part_name       TEXT,
                quantity        INTEGER NOT NULL,
                due_date        DATE,
                priority        TEXT DEFAULT 'normal',
                ready_status    TEXT DEFAULT 'yes',
                status          TEXT DEFAULT 'pending',
                remark          TEXT
            );

            CREATE TABLE Machines (
                machine_id      TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                op_type_id      TEXT,
                status          TEXT DEFAULT 'active',
                remark          TEXT
            );
            """
        )
        conn0.commit()
    finally:
        conn0.close()

    # 对旧库执行 ensure_schema（应触发：SchemaVersion=0 -> 迁移到当前版本，并生成 before_migrate 备份）
    ensure_schema(old_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=migrate_backups)

    expected_suffix = f"before_migrate_v0_to_v{CURRENT_SCHEMA_VERSION}"
    backup_files = [f for f in os.listdir(migrate_backups) if expected_suffix in f and f.endswith(".db")]
    lines.append(f"- 迁移前备份文件数（{expected_suffix}）：{len(backup_files)}")
    if not backup_files:
        raise RuntimeError(f"未生成迁移前备份（{expected_suffix}）")

    conn1 = get_connection(old_db)
    try:
        cols_batches = [r[1] for r in conn1.execute("PRAGMA table_info(Batches)").fetchall()]
        cols_machines = [r[1] for r in conn1.execute("PRAGMA table_info(Machines)").fetchall()]
        if "ready_date" not in cols_batches:
            raise RuntimeError("迁移后仍缺少 Batches.ready_date")
        if "category" not in cols_machines:
            raise RuntimeError("迁移后仍缺少 Machines.category")
        row = conn1.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        v = int(row[0]) if row else 0
        lines.append(f"- 旧库迁移后 SchemaVersion.version：{v}")
        if v < CURRENT_SCHEMA_VERSION:
            raise RuntimeError(f"旧库迁移后 SchemaVersion.version 异常：{v}（期望 >= {CURRENT_SCHEMA_VERSION}）")
    finally:
        conn1.close()

    # 2) OpenpyxlBackend 读写 + ExcelService 预览
    from core.services.common.openpyxl_backend import OpenpyxlBackend
    from core.services.common.excel_service import ExcelService, ImportMode, RowStatus

    backend = OpenpyxlBackend()
    svc = ExcelService(backend=backend)

    xlsx_path = os.path.join(tmpdir, "test.xlsx")
    backend.write(
        rows=[
            {"工号": "OP001", "姓名": "张三", "状态": "active", "备注": "a"},
            {"工号": "OP002", "姓名": "李四", "状态": "inactive", "备注": None},
        ],
        file_path=xlsx_path,
        sheet="Sheet1",
    )
    read_rows = backend.read(xlsx_path)

    lines.append("")
    lines.append("## 2. Excel 读写与预览")
    lines.append(f"- 写入并读取行数：{len(read_rows)}（期望 2）")
    if len(read_rows) != 2:
        raise RuntimeError("OpenpyxlBackend 读写行数不符合预期")

    existing = {
        "OP001": {"工号": "OP001", "姓名": "张三", "状态": "active", "备注": "old"},
    }
    preview = svc.preview_import(
        rows=read_rows,
        id_column="工号",
        existing_data=existing,
        validators=[],
        mode=ImportMode.OVERWRITE,
    )

    status_counts = {}
    for r in preview:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1
    lines.append(f"- 预览状态统计：{json.dumps(status_counts, ensure_ascii=False)}")

    # 基本断言：OP001 应为 UPDATE 或 UNCHANGED（取决于备注差异）
    # 这里我们保证 existing['OP001']['备注']='old'，导入行备注='a'，应为 UPDATE
    op001 = next((r for r in preview if r.data.get("工号") == "OP001"), None)
    if not op001 or op001.status != RowStatus.UPDATE:
        raise RuntimeError("预览差异判断不符合预期：OP001 应为 UPDATE")
    lines.append(f"- OP001 行号(row_num)：{op001.row_num}（应为 2）")
    if op001.row_num != 2:
        raise RuntimeError("row_num 计算不符合预期（应为标题行+1）")

    # 3) 留痕：OperationLogs 写入（import/export）
    from core.infrastructure.logging import OperationLogger
    from core.services.common.excel_audit import log_excel_import, log_excel_export

    conn = get_connection(test_db)
    try:
        op_logger = OperationLogger(conn)
        log_excel_import(
            op_logger=op_logger,
            module="smoke_test",
            target_type="operator",
            filename="test.xlsx",
            mode=ImportMode.OVERWRITE,
            preview_or_result=preview,
            time_cost_ms=123,
        )
        log_excel_export(
            op_logger=op_logger,
            module="smoke_test",
            target_type="operator",
            template_or_export_type="人员基本信息模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=45,
        )
        rows = conn.execute(
            "SELECT id, log_level, module, action, target_type, detail FROM OperationLogs ORDER BY id DESC LIMIT 5"
        ).fetchall()

        lines.append("")
        lines.append("## 3. 留痕（OperationLogs）检查")
        lines.append(f"- 最近记录数（取 5 条）：{len(rows)}")
        for r in rows:
            detail = r["detail"]
            lines.append(f"- id={r['id']} action={r['action']} module={r['module']} target_type={r['target_type']}")
            # detail 是 JSON 字符串（键名英文固定）
            lines.append(f"  - detail={detail}")
    finally:
        conn.close()

    # 4) Flask 路由可用（不启动 server，使用 test client）
    import importlib

    app_mod = importlib.import_module("app")
    test_app = app_mod.create_app()
    client = test_app.test_client()

    lines.append("")
    lines.append("## 4. Web 冒烟（Flask test_client）")
    r = client.get("/")
    lines.append(f"- GET /：{r.status_code}")
    if r.status_code != 200:
        raise RuntimeError("GET / 返回非 200")

    r = client.get("/excel-demo/")
    lines.append(f"- GET /excel-demo/：{r.status_code}")
    if r.status_code != 200:
        raise RuntimeError("GET /excel-demo/ 返回非 200")

    # 用户可见中文提示：404 页面
    r = client.get("/__not_found__")
    lines.append(f"- GET /__not_found__：{r.status_code}")
    body = r.data.decode("utf-8", errors="ignore")
    if r.status_code != 404:
        raise RuntimeError("404 测试失败：状态码不是 404")
    if "页面不存在" not in body and "请求的资源不存在" not in body:
        raise RuntimeError("404 页面中文提示缺失（应包含“页面不存在/请求的资源不存在”）")

    r = client.get("/excel-demo/template")
    lines.append(f"- GET /excel-demo/template：{r.status_code} content-type={r.headers.get('Content-Type')}")
    if r.status_code != 200:
        raise RuntimeError("GET /excel-demo/template 返回非 200")

    # 端到端：上传 → 预览 → 确认导入（验证 Operators + OperationLogs）
    lines.append("")
    lines.append("### 4.1 端到端：上传→预览→确认导入")
    import re
    import html as html_module

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工号", "姓名", "状态", "备注"])
    ws.append(["OP100", "测试员A", "active", "e2e"])
    ws.append(["OP101", "测试员B", "inactive", "e2e"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = client.post(
        "/excel-demo/preview",
        data={
            "mode": "overwrite",
            "file": (buf, "e2e.xlsx"),
        },
        content_type="multipart/form-data",
    )
    lines.append(f"- POST /excel-demo/preview：{resp.status_code}")
    if resp.status_code != 200:
        raise RuntimeError("预览接口返回非 200")

    html = resp.data.decode("utf-8", errors="ignore")
    if "导入预览" not in html:
        raise RuntimeError("预览页面未包含“导入预览”字样（可能渲染失败）")

    m = re.search(r'<textarea name=\"raw_rows_json\"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("未能从预览页面提取 raw_rows_json（确认导入需要该字段）")
    raw_rows_json = html_module.unescape(m.group(1)).strip()

    resp2 = client.post(
        "/excel-demo/confirm",
        data={
            "mode": "overwrite",
            "filename": "e2e.xlsx",
            "raw_rows_json": raw_rows_json,
        },
        follow_redirects=True,
    )
    lines.append(f"- POST /excel-demo/confirm（follow_redirects）：{resp2.status_code}")
    if resp2.status_code != 200:
        raise RuntimeError("确认导入流程返回非 200")

    # 核对数据库写入
    conn = get_connection(test_db)
    try:
        c = conn.execute("SELECT COUNT(1) FROM Operators WHERE operator_id IN ('OP100','OP101')").fetchone()[0]
        lines.append(f"- Operators 写入校验：OP100/OP101 行数={c}（期望 2）")
        if c != 2:
            raise RuntimeError("确认导入未写入 Operators 表")

        # 核对 OperationLogs
        log_cnt = conn.execute(
            "SELECT COUNT(1) FROM OperationLogs WHERE module='excel_demo' AND action='import'"
        ).fetchone()[0]
        lines.append(f"- OperationLogs 写入校验：excel_demo import 记录数={log_cnt}（期望 >= 1）")
        if log_cnt < 1:
            raise RuntimeError("确认导入未写入 OperationLogs（excel_demo/import）")
    finally:
        conn.close()

    # 5) 退出自动备份（直接调用 BackupManager 代替真实退出）
    from core.infrastructure.backup import BackupManager

    bm = BackupManager(db_path=test_db, backup_dir=test_backups, keep_days=7)
    auto_path = bm.backup(suffix="auto_test")
    lines.append("")
    lines.append("## 5. 备份检查")
    lines.append(f"- 手动触发备份：`{auto_path}`")
    lines.append(f"- backups 文件数：{len(os.listdir(test_backups))}")

    # 6) 日志文件存在性与摘录（用户排障）
    lines.append("")
    lines.append("## 6. 文件日志检查（用户排障）")
    aps_log = os.path.join(test_logs, "aps.log")
    aps_err = os.path.join(test_logs, "aps_error.log")
    lines.append(f"- aps.log 是否存在：{os.path.exists(aps_log)}（`{aps_log}`）")
    lines.append(f"- aps_error.log 是否存在：{os.path.exists(aps_err)}（`{aps_err}`）")

    def tail(path, max_lines=20):
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.read().splitlines()
            return all_lines[-max_lines:]
        except Exception:
            return []

    tail_log = tail(aps_log, 20)
    if tail_log:
        lines.append("")
        lines.append("### aps.log 摘录（最后 20 行）")
        lines.append("```")
        lines.extend(tail_log)
        lines.append("```")

    # 成功结论
    lines.append("")
    lines.append("## 结论")
    lines.append("- 通过：Phase0+Phase1 核心链路冒烟测试通过（Schema/Excel/留痕/Web/备份）。")
    lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    report_path = os.path.join(repo_root, "evidence", "Phase0_Phase1", "smoke_test_report.md")
    write_report(report_path, lines)
    print("OK")
    print(report_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 失败也输出报告
        repo_root = None
        try:
            repo_root = find_repo_root()
        except Exception:
            pass

        lines = []
        lines.append("# Phase0+Phase1 冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase0_Phase1", "smoke_test_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

