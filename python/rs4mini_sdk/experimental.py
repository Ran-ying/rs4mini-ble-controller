"""Timed experimental tasks above the device protocol contract."""
import time
from .experimental_device import ExperimentalDevice, _duration

class ExperimentalGimbal(ExperimentalDevice):
    async def absolute(self, *, parameterByte, pan=None, tilt=None, roll=None, observeMs=3000):
        _duration(observeMs, 'observeMs')
        values = dict(pan=pan, tilt=tilt, roll=roll, parameterByte=parameterByte)
        self._validate_absolute(values)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            await self._write_absolute(values, operation)
            await self.owner._motion_delay(observeMs, operation)
            return dict(sent=True, deviceVerified=False, physicalCompletionVerified=False)
        return await self.owner._run('experimentalAbsolute', body)

    async def rateFor(self, *, durationMs, pan=0, tilt=0, roll=0):
        _duration(durationMs, 'durationMs')
        values = dict(pan=pan, tilt=tilt, roll=roll)
        self._validate_rate(values)
        async def body(operation):
            started = time.monotonic()
            self._begin_rate()
            while (time.monotonic() - started) * 1000 < durationMs:
                self.owner._check(operation)
                await self._write_rate(values, operation)
                await self.owner._motion_delay(min(1000 / self.owner.rateHz, max(0, durationMs - (time.monotonic() - started) * 1000)), operation)
            return dict(sent=True, deviceVerified=False, physicalCompletionVerified=False)
        return await self.owner._run('experimentalRate', body)

    async def rate_for(self, *, duration_ms, pan=0, tilt=0, roll=0):
        return await self.rateFor(durationMs=duration_ms, pan=pan, tilt=tilt, roll=roll)
