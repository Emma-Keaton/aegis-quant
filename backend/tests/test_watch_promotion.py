"""Tests for the market-watch port: quota, dex parsing/spikes, whale flows,
and the promotion gate's pure evaluation logic."""
from __future__ import annotations

import time

from app.services import quota
from app.services.dexwatch import (
    detect_spikes,
    parse_pair,
    parse_pairs_response,
    rank_and_filter,
)
from app.services.promotion import (
    default_bar,
    deflated_sharpe,
    evaluate,
    evaluate_evidence,
    probabilistic_sharpe,
)
from app.services.position_manager import trigger_hit
from app.services.whale_watch import flow_key, parse_whale_flow


# ── quota ────────────────────────────────────────────────────────────────────

def test_window_allows_up_to_limit_then_degrades():
    w = quota.Window(60_000, 3)
    assert [w.take() for _ in range(3)] == [True, True, True]
    assert w.take() is False
    assert w.remaining() == 0


def test_window_refills_after_window_elapses():
    w = quota.Window(40, 1)  # 40ms window
    assert w.take() is True
    assert w.take() is False
    time.sleep(0.06)
    assert w.take() is True


def test_credits_spend_and_reject_over_budget():
    c = quota.Credits(100)
    assert c.spend(60) is True
    assert c.spend(40) is True
    assert c.spend(1) is False
    assert c.remaining() == 0


def test_status_exposes_budgets():
    s = quota.status()
    assert s["in_memory_only"] is True
    assert s["dexscreener_pairs_remaining"] >= 0
    assert s["dexscreener_pairs_limit"] == 280


# ── dexscreener parsing ─────────────────────────────────────────────────────

def _pair(**over):
    base = {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": "pair1",
        "baseToken": {"address": "mint1", "symbol": "WIF"},
        "priceUsd": "1.25",
        "liquidity": {"usd": 250_000},
        "volume": {"h24": 1_000_000},
        "txns": {"h24": {"buys": 120, "sells": 80}},
        "priceChange5m": "1.5",
        "priceChange1h": "-4.5",
        "priceChange24h": "12",
    }
    base.update(over)
    return base


def test_parse_pair_happy_path():
    row = parse_pair(_pair())
    assert row is not None
    assert row["symbol"] == "WIF"
    assert row["price_usd"] == 1.25
    assert row["liquidity_usd"] == 250_000
    assert row["price_change_1h"] == -4.5
    assert row["buys"] == 120


def test_parse_pair_rejects_unusable_rows():
    assert parse_pair("not a dict") is None
    assert parse_pair(_pair(baseToken={})) is None
    assert parse_pair(_pair(priceUsd=None)) is None
    assert parse_pair(_pair(priceUsd="0")) is None
    assert parse_pair(_pair(priceUsd="-1")) is None


def test_parse_pairs_response_filters_chain_and_bad_rows():
    payload = {"pairs": [_pair(), _pair(chainId="bsc"), _pair(priceUsd="bad"), {}]}
    rows = parse_pairs_response(payload, chains=["solana"])
    assert len(rows) == 1
    assert rows[0]["chain"] == "solana"


def test_rank_and_filter_dedupes_prefers_completeness_then_depth():
    thin = {"address": "mintA", "liquidity_usd": 10_000, "price_change_1h": None}
    deep_thin = {"address": "mintA", "liquidity_usd": 90_000, "price_change_1h": None}
    complete = {"address": "mintA", "liquidity_usd": 50_000, "price_change_1h": 3.0}
    below_floor = {"address": "mintB", "liquidity_usd": 100, "price_change_1h": 9.0}
    ranked = rank_and_filter([thin, deep_thin, complete, below_floor],
                             limit=5, min_liquidity_usd=1_000)
    assert len(ranked) == 1
    assert ranked[0]["price_change_1h"] == 3.0  # completeness beats depth


def test_detect_spikes_threshold_and_liquidity_floor():
    rows = [
        {"symbol": "PUMP", "price_change_1h": 42.0, "liquidity_usd": 500_000},
        {"symbol": "FLAT", "price_change_1h": 4.0, "liquidity_usd": 500_000},
        {"symbol": "THIN", "price_change_1h": 90.0, "liquidity_usd": 500},
        {"symbol": "NONE", "price_change_1h": None, "liquidity_usd": 500_000},
        {"symbol": "DUMP", "price_change_1h": -42.0, "liquidity_usd": 500_000},
    ]
    spikes = detect_spikes(rows, pct_1h=25.0, min_liquidity_usd=10_000)
    names = {s["symbol"] for s in spikes}
    assert names == {"PUMP", "DUMP"}  # pumps and dumps both count
    assert all("spike_pct" in s for s in spikes)


# ── whale flows ─────────────────────────────────────────────────────────────

def test_parse_whale_flow_swap_buy_and_sell_sides():
    tx = {
        "signature": "sig1",
        "timestamp": 1_700_000_000,
        "type": "SWAP",
        "feePayer": "whale",
        "tokenTransfers": [
            {"mint": "SOLMINT", "tokenAmount": 500.0,
             "fromUserOwner": "pool", "toUserOwner": "whale"},
        ],
    }
    buy = parse_whale_flow(tx, mint="SOLMINT", symbol="SOL", price_usd=200.0,
                           min_usd=50_000.0)
    assert len(buy) == 1
    assert buy[0]["side"] == "buy"
    assert buy[0]["amount_usd"] == 100_000.0
    assert buy[0]["wallet"] == "whale"

    sell_tx = dict(tx, tokenTransfers=[
        {"mint": "SOLMINT", "tokenAmount": 500.0,
         "fromUserOwner": "whale", "toUserOwner": "pool"},
    ])
    sell = parse_whale_flow(sell_tx, mint="SOLMINT", symbol="SOL",
                            price_usd=200.0, min_usd=50_000.0)
    assert sell[0]["side"] == "sell"


def test_parse_whale_flow_filters_below_min_usd_and_bad_input():
    tx = {
        "signature": "sig2", "timestamp": 1_700_000_000, "type": "SWAP",
        "feePayer": "whale",
        "tokenTransfers": [
            {"mint": "SOLMINT", "tokenAmount": 1.0},
        ],
    }
    assert parse_whale_flow(tx, mint="SOLMINT", symbol="SOL",
                            price_usd=200.0, min_usd=50_000.0) == []
    assert parse_whale_flow("bad", mint="X", symbol="X", price_usd=1.0) == []
    assert parse_whale_flow(tx, mint="", symbol="SOL", price_usd=200.0) == []
    assert parse_whale_flow(dict(tx, signature=None), mint="SOLMINT",
                            symbol="SOL", price_usd=200.0) == []
    assert parse_whale_flow(dict(tx, timestamp="nope"), mint="SOLMINT",
                            symbol="SOL", price_usd=200.0) == []


def test_flow_key_is_stable_and_unique():
    row = {"tx_signature": "s", "symbol": "SOL", "wallet": "w", "side": "buy"}
    assert flow_key(row) == "s|SOL|w|buy"
    assert flow_key({**row, "side": "sell"}) != flow_key(row)


# ── promotion gate ──────────────────────────────────────────────────────────

def _strong_returns(n: int = 40) -> list:
    # steady positive drift with noise: high, consistent Sharpe
    return [0.012 + 0.002 * ((i % 5) - 2) for i in range(n)]


def test_probabilistic_sharpe_rules():
    assert probabilistic_sharpe([0.01, 0.02, 0.03]) == 0.0  # n < 4
    assert probabilistic_sharpe([0.01] * 10) == 0.0  # zero variance
    assert probabilistic_sharpe(_strong_returns()) > 0.9


def test_deflated_sharpe_rules():
    assert deflated_sharpe([0.01] * 3) == 0.0  # n < 4
    assert deflated_sharpe(_strong_returns(), trials=0) == 0.0  # invalid trials
    assert deflated_sharpe(_strong_returns()) > 0.9
    # more trials raise the hurdle, so DSR cannot increase
    assert deflated_sharpe(_strong_returns(), trials=50) <= deflated_sharpe(
        _strong_returns(), trials=1)


def test_default_bar_reads_settings():
    bar = default_bar()
    assert bar["min_trades"] == 30
    assert bar["min_accuracy"] == 0.53
    assert bar["max_brier"] == 0.25
    assert bar["min_deflated_sharpe"] == 0.95


def test_evaluate_passing_report_promotes():
    report = {"brier": 0.10, "accuracy": 0.70, "expectancy": 0.02,
              "trades": 35, "deflated_sharpe": 0.97, "age_days": 5.0}
    verdict = evaluate(report)
    assert verdict["promoted"] is True
    assert verdict["reasons"] == []


def test_evaluate_collects_reasons_for_empty_report():
    verdict = evaluate({})
    assert verdict["promoted"] is False
    assert any("calibrated" in r for r in verdict["reasons"])
    assert any("Not enough practice trades" in r for r in verdict["reasons"])
    assert any("luck" in r for r in verdict["reasons"])


def test_evaluate_accuracy_boundary_is_strict():
    report = {"brier": 0.10, "accuracy": 0.53, "expectancy": 0.02,
              "trades": 40, "deflated_sharpe": 0.99, "age_days": 10.0}
    verdict = evaluate(report)
    assert verdict["promoted"] is False
    assert "Win rate is no better than a guess" in verdict["reasons"]


def test_evaluate_evidence_promotes_strong_paper_record():
    evidence = {
        "trades": 40, "wins": 28, "win_rate": 0.70, "expectancy": 0.015,
        "max_drawdown": 0.08, "profit_factor": 1.8, "age_days": 5.0,
        "brier": 0.11, "deflated_sharpe": 0.96, "returns_sample": [0.01] * 40,
    }
    verdict = evaluate_evidence(evidence)
    assert verdict["promoted"] is True
    assert verdict["stability"] == []


def test_evaluate_evidence_stability_rules_can_veto():
    evidence = {
        "trades": 12, "wins": 5, "win_rate": 0.417, "expectancy": 0.05,
        "max_drawdown": 0.40, "profit_factor": 1.0, "age_days": 6.0,
        "brier": 0.10, "deflated_sharpe": 0.99, "returns_sample": [],
    }
    verdict = evaluate_evidence(evidence)
    assert verdict["promoted"] is False  # stability veto overrides a passing bar
    assert any("coin flip" in r for r in verdict["stability"])
    assert any("Drawdown too deep" in r for r in verdict["stability"])
    assert any("Profit factor too low" in r for r in verdict["stability"])


# ── SL/TP trigger (pure) ────────────────────────────────────────────────────

class _Pos:
    def __init__(self, side, stop_loss=None, take_profit=None):
        self.side = type("S", (), {"value": side})()
        self.stop_loss = stop_loss
        self.take_profit = take_profit


def test_trigger_hit_long():
    long_pos = _Pos("buy", stop_loss=90.0, take_profit=110.0)
    assert trigger_hit(long_pos, 89.9) == "stop_loss"
    assert trigger_hit(long_pos, 110.0) == "take_profit"
    assert trigger_hit(long_pos, 100.0) is None
    assert trigger_hit(long_pos, 0) is None  # no mark price, no trigger


def test_trigger_hit_short():
    short_pos = _Pos("sell", stop_loss=110.0, take_profit=90.0)
    assert trigger_hit(short_pos, 110.1) == "stop_loss"
    assert trigger_hit(short_pos, 89.9) == "take_profit"
    assert trigger_hit(short_pos, 100.0) is None


def test_trigger_hit_without_levels_never_fires():
    bare = _Pos("buy")
    assert trigger_hit(bare, 50.0) is None
    only_tp = _Pos("buy", take_profit=60.0)
    assert trigger_hit(only_tp, 60.0) == "take_profit"
    assert trigger_hit(only_tp, 59.0) is None
