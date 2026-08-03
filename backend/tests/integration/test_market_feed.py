import asyncio
import pytest

# Patch CCXT exchange used by market_hub
@pytest.fixture(autouse=True)
def patch_ccxt(monkeypatch):
    class FakeExchange:
        def fetch_ticker(self, symbol):
            # Simple deterministic ticker payload
            return {"symbol": symbol, "price": 123.45}
    # The market_hub imports get_ccxt_exchange from wallet_gateway; we replace it.
    # Ensure the backend package is importable for monkeypatch path
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../backend")))
    monkeypatch.setattr(
        "app.services.market_hub.get_ccxt_exchange",
        lambda name: FakeExchange()
    )

@pytest.mark.asyncio
async def test_market_feed_populates_cache():
    from app.services.market_hub import start_market_feed, get_market_data, stop_market_feed
    # Use a very short interval so the test finishes quickly
    await start_market_feed(symbols=["BTC/USDT"], interval=0.01, exchange_name="binance")
    # Allow the background task to run at least once
    await asyncio.sleep(0.05)
    data = get_market_data("BTC/USDT")
    assert data is not None
    assert data["symbol"] == "BTC/USDT"
    assert data["price"] == 123.45
    # Clean up
    await stop_market_feed()
