"""
Moto-Weather Router — FastAPI application entrypoint.

Run with:
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

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
# CORS — allow SvelteKit dev server
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # SvelteKit dev server
        "http://localhost:4173",   # SvelteKit preview
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(route_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Quick liveness check."""
    return {"status": "ok", "service": "moto-weather-router"}
