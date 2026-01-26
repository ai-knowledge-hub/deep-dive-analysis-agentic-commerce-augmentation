"""Minimal agent harness primitives.

This is intentionally small and incremental:
- tool registry/execution
- observation logging
- replay metadata
- context packaging + prompt caching

Richer belief-state tracking and RL-style environment state are future experiments
and should not block product iteration.
"""
