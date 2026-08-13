import json
import asyncio
from typing import Literal, Dict

from .gemini_llm import GeminiLLM
from .wallet_gateway import get_ccxt_exchange, get_solana_client, load_solana_keypair

class ExecutionError(RuntimeError):
    pass

async def execute_trade_via_llm(
    task_prompt: str,
    exchange_type: Literal["centralized", "solana"],
    exchange_name: str | None = None,
    wallet_address: str | None = None,
) -> Dict:
    """1️⃣ Ask Gemini to turn *task_prompt* into a structured order JSON.
    2️⃣ Dispatch that order to the appropriate wallet (CCXT or Solana).
    Returns a dict with the external identifier (order_id / tx_hash) and any useful info.
    """
    # ----- 1. LLM -----
    llm = GeminiLLM()
    order = await llm.generate(task_prompt)
    # Expected order schema (all keys are optional depending on exchange):
    # {"symbol": "BTC/USDT", "side": "buy", "size": 0.01, "price": 30000, "exchange": "binance"}

    # ----- 2. Dispatch -----
    if exchange_type == "solana":
        if not wallet_address:
            raise ExecutionError("wallet_address required for solana execution")
        client = get_solana_client()
        try:
            kp = load_solana_keypair()
            from solders.transaction import Transaction
            from solders.system_program import TransferParams, transfer
            from solders.pubkey import Pubkey

            # Simple SOL transfer – replace with a Jupiter swap later.
            txn = Transaction()
            txn.add(
                transfer(
                    TransferParams(
                        from_pubkey=kp.public_key,
                        to_pubkey=Pubkey.from_string(wallet_address),
                        lamports=int(order.get("size", 0) * 1e9),
                    )
                )
            )
            resp = await client.send_transaction(txn, kp)
            sig = str(resp.value) if hasattr(resp, "value") else str(resp)
            return {"tx_hash": sig}
        finally:
            await client.close()
    else:
        # Centralized exchange via CCXT
        if not exchange_name:
            raise ExecutionError("exchange_name required for centralized execution")
        exchange = get_ccxt_exchange(exchange_name)
        try:
            created = exchange.create_order(
                symbol=order["symbol"],
                type="limit" if order.get("price") else "market",
                side=order["side"],
                amount=order["size"],
                price=order.get("price"),
            )
        except Exception as exc:
            raise ExecutionError(str(exc))
        return {"order_id": created.get("id"), "info": created}
