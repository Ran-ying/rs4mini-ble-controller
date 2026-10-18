"""DUML stream reassembly and verified RS 4 Mini feedback mappings."""
import math
import struct
import time
from .protocol import crc8, crc16


def parse_duml_frame(data):
    packet = bytes(data)
    if len(packet) < 13 or packet[0] != 0x55:
        raise ValueError('Invalid DUML header')
    length = packet[1] | ((packet[2] & 3) << 8)
    if length != len(packet) or crc8(packet[:3]) != packet[3]:
        raise ValueError('DUML length/CRC8 mismatch')
    if crc16(packet[:-2]) != struct.unpack_from('<H', packet, len(packet) - 2)[0]:
        raise ValueError('DUML CRC16 mismatch')
    return dict(raw=packet, length=length, sender=packet[4], receiver=packet[5],
                sequence=struct.unpack_from('<H', packet, 6)[0], flags=packet[8],
                commandSet=packet[9], commandId=packet[10], payload=packet[11:-2])


class DumlStreamDecoder:
    def __init__(self, maxBufferedBytes=8192):
        if not isinstance(maxBufferedBytes, int) or maxBufferedBytes < 13:
            raise ValueError('maxBufferedBytes must be an integer >= 13')
        self.maxBufferedBytes = maxBufferedBytes
        self.reset()

    def reset(self):
        self.buffer = b''
        self.invalidFrames = 0
        self.discardedBytes = 0

    def push(self, chunk):
        self.buffer += bytes(chunk)
        if len(self.buffer) > self.maxBufferedBytes:
            keep = max(0, self.buffer.rfind(b'\x55'))
            self.discardedBytes += keep
            self.buffer = self.buffer[keep:]
            if len(self.buffer) > self.maxBufferedBytes:
                self.discardedBytes += len(self.buffer)
                self.buffer = b''
        messages = []
        while self.buffer:
            start = self.buffer.find(b'\x55')
            if start < 0:
                self.discardedBytes += len(self.buffer)
                self.buffer = b''
                break
            self.discardedBytes += start
            self.buffer = self.buffer[start:]
            if len(self.buffer) < 4:
                break
            length = self.buffer[1] | ((self.buffer[2] & 3) << 8)
            if not 13 <= length <= 1023 or crc8(self.buffer[:3]) != self.buffer[3]:
                self.invalidFrames += 1
                self.discardedBytes += 1
                self.buffer = self.buffer[1:]
                continue
            if len(self.buffer) < length:
                break
            try:
                messages.append(parse_duml_frame(self.buffer[:length]))
                self.buffer = self.buffer[length:]
            except ValueError:
                self.invalidFrames += 1
                self.discardedBytes += 1
                self.buffer = self.buffer[1:]
        return messages


def decode_gimbal_telemetry(message):
    if not message or (message['commandSet'], message['commandId']) != (4, 5) or type(message.get('flags')) is not int or not 0<=message['flags']<=255 or message['flags']&0x87:
        return None
    data = message['payload']
    if len(data) < 6:
        return None
    def angles(offsets, scales):
        raw = {axis: struct.unpack_from('<h', data, offset)[0]
               for axis, offset in zip(('pitch', 'roll', 'yaw'), offsets)}
        return dict({axis: raw[axis] / scale for axis, scale in zip(('pitch', 'roll', 'yaw'), scales)}, unit='deg', raw=raw)
    attitude = angles((0, 2, 4), (10, 10, 10))
    attitude['wrap'] = 180
    joints = angles((20, 22, 16), (10, 10, 100)) if len(data) >= 24 else None
    quaternion = None
    if len(data) >= 40:
        components = list(struct.unpack_from('<ffff', data, 24))
        quaternion = dict(components=components, norm=math.sqrt(sum(value * value for value in components)), componentOrder='unverified')
    return dict(kind='gimbal-telemetry', verified=True, pitch=attitude['pitch'], roll=attitude['roll'], yaw=attitude['yaw'],
                raw=attitude['raw'], attitude=attitude, jointAngles=joints, orientationQuaternion=quaternion,
                modeFlags=data[6] if len(data) >= 7 else None,
                rollAdjust=struct.unpack_from('<b', data, 7)[0] if len(data) >= 8 else None,
                yawAngle=struct.unpack_from('<h', data, 8)[0] / 10 if len(data) >= 10 else None,
                limitFlags=data[10] if len(data) >= 11 else None, stateFlags=data[11] if len(data) >= 12 else None,
                payloadHex=data.hex(), sequence=message['sequence'], timestamp=message.get('receivedAt', int(time.time() * 1000)))
