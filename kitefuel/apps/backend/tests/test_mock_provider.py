import asyncio
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.mock_provider import MockDataProvider, DataResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sync_purchase(task_id: str) -> DataResult:
    """Run purchase_data synchronously inside tests."""
    provider = MockDataProvider()
    # Patch sleep so tests don't actually wait 1.5 s
    async def _run():
        import unittest.mock as mock
        with mock.patch("asyncio.sleep", return_value=None):
            return await provider.purchase_data(task_id)
    return asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# Test: same task_id always returns identical DataResult
# ---------------------------------------------------------------------------

def test_same_task_id_returns_identical_result():
    # Invariant: deterministic by task_id — two calls with the same id must be equal
    result1 = _sync_purchase("task-abc-123")
    result2 = _sync_purchase("task-abc-123")
    assert result1 == result2


# ---------------------------------------------------------------------------
# Test: different task_ids return different results
# ---------------------------------------------------------------------------

def test_different_task_ids_return_different_results():
    # Invariant: hash seeds differ enough that outputs differ for distinct ids
    result_a = _sync_purchase("task-alpha-001")
    result_b = _sync_purchase("task-beta-999")
    assert result_a != result_b


# ---------------------------------------------------------------------------
# Test: cost_eth is always exactly 0.005
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("task_id", [
    "task-001",
    "task-xyz",
    "00000000-0000-0000-0000-000000000001",
    "another-random-task",
])
def test_cost_eth_is_always_0_005(task_id):
    # Invariant: the provider always charges exactly 0.005 ETH regardless of task
    result = _sync_purchase(task_id)
    assert result.cost_eth == 0.005


# ---------------------------------------------------------------------------
# Test: returned object is a DataResult with expected fields
# ---------------------------------------------------------------------------

def test_purchase_data_returns_dataresult():
    result = _sync_purchase("some-task-id")
    assert isinstance(result, DataResult)
    assert isinstance(result.symbol, str) and result.symbol
    assert isinstance(result.price_usd, float) and result.price_usd > 0
    assert isinstance(result.volume_24h, float) and result.volume_24h > 0
    assert result.trend in ("bullish", "bearish", "neutral")
    assert isinstance(result.summary, str) and result.summary
