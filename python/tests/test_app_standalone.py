import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_standalone import standalone_selection

class AppStandaloneTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown

    async def test_default_read_preserves_source_and_unsigned_values(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.get_standalone_tuning())
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10)
        self.assertEqual(r['payload'].hex(),'48504f514d4c4e');data=[0,72,9,255]
        for row in standalone_selection():data.extend((row['index'],9,255,255))
        reply(self.client,r,data);result=await task
        self.assertEqual(result['inputSourceRaw'],255);self.assertEqual(len(result['values']),6);self.assertEqual(result['values'][0]['rawValue'],65535);self.assertFalse(result['values'][0]['withinSourceRange']);self.assertFalse(result['activePresetVerified']);self.assertIsNone(sent(self.client,0x0f))

    async def test_filtered_little_endian_read(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.appCommands.getStandaloneTuning(axis='roll',parameter='smoothing'))
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10);self.assertEqual(r['payload'].hex(),'484c')
        reply(self.client,r,[0,72,1,1,76,9,0x34,0x12]);result=await task
        self.assertEqual(result['inputSourceRaw'],1);self.assertEqual(result['values'][0]['rawValue'],4660);self.assertEqual(result['values'][0]['axis'],'roll')

    async def test_explicit_source_and_value_share_ack_owned_packet(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.set_standalone_tuning(inputSource=2,axis='pitch',parameter='speed',value=100))
        await fixtures.until(lambda:sent(self.client,0x0f));r=sent(self.client,0x0f);self.assertEqual(r['payload'].hex(),'48010250026400');self.assertIsNone(sent(self.client,0x10))
        with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
        self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0]);result=await task
        self.assertEqual(result['requestedInputSource'],2);self.assertEqual(result['requestedValue'],100);self.assertFalse(result['physicalCompletionVerified']);self.assertFalse(result['activePresetVerified'])
        self.assertEqual(len([f for f in self.client.frames() if f['commandId']==0x0f]),1)

    async def test_validation_precedes_frames(self):
        with self.assertRaises(Exception):await self.gimbal.appCommands.getStandaloneTuning()
        self.gimbal.appCommands.useProfile('ronin-2.2.2');good=dict(inputSource=2,axis='yaw',parameter='smoothing',value=30)
        for patch in [dict(inputSource=1),dict(inputSource=3),dict(inputSource=True),dict(axis='pan'),dict(parameter='acceleration'),dict(value=31),dict(value=-1),dict(value=True),dict(value=1.5),dict(index=72)]:
            with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.setStandaloneTuning(**dict(good,**patch))
        del good['inputSource']
        with self.assertRaises(TypeError):await self.gimbal.appCommands.setStandaloneTuning(**good)
        self.assertEqual(self.client.frames(),[])

    async def test_wrong_namespace_truncation_and_nack(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.getStandaloneTuning(axis='yaw',parameter='speed'))
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10)
        reply(self.client,dict(r,commandId=0x32),[0,72,1,2,81,2,1,0]);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[0,72,1,2,81,2,1])
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_PROTOCOL_ERROR')
        task=asyncio.create_task(self.gimbal.appCommands.setStandaloneTuning(inputSource=2,axis='roll',parameter='smoothing',value=0))
        await fixtures.until(lambda:sent(self.client,0x0f));reply(self.client,sent(self.client,0x0f),[7])
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_DEVICE_ERROR');self.assertFalse(self.gimbal.experimental.pending)

    async def test_cancel_timeout_do_not_replay_or_restore_source(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2');options=dict(inputSource=2,axis='yaw',parameter='speed',value=0)
        task=asyncio.create_task(self.gimbal.appCommands.setStandaloneTuning(**options))
        await fixtures.until(lambda:sent(self.client,0x0f));await self.gimbal.stop()
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
        with self.assertRaises(Exception) as e:await self.gimbal.appCommands.setStandaloneTuning(**dict(options,timeoutMs=10))
        self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT');writes=[f for f in self.client.frames() if f['commandId']==0x0f]
        self.assertEqual(len(writes),2);self.assertTrue(all(f['payload'].hex()=='48010251020000' for f in writes));self.assertFalse(self.gimbal.experimental.pending)
