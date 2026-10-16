#import "RSDeviceProtocol.h"
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
    NSDictionary *ids = @{@"version": @1, @"position": @2, @"controlStatus": @0x0b, @"type": @0x1c, @"degreeInfo": @0x1e};
    if (!ids[kind]) return nil;
    return CommandFrame(sequence, [kind isEqualToString:@"version"] ? 0 : 4, [ids[kind] unsignedCharValue], [NSData data], 0x40);
}
NSDictionary *RSDecodeResearchStatus(NSDictionary *message, NSString *profile) {
    if (![@[@"rs3", @"rs3mini"] containsObject:profile] || [message[@"receiver"] intValue] != 2) return nil;
    NSData *payload = message[@"payload"]; if (![payload isKindOfClass:NSData.class]) return nil;
    const uint8_t *p = payload.bytes; NSUInteger n = payload.length;
    NSMutableDictionary *result = [@{@"profile": profile, @"deviceVerified": @NO, @"payloadHex": Hex(payload)} mutableCopy];
    int set = [message[@"commandSet"] intValue], cmd = [message[@"commandId"] intValue], sender = [message[@"sender"] intValue];
    if (sender == 4 && set == 4 && ([message[@"flags"] intValue] & 0x80) && cmd == 0x10 && n) {
        NSMutableArray *parameters = [NSMutableArray array]; NSUInteger offset = 1;
        while (offset < n) {
            uint8_t index = p[offset++];
            if (index >= 0x80) { [parameters addObject:@{@"errorCode": @((int)index - 256)}]; continue; }
            if (offset >= n) return nil;
            uint8_t size = p[offset++];
            if (!(size == 1 || size == 2 || size == 4 || size == 8) || offset + size > n) return nil;
            [parameters addObject:@{@"index": @(index), @"size": @(size), @"rawHex": Hex([payload subdataWithRange:NSMakeRange(offset, size)])}]; offset += size;
        }
        result[@"kind"] = @"user-parameters"; result[@"layoutSource"] = @"legacy-duml"; result[@"statusCode"] = @(p[0]); result[@"parameters"] = parameters;
    } else if (sender == 4 && set == 4 && ([message[@"flags"] intValue] & 0x80) && cmd == 0x0f && n == 1) {
        result[@"kind"] = @"user-parameter-ack"; result[@"layoutSource"] = @"legacy-duml"; result[@"statusCode"] = @(p[0]);
    } else if (sender == 4 && set == 4 && cmd == 0x27 && n == 5 && p[0] == 0 && p[1] == 0 && p[2] == 0 && p[3] == 0 && p[4] <= 1) { result[@"kind"] = @"sleep"; result[@"asleep"] = @(p[4] == 1); }
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


NSArray<NSDictionary *> *RSAppParameterContext(NSArray *parameters) {
    if (![parameters isKindOfClass:NSArray.class] || !parameters.count || parameters.count > 64) return nil;
    NSMutableArray *result = [NSMutableArray array];
    for (id row in parameters) {
        if (![row isKindOfClass:NSDictionary.class] || [row count] != 2 || !row[@"index"] || !row[@"size"]) return nil;
        NSNumber *index = row[@"index"], *size = row[@"size"];
        if (!Numeric(index) || index.doubleValue != floor(index.doubleValue) || index.doubleValue < 0 || index.doubleValue > 255 ||
            !Numeric(size) || ![@[@1, @2, @4, @8] containsObject:size]) return nil;
        [result addObject:@{@"index": @(index.unsignedIntegerValue), @"size": @(size.unsignedIntegerValue)}];
    }
    return [result copy];
}
NSData *RSAppParameterRequestFrame(uint16_t sequence, NSArray *parameters) {
    NSArray *context = RSAppParameterContext(parameters); if (!context) return nil;
    NSMutableData *data = [NSMutableData dataWithCapacity:context.count];
    for (NSDictionary *row in context) { uint8_t index = [row[@"index"] unsignedCharValue]; [data appendBytes:&index length:1]; }
    return Frame(sequence, 0x10, data, 0x40);
}
NSData *RSAppSensitivityFrame(uint16_t sequence, NSNumber *mode) {
    if (!Numeric(mode)) return nil;
    if (![@[@0, @1] containsObject:mode]) return nil;
    uint8_t data[] = {150, 1, mode.unsignedCharValue};
    return Frame(sequence, 0x0f, [NSData dataWithBytes:data length:3], 0x40);
}
NSError *RSAppError(NSString *code, NSString *message, NSNumber *statusCode) {
    NSMutableDictionary *info = [@{@"code": code, NSLocalizedDescriptionKey: message} mutableCopy];
    if (statusCode) info[@"statusCode"] = statusCode;
    return [NSError errorWithDomain:@"RS4MiniSDK" code:statusCode ? statusCode.integerValue : -1 userInfo:info];
}
NSDictionary *RSDecodeAppReply(NSDictionary *message, uint8_t command, NSArray *parameters, NSError **error) {
    NSData *payload = message[@"payload"];
    if ([message[@"sender"] intValue] != 4 || [message[@"receiver"] intValue] != 2 || [message[@"commandSet"] intValue] != 4 ||
        [message[@"commandId"] intValue] != command || !([message[@"flags"] intValue] & 0x80) || ![payload isKindOfClass:NSData.class] || !payload.length) {
        if (error) *error = RSAppError(@"RS4MINI_PROTOCOL_ERROR", @"Expected correlated App response with status byte", nil); return nil;
    }
    const uint8_t *p = payload.bytes;
    if (p[0]) { if (error) *error = RSAppError(@"RS4MINI_DEVICE_ERROR", @"Device rejected App command", @(p[0])); return nil; }
    NSMutableDictionary *result = [@{@"profile": @"ronin-2.2.2", @"statusCode": @0, @"acknowledged": @YES,
        @"deviceVerified": @NO, @"physicalCompletionVerified": @NO, @"message": [message copy],
        @"bodyHex": Hex([payload subdataWithRange:NSMakeRange(1, payload.length - 1)])} mutableCopy];
    if (parameters) {
        NSArray *context = RSAppParameterContext(parameters); NSUInteger offset = 1;
        NSMutableArray *records = [NSMutableArray array];
        if (!context) { if (error) *error = RSAppError(@"RS4MINI_PROTOCOL_ERROR", @"Invalid parameter context", nil); return nil; }
        for (NSDictionary *row in context) {
            NSUInteger size = [row[@"size"] unsignedIntegerValue];
            if (offset + 2 + size > payload.length || p[offset] != [row[@"index"] unsignedCharValue]) {
                if (error) *error = RSAppError(@"RS4MINI_PROTOCOL_ERROR", @"Parameter response does not match request context", nil); return nil;
            }
            [records addObject:@{@"index": row[@"index"], @"size": row[@"size"], @"headerByte": @(p[offset + 1]),
                @"rawHex": Hex([payload subdataWithRange:NSMakeRange(offset + 2, size)])}];
            offset += 2 + size;
        }
        if (offset != payload.length) { if (error) *error = RSAppError(@"RS4MINI_PROTOCOL_ERROR", @"Unconsumed parameter response bytes", nil); return nil; }
        result[@"parameters"] = [records copy];
    }
    return [result copy];
}

NSDictionary *RSAppSettingsSchema(NSString *kind) {
    if ([kind isEqualToString:@"customFollow"]) return @{@"index": @132, @"max": @15, @"mask": @15, @"fields": @{@"enabled": @1, @"pitch": @2, @"roll": @4, @"yaw": @8}};
    if ([kind isEqualToString:@"motor"]) return @{@"index": @35, @"max": @255, @"mask": @113, @"fields": @{@"enabled": @1, @"forbidSelfie": @16, @"forbidVertical": @32, @"roll360": @64}};
    return nil;
}
NSDictionary *RSAppSettingsPatch(NSString *kind, NSDictionary *patch) {
    NSDictionary *schema = RSAppSettingsSchema(kind);
    if (!schema || ![patch isKindOfClass:NSDictionary.class] || !patch.count) return nil;
    NSMutableDictionary *result = [NSMutableDictionary dictionary];
    for (id key in patch) {
        id value = patch[key];
        if (![key isKindOfClass:NSString.class] || !schema[@"fields"][key] || ![value isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)value) != CFBooleanGetTypeID()) return nil;
        result[key] = value;
    }
    return [result copy];
}
NSDictionary *RSDecodeAppSettings(NSDictionary *reply, NSString *kind) {
    NSDictionary *schema = RSAppSettingsSchema(kind); if (!schema) return nil;
    unsigned int raw = 0; [[NSScanner scannerWithString:reply[@"parameters"][0][@"rawHex"]] scanHexInt:&raw];
    NSMutableDictionary *settings = [NSMutableDictionary dictionary];
    for (NSString *key in schema[@"fields"]) {
        BOOL enabled = (raw & [schema[@"fields"][key] intValue]) != 0;
        settings[key] = @([kind isEqualToString:@"motor"] && [key isEqualToString:@"enabled"] ? !enabled : enabled);
    }
    NSMutableDictionary *result = [reply mutableCopy]; result[@"settings"] = [settings copy]; result[@"rawValue"] = @(raw);
    result[@"unknownBits"] = @(raw & (255 ^ [schema[@"mask"] intValue])); return [result copy];
}
NSData *RSAppSettingsFrame(uint16_t sequence, NSString *kind, NSDictionary *patch, NSNumber *currentValue) {
    NSDictionary *schema = RSAppSettingsSchema(kind); patch = RSAppSettingsPatch(kind, patch);
    if (!patch || !Numeric(currentValue) || floor(currentValue.doubleValue) != currentValue.doubleValue || currentValue.doubleValue < 0 || currentValue.doubleValue > [schema[@"max"] intValue]) return nil;
    int value = currentValue.intValue;
    for (NSString *key in patch) {
        int bit = [schema[@"fields"][key] intValue]; BOOL enabled = [patch[key] boolValue];
        if ([kind isEqualToString:@"motor"] && [key isEqualToString:@"enabled"]) enabled = !enabled;
        value = enabled ? value | bit : value & (255 ^ bit);
    }
    uint8_t payload[] = {[schema[@"index"] unsignedCharValue], 1, value};
    return CommandFrame(sequence, 4, 0x0f, [NSData dataWithBytes:payload length:3], 0x40);
}

NSData *RSAppAutoTuneFrame(uint16_t sequence, NSNumber *start) {
    if (![start isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)start) != CFBooleanGetTypeID()) return nil;
    uint8_t payload[] = {0, 1, start.boolValue};
    return CommandFrame(sequence, 4, 0x6a, [NSData dataWithBytes:payload length:3], 0);
}
NSData *RSAppCalibrationQueryFrame(uint16_t sequence) {
    return CommandFrame(sequence, 4, 0x6e, [NSData data], 0x40);
}
NSDictionary *RSDecodeAppCalibrationRecords(NSData *body) {
    if (![body isKindOfClass:NSData.class]) return nil;
    const uint8_t *p = body.bytes; NSUInteger offset = 0;
    if (body.length && p[0] != 0 && p[0] != 1) return nil;
    NSMutableArray *records = [NSMutableArray array]; id rawState = NSNull.null, rawPercent = NSNull.null;
    while (offset < body.length) {
        if (offset + 2 > body.length) return nil;
        uint8_t tag = p[offset++], size = p[offset++];
        if (size > 127 || offset + size > body.length || (tag == 0 && size < 2)) return nil;
        [records addObject:@{@"tag": @(tag), @"size": @(size), @"rawHex": [Hex([body subdataWithRange:NSMakeRange(offset,size)]) copy]}];
        if (tag == 0) { rawState = @(p[offset]); rawPercent = @(p[offset+1]); }
        offset += size;
    }
    NSDictionary *states = @{@0: @"UnStart", @1: @"Processing", @2: @"Complete", @3: @"Failure", @255: @"UnKnown"};
    return @{@"records": [records copy], @"rawState": rawState, @"state": states[rawState] ?: NSNull.null,
             @"rawPercent": rawPercent, @"percent": rawPercent != NSNull.null && [rawPercent intValue] <= 100 ? rawPercent : NSNull.null,
             @"bodyHex": [Hex(body) copy]};
}
NSDictionary *RSDecodeAppCalibrationReply(NSDictionary *message, NSError **error) {
    NSDictionary *reply = RSDecodeAppReply(message, 0x6e, nil, error); if (!reply) return nil;
    NSData *payload = message[@"payload"];
    NSDictionary *calibration = RSDecodeAppCalibrationRecords([payload subdataWithRange:NSMakeRange(1, payload.length-1)]);
    if (!calibration) { if (error) *error = RSAppError(@"RS4MINI_PROTOCOL_ERROR", @"Malformed current-App calibration records", nil); return nil; }
    NSMutableDictionary *result = [reply mutableCopy]; result[@"calibration"] = calibration; return [result copy];
}
NSDictionary *RSDecodeAppCalibrationNotification(NSDictionary *message) {
    if ([message[@"sender"] intValue] != 4 || [message[@"receiver"] intValue] != 2 || [message[@"commandSet"] intValue] != 4 || [message[@"commandId"] intValue] != 0x6e || ([message[@"flags"] intValue] & 0x80)) return nil;
    NSDictionary *calibration = RSDecodeAppCalibrationRecords(message[@"payload"]);
    if (!calibration || calibration[@"rawState"] == NSNull.null) return nil;
    NSMutableDictionary *result = [calibration mutableCopy];
    [result addEntriesFromDictionary:@{@"kind": @"calibration", @"profile": @"ronin-2.2.2", @"deviceVerified": @NO,
        @"physicalCompletionVerified": @NO, @"timestamp": @(NSDate.date.timeIntervalSince1970*1000)}];
    return [result copy];
}

NSArray<NSDictionary *> *RSAppMotorSelection(NSDictionary *filters) {
    filters = filters ?: @{};
    if (![filters isKindOfClass:NSDictionary.class]) return nil;
    for (id key in filters) if (![@[@"axis",@"parameter"] containsObject:key]) return nil;
    NSArray *axes = @[@"pitch",@"roll",@"yaw"], *parameters = @[@"stiffness",@"strength",@"gyroFiltering",@"preControl"], *minimums = @[@5,@1,@0,@0];
    if ((filters[@"axis"] && ![axes containsObject:filters[@"axis"]]) || (filters[@"parameter"] && ![parameters containsObject:filters[@"parameter"]])) return nil;
    NSMutableArray *result = [NSMutableArray array];
    for (NSUInteger g=0;g<4;g++) for (NSUInteger a=0;a<3;a++) {
        if ((filters[@"axis"] && ![filters[@"axis"] isEqual:axes[a]]) || (filters[@"parameter"] && ![filters[@"parameter"] isEqual:parameters[g]])) continue;
        [result addObject:@{@"axis":axes[a],@"parameter":parameters[g],@"index":@(g*3+a),@"size":@1,@"min":minimums[g],@"max":@100}];
    }
    return [result copy];
}
NSDictionary *RSAppMotorWriteSpec(NSDictionary *spec) {
    if (![spec isKindOfClass:NSDictionary.class] || spec.count!=3 || !spec[@"axis"] || !spec[@"parameter"] || !spec[@"value"]) return nil;
    NSArray *selected=RSAppMotorSelection(@{@"axis":spec[@"axis"],@"parameter":spec[@"parameter"]});
    if (selected.count!=1 || !Numeric(spec[@"value"])) return nil;
    double value=[spec[@"value"] doubleValue]; NSDictionary *row=selected[0];
    if (floor(value)!=value || value<[row[@"min"] intValue] || value>[row[@"max"] intValue]) return nil;
    NSMutableDictionary *result=[row mutableCopy]; result[@"value"]=@(value); return [result copy];
}
NSData *RSAppMotorReadFrame(uint16_t sequence, NSArray *context) {
    context=RSAppParameterContext(context);
    if (!context || context.count>12) return nil;
    NSMutableData *payload=[NSMutableData data];
    for (NSDictionary *row in context) {
        if ([row[@"index"] intValue]>11 || [row[@"size"] intValue]!=1) return nil;
        uint8_t index=[row[@"index"] unsignedCharValue]; [payload appendBytes:&index length:1];
    }
    return CommandFrame(sequence,4,0x32,payload,0x40);
}
NSData *RSAppMotorWriteFrame(uint16_t sequence, NSArray *context, NSNumber *value) {
    if (!RSAppMotorReadFrame(0,context) || context.count!=1) return nil;
    NSDictionary *row=RSAppMotorSelection(@{})[[context[0][@"index"] unsignedIntegerValue]];
    NSDictionary *spec=RSAppMotorWriteSpec(@{@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"value":value ?: NSNull.null});
    if (!spec) return nil;
    uint8_t payload[]={[row[@"index"] unsignedCharValue],1,[value unsignedCharValue]};
    return CommandFrame(sequence,4,0x31,[NSData dataWithBytes:payload length:3],0x40);
}
NSDictionary *RSDecodeAppMotorReply(NSDictionary *message, NSArray *selection, NSError **error) {
    NSMutableArray *context=[NSMutableArray array];
    for (NSDictionary *row in selection) [context addObject:@{@"index":row[@"index"],@"size":@1}];
    NSDictionary *reply=RSDecodeAppReply(message,0x32,context,error); if (!reply) return nil;
    NSMutableArray *values=[NSMutableArray array];
    for (NSUInteger i=0;i<selection.count;i++) {
        NSDictionary *row=selection[i], *record=reply[@"parameters"][i]; unsigned int raw=0;
        [[NSScanner scannerWithString:record[@"rawHex"]] scanHexInt:&raw];
        NSMutableDictionary *entry=[record mutableCopy];
        [entry addEntriesFromDictionary:@{@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"rawValue":@(raw),@"withinSourceRange":@(raw>=[row[@"min"] unsignedIntValue] && raw<=[row[@"max"] unsignedIntValue])}];
        [values addObject:[entry copy]];
    }
    NSMutableDictionary *result=[reply mutableCopy]; result[@"values"]=[values copy]; return [result copy];
}

NSData *RSAppBalanceStartFrame(uint16_t sequence) {
    uint8_t payload[]={37,1,64};
    return Frame(sequence,0x0f,[NSData dataWithBytes:payload length:3],0x40);
}
NSDictionary *RSAppBalanceFields(uint8_t rawValue) {
    NSUInteger stateCode=rawValue>>6;
    NSMutableDictionary *axes=[NSMutableDictionary dictionary];
    NSArray *names=@[@"roll",@"pitch",@"yaw"], *results=@[@"PASS",@"MARGINAL",@"FAIL"];
    BOOL valid=YES;
    for (NSUInteger i=0;i<3;i++) {
        NSUInteger value=(rawValue>>(4-2*i))&3;
        axes[names[i]]=@{@"rawValue":@(value),@"result":value?results[value-1]:NSNull.null};
        if (!value) valid=NO;
    }
    return @{@"rawValue":@(rawValue),@"stateCode":@(stateCode),@"state":@[@"DEFAULT",@"TESTING",@"FINISH",@"ERROR"][stateCode],@"axisResults":[axes copy],@"axisFieldsValid":@(valid)};
}
NSDictionary *RSDecodeAppBalanceReply(NSDictionary *reply) {
    NSArray *records=reply[@"parameters"];
    if (records.count!=1 || [records[0][@"index"] intValue]!=37 || [records[0][@"size"] intValue]!=1) return nil;
    unsigned value=0; NSScanner *scanner=[NSScanner scannerWithString:records[0][@"rawHex"]];
    if (![scanner scanHexInt:&value] || !scanner.isAtEnd || value>255) return nil;
    NSMutableDictionary *result=[reply mutableCopy];result[@"balance"]=RSAppBalanceFields((uint8_t)value);return [result copy];
}

NSData *RSAppSystemCalibrationStartFrame(uint16_t sequence) {
    uint8_t payload[]={36,1,1};return Frame(sequence,0x0f,[NSData dataWithBytes:payload length:3],0x40);
}
NSDictionary *RSAppSystemCalibrationFields(uint8_t rawValue) {
    return @{@"rawValue":@(rawValue),@"state":rawValue<4?@[@"DEFAULT",@"START",@"FAIL",@"SUCCESS"][rawValue]:NSNull.null};
}
NSDictionary *RSDecodeAppSystemCalibrationReply(NSDictionary *reply) {
    NSArray *records=reply[@"parameters"];
    if (records.count!=1 || [records[0][@"index"] intValue]!=36 || [records[0][@"size"] intValue]!=1) return nil;
    unsigned value=0;NSScanner *scanner=[NSScanner scannerWithString:records[0][@"rawHex"]];
    if (![scanner scanHexInt:&value] || !scanner.isAtEnd || value>255) return nil;
    NSMutableDictionary *result=[reply mutableCopy];result[@"systemCalibration"]=RSAppSystemCalibrationFields((uint8_t)value);return [result copy];
}
