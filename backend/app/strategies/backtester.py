"""Vectorized backtester — real simulation, real metrics.

Replaces the fabricated legacy metrics (Sharpe = return/10, hardcoded 75%
win rate). Signal strategy: SMA-cross (fast/slow). Costs: proportional fee
per side. Annualization is per-interval via `core.statistics` — crypto is
24/7, never 252.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.core import indicators as ind
from app.core.statistics import (
    calmar_ratio,
    conditional_var,
    periods_per_year,
    profit_factor,
    sample_mean,
    sample_std,
    sharpe_ratio,
    sortino_ratio,
    value_at_risk,
)

DEFAULT_FEE_PCT = 0.001  # 10 bps per side (typical taker)


def timeframe_to_seconds(timeframe: str) -> int:
    unit = timeframe[-1] if timeframe else "h"
    try:
        n = int(timeframe[:-1])
    except ValueError:
        n = 1
    return n * {"m": 60, "h": 3600, "d": 86400, "w": 7 * 86400}.get(unit, 3600)


def sma_cross_signals(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.Series:
    """1 = long entry, -1 = exit-to-flat. Long-only."""
    close = df["close"]
    fast_ma = ind.sma(close, fast)
    slow_ma = ind.sma(close, slow)
    cross_up = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
    cross_down = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
    signal = pd.Series(0, index=df.index, dtype=int)
    signal[cross_up] = 1
    signal[cross_down] = -1
    return signal.fillna(0)


def simulate(df: pd.DataFrame, signals: pd.Series, *, initial_capital: float = 10_000.0,
             fee_pct: float = DEFAULT_FEE_PCT, allocation: float = 1.0) -> Dict:
    """Event-loop long-only simulation.

    `signals` uses 1 (enter) / -1 (exit) / 0 (hold). Entries are all-in on the
    allocation fraction; exits are all-out. Both pay the fee.
    """
    close = df["close"].astype(float).to_numpy()
    n = len(close)
    if n < 3 or len(signals) != n:
        return {"error": "insufficient data or signal length mismatch"}

    equity = float(initial_capital)
    cash = float(initial_capital)
    position_units = 0.0
    peak = equity
    max_dd = 0.0
    curve: List[float] = [equity]
    trades: List[Dict] = []
    entry_price = 0.0
    entry_idx = 0
    fees_paid = 0.0

    sig = signals.astype(int).to_numpy()
    for i in range(1, n):
        price = close[i]
        s = sig[i]
        if s == 1 and position_units == 0 and price > 0:
            gross = cash * allocation
            fee = gross * fee_pct
            fees_paid += fee
            cash -= gross
            position_units = (gross - fee) / price
            entry_price = price
            entry_idx = i
        elif s == -1 and position_units > 0 and price > 0:
            gross = position_units * price
            fee = gross * fee_pct
            fees_paid += fee
            cash += gross - fee
            pnl = (price - entry_price) * position_units - fee - (
                position_units * entry_price * fee_pct
            )
            trades.append({
                "entry_index": entry_idx,
                "exit_index": i,
                "entry_price": float(entry_price),
                "exit_price": float(price),
                "size": float(position_units),
                "pnl": float(pnl),
                "return_pct": float((price - entry_price) / entry_price * 100.0) if entry_price else 0.0,
            })
            position_units = 0.0
            entry_price = 0.0
        mark = position_units * price if position_units > 0 else 0.0
        equity = cash + mark
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
        curve.append(equity)

    # Force-flat mark at the last close so open trades appear in trade stats.
    final_price = close[-1]
    if position_units > 0 and final_price > 0:
        gross = position_units * final_price
        fee = gross * fee_pct
        fees_paid += fee
        cash += gross - fee
        pnl = (final_price - entry_price) * position_units - fee - (
            position_units * entry_price * fee_pct
        )
        trades.append({
            "entry_index": entry_idx,
            "exit_index": n - 1,
            "entry_price": float(entry_price),
            "exit_price": float(final_price),
            "size": float(position_units),
            "pnl": float(pnl),
            "return_pct": float((final_price - entry_price) / entry_price * 100.0) if entry_price else 0.0,
        })
        position_units = 0.0
        equity = cash
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
        curve[-1] = equity

    trade_returns = [t["return_pct"] / 100.0 for t in trades]
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    total_return = (equity - initial_capital) / initial_capital if initial_capital else 0.0
    interval_seconds = 3600  # caller may re-derive; stored via equity path below

    return {
        "initial_capital": float(initial_capital),
        "final_capital": float(equity),
        "total_return_pct": float(total_return * 100.0),
        "max_drawdown_pct": float(max_dd * 100.0),
        "sharpe_ratio": float(sharpe_ratio(trade_returns, interval_seconds=interval_seconds)) if len(trade_returns) >= 2 else 0.0,
        "sortino_ratio": float(sortino_ratio(trade_returns, interval_seconds=interval_seconds)) if len(trade_returns) >= 2 else 0.0,
        "calmar_ratio": float(calmar_ratio(curve, interval_seconds=interval_seconds)),
        "var_95": float(value_at_risk(trade_returns, 0.95)) if trade_returns else 0.0,
        "cvar_95": float(conditional_var(trade_returns, 0.95)) if trade_returns else 0.0,
        "win_rate_pct": float(wins / len(trades) * 100.0) if trades else 0.0,
        "wins": wins,
        "losses": losses,
        "total_trades": len(trades),
        "profit_factor": float(profit_factor(trade_returns)) if trade_returns else None,
        "fees_paid": float(fees_paid),
        "equity_curve": curve,
        "trades": trades,
    }


def run_backtest(df: pd.DataFrame, *, timeframe: str = "1h",
                 initial_capital: float = 10_000.0, fee_pct: float = DEFAULT_FEE_PCT,
                 fast: int = 20, slow: int = 50) -> Dict:
    """SMA-cross backtest over an OHLCV frame with full metric set."""
    if df is None or df.empty or len(df) < slow + 5:
        return {"error": "insufficient OHLCV rows", "total_trades": 0}
    interval_seconds = timeframe_to_seconds(timeframe)
    signals = sma_cross_signals(df, fast=fast, slow=slow)
    result = simulate(df, signals, initial_capital=initial_capital,
                      fee_pct=fee_pct)
    if "error" in result:
        return result

    # Bar-level returns (not just trade returns) for Sharpe — the honest way.
    close = df["close"].astype(float)
    bar_returns = (close / close.shift(1) - 1.0).dropna().tolist()
    # Equity-curve returns capture the actual strategy P&L path.
    curve = result["equity_curve"]
    if len(curve) >= 2:
        eq_returns = [
            (curve[i] / curve[i - 1] - 1.0)
            for i in range(1, len(curve))
            if curve[i - 1] > 0
        ]
    else:
        eq_returns = []
    result["sharpe_ratio"] = float(sharpe_ratio(eq_returns, interval_seconds=interval_seconds)) if len(eq_returns) >= 2 else 0.0
    result["sortino_ratio"] = float(sortino_ratio(eq_returns, interval_seconds=interval_seconds)) if len(eq_returns) >= 2 else 0.0
    result["calmar_ratio"] = float(calmar_ratio(curve, interval_seconds=interval_seconds))
    result["benchmark_sharpe"] = float(sharpe_ratio(bar_returns, interval_seconds=interval_seconds)) if len(bar_returns) >= 2 else 0.0
    result["timeframe"] = timeframe
    result["interval_seconds"] = interval_seconds
    result["periods_per_year"] = periods_per_year(interval_seconds)
    return result
