"""Composed motion policies, independent of Bleak transports."""
import asyncio
import copy
import math
import time
from .orientation import orientation_from_components

AXES = ('pan', 'tilt', 'roll')


def _positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' must be greater than zero')


def _error(code, message):
    # Shared error contract does not import the application layer.
    from .errors import RS4MiniError
    return RS4MiniError(code, message)


def velocity_keyframes(points, interpolation):
    if interpolation not in ('linear', 'smoothstep', 'step'):
        raise ValueError('invalid interpolation')
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise ValueError('trajectory requires at least two keyframes')
    result, previous = [], -1
    for index, point in enumerate(points):
        if not isinstance(point, dict) or set(point) - set(AXES + ('timeMs',)):
            raise ValueError('invalid keyframe')
        stamp = point.get('timeMs')
        if type(stamp) not in (float, int) or not math.isfinite(stamp) or stamp > 0x7fffffff or stamp <= previous or (index == 0 and stamp != 0):
            raise ValueError('keyframe times must start at zero and strictly increase')
        values = {axis: point.get(axis, 0) for axis in AXES}
        if any(type(value) not in (float, int) or not math.isfinite(value) or abs(value) > 1 for value in values.values()):
            raise ValueError('axis values must be in -1..1')
        result.append(dict(values, timeMs=stamp))
        previous = stamp
    return result


def interpolate_velocity(points, stamp, interpolation):
    index = 0
    while index < len(points) - 2 and points[index + 1]['timeMs'] <= stamp:
        index += 1
    a, b = points[index:index + 2]
    ratio = max(0, min(1, (stamp - a['timeMs']) / (b['timeMs'] - a['timeMs'])))
    if interpolation == 'step':
        ratio = 1 if stamp >= b['timeMs'] else 0
    elif interpolation == 'smoothstep':
        ratio = ratio * ratio * (3 - 2 * ratio)
    return {axis: a[axis] + (b[axis] - a[axis]) * ratio for axis in AXES}


class ExpansionMixin:
    def _init_expansion(self):
        self._trajectoryProgress = self._home = None

    trajectoryProgress = property(lambda self: copy.deepcopy(self._trajectoryProgress))
    home = property(lambda self: copy.deepcopy(self._home))
    trajectory_progress = property(lambda self: self.trajectoryProgress)

    async def _motion_delay(self, milliseconds, operation):
        await self._bounded(asyncio.sleep(milliseconds / 1000), milliseconds / 1000 + 1,
                            cancel=operation['cancel'], cancel_error=lambda: operation['error'])
        self._check(operation)

    async def runTrajectory(self, keyframes, *, interpolation='linear', maxLagMs=500):
        points = velocity_keyframes(keyframes, interpolation)
        _positive(maxLagMs, 'maxLagMs')
        async def body(operation):
            start, duration, interval = time.monotonic(), points[-1]['timeMs'], 1000 / self.rateHz
            due = sent = skipped = 0
            try:
                while True:
                    await self._motion_delay(max(0, due - (time.monotonic() - start) * 1000), operation)
                    elapsed = (time.monotonic() - start) * 1000
                    if elapsed - due > maxLagMs:
                        raise _error('RS4MINI_TRAJECTORY_OVERRUN', 'Trajectory scheduler exceeded maxLagMs')
                    if elapsed >= duration:
                        break
                    values = interpolate_velocity(points, elapsed, interpolation)
                    await self._write_velocity(values, operation)
                    if (time.monotonic() - start) * 1000 - elapsed > maxLagMs:
                        raise _error('RS4MINI_TRAJECTORY_OVERRUN', 'BLE trajectory write exceeded maxLagMs')
                    sent += 1
                    self._trajectoryProgress = dict(kind='velocity', elapsedMs=elapsed, durationMs=duration, sentFrames=sent, skippedFrames=skipped)
                    following = min(duration, max(due + interval, math.ceil((time.monotonic() - start) * 1000 / interval) * interval))
                    skipped += max(0, math.floor((following - due) / interval + 0.5) - 1)
                    due = following
                return dict(elapsedMs=(time.monotonic() - start) * 1000, durationMs=duration, sentFrames=sent, skippedFrames=skipped)
            finally:
                self._trajectoryProgress = None
        return await self._run('runTrajectory', body)

    async def moveThrough(self, waypoints, **settings):
        if set(settings) - {'toleranceDeg', 'timeoutMs', 'telemetryTimeoutMs', 'gain', 'minSpeed', 'maxSpeed'}:
            raise TypeError('invalid position settings')
        if not isinstance(waypoints, (list, tuple)) or not waypoints:
            raise ValueError('moveThrough requires waypoints')
        prepared = []
        for point in waypoints:
            if not isinstance(point, dict) or set(point) - set(AXES + ('holdMs',)):
                raise ValueError('invalid waypoint')
            hold = point.get('holdMs', 0)
            if type(hold) not in (float, int) or not math.isfinite(hold) or hold < 0 or hold > 0x7fffffff:
                raise ValueError('holdMs must be non-negative')
            target = {key: value for key, value in point.items() if key != 'holdMs'}
            prepared.append((self._prepare_move(**dict(settings, **target)), hold))
        async def body(operation):
            results = []
            try:
                for index, (move, hold) in enumerate(prepared):
                    self._trajectoryProgress = dict(kind='waypoints', index=index, count=len(prepared))
                    results.append(await move(operation))
                    operation.pop('deadline', None)
                    await self._halt()
                    await self._motion_delay(hold, operation)
                return results
            finally:
                self._trajectoryProgress = None
        return await self._run('moveThrough', body)

    async def captureHome(self, *, fresh=False, timeoutMs=3000):
        reading = await self.getJointAngles(fresh=fresh, timeoutMs=timeoutMs)
        self._home = dict(pan=reading['yaw'], tilt=reading['pitch'], roll=reading['roll'], timestamp=reading['timestamp'], deviceId=self.deviceId)
        return self.home

    async def getOrientation(self, *, componentOrder, conjugate=False, fresh=False, timeoutMs=3000, normTolerance=.1):
        orientation_from_components([1, 0, 0, 0], component_order=componentOrder, conjugate=conjugate)
        _positive(normTolerance, 'normTolerance')
        raw = await self._reading('orientationQuaternion', fresh, timeoutMs)
        if not math.isfinite(raw['norm']) or abs(raw['norm'] - 1) > normTolerance:
            raise _error('RS4MINI_ORIENTATION_INVALID', 'Raw orientation components are not approximately unit length')
        return dict(orientation_from_components(raw['components'], component_order=componentOrder, conjugate=conjugate), timestamp=raw['timestamp'])

    async def moveHome(self, *, axes=AXES, **settings):
        if not self._home or self._home['deviceId'] != self.deviceId:
            raise _error('RS4MINI_HOME_UNSET', 'Capture home for this device first')
        if not isinstance(axes, (list, tuple)) or not axes or any(axis not in AXES for axis in axes) or len(set(axes)) != len(axes):
            raise ValueError('axes must contain distinct pan, tilt or roll names')
        if set(settings) - {'toleranceDeg', 'timeoutMs', 'telemetryTimeoutMs', 'gain', 'minSpeed', 'maxSpeed'}:
            raise TypeError('invalid position settings')
        return await self.moveTo(**dict(settings, **{axis: self._home[axis] for axis in axes}))

    async def run_trajectory(self, keyframes, *, interpolation='linear', max_lag_ms=500):
        return await self.runTrajectory(keyframes, interpolation=interpolation, maxLagMs=max_lag_ms)

    async def move_through(self, waypoints, **options):
        return await self.moveThrough(waypoints, **self._position_names(options))

    async def capture_home(self, *, fresh=False, timeout_ms=3000):
        return await self.captureHome(fresh=fresh, timeoutMs=timeout_ms)

    async def move_home(self, **options):
        return await self.moveHome(**self._position_names(options))

    async def get_orientation(self, *, component_order, conjugate=False, fresh=False, timeout_ms=3000, norm_tolerance=.1):
        return await self.getOrientation(componentOrder=component_order, conjugate=conjugate, fresh=fresh, timeoutMs=timeout_ms, normTolerance=norm_tolerance)

    @staticmethod
    def _position_names(options):
        names = dict(tolerance_deg='toleranceDeg', timeout_ms='timeoutMs', telemetry_timeout_ms='telemetryTimeoutMs', min_speed='minSpeed', max_speed='maxSpeed')
        return {names.get(key, key): value for key, value in options.items()}
