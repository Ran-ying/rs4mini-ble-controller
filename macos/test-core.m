#import "RSControlCore.h"
#include <math.h>

static NSUInteger assertions;
static void Require(BOOL value, NSString *message) { assertions++; if (!value) { fprintf(stderr, "FAIL: %s\n", message.UTF8String); exit(1); } }
static NSString *Hex(NSData *data) { NSMutableString *hex = [NSMutableString string]; for (NSUInteger i = 0; i < data.length; i++) [hex appendFormat:@"%02x", ((const uint8_t *)data.bytes)[i]]; return hex; }
static NSData *ProgramHex(NSString *hex) {NSMutableData *data=[NSMutableData data];for(NSUInteger i=0;i<hex.length;i+=2){unsigned value=0;[[NSScanner scannerWithString:[hex substringWithRange:NSMakeRange(i,2)]] scanHexInt:&value];uint8_t byte=value;[data appendBytes:&byte length:1];}return data;}
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
        NSDictionary *calRequest = [[RSFrameDecoder new] push:RSAppAutoTuneFrame(1,@YES)].firstObject;
        Require([calRequest[@"flags"] intValue] == 0 && [Hex(calRequest[@"payload"]) isEqualToString:@"000101"] && RSAppAutoTuneFrame(1,@1) == nil, @"HG702 auto-tune request has no ACK and strict boolean action");
        Require([Hex([[RSFrameDecoder new] push:RSAppAutoTuneFrame(1,@NO)].firstObject[@"payload"]) isEqualToString:@"000100"], @"false auto-tune request vector does not prove physical stop");
        NSDictionary *calRecords = RSDecodeAppCalibrationRecords([NSData dataWithBytes:(uint8_t[]){1,0,0,3,2,100,99,7,1,44} length:10]);
        Require([calRecords[@"state"] isEqualToString:@"Complete"] && [calRecords[@"percent"] intValue] == 100 && [calRecords[@"records"][1][@"rawHex"] isEqualToString:@"026463"], @"calibration records retain unknown tags and known record tail");
        NSDictionary *unknownCal = RSDecodeAppCalibrationRecords([NSData dataWithBytes:(uint8_t[]){0,2,77,255} length:4]);
        Require(unknownCal[@"state"] == NSNull.null && unknownCal[@"percent"] == NSNull.null && [unknownCal[@"rawPercent"] intValue] == 255, @"unknown calibration state and invalid percent remain raw");
        NSMutableData *wideCalRecord = [NSMutableData dataWithLength:130]; ((uint8_t *)wideCalRecord.mutableBytes)[1] = 128;
        Require(!RSDecodeAppCalibrationRecords(wideCalRecord) && !RSDecodeAppCalibrationRecords([NSData dataWithBytes:(uint8_t[]){0,1,2} length:3]) && !RSDecodeAppCalibrationRecords([NSData dataWithBytes:(uint8_t[]){0,2,1} length:3]), @"truncated calibration records reject");
        Require(RSDecodeAppCalibrationRecords([NSData data])[@"rawState"] == NSNull.null && RSDecodeAppCalibrationRecords([NSData dataWithBytes:(uint8_t[]){1,0} length:2])[@"rawState"] == NSNull.null, @"no known calibration record does not synthesize zero state");
        NSDictionary *duplicateCal = RSDecodeAppCalibrationRecords([NSData dataWithBytes:(uint8_t[]){0,2,1,10,0,2,3,20} length:8]);
        Require([duplicateCal[@"state"] isEqualToString:@"Failure"] && [duplicateCal[@"percent"] intValue] == 20, @"last complete calibration record wins");
        NSArray *motorRows=RSAppMotorSelection(@{@"axis":@"yaw"}); NSMutableArray *motorContext=[NSMutableArray array];
        for (NSDictionary *row in motorRows) [motorContext addObject:@{@"index":row[@"index"],@"size":@1}];
        NSDictionary *motorQuery=[[RSFrameDecoder new] push:RSAppMotorReadFrame(1,motorContext)].firstObject;
        Require([motorQuery[@"commandId"] intValue]==0x32 && [Hex(motorQuery[@"payload"]) isEqualToString:@"0205080b"],@"motor query uses separate namespace and explicit named order");
        NSDictionary *motorWrite=[[RSFrameDecoder new] push:RSAppMotorWriteFrame(1,@[@{@"index":@1,@"size":@1}],@50)].firstObject;
        Require([motorWrite[@"commandId"] intValue]==0x31 && [Hex(motorWrite[@"payload"]) isEqualToString:@"010132"],@"motor write scalar source vector");
        Require(!RSAppMotorWriteSpec(@{@"axis":@"pitch",@"parameter":@"stiffness",@"value":@4}) && !RSAppMotorWriteSpec(@{@"axis":@"pitch",@"parameter":@"preControl",@"value":@YES}) && !RSAppMotorSelection(@{@"index":@0}),@"motor named writes reject unsafe source range and raw indexes");
        NSMutableDictionary *motorMessage=[appMessage mutableCopy]; motorMessage[@"commandId"]=@0x32; motorMessage[@"payload"]=[NSData dataWithBytes:(uint8_t[]){0,0,9,255} length:4];
        NSDictionary *motorResult=RSDecodeAppMotorReply(motorMessage,RSAppMotorSelection(@{@"axis":@"pitch",@"parameter":@"stiffness"}),&appError);
        Require([motorResult[@"values"][0][@"rawValue"] intValue]==255 && ![motorResult[@"values"][0][@"withinSourceRange"] boolValue] && [motorResult[@"parameters"][0][@"headerByte"] intValue]==9,@"motor read retains unknown value and raw header using external width");
        NSDictionary *balanceFrame=[[RSFrameDecoder new] push:RSAppBalanceStartFrame(1)].firstObject;
        Require([balanceFrame[@"commandId"] intValue]==0x0f && [Hex(balanceFrame[@"payload"]) isEqualToString:@"250140"],@"balance start uses common parameter namespace and fixed64");
        NSDictionary *balance=RSAppBalanceFields(0x9b);
        Require([balance[@"state"] isEqualToString:@"FINISH"] && [balance[@"axisResults"][@"roll"][@"result"] isEqualToString:@"PASS"] && [balance[@"axisResults"][@"pitch"][@"result"] isEqualToString:@"MARGINAL"] && [balance[@"axisResults"][@"yaw"][@"result"] isEqualToString:@"FAIL"],@"balance status and axis bits source vector");
        Require(RSAppBalanceFields(0)[@"axisResults"][@"yaw"][@"result"]==NSNull.null && ![RSAppBalanceFields(0x90)[@"axisFieldsValid"] boolValue] && [RSAppBalanceFields(255)[@"state"] isEqualToString:@"ERROR"],@"zero fields stay invalid and unknown values remain raw");
        NSDictionary *systemCalibrationFrame=[[RSFrameDecoder new] push:RSAppSystemCalibrationStartFrame(1)].firstObject;
        Require([systemCalibrationFrame[@"commandId"] intValue]==0x0f && [Hex(systemCalibrationFrame[@"payload"]) isEqualToString:@"240101"],@"system calibration starts through index36 common namespace");
        Require([RSAppSystemCalibrationFields(0)[@"state"] isEqualToString:@"DEFAULT"] && [RSAppSystemCalibrationFields(1)[@"state"] isEqualToString:@"START"] && [RSAppSystemCalibrationFields(2)[@"state"] isEqualToString:@"FAIL"] && [RSAppSystemCalibrationFields(3)[@"state"] isEqualToString:@"SUCCESS"],@"system calibration reply enum is not restricted to write range");
        Require(RSAppSystemCalibrationFields(255)[@"state"]==NSNull.null && [RSAppSystemCalibrationFields(255)[@"rawValue"] intValue]==255,@"unknown system calibration stays raw instead of indexing enum out of bounds");
        Require([RSAppSettingsSchema(RSAppModeKind(@"follow",@"acceleration"))[@"index"] intValue]==71 && [RSAppSettingsSchema(RSAppModeKind(@"rc",@"smoothing"))[@"index"] intValue]==69 && !RSAppModeKind(@"follow",@"PF"),@"mode groups use named source records not PF presets");
        NSDictionary *modeFrame=[[RSFrameDecoder new] push:RSAppSettingsFrame(1,@"followSpeed",@{@"yaw":@"custom"},@255)].firstObject;
        Require([Hex(modeFrame[@"payload"]) isEqualToString:@"41013f"],@"mode update preserves other axes and opaque low bits");
        NSDictionary *modeReply=RSDecodeAppSettings(@{@"parameters":@[@{@"rawHex":@"9b"}]},@"rcSpeed");
        Require([modeReply[@"settings"][@"pitch"] isEqualToString:@"middle"] && [modeReply[@"settings"][@"roll"] isEqualToString:@"low"] && [modeReply[@"settings"][@"yaw"] isEqualToString:@"middle"] && [modeReply[@"unknownBits"] intValue]==3,@"packed axis shifts and source enum decode");
        Require(!RSAppSettingsPatch(@"followSpeed",@{@"yaw":@1}) && !RSAppSettingsPatch(@"followSpeed",@{@"pan":@"low"}) && !RSAppSettingsPatch(@"followSpeed",@{}),@"mode patch rejects numeric value unknown axis and empty update");
        Require(RSAppTuningSelection(@"follow",nil).count==9 && RSAppTuningSelection(@"rc",nil).count==9 && [RSAppTuningSelection(@"follow",@{@"axis":@"roll",@"parameter":@"acceleration"})[0][@"index"] intValue]==16,@"ordinary numeric catalogs use source names and indexes");
        NSDictionary *numericWrite=[[RSFrameDecoder new] push:RSAppTuningWriteFrame(1,@[@{@"index":@3,@"size":@2}],@100)].firstObject;
        Require([Hex(numericWrite[@"payload"]) isEqualToString:@"03026400"] && !RSAppTuningWriteFrame(1,@[@{@"index":@3,@"size":@1}],@100) && !RSAppTuningWriteFrame(1,@[@{@"index":@72,@"size":@1}],@2),@"numeric write uses metadata width and excludes input source");
        NSMutableDictionary *numericMessage=[appMessage mutableCopy];numericMessage[@"payload"]=[NSData dataWithBytes:(uint8_t[]){0,3,9,0x34,0x12} length:5];numericMessage[@"commandId"]=@0x10;
        NSDictionary *numericResult=RSDecodeAppTuningReply(numericMessage,RSAppTuningSelection(@"follow",@{@"axis":@"pitch",@"parameter":@"speed"}),&appError);
        Require([numericResult[@"values"][0][@"rawValue"] intValue]==4660 && ![numericResult[@"values"][0][@"withinSourceRange"] boolValue] && [numericResult[@"parameters"][0][@"headerByte"] intValue]==9 && ![numericResult[@"activePresetVerified"] boolValue],@"numeric decode retains unsigned little-endian feedback outside source range");
        Require([Hex([[[RSFrameDecoder new] push:RSAppTuningWriteFrame(1,@[@{@"index":@26,@"size":@1}],@100)] firstObject][@"payload"]) isEqualToString:@"1a0164"] && !RSAppTuningWriteSpec(@"follow",@{@"axis":@"pitch",@"parameter":@"speed",@"value":@0}) && !RSAppTuningWriteSpec(@"rc",@{@"axis":@"pitch",@"parameter":@"speed",@"value":@YES}),@"one-byte numeric fields retain independent ranges and boolean rejection");
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
        NSDictionary *message = @{@"sender": @0xe5, @"receiver": @2, @"commandSet": @0x0d, @"commandId": @2, @"flags": @0, @"payload": battery};
        Require([RSDecodeResearchStatus(message, @"rs3mini")[@"batteryPercent"] intValue] == 67 && RSDecodeResearchStatus(message, @"rs3")[@"batteryPercent"] == NSNull.null, @"battery interpretation is model-specific");
        Require(!RSDecodeResearchStatus(@{@"sender": @0xe5, @"receiver": @2, @"commandSet": @4, @"commandId": @0x66, @"flags": @0, @"payload": [NSData dataWithBytes:(uint8_t[]){1, 0x22, 2, 0} length:4]}, @"rs3mini"), @"malformed status TLV rejected");
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
        NSArray *standaloneRows=RSAppStandaloneSelection(nil);
        Require(standaloneRows.count==6 && !RSAppStandaloneSelection(@{@"axis":@"pan"}) && !RSAppStandaloneWriteSpec(@{@"axis":@"pitch",@"parameter":@"speed",@"value":@100}), @"standalone named catalog requires explicit source");
        NSArray *standaloneContext=@[@{@"index":@72,@"size":@1},@{@"index":@80,@"size":@2}];
        [decoder reset];NSDictionary *standaloneFrame=[decoder push:RSAppStandaloneWriteFrame(5,standaloneContext,@100)].firstObject;
        Require([Hex(standaloneFrame[@"payload"]) isEqualToString:@"48010250026400"] && !RSAppStandaloneWriteFrame(5,@[@{@"index":@72,@"size":@1},@{@"index":@3,@"size":@2}],@100), @"standalone allows only paired source2 and audited value in one packet");
        Require(!RSAppStandaloneWriteFrame(5,standaloneContext,@YES) && !RSAppStandaloneWriteSpec(@{@"inputSource":@3,@"axis":@"pitch",@"parameter":@"speed",@"value":@100}), @"standalone refuses boolean values and other sources");
        NSDictionary *standaloneReply=RSDecodeAppStandaloneReply(parameterMessage(0x10,[NSData dataWithBytes:(uint8_t[]){0,72,9,255,80,9,0x34,0x12} length:8],0x80),RSAppStandaloneSelection(@{@"axis":@"pitch",@"parameter":@"speed"}),&error);
        Require([standaloneReply[@"inputSourceRaw"] intValue]==255 && [standaloneReply[@"values"][0][@"rawValue"] intValue]==4660 && ![standaloneReply[@"values"][0][@"withinSourceRange"] boolValue] && ![standaloneReply[@"activePresetVerified"] boolValue], @"standalone preserves unknown source and unsigned little endian value");
        NSData *abnormalBody=[NSData dataWithBytes:(uint8_t[]){4,255,62,103,1,170,187} length:7];
        NSString *programFixture=[[@__FILE__ stringByDeletingLastPathComponent] stringByDeletingLastPathComponent];
        programFixture=[programFixture stringByAppendingPathComponent:@"node/test/fixtures/program-status.json"];
        NSArray *programVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:programFixture] options:0 error:nil];
        Require(programVectors.count==5,@"load shared program contract vectors");
        for(NSDictionary *vector in programVectors){
            NSDictionary *program=RSDecodeAppProgramStatusNotification(parameterMessage([vector[@"commandId"] unsignedIntegerValue],ProgramHex(vector[@"bodyHex"]),0));
            BOOL matches=program!=nil && [program[@"bodyHex"] isEqual:vector[@"bodyHex"]] && ![program[@"programCorrelationVerified"] boolValue];
            for(NSString *key in vector[@"expected"])matches=matches && [program[key] isEqual:vector[@"expected"][key]];
            Require(matches,vector[@"name"]);
        }
        for(NSString *bad in @[@"",@"00",@"0062",@"006204010203",@"006203010203",@"006280",@"00fe00620401"])
            Require(!RSDecodeAppProgramStatusNotification(parameterMessage(107,ProgramHex(bad),0)),@"program invalid TLV cannot publish partial snapshot");
        Require(!RSDecodeAppProgramStatusNotification(parameterMessage(56,[NSMutableData dataWithLength:3],0)) && !RSDecodeAppProgramStatusNotification(parameterMessage(100,[NSMutableData dataWithLength:4],0)),@"standalone program source requires complete fields");
        Require(!RSDecodeAppProgramStatusNotification(parameterMessage(107,ProgramHex(@"00620401020304"),128)) && !RSDecodeAppProgramStatusNotification(parameterMessage(107,ProgramHex(@"00620401020304"),1)),@"program ACK and encrypted payloads are separate");
        NSDictionary *immutableProgram=RSDecodeAppProgramStatusNotification(parameterMessage(107,ProgramHex(@"00620401020304"),64));BOOL programImmutable=NO;
        @try {[(NSMutableDictionary *)immutableProgram[@"records"][0][@"sourceValues"] setObject:@99 forKey:@"status"];} @catch(NSException *e){programImmutable=YES;}
        Require(programImmutable && [immutableProgram[@"records"][0][@"sourceValues"][@"status"] intValue]==1,@"native nested program snapshots are immutable");
        NSDictionary *abnormalStatus=RSDecodeAppSourceStatusNotification(parameterMessage(0x27,abnormalBody,0)),*abnormalValues=abnormalStatus[@"sourceValues"];
        Require(abnormalValues.count==22 && [abnormalValues[@"getGimbalGravity"] intValue]==3 && [abnormalValues[@"getSleepMode"] intValue]==1 && [abnormalValues[@"isMotorProtected"] boolValue],@"source abnormal fields preserve numeric and boolean getter semantics");
        Require([abnormalValues[@"isYawLocked"] boolValue] && ![abnormalValues[@"isGimbalLocked"] boolValue] && [abnormalStatus[@"bodyHex"] isEqualToString:@"04ff3e6701aabb"] && ![abnormalStatus[@"modelLayoutVerified"] boolValue],@"source composite excludes yaw and retains unknown/tail bytes without model claim");
        NSDictionary *batteryStatus=RSDecodeAppSourceStatusNotification(parameterMessage(0x33,[NSData dataWithBytes:(uint8_t[]){255,99} length:2],0));
        Require([batteryStatus[@"rawCapacityValue"] intValue]==255 && [batteryStatus[@"bodyHex"] isEqualToString:@"ff63"] && ![batteryStatus[@"deviceVerified"] boolValue],@"source battery keeps255 without clamp or physical percentage guarantee");
        Require(!RSDecodeAppSourceStatusNotification(parameterMessage(0x27,[NSMutableData dataWithLength:4],0)) && !RSDecodeAppSourceStatusNotification(parameterMessage(0x33,[NSData data],0)) && !RSDecodeAppSourceStatusNotification(parameterMessage(0x27,abnormalBody,128)) && !RSDecodeAppSourceStatusNotification(parameterMessage(0x33,[NSData dataWithBytes:(uint8_t[]){50} length:1],1)),@"source statuses reject short ACK and encrypted contexts");
        NSData *stickBody=[NSData dataWithBytes:(uint8_t[]){0,128,255,127,3,128,170,187} length:8];
        NSDictionary *stickStatus=RSDecodeAppHandheldStickNotification(parameterMessage(0x57,stickBody,0));
        Require([stickStatus[@"sourceStickX"] intValue]==-32768 && [stickStatus[@"sourceStickY"] intValue]==32767 && [stickStatus[@"rawStateWord"] intValue]==32771 && [stickStatus[@"unknownStateBits"] intValue]==32768,@"stick source is signed short LE with unknown word bits retained");
        Require([stickStatus[@"sourceTriggerPressed"] boolValue] && [stickStatus[@"sourceStickControlEnabled"] boolValue] && [stickStatus[@"bodyHex"] isEqualToString:@"0080ff7f0380aabb"] && ![stickStatus[@"axisMappingVerified"] boolValue],@"stick candidate owns complete source bytes without physical axis claim");
        Require(!RSDecodeAppHandheldStickNotification(parameterMessage(0x57,stickBody,128)) && !RSDecodeAppHandheldStickNotification(parameterMessage(0x57,stickBody,1)) && !RSDecodeAppHandheldStickNotification(parameterMessage(0x57,[NSMutableData dataWithLength:5],0)),@"stick candidate rejects ACK encrypted and short source bodies");
        NSDictionary *oneBit=RSDecodeAppHandheldStickNotification(parameterMessage(0x57,[NSData dataWithBytes:(uint8_t[]){0,0,0,0,1,0} length:6],0));
        Require([oneBit[@"sourceTriggerPressed"] boolValue] && ![oneBit[@"sourceStickControlEnabled"] boolValue],@"trigger and control enabled are separate source bits");
        NSMutableData *userBody=[NSMutableData dataWithLength:78];uint8_t *userBytes=userBody.mutableBytes;userBytes[0]=99;userBytes[2]=2;userBytes[9]=0x34;userBytes[10]=0x12;userBytes[63]=255;userBytes[64]=255;userBytes[73]=255;
        NSDictionary *userStatus=RSDecodeAppUserParameterNotification(parameterMessage(0x24,userBody,0));
        Require([userStatus[@"values"] count]==17 && [userStatus[@"preset"][@"rawValue"] intValue]==2 && userStatus[@"preset"][@"sourceEnum"]==NSNull.null,@"fixed user layout has17 source getters and preserves unknown preset2");
        NSMutableDictionary *byName=[NSMutableDictionary dictionary];for(NSDictionary *row in userStatus[@"values"])byName[row[@"sourceGetter"]]=row;
        Require([byName[@"getYawSpeed"][@"rawValue"] intValue]==4660 && [byName[@"getRollAccel"][@"rawValue"] intValue]==65535 && [byName[@"getRollSmoothTrack"][@"rawValue"] intValue]==255,@"user fixed layout preserves unsigned two-byte and raw enabled values");
        Require(!RSDecodeAppUserParameterNotification(parameterMessage(0x24,userBody,0x80)) && !RSDecodeAppUserParameterNotification(parameterMessage(0x24,userBody,1)) && !RSDecodeAppUserParameterNotification(parameterMessage(0x24,[NSMutableData dataWithLength:73],0)),@"fixed layout rejects ACK encrypted and short payload without zero fill");
        userBytes[9]=0;Require([byName[@"getYawSpeed"][@"rawHex"] isEqualToString:@"3412"] && [userStatus[@"bodyHex"] length]==156 && ![userStatus[@"modelLayoutVerified"] boolValue],@"fixed snapshot owns immutable strings and retains all unknown bytes");
        [decoder reset];NSDictionary *handleQuery=[decoder push:RSAppHandleQueryFrame(9)].firstObject;
        Require([handleQuery[@"commandId"] intValue]==0x36 && [handleQuery[@"payload"] length]==0 && [handleQuery[@"flags"] intValue]==0x40,@"handle query empty body and ACK envelope");
        NSDictionary *handle=RSDecodeAppHandleReply(parameterMessage(0x36,[NSData dataWithBytes:(uint8_t[]){0,7,1,0,255,3,2,3,254,99} length:10],0x80),&error);
        Require([handle[@"values"] count]==8 && [handle[@"values"][0][@"rawValue"] intValue]==7 && [handle[@"values"][3][@"rawValue"] intValue]==255 && ![handle[@"values"][5][@"sourceBit0"] boolValue] && [handle[@"values"][6][@"sourceBit0"] boolValue],@"handle raw values and bit0 remain separate from return status");
        Require(!RSDecodeAppHandleReply(parameterMessage(0x36,[NSMutableData dataWithLength:8],0x80),&error),@"short handle body rejected rather than padded");
        NSDictionary *fine=RSAppFineTuneSpec(@{@"axis":@"pitch",@"adjustmentDegrees":@(-1.29)});
        Require([fine[@"encodedTenths"] intValue]==-12 && [fine[@"axisWire"] intValue]==2,@"fine source float32 truncate and Pitch wire2");
        [decoder reset];NSDictionary *fineFrame=[decoder push:RSAppFineTuneFrame(4,@[@{@"index":@2,@"size":@1}],fine[@"encodedTenths"])].firstObject;
        Require([fineFrame[@"commandId"] intValue]==7 && [Hex(fineFrame[@"payload"]) isEqualToString:@"f402"],@"fine two-byte request matches source signed value/axis order");
        Require([RSAppFineTuneSpec(@{@"axis":@"roll",@"adjustmentDegrees":@(1.999999999)})[@"encodedTenths"] intValue]==20,@"fine float32 input conversion precedes scaling");
        Require(!RSAppFineTuneSpec(@{@"axis":@"yaw",@"adjustmentDegrees":@1}) && !RSAppFineTuneSpec(@{@"axis":@"roll",@"adjustmentDegrees":@YES}) && !RSAppFineTuneFrame(3,@[@{@"index":@4,@"size":@1}],@1),@"fine rejects unprovenYaw action boolean and raw axis4");
        for(NSArray *row in @[@[@"dualChannelMode",@0,@"00ffffffffffffff"],@[@"tiltDirection",@1,@"ff01ffffffffffff"],@[@"panDirection",@1,@"ffff01ffffffffff"]]) {
            NSDictionary *spec=RSAppHandleWriteSpec(@{@"setting":row[0],@"value":row[1]});[decoder reset];NSDictionary *f=[decoder push:RSAppHandleWriteFrame(9,@[@{@"index":spec[@"offset"],@"size":@1}],spec[@"requestedValue"])].firstObject;
            Require([f[@"commandId"] intValue]==0x35 && [f[@"flags"] intValue]==0x40 && [Hex(f[@"payload"]) isEqualToString:row[2]],@"handle single-field source frame with fresh FF defaults");
        }
        Require(!RSAppHandleWriteSpec(@{@"setting":@"panDirection",@"value":@YES}) && !RSAppHandleWriteSpec(@{@"setting":@"profile",@"value":@1}) && !RSAppHandleWriteSpec(@{@"setting":@"panDirection",@"value":@255}) && !RSAppHandleWriteSpec(@{@"setting":@"panDirection",@"value":@1,@"index":@2}),@"handle rejects booleans unknown keys fields and FF as explicit value");
        Require(!RSAppHandleWriteFrame(9,@[@{@"index":@3,@"size":@1}],@1) && !RSAppHandleWriteFrame(9,@[@{@"index":@0,@"size":@2}],@1) && !RSAppHandleWriteFrame(9,@[@{@"index":@0,@"size":@1}],@YES),@"handle frame has private exact field/value allowlist");
        [decoder reset];NSDictionary *resetFrame=[decoder push:RSAppFactoryResetFrame(3,@"HG724")].firstObject;
        Require([resetFrame[@"commandId"] intValue]==0x13 && [resetFrame[@"flags"] intValue]==0x40 && [Hex(resetFrame[@"payload"]) isEqualToString:@"010001"],@"factory reset source HG724 branch body and ACK envelope");
        Require(RSAppFactoryResetSpec(@{@"sourcePlatform":@"HG724"}) && !RSAppFactoryResetSpec(@{}) && !RSAppFactoryResetSpec(@{@"sourcePlatform":@103}) && !RSAppFactoryResetSpec(@{@"sourcePlatform":@"HG724",@"payload":@[]}),@"reset requires named source platform not enum ordinal or arbitrary body");
        Require(!RSAppFactoryResetFrame(3,@"HG702") && !RSAppFactoryResetFrame(3,nil),@"reset codec does not reuse another platform empty branch");
        for(NSArray *row in @[@[@"ThreeAxis",@0],@[@"TwoAxis",@8],@[@"Roll360",@16],@[@"ThreeDRoll360",@24]]) {
            NSDictionary *spec=RSAppAxisModeSpec(@{@"sourceMode":row[0]});[decoder reset];NSDictionary *f=[decoder push:RSAppAxisModeWriteFrame(3,@[@{@"index":@34,@"size":@1}],spec[@"requestedRawValue"])].firstObject;
            Require([f[@"commandId"] intValue]==15 && [f[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){34,1,[row[1] unsignedCharValue]} length:3]],@"axis source enum uses shifted parameter34 not motor35");
        }
        NSDictionary *axisRead=RSDecodeAppAxisModeReply(parameterMessage(16,[NSData dataWithBytes:(uint8_t[]){0,34,9,255} length:4],128),&error);
        Require([axisRead[@"rawValue"] intValue]==255 && [axisRead[@"unknownBits"] intValue]==231 && [axisRead[@"sourceMode"] isEqualToString:@"ThreeDRoll360"] && ![axisRead[@"modelLayoutVerified"] boolValue],@"axis source read mask preserves raw unknown bits");
        Require(!RSAppAxisModeSpec(@{@"sourceMode":@"FPV"}) && !RSAppAxisModeSpec(@{@"sourceMode":@24}) && !RSAppAxisModeSpec(@{@"sourceMode":@"ThreeAxis",@"value":@64}) && !RSAppAxisModeWriteFrame(3,@[@{@"index":@35,@"size":@1}],@24) && !RSAppAxisModeWriteFrame(3,@[@{@"index":@34,@"size":@1}],@YES),@"axis rejects mode aliases raw overrides motor context and boolean");
        Require(!RSDecodeAppAxisModeReply(parameterMessage(16,[NSData dataWithBytes:(uint8_t[]){0,35,9,24} length:4],128),&error),@"axis read rejects wrong parameter context");
        Require(RSAppSmoothTrackSelection(@{}).count==3 && [RSAppSmoothTrackSelection(@{@"axis":@"pitch"})[0][@"index"] intValue]==18,@"smooth query selects canonical three axes or named one");
        for(NSArray *row in @[@[@{@"roll":@YES,@"yaw":@YES,@"pitch":@YES},@"110101120101130101"],@[@{@"roll":@NO,@"yaw":@YES},@"110101130100"],@[@{@"pitch":@NO},@"120100"]]) {
            NSDictionary *spec=RSAppSmoothTrackSpec(@{@"axes":row[0]});[decoder reset];NSDictionary *f=[decoder push:RSAppSmoothTrackWriteFrame(4,spec[@"context"],spec[@"bits"])].firstObject;
            Require([f[@"commandId"] intValue]==15 && [Hex(f[@"payload"]) isEqualToString:row[1]],@"smooth patch emits one canonical frame without omitted-axis defaults");
        }
        Require(!RSAppSmoothTrackSpec(@{@"axes":@{}}) && !RSAppSmoothTrackSpec(@{@"axes":@{@"yaw":@1}}) && !RSAppSmoothTrackSelection(@{@"axis":@"pan"}) && !RSAppSmoothTrackWriteFrame(4,@[@{@"index":@17,@"size":@1}],@2),@"smooth rejects empty numeric axes and unused bitmask bits");
        NSDictionary *smoothRead=RSDecodeAppSmoothTrackReply(parameterMessage(16,[NSData dataWithBytes:(uint8_t[]){0,17,9,1,18,9,3,19,9,255} length:10],128),RSAppSmoothTrackSelection(@{}),&error);
        Require([smoothRead[@"values"][0][@"enabled"] boolValue] && smoothRead[@"values"][1][@"enabled"]==NSNull.null && ![smoothRead[@"values"][1][@"sourceEnabled"] boolValue] && [smoothRead[@"values"][2][@"rawValue"] intValue]==255,@"smooth preserves invalid raw values separately from source equality conversion");
        Require(!RSDecodeAppSmoothTrackReply(parameterMessage(16,[NSData dataWithBytes:(uint8_t[]){0,18,9,1} length:4],128),RSAppSmoothTrackSelection(@{@"axis":@"yaw"}),&error),@"smooth read rejects wrong index rather than mapping by position");
        Require([RSAppProfileValueContext(@"userProfile")[0][@"index"] intValue]==0 && [RSAppProfileValueContext(@"workMode")[0][@"index"] intValue]==62,@"profile and work have distinct contexts including zero index");
        for(NSArray *row in @[@[@"userProfile",@{@"sourceProfileValue":@0},@"000100"],@[@"userProfile",@{@"sourceProfileValue":@5},@"000105"],@[@"workMode",@{@"sourceMode":@"Free"},@"3e0100"],@[@"workMode",@{@"sourceMode":@"Flower"},@"3e0101"],@[@"workMode",@{@"sourceMode":@"Fpv"},@"3e0102"],@[@"workMode",@{@"sourceMode":@"Center"},@"3e0103"]]) {
            NSDictionary *spec=RSAppProfileValueSpec(row[0],row[1]);[decoder reset];NSDictionary *f=[decoder push:RSAppProfileValueWriteFrame(4,RSAppProfileValueContext(row[0]),spec[@"requestedRawValue"])].firstObject;
            Require([f[@"commandId"] intValue]==15 && [Hex(f[@"payload"]) isEqualToString:row[2]],@"profile/work named write golden vector");
        }
        NSDictionary *profileRead=RSDecodeAppProfileValueReply(parameterMessage(16,[NSData dataWithBytes:(uint8_t[]){0,0,9,5} length:4],128),@"userProfile",&error);
        Require([profileRead[@"rawValue"] intValue]==5 && profileRead[@"sourceUiName"]==NSNull.null && [profileRead[@"withinSourceRange"] boolValue] && ![profileRead[@"activePresetVerified"] boolValue],@"profile raw5 is in source range without invented UI or movement label");
        NSDictionary *workRead=RSDecodeAppProfileValueReply(parameterMessage(16,[NSData dataWithBytes:(uint8_t[]){0,62,9,128} length:4],128),@"workMode",&error);
        Require([workRead[@"rawValue"] intValue]==128 && workRead[@"sourceMode"]==NSNull.null && [workRead[@"withinSourceRange"] boolValue],@"work unknown enum inside source range is preserved");
        Require(!RSAppProfileValueSpec(@"userProfile",@{@"sourceProfileValue":@YES}) && !RSAppProfileValueSpec(@"userProfile",@{@"sourceProfileValue":@6}) && !RSAppProfileValueSpec(@"workMode",@{@"sourceMode":@"FPV"}) && !RSAppProfileValueWriteFrame(4,RSAppProfileValueContext(@"workMode"),@128),@"profile/work write forbids boolean unknown label or unnamed raw value");
        Require(!RSDecodeAppProfileValueReply(parameterMessage(16,[NSData dataWithBytes:(uint8_t[]){0,62,9,2} length:4],128),@"userProfile",&error),@"profile/work cross-domain read context rejected");
        for(NSString *name in @[@"track",@"timelapse",@"panorama"]) {
            NSDictionary *selected=RSAppProgramStatusSelection(@{@"program":name});
            NSData *request=RSAppProgramStatusRequestFrame(42,selected[@"requestedProgramCommandId"]);
            RSFrameDecoder *programDecoder=[RSFrameDecoder new];NSDictionary *decoded=[programDecoder push:request].lastObject;
            const uint8_t *requestBytes=[decoded[@"payload"] bytes];
            Require([decoded[@"commandId"] intValue]==107 && [decoded[@"flags"] intValue]==64 && [decoded[@"payload"] length]==4 && requestBytes[0]==0 && requestBytes[1]==2 && requestBytes[2]==1 && requestBytes[3]==[selected[@"requestedProgramCommandId"] intValue],@"single request uses fixed type2 and exact program tag");
        }
        Require(!RSAppProgramStatusSelection(@{@"program":@98}) && !RSAppProgramStatusSelection(@{@"program":@"track",@"requestType":@0}) && !RSAppProgramStatusSelection(@{@"program":@"delay"}) && !RSAppProgramStatusRequestFrame(1,@YES) && !RSAppProgramStatusRequestFrame(1,@25),@"single request rejects raw tags boolean and subscription options");
        NSString *subscriptionFixture=[[@__FILE__ stringByDeletingLastPathComponent] stringByDeletingLastPathComponent];
        subscriptionFixture=[subscriptionFixture stringByAppendingPathComponent:@"node/test/fixtures/program-subscription.json"];
        NSArray *subscriptionVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:subscriptionFixture] options:0 error:nil];
        Require(subscriptionVectors.count==6,@"load shared six subscription contract vectors");
        for(NSDictionary *vector in subscriptionVectors){
            NSDictionary *spec=@{@"program":vector[@"program"],@"enabled":vector[@"enabled"]};NSDictionary *selection=RSAppProgramStatusSubscriptionSelection(spec);
            NSDictionary *request=[[RSFrameDecoder new] push:RSAppProgramStatusSubscriptionFrame(45,spec)].lastObject;
            Require([Hex(request[@"payload"]) isEqualToString:vector[@"bodyHex"]] && [request[@"flags"] intValue]==64 && [selection[@"requestType"] isEqual:vector[@"requestType"]] && [selection[@"requestedProgramCommandId"] isEqual:vector[@"programCommand"]],@"fixed subscription body uses exact program wire value and source enable type");
        }
        Require(!RSAppProgramStatusSubscriptionSelection(@{@"program":@"track",@"enabled":@1}) && !RSAppProgramStatusSubscriptionFrame(1,@{@"program":@98,@"enabled":@YES}) && !RSAppProgramStatusSubscriptionFrame(1,@{@"program":@"track",@"enabled":@YES,@"requestType":@0}) && !RSAppProgramStatusSubscriptionSelection(@{@"program":@"track"}),@"subscription requires named program and exact boolean with no arbitrary type override");
        NSString *peripheralFixture=[[@__FILE__ stringByDeletingLastPathComponent] stringByDeletingLastPathComponent];peripheralFixture=[peripheralFixture stringByAppendingPathComponent:@"node/test/fixtures/peripheral-status.json"];
        NSArray *peripheralVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:peripheralFixture] options:0 error:nil];Require(peripheralVectors.count==6,@"load complete peripheral contracts");
        for(NSDictionary *v in peripheralVectors){NSDictionary *decoded=RSDecodeAppPeripheralNotification(parameterMessage(102,ProgramHex(v[@"bodyHex"]),0));BOOL matches=decoded!=nil && ![decoded[@"referenceFrameVerified"] boolValue];for(NSString *k in v[@"expected"])matches=matches && [decoded[k] isEqual:v[@"expected"][k]];Require(matches,v[@"name"]);}
        for(NSUInteger n=0;n<128;n++){NSMutableData *body=[NSMutableData dataWithBytes:(uint8_t[]){1,0,(uint8_t)n} length:3];NSMutableData *p=[NSMutableData dataWithLength:n];memset(p.mutableBytes,255,n);[body appendData:p];NSDictionary *decoded=RSDecodeAppPeripheralNotification(parameterMessage(102,body,0));Require([decoded[@"records"][0][@"sourceInt32"] intValue]==(n==0?0:n==3?16777215:-1),@"every source length keeps padding sign and low32 semantics");}
        for(NSNumber *badFlags in @[@128,@1])Require(!RSDecodeAppPeripheralNotification(parameterMessage(102,ProgramHex(@"0122020a00"),[badFlags intValue])),@"peripheral invalid ACK encrypted or flag envelope rejected");
        Require(!RSDecodeAppPeripheralNotification(parameterMessage(102,ProgramHex(@"01220200"),0)) && !RSDecodeAppPeripheralNotification(parameterMessage(102,ProgramHex(@"0122"),0)),@"peripheral truncation rejects entire frame");
        for(NSNumber *flagsValue in @[@(-128),@256,@NO]){NSMutableDictionary *badMessage=[parameterMessage(102,ProgramHex(@"0122020a00"),0) mutableCopy];badMessage[@"flags"]=flagsValue;Require(!RSDecodeAppPeripheralNotification(badMessage),@"peripheral rejects out-of-byte or boolean flags before masking");}
        NSDictionary *peripheralImmutable=RSDecodeAppPeripheralNotification(parameterMessage(102,ProgramHex(@"01150164"),0));BOOL immutableView=NO;@try{[(NSMutableDictionary *)peripheralImmutable[@"records"][0][@"sourceViews"][0] setObject:@99 forKey:@"value"];}@catch(NSException *e){immutableView=YES;}Require(immutableView,@"peripheral nested views immutable");
        NSArray *parameterSubscriptionVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[[[NSString stringWithUTF8String:__FILE__] stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"../node/test/fixtures/parameter-subscription.json"]] options:0 error:nil];
        Require(parameterSubscriptionVectors.count==4,@"shared named subscription vectors loaded");
        for(NSDictionary *v in parameterSubscriptionVectors){NSDictionary *spec=@{@"keys":v[@"keys"]};NSDictionary *selection=RSAppParameterSubscriptionSpec(spec);Require([selection[@"requestBodyHex"] isEqual:v[@"bodyHex"]],@"source subscription vector body");NSDictionary *f=[[RSFrameDecoder new] push:RSAppParameterSubscriptionFrame(123,spec)].firstObject;Require([f[@"receiver"] intValue]==229 && [f[@"flags"] intValue]==0 && [f[@"commandId"] intValue]==18,@"subscription fixed CENTER endpoint flags and valid CRC");}
        NSDictionary *allSubscriptions=RSAppParameterSubscriptionSpec(@{@"keys":RSAppParameterSubscriptionKeys()});
        Require(RSAppParameterSubscriptionKeys().count==152 && [allSubscriptions[@"payload"] length]==36 && [allSubscriptions[@"metadataConditionalKeys"] count]==21 && [allSubscriptions[@"modelConditionalKeys"] count]==2,@"full catalog and explicit metadata/model conditions");
        for(NSDictionary *bad in @[@{@"keys":@[]},@{@"keys":@[@0]},@{@"keys":@[@"unknown"]},@{@"keys":@[@"UserProfile"],@"enabled":@NO}])Require(!RSAppParameterSubscriptionSpec(bad),@"invalid selection cannot encode remote stop or raw fields");
        NSDictionary *subscriptionSent=RSAppParameterSubscriptionSent(allSubscriptions);Require(!subscriptionSent[@"payload"] && ![subscriptionSent[@"acknowledged"] boolValue] && ![subscriptionSent[@"targetRoutingVerified"] boolValue] && ![subscriptionSent[@"remoteSubscriptionStateVerified"] boolValue],@"local sent report cannot claim target acceptance");
        NSString *externalFixture=[[@__FILE__ stringByDeletingLastPathComponent] stringByDeletingLastPathComponent];externalFixture=[externalFixture stringByAppendingPathComponent:@"node/test/fixtures/external-device.json"];
        NSArray *externalVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:externalFixture] options:0 error:nil];Require(externalVectors.count==7,@"seven external-device shared vectors loaded");
        for(NSDictionary *v in externalVectors){NSDictionary *decoded=RSDecodeAppExternalDeviceNotification(parameterMessage(105,ProgramHex(v[@"bodyHex"]),0));Require([decoded[@"records"] isEqual:v[@"records"]] && [decoded[@"bodyHex"] isEqual:v[@"bodyHex"]],@"external source vector preserves signed axes, duplicates, unknowns and tail");Require(![decoded[@"unitVerified"] boolValue] && ![decoded[@"modelLayoutVerified"] boolValue] && ![decoded[@"referenceFrameVerified"] boolValue],@"external raw source fields cannot claim units or model mapping");}
        NSDictionary *externalDecoded=RSDecodeAppExternalDeviceNotification(parameterMessage(105,ProgramHex(@"0207010080ff7f0000"),0));
        Require(![externalDecoded[@"records"] isKindOfClass:NSMutableArray.class] && ![externalDecoded[@"records"][0] isKindOfClass:NSMutableDictionary.class] && ![externalDecoded[@"records"][0][@"speedControl"] isKindOfClass:NSMutableDictionary.class],@"native external snapshot is deeply immutable");
        for(NSString *bad in @[@"",@"02",@"0206000000000000",@"0207000000000000",@"0980",@"0207010080ff7f000009"])Require(!RSDecodeAppExternalDeviceNotification(parameterMessage(105,ProgramHex(bad),0)),@"bad external TLV or negative source length rejects entire frame");
        for(NSNumber *bad in @[@128,@1,@256,@(-1),@NO]){NSMutableDictionary *m=[parameterMessage(105,ProgramHex(@"0207010080ff7f0000"),0) mutableCopy];m[@"flags"]=bad;Require(!RSDecodeAppExternalDeviceNotification(m),@"external ACK encrypted and invalid-byte flags reject");}
        for(NSString *key in @[@"sender",@"receiver",@"commandSet",@"commandId"]){NSMutableDictionary *m=[parameterMessage(105,ProgramHex(@"0207010080ff7f0000"),0) mutableCopy];m[key]=@0;Require(!RSDecodeAppExternalDeviceNotification(m),@"external wrong envelope rejects");}
        NSMutableData *externalMax=[NSMutableData dataWithBytes:(uint8_t[]){9,127} length:2];[externalMax appendData:[NSMutableData dataWithLength:127]];Require(RSDecodeAppExternalDeviceNotification(parameterMessage(105,externalMax,0))!=nil,@"external unknown record length127 accepted");
        NSString *sensorFixture=[[@__FILE__ stringByDeletingLastPathComponent] stringByDeletingLastPathComponent];sensorFixture=[sensorFixture stringByAppendingPathComponent:@"node/test/fixtures/sensor-calibration.json"];
        NSArray *sensorVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:sensorFixture] options:0 error:nil];Require(sensorVectors.count==7,@"seven sensor calibration source vectors loaded");
        for(NSDictionary *v in sensorVectors){NSDictionary *decoded=RSDecodeAppSensorCalibrationNotification(parameterMessage(48,ProgramHex(v[@"bodyHex"]),0));BOOL match=decoded!=nil;for(NSString *key in v[@"expected"]){NSString *actualKey=[key isEqual:@"targetDeviceVerified"]?@"deviceVerified":key;match=match && [decoded[actualKey] isEqual:v[@"expected"][key]];}Require(match,@"sensor domain, unsigned values, unknown and tail match source vector");Require(![decoded[@"requestAssociationVerified"] boolValue] && ![decoded[@"modelLayoutVerified"] boolValue] && ![decoded isKindOfClass:NSMutableDictionary.class],@"sensor status immutable without model or request completion claim");}
        NSDictionary *sensorStates=@{@0:@"COMPLETE",@1:@"PROCESSING",@3:@"FAIL",@9:@"OTHER"};
        for(NSUInteger value=0;value<256;value++){NSDictionary *decoded=RSDecodeAppSensorCalibrationNotification(parameterMessage(48,[NSData dataWithBytes:(uint8_t[]){(uint8_t)value,(uint8_t)value} length:2],0));Require([decoded[@"rawProgressValue"] unsignedIntegerValue]==value && [decoded[@"rawStatus"] unsignedIntegerValue]==value && [decoded[@"sourceStatus"] isEqual:(sensorStates[@(value)]?:@"OTHER")] && [decoded[@"sourceStatusKnown"] boolValue]==(sensorStates[@(value)]!=nil),@"every source progress/status byte preserved without bool or ordinal conversion");}
        Require(!RSDecodeAppSensorCalibrationNotification(parameterMessage(48,ProgramHex(@"00"),0)) && !RSDecodeAppSensorCalibrationNotification(parameterMessage(48,NSData.data,0)),@"sensor short body never synthesizes zero progress or status");
        for(NSNumber *bad in @[@128,@1,@256,@(-1),@NO]){NSMutableDictionary *m=[parameterMessage(48,ProgramHex(@"6403"),0) mutableCopy];m[@"flags"]=bad;Require(!RSDecodeAppSensorCalibrationNotification(m),@"sensor rejects ACK encrypted and nonbyte/bool flags");}
        for(NSString *key in @[@"sender",@"receiver",@"commandSet",@"commandId"]){NSMutableDictionary *m=[parameterMessage(48,ProgramHex(@"6403"),0) mutableCopy];m[key]=@0;Require(!RSDecodeAppSensorCalibrationNotification(m),@"sensor rejects other command or endpoint");}
        for(NSUInteger mode=1;mode<8;mode++)for(NSUInteger code=0;code<2;code++){NSError *cipherError=nil;NSDictionary *m=parameterMessage(15,[NSData dataWithBytes:(uint8_t[]){code?7:0} length:1],128|mode);Require(!RSDecodeAppReply(m,15,nil,&cipherError) && [cipherError.userInfo[@"code"] isEqual:@"RS4MINI_PROTOCOL_ERROR"],@"cipher ACK rejected before response status interpretation");}
        for(NSNumber *bad in @[@(-128),@384,@128.5,@YES]){NSMutableDictionary *m=[parameterMessage(15,ProgramHex(@"00"),128) mutableCopy];m[@"flags"]=bad;NSError *e=nil;Require(!RSDecodeAppReply(m,15,nil,&e),@"App ACK requires uint8 flags");}
        for(NSUInteger mode=1;mode<8;mode++){Require(!RSDecodeAppCalibrationNotification(parameterMessage(110,ProgramHex(@"00020264"),mode)),@"auto-tune candidate rejects encrypted body");Require(!RSDecodeResearchStatus(parameterMessage(48,ProgramHex(@"6401"),mode),@"rs3"),@"legacy candidate rejects encrypted body");}
        NSString *componentFixture=[[[NSString stringWithUTF8String:__FILE__] stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"../node/test/fixtures/component-calibration.json"];
        NSArray *componentVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:componentFixture] options:0 error:nil];Require(componentVectors.count==7,@"seven component calibration contracts");
        Require(RSAppComponentCalibrationFrame(1,@"AUTO")!=nil && !RSAppComponentCalibrationFrame(1,@"GYRO") && !RSAppComponentCalibrationFrame(1,(id)@0),@"component action source is explicit AUTO only");
        for(NSDictionary *v in componentVectors){NSError *e=nil;NSDictionary *r=RSDecodeAppComponentCalibrationReply(parameterMessage(8,ProgramHex(v[@"payloadHex"]),128),128,&e);BOOL match=r && !e;for(NSString *key in v[@"expected"])match=match && [r[key] isEqual:v[@"expected"][key]];Require(match,@"component ACK source domain and partial business contracts match");Require(![r[@"physicalCompletionVerified"] boolValue] && ![r[@"businessRequestAssociationVerified"] boolValue],@"component ACK not physical completion");}
        for(NSUInteger v=0;v<256;v++){NSError *e=nil;NSDictionary *r=RSDecodeAppComponentCalibrationReply(parameterMessage(8,[NSData dataWithBytes:(uint8_t[]){0,v,v} length:3],128),0,&e);Require(!e && [r[@"calibration"][@"rawPart"] unsignedIntegerValue]==v && [r[@"calibration"][@"rawStatus"] unsignedIntegerValue]==v && [r[@"calibration"][@"sourcePartKnown"] boolValue]==(v<10) && [r[@"calibration"][@"sourceStatusKnown"] boolValue]==(v<3),@"component uint8 domains preserve unknown source enums");}
        for(NSUInteger enc=1;enc<=7;enc++){NSError *e=nil;Require(!RSDecodeAppComponentCalibrationReply(parameterMessage(8,ProgramHex(@"000001"),128|enc),0,&e) && [e.userInfo[@"code"] isEqual:@"RS4MINI_PROTOCOL_ERROR"],@"component ciphertext rejected before business status");}
        NSError *componentNack=nil;Require(!RSDecodeAppComponentCalibrationReply(parameterMessage(8,ProgramHex(@"010001"),128),0,&componentNack) && [componentNack.userInfo[@"code"] isEqual:@"RS4MINI_DEVICE_ERROR"],@"component return code1 is rejection despite business success1");
        NSString *stickControlFixture=[[[NSString stringWithUTF8String:__FILE__] stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"../node/test/fixtures/handheld-stick-control.json"];
        NSArray *stickControlVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:stickControlFixture] options:0 error:nil];Require(stickControlVectors.count==3,@"three stick-control shared contracts");
        for(NSDictionary *v in stickControlVectors){NSError *e=nil;NSDictionary *r=RSDecodeAppHandheldStickControlReply(parameterMessage(88,ProgramHex(v[@"payloadHex"]),128),v[@"enabled"],&e);BOOL match=r && !e;for(NSString *key in v[@"expected"])match=match && [r[key] isEqual:v[@"expected"][key]];Require(match && ![r[@"physicalCompletionVerified"] boolValue] && ![r[@"notificationAssociationVerified"] boolValue],@"stick requested boolean and opaque tail match source contract");NSArray *encoded=[[RSFrameDecoder new] push:RSAppHandheldStickControlFrame(1,v[@"enabled"])];Require([encoded.firstObject[@"flags"] intValue]==64 && [encoded.firstObject[@"commandId"] intValue]==88 && [encoded.firstObject[@"payload"] isEqual:[NSData dataWithBytes:(uint8_t[]){[v[@"enabled"] boolValue]} length:1]],@"stick frame is explicit bool with ACK request");}
        for(id value in @[@0,@1,@"true",NSNull.null,@[]])Require(!RSAppHandheldStickControlFrame(1,value),@"stick control rejects nonboolean values");
        for(NSUInteger enc=1;enc<=7;enc++){NSError *e=nil;Require(!RSDecodeAppHandheldStickControlReply(parameterMessage(88,ProgramHex(@"00"),128|enc),@YES,&e) && [e.userInfo[@"code"] isEqual:@"RS4MINI_PROTOCOL_ERROR"],@"stick encrypted ACK rejected");}
        NSError *stickNack=nil;Require(!RSDecodeAppHandheldStickControlReply(parameterMessage(88,ProgramHex(@"07"),128),@NO,&stickNack) && [stickNack.userInfo[@"code"] isEqual:@"RS4MINI_DEVICE_ERROR"],@"stick rejection is not applied state");
        NSString *tutorialFixture=[[[NSString stringWithUTF8String:__FILE__] stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"../node/test/fixtures/tutorial-status.json"];
        NSArray *tutorialVectors=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:tutorialFixture] options:0 error:nil];Require(tutorialVectors.count==8,@"eight tutorial shared source contracts");
        for(NSDictionary *v in tutorialVectors){NSDictionary *r=RSDecodeAppTutorialNotification(parameterMessage(43,ProgramHex(v[@"bodyHex"]),0));BOOL match=r!=nil;for(NSString *key in v[@"expected"])match=match && [r[key] isEqual:v[@"expected"][key]];Require(match,@"tutorial signed/unsigned, fallback, bit views and tail match contracts");Require(![r isKindOfClass:NSMutableDictionary.class] && ![r[@"sourceFlags"] isKindOfClass:NSMutableDictionary.class] && ![r[@"sourceStepStatus"] isKindOfClass:NSMutableDictionary.class] && ![r[@"physicalCompletionVerified"] boolValue],@"tutorial snapshot and nested source dictionaries are immutable without completion claim");}
        for(NSUInteger v=0;v<256;v++){NSDictionary *r=RSDecodeAppTutorialNotification(parameterMessage(43,[NSData dataWithBytes:(uint8_t[]){v,0,0,0,0} length:5],0));Require([r[@"rawStep"] unsignedIntegerValue]==v && ((r[@"knownSourceStepName"]!=NSNull.null)==(v<11)),@"all step bytes preserved without false known finish");}
        for(NSUInteger bit=0;bit<32;bit++){uint32_t word=1u<<bit;uint8_t p[]={0,word&255,(word>>8)&255,(word>>16)&255,(word>>24)&255};NSDictionary *r=RSDecodeAppTutorialNotification(parameterMessage(43,[NSData dataWithBytes:p length:5],0));NSUInteger sum=0;for(NSNumber *v in [r[@"sourceFlags"] allValues])sum+=v.unsignedIntegerValue;Require([r[@"rawCompletionWord"] unsignedLongLongValue]==((uint64_t)1<<bit) && sum==(bit<9) && [r[@"sourceStepStatus"][@"STEP_FINISH"] boolValue]==(bit==30) && [r[@"sourceStepStatus"][@"STEP_START"] boolValue]==(bit==31),@"tutorial full32 bits preserve named and Java-wrapped views");}
        for(NSUInteger length=0;length<5;length++)Require(!RSDecodeAppTutorialNotification(parameterMessage(43,[NSMutableData dataWithLength:length],0)),@"tutorial short body not zero-filled");
        for(NSNumber *flags in @[@128,@1,@2,@3,@4,@5,@6,@7,@256,@(-1),@NO]){NSMutableDictionary *m=[parameterMessage(43,ProgramHex(@"0000000000"),0) mutableCopy];m[@"flags"]=flags;Require(!RSDecodeAppTutorialNotification(m),@"tutorial requires explicit unencrypted request flags");}
        printf("Native protocol, reassembly, stop queue and motion-core checks: %lu passed\n", (unsigned long)assertions);
    }
    return 0;
}
