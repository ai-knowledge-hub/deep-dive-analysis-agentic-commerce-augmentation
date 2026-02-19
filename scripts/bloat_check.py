"""Compatibility wrapper for scripts.checks.bloat_check."""

from scripts.checks.bloat_check import *  # noqa: F401,F403

if __name__ == "__main__":
    from scripts.checks.bloat_check import main

    main()
