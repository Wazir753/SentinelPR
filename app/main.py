"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import status as status_api
from app.config import settings
from app.logging_config import configure_logging, log_stage
from app.webhooks import github_webhook

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_stage(
        logger,
        "startup",
        "SentinelPR starting",
        version=__version__,
        env=settings.app_env,
    )
    yield
    log_stage(logger, "shutdown", "SentinelPR shutting down")


app = FastAPI(
    title="SentinelPR",
    description=(
        "Autonomous code-repair agent: watches GitHub CI failures, retrieves context via RAG, "
        "generates patches, verifies in a sandbox, and opens PRs for human review."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(github_webhook.router)
app.include_router(status_api.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__, "phase": 1}


@app.get("/")
async def root():
    return {
        "service": "SentinelPR",
        "version": __version__,
        "phase": 1,
        "docs": "/docs",
        "status": "/api/status",
    }
