import asyncio
import struct
import unittest
import test_controller as fixtures
from rs4mini_sdk import orientation_from_components
from rs4mini_sdk.protocol import frame
from rs4mini_sdk.expansion import velocity_keyframes, interpolate_velocity


class ExpansionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ControllerTests.asyncSetUp
    asyncTearDown = fixtures.ControllerTests.asyncTearDown

    async def test_orientation_order_math_and_short_frame_wait(self):
        q = [2 ** -.5, 0, 0, 2 ** -.5]
        self.assertAlmostEqual(orientation_from_components(q, component_order='wxyz')['euler']['yaw'], 90)
        self.assertAlmostEqual(orientation_from_components(q, component_order='wxyz', conjugate=True)['euler']['yaw'], -90)
        with self.assertRaises(ValueError):
            orientation_from_components([0, 0, 0, 0], component_order='wxyz')
        task = asyncio.create_task(self.gimbal.get_orientation(component_order='xyzw', fresh=True))
        await fixtures.until(lambda: self.gimbal._waiters)
        self.client.telemetry(short=True)
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        payload = bytearray(49)
        struct.pack_into('<f', payload, 36, 1)
        self.client.notify(None, frame(1, 4, 5, payload))
        result = await task
        self.assertEqual(result['quaternion']['w'], 1)
        self.assertFalse(result['deviceConventionVerified'])
        self.client.telemetry()
        with self.assertRaises(Exception) as bad:
            await self.gimbal.getOrientation(componentOrder='wxyz')
        self.assertEqual(bad.exception.code, 'RS4MINI_ORIENTATION_INVALID')

    async def test_interpolation_validation_and_copy(self):
        original = [dict(timeMs=0, pan=1), dict(timeMs=100, tilt=-1)]
        points = velocity_keyframes(original, 'linear')
        original[0]['pan'] = -1
        self.assertEqual(interpolate_velocity(points, 25, 'linear'), dict(pan=.75, tilt=-.25, roll=0))
        self.assertEqual(interpolate_velocity(points, 25, 'smoothstep')['pan'], .84375)
        self.assertEqual(interpolate_velocity(points, 99, 'step')['pan'], 1)
        for bad in [[], [dict(timeMs=1), dict(timeMs=2)], [dict(timeMs=0), dict(timeMs=0)], [dict(timeMs=0, pan=2), dict(timeMs=1)]]:
            with self.assertRaises(ValueError):
                velocity_keyframes(bad, 'linear')

    async def test_trajectory_writes_and_neutral_completion(self):
        self.gimbal.rateHz = 100
        result = await self.gimbal.run_trajectory([dict(timeMs=0, pan=.1), dict(timeMs=60, tilt=-.1)])
        self.assertGreaterEqual(result['sentFrames'], 2)
        frames = self.client.frames()
        self.assertEqual(len(frames), result['sentFrames'] + 3)
        self.assertLess(struct.unpack_from('<h', frames[-4]['payload'], 0)[0], 1024)
        for item in frames[-3:]:
            self.assertEqual(struct.unpack_from('<hhh', item['payload']), (1024, 1024, 1024))
        self.assertIsNone(self.gimbal.trajectory_progress)

    async def test_trajectory_cancellation_and_ownership(self):
        task = asyncio.create_task(self.gimbal.runTrajectory([dict(timeMs=0, pan=.1), dict(timeMs=10000, pan=.1)]))
        await fixtures.until(lambda: self.client.frames())
        with self.assertRaises(Exception) as busy:
            await self.gimbal.moveTo(pan=1)
        self.assertEqual(busy.exception.code, 'RS4MINI_BUSY')
        await self.gimbal.stop()
        with self.assertRaises(Exception) as cancelled:
            await task
        self.assertEqual(cancelled.exception.code, 'RS4MINI_MOVE_CANCELLED')
        await self.gimbal.setVelocity(tilt=.1)
        await self.gimbal.stop()

    async def test_slow_trajectory_write_fails_and_stops(self):
        self.gimbal.ioTimeoutMs = 100
        original = self.client.write_gatt_char
        async def slow(*args, **kwargs):
            await asyncio.sleep(.01)
            await original(*args, **kwargs)
        self.client.write_gatt_char = slow
        with self.assertRaises(Exception) as error:
            await self.gimbal.runTrajectory([dict(timeMs=0, pan=.1), dict(timeMs=100, pan=.1)], maxLagMs=5)
        self.assertEqual(error.exception.code, 'RS4MINI_TRAJECTORY_OVERRUN')
        self.assertEqual(len(self.client.frames()), 4)

    async def test_waypoints_validate_before_motion_and_cancel_dwell(self):
        with self.assertRaises(ValueError):
            await self.gimbal.moveThrough([dict(pan=1), dict(pan=181)])
        self.assertFalse(self.client.frames())
        task = asyncio.create_task(self.gimbal.move_through([dict(pan=3), dict(tilt=2, holdMs=10000)]))
        await fixtures.until(lambda: self.gimbal._waiters)
        self.client.telemetry(yaw=3)
        await fixtures.until(lambda: self.gimbal.trajectory_progress['index'] == 1 and self.gimbal._waiters)
        self.client.telemetry(pitch=2)
        await fixtures.until(lambda: len(self.client.frames()) >= 6)
        await self.gimbal.stop()
        with self.assertRaises(Exception) as error:
            await task
        self.assertEqual(error.exception.code, 'RS4MINI_MOVE_CANCELLED')

    async def test_home_is_device_bound_copied_and_axis_selective(self):
        with self.assertRaises(Exception) as unset:
            await self.gimbal.moveHome()
        self.assertEqual(unset.exception.code, 'RS4MINI_HOME_UNSET')
        self.client.telemetry(yaw=4, pitch=3, roll=2)
        home = await self.gimbal.capture_home()
        home['pan'] = 99
        self.assertEqual(self.gimbal.home['pan'], 4)
        task = asyncio.create_task(self.gimbal.move_home(axes=['pan']))
        await fixtures.until(lambda: self.gimbal._waiters)
        self.client.telemetry(yaw=4, pitch=20)
        self.assertEqual((await task)['target'], dict(pan=4))
        self.gimbal.deviceId = 'OTHER'
        with self.assertRaises(Exception) as other:
            await self.gimbal.moveHome()
        self.assertEqual(other.exception.code, 'RS4MINI_HOME_UNSET')

    async def test_reconnect_restores_link_without_motion(self):
        states = []
        self.gimbal.on_reconnect = lambda state: states.append(state['state'])
        self.gimbal.enable_auto_reconnect(initial_delay_ms=2, max_delay_ms=5, max_attempts=2)
        await self.gimbal.setVelocity(pan=.1)
        await self.client.disconnect()
        await fixtures.until(lambda: self.gimbal.reconnect_state['state'] == 'restored')
        self.assertTrue(self.gimbal.connected)
        self.assertFalse(any(self.gimbal.velocity.values()))
        self.assertEqual(self.clients[-1].writes, [])
        self.assertEqual(states, ['idle', 'waiting', 'connecting', 'restored'])

    async def test_retries_exhaust_and_manual_disconnect_disables(self):
        self.gimbal.enableAutoReconnect(initialDelayMs=2, maxDelayMs=5, maxAttempts=2, timeoutMs=15, directConnectTimeoutMs=5)
        class OfflineScanner:
            @staticmethod
            async def find_device_by_filter(*args, **kwargs):
                return None
        def factory(*args, **kwargs):
            candidate = fixtures.FakeClient(*args, **kwargs)
            async def offline():
                raise RuntimeError('offline')
            candidate.connect = offline
            return candidate
        self.gimbal._factory, self.gimbal._scanner = factory, OfflineScanner
        await self.client.disconnect()
        await fixtures.until(lambda: self.gimbal.reconnect_state['state'] == 'exhausted')
        self.assertEqual(self.gimbal.reconnect_state['attempt'], 2)
        await self.gimbal.disconnect()
        self.assertEqual(self.gimbal.reconnect_state['state'], 'disabled')

    async def test_disable_retry_during_pending_connection_cleans_it(self):
        entered = asyncio.Event()
        def factory(*args, **kwargs):
            candidate = fixtures.FakeClient(*args, **kwargs)
            async def hanging():
                entered.set()
                await asyncio.Event().wait()
            candidate.connect = hanging
            return candidate
        self.gimbal._factory = factory
        self.gimbal.enableAutoReconnect(initialDelayMs=2, maxDelayMs=5)
        await self.client.disconnect()
        await entered.wait()
        await self.gimbal.disable_auto_reconnect()
        self.assertIsNone(self.gimbal._connectTask)
        self.assertIsNone(self.gimbal._reconnectTask)
        self.assertFalse(self.gimbal.connected)

    async def test_invalid_retry_policy_and_manual_cancel_waiting(self):
        for options in [dict(maxAttempts=1.5), dict(backoff=.5), dict(maxDelayMs=1)]:
            with self.assertRaises(ValueError):
                self.gimbal.enableAutoReconnect(**options)
        self.gimbal.enableAutoReconnect(initialDelayMs=500, maxDelayMs=500)
        await self.client.disconnect()
        await fixtures.until(lambda: self.gimbal.reconnect_state['state'] == 'waiting')
        await self.gimbal.disconnect()
        self.assertIsNone(self.gimbal._reconnectTask)
        self.assertEqual(len(self.clients), 1)

    async def test_waypoint_dwell_does_not_exhaust_leg_timeout(self):
        task = asyncio.create_task(self.gimbal.moveThrough([dict(pan=2, holdMs=40), dict(tilt=3)], timeoutMs=20))
        await fixtures.until(lambda: self.gimbal._waiters)
        self.client.telemetry(yaw=2)
        await fixtures.until(lambda: self.gimbal.trajectoryProgress['index'] == 1 and self.gimbal._waiters)
        self.client.telemetry(pitch=3)
        self.assertEqual([item['target'] for item in await task], [dict(pan=2), dict(tilt=3)])

    async def test_failed_write_recovers_link_without_replaying_command(self):
        async def broken(*args, **kwargs):
            raise RuntimeError('write lost')
        self.client.write_gatt_char = broken
        self.gimbal.enableAutoReconnect(initialDelayMs=2, maxDelayMs=5)
        with self.assertRaises(RuntimeError):
            await self.gimbal.setVelocity(pan=.1)
        await fixtures.until(lambda: self.gimbal.reconnectState['state'] == 'restored')
        self.assertEqual(self.clients[-1].writes, [])
