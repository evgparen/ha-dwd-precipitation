"""Maintained-fork regression tests, using real HA imports and isolated state.

Run directly with Python/unittest or alongside the upstream pytest suite.
No network, live HA state, credentials, or actuator calls are used.
"""

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import aiohttp

from custom_components.dwd_precipitation import coordinator as module
from custom_components.dwd_precipitation.coordinator import (
    BaseProductUpdateCoordinator as Coordinator,
    UpdateFailed,
)

RELEASE = datetime(2026, 9, 12, 2, 50, tzinfo=timezone.utc)
REQUEST = RELEASE + timedelta(minutes=4, seconds=10, milliseconds=1)


class RetryRegressionTests(unittest.IsolatedAsyncioTestCase):
    def make_coordinator(self):
        obj = SimpleNamespace(
            USE_LOCAL_TIME=False,
            RELEASE_DELAY=timedelta(minutes=4, seconds=10),
            RELEASE_INTERVAL=timedelta(minutes=5),
            RELEASE_OFFSET=timedelta(),
            STALE_AFTER=timedelta(),
            curr_release=RELEASE - timedelta(minutes=5),
            data=object(),
            config_entry=SimpleNamespace(options={}),
            retry=False,
        )
        obj._get_latest_release = lambda now: Coordinator._get_latest_release(obj, now)
        obj._data_is_stale = lambda now: Coordinator._data_is_stale(obj, now)
        obj._start_fast_polling = lambda: setattr(obj, "retry", True)
        obj._stop_fast_polling = lambda: setattr(obj, "retry", False)
        return obj

    async def update(self, obj, when=REQUEST):
        with patch.object(module.dt_util, "utcnow", return_value=when):
            return await Coordinator._async_update_data(obj)

    async def test_first_failed_release_keeps_retrying_for_each_error_type(self):
        for error in (
            aiohttp.ClientResponseError(None, (), status=404),
            aiohttp.ClientResponseError(None, (), status=503),
            aiohttp.ClientConnectionError("connection lost"),
            TimeoutError("download timed out"),
            ValueError("invalid archive"),
        ):
            with self.subTest(error=type(error).__name__, status=getattr(error, "status", None)):
                obj = self.make_coordinator()
                original_data, original_release = obj.data, obj.curr_release

                async def fetch(ts):
                    self.assertEqual(ts, RELEASE)
                    raise error

                obj._fetch_and_parse = fetch
                with self.assertRaises(UpdateFailed):
                    await self.update(obj)
                self.assertTrue(obj.retry)
                self.assertIs(obj.data, original_data)
                self.assertEqual(obj.curr_release, original_release)

    async def test_late_file_is_retried_with_same_timestamp_and_recovers(self):
        obj = self.make_coordinator()
        timestamps = []

        async def fetch(ts):
            timestamps.append(ts)
            if len(timestamps) == 1:
                raise aiohttp.ClientResponseError(None, (), status=404)
            return 1.0, None

        obj._fetch_and_parse = fetch
        with self.assertRaises(UpdateFailed):
            await self.update(obj)
        result = await self.update(obj, REQUEST + timedelta(seconds=60))
        self.assertEqual(timestamps, [RELEASE, RELEASE])
        self.assertEqual(result.data, 1.0)
        self.assertEqual(obj.curr_release, RELEASE)
        self.assertFalse(obj.retry)

    async def test_initial_failure_has_retry_without_claiming_fresh_data(self):
        obj = self.make_coordinator()
        obj.curr_release, obj.data = None, None

        async def fetch(ts):
            raise TimeoutError("initial download")

        obj._fetch_and_parse = fetch
        with self.assertRaises(UpdateFailed):
            await self.update(obj)
        self.assertTrue(obj.retry)
        self.assertIsNone(obj.curr_release)

    async def test_extended_outage_keeps_old_timestamp_and_unavailable(self):
        obj = self.make_coordinator()
        previous = obj.curr_release

        async def fetch(ts):
            raise aiohttp.ClientResponseError(None, (), status=404)

        obj._fetch_and_parse = fetch
        for minute in range(61):
            with self.assertRaises(UpdateFailed):
                await self.update(obj, REQUEST + timedelta(minutes=minute))
            self.assertTrue(obj.retry)
            self.assertEqual(obj.curr_release, previous)

    async def test_fresh_cache_can_bridge_error_without_renewing_its_age(self):
        obj = self.make_coordinator()
        obj.STALE_AFTER = timedelta(minutes=10)
        previous = obj.curr_release

        async def fetch(ts):
            raise TimeoutError("temporary")

        obj._fetch_and_parse = fetch
        self.assertIs(await self.update(obj), obj.data)
        self.assertTrue(obj.retry)
        self.assertEqual(obj.curr_release, previous)

    async def test_explicit_stale_option_false_remains_supported(self):
        obj = self.make_coordinator()
        obj.config_entry.options = {"unavailable_when_stale": False}

        async def fetch(ts):
            raise TimeoutError("temporary")

        obj._fetch_and_parse = fetch
        self.assertIs(await self.update(obj), obj.data)
        self.assertTrue(obj.retry)

    async def test_cancellation_propagates(self):
        obj = self.make_coordinator()

        async def fetch(ts):
            raise asyncio.CancelledError

        obj._fetch_and_parse = fetch
        with self.assertRaises(asyncio.CancelledError):
            await self.update(obj)
        self.assertFalse(obj.retry)

    def test_stale_boundary_has_no_second_failure_grace_period(self):
        obj = self.make_coordinator()
        exact = REQUEST.replace(microsecond=0)
        self.assertFalse(obj._data_is_stale(exact))
        self.assertTrue(obj._data_is_stale(exact + timedelta(microseconds=1)))

    def test_retry_timer_is_single_and_unload_cleans_up(self):
        callbacks, intervals, cancelled = [], [], []
        obj = SimpleNamespace(
            _fast_poll_unsub=None, hass=object(), PRODUCT_KEY="rv",
            config_entry=SimpleNamespace(async_on_unload=callbacks.append),
        )
        obj._stop_fast_polling = lambda: Coordinator._stop_fast_polling(obj)

        def register(hass, callback, interval):
            intervals.append(interval)
            return lambda: cancelled.append(True)

        with patch.object(module, "async_track_time_interval", register):
            Coordinator._start_fast_polling(obj)
            Coordinator._start_fast_polling(obj)
        self.assertEqual(intervals, [timedelta(seconds=60)])
        callbacks[0]()
        self.assertIsNone(obj._fast_poll_unsub)
        self.assertEqual(cancelled, [True])

    def test_404_message_reports_response_without_inventing_publication_cause(self):
        error = aiohttp.ClientResponseError(None, (), status=404)
        message = module._describe_fetch_error(error, RELEASE)
        self.assertIn("HTTP 404", message)
        self.assertIn("2026-09-12 02:50 UTC", message)
        self.assertNotIn("has not published", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
