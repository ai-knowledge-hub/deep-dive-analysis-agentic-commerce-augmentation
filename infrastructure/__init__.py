"""Infrastructure layer.

Concrete implementations and adapters for external systems:
- DB repositories
- LLM clients/classifiers
- Tool execution surfaces

Application/services should prefer importing from `infrastructure.*` rather than
directly from `modules/*` or `shared/*`, so we can evolve implementations
without rewriting higher layers.
"""
