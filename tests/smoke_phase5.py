import os
import sys
import tempfile
import time
import traceback


def find_repo_root():
    """
    约定：用户机器常见路径为 D:\\Github\\<项目>，且根目录包含 app.py 与 schema.sql。
    为了兼容本地/CI/不同目录结构，增加 fallback：使用当前 tests/ 的上一级作为 repo_root。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root

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
    lines.append("# Phase5（工艺管理模块）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase5_")
    test_db = os.path.join(tmpdir, "aps_phase5_test.db")
    lines.append("")
    lines.append("## 0. 测试环境")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")

    sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import AppError, ErrorCode
    from core.services.process import ExternalGroupService, PartService, RouteParser
    from data.repositories import OpTypeRepository, SupplierRepository

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
        lines.append("")
        lines.append("## 1. Schema 检查（Phase5 相关表）")
        for t in ["OpTypes", "Suppliers", "Parts", "PartOperations", "ExternalGroups"]:
            lines.append(f"- 是否存在 {t}：{t in tables}")

        # 准备工种（内部/外部）
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_1", "数铣", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_2", "钳", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_3", "数车", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_1", "标印", "external"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_2", "总检", "external"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_3", "表处理", "external"))

        # 准备供应商（按工种绑定）
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            ("S001", "外协-标印厂", "OT_EX_1", 0.5, "active"),
        )
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            ("S002", "外协-总检厂", "OT_EX_2", 1.0, "active"),
        )
        conn.commit()

        lines.append("")
        lines.append("## 2. 工艺路线解析器：预处理/识别/连续外部组")
        op_repo = OpTypeRepository(conn)
        sup_repo = SupplierRepository(conn)
        parser = RouteParser(op_repo, sup_repo, logger=None)
        r = parser.parse("5数铣 10钳-20数车、35标印 40总检45表处理", part_no="A1234")
        lines.append(f"- 解析状态：{r.status.value}")
        lines.append(f"- 统计：{r.stats}")
        lines.append(f"- 连续外部组数量：{len(r.external_groups)}（期望 1）")
        if len(r.external_groups) != 1:
            raise RuntimeError("连续外部组识别失败：期望 1 组")

        # 兼容分隔符：-> / > / →（按开发文档要求应被预处理移除）
        r_arrow = parser.parse("5数铣->10钳>20数车→35标印", part_no="A1234_ARROW")
        lines.append(f"- 分隔符兼容（->/>/→）解析状态：{r_arrow.status.value}")
        lines.append(f"- 分隔符兼容 operations：{[(op.seq, op.op_type_name) for op in r_arrow.operations]}")
        if [op.op_type_name for op in r_arrow.operations] != ["数铣", "钳", "数车", "标印"]:
            raise RuntimeError("分隔符兼容失败：工种名被污染或解析顺序不正确")

        lines.append("")
        lines.append("## 2.1 工艺路线解析器：边界用例（validate_format/重复工序号/未识别工种）")
        ok, msg = parser.validate_format("")
        lines.append(f"- validate_format(空)：ok={ok} msg={msg!r}")
        if ok:
            raise RuntimeError("validate_format 空字符串应返回 False")

        ok, msg = parser.validate_format("abc")
        lines.append(f"- validate_format(无工序号)：ok={ok} msg={msg!r}")
        if ok:
            raise RuntimeError("validate_format 无数字工序号应返回 False")

        ok, msg = parser.validate_format("5数车")
        lines.append(f"- validate_format(正常)：ok={ok} msg={msg!r}")
        if not ok:
            raise RuntimeError("validate_format 正常字符串应返回 True")

        # 重复工序号：应给 warning，且保留第一个
        r_dup = parser.parse("5数铣5钳10数车", part_no="P_DUP")
        lines.append(f"- 重复工序号解析状态：{r_dup.status.value}")
        lines.append(f"- 重复工序号 warnings：{r_dup.warnings}")
        lines.append(f"- 重复工序号 operations：{[(op.seq, op.op_type_name) for op in r_dup.operations]}")
        if r_dup.status.value != "partial":
            raise RuntimeError("重复工序号应产生 warnings，状态应为 partial")
        if not any("重复" in w for w in (r_dup.warnings or [])):
            raise RuntimeError("重复工序号应包含“重复”提示")
        if [op.seq for op in r_dup.operations].count(5) != 1:
            raise RuntimeError("重复工序号应只保留一个 seq=5")
        op5 = next((op for op in r_dup.operations if op.seq == 5), None)
        if not op5 or op5.op_type_name != "数铣":
            raise RuntimeError("重复工序号应保留第一个工种（期望 seq=5 为 数铣）")

        # 未识别工种：默认 external + warnings + unknown 统计
        r_unknown = parser.parse("5数铣10未知工种", part_no="P_UNK")
        lines.append(f"- 未识别工种解析状态：{r_unknown.status.value}")
        lines.append(f"- 未识别工种统计：{r_unknown.stats}")
        lines.append(f"- 未识别工种 warnings：{r_unknown.warnings}")
        if r_unknown.status.value != "partial":
            raise RuntimeError("未识别工种应产生 warnings，状态应为 partial")
        if (r_unknown.stats or {}).get("unknown") != 1:
            raise RuntimeError("未识别工种 unknown 统计应为 1")
        op10 = next((op for op in r_unknown.operations if op.seq == 10), None)
        if not op10:
            raise RuntimeError("未识别工种工序（seq=10）应存在")
        if op10.source != "external" or op10.is_recognized is not False:
            raise RuntimeError("未识别工种应默认 external 且 is_recognized=False")

        lines.append("")
        lines.append("## 3. 零件模板保存：解析后写 PartOperations + ExternalGroups")
        p_svc = PartService(conn)
        # 先创建零件
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("A1234", "壳体-大", "no"))
        conn.commit()
        result = p_svc.reparse_and_save("A1234", "5数铣10钳20数车35标印40总检45表处理")
        lines.append(f"- 保存后解析状态：{result.status.value}")

        ops = conn.execute("SELECT seq, op_type_name, source, supplier_id, ext_days, ext_group_id FROM PartOperations WHERE part_no=? AND status='active' ORDER BY seq", ("A1234",)).fetchall()
        groups = conn.execute("SELECT group_id, start_seq, end_seq, merge_mode, total_days FROM ExternalGroups WHERE part_no=? ORDER BY start_seq", ("A1234",)).fetchall()
        lines.append(f"- 工序数量：{len(ops)}（期望 6）")
        lines.append(f"- 外部组数量：{len(groups)}（期望 1）")
        if len(ops) != 6 or len(groups) != 1:
            raise RuntimeError("模板保存失败：工序/外部组数量不符合预期")

        gid = groups[0]["group_id"]
        lines.append(f"- 外部组ID：{gid}")

        lines.append("")
        lines.append("## 4. 连续外部工序合并周期：separate/merged 存储规则")
        eg_svc = ExternalGroupService(conn)

        # separate -> merged
        eg_svc.set_merge_mode(group_id=gid, merge_mode="merged", total_days=3)
        g1 = conn.execute("SELECT merge_mode, total_days FROM ExternalGroups WHERE group_id=?", (gid,)).fetchone()
        op_ext_days = conn.execute(
            "SELECT seq, ext_days FROM PartOperations WHERE part_no=? AND ext_group_id=? AND source='external' AND status='active' ORDER BY seq",
            ("A1234", gid),
        ).fetchall()
        lines.append(f"- 切换 merged：merge_mode={g1['merge_mode']} total_days={g1['total_days']}")
        lines.append(f"- 组内 ext_days：{[x['ext_days'] for x in op_ext_days]}（期望均为 None）")
        if g1["merge_mode"] != "merged" or g1["total_days"] is None:
            raise RuntimeError("merged 模式存储失败：ExternalGroups 未正确写入")
        if any(x["ext_days"] is not None for x in op_ext_days):
            raise RuntimeError("merged 模式存储失败：组内 ext_days 未清空为 NULL")

        # merged -> separate
        per_op = {int(x["seq"]): 1.0 for x in op_ext_days}
        eg_svc.set_merge_mode(group_id=gid, merge_mode="separate", per_op_days=per_op)
        g2 = conn.execute("SELECT merge_mode, total_days FROM ExternalGroups WHERE group_id=?", (gid,)).fetchone()
        op_ext_days2 = conn.execute(
            "SELECT seq, ext_days FROM PartOperations WHERE part_no=? AND ext_group_id=? AND source='external' AND status='active' ORDER BY seq",
            ("A1234", gid),
        ).fetchall()
        lines.append(f"- 切换 separate：merge_mode={g2['merge_mode']} total_days={g2['total_days']}")
        lines.append(f"- 组内 ext_days：{[x['ext_days'] for x in op_ext_days2]}（期望均有值）")
        if g2["merge_mode"] != "separate" or g2["total_days"] is not None:
            raise RuntimeError("separate 模式存储失败：ExternalGroups.total_days 未清空")
        if any(x["ext_days"] is None for x in op_ext_days2):
            raise RuntimeError("separate 模式存储失败：组内 ext_days 未写回")

        lines.append("")
        lines.append("## 5. 外部工序删除规则：中间外部组禁止，尾部外部组允许")
        # 案例A：中间外部组（应禁止）
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_MID", "中间外部组", "no"))
        conn.commit()
        p_svc.reparse_and_save("P_MID", "5数铣10标印15数车")
        gid_mid = conn.execute("SELECT group_id FROM ExternalGroups WHERE part_no='P_MID'").fetchone()["group_id"]
        try:
            p_svc.delete_external_group("P_MID", gid_mid)
            raise RuntimeError("期望中间外部组删除被拒绝，但未拒绝")
        except AppError as e:
            lines.append(f"- 中间外部组删除：code={e.code.value} message={e.message}")
            if e.code != ErrorCode.OPERATION_DELETE_DENIED:
                raise RuntimeError("中间外部组删除未返回 OPERATION_DELETE_DENIED")

        # 案例B：尾部外部组（应允许）
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_TAIL", "尾部外部组", "no"))
        conn.commit()
        p_svc.reparse_and_save("P_TAIL", "5数铣10数车15标印20总检")
        gid_tail = conn.execute("SELECT group_id FROM ExternalGroups WHERE part_no='P_TAIL'").fetchone()["group_id"]
        r = p_svc.delete_external_group("P_TAIL", gid_tail)
        lines.append(f"- 尾部外部组删除：{r}")

        remained_groups = conn.execute("SELECT COUNT(1) AS c FROM ExternalGroups WHERE part_no='P_TAIL'").fetchone()["c"]
        remained_ext_ops = conn.execute(
            "SELECT COUNT(1) AS c FROM PartOperations WHERE part_no='P_TAIL' AND source='external' AND status='active'"
        ).fetchone()["c"]
        lines.append(f"- 删除后外部组剩余：{remained_groups}（期望 0）")
        lines.append(f"- 删除后外部工序剩余：{remained_ext_ops}（期望 0）")
        if remained_groups != 0 or remained_ext_ops != 0:
            raise RuntimeError("尾部外部组删除未生效（ExternalGroups/PartOperations 未同步）")

        # 案例C：首部外部组（应允许）
        lines.append("")
        lines.append("## 5.1 外部工序删除规则：首部外部组允许")
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_HEAD", "首部外部组", "no"))
        conn.commit()
        p_svc.reparse_and_save("P_HEAD", "5标印10总检15数铣20数车")
        gid_head = conn.execute("SELECT group_id FROM ExternalGroups WHERE part_no='P_HEAD'").fetchone()["group_id"]
        r_head = p_svc.delete_external_group("P_HEAD", gid_head)
        lines.append(f"- 首部外部组删除：{r_head}")
        remained_groups = conn.execute("SELECT COUNT(1) AS c FROM ExternalGroups WHERE part_no='P_HEAD'").fetchone()["c"]
        remained_ext_ops = conn.execute(
            "SELECT COUNT(1) AS c FROM PartOperations WHERE part_no='P_HEAD' AND source='external' AND status='active'"
        ).fetchone()["c"]
        lines.append(f"- 删除后外部组剩余：{remained_groups}（期望 0）")
        lines.append(f"- 删除后外部工序剩余：{remained_ext_ops}（期望 0）")
        if remained_groups != 0 or remained_ext_ops != 0:
            raise RuntimeError("首部外部组删除未生效（ExternalGroups/PartOperations 未同步）")

        # 案例D：全部外部工序（应允许，且为 warning 分支：删除后无工序）
        lines.append("")
        lines.append("## 5.2 外部工序删除规则：全部外部工序（warning 分支）")
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_ALL_EX", "全部外部工序", "no"))
        conn.commit()
        p_svc.reparse_and_save("P_ALL_EX", "5标印10总检")
        gid_all = conn.execute("SELECT group_id FROM ExternalGroups WHERE part_no='P_ALL_EX'").fetchone()["group_id"]
        r_all = p_svc.delete_external_group("P_ALL_EX", gid_all)
        lines.append(f"- 全部外部工序删除：{r_all}")
        if r_all.get("result") != "warning":
            raise RuntimeError("全部外部工序删除应进入 warning 分支（result=warning）")

        lines.append("")
        lines.append("## 结论")
        lines.append("- 通过：Phase5（工艺管理模块）冒烟测试通过（解析器/边界用例/模板保存/合并周期/删除规则）。")
        lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    report_path = os.path.join(repo_root, "evidence", "Phase5", "smoke_phase5_report.md")
    write_report(report_path, lines)
    print("OK")
    print(report_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        repo_root = None
        try:
            repo_root = find_repo_root()
        except Exception:
            pass

        lines = []
        lines.append("# Phase5（工艺管理模块）冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase5", "smoke_phase5_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

