import httpx
import logging
from typing import List, Dict, Optional
from datetime import datetime

from app.config import get_settings
from app.core.exceptions import KronosError

logger = logging.getLogger(__name__)


class KronosClient:
    """HTTP client for Kronos AI service on Render"""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.KRONOS_API_URL.rstrip("/")
        self.api_key = self.settings.KRONOS_API_KEY
        self.timeout = self.settings.KRONOS_TIMEOUT
        self._client: httpx.AsyncClient | None = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            )
        return self._client
    
    async def forecast(self, candles: List[Dict], horizon: int = 30, num_samples: int = 30) -> Optional[Dict]:
        """
        Request forecast from Kronos AI
        
        Args:
            candles: List of OHLCV dicts with timestamp, open, high, low, close, volume
            horizon: Number of future candles to predict
            num_samples: Monte Carlo samples
        
        Returns:
            Dict with trajectories, mean_path, confidence intervals, confidence score
        """
        try:
            payload = {
                "candles": candles,
                "horizon": horizon,
                "num_samples": num_samples
            }
            
            response = await self.client.post("/forecast", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response structure
            required_keys = ["trajectories", "mean_path", "confidence_90", "confidence"]
            if not all(k in data for k in required_keys):
                raise KronosError(f"Invalid response structure: {data.keys()}")
            
            return data
            
        except httpx.TimeoutException:
            logger.error(f"Kronos request timeout after {self.timeout}s")
            raise KronosError("Request timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"Kronos HTTP error: {e.response.status_code} - {e.response.text}")
            raise KronosError(f"HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Kronos client error: {e}")
            raise KronosError(str(e))
    
    async def health_check(self) -> bool:
        """Check if Kronos service is healthy"""
        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None