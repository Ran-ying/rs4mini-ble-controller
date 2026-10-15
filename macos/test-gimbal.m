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
@property(nonatomic, strong) NSMutableData *writes;
@end
@implementation FakePeripheral
- (void)discoverServices:(NSArray *)services {}
- (void)discoverCharacteristics:(NSArray *)characteristics forService:(id)service {}
- (void)setNotifyValue:(BOOL)value forCharacteristic:(id)characteristic {}
- (void)writeValue:(NSData *)value forCharacteristic:(id)characteristic type:(CBCharacteristicWriteType)type {
    [self.writes appendData:value]; if (self.pauseAfterChunk) { self.canSendWriteWithoutResponse = NO; self.pauseAfterChunk = NO; }
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
        [gimbal disconnect]; ThreeTicks(gimbal);
        printf("Native fake-device lifecycle checks: %lu passed (no Bluetooth manager created)\n", (unsigned long)assertions);
    }
    return 0;
}
