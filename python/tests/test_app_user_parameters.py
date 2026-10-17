import unittest
import test_controller as fixtures
from rs4mini_sdk.app_user_parameters import user_parameter_notification
from test_app_commands import reply

def payload():
    b=bytearray([0xaa]*78);b[0]=99;b[2]=2;b[9:11]=b'\x34\x12';b[63:65]=b'\xff\xff';b[73]=255;return bytes(b)
def message(body=None,flags=0):return dict(sender=4,receiver=2,commandSet=4,commandId=0x24,flags=flags,payload=payload() if body is None else body)
class UserParameterTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown
    def incoming(self,body=None,flags=0):
        reply(self.client,dict(sequence=1,commandId=0x24),payload() if body is None else body,lambda data:data.__setitem__(8,flags))
    async def test_all_source_fields_unsigned_and_unknown_bytes(self):
        r=user_parameter_notification(message());values={row['sourceGetter']:row for row in r['values']}
        self.assertEqual(len(values),17);self.assertEqual(values['getYawSpeed']['rawValue'],4660);self.assertEqual(values['getRollAccel']['rawValue'],65535);self.assertEqual(values['getRollSmoothTrack']['rawValue'],255);self.assertEqual(r['preset']['rawValue'],2);self.assertIsNone(r['preset']['sourceEnum']);self.assertEqual(r['bodyHex'],payload().hex());self.assertFalse(r['activePresetVerified'])
    async def test_complete_layout_and_unencrypted_request_context_required(self):
        for flags in (128,1,7,256,-256,.5,True):self.assertIsNone(user_parameter_notification(message(flags=flags)))
        for patch in (dict(sender=229),dict(receiver=4),dict(commandId=16),dict(payload=bytes(73)),dict(flags=None)):
            self.assertIsNone(user_parameter_notification(dict(message(),**patch)))
        b=bytearray(payload());b[2]=1;self.assertEqual(user_parameter_notification(message(b))['preset']['sourceEnum'],'CUSTOM_2')
    async def test_profile_gating_copy_and_no_writes(self):
        self.incoming();self.assertIsNone(self.gimbal.appCommands.userParameterStatus);self.gimbal.appCommands.useProfile('ronin-2.2.2');errors=[];self.gimbal.onError=errors.append
        def observer(status):
            status['values'].clear();status['preset']['rawValue']=99;raise ValueError('observer')
        self.gimbal.onAppStatus=observer;self.incoming();r=self.gimbal.app_commands.user_parameter_status
        self.assertEqual(len(r['values']),17);self.assertEqual(r['preset']['rawValue'],2);r['values'].clear();self.assertEqual(len(self.gimbal.appCommands.userParameterStatus['values']),17);self.assertEqual(len(errors),1);self.assertEqual(self.client.frames(),[]);self.assertIsNone(self.gimbal.appCommands.calibrationStatus)
    async def test_invalid_push_retains_report_profile_reset_clears(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();before=self.gimbal.appCommands.userParameterStatus
        self.incoming(bytes(73));self.incoming(flags=128);self.incoming(flags=1);self.assertEqual(self.gimbal.appCommands.userParameterStatus,before)
        self.gimbal.appCommands.useProfile('ronin-2.2.2');self.assertIsNone(self.gimbal.appCommands.userParameterStatus);self.incoming();self.gimbal.experimental.useProfile('rs3');self.assertIsNone(self.gimbal.appCommands.userParameterStatus);self.incoming();self.assertIsNone(self.gimbal.appCommands.userParameterStatus);self.assertEqual(self.client.frames(),[])
    async def test_disconnect_clears_without_subscription_request(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();await self.gimbal.disconnect();self.assertIsNone(self.gimbal.appCommands.userParameterStatus);self.assertFalse(any(f['commandId']==18 for f in self.client.frames()))
