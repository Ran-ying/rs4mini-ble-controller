"""Explicit hardware motion: low-speed, single-axis out and back."""
import asyncio
import math
import os
from rs4mini_sdk import RS4Mini


async def main():
    axis = os.environ.get('RS4MINI_POSITION_AXIS', 'pan').lower()
    delta = float(os.environ.get('RS4MINI_POSITION_DELTA', '3'))
    if axis not in ('pan', 'tilt', 'roll') or not math.isfinite(delta) or not 0 < abs(delta) <= 90:
        raise ValueError('Choose pan/tilt/roll and a nonzero finite delta in -90..90 degrees')
    print('Hardware motion:', axis, delta, 'degrees out and back; confirm balance and clear space first.')
    gimbal = RS4Mini(deviceId=os.environ.get('RS4MINI_DEVICE_ID'))
    try:
        await gimbal.connect()
        start = await gimbal.getJointAngles(fresh=True)
        key = dict(pan='yaw', tilt='pitch', roll='roll')[axis]
        target = start[key] + delta
        if axis == 'pan':
            target = (target + 180) % 360 - 180
        if not -180 <= target <= 180:
            raise ValueError('Target is outside the API angle range')
        print(await gimbal.moveTo(**{axis: target}))
        await asyncio.sleep(0.5)
        print(await gimbal.moveTo(**{axis: start[key]}))
    finally:
        await gimbal.close()


if __name__ == '__main__':
    asyncio.run(main())
