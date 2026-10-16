"""Current-App device commands share the existing connection/queue/pending map."""
import time
from .app_settings import SCHEMAS, settings_patch, decode_settings, settings_write
from .app_protocol import app_profile, parameter_context, parameter_request, sensitivity_payload, app_reply, parameter_reply
from .experimental_device import _duration
from .errors import RS4MiniError


class AppCommands:
    def __init__(self, owner):
        self.owner, self._profile = owner, None

    profile = property(lambda self: self._profile)

    def useProfile(self, profile):
        app_profile(profile)
        if self.owner.activeOperation or self.owner.experimental.pending:
            raise RS4MiniError('RS4MINI_BUSY', 'Cannot change protocol source during an operation or query')
        self.owner.experimental._profile = None
        self.owner.experimental._reset()
        self._profile = profile

    use_profile = useProfile

    def _require_profile(self):
        app_profile(self._profile)

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

    async def _get_settings(self, kind, timeoutMs):
        result = await self.readParameters(parameters=[dict(index=SCHEMAS[kind]['index'], size=1)], timeoutMs=timeoutMs)
        return decode_settings(result, kind)

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
        name = 'setMotorSettings' if kind == 'motor' else 'setCustomFollowSettings'
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
