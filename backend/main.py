"""
Moto-Weather Router — FastAPI application entrypoint.

Run with:
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from routers.route import router as route_router
from utils.logger import setup_logger

logger = setup_logger("main")

# ---------------------------------------------------------------------------
# App & Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Moto-Weather Router backend starting up...")
    yield
    logger.info("Moto-Weather Router backend shutting down.")

app = FastAPI(
    title="Moto-Weather Router API",
    description=(
        "Deterministic routing and weather intelligence for motorcycle riders. "
        "No LLMs. No generative AI. Pure math."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Logging Middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Don't log health check repeatedly
    if request.url.path == "/health":
        return await call_next(request)
        
    logger.info(f"Incoming Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Completed Request: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Failed Request: {request.method} {request.url.path} - Exception: {e} - Time: {process_time:.3f}s")
        raise

# ---------------------------------------------------------------------------
# CORS — allow SvelteKit dev & deployed frontend
# ---------------------------------------------------------------------------

cors_origins_env = os.getenv("CORS_ORIGINS", "*")
if cors_origins_env.strip() == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if allowed_origins != ["*"] else False,
    allow_origin_regex="https?://.*" if allowed_origins == ["*"] else None,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(route_router)


@app.get("/", tags=["meta"])
async def root() -> dict:
    """Root endpoint welcoming visitors and providing documentation links."""
    return {
        "status": "online",
        "service": "Moto-Weather Router API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Quick liveness check."""
    return {"status": "ok", "service": "moto-weather-router"}
