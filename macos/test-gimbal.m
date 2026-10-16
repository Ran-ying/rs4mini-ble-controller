#import "RSGimbal.h"
#import "RSControlCore.h"

@interface RSGimbal (OfflineTest)
- (void)tick;
@end
@interface FakeCentral : NSObject
@property(nonatomic) CBManagerState state;
@property(nonatomic) NSUInteger scans;
@property(nonatomic) NSUInteger cancels;
@end
@implementation FakeCentral
- (NSArray *)retrieveConnectedPeripheralsWithServices:(NSArray *)services { return @[]; }
- (void)scanForPeripheralsWithServices:(NSArray *)services options:(NSDictionary *)options { self.scans++; }
- (void)stopScan {}
- (void)connectPeripheral:(id)peripheral options:(NSDictionary *)options {}
- (void)cancelPeripheralConnection:(id)peripheral { self.cancels++; }
@end
@interface FakeCharacteristic : NSObject
@property(nonatomic, strong) CBUUID *UUID;
@property(nonatomic) CBCharacteristicProperties properties;
@property(nonatomic) BOOL isNotifying;
@property(nonatomic, strong) NSData *value;
@end
@implementation FakeCharacteristic
@end
@interface FakeService : NSObject
@property(nonatomic, strong) NSArray *characteristics;
@end
@implementation FakeService
@end
@interface FakePeripheral : NSObject
@property(nonatomic) CBPeripheralState state;
@property(nonatomic) id delegate;
@property(nonatomic, copy) NSString *name;
@property(nonatomic, strong) NSUUID *identifier;
@property(nonatomic, strong) NSArray *services;
@property(nonatomic) BOOL canSendWriteWithoutResponse;
@property(nonatomic) BOOL pauseAfterChunk;
@property(nonatomic) BOOL pauseAfterShortChunk;
@property(nonatomic, strong) NSMutableData *writes;
@end
@implementation FakePeripheral
- (void)discoverServices:(NSArray *)services {}
- (void)discoverCharacteristics:(NSArray *)characteristics forService:(id)service {}
- (void)setNotifyValue:(BOOL)value forCharacteristic:(id)characteristic {}
- (void)writeValue:(NSData *)value forCharacteristic:(id)characteristic type:(CBCharacteristicWriteType)type {
    [self.writes appendData:value]; if (self.pauseAfterChunk || (self.pauseAfterShortChunk && value.length < 20)) { self.canSendWriteWithoutResponse = NO; self.pauseAfterChunk = NO; self.pauseAfterShortChunk = NO; }
}
@end
static NSUInteger assertions;
static void Require(BOOL value, NSString *message) { assertions++; if (!value) { fprintf(stderr, "FAIL: %s\n", message.UTF8String); exit(1); } }
static FakePeripheral *Connect(RSGimbal *gimbal, FakeCentral *central) {
    [gimbal connect];
    FakePeripheral *peripheral = [FakePeripheral new]; peripheral.state = CBPeripheralStateConnected;
    peripheral.identifier = [[NSUUID alloc] initWithUUIDString:@"00000000-0000-0000-0000-000000000001"];
    peripheral.name = @"DJI RS 4 MINI-TEST"; peripheral.canSendWriteWithoutResponse = YES; peripheral.writes = [NSMutableData data];
    FakeCharacteristic *rx = [FakeCharacteristic new], *tx = [FakeCharacteristic new];
    rx.UUID = [CBUUID UUIDWithString:@"FFF4"]; rx.isNotifying = YES;
    tx.UUID = [CBUUID UUIDWithString:@"FFF5"]; tx.properties = CBCharacteristicPropertyWriteWithoutResponse;
    FakeService *service = [FakeService new]; service.characteristics = @[rx, tx]; peripheral.services = @[service];
    [gimbal centralManager:(id)central didDiscoverPeripheral:(id)peripheral advertisementData:@{} RSSI:@(-40)];
    [gimbal centralManager:(id)central didConnectPeripheral:(id)peripheral];
    [gimbal peripheral:(id)peripheral didDiscoverServices:nil];
    [gimbal peripheral:(id)peripheral didDiscoverCharacteristicsForService:(id)service error:nil];
    [gimbal peripheral:(id)peripheral didUpdateNotificationStateForCharacteristic:(id)rx error:nil];
    Require(gimbal.ready && !gimbal.connecting, @"connect and notification lifecycle");
    return peripheral;
}
static void ThreeTicks(RSGimbal *gimbal) { [gimbal tick]; [gimbal tick]; [gimbal tick]; }
static NSData *QueryResponse(uint16_t sequence, NSString *kind, uint8_t sender, uint8_t flags) {
    NSMutableData *data = [RSResearchQueryFrame(sequence, kind) mutableCopy]; uint8_t *p = data.mutableBytes;
    p[4] = sender; p[5] = 2; p[8] = flags; uint16_t crc = 0x3692;
    for (NSUInteger i = 0; i < data.length - 2; i++) { crc ^= p[i]; for (NSUInteger bit = 0; bit < 8; bit++) crc = crc & 1 ? (crc >> 1) ^ 0x8408 : crc >> 1; }
    p[data.length - 2] = crc & 255; p[data.length - 1] = crc >> 8; return data;
}
static NSData *AppResponse(uint16_t sequence, uint8_t command, NSData *payload, uint8_t sender) {
    NSMutableData *data = [NSMutableData dataWithLength:13 + payload.length]; uint8_t *p = data.mutableBytes;
    p[0] = 0x55; p[1] = data.length & 255; p[2] = 4 | ((data.length >> 8) & 3);
    uint8_t c8 = 0x77; for (NSUInteger i=0;i<3;i++) { c8 ^= p[i]; for (int b=0;b<8;b++) c8 = c8 & 1 ? (c8 >> 1) ^ 0x8c : c8 >> 1; } p[3] = c8;
    p[4] = sender; p[5] = 2; p[6] = sequence & 255; p[7] = sequence >> 8; p[8] = 0x80; p[9] = 4; p[10] = command;
    memcpy(p+11, payload.bytes, payload.length); uint16_t crc = 0x3692;
    for (NSUInteger i=0;i<data.length-2;i++) { crc ^= p[i]; for (int b=0;b<8;b++) crc = crc & 1 ? (crc >> 1) ^ 0x8408 : crc >> 1; }
    p[data.length-2] = crc & 255; p[data.length-1] = crc >> 8; return data;
}
static void PumpCallbacks(void) { [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.003]]; }
int main(void) {
    @autoreleasepool {
        FakeCentral *central = [FakeCentral new]; central.state = CBManagerStatePoweredOn;
        RSGimbal *gimbal = [[RSGimbal alloc] initWithStatus:^(NSString *text, BOOL ready) {} central:(id)central];
        FakePeripheral *peripheral = Connect(gimbal, central);
        [gimbal drivePan:0.1 tilt:0 roll:0]; Require(peripheral.writes.length == 22, @"manual first frame");
        [gimbal stop]; Require(gimbal.busy, @"stop owns cleanup");
        NSUInteger count = peripheral.writes.length;
        [gimbal drivePan:0.5 tilt:0 roll:0]; Require(peripheral.writes.length == count, @"reject conflicting motion while stopping");
        ThreeTicks(gimbal); Require(!gimbal.busy, @"stop releases after three frames");
        RSFrameDecoder *decoder = [RSFrameDecoder new]; NSArray *frames = [decoder push:peripheral.writes];
        Require(frames.count == 4, @"one manual and three neutral frames");
        [peripheral.writes setLength:0]; peripheral.pauseAfterChunk = YES;
        [gimbal drivePan:0.1 tilt:0 roll:0]; Require(peripheral.writes.length == 20, @"respect backpressure mid-frame");
        [gimbal stop]; peripheral.canSendWriteWithoutResponse = YES; ThreeTicks(gimbal);
        [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(frames.count == 4 && decoder.invalidFrames == 0, @"finish partial frame before stop; no interleaving");
        [peripheral.writes setLength:0]; [gimbal recenter]; [gimbal stop]; ThreeTicks(gimbal);
        [decoder reset]; frames = [decoder push:peripheral.writes];
        for (NSDictionary *frame in frames) Require([frame[@"commandId"] intValue] != 0x4c, @"stop cancels delayed recenter");
        [gimbal moveTo:@{@"pan": @5}]; Require(gimbal.busy, @"position owns motion");
        count = peripheral.writes.length; [gimbal drivePan:0.1 tilt:0 roll:0]; Require(peripheral.writes.length == count, @"position conflict rejected");
        RSPositionLoop *loop = [gimbal valueForKey:@"position"];
        [loop feedback:@{@"yaw": @0, @"pitch": @0, @"roll": @0} at:NSProcessInfo.processInfo.systemUptime]; [gimbal tick];
        Require(peripheral.writes.length > count, @"position sends speed after feedback");
        [gimbal stop]; ThreeTicks(gimbal); Require(!gimbal.busy, @"position cancellation cleanup");
        [gimbal disconnect]; ThreeTicks(gimbal); Require(!gimbal.ready && central.cancels > 0 && peripheral.delegate == nil, @"disconnect clears delegate and state");
        [gimbal connect]; Require(gimbal.connecting, @"start new connection");
        [(NSTimer *)[gimbal valueForKey:@"connectionTimer"] fire]; Require(!gimbal.connecting, @"connection deadline cancels scan");
        count = central.cancels; [gimbal centralManager:(id)central didConnectPeripheral:(id)peripheral];
        Require(!gimbal.ready && central.cancels == count + 1, @"late connection rejected");
        peripheral = Connect(gimbal, central); peripheral.canSendWriteWithoutResponse = NO;
        [gimbal drivePan:0.1 tilt:0 roll:0]; [gimbal setValue:@(NSProcessInfo.processInfo.systemUptime - 4) forKey:@"lastWriteProgress"];
        [gimbal tick]; Require(!gimbal.ready && peripheral.delegate == nil, @"write watchdog invalidates connection");
        peripheral = Connect(gimbal, central); [peripheral.writes setLength:0];
        [gimbal runTrajectory:@[@{@"timeMs": @0, @"pan": @0.05}, @{@"timeMs": @1000, @"pan": @0.05}] interpolation:@"linear"];
        Require(gimbal.busy, @"trajectory owns stop preamble"); ThreeTicks(gimbal); [gimbal tick];
        RSTrajectoryLoop *trajectory = [gimbal valueForKey:@"trajectory"];
        Require(trajectory.active && gimbal.busy, @"trajectory starts after neutral preamble");
        count = peripheral.writes.length; [gimbal moveTo:@{@"pan": @5}]; Require(count == peripheral.writes.length, @"trajectory rejects position conflict");
        [trajectory setValue:@(NSProcessInfo.processInfo.systemUptime - 2) forKey:@"started"]; [gimbal tick]; ThreeTicks(gimbal);
        Require(!gimbal.busy && !trajectory.active, @"trajectory completion releases motion after stops");
        [gimbal runTrajectory:@[@{@"timeMs": @0, @"pan": @.05}, @{@"timeMs": @1000}] interpolation:@"linear"]; [gimbal stop]; ThreeTicks(gimbal);
        Require(!trajectory.active && !gimbal.busy, @"stop cancels delayed trajectory start");
        count = peripheral.writes.length; [gimbal moveThrough:@[@{@"pan": @5}, @{@"pan": @181}]];
        Require(peripheral.writes.length == count && !gimbal.busy, @"validate all waypoints before any write");
        [gimbal moveThrough:@[@{@"pan": @5, @"holdMs": @10000}, @{@"tilt": @3}]]; ThreeTicks(gimbal);
        [loop feedback:@{@"yaw": @5, @"pitch": @0, @"roll": @0} at:NSProcessInfo.processInfo.systemUptime]; [gimbal tick]; ThreeTicks(gimbal);
        Require(gimbal.busy && !loop.active, @"waypoint dwell retains motion ownership");
        [gimbal stop]; ThreeTicks(gimbal); count = peripheral.writes.length; [gimbal tick];
        Require(!gimbal.busy && peripheral.writes.length == count, @"stop in dwell cannot enter next waypoint");
        [gimbal moveThrough:@[@{@"pan": @5}, @{@"tilt": @3}]]; ThreeTicks(gimbal);
        [loop feedback:@{@"yaw": @5, @"pitch": @0, @"roll": @0} at:NSProcessInfo.processInfo.systemUptime]; [gimbal tick]; ThreeTicks(gimbal); [gimbal tick];
        Require(loop.active && [[gimbal valueForKey:@"waypointIndex"] unsignedIntegerValue] == 1, @"next waypoint starts after first stop and dwell");
        [loop feedback:@{@"yaw": @5, @"pitch": @3, @"roll": @0} at:NSProcessInfo.processInfo.systemUptime]; [gimbal tick]; ThreeTicks(gimbal); [gimbal tick];
        Require(!gimbal.busy, @"final waypoint completion clears ownership");
        [gimbal setValue:@{@"yaw": @4, @"pitch": @3, @"roll": @2} forKey:@"latestJoints"];
        [gimbal setValue:@(NSProcessInfo.processInfo.systemUptime) forKey:@"latestJointAt"]; [gimbal captureHome];
        Require([gimbal.home[@"pan"] doubleValue] == 4, @"capture saved home");
        [gimbal moveHomeAxes:@[@"pan"]]; [loop feedback:@{@"yaw": @4, @"pitch": @20, @"roll": @30} at:NSProcessInfo.processInfo.systemUptime]; [gimbal tick]; ThreeTicks(gimbal);
        Require(!gimbal.busy, @"saved home target only selected axis");
        gimbal.autoReconnectEnabled = YES; [gimbal drivePan:.05 tilt:0 roll:0];
        [gimbal centralManager:(id)central didDisconnectPeripheral:(id)peripheral error:nil];
        Require(!gimbal.ready && gimbal.reconnectAttempt == 1 && [gimbal valueForKey:@"reconnectTimer"] != nil, @"unexpected loss schedules bounded retry");
        [(NSTimer *)[gimbal valueForKey:@"reconnectTimer"] fire];
        Require(gimbal.connecting, @"retry timer begins new connection");
        FakePeripheral *other = [FakePeripheral new]; other.name = @"DJI RS4 MINI-TEST"; other.identifier = NSUUID.UUID;
        [gimbal centralManager:(id)central didDiscoverPeripheral:(id)other advertisementData:@{} RSSI:@(-40)];
        Require([gimbal valueForKey:@"peripheral"] == nil, @"automatic retry rejects another device identity");
        peripheral = Connect(gimbal, central); [gimbal tick];
        Require(peripheral.writes.length == 0 && [[gimbal valueForKey:@"pan"] doubleValue] == 0, @"reconnected device never receives old velocity");
        [gimbal disconnect]; ThreeTicks(gimbal);
        Require(!gimbal.autoReconnectEnabled && [gimbal valueForKey:@"reconnectTimer"] == nil, @"manual disconnect disables retry policy");
        peripheral = Connect(gimbal, central); gimbal.autoReconnectEnabled = YES;
        [gimbal centralManager:(id)central didDisconnectPeripheral:(id)peripheral error:nil];
        for (NSUInteger attempt = 0; attempt < 5; attempt++) {
            [(NSTimer *)[gimbal valueForKey:@"reconnectTimer"] fire];
            [(NSTimer *)[gimbal valueForKey:@"connectionTimer"] fire];
        }
        Require(gimbal.reconnectAttempt == 5 && !gimbal.connecting && [gimbal valueForKey:@"reconnectTimer"] == nil, @"automatic retry exhausts after five attempts");
        gimbal.autoReconnectEnabled = NO;
        peripheral = Connect(gimbal, central); [peripheral.writes setLength:0];
        [gimbal sendExperimentalCommand:@{@"profile": @"rs4mini", @"command": @"sleep", @"asleep": @YES}];
        Require(peripheral.writes.length == 0 && !gimbal.busy, @"research controls require explicit supported profile");
        [gimbal sendExperimentalCommand:@{@"profile": @"rs3", @"command": @"absolute", @"pan": @2, @"parameterByte": @20, @"observeMs": @1000}]; ThreeTicks(gimbal);
        [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue] == 0x14, @"absolute experiment retains observation ownership");
        [gimbal stop]; ThreeTicks(gimbal); Require(!gimbal.busy, @"stop cancels absolute observation");
        [peripheral.writes setLength:0];
        [gimbal sendExperimentalCommand:@{@"profile": @"rs3", @"command": @"rate", @"pan": @2, @"durationMs": @1000}]; ThreeTicks(gimbal); [gimbal stop]; ThreeTicks(gimbal);
        [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(frames.count == 8 && [frames[4][@"commandId"] intValue] == 0x0c && ((const uint8_t *)[frames[4][@"payload"] bytes])[6] == 0, @"native rate releases before three ordinary neutral frames");
        [peripheral.writes setLength:0];
        [gimbal sendExperimentalCommand:@{@"profile": @"rs3mini", @"command": @"sleep", @"asleep": @YES}]; ThreeTicks(gimbal); [gimbal tick];
        [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(!gimbal.busy && frames.count == 4 && [frames.lastObject[@"commandId"] intValue] == 0x0f, @"sleep experiment ends after write without trailing motion");
        [gimbal sendExperimentalCommand:@{@"profile": @"rs3", @"command": @"query", @"kind": @"type"}]; ThreeTicks(gimbal);
        Require(gimbal.busy, @"research query waits for correlated response");
        [gimbal setValue:@(NSProcessInfo.processInfo.systemUptime - 1) forKey:@"experimentalDeadline"]; [gimbal tick];
        Require(!gimbal.busy, @"query timeout releases ownership");
        uint16_t oldSequence = [[gimbal valueForKey:@"experimentalSequence"] unsignedShortValue];
        [gimbal sendExperimentalCommand:@{@"profile": @"rs3", @"command": @"query", @"kind": @"type"}];
        FakeService *fakeService = (id)peripheral.services.firstObject;
        FakeCharacteristic *notify = (id)fakeService.characteristics.firstObject;
        notify.value = QueryResponse(oldSequence, @"type", 4, 0x80);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(gimbal.busy && [gimbal valueForKey:@"experimentalJob"] != nil, @"stale response during new query preamble cannot satisfy it");
        ThreeTicks(gimbal); uint16_t seq = [[gimbal valueForKey:@"experimentalSequence"] unsignedShortValue];
        for (NSData *response in @[QueryResponse(seq + 1, @"type", 4, 0x80), QueryResponse(seq, @"position", 4, 0x80), QueryResponse(seq, @"type", 5, 0x80), QueryResponse(seq, @"type", 4, 0)]) {
            notify.value = response; [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        }
        Require(gimbal.busy, @"query checks sequence, endpoints, command and response flag");
        notify.value = QueryResponse(seq, @"type", 4, 0x80); [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(!gimbal.busy, @"matching query response releases motion slot");
        [peripheral.writes setLength:0]; [gimbal requestDegreeInfo]; ThreeTicks(gimbal);
        [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue] == 0x1e, @"degree-info routes through SDK and awaits correlated raw reply");
        uint16_t degreeSequence = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        notify.value = QueryResponse(degreeSequence + 1, @"degreeInfo", 4, 0x80);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(gimbal.busy, @"degree-info rejects unrelated sequence");
        notify.value = QueryResponse(degreeSequence, @"degreeInfo", 4, 0x80);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(!gimbal.busy, @"degree-info matching response releases SDK ownership");
        [peripheral.writes setLength:0]; [gimbal requestDegreeInfo]; [gimbal stop]; ThreeTicks(gimbal);
        [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(!gimbal.busy && [frames.lastObject[@"commandId"] intValue] != 0x1e, @"stop cancels delayed device query");
        Require([gimbal useAppProfile:@"ronin-2.2.2"], @"explicit current App profile accepted when idle");
        __block NSDictionary *appResult = nil; __block NSError *appError = nil; __block NSUInteger appCallbacks = 0;
        RSAppCompletion appDone = ^(NSDictionary *result, NSError *error) { appResult = result; appError = error; appCallbacks++; };
        [peripheral.writes setLength:0]; [gimbal setFollowSensitivity:@1 timeoutMs:1000 completion:appDone];
        Require(gimbal.busy && ![gimbal useAppProfile:@"ronin-2.2.2"], @"App preamble owns native operation and blocks profile changes");
        ThreeTicks(gimbal); [decoder reset]; frames = [decoder push:peripheral.writes];
        Require([frames.lastObject[@"commandId"] intValue] == 0x0f && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){150,1,1} length:3]], @"native setter sends exact source payload");
        uint16_t appSequence = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        NSData *ok = [NSData dataWithBytes:(uint8_t[]){0} length:1];
        notify.value = AppResponse(appSequence+1,0x0f,ok,4); [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        notify.value = AppResponse(appSequence,0x0f,ok,0x24); [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(gimbal.busy && appCallbacks == 0, @"native App ACK correlates exact sequence and endpoint");
        notify.value = AppResponse(appSequence,0x0f,ok,4); [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(!gimbal.busy && appCallbacks == 1 && appError == nil && [appResult[@"requestedMode"] intValue] == 1 && ![appResult[@"physicalCompletionVerified"] boolValue], @"native acknowledged result does not imply physical completion");
        appResult = nil; appError = nil;
        [gimbal getFollowSensitivityWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        appSequence = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        notify.value = AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,150,1,255} length:4],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks == 2 && [appResult[@"rawValue"] intValue] == 255 && appResult[@"mode"] == NSNull.null, @"native high index and unknown mode remain raw");
        appError = nil; [gimbal setFollowSensitivity:@0 timeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        appSequence = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        notify.value = AppResponse(appSequence,0x0f,[NSData dataWithBytes:(uint8_t[]){7} length:1],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(gimbal.busy, @"device rejection retains ownership through neutral cleanup"); ThreeTicks(gimbal); PumpCallbacks();
        Require(appCallbacks == 3 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_DEVICE_ERROR"] && [appError.userInfo[@"statusCode"] intValue] == 7, @"native device return code is an error");
        [peripheral.writes setLength:0]; [gimbal setFollowSensitivity:@1 timeoutMs:1000 completion:appDone]; [gimbal stop]; ThreeTicks(gimbal); PumpCallbacks();
        [decoder reset]; frames = [decoder push:peripheral.writes];
        BOOL appSent = NO; for (NSDictionary *f in frames) if ([f[@"commandId"] intValue] == 0x0f) appSent = YES;
        Require(!appSent && appCallbacks == 4 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"], @"stop cancels App preamble without sending setting");
        [gimbal setFollowSensitivity:@1 timeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [gimbal setValue:@(NSProcessInfo.processInfo.systemUptime - 1) forKey:@"deviceQueryDeadline"]; [gimbal tick]; ThreeTicks(gimbal); PumpCallbacks();
        Require(appCallbacks == 5 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_RESPONSE_TIMEOUT"] && !gimbal.busy, @"native App timeout cleans up exactly once");
        [peripheral.writes setLength:0];
        NSMutableDictionary *settingsPatch = [@{@"enabled": @YES, @"pitch": @NO} mutableCopy];
        [gimbal setCustomFollowSettings:settingsPatch timeoutMs:1000 completion:appDone]; settingsPatch[@"yaw"] = @NO;
        ThreeTicks(gimbal); [decoder reset]; frames = [decoder push:peripheral.writes];
        Require([frames.lastObject[@"commandId"] intValue] == 0x10 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){132} length:1]], @"settings first read current unsigned index");
        appSequence = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        double transactionDeadline = [[gimbal valueForKey:@"deviceQueryDeadline"] doubleValue];
        notify.value = AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,132,9,14} length:4],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        uint16_t settingsWriteSeq = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(gimbal.busy && appCallbacks == 5 && settingsWriteSeq != appSequence && [[gimbal valueForKey:@"deviceQueryDeadline"] doubleValue] == transactionDeadline && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){132,1,13} length:3]], @"settings preserve snapshot and slot across read/write with one deadline");
        notify.value = AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,132,1,0} length:4],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(gimbal.busy && appCallbacks == 5, @"late read cannot satisfy settings ACK");
        notify.value = AppResponse(settingsWriteSeq,0x0f,ok,4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks == 6 && !gimbal.busy && [appResult[@"previousRawValue"] intValue] == 14 && [appResult[@"requestedRawValue"] intValue] == 13, @"settings callback once after write ACK");
        [peripheral.writes setLength:0]; [gimbal setMotorSettings:@{@"enabled": @NO} timeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        appSequence = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; [gimbal stop]; ThreeTicks(gimbal); PumpCallbacks();
        notify.value = AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,35,1,0} length:4],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        [decoder reset]; frames = [decoder push:peripheral.writes]; BOOL settingWritten = NO;
        for (NSDictionary *f in frames) if ([f[@"commandId"] intValue] == 0x0f) settingWritten = YES;
        Require(!settingWritten && appCallbacks == 7 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"], @"stop before read reply prevents any settings write");
        [gimbal setCustomFollowSettings:@{@"yaw": @YES} timeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        appSequence = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        notify.value = AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,132,1,128} length:4],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; ThreeTicks(gimbal); PumpCallbacks();
        Require(appCallbacks == 8 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_UNSUPPORTED_VALUE"], @"unknown custom bits reject writing after cleanup");
        [peripheral.writes setLength:0]; [gimbal sendAutoTuneRequest:@1 completion:appDone]; PumpCallbacks();
        Require(appCallbacks == 9 && !gimbal.busy && peripheral.writes.length == 0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"], @"auto-tune validates boolean before stop/write");
        [gimbal sendAutoTuneRequest:@NO completion:appDone]; ThreeTicks(gimbal);
        Require(gimbal.busy && ![[gimbal valueForKey:@"awaitingDeviceQuery"] boolValue], @"no ACK request owns host slot through write without awaiting reply");
        [gimbal tick]; PumpCallbacks(); [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(appCallbacks == 10 && !gimbal.busy && [frames.lastObject[@"commandId"] intValue] == 0x6a && [frames.lastObject[@"flags"] intValue] == 0 && ![appResult[@"acknowledged"] boolValue] && ![appResult[@"physicalCompletionVerified"] boolValue], @"native no ACK result reports only local send");
        [peripheral.writes setLength:0]; [gimbal sendAutoTuneRequest:@YES completion:appDone]; [gimbal tick]; [gimbal tick];
        peripheral.pauseAfterShortChunk = YES; [gimbal tick];
        [decoder reset]; frames = [decoder push:peripheral.writes];
        Require(gimbal.busy && appCallbacks == 10 && [frames.lastObject[@"commandId"] intValue] != 0x6a, @"backpressure retains auto-tune ownership before any request chunk");
        peripheral.canSendWriteWithoutResponse = YES; [gimbal peripheralIsReadyToSendWriteWithoutResponse:(id)peripheral]; [gimbal tick]; PumpCallbacks();
        Require(appCallbacks == 11 && !gimbal.busy && [appResult[@"sent"] boolValue], @"auto-tune send finishes only when queue drains");
        [peripheral.writes setLength:0]; [gimbal sendAutoTuneRequest:@YES completion:appDone]; [gimbal tick]; [gimbal tick];
        peripheral.pauseAfterShortChunk = YES; [gimbal tick]; [gimbal stop]; peripheral.canSendWriteWithoutResponse = YES; ThreeTicks(gimbal); PumpCallbacks();
        [decoder reset]; frames = [decoder push:peripheral.writes]; BOOL tuneWritten = NO;
        for (NSDictionary *f in frames) if ([f[@"commandId"] intValue] == 0x6a) tuneWritten = YES;
        Require(appCallbacks == 12 && !tuneWritten && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"], @"stop discards queued auto-tune request without physical stop claim");
        [gimbal queryCalibrationStatusWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        appSequence = [[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        notify.value = AppResponse(appSequence,0x6e,[NSData dataWithBytes:(uint8_t[]){0,0,2,1,30} length:5],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks == 13 && [appResult[@"calibration"][@"state"] isEqualToString:@"Processing"] && [appResult[@"calibration"][@"percent"] intValue] == 30 && !gimbal.appCalibrationStatus, @"query return code is separate from TLV and does not populate notification cache");
        __block NSUInteger statusCallbacks = 0; gimbal.appStatusHandler = ^(NSDictionary *status) { statusCallbacks++; };
        NSMutableData *calPush = [AppResponse(1,0x6e,[NSData dataWithBytes:(uint8_t[]){0,2,2,100} length:4],4) mutableCopy];
        uint8_t *calP = calPush.mutableBytes; calP[8] = 0; uint16_t calCrc = 0x3692; for (NSUInteger ci=0;ci<calPush.length-2;ci++) { calCrc ^= calP[ci]; for (int cb=0;cb<8;cb++) calCrc = calCrc & 1 ? (calCrc >> 1) ^ 0x8408 : calCrc >> 1; } calP[calPush.length-2] = calCrc; calP[calPush.length-1] = calCrc >> 8;
        notify.value = calPush; [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(statusCallbacks == 1 && [gimbal.appCalibrationStatus[@"state"] isEqualToString:@"Complete"] && ![gimbal.appCalibrationStatus[@"physicalCompletionVerified"] boolValue], @"native passive calibration report has no program completion guarantee");
        Require([gimbal useAppProfile:@"ronin-2.2.2"] && !gimbal.appCalibrationStatus, @"explicit profile reselection resets cached calibration report");
        [peripheral.writes setLength:0]; [gimbal setMotorTuning:@{@"axis":@"pitch",@"parameter":@"stiffness",@"value":@4} timeoutMs:1000 completion:appDone]; PumpCallbacks();
        Require(appCallbacks==14 && peripheral.writes.length==0 && !gimbal.busy && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"invalid motor range rejected before stopping");
        [gimbal setMotorTuning:@{@"axis":@"roll",@"parameter":@"stiffness",@"value":@50} timeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [decoder reset]; frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x31 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){1,1,50} length:3]],@"motor setter owns slot and uses31 namespace");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; notify.value=AppResponse(appSequence,0x31,ok,4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks==15 && !gimbal.busy && [appResult[@"requestedValue"] intValue]==50 && [appResult[@"axis"] isEqualToString:@"roll"] && ![appResult[@"physicalCompletionVerified"] boolValue],@"motor ACK validates no parameter body and does not imply physical effect");
        [peripheral.writes setLength:0]; [gimbal getMotorTuning:@{@"axis":@"yaw"} timeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [decoder reset]; frames=[decoder push:peripheral.writes];
        Require([frames.lastObject[@"commandId"] intValue]==0x32 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){2,5,8,11} length:4]],@"native motor selection uses32 and source indexes");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; notify.value=AppResponse(appSequence,0x32,[NSData dataWithBytes:(uint8_t[]){0,2,9,255,5,1,30,8,1,0,11,1,100} length:13],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks==16 && [appResult[@"values"] count]==4 && [appResult[@"values"][0][@"rawValue"] intValue]==255 && ![appResult[@"values"][0][@"withinSourceRange"] boolValue],@"native motor decode retains unknown source value without guessing defaults");
        [peripheral.writes setLength:0]; [gimbal sendBalanceTestRequestWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [decoder reset]; frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x0f && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){37,1,64} length:3]],@"balance start owns request ACK and selects0F not40");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; notify.value=AppResponse(appSequence,0x0f,ok,4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks==17 && !gimbal.busy && [appResult[@"requestedValue"] intValue]==64 && ![appResult[@"physicalCompletionVerified"] boolValue],@"balance ACK releases host slot without claiming physical completion");
        [peripheral.writes setLength:0]; [gimbal getBalanceTestStatusWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [decoder reset]; frames=[decoder push:peripheral.writes];
        Require([frames.lastObject[@"commandId"] intValue]==0x10 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){37} length:1]],@"balance status uses named read index37");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,37,9,0x90} length:4],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks==18 && [appResult[@"balance"][@"state"] isEqualToString:@"FINISH"] && appResult[@"balance"][@"axisResults"][@"yaw"][@"result"]==NSNull.null && [appResult[@"parameters"][0][@"headerByte"] intValue]==9,@"balance decode keeps invalid results and external width");
        [peripheral.writes setLength:0]; [gimbal sendBalanceTestRequestWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal); [gimbal stop]; ThreeTicks(gimbal); PumpCallbacks();
        [decoder reset]; frames=[decoder push:peripheral.writes]; NSUInteger balanceWrites=0;
        for (NSDictionary *f in frames) if ([f[@"commandId"] intValue]==0x0f) { balanceWrites++; Require([f[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){37,1,64} length:3]],@"no invented balance abort value"); }
        Require(appCallbacks==19 && balanceWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"balance cancellation clears pending without replay");
        [peripheral.writes setLength:0]; [gimbal sendAutoCalibrationRequestWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [decoder reset]; frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x0f && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){36,1,1} length:3]],@"system calibration owns ACK and is distinct from6A/08");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; notify.value=AppResponse(appSequence,0x0f,ok,4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks==20 && !gimbal.busy && [appResult[@"requestedValue"] intValue]==1 && ![appResult[@"physicalCompletionVerified"] boolValue],@"system calibration request ACK does not prove completion");
        [peripheral.writes setLength:0]; [gimbal getAutoCalibrationStatusWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [decoder reset]; frames=[decoder push:peripheral.writes];
        Require([frames.lastObject[@"commandId"] intValue]==0x10 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){36} length:1]],@"system calibration reads named36 via10");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,36,9,3} length:4],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks==21 && [appResult[@"systemCalibration"][@"state"] isEqualToString:@"SUCCESS"] && [appResult[@"parameters"][0][@"headerByte"] intValue]==9,@"system status allows source enum3 beyond write range and keeps raw header");
        [gimbal getAutoCalibrationStatusWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,36,1,255} length:4],4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks==22 && appResult[@"systemCalibration"][@"state"]==NSNull.null && [appResult[@"systemCalibration"][@"rawValue"] intValue]==255,@"unknown system status never becomes success or default");
        [peripheral.writes setLength:0]; [gimbal sendAutoCalibrationRequestWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal); [gimbal stop]; ThreeTicks(gimbal); PumpCallbacks();
        [decoder reset]; frames=[decoder push:peripheral.writes]; NSUInteger systemWrites=0;
        for (NSDictionary *f in frames) if ([f[@"commandId"] intValue]==0x0f) { systemWrites++; Require([f[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){36,1,1} length:3]],@"system calibration cancellation never writes zero abort"); }
        Require(appCallbacks==23 && systemWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"system cancellation clears host transaction without replay");
        [peripheral.writes setLength:0];[gimbal setFollowSettings:@"speed" settings:@{@"yaw":@1} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==24 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"invalid packed mode rejects before stopping");
        NSMutableString *modePatch=[NSMutableString stringWithString:@"custom"];[gimbal setFollowSettings:@"speed" settings:@{@"yaw":modePatch} timeoutMs:1000 completion:appDone];[modePatch setString:@"high"];ThreeTicks(gimbal);
        [decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x10 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){65} length:1]],@"mode setting first reads current shared register");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];double modeDeadline=[[gimbal valueForKey:@"deviceQueryDeadline"] doubleValue];
        notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,65,9,255} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        uint16_t modeSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && modeSequence!=appSequence && [[gimbal valueForKey:@"deviceQueryDeadline"] doubleValue]==modeDeadline && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){65,1,63} length:3]],@"mode read modify write preserves low bits and shares deadline/owner");
        notify.value=AppResponse(modeSequence,0x0f,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==25 && !gimbal.busy && [appResult[@"requestedRawValue"] intValue]==63 && ![appResult[@"physicalCompletionVerified"] boolValue],@"mode write finishes only after correlated ACK");
        [gimbal getRcSettings:@"smoothing" timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,69,1,0x9b} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==26 && [appResult[@"settings"][@"pitch"] isEqualToString:@"middle"] && [appResult[@"unknownBits"] intValue]==3,@"RC mode getter uses same axis schema with named index69");
        [peripheral.writes setLength:0];[gimbal setRcSettings:@"deadZone" settings:@{@"roll":@"low"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();
        [decoder reset];frames=[decoder push:peripheral.writes];BOOL modeWritten=NO;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==0x0f)modeWritten=YES;
        Require(appCallbacks==27 && !modeWritten && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"cancel before mode read reply prevents write");
        [peripheral.writes setLength:0];[gimbal setFollowTuning:@{@"axis":@"pitch",@"parameter":@"speed",@"value":@0} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==28 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"invalid numeric source range rejects before stopping");
        NSMutableDictionary *numericSpec=[@{@"axis":@"pitch",@"parameter":@"speed",@"value":@100} mutableCopy];[gimbal setFollowTuning:numericSpec timeoutMs:1000 completion:appDone];numericSpec[@"value"]=@50;ThreeTicks(gimbal);
        [decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x0f && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){3,2,100,0} length:4]],@"numeric setter copies value and sends one named two-byte write");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x0f,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==29 && !gimbal.busy && [appResult[@"requestedValue"] intValue]==100 && ![appResult[@"physicalCompletionVerified"] boolValue] && ![appResult[@"activePresetVerified"] boolValue],@"numeric ACK releases host slot without physical or active-preset claim");
        [peripheral.writes setLength:0];[gimbal getRcTuning:@{@"axis":@"yaw",@"parameter":@"smoothing"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require([frames.lastObject[@"commandId"] intValue]==0x10 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){8} length:1]],@"numeric RC getter queries ordinary index8 without switching inputs");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,8,9,0x34,0x12} length:5],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==30 && [appResult[@"values"][0][@"rawValue"] intValue]==4660 && ![appResult[@"values"][0][@"withinSourceRange"] boolValue],@"numeric native query preserves unknown unsigned feedback");
        [peripheral.writes setLength:0];[gimbal setRcTuning:@{@"axis":@"roll",@"parameter":@"deadZone",@"value":@0} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();
        [decoder reset];frames=[decoder push:peripheral.writes];NSUInteger numericWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==0x0f)numericWrites++;
        Require(appCallbacks==31 && numericWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"numeric cancellation clears pending ACK without replay");
        [gimbal getFollowSensitivityWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [gimbal centralManager:(id)central didDisconnectPeripheral:(id)peripheral error:nil]; PumpCallbacks();
        Require(appCallbacks == 32 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_DISCONNECTED"], @"native disconnect rejects pending App query");
        [gimbal disconnect]; ThreeTicks(gimbal);
        printf("Native fake-device lifecycle checks: %lu passed (no Bluetooth manager created)\n", (unsigned long)assertions);
    }
    return 0;
}
