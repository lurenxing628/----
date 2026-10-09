"""Only one first-time injector may create the existing progress record."""

import json
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from web.bootstrap.sample_http import SampleClient, SampleProgress


def _create_progress(output, gate, results, worker):
    gate.wait(timeout=15)
    try:
        SampleProgress(output, SampleClient("http://worker-" + str(worker)))
    except FileExistsError:
        result = ("exists", worker)
    except Exception as exc:
        result = (type(exc).__name__, worker)
    else:
        result = ("created", worker)
    if results is not None:
        results.put(result)
    return result


def _assert_single_creator(output, results):
    created = [worker for state, worker in results if state == "created"]
    assert len(created) == 1, "Both first-time injectors created/overwrote the progress record: " + repr(results)
    assert sum(state == "exists" for state, _ in results) == 1, results
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["base_url"] == "http://worker-" + str(created[0])
    assert report["state"] == "injecting"


def test_concurrent_threads_have_one_progress_creator(tmp_path):
    output = tmp_path / "thread" / "sample-acceptance.json"
    gate = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_create_progress, output, gate, None, worker) for worker in range(2)]
        results = [future.result(timeout=20) for future in futures]
    _assert_single_creator(output, results)


def test_concurrent_processes_have_one_progress_creator(tmp_path):
    output = tmp_path / "process" / "sample-acceptance.json"
    context = multiprocessing.get_context("spawn")
    gate, results = context.Barrier(2), context.Queue()
    processes = [context.Process(target=_create_progress, args=(output, gate, results, worker))
                 for worker in range(2)]
    try:
        for process in processes:
            process.start()
        outcomes = [results.get(timeout=20) for _ in processes]
        for process in processes:
            process.join(timeout=20)
            assert process.exitcode == 0
        _assert_single_creator(output, outcomes)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()
        results.join_thread()


def test_existing_injection_record_is_never_replaced_by_another_creator(tmp_path):
    output = tmp_path / "sample-acceptance.json"
    original = '{"state":"seeded","request_count":81,"committed":true,"note":"原记录"}'
    output.write_text(original, encoding="utf-8")
    with pytest.raises(FileExistsError):
        SampleProgress(output, SampleClient("http://loser"))
    assert output.read_text(encoding="utf-8") == original


def test_owner_can_save_steps_and_complete_on_the_same_report(tmp_path):
    output = tmp_path / "sample-acceptance.json"
    client = SampleClient("http://owner")
    progress = SampleProgress(output, client)
    client.request_count = 3
    assert progress.step("write", lambda: {"committed": True}) == {"committed": True}
    progress.report["state"] = "seeded"
    progress.save()
    progress.report["state"] = "complete"
    progress.save()
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["state"] == "complete" and saved["request_count"] == 3
    assert saved["steps"][0]["state"] == "complete"


def test_in_memory_progress_and_seeded_exercise_reuse_the_existing_record(tmp_path, monkeypatch):
    from web.bootstrap import sample_exercise

    output = tmp_path / "sample-acceptance.json"
    seed = {"state": "seeded", "steps": [], "request_count": 7, "elapsed_seconds": 1.0,
            "refs": {"batch": {"B": "batch-ref"}}}
    output.write_text(json.dumps(seed), encoding="utf-8")

    def exercise(client, selected_seed, progress):
        assert selected_seed is seed
        assert client.request_count == 7
        assert progress.output == output
        progress.report = dict(selected_seed, state="complete", exercise_state="complete")
        progress.save()
        return progress.report

    monkeypatch.setattr(sample_exercise, "exercise", exercise)
    result = sample_exercise.exercise_sample("http://existing", seed, output)
    assert result["state"] == "complete"
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["request_count"] == 7 and saved["elapsed_seconds"] >= 1.0
    in_memory = SampleProgress(None, SampleClient("http://memory"))
    in_memory.report["state"] = "seeded"
    in_memory.save()
    assert in_memory.output is None
