import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_settings import settings_write,decode_settings

class AppFollowModeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown

    async def test_other_axes_and_opaque_bits_preserved(self):
        for raw in range(256):
            _,value=settings_write('followSpeed',dict(yaw='custom'),raw)
            self.assertEqual(value&63,raw&63);self.assertEqual(value>>6,0)
        self.assertEqual(settings_write('followSpeed',dict(pitch='high'),0x9b)[1],0x9f)
        self.assertEqual(decode_settings(dict(parameters=[dict(rawHex='9b')]),'rcSpeed')['settings'],dict(pitch='middle',roll='low',yaw='middle'))

    async def test_six_named_groups(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for method,parameter,index in [('getFollowSettings','speed',65),('getFollowSettings','acceleration',71),('getFollowSettings','deadZone',66),('getRcSettings','speed',67),('getRcSettings','deadZone',68),('getRcSettings','smoothing',69)]:
            previous=sent(self.client,0x10)
            task=asyncio.create_task(getattr(self.gimbal.appCommands,method)(parameter=parameter))
            await fixtures.until(lambda:sent(self.client,0x10)!=previous);r=sent(self.client,0x10)
            self.assertEqual(r['payload'],bytes((index,)));reply(self.client,r,[0,index,9,0x9b]);result=await task
            self.assertEqual(result['settings']['pitch'],'middle');self.assertEqual(result['unknownBits'],3)
            self.assertEqual(result['parameters'][0]['headerByte'],9)

    async def test_read_modify_ack_keeps_slot(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.set_follow_settings(parameter='speed',yaw='custom'))
        await fixtures.until(lambda:sent(self.client,0x10));reply(self.client,sent(self.client,0x10),[0,65,1,255])
        await fixtures.until(lambda:sent(self.client,0x0f));r=sent(self.client,0x0f)
        self.assertEqual(r['payload'].hex(),'41013f')
        with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
        self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0]);result=await task
        self.assertEqual(result['previousRawValue'],255);self.assertEqual(result['requestedRawValue'],63)
        self.assertFalse(result['physicalCompletionVerified'])

    async def test_cancel_read_prevents_write(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.set_rc_settings(parameter='smoothing',roll='middle'))
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10)
        await self.gimbal.stop();reply(self.client,r,[0,69,1,0])
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
        self.assertIsNone(sent(self.client,0x0f));self.assertFalse(self.gimbal.experimental.pending)

    async def test_invalid_fields_malformed_read_and_ack_deadline(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for fields in ({'parameter':'speed'},{'parameter':'speed','yaw':1},{'parameter':'PF','yaw':'low'},{'parameter':'speed','pan':'low'},{'parameter':'speed','yaw':'medium'}):
            with self.assertRaises(ValueError):await self.gimbal.appCommands.setFollowSettings(**fields)
        self.assertEqual(self.client.frames(),[])
        task=asyncio.create_task(self.gimbal.appCommands.setRcSettings(parameter='deadZone',pitch='low'))
        await fixtures.until(lambda:sent(self.client,0x10));reply(self.client,sent(self.client,0x10),[0,68,1])
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_PROTOCOL_ERROR');self.assertIsNone(sent(self.client,0x0f))
        previous=sent(self.client,0x10)
        task=asyncio.create_task(self.gimbal.appCommands.setRcSettings(parameter='speed',yaw='low',timeoutMs=30))
        await fixtures.until(lambda:sent(self.client,0x10)!=previous);reply(self.client,sent(self.client,0x10),[0,67,1,0])
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT')
        self.assertEqual(len([f for f in self.client.frames() if f['commandId']==0x0f]),1)
        self.assertFalse(self.gimbal.experimental.pending)
