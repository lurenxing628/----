"""Preview and confirm exact shipment intent using the shared receipt transaction."""

import getpass
from typing import cast

from core.models.workbench_command import WorkbenchCommandOutcome
from core.models.workbench_outsourcing import reject
from core.models.workbench_outsourcing_input import normalize_input, prepare_values
from core.services.workbench.commands import WorkbenchCommandService

from .projection import execution_boundary, values
from .service import WorkbenchOutsourcingService


class WorkbenchOutsourcingCommandService:
    def __init__(self, conn, *, clock=None, actor_provider=None, context_factory=None):
        self.reader = WorkbenchOutsourcingService(conn, clock=clock)
        self.commands = WorkbenchCommandService(conn)
        self.actor_provider = actor_provider or getpass.getuser
        self.context_factory = context_factory

    def _prepare(self, payload):
        repo, ref = self.reader.repo, payload.get("outsourcing_ref")
        previous, header = None, None
        if ref is not None:
            header = self.reader.header(ref)
            previous = self.reader.latest(ref)
        target = header["target"] if header else payload["target"]
        sources = self.reader.sources.capture([target], include_routes=header is None)
        source = sources.load(target, new_registration=header is None)
        if header and source["identity"] != header["identity"]:
            reject("原登记的工序或所属批次已变化，请刷新后重新登记。", "identity_drift", 409)
        memberships = repo.membership(target["operation_refs"])
        if header is None and memberships:
            reject("这些工序已经有外协登记了；请打开原来的登记修改，不要重复登记或换组。", "constraint_conflict", 409)
        before = values(previous) if previous else None
        prepared_values = prepare_values(before, payload, self.reader.now())
        after = prepared_values.values
        snapshot = {"input": payload, "source": source["facts"],
                    "memberships": memberships, "header": header, "latest_fact_ref": previous["fact_ref"] if previous else None}
        return {"ref": ref, "target": target, "source": source, "previous": previous, "before": before, "after": after,
                "input": payload, "snapshot": snapshot, "subject": ref or target["batch_ref"], "values": prepared_values}

    def preview(self, payload):
        normalized = normalize_input(payload)
        with self.reader.read_snapshot():
            prepared = self._prepare(normalized)
            result = {"outsourcing_ref": prepared["ref"], "target": prepared["source"]["public"],
                      "before": prepared["before"], "after": prepared["after"], "input": normalized,
                      "can_confirm": True, "execution": execution_boundary(prepared["target"]), "write_context": None}
            if self.context_factory:
                result["write_context"] = self.context_factory(prepared["subject"], ["confirm"], prepared["snapshot"])
            return result

    def execute(self, payload, *, request_key, validate_context):
        normalized = normalize_input(payload)
        subject = (normalized["outsourcing_ref"] if "outsourcing_ref" in normalized
                   else cast(dict, normalized["target"])["batch_ref"])
        if type(subject) is not str:
            raise RuntimeError("Validated outsourcing subject must be a permanent text reference")

        def guard():
            self.reader.require_schema()
            prepared = self._prepare(normalized)
            validate_context(subject, "confirm", prepared["snapshot"])
            actor = self.actor_provider()
            if type(actor) is not str or not actor.strip() or "\x00" in actor or len(actor) > 200:
                raise RuntimeError("Actual local application operator is required")
            prepared["actor"] = actor.strip()
            return prepared

        def mutate(prepared):
            now = self.reader.now()
            # Revalidate at the actual recording time; never store preview's clock.
            prepared["values"].check_recording_time(now)
            refs = self.reader.repo.append(prepared, request_key=request_key, local_operator=prepared["actor"],
                                           now=now.isoformat(timespec="seconds"))
            return WorkbenchCommandOutcome("committed", {**refs, **prepared["after"],
                "target": prepared["source"]["public"], "declared_operator": normalized["declared_operator"],
                "local_operator": prepared["actor"], "reason": normalized["reason"],
                "confirmed_at": now.isoformat(timespec="seconds"), "refresh_required": True,
                "execution": execution_boundary(prepared["target"])})

        return self.commands.execute(request_key=request_key, action="outsourcing.confirm", context_ref=subject,
                                     normalized_input=normalized, guard=guard, mutate=mutate)
