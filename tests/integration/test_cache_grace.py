"""HA lifecycle: deadline expiry during an in-flight first failed fetch."""
import asyncio
from datetime import timedelta
from unittest.mock import patch, AsyncMock
import pytest
from homeassistant.util import dt as dt_util
from custom_components.dwd_precipitation import coordinator as mod
from .test_setup_entry import _entry, _patched_products, _state_for

@pytest.mark.parametrize("hide_stale", [True, False])
async def test_deadline_diagnostics_and_recovery_without_entity_id_changes(hass, hide_stale):
    entry = _entry(hass)
    hass.config_entries.async_update_entry(entry, options={"unavailable_when_stale":hide_stale})
    with _patched_products():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    rv = entry.runtime_data.coordinators["rv"]
    old = rv.curr_release
    old_payload = rv.data
    deadline = rv._stale_deadline()
    rain = _state_for(hass, "radvor_rv_precipitation_expected_120", "binary_sensor")
    entity_id = rain.entity_id
    diagnostic = _state_for(hass, "rv_fetch_status")
    assert diagnostic.state == "current"
    assert rv._stale_unsub is not None
    started = asyncio.Event(); finish = asyncio.Event()
    async def hanging(release):
        started.set()
        await finish.wait()
        raise TimeoutError("late file")
    with patch.object(rv,"_fetch_and_parse",hanging), patch.object(mod.dt_util,"utcnow",return_value=deadline):
        task = asyncio.create_task(rv.async_refresh())
        await started.wait()
        rv._cancel_stale_check()
        rv._stale_reached(deadline)
        # Writes are scheduled; do not await the deliberately pending refresh.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        state = hass.states.get(entity_id)
        assert (state.state == "unavailable") == hide_stale
        diag = hass.states.get(diagnostic.entity_id)
        assert diag.state == ("unavailable" if hide_stale else "expired")
        assert diag.attributes["source_release"] == old.isoformat()
        assert diag.attributes["valid_until"] == deadline.isoformat()
        finish.set(); await task
    assert rv.curr_release == old
    assert rv._fast_poll_unsub is not None
    with patch.object(rv,"_fetch_and_parse",AsyncMock(return_value=(old_payload.data,old_payload.metadata))), patch.object(mod.dt_util,"utcnow",return_value=deadline+timedelta(seconds=60)):
        await rv.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state != "unavailable"
        assert hass.states.get(diagnostic.entity_id).state == "current"
        assert hass.states.get(diagnostic.entity_id).attributes["error"] is None
    assert rv._fast_poll_unsub is None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert rv._stale_unsub is None
