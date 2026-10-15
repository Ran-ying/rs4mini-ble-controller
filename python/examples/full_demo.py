import asyncio
import os

from rs4mini_sdk import RS4Mini


async def main() -> None:
    # Python exposes the same camelCase API as the primary Node implementation.
    # Snake_case aliases remain available for Python projects that prefer them.
    gimbal = RS4Mini(nameIncludes="DJI RS4 MINI", rateHz=15)

    # Raw chunks and decoded feedback are both available in 0.6.0.
    def notification(packet: bytes) -> None:
        if os.getenv("RS4MINI_LOG_PACKETS") == "1":
            print("notify:", packet.hex())

    gimbal.onNotification = notification
    gimbal.onDisconnect = lambda: print("gimbal disconnected")
    gimbal.onError = lambda error: print("BLE stream error:", error)

    try:
        # 1. Scan, connect, discover FFF4/FFF5, and subscribe to notifications.
        name = await gimbal.connect(timeoutMs=30_000)
        print("connected:", name, gimbal.deviceAddress)
        print("joint angles:", await gimbal.getJointAngles(fresh=True))

        # 2. Safe, duration-bounded single-axis movements (-1..+1).
        await gimbal.moveFor(durationMs=600, pan=0.12)
        await asyncio.sleep(0.3)
        await gimbal.moveFor(durationMs=600, tilt=0.10)
        await asyncio.sleep(0.3)
        await gimbal.moveFor(durationMs=400, roll=0.05)
        await asyncio.sleep(0.3)

        # 3. Simultaneous three-axis virtual-stick control, then explicit stop.
        await gimbal.setVelocity(pan=-0.10, tilt=-0.06, roll=-0.03)
        await asyncio.sleep(0.5)
        await gimbal.stop()

        # 4. Approximate degrees/second. These are empirical conversions,
        #    not encoder/attitude feedback.
        await gimbal.setVelocityDeg(pan=5, tilt=2, roll=1)
        await asyncio.sleep(0.5)
        await gimbal.stop()

        # 5. DJI's three-axis recenter command.
        print("recentering all three axes...")
        await gimbal.recenter()
        await asyncio.sleep(2.0)
    finally:
        # Sends neutral frames before closing BLE, including after an exception.
        await gimbal.close()


if __name__ == "__main__":
    asyncio.run(main())
