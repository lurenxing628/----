"""
APS 漂移检测（综合体检）脚本。
依次运行：架构审计 → 一致性对标 → ruff 全量 → 文档新鲜度。
输出综合 Markdown 报告。
"""
import argparse
import locale
import os
import subprocess
import sys
import time

DEFAULT_SCRIPT_TIMEOUT_S = 180
DEFAULT_RUFF_TIMEOUT_S = 300
TIMEOUT_EXIT_CODE = 124  # 与常见 CI 约定一致：超时 = 124


def find_repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(here, "app.py")) and os.path.exists(os.path.join(here, "schema.sql")):
            return here
        here = os.path.dirname(here)
    raise RuntimeError("未找到项目根目录")


def _tail_nonempty_lines(text: str, n: int = 3, limit: int = 300) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return "(无输出)"
    s = " | ".join(lines[-max(int(n), 1):])
    return s[: max(int(limit), 1)]


def _decode_subprocess_output(data) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        text = data
    else:
        encodings = ["utf-8", "utf-8-sig"]
        preferred = locale.getpreferredencoding(False)
        if preferred:
            encodings.append(preferred)
        encodings.extend(["gbk", "cp936"])
        text = ""
        for enc in encodings:
            if not enc:
                continue
            try:
                text = data.decode(enc)
                break
            except Exception:
                continue
        if text == "":
            text = data.decode("utf-8", errors="ignore")
    return text.replace("\ufeff", "").replace("\ufffd", "")


def run_script(repo_root, script_rel, label, *, timeout_s: int):
    """运行子脚本并返回 (exit_code, stdout)。"""
    script_path = os.path.join(repo_root, script_rel)
    if not os.path.exists(script_path):
        return -1, f"脚本不存在：{script_rel}"
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=repo_root,
            capture_output=True,
            timeout=int(timeout_s),
        )
        out = _decode_subprocess_output(result.stdout)
        err = _decode_subprocess_output(result.stderr)
        merged = out + ("\n" if out and err else "") + err
        return result.returncode, merged.strip()
    except subprocess.TimeoutExpired as e:
        out = _decode_subprocess_output(getattr(e, "stdout", None))
        err = _decode_subprocess_output(getattr(e, "stderr", None))
        merged = out + ("\n" if out and err else "") + err
        note = f"[TIMEOUT] {label} 超时（>{int(timeout_s)}s）：{script_rel}"
        return TIMEOUT_EXIT_CODE, (note + ("\n" + merged if merged else "")).strip()
    except Exception as e:
        return -1, f"[ERROR] {label} 执行异常：{type(e).__name__}: {e}"

def run_ruff_full(repo_root, *, timeout_s: int):
    """对核心目录运行 ruff check。"""
    dirs = ["web/routes", "core/services", "data/repositories", "core/infrastructure", "core/models"]
    abs_dirs = [os.path.join(repo_root, d) for d in dirs if os.path.isdir(os.path.join(repo_root, d))]
    if not abs_dirs:
        return 0, "无核心目录"
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format", "grouped"] + abs_dirs,
            cwd=repo_root,
            capture_output=True,
            timeout=int(timeout_s),
        )
        stdout = _decode_subprocess_output(result.stdout)
        stderr = _decode_subprocess_output(result.stderr)
        summary_lines = [line for line in stdout.strip().splitlines() if line.startswith("Found ")]
        merged = stdout if stdout else stderr
        return result.returncode, "\n".join(summary_lines) if summary_lines else merged[-500:] if merged else "(无输出)"
    except FileNotFoundError:
        return -1, "ruff 未安装，跳过 lint 全量检查"
    except subprocess.TimeoutExpired as e:
        out = _decode_subprocess_output(getattr(e, "stdout", None))
        err = _decode_subprocess_output(getattr(e, "stderr", None))
        merged = out + ("\n" if out and err else "") + err
        note = f"[TIMEOUT] Ruff 超时（>{int(timeout_s)}s）"
        return TIMEOUT_EXIT_CODE, (note + ("\n" + merged if merged else "")).strip()

def check_doc_freshness(repo_root):
    """检查开发文档最后修改时间 vs 代码最后修改时间。"""
    doc_files = [
        "开发文档/开发文档.md",
        "开发文档/系统速查表.md",
        "开发文档/面板与接口清单.md",
        "开发文档/阶段留痕与验收记录.md",
    ]
    code_dirs = ["web/routes", "core/services", "data/repositories", "schema.sql"]

    latest_code_time = 0
    latest_code_file = ""
    for cd in code_dirs:
        p = os.path.join(repo_root, cd)
        if os.path.isfile(p):
            mt = os.path.getmtime(p)
            if mt > latest_code_time:
                latest_code_time = mt
                latest_code_file = cd
        elif os.path.isdir(p):
            for dirpath, _, filenames in os.walk(p):
                for fname in filenames:
                    if fname.endswith(".py"):
                        fp = os.path.join(dirpath, fname)
                        mt = os.path.getmtime(fp)
                        if mt > latest_code_time:
                            latest_code_time = mt
                            latest_code_file = os.path.relpath(fp, repo_root).replace("\\", "/")

    stale_docs = []
    for doc in doc_files:
        dp = os.path.join(repo_root, doc)
        if os.path.exists(dp):
            doc_time = os.path.getmtime(dp)
            if latest_code_time - doc_time > 86400:
                days = int((latest_code_time - doc_time) / 86400)
                stale_docs.append(f"{doc}（落后代码 {days} 天）")

    return stale_docs, latest_code_file


def main(argv=None):
    p = argparse.ArgumentParser(description="APS 漂移检测（综合体检）")
    p.add_argument("--timeout", type=int, default=DEFAULT_SCRIPT_TIMEOUT_S, help="子步骤默认超时秒数（默认：180）")
    p.add_argument("--timeout-arch", type=int, default=None, help="架构审计超时秒数（默认：同 --timeout）")
    p.add_argument("--timeout-conf", type=int, default=None, help="一致性对标超时秒数（默认：同 --timeout）")
    p.add_argument("--timeout-ruff", type=int, default=DEFAULT_RUFF_TIMEOUT_S, help="Ruff 全量超时秒数（默认：300）")
    args = p.parse_args(list(argv) if argv is not None else None)

    repo_root = find_repo_root()
    start = time.time()

    lines = []
    lines.append("# APS 漂移检测（综合体检）报告")
    lines.append("")
    lines.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 仓库根目录：`{repo_root}`")
    lines.append("")

    overall_ok = True
    timeout_arch = int(args.timeout_arch) if args.timeout_arch is not None else int(args.timeout)
    timeout_conf = int(args.timeout_conf) if args.timeout_conf is not None else int(args.timeout)
    timeout_ruff = int(args.timeout_ruff)

    # 1) 架构审计
    print("[1/4] 运行架构审计...")
    arch_code, arch_out = run_script(
        repo_root,
        ".cursor/skills/aps-arch-audit/scripts/arch_audit.py",
        "架构审计",
        timeout_s=timeout_arch,
    )
    arch_ok = arch_code == 0
    if not arch_ok:
        overall_ok = False
    lines.append("## 1. 架构合规审计")
    lines.append(f"- 结论：{'PASS' if arch_ok else 'FAIL'}")
    lines.append(f"- exit_code：{arch_code}")
    if not arch_ok:
        if arch_code == TIMEOUT_EXIT_CODE:
            lines.append(f"- 备注：TIMEOUT（>{timeout_arch}s）")
        else:
            lines.append(f"- 失败摘要：{_tail_nonempty_lines(arch_out)}")
    lines.append("- 详细报告：`evidence/ArchAudit/arch_audit_report.md`")
    lines.append("")

    # 2) 一致性对标
    print("[2/4] 运行一致性对标...")
    conf_code, conf_out = run_script(
        repo_root,
        "tests/generate_conformance_report.py",
        "一致性对标",
        timeout_s=timeout_conf,
    )
    conf_ok = conf_code == 0
    if not conf_ok:
        overall_ok = False
    lines.append("## 2. 一致性对标报告")
    lines.append(f"- 结论：{'PASS' if conf_ok else 'FAIL'}")
    lines.append(f"- exit_code：{conf_code}")
    if not conf_ok:
        if conf_code == TIMEOUT_EXIT_CODE:
            lines.append(f"- 备注：TIMEOUT（>{timeout_conf}s）")
        else:
            lines.append(f"- 失败摘要：{_tail_nonempty_lines(conf_out)}")
    lines.append("- 详细报告：`evidence/Conformance/conformance_report.md`")
    lines.append("")

    # 3) Ruff 全量
    print("[3/4] 运行 Ruff 全量检查...")
    ruff_code, ruff_summary = run_ruff_full(repo_root, timeout_s=timeout_ruff)
    ruff_ok = ruff_code == 0
    if ruff_code not in (0, -1):
        overall_ok = False
    lines.append("## 3. Ruff Lint 全量检查")
    if ruff_code == -1:
        lines.append("- 结论：SKIP（ruff 未安装）")
    else:
        lines.append(f"- 结论：{'PASS' if ruff_ok else 'FAIL'}")
    lines.append(f"- exit_code：{ruff_code}")
    if ruff_code == TIMEOUT_EXIT_CODE:
        lines.append(f"- 备注：TIMEOUT（>{timeout_ruff}s）")
    lines.append(f"- 摘要：{ruff_summary.strip()}")
    lines.append("")

    # 4) 文档新鲜度
    print("[4/4] 检查文档新鲜度...")
    stale_docs, latest_code = check_doc_freshness(repo_root)
    lines.append("## 4. 文档新鲜度")
    lines.append(f"- 代码最新修改：`{latest_code}`")
    if stale_docs:
        lines.append("- 以下文档可能需要更新：")
        for sd in stale_docs:
            lines.append(f"  - {sd}")
    else:
        lines.append("- 所有文档均在代码变更 1 天内更新过")
    lines.append("")

    # 总结
    elapsed = time.time() - start
    lines.append("## 总结")
    if overall_ok and not stale_docs:
        verdict = "健康"
    elif not overall_ok:
        verdict = "需要修复"
    else:
        verdict = "需要关注"
    lines.append(f"- 健康状态：**{verdict}**")
    lines.append(f"- 耗时：{elapsed:.1f} 秒")
    lines.append("")

    report = ("\n".join(lines) + "\n").replace("\ufffd", "")

    out_dir = os.path.join(repo_root, "evidence", "DriftDetect")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "drift_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    try:
        print("\n" + report)
    except UnicodeEncodeError:
        # 子脚本输出按 UTF-8 解码时可能产生 U+FFFD（�），GBK 控制台无法编码该字符
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(("\n" + report).encode(enc, errors="replace").decode(enc, errors="replace"))
    print(f"综合报告已输出到：{out_path}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
