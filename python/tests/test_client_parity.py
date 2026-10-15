import asyncio
import unittest

from rs4mini_sdk import RS4Mini


class FakeClient:
    def __init__(self):
        self.is_connected = True
        self.writes = []

    async def write_gatt_char(self, characteristic, data, response=False):
        self.writes.append((characteristic, bytes(data), response))


class ClientParityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gimbal = RS4Mini(nameIncludes="DJI RS4 MINI", rateHz=1000)
        self.gimbal.client = FakeClient()

    async def asyncTearDown(self):
        self.gimbal.client.is_connected = False
        await self.gimbal.stop()

    async def test_camel_case_velocity_and_three_stop_frames(self):
        await self.gimbal.setVelocity(pan=0.1, tilt=-0.2, roll=0.03)
        self.assertTrue(self.gimbal.connected)
        self.assertGreaterEqual(len(self.gimbal.client.writes), 1)
        writes_before_stop = len(self.gimbal.client.writes)
        await self.gimbal.stop()
        # Each 22-byte DUML frame is split into 20-byte + 2-byte GATT writes.
        self.assertEqual(len(self.gimbal.client.writes) - writes_before_stop, 6)

    async def test_node_style_bounded_move(self):
        await self.gimbal.moveFor(durationMs=0, pan=0.1)
        self.assertGreaterEqual(len(self.gimbal.client.writes), 4)

    async def test_snake_case_aliases_share_the_same_state(self):
        self.gimbal.on_notification = lambda _packet: None
        self.assertIs(self.gimbal.on_notification, self.gimbal.onNotification)
        self.assertEqual(self.gimbal.rate_hz, self.gimbal.rateHz)
        await self.gimbal.set_velocity(pan=0.05)
        self.assertEqual(self.gimbal.velocity["pan"], 0.05)
        await self.gimbal.stop()


if __name__ == "__main__":
    unittest.main()
