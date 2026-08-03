import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)

@pytest.fixture
def settings_env(monkeypatch):
    # Set required env vars for the test
    monkeypatch.setenv("QUANTDINGER_BASE_URL", "http://dummy-quantdinger:5000")
    monkeypatch.setenv("QUANTDINGER_AGENT_TOKEN", "test-token")
    return True

@patch("httpx.AsyncClient")
def test_submit_trade_success(mock_async_client, settings_env):
    # Mock the async client post method
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "executed", "order_id": "12345"}
    mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

    payload = {"action": "buy", "symbol": "BTCUSDT", "amount": 0.01}
    response = client.post("/ai-trade/", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "executed", "order_id": "12345"}

@patch("httpx.AsyncClient")
def test_submit_trade_missing_config(mock_async_client, monkeypatch):
    # Unset token to trigger config error
    monkeypatch.delenv("QUANTDINGER_BASE_URL", raising=False)
    monkeypatch.delenv("QUANTDINGER_AGENT_TOKEN", raising=False)
    payload = {"action": "sell", "symbol": "ETHUSDT", "amount": 0.5}
    response = client.post("/ai-trade/", json=payload)
    assert response.status_code == 500
    assert "QuantDinger integration not configured" in response.json()["detail"]
