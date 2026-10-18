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
    if (![@[@"rs3", @"rs3mini"] containsObject:profile] || [message[@"receiver"] intValue] != 2 || ![message[@"flags"] isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)message[@"flags"])==CFBooleanGetTypeID() || [message[@"flags"] doubleValue]!=floor([message[@"flags"] doubleValue]) || [message[@"flags"] doubleValue]<0 || [message[@"flags"] doubleValue]>255 || ([message[@"flags"] intValue]&7)) return nil;
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
static BOOL AppPlainFlags(id flags, BOOL ack) {
    return [flags isKindOfClass:NSNumber.class] && CFGetTypeID((__bridge CFTypeRef)flags)!=CFBooleanGetTypeID() && [flags doubleValue]==floor([flags doubleValue]) && [flags doubleValue]>=0 && [flags doubleValue]<=255 && !([flags intValue]&7) && ((([flags intValue]&128)!=0)==ack);
}
NSDictionary *RSDecodeAppReply(NSDictionary *message, uint8_t command, NSArray *parameters, NSError **error) {
    NSData *payload = message[@"payload"];
    if ([message[@"sender"] intValue] != 4 || [message[@"receiver"] intValue] != 2 || [message[@"commandSet"] intValue] != 4 ||
        [message[@"commandId"] intValue] != command || !AppPlainFlags(message[@"flags"],YES) || ![payload isKindOfClass:NSData.class] || !payload.length) {
        if (error) *error = RSAppError(@"RS4MINI_PROTOCOL_ERROR", @"Expected correlated unencrypted App response with status byte", nil); return nil;
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

NSString *RSAppModeKind(NSString *domain, NSString *parameter) {
    if (![domain isKindOfClass:NSString.class] || ![parameter isKindOfClass:NSString.class]) return nil;
    return @{@"follow":@{@"speed":@"followSpeed",@"acceleration":@"followAcceleration",@"deadZone":@"followDeadZone"},@"rc":@{@"speed":@"rcSpeed",@"deadZone":@"rcDeadZone",@"smoothing":@"rcSmoothing"}}[domain][parameter];
}
NSDictionary *RSAppSettingsSchema(NSString *kind) {
    if (![kind isKindOfClass:NSString.class]) return nil;
    NSNumber *index=@{@"followSpeed":@65,@"followAcceleration":@71,@"followDeadZone":@66,@"rcSpeed":@67,@"rcDeadZone":@68,@"rcSmoothing":@69}[kind];
    if (index) return @{@"index":index,@"max":@255,@"mask":@252,@"modes":@YES,@"fields":@{@"pitch":@2,@"roll":@4,@"yaw":@6}};
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
        if (![key isKindOfClass:NSString.class] || !schema[@"fields"][key]) return nil;
        if ([schema[@"modes"] boolValue]) {
            if (![@[@"custom",@"low",@"middle",@"high"] containsObject:value]) return nil;
        } else if (![value isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)value)!=CFBooleanGetTypeID()) return nil;
        result[key] = [value copy];
    }
    return [result copy];
}
NSDictionary *RSDecodeAppSettings(NSDictionary *reply, NSString *kind) {
    NSDictionary *schema = RSAppSettingsSchema(kind); if (!schema) return nil;
    unsigned int raw = 0; [[NSScanner scannerWithString:reply[@"parameters"][0][@"rawHex"]] scanHexInt:&raw];
    NSMutableDictionary *settings = [NSMutableDictionary dictionary];
    for (NSString *key in schema[@"fields"]) {
        if ([schema[@"modes"] boolValue]) {
            settings[key]=@[@"custom",@"low",@"middle",@"high"][(raw>>[schema[@"fields"][key] intValue])&3];continue;
        }
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
        if ([schema[@"modes"] boolValue]) {
            int shift=[schema[@"fields"][key] intValue],mode=(int)[@[@"custom",@"low",@"middle",@"high"] indexOfObject:patch[key]];
            value=(value & (255^(3<<shift))) | (mode<<shift);continue;
        }
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
    if ([message[@"sender"] intValue] != 4 || [message[@"receiver"] intValue] != 2 || [message[@"commandSet"] intValue] != 4 || [message[@"commandId"] intValue] != 0x6e || !AppPlainFlags(message[@"flags"],NO)) return nil;
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

NSArray<NSDictionary *> *RSAppTuningSelection(NSString *domain, NSDictionary *filters) {
    if (![domain isKindOfClass:NSString.class]) return nil;
    NSArray *groups=@{@"follow":@[@[@"speed",@[@3,@12,@2],@2,@1,@100],@[@"acceleration",@[@15,@16,@14],@2,@1,@100],@[@"deadZone",@[@5,@13,@4],@2,@0,@100]],
        @"rc":@[@[@"speed",@[@42,@43,@41],@2,@0,@100],@[@"deadZone",@[@27,@40,@26],@1,@0,@100],@[@"smoothing",@[@9,@39,@8],@2,@0,@30]]}[domain];
    if (!groups || (filters && ![filters isKindOfClass:NSDictionary.class])) return nil;
    for (id key in filters) if (![@[@"axis",@"parameter"] containsObject:key]) return nil;
    NSArray *axes=@[@"pitch",@"roll",@"yaw"];
    if (filters[@"axis"] && ![axes containsObject:filters[@"axis"]]) return nil;
    BOOL found=filters[@"parameter"]==nil;
    NSMutableArray *result=[NSMutableArray array];
    for (NSArray *group in groups) {
        if (filters[@"parameter"] && ![filters[@"parameter"] isEqual:group[0]]) continue;
        found=YES;
        for (NSUInteger i=0;i<3;i++) {
            if (filters[@"axis"] && ![filters[@"axis"] isEqual:axes[i]]) continue;
            [result addObject:@{@"axis":axes[i],@"parameter":group[0],@"index":group[1][i],@"size":group[2],@"min":group[3],@"max":group[4]}];
        }
    }
    return found?[result copy]:nil;
}
NSDictionary *RSAppTuningWriteSpec(NSString *domain, NSDictionary *spec) {
    if (![spec isKindOfClass:NSDictionary.class] || spec.count!=3 || !spec[@"axis"] || !spec[@"parameter"] || !Numeric(spec[@"value"])) return nil;
    NSArray *selected=RSAppTuningSelection(domain,@{@"axis":spec[@"axis"],@"parameter":spec[@"parameter"]});
    if (selected.count!=1) return nil;
    double value=[spec[@"value"] doubleValue];NSDictionary *row=selected[0];
    if (floor(value)!=value || value<[row[@"min"] intValue] || value>[row[@"max"] intValue]) return nil;
    NSMutableDictionary *result=[row mutableCopy];result[@"value"]=@(value);return [result copy];
}
NSData *RSAppTuningWriteFrame(uint16_t sequence, NSArray *context, NSNumber *value) {
    context=RSAppParameterContext(context);if (context.count!=1 || !Numeric(value)) return nil;
    for (NSString *domain in @[@"follow",@"rc"]) for (NSDictionary *row in RSAppTuningSelection(domain,nil)) {
        if (![row[@"index"] isEqual:context[0][@"index"]] || ![row[@"size"] isEqual:context[0][@"size"]]) continue;
        if (!RSAppTuningWriteSpec(domain,@{@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"value":value})) return nil;
        uint8_t payload[]={[row[@"index"] unsignedCharValue],[row[@"size"] unsignedCharValue],value.unsignedIntValue&255,(value.unsignedIntValue>>8)&255};
        return CommandFrame(sequence,4,0x0f,[NSData dataWithBytes:payload length:2+[row[@"size"] unsignedIntegerValue]],0x40);
    }
    return nil;
}
NSDictionary *RSDecodeAppTuningReply(NSDictionary *message, NSArray *selection, NSError **error) {
    NSMutableArray *context=[NSMutableArray array];
    for (NSDictionary *row in selection) [context addObject:@{@"index":row[@"index"],@"size":row[@"size"]}];
    NSDictionary *reply=RSDecodeAppReply(message,0x10,context,error);if (!reply) return nil;
    NSMutableArray *values=[NSMutableArray array];
    for (NSUInteger i=0;i<selection.count;i++) {
        NSDictionary *row=selection[i],*record=reply[@"parameters"][i];NSString *hex=record[@"rawHex"];NSUInteger size=[row[@"size"] unsignedIntegerValue];unsigned raw=0;
        if (size<1 || size>2 || hex.length!=size*2) { if(error)*error=RSAppError(@"RS4MINI_PROTOCOL_ERROR",@"Invalid tuning width",nil);return nil; }
        for (NSUInteger b=0;b<size;b++) { unsigned byte=0;NSScanner *scanner=[NSScanner scannerWithString:[hex substringWithRange:NSMakeRange(b*2,2)]];
            if (![scanner scanHexInt:&byte] || !scanner.isAtEnd) { if(error)*error=RSAppError(@"RS4MINI_PROTOCOL_ERROR",@"Invalid tuning bytes",nil);return nil; }raw|=byte<<(8*b);
        }
        NSMutableDictionary *value=[record mutableCopy];[value addEntriesFromDictionary:@{@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"rawValue":@(raw),@"withinSourceRange":@(raw>=[row[@"min"] unsignedIntValue] && raw<=[row[@"max"] unsignedIntValue])}];[values addObject:[value copy]];
    }
    NSMutableDictionary *result=[reply mutableCopy];result[@"values"]=[values copy];result[@"activePresetVerified"]=@NO;return [result copy];
}

NSArray<NSDictionary *> *RSAppStandaloneSelection(NSDictionary *filters) {
    if (filters && ![filters isKindOfClass:NSDictionary.class]) return nil;
    for (id key in filters) if (![@[@"axis",@"parameter"] containsObject:key]) return nil;
    NSArray *axes=@[@"pitch",@"roll",@"yaw"];
    NSArray *groups=@[@[@"speed",@[@80,@79,@81],@0,@100],@[@"smoothing",@[@77,@76,@78],@0,@30]];
    if (filters[@"axis"] && ![axes containsObject:filters[@"axis"]]) return nil;
    BOOL found=filters[@"parameter"]==nil;NSMutableArray *result=[NSMutableArray array];
    for (NSArray *group in groups) {
        if (filters[@"parameter"] && ![filters[@"parameter"] isEqual:group[0]]) continue;found=YES;
        for (NSUInteger i=0;i<3;i++) {
            if (filters[@"axis"] && ![filters[@"axis"] isEqual:axes[i]]) continue;
            [result addObject:@{@"axis":axes[i],@"parameter":group[0],@"index":group[1][i],@"size":@2,@"min":group[2],@"max":group[3]}];
        }
    }
    return found?[result copy]:nil;
}
NSDictionary *RSAppStandaloneWriteSpec(NSDictionary *spec) {
    if (![spec isKindOfClass:NSDictionary.class] || spec.count!=4 || !Numeric(spec[@"inputSource"]) || [spec[@"inputSource"] doubleValue]!=2 || !spec[@"axis"] || !spec[@"parameter"] || !Numeric(spec[@"value"])) return nil;
    NSArray *selected=RSAppStandaloneSelection(@{@"axis":spec[@"axis"],@"parameter":spec[@"parameter"]});if (selected.count!=1) return nil;
    NSDictionary *row=selected[0];double value=[spec[@"value"] doubleValue];
    if (floor(value)!=value || value<[row[@"min"] intValue] || value>[row[@"max"] intValue]) return nil;
    NSMutableDictionary *result=[row mutableCopy];result[@"value"]=@(value);result[@"inputSource"]=@2;return [result copy];
}
NSData *RSAppStandaloneWriteFrame(uint16_t sequence, NSArray *context, NSNumber *value) {
    context=RSAppParameterContext(context);
    if (context.count!=2 || ![context[0][@"index"] isEqual:@72] || ![context[0][@"size"] isEqual:@1]) return nil;
    for (NSDictionary *row in RSAppStandaloneSelection(nil)) {
        if (![row[@"index"] isEqual:context[1][@"index"]] || ![context[1][@"size"] isEqual:@2]) continue;
        if (!RSAppStandaloneWriteSpec(@{@"inputSource":@2,@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"value":value ?: NSNull.null})) return nil;
        uint8_t body[]={72,1,2,[row[@"index"] unsignedCharValue],2,value.unsignedIntValue&255,(value.unsignedIntValue>>8)&255};
        return CommandFrame(sequence,4,0x0f,[NSData dataWithBytes:body length:7],0x40);
    }
    return nil;
}
NSDictionary *RSDecodeAppStandaloneReply(NSDictionary *message, NSArray *selection, NSError **error) {
    NSMutableArray *context=[NSMutableArray arrayWithObject:@{@"index":@72,@"size":@1}];
    for(NSDictionary *row in selection)[context addObject:@{@"index":row[@"index"],@"size":@2}];
    NSDictionary *reply=RSDecodeAppReply(message,0x10,context,error);if(!reply)return nil;
    unsigned input=0;[[NSScanner scannerWithString:reply[@"parameters"][0][@"rawHex"]] scanHexInt:&input];
    NSMutableArray *values=[NSMutableArray array];
    for(NSUInteger i=0;i<selection.count;i++) {
        NSDictionary *row=selection[i],*record=reply[@"parameters"][i+1];unsigned encoded=0;
        [[NSScanner scannerWithString:record[@"rawHex"]] scanHexInt:&encoded];unsigned raw=((encoded&255)<<8)|(encoded>>8);
        NSMutableDictionary *item=[record mutableCopy];[item addEntriesFromDictionary:@{@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"rawValue":@(raw),@"withinSourceRange":@(raw>=[row[@"min"] unsignedIntValue] && raw<=[row[@"max"] unsignedIntValue])}];[values addObject:[item copy]];
    }
    NSMutableDictionary *result=[reply mutableCopy];result[@"inputSourceRaw"]=@(input);result[@"activePresetVerified"]=@NO;result[@"values"]=[values copy];return [result copy];
}

NSDictionary *RSDecodeAppUserParameterNotification(NSDictionary *message) {
    if ([message[@"sender"] intValue]!=4 || [message[@"receiver"] intValue]!=2 || [message[@"commandSet"] intValue]!=4 || [message[@"commandId"] intValue]!=0x24 || !Numeric(message[@"flags"]) || [message[@"flags"] doubleValue]!=floor([message[@"flags"] doubleValue]) || [message[@"flags"] doubleValue]<0 || [message[@"flags"] doubleValue]>255 || ([message[@"flags"] intValue]&0x87)) return nil;
    NSData *body=message[@"payload"];if (![body isKindOfClass:NSData.class] || body.length<74) return nil;
    NSArray *fields=@[@[@"getPitchAccel",@59,@2],@[@"getPitchDeadband",@21,@2],@[@"getPitchSmoothTrack",@70,@1],@[@"getPitchSpeed",@13,@2],@[@"getPresetID",@2,@1],@[@"getRollAccel",@63,@2],@[@"getRollDeadband",@51,@2],@[@"getRollSmoothTrack",@73,@1],@[@"getRollSpeed",@47,@2],@[@"getStickPitchSmooth",@37,@2],@[@"getStickPitchSpeed",@29,@2],@[@"getStickYawSmooth",@33,@2],@[@"getStickYawSpeed",@25,@2],@[@"getYawAccel",@55,@2],@[@"getYawDeadband",@17,@2],@[@"getYawSmoothTrack",@67,@1],@[@"getYawSpeed",@9,@2]];
    const uint8_t *p=body.bytes;NSMutableArray *values=[NSMutableArray array];
    for (NSArray *row in fields) {NSUInteger offset=[row[1] unsignedIntegerValue],size=[row[2] unsignedIntegerValue];unsigned raw=p[offset]+(size==2?256*p[offset+1]:0);
        [values addObject:@{@"sourceGetter":row[0],@"offset":row[1],@"size":row[2],@"rawValue":@(raw),@"rawHex":[Hex([body subdataWithRange:NSMakeRange(offset,size)]) copy]}];}
    NSNumber *raw=@(p[2]);NSString *name=@{@0:@"CUSTOM_1",@1:@"CUSTOM_2",@3:@"FAST",@4:@"MEDIUM",@5:@"SLOW"}[raw];
    return @{@"kind":@"userParameters",@"profile":@"ronin-2.2.2",@"timestamp":@(NSDate.date.timeIntervalSince1970*1000),@"values":[values copy],@"preset":@{@"rawValue":raw,@"sourceEnum":name ?: NSNull.null},@"bodyHex":[Hex(body) copy],@"deviceVerified":@NO,@"modelLayoutVerified":@NO,@"activePresetVerified":@NO,@"physicalCompletionVerified":@NO};
}

NSData *RSAppHandleQueryFrame(uint16_t sequence) {return CommandFrame(sequence,4,0x36,NSData.data,0x40);}
NSDictionary *RSDecodeAppHandleReply(NSDictionary *message,NSError **error) {
    NSDictionary *reply=RSDecodeAppReply(message,0x36,nil,error);if(!reply)return nil;
    NSData *payload=message[@"payload"];if(payload.length<9){if(error)*error=RSAppError(@"RS4MINI_PROTOCOL_ERROR",@"Handle body requires eight source bytes",nil);return nil;}
    NSArray *fields=@[@[@"getDualChannelEnable",@0,@NO],@[@"getTiltDirection",@1,@NO],@[@"getPanDirection",@2,@NO],@[@"getProfile",@3,@NO],@[@"getPitchFree",@4,@NO],@[@"getZoom2SpeedEnable",@5,@YES],@[@"getRotationFocusEnable",@6,@YES],@[@"getCellphoneSensorDisable",@7,@YES]];const uint8_t *body=((const uint8_t *)payload.bytes)+1;NSMutableArray *values=[NSMutableArray array];
    for(NSArray *row in fields){NSUInteger offset=[row[1] unsignedIntegerValue];[values addObject:@{@"sourceGetter":row[0],@"offset":row[1],@"size":@1,@"rawValue":@(body[offset]),@"sourceBit0":[row[2] boolValue]?@((body[offset]&1)!=0):NSNull.null}];}
    NSMutableDictionary *result=[reply mutableCopy];result[@"values"]=[values copy];result[@"modelLayoutVerified"]=@NO;return [result copy];
}

NSDictionary *RSAppFineTuneSpec(NSDictionary *spec) {
    if(![spec isKindOfClass:NSDictionary.class]||spec.count!=2||!Numeric(spec[@"adjustmentDegrees"]))return nil;
    NSDictionary *axes=@{@"roll":@0,@"pitch":@2};NSNumber *wire=[spec[@"axis"] isKindOfClass:NSString.class]?axes[spec[@"axis"]]:nil;if(!wire)return nil;
    double requested=[spec[@"adjustmentDegrees"] doubleValue];if(requested < -2||requested > 2)return nil;
    float value=(float)requested;float scaled=(float)(value*10.0f);int encoded=(int)scaled;
    return @{@"axis":[wire intValue]==0?@"roll":@"pitch",@"axisWire":wire,@"requestedAdjustmentDegrees":@(requested),@"encodedTenths":@(encoded),@"nominalAdjustmentDegrees":@(encoded/10.0)};
}
NSData *RSAppFineTuneFrame(uint16_t sequence,NSArray *context,NSNumber *tenths) {
    context=RSAppParameterContext(context);if(context.count!=1||![context[0][@"size"] isEqual:@1]||![@[@0,@2] containsObject:context[0][@"index"]]||!Numeric(tenths))return nil;
    double value=tenths.doubleValue;if(floor(value)!=value||value < -20||value > 20)return nil;
    uint8_t payload[]={(uint8_t)tenths.intValue,[context[0][@"index"] unsignedCharValue]};return CommandFrame(sequence,4,7,[NSData dataWithBytes:payload length:2],0x40);
}

NSDictionary *RSAppHandleWriteSpec(NSDictionary *spec) {
    if(![spec isKindOfClass:NSDictionary.class]||spec.count!=2||!Numeric(spec[@"value"]))return nil;
    NSDictionary *settings=@{@"dualChannelMode":@0,@"tiltDirection":@1,@"panDirection":@2};
    NSNumber *offset=[spec[@"setting"] isKindOfClass:NSString.class]?settings[spec[@"setting"]]:nil;
    double value=[spec[@"value"] doubleValue];if(!offset||(value!=0&&value!=1))return nil;
    return @{@"setting":@[@"dualChannelMode",@"tiltDirection",@"panDirection"][offset.unsignedIntegerValue],@"offset":offset,@"requestedValue":@(value==1?1:0)};
}
NSData *RSAppHandleWriteFrame(uint16_t sequence,NSArray *context,NSNumber *value) {
    context=RSAppParameterContext(context);if(context.count!=1||![context[0][@"size"] isEqual:@1]||![@[@0,@1,@2] containsObject:context[0][@"index"]]||!Numeric(value)||(value.doubleValue!=0&&value.doubleValue!=1))return nil;
    uint8_t payload[8];memset(payload,255,8);payload[[context[0][@"index"] unsignedIntegerValue]]=value.unsignedCharValue;
    return CommandFrame(sequence,4,0x35,[NSData dataWithBytes:payload length:8],0x40);
}

NSDictionary *RSAppFactoryResetSpec(NSDictionary *spec) {
    if(![spec isKindOfClass:NSDictionary.class]||spec.count!=1||![spec[@"sourcePlatform"] isKindOfClass:NSString.class]||![spec[@"sourcePlatform"] isEqualToString:@"HG724"])return nil;
    return @{@"requestedSourcePlatform":@"HG724"};
}
NSData *RSAppFactoryResetFrame(uint16_t sequence,NSString *sourcePlatform) {
    if(![sourcePlatform isKindOfClass:NSString.class]||![sourcePlatform isEqualToString:@"HG724"])return nil;
    uint8_t payload[]={1,0,1};return CommandFrame(sequence,4,0x13,[NSData dataWithBytes:payload length:3],0x40);
}

NSDictionary *RSAppAxisModeSpec(NSDictionary *spec) {
    if(![spec isKindOfClass:NSDictionary.class]||spec.count!=1||![spec[@"sourceMode"] isKindOfClass:NSString.class])return nil;
    NSDictionary *modes=@{@"ThreeAxis":@0,@"TwoAxis":@8,@"Roll360":@16,@"ThreeDRoll360":@24};NSNumber *value=modes[spec[@"sourceMode"]];if(!value)return nil;
    return @{@"requestedSourceMode":@[@"ThreeAxis",@"TwoAxis",@"Roll360",@"ThreeDRoll360"][value.unsignedIntegerValue>>3],@"requestedRawValue":value};
}
NSData *RSAppAxisModeWriteFrame(uint16_t sequence,NSArray *context,NSNumber *value) {
    context=RSAppParameterContext(context);if(context.count!=1||![context[0][@"index"] isEqual:@34]||![context[0][@"size"] isEqual:@1]||!Numeric(value)||![@[@0,@8,@16,@24] containsObject:value])return nil;
    uint8_t payload[]={34,1,value.unsignedCharValue};return CommandFrame(sequence,4,0x0f,[NSData dataWithBytes:payload length:3],0x40);
}
NSDictionary *RSDecodeAppAxisModeReply(NSDictionary *message,NSError **error) {
    NSDictionary *reply=RSDecodeAppReply(message,0x10,@[@{@"index":@34,@"size":@1}],error);if(!reply)return nil;
    unsigned raw=(unsigned)strtoul([reply[@"parameters"][0][@"rawHex"] UTF8String],NULL,16),mode=(raw>>3)&3;
    NSMutableDictionary *result=[reply mutableCopy];result[@"rawValue"]=@(raw);result[@"sourceModeValue"]=@(mode);result[@"sourceMode"]=@[@"ThreeAxis",@"TwoAxis",@"Roll360",@"ThreeDRoll360"][mode];result[@"unknownBits"]=@(raw&231);result[@"modelLayoutVerified"]=@NO;result[@"activePresetVerified"]=@NO;return [result copy];
}

static NSArray *SmoothContext(NSArray *context) {
    context=RSAppParameterContext(context);if(context.count<1||context.count>3)return nil;
    int last=16;for(NSDictionary *row in context){int index=[row[@"index"] intValue];if(index<=last||index>19||![row[@"size"] isEqual:@1])return nil;last=index;}return context;
}
NSArray *RSAppSmoothTrackSelection(NSDictionary *filters) {
    if(![filters isKindOfClass:NSDictionary.class]||filters.count>1||(filters.count==1&&!filters[@"axis"]))return nil;
    NSDictionary *axes=@{@"yaw":@17,@"pitch":@18,@"roll":@19};id axis=filters[@"axis"];if(axis&&(![axis isKindOfClass:NSString.class]||!axes[axis]))return nil;
    NSMutableArray *result=[NSMutableArray array];for(NSString *name in @[@"yaw",@"pitch",@"roll"])if(!axis||[axis isEqual:name])[result addObject:@{@"index":axes[name],@"size":@1}];return [result copy];
}
NSDictionary *RSAppSmoothTrackSpec(NSDictionary *spec) {
    if(![spec isKindOfClass:NSDictionary.class]||spec.count!=1||![spec[@"axes"] isKindOfClass:NSDictionary.class])return nil;
    NSDictionary *patch=spec[@"axes"];if(patch.count<1||patch.count>3)return nil;
    for(id key in patch){id v=patch[key];if(![@[@"yaw",@"pitch",@"roll"] containsObject:key]||![v isKindOfClass:NSNumber.class]||CFGetTypeID((__bridge CFTypeRef)v)!=CFBooleanGetTypeID())return nil;}
    NSMutableArray *context=[NSMutableArray array];NSMutableDictionary *requested=[NSMutableDictionary dictionary];unsigned bits=0;NSArray *names=@[@"yaw",@"pitch",@"roll"];
    for(unsigned i=0;i<3;i++){NSString *name=names[i];if(!patch[name])continue;BOOL enabled=[patch[name] boolValue];requested[name]=@(enabled);[context addObject:@{@"index":@(17+i),@"size":@1}];if(enabled)bits|=1u<<i;}
    return @{@"context":[context copy],@"requestedAxes":[requested copy],@"bits":@(bits)};
}
NSData *RSAppSmoothTrackWriteFrame(uint16_t sequence,NSArray *context,NSNumber *bits) {
    context=SmoothContext(context);if(!context||!Numeric(bits)||floor(bits.doubleValue)!=bits.doubleValue||bits.doubleValue<0||bits.doubleValue>7)return nil;
    unsigned mask=0;for(NSDictionary *row in context)mask|=1u<<([row[@"index"] unsignedIntValue]-17);if(bits.unsignedIntValue&~mask)return nil;
    NSMutableData *payload=[NSMutableData data];for(NSDictionary *row in context){unsigned index=[row[@"index"] unsignedIntValue];uint8_t part[]={(uint8_t)index,1,(bits.unsignedIntValue>>(index-17))&1};[payload appendBytes:part length:3];}
    return CommandFrame(sequence,4,0x0f,payload,0x40);
}
NSDictionary *RSDecodeAppSmoothTrackReply(NSDictionary *message,NSArray *context,NSError **error) {
    context=SmoothContext(context);if(!context){if(error)*error=RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Named smooth track context required",nil);return nil;}
    NSDictionary *reply=RSDecodeAppReply(message,0x10,context,error);if(!reply)return nil;NSMutableArray *values=[NSMutableArray array];
    for(NSDictionary *record in reply[@"parameters"]){unsigned index=[record[@"index"] unsignedIntValue],raw=(unsigned)strtoul([record[@"rawHex"] UTF8String],NULL,16);NSMutableDictionary *row=[record mutableCopy];row[@"axis"]=@[@"yaw",@"pitch",@"roll"][index-17];row[@"rawValue"]=@(raw);row[@"withinSourceRange"]=@(raw<=1);row[@"sourceEnabled"]=@(raw==1);row[@"enabled"]=raw<=1?@(raw==1):NSNull.null;[values addObject:[row copy]];}
    NSMutableDictionary *result=[reply mutableCopy];result[@"values"]=[values copy];result[@"modelLayoutVerified"]=@NO;result[@"activePresetVerified"]=@NO;return [result copy];
}

static NSDictionary *ProfileValueCatalog(void) {
    NSDictionary *catalog=@{@"userProfile":@{@"index":@0,@"size":@1,@"min":@0,@"max":@5},@"workMode":@{@"index":@62,@"size":@1,@"min":@0,@"max":@128}};return catalog;
}
NSArray *RSAppProfileValueContext(NSString *kind) {
    if(![kind isKindOfClass:NSString.class])return nil;NSDictionary *row=ProfileValueCatalog()[kind];return row?@[@{@"index":row[@"index"],@"size":row[@"size"]}]:nil;
}
NSDictionary *RSAppProfileValueSpec(NSString *kind,NSDictionary *spec) {
    if(![spec isKindOfClass:NSDictionary.class]||spec.count!=1)return nil;unsigned raw;NSMutableDictionary *result=[NSMutableDictionary dictionary];
    if([kind isEqual:@"userProfile"]){NSNumber *v=spec[@"sourceProfileValue"];if(!Numeric(v)||floor(v.doubleValue)!=v.doubleValue||v.doubleValue<0||v.doubleValue>5)return nil;raw=v.unsignedIntValue;result[@"requestedSourceProfileValue"]=@(raw);}
    else if([kind isEqual:@"workMode"]){NSDictionary *modes=@{@"Free":@0,@"Flower":@1,@"Fpv":@2,@"Center":@3};id name=spec[@"sourceMode"];NSNumber *v=[name isKindOfClass:NSString.class]?modes[name]:nil;if(!v)return nil;raw=v.unsignedIntValue;result[@"requestedSourceMode"]=@[@"Free",@"Flower",@"Fpv",@"Center"][raw];}
    else return nil;
    result[@"parameter"]=[kind copy];result[@"requestedRawValue"]=@(raw);return [result copy];
}
NSData *RSAppProfileValueWriteFrame(uint16_t sequence,NSArray *context,NSNumber *value) {
    context=RSAppParameterContext(context);if(context.count!=1||![context[0][@"size"] isEqual:@1]||!Numeric(value)||floor(value.doubleValue)!=value.doubleValue)return nil;
    unsigned index=[context[0][@"index"] unsignedIntValue];int max=index==0?5:index==62?3:-1;if(max<0||value.doubleValue<0||value.doubleValue>max)return nil;
    uint8_t payload[]={(uint8_t)index,1,value.unsignedCharValue};return CommandFrame(sequence,4,0x0f,[NSData dataWithBytes:payload length:3],0x40);
}
NSDictionary *RSDecodeAppProfileValueReply(NSDictionary *message,NSString *kind,NSError **error) {
    NSArray *context=RSAppProfileValueContext(kind);if(!context){if(error)*error=RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Named profile parameter required",nil);return nil;}
    NSDictionary *reply=RSDecodeAppReply(message,0x10,context,error);if(!reply)return nil;unsigned raw=(unsigned)strtoul([reply[@"parameters"][0][@"rawHex"] UTF8String],NULL,16);NSMutableDictionary *result=[reply mutableCopy];
    result[@"parameter"]=[kind copy];result[@"rawValue"]=@(raw);result[@"withinSourceRange"]=@(raw<=[ProfileValueCatalog()[kind][@"max"] unsignedIntValue]);result[@"modelLayoutVerified"]=@NO;result[@"activePresetVerified"]=@NO;
    if([kind isEqual:@"userProfile"])result[@"sourceUiName"]=raw<3?@[@"M1",@"M2",@"M3"][raw]:NSNull.null;
    else result[@"sourceMode"]=raw<4?@[@"Free",@"Flower",@"Fpv",@"Center"][raw]:NSNull.null;return [result copy];
}

NSDictionary *RSDecodeAppHandheldStickNotification(NSDictionary *message) {
    if ([message[@"sender"] intValue]!=4 || [message[@"receiver"] intValue]!=2 || [message[@"commandSet"] intValue]!=4 || [message[@"commandId"] intValue]!=0x57 || !Numeric(message[@"flags"]) || [message[@"flags"] doubleValue]!=floor([message[@"flags"] doubleValue]) || [message[@"flags"] doubleValue]<0 || [message[@"flags"] doubleValue]>255 || ([message[@"flags"] intValue]&0x87)) return nil;
    NSData *body=message[@"payload"];if(![body isKindOfClass:NSData.class] || body.length<6)return nil;
    const uint8_t *b=body.bytes;uint16_t word=(uint16_t)(b[4]|((uint16_t)b[5]<<8));
    return @{@"kind":@"handheldStick",@"profile":@"ronin-2.2.2",@"timestamp":@(NSDate.date.timeIntervalSince1970*1000),@"sourceStickX":@((int16_t)(b[0]|((uint16_t)b[1]<<8))),@"sourceStickY":@((int16_t)(b[2]|((uint16_t)b[3]<<8))),@"rawStateWord":@(word),@"unknownStateBits":@(word&0xfffc),@"sourceTriggerPressed":@((word&1)!=0),@"sourceStickControlEnabled":@((word&2)!=0),@"bodyHex":[Hex(body) copy],@"deviceVerified":@NO,@"modelLayoutVerified":@NO,@"axisMappingVerified":@NO,@"physicalCompletionVerified":@NO};
}

NSDictionary *RSDecodeAppSourceStatusNotification(NSDictionary *message) {
    int command=[message[@"commandId"] intValue];
    if ([message[@"sender"] intValue]!=4 || [message[@"receiver"] intValue]!=2 || [message[@"commandSet"] intValue]!=4 || (command!=0x27 && command!=0x33) || !Numeric(message[@"flags"]) || [message[@"flags"] doubleValue]!=floor([message[@"flags"] doubleValue]) || [message[@"flags"] doubleValue]<0 || [message[@"flags"] doubleValue]>255 || ([message[@"flags"] intValue]&0x87)) return nil;
    NSData *body=message[@"payload"];BOOL abnormal=command==0x27;if(![body isKindOfClass:NSData.class] || body.length<(abnormal?5:1))return nil;
    const uint8_t *b=body.bytes;
    NSMutableDictionary *result=[@{@"kind":abnormal?@"abnormal":@"battery",@"profile":@"ronin-2.2.2",@"timestamp":@(NSDate.date.timeIntervalSince1970*1000),@"bodyHex":[Hex(body) copy],@"deviceVerified":@NO,@"modelLayoutVerified":@NO,@"physicalCompletionVerified":@NO} mutableCopy];
    if(!abnormal){result[@"rawCapacityValue"]=@(b[0]);result[@"sourceGetter"]=@"getCapacityPercentage";return [result copy];}
    NSArray *fields=@[@[@"getFanDirection",@2,@1,@1,@NO],@[@"getGimbalDirectionWhenVertical",@2,@5,@1,@NO],@[@"getGimbalGravity",@3,@1,@3,@NO],@[@"getSleepMode",@4,@0,@1,@NO],@[@"getVerticalDirection",@2,@2,@1,@NO],@[@"isErrorRecentOrSelfie",@1,@6,@1,@YES],@[@"isErrorRecentWhenStartUp",@1,@3,@1,@YES],@[@"isInFlashlight",@2,@3,@1,@YES],@[@"isJointLockAfterStartup",@1,@0,@1,@YES],@[@"isJointLockWhenStartup",@1,@1,@1,@YES],@[@"isMotorProtected",@1,@2,@1,@YES],@[@"isPanoReady",@1,@7,@1,@YES],@[@"isPhoneOutGimbal",@3,@0,@1,@YES],@[@"isPitchLimitedInTracking",@3,@6,@1,@YES],@[@"isPitchLocked",@0,@1,@1,@YES],@[@"isPortrait",@2,@4,@1,@YES],@[@"isRollLocked",@0,@0,@1,@YES],@[@"isUpgrading",@1,@4,@1,@YES],@[@"isYawLimit",@1,@5,@1,@YES],@[@"isYawLimitedInTracking",@3,@5,@1,@YES],@[@"isYawLocked",@0,@2,@1,@YES]];
    NSMutableDictionary *values=[NSMutableDictionary dictionary];
    for(NSArray *field in fields){unsigned value=(b[[field[1] unsignedIntegerValue]]>>[field[2] unsignedIntValue])&[field[3] unsignedIntValue];values[field[0]]=[field[4] boolValue]?@(value!=0):@(value);}
    values[@"isGimbalLocked"]=@([values[@"isRollLocked"] boolValue] || [values[@"isPitchLocked"] boolValue]);result[@"sourceValues"]=[values copy];return [result copy];
}

static NSDictionary *AppProgramValues(int tag,const uint8_t *p) {
    if(tag==0x62)return @{@"status":@(p[0]),@"finishedPoints":@(p[1]),@"currentPercent":@(p[2]),@"totalPercent":@(p[3])};
    if(tag==0x37)return @{@"rawFlags":@(p[0]),@"status":@(p[0]&7),@"recordingOrPreview":@((p[0]>>3)&1),@"finishedPoints":@(p[1]),@"currentRoadPercent":@(p[2]),@"totalRoadPercent":@(p[3]),@"unknownFlagBits":@(p[0]&0xf0)};
    if(tag==0x63)return @{@"status":@(p[0]),@"currentPictures":@(p[1]|((unsigned)p[2]<<8)),@"totalPictures":@(p[3]|((unsigned)p[4]<<8))};
    return nil;
}
NSDictionary *RSDecodeAppProgramStatusNotification(NSDictionary *message) {
    for(NSString *key in @[@"sender",@"receiver",@"commandSet",@"commandId",@"flags"]){id n=message[key];if(!Numeric(n) || [n doubleValue]!=floor([n doubleValue]) || [n doubleValue]<0 || [n doubleValue]>255)return nil;}
    int command=[message[@"commandId"] intValue],flags=[message[@"flags"] intValue];
    if([message[@"sender"] intValue]!=4 || [message[@"receiver"] intValue]!=2 || [message[@"commandSet"] intValue]!=4 || (command!=0x38 && command!=0x64 && command!=0x6b) || (flags&0x87))return nil;
    NSData *body=message[@"payload"];if(![body isKindOfClass:NSData.class] || body.length<(command==0x38?4:command==0x64?5:2))return nil;
    const uint8_t *b=body.bytes;
    NSMutableDictionary *result=[@{@"kind":@"program",@"profile":@"ronin-2.2.2",@"commandId":@(command),@"timestamp":@(NSDate.date.timeIntervalSince1970*1000),@"bodyHex":[Hex(body) copy],@"format":command==0x38?@"standalone-timelapse":command==0x64?@"standalone-panorama":@"program-records",@"sourceValues":NSNull.null,@"rawSuccessByte":NSNull.null,@"sourceSuccess":NSNull.null,@"records":@[],@"deviceVerified":@NO,@"modelLayoutVerified":@NO,@"programCorrelationVerified":@NO,@"physicalCompletionVerified":@NO} mutableCopy];
    if(command==0x38){result[@"sourceValues"]=@{@"rawFlags":@(b[0]),@"status":@(b[0]&3),@"takingOrPreview":@((b[0]>>3)&1),@"finishedPoints":@(b[1]),@"currentRoadPercent":@(b[2]),@"totalRoadPercent":@(b[3]),@"unknownFlagBits":@(b[0]&0xf4)};return [result copy];}
    if(command==0x64){result[@"sourceValues"]=AppProgramValues(0x63,b);return [result copy];}
    result[@"rawSuccessByte"]=@(b[0]);BOOL success=b[0]==0 || b[0]==1;result[@"sourceSuccess"]=@(success);if(!success)return [result copy];
    NSMutableArray *records=[NSMutableArray array];
    for(NSUInteger offset=1;offset<body.length;){
        if(body.length-offset<2)return nil;
        unsigned tag=b[offset],length=b[offset+1];NSUInteger end=offset+2+length;
        if(length>=128 || end>body.length || length<(tag==0x62 || tag==0x37?4:tag==0x63?5:0))return nil;
        NSData *payload=[body subdataWithRange:NSMakeRange(offset+2,length)];
        [records addObject:@{@"rawTag":@(tag),@"sourceSignedTag":@(tag<128?(int)tag:(int)tag-256),@"length":@(length),@"payloadHex":[Hex(payload) copy],@"sourceValues":AppProgramValues(tag,b+offset+2)?:NSNull.null}];offset=end;
    }
    result[@"records"]=[records copy];return [result copy];
}

NSDictionary *RSAppProgramStatusSelection(NSDictionary *spec) {
    if(![spec isKindOfClass:NSDictionary.class] || spec.count!=1 || ![spec[@"program"] isKindOfClass:NSString.class])return nil;
    NSDictionary *catalog=@{@"track":@98,@"timelapse":@55,@"panorama":@99};
    NSNumber *tag=catalog[spec[@"program"]];if(!tag)return nil;
    return @{@"requestedProgram":[spec[@"program"] copy],@"requestedProgramCommandId":tag};
}
NSData *RSAppProgramStatusRequestFrame(uint16_t sequence, NSNumber *programCommand) {
    if(!Numeric(programCommand) || [programCommand doubleValue]!=floor([programCommand doubleValue]) || ![@[@98,@55,@99] containsObject:programCommand])return nil;
    const uint8_t body[]={0,2,1,programCommand.unsignedCharValue};
    return Frame(sequence,0x6b,[NSData dataWithBytes:body length:4],0x40);
}

NSDictionary *RSAppProgramStatusSubscriptionSelection(NSDictionary *spec) {
    if(![spec isKindOfClass:NSDictionary.class] || spec.count!=2 || ![spec[@"enabled"] isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)spec[@"enabled"])!=CFBooleanGetTypeID())return nil;
    NSDictionary *selected=RSAppProgramStatusSelection(@{@"program":spec[@"program"]?:NSNull.null});
    if(!selected)return nil;
    NSMutableDictionary *result=[selected mutableCopy];
    result[@"requestedEnabled"]=spec[@"enabled"];
    result[@"requestType"]=[spec[@"enabled"] boolValue]?@"StartContinuePush":@"StopContinuePush";
    return [result copy];
}
NSData *RSAppProgramStatusSubscriptionFrame(uint16_t sequence, NSDictionary *spec) {
    NSDictionary *selection=RSAppProgramStatusSubscriptionSelection(spec);
    if(!selection)return nil;
    const uint8_t body[]={0,[selection[@"requestedEnabled"] boolValue]?0:1,1,[selection[@"requestedProgramCommandId"] unsignedCharValue]};
    return Frame(sequence,0x6b,[NSData dataWithBytes:body length:4],0x40);
}

static NSDictionary *AppPeripheralCatalog(void) {
    static NSDictionary *catalog;static dispatch_once_t once;
    dispatch_once(&once, ^{catalog=[NSJSONSerialization JSONObjectWithData:[@"{\"types\":[{\"name\":\"Channel1\",\"ordinal\":0,\"sourceId\":0},{\"name\":\"Channel2\",\"ordinal\":1,\"sourceId\":1},{\"name\":\"Channel3\",\"ordinal\":2,\"sourceId\":2},{\"name\":\"Channel4\",\"ordinal\":3,\"sourceId\":3},{\"name\":\"Channel5\",\"ordinal\":4,\"sourceId\":4},{\"name\":\"Channel6\",\"ordinal\":5,\"sourceId\":5},{\"name\":\"PMotorPower\",\"ordinal\":6,\"sourceId\":6},{\"name\":\"RMotorPower\",\"ordinal\":7,\"sourceId\":7},{\"name\":\"YMotorPower\",\"ordinal\":8,\"sourceId\":8},{\"name\":\"PMotorTemp\",\"ordinal\":9,\"sourceId\":10},{\"name\":\"RMotorTemp\",\"ordinal\":10,\"sourceId\":11},{\"name\":\"YMotorTemp\",\"ordinal\":11,\"sourceId\":12},{\"name\":\"PMotorCurrent\",\"ordinal\":12,\"sourceId\":13},{\"name\":\"RMotorCurrent\",\"ordinal\":13,\"sourceId\":14},{\"name\":\"YMotorCurrent\",\"ordinal\":14,\"sourceId\":15},{\"name\":\"PMotorAngle\",\"ordinal\":15,\"sourceId\":16},{\"name\":\"RMotorAngle\",\"ordinal\":16,\"sourceId\":17},{\"name\":\"YMotorAngle\",\"ordinal\":17,\"sourceId\":18},{\"name\":\"PGyroOut\",\"ordinal\":18,\"sourceId\":19},{\"name\":\"RGyroOut\",\"ordinal\":19,\"sourceId\":20},{\"name\":\"YGyroOut\",\"ordinal\":20,\"sourceId\":21},{\"name\":\"PAcceOut\",\"ordinal\":21,\"sourceId\":21},{\"name\":\"RAcceOut\",\"ordinal\":22,\"sourceId\":23},{\"name\":\"YAcceOut\",\"ordinal\":23,\"sourceId\":24},{\"name\":\"PGyroBias\",\"ordinal\":24,\"sourceId\":25},{\"name\":\"RGyroBias\",\"ordinal\":25,\"sourceId\":26},{\"name\":\"YGyroBias\",\"ordinal\":26,\"sourceId\":27},{\"name\":\"PPoseBias\",\"ordinal\":27,\"sourceId\":28},{\"name\":\"RPoseBias\",\"ordinal\":28,\"sourceId\":29},{\"name\":\"YPoseBias\",\"ordinal\":29,\"sourceId\":30},{\"name\":\"PTargetPose\",\"ordinal\":30,\"sourceId\":31},{\"name\":\"RTargetPose\",\"ordinal\":31,\"sourceId\":32},{\"name\":\"YTargetPose\",\"ordinal\":32,\"sourceId\":33},{\"name\":\"PActualPose\",\"ordinal\":33,\"sourceId\":34},{\"name\":\"RActualPose\",\"ordinal\":34,\"sourceId\":35},{\"name\":\"YActualPose\",\"ordinal\":35,\"sourceId\":36},{\"name\":\"GpsNum\",\"ordinal\":36,\"sourceId\":37},{\"name\":\"GpsLong\",\"ordinal\":37,\"sourceId\":38},{\"name\":\"GpsLat\",\"ordinal\":38,\"sourceId\":39},{\"name\":\"GpsNorthSpeed\",\"ordinal\":39,\"sourceId\":40},{\"name\":\"GpsEastSpeed\",\"ordinal\":40,\"sourceId\":41},{\"name\":\"GpsNorthAcceSpeed\",\"ordinal\":41,\"sourceId\":42},{\"name\":\"GpsEastAcceSpeed\",\"ordinal\":42,\"sourceId\":43},{\"name\":\"HandDeviceAngle\",\"ordinal\":43,\"sourceId\":46},{\"name\":\"ControlState\",\"ordinal\":44,\"sourceId\":65},{\"name\":\"Other\",\"ordinal\":45,\"sourceId\":255}],\"getters\":[{\"sourceGetter\":\"getControlState\",\"sourceType\":\"ControlState\",\"sourceId\":65,\"conversion\":\"int32\"},{\"sourceGetter\":\"getChannel1\",\"sourceType\":\"Channel1\",\"sourceId\":0,\"conversion\":\"int32\"},{\"sourceGetter\":\"getChannel2\",\"sourceType\":\"Channel2\",\"sourceId\":1,\"conversion\":\"int32\"},{\"sourceGetter\":\"getChannel3\",\"sourceType\":\"Channel3\",\"sourceId\":2,\"conversion\":\"int32\"},{\"sourceGetter\":\"getChannel4\",\"sourceType\":\"Channel4\",\"sourceId\":3,\"conversion\":\"int32\"},{\"sourceGetter\":\"getChannel5\",\"sourceType\":\"Channel5\",\"sourceId\":4,\"conversion\":\"int32\"},{\"sourceGetter\":\"getChannel6\",\"sourceType\":\"Channel6\",\"sourceId\":5,\"conversion\":\"int32\"},{\"sourceGetter\":\"getGimbalControlStateBad\",\"sourceType\":\"ControlState\",\"sourceId\":65,\"conversion\":\"masked3-equals2\"},{\"sourceGetter\":\"getGpsEastAcceSpeed\",\"sourceType\":\"GpsEastAcceSpeed\",\"sourceId\":43,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getGpsEastSpeed\",\"sourceType\":\"GpsEastSpeed\",\"sourceId\":41,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getGpsLat\",\"sourceType\":\"GpsLat\",\"sourceId\":39,\"conversion\":\"int-div1000000-to-double\"},{\"sourceGetter\":\"getGpsLng\",\"sourceType\":\"GpsLong\",\"sourceId\":38,\"conversion\":\"int-div1000000-to-double\"},{\"sourceGetter\":\"getGpsNorthAcceSpeed\",\"sourceType\":\"GpsNorthAcceSpeed\",\"sourceId\":42,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getGpsNorthSpeed\",\"sourceType\":\"GpsNorthSpeed\",\"sourceId\":40,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getGpsNum\",\"sourceType\":\"GpsNum\",\"sourceId\":37,\"conversion\":\"int32\"},{\"sourceGetter\":\"getHandDeviceAngle\",\"sourceType\":\"HandDeviceAngle\",\"sourceId\":46,\"conversion\":\"int32\"},{\"sourceGetter\":\"getPAcceOut\",\"sourceType\":\"PAcceOut\",\"sourceId\":21,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getPActualPose\",\"sourceType\":\"PActualPose\",\"sourceId\":34,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getPGyroBias\",\"sourceType\":\"PGyroBias\",\"sourceId\":25,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getPGyroOut\",\"sourceType\":\"PGyroOut\",\"sourceId\":19,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getPMotorAngle\",\"sourceType\":\"PMotorAngle\",\"sourceId\":16,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getPMotorPower\",\"sourceType\":\"PMotorPower\",\"sourceId\":6,\"conversion\":\"int32\"},{\"sourceGetter\":\"getPMotorTemp\",\"sourceType\":\"PMotorTemp\",\"sourceId\":10,\"conversion\":\"int32\"},{\"sourceGetter\":\"getPPoseBias\",\"sourceType\":\"PPoseBias\",\"sourceId\":28,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getPTargetPos\",\"sourceType\":\"PTargetPose\",\"sourceId\":31,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getRAcceOut\",\"sourceType\":\"RAcceOut\",\"sourceId\":23,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getRActualPose\",\"sourceType\":\"RActualPose\",\"sourceId\":35,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getRGyroBias\",\"sourceType\":\"RGyroBias\",\"sourceId\":26,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getRGyroOut\",\"sourceType\":\"RGyroOut\",\"sourceId\":20,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getRMotorAngle\",\"sourceType\":\"RMotorAngle\",\"sourceId\":17,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getRMotorPower\",\"sourceType\":\"RMotorPower\",\"sourceId\":7,\"conversion\":\"int32\"},{\"sourceGetter\":\"getRMotorTemp\",\"sourceType\":\"RMotorTemp\",\"sourceId\":11,\"conversion\":\"int32\"},{\"sourceGetter\":\"getRPoseBias\",\"sourceType\":\"RPoseBias\",\"sourceId\":29,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getRTargetPos\",\"sourceType\":\"RTargetPose\",\"sourceId\":32,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getYAcceOut\",\"sourceType\":\"YAcceOut\",\"sourceId\":24,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getYActualPose\",\"sourceType\":\"YActualPose\",\"sourceId\":36,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getYGyroBias\",\"sourceType\":\"YGyroBias\",\"sourceId\":27,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getYGyroOut\",\"sourceType\":\"YGyroOut\",\"sourceId\":21,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getYMotorAngle\",\"sourceType\":\"YMotorAngle\",\"sourceId\":18,\"conversion\":\"float32-div10\"},{\"sourceGetter\":\"getYMotorPower\",\"sourceType\":\"YMotorPower\",\"sourceId\":8,\"conversion\":\"int32\"},{\"sourceGetter\":\"getYMotorTemp\",\"sourceType\":\"YMotorTemp\",\"sourceId\":12,\"conversion\":\"int32\"},{\"sourceGetter\":\"getYPoseBias\",\"sourceType\":\"YPoseBias\",\"sourceId\":30,\"conversion\":\"float32-div100\"},{\"sourceGetter\":\"getYTargetPos\",\"sourceType\":\"YTargetPose\",\"sourceId\":33,\"conversion\":\"float32-div10\"}]}" dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];});
    return catalog;
}
static NSNumber *AppPeripheralConvert(int32_t value,NSString *kind) {
    if([kind isEqualToString:@"masked3-equals2"]){BOOL bad=(value&3)==2;return @(bad);}
    if([kind isEqualToString:@"int-div1000000-to-double"])return @((double)(value/1000000));
    if([kind isEqualToString:@"float32-div10"])return @((float)value/10.0f);
    if([kind isEqualToString:@"float32-div100"])return @((float)value/100.0f);
    return @(value);
}
NSDictionary *RSDecodeAppPeripheralNotification(NSDictionary *message) {
    id flags=message[@"flags"],payload=message[@"payload"];
    if(!Numeric(flags) || [flags doubleValue]!=floor([flags doubleValue]) || [flags intValue]<0 || [flags intValue]>255 || ([flags intValue]&0x87) || [message[@"sender"] intValue]!=4 || [message[@"receiver"] intValue]!=2 || [message[@"commandSet"] intValue]!=4 || [message[@"commandId"] intValue]!=102 || ![payload isKindOfClass:NSData.class] || ![payload length])return nil;
    NSData *body=payload;const uint8_t *b=body.bytes;NSMutableArray *records=[NSMutableArray array];BOOL branch=b[0]==1;
    NSMutableDictionary *result=[@{@"kind":@"peripheral",@"profile":@"ronin-2.2.2",@"commandId":@102,@"timestamp":@(NSDate.date.timeIntervalSince1970*1000),@"bodyHex":[Hex(body) copy],@"rawFlag":@(b[0]),@"sourceRecordBranchSelected":@(branch),@"records":@[],@"deviceVerified":@NO,@"modelLayoutVerified":@NO,@"referenceFrameVerified":@NO,@"physicalCompletionVerified":@NO} mutableCopy];
    if(!branch)return [result copy];
    for(NSUInteger offset=1;offset<body.length;){
        if(body.length-offset<2)return nil;
        unsigned tag=b[offset],length=b[offset+1];NSUInteger end=offset+2+length;
        if(length>=128 || end>body.length)return nil;
        const uint8_t *p=b+offset+2;int signedTag=tag<128?(int)tag:(int)tag-256;
        NSMutableArray *types=[NSMutableArray array],*getters=[NSMutableArray array],*views=[NSMutableArray array];
        for(NSDictionary *row in AppPeripheralCatalog()[@"types"])if([row[@"sourceId"] intValue]==signedTag)[types addObject:row[@"name"]];
        for(NSDictionary *row in AppPeripheralCatalog()[@"getters"])if([row[@"sourceId"] intValue]==signedTag)[getters addObject:row];
        uint32_t u=0;for(NSUInteger i=0;i<MIN(length,4);i++)u|=(uint32_t)p[i]<<(8*i);
        int32_t value=length==1?(int8_t)p[0]:length==2?Get16(p):(int32_t)u;
        for(NSDictionary *row in getters)[views addObject:@{@"sourceType":row[@"sourceType"],@"sourceGetter":row[@"sourceGetter"],@"conversion":row[@"conversion"],@"value":AppPeripheralConvert(value,row[@"conversion"])}];
        BOOL ambiguous=types.count>1;
        [records addObject:@{@"rawTag":@(tag),@"sourceSignedTag":@(signedTag),@"length":@(length),@"payloadHex":[Hex([body subdataWithRange:NSMakeRange(offset+2,length)]) copy],@"sourceTypes":[types copy],@"ambiguous":@(ambiguous),@"sourceInt32":getters.count?@(value):NSNull.null,@"sourceViews":[views copy]}];offset=end;
    }
    result[@"records"]=[records copy];return [result copy];
}

static NSArray *AppParameterSubscriptionCatalog(void){
    static NSArray *catalog;static dispatch_once_t once;
    dispatch_once(&once, ^{catalog=[NSJSONSerialization JSONObjectWithData:[@"[{\"key\":\"UserProfile\",\"commandId\":16,\"channel\":0,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"SilentMode\",\"commandId\":16,\"channel\":1,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchMotorControlStiffness\",\"commandId\":50,\"channel\":0,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawMotorControlStiffness\",\"commandId\":50,\"channel\":2,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollMotorControlStiffness\",\"commandId\":50,\"channel\":1,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchMotorControlStrength\",\"commandId\":50,\"channel\":3,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawMotorControlStrength\",\"commandId\":50,\"channel\":5,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollMotorControlStrength\",\"commandId\":50,\"channel\":4,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchMotorControlGyroFilteringFactor\",\"commandId\":50,\"channel\":6,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawMotorControlGyroFilteringFactor\",\"commandId\":50,\"channel\":8,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollMotorControlGyroFilteringFactor\",\"commandId\":50,\"channel\":7,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchMotorControlPreControl\",\"commandId\":50,\"channel\":9,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawMotorControlPreControl\",\"commandId\":50,\"channel\":11,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollMotorControlPreControl\",\"commandId\":50,\"channel\":10,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"MotorBlockUpTime\",\"commandId\":16,\"channel\":59,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawFineTuning\",\"commandId\":16,\"channel\":23,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"MotorEnabled\",\"commandId\":16,\"channel\":35,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"ForbidTriggerSelfie\",\"commandId\":16,\"channel\":35,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"ForbidVerticalShootingSwitch\",\"commandId\":16,\"channel\":35,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"ForbidRoll360Switch\",\"commandId\":16,\"channel\":35,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"StartBalanceTest\",\"commandId\":16,\"channel\":37,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"BalanceTestStatus\",\"commandId\":16,\"channel\":37,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"IsTestingBalance\",\"commandId\":16,\"channel\":37,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchTestResult\",\"commandId\":16,\"channel\":37,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollTestResult\",\"commandId\":16,\"channel\":37,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawTestResult\",\"commandId\":16,\"channel\":37,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchFineTuning\",\"commandId\":16,\"channel\":24,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalHoldType\",\"commandId\":16,\"channel\":60,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalWorkMode\",\"commandId\":16,\"channel\":62,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalAxisMode\",\"commandId\":16,\"channel\":34,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PushEnableYaw\",\"commandId\":16,\"channel\":20,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PushEnablePitch\",\"commandId\":16,\"channel\":21,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PushEnableRoll\",\"commandId\":16,\"channel\":22,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalInputSource\",\"commandId\":16,\"channel\":72,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalCreateSmoothRoll\",\"commandId\":16,\"channel\":76,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalCreateSmoothPitch\",\"commandId\":16,\"channel\":77,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalCreateSmoothYaw\",\"commandId\":16,\"channel\":78,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalCreateMaxSpeedRoll\",\"commandId\":16,\"channel\":79,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalCreateMaxSpeedPitch\",\"commandId\":16,\"channel\":80,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalCreateMaxSpeedYaw\",\"commandId\":16,\"channel\":81,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalMotionSmoothRoll\",\"commandId\":16,\"channel\":76,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalMotionSmoothPitch\",\"commandId\":16,\"channel\":77,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalMotionSmoothYaw\",\"commandId\":16,\"channel\":78,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalMotionMaxSpeedRoll\",\"commandId\":16,\"channel\":79,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalMotionMaxSpeedPitch\",\"commandId\":16,\"channel\":80,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalMotionMaxSpeedYaw\",\"commandId\":16,\"channel\":81,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalGamepadSmoothRoll\",\"commandId\":16,\"channel\":76,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalGamepadSmoothPitch\",\"commandId\":16,\"channel\":77,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalGamepadSmoothYaw\",\"commandId\":16,\"channel\":78,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalGamepadMaxSpeedRoll\",\"commandId\":16,\"channel\":79,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalGamepadMaxSpeedPitch\",\"commandId\":16,\"channel\":80,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalGamepadMaxSpeedYaw\",\"commandId\":16,\"channel\":81,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"TrackingSpeed\",\"commandId\":16,\"channel\":117,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"TrackingOrientationVertical\",\"commandId\":16,\"channel\":122,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalAutoMovement\",\"commandId\":16,\"channel\":105,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"GimbalFoldMode\",\"commandId\":16,\"channel\":107,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawSmoothTrackEnabled\",\"commandId\":16,\"channel\":17,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchSmoothTrackEnabled\",\"commandId\":16,\"channel\":18,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollSmoothTrackEnabled\",\"commandId\":16,\"channel\":19,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawSmoothTrackSpeed\",\"commandId\":16,\"channel\":2,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchSmoothTrackSpeed\",\"commandId\":16,\"channel\":3,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollSmoothTrackSpeed\",\"commandId\":16,\"channel\":12,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawSmoothTrackDeadband\",\"commandId\":16,\"channel\":4,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchSmoothTrackDeadband\",\"commandId\":16,\"channel\":5,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollSmoothTrackDeadband\",\"commandId\":16,\"channel\":13,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawSmoothTrackAcceleration\",\"commandId\":16,\"channel\":14,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchSmoothTrackAcceleration\",\"commandId\":16,\"channel\":15,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollSmoothTrackAcceleration\",\"commandId\":16,\"channel\":16,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawControllerSmoothingFactor\",\"commandId\":16,\"channel\":8,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchControllerSmoothingFactor\",\"commandId\":16,\"channel\":9,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollControllerSmoothingFactor\",\"commandId\":16,\"channel\":39,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"YawControllerDeadband\",\"commandId\":16,\"channel\":26,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"PitchControllerDeadband\",\"commandId\":16,\"channel\":27,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RollControllerDeadband\",\"commandId\":16,\"channel\":40,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"ControllerMaxSpeedYaw\",\"commandId\":16,\"channel\":41,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"ControllerMaxSpeedPitch\",\"commandId\":16,\"channel\":42,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"ControllerMaxSpeedRoll\",\"commandId\":16,\"channel\":43,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Ronin2MaxAngleYaw\",\"commandId\":16,\"channel\":49,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Ronin2MinAngleYaw\",\"commandId\":16,\"channel\":50,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Ronin2MaxAnglePitch\",\"commandId\":16,\"channel\":47,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Ronin2MinAnglePitch\",\"commandId\":16,\"channel\":48,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Ronin2MaxAngleRoll\",\"commandId\":16,\"channel\":51,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Ronin2MinAngleRoll\",\"commandId\":16,\"channel\":52,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"IsChannel1Rev\",\"commandId\":16,\"channel\":53,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Channel1MapState\",\"commandId\":16,\"channel\":53,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"IsChannel2Rev\",\"commandId\":16,\"channel\":54,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Channel2MapState\",\"commandId\":16,\"channel\":54,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"IsChannel3Rev\",\"commandId\":16,\"channel\":55,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Channel3MapState\",\"commandId\":16,\"channel\":55,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"IsChannel4Rev\",\"commandId\":16,\"channel\":56,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Channel4MapState\",\"commandId\":16,\"channel\":56,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"IsChannel5Rev\",\"commandId\":16,\"channel\":57,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Channel5MapState\",\"commandId\":16,\"channel\":57,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"IsChannel6Rev\",\"commandId\":16,\"channel\":58,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"Channel6MapState\",\"commandId\":16,\"channel\":58,\"channelSource\":\"resource-if-present\",\"sourceCondition\":null},{\"key\":\"IsAutoTune\",\"commandId\":16,\"channel\":63,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"AutoTuneProgress\",\"commandId\":16,\"channel\":63,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"AutoTunePercent\",\"commandId\":16,\"channel\":64,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"FollowSpeedMode\",\"commandId\":16,\"channel\":65,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"FollowDeadZoneMode\",\"commandId\":16,\"channel\":66,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RcSpeedMode\",\"commandId\":16,\"channel\":67,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RcDeadZoneMode\",\"commandId\":16,\"channel\":68,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"RcSmoothMode\",\"commandId\":16,\"channel\":69,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"ControlParamMode\",\"commandId\":16,\"channel\":70,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"FollowAcceMode\",\"commandId\":16,\"channel\":71,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"IsCustomFollowMode\",\"commandId\":16,\"channel\":132,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"CustomFollowModePitchEnabled\",\"commandId\":16,\"channel\":132,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"CustomFollowModeRollEnabled\",\"commandId\":16,\"channel\":132,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"CustomFollowModeYawEnabled\",\"commandId\":16,\"channel\":132,\"channelSource\":\"explicit-base\",\"sourceCondition\":null},{\"key\":\"FollowModeSensitivity\",\"commandId\":16,\"channel\":150,\"channelSource\":\"explicit-base\",\"sourceCondition\":\"isSupportStateSince4Gen\"},{\"key\":\"Channel1Val\",\"commandId\":102,\"channel\":0,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"Channel2Val\",\"commandId\":102,\"channel\":1,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"Channel3Val\",\"commandId\":102,\"channel\":2,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"Channel4Val\",\"commandId\":102,\"channel\":3,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"Channel5Val\",\"commandId\":102,\"channel\":4,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"Channel6Val\",\"commandId\":102,\"channel\":5,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPowerPitch\",\"commandId\":102,\"channel\":6,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPowerYaw\",\"commandId\":102,\"channel\":8,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPowerRoll\",\"commandId\":102,\"channel\":7,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralAnglePitch\",\"commandId\":102,\"channel\":16,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralAngleYaw\",\"commandId\":102,\"channel\":18,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralAngleRoll\",\"commandId\":102,\"channel\":17,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralTempPitch\",\"commandId\":102,\"channel\":10,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralTempYaw\",\"commandId\":102,\"channel\":12,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralTempRoll\",\"commandId\":102,\"channel\":11,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPosPitchBias\",\"commandId\":102,\"channel\":28,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPosYawBias\",\"commandId\":102,\"channel\":30,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPosRollBias\",\"commandId\":102,\"channel\":29,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPosPitch\",\"commandId\":102,\"channel\":34,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPosYaw\",\"commandId\":102,\"channel\":36,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralPosRoll\",\"commandId\":102,\"channel\":35,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralTargetPosPitch\",\"commandId\":102,\"channel\":31,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralTargetPosYaw\",\"commandId\":102,\"channel\":33,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralTargetPosRoll\",\"commandId\":102,\"channel\":32,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroOutPitch\",\"commandId\":102,\"channel\":19,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroOutYaw\",\"commandId\":102,\"channel\":21,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroOutRoll\",\"commandId\":102,\"channel\":20,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroAccePitch\",\"commandId\":102,\"channel\":21,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroAcceYaw\",\"commandId\":102,\"channel\":24,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroAcceRoll\",\"commandId\":102,\"channel\":23,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroBiasPitch\",\"commandId\":102,\"channel\":25,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroBiasYaw\",\"commandId\":102,\"channel\":27,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGyroBiasRoll\",\"commandId\":102,\"channel\":26,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGpsNum\",\"commandId\":102,\"channel\":37,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGpsLat\",\"commandId\":102,\"channel\":39,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGpsLng\",\"commandId\":102,\"channel\":38,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGpsNorthSpeed\",\"commandId\":102,\"channel\":40,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGpsEastSpeed\",\"commandId\":102,\"channel\":41,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGpsNorthAcceSpeed\",\"commandId\":102,\"channel\":42,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralGpsEastAcceSpeed\",\"commandId\":102,\"channel\":43,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"PeripheralHandDeviceAngle\",\"commandId\":102,\"channel\":46,\"channelSource\":\"explicit-direct\",\"sourceCondition\":null},{\"key\":\"GimbalControlState\",\"commandId\":102,\"channel\":65,\"channelSource\":\"explicit-direct\",\"sourceCondition\":\"isSupportStateSince4Gen\"}]" dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];});return catalog;
}
NSArray *RSAppParameterSubscriptionKeys(void){NSMutableArray *names=[NSMutableArray array];for(NSDictionary *row in AppParameterSubscriptionCatalog())[names addObject:row[@"key"]];return [names sortedArrayUsingSelector:@selector(compare:)];}
NSDictionary *RSAppParameterSubscriptionSpec(NSDictionary *spec){
    if(![spec isKindOfClass:NSDictionary.class]||spec.count!=1||![spec[@"keys"] isKindOfClass:NSArray.class]||[spec[@"keys"] count]<1||[spec[@"keys"] count]>152)return nil;
    NSMutableDictionary *index=[NSMutableDictionary dictionary];for(NSDictionary *row in AppParameterSubscriptionCatalog())index[row[@"key"]]=row;
    NSMutableSet *unique=[NSMutableSet set];for(id key in spec[@"keys"]){if(![key isKindOfClass:NSString.class]||!index[key])return nil;[unique addObject:[key copy]];}
    NSArray *requested=[[unique allObjects] sortedArrayUsingSelector:@selector(compare:)];NSMutableDictionary *groups=[NSMutableDictionary dictionary];NSMutableArray *metadata=[NSMutableArray array],*model=[NSMutableArray array],*sourceGroups=[NSMutableArray array];
    for(NSString *key in requested){NSDictionary *row=index[key];if([row[@"channelSource"] isEqualToString:@"resource-if-present"])[metadata addObject:key];if([row[@"sourceCondition"] isKindOfClass:NSString.class])[model addObject:key];NSNumber *command=row[@"commandId"];if(!groups[command])groups[command]=[NSMutableSet set];[groups[command] addObject:row[@"channel"]];}
    NSMutableData *body=[NSMutableData data];for(NSNumber *command in @[@16,@50,@102]){if(!groups[command])continue;NSArray *channels=[[groups[command] allObjects] sortedArrayUsingSelector:@selector(compare:)];NSUInteger highest=[channels.lastObject unsignedIntegerValue];NSMutableData *bitmap=[NSMutableData dataWithLength:highest/8+1];uint8_t *p=bitmap.mutableBytes;for(NSNumber *value in channels){NSUInteger channel=value.unsignedIntegerValue;p[channel/8]|=1<<(channel%8);}uint8_t header[]={command.unsignedCharValue,(uint8_t)highest};[body appendBytes:header length:2];[body appendData:bitmap];[sourceGroups addObject:@{@"commandId":command,@"channels":channels,@"highestChannelIndex":@(highest),@"bitmapHex":[Hex(bitmap) copy]}];}
    return @{@"payload":[body copy],@"requestedKeys":requested,@"sourceGroups":[sourceGroups copy],@"metadataConditionalKeys":[metadata copy],@"modelConditionalKeys":[model copy],@"requestBodyHex":[Hex(body) copy]};
}
NSData *RSAppParameterSubscriptionFrame(uint16_t sequence,NSDictionary *spec){NSDictionary *selection=RSAppParameterSubscriptionSpec(spec);if(!selection)return nil;NSMutableData *packet=[Frame(sequence,18,selection[@"payload"],0) mutableCopy];uint8_t *p=packet.mutableBytes;p[5]=229;Put16(p+packet.length-2,CRC16(p,packet.length-2));return [packet copy];}
NSDictionary *RSAppParameterSubscriptionSent(NSDictionary *selection){NSMutableDictionary *result=[selection mutableCopy];[result removeObjectForKey:@"payload"];[result addEntriesFromDictionary:@{@"profile":@"ronin-2.2.2",@"sent":@YES,@"receiverByte":@229,@"sourceCase":@"pinned-db-present/HG724",@"acknowledgementRequested":@NO,@"acknowledged":@NO,@"sourceAppInitializationVerified":@NO,@"targetRoutingVerified":@NO,@"notificationStreamVerified":@NO,@"remoteSubscriptionStateVerified":@NO,@"freshStatusVerified":@NO,@"deviceVerified":@NO,@"physicalCompletionVerified":@NO}];return [result copy];}

NSDictionary *RSDecodeAppExternalDeviceNotification(NSDictionary *message) {
    NSNumber *flags=message[@"flags"];
    if([message[@"sender"] intValue]!=4 || [message[@"receiver"] intValue]!=2 || [message[@"commandSet"] intValue]!=4 || [message[@"commandId"] intValue]!=105 || ![flags isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)flags)==CFBooleanGetTypeID() || flags.doubleValue!=floor(flags.doubleValue) || flags.doubleValue<0 || flags.doubleValue>255 || (flags.intValue&0x87))return nil;
    NSData *body=message[@"payload"];if(![body isKindOfClass:NSData.class] || body.length<2)return nil;
    const uint8_t *b=body.bytes;NSMutableArray *records=[NSMutableArray array];NSDictionary *types=@{@1:@"CommonStick",@2:@"RockWheel",@3:@"Sensor",@7:@"Other"};
    for(NSUInteger offset=0;offset<body.length;){
        if(body.length-offset<2)return nil;uint8_t tag=b[offset],length=b[offset+1];NSUInteger end=offset+2+length;
        if(length>=128 || end>body.length)return nil;
        NSData *payload=[body subdataWithRange:NSMakeRange(offset+2,length)];NSMutableDictionary *record=[@{@"rawTag":@(tag),@"sourceSignedTag":@(tag<128?tag:(int)tag-256),@"length":@(length),@"payloadHex":[Hex(payload) copy]} mutableCopy];
        if(tag==2){
            if(length<7)return nil;const uint8_t *p=payload.bytes;NSNumber *raw=@(p[0]);
            record[@"speedControl"]=@{@"rawControlType":raw,@"sourceControlType":types[raw]?:@"Other",@"sourceControlTypeKnown":@(types[raw]!=nil),@"sourcePitchSpeed":@((int16_t)(p[1]|((uint16_t)p[2]<<8))),@"sourceRollSpeed":@((int16_t)(p[3]|((uint16_t)p[4]<<8))),@"sourceYawSpeed":@((int16_t)(p[5]|((uint16_t)p[6]<<8))),@"trailingHex":[Hex([payload subdataWithRange:NSMakeRange(7,length-7)]) copy]};
        }
        [records addObject:[record copy]];offset=end;
    }
    return @{@"kind":@"externalDevice",@"profile":@"ronin-2.2.2",@"commandId":@105,@"timestamp":@(NSDate.date.timeIntervalSince1970*1000),@"bodyHex":[Hex(body) copy],@"records":[records copy],@"deviceVerified":@NO,@"modelLayoutVerified":@NO,@"unitVerified":@NO,@"referenceFrameVerified":@NO,@"physicalCompletionVerified":@NO};
}

NSDictionary *RSDecodeAppSensorCalibrationNotification(NSDictionary *message) {
    NSNumber *flags=message[@"flags"];
    if([message[@"sender"] intValue]!=4 || [message[@"receiver"] intValue]!=2 || [message[@"commandSet"] intValue]!=4 || [message[@"commandId"] intValue]!=48 || ![flags isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)flags)==CFBooleanGetTypeID() || flags.doubleValue!=floor(flags.doubleValue) || flags.doubleValue<0 || flags.doubleValue>255 || (flags.intValue&0x87))return nil;
    NSData *body=message[@"payload"];if(![body isKindOfClass:NSData.class] || body.length<2)return nil;
    const uint8_t *p=body.bytes;NSNumber *raw=@(p[1]);NSDictionary *states=@{@0:@"COMPLETE",@1:@"PROCESSING",@3:@"FAIL",@9:@"OTHER"};
    return @{@"kind":@"sensorCalibration",@"profile":@"ronin-2.2.2",@"commandId":@48,@"timestamp":@(NSDate.date.timeIntervalSince1970*1000),@"rawProgressValue":@(p[0]),@"rawStatus":raw,@"sourceStatus":states[raw]?:@"OTHER",@"sourceStatusKnown":@(states[raw]!=nil),@"bodyHex":[Hex(body) copy],@"trailingHex":[Hex([body subdataWithRange:NSMakeRange(2,body.length-2)]) copy],@"deviceVerified":@NO,@"modelLayoutVerified":@NO,@"progressUnitVerified":@NO,@"requestAssociationVerified":@NO,@"physicalCompletionVerified":@NO};
}

NSData *RSAppComponentCalibrationFrame(uint16_t sequence,NSString *sourcePart) {
    if(![sourcePart isKindOfClass:NSString.class]||![sourcePart isEqualToString:@"AUTO"])return nil;
    return CommandFrame(sequence,4,8,[NSData dataWithBytes:(uint8_t[]){0} length:1],0x40);
}
NSDictionary *RSDecodeAppComponentCalibrationReply(NSDictionary *message,uint8_t motorRaw,NSError **error) {
    NSDictionary *ack=RSDecodeAppReply(message,8,nil,error);if(!ack)return nil;
    NSData *payload=message[@"payload"],*body=[payload subdataWithRange:NSMakeRange(1,payload.length-1)];const uint8_t *p=body.bytes;BOOL complete=body.length>=2;id calibration=NSNull.null;
    if(complete){NSArray *parts=@[@"AUTO",@"JOINT_ANGLE",@"HALL_LINEAR",@"JOINT_ANGLE_CAMERA",@"JOINT_ANGLE_FIXTURE",@"GYRO",@"ACCELERATION",@"COMPASS",@"IMU_AND_SENSOR",@"SHOCK_PLATE"],*states=@[@"FAIL",@"SUCCESS",@"PROCESSING"];
        calibration=@{@"rawPart":@(p[0]),@"sourcePart":p[0]<parts.count?parts[p[0]]:@"AUTO",@"sourcePartKnown":@(p[0]<parts.count),@"rawStatus":@(p[1]),@"sourceStatus":p[1]<states.count?states[p[1]]:@"PROCESSING",@"sourceStatusKnown":@(p[1]<states.count),@"bodyHex":Hex(body),@"trailingHex":Hex([body subdataWithRange:NSMakeRange(2,body.length-2)])};}
    NSMutableDictionary *result=[ack mutableCopy];[result addEntriesFromDictionary:@{@"requestedSourcePart":@"AUTO",@"motorPreflightRawValue":@(motorRaw),@"motorPreflightEnabled":@(!(motorRaw&1)),@"businessComplete":@(complete),@"calibration":calibration,@"responsePartMatchesRequested":complete?@(p[0]==0):NSNull.null,@"modelLayoutVerified":@NO,@"motorStatePhysicalVerified":@NO,@"businessRequestAssociationVerified":@NO,@"firmwareAbortVerified":@NO}];return [result copy];
}

NSData *RSAppHandheldStickControlFrame(uint16_t sequence,NSNumber *enabled){
    if(![enabled isKindOfClass:NSNumber.class]||CFGetTypeID((__bridge CFTypeRef)enabled)!=CFBooleanGetTypeID())return nil;
    uint8_t value=enabled.boolValue;return CommandFrame(sequence,4,0x58,[NSData dataWithBytes:&value length:1],0x40);
}
NSDictionary *RSDecodeAppHandheldStickControlReply(NSDictionary *message,NSNumber *enabled,NSError **error){
    if(![enabled isKindOfClass:NSNumber.class]||CFGetTypeID((__bridge CFTypeRef)enabled)!=CFBooleanGetTypeID()){if(error)*error=RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"enabled must be boolean",nil);return nil;}
    NSDictionary *ack=RSDecodeAppReply(message,0x58,nil,error);if(!ack)return nil;
    NSMutableDictionary *result=[ack mutableCopy];[result addEntriesFromDictionary:@{@"sourceSetting":@"StickGimbalControlEnabled",@"requestedEnabled":enabled,@"modelLayoutVerified":@NO,@"readbackVerified":@NO,@"persistenceVerified":@NO,@"notificationAssociationVerified":@NO}];return [result copy];
}

NSDictionary *RSDecodeAppTutorialNotification(NSDictionary *message){
    if([message[@"sender"] intValue]!=4||[message[@"receiver"] intValue]!=2||[message[@"commandSet"] intValue]!=4||[message[@"commandId"] intValue]!=43||!AppPlainFlags(message[@"flags"],NO))return nil;
    NSData *body=message[@"payload"];if(![body isKindOfClass:NSData.class]||body.length<5)return nil;const uint8_t *p=body.bytes;uint32_t word=(uint32_t)p[1]|((uint32_t)p[2]<<8)|((uint32_t)p[3]<<16)|((uint32_t)p[4]<<24);
    NSArray *steps=@[@"STEP_FINISH",@"STEP_START",@"STEP_UNLOCK_GIMBAL",@"STEP_HOLD_GIMBAL_UPRIGHT",@"STEP_FOLLOW",@"STEP_STICK",@"STEP_LOCK_DIRECTION",@"STEP_RECENTER",@"STEP_SELFIE",@"STEP_PUSH",@"STEP_APP_CONTROL"],*getters=@[@"getIsUnlock",@"getIsUpright",@"getIsFollowFinish",@"getIsStickFinish",@"getIsLockDirectionFinish",@"getIsRecentFinish",@"getIsSelfieFinish",@"getIsHandlePushFinish",@"getIsAppControlFinish"];
    NSMutableDictionary *flags=[NSMutableDictionary dictionary],*views=[NSMutableDictionary dictionary];for(NSUInteger i=0;i<getters.count;i++)flags[getters[i]]=@((word>>i)&1);for(NSUInteger i=0;i<steps.count;i++)views[steps[i]]=((word>>((i+30)&31))&1)?@YES:@NO;
    return @{@"kind":@"tutorial",@"profile":@"ronin-2.2.2",@"commandId":@43,@"timestamp":@([NSDate date].timeIntervalSince1970*1000),@"rawStep":@(p[0]),@"knownSourceStepName":p[0]<steps.count?steps[p[0]]:NSNull.null,@"sourceFindResult":p[0]<steps.count?steps[p[0]]:@"STEP_FINISH",@"rawCompletionWord":@(word),@"sourceSignedCompletionWord":@(word>=0x80000000u?(int64_t)word-4294967296LL:(int64_t)word),@"unknownCompletionBits":@(word&0xfffffe00u),@"sourceFlags":[flags copy],@"sourceStepStatus":[views copy],@"bodyHex":Hex(body),@"trailingHex":Hex([body subdataWithRange:NSMakeRange(5,body.length-5)]),@"deviceVerified":@NO,@"modelLayoutVerified":@NO,@"requestAssociationVerified":@NO,@"physicalCompletionVerified":@NO};
}
