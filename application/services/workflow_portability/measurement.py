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
    PortabilityOperation,
)


MEASUREMENT_SCHEMA_VERSION = "workflow-portability-measurements.v1"
_PAYLOAD_HASH = hashlib.sha256(b"portability measurement effect").hexdigest()


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
            sqlite_candidate=False,
        ),
        _measure_adapter(
            adapter_id=SQLitePortabilityAdapter.adapter_id,
            output_directory=run_directory,
            sample_count=sample_count,
            sqlite_candidate=True,
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
    sqlite_candidate: bool,
) -> dict[str, object]:
    samples = [
        _measure_sample(
            adapter_id=adapter_id,
            output_directory=output_directory,
            sample_index=index,
            sqlite_candidate=sqlite_candidate,
        )
        for index in range(sample_count)
    ]
    return {
        "adapter_id": adapter_id,
        "all_scenarios_passed": all(sample["passed"] for sample in samples),
        "connection_settings": samples[0]["connection_settings"],
        "external_services": [],
        "required_packages": [],
        "samples": samples,
    }


def _measure_sample(
    *,
    adapter_id: str,
    output_directory: Path,
    sample_index: int,
    sqlite_candidate: bool,
) -> dict[str, object]:
    tenant_id = f"tenant-measurement-{sample_index}"
    workflow_id = f"workflow-measurement-{sample_index}"
    database_path = output_directory / f"sqlite-sample-{sample_index}.sqlite3"
    clock = DeterministicClock()
    sink = DeterministicEffectSink()
    factory: Any = (
        SQLitePortabilityAdapterFactory(database_path)
        if sqlite_candidate
        else InternalKernelAdapter
    )
    sample: dict[str, object] = {
        "cold_start_latency_ns": None,
        "connection_settings": {},
        "evidence_counts": None,
        "error_type": None,
        "history_hash": None,
        "passed": False,
        "persisted_database_bytes": 0,
        "recovery_latency_ns": None,
        "sample_index": sample_index,
        "scenario": "sequential_effect_and_fresh_restore",
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
                "command-assign",
                PortabilityOperation.ASSIGN_ATTEMPT,
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
                task_id="task-a",
                attempt_id="attempt-a1",
                worker_id="worker-a",
                fencing_token=1,
                effect_id="effect-a",
                payload_hash=_PAYLOAD_HASH,
            )
        )
        history = adapter.export_history()
        checkpoint = adapter.checkpoint()
        if sqlite_candidate:
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
            )
        )
        final_checkpoint = restored.checkpoint()
        final_history = restored.export_history()
        sample["history_hash"] = final_checkpoint.history_hash
        if sqlite_candidate:
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


__all__ = [
    "MEASUREMENT_SCHEMA_VERSION",
    "canonical_measurement_json",
    "measurements_passed",
    "run_portability_measurements",
]
