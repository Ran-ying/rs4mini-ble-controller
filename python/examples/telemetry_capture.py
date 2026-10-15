"""Read feedback only; normal close sends the SDK's neutral frames."""
import asyncio
import os
from rs4mini_sdk import RS4Mini


async def main():
    duration = float(os.environ.get('RS4MINI_CAPTURE_MS', '5000'))
    if not 0 < duration <= 60000:
        raise ValueError('RS4MINI_CAPTURE_MS must be in 0..60000')
    gimbal = RS4Mini(deviceId=os.environ.get('RS4MINI_DEVICE_ID'))
    try:
        await gimbal.connect()
        deadline = asyncio.get_running_loop().time() + duration / 1000
        while asyncio.get_running_loop().time() < deadline:
            print(await gimbal.getJointAngles(fresh=True))
    finally:
        await gimbal.close()


if __name__ == '__main__':
    asyncio.run(main())
