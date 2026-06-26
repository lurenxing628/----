"""Loaders for vendored external scheduling benchmarks with published optima.

These feed the optimizer proof harness with *external* reference instances. They
live under ``tests/`` (not ``core/``) because they are evaluation scaffolding,
not production scheduling code -- the same convention as ``benchmark_fjsp.py``.

Sources (vendored under ``tests/_data/optimizer_benchmarks/``):
- SMTWT: OR-Library single-machine total weighted tardiness (Beasley), ``wt40``/
  ``wt50`` instances + ``wtopt`` optimal/best-known objective values
  (Crauwels/Potts/Van Wassenhove report 124/125 for n=40 and 115/125 for n=50 as
  proven optimal; this repo does not re-verify that external claim, and these
  weighted values are not used for any grading here).
- JSP: classic job-shop instances (Fisher-Thompson ``ft``, Lawrence ``la``) whose
  makespan optima are proven (LB=UB).

Comparability caveat (read before using for proof, see roadmap 4.2 / 102 / 274):
- JSP optima are *makespan* -> only ``folded_not_comparable`` references for the
  APS ``min_overdue`` objective.
- SMTWT optima are *weighted* tardiness with free integer weights w(j) in [1,10].
  APS weighted tardiness uses 3 discrete priority classes
  (critical=3/urgent=2/normal=1), so weighted SMTWT optima are NOT objective
  comparable. The weight-independent component ``overdue_count`` (number of tardy
  jobs) IS comparable and has an exact polynomial optimum via Moore-Hodgson
  (:func:`moore_hodgson_min_tardy`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from tests._support.paths import REPO_ROOT

BENCHMARK_DATA_DIR = REPO_ROOT / "tests" / "_data" / "optimizer_benchmarks"

# Proven optimal makespans (LB=UB) from JSPLib / JobShopLib metadata.
JSP_PROVEN_OPTIMUM: Dict[str, int] = {
    "ft06": 55,
    "ft10": 930,
    "ft20": 1165,
    "la01": 666,
    "la02": 655,
    "la03": 597,
    "la04": 590,
    "la05": 593,
}


@dataclass(frozen=True)
class SmtwtInstance:
    """One single-machine total weighted tardiness instance."""

    name: str
    processing_times: Tuple[int, ...]
    weights: Tuple[int, ...]
    due_dates: Tuple[int, ...]

    @property
    def num_jobs(self) -> int:
        return len(self.processing_times)


@dataclass(frozen=True)
class JspInstance:
    """One job-shop instance: jobs[j] = ordered list of (machine_index, duration)."""

    name: str
    num_jobs: int
    num_machines: int
    jobs: Tuple[Tuple[Tuple[int, int], ...], ...]


@dataclass(frozen=True)
class RcpspInstance:
    """One single-mode RCPSP instance (PSPLIB ``.sm``), 1-indexed jobs incl. source/sink.

    Renewable-resource *pools* (capacities) do not fold into the single-capacity
    APS machine/operator model, so these are not run through APS -- they serve as
    a parsed instance + published-optimum reference + critical-path lower bound.
    """

    name: str
    num_jobs: int  # incl. supersource(1) and sink(num_jobs)
    durations: Tuple[int, ...]  # index 0 == job 1
    successors: Tuple[Tuple[int, ...], ...]  # successors[j-1] = forward edges of job j
    demands: Tuple[Tuple[int, ...], ...]  # demands[j-1] = per-resource request
    capacities: Tuple[int, ...]


def _read_ints(path: Path) -> List[int]:
    if not path.exists():
        raise FileNotFoundError(f"benchmark data file missing: {path}")
    tokens = path.read_text(encoding="utf-8").split()
    out: List[int] = []
    for token in tokens:
        try:
            out.append(int(token))
        except ValueError as exc:
            raise ValueError(f"non-integer token {token!r} in {path.name}") from exc
    return out


def load_smtwt_instances(size: int) -> List[SmtwtInstance]:
    """Load all 125 SMTWT instances of the given job size (40 or 50)."""
    path = BENCHMARK_DATA_DIR / "smtwt" / f"wt{int(size)}.txt"
    flat = _read_ints(path)
    block = 3 * int(size)
    if len(flat) % block != 0:
        raise ValueError(
            f"wt{size} length {len(flat)} is not a multiple of 3*{size}={block}"
        )
    count = len(flat) // block
    instances: List[SmtwtInstance] = []
    for idx in range(count):
        chunk = flat[idx * block : (idx + 1) * block]
        n = int(size)
        instances.append(
            SmtwtInstance(
                name=f"wt{size}_{idx + 1}",
                processing_times=tuple(chunk[0:n]),
                weights=tuple(chunk[n : 2 * n]),
                due_dates=tuple(chunk[2 * n : 3 * n]),
            )
        )
    return instances


def load_smtwt_optima(size: int) -> List[int]:
    """Load published optimal/best-known weighted-tardiness values (1-indexed order)."""
    path = BENCHMARK_DATA_DIR / "smtwt" / f"wtopt{int(size)}.txt"
    values = _read_ints(path)
    if not values:
        raise ValueError(f"no optimum values parsed from {path.name}")
    return values


def load_jsp_instance(name: str) -> JspInstance:
    """Parse a classic job-shop instance file (``# comment`` lines ignored)."""
    path = BENCHMARK_DATA_DIR / "jsp" / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"JSP instance file missing: {path}")
    data_lines = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    if not data_lines:
        raise ValueError(f"{name}: no data lines")
    header = data_lines[0].split()
    num_jobs, num_machines = int(header[0]), int(header[1])
    if len(data_lines) - 1 < num_jobs:
        raise ValueError(f"{name}: expected {num_jobs} job rows, found {len(data_lines) - 1}")
    jobs: List[Tuple[Tuple[int, int], ...]] = []
    for j in range(num_jobs):
        tokens = [int(t) for t in data_lines[1 + j].split()]
        if len(tokens) != 2 * num_machines:
            raise ValueError(
                f"{name}: job {j + 1} has {len(tokens)} tokens, expected {2 * num_machines}"
            )
        ops = tuple((tokens[2 * k], tokens[2 * k + 1]) for k in range(num_machines))
        for machine_idx, duration in ops:
            if machine_idx < 0 or machine_idx >= num_machines:
                raise ValueError(f"{name}: machine index {machine_idx} out of range")
            if duration <= 0:
                raise ValueError(f"{name}: non-positive duration {duration}")
        jobs.append(ops)
    return JspInstance(name=name, num_jobs=num_jobs, num_machines=num_machines, jobs=tuple(jobs))


def _find_marker(lines: List[str], marker: str) -> int:
    for idx, line in enumerate(lines):
        if line.strip().startswith(marker):
            return idx
    raise ValueError(f"marker {marker!r} not found")


def load_rcpsp_instance(name: str) -> RcpspInstance:
    """Parse a PSPLIB single-mode ``.sm`` instance (renewable resources only)."""
    path = BENCHMARK_DATA_DIR / "rcpsp" / f"{name}.sm"
    if not path.exists():
        raise FileNotFoundError(f"RCPSP instance file missing: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    num_jobs = next(int(line.split(":")[1]) for line in lines if line.strip().startswith("jobs (incl"))
    num_renewable = next(
        int(line.split(":")[1].split()[0]) for line in lines if line.strip().startswith("- renewable")
    )

    prec_start = _find_marker(lines, "PRECEDENCE RELATIONS:") + 2
    successors: List[Tuple[int, ...]] = []
    for offset, row in enumerate(lines[prec_start : prec_start + num_jobs]):
        toks = [int(t) for t in row.split()]
        if toks[0] != offset + 1:
            raise ValueError(f"{name}: precedence row {offset + 1} misaligned (jobnr={toks[0]})")
        n_succ = toks[2]
        if len(toks) != 3 + n_succ:
            raise ValueError(f"{name}: job {toks[0]} lists {len(toks) - 3} successors, declared {n_succ}")
        successors.append(tuple(toks[3:]))

    req_start = _find_marker(lines, "REQUESTS/DURATIONS:") + 3
    durations: List[int] = []
    demands: List[Tuple[int, ...]] = []
    for offset, row in enumerate(lines[req_start : req_start + num_jobs]):
        toks = [int(t) for t in row.split()]
        # jobnr mode duration + one request per renewable resource -> offset error fails loud.
        if len(toks) != 3 + num_renewable or toks[0] != offset + 1:
            raise ValueError(f"{name}: requests row {offset + 1} misaligned/wrong width: {row!r}")
        durations.append(toks[2])
        demands.append(tuple(toks[3:]))

    avail_start = _find_marker(lines, "RESOURCEAVAILABILITIES:") + 2
    capacities = tuple(int(t) for t in lines[avail_start].split())
    if len(capacities) != num_renewable:
        raise ValueError(f"{name}: {len(capacities)} capacities for {num_renewable} renewable resources")

    if not (len(successors) == len(durations) == len(demands) == num_jobs):
        raise ValueError(f"{name}: parsed row counts disagree with num_jobs={num_jobs}")
    return RcpspInstance(
        name=name,
        num_jobs=num_jobs,
        durations=tuple(durations),
        successors=tuple(successors),
        demands=tuple(demands),
        capacities=capacities,
    )


def load_rcpsp_optima() -> Dict[Tuple[int, int], int]:
    """Parse ``j30opt.sm`` into {(parameter, instance): optimal_makespan}."""
    path = BENCHMARK_DATA_DIR / "rcpsp" / "j30opt.sm.txt"
    if not path.exists():
        raise FileNotFoundError(f"RCPSP optima file missing: {path}")
    optima: Dict[Tuple[int, int], int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        toks = line.split()
        if len(toks) >= 3 and all(_is_int(t) for t in toks[:3]):
            param, inst, makespan = int(toks[0]), int(toks[1]), int(toks[2])
            optima[(param, inst)] = makespan
    if not optima:
        raise ValueError("no optima rows parsed from j30opt.sm")
    return optima


def _is_int(token: str) -> bool:
    try:
        int(token)
        return True
    except ValueError:
        return False


def rcpsp_critical_path_lower_bound(instance: RcpspInstance) -> int:
    """Longest duration-weighted path through the precedence DAG.

    Resources only add constraints, so this is a valid lower bound on the optimal
    makespan -- a parser sanity check that must never exceed the published optimum.
    """
    n = instance.num_jobs
    # finish[j] accumulates the max predecessor finish (= earliest start of j) as we
    # relax forward edges; PSPLIB jobs are numbered so every edge goes low -> high,
    # so a single ascending pass is a valid topological order.
    finish = [0] * (n + 1)  # 1-indexed
    for job in range(1, n + 1):
        finish[job] += instance.durations[job - 1]
        for succ in instance.successors[job - 1]:
            finish[succ] = max(finish[succ], finish[job])
    return max(finish)


def moore_hodgson_min_tardy(processing_times: Sequence[int], due_dates: Sequence[int]) -> int:
    """Exact minimum number of tardy jobs for 1||sum U_j (Moore-Hodgson, 1968).

    All jobs ready at time 0 on a single machine. Returns the provably minimal
    count of jobs that must finish after their due date. O(n log n).
    """
    if len(processing_times) != len(due_dates):
        raise ValueError("processing_times and due_dates length mismatch")
    order = sorted(range(len(processing_times)), key=lambda i: int(due_dates[i]))
    scheduled: List[int] = []  # processing times of on-time jobs, kept as a list
    clock = 0
    for i in order:
        p = int(processing_times[i])
        scheduled.append(p)
        clock += p
        if clock > int(due_dates[i]):
            longest = max(scheduled)
            scheduled.remove(longest)
            clock -= longest
    return len(processing_times) - len(scheduled)
