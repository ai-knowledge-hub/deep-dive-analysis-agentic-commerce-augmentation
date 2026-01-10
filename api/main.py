"""Thin FastAPI wrapper that exposes products/search/conversation endpoints."""

from __future__ import annotations

import os

from config import env as _env  # noqa: F401  # ensure dotenv is loaded early

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore
    CORSMiddleware = None  # type: ignore

from api.routes import products as products_route
from api.routes import conversation as conversation_route

if FastAPI:
    app = FastAPI(title="Contextual Commerce Optimization API")
    if CORSMiddleware:
        frontend_origin = os.getenv("FRONTEND_URL", "http://localhost:3000")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[frontend_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(products_route.router)
    app.include_router(conversation_route.router)
else:
    app = None
