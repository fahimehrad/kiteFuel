import asyncio
import hashlib
import random
from dataclasses import dataclass, field
from typing import Literal

_SYMBOLS = ["BTC", "ETH", "SOL", "AVAX", "ARB", "OP", "LINK", "UNI", "AAVE", "MKR"]

_SUMMARIES = [
    (
        "Momentum indicators suggest a continuation of the current uptrend. "
        "On-chain activity remains elevated, pointing to sustained buying pressure. "
        "Short-term resistance is being tested at key Fibonacci levels."
    ),
    (
        "Bearish divergence on the 4-hour chart signals potential mean reversion. "
        "Funding rates have turned negative, indicating growing short interest. "
        "Watch for a re-test of the previous support zone before any recovery."
    ),
    (
        "The asset is consolidating within a tight range after last week's breakout. "
        "Volume is declining, suggesting market indecision at current price levels. "
        "A catalyst event could trigger a directional move in either direction."
    ),
    (
        "Whale wallets have accumulated significantly over the past 48 hours. "
        "Social sentiment is trending positive across major crypto communities. "
        "Risk-adjusted metrics favour a cautious long position at this level."
    ),
    (
        "Recent protocol upgrades have increased network throughput considerably. "
        "Developer activity on the repository hit a 3-month high this week. "
        "Fundamentals appear strong, though macro headwinds persist."
    ),
    (
        "Liquidation clusters lie just below current price, adding downside risk. "
        "Open interest has expanded rapidly, raising the probability of a squeeze. "
        "Prudent risk management is advised until structure becomes clearer."
    ),
    (
        "The weekly candle closed above the 200-period moving average for the first time in months. "
        "Institutional flows, as tracked by exchange reserves, are net positive. "
        "Traders are watching a potential golden cross on the daily timeframe."
    ),
    (
        "Correlation with broader equity markets has increased significantly. "
        "Macro data releases this week may drive short-term price action. "
        "On-chain transfer volume remains a healthy signal for medium-term holders."
    ),
]


@dataclass
class DataResult:
    symbol: str
    price_usd: float
    volume_24h: float
    trend: Literal["bullish", "bearish", "neutral"]
    summary: str
    cost_eth: float = field(default=0.005)


class MockDataProvider:
    """Deterministic mock paid data provider.

    For a given task_id, purchase_data always returns the same DataResult.
    The result is derived via a seeded PRNG so that different task_ids
    produce different (but reproducible) market data.
    """

    async def purchase_data(self, task_id: str) -> DataResult:
        await asyncio.sleep(1.5)
        return self._generate(task_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _generate(task_id: str) -> DataResult:
        digest = hashlib.sha256(task_id.encode()).hexdigest()
        seed = int(digest, 16)
        rng = random.Random(seed)

        symbol = rng.choice(_SYMBOLS)
        price_usd = round(rng.uniform(0.50, 80_000.0), 2)
        volume_24h = round(rng.uniform(1_000_000.0, 5_000_000_000.0), 2)
        trend: Literal["bullish", "bearish", "neutral"] = rng.choice(
            ["bullish", "bearish", "neutral"]
        )
        summary = rng.choice(_SUMMARIES)

        return DataResult(
            symbol=symbol,
            price_usd=price_usd,
            volume_24h=volume_24h,
            trend=trend,
            summary=summary,
            cost_eth=0.005,
        )
