"""Vectorized technical indicators on OHLCV dataframes.

Shared by Engine A enrichment, dexwatch spike z-scores, and the backtester
so the three never disagree on what an ATR or a Bollinger band means.
Wilder's smoothing is used for ATR/RSI/ADX (the original definition); the
plain-EMA variants in `core.math_helpers` stay for scalar fallback paths.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def _require_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    needed = {"open", "high", "low", "close", "volume"}
    if df is None or df.empty or not needed.issubset(set(df.columns)):
        return pd.DataFrame()
    return df


def sma(close: pd.Series, period: int = 20) -> pd.Series:
    return close.rolling(window=period, min_periods=period).mean()


def ema(close: pd.Series, period: int = 20) -> pd.Series:
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> Dict[str, pd.Series]:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    line = ema_fast - ema_slow
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return {"macd": line, "signal": signal_line, "hist": line - signal_line}


def bollinger(close: pd.Series, period: int = 20,
              num_std: float = 2.0) -> Dict[str, pd.Series]:
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    bandwidth = (upper - lower) / mid.replace(0, np.nan)
    # %B = (price - lower) / (upper - lower); 0 at the band, 1 above it.
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    return {
        "middle": mid, "upper": upper, "lower": lower,
        "bandwidth": bandwidth, "pct_b": pct_b,
    }


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range with Wilder's RMA smoothing."""
    tr = true_range(df)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index with Wilder's smoothing."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    index = 100 - (100 / (1 + rs))
    # Flat series (avg_loss == 0) → RSI 100; both zero → 50 neutral.
    index = index.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    index = index.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return index.fillna(50.0)


def adx(df: pd.DataFrame, period: int = 14) -> Dict[str, pd.Series]:
    """ADX / +DI / -DI via Wilder's smoothing."""
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move
    atr_vals = atr(df, period)
    alpha = 1.0 / period
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr_vals.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr_vals.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0.0)
    adx_line = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    return {"adx": adx_line, "plus_di": plus_di.fillna(0.0), "minus_di": minus_di.fillna(0.0)}


def vwap(df: pd.DataFrame, period: Optional[int] = None) -> pd.Series:
    """Rolling VWAP over `period` bars (None = expanding)."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"]
    if period is None:
        cum_pv = pv.cumsum()
        cum_v = df["volume"].cumsum()
    else:
        cum_pv = pv.rolling(window=period, min_periods=1).sum()
        cum_v = df["volume"].rolling(window=period, min_periods=1).sum()
    return cum_pv / cum_v.replace(0.0, np.nan)


def rolling_zscore(series: pd.Series, period: int = 20) -> pd.Series:
    """(x − mean) / std over a rolling window — for spike detection."""
    mean = series.rolling(window=period, min_periods=max(2, period // 2)).mean()
    std = series.rolling(window=period, min_periods=max(2, period // 2)).std(ddof=0)
    return ((series - mean) / std.replace(0.0, np.nan)).fillna(0.0)


def atr_levels(df: pd.DataFrame, side: str = "buy", atr_period: int = 14,
               sl_mult: float = 2.0, tp_mult: float = 3.0) -> Optional[Dict[str, float]]:
    """ATR-based stop-loss / take-profit off the last close."""
    frame = _require_ohlcv(df)
    if frame.empty or len(frame) < atr_period + 2:
        return None
    last_close = float(frame["close"].iloc[-1])
    atr_series = atr(frame, period=atr_period)
    atr_last = atr_series.iloc[-1]
    if atr_last is None or not np.isfinite(atr_last) or atr_last <= 0:
        return None
    atr_last = float(atr_last)
    if side == "buy":
        return {
            "stop_loss": last_close - sl_mult * atr_last,
            "take_profit": last_close + tp_mult * atr_last,
            "atr": atr_last,
        }
    return {
        "stop_loss": last_close + sl_mult * atr_last,
        "take_profit": last_close - tp_mult * atr_last,
        "atr": atr_last,
    }


def enrich_frame(df: pd.DataFrame) -> pd.DataFrame:
    """One-call envelope: the indicator series the engines/prompts consume."""
    frame = _require_ohlcv(df)
    if frame.empty:
        return frame
    out = frame.copy()
    out["sma_20"] = sma(out["close"], 20)
    out["ema_20"] = ema(out["close"], 20)
    out["rsi_14"] = rsi(out["close"], 14)
    out["atr_14"] = atr(out, 14)
    bb = bollinger(out["close"], 20)
    out["bb_upper"] = bb["upper"]
    out["bb_lower"] = bb["lower"]
    out["bb_pct_b"] = bb["pct_b"]
    out["bb_bandwidth"] = bb["bandwidth"]
    macd_vals = macd(out["close"])
    out["macd"] = macd_vals["macd"]
    out["macd_signal"] = macd_vals["signal"]
    out["macd_hist"] = macd_vals["hist"]
    return out


def frame_snapshot(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """Last-bar scalar view for prompts/audit (None when not computable)."""
    frame = _require_ohlcv(df)
    if frame.empty:
        return {}
    enriched = enrich_frame(frame)

    def _f(key: str) -> Optional[float]:
        if key not in enriched.columns:
            return None
        val = enriched[key].iloc[-1]
        try:
            fval = float(val)
        except (TypeError, ValueError):
            return None
        return fval if np.isfinite(fval) else None

    return {
        "close": _f("close"),
        "sma_20": _f("sma_20"),
        "ema_20": _f("ema_20"),
        "rsi_14": _f("rsi_14"),
        "atr_14": _f("atr_14"),
        "bb_upper": _f("bb_upper"),
        "bb_lower": _f("bb_lower"),
        "bb_pct_b": _f("bb_pct_b"),
        "macd": _f("macd"),
        "macd_signal": _f("macd_signal"),
    }
