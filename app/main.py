"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.routers import webhook

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SentinelPR starting (env=%s, version=%s)", settings.app_env, __version__)
    yield
    logger.info("SentinelPR shutting down")


app = FastAPI(
    title="SentinelPR",
    description="AI agent that diagnoses CI failures and opens fix PRs.",
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

app.include_router(webhook.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__, "env": settings.app_env}


@app.get("/")
async def root():
    return {
        "service": "SentinelPR",
        "version": __version__,
        "docs": "/docs",
        "step": "1 — webhook ingress (mock + real GitHub workflow_run)",
    }
