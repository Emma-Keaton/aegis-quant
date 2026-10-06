"""Paper → live promotion (port of beast-trader's evaluate.js + gate.js).

Two halves, kept separate like the reference:

* `evaluate()` — the static bar. Pure, no I/O, every condition must hold and
  each failure pushes a human-readable reason.
* `run_cycle()` / `live_readiness()` — the runtime half. Evidence is gathered
  from closed paper positions plus the forecast ledger's calibration, the bar
  is applied, the decision is persisted (`promotion_decisions`, auditable),
  and live orders are gated on `promoted` until an operator flips the mode.

Nothing here flips `trading_mode` by itself: promotion certifies readiness;
switching to live remains an explicit act (and still requires
`LIVE_TRADING_ENABLED` and closed breakers).
"""
from __future__ import annotations

import logging
import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Position, Profile, PromotionDecision, TradeMode
from app.services import circuit_breaker
from app.services.strategy_learner import beats_coin_flip

logger = logging.getLogger(__name__)


# ── statistical helpers ─────────────────────────────────────────────────────

def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _phi_inv(p: float) -> float:
    from scipy.stats import norm

    return float(norm.ppf(p))


def _moment_skew(returns: Sequence[float]) -> float:
    from scipy.stats import skew

    return float(skew(returns, bias=False))


def _moment_kurtosis(returns: Sequence[float]) -> float:
    from scipy.stats import kurtosis

    # Pearson (non-Fisher) convention: normal == 3, matching the formula.
    return float(kurtosis(returns, fisher=False, bias=False))


def probabilistic_sharpe(returns: Sequence[float]) -> float:
    """P(true Sharpe > 0) — the PSR used as the significance term.

    Below 4 observations there is nothing to judge; report 0 so the bar fails
    rather than passing on absent evidence (the reference's rule for DSR).
    """
    n = len(returns)
    if n < 4:
        return 0.0
    mean = statistics.fmean(returns)
    try:
        sd = statistics.stdev(returns)
    except statistics.StatisticsError:
        return 0.0
    if sd <= 0:
        return 0.0
    sr = mean / sd
    m3 = _moment_skew(returns)
    m4 = _moment_kurtosis(returns)
    denom = math.sqrt(max(1e-12, 1.0 - m3 * sr + (m4 - 1.0) / 4.0 * sr * sr))
    return _phi(sr * math.sqrt(n - 1) / denom)


def deflated_sharpe(returns: Sequence[float], trials: int = 1) -> float:
    """PSR against the expected best of `trials` attempts (Blom approximation)."""
    n = len(returns)
    if n < 4 or trials < 1:
        return 0.0
    mean = statistics.fmean(returns)
    try:
        sd = statistics.stdev(returns)
    except statistics.StatisticsError:
        return 0.0
    if sd <= 0:
        return 0.0
    sr = mean / sd
    expected_max_z = _phi_inv((trials - 0.375) / (trials + 0.25))
    hurdle_sr = expected_max_z / math.sqrt(n)
    m3 = _moment_skew(returns)
    m4 = _moment_kurtosis(returns)
    denom = math.sqrt(max(1e-12, 1.0 - m3 * sr + (m4 - 1.0) / 4.0 * sr * sr))
    return _phi((sr - hurdle_sr) * math.sqrt(n - 1) / denom)


# ── the static bar (faithful port) ──────────────────────────────────────────

def default_bar() -> dict:
    s = get_settings()
    return {
        "max_brier": s.PROMOTION_MAX_BRIER,
        "min_accuracy": s.PROMOTION_MIN_ACCURACY,
        "min_expectancy": s.PROMOTION_MIN_EXPECTANCY,
        "min_trades": s.PROMOTION_MIN_TRADES,
        "min_deflated_sharpe": s.PROMOTION_MIN_DEFALTED_SHARPE,
        "min_track_days": s.PROMOTION_MIN_TRACK_DAYS,
    }


def evaluate(report: dict, bar: Optional[dict] = None) -> dict:
    """All conditions must hold; failures collect user-facing reasons."""
    bar = bar or default_bar()
    reasons: List[str] = []

    brier = report.get("brier")
    if brier is None:
        reasons.append("No calibrated forecast evidence yet (nothing has been scored)")
    elif brier >= bar["max_brier"]:
        reasons.append(f"Forecast calibration is off (brier {brier:.3f} >= {bar['max_brier']})")

    accuracy = report.get("accuracy")
    if accuracy is None:
        reasons.append("No trade outcomes to judge yet")
    elif accuracy <= bar["min_accuracy"]:
        reasons.append("Win rate is no better than a guess")

    expectancy = report.get("expectancy")
    if expectancy is None:
        reasons.append("No expectancy to judge yet")
    elif expectancy <= bar["min_expectancy"]:
        reasons.append("Does not make money after fees")

    trades = int(report.get("trades") or 0)
    if trades < bar["min_trades"]:
        reasons.append(f"Not enough practice trades ({trades} < {bar['min_trades']})")

    dsr = report.get("deflated_sharpe")
    if dsr is None or dsr < bar["min_deflated_sharpe"]:
        reasons.append("Edge could be luck (significance below bar)")

    age_days = report.get("age_days")
    if age_days is not None and age_days < bar["min_track_days"]:
        reasons.append(f"Not tracked long enough ({age_days:.1f} < {bar['min_track_days']} days)")

    promoted = not reasons
    return {
        "promoted": promoted,
        "reasons": reasons,
        "headline": "Criteria met — ready for live" if promoted else reasons[0],
    }


# ── evidence ────────────────────────────────────────────────────────────────

async def _forecast_brier(db) -> Optional[float]:
    from app.models import KronosForecast

    rows = (await db.execute(
        select(KronosForecast.probability_up, KronosForecast.was_up)
        .where(KronosForecast.scored.is_(True))
        .order_by(KronosForecast.created_at.desc())
        .limit(500)
    )).all()
    if not rows:
        return None
    total = 0.0
    for prob, was_up in rows:
        if prob is None or was_up is None:
            continue
        p = min(max(float(prob), 0.0), 1.0)
        y = 1.0 if bool(was_up) else 0.0
        total += (p - y) ** 2
    return total / len(rows) if rows else None


async def paper_evidence(profile_id) -> dict:
    """Closed paper positions → the numbers the bar consumes (pure-ish)."""
    async with AsyncSessionLocal() as db:
        positions = (await db.execute(
            select(Position)
            .where(Position.profile_id == profile_id)
            .where(Position.is_closed.is_(True))
            .where(Position.mode == TradeMode.PAPER)
            .order_by(Position.opened_at.asc())
        )).scalars().all()
        brier = await _forecast_brier(db)

    returns: List[float] = []
    wins = 0
    gross_win = gross_loss = 0.0
    for pos in positions:
        margin = float(pos.entry_price or 0) * float(pos.size or 0)
        if margin <= 0:
            continue
        ret = float(pos.unrealized_pnl or 0) / margin
        returns.append(ret)
        if ret > 0:
            wins += 1
            gross_win += ret
        else:
            gross_loss += abs(ret)

    trades = len(returns)
    win_rate = (wins / trades) if trades else None
    expectancy = statistics.fmean(returns) if trades else None
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (math.inf if gross_win > 0 else None)

    max_dd = 0.0
    equity = peak = 1.0
    for ret in returns:
        equity *= (1.0 + ret)
        peak = max(peak, equity)
        max_dd = max(max_dd, 1.0 - equity / peak)

    oldest = min((p.opened_at for p in positions), default=None)
    age_days = None
    if oldest is not None:
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - oldest) / timedelta(days=1))

    from app.core.statistics import (
        calmar_ratio, conditional_var, sharpe_ratio, value_at_risk, wilson_interval,
    )

    interval_seconds = 3600
    return {
        "trades": trades,
        "wins": wins,
        "win_rate": win_rate,
        # Wilson score interval: honest on small samples (unlike a raw ratio).
        "win_rate_ci": wilson_interval(wins, trades) if trades else None,
        "expectancy": expectancy,
        "max_drawdown": max_dd,
        "profit_factor": None if profit_factor is None or math.isinf(profit_factor) else profit_factor,
        "age_days": age_days,
        "brier": brier,
        "deflated_sharpe": deflated_sharpe(returns) if trades >= 4 else 0.0,
        # Interval-aware risk shape (crypto 24/7 annualization on 1h bars).
        "sharpe_ratio": sharpe_ratio(returns, interval_seconds=interval_seconds) if trades >= 2 else None,
        "calmar_ratio": calmar_ratio(_equity_curve(returns), interval_seconds=interval_seconds) if trades >= 2 else None,
        "var_95": value_at_risk(returns, 0.95) if trades else None,
        "cvar_95": conditional_var(returns, 0.95) if trades else None,
        "returns_sample": returns[-50:],
    }


def _equity_curve(returns):
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    return equity


def evaluate_evidence(evidence: dict) -> dict:
    """Evidence dict → bar report, plus the stability rules from the port."""
    bar = default_bar()
    report = {
        "brier": evidence.get("brier"),
        "accuracy": evidence.get("win_rate"),
        "expectancy": evidence.get("expectancy"),
        "trades": evidence.get("trades"),
        "deflated_sharpe": evidence.get("deflated_sharpe"),
        "age_days": evidence.get("age_days"),
    }
    verdict = evaluate(report, bar)
    extra: List[str] = []
    trades = int(evidence.get("trades") or 0)
    wins = int(evidence.get("wins") or 0)
    if trades >= 10 and not beats_coin_flip(wins, trades):
        extra.append("Win rate is not statistically better than a coin flip")
    # Wilson CI: a 55% hit rate on 12 trades is indistinguishable from noise.
    ci = evidence.get("win_rate_ci")
    if ci and ci.get("lower") is not None and trades >= 10 and ci["lower"] <= 0.5:
        extra.append(
            f"Win rate interval includes coin flip "
            f"({ci['lower']:.0%}–{ci['upper']:.0%} on {trades} trades)"
        )
    dd = evidence.get("max_drawdown")
    if dd is not None and dd > 0.25:
        extra.append(f"Drawdown too deep ({dd:.0%} > 25%)")
    pf = evidence.get("profit_factor")
    if trades >= 10 and pf is not None and pf < 1.1:
        extra.append(f"Profit factor too low ({pf:.2f} < 1.1)")
    # Tail risk: a strategy whose 95% single-trade tail worse than -15% is
    # not fit for live capital regardless of its mean.
    var = evidence.get("var_95")
    if trades >= 20 and var is not None and var > 0.15:
        extra.append(f"Tail risk too deep (95% VaR {var:.1%} of margin per trade)")
    if extra:
        verdict["promoted"] = False
        verdict["reasons"] = verdict["reasons"] + extra
        verdict["headline"] = verdict["reasons"][0]
    return {**verdict, "report": report, "stability": extra}


# ── runtime: decisions, readiness, cycle ────────────────────────────────────

async def latest_decision(profile_id) -> Optional[PromotionDecision]:
    async with AsyncSessionLocal() as db:
        return (await db.execute(
            select(PromotionDecision)
            .where(PromotionDecision.profile_id == str(profile_id))
            .order_by(PromotionDecision.created_at.desc())
        )).scalars().first()


async def is_promoted(profile_id) -> bool:
    decision = await latest_decision(profile_id)
    return bool(decision and decision.status == "promoted")


async def run_evaluation(profile: Profile) -> dict:
    evidence = await paper_evidence(profile.id)
    verdict = evaluate_evidence(evidence)
    breaker_ok, breaker_reason = await circuit_breaker.can_trade()
    status = "promoted" if verdict["promoted"] else "rejected"
    reasons = list(verdict["reasons"])
    if verdict["promoted"] and not breaker_ok:
        status = "eligible"
        reasons.append(breaker_reason or "Circuit breaker is open")

    previous = await latest_decision(profile.id)
    previous_status = previous.status if previous else None

    # No state change and nothing to refresh → don't churn the audit table.
    if previous is not None and previous_status == status and status != "promoted":
        return {"status": status, "reasons": reasons, "evidence": evidence,
                "decision_id": previous.id, "changed": False}

    async with AsyncSessionLocal() as db:
        decision = PromotionDecision(
            profile_id=str(profile.id),
            status=status,
            reason="; ".join(reasons) if reasons else "criteria met",
            evidence={
                **{k: v for k, v in evidence.items() if k != "returns_sample"},
                "report": verdict["report"],
                "verdict_reasons": verdict["reasons"],
            },
            created_at=datetime.now(timezone.utc),
            decided_at=datetime.now(timezone.utc),
        )
        db.add(decision)
        await db.commit()
        await db.refresh(decision)

    if status != previous_status and profile.telegram_id:
        from app.services.notifier import notifier

        if status == "promoted":
            notifier.notify_soon(
                profile.telegram_id,
                "✅ <b>Promotion criteria met</b>\n"
                f"Trades: {evidence['trades']} · win rate: "
                f"{(evidence['win_rate'] or 0):.0%} · expectancy: "
                f"{(evidence['expectancy'] or 0):+.2%}\n"
                "Enable live trading in Settings when ready.",
            )
        elif status == "rejected" and previous_status == "promoted":
            notifier.notify_soon(
                profile.telegram_id,
                "⚠️ <b>Live promotion revoked</b>\n"
                f"Reason: {decision.reason}",
            )
    return {"status": status, "reasons": reasons, "evidence": evidence,
            "decision_id": decision.id, "changed": status != previous_status}


async def run_cycle() -> dict:
    """Scheduled job: evaluate every bot-enabled profile once."""
    settings = get_settings()
    if not settings.PROMOTION_ENABLED:
        return {"enabled": False, "evaluated": 0}
    await circuit_breaker.evaluate()
    async with AsyncSessionLocal() as db:
        profiles = (await db.execute(
            select(Profile).where(Profile.bot_enabled.is_(True))
        )).scalars().all()
    results: Dict[str, str] = {}
    for profile in profiles:
        try:
            outcome = await run_evaluation(profile)
            results[str(profile.id)] = outcome["status"]
        except Exception as exc:
            logger.warning("promotion evaluation failed for %s: %s", profile.id, exc)
    logger.info("promotion cycle complete: %s", results)
    return {"enabled": True, "evaluated": len(results), "results": results}


async def live_readiness(profile: Profile) -> dict:
    """The checklist that must pass before live mode may be switched on."""
    settings = get_settings()
    checks: List[dict] = []

    breaker_ok, breaker_reason = await circuit_breaker.can_trade()
    checks.append({"name": "breaker_closed", "passed": breaker_ok,
                   "detail": breaker_reason or "Circuit breaker closed"})
    checks.append({"name": "live_enabled", "passed": settings.LIVE_TRADING_ENABLED,
                   "detail": "LIVE_TRADING_ENABLED is true" if settings.LIVE_TRADING_ENABLED
                   else "Set LIVE_TRADING_ENABLED=true to allow live trading"})
    promoted = await is_promoted(profile.id)
    checks.append({"name": "promotion", "passed": promoted or not settings.REQUIRE_PROMOTION_FOR_LIVE,
                   "detail": "Promotion criteria met" if promoted
                   else "Paper promotion criteria not met yet"})
    checks.append({"name": "agent_enabled", "passed": bool(profile.bot_enabled),
                   "detail": "Trading agent enabled"})
    rs_ok = False
    async with AsyncSessionLocal() as db:
        from app.models import RiskSettings

        rs = (await db.execute(
            select(RiskSettings).where(RiskSettings.profile_id == profile.id)
        )).scalar_one_or_none()
        rs_ok = rs is not None
        checks.append({"name": "limits_configured", "passed": rs_ok,
                       "detail": "Risk settings exist" if rs_ok else "Risk settings missing"})
        checks.append({"name": "spot_margin", "passed": bool(rs and rs.spot_margin_enabled),
                       "detail": "Spot & margin permission granted" if (rs and rs.spot_margin_enabled)
                       else "Spot & margin trading disabled"})
    venue_ok = bool(profile.wallet_connected) or bool(profile.wallet_address)
    checks.append({"name": "venue_connected", "passed": venue_ok,
                   "detail": "Wallet or CEX venue configured" if venue_ok
                   else "No wallet/API keys connected"})

    failures = [c for c in checks if not c["passed"]]
    return {"ready": not failures, "checks": checks,
            "failures": [f"{c['name']}: {c['detail']}" for c in failures]}
