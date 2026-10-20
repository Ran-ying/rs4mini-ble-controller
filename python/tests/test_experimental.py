import asyncio
import struct
import unittest
import test_controller as fixtures
from rs4mini_sdk.protocol import frame, crc16
from rs4mini_sdk.telemetry import parse_duml_frame
from rs4mini_sdk.experimental_protocol import rs3_absolute_frame, rs3_rate_frame, research_sleep_frame, decode_research_status


def incoming(sequence, command_set, command_id, payload=b'', sender=4, flags=0x80):
    packet = bytearray(frame(sequence, command_set, command_id, payload, receiver=2, flags=flags))
    packet[4] = sender
    struct.pack_into('<H', packet, len(packet) - 2, crc16(packet[:-2]))
    return bytes(packet)


class ExperimentalTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ControllerTests.asyncSetUp
    asyncTearDown = fixtures.ControllerTests.asyncTearDown

    async def test_research_frame_vectors_and_model_separation(self):
        self.assertEqual(parse_duml_frame(rs3_absolute_frame(1, pan=45, parameterByte=20))['payload'].hex(), 'c201000000000d14')
        self.assertEqual(parse_duml_frame(rs3_rate_frame(1, pan=2))['payload'].hex(), '14000000000080')
        self.assertEqual(parse_duml_frame(research_sleep_frame(1, 'rs3', True))['payload'].hex(), '230101')
        self.assertEqual(parse_duml_frame(research_sleep_frame(1, 'rs3mini', True))['payload'].hex(), '230111')
        with self.assertRaises(ValueError):
            rs3_absolute_frame(1, pan=181, parameterByte=20)
        with self.assertRaises(ValueError):
            rs3_rate_frame(1, pan=float('nan'))

    async def test_profile_is_explicit_and_invalid_queries_cannot_send_other_commands(self):
        with self.assertRaises(ValueError):
            await self.gimbal.experimental.set_sleep(asleep=True)
        self.gimbal.experimental.use_profile('rs3mini')
        with self.assertRaises(ValueError):
            await self.gimbal.experimental.absolute(pan=0, parameterByte=20)
        with self.assertRaises(ValueError):
            await self.gimbal.experimental.query(kind='calibrate')
        self.assertEqual(self.client.frames(), [])

    async def test_query_correlation_and_reserved_sequence(self):
        self.gimbal.experimental.useProfile('rs3')
        task = asyncio.create_task(self.gimbal.experimental.query(kind='type'))
        await fixtures.until(lambda: self.client.frames())
        sent = self.client.frames()[0]
        seq = sent['sequence']
        for packet in [incoming(seq + 1, 4, 0x1c), incoming(seq, 4, 2), incoming(seq, 4, 0x1c, sender=5), incoming(seq, 4, 0x1c, flags=0)]:
            self.client.notify(None, packet)
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        self.gimbal.sequence = seq
        await self.gimbal.setVelocity(pan=.05)
        self.assertNotEqual(self.client.frames()[1]['sequence'], seq)
        self.client.notify(None, incoming(seq, 4, 0x1c, bytes([0, 42])))
        self.assertEqual((await task)['payload'][1], 42)
        self.assertFalse(self.gimbal.experimental.pending)

    async def test_query_timeout_and_disconnect_clear_pending_waits(self):
        self.gimbal.experimental.useProfile('rs3')
        with self.assertRaises(Exception) as timeout:
            await self.gimbal.experimental.query(kind='type', timeoutMs=10)
        self.assertEqual(timeout.exception.code, 'RS4MINI_RESPONSE_TIMEOUT')
        task = asyncio.create_task(self.gimbal.experimental.query(kind='version'))
        await fixtures.until(lambda: self.gimbal.experimental.pending)
        await self.client.disconnect()
        with self.assertRaises(Exception) as disconnected:
            await task
        self.assertEqual(disconnected.exception.code, 'RS4MINI_DISCONNECTED')
        self.assertFalse(self.gimbal.experimental.pending)

    async def test_expired_queued_query_cannot_send_after_motion_write_unlocks(self):
        self.gimbal.experimental.useProfile('rs3')
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.client.write_gatt_char
        async def blocked(*args, **kwargs):
            entered.set()
            await release.wait()
            await original(*args, **kwargs)
        self.client.write_gatt_char = blocked
        self.gimbal.ioTimeoutMs = 500
        moving = asyncio.create_task(self.gimbal.setVelocity(pan=.05))
        await entered.wait()
        with self.assertRaises(Exception) as timeout:
            await self.gimbal.experimental.query(kind='type', timeoutMs=5)
        self.assertEqual(timeout.exception.code, 'RS4MINI_RESPONSE_TIMEOUT')
        release.set()
        await moving
        await self.gimbal.stop()
        self.assertTrue(self.gimbal.connected)
        self.assertTrue(all(item['commandId'] == 1 for item in self.client.frames()))

    async def test_native_rate_cancel_releases_before_neutrals(self):
        self.gimbal.experimental.useProfile('rs3')
        task = asyncio.create_task(self.gimbal.experimental.rate_for(pan=2, duration_ms=10000))
        await fixtures.until(lambda: self.client.frames())
        await self.gimbal.stop()
        with self.assertRaises(Exception) as cancelled:
            await task
        self.assertEqual(cancelled.exception.code, 'RS4MINI_MOVE_CANCELLED')
        frames = self.client.frames()
        self.assertEqual(frames[0]['payload'][-1], 0x80)
        self.assertEqual(frames[-4]['commandId'], 0x0c)
        self.assertEqual(frames[-4]['payload'], b'\0' * 7)
        self.assertTrue(all(item['commandId'] == 1 for item in frames[-3:]))

    async def test_absolute_owns_observation_and_sleep_ends_after_command(self):
        self.gimbal.experimental.useProfile('rs3')
        task = asyncio.create_task(self.gimbal.experimental.absolute(pan=2, parameterByte=20, observeMs=10000))
        await fixtures.until(lambda: any(item['commandId'] == 0x14 for item in self.client.frames()))
        await self.gimbal.stop()
        with self.assertRaises(Exception) as cancelled:
            await task
        self.assertEqual(cancelled.exception.code, 'RS4MINI_MOVE_CANCELLED')
        result = await self.gimbal.experimental.setSleep(asleep=True)
        self.assertFalse(result['physicalCompletionVerified'])
        self.assertEqual(self.client.frames()[-1]['commandId'], 0x0f)

    async def test_passive_status_is_profile_specific_copied_and_reset(self):
        self.gimbal.experimental.useProfile('rs3mini')
        payload = bytearray(21)
        struct.pack_into('<i', payload, 1, -123)
        payload[20] = 67
        packet = incoming(1, 0x0d, 2, payload, sender=0xe5)
        message = parse_duml_frame(packet)
        self.assertEqual(decode_research_status(message, 'rs3mini')['batteryPercent'], 67)
        self.assertIsNone(decode_research_status(message, 'rs3')['batteryPercent'])
        self.client.notify(None, packet)
        snapshot = self.gimbal.experimental.status
        snapshot['battery-status']['batteryPercent'] = 0
        self.assertEqual(self.gimbal.experimental.status['battery-status']['batteryPercent'], 67)
        self.assertFalse(self.gimbal.experimental.status['battery-status']['deviceVerified'])
        await self.gimbal.disconnect()
        self.assertEqual(self.gimbal.experimental.status, {})

    async def test_legacy_parameter_response_records_and_malformed_payloads(self):
        msg = lambda command, payload, flags=0x80: parse_duml_frame(incoming(1, 4, command, bytes(payload), flags=flags))
        value = decode_research_status(msg(0x10, [0, 18, 1, 0]), 'rs3')
        self.assertEqual(value['parameters'], [dict(index=18, size=1, rawHex='00')])
        self.assertFalse(value['deviceVerified'])
        self.assertEqual(value['layoutSource'], 'legacy-duml')
        value = decode_research_status(msg(0x10, [5, 18, 1, 0, 18, 2, 255, 255, 255, 62, 8] + [255] * 8), 'rs3mini')
        self.assertEqual(value['statusCode'], 5)
        self.assertEqual(value['parameters'], [dict(index=18, size=1, rawHex='00'), dict(index=18, size=2, rawHex='ffff'), dict(errorCode=-1), dict(index=62, size=8, rawHex='ffffffffffffffff')])
        self.assertEqual(decode_research_status(msg(0x0f, [7]), 'rs3')['statusCode'], 7)
        for payload in ([], [0, 18], [0, 18, 0], [0, 18, 3, 1, 2, 3], [0, 18, 2, 1]):
            self.assertIsNone(decode_research_status(msg(0x10, payload), 'rs3'))
        self.assertIsNone(decode_research_status(msg(0x10, [0, 18, 1, 0], 0x40), 'rs3'))
        self.assertIsNone(decode_research_status(msg(0x0f, [7], 0), 'rs3'))

    async def test_parameter_responses_are_passive_and_profile_gated(self):
        packet = incoming(1, 4, 0x10, bytes([0, 18, 1, 0]))
        self.client.notify(None, packet)
        self.assertEqual(self.gimbal.experimental.status, {})
        self.gimbal.experimental.useProfile('rs3')
        self.client.notify(None, packet)
        value = self.gimbal.experimental.status
        value['user-parameters']['parameters'][0]['rawHex'] = 'ff'
        self.assertEqual(self.gimbal.experimental.status['user-parameters']['parameters'][0]['rawHex'], '00')
        self.assertEqual(self.client.frames(), [])
