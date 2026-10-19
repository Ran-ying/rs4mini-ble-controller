"""Explicit experimental command facade, separate from verified joint control."""
import asyncio
import copy
import math
import time
from .protocol import frame
from .experimental_protocol import research_profile, rs3_absolute_frame, rs3_rate_frame, research_sleep_frame, decode_research_status


def _error(code, message):
    from .errors import RS4MiniError
    return RS4MiniError(code, message)


def _duration(value, name, zero=True):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (not zero and value == 0) or value > 60000:
        raise ValueError(name + ' outside 0..60000 ms')


class ExperimentalDevice:
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
        if hasattr(self.owner, "appCommands"):
            self.owner.appCommands._profile = None
            self.owner.appCommands._reset()

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
        if (pending and pending['client'] is self.owner.client and message['sender'] == pending['receiver'] and message['receiver'] == 2 and
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
        return await self._query_command(kind, commands[kind], timeoutMs)

    async def _query_command(self, kind, command, timeoutMs=3000):
        return await self._query_payload_command(kind, command, b'', timeoutMs)

    async def _query_payload_command(self, kind, command, payload, timeoutMs=3000, *, external_operation=None, epoch=None, receiver=4):
        if receiver != 4 and not (type(receiver) is int and receiver == 229 and command == (0,50) and self.owner.appCommands.profile == 'ronin-2.2.2' and isinstance(payload,(bytes,bytearray)) and payload in (b'\x01',b'\x11')):
            raise ValueError('Unsupported query route')
        _duration(timeoutMs, 'timeoutMs', False)
        self.owner._require_connected()
        if len(self.pending) >= 64:
            raise _error('RS4MINI_BUSY', 'Too many pending queries')
        sequence = self.owner._next_sequence()
        response = asyncio.get_running_loop().create_future()
        operation = dict(cancel=asyncio.Event(), error=_error('RS4MINI_OPERATION_CANCELLED', 'Query finished'))
        bridge = None
        if external_operation:
            async def propagate_cancel():
                await external_operation['cancel'].wait()
                operation['error'] = external_operation['error'] or _error('RS4MINI_OPERATION_CANCELLED', 'Operation cancelled')
                operation['cancel'].set()
            bridge = asyncio.create_task(propagate_cancel())
        entry = dict(future=response, operation=operation, client=self.owner.client, command=command, receiver=receiver)
        self.pending[sequence] = entry
        command_set, command_id = command

        async def work():
            await self.owner._enqueue(frame(sequence, command_set, command_id, payload, flags=0x40, receiver=receiver), operation=operation, epoch=epoch)
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
            if bridge:
                bridge.cancel()
                await asyncio.gather(bridge, return_exceptions=True)
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

    def _validate_absolute(self, values):
        self._require_profile(True)
        rs3_absolute_frame(0, **values)

    def _validate_rate(self, values):
        self._require_profile(True)
        rs3_rate_frame(0, **values)

    async def _write_absolute(self, values, operation):
        await self.owner._enqueue(rs3_absolute_frame(self.owner._next_sequence(), **values), operation=operation, epoch=self.owner._epoch)

    def _begin_rate(self):
        self.owner._nativeRateProfile = 'rs3'

    async def _write_rate(self, values, operation):
        self._begin_rate()
        await self.owner._enqueue(rs3_rate_frame(self.owner._next_sequence(), **values), operation=operation, epoch=self.owner._epoch)
