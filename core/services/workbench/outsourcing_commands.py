"""Preview and confirm exact shipment intent using the shared receipt transaction."""

import getpass

from core.models.workbench_command import WorkbenchCommandOutcome, input_fingerprint
from core.models.workbench_outsourcing import bounded, reference, reject
from core.models.workbench_outsourcing_input import next_values, normalize_input, target_input
from core.services.workbench.commands import WorkbenchCommandService

from .outsourcing import WorkbenchOutsourcingService
from .outsourcing_projection import execution_boundary, values


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
            header = repo.header(ref)
            previous = repo.latest(ref)
        target = header["target"] if header else payload["target"]
        source = self.reader.sources.load(target)
        if header and source["identity"] != header["identity"]:
            reject("原登记成员或所属对象发生漂移，不能把历史重新关联到当前同编号对象。", "identity_drift", 409)
        memberships = repo.membership(target["operation_refs"])
        if header is None and memberships:
            reject("成员已有外协登记；请打开原登记，不能重复建账或换组。", "constraint_conflict", 409)
        before = values(previous) if previous else None
        after = next_values(before, payload, self.reader.now())
        snapshot = {"input_hash": input_fingerprint(payload), "source": source["facts"],
                    "memberships": memberships, "header": header, "latest_fact_ref": previous["fact_ref"] if previous else None}
        return {"ref": ref, "target": target, "source": source, "previous": previous, "before": before, "after": after,
                "input": payload, "snapshot": bounded(snapshot), "subject": ref or target["batch_ref"]}

    def preview(self, payload):
        normalized = normalize_input(payload)
        with self.reader.read_snapshot():
            prepared = self._prepare(normalized)
            result = {"outsourcing_ref": prepared["ref"], "target": prepared["source"]["public"],
                      "before": prepared["before"], "after": prepared["after"], "input": normalized,
                      "can_confirm": True, "execution": execution_boundary(prepared["target"]), "write_context": None}
            if self.context_factory:
                result["write_context"] = self.context_factory(prepared["subject"], ["confirm"], prepared["snapshot"])
            return bounded(result)

    def execute(self, payload, *, request_key, validate_context):
        normalized = normalize_input(payload)
        self.reader.repo.require_schema()
        subject = (reference(normalized["outsourcing_ref"]) if "outsourcing_ref" in normalized
                   else target_input(normalized["target"])["batch_ref"])
        if type(subject) is not str:
            raise RuntimeError("Validated outsourcing subject must be a permanent text reference")

        def guard():
            self.reader.repo.require_schema()
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
            next_values(prepared["before"], normalized, now)
            refs = self.reader.repo.append(prepared, request_key=request_key, local_operator=prepared["actor"],
                                           now=now.isoformat(timespec="seconds"))
            return WorkbenchCommandOutcome("committed", bounded({**refs, **prepared["after"],
                "target": prepared["source"]["public"], "declared_operator": normalized["declared_operator"],
                "local_operator": prepared["actor"], "reason": normalized["reason"],
                "confirmed_at": now.isoformat(timespec="seconds"), "refresh_required": True,
                "execution": execution_boundary(prepared["target"])}))

        return self.commands.execute(request_key=request_key, action="outsourcing.confirm", context_ref=subject,
                                     normalized_input=normalized, guard=guard, mutate=mutate)
