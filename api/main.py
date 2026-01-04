"""Thin FastAPI wrapper that exposes products/search endpoints."""

from __future__ import annotations

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore

from api.routes import products as products_route

if FastAPI:
    app = FastAPI(title="Contextual Commerce Optimization API")
    app.include_router(products_route.router)
else:
    app = None
