from __future__ import annotations

from scripts.checks import arch_check


def test_architecture_boundaries_pass():
    assert arch_check.main() == 0
