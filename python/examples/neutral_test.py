import asyncio

from rs4mini_sdk import RS4Mini


async def main():
    gimbal = RS4Mini()
    try:
        await gimbal.connect(timeoutMs=20_000)
        print("connected:", gimbal.deviceName, gimbal.deviceAddress)
        await gimbal.stop()
        print("neutral stop test complete")
    finally:
        await gimbal.close()


if __name__ == "__main__":
    asyncio.run(main())
