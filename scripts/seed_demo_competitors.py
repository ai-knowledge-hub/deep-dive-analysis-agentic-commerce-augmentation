"""Compatibility wrapper for scripts.seed.seed_demo_competitors."""

from scripts.seed.seed_demo_competitors import *  # noqa: F401,F403

if __name__ == "__main__":
    from scripts.seed.seed_demo_competitors import main

    main()
