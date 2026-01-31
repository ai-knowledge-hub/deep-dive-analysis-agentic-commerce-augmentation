"""Thin FastAPI wrapper that exposes products/search/conversation endpoints."""

from __future__ import annotations

import os

from shared.config import env as _env  # noqa: F401  # ensure dotenv is loaded early

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore
    CORSMiddleware = None  # type: ignore

from shared.db.connection import init_db
from api.routes import products as products_route
from api.routes import conversation as conversation_route
from api.routes import intent as intent_route
from api.routes import evidence as evidence_route
from api.routes import simulation as simulation_route
from api.routes import batteries as batteries_route
from api.routes import experiments as experiments_route
from api.routes import beliefs as beliefs_route
from api.routes import brands as brands_route
from api.routes import webhooks as webhooks_route
from api.routes import admin as admin_route
from api.routes import replay as replay_route
from api.routes import agents as agents_route

if FastAPI:
    app = FastAPI(title="Contextual Commerce Optimization API")
    init_db()
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
    app.include_router(intent_route.router)
    app.include_router(evidence_route.router)
    app.include_router(evidence_route.representation_router)
    app.include_router(evidence_route.recommendation_router)
    if brands_route.router:
        app.include_router(brands_route.router)
    app.include_router(simulation_route.router)
    app.include_router(batteries_route.router)
    app.include_router(experiments_route.router)
    app.include_router(beliefs_route.router)
    if replay_route.router:
        app.include_router(replay_route.router)
    if webhooks_route.router:
        app.include_router(webhooks_route.router)
    if admin_route.router:
        app.include_router(admin_route.router)
    if agents_route.router:
        app.include_router(agents_route.router)
else:
    app = None
