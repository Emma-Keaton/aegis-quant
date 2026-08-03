import pytest, asyncio
from app.services.kronos_service import KronosService, ForecastResult

@pytest.mark.asyncio
async def test_kronos_forecast_placeholder():
    # Prepare a synthetic close price series (100 points)
    closes = [float(i) for i in range(100)]
    service = KronosService()
    # Directly initialize the HF model (may be a quick download on CI, but we rely on placeholder if unavailable)
    try:
        await service.initialize()
    except Exception as e:
        # If the model cannot be loaded (e.g., no internet), we still want the placeholder to work.
        # The placeholder is already the fallback in _real_model_forecast, so we just continue.
        pytest.fail(f"Failed to initialize KronosService: {e}")

    result: ForecastResult = await service.forecast(closes=closes, horizon=30, samples=3)
    # Ensure we got a result with the expected lengths
    assert isinstance(result, ForecastResult)
    assert len(result.mean_path) == 30
    assert len(result.trajectories) == 3
    for traj in result.trajectories:
        assert len(traj) == 30
