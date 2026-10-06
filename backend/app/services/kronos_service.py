"""Kronos forecasting client — remote-only.

Division of responsibility:

- **This service owns market data.** `fetch_candles` pulls OHLCV through
  `app.services.market_service` (CCXT / CoinGecko / Coinlore) and normalises it
  into the wire format modal-kronos expects.
- **Kronos owns prediction only.** It never fetches bars and never trains. It
  receives a validated OHLCV window and returns a predictive distribution.

Kronos is a forecasting model, not a trained strategy, so every learning loop
belongs here: recording what it predicted, and scoring that prediction against
realised prices to calibrate `confidence`. See `record_forecast` and
`score_forecast`.

The heavy ML stack lives on the Modal service and is intentionally not installed
in this backend.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.models import KronosForecast
from app.services.forecasting import get_forecasting_service
from app.services.kronos_ledger_store import LedgerStore

logger = logging.getLogger(__name__)
settings = get_settings()

#: Kronos requires at least this many candles to produce a usable window.
MIN_CANDLES = 16

#: Bar intervals Kronos understands, in seconds.
INTERVAL_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
}


@dataclass
class ForecastResult:
    """Forecast result, populated directly from the modal-kronos response.

    Field names match the wire format so `kronos_service.py` needs no adapter.
    """

    trajectories: List[List[float]]
    mean_path: List[float]
    confidence_90: List[List[float]]
    confidence: int
    metadata: Dict[str, Any]

    @property
    def direction(self) -> str:
        """UP / DOWN / FLAT from the terminal of the mean path."""
        if not self.mean_path:
            return "FLAT"
        change = float(self.metadata.get("predicted_change", 0.0) or 0.0)
        return "UP" if change > 0 else ("DOWN" if change < 0 else "FLAT")

    @property
    def is_degenerate(self) -> bool:
        """True when the service could not produce a real distribution.

        Either a placeholder fallback, or a single sampled path, which carries no
        distributional information. `engine_a.py` gates on `confidence`, so a
        degenerate result must not be traded on.
        """
        return (
            self.metadata.get("model_source") != "kronos"
            or bool(self.metadata.get("distribution_valid") is False)
            or len(self.trajectories) < 2
        )


@dataclass
class ForecastOutcome:
    """A recorded forecast, kept so it can be scored against realised prices.

    This is the training/calibration record. Kronos does not learn from it; this
    service does, and that feedback is what turns `confidence` from a raw model
    frequency into something trustworthy.
    """

    symbol: str
    created_at: datetime
    horizon: int
    interval_seconds: int
    last_close: float
    mean_path: List[float]
    trajectories: List[List[float]]
    confidence: int
    probability_up: float
    terminal_low: float
    terminal_high: float
    model: str
    sample_count: int
    scored: bool = False
    realised: Optional[float] = None
    was_up: Optional[bool] = None
    error: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    #: Primary key of the matching durable ledger row, set when the forecast is
    #: persisted. Scoring writes back through this rather than searching for the
    #: row again.
    ledger_id: Optional[int] = None

    @property
    def predicted_up(self) -> bool:
        return self.probability_up >= 0.5

    def to_record(self) -> Dict[str, Any]:
        """Flatten for the `kronos_forecasts` table."""
        return {
            "symbol": self.symbol,
            "created_at": self.created_at,
            "horizon": self.horizon,
            "interval_seconds": self.interval_seconds,
            "last_close": self.last_close,
            "mean_path": self.mean_path,
            "trajectories": self.trajectories,
            "confidence": self.confidence,
            "probability_up": self.probability_up,
            "terminal_low": self.terminal_low,
            "terminal_high": self.terminal_high,
            "model": self.model,
            "sample_count": self.sample_count,
            "scored": self.scored,
            "realised": self.realised,
            "was_up": self.was_up,
            "error": self.error,
        }


def _normalise_candles(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert `market_service` OHLCV dicts into modal-kronos wire format.

    `market_service.fetch_ohlcv` returns `timestamp` as a Unix epoch in
    milliseconds (`market_service.py:105`). Kronos needs ISO-8601 strings and a
    strictly increasing series, so conversion and ordering happen here rather
    than inside the model service.
    """
    from datetime import datetime as _dt

    converted: List[Dict[str, Any]] = []
    for row in rows:
        raw = row.get("timestamp")
        if raw is None:
            continue
        if isinstance(raw, str):
            stamp = raw
        else:
            seconds = float(raw) / 1000.0
            stamp = _dt.fromtimestamp(seconds, tz=timezone.utc).isoformat()
        entry = {
            "timestamp": stamp,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }
        if row.get("volume") is not None:
            entry["volume"] = float(row["volume"])
        converted.append(entry)

    # Strictly increasing, and de-duplicated: duplicate stamps make Kronos reject
    # the window, and equal timestamps are common in the CCXT fallback chain.
    converted.sort(key=lambda item: item["timestamp"])
    deduped: List[Dict[str, Any]] = []
    for entry in converted:
        if deduped and entry["timestamp"] == deduped[-1]["timestamp"]:
            deduped[-1] = entry
        else:
            deduped.append(entry)
    return deduped


class KronosService:
    """Remote-only Kronos client, with market data owned locally."""

    def __init__(self) -> None:
        self.model_loaded = False  # retained for backward compatibility
        self._http = httpx.AsyncClient(timeout=float(settings.KRONOS_TIMEOUT or 30.0))
        #: Forecasts awaiting scoring, newest last.
        self._outcomes: List[ForecastOutcome] = []

    async def initialize(self) -> None:
        """No-op: this service never loads a local Kronos model."""
        logger.info("Kronos service is remote-only (no local model loading)")

    async def aclose(self) -> None:
        await self._http.aclose()

    # -- market data ---------------------------------------------------------

    async def fetch_candles(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
        exchange_id: str = "binance",
    ) -> List[Dict[str, Any]]:
        """Fetch and normalise OHLCV for Kronos.

        Market data is this service's responsibility, not the model's.
        """
        from app.services.market_service import get_market_service

        market = get_market_service()
        rows = await market.fetch_ohlcv(
            symbol=symbol,
            exchange_id=exchange_id,
            timeframe=timeframe,
            limit=limit,
        )
        candles = _normalise_candles(rows or [])
        if len(candles) < MIN_CANDLES:
            raise ValueError(
                f"{symbol} {timeframe}: only {len(candles)} usable candles, "
                f"need {MIN_CANDLES}"
            )
        return candles

    # -- prediction ----------------------------------------------------------

    @staticmethod
    def candles_from_rows(
        rows: List[Dict[str, Any]],
        timestamps: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Convert engine-owned OHLCV rows into the Kronos wire format.

        The engines hold a pandas frame; this accepts the equivalent list form so
        no pandas dependency leaks into the client. Pass `timestamps` as ISO
        strings when the frame's index carries them.
        """
        out: List[Dict[str, Any]] = []
        for index, row in enumerate(rows):
            if timestamps is not None:
                stamp = timestamps[index]
            else:
                raw = row.get("timestamp")
                if raw is None:
                    raise ValueError(f"row {index} has no timestamp")
                if isinstance(raw, str):
                    stamp = raw
                else:
                    from datetime import datetime as _dt

                    stamp = _dt.fromtimestamp(
                        float(raw) / 1000.0, tz=timezone.utc
                    ).isoformat()
            out.append(
                {
                    "timestamp": stamp,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume") or 0.0),
                }
            )
        return out

    async def forecast(
        self,
        candles: List[Dict[str, Any]],
        horizon: int = 30,
        samples: int = 10,
        *,
        symbol: str = "unknown",
        interval_seconds: int = 3600,
        record: bool = True,
    ) -> ForecastResult:
        """Forecast from caller-supplied OHLCV.

        `samples` defaults to 10 rather than 30: ten paths give a usable 90%
        envelope for a third of the cost, and a single path is not a
        distribution at all (Kronos clamps its `confidence` to a neutral 50 in
        that case).
        """
        if len(candles) < MIN_CANDLES:
            raise ValueError(
                f"need at least {MIN_CANDLES} candles, got {len(candles)}"
            )

        if settings.KRONOS_SERVICE_URL:
            try:
                result = await self._remote_forecast(
                    candles, horizon, samples, symbol, interval_seconds, record
                )
                return result
            except Exception as exc:
                # This is the silent-fabrication path that made the previous
                # service untrustworthy, so it is logged loudly and marked in
                # `metadata.model_source`.
                logger.warning(
                    "Remote Kronos (%s) unavailable for %s: %s; using replacement",
                    settings.KRONOS_SERVICE_URL,
                    symbol,
                    exc,
                )

        result = await self._fallback_forecast(candles, horizon, samples)
        # Record replacement forecasts too. Calibration (and therefore the
        # promotion gate) must not depend on the remote service being
        # configured: an unrecorded forecast can never be scored, and an
        # unscored ledger leaves brier permanently None.
        if record and not result.is_degenerate:
            meta = dict(result.metadata or {})
            meta.setdefault("last_close", float(candles[-1]["close"]))
            meta.setdefault("model", meta.get("model_source") or "fallback")
            result.metadata = meta
            await self._record(result, symbol, interval_seconds)
        return result

    async def forecast_symbol(
        self,
        symbol: str,
        timeframe: str = "1h",
        horizon: int = 30,
        samples: int = 10,
        exchange_id: str = "binance",
        limit: int = 200,
    ) -> ForecastResult:
        """Fetch candles locally, then forecast. The normal entry point."""
        candles = await self.fetch_candles(
            symbol, timeframe=timeframe, limit=limit, exchange_id=exchange_id
        )
        return await self.forecast(
            candles,
            horizon=horizon,
            samples=samples,
            symbol=symbol,
            interval_seconds=INTERVAL_SECONDS.get(timeframe, 3600),
        )

    async def _remote_forecast(
        self,
        candles: List[Dict[str, Any]],
        horizon: int,
        samples: int,
        symbol: str,
        interval_seconds: int,
        record: bool,
    ) -> ForecastResult:
        url = f"{settings.KRONOS_SERVICE_URL.rstrip('/')}/forecast"
        headers = {}
        api_key = getattr(settings, "KRONOS_API_KEY", "")
        if api_key:
            headers["x-api-key"] = api_key
        resp = await self._http.post(
            url,
            json={
                "candles": candles,
                "horizon": horizon,
                "sample_count": samples,
            },
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

        metadata: Dict[str, Any] = {
            "model_source": "kronos",
            "model": data.get("model"),
            "symbol": symbol,
            "interval_seconds": interval_seconds,
            "last_close": data.get("last_close"),
            "predicted_change": data.get("predicted_change"),
            "direction": data.get("direction"),
            "distribution_valid": data.get("distribution_valid"),
            "probability_up": data.get("probability_up"),
            "terminal_low": data.get("terminal_low"),
            "terminal_high": data.get("terminal_high"),
            "sample_count": data.get("sample_count", samples),
            "lookback": data.get("lookback", len(candles)),
            "latency_ms": None,
        }

        result = ForecastResult(
            trajectories=data.get("trajectories") or [],
            mean_path=data.get("mean_path") or [],
            confidence_90=data.get("confidence_90") or [],
            confidence=int(data.get("confidence", 50)),
            metadata=metadata,
        )

        if record:
            await self._record(result, symbol, interval_seconds)
        return result

    async def _fallback_forecast(
        self, candles: List[Dict[str, Any]], horizon: int, samples: int
    ) -> ForecastResult:
        closes = [float(c["close"]) for c in candles]
        try:
            result = await get_forecasting_service().forecast(
                symbol="kronos-fallback",
                closes=closes,
                horizon=horizon,
                samples=samples,
            )
            # Mark it explicitly: callers must be able to tell a real forecast
            # from a replacement, and `ForecastResult.is_degenerate` keys off it.
            result.metadata = dict(result.metadata or {})
            result.metadata["model_source"] = "fallback"
            return result
        except Exception as exc:
            logger.error("Replacement forecast failed: %s, using placeholder", exc)
            return self._placeholder_forecast(closes, horizon, samples)

    def _placeholder_forecast(
        self, closes: List[float], horizon: int, samples: int
    ) -> ForecastResult:
        last_price = closes[-1]
        mean_path = [
            last_price * (1 + (i - horizon / 2) * 0.001) for i in range(horizon)
        ]
        return ForecastResult(
            trajectories=[list(mean_path) for _ in range(samples)],
            mean_path=mean_path,
            confidence_90=[],
            confidence=50,
            metadata={
                "model_source": "placeholder",
                "reason": "forecasting unavailable",
            },
        )

    # -- calibration ---------------------------------------------------------

    async def _record(
        self, result: ForecastResult, symbol: str, interval_seconds: int
    ) -> None:
        """Keep a forecast so it can be scored once prices are known."""
        if result.is_degenerate:
            logger.debug("Not recording a degenerate forecast for %s", symbol)
            return
        outcome = ForecastOutcome(
            symbol=symbol,
            created_at=datetime.now(timezone.utc),
            horizon=len(result.mean_path),
            interval_seconds=interval_seconds,
            last_close=float(result.metadata.get("last_close") or 0.0),
            mean_path=list(result.mean_path),
            trajectories=[list(path) for path in result.trajectories],
            confidence=result.confidence,
            probability_up=float(result.metadata.get("probability_up") or 0.5),
            terminal_low=float(result.metadata.get("terminal_low") or 0.0),
            terminal_high=float(result.metadata.get("terminal_high") or 0.0),
            model=str(result.metadata.get("model") or "unknown"),
            sample_count=int(result.metadata.get("sample_count") or 0),
            metadata=dict(result.metadata),
        )
        self._outcomes.append(outcome)
        # Bounded so a long-running process cannot grow without limit.
        if len(self._outcomes) > 2000:
            del self._outcomes[: len(self._outcomes) - 2000]
        try:
            await self._persist_forecast(outcome)
        finally:
            # The trajectories now live in the durable ledger. Retaining them on
            # the in-memory record as well costs ~30 MB at the 2000-record cap
            # (8 paths x 50 steps x 2000), which matters on a 512 MB Render
            # instance, and nothing in the scoring path reads them.
            outcome.trajectories = []

    async def score_pending(self, price_lookup=None) -> List[ForecastOutcome]:
        """Score recorded forecasts against realised prices.

        This is the feedback loop Kronos itself does not provide: the model
        predicts, this service observes what actually happened, and the resulting
        hit rate is what `confidence` should eventually be calibrated against.

        `price_lookup` is an optional async callable
        `(symbol, unix_seconds) -> float | None`, letting a caller supply prices
        from a better source than the default Binance close.
        """
        now = time.time()
        scored: List[ForecastOutcome] = []

        for outcome in list(self._outcomes):
            if outcome.scored:
                continue
            due = (
                outcome.created_at.timestamp()
                + outcome.horizon * outcome.interval_seconds
            )
            if now < due:
                continue

            realised: Optional[float] = None
            if price_lookup is not None:
                realised = await price_lookup(
                    outcome.symbol, int(due)
                )
            else:
                realised = await self._default_price(outcome.symbol, int(due))

            outcome.scored = True
            if realised is None or not outcome.last_close:
                outcome.error = "no realised price"
                await self._write_back(outcome, None, reason=outcome.error)
                continue

            outcome.realised = float(realised)
            outcome.was_up = outcome.realised > outcome.last_close
            outcome.error = outcome.realised - outcome.mean_path[-1] if outcome.mean_path else None
            await self._write_back(outcome, realised=outcome.realised)
            scored.append(outcome)

        # Durable orphans: rows persisted by a previous process whose in-memory
        # outcome is gone (free-instance restart). Without this pass they stay
        # unscored forever and calibration never sees them.
        try:
            orphan_scored = await self._score_due_rows(now)
            if orphan_scored:
                logger.info("Scored %d orphaned ledger forecasts", orphan_scored)
        except Exception as exc:
            logger.warning("Ledger scoring pass failed: %s", exc)

        return scored

    async def _score_due_rows(self, now: float) -> int:
        """Score elapsed forecasts found only in the durable ledger."""
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            store = LedgerStore(db)
            due_rows = await store.due_forecasts(limit=50)
            count = 0
            for row in due_rows:
                created = row.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                due_dt = created + timedelta(seconds=row.horizon * row.interval_seconds)
                if now < due_dt.timestamp():
                    continue
                realised = await self._default_price(row.symbol, int(due_dt.timestamp()))
                if realised is None or not row.last_close:
                    await store.mark_unscoreable(row, "no realised price")
                    continue
                await store.score(row, float(realised))
                count += 1
            return count

    # -- durable ledger ------------------------------------------------------

    async def _persist_forecast(self, outcome: ForecastOutcome) -> None:
        """Record one forecast in the durable ledger.

        Calibration is the evidence that makes `confidence` meaningful, so it has
        to outlive the process: on a free instance the container is destroyed
        between requests, and a purely in-memory ledger would restart from zero
        evidence every time, so `confidence` could never be validated.

        Sets `outcome.ledger_id` so scoring writes back to this exact row.
        """
        from app.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as db:
                store = LedgerStore(db)
                row = await store.record_forecast(
                    symbol=outcome.symbol,
                    source="kronos",
                    model=outcome.model,
                    horizon=outcome.horizon,
                    interval_seconds=outcome.interval_seconds,
                    sample_count=outcome.sample_count,
                    last_close=outcome.last_close,
                    mean_path=outcome.mean_path,
                    trajectories=outcome.trajectories,
                    probability_up=outcome.probability_up,
                    confidence=outcome.confidence,
                    terminal_low=outcome.terminal_low,
                    terminal_high=outcome.terminal_high,
                )
                if row is not None:
                    outcome.ledger_id = row.id
        except Exception as exc:
            # Losing one forecast is survivable; failing the request is not.
            logger.warning("Could not persist Kronos forecast for %s: %s", outcome.symbol, exc)

    async def _write_back(self, outcome: ForecastOutcome, realised: Optional[float],
                          reason: str = "") -> None:
        """Score or close out the durable row behind one outcome."""
        if outcome.ledger_id is None:
            return
        from app.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as db:
                store = LedgerStore(db)
                row = await db.get(KronosForecast, outcome.ledger_id)
                if row is None:
                    return
                if realised is None:
                    await store.mark_unscoreable(row, reason)
                else:
                    await store.score(row, realised=realised)
        except Exception as exc:
            logger.warning(
                "Could not write back Kronos forecast for %s: %s", outcome.symbol, exc
            )

    async def _default_price(self, symbol: str, unix_seconds: int) -> Optional[float]:
        """Best-effort realised close via the local market service."""
        from app.services.market_service import get_market_service

        try:
            market = get_market_service()
            rows = await market.fetch_ohlcv(
                symbol=symbol,
                exchange_id="binance",
                timeframe="1m",
                limit=1,
            )
            if not rows:
                return None
            return float(rows[-1]["close"])
        except Exception as exc:
            logger.debug("Price lookup failed for %s: %s", symbol, exc)
            return None

    async def calibration_summary(self) -> Dict[str, Any]:
        """Observed accuracy, for checking whether `confidence` is meaningful.

        A `confidence` of 80 that only lands 55% of the time is the signal that
        the number needs recalibrating before it gates real capital.

        Read from the durable ledger rather than an in-process list: this is the
        evidence that decides whether a learned threshold may be trusted, so it
        must include every scored forecast the workspace has ever seen, including
        those from other instances and earlier deployments.
        """
        from app.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as db:
                store = LedgerStore(db)
                rows = await store.scored_forecasts()
        except Exception as exc:
            logger.warning("Could not read calibration ledger: %s", exc)
            return {"scored": 0, "error": str(exc)}

        scored = [row for row in rows if row.was_up is not None]
        if not scored:
            return {"scored": 0, "note": "no scored forecasts yet"}

        total = len(scored)
        hits = sum(1 for row in scored if row.hit)
        banded = [row for row in scored if row.within_band is not None]
        errors = [
            abs(row.absolute_error)
            for row in scored
            if row.absolute_error is not None
        ]
        by_confidence: Dict[str, Dict[str, int]] = {}
        for row in scored:
            bucket = str((row.confidence // 10) * 10)
            entry = by_confidence.setdefault(bucket, {"n": 0, "hits": 0})
            entry["n"] += 1
            if row.hit:
                entry["hits"] += 1
        for entry in by_confidence.values():
            entry["hit_rate"] = round(entry["hits"] / entry["n"], 4) if entry["n"] else 0.0

        return {
            "scored": total,
            "hit_rate": round(hits / total, 4) if total else 0.0,
            "within_90_band": (
                round(sum(1 for row in banded if row.within_band) / len(banded), 4)
                if banded
                else None
            ),
            "mean_absolute_error": (
                round(sum(errors) / len(errors), 8) if errors else None
            ),
            "by_confidence_bucket": by_confidence,
        }

    async def refit(self) -> Dict[str, Any]:
        """Refit learned parameters from the durable ledger and persist them.

        Learned parameters and the active model assignment are workspace-global,
        so one refit incorporates evidence from every profile and device. The
        result is stored even when unvalidated, which makes the fitted values
        inspectable while still refusing to move a live threshold.
        """
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            store = LedgerStore(db)
            state = await store.fit()
            await store.persist_learned(state)
            ranking = await store.rank_models()

        promoted = None
        if ranking and ranking[0].get("significant"):
            async with AsyncSessionLocal() as db:
                promoted = await LedgerStore(db).assign_model(ranking[0]["model"])

        return {
            "sample_size": state.sample_size,
            "validated": state.validated,
            "reason": state.reason,
            "hit_rate": state.hit_rate,
            "promoted_model": getattr(promoted, "model", None),
            "promoted": bool(getattr(promoted, "promoted", False)),
        }

    def pending_forecasts(self) -> List[ForecastOutcome]:
        return [outcome for outcome in self._outcomes if not outcome.scored]


# Global service instance (singleton)
_kronos_service: Optional["KronosService"] = None


def get_kronos_service() -> KronosService:
    """Get the global Kronos service instance (lazy-initialized)."""
    global _kronos_service
    if _kronos_service is None:
        _kronos_service = KronosService()
        asyncio.create_task(_kronos_service.initialize())
    return _kronos_service


def get_kronos_client() -> KronosService:
    """Alias for backward compatibility."""
    return get_kronos_service()


class KronosClientWrapper:
    """Wrapper adapting KronosService to the legacy KronosClient API.

    The legacy signature took a bare list of closes. That shape loses OHLC, which
    Kronos needs, so the close list is expanded into a minimal window rather than
    forwarded as-is.
    """

    def __init__(self) -> None:
        self._service = get_kronos_service()

    async def forecast(self, candles: List[float], horizon: int = 30, samples: int = 10):
        """Legacy close-only entry point.

        Routed to `/forecast/closes`, which synthesises the missing OHLC legs
        server-side. Prefer `KronosService.forecast` with real candles: this
        path has no volume and reconstructs high/low from the close series.
        """
        if len(candles) < MIN_CANDLES:
            raise ValueError(
                f"Insufficient candles: {len(candles)}, need at least {MIN_CANDLES}"
            )
        url = f"{settings.KRONOS_SERVICE_URL.rstrip('/')}/forecast/closes"
        headers = {}
        api_key = getattr(settings, "KRONOS_API_KEY", "")
        if api_key:
            headers["x-api-key"] = api_key
        resp = await self._service._http.post(
            url,
            json={"closes": [float(v) for v in candles], "horizon": horizon, "samples": samples},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "confidence": int(data.get("confidence", 50)),
            "trajectories": data.get("trajectories") or [],
            "mean_path": data.get("mean_path") or [],
            "confidence_90": data.get("confidence_90") or [],
            "metadata": {
                "model_source": "kronos",
                "model": data.get("model"),
                "distribution_valid": data.get("distribution_valid"),
                "synthetic_ohlc": True,
            },
        }


KronosClient = KronosClientWrapper