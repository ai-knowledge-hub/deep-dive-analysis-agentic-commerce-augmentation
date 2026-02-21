"""Compatibility wrapper for scripts.ops.run_agent_runtime_worker."""

from scripts.ops.run_agent_runtime_worker import *  # noqa: F401,F403

if __name__ == "__main__":
    from scripts.ops.run_agent_runtime_worker import main

    main()
