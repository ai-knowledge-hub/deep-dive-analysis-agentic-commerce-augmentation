"""Application-layer services.

This package is the first step of the "strangler" migration to a Clean Architecture
layout. Services orchestrate use-cases using existing `modules/*` implementations.

Over time, pure domain logic can be moved into a dedicated `domain/` package and
`modules/*` can become thin compatibility shims.
"""

