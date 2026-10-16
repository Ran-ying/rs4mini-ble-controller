import asyncio
import struct
import unittest
import test_controller as fixtures
from rs4mini_sdk.protocol import frame, crc16


def reply(client, sent, payload, mutate=None):
    raw = bytearray(frame(sent['sequence'], 4, sent['commandId'], bytes(payload), flags=0x80))
    raw[4], raw[5] = 4, 2
    if mutate:
        mutate(raw)
    struct.pack_into('<H', raw, len(raw)-2, crc16(raw[:-2]))
    client.notify(None, raw)


def sent(client, command):
    rows = [f for f in client.frames() if f['commandId'] == command]
    return rows[-1] if rows else None


class AppCommandsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ControllerTests.asyncSetUp
    asyncTearDown = fixtures.ControllerTests.asyncTearDown

    async def test_profile_is_explicit_and_excludes_legacy_decode(self):
        with self.assertRaises(ValueError):
            await self.gimbal.appCommands.getFollowSensitivity()
        self.assertEqual(self.client.frames(), [])
        self.gimbal.experimental.useProfile('rs3')
        self.gimbal.app_commands.use_profile('ronin-2.2.2')
        self.assertIsNone(self.gimbal.experimental.profile)
        self.gimbal.experimental.useProfile('rs3mini')
        self.assertIsNone(self.gimbal.appCommands.profile)

    async def test_unsigned_high_index_duplicate_context_and_copy(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        context = [dict(index=150, size=1), dict(index=150, size=8)]
        task = asyncio.create_task(self.gimbal.appCommands.readParameters(parameters=context))
        await fixtures.until(lambda: sent(self.client, 0x10))
        context[0]['index'] = 1
        request = sent(self.client, 0x10)
        self.assertEqual(request['payload'].hex(), '9696')
        with self.assertRaises(Exception) as busy:
            self.gimbal.experimental.useProfile('rs3')
        self.assertEqual(busy.exception.code, 'RS4MINI_BUSY')
        reply(self.client, request, [0,150,9,1,150,8]+[255]*8)
        result = await task
        self.assertEqual(result['parameters'], [dict(index=150,size=1,headerByte=9,rawHex='01'),dict(index=150,size=8,headerByte=8,rawHex='ffffffffffffffff')])
        self.assertFalse(result['deviceVerified'])
        self.assertFalse(self.gimbal.experimental.pending)

    async def test_setter_owns_operation_and_correlates_ack(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task = asyncio.create_task(self.gimbal.appCommands.setFollowSensitivity(mode=1))
        await fixtures.until(lambda: sent(self.client,0x0f))
        request = sent(self.client,0x0f)
        self.assertEqual(request['payload'].hex(),'960101')
        with self.assertRaises(Exception) as busy:
            await self.gimbal.setVelocity(pan=.1)
        self.assertEqual(busy.exception.code,'RS4MINI_BUSY')
        reply(self.client,request,[0],lambda raw: raw.__setitem__(6,raw[6]^1))
        reply(self.client,request,[0],lambda raw: raw.__setitem__(4,0x24))
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        reply(self.client,request,[0])
        result = await task
        self.assertEqual(result['requestedMode'],1)
        self.assertTrue(result['acknowledged'])
        self.assertFalse(result['physicalCompletionVerified'])
        self.assertIsNone(self.gimbal.activeOperation)

    async def test_device_rejection_and_truncated_reply_are_errors(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task = asyncio.create_task(self.gimbal.appCommands.setFollowSensitivity(mode=0))
        await fixtures.until(lambda: sent(self.client,0x0f))
        reply(self.client,sent(self.client,0x0f),[7])
        with self.assertRaises(Exception) as bad:
            await task
        self.assertEqual(bad.exception.code,'RS4MINI_DEVICE_ERROR')
        self.assertEqual(bad.exception.statusCode,7)
        task = asyncio.create_task(self.gimbal.appCommands.getFollowSensitivity())
        await fixtures.until(lambda: sent(self.client,0x10))
        reply(self.client,sent(self.client,0x10),[0,150,1])
        with self.assertRaises(Exception) as bad:
            await task
        self.assertEqual(bad.exception.code,'RS4MINI_PROTOCOL_ERROR')
        self.assertFalse(self.gimbal.experimental.pending)

    async def test_stop_cancels_setter_and_timeout_never_retries(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task = asyncio.create_task(self.gimbal.appCommands.setFollowSensitivity(mode=1))
        await fixtures.until(lambda: sent(self.client,0x0f))
        await self.gimbal.stop()
        with self.assertRaises(Exception) as bad:
            await task
        self.assertEqual(bad.exception.code,'RS4MINI_OPERATION_CANCELLED')
        self.assertFalse(self.gimbal.experimental.pending)
        with self.assertRaises(Exception) as bad:
            await self.gimbal.appCommands.setFollowSensitivity(mode=0,timeoutMs=5)
        self.assertEqual(bad.exception.code,'RS4MINI_RESPONSE_TIMEOUT')
        self.assertEqual(len([f for f in self.client.frames() if f['commandId']==0x0f]),2)

    async def test_invalid_input_sends_nothing(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for value in (-1,2,True,None,'1'):
            with self.assertRaises(ValueError):
                await self.gimbal.appCommands.setFollowSensitivity(mode=value)
        for records in ([],[dict(index=True,size=1)],[dict(index=150,size=3)],[dict(index=150,size=1,name='inferred')]):
            with self.assertRaises(ValueError):
                await self.gimbal.appCommands.readParameters(parameters=records)
        self.assertEqual(self.client.frames(),[])

    async def test_disconnect_rejects_read_and_unknown_raw_mode_is_preserved(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task = asyncio.create_task(self.gimbal.appCommands.getFollowSensitivity())
        await fixtures.until(lambda: sent(self.client,0x10))
        self.client.callback(self.client)
        with self.assertRaises(Exception) as bad:
            await task
        self.assertEqual(bad.exception.code,'RS4MINI_DISCONNECTED')
        await self.gimbal.connect()
        self.client = self.clients[-1]
        task = asyncio.create_task(self.gimbal.appCommands.get_follow_sensitivity())
        await fixtures.until(lambda: sent(self.client,0x10))
        reply(self.client,sent(self.client,0x10),[0,150,1,255])
        result=await task
        self.assertIsNone(result['mode'])
        self.assertEqual(result['rawValue'],255)
