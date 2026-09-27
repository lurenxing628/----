"""Wrap verified portable 7z volumes in self-contained ZIPs below a byte limit."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from scripts.portable_release import payload_files

REPO = Path(__file__).resolve().parents[1]


def digest(file: Path) -> str:
    value = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def record(file: Path, relative: str) -> dict:
    return {"Path": relative, "SHA256": digest(file), "Bytes": file.stat().st_size}


def csv_file(file: Path, rows: list) -> None:
    with file.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def archive(output: Path, files: list, maximum: int) -> None:
    with zipfile.ZipFile(str(output), "x", compression=zipfile.ZIP_STORED) as target:
        for source, relative in files:
            if not relative.isascii():
                raise ValueError("Outer ZIP names must support the Win7 built-in extractor")
            target.write(str(source), relative)
    if output.stat().st_size >= maximum:
        raise ValueError("ZIP reaches or exceeds the byte limit: " + str(output))
    with zipfile.ZipFile(str(output)) as target:
        if target.testzip():
            raise ValueError("ZIP integrity failure")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("volumes", type=Path)
    parser.add_argument("sevenzip", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--name", default="APS_Win7_x64_20260928")
    parser.add_argument("--maximum-bytes", type=int, default=80_000_000)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    bootstrap = args.output / "bootstrap"
    (bootstrap / "tools").mkdir(parents=True)
    (bootstrap / "payload").mkdir()
    files = payload_files(args.payload)
    csv_file(bootstrap / "files.csv", [record(file, file.relative_to(args.payload).as_posix()) for file in files])
    for name in ("Install.cmd", "Install.ps1"):
        text = (REPO / "packaging/win7" / name).read_text(encoding="ascii")
        (bootstrap / name).write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    shutil.copyfile(str(args.sevenzip / "x64/7za.exe"), str(bootstrap / "tools/7za.exe"))
    for name in ("License.txt", "readme.txt"):
        shutil.copyfile(str(args.sevenzip / name), str(bootstrap / "tools" / name))
    volumes = sorted(args.volumes.glob("APS_Portable.7z.*"))
    if not volumes or [file.suffix for file in volumes] != [f".{i + 1:03d}" for i in range(len(volumes))]:
        raise ValueError("Missing or non-contiguous payload volumes")
    rows, outputs = [], []
    for index, volume in enumerate(volumes, 1):
        relative = "payload/" + volume.name
        row = dict(record(volume, relative), Zip="", ZipSHA256="", ZipBytes="")
        if index == 1:
            shutil.copyfile(str(volume), str(bootstrap / relative))
        else:
            output = args.output / (args.name + f"_{index:02d}.zip")
            archive(output, [(volume, relative)], args.maximum_bytes)
            row.update(Zip=output.name, ZipSHA256=digest(output), ZipBytes=output.stat().st_size)
            outputs.append(output)
        rows.append(row)
    csv_file(bootstrap / "parts.csv", rows)
    readme = """APS 排产系统 · Win7 x64 离线交付包 · 2026-09-28

使用步骤（无需另装解压软件）：
1. 把全部编号 ZIP 保存到同一个本机文件夹，保持文件名不变。
2. 只需用 Windows 自带“全部提取”解压 01.zip。
3. 在解压出的文件夹内双击 Install.cmd。它会自动找到旁边的后续 ZIP，校验并完整解压。
   也可以先把全部 ZIP 解压到同一文件夹，再运行 Install.cmd。
4. 完成后双击 Application\\Start.cmd；或进入 Application\\APS_Portable，双击启动_排产系统_Chrome.bat。

目标为 Windows 7 SP1 64 位。主程序、Python 3.8 运行时、VC/UCRT DLL、Chrome109、
中文和英文浏览器资源、Excel 读写依赖、静态页面、字体及解压工具均已包含。
解压脚本支持 Win7 自带 PowerShell 2.0，不要求安装 Python、浏览器、7-Zip 或联网下载。
请完整下载全部 ZIP；任何文件缺失或校验失败都会停止，不会覆盖旧程序或旧数据。
请留出至少 1 GB 可用空间，放在当前账户可读写的本机目录，不要直接在 ZIP 内运行。

数据和升级：
首次启动建立空库，业务数据位于 Application\\APS_Portable\\user-data。
Excel 模板从各业务页的导入窗口下载，不要求目标机安装 Microsoft Office。
日常通过系统页面正常退出；备份从系统维护页面操作。
升级时先在旧系统备份并正常退出，把新包部署到新的空目录，再复制旧 user-data，
或通过新系统的备份恢复功能导入。不要在运行中复制数据库，也不要覆盖原程序目录。
迁移时正常退出后复制整个 APS_Portable 文件夹。专用浏览器用于本机 APS 页面。
仅关闭浏览器窗口不代表后台服务已停止；再次启动会复用健康的本机实例。

本包程序与 2026-09-27 已完成 Win7 验收的 d1307cb8 完全相同，后续主分支改动为测试和文档。
验收覆盖 Excel、批次三模式和关联保护、报工、完整试调及重启保存回读。
已知观察：自动化中出现过字体等待，以及一次尺寸/主题切换截图留白，后续稳定帧未复现。
遇到启动问题，保留 user-data\\logs\\launcher.log 和 aps_launch_error.txt 联系交付人员。
请不要删除运行锁来强行启动多个实例，也不要在同一份数据上同时运行多个用户。

本交付附带未修改的 7-Zip 26.03 独立解压工具。许可及说明在 tools 目录，
GNU LGPL 许可说明、对应源码与官方下载：https://www.7-zip.org/ 。
对应源码版本：https://github.com/ip7z/7zip/releases/tag/26.03 。
"""
    (bootstrap / "README.txt").write_text(readme, encoding="utf-8-sig")
    support = [file for file in bootstrap.rglob("*") if file.is_file()
               and file.name != "support.csv" and "payload" not in file.relative_to(bootstrap).parts]
    csv_file(bootstrap / "support.csv", [record(file, file.relative_to(bootstrap).as_posix()) for file in sorted(support)])
    first = args.output / (args.name + "_01.zip")
    archive(first, [(file, file.relative_to(bootstrap).as_posix()) for file in sorted(bootstrap.rglob("*"))
                    if file.is_file()], args.maximum_bytes)
    outputs.insert(0, first)
    checks = [record(file, file.name) for file in outputs]
    (args.output / "SHA256SUMS.txt").write_text("".join(row["SHA256"] + "  " + row["Path"] + "\n" for row in checks), encoding="ascii")
    (args.output / "README.txt").write_text(readme, encoding="utf-8-sig")
    (args.output / "delivery.json").write_text(json.dumps({"maximum_bytes_exclusive": args.maximum_bytes,
        "original_payload_files": len(files), "original_payload_bytes": sum(file.stat().st_size for file in files),
        "archives": checks, "sevenzip_exe_sha256": digest(bootstrap / "tools/7za.exe")}, indent=2), encoding="utf-8")
    print(json.dumps(checks))


if __name__ == "__main__":
    main()
