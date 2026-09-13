"""Bounded late-file cache: age, diagnostics, expiry and recovery."""
from datetime import timedelta
from unittest.mock import patch
from types import MethodType
import pytest

from . import test_retry_regression as regression
from .test_retry_regression import REQUEST, RELEASE
from custom_components.dwd_precipitation import coordinator as module
from custom_components.dwd_precipitation.coordinator import BaseProductUpdateCoordinator as C, UpdateFailed
from custom_components.dwd_precipitation.products import RadvorRV, RadvorRS, HymecNG, RadolanRW


def make():
    c = regression.RetryRegressionTests().make_coordinator()
    c.LATE_FILE_GRACE = timedelta(minutes=5)
    c.last_fetch_error = None
    c.last_fetch_attempt = None
    c.last_update_success = True
    c._expiry_unsub = None
    c.hass = object()
    c._cache_deadline = MethodType(C._cache_deadline, c)
    c._cancel_expiry = MethodType(C._cancel_expiry, c)
    c._arm_expiry = MethodType(C._arm_expiry, c)
    c.errors = []
    c.async_set_update_error = c.errors.append
    async def fail(ts):
        raise TimeoutError("late file")
    c._fetch_and_parse = fail
    return c


async def update(c, at):
    with patch.object(module.dt_util, "utcnow", return_value=at):
        return await C._async_update_data(c)


@pytest.mark.parametrize("cls", [RadvorRV, RadvorRS, HymecNG])
def test_fast_products_opt_in_only(cls):
    assert cls.LATE_FILE_GRACE == timedelta(minutes=5)
    assert RadolanRW.LATE_FILE_GRACE == timedelta()


@pytest.mark.parametrize("minutes", [0, 1, 3, 4])
async def test_late_file_bridged_without_refreshing_source(minutes):
    c = make(); old = c.curr_release
    with patch.object(module, "async_call_later", return_value=lambda: None) as timer:
        result = await update(c, REQUEST + timedelta(minutes=minutes))
        assert result is c.data
        assert c.curr_release == old and c.retry
        assert timer.call_count == 1
        assert c.last_fetch_error
        with patch.object(module.dt_util, "utcnow", return_value=REQUEST + timedelta(minutes=minutes)):
            attrs = C.fetch_status_attributes.fget(c)["dwd_fetch"]
        assert attrs["status"] == "cached"
        assert attrs["source_release"] == old.isoformat()
        assert attrs["valid_until"] == c._cache_deadline().isoformat()


async def test_hard_deadline_is_not_extended_by_retries():
    c = make(); old = c.curr_release
    callbacks = []; cancellations = []
    def arm(hass, delay, callback):
        callbacks.append((delay, callback))
        return lambda: cancellations.append(True)
    with patch.object(module, "async_call_later", side_effect=arm):
        await update(c, REQUEST)
        await update(c, REQUEST + timedelta(minutes=3))
        assert len(callbacks) == 1
        assert callbacks[0][0] == pytest.approx(299.999)
        callbacks[0][1](None)
        assert len(c.errors) == 1 and c.retry
        assert c.curr_release == old
        with pytest.raises(UpdateFailed):
            await update(c, c._cache_deadline())
        with pytest.raises(UpdateFailed):
            await update(c, REQUEST + timedelta(hours=1))


async def test_request_crossing_deadline_does_not_return_cached_success():
    c=make();deadline=c._cache_deadline()
    with patch.object(module.dt_util,"utcnow",side_effect=[deadline-timedelta(seconds=1),deadline+timedelta(seconds=1)]):
        with pytest.raises(UpdateFailed):await C._async_update_data(c)


async def test_recovery_cancels_expiry_and_clears_error():
    c = make(); cancelled=[]
    with patch.object(module, "async_call_later", return_value=lambda: cancelled.append(True)):
        await update(c, REQUEST)
    async def good(ts):return 0.0, None
    c._fetch_and_parse=good
    result=await update(c, REQUEST+timedelta(minutes=1))
    assert result.data == 0.0 and not c.retry
    assert c.last_fetch_error is None and c.curr_release == RELEASE
    assert cancelled == [True] and c._expiry_unsub is None
    with patch.object(module.dt_util,"utcnow",return_value=REQUEST+timedelta(minutes=1)):
        assert C.fetch_status_attributes.fget(c)["dwd_fetch"]["status"] == "current"


async def test_no_cache_never_claims_available():
    c=make();c.curr_release=None;c.data=None
    with pytest.raises(UpdateFailed):await update(c,REQUEST)
    assert c.retry and c._expiry_unsub is None


async def test_explicit_disabled_stale_check_is_labelled_expired():
    c=make();c.config_entry.options={"unavailable_when_stale":False}
    at=REQUEST+timedelta(hours=1)
    assert await update(c,at) is c.data
    with patch.object(module.dt_util,"utcnow",return_value=at):
        assert C.fetch_status_attributes.fget(c)["dwd_fetch"]["status"] == "expired"
    assert c._expiry_unsub is None


async def test_unload_cancels_expiry_once():
    c=make();cancelled=[]
    with patch.object(module,"async_call_later",return_value=lambda:cancelled.append(True)):
        await update(c,REQUEST)
    c._cancel_expiry();c._cancel_expiry()
    assert cancelled == [True]


def test_status_in_sensor_attributes_even_without_optional_metadata():
    from .test_sensor import _make_sensor
    from .test_binary_sensor import _make_binary
    diagnostic={"dwd_fetch":{"status":"cached","source_release":RELEASE.isoformat()}}
    for entity in [_make_sensor(None,extra=False),_make_binary({"rain_within_2h":False})]:
        entity.coordinator.fetch_status_attributes=diagnostic
        assert entity.extra_state_attributes["dwd_fetch"] == diagnostic["dwd_fetch"]
