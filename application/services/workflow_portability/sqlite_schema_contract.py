"""Shared immutable-table inventory for the portability benchmark schema."""

SQLITE_IMMUTABLE_TABLES = (
    "portability_benchmark_schema",
    "portability_benchmark_workflows",
    "portability_benchmark_graph_definitions",
    "portability_benchmark_durable_definitions",
    "portability_benchmark_durable_records",
    "portability_benchmark_commands",
    "portability_benchmark_events",
    "portability_benchmark_command_receipts",
    "portability_benchmark_effect_receipts",
    "portability_benchmark_checkpoints",
)

__all__ = ["SQLITE_IMMUTABLE_TABLES"]
