"""门禁：说明书第 1 章的列说明必须和 12 张表的表描述一致。

用户文档和文件里的「填写说明」表讲的是同一件事。如果文档是人手抄的，改一列就要在两处改，
迟早对不上。所以列说明由 tools.generate_table_docs 从表描述生成，这里只负责比对。
散文段落仍然人工撰写，不进这个门禁。
"""

import subprocess
import sys

from core.models.workbench_table_catalog import TABLE_IDS
from tests._support.paths import REPO_ROOT_STR
from tools.generate_table_docs import BEGIN, END, MANUAL, render


def _manual_text():
    return MANUAL.read_text(encoding="utf-8")


def test_manual_table_docs_match_the_descriptors():
    text = _manual_text()
    assert render(text) == text, (
        "说明书里的列说明和表描述对不上。请跑：python3 -m tools.generate_table_docs --write")


def test_check_mode_exits_zero_on_the_committed_manual():
    """门禁真正跑的是这条命令，所以这里按子进程验一次退出码，不只验函数。"""
    result = subprocess.run([sys.executable, "-m", "tools.generate_table_docs", "--check"],
                            cwd=REPO_ROOT_STR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode == 0, result.stdout.decode("utf-8", "replace")


def test_every_registered_table_has_a_region_in_the_manual():
    """新增一张能导入的表就必须在说明书里开一节，不能只进目录不进文档。"""
    text = _manual_text()
    marked = {line[len(BEGIN):].split("-->")[0].strip()
              for line in text.split("\n") if line.startswith(BEGIN)}
    assert marked == {"overview", *TABLE_IDS}


def test_regions_are_closed_and_not_hand_edited():
    text = _manual_text()
    opens = [line for line in text.split("\n") if line.startswith(BEGIN)]
    closes = [line for line in text.split("\n") if line.strip() == END]
    assert len(opens) == len(closes) == len(TABLE_IDS) + 1
    assert text.count("由 python3 -m tools.generate_table_docs --write 生成") == len(opens)
