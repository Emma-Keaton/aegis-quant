"""
Prometheus metrics for Aegis Quant.
Tracks trades, engine performance, errors, and system health.
"""

import logging
import time
from datetime import datetime, timezone
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    start_http_server,
)
from fastapi import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ── Registry ──────────────────────────────────────────────────────

registry = CollectorRegistry()

# ── Trading Metrics ───────────────────────────────────────────────

trades_executed = Counter(
    'trades_executed_total',
    'Total trades executed',
    ['symbol', 'side', 'venue', 'status'],
    registry=registry,
)

trade_pnl = Gauge(
    'trade_pnl_total',
    'Realized PnL in USD',
    registry=registry,
)

open_positions = Gauge(
    'open_positions_count',
    'Number of open positions',
    registry=registry,
)

win_rate = Gauge(
    'win_rate_ratio',
    'Win rate percentage',
    registry=registry,
)

trade_latency = Histogram(
    'trade_latency_seconds',
    'Time to execute trade',
    registry=registry,
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ── Engine Metrics ────────────────────────────────────────────────

analysis_cycles = Counter(
    'analysis_cycles_total',
    'Total analysis cycles run',
    ['engine'],
    registry=registry,
)

analysis_duration = Histogram(
    'analysis_duration_seconds',
    'Time per analysis cycle',
    registry=registry,
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0],
)

confidence_scores = Histogram(
    'confidence_scores',
    'AI decision confidence scores',
    registry=registry,
    buckets=[0.3, 0.5, 0.7, 0.8, 0.9, 1.0],
)

# ── Source Metrics (Engine B) ─────────────────────────────────────

signals_generated = Counter(
    'signals_generated_total',
    'Total signals generated',
    ['source_type'],
    registry=registry,
)

source_errors = Counter(
    'source_errors_total',
    'Errors from source scrapers',
    ['source_type'],
    registry=registry,
)

# ── System Metrics ────────────────────────────────────────────────

app_up = Gauge(
    'app_up',
    'Application uptime (1 = up, 0 = down)',
    registry=registry,
)

app_start_time = Gauge(
    'app_start_time_seconds',
    'Application start timeUnix timestamp',
    registry=registry,
)

http_requests = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry,
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    registry=registry,
)

error_count = Counter(
    'errors_total',
    'Total errors',
    ['error_type'],
    registry=registry,
)

# ── Initialize ────────────────────────────────────────────────────

def initialize():
    """Set app up to 1 and record start time."""
    app_up.set(1)
    app_start_time.set(time.time())
    logger.info("Prometheus metrics initialized")


def get_metrics_endpoint():
    """Return FastAPI endpoint for /metrics."""
    async def metrics():
        return Response(
            content=generate_latest(registry),
            headers={"Content-Type": CONTENT_TYPE_LATEST},
        )
    return metrics


def track_request(request: Request, response_time: float, status_code: int):
    """Track HTTP request metrics."""
    http_requests.labels(
        method=request.method,
        endpoint=request.url.path,
        status=str(status_code),
    ).inc()
    
    http_request_duration.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(response_time)


def record_trade(symbol: str, side: str, venue: str, status: str = "success"):
    """Record a trade execution."""
    trades_executed.labels(
        symbol=symbol,
        side=side,
        venue=venue,
        status=status,
    ).inc()


def record_pnl(pnl: float):
    """Record realized PnL."""
    trade_pnl.set(pnl)


def update_positions(count: int):
    """Update open positions count."""
    open_positions.set(count)


def update_win_rate(rate: float):
    """Update win rate."""
    win_rate.set(rate)


def record_analysis_cycle(engine: str, duration: float, confidence: float):
    """Record an analysis cycle."""
    analysis_cycles.labels(engine=engine).inc()
    analysis_duration.observe(duration)
    confidence_scores.observe(confidence)


def record_signal(source_type: str):
    """Record a generated signal."""
    signals_generated.labels(source_type=source_type).inc()


def record_source_error(source_type: str):
    """Record a source error."""
    source_errors.labels(source_type=source_type).inc()


def record_error(error_type: str = "general"):
    """Record an error."""
    error_count.labels(error_type=error_type).inc()
