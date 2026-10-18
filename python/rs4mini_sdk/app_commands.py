from .app_program_request import program_status_request_spec,program_status_request_reply,program_status_subscription_spec,program_status_subscription_reply
from .app_program_status import program_status_notification
from .app_source_status import source_status_notification
from .app_handheld_stick import handheld_stick_notification
from .app_profile_values import profile_value_selection,profile_value_write,profile_value_reply
from .app_smooth_track import smooth_track_selection,smooth_track_write,smooth_track_reply
from .app_axis_mode import axis_mode_write,axis_mode_reply
"""Current-App device commands share the existing connection/queue/pending map."""
from .app_fine_tune import fine_tune_spec
from .app_handle import handle_reply,handle_write_spec
from .app_user_parameters import user_parameter_notification
from .app_standalone import standalone_selection,standalone_write,standalone_context,standalone_reply
from .app_tuning import tuning_selection,tuning_write,tuning_reply
from .app_motor import motor_selection, motor_write, motor_reply
from .app_system_calibration import system_calibration_reply
from .app_balance import balance_reply
import time
import copy
from .protocol import frame
from .app_calibration import auto_tune_payload, calibration_reply, calibration_notification
from .app_settings import mode_kind, SCHEMAS, settings_patch, decode_settings, settings_write
from .app_protocol import app_profile, parameter_context, parameter_request, sensitivity_payload, factory_reset_spec, app_reply, parameter_reply
from .experimental_device import _duration
from .errors import RS4MiniError


class AppCommands:
    def __init__(self, owner):
        self.owner, self._profile = owner, None
        self._calibration_status = None
        self._user_parameter_status = None
        self._handheld_stick_status = None
        self._abnormal_status = None
        self._battery_status = None
        self._program_status = None

    programStatus = property(lambda self: copy.deepcopy(self._program_status))
    program_status = programStatus
    abnormalStatus = property(lambda self: copy.deepcopy(self._abnormal_status))
    abnormal_status = abnormalStatus
    batteryStatus = property(lambda self: copy.deepcopy(self._battery_status))
    battery_status = batteryStatus
    handheldStickStatus = property(lambda self: copy.deepcopy(self._handheld_stick_status))
    handheld_stick_status = handheldStickStatus
    userParameterStatus = property(lambda self: copy.deepcopy(self._user_parameter_status))
    user_parameter_status = userParameterStatus
    profile = property(lambda self: self._profile)
    calibrationStatus = property(lambda self: copy.deepcopy(self._calibration_status))
    calibration_status = calibrationStatus

    def _reset(self):
        self._calibration_status = None
        self._user_parameter_status = None
        self._handheld_stick_status = None
        self._abnormal_status = None
        self._battery_status = None
        self._program_status = None

    def _message(self, message):
        if not self._profile:
            return
        program=program_status_notification(message)
        if program:
            self._program_status=program
            self.owner._emit('onAppStatus',copy.deepcopy(program))
        source=source_status_notification(message)
        if source:
            if source['kind']=='abnormal':self._abnormal_status=source
            else:self._battery_status=source
            self.owner._emit('onAppStatus',copy.deepcopy(source))
        stick=handheld_stick_notification(message)
        if stick:
            self._handheld_stick_status=stick
            self.owner._emit('onAppStatus',copy.deepcopy(stick))
        parameters=user_parameter_notification(message)
        if parameters:
            self._user_parameter_status=parameters
            self.owner._emit('onAppStatus',copy.deepcopy(parameters))
        status = calibration_notification(message)
        if status:
            self._calibration_status = status
            self.owner._emit('onAppStatus', copy.deepcopy(status))

    def useProfile(self, profile):
        app_profile(profile)
        if self.owner.activeOperation or self.owner.experimental.pending:
            raise RS4MiniError('RS4MINI_BUSY', 'Cannot change protocol source during an operation or query')
        self.owner.experimental._profile = None
        self.owner.experimental._reset()
        self._profile = profile
        self._reset()

    use_profile = useProfile

    def _require_profile(self):
        app_profile(self._profile)

    async def sendProgramStatusSubscriptionRequest(self, *, program, enabled, timeoutMs=3000):
        self._require_profile()
        spec=program_status_subscription_spec(program,enabled)
        response=await self.owner.experimental._query_payload_command('App program status subscription request',(4,0x6b),spec['payload'],timeoutMs)
        return program_status_subscription_reply(response,spec['requestedProgram'],spec['requestedEnabled'])

    send_program_status_subscription_request = sendProgramStatusSubscriptionRequest

    async def sendProgramStatusRequest(self, *, program, timeoutMs=3000):
        self._require_profile()
        spec=program_status_request_spec(program)
        response=await self.owner.experimental._query_payload_command('App single program status request',(4,0x6b),spec['payload'],timeoutMs)
        return program_status_request_reply(response,spec['requestedProgram'])

    send_program_status_request = sendProgramStatusRequest

    async def sendFineTuneRequest(self, *, axis, adjustmentDegrees, timeoutMs=3000):
        self._require_profile()
        spec=fine_tune_spec(axis,adjustmentDegrees);_duration(timeoutMs,'timeoutMs',False)
        async def body(operation):
            await self.owner._halt();self.owner._check(operation)
            message=await self.owner.experimental._query_payload_command('App fine tune',(4,7),spec['payload'],timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(message,7),**{key:value for key,value in spec.items() if key!='payload'},stabilizationStateVerified=False)
        return await self.owner._run('sendFineTuneRequest',body,False)

    send_fine_tune_request=sendFineTuneRequest

    async def getUserProfile(self,*,timeoutMs=3000):return await self._get_profile_value('userProfile',timeoutMs)
    get_user_profile=getUserProfile
    async def getWorkMode(self,*,timeoutMs=3000):return await self._get_profile_value('workMode',timeoutMs)
    get_work_mode=getWorkMode
    async def _get_profile_value(self,kind,timeout_ms):
        self._require_profile();row=profile_value_selection(kind)
        message=await self.owner.experimental._query_payload_command('App '+kind+' query',(4,0x10),parameter_request([dict(index=row['index'],size=1)]),timeout_ms)
        return profile_value_reply(message,kind)
    async def sendUserProfileRequest(self,*,sourceProfileValue,timeoutMs=3000):
        self._require_profile();return await self._send_profile_value('userProfile',profile_value_write('userProfile',sourceProfileValue),timeoutMs)
    send_user_profile_request=sendUserProfileRequest
    async def sendWorkModeRequest(self,*,sourceMode,timeoutMs=3000):
        self._require_profile();return await self._send_profile_value('workMode',profile_value_write('workMode',sourceMode),timeoutMs)
    send_work_mode_request=sendWorkModeRequest
    async def _send_profile_value(self,kind,spec,timeout_ms):
        _duration(timeout_ms,'timeoutMs',False)
        async def work(operation):
            await self.owner._halt();self.owner._check(operation)
            message=await self.owner.experimental._query_payload_command('App '+kind+' write',(4,0x0f),spec['payload'],timeout_ms,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(message,0x0f),**{k:v for k,v in spec.items() if k!='payload'},activePresetVerified=False,persistenceVerified=False)
        return await self.owner._run('sendUserProfileRequest' if kind=='userProfile' else 'sendWorkModeRequest',work,False)

    async def getSmoothTrackAxes(self,*,axis=None,timeoutMs=3000):
        self._require_profile();selection=smooth_track_selection(axis)
        message=await self.owner.experimental._query_payload_command('App smooth track query',(4,0x10),parameter_request([dict(index=r['index'],size=1) for r in selection]),timeoutMs)
        return smooth_track_reply(message,selection)
    get_smooth_track_axes=getSmoothTrackAxes

    async def sendSmoothTrackAxesRequest(self,*,axes,timeoutMs=3000):
        self._require_profile();spec=smooth_track_write(axes);_duration(timeoutMs,'timeoutMs',False)
        async def work(operation):
            await self.owner._halt();self.owner._check(operation)
            message=await self.owner.experimental._query_payload_command('App smooth track axes',(4,0x0f),spec['payload'],timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(message,0x0f),requestedAxes=dict(spec['requestedAxes']),activePresetVerified=False,atomicApplicationVerified=False,persistenceVerified=False)
        return await self.owner._run('sendSmoothTrackAxesRequest',work,False)
    send_smooth_track_axes_request=sendSmoothTrackAxesRequest

    async def getAxisMode(self,*,timeoutMs=3000):
        self._require_profile()
        message=await self.owner.experimental._query_payload_command('App axis mode query',(4,0x10),parameter_request([dict(index=34,size=1)]),timeoutMs)
        return axis_mode_reply(message)
    get_axis_mode=getAxisMode

    async def sendAxisModeRequest(self,*,sourceMode,timeoutMs=3000):
        self._require_profile();spec=axis_mode_write(sourceMode);_duration(timeoutMs,'timeoutMs',False)
        async def work(operation):
            await self.owner._halt();self.owner._check(operation)
            message=await self.owner.experimental._query_payload_command('App axis mode',(4,0x0f),spec['payload'],timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(message,0x0f),**{k:v for k,v in spec.items() if k!='payload'},activePresetVerified=False,otherBitsPreservationVerified=False,persistenceVerified=False)
        return await self.owner._run('sendAxisModeRequest',work,False)
    send_axis_mode_request=sendAxisModeRequest

    async def sendFactorySettingsResetRequest(self,*,sourcePlatform,timeoutMs=3000):
        self._require_profile();spec=factory_reset_spec(sourcePlatform);_duration(timeoutMs,'timeoutMs',False)
        async def work(operation):
            await self.owner._halt();self.owner._check(operation)
            message=await self.owner.experimental._query_payload_command('App factory settings reset',(4,0x13),spec['payload'],timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(message,0x13),requestedSourcePlatform=spec['requestedSourcePlatform'],targetResetScopeVerified=False,persistenceVerified=False)
        return await self.owner._run('sendFactorySettingsResetRequest',work,False)
    send_factory_settings_reset_request=sendFactorySettingsResetRequest

    async def sendHandleSettingRequest(self,*,setting,value,timeoutMs=3000):
        self._require_profile();spec=handle_write_spec(setting,value);_duration(timeoutMs,'timeoutMs',False)
        async def work(operation):
            await self.owner._halt();self.owner._check(operation)
            message=await self.owner.experimental._query_payload_command('App handle setting',(4,0x35),spec['payload'],timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(message,0x35),**{k:v for k,v in spec.items() if k!='payload'},unspecifiedByteSemanticsVerified=False,readbackVerified=False,persistenceVerified=False)
        return await self.owner._run('sendHandleSettingRequest',work,False)
    send_handle_setting_request=sendHandleSettingRequest

    async def getHandleSettings(self, *, timeoutMs=3000):
        self._require_profile()
        message=await self.owner.experimental._query_payload_command('App handle query',(4,0x36),b'',timeoutMs)
        return handle_reply(message)

    get_handle_settings=getHandleSettings

    async def readParameters(self, *, parameters, timeoutMs=3000):
        self._require_profile()
        context = parameter_context(parameters)
        response = await self.owner.experimental._query_payload_command('App parameters', (4, 0x10), parameter_request(context), timeoutMs)
        return parameter_reply(response, context)

    read_parameters = readParameters

    async def getFollowSensitivity(self, *, timeoutMs=3000):
        result = await self.readParameters(parameters=[dict(index=150, size=1)], timeoutMs=timeoutMs)
        raw = int(result['parameters'][0]['rawHex'], 16)
        result.update(rawValue=raw, mode=raw if raw in (0, 1) else None)
        return result

    get_follow_sensitivity = getFollowSensitivity

    async def getAutoCalibrationStatus(self, *, timeoutMs=3000):
        return system_calibration_reply(await self.readParameters(parameters=[dict(index=36,size=1)],timeoutMs=timeoutMs))

    get_auto_calibration_status=getAutoCalibrationStatus

    async def sendAutoCalibrationRequest(self, *, timeoutMs=3000):
        self._require_profile()
        _duration(timeoutMs,'timeoutMs',False)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            response=await self.owner.experimental._query_payload_command('App system calibration start',(4,0x0f),bytes((36,1,1)),timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(response,0x0f),requestedValue=1)
        return await self.owner._run('sendAutoCalibrationRequest',body,False)

    send_auto_calibration_request=sendAutoCalibrationRequest

    async def getBalanceTestStatus(self, *, timeoutMs=3000):
        return balance_reply(await self.readParameters(parameters=[dict(index=37,size=1)],timeoutMs=timeoutMs))

    get_balance_test_status=getBalanceTestStatus

    async def sendBalanceTestRequest(self, *, timeoutMs=3000):
        self._require_profile()
        _duration(timeoutMs,'timeoutMs',False)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            response=await self.owner.experimental._query_payload_command('App balance start',(4,0x0f),bytes((37,1,64)),timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(response,0x0f),requestedValue=64)
        return await self.owner._run('sendBalanceTestRequest',body,False)

    send_balance_test_request=sendBalanceTestRequest

    async def getStandaloneTuning(self, *, axis=None, parameter=None, timeoutMs=3000):
        self._require_profile()
        selection=standalone_selection(axis,parameter)
        response=await self.owner.experimental._query_payload_command('App standalone query',(4,0x10),parameter_request(standalone_context(selection)),timeoutMs)
        return standalone_reply(response,selection)

    get_standalone_tuning=getStandaloneTuning

    async def setStandaloneTuning(self, *, inputSource, axis, parameter, value, timeoutMs=3000):
        self._require_profile()
        payload=standalone_write(inputSource,axis,parameter,value)
        _duration(timeoutMs,'timeoutMs',False)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            response=await self.owner.experimental._query_payload_command('App standalone source/value write',(4,0x0f),payload,timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(response,0x0f),axis=axis,parameter=parameter,requestedValue=value,requestedInputSource=2,activePresetVerified=False)
        return await self.owner._run('setStandaloneTuning',body,False)

    set_standalone_tuning=setStandaloneTuning

    async def getFollowTuning(self, *, axis=None, parameter=None, timeoutMs=3000):
        return await self._get_tuning('follow',axis,parameter,timeoutMs)

    get_follow_tuning=getFollowTuning

    async def setFollowTuning(self, *, axis, parameter, value, timeoutMs=3000):
        return await self._set_tuning('follow',axis,parameter,value,timeoutMs)

    set_follow_tuning=setFollowTuning

    async def getRcTuning(self, *, axis=None, parameter=None, timeoutMs=3000):
        return await self._get_tuning('rc',axis,parameter,timeoutMs)

    get_rc_tuning=getRcTuning

    async def setRcTuning(self, *, axis, parameter, value, timeoutMs=3000):
        return await self._set_tuning('rc',axis,parameter,value,timeoutMs)

    set_rc_tuning=setRcTuning

    async def _get_tuning(self,domain,axis,parameter,timeoutMs):
        self._require_profile()
        selection=tuning_selection(domain,axis,parameter)
        context=[dict(index=row['index'],size=row['size']) for row in selection]
        response=await self.owner.experimental._query_payload_command('App numeric tuning',(4,0x10),parameter_request(context),timeoutMs)
        return tuning_reply(response,selection)

    async def _set_tuning(self,domain,axis,parameter,value,timeoutMs):
        self._require_profile()
        payload=tuning_write(domain,axis,parameter,value)
        _duration(timeoutMs,'timeoutMs',False)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            response=await self.owner.experimental._query_payload_command('App numeric write',(4,0x0f),payload,timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(response,0x0f),axis=axis,parameter=parameter,requestedValue=value,activePresetVerified=False)
        return await self.owner._run('setFollowTuning' if domain=='follow' else 'setRcTuning',body,False)

    async def getMotorTuning(self, *, axis=None, parameter=None, timeoutMs=3000):
        self._require_profile()
        selection=motor_selection(axis,parameter)
        context=[dict(index=row['index'],size=1) for row in selection]
        response=await self.owner.experimental._query_payload_command('App motor tuning',(4,0x32),parameter_request(context),timeoutMs)
        return motor_reply(response,selection)

    get_motor_tuning=getMotorTuning

    async def setMotorTuning(self, *, axis, parameter, value, timeoutMs=3000):
        self._require_profile()
        payload=motor_write(axis,parameter,value)
        _duration(timeoutMs,'timeoutMs',False)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            response=await self.owner.experimental._query_payload_command('App motor write',(4,0x31),payload,timeoutMs,external_operation=operation,epoch=self.owner._epoch)
            return dict(app_reply(response,0x31),axis=axis,parameter=parameter,requestedValue=value)
        return await self.owner._run('setMotorTuning',body,False)

    set_motor_tuning=setMotorTuning

    async def queryCalibrationStatus(self, *, timeoutMs=3000):
        self._require_profile()
        response = await self.owner.experimental._query_payload_command('App calibration status', (4, 0x6e), b'', timeoutMs)
        return calibration_reply(response)

    query_calibration_status = queryCalibrationStatus

    async def sendAutoTuneRequest(self, *, start):
        self._require_profile()
        payload = auto_tune_payload(start)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            await self.owner._enqueue(frame(self.owner._next_sequence(), 4, 0x6a, payload, flags=0), operation=operation, epoch=self.owner._epoch)
            return dict(profile=self._profile, sent=True, requestedStart=start, acknowledgementRequested=False,
                        acknowledged=False, deviceVerified=False, physicalCompletionVerified=False)
        return await self.owner._run('sendAutoTuneRequest', body, False)

    send_auto_tune_request = sendAutoTuneRequest

    async def _get_settings(self, kind, timeoutMs):
        result = await self.readParameters(parameters=[dict(index=SCHEMAS[kind]['index'], size=1)], timeoutMs=timeoutMs)
        return decode_settings(result, kind)

    async def getFollowSettings(self, *, parameter, timeoutMs=3000):
        return await self._get_settings(mode_kind('follow',parameter),timeoutMs)

    get_follow_settings=getFollowSettings

    async def setFollowSettings(self, *, parameter, timeoutMs=3000, **fields):
        return await self._set_settings(mode_kind('follow',parameter),fields,timeoutMs)

    set_follow_settings=setFollowSettings

    async def getRcSettings(self, *, parameter, timeoutMs=3000):
        return await self._get_settings(mode_kind('rc',parameter),timeoutMs)

    get_rc_settings=getRcSettings

    async def setRcSettings(self, *, parameter, timeoutMs=3000, **fields):
        return await self._set_settings(mode_kind('rc',parameter),fields,timeoutMs)

    set_rc_settings=setRcSettings

    async def getCustomFollowSettings(self, *, timeoutMs=3000):
        return await self._get_settings('customFollow', timeoutMs)

    get_custom_follow_settings = getCustomFollowSettings

    async def getMotorSettings(self, *, timeoutMs=3000):
        return await self._get_settings('motor', timeoutMs)

    get_motor_settings = getMotorSettings

    async def setCustomFollowSettings(self, *, timeoutMs=3000, **fields):
        return await self._set_settings('customFollow', fields, timeoutMs)

    set_custom_follow_settings = setCustomFollowSettings

    async def setMotorSettings(self, *, timeoutMs=3000, **fields):
        return await self._set_settings('motor', fields, timeoutMs)

    set_motor_settings = setMotorSettings

    async def _set_settings(self, kind, fields, timeoutMs):
        self._require_profile()
        patch = settings_patch(kind, fields)
        _duration(timeoutMs, 'timeoutMs', False)
        name = 'setMotorSettings' if kind == 'motor' else 'setCustomFollowSettings' if kind=='customFollow' else 'setFollowSettings' if kind.startswith('follow') else 'setRcSettings'
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            deadline = time.monotonic() + timeoutMs / 1000
            def remaining():
                left = (deadline - time.monotonic()) * 1000
                if left <= 0:
                    raise RS4MiniError('RS4MINI_RESPONSE_TIMEOUT', 'Settings transaction deadline expired')
                return left
            parameters = [dict(index=SCHEMAS[kind]['index'], size=1)]
            response = await self.owner.experimental._query_payload_command(name + ' read', (4, 0x10), parameter_request(parameters), remaining(), external_operation=operation, epoch=self.owner._epoch)
            before = decode_settings(parameter_reply(response, parameters), kind)
            self.owner._check(operation)
            payload, value = settings_write(kind, patch, before['rawValue'])
            ack = await self.owner.experimental._query_payload_command(name + ' write', (4, 0x0f), payload, remaining(), external_operation=operation, epoch=self.owner._epoch)
            return dict(app_reply(ack, 0x0f), previousRawValue=before['rawValue'], requestedRawValue=value, requestedSettings=patch)
        return await self.owner._run(name, body, False)

    async def setFollowSensitivity(self, *, mode, timeoutMs=3000):
        self._require_profile()
        payload = sensitivity_payload(mode)
        _duration(timeoutMs, 'timeoutMs', False)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            response = await self.owner.experimental._query_payload_command('follow sensitivity', (4, 0x0f), payload, timeoutMs, external_operation=operation, epoch=self.owner._epoch)
            result = app_reply(response, 0x0f)
            result['requestedMode'] = mode
            return result
        return await self.owner._run('setFollowSensitivity', body, False)

    set_follow_sensitivity = setFollowSensitivity
