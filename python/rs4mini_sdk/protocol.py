"""Pure DJI RS BLE framing helpers (no Bluetooth dependency)."""

from __future__ import annotations

import struct

APP = 0x02
GIMBAL = 0x04
FLAG_NO_ACK = 0x00
FLAG_REQUEST = 0x40
RC_MID = 1024
RC_SPAN = 660


def crc8(data: bytes) -> int:
    value = 0x77
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = ((value >> 1) ^ 0x8C) if value & 1 else value >> 1
    return value & 0xFF


def crc16(data: bytes) -> int:
    value = 0x3692
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = ((value >> 1) ^ 0x8408) if value & 1 else value >> 1
    return value & 0xFFFF


def frame(
    sequence: int,
    command_set: int,
    command_id: int,
    payload: bytes = b"",
    *,
    receiver: int = GIMBAL,
    flags: int = FLAG_NO_ACK,
) -> bytes:
    total = 13 + len(payload)
    if total > 0x3FF:
        raise ValueError("DUML frame exceeds the 10-bit length field")
    packet = bytearray(total)
    packet[0] = 0x55
    packet[1] = total & 0xFF
    packet[2] = 0x04 | ((total >> 8) & 0x03)
    packet[3] = crc8(packet[:3])
    packet[4] = APP
    packet[5] = receiver & 0xFF
    struct.pack_into("<H", packet, 6, sequence & 0xFFFF)
    packet[8] = flags & 0xFF
    packet[9] = command_set & 0xFF
    packet[10] = command_id & 0xFF
    packet[11 : 11 + len(payload)] = payload
    struct.pack_into("<H", packet, total - 2, crc16(packet[:-2]))
    return bytes(packet)


def rc_units(value: float) -> int:
    normalized = max(-1.0, min(1.0, float(value)))
    return RC_MID + round(normalized * RC_SPAN)


def velocity_payload(pan: float, tilt: float, roll: float) -> bytes:
    """Three normalized axes, each in the inclusive range -1..+1."""
    return struct.pack(
        "<hhhhB",
        rc_units(tilt),
        rc_units(roll),
        rc_units(pan),
        0,
        0x02,  # virtual joystick source
    )


def velocity_frame(sequence: int, pan: float, tilt: float, roll: float) -> bytes:
    return frame(sequence, 0x04, 0x01, velocity_payload(pan, tilt, roll))


def stop_frame(sequence: int) -> bytes:
    return velocity_frame(sequence, 0.0, 0.0, 0.0)


def recenter_frame(sequence: int) -> bytes:
    return frame(sequence, 0x04, 0x4C, b"\xFE\x01", flags=FLAG_REQUEST)
