"""
Freqtrade Strategy Adapter
Adapted from E:/Projects/finance-repos/freqtrade
Provides strategy base classes and indicators for Aegis Quant.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy."""
    name: str
    timeframe: str = "1h"
    stake_currency: str = "USDT"
    stake_amount: float = 100.0
    max_open_trades: int = 3
    stoploss: float = -0.05
    trailing_stop: bool = False
    trailing_stop_positive: Optional[float] = None
    trailing_stop_positive_offset: Optional[float] = None
    use_custom_stoploss: bool = False
    process_only_new_candles: bool = True
    order_types: Dict = None
    order_time_in_force: Dict = None
    stake_amount_config: str = "fixed"
    profit_target: Dict = None


class BaseStrategy:
    """
    Base strategy class adapted from Freqtrade.
    Provides common indicators and helper methods.
    """
    
    # Class variables - customize these in subclass
    timeframe = "1h"
    stoploss = -0.05
    trailing_stop = False
    
    #populate_indicators
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Add indicators to the dataframe.
        Override this method in your strategy.
        """
        # Default indicators
        dataframe['sma_20'] = dataframe['close'].rolling(20).mean()
        dataframe['sma_50'] = dataframe['close'].rolling(50).mean()
        dataframe['sma_200'] = dataframe['close'].rolling(200).mean()
        dataframe['ema_12'] = dataframe['close'].ewm(span=12, adjust=False).mean()
        dataframe['ema_26'] = dataframe['close'].ewm(span=26, adjust=False).mean()
        
        # RSI
        dataframe['rsi'] = self._calculate_rsi(dataframe['close'], 14)
        
        # MACD
        dataframe['macd'] = dataframe['ema_12'] - dataframe['ema_26']
        dataframe['macd_signal'] = dataframe['macd'].ewm(span=9, adjust=False).mean()
        dataframe['macd_hist'] = dataframe['macd'] - dataframe['macd_signal']
        
        # Bollinger Bands
        bollinger = dataframe['close'].rolling(20).std()
        dataframe['bb_upper'] = dataframe['sma_20'] + (bollinger * 2)
        dataframe['bb_lower'] = dataframe['sma_20'] - (bollinger * 2)
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['sma_20']
        
        # Volume indicators
        dataframe['volume_sma'] = dataframe['volume'].rolling(20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # ATR
        dataframe['atr'] = self._calculate_atr(dataframe, 14)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Define entry signals.
        Override this method in your strategy.
        """
        dataframe.loc[:, 'enter_long'] = 0
        return dataframe
    
    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Define exit signals.
        Override this method in your strategy.
        """
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe
    
    # Helper methods
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_atr(self, dataframe: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ATR indicator."""
        high = dataframe['high']
        low = dataframe['low']
        close = dataframe['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _calculate_macd(self, prices: pd.Series) -> Dict:
        """Calculate MACD indicators."""
        ema12 = prices.ewm(span=12, adjust=False).mean()
        ema26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return {"macd": macd, "signal": signal, "histogram": hist}


class SMACrossStrategy(BaseStrategy):
    """Simple Moving Average Crossover Strategy."""
    
    timeframe = "1h"
    
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Entry: Golden cross (SMA 20 > SMA 50)."""
        dataframe.loc[
            (dataframe['sma_20'] > dataframe['sma_50']) &
            (dataframe['sma_20'].shift(1) <= dataframe['sma_50'].shift(1)) &
            (dataframe['rsi'] < 70),
            'enter_long'] = 1
        return dataframe
    
    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Exit: Death cross (SMA 20 < SMA 50)."""
        dataframe.loc[
            (dataframe['sma_20'] < dataframe['sma_50']) &
            (dataframe['sma_20'].shift(1) >= dataframe['sma_50'].shift(1)) |
            (dataframe['rsi'] > 80),
            'exit_long'] = 1
        return dataframe


class RSIReversalStrategy(BaseStrategy):
    """RSI Reversal Strategy."""
    
    timeframe = "1h"
    
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Entry: RSI oversold."""
        dataframe.loc[
            (dataframe['rsi'] < 30) &
            (dataframe['close'] > dataframe['sma_50']),
            'enter_long'] = 1
        return dataframe
    
    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Exit: RSI overbought."""
        dataframe.loc[
            (dataframe['rsi'] > 70) |
            (dataframe['close'] < dataframe['sma_50']),
            'exit_long'] = 1
        return dataframe


class BollingerBreakoutStrategy(BaseStrategy):
    """Bollinger Band Breakout Strategy."""
    
    timeframe = "1h"
    
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Entry: Price breaks above upper band."""
        dataframe.loc[
            (dataframe['close'] > dataframe['bb_upper']) &
            (dataframe['bb_width'] < dataframe['bb_width'].rolling(20).mean()),
            'enter_long'] = 1
        return dataframe
    
    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Exit: Price touches lower band or RSI overbought."""
        dataframe.loc[
            (dataframe['close'] < dataframe['bb_lower']) |
            (dataframe['rsi'] > 75),
            'exit_long'] = 1
        return dataframe


class VolatilitySqueezeStrategy(BaseStrategy):
    """Volatility Squeeze Strategy (TTM Squeeze inspired)."""
    
    timeframe = "1h"
    
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Entry: Volatility squeeze breakout."""
        # KB width (Keltner Band width)
        atr = self._calculate_atr(dataframe, 20)
        kc_upper = dataframe['sma_20'] + (atr * 1.5)
        kc_lower = dataframe['sma_20'] - (atr * 1.5)
        
        dataframe.loc[
            (dataframe['close'] > kc_upper) &
            (dataframe['bb_width'] < dataframe['bb_width'].rolling(50).mean()) &
            (dataframe['volume_ratio'] > 1.5),
            'enter_long'] = 1
        return dataframe
    
    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Exit: Price returns to mean."""
        dataframe.loc[
            (dataframe['close'] < dataframe['sma_20']) |
            (dataframe['rsi'] > 75),
            'exit_long'] = 1
        return dataframe


# 

# Strategy registry
STRATEGIES = {
    "sma_cross": SMACrossStrategy,
    "rsi_reversal": RSIReversalStrategy,
    "bollinger_breakout": BollingerBreakoutStrategy,
    "volatility_squeeze": VolatilitySqueezeStrategy,
}


def get_strategy(name: str):
    """Get strategy by name."""
    return STRATEGIES.get(name.lower())


def list_strategies():
    """List available strategies."""
    return list(STRATEGIES.keys())
