import asyncio

from rs4mini_sdk import RS4Mini


async def main():
    async with RS4Mini() as gimbal:
        # About 8°/s pan-right + 4°/s tilt-up + gentle positive roll.
        await gimbal.setVelocity(pan=8 / 37.5, tilt=4 / 27.5, roll=0.08)
        await asyncio.sleep(1.0)
        await gimbal.stop()


if __name__ == "__main__":
    asyncio.run(main())
