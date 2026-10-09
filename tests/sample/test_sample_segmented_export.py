"""Real scoped HTTP exports keep each snapshot and all overlapping task facts."""

from datetime import datetime, timedelta

from tests.sample.test_sample_exercise import sample_runtime as sample_runtime  # noqa: F401
from web.bootstrap.sample_exercise import _exports, _query, _run
from web.bootstrap.sample_formal_read import _assembled
from web.bootstrap.sample_http import BASE, SampleClient, SampleProgress
from web.bootstrap.sample_injection import inject_sample


def _adopt(client, candidate):
    path = BASE + "/scheduling/candidates/" + candidate
    preview = client.post(path + "/adopt-preview", {})["data"]
    assert preview["validation"]["can_adopt"]
    return client.command(path + "/adopt", preview["write_context"],
        {"confirm": True, "reason": "独立分段文件验收", "declared_operator": "样例测试"})["data"]["official_plan"]["plan_ref"]


def _scoped_documents(client, plan_ref, expected):
    low = min(datetime.fromisoformat(row["start"]) for row in expected)
    high = max(datetime.fromisoformat(row["end"]) for row in expected) + timedelta(microseconds=1)
    # A real merged external task crosses the split, so both files include it.
    external = next(row for row in expected if row["source"] == "external")
    middle = datetime.fromisoformat(external["start"]) + (datetime.fromisoformat(external["end"]) - datetime.fromisoformat(external["start"])) / 2
    path = BASE + "/plans/" + plan_ref + "/workspace"
    documents = [client.document(_query(path, {"range_start": first.isoformat(), "range_end": last.isoformat()}))
                 for first, last in ((low, middle), (middle, high))]
    return _assembled(plan_ref, expected, documents, [], low, high)


def test_two_real_official_versions_export_scoped_csv_and_xlsx_exactly(sample_runtime, tmp_path):
    client = SampleClient(sample_runtime)
    seed = inject_sample(sample_runtime, tmp_path / "seed.json", batch_count=2, operation_count=8)
    progress = SampleProgress(None, client)
    artifacts = []
    for version in (1, 2):
        run = _run(client, seed, progress, "scoped-exports-v" + str(version))
        plan_ref = _adopt(client, run["candidate_ref"])
        artifacts.append((plan_ref, run["workspace"]["data"]["tasks"]))
    for version, (plan_ref, expected) in enumerate(artifacts, 1):
        document = _scoped_documents(client, plan_ref, expected)
        assert document["meta"]["snapshot_ref"] is None
        assert document["assembly"]["unique_task_count"] == 16
        assert document["assembly"]["duplicate_overlap_count"] >= 2
        result = _exports(client, document, BASE + "/plans/" + plan_ref, tmp_path / "downloads", "plan-v" + str(version))
        assert result["mode"] == "segmented_http"
        assert result["unique_task_count"] == 16
        assert result["physical_rows"] == 16 + result["duplicate_overlap_rows"]
        for fmt in ("csv", "xlsx"):
            assert result[fmt]["rows"] == 16 and result[fmt]["single_full_scope_file"] is False
            assert result[fmt]["physical_rows"] == result["physical_rows"]
            assert len(result[fmt]["files"]) == 2
        for row in result["segments"]:
            assert row["snapshot_ref"] and row["scope"]["range_start"] < row["scope"]["range_end"]
            assert row["csv"]["all_columns_match_real_scope"] and row["xlsx"]["all_columns_match_real_scope"]
