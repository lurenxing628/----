"""Small real managed-HTTP contract; the 5000 timing command stays Main-owned."""

from tests.workbench.final_capacity_probe import run_managed


def test_dense_200_full_candidates_persist_and_survive_managed_restart(tmp_path):
    result = run_managed(tmp_path / "dense-managed-200", batches=100, operations=2)
    assert result["complete"] is True and result["formal_capacity_passed"] is False
    assert result["persistence"]["operation_count"] == 200
    assert result["persistence"]["all_persisted_tasks"] == 800
    assert [row["task_count"] for row in result["persistence"]["candidates"]] == [200] * 4
    assert len(result["workspaces"]) == len(result["restart_workspaces"]) == 4
    assert result["admission"]["running_reads"]
    assert result["restart_retention"]["all_old_rows_preserved"]
    assert result["restart_retention"]["get_requests_zero_writes"]
    assert result["loaded_source_hashes_unchanged_across_restart"]
    assert result["shutdown"]["returncode"] == result["restart_shutdown"]["returncode"] == 0
    assert result["persistence"]["candidate_payloads_sha256"] == "72edcfc767a042d54ba4afb17222643beff1a94541e015bd14f7b9199f04c9b0"
