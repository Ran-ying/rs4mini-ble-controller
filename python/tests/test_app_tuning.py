import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_tuning import tuning_selection

class AppTuningTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown

    async def test_two_byte_named_read_little_endian(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.get_follow_tuning(axis='pitch',parameter='speed'))
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10);self.assertEqual(r['payload'],b'\x03')
        reply(self.client,r,[0,3,9,0x34,0x12]);result=await task
        self.assertEqual(result['values'][0]['rawValue'],4660);self.assertFalse(result['values'][0]['withinSourceRange']);self.assertEqual(result['values'][0]['headerByte'],9);self.assertFalse(result['activePresetVerified'])

    async def test_rc_mixed_width_unsigned_feedback(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.get_rc_tuning())
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10);self.assertEqual(r['payload'].hex(),'2a2b291b281a092708')
        data=[0]
        for i,row in enumerate(tuning_selection('rc')):
            value=65535 if i==0 else 255 if i==3 else 30
            data.extend((row['index'],9));data.extend(value.to_bytes(row['size'],'little'))
        reply(self.client,r,data);result=await task
        self.assertEqual(len(result['values']),9);self.assertEqual(result['values'][0]['rawValue'],65535);self.assertEqual(result['values'][3]['rawValue'],255);self.assertFalse(result['values'][3]['withinSourceRange']);self.assertTrue(result['values'][8]['withinSourceRange'])

    async def test_scalar_widths_and_ack_ownership(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for method,options,hex_value in [('setFollowTuning',dict(axis='pitch',parameter='speed',value=100),'03026400'),('setRcTuning',dict(axis='yaw',parameter='deadZone',value=100),'1a0164'),('setRcTuning',dict(axis='pitch',parameter='smoothing',value=30),'09021e00')]:
            previous=sent(self.client,0x0f);task=asyncio.create_task(getattr(self.gimbal.appCommands,method)(**options))
            await fixtures.until(lambda:sent(self.client,0x0f)!=previous);r=sent(self.client,0x0f);self.assertEqual(r['payload'].hex(),hex_value)
            with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
            self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0]);result=await task
            self.assertEqual(result['requestedValue'],options['value']);self.assertFalse(result['physicalCompletionVerified']);self.assertFalse(result['activePresetVerified'])
        self.assertIsNone(sent(self.client,0x31));self.assertIsNone(sent(self.client,0x10))

    async def test_named_validation_before_frames(self):
        with self.assertRaises(Exception):await self.gimbal.appCommands.getFollowTuning()
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for options in [dict(axis='pitch',parameter='speed',value=0),dict(axis='pitch',parameter='speed',value=101),dict(axis='pan',parameter='speed',value=10),dict(axis='pitch',parameter='speed',value=True),dict(axis='pitch',parameter='speed',value=1.5)]:
            with self.assertRaises(ValueError):await self.gimbal.appCommands.setFollowTuning(**options)
        with self.assertRaises(ValueError):await self.gimbal.appCommands.setRcTuning(axis='pitch',parameter='smoothing',value=31)
        with self.assertRaises(ValueError):await self.gimbal.appCommands.getRcTuning(parameter='gimbal_create_max_speed_pitch')
        with self.assertRaises(TypeError):await self.gimbal.appCommands.setRcTuning(axis='pitch',parameter='speed',value=1,index=72)
        self.assertEqual(self.client.frames(),[])

    async def test_truncated_read_wrong_namespace_and_negative_ack(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.appCommands.getFollowTuning(axis='roll',parameter='deadZone'))
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10)
        reply(self.client,dict(r,commandId=0x32),[0,13,1,1,0]);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[0,13,1,1])
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_PROTOCOL_ERROR')
        task=asyncio.create_task(self.gimbal.appCommands.setRcTuning(axis='yaw',parameter='speed',value=0))
        await fixtures.until(lambda:sent(self.client,0x0f));reply(self.client,sent(self.client,0x0f),[7])
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_DEVICE_ERROR');self.assertFalse(self.gimbal.experimental.pending)

    async def test_cancel_timeout_do_not_replay_or_select_presets(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.appCommands.setRcTuning(axis='yaw',parameter='speed',value=0))
        await fixtures.until(lambda:sent(self.client,0x0f));await self.gimbal.stop()
        with self.assertRaises(Exception) as e:await task
        self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
        with self.assertRaises(Exception) as e:await self.gimbal.appCommands.setFollowTuning(axis='pitch',parameter='deadZone',value=0,timeoutMs=10)
        self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT')
        writes=[r for r in self.client.frames() if r['commandId']==0x0f]
        self.assertEqual(len(writes),2);self.assertTrue(all(r['payload'][0] not in (65,66,67,68,69,71,72) for r in writes));self.assertFalse(self.gimbal.experimental.pending)
