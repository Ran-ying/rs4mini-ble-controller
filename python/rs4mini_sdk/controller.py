"""Single application entry above the BLE SDK; existing imports stay compatible."""
import asyncio
import math
import time
from .device import BleDevice
from .errors import RS4MiniError, positive, finite
from .expansion import ExpansionMixin
from .experimental import ExperimentalGimbal

class RS4Mini(ExpansionMixin, BleDevice):
    def __init__(self, **options):
        super().__init__(**options)
        self._init_expansion()
        self.experimental = ExperimentalGimbal(self)

    async def _run(self, kind, body, stop_after=True):
        cancel_as_move = kind in ('moveTo', 'moveFor', 'runTrajectory', 'moveThrough', 'experimentalAbsolute', 'experimentalRate')
        return await super()._run(kind, body, stop_after, cancel_as_move=cancel_as_move)

    @property
    def moveToActive(self):
        return bool(self._operation and self._operation['kind'] == 'moveTo')

    async def setVelocityDeg(self, *, pan=0.0, tilt=0.0, roll=0.0, panFullScale=37.5, tiltFullScale=27.5, rollFullScale=30):
        for name, scale in dict(pan=panFullScale, tilt=tiltFullScale, roll=rollFullScale).items():
            positive(scale, name + 'FullScale')
        await self.setVelocity(pan=finite(pan, 'pan') / panFullScale, tilt=finite(tilt, 'tilt') / tiltFullScale, roll=finite(roll, 'roll') / rollFullScale)

    async def moveFor(self, *, durationMs, pan=0.0, tilt=0.0, roll=0.0):
        if not math.isfinite(durationMs) or durationMs < 0:
            raise ValueError('durationMs must be non-negative and finite')
        values = {name: max(-1, min(1, finite(value, name))) for name, value in dict(pan=pan, tilt=tilt, roll=roll).items()}
        async def body(operation):
            await self._set_velocity(values, operation)
            await self._bounded(asyncio.sleep(durationMs / 1000), durationMs / 1000 + 1,
                                cancel=operation['cancel'], cancel_error=lambda: operation['error'])
        await self._run('moveFor', body)

    async def moveTo(self, *, pan=None, tilt=None, roll=None, toleranceDeg=1, timeoutMs=30000,
                     telemetryTimeoutMs=3000, gain=0.02, minSpeed=0.05, maxSpeed=0.18):
        body = self._prepare_move(pan=pan, tilt=tilt, roll=roll, toleranceDeg=toleranceDeg, timeoutMs=timeoutMs,
                                  telemetryTimeoutMs=telemetryTimeoutMs, gain=gain, minSpeed=minSpeed, maxSpeed=maxSpeed)
        return await self._run('moveTo', body)

    def _prepare_move(self, *, pan=None, tilt=None, roll=None, toleranceDeg=1, timeoutMs=30000,
                      telemetryTimeoutMs=3000, gain=0.02, minSpeed=0.05, maxSpeed=0.18):
        target = {name: finite(value, name) for name, value in dict(pan=pan, tilt=tilt, roll=roll).items() if value is not None}
        if not target or any(abs(value) > 180 for value in target.values()):
            raise ValueError('Provide at least one target in -180..180 degrees')
        for name, value in dict(toleranceDeg=toleranceDeg, timeoutMs=timeoutMs, telemetryTimeoutMs=telemetryTimeoutMs, gain=gain).items():
            positive(value, name)
        if not (math.isfinite(minSpeed) and math.isfinite(maxSpeed) and 0 <= minSpeed <= maxSpeed <= 1):
            raise ValueError('speeds must satisfy 0 <= minSpeed <= maxSpeed <= 1')
        async def body(operation):
            started = time.monotonic()
            operation['deadline'] = started + timeoutMs / 1000
            current = None
            as_axes = lambda value: dict(pan=value['yaw'], tilt=value['pitch'], roll=value['roll'])
            operation['timeout_error'] = lambda: RS4MiniError('RS4MINI_MOVE_TIMEOUT', 'moveTo timed out', target=dict(target), current=as_axes(current) if current else None)
            while True:
                current = await self._reading('jointAngles', True, telemetryTimeoutMs, operation)
                self._check(operation)
                values = as_axes(current)
                errors = {name: target[name] - values[name] if name in target else 0 for name in ('pan', 'tilt', 'roll')}
                errors['pan'] = (errors['pan'] + 180) % 360 - 180
                if all(abs(value) <= toleranceDeg for value in errors.values()):
                    return dict(target=dict(target), current=values, error=errors, toleranceDeg=toleranceDeg, elapsedMs=(time.monotonic() - started) * 1000)
                def speed(error):
                    return 0 if abs(error) <= toleranceDeg else math.copysign(min(maxSpeed, max(minSpeed, abs(error) * gain)), error)
                await self._set_velocity(dict(pan=speed(errors['pan']), tilt=-speed(errors['tilt']), roll=speed(errors['roll'])), operation)
        return body

    async def set_velocity_deg(self, *, pan=0.0, tilt=0.0, roll=0.0, pan_full_scale=37.5, tilt_full_scale=27.5, roll_full_scale=30):
        return await self.setVelocityDeg(pan=pan, tilt=tilt, roll=roll, panFullScale=pan_full_scale, tiltFullScale=tilt_full_scale, rollFullScale=roll_full_scale)

    async def move_for(self, duration, *, pan=0.0, tilt=0.0, roll=0.0):
        return await self.moveFor(durationMs=duration * 1000, pan=pan, tilt=tilt, roll=roll)

    async def move_to(self, **options):
        names = dict(tolerance_deg='toleranceDeg', timeout_ms='timeoutMs', telemetry_timeout_ms='telemetryTimeoutMs', min_speed='minSpeed', max_speed='maxSpeed')
        return await self.moveTo(**{names.get(key, key): value for key, value in options.items()})

    move_to_active = property(lambda self: self.moveToActive)
