"""Write canonical workflow-portability measurements for local comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

from application.services.workflow_portability.measurement import (
    canonical_measurement_json,
    measurements_passed,
    run_portability_measurements,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the canonical JSON measurement artifact.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Number of raw timing samples per adapter.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    measurements = run_portability_measurements(
        output_directory=args.output.parent / f"{args.output.stem}-data",
        sample_count=args.samples,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        f"{canonical_measurement_json(measurements)}\n",
        encoding="utf-8",
    )
    return 0 if measurements_passed(measurements) else 1


if __name__ == "__main__":
    raise SystemExit(main())
