"""Canonical operational measurement runner for portability candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import tempfile
from time import perf_counter_ns
from typing import Any

from application.services.workflow_portability.harness import (
    DeterministicClock,
    DeterministicEffectSink,
)
from application.services.workflow_portability.graph_state_adapter import (
    GraphStatePortabilityAdapter,
    GraphStatePortabilityAdapterFactory,
)
from application.services.workflow_portability.durable_history_adapter import (
    DurableHistoryPortabilityAdapter,
    DurableHistoryPortabilityAdapterFactory,
)
from application.services.workflow_portability.internal_kernel import (
    InternalKernelAdapter,
)
from application.services.workflow_portability.sqlite_adapter import (
    SQLitePortabilityAdapter,
    SQLitePortabilityAdapterFactory,
)
from domain.workflow.portability import (
    PORTABILITY_CONTRACT_VERSION,
    PortabilityCommand,
    PortabilityEdgeDefinition,
    PortabilityGraphRevision,
    PortabilityJoinDefinition,
    PortabilityJoinPolicy,
    PortabilityOperation,
    PortabilityTaskDefinition,
    PortabilityTaskOutcome,
)


MEASUREMENT_SCHEMA_VERSION = "workflow-portability-measurements.v4"
_PAYLOAD_HASH = hashlib.sha256(b"portability measurement effect").hexdigest()
_IMPLEMENTATION_MODULES = {
    "internal": ("application/services/workflow_portability/internal_kernel.py",),
    "sqlite": ("application/services/workflow_portability/sqlite_adapter.py",),
    "graph-state": (
        "domain/workflow/graph_state.py",
        "application/services/workflow_portability/graph_state_adapter.py",
    ),
    "durable-history": (
        "domain/workflow/durable_history.py",
        "application/services/workflow_portability/durable_history_adapter.py",
        "application/services/workflow_portability/sqlite_durable_history.py",
    ),
}


def run_portability_measurements(
    *, output_directory: str | Path, sample_count: int = 3
) -> dict[str, object]:
    if type(sample_count) is not int or sample_count < 1:
        raise ValueError("sample_count must be a positive integer")
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    run_directory = Path(tempfile.mkdtemp(prefix="run-", dir=directory))

    adapters = (
        _measure_adapter(
            adapter_id=InternalKernelAdapter.adapter_id,
            output_directory=run_directory,
            sample_count=sample_count,
            candidate_kind="internal",
        ),
        _measure_adapter(
            adapter_id=SQLitePortabilityAdapter.adapter_id,
            output_directory=run_directory,
            sample_count=sample_count,
            candidate_kind="sqlite",
        ),
        _measure_adapter(
            adapter_id=GraphStatePortabilityAdapter.adapter_id,
            output_directory=run_directory,
            sample_count=sample_count,
            candidate_kind="graph-state",
        ),
        _measure_adapter(
            adapter_id=DurableHistoryPortabilityAdapter.adapter_id,
            output_directory=run_directory,
            sample_count=sample_count,
            candidate_kind="durable-history",
        ),
    )
    return {
        "adapters": list(adapters),
        "environment": {
            "python_version": platform.python_version(),
            "sqlite_version": sqlite3.sqlite_version,
        },
        "measurement_schema_version": MEASUREMENT_SCHEMA_VERSION,
        "portability_contract_version": PORTABILITY_CONTRACT_VERSION,
        "sample_count": sample_count,
    }


def canonical_measurement_json(measurements: dict[str, object]) -> str:
    return json.dumps(
        measurements,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def measurements_passed(measurements: dict[str, object]) -> bool:
    adapters = measurements.get("adapters")
    if type(adapters) is not list:
        return False
    return bool(adapters) and all(
        type(adapter) is dict and adapter.get("all_scenarios_passed") is True
        for adapter in adapters
    )


def _measure_adapter(
    *,
    adapter_id: str,
    output_directory: Path,
    sample_count: int,
    candidate_kind: str,
) -> dict[str, object]:
    samples = [
        _measure_sample(
            adapter_id=adapter_id,
            output_directory=output_directory,
            sample_index=index,
            candidate_kind=candidate_kind,
        )
        for index in range(sample_count)
    ]
    return {
        "adapter_id": adapter_id,
        "all_scenarios_passed": all(sample["passed"] for sample in samples),
        "connection_settings": samples[0]["connection_settings"],
        "external_services": [],
        "implementation_modules": list(_IMPLEMENTATION_MODULES[candidate_kind]),
        "implementation_source_lines": _implementation_source_lines(candidate_kind),
        "required_packages": [],
        "samples": samples,
    }


def _measure_sample(
    *,
    adapter_id: str,
    output_directory: Path,
    sample_index: int,
    candidate_kind: str,
) -> dict[str, object]:
    tenant_id = f"tenant-measurement-{sample_index}"
    workflow_id = f"workflow-measurement-{sample_index}"
    database_path = output_directory / (
        f"{candidate_kind}-sample-{sample_index}.sqlite3"
    )
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory: Any
    if candidate_kind == "internal":
        factory = InternalKernelAdapter
    elif candidate_kind == "sqlite":
        factory = SQLitePortabilityAdapterFactory(database_path)
    elif candidate_kind == "graph-state":
        factory = GraphStatePortabilityAdapterFactory(database_path)
    elif candidate_kind == "durable-history":
        factory = DurableHistoryPortabilityAdapterFactory(database_path)
    else:
        raise ValueError("unsupported portability measurement candidate")
    persistent_candidate = candidate_kind != "internal"
    sample: dict[str, object] = {
        "cold_start_latency_ns": None,
        "connection_settings": {},
        "evidence_counts": None,
        "error_type": None,
        "history_hash": None,
        "graph_revision": None,
        "join_states": None,
        "passed": False,
        "persisted_database_bytes": 0,
        "recovery_latency_ns": None,
        "sample_index": sample_index,
        "scenario": "dynamic_join_effect_and_fresh_restore",
        "strategy_state_hash": None,
    }
    adapter = None
    restored = None
    try:
        started = perf_counter_ns()
        adapter = factory.create(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            graph_revision=1,
            clock=clock,
            effect_sink=sink,
        )
        sample["cold_start_latency_ns"] = perf_counter_ns() - started
        adapter.apply(
            _command(
                tenant_id,
                workflow_id,
                "command-start",
                PortabilityOperation.START_WORKFLOW,
            )
        )
        adapter.apply(
            _command(
                tenant_id,
                workflow_id,
                "command-expand",
                PortabilityOperation.COMMIT_GRAPH_REVISION,
                topology_revision=_measurement_topology(),
            )
        )
        adapter.apply(
            _command(
                tenant_id,
                workflow_id,
                "command-assign",
                PortabilityOperation.ASSIGN_ATTEMPT,
                graph_revision=2,
                task_id="task-a",
                attempt_id="attempt-a1",
                worker_id="worker-a",
                fencing_token=1,
                lease_expires_at_tick=10,
            )
        )
        adapter.apply(
            _command(
                tenant_id,
                workflow_id,
                "command-effect",
                PortabilityOperation.COMMIT_EFFECT,
                graph_revision=2,
                task_id="task-a",
                attempt_id="attempt-a1",
                worker_id="worker-a",
                fencing_token=1,
                effect_id="effect-a",
                payload_hash=_PAYLOAD_HASH,
            )
        )
        adapter.apply(
            _command(
                tenant_id,
                workflow_id,
                "command-outcome",
                PortabilityOperation.RECORD_TASK_OUTCOME,
                graph_revision=2,
                task_id="task-a",
                attempt_id="attempt-a1",
                worker_id="worker-a",
                fencing_token=1,
                task_outcome=PortabilityTaskOutcome.SUCCEEDED,
                result_hash=hashlib.sha256(b"measurement result").hexdigest(),
            )
        )
        adapter.apply(
            _command(
                tenant_id,
                workflow_id,
                "command-assign-join",
                PortabilityOperation.ASSIGN_ATTEMPT,
                graph_revision=2,
                task_id="task-join",
                attempt_id="attempt-join-1",
                worker_id="worker-join",
                fencing_token=1,
                lease_expires_at_tick=10,
            )
        )
        history = adapter.export_history()
        checkpoint = adapter.checkpoint()
        if persistent_candidate:
            adapter.close()
            adapter = None

        recovery_started = perf_counter_ns()
        restored = factory.restore(
            history=history,
            checkpoint=checkpoint,
            clock=clock,
            effect_sink=sink,
        )
        sample["recovery_latency_ns"] = perf_counter_ns() - recovery_started
        if restored.export_history() != history:
            raise RuntimeError("restored portable history changed")
        restored.apply(
            _command(
                tenant_id,
                workflow_id,
                "command-complete",
                PortabilityOperation.COMPLETE_WORKFLOW,
                graph_revision=2,
            )
        )
        final_checkpoint = restored.checkpoint()
        final_history = restored.export_history()
        sample["history_hash"] = final_checkpoint.history_hash
        sample["graph_revision"] = final_checkpoint.snapshot.graph_revision
        sample["join_states"] = [
            list(item) for item in final_checkpoint.snapshot.join_states
        ]
        graph_state = getattr(restored, "graph_state", None)
        if callable(graph_state):
            sample["strategy_state_hash"] = graph_state().state_hash
        durable_state = getattr(restored, "durable_history_state", None)
        if callable(durable_state):
            sample["strategy_state_hash"] = durable_state().state_hash
        if persistent_candidate:
            sample["connection_settings"] = restored.connection_settings
            sample["evidence_counts"] = restored.evidence_counts()
            restored.close()
            restored = None
            sample["persisted_database_bytes"] = _database_footprint(database_path)
        else:
            sample["evidence_counts"] = {
                "checkpoints": 2,
                "command_receipts": len(final_history.command_receipts),
                "commands": len(final_history.commands),
                "effect_receipts": len(final_history.effect_receipts),
                "events": len(final_history.events),
            }
        sample["passed"] = True
    except Exception as exc:  # measurement output must retain failed samples
        sample["error_type"] = type(exc).__name__
    finally:
        for candidate in (adapter, restored):
            close = getattr(candidate, "close", None)
            if callable(close):
                close()
    return sample


def _measurement_topology() -> PortabilityGraphRevision:
    return PortabilityGraphRevision(
        revision=2,
        parent_revision=1,
        tasks=(
            PortabilityTaskDefinition("task-a", "portable-task"),
            PortabilityTaskDefinition("task-join", "portable-task"),
        ),
        edges=(PortabilityEdgeDefinition("task-a", "task-join", "join-any"),),
        joins=(
            PortabilityJoinDefinition(
                "join-any", "task-join", PortabilityJoinPolicy.ANY
            ),
        ),
    )


def _command(
    tenant_id: str,
    workflow_id: str,
    command_id: str,
    operation: PortabilityOperation,
    **overrides: object,
) -> PortabilityCommand:
    values: dict[str, object] = {
        "command_id": command_id,
        "operation": operation,
        "tenant_id": tenant_id,
        "workflow_id": workflow_id,
    }
    values.update(overrides)
    return PortabilityCommand(**values)  # type: ignore[arg-type]


def _database_footprint(database_path: Path) -> int:
    return sum(
        candidate.stat().st_size
        for candidate in (
            database_path,
            Path(f"{database_path}-wal"),
            Path(f"{database_path}-shm"),
        )
        if candidate.exists()
    )


def _implementation_source_lines(candidate_kind: str) -> int:
    repository_root = Path(__file__).resolve().parents[3]
    return sum(
        len((repository_root / module).read_text(encoding="utf-8").splitlines())
        for module in _IMPLEMENTATION_MODULES[candidate_kind]
    )


__all__ = [
    "MEASUREMENT_SCHEMA_VERSION",
    "canonical_measurement_json",
    "measurements_passed",
    "run_portability_measurements",
]
