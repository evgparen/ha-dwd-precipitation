"""Fork recovery policy against upstream timing and real HA entities."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import aiohttp
import pytest
from custom_components.dwd_precipitation import coordinator as mod
from custom_components.dwd_precipitation.coordinator import CoordinatorData, UpdateFailed
from custom_components.dwd_precipitation.products import RadvorRV, RadvorRS, HymecNG
from .test_coordinator_timing import _make_coordinator, _capture_scheduled_delays

OLD = datetime(2026, 9, 12, 2, 45, tzinfo=timezone.utc)
DUE = OLD + timedelta(minutes=9, seconds=10)

@pytest.mark.parametrize("cls", [RadvorRS, RadvorRV, HymecNG])
def test_fast_radar_retry_stays_at_60_seconds_through_long_outage(cls):
    c = _make_coordinator(cls)
    with _capture_scheduled_delays() as delays:
        for _ in range(100):
            c._schedule_fast_poll()
    assert delays == [60] * 100

@pytest.mark.parametrize("error", [TimeoutError(), ValueError("archive"),
    aiohttp.ClientConnectionError("connection"),
    aiohttp.ClientResponseError(None, (), status=404),
    aiohttp.ClientResponseError(None, (), status=503)])
async def test_errors_retry_cache_expires_and_same_release_recovers(error):
    c = _make_coordinator(RadvorRV, data=CoordinatorData(1, {}), curr_release=OLD)
    c._fetch_and_parse = AsyncMock(side_effect=error)
    deadline = c._stale_deadline()
    with _capture_scheduled_delays() as delays:
        with patch.object(mod.dt_util, "utcnow", return_value=DUE+timedelta(seconds=1)):
            assert await c._async_update_data() is c.data
            assert c.fetch_status_attributes["dwd_fetch"]["status"] == "cached"
        with patch.object(mod.dt_util, "utcnow", return_value=deadline):
            with pytest.raises(UpdateFailed):
                await c._async_update_data()
            assert c.fetch_status_attributes["dwd_fetch"]["status"] == "unavailable"
        assert c.curr_release == OLD and c._stale_deadline() == deadline
        assert delays == [60, 60]
        attempted_release = c._fetch_and_parse.call_args.args[0]
        c._fetch_and_parse = AsyncMock(return_value=(0, {}))
        with patch.object(mod.dt_util, "utcnow", return_value=deadline+timedelta(seconds=60)):
            result = await c._async_update_data()
            assert c._fetch_and_parse.call_args.args[0] == attempted_release
            c.data = result
            assert c.fetch_status_attributes["dwd_fetch"]["status"] == "current"
        assert c.last_fetch_error is None and c._fast_poll_unsub is None

async def test_request_crossing_deadline_cannot_return_cached_success():
    c = _make_coordinator(RadvorRV, data=CoordinatorData(1, {}), curr_release=OLD)
    c._fetch_and_parse = AsyncMock(side_effect=TimeoutError())
    end = c._stale_deadline()
    with _capture_scheduled_delays(), patch.object(mod.dt_util, "utcnow", side_effect=[end-timedelta(seconds=1), end-timedelta(seconds=1), end+timedelta(seconds=1)]):
        with pytest.raises(UpdateFailed):
            await c._async_update_data()
    assert c.curr_release == OLD

async def test_cancelled_request_propagates_without_starting_retry():
    c = _make_coordinator(RadvorRV)
    c._fetch_and_parse = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await c._async_update_data()
    assert c._fast_poll_unsub is None
