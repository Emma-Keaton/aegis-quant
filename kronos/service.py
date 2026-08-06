"""Kronos forecasting service — self-contained, deployable as a separate Render service.

Runs the Kronos Hugging Face time-series model (when the Kronos lib + torch are
available) and otherwise falls back to a lightweight persistence placeholder so
the endpoint is always usable on CPU/free-tier instances.

When deployed separately, the main backend (`backend/app/services/kronos_service.py`)
proxies forecast requests here via `KRONOS_SERVICE_URL` + `KRONOS_API_KEY`.
"""

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("kronos")

# Earth-model "Kronos" variants (smallest first). Only used when model loading is
# enabled AND the `model` (Kronos) lib is importable on the service.
MODEL_VARIANTS = [
    ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k", 4.1e6, "mini"),
    ("NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base", 24.7e6, "small"),
    ("NeoQuasar/Kronos-base", "NeoQuasar/Kronos-Tokenizer-base", 102.3e6, "base"),
]

_LOAD_MODEL = os.getenv("KRONOS_LOAD_MODEL", "0").strip().lower() in ("1", "true", "yes")


@dataclass
class ForecastResult:
    trajectories: List[List[float]]
    mean_path: List[float]
    confidence_90: List[List[float]]
    confidence: int
    metadata: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "trajectories": self.trajectories,
            "mean_path": self.mean_path,
            "confidence_90": self.confidence_90,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class KronosService:
    def __init__(self):
        self.model_loaded = False
        self.model = None
        self.tokenizer = None
        self.predictor = None
        self.model_name: Optional[str] = None
        self.model_params = 0

    async def initialize(self) -> None:
        if not _LOAD_MODEL:
            logger.info("KRONOS_LOAD_MODEL not enabled — using placeholder forecasting")
            self.model_loaded = False
            return
        try:
            await asyncio.to_thread(self._load_best_model)
            if self.model_loaded:
                logger.info(f"Kronos model loaded: {self.model_name}")
            else:
                logger.warning("Kronos model could not be loaded — using placeholder")
        except Exception as e:
            logger.error(f"Kronos initialization failed: {e}")
            self.model_loaded = False

    def _load_best_model(self) -> bool:
        try:
            import torch  # noqa: F401
            from model import Kronos, KronosPredictor, KronosTokenizer  # local Kronos lib
        except ImportError as e:
            logger.warning(f"Kronos lib unavailable ({e}) — using placeholder")
            return False
        for model_path, tok_path, params, name in reversed(MODEL_VARIANTS):
            try:
                self.tokenizer = KronosTokenizer.from_pretrained(tok_path)
                self.model = Kronos.from_pretrained(
                    model_path,
                    device_map="auto" if torch.cuda.is_available() else "cpu",
                    trust_remote_code=True,
                )
                self.model.eval()
                max_context = 2048 if name == "mini" else 512
                self.predictor = KronosPredictor(self.model, self.tokenizer, max_context=max_context)
                self.model_name = model_path
                self.model_params = params
                self.model_loaded = True
                return True
            except Exception as e:
                logger.warning(f"  failed to load {name}: {e}")
                self.model = self.tokenizer = self.predictor = None
        return False

    async def forecast(self, closes: List[float], horizon: int, samples: int) -> ForecastResult:
        if len(closes) < 16:
            raise ValueError(f"Insufficient data: need >=16 candles, got {len(closes)}")
        if not self.model_loaded or self.predictor is None:
            return self._placeholder_forecast(closes, horizon, samples)
        try:
            return await asyncio.to_thread(self._model_forecast, closes, horizon, samples)
        except Exception as e:
            logger.error(f"Kronos forecast failed ({e}) — placeholder")
            return self._placeholder_forecast(closes, horizon, samples)

    def _model_forecast(self, closes: List[float], horizon: int, samples: int) -> ForecastResult:
        import pandas as pd

        n = len(closes)
        df = pd.DataFrame(
            {
                "open": closes,
                "high": [c * (1 + abs(i) * 0.001) for i, c in enumerate(closes)],
                "low": [c * (1 - abs(i) * 0.001) for i, c in enumerate(closes)],
                "close": closes,
                "volume": [1000 + i * 10 for i in range(n)],
            }
        )
        pred_df = self.predictor.predict(
            df=df, pred_len=horizon, T=1.0, top_p=0.9, sample_count=samples, verbose=False
        )
        if len(pred_df):
            mean_path = pred_df["close"].tolist()[:horizon]
            trajectories = [pred_df["close"].tolist()[:horizon] for _ in range(min(samples, len(pred_df)))]
        else:
            mean_path = [closes[-1]] * horizon
            trajectories = [list(mean_path) for _ in range(samples)]
        return ForecastResult(
            trajectories=trajectories,
            mean_path=mean_path,
            confidence_90=[],
            confidence=85,
            metadata={"model_source": "kronos", "model_name": self.model_name},
        )

    def _placeholder_forecast(self, closes: List[float], horizon: int, samples: int) -> ForecastResult:
        last = closes[-1]
        mean_path = [last * (1 + (i - horizon / 2) * 0.001) for i in range(horizon)]
        trajectories = [list(mean_path) for _ in range(samples)]
        return ForecastResult(
            trajectories=trajectories,
            mean_path=mean_path,
            confidence_90=[],
            confidence=50,
            metadata={"model_source": "placeholder", "reason": "kronos model not available"},
        )


_service: Optional[KronosService] = None


def get_service() -> KronosService:
    global _service
    if _service is None:
        _service = KronosService()
    return _service
