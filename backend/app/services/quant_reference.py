"""Deterministic quant-formula digest for LLM signal prompts.

The reference link-sheet (wzchen probability, CMU stochastic notes, CS229
ML-for-quants, QuantEcon) is absorbed here as a short, curated set of rules —
not a Wikipedia dump. Prompts stay cheap: each entry is a few lines the model
can cite when reasoning about volatility, stationarity, or sizing.
"""
from __future__ import annotations

DIGEST = """\
Quant reference (use these consistently; do not invent other formulas):
- Sharpe = mean(excess return) / std(return) × sqrt(annualization); crypto annualizes at sqrt(24×365), NOT sqrt(252).
- Sortino uses downside deviation only (std of negative returns over the full sample).
- Win-rate confidence: Wilson score interval — a 55% hit rate over 12 trades includes 50%.
- GARCH(1,1) forecasts conditional variance; rising sigma means wider stops, smaller size.
- ADF p-value < 0.05 ⇒ price series is mean-reverting (fades ok); p > 0.05 ⇒ trending (breakouts ok).
- Hurst H ≈ 0.5 random walk; H > 0.5 trending; H < 0.5 mean-reverting.
- ATR multiple stop: stop = entry ∓ k×ATR, k ≈ 2–3; take profit ≈ 1.5–2× the risk.
- Bollinger %B: below 0 = under lower band (oversold zone); above 1 = overbought.
- VaR 95%: the 5th-percentile loss on a single trade; reject if the tail is > ~15% of margin.
- Kelly: f* = (p·b − q)/b; use quarter-Kelly (f*/4) for sizing, cap at 25%.
- Spearman IC between forecast probability and realised return > 0.05 is meaningful signal;
  IC ≈ 0 means the model ranks random.
- Cointegration (Engle-Granger p < 0.05) means two assets' spread is mean-reverting — pairs trades ok.
"""


def prompt_block() -> str:
    return DIGEST


def compact_block() -> str:
    """Short form for token-tight signal parsers."""
    return (
        "Quant rules: Sharpe annualizes at sqrt(24*365) for crypto; "
        "use Wilson intervals for win rates; ATR-based stops (k=2-3); "
        "quarter-Kelly sizing capped at 25%; IC>0.05 = real signal; "
        "VaR95 tail >15% of margin = reject."
    )
