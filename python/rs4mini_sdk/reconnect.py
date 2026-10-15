"""Bounded device reconnection policy; never resumes motion."""
import asyncio
import copy
import math

def _positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' must be greater than zero')


class ReconnectMixin:
    def _init_reconnect(self):
        self._reconnectPolicy = self._reconnectTask = self._reconnectCancel = None
        self._reconnectAgain = False
        self._reconnectState = dict(state='disabled', attempt=0)
        self.onReconnect = None

    reconnectState = property(lambda self: copy.deepcopy(self._reconnectState))
    reconnect_state = property(lambda self: self.reconnectState)

    def enableAutoReconnect(self, *, maxAttempts=5, initialDelayMs=500, maxDelayMs=10000,
                            backoff=2, timeoutMs=10000, directConnectTimeoutMs=5000):
        if self.closed:
            raise RuntimeError('RS4Mini controller is closed')
        policy = dict(maxAttempts=maxAttempts, initialDelayMs=initialDelayMs, maxDelayMs=maxDelayMs,
                      backoff=backoff, timeoutMs=timeoutMs, directConnectTimeoutMs=directConnectTimeoutMs)
        for name, value in policy.items():
            _positive(value, name)
        if any(policy[name] > 0x7fffffff for name in ('initialDelayMs', 'maxDelayMs', 'timeoutMs', 'directConnectTimeoutMs')):
            raise ValueError('reconnect duration exceeds timer range')
        if not isinstance(maxAttempts, int) or maxAttempts > 100 or backoff < 1 or maxDelayMs < initialDelayMs:
            raise ValueError('invalid reconnect retry policy')
        self._reconnectPolicy = policy
        if not self._reconnectTask:
            self._reconnect_status('idle', 0)

    def _reconnect_status(self, state, attempt, **details):
        self._reconnectState = dict(state=state, attempt=attempt, **details)
        self._emit('onReconnect', self.reconnectState)

    def _cancel_reconnect(self):
        self._reconnectPolicy = None
        if self._reconnectCancel:
            self._reconnectCancel.set()
        if self._context and self._context.get('reconnectOwner') is self._reconnectTask and self._reconnectTask:
            self._context['cancel'].set()
        self._reconnect_status('disabled', 0)

    async def disableAutoReconnect(self):
        self._cancel_reconnect()
        if self._reconnectTask:
            await asyncio.shield(self._reconnectTask)

    def _schedule_reconnect(self):
        if not self._reconnectPolicy or self.closed or self._disconnectTask:
            return
        if self._reconnectTask:
            self._reconnectAgain = True
            return
        policy, cancel = dict(self._reconnectPolicy), asyncio.Event()
        self._reconnectCancel = cancel
        old_operation = self._operation
        old_connect, old_stream = self._connectTask, self._streamTask

        async def run():
            try:
                await asyncio.sleep(0)  # Include cleanup scheduled by a failing write.
                drain = [task for task in [old_connect, old_stream, old_operation['done'] if old_operation else None] if task]
                await asyncio.gather(*(drain + list(self._backgroundTasks)), return_exceptions=True)
                for attempt in range(1, policy['maxAttempts'] + 1):
                    if cancel.is_set():
                        return
                    if self.connected:
                        self._reconnect_status('restored', attempt - 1)
                        return
                    delay_ms = policy['initialDelayMs'] if attempt == 1 else min(policy['maxDelayMs'], delay_ms * policy['backoff'])
                    self._reconnect_status('waiting', attempt, delayMs=delay_ms)
                    try:
                        await asyncio.wait_for(cancel.wait(), delay_ms / 1000)
                        return
                    except asyncio.TimeoutError:
                        pass
                    self._reconnect_status('connecting', attempt)
                    if cancel.is_set():
                        return
                    try:
                        await self.connect(timeoutMs=policy['timeoutMs'], directConnectTimeoutMs=policy['directConnectTimeoutMs'])
                        if not cancel.is_set():
                            self._reconnect_status('restored', attempt)
                        return
                    except Exception as error:
                        if cancel.is_set():
                            return
                        if attempt == policy['maxAttempts']:
                            self._reconnect_status('exhausted', attempt, error=dict(code=getattr(error, 'code', None), message=str(error)))
            except Exception as error:
                if not cancel.is_set():
                    self._emit('onError', error)
            finally:
                if self._reconnectTask is asyncio.current_task():
                    self._reconnectTask = self._reconnectCancel = None
                    again, self._reconnectAgain = self._reconnectAgain, False
                    if again and not self.connected:
                        self._schedule_reconnect()
        self._reconnectTask = asyncio.create_task(run())

    def enable_auto_reconnect(self, **options):
        names = dict(max_attempts='maxAttempts', initial_delay_ms='initialDelayMs', max_delay_ms='maxDelayMs',
                     timeout_ms='timeoutMs', direct_connect_timeout_ms='directConnectTimeoutMs')
        return self.enableAutoReconnect(**{names.get(key, key): value for key, value in options.items()})

    disable_auto_reconnect = disableAutoReconnect
