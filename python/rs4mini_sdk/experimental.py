"""Explicit experimental command facade, separate from verified joint control."""
import asyncio
import copy
import math
import time
from .protocol import frame
from .experimental_protocol import research_profile, rs3_absolute_frame, rs3_rate_frame, research_sleep_frame, decode_research_status


def _error(code, message):
    from .controller import RS4MiniError
    return RS4MiniError(code, message)


def _duration(value, name, zero=True):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (not zero and value == 0) or value > 60000:
        raise ValueError(name + ' outside 0..60000 ms')


class ExperimentalGimbal:
    def __init__(self, owner):
        self.owner = owner
        self._profile = None
        self._status = {}
        self.pending = {}

    profile = property(lambda self: self._profile)
    status = property(lambda self: copy.deepcopy(self._status))

    def useProfile(self, profile):
        research_profile(profile)
        if self.owner.activeOperation or self.pending:
            raise _error('RS4MINI_BUSY', 'Cannot change research profile during an operation or query')
        self._profile, self._status = profile, {}

    use_profile = useProfile

    def _require_profile(self, rs3_only=False):
        research_profile(self._profile)
        if rs3_only and self._profile != 'rs3':
            raise ValueError('This command is documented only in the rs3 research profile')
        return self._profile

    def _reset(self):
        self._status = {}
        for entry in list(self.pending.values()):
            entry['operation']['error'] = _error('RS4MINI_DISCONNECTED', 'Disconnected during query')
            entry['operation']['cancel'].set()

    def _message(self, message):
        pending = self.pending.get(message['sequence'])
        if (pending and pending['client'] is self.owner.client and message['sender'] == 4 and message['receiver'] == 2 and
                message['flags'] & 0x80 and (message['commandSet'], message['commandId']) == pending['command'] and not pending['future'].done()):
            pending['future'].set_result(copy.deepcopy(message))
        if self._profile:
            status = decode_research_status(message, self._profile)
            if status:
                self._status[status['kind']] = status
                self.owner._emit('onExperimentalStatus', copy.deepcopy(status))

    async def query(self, *, kind, timeoutMs=3000):
        self._require_profile()
        commands = dict(version=(0, 1), position=(4, 2), controlStatus=(4, 0x0b), type=(4, 0x1c))
        if kind not in commands:
            raise ValueError('invalid research query kind')
        _duration(timeoutMs, 'timeoutMs', False)
        self.owner._require_connected()
        if len(self.pending) >= 64:
            raise _error('RS4MINI_BUSY', 'Too many pending queries')
        sequence = self.owner._next_sequence()
        response = asyncio.get_running_loop().create_future()
        operation = dict(cancel=asyncio.Event(), error=_error('RS4MINI_OPERATION_CANCELLED', 'Query finished'))
        entry = dict(future=response, operation=operation, client=self.owner.client, command=commands[kind])
        self.pending[sequence] = entry
        command_set, command_id = commands[kind]

        async def work():
            await self.owner._enqueue(frame(sequence, command_set, command_id, flags=0x40), operation=operation)
            self.owner._check(operation)
            return await response
        task = asyncio.create_task(work())
        self.owner._backgroundTasks.add(task)
        def completed(done):
            self.owner._backgroundTasks.discard(done)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(completed)
        try:
            # Shield an already-started frame; timeout cancels queued work via its operation event.
            return await self.owner._bounded(asyncio.shield(task), timeoutMs / 1000, cancel=operation['cancel'],
                cancel_error=lambda: operation['error'], timeout_error=_error('RS4MINI_RESPONSE_TIMEOUT', kind + ' query had no correlated response'))
        finally:
            self.pending.pop(sequence, None)
            operation['cancel'].set()
            if not response.done():
                response.cancel()

    async def setSleep(self, *, asleep):
        profile = self._require_profile()
        research_sleep_frame(0, profile, asleep)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            await self.owner._enqueue(research_sleep_frame(self.owner._next_sequence(), profile, asleep), operation=operation, epoch=self.owner._epoch)
            return dict(sent=True, deviceVerified=False, physicalCompletionVerified=False)
        return await self.owner._run('experimentalSleep', body, False)

    set_sleep = setSleep

    async def absolute(self, *, parameterByte, pan=None, tilt=None, roll=None, observeMs=3000):
        self._require_profile(True)
        _duration(observeMs, 'observeMs')
        values = dict(pan=pan, tilt=tilt, roll=roll, parameterByte=parameterByte)
        rs3_absolute_frame(0, **values)
        async def body(operation):
            await self.owner._halt()
            self.owner._check(operation)
            await self.owner._enqueue(rs3_absolute_frame(self.owner._next_sequence(), **values), operation=operation, epoch=self.owner._epoch)
            await self.owner._motion_delay(observeMs, operation)
            return dict(sent=True, deviceVerified=False, physicalCompletionVerified=False)
        return await self.owner._run('experimentalAbsolute', body)

    async def rateFor(self, *, durationMs, pan=0, tilt=0, roll=0):
        self._require_profile(True)
        _duration(durationMs, 'durationMs')
        values = dict(pan=pan, tilt=tilt, roll=roll)
        rs3_rate_frame(0, **values)
        async def body(operation):
            started = time.monotonic()
            self.owner._nativeRateProfile = 'rs3'
            while (time.monotonic() - started) * 1000 < durationMs:
                self.owner._check(operation)
                await self.owner._enqueue(rs3_rate_frame(self.owner._next_sequence(), **values), operation=operation, epoch=self.owner._epoch)
                await self.owner._motion_delay(min(1000 / self.owner.rateHz, max(0, durationMs - (time.monotonic() - started) * 1000)), operation)
            return dict(sent=True, deviceVerified=False, physicalCompletionVerified=False)
        return await self.owner._run('experimentalRate', body)

    async def rate_for(self, *, duration_ms, pan=0, tilt=0, roll=0):
        return await self.rateFor(durationMs=duration_ms, pan=pan, tilt=tilt, roll=roll)
