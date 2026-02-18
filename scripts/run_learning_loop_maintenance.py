"""Compatibility wrapper for scripts.ops.run_learning_loop_maintenance."""

from scripts.ops.run_learning_loop_maintenance import *  # noqa: F401,F403

if __name__ == "__main__":
    from scripts.ops.run_learning_loop_maintenance import main

    main()
