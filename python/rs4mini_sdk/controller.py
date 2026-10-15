"""Async BLE control, feedback, and cancellable motion operations (Python 3.8+)."""
import asyncio
import copy
import inspect
import math
import time
from contextlib import suppress
from bleak import BleakClient, BleakScanner
from .protocol import recenter_frame, velocity_frame
from .telemetry import DumlStreamDecoder, decode_gimbal_telemetry
from .expansion import ExpansionMixin
from .experimental import ExperimentalGimbal
from .experimental_protocol import rs3_rate_frame

NOTIFY = '0000fff4-0000-1000-8000-00805f9b34fb'
WRITE = '0000fff5-0000-1000-8000-00805f9b34fb'
_UNSET = object()


class RS4MiniError(RuntimeError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.__dict__.update(details)


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' must be greater than 0')


def finite(value, name):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(name + ' must be finite')
    return number


class RS4Mini(ExpansionMixin):
    def __init__(self, *, nameIncludes='DJI RS4 MINI', rateHz=15.0, deviceId=None,
                 ioTimeoutMs=3000, name_contains=None, rate_hz=None,
                 client_factory=None, scanner=None):
        if name_contains is not None:
            nameIncludes = name_contains
        if rate_hz is not None:
            rateHz = rate_hz
        positive(rateHz, 'rateHz')
        positive(ioTimeoutMs, 'ioTimeoutMs')
        if not isinstance(nameIncludes, str) or not nameIncludes.strip():
            raise ValueError('nameIncludes must be nonempty')
        if deviceId is not None and (not isinstance(deviceId, str) or not deviceId):
            raise ValueError('deviceId must be a nonempty string or None')
        self.nameIncludes = nameIncludes.upper()
        self.rateHz, self.ioTimeoutMs = float(rateHz), ioTimeoutMs
        self.deviceId = deviceId
        self.client = self.deviceName = None
        self._ready = False
        self.closed = False
        self.sequence = 0x0100
        self._velocity = dict(pan=0.0, tilt=0.0, roll=0.0)
        self._latestTelemetry = None
        self.decoder = DumlStreamDecoder()
        self.onNotification = self.onMessage = self.onTelemetry = self.onDisconnect = self.onError = None
        self._factory, self._scanner = client_factory or BleakClient, scanner or BleakScanner
        self._connectTask = self._disconnectTask = self._closeTask = self._stopTask = self._streamTask = None
        self._context = self._operation = self._streamStop = self._writeLock = None
        self._waiters = set()
        self._backgroundTasks = set()
        self._epoch = 0
        self._init_expansion()
        self.experimental = ExperimentalGimbal(self)
        self.onExperimentalStatus = self._nativeRateProfile = None

    @property
    def connected(self):
        return bool(self._ready and self.client and self.client.is_connected)

    @property
    def moveToActive(self):
        return bool(self._operation and self._operation['kind'] == 'moveTo')

    @property
    def activeOperation(self):
        return self._operation['kind'] if self._operation else ('stop' if self._stopTask else None)

    @property
    def deviceAddress(self):
        return self.deviceId

    @property
    def velocity(self):
        return dict(self._velocity)

    @property
    def latestTelemetry(self):
        return copy.deepcopy(self._latestTelemetry)

    def _emit(self, name, *args):
        callback = getattr(self, name)
        if callback is None:
            return
        try:
            result = callback(*args)
            if inspect.isawaitable(result):
                task = asyncio.ensure_future(result)
                task.add_done_callback(lambda done: self._callback_done(done, name))
        except Exception as error:
            if name != 'onError':
                self._emit('onError', error)

    def _callback_done(self, task, name):
        if not task.cancelled() and task.exception() and name != 'onError':
            self._emit('onError', task.exception())

    async def _bounded(self, work, seconds, *, cancel=None, cancel_error=None, timeout_error=None, late=None):
        task = asyncio.ensure_future(work)
        cancellation = asyncio.create_task(cancel.wait()) if cancel else None
        abandoned = False
        try:
            done, _ = await asyncio.wait([task] + ([cancellation] if cancellation else []), timeout=max(0, seconds), return_when=asyncio.FIRST_COMPLETED)
            if cancel and cancel.is_set():
                raise cancel_error() if callable(cancel_error) else cancel_error or RS4MiniError('RS4MINI_OPERATION_CANCELLED', 'Operation cancelled')
            if task not in done:
                raise timeout_error or RS4MiniError('RS4MINI_IO_TIMEOUT', 'BLE operation timed out')
            return await task
        except BaseException:
            abandoned = True
            task.cancel()
            def finished(done):
                if done.cancelled():
                    return
                error = done.exception()
                if error is None and late:
                    self._background(late(done.result()))
            task.add_done_callback(finished)
            raise
        finally:
            if cancellation:
                cancellation.cancel()
            if not abandoned and task.done() and not task.cancelled():
                task.exception()

    def _background(self, work):
        task = asyncio.create_task(self._bounded(work, self.ioTimeoutMs / 1000))
        self._backgroundTasks.add(task)
        def completed(done):
            self._backgroundTasks.discard(done)
            if not done.cancelled() and done.exception():
                self._emit('onError', done.exception())
        task.add_done_callback(completed)
        return task

    async def connect(self, timeout=None, *, timeoutMs=None, deviceId=_UNSET, directConnectTimeoutMs=5000):
        if timeout is not None and timeoutMs is not None:
            raise ValueError('use either timeout (seconds) or timeoutMs, not both')
        milliseconds = timeoutMs if timeoutMs is not None else (timeout * 1000 if timeout is not None else 30000)
        positive(milliseconds, 'timeoutMs')
        positive(directConnectTimeoutMs, 'directConnectTimeoutMs')
        selected_id = self.deviceId if deviceId is _UNSET else deviceId
        if selected_id is not None and (not isinstance(selected_id, str) or not selected_id):
            raise ValueError('deviceId must be a nonempty string or None')
        if self.closed:
            raise RuntimeError('RS4Mini controller is closed')
        if self._disconnectTask:
            raise RS4MiniError('RS4MINI_BUSY', 'disconnect is active')
        if self._connectTask:
            return await asyncio.shield(self._connectTask)
        if self.connected:
            return self.deviceName
        context = dict(cancel=asyncio.Event(), deadline=time.monotonic() + milliseconds / 1000,
                       client=None, error=RS4MiniError('RS4MINI_CONNECT_CANCELLED', 'Connection cancelled by close() or disconnect()'))
        context['reconnectOwner'] = asyncio.current_task() if asyncio.current_task() is self._reconnectTask else None
        self._context = context
        task = self._connectTask = asyncio.create_task(self._connect(context, selected_id, directConnectTimeoutMs))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            context['cancel'].set()
            raise
        finally:
            if task.done() and self._connectTask is task:
                self._connectTask = self._context = None
            elif not task.done():
                def clear(done):
                    if self._connectTask is done:
                        self._connectTask = self._context = None
                    if not done.cancelled():
                        done.exception()
                task.add_done_callback(clear)

    async def _connection_wait(self, context, work, stage, cap=math.inf, late=None):
        remaining = context['deadline'] - time.monotonic()
        return await self._bounded(work, min(cap, remaining), cancel=context['cancel'], cancel_error=context['error'],
                                   timeout_error=RS4MiniError('RS4MINI_CONNECT_TIMEOUT', 'Connection timed out during ' + stage), late=late)

    async def _connect(self, context, device_id, direct_timeout):
        candidate = None
        try:
            if device_id:
                candidate = context['client'] = self._factory(device_id, disconnected_callback=self._on_disconnect)
                try:
                    await self._connection_wait(context, candidate.connect(), 'cached connection', direct_timeout / 1000,
                                                late=lambda _, stale=candidate: self._discard(stale))
                except Exception:
                    self._background(self._discard(candidate))
                    if context['cancel'].is_set() or time.monotonic() >= context['deadline']:
                        raise
                    candidate = context['client'] = None
            if candidate is None:
                normalize = lambda value: ''.join((value or '').upper().split())
                def matches(device, advertisement):
                    return normalize(self.nameIncludes) in normalize(advertisement.local_name or device.name)
                device = await self._connection_wait(context, self._scanner.find_device_by_filter(matches, timeout=max(0.001, context['deadline'] - time.monotonic())), 'scan')
                if device is None:
                    raise RS4MiniError('RS4MINI_CONNECT_TIMEOUT', 'RS 4 Mini scan timed out')
                candidate = context['client'] = self._factory(device, disconnected_callback=self._on_disconnect)
                await self._connection_wait(context, candidate.connect(), 'GATT connection', late=lambda _, stale=candidate: self._discard(stale))
            if context['cancel'].is_set():
                raise context['error']
            self.client = candidate
            self.decoder.reset()
            self._latestTelemetry = None
            await self._connection_wait(context, candidate.start_notify(NOTIFY, lambda c, data: self._notification(candidate, data)), 'notification subscription',
                                        late=lambda _, stale=candidate: self._discard(stale))
            if context['cancel'].is_set():
                raise context['error']
            self._ready = True
            self.deviceId = candidate.address
            self.deviceName = getattr(candidate, 'name', None) or 'DJI RS4 MINI'
            return self.deviceName
        except BaseException:
            if self.client is candidate:
                self.client = None
                self._ready = False
            if candidate:
                self._background(self._discard(candidate))
            raise

    async def _discard(self, candidate):
        if self.client is candidate:
            return
        await candidate.disconnect()

    def _notification(self, candidate, data):
        if candidate is not self.client:
            return
        messages = self.decoder.push(data)
        self._emit('onNotification', bytes(data))
        for message in messages:
            if self.client is not candidate:
                break
            self.experimental._message(message)
            telemetry = decode_gimbal_telemetry(message)
            if telemetry:
                self._latestTelemetry = telemetry
                for waiter, field in list(self._waiters):
                    if not waiter.done() and telemetry.get(field):
                        waiter.set_result(telemetry)
            self._emit('onMessage', copy.deepcopy(message))
            if telemetry:
                self._emit('onTelemetry', copy.deepcopy(telemetry))

    def _on_disconnect(self, candidate):
        error = RS4MiniError('RS4MINI_DISCONNECTED', 'RS 4 Mini disconnected')
        if self._context and self._context['client'] is candidate:
            self._context['error'] = error
            self._context['cancel'].set()
        if candidate is not self.client:
            return
        was_ready = self._ready
        self.client = self.deviceName = self._latestTelemetry = None
        self._ready = False
        self._nativeRateProfile = None
        self.experimental._reset()
        self.decoder.reset()
        self._velocity = dict(pan=0.0, tilt=0.0, roll=0.0)
        self._epoch += 1
        if self._streamStop:
            self._streamStop.set()
        self._cancel_operation(error)
        self._reject_waiters(error)
        self._emit('onDisconnect')
        if was_ready:
            self._schedule_reconnect()

    def _require_connected(self):
        if not self.connected:
            raise RS4MiniError('RS4MINI_DISCONNECTED', 'RS 4 Mini is not connected')

    def _check(self, operation):
        if operation['cancel'].is_set():
            raise operation['error']
        if operation.get('deadline') and time.monotonic() >= operation['deadline']:
            raise operation['timeout_error']()

    async def _run(self, kind, body, stop_after=True):
        self._require_connected()
        if self.closed or self._operation or self._stopTask or self._disconnectTask or self._connectTask:
            raise RS4MiniError('RS4MINI_BUSY', kind + ' cannot run while another operation is active')
        operation = dict(kind=kind, cancel=asyncio.Event(), error=None, done=asyncio.get_running_loop().create_future(), stop=None)
        self._operation = operation
        result = error = None
        try:
            if kind != 'setVelocity' and (self._streamTask or any(self.velocity.values())):
                await self._halt()
                self._check(operation)
            result = await body(operation)
            self._check(operation)
        except BaseException as reason:
            error = reason
        finally:
            if stop_after or error:
                try:
                    operation['stop'] = operation['stop'] or self._start_halt()
                    await asyncio.shield(operation['stop'])
                except BaseException as cleanup:
                    if error is None:
                        error = cleanup
                    else:
                        error.cleanup_error = cleanup
            if self._operation is operation:
                self._operation = None
            operation['done'].set_result(None)
        if error:
            if isinstance(error, asyncio.CancelledError):
                raise error
            if operation['cancel'].is_set() and kind in ('moveTo', 'moveFor', 'runTrajectory', 'moveThrough', 'experimentalAbsolute', 'experimentalRate'):
                raise RS4MiniError('RS4MINI_MOVE_CANCELLED', kind + ' was cancelled', cause=error)
            raise error
        return result

    async def setVelocity(self, *, pan=0.0, tilt=0.0, roll=0.0):
        values = {name: max(-1, min(1, finite(value, name))) for name, value in dict(pan=pan, tilt=tilt, roll=roll).items()}
        await self._run('setVelocity', lambda op: self._set_velocity(values, op), False)

    async def _set_velocity(self, values, operation):
        self._check(operation)
        self._velocity = dict(values)
        if not any(values.values()):
            await self._halt()
            return
        await self._enqueue(velocity_frame(self._next_sequence(), **values), operation=operation, epoch=self._epoch)
        self._check(operation)
        self._start_stream()

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

    async def _reading(self, kind, fresh=False, timeoutMs=3000, operation=None):
        if not isinstance(fresh, bool):
            raise ValueError('fresh must be boolean')
        positive(timeoutMs, 'timeoutMs')
        self._require_connected()
        if not fresh and self.latestTelemetry and self.latestTelemetry[kind]:
            sample = self.latestTelemetry
        else:
            if operation:
                self._check(operation)
            future = asyncio.get_running_loop().create_future()
            waiter = (future, kind)
            self._waiters.add(waiter)
            seconds = timeoutMs / 1000
            if operation and operation.get('deadline'):
                seconds = min(seconds, operation['deadline'] - time.monotonic())
            try:
                sample = await self._bounded(future, seconds, cancel=operation['cancel'] if operation else None,
                    cancel_error=(lambda: operation['error']) if operation else None,
                    timeout_error=RS4MiniError('RS4MINI_TELEMETRY_TIMEOUT', 'Timed out waiting for RS 4 Mini telemetry'))
            except RS4MiniError as error:
                if operation and operation.get('deadline') and time.monotonic() >= operation['deadline']:
                    raise operation['timeout_error']()
                raise error
            finally:
                self._waiters.discard(waiter)
                if not future.done():
                    future.cancel()
        return dict(copy.deepcopy(sample[kind]), timestamp=sample['timestamp'])

    async def getAttitude(self, *, fresh=False, timeoutMs=3000):
        return await self._reading('attitude', fresh, timeoutMs)

    async def getJointAngles(self, *, fresh=False, timeoutMs=3000):
        return await self._reading('jointAngles', fresh, timeoutMs)

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

    def _cancel_operation(self, error):
        if self._operation and not self._operation['cancel'].is_set():
            self._operation['error'] = error
            self._operation['cancel'].set()

    async def stop(self):
        operation = self._operation
        self._cancel_operation(RS4MiniError('RS4MINI_OPERATION_CANCELLED', 'Operation cancelled by stop()'))
        task = self._start_halt()
        if operation:
            operation['stop'] = task
        try:
            await asyncio.shield(task)
        finally:
            if operation and asyncio.current_task() is not operation.get('task'):
                await asyncio.shield(operation['done'])

    def _start_halt(self):
        if self._stopTask:
            return self._stopTask
        self._velocity = dict(pan=0.0, tilt=0.0, roll=0.0)
        self._epoch += 1
        if self._streamStop:
            self._streamStop.set()
        native_rate, self._nativeRateProfile = self._nativeRateProfile, None
        task = self._stopTask = asyncio.create_task(self._halt_body(native_rate))
        def clear(done):
            if self._stopTask is done:
                self._stopTask = None
            if not done.cancelled():
                done.exception()
        task.add_done_callback(clear)
        return task

    async def _halt(self):
        await asyncio.shield(self._start_halt())

    async def _halt_body(self, native_rate=None):
        if self._streamTask:
            await self._streamTask
        if self.connected:
            if native_rate:
                await self._enqueue(rs3_rate_frame(self._next_sequence(), release=True))
            for _ in range(3):
                await self._enqueue(velocity_frame(self._next_sequence(), 0, 0, 0))
                await asyncio.sleep(1 / self.rateHz)

    async def recenter(self):
        async def body(operation):
            await self._halt()
            self._check(operation)
            await self._enqueue(recenter_frame(self._next_sequence()), operation=operation, epoch=self._epoch)
        await self._run('recenter', body)

    def _start_stream(self):
        if self._streamTask:
            return
        stop, epoch = asyncio.Event(), self._epoch
        self._streamStop = stop
        async def run():
            try:
                while self.connected and any(self.velocity.values()) and not stop.is_set():
                    try:
                        await asyncio.wait_for(stop.wait(), 1 / self.rateHz)
                        break
                    except asyncio.TimeoutError:
                        pass
                    await self._enqueue(velocity_frame(self._next_sequence(), **self.velocity), epoch=epoch)
            except Exception as error:
                if not stop.is_set() or getattr(error, 'code', None) not in ('RS4MINI_OPERATION_CANCELLED', 'RS4MINI_DISCONNECTED'):
                    self._emit('onError', error)
            finally:
                if self._streamTask is asyncio.current_task():
                    self._streamTask = self._streamStop = None
        self._streamTask = asyncio.create_task(run())

    async def _enqueue(self, packet, operation=None, epoch=None):
        candidate = self.client
        if self._writeLock is None:
            self._writeLock = asyncio.Lock()
        async with self._writeLock:
            if operation:
                self._check(operation)
            self._require_connected()
            if candidate is not self.client or (epoch is not None and epoch != self._epoch):
                raise RS4MiniError('RS4MINI_OPERATION_CANCELLED', 'Stale queued write')
            try:
                for offset in range(0, len(packet), 20):
                    if candidate is not self.client:
                        raise RS4MiniError('RS4MINI_DISCONNECTED', 'BLE session changed')
                    await self._bounded(candidate.write_gatt_char(WRITE, packet[offset:offset + 20], response=False), self.ioTimeoutMs / 1000)
            except BaseException:
                self._on_disconnect(candidate)
                self._background(self._discard(candidate))
                raise

    def _reject_waiters(self, error):
        for future, _ in list(self._waiters):
            if not future.done():
                future.set_exception(error)

    async def disconnect(self):
        self._cancel_reconnect()
        self.experimental._reset()
        if self._disconnectTask:
            return await asyncio.shield(self._disconnectTask)
        if self._context:
            self._context['cancel'].set()
        async def cleanup():
            error = None
            self._reject_waiters(RS4MiniError('RS4MINI_DISCONNECTED', 'Disconnected while waiting for telemetry'))
            try:
                await self.stop()
            except Exception as reason:
                error = reason
            if self._connectTask:
                with suppress(Exception, asyncio.CancelledError):
                    await self._connectTask
            if self._reconnectTask:
                await self._reconnectTask
            candidate, self.client = self.client, None
            self._ready = False
            self.deviceName = self._latestTelemetry = None
            if candidate:
                try:
                    await self._bounded(candidate.stop_notify(NOTIFY), self.ioTimeoutMs / 1000)
                except Exception as reason:
                    error = error or reason
                try:
                    await self._bounded(candidate.disconnect(), self.ioTimeoutMs / 1000)
                except Exception as reason:
                    error = error or reason
                self._emit('onDisconnect')
            if error:
                raise error
        task = self._disconnectTask = asyncio.create_task(cleanup())
        def clear(done):
            if self._disconnectTask is done:
                self._disconnectTask = None
            if not done.cancelled():
                done.exception()
        task.add_done_callback(clear)
        try:
            await asyncio.shield(task)
        finally:
            if task.done():
                self._disconnectTask = None

    async def close(self):
        if self._closeTask:
            return await asyncio.shield(self._closeTask)
        self.closed = True
        async def cleanup():
            try:
                await self.disconnect()
            finally:
                if self._backgroundTasks:
                    await asyncio.gather(*list(self._backgroundTasks), return_exceptions=True)
        self._closeTask = asyncio.create_task(cleanup())
        await asyncio.shield(self._closeTask)

    def _next_sequence(self):
        while self.sequence in self.experimental.pending:
            self.sequence = (self.sequence + 1) & 0xffff
        current = self.sequence
        self.sequence = (current + 1) & 0xffff
        return current

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def set_velocity(self, pan=0.0, tilt=0.0, roll=0.0):
        return await self.setVelocity(pan=pan, tilt=tilt, roll=roll)

    async def set_velocity_deg(self, *, pan=0.0, tilt=0.0, roll=0.0, pan_full_scale=37.5, tilt_full_scale=27.5, roll_full_scale=30):
        return await self.setVelocityDeg(pan=pan, tilt=tilt, roll=roll, panFullScale=pan_full_scale, tiltFullScale=tilt_full_scale, rollFullScale=roll_full_scale)

    async def move_for(self, duration, *, pan=0.0, tilt=0.0, roll=0.0):
        return await self.moveFor(durationMs=duration * 1000, pan=pan, tilt=tilt, roll=roll)

    async def get_attitude(self, *, fresh=False, timeout_ms=3000):
        return await self.getAttitude(fresh=fresh, timeoutMs=timeout_ms)

    async def get_joint_angles(self, *, fresh=False, timeout_ms=3000):
        return await self.getJointAngles(fresh=fresh, timeoutMs=timeout_ms)

    async def move_to(self, **options):
        names = dict(tolerance_deg='toleranceDeg', timeout_ms='timeoutMs', telemetry_timeout_ms='telemetryTimeoutMs', min_speed='minSpeed', max_speed='maxSpeed')
        return await self.moveTo(**{names.get(key, key): value for key, value in options.items()})

    name_contains = property(lambda self: self.nameIncludes)
    rate_hz = property(lambda self: self.rateHz)
    device_name = property(lambda self: self.deviceName)
    device_address = property(lambda self: self.deviceAddress)
    device_id = property(lambda self: self.deviceId)
    latest_telemetry = property(lambda self: copy.deepcopy(self.latestTelemetry))
    move_to_active = property(lambda self: self.moveToActive)


for _snake, _camel in [('on_notification', 'onNotification'), ('on_message', 'onMessage'), ('on_telemetry', 'onTelemetry'), ('on_disconnect', 'onDisconnect'), ('on_error', 'onError'), ('on_reconnect', 'onReconnect'), ('on_experimental_status', 'onExperimentalStatus')]:
    setattr(RS4Mini, _snake, property(lambda self, name=_camel: getattr(self, name), lambda self, value, name=_camel: setattr(self, name, value)))
