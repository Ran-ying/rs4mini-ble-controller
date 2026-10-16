import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply, sent


class AppSettingsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ControllerTests.asyncSetUp
    asyncTearDown = fixtures.ControllerTests.asyncTearDown

    async def test_custom_follow_reads_fresh_flags_and_preserves_other_axes(self):
        self.gimbal.app_commands.use_profile('ronin-2.2.2')
        task = asyncio.create_task(self.gimbal.app_commands.set_custom_follow_settings(enabled=True, pitch=False))
        await fixtures.until(lambda: sent(self.client, 0x10))
        request = sent(self.client, 0x10)
        self.assertEqual(request['payload'], b'\x84')
        with self.assertRaises(Exception) as busy:
            await self.gimbal.setVelocity(pan=.1)
        self.assertEqual(busy.exception.code, 'RS4MINI_BUSY')
        reply(self.client, request, [0,132,9,14])
        await fixtures.until(lambda: sent(self.client, 0x0f))
        write = sent(self.client, 0x0f)
        self.assertEqual(write['payload'].hex(), '84010d')
        self.assertNotEqual(write['sequence'], request['sequence'])
        reply(self.client, write, [0])
        result = await task
        self.assertEqual(result['previousRawValue'], 14)
        self.assertEqual(result['requestedRawValue'], 13)
        self.assertFalse(result['physicalCompletionVerified'])

    async def test_motor_inversion_and_unknown_bits(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task = asyncio.create_task(self.gimbal.appCommands.setMotorSettings(enabled=True, forbidSelfie=True, roll360=False))
        await fixtures.until(lambda: sent(self.client, 0x10))
        reply(self.client, sent(self.client, 0x10), [0,35,1,207])
        await fixtures.until(lambda: sent(self.client, 0x0f))
        self.assertEqual(sent(self.client, 0x0f)['payload'].hex(), '23019e')
        reply(self.client, sent(self.client, 0x0f), [0])
        self.assertEqual((await task)['requestedRawValue'], 158)
        count = len(self.client.frames())
        read = asyncio.create_task(self.gimbal.appCommands.getMotorSettings())
        await fixtures.until(lambda: len(self.client.frames()) > count)
        reply(self.client, sent(self.client, 0x10), [0,35,1,158])
        result = await read
        self.assertEqual(result['unknownBits'], 142)
        self.assertEqual(result['settings'], dict(enabled=True, forbidSelfie=True, forbidVertical=False, roll360=False))

    async def test_rejected_truncated_or_out_of_range_reads_do_not_write(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for payload, code in [([7], 'RS4MINI_DEVICE_ERROR'), ([0,132,1], 'RS4MINI_PROTOCOL_ERROR'), ([0,132,1,128], 'RS4MINI_UNSUPPORTED_VALUE')]:
            old_request = sent(self.client, 0x10)
            task = asyncio.create_task(self.gimbal.appCommands.setCustomFollowSettings(yaw=True))
            await fixtures.until(lambda: sent(self.client, 0x10) is not None and sent(self.client, 0x10) != old_request)
            reply(self.client, sent(self.client, 0x10), payload)
            with self.assertRaises(Exception) as failed:
                await task
            self.assertEqual(failed.exception.code, code)
        self.assertIsNone(sent(self.client, 0x0f))
        self.assertFalse(self.gimbal.experimental.pending)

    async def test_stop_before_read_response_prevents_write(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task = asyncio.create_task(self.gimbal.appCommands.setMotorSettings(enabled=False))
        await fixtures.until(lambda: sent(self.client, 0x10))
        old = sent(self.client, 0x10)
        await self.gimbal.stop()
        with self.assertRaises(Exception) as cancelled:
            await task
        self.assertEqual(cancelled.exception.code, 'RS4MINI_OPERATION_CANCELLED')
        reply(self.client, old, [0,35,1,0])
        await asyncio.sleep(0)
        self.assertIsNone(sent(self.client, 0x0f))
        self.assertFalse(self.gimbal.experimental.pending)

    async def test_invalid_fields_and_unknown_read_bits(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for fields in [{}, dict(yaw=1), dict(enabled=None), dict(preset='PF'), dict(roll=True,timeoutMs=True)]:
            with self.assertRaises((ValueError, TypeError)):
                await self.gimbal.appCommands.setCustomFollowSettings(**fields)
        self.assertEqual(self.client.frames(), [])
        task = asyncio.create_task(self.gimbal.appCommands.getCustomFollowSettings())
        await fixtures.until(lambda: sent(self.client, 0x10))
        reply(self.client, sent(self.client, 0x10), [0,132,1,137])
        result = await task
        self.assertEqual(result['rawValue'], 137)
        self.assertEqual(result['unknownBits'], 128)
        self.assertEqual(result['settings'], dict(enabled=True,pitch=False,roll=False,yaw=True))

    async def test_ack_uses_remaining_transaction_deadline(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from rs4mini_sdk.app_commands import AppCommands
        clock, timeouts = [1.0], []
        async def halt():
            pass
        async def run(name, body, stop_after):
            return await body(dict(cancel=asyncio.Event(), error=None))
        async def query(name, command, payload, timeout, **kwargs):
            timeouts.append(timeout)
            if command[1] == 0x10:
                clock[0] += .075
                payload = bytes([0,132,1,0])
            else:
                payload = bytes([0])
            return dict(sender=4,receiver=2,commandSet=4,commandId=command[1],flags=128,payload=payload)
        owner = SimpleNamespace(_halt=halt, _check=lambda op: None, _epoch=1, _run=run,
                                experimental=SimpleNamespace(_query_payload_command=query))
        app = AppCommands(owner)
        app._profile = 'ronin-2.2.2'
        with patch('rs4mini_sdk.app_commands.time', SimpleNamespace(monotonic=lambda: clock[0])):
            await app.setCustomFollowSettings(yaw=True,timeoutMs=100)
        self.assertAlmostEqual(timeouts[0], 100)
        self.assertAlmostEqual(timeouts[1], 25)
