import asyncio
import struct
import unittest
from types import SimpleNamespace
from rs4mini_sdk import RS4Mini, DumlStreamDecoder, decode_gimbal_telemetry
from rs4mini_sdk.protocol import frame, rc_units


async def until(predicate):
    deadline = asyncio.get_running_loop().time() + 1
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError('Condition not reached')
        await asyncio.sleep(0)


class FakeClient:
    def __init__(self, device, disconnected_callback):
        self.address = getattr(device, 'address', device)
        self.name = getattr(device, 'name', 'DJI RS4 MINI-TEST')
        self.callback = disconnected_callback
        self.is_connected = False
        self.writes = []
        self.notify = None
        self.disconnects = 0

    async def connect(self):
        self.is_connected = True

    async def start_notify(self, characteristic, callback):
        self.notify = callback

    async def stop_notify(self, characteristic):
        self.notify = None

    async def disconnect(self):
        self.disconnects += 1
        self.is_connected = False
        self.callback(self)

    async def write_gatt_char(self, characteristic, data, response):
        self.writes.append(bytes(data))

    def telemetry(self, yaw=0, pitch=0, roll=0, short=False):
        payload = bytearray(6 if short else 49)
        if not short:
            struct.pack_into('<h', payload, 16, round(yaw * 100))
            struct.pack_into('<hh', payload, 20, round(pitch * 10), round(roll * 10))
        if self.notify:
            self.notify(None, bytearray(frame(1, 4, 5, payload)))

    def frames(self):
        return DumlStreamDecoder().push(b''.join(self.writes))


class Scanner:
    calls = 0

    @classmethod
    async def find_device_by_filter(cls, predicate, timeout):
        cls.calls += 1
        device = SimpleNamespace(name='DJI RS 4 MINI-TEST', address='TEST-ID')
        assert predicate(device, SimpleNamespace(local_name=device.name))
        return device


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clients = []
        def factory(*args, **kwargs):
            client = FakeClient(*args, **kwargs)
            self.clients.append(client)
            return client
        self.gimbal = RS4Mini(client_factory=factory, scanner=Scanner, rateHz=1000, ioTimeoutMs=30)
        await self.gimbal.connect()
        self.client = self.clients[-1]

    async def asyncTearDown(self):
        try:
            await self.gimbal.close()
        except Exception:
            pass

    async def test_readings_copies_fresh_and_short_frame_filter(self):
        self.client.telemetry(yaw=12.34)
        value = await self.gimbal.getJointAngles()
        value['raw']['yaw'] = 999
        self.assertEqual((await self.gimbal.getJointAngles())['raw']['yaw'], 1234)
        task = asyncio.create_task(self.gimbal.get_joint_angles(fresh=True))
        await until(lambda: self.gimbal._waiters)
        self.client.telemetry(short=True)
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        self.client.telemetry(yaw=5)
        self.assertEqual((await task)['yaw'], 5)

    async def test_callbacks_do_not_break_feedback(self):
        errors = []
        def broken(_):
            raise ValueError('callback')
        async def async_broken(_):
            raise ValueError('async callback')
        self.gimbal.on_notification = broken
        self.gimbal.on_message = async_broken
        self.gimbal.on_error = errors.append
        task = asyncio.create_task(self.gimbal.getAttitude(fresh=True))
        await until(lambda: self.gimbal._waiters)
        self.client.telemetry()
        self.assertEqual((await task)['unit'], 'deg')
        await until(lambda: len(errors) == 2)

    async def test_multi_axis_tolerance_direction_and_cleanup(self):
        task = asyncio.create_task(self.gimbal.move_to(pan=5, tilt=5, roll=-4))
        await until(lambda: self.gimbal._waiters)
        self.client.telemetry(yaw=4.5)
        await until(lambda: self.client.frames())
        payload = self.client.frames()[0]['payload']
        tilt, roll, pan = struct.unpack_from('<hhh', payload)
        self.assertEqual(pan, 1024)
        self.assertLess(tilt, 1024)
        self.assertLess(roll, 1024)
        await until(lambda: self.gimbal._waiters)
        self.client.telemetry(yaw=4.5, pitch=4.5, roll=-3.5)
        result = await task
        self.assertEqual(result['current']['pan'], 4.5)
        self.assertFalse(self.gimbal.move_to_active)

    async def test_stop_cancels_telemetry_wait_and_holds_ownership(self):
        task = asyncio.create_task(self.gimbal.moveTo(pan=30))
        await until(lambda: self.gimbal._waiters)
        with self.assertRaises(Exception) as conflict:
            await self.gimbal.moveFor(durationMs=0)
        self.assertEqual(conflict.exception.code, 'RS4MINI_BUSY')
        await self.gimbal.stop()
        with self.assertRaises(Exception) as cancelled:
            await task
        self.assertEqual(cancelled.exception.code, 'RS4MINI_MOVE_CANCELLED')
        self.assertFalse(self.gimbal._waiters)

    async def test_duration_cancel_cannot_stop_later_velocity(self):
        task = asyncio.create_task(self.gimbal.moveFor(durationMs=60, pan=0.1))
        await until(lambda: self.gimbal._streamTask)
        await self.gimbal.stop()
        with self.assertRaises(Exception) as cancelled:
            await task
        self.assertEqual(cancelled.exception.code, 'RS4MINI_MOVE_CANCELLED')
        await self.gimbal.set_velocity(tilt=0.1)
        await asyncio.sleep(0.07)
        self.assertEqual(self.gimbal.velocity['tilt'], 0.1)

    async def test_total_and_telemetry_timeout_are_distinct(self):
        with self.assertRaises(Exception) as total:
            await self.gimbal.moveTo(pan=3, timeoutMs=20, telemetryTimeoutMs=500)
        self.assertEqual(total.exception.code, 'RS4MINI_MOVE_TIMEOUT')
        self.assertIsNone(total.exception.current)
        with self.assertRaises(Exception) as telemetry:
            await self.gimbal.moveTo(pan=3, timeoutMs=500, telemetryTimeoutMs=20)
        self.assertEqual(telemetry.exception.code, 'RS4MINI_TELEMETRY_TIMEOUT')

    async def test_stop_inflight_finishes_first_frame_before_neutrals(self):
        block = asyncio.Event()
        entered = asyncio.Event()
        original = self.client.write_gatt_char
        async def write(*args, **kwargs):
            if not entered.is_set():
                entered.set()
                await block.wait()
            await original(*args, **kwargs)
        self.client.write_gatt_char = write
        motion = asyncio.create_task(self.gimbal.setVelocity(pan=0.2))
        await entered.wait()
        stopping = asyncio.create_task(self.gimbal.stop())
        await until(lambda: self.gimbal._operation['cancel'].is_set())
        block.set()
        await stopping
        with self.assertRaises(Exception):
            await motion
        frames = self.client.frames()
        self.assertEqual(len(frames), 4)
        self.assertGreater(struct.unpack_from('<h', frames[0]['payload'], 4)[0], 1024)
        self.assertTrue(all(struct.unpack_from('<h', item['payload'], 4)[0] == 1024 for item in frames[1:]))

    async def test_failure_disconnects_and_reconnect_does_not_restart_motion(self):
        async def hang(*args, **kwargs):
            await asyncio.Event().wait()
        self.client.write_gatt_char = hang
        with self.assertRaises(Exception) as error:
            await self.gimbal.setVelocity(pan=0.2)
        self.assertEqual(error.exception.code, 'RS4MINI_IO_TIMEOUT')
        self.assertFalse(self.gimbal.connected)
        await until(lambda: self.client.disconnects)
        await self.gimbal.connect()
        self.assertEqual(self.clients[-1].writes, [])

    async def test_disconnect_rejects_readers_removes_notify_and_reuses_instance(self):
        read = asyncio.create_task(self.gimbal.getAttitude(fresh=True))
        await until(lambda: self.gimbal._waiters)
        await self.gimbal.disconnect()
        with self.assertRaises(Exception) as error:
            await read
        self.assertEqual(error.exception.code, 'RS4MINI_DISCONNECTED')
        self.assertIsNone(self.client.notify)
        await self.gimbal.connect()
        self.assertTrue(self.gimbal.connected)

    async def test_unexpected_disconnect_cancels_motion(self):
        motion = asyncio.create_task(self.gimbal.moveFor(pan=0.1, durationMs=10000))
        await until(lambda: self.gimbal._streamTask)
        await self.client.disconnect()
        with self.assertRaises(Exception) as error:
            await motion
        self.assertEqual(error.exception.code, 'RS4MINI_MOVE_CANCELLED')

    async def test_external_task_cancellation_cleans_up_and_stays_cancelled_error(self):
        motion = asyncio.create_task(self.gimbal.moveTo(pan=10))
        await until(lambda: self.gimbal._waiters)
        motion.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await motion
        self.assertFalse(self.gimbal._waiters)
        self.assertIsNone(self.gimbal.activeOperation)
        self.assertEqual(len(self.client.frames()), 3)

    async def test_state_snapshots_and_background_write_error_reporting(self):
        self.client.telemetry(yaw=2)
        self.gimbal.latestTelemetry['jointAngles']['yaw'] = 999
        self.assertEqual((await self.gimbal.getJointAngles())['yaw'], 2)
        await self.gimbal.setVelocity(pan=0.1)
        self.gimbal.velocity['pan'] = 1
        self.assertEqual(self.gimbal.velocity['pan'], 0.1)
        errors = []
        self.gimbal.onError = errors.append
        async def broken(*args, **kwargs):
            raise RuntimeError('stream failed')
        self.client.write_gatt_char = broken
        await until(lambda: errors)
        self.assertIn('stream failed', str(errors[0]))

    async def test_explicit_none_device_id_bypasses_cached_direct_connection(self):
        await self.gimbal.disconnect()
        before = Scanner.calls
        await self.gimbal.connect(deviceId=None)
        self.assertEqual(Scanner.calls, before + 1)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_late_connection_is_disposed_after_close(self):
        release, entered = asyncio.Event(), asyncio.Event()
        clients = []
        def factory(*args, **kwargs):
            candidate = FakeClient(*args, **kwargs)
            async def late_connect():
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                candidate.is_connected = True
            candidate.connect = late_connect
            clients.append(candidate)
            return candidate
        gimbal = RS4Mini(client_factory=factory, scanner=Scanner, ioTimeoutMs=30)
        connecting = asyncio.create_task(gimbal.connect(deviceId='TEST-ID'))
        await entered.wait()
        await gimbal.close()
        with self.assertRaises(Exception) as error:
            await connecting
        self.assertEqual(error.exception.code, 'RS4MINI_CONNECT_CANCELLED')
        release.set()
        await until(lambda: clients[0].disconnects >= 2 and not clients[0].is_connected)
        self.assertFalse(gimbal.connected)

    async def test_connection_deadlines_and_close_at_each_stage(self):
        for stage in ('scan', 'direct', 'connect', 'subscribe'):
            for action in ('timeout', 'close'):
                with self.subTest(stage=stage, action=action):
                    entered = asyncio.Event()
                    clients = []
                    async def blocked(*args, **kwargs):
                        entered.set()
                        await asyncio.Event().wait()
                    class LocalScanner:
                        find_device_by_filter = staticmethod(blocked if stage == 'scan' else Scanner.find_device_by_filter)
                    def factory(*args, **kwargs):
                        client = FakeClient(*args, **kwargs)
                        if stage in ('connect', 'direct'):
                            client.connect = blocked
                        if stage == 'subscribe':
                            client.start_notify = blocked
                        clients.append(client)
                        return client
                    gimbal = RS4Mini(client_factory=factory, scanner=LocalScanner, ioTimeoutMs=30, rateHz=1000)
                    task = asyncio.create_task(gimbal.connect(timeoutMs=20 if action == 'timeout' else 10000,
                                                              deviceId='TEST-ID' if stage == 'direct' else None))
                    await entered.wait()
                    if action == 'close':
                        await gimbal.close()
                    with self.assertRaises(Exception) as error:
                        await task
                    self.assertEqual(error.exception.code, 'RS4MINI_CONNECT_TIMEOUT' if action == 'timeout' else 'RS4MINI_CONNECT_CANCELLED')
                    await gimbal.close()
                    self.assertFalse(gimbal.connected)


class TelemetryTests(unittest.TestCase):
    def test_crc_reassembly_mapping_and_recovery(self):
        payload = bytearray(49)
        struct.pack_into('<hhh', payload, 0, -123, 45, 901)
        struct.pack_into('<h', payload, 16, 12345)
        struct.pack_into('<hh', payload, 20, -67, 89)
        struct.pack_into('<ffff', payload, 24, 1, 0, 0, 0)
        packet = frame(1, 4, 5, payload)
        decoder = DumlStreamDecoder()
        self.assertEqual(decoder.push(packet[:20]), [])
        messages = decoder.push(packet[20:] + packet)
        self.assertEqual(len(messages), 2)
        sample = decode_gimbal_telemetry(messages[0])
        self.assertEqual(sample['attitude']['pitch'], -12.3)
        self.assertEqual(sample['jointAngles']['yaw'], 123.45)
        self.assertEqual(sample['jointAngles']['pitch'], -6.7)
        self.assertEqual(sample['orientationQuaternion']['norm'], 1)
        bad = bytearray(packet)
        bad[-1] ^= 1
        recovered = decoder.push(bad + packet)
        self.assertEqual(len(recovered), 1)
        self.assertGreater(decoder.invalidFrames, 0)

    def test_half_steps_match_javascript_rounding(self):
        for half, expected in [(0.5, 1025), (-0.5, 1024), (1.5, 1026), (-1.5, 1023)]:
            self.assertEqual(rc_units(half / 660), expected)
        with self.assertRaises(ValueError):
            rc_units(float('nan'))
