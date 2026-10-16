#import "RSControlCore.h"
#include <math.h>

static NSUInteger assertions;
static void Require(BOOL value, NSString *message) { assertions++; if (!value) { fprintf(stderr, "FAIL: %s\n", message.UTF8String); exit(1); } }
static NSString *Hex(NSData *data) { NSMutableString *hex = [NSMutableString string]; for (NSUInteger i = 0; i < data.length; i++) [hex appendFormat:@"%02x", ((const uint8_t *)data.bytes)[i]]; return hex; }
int main(void) {
    @autoreleasepool {
        NSArray *appContext = @[@{@"index": @150, @"size": @1}, @{@"index": @150, @"size": @8}];
        NSDictionary *appRequest = [[RSFrameDecoder new] push:RSAppParameterRequestFrame(7, appContext)].firstObject;
        Require([Hex(appRequest[@"payload"]) isEqualToString:@"9696"] && [appRequest[@"flags"] intValue] == 0x40, @"App request preserves duplicate unsigned indexes");
        Require(RSAppParameterRequestFrame(1, @[@{@"index": @YES, @"size": @1}]) == nil && RSAppSensitivityFrame(1, @2) == nil && RSAppSensitivityFrame(1, @YES) == nil, @"App inputs reject booleans and unsupported modes");
        Require([Hex([[RSFrameDecoder new] push:RSAppSensitivityFrame(1, @1)].firstObject[@"payload"]) isEqualToString:@"960101"], @"App source setter vector");
        const uint8_t appBytes[] = {0,150,9,1,150,8,255,255,255,255,255,255,255,255};
        NSDictionary *appMessage = @{@"sender": @4, @"receiver": @2, @"commandSet": @4, @"commandId": @16, @"flags": @128, @"payload": [NSData dataWithBytes:appBytes length:sizeof(appBytes)]};
        NSError *appError = nil; NSDictionary *appDecoded = RSDecodeAppReply(appMessage, 16, appContext, &appError);
        Require(appDecoded != nil && appError == nil && [appDecoded[@"parameters"][0][@"headerByte"] intValue] == 9 && [appDecoded[@"parameters"][1][@"rawHex"] isEqualToString:@"ffffffffffffffff"], @"App context decoder keeps header raw and 64-bit precision");
        NSMutableDictionary *badApp = [appMessage mutableCopy]; badApp[@"payload"] = [NSData dataWithBytes:appBytes length:sizeof(appBytes)-1];
        Require(RSDecodeAppReply(badApp, 16, appContext, &appError) == nil && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_PROTOCOL_ERROR"], @"App truncated data rejects");
        const uint8_t rejection[] = {7}; badApp[@"payload"] = [NSData dataWithBytes:rejection length:1];
        Require(RSDecodeAppReply(badApp,16,appContext,&appError) == nil && [appError.userInfo[@"statusCode"] intValue] == 7, @"App nonzero device status rejects before business decoding");
        Require([Hex([[RSFrameDecoder new] push:RSAppSettingsFrame(1, @"customFollow", @{@"enabled": @YES, @"pitch": @NO}, @14)].firstObject[@"payload"]) isEqualToString:@"84010d"], @"custom follow bits preserve other axes");
        Require([Hex([[RSFrameDecoder new] push:RSAppSettingsFrame(1, @"motor", @{@"enabled": @YES, @"forbidSelfie": @YES, @"roll360": @NO}, @207)].firstObject[@"payload"]) isEqualToString:@"23019e"], @"motor bit is inverted and unknown bits preserved");
        Require(!RSAppSettingsFrame(1, @"customFollow", @{@"yaw": @YES}, @128) && !RSAppSettingsPatch(@"customFollow", @{@"yaw": @1}) && !RSAppSettingsPatch(@"customFollow", @{}) && !RSAppSettingsPatch(@"motor", @{@"preset": @YES}), @"settings reject unknown range and invalid boolean fields");
        NSDictionary *settingsResult = RSDecodeAppSettings(@{@"parameters": @[@{@"rawHex": @"9e"}]}, @"motor");
        Require([settingsResult[@"unknownBits"] intValue] == 142 && [settingsResult[@"settings"][@"enabled"] boolValue] && ![settingsResult[@"settings"][@"roll360"] boolValue], @"settings read keeps unknown bits");
        NSData *stop = RSVelocityFrame(0x100, 0, 0, 0);
        Require([Hex(stop) isEqualToString:@"551604fc020400010004010004000400040000027705"], @"golden stop vector");
        Require(RSVelocityFrame(1, NAN, 0, 0) == nil, @"reject NaN");
        NSData *halfFrame = RSVelocityFrame(1, 0.5 / 660, -0.5 / 660, -1.5 / 660);
        const uint8_t *half = halfFrame.bytes;
        Require((half[15] | (half[16] << 8)) == 1025 && (half[11] | (half[12] << 8)) == 1024 && (half[13] | (half[14] << 8)) == 1023, @"JS half-step parity");
        RSFrameDecoder *decoder = [RSFrameDecoder new];
        Require([decoder push:[stop subdataWithRange:NSMakeRange(0, 20)]].count == 0, @"fragment held");
        NSMutableData *tail = [[stop subdataWithRange:NSMakeRange(20, 2)] mutableCopy]; [tail appendData:stop];
        Require([decoder push:tail].count == 2, @"fragment and coalesced frames");
        NSMutableData *bad = [stop mutableCopy]; ((uint8_t *)bad.mutableBytes)[21] ^= 1; [bad appendData:stop];
        Require([decoder push:bad].count == 1 && decoder.invalidFrames > 0, @"CRC resynchronization");
        NSMutableData *payload = [NSMutableData dataWithLength:49]; uint8_t *p = payload.mutableBytes;
        p[16] = 0x39; p[17] = 0x30; p[20] = 0xf6; p[21] = 0xff;
        NSDictionary *sample = RSDecodeTelemetry(payload);
        Require(fabs([sample[@"jointAngles"][@"yaw"] doubleValue] - 123.45) < 0.001 && [sample[@"jointAngles"][@"pitch"] doubleValue] == -1, @"joint scales and signs");
        Require(RSDecodeTelemetry([NSMutableData dataWithLength:5]) == nil, @"short feedback rejected");
        RSFrameQueue *queue = [RSFrameQueue new]; [queue enqueue:stop]; [queue enqueue:RSRecenterFrame(2)];
        Require([queue nextChunk].length == 20, @"20-byte chunks"); [queue discardPending]; [queue enqueue:stop];
        Require([queue nextChunk].length == 2 && [queue nextChunk].length == 20 && [queue nextChunk].length == 2 && queue.empty, @"stop keeps started frame and discards pending motion");
        RSPositionLoop *loop = [RSPositionLoop new]; NSError *error;
        Require(![loop begin:@{@"pan": @181} at:0 error:&error], @"invalid target rejected");
        Require([loop begin:@{@"pan": @5, @"tilt": @5, @"roll": @(-4)} at:0 error:&error], @"start position");
        Require(![loop begin:@{@"pan": @3} at:0 error:&error], @"position conflict rejected");
        Require([[loop step:0.1] isEqualToString:@"waiting"], @"wait next feedback");
        [loop feedback:@{@"yaw": @4.5, @"pitch": @0, @"roll": @0} at:0.2];
        Require([[loop step:0.2] isEqualToString:@"moving"] && [loop.velocity[@"pan"] doubleValue] == 0 && [loop.velocity[@"tilt"] doubleValue] < 0 && [loop.velocity[@"roll"] doubleValue] < 0, @"per-axis tolerance and direction");
        [loop feedback:@{@"yaw": @4.5, @"pitch": @4.5, @"roll": @(-3.5)} at:1];
        Require([[loop step:1] isEqualToString:@"arrived"] && !loop.active, @"arrived and neutral");
        [loop begin:@{@"pan": @(-179)} at:0 error:&error]; [loop feedback:@{@"yaw": @179, @"pitch": @0, @"roll": @0} at:0.1]; [loop step:0.1];
        Require([loop.velocity[@"pan"] doubleValue] > 0, @"Pan shortest wrap"); [loop cancel];
        Require(!loop.active && [loop.velocity[@"pan"] doubleValue] == 0, @"cancel clears motion");
        [loop begin:@{@"pan": @5} at:0 error:&error];
        Require([[loop step:3] isEqualToString:@"telemetryTimeout"], @"feedback watchdog");
        [loop begin:@{@"pan": @5} at:0 error:&error];
        Require([[loop step:30] isEqualToString:@"timeout"], @"total deadline distinct");
        RSTrajectoryLoop *trajectory = [RSTrajectoryLoop new];
        Require(![trajectory begin:@[@{@"timeMs": @1}, @{@"timeMs": @2}] interpolation:@"linear" at:0 error:&error], @"trajectory starts at zero");
        Require(![trajectory begin:@[@{@"timeMs": @0}, @{@"timeMs": @0}] interpolation:@"linear" at:0 error:&error], @"trajectory times increase");
        Require(![trajectory begin:@[@{@"timeMs": @0, @"pan": @2}, @{@"timeMs": @10}] interpolation:@"linear" at:0 error:&error], @"trajectory range validation");
        Require(![trajectory begin:@[@{@"timeMs": @0, @"pan": @YES}, @{@"timeMs": @10}] interpolation:@"linear" at:0 error:&error], @"trajectory rejects boolean axis values");
        NSMutableDictionary *point = [@{@"timeMs": @0, @"pan": @1} mutableCopy];
        Require([trajectory begin:@[point, @{@"timeMs": @100, @"tilt": @(-1)}] interpolation:@"linear" at:0 error:&error], @"trajectory begins");
        point[@"pan"] = @(-1); [trajectory step:.025];
        Require(fabs([trajectory.velocity[@"pan"] doubleValue] - .75) < 1e-9 && fabs([trajectory.velocity[@"tilt"] doubleValue] + .25) < 1e-9, @"trajectory input copied and axes interpolate");
        Require([[trajectory step:.1] isEqualToString:@"done"] && !trajectory.active, @"trajectory ends instead of holding final velocity");
        [trajectory begin:@[@{@"timeMs": @0, @"pan": @1}, @{@"timeMs": @100}] interpolation:@"smoothstep" at:0 error:&error]; [trajectory step:.025];
        Require(fabs([trajectory.velocity[@"pan"] doubleValue] - .84375) < 1e-9, @"smoothstep interpolation"); [trajectory cancel];
        [trajectory begin:@[@{@"timeMs": @0, @"pan": @1}, @{@"timeMs": @100}] interpolation:@"step" at:0 error:&error]; [trajectory step:.099];
        Require([trajectory.velocity[@"pan"] doubleValue] == 1, @"step interpolation holds preceding frame"); [trajectory cancel];
        [trajectory begin:@[@{@"timeMs": @0, @"pan": @1}, @{@"timeMs": @1000}] interpolation:@"linear" at:0 error:&error];
        Require([[trajectory step:.6] isEqualToString:@"overrun"] && !trajectory.active && [trajectory.velocity[@"pan"] doubleValue] == 0, @"late scheduler cancels rather than bursts");
        NSDictionary *orientation = RSOrientation(@[@(M_SQRT1_2), @0, @0, @(M_SQRT1_2)], @"wxyz", NO);
        Require(fabs([orientation[@"euler"][@"yaw"] doubleValue] - 90) < 1e-9 && ![orientation[@"deviceConventionVerified"] boolValue], @"quaternion conversion is mathematical with explicit unverified convention");
        Require(fabs([RSOrientation(@[@0, @0, @(M_SQRT1_2), @(M_SQRT1_2)], @"xyzw", YES)[@"euler"][@"yaw"] doubleValue] + 90) < 1e-9, @"quaternion ordering and conjugation");
        Require(!RSOrientation(@[@0, @0, @0, @0], @"wxyz", NO) && !RSOrientation(@[@1, @0, @0, @0], @"unknown", NO), @"quaternion rejects zero norm and unspecified order");
        [decoder reset]; NSArray *absolute = [decoder push:RSResearchAbsoluteFrame(1, @{@"pan": @45}, 20)];
        Require([Hex(absolute.firstObject[@"payload"]) isEqualToString:@"c201000000000d14"], @"RS 3 absolute-angle vector and omitted-axis mask");
        [decoder reset]; NSArray *rate = [decoder push:RSResearchRateFrame(1, @{@"pan": @2}, NO)];
        Require([Hex(rate.firstObject[@"payload"]) isEqualToString:@"14000000000080"], @"RS 3 native-rate vector");
        [decoder reset]; NSArray *sleep = [decoder push:RSResearchSleepFrame(1, @"rs3mini", YES)];
        Require([Hex(sleep.firstObject[@"payload"]) isEqualToString:@"230111"] && [sleep.firstObject[@"sequence"] intValue] == 1, @"RS 3 Mini sleep vector and frame metadata");
        Require(!RSResearchAbsoluteFrame(1, @{@"pan": @181}, 20) && !RSResearchQueryFrame(1, @"calibrate"), @"research command ranges and query allowlist");
        NSMutableData *battery = [NSMutableData dataWithLength:21]; ((uint8_t *)battery.mutableBytes)[20] = 67;
        NSDictionary *message = @{@"sender": @0xe5, @"receiver": @2, @"commandSet": @0x0d, @"commandId": @2, @"payload": battery};
        Require([RSDecodeResearchStatus(message, @"rs3mini")[@"batteryPercent"] intValue] == 67 && RSDecodeResearchStatus(message, @"rs3")[@"batteryPercent"] == NSNull.null, @"battery interpretation is model-specific");
        Require(!RSDecodeResearchStatus(@{@"sender": @0xe5, @"receiver": @2, @"commandSet": @4, @"commandId": @0x66, @"payload": [NSData dataWithBytes:(uint8_t[]){1, 0x22, 2, 0} length:4]}, @"rs3mini"), @"malformed status TLV rejected");
        NSDictionary *(^parameterMessage)(NSUInteger, NSData *, NSUInteger) = ^NSDictionary *(NSUInteger command, NSData *payload, NSUInteger flags) {
            return @{@"sender": @4, @"receiver": @2, @"commandSet": @4, @"commandId": @(command), @"flags": @(flags), @"payload": payload};
        };
        NSDictionary *params = RSDecodeResearchStatus(parameterMessage(0x10, [NSData dataWithBytes:(uint8_t[]){0,18,1,0,18,2,255,255,255} length:9], 0x80), @"rs3");
        Require([params[@"parameters"] count] == 3 && [params[@"parameters"][2][@"errorCode"] intValue] == -1, @"parameter responses preserve duplicates and signed retrieval errors");
        Require([params[@"parameters"][1][@"rawHex"] isEqualToString:@"ffff"] && ![params[@"deviceVerified"] boolValue], @"parameter values remain raw and unverified");
        Require([RSDecodeResearchStatus(parameterMessage(0x0f, [NSData dataWithBytes:(uint8_t[]){7} length:1], 0x80), @"rs3")[@"statusCode"] intValue] == 7, @"parameter write ACK retains raw status without writing");
        for (NSData *bad in @[[NSData data], [NSData dataWithBytes:(uint8_t[]){0,18} length:2], [NSData dataWithBytes:(uint8_t[]){0,18,0} length:3], [NSData dataWithBytes:(uint8_t[]){0,18,3,1,2,3} length:6], [NSData dataWithBytes:(uint8_t[]){0,18,2,1} length:4]])
            Require(!RSDecodeResearchStatus(parameterMessage(0x10, bad, 0x80), @"rs3"), @"malformed parameter payload rejected");
        Require(!RSDecodeResearchStatus(parameterMessage(0x10, [NSData dataWithBytes:(uint8_t[]){0,18,1,0} length:4], 0x40), @"rs3"), @"parameter response requires response bit");
        printf("Native protocol, reassembly, stop queue and motion-core checks: %lu passed\n", (unsigned long)assertions);
    }
    return 0;
}
