from typing import Optional, Dict, Any
from decimal import Decimal
import math


def kelly_criterion(
    win_probability: float,
    win_loss_ratio: float,
    kelly_fraction: float = 0.25  # Conservative: use 25% of Kelly
) -> float:
    """
    Calculate Kelly Criterion position size fraction.
    
    Args:
        win_probability: Probability of winning (0-1)
        win_loss_ratio: Average win / average loss
        kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)
    
    Returns:
        Optimal position size as fraction of capital (0-1)
    """
    if win_probability <= 0 or win_probability >= 1:
        return 0.0
    if win_loss_ratio <= 0:
        return 0.0
    
    kelly = (win_probability * win_loss_ratio - (1 - win_probability)) / win_loss_ratio
    return max(0.0, min(kelly * kelly_fraction, 0.25))  # Cap at 25%


def calculate_position_size(
    balance: float,
    max_allocation_pct: float,
    risk_pct: float,
    confidence: float,
    entry_price: float,
    stop_loss: float
) -> float:
    """
    Calculate position size based on risk management.
    
    Args:
        balance: Available balance
        max_allocation_pct: Max allocation per trade (%)
        risk_pct: Risk per trade (% of balance)
        confidence: Trade confidence (0-1)
        entry_price: Entry price
        stop_loss: Stop loss price
    
    Returns:
        Position size in base currency
    """
    if entry_price <= 0 or stop_loss <= 0:
        return 0.0
    
    # Risk-based sizing
    risk_amount = balance * (risk_pct / 100)
    price_risk = abs(entry_price - stop_loss) / entry_price
    
    if price_risk <= 0:
        return 0.0
    
    risk_based_size = risk_amount / price_risk
    
    # Allocation-based sizing
    max_position = balance * (max_allocation_pct / 100)
    
    # Apply confidence scaling
    confidence_factor = min(confidence, 1.0)
    
    # Take minimum of risk-based and allocation-based, scaled by confidence
    position_size = min(risk_based_size, max_position) * confidence_factor
    
    return max(0.0, position_size)


def calculate_pnl(
    entry_price: float,
    current_price: float,
    size: float,
    side: str  # "buy" or "sell"
) -> float:
    """Calculate unrealized PnL"""
    if side == "buy":
        return (current_price - entry_price) * size
    else:
        return (entry_price - current_price) * size


def calculate_sharpe(returns: list, risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio from returns series"""
    if len(returns) < 2:
        return 0.0
    
    mean_return = sum(returns) / len(returns)
    std_return = math.sqrt(sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1))
    
    if std_return == 0:
        return 0.0
    
    return (mean_return - risk_free_rate / 252) / std_return * math.sqrt(252)


def calculate_max_drawdown(equity_curve: list) -> float:
    """Calculate maximum drawdown from equity curve"""
    if not equity_curve:
        return 0.0
    
    peak = equity_curve[0]
    max_dd = 0.0
    
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak
        max_dd = max(max_dd, dd)
    
    return max_dd


def calculate_sortino(returns: list, risk_free_rate: float = 0.02) -> float:
    """Calculate Sortino ratio (downside deviation only)"""
    if len(returns) < 2:
        return 0.0
    
    mean_return = sum(returns) / len(returns)
    downside_returns = [r for r in returns if r < 0]
    
    if not downside_returns:
        return float('inf') if mean_return > 0 else 0.0
    
    downside_std = math.sqrt(sum(r ** 2 for r in downside_returns) / len(downside_returns))
    
    if downside_std == 0:
        return 0.0
    
    return (mean_return - risk_free_rate / 252) / downside_std * math.sqrt(252)


def atr(high: list, low: list, close: list, period: int = 14) -> float:
    """Calculate Average True Range"""
    if len(high) < period + 1:
        return 0.0
    
    true_ranges = []
    for i in range(1, len(close)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
        true_ranges.append(tr)
    
    return sum(true_ranges[-period:]) / period


def rsi(prices: list, period: int = 14) -> float:
    """Calculate Relative Strength Index"""
    if len(prices) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def ema(prices: list, period: int) -> float:
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return sum(prices) / len(prices)
    
    multiplier = 2 / (period + 1)
    ema_value = sum(prices[:period]) / period
    
    for price in prices[period:]:
        ema_value = (price - ema_value) * multiplier + ema_value
    
    return ema_value


def validate_trade_risk(
    balance: float,
    position_size: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    max_allocation_pct: float,
    max_drawdown_pct: float,
    current_drawdown: float = 0,
    open_positions: int = 0,
    max_concurrent: int = 3
) -> Dict[str, Any]:
    """
    Comprehensive trade risk validation.
    
    Returns:
        Dict with 'approved': bool, 'reason': str, 'adjusted_size': float
    """
    # Check max concurrent trades
    if open_positions >= max_concurrent:
        return {"approved": False, "reason": f"Max concurrent trades ({max_concurrent}) reached", "adjusted_size": 0}
    
    # Check max allocation
    position_value = position_size * entry_price
    allocation_pct = (position_value / balance) * 100
    if allocation_pct > max_allocation_pct:
        adjusted_size = (balance * max_allocation_pct / 100) / entry_price
        return {"approved": True, "reason": f"Size reduced to max allocation", "adjusted_size": adjusted_size}
    
    # Check drawdown limit
    if current_drawdown >= max_drawdown_pct:
        return {"approved": False, "reason": f"Daily drawdown limit ({max_drawdown_pct}%) reached", "adjusted_size": 0}
    
    # Validate stop loss and take profit
    if stop_loss >= entry_price:
        return {"approved": False, "reason": "Stop loss must be below entry for long", "adjusted_size": 0}
    if take_profit <= entry_price:
        return {"approved": False, "reason": "Take profit must be above entry for long", "adjusted_size": 0}
    
    # Risk/reward check
    risk = entry_price - stop_loss
    reward = take_profit - entry_price
    if reward / risk < 1.5:
        return {"approved": False, "reason": "Risk/reward ratio below 1.5", "adjusted_size": 0}
    
    return {"approved": True, "reason": "Risk checks passed", "adjusted_size": position_size}