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
from api.routes import analytics as analytics_route
from api.routes import health as health_route
from api.routes import llm_config as llm_config_route
from api.routes import overview as overview_route
from api.routes import validation as validation_route
from api.routes import copy_revisions as copy_revisions_route
from api.routes import loop as loop_route
from api.routes import memory as memory_route
from api.routes import calibration as calibration_route
from api.routes import agent_runs_registry as agent_runs_registry_route
from api.routes import agent_runs_control as agent_runs_control_route
from api.routes import agent_runs_commands as agent_runs_commands_route
from api.routes import agent_runs as agent_runs_route
from api.routes import external_agent_credentials as external_agent_credentials_route
from api.routes import external_agent_jobs as external_agent_jobs_route
from api.routes import external_agent_job_operator as external_agent_job_operator_route

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
    app.include_router(analytics_route.router)
    app.include_router(health_route.router)
    app.include_router(llm_config_route.router)
    app.include_router(overview_route.router)
    app.include_router(validation_route.router)
    app.include_router(copy_revisions_route.router)
    app.include_router(loop_route.router)
    app.include_router(memory_route.router)
    app.include_router(calibration_route.router)
    app.include_router(agent_runs_registry_route.router)
    app.include_router(agent_runs_control_route.router)
    app.include_router(agent_runs_commands_route.router)
    app.include_router(agent_runs_route.router)
    app.include_router(external_agent_credentials_route.router)
    app.include_router(external_agent_jobs_route.router)
    app.include_router(external_agent_job_operator_route.router)
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
