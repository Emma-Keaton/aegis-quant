"""
Aegis Trading Agents — Multi-agent LLM Trading Framework

Adapted from TradingAgents (E:/Projects/finance-repos/tradingagents)
Uses Gemini Flash for all agent analysis with consensus voting.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any

from app.engines.gemini_client import get_gemini_client
from app.services.market_service import get_market_service
from app.services.jupiter_client import get_jupiter_client

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    FUNDAMENTAL = "fundamental"
    RESEARCHER_BULL = "researcher_bull"
    RESEARCHER_BEAR = "researcher_bear"
    RISK_MANAGER = "risk_manager"
    PORTFOLIO_MANAGER = "portfolio_manager"
    TRADER = "trader"


@dataclass
class AgentResult:
    """Result from a single agent."""
    role: str
    symbol: str
    recommendation: str  # BUY, SELL, HOLD
    confidence: float    # 0-100
    reasoning: str
    key_factors: List[str]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "symbol": self.symbol,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "timestamp": self.timestamp.isoformat(),
        }


class TradingAgents:
    """
    Multi-agent trading framework using Gemini Flash.
    
    Agents:
    - Technical Analyst: Price action, indicators, patterns
    - Sentiment Analyst: Social media, news, whale movements
    - Fundamental Analyst: On-chain data, tokenomics
    - Bull Researcher: Bullish case analysis
    - Bear Researcher: Bearish case analysis
    - Risk Manager: Position sizing, stop loss, risk assessment
    - Trader: Final execution decision
    """

    def __init__(self, min_confidence: float = 60.0):
        self.gemini = get_gemini_client()
        self.market = get_market_service()
        self.jupiter = get_jupiter_client()
        self.min_confidence = min_confidence
        self.agent_results: List[AgentResult] = []

    async def analyze(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """
        Run full multi-agent analysis for a symbol.
        
        Returns:
            Dict with consensus decision, individual agent results, and metadata.
        """
        logger.info(f"Running multi-agent analysis for {symbol}")
        
        # Fetch market data
        market_data = await self._get_market_data(symbol, timeframe)
        
        # Run agents in parallel
        tasks = [
            self._analyze_technical(symbol, market_data),
            self._analyze_sentiment(symbol),
            self._analyze_fundamental(symbol, market_data),
            self._analyze_bull_case(symbol, market_data),
            self._analyze_bear_case(symbol, market_data),
            self._assess_risk(symbol, market_data),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Parse results
        self.agent_results = []
        for i, result in enumerate(results):
            if isinstance(result, AgentResult):
                self.agent_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Agent {i} failed: {result}")
        
        # Generate consensus
        consensus = self._compute_consensus()
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "consensus": consensus,
            "agents": [r.to_dict() for r in self.agent_results],
            "market_data": market_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _get_market_data(self, symbol: str, timeframe: str) -> Dict:
        """Get market data from CCXT or Jupiter."""
        data = {
            "symbol": symbol,
            "price": 0,
            "volume_24h": 0,
            "change_24h": 0,
            "source": None,
        }
        
        # Try CEX first
        try:
            ohlcv = await self.market.fetch_ohlcv(f"{symbol}/USDT", "binance", timeframe, limit=100)
            if ohlcv:
                data["price"] = ohlcv[-1]["close"]
                data["volume_24h"] = sum(c["volume"] for c in ohlcv[-24:])
                data["change_24h"] = ((ohlcv[-1]["close"] / ohlcv[-25]["close"] - 1) * 100) if len(ohlcv) > 25 else 0
                data["source"] = "binance"
                return data
        except Exception as e:
            logger.warning(f"CEX fetch failed for {symbol}: {e}")
        
        # Try Jupiter for Solana tokens
        try:
            price_data = await self.jupiter.get_price(symbol)
            if price_data:
                data["price"] = price_data.price
                data["source"] = "jupiter"
                return data
        except Exception as e:
            logger.warning(f"Jupiter fetch failed for {symbol}: {e}")
        
        return data

    async def _analyze_technical(self, symbol: str, market_data: Dict) -> AgentResult:
        """Technical analysis agent."""
        prompt = f"""You are a technical analyst for {symbol}. Current price: ${market_data.get('price', 0):.4f}

Analyze the technical indicators and provide:
1. Recommendation: BUY, SELL, or HOLD
2. Confidence (0-100)
3. Key technical factors (RSI, MACD, moving averages, support/resistance)
4. Short explanation

Return JSON only: {{"recommendation": "BUY/SELL/HOLD", "confidence": 75, "reasoning": "...", "key_factors": ["...", "..."]}}"""

        try:
            response = await self.gemini.generate(prompt)
            return self._parse_agent_result(response.text, AgentRole.TECHNICAL, symbol)
        except Exception as e:
            logger.error(f"Technical analysis failed: {e}")
            return AgentResult(
                role=AgentRole.TECHNICAL.value,
                symbol=symbol,
                recommendation="HOLD",
                confidence=0,
                reasoning=str(e),
                key_factors=[],
            )

    async def _analyze_sentiment(self, symbol: str) -> AgentResult:
        """Sentiment analysis agent."""
        prompt = f"""You are a sentiment analyst for {symbol}.

Analyze recent social signals, news, and whale movements for this token.
Consider:
- Social media buzz (Twitter, Reddit)
- Whale wallet movements
- News sentiment
- Community activity

Return JSON: {{"recommendation": "BUY/SELL/HOLD", "confidence": 70, "reasoning": "...", "key_factors": ["...", "..."]}}"""

        try:
            response = await self.gemini.generate(prompt)
            return self._parse_agent_result(response.text, AgentRole.SENTIMENT, symbol)
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return AgentResult(
                role=AgentRole.SENTIMENT.value,
                symbol=symbol,
                recommendation="HOLD",
                confidence=0,
                reasoning=str(e),
                key_factors=[],
            )

    async def _analyze_fundamental(self, symbol: str, market_data: Dict) -> AgentResult:
        """Fundamental analysis agent."""
        prompt = f"""You are a fundamental analyst for {symbol}.
Current price: ${market_data.get('price', 0):.4f}
24h volume: ${market_data.get('volume_24h', 0):,.0f}

Analyze the fundamental factors:
- Tokenomics (supply, inflation, vesting)
- On-chain metrics (active addresses, transactions)
- Development activity
- Market position

Return JSON: {{"recommendation": "BUY/SELL/HOLD", "confidence": 65, "reasoning": "...", "key_factors": ["...", "..."]}}"""

        try:
            response = await self.gemini.generate(prompt)
            return self._parse_agent_result(response.text, AgentRole.FUNDAMENTAL, symbol)
        except Exception as e:
            logger.error(f"Fundamental analysis failed: {e}")
            return AgentResult(
                role=AgentRole.FUNDAMENTAL.value,
                symbol=symbol,
                recommendation="HOLD",
                confidence=0,
                reasoning=str(e),
                key_factors=[],
            )

    async def _analyze_bull_case(self, symbol: str, market_data: Dict) -> AgentResult:
        """Bull case researcher."""
        prompt = f"""You are a BULLISH researcher for {symbol}.

Present the strongest BULLISH case for this token:
- Positive catalysts
- Growth potential
- Adoption metrics
- Technical breakout potential

Return JSON: {{"recommendation": "BUY", "confidence": 70, "reasoning": "...", "key_factors": ["...", "..."]}}"""

        try:
            response = await self.gemini.generate(prompt)
            return self._parse_agent_result(response.text, AgentRole.RESEARCHER_BULL, symbol)
        except Exception as e:
            return AgentResult(
                role=AgentRole.RESEARCHER_BULL.value,
                symbol=symbol,
                recommendation="BUY",
                confidence=50,
                reasoning=str(e),
                key_factors=[],
            )

    async def _analyze_bear_case(self, symbol: str, market_data: Dict) -> AgentResult:
        """Bear case researcher."""
        prompt = f"""You are a BEARISH researcher for {symbol}.

Present the strongest BEARISH case for this token:
- Risk factors
- Downside catalysts
- Competition threats
- Technical breakdown risks

Return JSON: {{"recommendation": "SELL", "confidence": 70, "reasoning": "...", "key_factors": ["...", "..."]}}"""

        try:
            response = await self.gemini.generate(prompt)
            return self._parse_agent_result(response.text, AgentRole.RESEARCHER_BEAR, symbol)
        except Exception as e:
            return AgentResult(
                role=AgentRole.RESEARCHER_BEAR.value,
                symbol=symbol,
                recommendation="SELL",
                confidence=50,
                reasoning=str(e),
                key_factors=[],
            )

    async def _assess_risk(self, symbol: str, market_data: Dict) -> AgentResult:
        """Risk assessment agent."""
        prompt = f"""You are a RISK MANAGER for {symbol}.
Current price: ${market_data.get('price', 0):.4f}

Assess the risk factors:
- Volatility
- Liquidity risk
- Market cap risk
- Regulatory risk
- Smart contract risk (for DeFi tokens)

Return JSON: {{"recommendation": "APPROVE/MODIFY/REJECT", "confidence": 80, "reasoning": "...", "key_factors": ["...", "..."], "suggested_stop_loss_pct": 10, "suggested_position_size_pct": 5}}"""

        try:
            response = await self.gemini.generate(prompt)
            return self._parse_agent_result(response.text, AgentRole.RISK_MANAGER, symbol)
        except Exception as e:
            return AgentResult(
                role=AgentRole.RISK_MANAGER.value,
                symbol=symbol,
                recommendation="APPROVE",
                confidence=50,
                reasoning=str(e),
                key_factors=[],
            )

    def _parse_agent_result(self, text: str, role: AgentRole, symbol: str) -> AgentResult:
        """Parse LLM response into AgentResult."""
        try:
            # Extract JSON from response
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                json_str = text[start:end+1]
                data = json.loads(json_str)
                
                return AgentResult(
                    role=role.value,
                    symbol=symbol,
                    recommendation=data.get('recommendation', 'HOLD'),
                    confidence=float(data.get('confidence', 50)),
                    reasoning=data.get('reasoning', ''),
                    key_factors=data.get('key_factors', []),
                )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse agent response: {e}")
        
        # Fallback
        return AgentResult(
            role=role.value,
            symbol=symbol,
            recommendation="HOLD",
            confidence=50,
            reasoning="Could not parse response",
            key_factors=[],
        )

    def _compute_consensus(self) -> Dict:
        """Compute consensus from all agents."""
        if not self.agent_results:
            return {
                "recommendation": "HOLD",
                "confidence": 0,
                "unanimous": False,
                "agent_count": 0,
            }
        
        # Count votes
        votes = {"BUY": 0, "SELL": 0, "HOLD": 0}
        total_confidence = 0
        
        for result in self.agent_results:
            rec = result.recommendation.upper()
            if rec in votes:
                votes[rec] += 1
            total_confidence += result.confidence
        
        avg_confidence = total_confidence / len(self.agent_results)
        
        # Determine consensus
        max_votes = max(votes.values())
        total = sum(votes.values())
        unanimous = max_votes == total
        
        if votes["BUY"] > votes["SELL"] and votes["BUY"] >= votes["HOLD"]:
            consensus = "BUY"
        elif votes["SELL"] > votes["BUY"] and votes["SELL"] >= votes["HOLD"]:
            consensus = "SELL"
        else:
            consensus = "HOLD"
        
        return {
            "recommendation": consensus,
            "confidence": round(avg_confidence, 1),
            "unanimous": unanimous,
            "agent_count": len(self.agent_results),
            "votes": votes,
            "min_confidence_met": avg_confidence >= self.min_confidence,
        }

    def get_agent_summary(self) -> List[Dict]:
        """Get summary of all agent results."""
        return [r.to_dict() for r in self.agent_results]


# Global instance
_trading_agents: Optional[TradingAgents] = None


def get_trading_agents(min_confidence: float = 60.0) -> TradingAgents:
    """Get global TradingAgents instance."""
    global _trading_agents
    if _trading_agents is None:
        _trading_agents = TradingAgents(min_confidence=min_confidence)
    return _trading_agents
