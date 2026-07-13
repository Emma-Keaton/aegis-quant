from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db, close_db
from app.core.exceptions import (
    AegisQuantError,
    TelegramAuthError,
    ExchangeError,
    InsufficientFundsError,
    RiskLimitExceededError,
    KronosError,
    GeminiError,
)
from app.api.v1 import state, whitelist, signals, execute, chat, risk, wallet, backtest, rules, logs, telegram


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    
    # Initialize database
    await init_db()
    
    # Start background tasks (engines, scheduler) would go here
    # from app.engines.engine_scheduler import start_engines
    # await start_engines()
    
    yield
    
    # Cleanup
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Aegis Quant - Advanced Telegram Mini App for Quantitative Crypto Trading",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handlers
    @app.exception_handler(AegisQuantError)
    async def aegis_error_handler(request: Request, exc: AegisQuantError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "code": exc.code, "details": exc.details}
        )
    
    @app.exception_handler(TelegramAuthError)
    async def telegram_auth_handler(request: Request, exc: TelegramAuthError):
        return JSONResponse(
            status_code=403,
            content={"error": f"Telegram auth failed: {exc}", "code": "TELEGRAM_AUTH_ERROR"}
        )
    
    @app.exception_handler(ExchangeError)
    async def exchange_error_handler(request: Request, exc: ExchangeError):
        return JSONResponse(
            status_code=502,
            content={"error": exc.message, "code": exc.code, "details": exc.details}
        )
    
    @app.exception_handler(InsufficientFundsError)
    async def insufficient_funds_handler(request: Request, exc: InsufficientFundsError):
        return JSONResponse(
            status_code=400,
            content={"error": exc.message, "code": exc.code, "details": exc.details}
        )
    
    @app.exception_handler(RiskLimitExceededError)
    async def risk_limit_handler(request: Request, exc: RiskLimitExceededError):
        return JSONResponse(
            status_code=400,
            content={"error": exc.message, "code": exc.code, "details": exc.details}
        )
    
    @app.exception_handler(KronosError)
    async def kronos_error_handler(request: Request, exc: KronosError):
        return JSONResponse(
            status_code=503,
            content={"error": exc.message, "code": exc.code, "details": exc.details}
        )
    
    @app.exception_handler(GeminiError)
    async def gemini_error_handler(request: Request, exc: GeminiError):
        return JSONResponse(
            status_code=503,
            content={"error": exc.message, "code": exc.code, "details": exc.details}
        )
    
    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "aegis-quant-backend"}
    
    # API routes
    app.include_router(state.router, prefix="/api/v1", tags=["state"])
    app.include_router(whitelist.router, prefix="/api/v1", tags=["whitelist"])
    app.include_router(signals.router, prefix="/api/v1", tags=["signals"])
    app.include_router(execute.router, prefix="/api/v1", tags=["execute"])
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(risk.router, prefix="/api/v1", tags=["risk"])
    app.include_router(wallet.router, prefix="/api/v1", tags=["wallet"])
    app.include_router(backtest.router, prefix="/api/v1", tags=["backtest"])
    app.include_router(rules.router, prefix="/api/v1", tags=["rules"])
    app.include_router(logs.router, prefix="/api/v1", tags=["logs"])
    app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["telegram"])
    
    return app


app = create_app()