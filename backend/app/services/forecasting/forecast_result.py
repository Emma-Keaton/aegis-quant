"""Shared forecast result used by every forecasting tier (Kronos + replacement)."""
from dataclasses import asdict, dataclass
from typing import Any, Dict, List


@dataclass
class ForecastResult:
    """A prediction: point forecast, sampled paths, and uncertainty bands.

    Mirrors the shape returned by Kronos so consumers (signals, backtest,
    worker) treat replacement forecasts identically.
    """

    trajectories: List[List[float]]
    mean_path: List[float]
    confidence_90: List[List[float]]
    confidence: int
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastResult":
        return cls(**data)