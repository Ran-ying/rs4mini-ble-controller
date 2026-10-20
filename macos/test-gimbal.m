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
@property(nonatomic) BOOL pauseOnParameterSubscription;
@property(nonatomic, strong) NSMutableData *writes;
@end
@implementation FakePeripheral
- (void)discoverServices:(NSArray *)services {}
- (void)discoverCharacteristics:(NSArray *)characteristics forService:(id)service {}
- (void)setNotifyValue:(BOOL)value forCharacteristic:(id)characteristic {}
- (void)writeValue:(NSData *)value forCharacteristic:(id)characteristic type:(CBCharacteristicWriteType)type {
    [self.writes appendData:value]; if(self.pauseOnParameterSubscription && value.length>=11 && ((const uint8_t *)value.bytes)[0]==85 && ((const uint8_t *)value.bytes)[10]==18){self.canSendWriteWithoutResponse=NO;self.pauseOnParameterSubscription=NO;} if (self.pauseAfterChunk || (self.pauseAfterShortChunk && value.length < 20)) { self.canSendWriteWithoutResponse = NO; self.pauseAfterChunk = NO; self.pauseAfterShortChunk = NO; }
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
static NSData *AppNotification(uint16_t sequence,uint8_t command,NSData *payload) {
    NSMutableData *data=[AppResponse(sequence,command,payload,4) mutableCopy];uint8_t *p=data.mutableBytes;p[8]=0;uint16_t crc=0x3692;
    for(NSUInteger i=0;i<data.length-2;i++){crc^=p[i];for(int b=0;b<8;b++)crc=crc&1?(crc>>1)^0x8408:crc>>1;}
    p[data.length-2]=crc&255;p[data.length-1]=crc>>8;return data;
}
static NSData *FlaggedApp(uint16_t sequence,uint8_t command,NSData *payload,uint8_t flags){NSMutableData *data=[AppResponse(sequence,command,payload,4) mutableCopy];uint8_t *p=data.mutableBytes;p[8]=flags;uint16_t crc=0x3692;for(NSUInteger i=0;i<data.length-2;i++){crc^=p[i];for(int bit=0;bit<8;bit++)crc=crc&1?(crc>>1)^0x8408:crc>>1;}p[data.length-2]=crc&255;p[data.length-1]=crc>>8;return data;}
static NSData *CenterResponse(uint16_t sequence,NSData *body,uint8_t sender,uint8_t flags,uint8_t set){NSMutableData *d=[AppResponse(sequence,50,body,sender) mutableCopy];uint8_t *p=d.mutableBytes;p[8]=flags;p[9]=set;uint16_t crc=0x3692;for(NSUInteger i=0;i<d.length-2;i++){crc^=p[i];for(int bit=0;bit<8;bit++)crc=crc&1?(crc>>1)^0x8408:crc>>1;}p[d.length-2]=crc&255;p[d.length-1]=crc>>8;return d;}
static void PumpCallbacks(void) { [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.003]]; }
int main(void) {
    @autoreleasepool {
        FakeCentral *central = [FakeCentral new]; central.state = CBManagerStatePoweredOn;
        __block NSString *lastStatus = nil;
        __block BOOL lastStatusReady = NO;
        RSGimbal *gimbal = [[RSGimbal alloc] initWithStatus:^(NSString *text, BOOL ready) { lastStatus = text; lastStatusReady = ready; } central:(id)central];
        FakePeripheral *peripheral = Connect(gimbal, central);
        __block NSUInteger cipherRawEvents=0,cipherTelemetryEvents=0;gimbal.messageHandler=^(NSDictionary *m){if([m[@"flags"] intValue]==3)cipherRawEvents++;};gimbal.telemetryHandler=^(NSDictionary *sample){cipherTelemetryEvents++;};
        [gimbal moveTo:@{@"pan":@5}];ThreeTicks(gimbal);NSMutableData *cipherJoints=[NSMutableData dataWithLength:49];((uint8_t *)cipherJoints.mutableBytes)[16]=244;((uint8_t *)cipherJoints.mutableBytes)[17]=1;FakeCharacteristic *cipherRx=[gimbal valueForKey:@"rx"];cipherRx.value=FlaggedApp(1,5,cipherJoints,3);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)cipherRx error:nil];
        Require(cipherRawEvents==1 && cipherTelemetryEvents==0 && ![gimbal valueForKey:@"latestJoints"] && gimbal.busy,@"cipher joint target stays raw and cannot feed native position loop");[gimbal stop];ThreeTicks(gimbal);gimbal.messageHandler=nil;gimbal.telemetryHandler=nil;[peripheral.writes setLength:0];
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
        NSData *externalBody=[NSData dataWithBytes:(uint8_t[]){2,7,1,0,128,255,127,0,0} length:9];
        __block NSUInteger externalEvents=0;gimbal.appStatusHandler=^(NSDictionary *status){if([status[@"kind"] isEqual:@"externalDevice"]){externalEvents++;@throw [NSException exceptionWithName:@"externalObserver" reason:nil userInfo:nil];}};
        [peripheral.writes setLength:0];notify.value=AppNotification(1,105,externalBody);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(externalEvents==1 && [gimbal.appExternalDeviceStatus[@"records"][0][@"speedControl"][@"sourcePitchSpeed"] intValue]==-32768 && peripheral.writes.length==0,@"external passive cache survives observer failure without sending");
        NSDictionary *externalBefore=gimbal.appExternalDeviceStatus;notify.value=AppResponse(1,105,externalBody,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];notify.value=AppNotification(1,105,[NSData dataWithBytes:(uint8_t[]){2,7,1} length:3]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require([gimbal.appExternalDeviceStatus isEqual:externalBefore] && externalEvents==1,@"external ACK and malformed TLV retain complete old snapshot");
        notify.value=AppNotification(1,105,[NSData dataWithBytes:(uint8_t[]){255,0} length:2]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require(!gimbal.appExternalDeviceStatus[@"records"][0][@"speedControl"] && externalEvents==2,@"external unknown-only frame does not inherit stale speeds");
        Require([gimbal useAppProfile:@"ronin-2.2.2"] && !gimbal.appExternalDeviceStatus,@"source reselection clears external cache");
        __block NSUInteger externalQueryCallbacks=0;[gimbal getWorkModeWithTimeoutMs:1000 completion:^(NSDictionary *result,NSError *error){externalQueryCallbacks++;}];ThreeTicks(gimbal);NSUInteger externalWrites=peripheral.writes.length;
        notify.value=AppNotification(1,105,externalBody);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require(gimbal.busy && externalQueryCallbacks==0 && externalEvents==3 && peripheral.writes.length==externalWrites,@"external status never completes query or changes ownership/writes");
        uint16_t externalQuerySequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(externalQuerySequence,16,[NSData dataWithBytes:(uint8_t[]){0,62,1,2} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();Require(externalQueryCallbacks==1 && !gimbal.busy,@"real matching query ACK still completes after external report");
        gimbal.appStatusHandler=nil;[gimbal useAppProfile:@"ronin-2.2.2"];[peripheral.writes setLength:0];
        NSData *sensorBody=[NSData dataWithBytes:(uint8_t[]){255,3,170} length:3];__block NSUInteger sensorStatusEvents=0;
        gimbal.appStatusHandler=^(NSDictionary *status){if([status[@"kind"] isEqual:@"sensorCalibration"]){sensorStatusEvents++;@throw [NSException exceptionWithName:@"sensorObserver" reason:nil userInfo:nil];}};
        notify.value=AppNotification(1,48,sensorBody);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require(sensorStatusEvents==1 && [gimbal.appSensorCalibrationStatus[@"sourceStatus"] isEqual:@"FAIL"] && [gimbal.appSensorCalibrationStatus[@"rawProgressValue"] intValue]==255 && peripheral.writes.length==0,@"sensor source cached independently despite observer error, without sends");
        NSDictionary *sensorBefore=gimbal.appSensorCalibrationStatus;notify.value=AppResponse(1,48,sensorBody,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];notify.value=AppNotification(1,48,[NSData dataWithBytes:(uint8_t[]){0} length:1]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require([gimbal.appSensorCalibrationStatus isEqual:sensorBefore] && sensorStatusEvents==1,@"short and ACK sensor reports preserve complete cache");
        Require(!gimbal.appCalibrationStatus && !gimbal.appExternalDeviceStatus,@"sensor calibration does not populate auto-tune or external caches");Require([gimbal useAppProfile:@"ronin-2.2.2"] && !gimbal.appSensorCalibrationStatus,@"source reselection clears sensor cache");
        __block NSUInteger sensorQueryCallbacks=0;[gimbal getWorkModeWithTimeoutMs:1000 completion:^(NSDictionary *result,NSError *error){sensorQueryCallbacks++;}];ThreeTicks(gimbal);NSUInteger sensorWrites=peripheral.writes.length;
        notify.value=AppNotification(1,48,[NSData dataWithBytes:(uint8_t[]){100,0} length:2]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require(gimbal.busy && sensorQueryCallbacks==0 && sensorStatusEvents==2 && peripheral.writes.length==sensorWrites && ![gimbal.appSensorCalibrationStatus[@"physicalCompletionVerified"] boolValue],@"COMPLETE source event neither completes query nor changes native ownership/writes");
        uint16_t sensorQuerySequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(sensorQuerySequence,16,[NSData dataWithBytes:(uint8_t[]){0,62,1,2} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();Require(sensorQueryCallbacks==1 && !gimbal.busy,@"actual query ACK still completes after sensor COMPLETE event");
        gimbal.appStatusHandler=nil;[gimbal useAppProfile:@"ronin-2.2.2"];[peripheral.writes setLength:0];
        __block NSUInteger cipherCallbacks=0;__block NSError *cipherAppError=nil;[gimbal setMotorSettings:@{@"forbidSelfie":@YES} timeoutMs:1000 completion:^(NSDictionary *result,NSError *error){cipherCallbacks++;cipherAppError=error;}];ThreeTicks(gimbal);uint16_t cipherSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=FlaggedApp(cipherSequence,16,[NSData dataWithBytes:(uint8_t[]){0,35,1,0} length:4],131);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];BOOL cipherWrite=NO;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==15)cipherWrite=YES;Require(cipherCallbacks==1 && [cipherAppError.userInfo[@"code"] isEqual:@"RS4MINI_PROTOCOL_ERROR"] && !cipherWrite && !gimbal.busy,@"encrypted preflight ACK cannot advance native RMW write");
        notify.value=AppNotification(1,110,[NSData dataWithBytes:(uint8_t[]){0,2,1,20} length:4]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];NSDictionary *cipherCalBefore=gimbal.appCalibrationStatus;notify.value=FlaggedApp(1,110,[NSData dataWithBytes:(uint8_t[]){0,2,2,100} length:4],3);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require([gimbal.appCalibrationStatus isEqual:cipherCalBefore],@"cipher calibration status preserves last valid plaintext cache");[gimbal useAppProfile:@"ronin-2.2.2"];[peripheral.writes setLength:0];
        __block NSDictionary *componentResult=nil;__block NSError *componentError=nil;__block NSUInteger componentCallbacks=0;
        RSAppCompletion componentDone=^(NSDictionary *r,NSError *e){componentResult=r;componentError=e;componentCallbacks++;};
        [gimbal useAppProfile:@"ronin-2.2.2"];[peripheral.writes setLength:0];
        [gimbal sendComponentCalibrationRequest:@{@"sourcePart":@"GYRO"} timeoutMs:1000 completion:componentDone];PumpCallbacks();Require(componentCallbacks==1 && peripheral.writes.length==0 && [componentError.userInfo[@"code"] isEqual:@"RS4MINI_INVALID_ARGUMENT"],@"component source validation before frames");
        [gimbal sendComponentCalibrationRequest:@{@"sourcePart":@"AUTO"} timeoutMs:1000 completion:componentDone];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];uint16_t componentRead=[frames.lastObject[@"sequence"] unsignedShortValue];NSTimeInterval componentDeadline=[[gimbal valueForKey:@"deviceQueryDeadline"] doubleValue];
        Require(gimbal.busy && frames.count==4 && [frames.lastObject[@"commandId"] intValue]==16 && [frames.lastObject[@"payload"] isEqual:[NSData dataWithBytes:(uint8_t[]){35} length:1]] && ![gimbal useAppProfile:@"ronin-2.2.2"],@"component owns fresh motor preflight after neutral stops");
        notify.value=AppResponse(componentRead,16,[NSData dataWithBytes:(uint8_t[]){0,35,1,128} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];[decoder reset];frames=[decoder push:peripheral.writes];uint16_t componentStart=[frames.lastObject[@"sequence"] unsignedShortValue];
        Require(gimbal.busy && componentRead!=componentStart && [frames.lastObject[@"commandId"] intValue]==8 && [frames.lastObject[@"flags"] intValue]==64 && [[gimbal valueForKey:@"deviceQueryDeadline"] doubleValue]==componentDeadline,@"component starts once under same deadline after enabled read");
        for(NSData *wrong in @[AppResponse(componentStart+1,8,[NSData dataWithBytes:(uint8_t[]){0,0,1} length:3],4),AppNotification(componentStart,8,[NSData dataWithBytes:(uint8_t[]){0,1} length:2]),AppResponse(componentStart,8,[NSData dataWithBytes:(uint8_t[]){0,0,1} length:3],5)]){notify.value=wrong;[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];}Require(gimbal.busy && componentCallbacks==1,@"component rejects stale sequence, request bit and wrong endpoint");
        notify.value=AppResponse(componentStart,8,[NSData dataWithBytes:(uint8_t[]){0,0,0} length:3],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();Require(componentCallbacks==2 && !componentError && !gimbal.busy && [componentResult[@"calibration"][@"sourceStatus"] isEqual:@"FAIL"] && [componentResult[@"motorPreflightRawValue"] intValue]==128 && !gimbal.appCalibrationStatus && !gimbal.appSensorCalibrationStatus,@"component ACK success and business FAIL separate without cache updates");
        for(NSData *body in @[[NSData dataWithBytes:(uint8_t[]){0,35,1,1} length:4],[NSData dataWithBytes:(uint8_t[]){7} length:1],[NSData dataWithBytes:(uint8_t[]){0,35,1} length:3]]){[peripheral.writes setLength:0];[gimbal sendComponentCalibrationRequest:@{@"sourcePart":@"AUTO"} timeoutMs:1000 completion:componentDone];ThreeTicks(gimbal);uint16_t read=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(read,16,body,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];BOOL started=NO;for(NSDictionary *f in frames)started|=[f[@"commandId"] intValue]==8;Require(componentError && !gimbal.busy && !started,@"component disabled, NACK or malformed preflight sends no start");}
        [peripheral.writes setLength:0];[gimbal sendComponentCalibrationRequest:@{@"sourcePart":@"AUTO"} timeoutMs:1000 completion:componentDone];ThreeTicks(gimbal);componentRead=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];[gimbal setValue:@0 forKey:@"deviceQueryDeadline"];notify.value=AppResponse(componentRead,16,[NSData dataWithBytes:(uint8_t[]){0,35,1,0} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];BOOL componentStarted=NO;for(NSDictionary *f in frames)componentStarted|=[f[@"commandId"] intValue]==8;Require(!componentStarted && [componentError.userInfo[@"code"] isEqual:@"RS4MINI_RESPONSE_TIMEOUT"],@"component expired preflight never sends start");
        [peripheral.writes setLength:0];[gimbal sendComponentCalibrationRequest:@{@"sourcePart":@"AUTO"} timeoutMs:1000 completion:componentDone];ThreeTicks(gimbal);componentRead=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();notify.value=AppResponse(componentRead,16,[NSData dataWithBytes:(uint8_t[]){0,35,1,0} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];[decoder reset];frames=[decoder push:peripheral.writes];componentStarted=NO;for(NSDictionary *f in frames)componentStarted|=[f[@"commandId"] intValue]==8;Require(!componentStarted && [componentError.userInfo[@"code"] isEqual:@"RS4MINI_OPERATION_CANCELLED"],@"component cancelled read ignores late response");
        [peripheral.writes setLength:0];[gimbal sendComponentCalibrationRequest:@{@"sourcePart":@"AUTO"} timeoutMs:1000 completion:componentDone];ThreeTicks(gimbal);componentRead=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(componentRead,16,[NSData dataWithBytes:(uint8_t[]){0,35,1,0} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger componentSends=0;for(NSDictionary *f in frames)componentSends+=[f[@"commandId"] intValue]==8;Require(componentSends==1 && [componentError.userInfo[@"code"] isEqual:@"RS4MINI_OPERATION_CANCELLED"],@"component stop after send does not invent inverse calibration request");
        [peripheral.writes setLength:0];[gimbal useAppProfile:@"ronin-2.2.2"];
        for(NSNumber *flags in @[@128,@131]){[peripheral.writes setLength:0];[gimbal sendComponentCalibrationRequest:@{@"sourcePart":@"AUTO"} timeoutMs:1000 completion:componentDone];ThreeTicks(gimbal);componentRead=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(componentRead,16,[NSData dataWithBytes:(uint8_t[]){0,35,1,0} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];componentStart=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=FlaggedApp(componentStart,8,[NSData dataWithBytes:(uint8_t[]){1,0,1} length:3],flags.unsignedCharValue);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];ThreeTicks(gimbal);PumpCallbacks();Require(!gimbal.busy && componentError && ![gimbal valueForKey:@"appSettingsBefore"] && !gimbal.appCalibrationStatus,@"component ACK NACK/cipher releases ownership and preflight without cache");}
        [peripheral.writes setLength:0];[gimbal useAppProfile:@"ronin-2.2.2"];
        FakeCentral *tutorialCentral=[FakeCentral new];tutorialCentral.state=CBManagerStatePoweredOn;
        RSGimbal *tutorialGimbal=[[RSGimbal alloc] initWithStatus:^(NSString *text,BOOL ready){} central:(id)tutorialCentral];FakePeripheral *tutorialPeripheral=Connect(tutorialGimbal,tutorialCentral);FakeCharacteristic *tutorialNotify=(id)[(FakeService *)tutorialPeripheral.services.firstObject characteristics].firstObject;
        NSData *tutorialBody=[NSData dataWithBytes:(uint8_t[]){255,255,255,255,255,170} length:6];tutorialNotify.value=AppNotification(1,43,tutorialBody);[tutorialGimbal peripheral:(id)tutorialPeripheral didUpdateValueForCharacteristic:(id)tutorialNotify error:nil];Require(!tutorialGimbal.appTutorialStatus && tutorialPeripheral.writes.length==0,@"tutorial requires explicit source without sends");
        [tutorialGimbal useAppProfile:@"ronin-2.2.2"];__block NSUInteger tutorialEvents=0;tutorialGimbal.appStatusHandler=^(NSDictionary *r){if([r[@"kind"] isEqual:@"tutorial"]){tutorialEvents++;@throw [NSException exceptionWithName:@"tutorialObserver" reason:@"isolated" userInfo:nil];}};
        [tutorialGimbal peripheral:(id)tutorialPeripheral didUpdateValueForCharacteristic:(id)tutorialNotify error:nil];NSDictionary *tutorialBefore=tutorialGimbal.appTutorialStatus;Require(tutorialEvents==1 && [tutorialBefore[@"knownSourceStepName"] isEqual:NSNull.null] && [tutorialBefore[@"rawCompletionWord"] unsignedLongLongValue]==4294967295ULL && ![tutorialBefore[@"physicalCompletionVerified"] boolValue],@"tutorial observer isolated and unknown source fallback preserved");
        for(NSData *bad in @[AppResponse(1,43,tutorialBody,4),FlaggedApp(1,43,tutorialBody,3),AppNotification(1,43,[NSData dataWithBytes:(uint8_t[]){0} length:1])]){tutorialNotify.value=bad;[tutorialGimbal peripheral:(id)tutorialPeripheral didUpdateValueForCharacteristic:(id)tutorialNotify error:nil];}Require(tutorialEvents==1 && [tutorialGimbal.appTutorialStatus isEqual:tutorialBefore] && tutorialPeripheral.writes.length==0,@"tutorial bad notifications preserve full cache and send no ACK or steps");
        Require([tutorialGimbal useAppProfile:@"ronin-2.2.2"] && !tutorialGimbal.appTutorialStatus,@"tutorial source reselection clears cache");__block NSUInteger tutorialQueryCallbacks=0;[tutorialGimbal getWorkModeWithTimeoutMs:1000 completion:^(NSDictionary *r,NSError *e){tutorialQueryCallbacks++;}];ThreeTicks(tutorialGimbal);uint16_t tutorialQuerySequence=[[tutorialGimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];NSUInteger tutorialQueryWrites=tutorialPeripheral.writes.length;tutorialNotify.value=AppNotification(tutorialQuerySequence,43,[NSData dataWithBytes:(uint8_t[]){0,255,255,255,255} length:5]);[tutorialGimbal peripheral:(id)tutorialPeripheral didUpdateValueForCharacteristic:(id)tutorialNotify error:nil];Require(tutorialGimbal.busy && tutorialQueryCallbacks==0 && tutorialPeripheral.writes.length==tutorialQueryWrites,@"tutorial finish-looking notification cannot complete or write into query");tutorialNotify.value=AppResponse(tutorialQuerySequence,16,[NSData dataWithBytes:(uint8_t[]){0,62,1,2} length:4],4);[tutorialGimbal peripheral:(id)tutorialPeripheral didUpdateValueForCharacteristic:(id)tutorialNotify error:nil];PumpCallbacks();Require(tutorialQueryCallbacks==1 && !tutorialGimbal.busy,@"actual query ACK remains independent from tutorial");
        [tutorialGimbal moveTo:@{@"pan":@5}];ThreeTicks(tutorialGimbal);tutorialNotify.value=AppNotification(1,43,tutorialBody);[tutorialGimbal peripheral:(id)tutorialPeripheral didUpdateValueForCharacteristic:(id)tutorialNotify error:nil];Require(tutorialGimbal.busy && ![tutorialGimbal valueForKey:@"latestJoints"] && !tutorialGimbal.appSensorCalibrationStatus && !tutorialGimbal.appCalibrationStatus,@"tutorial cannot supply feedback or complete position operation");[tutorialGimbal stop];ThreeTicks(tutorialGimbal);[tutorialGimbal disconnect];ThreeTicks(tutorialGimbal);Require(!tutorialGimbal.appTutorialStatus && !tutorialGimbal.ready,@"tutorial cache cleared on disconnect");
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
        Require(lastStatusReady && !gimbal.busy && [lastStatus isEqual:@"App 请求已结束（不代表设备动作完成）"], @"successful query publishes idle status so GUI motion buttons recover");
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
        Require(lastStatusReady && [lastStatus isEqual:@"App 请求失败或取消，详情见请求结果"], @"failed query publishes completed cleanup status without claiming success");
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
        Require(![gimbal respondsToSelector:NSSelectorFromString(@"queryCalibrationStatusWithTimeoutMs:completion:")],@"active calibration query removed");
        for(NSString *name in @[@"getAutoCalibrationStatusWithTimeoutMs:completion:",@"sendAutoCalibrationRequestWithTimeoutMs:completion:",@"getBalanceTestStatusWithTimeoutMs:completion:",@"sendBalanceTestRequestWithTimeoutMs:completion:"]) Require(![gimbal respondsToSelector:NSSelectorFromString(name)],@"ineffective legacy entry removed");
        __block NSUInteger statusCallbacks = 0; gimbal.appStatusHandler = ^(NSDictionary *status) { statusCallbacks++; };
        NSMutableData *calPush = [AppResponse(1,0x6e,[NSData dataWithBytes:(uint8_t[]){0,2,2,100} length:4],4) mutableCopy];
        uint8_t *calP = calPush.mutableBytes; calP[8] = 0; uint16_t calCrc = 0x3692; for (NSUInteger ci=0;ci<calPush.length-2;ci++) { calCrc ^= calP[ci]; for (int cb=0;cb<8;cb++) calCrc = calCrc & 1 ? (calCrc >> 1) ^ 0x8408 : calCrc >> 1; } calP[calPush.length-2] = calCrc; calP[calPush.length-1] = calCrc >> 8;
        notify.value = calPush; [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(statusCallbacks == 1 && [gimbal.appCalibrationStatus[@"state"] isEqualToString:@"Complete"] && ![gimbal.appCalibrationStatus[@"physicalCompletionVerified"] boolValue], @"native passive calibration report has no program completion guarantee");
        Require([gimbal useAppProfile:@"ronin-2.2.2"] && !gimbal.appCalibrationStatus, @"explicit profile reselection resets cached calibration report");
        [peripheral.writes setLength:0]; [gimbal setMotorTuning:@{@"axis":@"pitch",@"parameter":@"stiffness",@"value":@4} timeoutMs:1000 completion:appDone]; PumpCallbacks();
        Require(appCallbacks==13 && peripheral.writes.length==0 && !gimbal.busy && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"invalid motor range rejected before stopping");
        [gimbal setMotorTuning:@{@"axis":@"roll",@"parameter":@"stiffness",@"value":@50} timeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [decoder reset]; frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x31 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){1,1,50} length:3]],@"motor setter owns slot and uses31 namespace");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue]; notify.value=AppResponse(appSequence,0x31,ok,4);
        [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil]; PumpCallbacks();
        Require(appCallbacks==14 && !gimbal.busy && [appResult[@"requestedValue"] intValue]==50 && [appResult[@"axis"] isEqualToString:@"roll"] && ![appResult[@"physicalCompletionVerified"] boolValue],@"motor ACK validates no parameter body and does not imply physical effect");
        [peripheral.writes setLength:0]; [gimbal getMotorTuning:@{@"axis":@"yaw"} timeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        [decoder reset]; frames=[decoder push:peripheral.writes];
        for(NSUInteger mi=0;mi<4;mi++){
            uint8_t index=(uint8_t[]){2,5,8,11}[mi];[decoder reset];frames=[decoder push:peripheral.writes];
            Require(gimbal.busy && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:&index length:1]],@"native motor query requests exactly one index at a time");
            appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x32,[NSData dataWithBytes:(uint8_t[]){0,index,9,mi==0?255:20} length:4],4);
            [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
            if(mi<3){Require(appCallbacks==14 && gimbal.busy,@"no partial completion between records");[gimbal tick];}
        }
        Require(appCallbacks==15 && [appResult[@"values"] count]==4 && [appResult[@"replies"] count]==4 && [appResult[@"readMode"] isEqual:@"sequential"] && ![appResult[@"atomic"] boolValue] && !appResult[@"message"] && [appResult[@"values"][0][@"rawValue"] intValue]==255,@"native non-atomic aggregate retains actual replies");
        __block NSUInteger batchCallbacks=0;__block NSDictionary *batchResult=nil;__block NSError *batchError=nil;
        RSAppCompletion batchDone=^(NSDictionary *r,NSError *e){batchCallbacks++;batchResult=r;batchError=e;};
        for(NSUInteger scenario=0;scenario<3;scenario++){
            [peripheral.writes setLength:0];[gimbal getMotorTuning:@{} timeoutMs:1000 completion:batchDone];ThreeTicks(gimbal);
            if(scenario<2){
                appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x32,[NSData dataWithBytes:(uint8_t[]){0,0,1,10} length:4],4);
                [gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];[gimbal tick];
                Require(batchCallbacks==scenario && gimbal.busy,@"motor batch retains ownership after first response");
                if(scenario==0)[gimbal stop];
                else {appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x32,[NSData dataWithBytes:(uint8_t[]){7} length:1],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];}
            }else {[gimbal setValue:@(NSProcessInfo.processInfo.systemUptime-1) forKey:@"deviceQueryDeadline"];[gimbal tick];}
            ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger readCount=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==0x32)readCount++;
            Require(batchCallbacks==scenario+1 && batchResult==nil && !gimbal.busy,@"failed motor batch completes once without partial data");
            Require([batchError.userInfo[@"code"] isEqual:@[@"RS4MINI_OPERATION_CANCELLED",@"RS4MINI_DEVICE_ERROR",@"RS4MINI_RESPONSE_TIMEOUT"][scenario]],@"batch preserves cancel, NACK and total timeout errors");
            Require(readCount==(scenario<2?2:1) && ![gimbal valueForKey:@"appMotorReplies"],@"batch error clears pending data and stops later reads");
        }
        [peripheral.writes setLength:0];[gimbal setFollowSettings:@"speed" settings:@{@"yaw":@1} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==16 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"invalid packed mode rejects before stopping");
        NSMutableString *modePatch=[NSMutableString stringWithString:@"custom"];[gimbal setFollowSettings:@"speed" settings:@{@"yaw":modePatch} timeoutMs:1000 completion:appDone];[modePatch setString:@"high"];ThreeTicks(gimbal);
        [decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x10 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){65} length:1]],@"mode setting first reads current shared register");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];double modeDeadline=[[gimbal valueForKey:@"deviceQueryDeadline"] doubleValue];
        notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,65,9,255} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        uint16_t modeSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && modeSequence!=appSequence && [[gimbal valueForKey:@"deviceQueryDeadline"] doubleValue]==modeDeadline && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){65,1,63} length:3]],@"mode read modify write preserves low bits and shares deadline/owner");
        notify.value=AppResponse(modeSequence,0x0f,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==17 && !gimbal.busy && [appResult[@"requestedRawValue"] intValue]==63 && ![appResult[@"physicalCompletionVerified"] boolValue],@"mode write finishes only after correlated ACK");
        [gimbal getRcSettings:@"smoothing" timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
        notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,69,1,0x9b} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==18 && [appResult[@"settings"][@"pitch"] isEqualToString:@"middle"] && [appResult[@"unknownBits"] intValue]==3,@"RC mode getter uses same axis schema with named index69");
        [peripheral.writes setLength:0];[gimbal setRcSettings:@"deadZone" settings:@{@"roll":@"low"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();
        [decoder reset];frames=[decoder push:peripheral.writes];BOOL modeWritten=NO;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==0x0f)modeWritten=YES;
        Require(appCallbacks==19 && !modeWritten && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"cancel before mode read reply prevents write");
        [peripheral.writes setLength:0];[gimbal setFollowTuning:@{@"axis":@"pitch",@"parameter":@"speed",@"value":@0} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==20 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"invalid numeric source range rejects before stopping");
        NSMutableDictionary *numericSpec=[@{@"axis":@"pitch",@"parameter":@"speed",@"value":@100} mutableCopy];[gimbal setFollowTuning:numericSpec timeoutMs:1000 completion:appDone];numericSpec[@"value"]=@50;ThreeTicks(gimbal);
        [decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x0f && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){3,2,100,0} length:4]],@"numeric setter copies value and sends one named two-byte write");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x0f,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==21 && !gimbal.busy && [appResult[@"requestedValue"] intValue]==100 && ![appResult[@"physicalCompletionVerified"] boolValue] && ![appResult[@"activePresetVerified"] boolValue],@"numeric ACK releases host slot without physical or active-preset claim");
        [peripheral.writes setLength:0];[gimbal getRcTuning:@{@"axis":@"yaw",@"parameter":@"smoothing"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require([frames.lastObject[@"commandId"] intValue]==0x10 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){8} length:1]],@"numeric RC getter queries ordinary index8 without switching inputs");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,8,9,0x34,0x12} length:5],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==22 && [appResult[@"values"][0][@"rawValue"] intValue]==4660 && ![appResult[@"values"][0][@"withinSourceRange"] boolValue],@"numeric native query preserves unknown unsigned feedback");
        [peripheral.writes setLength:0];[gimbal setRcTuning:@{@"axis":@"roll",@"parameter":@"deadZone",@"value":@0} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();
        [decoder reset];frames=[decoder push:peripheral.writes];NSUInteger numericWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==0x0f)numericWrites++;
        Require(appCallbacks==23 && numericWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"numeric cancellation clears pending ACK without replay");
        [peripheral.writes setLength:0];[gimbal setStandaloneTuning:@{@"axis":@"pitch",@"parameter":@"speed",@"value":@100} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==24 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"standalone missing explicit source rejects before frames");
        NSMutableDictionary *standaloneSpec=[@{@"inputSource":@2,@"axis":@"pitch",@"parameter":@"speed",@"value":@100} mutableCopy];[gimbal setStandaloneTuning:standaloneSpec timeoutMs:1000 completion:appDone];standaloneSpec[@"value"]=@5;ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==0x0f && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){72,1,2,80,2,100,0} length:7]],@"standalone snapshots input and sends paired source/value packet");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x0f,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==25 && !gimbal.busy && [appResult[@"requestedInputSource"] intValue]==2 && [appResult[@"requestedValue"] intValue]==100 && ![appResult[@"physicalCompletionVerified"] boolValue],@"standalone ACK ends host ownership without physical claim");
        [peripheral.writes setLength:0];[gimbal getStandaloneTuning:@{@"axis":@"roll",@"parameter":@"smoothing"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require([frames.lastObject[@"commandId"] intValue]==0x10 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){72,76} length:2]],@"standalone getter reads source and named value without changing source");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,0x10,[NSData dataWithBytes:(uint8_t[]){0,72,9,1,76,9,255,255} length:8],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==26 && [appResult[@"inputSourceRaw"] intValue]==1 && [appResult[@"values"][0][@"rawValue"] intValue]==65535 && ![appResult[@"activePresetVerified"] boolValue],@"standalone read keeps actual source even when not2");
        [peripheral.writes setLength:0];[gimbal setStandaloneTuning:@{@"inputSource":@2,@"axis":@"yaw",@"parameter":@"speed",@"value":@0} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger standaloneWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==0x0f)standaloneWrites++;
        Require(appCallbacks==27 && standaloneWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"standalone cancel never replays or restores input source");
        [peripheral.writes setLength:0];NSMutableData *fixedBody=[NSMutableData dataWithLength:78];((uint8_t *)fixedBody.mutableBytes)[2]=1;((uint8_t *)fixedBody.mutableBytes)[9]=0x34;((uint8_t *)fixedBody.mutableBytes)[10]=0x12;
        notify.value=AppNotification(2,0x24,fixedBody);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require([gimbal.appUserParameterStatus[@"values"] count]==17 && [gimbal.appUserParameterStatus[@"preset"][@"sourceEnum"] isEqualToString:@"CUSTOM_2"] && peripheral.writes.length==0,@"native fixed report uses same connection without request or subscription");
        notify.value=AppNotification(3,0x24,[NSMutableData dataWithLength:73]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require([gimbal.appUserParameterStatus[@"preset"][@"rawValue"] intValue]==1 && ![gimbal.appUserParameterStatus[@"activePresetVerified"] boolValue],@"short fixed report does not replace cached state or verify active preset");
        Require([gimbal useAppProfile:@"ronin-2.2.2"] && !gimbal.appUserParameterStatus,@"native profile reselection clears fixed report");
        Require(![gimbal respondsToSelector:NSSelectorFromString(@"getHandleSettingsWithTimeoutMs:completion:")],@"active handle query removed");
        for(NSString *name in @[@"sendParameterSubscriptionRequest:completion:",@"sendProgramStatusSubscriptionRequest:timeoutMs:completion:",@"sendHandleSettingRequest:timeoutMs:completion:",@"sendHandheldStickControlRequest:timeoutMs:completion:",@"sendFactorySettingsResetRequest:timeoutMs:completion:",@"appParameterSubscriptionKeys"]) Require(![gimbal respondsToSelector:NSSelectorFromString(name)],@"retired SDK entry absent");
        [peripheral.writes setLength:0];[gimbal sendFineTuneRequest:@{@"axis":@"roll",@"adjustmentDegrees":@YES} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==28 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"fine validates before stop/frame");
        NSMutableString *fineAxis=[@"pitch" mutableCopy];NSMutableDictionary *fineInput=[@{@"axis":fineAxis,@"adjustmentDegrees":@(-1.29)} mutableCopy];[gimbal sendFineTuneRequest:fineInput timeoutMs:1000 completion:appDone];[fineAxis setString:@"roll"];fineInput[@"adjustmentDegrees"]=@2;ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==7 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){244,2} length:2]],@"fine snapshots mutable inputs and holds ACK ownership");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,7,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==29 && !gimbal.busy && [appResult[@"encodedTenths"] intValue]==-12 && [appResult[@"axis"] isEqualToString:@"pitch"] && ![appResult[@"stabilizationStateVerified"] boolValue] && ![appResult[@"physicalCompletionVerified"] boolValue],@"fine ACK does not assert pause or physical completion");
        [peripheral.writes setLength:0];[gimbal sendFineTuneRequest:@{@"axis":@"roll",@"adjustmentDegrees":@(.1)} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger fineWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==7)fineWrites++;
        Require(appCallbacks==30 && fineWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"fine cancel never replays or rolls back request");
        [peripheral.writes setLength:0];[gimbal sendAxisModeRequest:@{@"sourceMode":@"FPV"} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==31 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"axis rejects UI track label before writes");
        NSMutableString *axisName=[@"ThreeDRoll360" mutableCopy];[gimbal sendAxisModeRequest:@{@"sourceMode":axisName} timeoutMs:1000 completion:appDone];[axisName setString:@"ThreeAxis"];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==15 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){34,1,24} length:3]],@"axis request snapshots name and holds operation ownership");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,15,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==32 && !gimbal.busy && [appResult[@"requestedSourceMode"] isEqualToString:@"ThreeDRoll360"] && [appResult[@"requestedRawValue"] intValue]==24 && ![appResult[@"otherBitsPreservationVerified"] boolValue] && ![appResult[@"persistenceVerified"] boolValue] && ![appResult[@"physicalCompletionVerified"] boolValue],@"axis ACK is not physical or other-bit preservation proof");
        [peripheral.writes setLength:0];[gimbal getAxisModeWithTimeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==16 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){34} length:1]],@"native axis getter stops first and queries only34");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,16,[NSData dataWithBytes:(uint8_t[]){0,34,9,255} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==33 && [appResult[@"unknownBits"] intValue]==231 && [appResult[@"sourceMode"] isEqualToString:@"ThreeDRoll360"] && !gimbal.appUserParameterStatus,@"native axis read preserves packed raw value without cache mutation");
        [peripheral.writes setLength:0];[gimbal sendAxisModeRequest:@{@"sourceMode":@"TwoAxis"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,15,[NSData dataWithBytes:(uint8_t[]){7} length:1],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger axisWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==15)axisWrites++;
        Require(appCallbacks==34 && axisWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_DEVICE_ERROR"],@"axis NACK never retries or composes another mode write");
        [peripheral.writes setLength:0];[gimbal sendAxisModeRequest:@{@"sourceMode":@"ThreeAxis"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];axisWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==15)axisWrites++;
        Require(appCallbacks==35 && axisWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"axis cancel never sends inverse setting or replay");
        [peripheral.writes setLength:0];[gimbal sendSmoothTrackAxesRequest:@{@"axes":@{@"yaw":@1}} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==36 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"smooth requires booleans before pre-stop");
        NSMutableDictionary *smoothAxes=[@{@"roll":@NO,@"yaw":@YES} mutableCopy];[gimbal sendSmoothTrackAxesRequest:@{@"axes":smoothAxes} timeoutMs:1000 completion:appDone];smoothAxes[@"yaw"]=@NO;smoothAxes[@"pitch"]=@YES;ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==15 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){17,1,1,19,1,0} length:6]],@"smooth snapshots nested patch and owns until ACK");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,15,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==37 && !gimbal.busy && [appResult[@"requestedAxes"] isEqual:@{@"yaw":@YES,@"roll":@NO}] && ![appResult[@"atomicApplicationVerified"] boolValue] && ![appResult[@"activePresetVerified"] boolValue] && ![appResult[@"persistenceVerified"] boolValue],@"smooth ACK is not atomic application or active preset proof");
        [peripheral.writes setLength:0];[gimbal getSmoothTrackAxes:@{} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==16 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){17,18,19} length:3]],@"native smooth getter owns slot and reads only ordinary fields");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,16,[NSData dataWithBytes:(uint8_t[]){0,17,9,1,18,9,3,19,9,0} length:10],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==38 && [appResult[@"values"][0][@"enabled"] boolValue] && appResult[@"values"][1][@"enabled"]==NSNull.null && ![appResult[@"values"][2][@"enabled"] boolValue] && !gimbal.appUserParameterStatus,@"smooth query preserves unknown state and avoids passive cache mutation");
        [peripheral.writes setLength:0];[gimbal sendSmoothTrackAxesRequest:@{@"axes":@{@"yaw":@YES,@"pitch":@YES,@"roll":@YES}} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,15,[NSData dataWithBytes:(uint8_t[]){7} length:1],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger smoothWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==15)smoothWrites++;
        Require(appCallbacks==39 && smoothWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_DEVICE_ERROR"],@"smooth NACK never retries individual fields or rolls back");
        [peripheral.writes setLength:0];[gimbal sendSmoothTrackAxesRequest:@{@"axes":@{@"pitch":@NO}} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];smoothWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==15)smoothWrites++;
        Require(appCallbacks==40 && smoothWrites==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"smooth cancel never fills omitted axes or replays");
        [peripheral.writes setLength:0];[gimbal sendUserProfileRequest:@{@"sourceProfileValue":@YES} timeoutMs:1000 completion:appDone];PumpCallbacks();
        Require(appCallbacks==41 && peripheral.writes.length==0 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"profile rejects boolean before pre-stop");
        [gimbal getUserProfileWithTimeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==16 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){0} length:1]],@"native profile getter emits zero byte not empty request");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,16,[NSData dataWithBytes:(uint8_t[]){0,0,9,2} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==42 && [appResult[@"sourceUiName"] isEqualToString:@"M3"] && ![appResult[@"activePresetVerified"] boolValue] && !gimbal.appUserParameterStatus,@"profile read labels source UI without active preset or passive cache claim");
        [peripheral.writes setLength:0];[gimbal getWorkModeWithTimeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){62} length:1]],@"native work getter queries distinct62");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,16,[NSData dataWithBytes:(uint8_t[]){0,62,9,128} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==43 && [appResult[@"rawValue"] intValue]==128 && appResult[@"sourceMode"]==NSNull.null && [appResult[@"withinSourceRange"] boolValue],@"work unknown enum never falls back to stale mode");
        [peripheral.writes setLength:0];NSMutableDictionary *profileInput=[@{@"sourceProfileValue":@0} mutableCopy];[gimbal sendUserProfileRequest:profileInput timeoutMs:1000 completion:appDone];profileInput[@"sourceProfileValue"]=@5;ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){0,1,0} length:3]],@"profile write snapshots zero value and owns ACK");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,15,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==44 && [appResult[@"requestedSourceProfileValue"] intValue]==0 && ![appResult[@"activePresetVerified"] boolValue] && ![appResult[@"persistenceVerified"] boolValue],@"profile ACK does not confirm active preset or persistence");
        [peripheral.writes setLength:0];NSMutableString *workName=[@"Fpv" mutableCopy];[gimbal sendWorkModeRequest:@{@"sourceMode":workName} timeoutMs:1000 completion:appDone];[workName setString:@"Flower"];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
        Require(gimbal.busy && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:(uint8_t[]){62,1,2} length:3]],@"work source-name snapshot uses62 without complete FPV transaction");
        appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,15,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(appCallbacks==45 && [appResult[@"requestedSourceMode"] isEqualToString:@"Fpv"] && ![appResult[@"physicalCompletionVerified"] boolValue],@"work ACK is not a physical follow mode guarantee");
        for(unsigned i=0;i<2;i++) {
            [peripheral.writes setLength:0];if(i==0)[gimbal sendUserProfileRequest:@{@"sourceProfileValue":@2} timeoutMs:1000 completion:appDone];else [gimbal sendWorkModeRequest:@{@"sourceMode":@"Center"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppResponse(appSequence,15,[NSData dataWithBytes:(uint8_t[]){7} length:1],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger writes=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==15)writes++;
            Require(appCallbacks==46+i && writes==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_DEVICE_ERROR"],@"profile/work NACK never retries or writes another domain");
        }
        for(unsigned i=0;i<2;i++) {
            [peripheral.writes setLength:0];if(i==0)[gimbal sendUserProfileRequest:@{@"sourceProfileValue":@2} timeoutMs:1000 completion:appDone];else [gimbal sendWorkModeRequest:@{@"sourceMode":@"Center"} timeoutMs:1000 completion:appDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger writes=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==15)writes++;
            Require(appCallbacks==48+i && writes==1 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"profile/work cancellation never replays or rolls back");
        }
        __block NSUInteger programCallbacks=0;__block NSDictionary *programReply=nil;__block NSError *programError=nil;
        RSAppCompletion programDone=^(NSDictionary *reply,NSError *error){programCallbacks++;programReply=reply;programError=error;};
        [peripheral.writes setLength:0];[gimbal sendProgramStatusRequest:@{@"program":@"track",@"requestType":@0} timeoutMs:1000 completion:programDone];PumpCallbacks();
        Require(programCallbacks==1 && peripheral.writes.length==0 && [programError.userInfo[@"code"] isEqualToString:@"RS4MINI_INVALID_ARGUMENT"],@"single request rejects subscription options before neutral preamble");
        for(NSString *programName in @[@"track",@"timelapse",@"panorama"]) {
            [peripheral.writes setLength:0];NSMutableString *mutableProgram=[programName mutableCopy];NSUInteger beforeCallbacks=programCallbacks;
            [gimbal sendProgramStatusRequest:@{@"program":mutableProgram} timeoutMs:1000 completion:programDone];[mutableProgram setString:@"invalid"];ThreeTicks(gimbal);[decoder reset];frames=[decoder push:peripheral.writes];
            NSNumber *tag=@{@"track":@98,@"timelapse":@55,@"panorama":@99}[programName];const uint8_t body[]={0,2,1,tag.unsignedCharValue};
            Require(gimbal.busy && [frames.lastObject[@"commandId"] intValue]==107 && [frames.lastObject[@"payload"] isEqualToData:[NSData dataWithBytes:body length:4]],@"named single request snapshots name and sends fixed type2 after neutral preamble");
            appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppNotification(appSequence,107,[NSData dataWithBytes:(uint8_t[]){0,98,4,1,2,3,4} length:7]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();NSDictionary *beforeProgram=gimbal.appProgramStatus;
            Require(gimbal.busy && programCallbacks==beforeCallbacks && beforeProgram,@"notification with same sequence does not complete single request");
            notify.value=AppResponse(appSequence,107,[NSData dataWithBytes:(uint8_t[]){0,254} length:2],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
            Require(programCallbacks==beforeCallbacks+1 && !gimbal.busy && !programError && [programReply[@"requestedProgram"] isEqualToString:programName] && [programReply[@"bodyHex"] isEqualToString:@"fe"] && ![programReply[@"freshStatusVerified"] boolValue] && ![programReply[@"programCorrelationVerified"] boolValue] && [gimbal.appProgramStatus isEqual:beforeProgram],@"ACK body remains opaque and neither refreshes cache nor proves completion");
        }
        for(NSUInteger kind=0;kind<3;kind++) {
            [peripheral.writes setLength:0];NSUInteger beforeCallbacks=programCallbacks;
            [gimbal sendProgramStatusRequest:@{@"program":@"track"} timeoutMs:1000 completion:programDone];ThreeTicks(gimbal);appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];
            NSMutableData *bad=[AppResponse(appSequence,107,kind==0?[NSData dataWithBytes:(uint8_t[]){7} length:1]:kind==1?[NSData data]:ok,4) mutableCopy];
            if(kind==2){uint8_t *b=bad.mutableBytes;b[8]=129;uint16_t crc=0x3692;for(NSUInteger i=0;i<bad.length-2;i++){crc^=b[i];for(int bit=0;bit<8;bit++)crc=crc&1?(crc>>1)^0x8408:crc>>1;}b[bad.length-2]=crc&255;b[bad.length-1]=crc>>8;}
            notify.value=bad;[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger count=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==107)count++;
            Require(programCallbacks==beforeCallbacks+1 && count==1 && [programError.userInfo[@"code"] isEqualToString:kind==0?@"RS4MINI_DEVICE_ERROR":@"RS4MINI_PROTOCOL_ERROR"],@"bad ACK never uses passive cache or retries request");
        }
        [peripheral.writes setLength:0];NSUInteger beforeTimeout=programCallbacks;[gimbal sendProgramStatusRequest:@{@"program":@"timelapse"} timeoutMs:1000 completion:programDone];ThreeTicks(gimbal);appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];[gimbal setValue:@(NSProcessInfo.processInfo.systemUptime-1) forKey:@"deviceQueryDeadline"];[gimbal tick];ThreeTicks(gimbal);PumpCallbacks();
        Require(programCallbacks==beforeTimeout+1 && !gimbal.busy && [programError.userInfo[@"code"] isEqualToString:@"RS4MINI_RESPONSE_TIMEOUT"],@"single request timeout releases native ownership");
        notify.value=AppResponse(appSequence,107,ok,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger timeoutWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==107)timeoutWrites++;
        Require(programCallbacks==beforeTimeout+1 && timeoutWrites==1,@"late single ACK ignored without replay or new completion");
        [peripheral.writes setLength:0];NSUInteger beforeCancel=programCallbacks;[gimbal sendProgramStatusRequest:@{@"program":@"track"} timeoutMs:1000 completion:programDone];ThreeTicks(gimbal);[gimbal stop];ThreeTicks(gimbal);PumpCallbacks();[decoder reset];frames=[decoder push:peripheral.writes];NSUInteger programWrites=0;for(NSDictionary *f in frames)if([f[@"commandId"] intValue]==107)programWrites++;
        Require(programCallbacks==beforeCancel+1 && programWrites==1 && [programError.userInfo[@"code"] isEqualToString:@"RS4MINI_OPERATION_CANCELLED"],@"native stop cancels pending single request without program stop or replay");
        [peripheral.writes setLength:0];__block NSUInteger peripheralEvents=0;gimbal.appStatusHandler=^(NSDictionary *status){if([status[@"kind"] isEqualToString:@"peripheral"]){peripheralEvents++;@throw [NSException exceptionWithName:@"peripheralObserver" reason:nil userInfo:nil];}};
        notify.value=AppNotification(5,102,[NSData dataWithBytes:(uint8_t[]){1,34,2,10,0} length:5]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(peripheralEvents==1 && [gimbal.appPeripheralStatus[@"records"][0][@"sourceViews"][0][@"value"] intValue]==1 && peripheral.writes.length==0,@"peripheral candidate isolates observer error without ACK or subscription writes");
        NSDictionary *beforePeripheral=gimbal.appPeripheralStatus;notify.value=AppNotification(5,102,[NSData dataWithBytes:(uint8_t[]){1,34,2,0} length:4]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();Require([gimbal.appPeripheralStatus isEqual:beforePeripheral] && peripheralEvents==1,@"invalid peripheral frame retains whole prior snapshot");
        __block NSUInteger peripheralQueryCallbacks=0;[gimbal getFollowSensitivityWithTimeoutMs:1000 completion:^(NSDictionary *r,NSError *e){peripheralQueryCallbacks++;}];ThreeTicks(gimbal);NSUInteger peripheralWrites=peripheral.writes.length;appSequence=[[gimbal valueForKey:@"deviceQuerySequence"] unsignedShortValue];notify.value=AppNotification(appSequence,102,[NSData dataWithBytes:(uint8_t[]){1,34,2,10,0} length:5]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(gimbal.busy && peripheralQueryCallbacks==0 && peripheral.writes.length==peripheralWrites,@"peripheral notice cannot complete pending query or release host ownership");
        notify.value=AppResponse(appSequence,16,[NSData dataWithBytes:(uint8_t[]){0,150,1,0} length:4],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();Require(!gimbal.busy && peripheralQueryCallbacks==1,@"only correlated parameter ACK completes unrelated transaction");
        Require([gimbal useAppProfile:@"ronin-2.2.2"] && !gimbal.appPeripheralStatus,@"explicit profile reselection clears peripheral candidate");
        [peripheral.writes setLength:0];
        notify.value=AppNotification(5,107,[NSData dataWithBytes:(uint8_t[]){0,98,4,1,2,3,4} length:7]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require(gimbal.appProgramStatus && [gimbal useAppProfile:@"ronin-2.2.2"] && !gimbal.appProgramStatus && peripheral.writes.length==0,@"explicit source reselection clears program cache without sending");
        [gimbal getFollowSensitivityWithTimeoutMs:1000 completion:appDone]; ThreeTicks(gimbal);
        NSUInteger sourceWrites=peripheral.writes.length;__block NSUInteger sourceEvents=0;
        gimbal.appStatusHandler=^(NSDictionary *status){if([@[@"abnormal",@"battery"] containsObject:status[@"kind"]]){sourceEvents++;@throw [NSException exceptionWithName:@"sourceObserver" reason:nil userInfo:nil];}};
        notify.value=AppNotification(5,0x27,[NSData dataWithBytes:(uint8_t[]){4,255,62,103,1,170} length:6]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        notify.value=AppNotification(5,0x33,[NSData dataWithBytes:(uint8_t[]){255,99} length:2]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(gimbal.busy && appCallbacks==49 && sourceEvents==2 && ![gimbal.appAbnormalStatus[@"sourceValues"][@"isGimbalLocked"] boolValue] && [gimbal.appBatteryStatus[@"rawCapacityValue"] intValue]==255 && peripheral.writes.length==sourceWrites,@"passive source status candidates never complete query or send despite observer errors");
        NSDictionary *abnormalBefore=gimbal.appAbnormalStatus,*batteryBefore=gimbal.appBatteryStatus;
        notify.value=AppNotification(5,0x27,[NSMutableData dataWithLength:4]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        notify.value=AppResponse(5,0x33,[NSMutableData dataWithLength:1],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require([gimbal.appAbnormalStatus isEqual:abnormalBefore] && [gimbal.appBatteryStatus isEqual:batteryBefore] && sourceEvents==2,@"invalid source notifications preserve independent prior snapshots");
        __block NSUInteger programEvents=0;
        gimbal.appStatusHandler=^(NSDictionary *status){if([status[@"kind"] isEqual:@"program"]){programEvents++;@throw [NSException exceptionWithName:@"programObserver" reason:nil userInfo:nil];}};
        NSData *programBody=[NSData dataWithBytes:(uint8_t[]){1,98,4,255,1,2,3} length:7];
        notify.value=AppNotification(5,107,programBody);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(gimbal.busy && appCallbacks==49 && programEvents==1 && [gimbal.appProgramStatus[@"records"][0][@"sourceValues"][@"status"] intValue]==255 && peripheral.writes.length==sourceWrites,@"program candidate preserves ownership and pending query without writes despite observer error");
        NSDictionary *programBefore=gimbal.appProgramStatus;
        notify.value=AppResponse(5,107,programBody,4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        notify.value=AppNotification(5,107,[NSData dataWithBytes:(uint8_t[]){0,98,3,1,2,3} length:6]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require([gimbal.appProgramStatus isEqual:programBefore] && programEvents==1,@"invalid and ACK program messages retain last complete snapshot");
        notify.value=AppNotification(5,100,[NSData dataWithBytes:(uint8_t[]){255,255,255,0,128} length:5]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require([gimbal.appProgramStatus[@"records"] count]==0 && [gimbal.appProgramStatus[@"sourceValues"][@"currentPictures"] intValue]==65535 && peripheral.writes.length==sourceWrites,@"new standalone program frame never merges old record fields");
        NSUInteger stickWrites=peripheral.writes.length;__block NSUInteger stickEvents=0;
        gimbal.appStatusHandler=^(NSDictionary *status){if([status[@"kind"] isEqualToString:@"handheldStick"]){stickEvents++;@throw [NSException exceptionWithName:@"observer" reason:nil userInfo:nil];}};
        NSData *stickPayload=[NSData dataWithBytes:(uint8_t[]){0,128,255,127,3,128,170} length:7];
        notify.value=AppNotification(5,0x57,stickPayload);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(gimbal.busy && appCallbacks==49 && stickEvents==1 && [gimbal.appHandheldStickStatus[@"sourceStickX"] intValue]==-32768 && peripheral.writes.length==stickWrites,@"passive stick status preserves pending query ownership and never transmits despite observer exception");
        NSDictionary *stickBefore=gimbal.appHandheldStickStatus;
        notify.value=AppResponse(5,0x57,[NSMutableData dataWithLength:6],4);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        notify.value=AppNotification(5,0x57,[NSMutableData dataWithLength:5]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];
        Require([gimbal.appHandheldStickStatus isEqual:stickBefore] && stickEvents==1,@"ACK and short stick source reports leave prior cache intact");
        notify.value=AppNotification(5,0x24,fixedBody);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];PumpCallbacks();
        Require(gimbal.busy && gimbal.appUserParameterStatus && appCallbacks==49,@"passive report does not release or complete an outstanding parameter query");
        notify.value=AppNotification(5,102,[NSData dataWithBytes:(uint8_t[]){1,34,2,10,0} length:5]);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require(gimbal.appPeripheralStatus && gimbal.busy,@"live peripheral cache exists immediately before disconnect");
        notify.value=AppNotification(5,105,externalBody);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require(gimbal.appExternalDeviceStatus!=nil,@"external cache live before disconnect");
        notify.value=AppNotification(5,48,sensorBody);[gimbal peripheral:(id)peripheral didUpdateValueForCharacteristic:(id)notify error:nil];Require(gimbal.appSensorCalibrationStatus!=nil,@"sensor cache live before disconnect");
        [gimbal centralManager:(id)central didDisconnectPeripheral:(id)peripheral error:nil]; PumpCallbacks();
        Require(!gimbal.appPeripheralStatus && !gimbal.appExternalDeviceStatus && !gimbal.appSensorCalibrationStatus,@"disconnect clears passive source candidates");
        Require(appCallbacks == 50 && [appError.userInfo[@"code"] isEqualToString:@"RS4MINI_DISCONNECTED"], @"native disconnect rejects pending App query");
        Require(!gimbal.appUserParameterStatus && !gimbal.appHandheldStickStatus && !gimbal.appAbnormalStatus && !gimbal.appBatteryStatus && !gimbal.appProgramStatus,@"native disconnect clears cached fixed and stick reports");
        [gimbal disconnect]; ThreeTicks(gimbal);
        FakeCentral *centerCentral=[FakeCentral new];centerCentral.state=CBManagerStatePoweredOn;
        RSGimbal *centerGimbal=[[RSGimbal alloc] initWithStatus:^(NSString *text,BOOL ready){} central:(id)centerCentral];FakePeripheral *centerPeripheral=Connect(centerGimbal,centerCentral);FakeCharacteristic *centerRx=[centerGimbal valueForKey:@"rx"];
        [centerGimbal useAppProfile:@"ronin-2.2.2"];__block NSDictionary *centerResult=nil;__block NSError *centerError=nil;__block NSUInteger centerCallbacks=0;
        RSAppCompletion centerDone=^(NSDictionary *r,NSError *e){centerResult=r;centerError=e;centerCallbacks++;};
        [centerGimbal getCenterActivationInfo:@{} timeoutMs:3000 completion:centerDone];PumpCallbacks();Require(centerCallbacks==1 && centerError && !centerPeripheral.writes.length,@"CENTER invalid version sends no stop/query");
        [centerGimbal getCenterActivationInfo:@{@"sourceVersion":@"Ver1_1"} timeoutMs:3000 completion:centerDone];ThreeTicks(centerGimbal);
        NSArray *centerFrames=[[RSFrameDecoder new] push:centerPeripheral.writes];NSDictionary *centerRequest=centerFrames.lastObject;
        Require([centerRequest[@"receiver"] intValue]==229 && [centerRequest[@"commandSet"] intValue]==0 && [centerRequest[@"commandId"] intValue]==50 && ((const uint8_t *)[centerRequest[@"payload"] bytes])[0]==17,@"CENTER native query uses E5 COMMON GET11");
        Require(![centerGimbal useAppProfile:@"ronin-2.2.2"],@"CENTER source switch rejected during query");
        uint16_t centerSequence=[centerRequest[@"sequence"] unsignedShortValue];NSData *centerBody=[NSData dataWithBytes:(uint8_t[]){0,131,234,7,10,19,12,34,56,3,65,45,255,222,173} length:15];
        for(NSUInteger variant=0;variant<4;variant++){centerRx.value=CenterResponse(centerSequence+(variant==3),centerBody,variant==0?4:229,variant==2?0:128,variant==1?4:0);[centerGimbal peripheral:(id)centerPeripheral didUpdateValueForCharacteristic:(id)centerRx error:nil];PumpCallbacks();Require(centerGimbal.busy && centerCallbacks==1,@"CENTER wrong sender/set/ACK/sequence ignored");}
        centerRx.value=CenterResponse(centerSequence,centerBody,229,128,0);[centerGimbal peripheral:(id)centerPeripheral didUpdateValueForCharacteristic:(id)centerRx error:nil];PumpCallbacks();Require(centerCallbacks==2 && !centerError && [centerResult[@"sourceSerialNumber"] isEqual:@"A45-1"] && !centerGimbal.busy,@"CENTER native fresh ACK complete decoding");
        [centerPeripheral.writes setLength:0];[centerGimbal getCenterActivationInfo:@{@"sourceVersion":@"Ver1_1"} timeoutMs:3000 completion:centerDone];ThreeTicks(centerGimbal);centerRequest=[[RSFrameDecoder new] push:centerPeripheral.writes].lastObject;
        centerRx.value=CenterResponse([centerRequest[@"sequence"] unsignedShortValue],[NSData dataWithBytes:(uint8_t[]){0} length:1],229,128,0);[centerGimbal peripheral:(id)centerPeripheral didUpdateValueForCharacteristic:(id)centerRx error:nil];ThreeTicks(centerGimbal);PumpCallbacks();Require(centerCallbacks==3 && !centerResult && [centerError.userInfo[@"code"] isEqual:@"RS4MINI_PROTOCOL_ERROR"],@"CENTER short ACK cannot return old serial result");
        [centerPeripheral.writes setLength:0];[centerGimbal getWorkModeWithTimeoutMs:3000 completion:centerDone];ThreeTicks(centerGimbal);NSDictionary *oldRoute=[[RSFrameDecoder new] push:centerPeripheral.writes].lastObject;Require([oldRoute[@"receiver"] intValue]==4 && [oldRoute[@"commandSet"] intValue]==4 && [oldRoute[@"commandId"] intValue]==16,@"CENTER route cleanup preserves normal App routing");
        centerRx.value=AppResponse([oldRoute[@"sequence"] unsignedShortValue],16,[NSData dataWithBytes:(uint8_t[]){0,62,1,2} length:4],4);[centerGimbal peripheral:(id)centerPeripheral didUpdateValueForCharacteristic:(id)centerRx error:nil];PumpCallbacks();Require(centerCallbacks==4 && !centerError,@"normal App ACK still resolves after CENTER query");
        [centerGimbal getCenterActivationInfo:@{@"sourceVersion":@"Ver1_1"} timeoutMs:3000 completion:centerDone];ThreeTicks(centerGimbal);[centerGimbal setValue:@0 forKey:@"deviceQueryDeadline"];[centerGimbal tick];ThreeTicks(centerGimbal);PumpCallbacks();Require(centerCallbacks==5 && [centerError.userInfo[@"code"] isEqual:@"RS4MINI_RESPONSE_TIMEOUT"],@"CENTER timeout clears ownership without retry");
        [centerGimbal getCenterActivationInfo:@{@"sourceVersion":@"Ver1_1"} timeoutMs:3000 completion:centerDone];ThreeTicks(centerGimbal);[centerGimbal centralManager:(id)centerCentral didDisconnectPeripheral:(id)centerPeripheral error:nil];PumpCallbacks();Require(centerCallbacks==6 && [centerError.userInfo[@"code"] isEqual:@"RS4MINI_DISCONNECTED"],@"CENTER disconnect rejects only current session");[centerGimbal disconnect];ThreeTicks(centerGimbal);
        printf("Native fake-device lifecycle checks: %lu passed (no Bluetooth manager created)\n", (unsigned long)assertions);
    }
    return 0;
}
