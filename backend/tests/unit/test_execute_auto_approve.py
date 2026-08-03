import asyncio
import pytest
import sys, os, types
# Ensure the backend/app package is on sys.path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../backend")))
# Stub solana package to avoid import errors in test environment
solana_stub = types.ModuleType("solana")
sys.modules["solana"] = solana_stub
sys.modules["solana.rpc"] = types.ModuleType("solana.rpc")
sys.modules["solana.rpc.api"] = types.ModuleType("solana.rpc.api")
sys.modules["solana.rpc.api"].Client = lambda *args, **kwargs: None
sys.modules["solana.keypair"] = types.ModuleType("solana.keypair")
sys.modules["solana.keypair"].Keypair = lambda *args, **kwargs: None
# Stub base58 module used in wallet_gateway
sys.modules["base58"] = types.ModuleType("base58")
sys.modules["base58"].b58decode = lambda x: x.encode() if isinstance(x, str) else x

from app.services.execute_via_wallet import execute_trade_via_llm, ExecutionError

# --- Mocks ---------------------------------------------------------------

class FakeExchange:
    def create_order(self, *args, **kwargs):
        # Return a minimal order dict mimicking CCXT output
        return {"id": "order-12345", "info": "mocked"}

# Patch GeminiLLM.generate to return a deterministic order JSON
class DummyGemini:
    async def generate(self, prompt: str):
        return {
            "symbol": "BTC/USDT",
            "side": "buy",
            "size": 0.001,
            "price": 30000,
            "exchange": "binance",
            "exchange_type": "centralized",
        }

# Pytest fixtures to monkey‑patch the services
@pytest.fixture(autouse=True)
def patch_services(monkeypatch):
    # Patch the GeminiLLM class to return our dummy instance
    monkeypatch.setattr("app.services.execute_via_wallet.GeminiLLM", lambda: DummyGemini())
    # Patch the wallet gateway to return our fake exchange
    monkeypatch.setattr("app.services.execute_via_wallet.get_ccxt_exchange", lambda name: FakeExchange())
    # Solana path not used in this test, but provide a dummy to avoid import errors
    monkeypatch.setattr("app.services.execute_via_wallet.get_solana_client", lambda: None)
    monkeypatch.setattr("app.services.execute_via_wallet.load_solana_keypair", lambda: None)

# ------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_centralized_auto_approve_flow():
    prompt = "Execute trade:\nSymbol: BTC/USDT\nSide: buy\nSize: 0.001\nPrice: 30000\nExchange: binance\nExchangeType: centralized"
    result = await execute_trade_via_llm(
        task_prompt=prompt,
        exchange_type="centralized",
        exchange_name="binance",
        wallet_address=None,
    )
    assert isinstance(result, dict)
    assert result.get("order_id") == "order-12345"
    info = result.get("info")
    assert isinstance(info, dict)
    assert info.get("info") == "mocked"
