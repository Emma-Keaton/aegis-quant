"""Model scoreboard (port of beast-trader's ml/scoreboard.js).

The reference's board is a file of per-model pending/outcome pairs; here the
same numbers are derived from the durable `kronos_forecasts` ledger plus the
paper record, so nothing is lost to a process restart. Ranking is advisory —
the board promotes nothing; promotion only happens through `promotion.py`
(and the forecast-model gate in `LedgerStore.assign_model`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, func

from app.core.model_eval import roc_auc, spearman_ic
from app.database import AsyncSessionLocal
from app.models import KronosForecast, PaperBalance, Position, PromotionDecision, TradeMode
from app.services import circuit_breaker
from app.services.kronos_ledger_store import LedgerStore


async def _models_from_ledger() -> List[dict]:
    """Per-model discrimination + calibration straight from scored forecasts."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(KronosForecast.model, func.count(KronosForecast.id))
            .where(KronosForecast.scored.is_(True))
            .group_by(KronosForecast.model)
        )).all()

        board: List[dict] = []
        for model, total in rows:
            total = int(total or 0)
            if not total:
                continue
            hits = (await db.execute(
                select(func.count(KronosForecast.id))
                .where(KronosForecast.scored.is_(True))
                .where(KronosForecast.model == model)
                .where(KronosForecast.was_up.is_(True))
            )).scalar() or 0
            brier_rows = (await db.execute(
                select(
                    KronosForecast.probability_up,
                    KronosForecast.was_up,
                    KronosForecast.last_close,
                    KronosForecast.realised,
                )
                .where(KronosForecast.scored.is_(True))
                .where(KronosForecast.model == model)
                .limit(500)
            )).all()
            brier = None
            scores: List[float] = []
            labels: List[int] = []
            realized_move: List[float] = []
            if brier_rows:
                total_sq = 0.0
                counted = 0
                for prob, was_up, last_close, realised in brier_rows:
                    if prob is None or was_up is None:
                        continue
                    p = min(max(float(prob), 0.0), 1.0)
                    y = 1.0 if bool(was_up) else 0.0
                    total_sq += (p - y) ** 2
                    counted += 1
                    scores.append(p)
                    labels.append(int(y))
                    if last_close and realised:
                        try:
                            realized_move.append(float(realised) / float(last_close) - 1.0)
                        except ZeroDivisionError:
                            pass
                if counted:
                    brier = round(total_sq / counted, 4)
            auc = roc_auc(scores, labels)
            ic = spearman_ic(scores, realized_move) if len(scores) == len(realized_move) and scores else None
            board.append({
                "model": model or "unknown",
                "settled": total,
                "hit_rate": round(int(hits) / total, 4),
                "brier": brier,
                "roc_auc": round(auc, 4) if auc is not None else None,
                "spearman_ic": round(ic, 4) if ic is not None else None,
            })

    board.sort(key=lambda m: (m["hit_rate"], -(m["brier"] if m["brier"] is not None else 1.0)), reverse=True)
    for i, entry in enumerate(board, start=1):
        entry["rank"] = i
    return board


async def _paper_stats() -> dict:
    async with AsyncSessionLocal() as db:
        closed = (await db.execute(
            select(Position.unrealized_pnl, Position.entry_price, Position.size)
            .where(Position.is_closed.is_(True))
            .where(Position.mode == TradeMode.PAPER)
        )).all()
        open_count = (await db.execute(
            select(func.count(Position.id))
            .where(Position.is_closed.is_(False))
            .where(Position.mode == TradeMode.PAPER)
        )).scalar() or 0
        equity = (await db.execute(
            select(func.coalesce(func.sum(PaperBalance.balance), 0))
        )).scalar()
    wins = trades = 0
    for pnl, entry, size in closed:
        margin = float(entry or 0) * float(size or 0)
        if margin <= 0:
            continue
        trades += 1
        if float(pnl or 0) > 0:
            wins += 1
    return {
        "open_positions": int(open_count),
        "settled_trades": trades,
        "win_rate": round(wins / trades, 4) if trades else None,
        "equity_usd": float(equity or 0),
    }


async def scoreboard() -> dict:
    """Full board: forecast models (ledger) + paper record + breaker + latest promotion."""
    async with AsyncSessionLocal() as db:
        store = LedgerStore(db)
        ranking = await store.rank_models()
    ledger = await _models_from_ledger()
    paper = await _paper_stats()

    async with AsyncSessionLocal() as db:
        latest = (await db.execute(
            select(PromotionDecision)
            .order_by(PromotionDecision.created_at.desc())
            .limit(1)
        )).scalars().first()

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "forecast_models": ledger,
        "promotion_ranking": ranking,
        "paper": paper,
        "breaker": circuit_breaker.status(),
        "latest_promotion": {
            "profile_id": latest.profile_id,
            "status": latest.status,
            "reason": latest.reason,
            "decided_at": latest.decided_at.isoformat() if latest and latest.decided_at else None,
        } if latest else None,
        "note": "Advisory ranking — promotion runs through the promotion gate only.",
    }
