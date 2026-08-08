"""Groq LLM client for signal analysis and sentiment parsing.

Uses GROQ_API_KEY environment variable to access Groq's API.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GroqClient:
    """Thin wrapper around Groq API for signal analysis."""

    def __init__(self, api_key: str, model: str = "llama-3.1-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
            except ImportError:
                logger.error("groq package not installed")
                raise RuntimeError("Groq client requires 'groq' package")
        return self._client

    async def analyze_text(self, text: str, ticker: str) -> Dict:
        """Analyze text for sentiment and trading signal."""
        prompt = f"""Analyze this crypto news/social text for trading signals.

Ticker: {ticker}
Text: {text[:500]}

Output JSON with:
- sentiment: float between -1 and 1
- confidence: int between 0 and 100
- action: "BUY" | "SELL" | "HOLD"
- reasoning: brief explanation

Only output valid JSON, no markdown."""

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._get_client().chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=200,
                )
            )
            response_text = result.choices[0].message.content or ""
            
            # Parse JSON from response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(response_text[start:end])
                return parsed
            
            return {"sentiment": 0.0, "confidence": 50, "action": "HOLD", "reasoning": response_text}
        except Exception as e:
            logger.warning(f"Groq analysis failed: {e}")
            return {"sentiment": 0.0, "confidence": 30, "action": "HOLD", "reasoning": f"Analysis error: {e}"}

    async def batch_analyze(self, texts: List[Dict[str, str]]) -> List[Dict]:
        """Analyze multiple texts in parallel."""
        coros = [self.analyze_text(item["text"], item["ticker"]) for item in texts]
        return await asyncio.gather(*coros)


# Module-level singleton
_groq_client: Optional[GroqClient] = None


def get_groq_client() -> GroqClient:
    """Get or create the Groq client singleton."""
    global _groq_client
    from app.config import get_settings
    settings = get_settings()
    
    if _groq_client is None and settings.GROQ_API_KEY:
        model = getattr(settings, 'GROQ_MODEL', 'llama-3.1-70b-versatile')
        _groq_client = GroqClient(settings.GROQ_API_KEY, model)
    elif _groq_client is None:
        logger.warning("GROQ_API_KEY not set — skipping Groq analysis")
    
    return _groq_client
