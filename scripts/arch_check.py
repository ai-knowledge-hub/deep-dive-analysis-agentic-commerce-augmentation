"""Compatibility wrapper for scripts.checks.arch_check."""

from scripts.checks.arch_check import *  # noqa: F401,F403

if __name__ == "__main__":
    from scripts.checks.arch_check import main

    main()
