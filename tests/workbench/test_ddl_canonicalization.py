"""DDL 文本规范化合同：列序不比较、注释只在引号外才被去掉、物理列序另有专用读法。"""

from core.infrastructure.workbench_metadata_schema import _canonical_sql, canonical_ddl_parts

BASE = "CREATE TABLE IF NOT EXISTS t (\n  a TEXT NOT NULL, -- 说明\n  b INTEGER DEFAULT 0,\n  UNIQUE(a, b)\n);"


def test_column_order_is_not_part_of_the_contract():
    reordered = "CREATE TABLE t (b INTEGER DEFAULT 0, UNIQUE(a,b), a TEXT NOT NULL)"
    assert _canonical_sql(BASE) == _canonical_sql(reordered)
    assert _canonical_sql(BASE) != _canonical_sql("CREATE TABLE t (a TEXT, b INTEGER DEFAULT 0, UNIQUE(a,b))")


def test_line_comment_inside_quotes_is_a_literal_not_a_comment():
    quoted = "CREATE TABLE t (a TEXT DEFAULT '--', b TEXT DEFAULT \"x--y\", c TEXT) -- 尾注"
    assert _canonical_sql(quoted) == "CREATE TABLE t(a TEXT DEFAULT '--',b TEXT DEFAULT \"x--y\",c TEXT)"
    assert _canonical_sql("SELECT '--keep' -- drop\n FROM t") == "SELECT '--keep' FROM t"


def test_canonical_ddl_parts_keep_the_physical_order_and_ignore_non_tables():
    assert canonical_ddl_parts("CREATE TABLE t (b INT, a TEXT DEFAULT '--x', UNIQUE(a,b))") == [
        "b INT", "a TEXT DEFAULT '--x'", "UNIQUE(a,b)"]
    assert canonical_ddl_parts("CREATE INDEX i ON t(a)") == []
