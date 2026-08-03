"""
AEGIS QUANT - SUPERCHARGED AI TRADING ENGINE
=============================================
Multi-engine architecture with:
- Gemini Flash LLM for all analysis
- CCXT for exchange integration (100+ exchanges)
- VectorBT for fast backtesting
- Multi-agent decision making
- Live execution with risk management
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
import numpy as np

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Profile, Position, TradeLog, OrderSide, OrderStatus, ExecutionType
from app.core.encryption import decrypt_credentials
from app.services.kronos_service import get_kronos_client, KronosService
from app.engines.gemini_client import get_gemini_client
from app.services.market_service import get_market_service
from app.services.kronos_service import KronosService
from app.services.source_registry import get_all_sources, SourceType

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Response Models ──────────────────────────────────────────────────

class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"

@dataclass
class TradingDecision:
    """Final trading decision from multi-agent analysis."""
    symbol: str
    action: Action
    confidence: float  # 0-100
    reason: str
    position_size: float  # USD
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "action": self.action.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "position_size": self.position_size,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "timestamp": self.timestamp.isoformat(),
        }

@dataclass
class AnalystReport:
    """Report from a single analyst agent."""
    analyst_name: str
    symbol: str
    recommendation: Action
    confidence: float
    reasoning: str
    key_factors: List[str]

@dataclass
class EnsembleDecision:
    """Consensus decision from all analysts."""
    symbol: str
    action: Action
    avg_confidence: float
    unanimous: bool
    analyst_reports: List[AnalystReport]
    final_reasoning: str

# ── LLM-Powered Analyst Agents ───────────────────────────────────────

class TechnicalAnalyst:
    """Gemini-powered technical analysis agent."""
    
    ANALYST_NAME = "Technical Analyst"
    
    def __init__(self):
        self.gemini = get_gemini_client()
    
    async def analyze(self, symbol: str, df: pd.DataFrame, position: Optional[Position] = None) -> AnalystReport:
        """Analyze price action and generate trading signal."""
        try:
            # Calculate indicators
            df['ma_20'] = df['close'].rolling(20).mean()
            df['ma_50'] = df['close'].rolling(50).mean()
            df['rsi'] = self._calculate_rsi(df['close'], 14)
            df['macd'] = df['close'].ewm(span=12).mean() - df['close'].ewm(span=26).mean()
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['bb_upper'] = df['close'].rolling(20).mean() + 2 * df['close'].rolling(20).std()
            df['bb_lower'] = df['close'].rolling(20).mean() - 2 * df['close'].rolling(20).std()
            
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            # Prepare analysis prompt for Gemini
            prompt = f"""Analyze this {symbol} market data and provide a trading recommendation.

Current Price: ${latest['close']:.2f}
20-day MA: ${latest['ma_20']:.2f}
50-day MA: ${latest['ma_50']:.2f}
RSI (14): {latest['rsi']:.1f}
MACD: {latest['macd']:.4f}
MACD Signal: {latest['macd_signal']:.4f}
Bollinger Upper: ${latest['bb_upper']:.2f}
Bollinger Lower: ${latest['bb_lower']:.2f}
24h Change: {(latest['close']/prev['close']-1)*100:.2f}%

Existing Position: {position.symbol if position else 'None'}

Based on technical analysis, provide:
1. Recommendation: BUY, SELL, or HOLD
2. Confidence (0-100)
3. Key technical factors
4. Suggested stop loss and take profit levels

Return JSON: {{"recommendation": "BUY/SELL/HOLD", "confidence": 75, "reasoning": "...", "key_factors": [...], "stop_loss": 95.5, "take_profit": 105.2}}"""

            response = await self.gemini.generate(prompt)
            decision = self._parse_response(response.text, symbol)
            
            return AnalystReport(
                analyst_name=self.ANALYST_NAME,
                symbol=symbol,
                recommendation=Action(decision.get('recommendation', 'HOLD')),
                confidence=float(decision.get('confidence', 50)),
                reasoning=decision.get('reasoning', ''),
                key_factors=decision.get('key_factors', []),
            )
        except Exception as e:
            logger.error(f"Technical analysis failed for {symbol}: {e}")
            return AnalystReport(
                analyst_name=self.ANALYST_NAME,
                symbol=symbol,
                recommendation=Action.HOLD,
                confidence=0,
                reasoning=f"Analysis error: {str(e)}",
                key_factors=[],
            )
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs)).iloc[-1] if len(prices) > period else 50
    
    def _parse_response(self, text: str, symbol: str) -> Dict:
        """Parse Gemini JSON response."""
        try:
            # Extract JSON from response
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                json_str = text[start:end+1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        # Fallback
        return {
            "recommendation": "HOLD",
            "confidence": 50,
            "reasoning": "Could not parse technical analysis",
            "key_factors": [],
        }


class SentimentAnalyst:
    """Gemini-powered sentiment analysis agent."""
    
    ANALYST_NAME = "Sentiment Analyst"
    
    def __init__(self):
        self.gemini = get_gemini_client()
    
    async def analyze(self, symbol: str, signals: List) -> AnalystReport:
        """Analyze social sentiment for a symbol."""
        try:
            # Prepare sentiment prompt
            recent_signals = signals[:10] if signals else []
            signal_text = "\n".join([f"- {s.ticker}: {s.raw_text[:100]} (sentiment: {s.sentiment:.2f})" 
                                    for s in recent_signals if s.ticker == symbol])
            
            if not signal_text:
                return AnalystReport(
                    analyst_name=self.ANALYST_NAME,
                    symbol=symbol,
                    recommendation=Action.HOLD,
                    confidence=0,
                    reasoning="No social signals found",
                    key_factors=[],
                )
            
            prompt = f"""Analyze crypto market sentiment for {symbol}.

Recent social signals:
{signal_text}

Based on social sentiment analysis, provide:
1. Recommendation: BUY, SELL, or HOLD
2. Confidence (0-100)
3. Sentiment summary
4. Key social factors

Return JSON: {{"recommendation": "BUY/SELL/HOLD", "confidence": 65, "reasoning": "...", "key_factors": [...]}}"""

            response = await self.gemini.generate(prompt)
            decision = self._parse_response(response.text, symbol)
            
            return AnalystReport(
                analyst_name=self.ANALYST_NAME,
                symbol=symbol,
                recommendation=Action(decision.get('recommendation', 'HOLD')),
                confidence=float(decision.get('confidence', 50)),
                reasoning=decision.get('reasoning', ''),
                key_factors=decision.get('key_factors', []),
            )
        except Exception as e:
            logger.error(f"Sentiment analysis failed for {symbol}: {e}")
            return AnalystReport(
                analyst_name=self.ANALYST_NAME,
                symbol=symbol,
                recommendation=Action.HOLD,
                confidence=0,
                reasoning=f"Analysis error: {str(e)}",
                key_factors=[],
            )
    
    def _parse_response(self, text: str, symbol: str) -> Dict:
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                return json.loads(text[start:end+1])
        except:
            pass
        return {"recommendation": "HOLD", "confidence": 50, "reasoning": "Could not parse", "key_factors": []}


class RiskAnalyst:
    """Gemini-powered risk assessment agent."""
    
    ANALYST_NAME = "Risk Analyst"
    
    def __init__(self):
        self.gemini = get_gemini_client()
    
    async def assess(self, symbol: str, decision: TradingDecision, portfolio_value: float) -> AnalystReport:
        """Assess risk for a proposed trade."""
        try:
            prompt = f"""Assess the risk of this proposed trade.

Symbol: {symbol}
Proposed Action: {decision.action.value}
Position Size: ${decision.position_size:.2f}
Stop Loss: ${decision.stop_loss:.2f} if provided
Take Profit: ${decision.take_profit:.2f} if provided
Portfolio Value: ${portfolio_value:.2f}
Confidence: {decision.confidence:.1f}%

Calculate:
1. Risk-reward ratio
2. Maximum loss as % of portfolio
3. Overall risk assessment
4. Recommendation: APPROVE, MODIFY, or REJECT

Return JSON: {{"recommendation": "APPROVE/MODIFY/REJECT", "confidence": 80, "reasoning": "...", "suggested_stop_loss": 95.0, "suggested_take_profit": 105.0, "risk_percent": 2.5}}"""

            response = await self.gemini.generate(prompt)
            assessment = self._parse_response(response.text)
            
            # Update decision based on risk assessment
            if assessment.get('recommendation') == 'REJECT':
                decision.confidence = 0
            
            return AnalystReport(
                analyst_name=self.ANALYST_NAME,
                symbol=symbol,
                recommendation=Action.HOLD,  # Risk analyst doesn't decide direction
                confidence=float(assessment.get('confidence', 50)),
                reasoning=assessment.get('reasoning', ''),
                key_factors=[f"Risk: {assessment.get('risk_percent', 'N/A')}%"],
            )
        except Exception as e:
            logger.error(f"Risk assessment failed for {symbol}: {e}")
            return AnalystReport(
                analyst_name=self.ANALYST_NAME,
                symbol=symbol,
                recommendation=Action.HOLD,
                confidence=0,
                reasoning=f"Assessment error: {str(e)}",
                key_factors=[],
            )
    
    def _parse_response(self, text: str) -> Dict:
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                return json.loads(text[start:end+1])
        except:
            pass
        return {"recommendation": "APPROVE", "confidence": 50, "reasoning": "Could not parse", "risk_percent": 0}


class PortfolioManager:
    """Final decision ensembler and portfolio manager."""
    
    async def make_decision(self, symbol: str, reports: List[AnalystReport], 
                           portfolio_value: float) -> EnsembleDecision:
        """Ensemble all analyst reports into final decision."""
        # Count votes
        buy_count = sum(1 for r in reports if r.recommendation == Action.BUY)
        sell_count = sum(1 for r in reports if r.recommendation == Action.SELL)
        hold_count = sum(1 for r in reports if r.recommendation == Action.HOLD)
        
        total = len(reports)
        
        # Determine consensus action
        if buy_count > sell_count and buy_count >= hold_count:
            action = Action.BUY
        elif sell_count > buy_count and sell_count >= hold_count:
            action = Action.SELL
        else:
            action = Action.HOLD
        
        # Calculate average confidence
        avg_confidence = sum(r.confidence for r in reports) / total if total > 0 else 0
        
        # Check for unanimity
        unanimous = buy_count == total or sell_count == total or hold_count == total
        
        # Generate final reasoning
        reasoning = f"Consensus: {buy_count} buy, {sell_count} sell, {hold_count} hold"
        
        return EnsembleDecision(
            symbol=symbol,
            action=action,
            avg_confidence=avg_confidence,
            unanimous=unanimous,
            analyst_reports=reports,
            final_reasoning=reasoning,
        )


# ── Main Trading Engine ──────────────────────────────────────────────

class AegisEngine:
    """Supercharged AI Trading Engine with Gemini Flash."""
    
    def __init__(self):
        self.settings = get_settings()
        self.market = get_market_service()
        self.kronos = KronosService()
        self.gemini = get_gemini_client()
        
        # Analyst agents
        self.technical = TechnicalAnalyst()
        self.sentiment = SentimentAnalyst()
        self.risk = RiskAnalyst()
        self.portfolio_manager = PortfolioManager()
        
        # Symbols to monitor (CEX)
        self.symbols = ['BTC', 'ETH', 'SOL', 'TON', 'WIF', 'BONK', 'PEPE', 'DOGE']
        
        # Solana tokens to monitor
        self.solana_symbols = ['SOL', 'BONK', 'WIF', 'PEPE', 'DOGE', 'POPCAT', 'BOME', 'TRUMP']
        
        # Import Solana services
        from app.services.jupiter_client import get_jupiter_client, SOL_MINT, USDC_MINT
        from app.services.dexscreener_client import get_dex_client
        self.jupiter = get_jupiter_client()
        self.dex = get_dex_client()
    
    async def run_analysis_cycle(self, profile: Profile):
        """Run one complete analysis cycle for all symbols."""
        logger.info(f"Running analysis cycle for profile {profile.id}")
        
        # Get watchlist
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from app.models import UserWhitelist
            wl = await db.execute(
                select(UserWhitelist).where(UserWhitelist.profile_id == profile.id)
            )
            watchlist = [w.symbol for w in wl.scalars().all()]
        
        symbols = list(set(watchlist + self.symbols))
        
        # Analyze CEX symbols
        for symbol in symbols[:3]:  # Limit to avoid rate limits
            try:
                decision = await self._analyze_symbol(symbol, profile)
                if decision and decision.confidence > 60:
                    await self._execute_decision(profile, decision)
            except Exception as e:
                logger.error(f"Analysis failed for {symbol}: {e}")
        
        # Analyze Solana tokens
        await self._analyze_solana_tokens(profile)
    
    async def _analyze_symbol(self, symbol: str, profile: Profile) -> Optional[TradingDecision]:
        """Run full analysis pipeline for a symbol."""
        # 1. Fetch market data
        try:
            ohlcv = await self.market.fetch_ohlcv(f"{symbol}/USDT", 'binance', '1h', limit=100)
            df = pd.DataFrame(ohlcv)
        except Exception as e:
            logger.warning(f"Failed to fetch market data for {symbol}: {e}")
            return None
        
        # 2. Get Kronos forecast
        try:
            closes = df['close'].tolist()
            forecast = await self.kronos.forecast(closes, horizon=24, samples=10)
            trend = forecast.mean_path[-1] if forecast.mean_path else closes[-1]
        except:
            trend = closes[-1]
        
        # 3. Run technical analysis
        technical_report = await self.technical.analyze(symbol, df)
        
        # 4. Run sentiment analysis (from social signals)
        sentiment_report = await self.sentiment.analyze(symbol, [])
        
        # 5. Get existing position
        existing_position = await self._get_position(profile.id, symbol)
        
        # 6. Create proposed decision
        action = technical_report.recommendation
        confidence = max(technical_report.confidence, sentiment_report.confidence)
        position_size = self._calculate_position_size(confidence, profile.max_allocation_pct)
        
        decision = TradingDecision(
            symbol=symbol,
            action=action,
            confidence=confidence,
            reason=f"Technical: {technical_report.reasoning[:100]}",
            position_size=position_size,
        )
        
        # 7. Risk assessment
        risk_report = await self.risk.assess(symbol, decision, profile.max_allocation_pct)
        
        # 8. Ensemble decision
        reports = [technical_report, sentiment_report, risk_report]
        ensemble = await self.portfolio_manager.make_decision(symbol, reports, profile.max_allocation_pct)
        
        # Update decision with ensemble result
        decision.action = ensemble.action
        decision.confidence = ensemble.avg_confidence
        decision.reason = ensemble.final_reasoning
        
        # Apply risk adjustment
        if risk_report.reasoning and 'REJECT' in risk_report.reasoning.upper():
            decision.confidence = 0
        
        return decision
    
    def _calculate_position_size(self, confidence: float, max_allocation: float) -> float:
        """Calculate position size based on Kelly criterion and confidence."""
        # Simple confidence-weighted position sizing
        base_size = 1000  # $1000 base
        confidence_factor = confidence / 100
        return base_size * min(confidence_factor, max_allocation / 100 * 5)
    
    async def _get_position(self, profile_id, symbol: str) -> Optional[Position]:
        """Get existing position for symbol."""
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from app.models import Position
            result = await db.execute(
                select(Position).where(
                    Position.profile_id == profile_id,
                    Position.symbol == symbol
                )
            )
            return result.scalar_one_or_none()
    
    async def _execute_decision(self, profile: Profile, decision: TradingDecision):
        """Execute trading decision with risk checks."""
        if decision.confidence < 60:
            return
        
        # Check max concurrent trades
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from app.models import Position
            result = await db.execute(
                select(Position).where(Position.profile_id == profile.id)
            )
            open_positions = result.scalars().all()
            
            if len(open_positions) >= profile.max_concurrent_trades:
                logger.info(f"Max positions reached ({len(open_positions)}), skipping {decision.symbol}")
                return
        
        # Execute trade via CCXT
        try:
            await self._execute_trade(profile, decision)
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
    
    async def _execute_trade(self, profile: Profile, decision: TradingDecision):
        """Execute trade via CCXT with encrypted API keys."""
        from app.models import UserCredential
        from sqlalchemy import select
        
        # Get exchange credentials
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserCredential).where(
                    UserCredential.profile_id == profile.id,
                    UserCredential.exchange == 'binance',
                    UserCredential.is_active == True
                )
            )
            cred = result.scalar_one_or_none()
        
        if not cred:
            logger.info(f"No Binance credentials for profile {profile.id}, paper trading only")
            # Paper trade
            await self._paper_trade(profile, decision)
            return
        
        # Decrypt credentials
        decrypted = decrypt_credentials({
            "api_key": cred.encrypted_api_key,
            "api_secret": cred.encrypted_api_secret,
            "passphrase": cred.encrypted_passphrase
        })
        
        # Execute via CCXT
        exchange = ccxt.binance({
            'apiKey': decrypted['api_key'],
            'secret': decrypted['api_secret'],
            'enableRateLimit': True,
        })
        
        try:
            symbol = f"{decision.symbol}/USDT"
            
            if decision.action == Action.BUY:
                order = exchange.create_market_buy_order(symbol, decision.position_size / decision.current_price)
            elif decision.action == Action.SELL:
                order = exchange.create_market_sell_order(symbol, decision.position_size / decision.current_price)
            
            # Log execution
            await self._log_execution(profile, decision, order)
            
        finally:
            await exchange.close()
    
    async def _paper_trade(self, profile: Profile, decision: TradingDecision):
        """Execute paper trade."""
        logger.info(f"Paper trade: {decision.action.value} {decision.symbol} ${decision.position_size:.2f}")
        
        # Save to database
        async with AsyncSessionLocal() as db:
            from app.models import Position, TradeLog
            import uuid
            
            # Update position
            position = Position(
                profile_id=profile.id,
                symbol=decision.symbol,
                exchange='paper',
                side=OrderSide.BUY if decision.action == Action.BUY else OrderSide.SELL,
                size=decision.position_size,
                entry_price=0,  # Would get from market
                current_price=0,
                mode=profile.trading_mode,
            )
            db.add(position)
            
            # Log trade
            trade = TradeLog(
                profile_id=profile.id,
                symbol=decision.symbol,
                exchange='paper',
                side=OrderSide.BUY if decision.action == Action.BUY else OrderSide.SELL,
                execution_type=ExecutionType.PAPER,
                size=decision.position_size,
                price=0,
                total_value_usd=decision.position_size,
                status=OrderStatus.FILLED,
            )
            db.add(trade)
            
            await db.commit()
            logger.info(f"Paper trade executed: {decision.action.value} {decision.symbol}")
    
    async def _analyze_solana_tokens(self, profile: Profile):
        """Analyze and trade Solana chain tokens via Jupiter."""
        logger.info(f"Analyzing Solana tokens for profile {profile.id}")
        
        for symbol in self.solana_symbols[:3]:  # Limit to avoid rate limits
            try:
                # Get market data from DexScreener
                market_data = await self._get_solana_market_data(symbol)
                if not market_data or not market_data.get('price_usd'):
                    continue
                
                # Run AI analysis
                decision = await self._analyze_solana_symbol(symbol, profile, market_data)
                if decision and decision.confidence > 65:
                    await self._execute_solana_trade(profile, decision)
            except Exception as e:
                logger.error(f"Solana analysis failed for {symbol}: {e}")
    
    async def _get_solana_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for Solana token."""
        try:
            # Get from DexScreener
            pairs = await self.dex.get_solana_pairs(symbol)
            if not pairs:
                # Try Jupiter price
                price_data = await self.jupiter.get_price(symbol)
                if price_data:
                    return {'price_usd': price_data.price, 'source': 'jupiter'}
                return None
            
            best_pair = max(pairs, key=lambda p: p.liquidity_usd)
            return {
                'price_usd': best_pair.price_usd,
                'volume_24h': best_pair.volume_24h,
                'liquidity': best_pair.liquidity_usd,
                'source': 'dexscreener',
            }
        except Exception as e:
            logger.error(f"Failed to get Solana market data for {symbol}: {e}")
            return None
    
    async def _analyze_solana_symbol(self, symbol: str, profile: Profile, market_data: Dict) -> Optional[TradingDecision]:
        """Run AI analysis on Solana token."""
        try:
            # Get token mint address
            token_mint = await self.jupiter.get_token_by_symbol(symbol)
            if not token_mint:
                logger.warning(f"Token {symbol} not found on Jupiter")
                return None
            
            # Run technical analysis via Gemini
            prompt = f"""Analyze {symbol} on Solana. Current price: ${market_data.get('price_usd', 0):.6f}
Volume 24h: ${market_data.get('volume_24h', 0):,.0f}
Liquidity: ${market_data.get('liquidity', 0):,.0f}

Provide trading recommendation: BUY, SELL, or HOLD.
Return JSON: {{"recommendation": "BUY/SELL/HOLD", "confidence": 75, "reasoning": "...", "key_factors": [...]}}"""
            
            response = await self.gemini.generate(prompt)
            decision_data = self._parse_response(response.text)
            
            action = Action(decision_data.get('recommendation', 'HOLD'))
            confidence = float(decision_data.get('confidence', 50))
            
            return TradingDecision(
                symbol=symbol,
                action=action,
                confidence=confidence,
                reason=decision_data.get('reasoning', ''),
                position_size=market_data.get('price_usd', 0) * 100,  # $100 position
                token_mint=token_mint,
            )
        except Exception as e:
            logger.error(f"Solana analysis failed for {symbol}: {e}")
            return None
    
    async def _execute_solana_trade(self, profile: Profile, decision: TradingDecision):
        """Execute Solana DEX trade via Jupiter."""
        if decision.confidence < 65:
            return
        
        token_mint = getattr(decision, 'token_mint', None)
        if not token_mint:
            token_mint = await self.jupiter.get_token_by_symbol(decision.symbol)
        
        if not token_mint:
            logger.error(f"No token mint for {decision.symbol}")
            return
        
        try:
            # Get quote
            from app.services.jupiter_client import SOL_MINT, usd_to_sol_amount
            sol_lamports = await usd_to_sol_amount(decision.position_size)
            
            quote = await self.jupiter.get_quote(
                input_mint=SOL_MINT,
                output_mint=token_mint,
                amount=sol_lamports,
                slippage_bps=200,  # 2% slippage for memecoins
            )
            
            if not quote:
                logger.error(f"Failed to get quote for {decision.symbol}")
                return
            
            # Log the trade
            await self._log_solana_execution(profile, decision, quote)
            
            logger.info(f"Solana trade ready: {decision.symbol} - Quote: {quote.output_amount} tokens")
            
        except Exception as e:
            logger.error(f"Solana trade execution failed: {e}")
    
    async def _log_solana_execution(self, profile: Profile, decision: TradingDecision, quote: Dict):
        """Log Solana trade execution."""
        async with AsyncSessionLocal() as db:
            from app.models import TradeLog, ExecutionType, OrderSide
            
            trade = TradeLog(
                profile_id=profile.id,
                symbol=decision.symbol,
                exchange='jupiter',
                side=OrderSide.BUY,
                execution_type=ExecutionType.PAPER,  # Paper for now until wallet integration
                size=decision.position_size,
                price=quote.get('price_pure', 0),
                total_value_usd=decision.position_size,
                status=OrderStatus.PENDING,
            )
            db.add(trade)
            await db.commit()
    
    async def _log_execution(self, profile: Profile, decision: TradingDecision, order: dict):
        """Log trade execution to database."""
        async with AsyncSessionLocal() as db:
            from app.models import Position, TradeLog, ExecutionAudit
            import uuid
            
            trade = TradeLog(
                profile_id=profile.id,
                symbol=decision.symbol,
                exchange='binance',
                side=OrderSide.BUY if decision.action == Action.BUY else OrderSide.SELL,
                execution_type=ExecutionType.LIVE,
                size=decision.position_size,
                price=order.get('average', 0),
                total_value_usd=decision.position_size,
                status=OrderStatus.FILLED,
                tx_hash=order.get('id'),
            )
            db.add(trade)
            
            # Log execution audit
            audit = ExecutionAudit(
                profile_id=profile.id,
                mode=profile.trading_mode,
                symbol=decision.symbol,
                side=OrderSide.BUY if decision.action == Action.BUY else OrderSide.SELL,
                size=decision.position_size,
                price=order.get('average', 0),
                trigger_type='ai_decision',
                status=OrderStatus.FILLED,
            )
            db.add(audit)
            
            await db.commit()


# ── Backtesting with VectorBT ────────────────────────────────────────

class BacktestEngine:
    """Fast backtesting engine using VectorBT."""
    
    def __init__(self):
        try:
            import vectorbt as vbt
            self.vbt = vbt
            self.available = True
        except ImportError:
            self.available = False
            logger.warning("vectorbt not available, using simple backtest")
    
    async def run_backtest(self, symbol: str, strategy: str, start_date: str, end_date: str) -> Dict:
        """Run backtest with VectorBT."""
        if not self.available:
            return await self._simple_backtest(symbol, strategy, start_date, end_date)
        
        try:
            # Fetch data
            market_service = get_market_service()
            ohlcv = await market_service.fetch_ohlcv(symbol, 'binance', '1h', limit=1000)
            df = pd.DataFrame(ohlcv)
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('date', inplace=True)
            
            # Run strategy (simplified - would use actual strategy logic)
            close = df['close']
            
            # Simple moving average crossover
            fast_ma = close.rolling(20).mean()
            slow_ma = close.rolling(50).mean()
            
            entries = fast_ma > slow_ma
            exits = fast_ma < slow_ma
            
            # Backtest
            portfolio = self.vbt.Portfolio.from_signals(
                close, entries, exits
            )
            
            stats = portfolio.stats()
            
            return {
                "total_return": float(portfolio.total_return()),
                "sharpe_ratio": float(portfolio.sharpe_ratio()),
                "max_drawdown": float(portfolio.max_drawdown()),
                "win_rate": float(portfolio.win_rate()),
                "total_trades": portfolio.trades.count(),
                "final_value": float(portfolio.final_value()),
            }
        except Exception as e:
            logger.error(f"VectorBT backtest failed: {e}")
            return await self._simple_backtest(symbol, strategy, start_date, end_date)
    
    async def _simple_backtest(self, symbol: str, strategy: str, start_date: str, end_date: str) -> Dict:
        """Simple fallback backtest."""
        market_service = get_market_service()
        ohlcv = await market_service.fetch_ohlcv(symbol, 'binance', '1d', limit=365)
        df = pd.DataFrame(ohlcv)
        
        if len(df) < 10:
            return {"error": "Insufficient data"}
        
        returns = df['close'].pct_change().dropna()
        total_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
        
        return {
            "total_return": float(total_return),
            "sharpe_ratio": float(returns.mean() / returns.std() * 12) if returns.std() > 0 else 0,
            "max_drawdown": float(((df['close'].cummax() - df['close']) / df['close'].cummax()).max() * 100),
            "win_rate": float((returns > 0).mean() * 100),
            "total_trades": 0,
            "final_value": float(df['close'].iloc[-1]),
        }
