"""Hash every product input and watch for source mutations during a Main window."""

import hashlib
import threading
import time

from tests.workbench.live_environment import REPO, write_json


def product_paths(repo=REPO):
    paths = set(repo.glob("*.py")) | {repo / "schema.sql"}
    for name in ("core", "data", "web", "plugins"):
        paths.update(path for path in (repo / name).rglob("*") if path.is_file() and path.suffix in (".py", ".sql", ".json"))
    for name in ("frontend/workbench", "templates/workbench"):
        paths.update(path for path in (repo / name).rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    return sorted(paths)


def source_hashes(repo=REPO):
    return {str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest() for path in product_paths(repo)}


def source_metadata(repo=REPO):
    result = {}
    for path in product_paths(repo):
        stat = path.stat()
        result[str(path.relative_to(repo))] = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return result


class ProductSourceFreeze:
    def __init__(self, output, *, repo=REPO):
        self.repo, self.output = repo, output
        metadata_before = source_metadata(repo)
        self.before = source_hashes(repo)
        self.metadata = source_metadata(repo)
        if metadata_before != self.metadata:
            raise RuntimeError("Product inputs changed while taking the source freeze")
        self.failure = None
        self.checks = 0
        self.seconds = 0.0
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.watch, name="capacity-source-observer", daemon=True)
        write_json(output / "product-inputs-before.json", self.before)

    def start(self):
        self.thread.start()

    def watch(self):
        while not self.stop_event.wait(1.0):
            started = time.monotonic()
            try:
                current = source_metadata(self.repo)
                if current != self.metadata:
                    self.failure = {"code": "product_input_metadata_changed",
                                    "paths": sorted(name for name in set(current) | set(self.metadata)
                                                    if current.get(name) != self.metadata.get(name))}
                    return
                self.checks += 1
            except Exception as exc:
                self.failure = {"code": "product_input_observation_failed", "type": type(exc).__name__, "message": str(exc)}
                return
            finally:
                self.seconds += time.monotonic() - started

    def finish(self):
        self.stop_event.set()
        self.thread.join()
        after = source_hashes(self.repo)
        metadata_after = source_metadata(self.repo)
        if metadata_after != self.metadata and self.failure is None:
            self.failure = {"code": "product_input_metadata_changed_before_exit",
                            "paths": sorted(name for name in set(metadata_after) | set(self.metadata)
                                            if metadata_after.get(name) != self.metadata.get(name))}
        write_json(self.output / "product-inputs-after.json", after)
        differences = sorted(name for name in set(self.before) | set(after) if self.before.get(name) != after.get(name))
        proof = {"file_count": len(self.before), "before_sha256": hashlib.sha256(
                 (self.output / "product-inputs-before.json").read_bytes()).hexdigest(),
                 "after_sha256": hashlib.sha256((self.output / "product-inputs-after.json").read_bytes()).hexdigest(),
                 "differences": differences, "watch_failure": self.failure, "metadata_checks": self.checks,
                 "observer_seconds": self.seconds, "unchanged": not differences and self.failure is None,
                 "scope": "all root Python, core/data/web/plugins Python/SQL/JSON, frontend/workbench and templates/workbench"}
        write_json(self.output / "product-input-proof.json", proof)
        return proof
