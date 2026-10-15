#import "RSControlCore.h"
#include <math.h>

static uint8_t CRC8(const uint8_t *p, NSUInteger n) {
    uint8_t crc = 0x77;
    for (NSUInteger i = 0; i < n; i++) { crc ^= p[i]; for (int bit = 0; bit < 8; bit++) crc = crc & 1 ? (crc >> 1) ^ 0x8c : crc >> 1; }
    return crc;
}
static uint16_t CRC16(const uint8_t *p, NSUInteger n) {
    uint16_t crc = 0x3692;
    for (NSUInteger i = 0; i < n; i++) { crc ^= p[i]; for (int bit = 0; bit < 8; bit++) crc = crc & 1 ? (crc >> 1) ^ 0x8408 : crc >> 1; }
    return crc;
}
static void Put16(uint8_t *p, uint16_t value) { p[0] = value & 255; p[1] = value >> 8; }
static int16_t Get16(const uint8_t *p) { return (int16_t)(p[0] | ((uint16_t)p[1] << 8)); }
static NSData *CommandFrame(uint16_t seq, uint8_t commandSet, uint8_t command, NSData *payload, uint8_t flags) {
    NSMutableData *data = [NSMutableData dataWithLength:13 + payload.length];
    uint8_t *p = data.mutableBytes;
    p[0] = 0x55; p[1] = data.length & 255; p[2] = 0x04 | ((data.length >> 8) & 3); p[3] = CRC8(p, 3);
    p[4] = 2; p[5] = 4; Put16(p + 6, seq); p[8] = flags; p[9] = commandSet; p[10] = command;
    memcpy(p + 11, payload.bytes, payload.length); Put16(p + data.length - 2, CRC16(p, data.length - 2));
    return data;
}
static NSData *Frame(uint16_t seq, uint8_t command, NSData *payload, uint8_t flags) { return CommandFrame(seq, 4, command, payload, flags); }
static BOOL Numeric(id value) { return [value isKindOfClass:NSNumber.class] && CFGetTypeID((__bridge CFTypeRef)value) != CFBooleanGetTypeID() && isfinite([value doubleValue]); }
static NSString *Hex(NSData *data) { NSMutableString *text = [NSMutableString string]; for (NSUInteger i = 0; i < data.length; i++) [text appendFormat:@"%02x", ((const uint8_t *)data.bytes)[i]]; return text; }
NSData *RSVelocityFrame(uint16_t sequence, double pan, double tilt, double roll) {
    if (!isfinite(pan) || !isfinite(tilt) || !isfinite(roll)) return nil;
    uint8_t p[9] = {0}; double inputs[] = {tilt, roll, pan};
    for (int i = 0; i < 3; i++) Put16(p + i * 2, (uint16_t)(1024 + floor(fmax(-1, fmin(1, inputs[i])) * 660 + 0.5)));
    p[8] = 2;
    return Frame(sequence, 1, [NSData dataWithBytes:p length:9], 0);
}
NSData *RSRecenterFrame(uint16_t sequence) {
    const uint8_t p[] = {0xfe, 1}; return Frame(sequence, 0x4c, [NSData dataWithBytes:p length:2], 0x40);
}
NSDictionary *RSDecodeTelemetry(NSData *payload) {
    if (payload.length < 6) return nil;
    const uint8_t *p = payload.bytes;
    NSMutableDictionary *result = [@{@"attitude": @{@"pitch": @(Get16(p) / 10.0), @"roll": @(Get16(p + 2) / 10.0), @"yaw": @(Get16(p + 4) / 10.0)}} mutableCopy];
    if (payload.length >= 24) result[@"jointAngles"] = @{@"pitch": @(Get16(p + 20) / 10.0), @"roll": @(Get16(p + 22) / 10.0), @"yaw": @(Get16(p + 16) / 100.0)};
    if (payload.length >= 40) {
        NSMutableArray *values = [NSMutableArray array]; double norm = 0;
        for (NSUInteger i = 0; i < 4; i++) { uint32_t bits = (uint32_t)p[24 + i * 4] | ((uint32_t)p[25 + i * 4] << 8) | ((uint32_t)p[26 + i * 4] << 16) | ((uint32_t)p[27 + i * 4] << 24); float value; memcpy(&value, &bits, 4); [values addObject:@(value)]; norm = hypot(norm, value); }
        result[@"orientationQuaternion"] = @{@"components": values, @"norm": @(norm), @"componentOrder": @"unverified"};
    }
    return result;
}
NSDictionary *RSOrientation(NSArray *components, NSString *order, BOOL conjugate) {
    if (![components isKindOfClass:NSArray.class] || components.count != 4 || ![@[@"wxyz", @"xyzw"] containsObject:order]) return nil;
    double values[4], norm = 0;
    for (NSUInteger i = 0; i < 4; i++) { if (!Numeric(components[i])) return nil; values[i] = [components[i] doubleValue]; norm = hypot(norm, values[i]); }
    if (!isfinite(norm) || norm < 1e-12) return nil;
    double w = values[[order isEqualToString:@"wxyz"] ? 0 : 3] / norm;
    double x = values[[order isEqualToString:@"wxyz"] ? 1 : 0] / norm, y = values[[order isEqualToString:@"wxyz"] ? 2 : 1] / norm, z = values[[order isEqualToString:@"wxyz"] ? 3 : 2] / norm;
    if (conjugate) { x = -x; y = -y; z = -z; }
    double toDeg = 180 / M_PI;
    return @{@"quaternion": @{@"w": @(w), @"x": @(x), @"y": @(y), @"z": @(z)}, @"inputNorm": @(norm),
        @"euler": @{@"roll": @(atan2(2 * (w*x + y*z), 1 - 2*(x*x+y*y)) * toDeg), @"pitch": @(asin(fmax(-1,fmin(1,2*(w*y-z*x)))) * toDeg), @"yaw": @(atan2(2*(w*z+x*y),1-2*(y*y+z*z)) * toDeg)},
        @"componentOrder": order, @"conjugate": @(conjugate), @"convention": @"right-handed-intrinsic-ZYX", @"deviceConventionVerified": @NO};
}
NSData *RSResearchAbsoluteFrame(uint16_t sequence, NSDictionary *targets, NSUInteger parameter) {
    if (![targets isKindOfClass:NSDictionary.class] || !targets.count || parameter > 255) return nil;
    for (NSString *key in targets) if (![@[@"pan", @"roll", @"tilt"] containsObject:key]) return nil;
    uint8_t payload[8] = {0}; payload[6] = 1; payload[7] = parameter;
    NSArray *axes = @[@"pan", @"roll", @"tilt"];
    for (NSUInteger i = 0; i < 3; i++) {
        id value = targets[axes[i]];
        if (!value) payload[6] |= (2 << i);
        else { if (!Numeric(value) || fabs([value doubleValue]) > 180) return nil; Put16(payload + i * 2, (uint16_t)(int16_t)floor([value doubleValue] * 10 + .5)); }
    }
    return Frame(sequence, 0x14, [NSData dataWithBytes:payload length:8], 0x40);
}
NSData *RSResearchRateFrame(uint16_t sequence, NSDictionary *rates, BOOL release) {
    if (![rates isKindOfClass:NSDictionary.class]) return nil;
    for (NSString *key in rates) if (![@[@"pan", @"roll", @"tilt"] containsObject:key]) return nil;
    uint8_t payload[7] = {0}; payload[6] = release ? 0 : 0x80; NSArray *axes = @[@"pan", @"roll", @"tilt"];
    for (NSUInteger i = 0; i < 3; i++) { id value = rates[axes[i]] ?: @0; if (!Numeric(value) || fabs([value doubleValue]) > 360) return nil; Put16(payload + i * 2, (uint16_t)(int16_t)floor([value doubleValue] * 10 + .5)); }
    return Frame(sequence, 0x0c, [NSData dataWithBytes:payload length:7], 0x40);
}
NSData *RSResearchSleepFrame(uint16_t sequence, NSString *profile, BOOL asleep) {
    if (![@[@"rs3", @"rs3mini"] containsObject:profile]) return nil;
    uint8_t payload[] = {0x23, 1, ([profile isEqualToString:@"rs3mini"] ? 0x10 : 0) | asleep};
    return Frame(sequence, 0x0f, [NSData dataWithBytes:payload length:3], 0x40);
}
NSData *RSResearchQueryFrame(uint16_t sequence, NSString *kind) {
    if (![kind isKindOfClass:NSString.class]) return nil;
    NSDictionary *ids = @{@"version": @1, @"position": @2, @"controlStatus": @0x0b, @"type": @0x1c};
    if (!ids[kind]) return nil;
    return CommandFrame(sequence, [kind isEqualToString:@"version"] ? 0 : 4, [ids[kind] unsignedCharValue], [NSData data], 0x40);
}
NSDictionary *RSDecodeResearchStatus(NSDictionary *message, NSString *profile) {
    if (![@[@"rs3", @"rs3mini"] containsObject:profile] || [message[@"receiver"] intValue] != 2) return nil;
    NSData *payload = message[@"payload"]; if (![payload isKindOfClass:NSData.class]) return nil;
    const uint8_t *p = payload.bytes; NSUInteger n = payload.length;
    NSMutableDictionary *result = [@{@"profile": profile, @"deviceVerified": @NO, @"payloadHex": Hex(payload)} mutableCopy];
    int set = [message[@"commandSet"] intValue], cmd = [message[@"commandId"] intValue], sender = [message[@"sender"] intValue];
    if (sender == 4 && set == 4 && cmd == 0x27 && n == 5 && p[0] == 0 && p[1] == 0 && p[2] == 0 && p[3] == 0 && p[4] <= 1) { result[@"kind"] = @"sleep"; result[@"asleep"] = @(p[4] == 1); }
    else if (sender == 4 && set == 4 && cmd == 0x0f && n == 4 && p[0] == 0 && p[1] == 0x23 && p[2] == 1 && (p[3] == ([profile isEqualToString:@"rs3mini"] ? 0x10 : 0) || p[3] == ([profile isEqualToString:@"rs3mini"] ? 0x11 : 1))) { result[@"kind"] = @"sleep"; result[@"asleep"] = @((p[3] & 1) != 0); }
    else if (sender == 4 && set == 4 && cmd == 0x30 && n == 2 && p[0] <= 100 && p[1] <= 1) { result[@"kind"] = @"calibration"; result[@"percent"] = @(p[0]); result[@"inProgress"] = @(p[1] != 0); }
    else if (sender == 0xe5 && set == 0x0d && cmd == 2 && n >= 17) {
        NSMutableArray *values = [NSMutableArray array];
        for (NSUInteger i = 1; i <= 13; i += 4) [values addObject:@((int32_t)((uint32_t)p[i] | ((uint32_t)p[i+1] << 8) | ((uint32_t)p[i+2] << 16) | ((uint32_t)p[i+3] << 24)))];
        result[@"kind"] = @"battery-status"; result[@"rawFields"] = values;
        result[@"batteryPercent"] = [profile isEqualToString:@"rs3mini"] && n == 21 && p[20] <= 100 ? @(p[20]) : NSNull.null;
    } else if (sender == 0xe5 && set == 4 && cmd == 0x66 && n) {
        NSMutableArray *fields = [NSMutableArray array]; NSUInteger offset = 1;
        while (offset < n) {
            if (offset + 2 > n) return nil; uint8_t tag = p[offset++], size = p[offset++];
            if (!size || offset + size > n) return nil;
            [fields addObject:@{@"tag": @(tag), @"size": @(size), @"rawHex": Hex([payload subdataWithRange:NSMakeRange(offset, size)])}]; offset += size;
        }
        result[@"kind"] = @"status-tlv"; result[@"header"] = @(p[0]); result[@"fields"] = fields;
    } else return nil;
    return [result copy];
}

@implementation RSFrameDecoder {
    NSMutableData *_buffer;
    NSUInteger _invalidFrames, _discardedBytes;
}
- (instancetype)init { if ((self = [super init])) [self reset]; return self; }
- (void)reset { _buffer = [NSMutableData data]; _invalidFrames = _discardedBytes = 0; }
- (NSUInteger)invalidFrames { return _invalidFrames; }
- (NSUInteger)discardedBytes { return _discardedBytes; }
- (NSArray<NSDictionary *> *)push:(NSData *)data {
    [_buffer appendData:data];
    if (_buffer.length > 8192) { _discardedBytes += _buffer.length; [_buffer setLength:0]; }
    NSMutableArray *messages = [NSMutableArray array];
    while (_buffer.length) {
        const uint8_t *p = _buffer.bytes;
        NSUInteger start = 0;
        while (start < _buffer.length && p[start] != 0x55) start++;
        if (start) { _discardedBytes += start; [_buffer replaceBytesInRange:NSMakeRange(0, start) withBytes:NULL length:0]; continue; }
        if (_buffer.length < 4) break;
        NSUInteger length = p[1] | ((p[2] & 3) << 8);
        if (length < 13 || length > 1023 || CRC8(p, 3) != p[3]) {
            _invalidFrames++; _discardedBytes++; [_buffer replaceBytesInRange:NSMakeRange(0, 1) withBytes:NULL length:0]; continue;
        }
        if (_buffer.length < length) break;
        if (CRC16(p, length - 2) != (uint16_t)(p[length - 2] | ((uint16_t)p[length - 1] << 8))) {
            _invalidFrames++; _discardedBytes++; [_buffer replaceBytesInRange:NSMakeRange(0, 1) withBytes:NULL length:0]; continue;
        }
        [messages addObject:@{@"sender": @(p[4]), @"receiver": @(p[5]), @"sequence": @((uint16_t)(p[6] | ((uint16_t)p[7] << 8))), @"flags": @(p[8]), @"commandSet": @(p[9]), @"commandId": @(p[10]), @"payload": [_buffer subdataWithRange:NSMakeRange(11, length - 13)]}];
        [_buffer replaceBytesInRange:NSMakeRange(0, length) withBytes:NULL length:0];
    }
    return messages;
}
@end

@implementation RSFrameQueue {
    NSMutableArray<NSData *> *_pending;
    NSData *_current;
    NSUInteger _offset;
}
- (instancetype)init { if ((self = [super init])) [self reset]; return self; }
- (BOOL)empty { return !_current && !_pending.count; }
- (void)enqueue:(NSData *)frame { if (frame.length) [_pending addObject:frame]; }
- (NSData *)nextChunk {
    if (!_current && _pending.count) { _current = _pending.firstObject; [_pending removeObjectAtIndex:0]; _offset = 0; }
    if (!_current) return nil;
    NSUInteger count = MIN((NSUInteger)20, _current.length - _offset);
    NSData *chunk = [_current subdataWithRange:NSMakeRange(_offset, count)]; _offset += count;
    if (_offset == _current.length) { _current = nil; _offset = 0; }
    return chunk;
}
- (void)discardPending { [_pending removeAllObjects]; }
- (void)reset { _pending = [NSMutableArray array]; _current = nil; _offset = 0; }
@end

@implementation RSPositionLoop {
    NSDictionary *_targets, *_current, *_velocity;
    NSTimeInterval _started, _feedbackAt;
    BOOL _active;
}
- (BOOL)active { return _active; }
- (NSDictionary *)velocity { return _velocity ?: @{@"pan": @0, @"tilt": @0, @"roll": @0}; }
- (NSDictionary *)current { return _current; }
- (BOOL)begin:(NSDictionary *)targets at:(NSTimeInterval)now error:(NSError **)error {
    BOOL valid = targets.count > 0 && !_active;
    for (NSString *key in targets) {
        id value = targets[key];
        if (![@[@"pan", @"tilt", @"roll"] containsObject:key] || ![value isKindOfClass:NSNumber.class] || !isfinite([value doubleValue]) || fabs([value doubleValue]) > 180) valid = NO;
    }
    if (!valid) { if (error) *error = [NSError errorWithDomain:@"RS4Mini" code:1 userInfo:@{NSLocalizedDescriptionKey: @"目标角度无效或定位已在运行"}]; return NO; }
    _targets = [targets copy]; _started = now; _feedbackAt = now; _current = nil; _velocity = nil; _active = YES;
    return YES;
}
- (void)feedback:(NSDictionary *)joints at:(NSTimeInterval)now {
    if (!_active) return;
    for (NSString *axis in @[@"pitch", @"roll", @"yaw"]) if (![joints[axis] isKindOfClass:NSNumber.class] || !isfinite([joints[axis] doubleValue])) return;
    _current = [joints copy]; _feedbackAt = now;
}
- (NSString *)step:(NSTimeInterval)now {
    if (!_active) return @"idle";
    if (now - _started >= 30) { [self cancel]; return @"timeout"; }
    if (now - _feedbackAt >= 3) { [self cancel]; return @"telemetryTimeout"; }
    if (!_current) return @"waiting";
    NSMutableDictionary *velocity = [NSMutableDictionary dictionary];
    NSDictionary *mapping = @{@"pan": @"yaw", @"tilt": @"pitch", @"roll": @"roll"};
    BOOL arrived = YES;
    for (NSString *axis in @[@"pan", @"tilt", @"roll"]) {
        double error = _targets[axis] ? [_targets[axis] doubleValue] - [_current[mapping[axis]] doubleValue] : 0;
        if ([axis isEqualToString:@"pan"]) error = fmod(error + 540, 360) - 180;
        double speed = 0;
        if (fabs(error) > 1) { arrived = NO; speed = copysign(fmin(0.18, fmax(0.05, fabs(error) * 0.02)), error); }
        velocity[axis] = @([axis isEqualToString:@"tilt"] ? -speed : speed);
    }
    _velocity = velocity;
    if (arrived) { _active = NO; return @"arrived"; }
    return @"moving";
}
- (void)cancel { _active = NO; _velocity = nil; }
@end

@implementation RSTrajectoryLoop {
    NSArray *_points;
    NSString *_interpolation;
    NSDictionary *_velocity;
    NSTimeInterval _started, _lastStep;
    BOOL _active;
}
- (BOOL)active { return _active; }
- (NSDictionary *)velocity { return _velocity ?: @{@"pan": @0, @"tilt": @0, @"roll": @0}; }
- (BOOL)begin:(NSArray *)keyframes interpolation:(NSString *)interpolation at:(NSTimeInterval)now error:(NSError **)error {
    BOOL valid = !_active && [keyframes isKindOfClass:NSArray.class] && keyframes.count >= 2 && isfinite(now) &&
        [@[@"linear", @"smoothstep", @"step"] containsObject:interpolation];
    NSMutableArray *points = [NSMutableArray array]; double previous = -1;
    if (valid) for (id point in keyframes) {
        if (![point isKindOfClass:NSDictionary.class]) { valid = NO; break; }
        id stamp = point[@"timeMs"];
        if (![stamp isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)stamp) == CFBooleanGetTypeID() ||
            !isfinite([stamp doubleValue]) || [stamp doubleValue] <= previous || [stamp doubleValue] > 2147483647 ||
            (!points.count && [stamp doubleValue] != 0)) { valid = NO; break; }
        NSMutableDictionary *copy = [NSMutableDictionary dictionary]; copy[@"timeMs"] = @([stamp doubleValue]); previous = [stamp doubleValue];
        for (NSString *key in point) if (![@[@"timeMs", @"pan", @"tilt", @"roll"] containsObject:key]) valid = NO;
        for (NSString *axis in @[@"pan", @"tilt", @"roll"]) {
            id value = point[axis] ?: @0;
            if (![value isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)value) == CFBooleanGetTypeID() ||
                !isfinite([value doubleValue]) || fabs([value doubleValue]) > 1) { valid = NO; break; }
            copy[axis] = @([value doubleValue]);
        }
        [points addObject:[copy copy]];
    }
    if (!valid) { if (error) *error = [NSError errorWithDomain:@"RS4Mini" code:2 userInfo:@{NSLocalizedDescriptionKey: @"轨迹需至少两个严格递增、从零开始的 timeMs 关键帧，各轴值为 -1 到 1"}]; return NO; }
    _points = [points copy]; _interpolation = [interpolation copy]; _started = _lastStep = now; _velocity = nil; _active = YES; return YES;
}
- (NSString *)step:(NSTimeInterval)now {
    if (!_active) return @"idle";
    if (!isfinite(now) || now - _lastStep > .5 || now < _started) { [self cancel]; return @"overrun"; }
    _lastStep = now; double elapsed = (now - _started) * 1000;
    if (elapsed >= [_points.lastObject[@"timeMs"] doubleValue]) { [self cancel]; return @"done"; }
    NSUInteger index = 0;
    while (index < _points.count - 2 && [_points[index + 1][@"timeMs"] doubleValue] <= elapsed) index++;
    NSDictionary *a = _points[index], *b = _points[index + 1];
    double ratio = fmax(0, fmin(1, (elapsed - [a[@"timeMs"] doubleValue]) / ([b[@"timeMs"] doubleValue] - [a[@"timeMs"] doubleValue])));
    if ([_interpolation isEqualToString:@"step"]) ratio = 0;
    else if ([_interpolation isEqualToString:@"smoothstep"]) ratio = ratio * ratio * (3 - 2 * ratio);
    NSMutableDictionary *values = [NSMutableDictionary dictionary];
    for (NSString *axis in @[@"pan", @"tilt", @"roll"]) values[axis] = @([a[axis] doubleValue] + ([b[axis] doubleValue] - [a[axis] doubleValue]) * ratio);
    _velocity = [values copy]; return @"moving";
}
- (void)cancel { _active = NO; _velocity = nil; }
@end
