"""Application-layer ports (interfaces).

These are dependency inversion points: application services depend on ports,
and infrastructure provides concrete implementations.
"""

from application.ports.deps import AppDeps

__all__ = ["AppDeps"]
