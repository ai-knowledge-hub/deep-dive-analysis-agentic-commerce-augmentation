"""Compatibility wrapper for scripts.seed.seed_demo_acme."""

from scripts.seed.seed_demo_acme import *  # noqa: F401,F403
from scripts.seed.seed_demo_acme import seed_demo_acme


if __name__ == "__main__":
    from scripts.seed.seed_demo_acme import DEFAULT_DB_PATH

    seeded = seed_demo_acme()
    print(f"Seeded demo client in {DEFAULT_DB_PATH}: {seeded}")
