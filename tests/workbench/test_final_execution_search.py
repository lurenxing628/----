"""Every advertised field-search dimension matches actual displayed business facts."""

from tests.workbench.final_execution_cases import EXECUTION
from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_cases import final_execution_host as final_execution_host
from tests.workbench.final_execution_seed import execution
from tests.workbench.live_environment import write_json
from tests.workbench.report_execution_ledger_support import report_ledger_api as report_ledger_api
from tests.workbench.run_live_server_support import database_state


def check_search(read, state, output):
    before = state()
    original = read({"size": 100})
    summary = original['data']['summary']
    assert summary['state_counts'] == {'unreported': 29, 'started': 1, 'partial': 1, 'paused': 1, 'exception': 0, 'complete': 1}
    assert summary['effective_processing_hours'] is None and summary['known_effective_processing_hours'] == 3
    assert summary['unknown_hour_reports'] == 1
    for state_name, expected in summary['state_counts'].items():
        scoped = read({'size': 10, 'state': state_name})['data']
        assert scoped['page']['total'] == expected
        assert scoped['summary']['state_counts'] == summary['state_counts']
        assert scoped['summary']['state_scope_tasks'] == 33
    cases = [("B1", 33), ("Part", 33), ("30 Turning", 1), ("中文车床", 33), ("中文人员", 33)]
    report = next(row for task in original["data"]["tasks"] for row in task["execution"]["reports"])
    cases.append((report["report_no"], 1))
    observations = []
    for query, expected in cases:
        result = read({"size": 100, "query": query})
        observations.append({"query": query, "expected": expected, "actual": result["data"]["page"]["total"],
                             "task_refs": [row["task_ref"] for row in result["data"]["tasks"]]})
    write_json(output, {"cases": observations, "strict_changed_tables": [],
        "no_writes": state() == before, "plan_ref": original["data"]["plan"]["plan_ref"]})
    assert state() == before
    assert all(row["actual"] == row["expected"] for row in observations), observations


def test_full_factory_search_batch_part_operation_planned_actual_resources_and_report_number(final_execution_host):
    host = final_execution_host
    check_search(lambda query: host.json(EXECUTION + "/tasks", query=query), host.state, host.root / "final-search-proof.json")


def test_factory_client_search_contract_without_frontend_build_dependency(report_ledger_api, tmp_path):
    api = report_ledger_api
    execution(api)

    def read(query):
        response = api.client.get(EXECUTION + "/tasks", query_string=query)
        assert response.status_code == 200
        return response.get_json()

    check_search(read, lambda: database_state(api.path), tmp_path / "factory-client-search-proof.json")
