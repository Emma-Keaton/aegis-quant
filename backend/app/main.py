"""Aegis Quant — merged FastAPI application.

Replaces the Express server.ts entirely.
Serves the Vite-built SPA, handles all REST API endpoints,
WebSocket price feed, and background engines.
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio

from app.config import get_settings
from app.database import init_db, close_db
from app.core.exceptions import (
    AegisQuantError, TelegramAuthError, ExchangeError,
    InsufficientFundsError, RiskLimitExceededError,
    KronosError, GeminiError, EngineError,
)
from app.middleware.rate_limit import rate_limiter
from app.middleware.metrics import metrics_middleware
from app.api.v1.auth import router as auth_router
from app.api.v1.state import router as state_router
from app.api.v1.signals import router as signals_router
from app.api.v1.logs import router as logs_router
from app.api.v1.backtest import router as backtest_router
from app.api.v1.rules import router as rules_router
from app.api.v1.copytrade import router as copytrade_router
from app.api.v1.chat import router as chat_router
from app.api.v1.wallet import router as wallet_router
from app.api.v1.risk import router as risk_router
from app.api.v1.whitelist import router as whitelist_router
from app.api.websocket import router as ws_router
from app.api.v1.telegram import router as telegram_router
from app.api.v1.admin import router as admin_router
from app.api.v1.sources import router as sources_router

# ── Logging ───────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("aegis")


# ── Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"[AEGIS] Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    await init_db()
    logger.info("[AEGIS] Database initialized")
    
    # Start background engines
    try:
        from app.engines.engine_scheduler import start_engines
        await start_engines()
        logger.info("[AEGIS] Trading engines started")
    except Exception as e:
        logger.warning(f"[AEGIS] Engine startup skipped: {e}")

    # Start market data feed (default symbol list, 5‑second interval)
    try:
        from app.services.market_hub import start_market_feed
        await start_market_feed()
        logger.info("[AEGIS] Market feed started")
    except Exception as e:
        logger.warning(f"[AEGIS] Market feed startup skipped: {e}")

    # Start QuantDinger background workers (market fetcher)
    try:
        from app.quantdinger.utils.market_fetcher import market_fetcher_task
        task = asyncio.create_task(market_fetcher_task(app))
        app.state.quantdinger_tasks = [task]
        logger.info("[AEGIS] QuantDinger market fetcher started")
    except Exception as e:
        logger.warning(f"[AEGIS] QuantDinger market fetcher start failed: {e}")
    yield

    # Stop engines
    try:
        from app.engines.engine_scheduler import stop_engines
        await stop_engines()
        logger.info("[AEGIS] Engines stopped")
    except Exception:
        pass

    # Stop market feed
    try:
        from app.services.market_hub import stop_market_feed
        await stop_market_feed()
        logger.info("[AEGIS] Market feed stopped")
    except Exception:
        pass

    await close_db()
    logger.info("[AEGIS] Shutting down")


# ── App ───────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    
    # ── Middleware ────────────────────────────────────────────────
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Rate limiting
    app.add_middleware(metrics_middleware)
    
    # Trusted host + security headers (basic Helmet equivalent)
    if not settings.DEBUG:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
    
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response
    
    # ── Exception handlers ────────────────────────────────────────
    
    @app.exception_handler(AegisQuantError)
    async def aegis_handler(request, exc: AegisQuantError):
        return {"error": exc.message, "code": exc.code, "status_code": exc.status_code}
    
    @app.exception_handler(TelegramAuthError)
    async def telegram_auth_handler(request, exc: TelegramAuthError):
        return {"error": str(exc), "code": "TELEGRAM_AUTH_ERROR"}, 403
    
    @app.exception_handler(ExchangeError)
    async def exchange_handler(request, exc: ExchangeError):
        return {"error": exc.message, "code": exc.code}, 502
    
    @app.exception_handler(InsufficientFundsError)
    async def funds_handler(request, exc: InsufficientFundsError):
        return {"error": exc.message, "code": exc.code}, 400
    
    @app.exception_handler(RiskLimitExceededError)
    async def risk_handler(request, exc: RiskLimitExceededError):
        return {"error": exc.message, "code": exc.code}, 400
    
    @app.exception_handler(KronosError)
    async def kronos_handler(request, exc: KronosError):
        return {"error": exc.message, "code": exc.code}, 503
    
    @app.exception_handler(GeminiError)
    async def gemini_handler(request, exc: GeminiError):
        return {"error": exc.message, "code": exc.code}, 503
    
    # ── Health ────────────────────────────────────────────────────
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "aegis-quant", "version": settings.APP_VERSION}
    
    # ── Merged API routers (replaces Express /api/*) ──────────────
    
    # Auth — must be first
    app.include_router(auth_router)
    
    # Core state, signals, logs, backtest, rules, copytrade, chat
    app.include_router(state_router)
    app.include_router(signals_router)
    app.include_router(logs_router)
    app.include_router(backtest_router)
    app.include_router(rules_router)
    app.include_router(copytrade_router)
    app.include_router(chat_router)
    
    # Existing cleaned-up routers (wallet, risk, whitelist, telegram)
    app.include_router(wallet_router)
    app.include_router(risk_router)
    app.include_router(whitelist_router)
    app.include_router(telegram_router)
    # AI Trade integration
    from app.api.v1.ai_trade import router as ai_trade_router
    app.include_router(ai_trade_router)

    # Admin routes (guarded by ADMIN_CHAT_ID)
    from app.api.v1.admin import router as admin_router
    app.include_router(admin_router)
    app.include_router(sources_router)  # Source management
    # Metrics API
    from app.api.v1.metrics import router as metrics_router
    app.include_router(metrics_router)

    # WebSocket
    # Prometheus metrics
    from app.metrics import get_metrics_endpoint, initialize
    app.get("/metrics")(get_metrics_endpoint())
    initialize()
    app.include_router(ws_router)
    
    # ── SPA serving ───────────────────────────────────────────────
    
    SPA_PATH = Path(__file__).parent.parent.parent / "dist"
    
    if SPA_PATH.exists():
        app.mount("/static", StaticFiles(directory=str(SPA_PATH)), name="static")
    
    @app.get("/{full_path:path}")
    async def spa_index(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("redoc"):
            return {"detail": "Not found"}, 404
        
        spa_file = SPA_PATH / (full_path if full_path.endswith(".html") else full_path + ".html")
        if spa_file.exists():
            return FileResponse(spa_file)
        
        index_file = SPA_PATH / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        
        return {"detail": "Not found"}, 404
    
    logger.info(f"[AEGIS] App created — docs: /docs")
    return app


app = create_app()

# ── Solana Trading Router ────────────────────────────────────────
from app.api.v1.solana import router as solana_router
app.include_router(solana_router)
