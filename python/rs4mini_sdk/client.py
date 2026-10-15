"""Legacy Python controller matching the early Node 0.2.x control API."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable
from contextlib import suppress
from typing import Optional

from bleak import BleakClient, BleakScanner

from .protocol import recenter_frame, velocity_frame

SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY = "0000fff4-0000-1000-8000-00805f9b34fb"
WRITE = "0000fff5-0000-1000-8000-00805f9b34fb"


class RS4Mini:
    """Direct BLE controller matching the early Node 0.2.x control capabilities.

    The camelCase API follows the original Node naming. Snake_case aliases
    remain available for Python style and backward compatibility. Node 0.5.x
    adds telemetry, cached connections, close(), and moveTo(); those features
    are not implemented here yet.
    """

    def __init__(
        self,
        *,
        nameIncludes: str = "DJI RS4 MINI",
        rateHz: float = 15.0,
        name_contains: Optional[str] = None,
        rate_hz: Optional[float] = None,
    ):
        if name_contains is not None:
            nameIncludes = name_contains
        if rate_hz is not None:
            rateHz = rate_hz
        if not math.isfinite(rateHz) or rateHz <= 0:
            raise ValueError("rateHz must be greater than 0")

        self.nameIncludes = nameIncludes.upper()
        self.rateHz = float(rateHz)
        self.client: Optional[BleakClient] = None
        self.deviceName: Optional[str] = None
        self.deviceAddress: Optional[str] = None
        self.sequence = 0x0100
        self.velocity = {"pan": 0.0, "tilt": 0.0, "roll": 0.0}
        self._streamTask: Optional[asyncio.Task] = None
        self._streamGeneration = 0
        self._writeLock = asyncio.Lock()

        self.onNotification: Optional[Callable[[bytes], None]] = None
        self.onDisconnect: Optional[Callable[[], None]] = None
        self.onError: Optional[Callable[[Exception], None]] = None

    @property
    def connected(self) -> bool:
        return bool(self.client and self.client.is_connected)

    async def connect(
        self,
        timeout: Optional[float] = None,
        *,
        timeoutMs: Optional[float] = None,
    ) -> str:
        """Scan and connect.

        ``timeoutMs`` matches Node. ``timeout`` is the legacy Python value in
        seconds. Supplying both is an error.
        """
        if self.connected:
            return self.deviceName or self.deviceAddress or "DJI RS4 MINI"
        if timeout is not None and timeoutMs is not None:
            raise ValueError("use either timeout (seconds) or timeoutMs, not both")
        effective_ms = 30000.0 if timeout is None and timeoutMs is None else (
            float(timeoutMs) if timeoutMs is not None else float(timeout) * 1000.0
        )
        if not math.isfinite(effective_ms) or effective_ms <= 0:
            raise ValueError("timeoutMs must be greater than 0")

        def matches(device, advertisement) -> bool:
            name = (advertisement.local_name or device.name or "").upper()
            return self.nameIncludes in name

        device = await BleakScanner.find_device_by_filter(
            matches,
            timeout=effective_ms / 1000.0,
        )
        if device is None:
            raise TimeoutError(f"RS 4 Mini scan timed out after {effective_ms:g} ms")

        self.client = BleakClient(device, disconnected_callback=self._on_disconnect)
        self.deviceName = device.name or "DJI RS4 MINI"
        self.deviceAddress = device.address
        try:
            await self.client.connect()
            await self.client.start_notify(NOTIFY, self._notification)
            return self.deviceName
        except Exception:
            if self.client.is_connected:
                with suppress(Exception):
                    await self.client.disconnect()
            self.client = None
            self.deviceName = None
            self.deviceAddress = None
            raise

    async def setVelocity(
        self,
        *,
        pan: float = 0.0,
        tilt: float = 0.0,
        roll: float = 0.0,
    ) -> None:
        """Stream normalized virtual-stick velocities in the range -1..+1."""
        self._require_connected()
        self.velocity = {
            "pan": self._normalize_axis(pan, "pan"),
            "tilt": self._normalize_axis(tilt, "tilt"),
            "roll": self._normalize_axis(roll, "roll"),
        }
        if all(value == 0 for value in self.velocity.values()):
            await self.stop()
            return
        await self._enqueue(velocity_frame(self._next_sequence(), **self.velocity))
        self._start_stream()

    async def setVelocityDeg(
        self,
        *,
        pan: float = 0.0,
        tilt: float = 0.0,
        roll: float = 0.0,
        panFullScale: float = 37.5,
        tiltFullScale: float = 27.5,
        rollFullScale: float = 30.0,
    ) -> None:
        """Set approximate degrees/second using empirical full-scale values."""
        scales = {
            "panFullScale": panFullScale,
            "tiltFullScale": tiltFullScale,
            "rollFullScale": rollFullScale,
        }
        for name, value in scales.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be greater than 0")
        await self.setVelocity(
            pan=float(pan) / panFullScale,
            tilt=float(tilt) / tiltFullScale,
            roll=float(roll) / rollFullScale,
        )

    async def moveFor(
        self,
        *,
        durationMs: float,
        pan: float = 0.0,
        tilt: float = 0.0,
        roll: float = 0.0,
    ) -> None:
        """Move for a bounded duration and always send stop frames afterward."""
        if not math.isfinite(durationMs) or durationMs < 0:
            raise ValueError("durationMs must be a non-negative finite number")
        try:
            await self.setVelocity(pan=pan, tilt=tilt, roll=roll)
            await asyncio.sleep(durationMs / 1000.0)
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop streaming and send three independent all-axis neutral frames."""
        self.velocity = {"pan": 0.0, "tilt": 0.0, "roll": 0.0}
        await self._cancel_stream()
        if not self.connected:
            return
        for _ in range(3):
            await self._enqueue(velocity_frame(self._next_sequence(), 0, 0, 0))
            await asyncio.sleep(1 / self.rateHz)

    async def recenter(self) -> None:
        """Stop, then issue DJI's three-axis recenter command."""
        self._require_connected()
        await self.stop()
        await self._enqueue(recenter_frame(self._next_sequence()))

    async def disconnect(self) -> None:
        """Stop safely, unsubscribe, and disconnect."""
        self.velocity = {"pan": 0.0, "tilt": 0.0, "roll": 0.0}
        await self._cancel_stream()
        if not self.client:
            return
        if self.connected:
            await self.stop()
            with suppress(Exception):
                await self.client.stop_notify(NOTIFY)
            await self.client.disconnect()
        self.client = None
        self.deviceName = None
        self.deviceAddress = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    def _start_stream(self) -> None:
        if self._streamTask and not self._streamTask.done():
            return
        self._streamGeneration += 1
        generation = self._streamGeneration
        self._streamTask = asyncio.create_task(self._stream_velocity(generation))

    async def _stream_velocity(self, generation: int) -> None:
        current = asyncio.current_task()
        try:
            while self.connected and generation == self._streamGeneration:
                await asyncio.sleep(1 / self.rateHz)
                if not self.connected or generation != self._streamGeneration:
                    break
                if all(value == 0 for value in self.velocity.values()):
                    break
                await self._enqueue(velocity_frame(self._next_sequence(), **self.velocity))
        except Exception as error:
            if self.onError:
                self.onError(error)
        finally:
            if self._streamTask is current and generation == self._streamGeneration:
                self._streamTask = None

    async def _cancel_stream(self) -> None:
        self._streamGeneration += 1
        pending, self._streamTask = self._streamTask, None
        if pending:
            with suppress(asyncio.CancelledError):
                await pending

    async def _enqueue(self, packet: bytes) -> None:
        self._require_connected()
        async with self._writeLock:
            self._require_connected()
            assert self.client is not None
            for offset in range(0, len(packet), 20):
                await self.client.write_gatt_char(
                    WRITE,
                    packet[offset : offset + 20],
                    response=False,
                )

    def _next_sequence(self) -> int:
        current = self.sequence
        self.sequence = (self.sequence + 1) & 0xFFFF
        return current

    def _notification(self, _characteristic, data: bytearray) -> None:
        if self.onNotification:
            self.onNotification(bytes(data))

    def _on_disconnect(self, _client) -> None:
        self.velocity = {"pan": 0.0, "tilt": 0.0, "roll": 0.0}
        self._streamGeneration += 1
        self._streamTask = None
        if self.onDisconnect:
            self.onDisconnect()

    def _require_connected(self) -> None:
        if not self.connected:
            raise RuntimeError("RS 4 Mini is not connected")

    @staticmethod
    def _normalize_axis(value: float, name: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{name} must be a finite number")
        return max(-1.0, min(1.0, number))

    # Pythonic aliases. CamelCase above remains the source of truth.
    async def set_velocity(self, pan=0.0, tilt=0.0, roll=0.0) -> None:
        await self.setVelocity(pan=pan, tilt=tilt, roll=roll)

    async def set_velocity_deg(
        self,
        *,
        pan=0.0,
        tilt=0.0,
        roll=0.0,
        pan_full_scale=37.5,
        tilt_full_scale=27.5,
        roll_full_scale=30.0,
    ) -> None:
        await self.setVelocityDeg(
            pan=pan,
            tilt=tilt,
            roll=roll,
            panFullScale=pan_full_scale,
            tiltFullScale=tilt_full_scale,
            rollFullScale=roll_full_scale,
        )

    async def move_for(self, duration, *, pan=0.0, tilt=0.0, roll=0.0) -> None:
        await self.moveFor(
            durationMs=float(duration) * 1000.0,
            pan=pan,
            tilt=tilt,
            roll=roll,
        )

    @property
    def name_contains(self):
        return self.nameIncludes

    @property
    def rate_hz(self):
        return self.rateHz

    @property
    def device_name(self):
        return self.deviceName

    @property
    def device_address(self):
        return self.deviceAddress

    @property
    def on_notification(self):
        return self.onNotification

    @on_notification.setter
    def on_notification(self, callback):
        self.onNotification = callback

    @property
    def on_disconnect(self):
        return self.onDisconnect

    @on_disconnect.setter
    def on_disconnect(self, callback):
        self.onDisconnect = callback

    @property
    def on_error(self):
        return self.onError

    @on_error.setter
    def on_error(self, callback):
        self.onError = callback
