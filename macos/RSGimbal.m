#import "RSGimbal.h"
#import "RSControlCore.h"
#include <math.h>

static NSTimeInterval Clock(void) { return NSProcessInfo.processInfo.systemUptime; }
static BOOL Matches(NSString *name) {
    NSString *source = (name ?: @"").uppercaseString;
    NSString *normalized = [[source componentsSeparatedByCharactersInSet:NSCharacterSet.whitespaceCharacterSet] componentsJoinedByString:@""];
    return [normalized containsString:@"DJIRS4MINI"];
}
@interface RSGimbal ()
@property(nonatomic, strong) CBCentralManager *central;
@property(nonatomic, strong) CBPeripheral *peripheral;
@property(nonatomic, strong) CBCharacteristic *rx;
@property(nonatomic, strong) CBCharacteristic *tx;
@property(nonatomic, strong) NSTimer *connectionTimer;
@property(nonatomic, strong) NSTimer *tickTimer;
@property(nonatomic, strong) RSFrameQueue *outgoing;
@property(nonatomic, strong) RSFrameDecoder *decoder;
@property(nonatomic, strong) RSPositionLoop *position;
@property(nonatomic, strong) RSTrajectoryLoop *trajectory;
@property(nonatomic, strong) NSTimer *reconnectTimer;
@property(nonatomic) NSUInteger reconnectAttempt;
@property(nonatomic) BOOL retrying;
@property(nonatomic, strong) NSUUID *lastIdentifier;
@property(nonatomic, strong) NSDictionary *latestJoints;
@property(nonatomic) NSTimeInterval latestJointAt;
@property(nonatomic, strong) NSDictionary *home;
@property(nonatomic, strong) NSUUID *homeIdentifier;
@property(nonatomic, strong) NSArray *waypoints;
@property(nonatomic) NSUInteger waypointIndex;
@property(nonatomic) NSTimeInterval waypointDeadline;
@property(nonatomic, strong) NSDictionary *latestSample;
@property(nonatomic, copy) NSString *researchProfile;
@property(nonatomic, strong) NSMutableDictionary *researchStatus;
@property(nonatomic, strong) NSDictionary *experimentalJob;
@property(nonatomic) NSTimeInterval experimentalDeadline;
@property(nonatomic) uint16_t experimentalSequence;
@property(nonatomic) BOOL experimentalSent;
@property(nonatomic) BOOL nativeRateActive;
@property(nonatomic, copy) StatusHandler statusHandler;
@property(nonatomic, copy) void (^afterStop)(void);
@property(nonatomic, copy) NSString *stopMessage;
@property(nonatomic) BOOL ready;
@property(nonatomic) BOOL connecting;
@property(nonatomic) BOOL stopping;
@property(nonatomic) BOOL disconnecting;
@property(nonatomic) NSInteger pendingStops;
@property(nonatomic) double pan;
@property(nonatomic) double tilt;
@property(nonatomic) double roll;
@property(nonatomic) uint16_t sequence;
@property(nonatomic) NSTimeInterval lastWriteProgress;
@end

@implementation RSGimbal
- (BOOL)busy { return self.stopping || self.disconnecting || self.position.active || self.trajectory.active || self.waypoints != nil || self.experimentalJob != nil; }
- (NSDictionary *)experimentalStatus {
    if (!self.researchStatus) return @{};
    NSData *json = [NSJSONSerialization dataWithJSONObject:self.researchStatus options:0 error:nil];
    return [NSJSONSerialization JSONObjectWithData:json options:0 error:nil];
}
- (instancetype)initWithStatus:(StatusHandler)handler {
    return [self initWithStatus:handler central:nil];
}
- (instancetype)initWithStatus:(StatusHandler)handler central:(CBCentralManager *)central {
    if ((self = [super init])) {
        _statusHandler = [handler copy]; _sequence = 0x0100;
        _outgoing = [RSFrameQueue new]; _decoder = [RSFrameDecoder new]; _position = [RSPositionLoop new];
        _trajectory = [RSTrajectoryLoop new];
        _central = central ?: [[CBCentralManager alloc] initWithDelegate:self queue:dispatch_get_main_queue()];
    }
    return self;
}
- (void)status:(NSString *)text { if (self.statusHandler) self.statusHandler(text, self.ready); }
- (void)resetLink:(NSString *)message {
    BOOL recover = self.autoReconnectEnabled && (self.ready || self.retrying) && !self.disconnecting;
    [self.central stopScan]; [self.connectionTimer invalidate]; self.connectionTimer = nil;
    [self.tickTimer invalidate]; self.tickTimer = nil; [self.position cancel];
    [self.trajectory cancel]; self.waypoints = nil; self.waypointDeadline = 0; self.latestJoints = nil;
    self.experimentalJob = nil; self.nativeRateActive = NO; self.researchStatus = nil; self.latestSample = nil;
    CBPeripheral *old = self.peripheral; old.delegate = nil;
    self.ready = self.connecting = self.stopping = self.disconnecting = NO;
    self.pan = self.tilt = self.roll = 0; self.pendingStops = 0; self.afterStop = nil;
    self.rx = self.tx = nil; self.peripheral = nil; [self.outgoing reset]; [self.decoder reset];
    if (old) [self.central cancelPeripheralConnection:old];
    if (self.telemetryHandler) self.telemetryHandler(@{});
    [self status:message];
    if (recover) [self scheduleReconnect];
}
- (void)setAutoReconnectEnabled:(BOOL)enabled {
    _autoReconnectEnabled = enabled;
    if (!enabled) {
        [self.reconnectTimer invalidate]; self.reconnectTimer = nil;
        BOOL cancel = self.retrying && self.connecting; self.retrying = NO;
        if (cancel) [self resetLink:@"自动重连已取消"];
    } else if (!self.retrying) self.reconnectAttempt = 0;
}
- (void)scheduleReconnect {
    if (!self.autoReconnectEnabled || self.disconnecting || self.reconnectTimer) return;
    if (self.reconnectAttempt >= 5) { self.retrying = NO; [self status:@"自动重连已尝试 5 次，请检查设备并手动连接"]; return; }
    self.retrying = YES; self.reconnectAttempt++;
    double wait = fmin(10, .5 * pow(2, self.reconnectAttempt - 1));
    [self status:[NSString stringWithFormat:@"%.1f 秒后自动重连（%lu/5），不会恢复运动", wait, (unsigned long)self.reconnectAttempt]];
    __weak typeof(self) weak = self;
    self.reconnectTimer = [NSTimer timerWithTimeInterval:wait repeats:NO block:^(NSTimer *timer) {
        weak.reconnectTimer = nil;
        if (!weak.autoReconnectEnabled) return;
        if (weak.central.state == CBManagerStatePoweredOn) [weak connect]; else [weak scheduleReconnect];
    }];
    [[NSRunLoop mainRunLoop] addTimer:self.reconnectTimer forMode:NSRunLoopCommonModes];
}
- (void)connect {
    if (self.ready || self.connecting || self.disconnecting) return;
    if (self.central.state != CBManagerStatePoweredOn) { [self status:@"请确认 Mac 蓝牙已开启且已授权"]; return; }
    [self.reconnectTimer invalidate]; self.reconnectTimer = nil;
    self.connecting = YES; [self status:@"正在寻找并连接 RS 4 Mini…"];
    __weak typeof(self) weak = self;
    self.connectionTimer = [NSTimer timerWithTimeInterval:30 repeats:NO block:^(NSTimer *timer) { [weak resetLink:@"连接超时，请重新连接"]; }];
    [[NSRunLoop mainRunLoop] addTimer:self.connectionTimer forMode:NSRunLoopCommonModes];
    for (NSString *uuid in @[@"FFF0", @"1812"]) {
        for (CBPeripheral *candidate in [self.central retrieveConnectedPeripheralsWithServices:@[[CBUUID UUIDWithString:uuid]]]) {
            if (!Matches(candidate.name)) continue;
            if (self.retrying && self.lastIdentifier && ![candidate.identifier isEqual:self.lastIdentifier]) continue;
            self.peripheral = candidate; candidate.delegate = self;
            [self.central connectPeripheral:candidate options:nil]; return;
        }
    }
    [self.central scanForPeripheralsWithServices:nil options:@{CBCentralManagerScanOptionAllowDuplicatesKey: @NO}];
}
- (void)centralManagerDidUpdateState:(CBCentralManager *)central {
    if (central.state != CBManagerStatePoweredOn && (self.ready || self.connecting)) { [self resetLink:@"蓝牙不可用，连接已清理"]; return; }
    if (central.state == CBManagerStatePoweredOn) [self status:@"蓝牙就绪，点击连接"];
    else if (central.state == CBManagerStateUnauthorized) [self status:@"请在系统设置中允许蓝牙权限"];
    else if (central.state == CBManagerStatePoweredOff) [self status:@"Mac 蓝牙已关闭"];
    else [self status:@"正在初始化蓝牙…"];
}
- (void)centralManager:(CBCentralManager *)central didDiscoverPeripheral:(CBPeripheral *)peripheral advertisementData:(NSDictionary<NSString *,id> *)advertisementData RSSI:(NSNumber *)RSSI {
    if (!self.connecting || self.peripheral || !Matches(advertisementData[CBAdvertisementDataLocalNameKey] ?: peripheral.name)) return;
    if (self.retrying && self.lastIdentifier && ![peripheral.identifier isEqual:self.lastIdentifier]) return;
    self.peripheral = peripheral; peripheral.delegate = self; [central stopScan]; [central connectPeripheral:peripheral options:nil];
}
- (void)centralManager:(CBCentralManager *)central didConnectPeripheral:(CBPeripheral *)peripheral {
    if (!self.connecting || self.peripheral != peripheral) { [central cancelPeripheralConnection:peripheral]; return; }
    [peripheral discoverServices:@[[CBUUID UUIDWithString:@"FFF0"]]];
}
- (void)centralManager:(CBCentralManager *)central didFailToConnectPeripheral:(CBPeripheral *)peripheral error:(NSError *)error {
    if (peripheral == self.peripheral) [self resetLink:[NSString stringWithFormat:@"连接失败：%@", error.localizedDescription ?: @"未知错误"]];
}
- (void)centralManager:(CBCentralManager *)central didDisconnectPeripheral:(CBPeripheral *)peripheral error:(NSError *)error {
    if (peripheral == self.peripheral) [self resetLink:error ? @"连接意外中断，已清理运动状态" : @"已断开"];
}
- (void)centralManager:(CBCentralManager *)central didDisconnectPeripheral:(CBPeripheral *)peripheral timestamp:(CFAbsoluteTime)timestamp isReconnecting:(BOOL)isReconnecting error:(NSError *)error API_AVAILABLE(macos(13.0)) {
    [self centralManager:central didDisconnectPeripheral:peripheral error:error];
}
- (void)peripheral:(CBPeripheral *)peripheral didDiscoverServices:(NSError *)error {
    if (peripheral != self.peripheral || !self.connecting) return;
    if (error || !peripheral.services.count) { [self resetLink:@"未找到 FFF0 控制服务"]; return; }
    for (CBService *service in peripheral.services) [peripheral discoverCharacteristics:@[[CBUUID UUIDWithString:@"FFF4"], [CBUUID UUIDWithString:@"FFF5"]] forService:service];
}
- (void)peripheral:(CBPeripheral *)peripheral didDiscoverCharacteristicsForService:(CBService *)service error:(NSError *)error {
    if (peripheral != self.peripheral || !self.connecting) return;
    if (error) { [self resetLink:@"读取控制通道失败"]; return; }
    for (CBCharacteristic *characteristic in service.characteristics) {
        if ([characteristic.UUID isEqual:[CBUUID UUIDWithString:@"FFF4"]]) self.rx = characteristic;
        if ([characteristic.UUID isEqual:[CBUUID UUIDWithString:@"FFF5"]]) self.tx = characteristic;
    }
    if (!self.rx || !self.tx || !(self.tx.properties & CBCharacteristicPropertyWriteWithoutResponse)) { [self resetLink:@"FFF4/FFF5 控制通道不可用"]; return; }
    [peripheral setNotifyValue:YES forCharacteristic:self.rx];
}
- (void)peripheral:(CBPeripheral *)peripheral didUpdateNotificationStateForCharacteristic:(CBCharacteristic *)characteristic error:(NSError *)error {
    if (peripheral != self.peripheral || characteristic != self.rx) return;
    if (error || !characteristic.isNotifying) { [self resetLink:@"通知订阅失败"]; return; }
    [self.connectionTimer invalidate]; self.connectionTimer = nil; self.connecting = NO; self.ready = YES;
    self.retrying = NO; self.reconnectAttempt = 0; self.lastIdentifier = peripheral.identifier;
    [self status:@"已连接，等待姿态与关节反馈"];
}
- (void)peripheral:(CBPeripheral *)peripheral didUpdateValueForCharacteristic:(CBCharacteristic *)characteristic error:(NSError *)error {
    if (peripheral != self.peripheral || characteristic != self.rx || error || !self.ready) return;
    for (NSDictionary *message in [self.decoder push:characteristic.value]) {
        if (self.researchProfile) {
            NSDictionary *extra = RSDecodeResearchStatus(message, self.researchProfile);
            if (extra) {
                if (!self.researchStatus) self.researchStatus = [NSMutableDictionary dictionary];
                self.researchStatus[extra[@"kind"]] = extra;
                if (self.experimentalStatusHandler) self.experimentalStatusHandler(extra);
            }
        }
        if (self.experimentalSent && [self.experimentalJob[@"command"] isEqualToString:@"query"] && [message[@"sender"] intValue] == 4 && [message[@"receiver"] intValue] == 2 &&
            ([message[@"flags"] intValue] & 0x80) && [message[@"sequence"] unsignedShortValue] == self.experimentalSequence) {
            RSFrameDecoder *expectedDecoder = [RSFrameDecoder new];
            NSDictionary *expected = [expectedDecoder push:RSResearchQueryFrame(self.experimentalSequence, self.experimentalJob[@"kind"])].firstObject;
            if ([message[@"commandSet"] isEqual:expected[@"commandSet"]] && [message[@"commandId"] isEqual:expected[@"commandId"]]) {
                self.experimentalJob = nil;
                [self status:[NSString stringWithFormat:@"已收到关联实验查询响应（%lu 字节）", (unsigned long)[message[@"payload"] length]]];
                if (self.experimentalStatusHandler) self.experimentalStatusHandler(@{@"kind": @"query-response", @"message": message, @"deviceVerified": @NO});
            }
        }
        if ([message[@"commandSet"] intValue] != 4 || [message[@"commandId"] intValue] != 5) continue;
        NSDictionary *sample = RSDecodeTelemetry(message[@"payload"]);
        if (!sample) continue;
        self.latestSample = sample;
        if (sample[@"jointAngles"]) {
            self.latestJoints = sample[@"jointAngles"]; self.latestJointAt = Clock();
            [self.position feedback:sample[@"jointAngles"] at:self.latestJointAt];
        }
        if (self.telemetryHandler) self.telemetryHandler(sample);
    }
}
- (void)ensureTimer {
    if (self.tickTimer) return;
    __weak typeof(self) weak = self;
    self.tickTimer = [NSTimer timerWithTimeInterval:1.0 / 15 repeats:YES block:^(NSTimer *timer) { [weak tick]; }];
    [[NSRunLoop mainRunLoop] addTimer:self.tickTimer forMode:NSRunLoopCommonModes];
}
- (void)drain {
    if (!self.ready) return;
    while (self.peripheral.canSendWriteWithoutResponse && !self.outgoing.empty) {
        NSData *chunk = [self.outgoing nextChunk];
        [self.peripheral writeValue:chunk forCharacteristic:self.tx type:CBCharacteristicWriteWithoutResponse];
        self.lastWriteProgress = Clock();
    }
}
- (void)peripheralIsReadyToSendWriteWithoutResponse:(CBPeripheral *)peripheral { if (peripheral == self.peripheral) [self drain]; }
- (void)writeFrame:(NSData *)frame {
    if (!self.ready || !frame) return;
    if (self.outgoing.empty) self.lastWriteProgress = Clock();
    [self.outgoing enqueue:frame]; [self drain]; [self ensureTimer];
}
- (void)beginStop:(void (^)(void))after message:(NSString *)message {
    self.pan = self.tilt = self.roll = 0; [self.position cancel];
    self.afterStop = after; self.stopMessage = message;
    if (!self.ready) { if (after) after(); return; }
    if (!self.stopping) {
        self.stopping = YES; self.pendingStops = 3; [self.outgoing discardPending];
        if (self.nativeRateActive) { self.nativeRateActive = NO; [self writeFrame:RSResearchRateFrame(self.sequence++, @{}, YES)]; }
    }
    [self status:@"正在停止并清理当前运动…"];
    [self ensureTimer];
}
- (void)tick {
    if (!self.ready) return;
    if (!self.outgoing.empty && Clock() - self.lastWriteProgress >= 3) { [self resetLink:@"发送超时，已断开；请检查稳定器"]; return; }
    [self drain];
    if (self.trajectory.active && !self.outgoing.empty && Clock() - self.lastWriteProgress > .5) {
        [self.trajectory cancel]; [self beginStop:nil message:@"轨迹链路延误超过 500 ms，已取消并尝试停止"];
    }
    if (self.stopping) {
        if (self.pendingStops > 0 && self.outgoing.empty) { self.pendingStops--; [self writeFrame:RSVelocityFrame(self.sequence++, 0, 0, 0)]; }
        if (!self.pendingStops && self.outgoing.empty) {
            self.stopping = NO; void (^after)(void) = self.afterStop; self.afterStop = nil;
            if (self.stopMessage) [self status:self.stopMessage];
            if (after) after();
        }
    } else if (self.experimentalJob) {
        NSString *kind = self.experimentalJob[@"command"];
        if ([kind isEqualToString:@"sleep"] && self.outgoing.empty) { self.experimentalJob = nil; [self status:@"实验休眠/唤醒写入已完成，设备效果未验证"]; }
        else if (Clock() >= self.experimentalDeadline) {
            self.experimentalJob = nil;
            if ([kind isEqualToString:@"query"]) [self status:@"实验查询超时，未收到关联响应"];
            else [self beginStop:nil message:@"实验观察/速率时段已结束并尝试停止，不代表物理到位"];
        } else if ([kind isEqualToString:@"rate"] && self.outgoing.empty) {
            NSMutableDictionary *rates = [self.experimentalJob mutableCopy];
            for (NSString *key in @[@"profile", @"command", @"durationMs"]) [rates removeObjectForKey:key];
            [self writeFrame:RSResearchRateFrame(self.sequence++, rates, NO)];
        }
    } else if (self.position.active) {
        NSString *state = [self.position step:Clock()];
        if ([state isEqualToString:@"arrived"]) {
            if (self.waypoints) {
                __weak typeof(self) weak = self;
                [self beginStop:^{ weak.waypointDeadline = Clock() + [weak.waypoints[weak.waypointIndex][@"holdMs"] doubleValue] / 1000; } message:@"路点已到位，停止后停留"];
            } else [self beginStop:nil message:@"关节目标已进入 1° 容差，停止指令已发送"];
        }
        else if ([state isEqualToString:@"timeout"] || [state isEqualToString:@"telemetryTimeout"]) {
            self.waypoints = nil; [self beginStop:nil message:[state isEqualToString:@"timeout"] ? @"定位总超时，已发送停止指令" : @"超过 3 秒无关节反馈，已发送停止指令"];
        }
        else if ([state isEqualToString:@"moving"] && self.outgoing.empty) {
            NSDictionary *v = self.position.velocity;
            [self writeFrame:RSVelocityFrame(self.sequence++, [v[@"pan"] doubleValue], [v[@"tilt"] doubleValue], [v[@"roll"] doubleValue])];
        }
    } else if (self.trajectory.active) {
        if (self.outgoing.empty) {
            NSString *state = [self.trajectory step:Clock()]; NSDictionary *v = self.trajectory.velocity;
            if ([state isEqualToString:@"moving"]) [self writeFrame:RSVelocityFrame(self.sequence++, [v[@"pan"] doubleValue], [v[@"tilt"] doubleValue], [v[@"roll"] doubleValue])];
            else [self beginStop:nil message:[state isEqualToString:@"done"] ? @"速度轨迹结束，已发送停止指令" : @"轨迹调度延误，已取消并停止"];
        }
    } else if (self.waypoints) {
        if (self.waypointDeadline && Clock() >= self.waypointDeadline) {
            self.waypointDeadline = 0; self.waypointIndex++;
            if (self.waypointIndex >= self.waypoints.count) { self.waypoints = nil; [self status:@"所有路点已完成"]; }
            else [self startWaypoint];
        }
    } else if ((self.pan || self.tilt || self.roll) && self.outgoing.empty) [self writeFrame:RSVelocityFrame(self.sequence++, self.pan, self.tilt, self.roll)];
    else if (self.outgoing.empty) { [self.tickTimer invalidate]; self.tickTimer = nil; }
}
- (void)drivePan:(double)pan tilt:(double)tilt roll:(double)roll {
    if (!self.ready || self.busy) { [self status:@"当前操作未结束，请先停止"]; return; }
    if (!isfinite(pan) || !isfinite(tilt) || !isfinite(roll)) return;
    self.pan = fmax(-1, fmin(1, pan)); self.tilt = fmax(-1, fmin(1, tilt)); self.roll = fmax(-1, fmin(1, roll));
    if (!self.outgoing.empty) [self.outgoing discardPending];
    [self writeFrame:RSVelocityFrame(self.sequence++, self.pan, self.tilt, self.roll)];
}
- (void)moveTo:(NSDictionary *)targets {
    if (!self.ready || self.busy) { [self status:@"当前操作未结束，请先停止"]; return; }
    if (![targets isKindOfClass:NSDictionary.class]) { [self status:@"目标格式无效"]; return; }
    RSPositionLoop *validation = [RSPositionLoop new]; NSError *validationError;
    if (![validation begin:targets at:Clock() error:&validationError]) { [self status:validationError.localizedDescription]; return; }
    NSDictionary *copiedTargets = [targets copy];
    __weak typeof(self) weak = self;
    void (^start)(void) = ^{
        NSError *error;
        if (![weak.position begin:copiedTargets at:Clock() error:&error]) { [weak status:error.localizedDescription]; return; }
        [weak status:@"低速定位中，等待新关节反馈…"]; [weak ensureTimer];
    };
    if (self.pan || self.tilt || self.roll || !self.outgoing.empty) [self beginStop:start message:nil]; else start();
}
- (void)stop {
    if (self.disconnecting) return;
    [self.trajectory cancel]; self.waypoints = nil; self.waypointDeadline = 0;
    self.experimentalJob = nil;
    [self beginStop:nil message:@"停止指令已发送"];
}
- (void)recenter {
    if (!self.ready || self.busy) { [self status:@"当前操作未结束，请先停止"]; return; }
    __weak typeof(self) weak = self;
    [self beginStop:^{ [weak writeFrame:RSRecenterFrame(weak.sequence)]; weak.sequence++; [weak status:@"三轴回中指令已发送"]; } message:nil];
}
- (void)disconnect {
    self.autoReconnectEnabled = NO;
    if (self.connecting) { [self resetLink:@"连接已取消"]; return; }
    if (!self.ready || self.disconnecting) return;
    self.disconnecting = YES; __weak typeof(self) weak = self;
    [self.trajectory cancel]; self.waypoints = nil; self.waypointDeadline = 0;
    self.experimentalJob = nil;
    [self beginStop:^{ [weak resetLink:@"已断开"]; } message:nil];
}
- (void)runTrajectory:(NSArray *)keyframes interpolation:(NSString *)interpolation {
    if (!self.ready || self.busy) { [self status:@"当前操作未结束，请先停止"]; return; }
    RSTrajectoryLoop *prepared = [RSTrajectoryLoop new]; NSError *error;
    if (![prepared begin:keyframes interpolation:interpolation at:Clock() error:&error]) { [self status:error.localizedDescription]; return; }
    [prepared cancel];
    __weak typeof(self) weak = self;
    NSArray *points = [[NSArray alloc] initWithArray:keyframes copyItems:YES]; NSString *method = [interpolation copy];
    self.trajectory = prepared;
    [self beginStop:^{
        NSError *startError;
        if (![weak.trajectory begin:points interpolation:method at:Clock() error:&startError]) { [weak status:startError.localizedDescription]; return; }
        [weak status:@"速度轨迹执行中（开环），可随时停止"]; [weak ensureTimer];
    } message:nil];
}
- (void)startWaypoint {
    NSMutableDictionary *targets = [self.waypoints[self.waypointIndex] mutableCopy]; [targets removeObjectForKey:@"holdMs"];
    NSError *error;
    if (![self.position begin:targets at:Clock() error:&error]) { self.waypoints = nil; [self beginStop:nil message:error.localizedDescription]; return; }
    [self status:[NSString stringWithFormat:@"关节路点 %lu/%lu，等待新反馈", (unsigned long)self.waypointIndex + 1, (unsigned long)self.waypoints.count]]; [self ensureTimer];
}
- (void)moveThrough:(NSArray *)waypoints {
    if (!self.ready || self.busy) { [self status:@"当前操作未结束，请先停止"]; return; }
    if (![waypoints isKindOfClass:NSArray.class] || !waypoints.count) { [self status:@"至少需要一个路点"]; return; }
    NSMutableArray *points = [NSMutableArray array];
    for (id point in waypoints) {
        if (![point isKindOfClass:NSDictionary.class]) { [self status:@"路点格式无效"]; return; }
        NSMutableDictionary *target = [point mutableCopy]; id hold = target[@"holdMs"] ?: @0; [target removeObjectForKey:@"holdMs"];
        NSError *error; RSPositionLoop *validation = [RSPositionLoop new];
        if (![hold isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)hold) == CFBooleanGetTypeID() || !isfinite([hold doubleValue]) || [hold doubleValue] < 0 || [hold doubleValue] > 2147483647 || ![validation begin:target at:Clock() error:&error]) { [self status:@"路点角度或停留时间无效"]; return; }
        target[@"holdMs"] = @([hold doubleValue]); [points addObject:[target copy]];
    }
    self.waypoints = [points copy]; self.waypointIndex = 0; self.waypointDeadline = 0;
    __weak typeof(self) weak = self;
    [self beginStop:^{ [weak startWaypoint]; } message:nil];
}
- (void)captureHome {
    if (!self.ready || !self.latestJoints || Clock() - self.latestJointAt > 3) { [self status:@"请等待新的机械关节反馈后保存位置"]; return; }
    self.home = @{@"pan": self.latestJoints[@"yaw"], @"tilt": self.latestJoints[@"pitch"], @"roll": self.latestJoints[@"roll"]};
    self.homeIdentifier = self.peripheral.identifier; [self status:@"已保存本设备当前位置（仅本次应用有效）"];
}
- (void)moveHomeAxes:(NSArray<NSString *> *)axes {
    if (!self.home || ![self.homeIdentifier isEqual:self.peripheral.identifier]) { [self status:@"请先保存当前设备的位置"]; return; }
    if (![axes isKindOfClass:NSArray.class] || !axes.count || [NSSet setWithArray:axes].count != axes.count) { [self status:@"请选择不重复的返回轴"]; return; }
    NSMutableDictionary *targets = [NSMutableDictionary dictionary];
    for (NSString *axis in axes) { if (!self.home[axis]) { [self status:@"返回轴名称无效"]; return; } targets[axis] = self.home[axis]; }
    [self moveTo:targets];
}
- (NSDictionary *)orientationWithOrder:(NSString *)order conjugate:(BOOL)conjugate {
    NSDictionary *raw = self.latestSample[@"orientationQuaternion"];
    if (!self.ready || !raw || !isfinite([raw[@"norm"] doubleValue]) || fabs([raw[@"norm"] doubleValue] - 1) > .1) return nil;
    return RSOrientation(raw[@"components"], order, conjugate);
}
- (NSData *)researchFrame:(NSDictionary *)command sequence:(uint16_t)sequence {
    NSString *kind = [command[@"command"] copy];
    if ([kind isEqualToString:@"query"]) return RSResearchQueryFrame(sequence, command[@"kind"]);
    if ([kind isEqualToString:@"sleep"]) return RSResearchSleepFrame(sequence, command[@"profile"], [command[@"asleep"] boolValue]);
    NSMutableDictionary *axes = [NSMutableDictionary dictionary];
    for (NSString *axis in @[@"pan", @"tilt", @"roll"]) if (command[axis]) axes[axis] = command[axis];
    if ([kind isEqualToString:@"absolute"]) return RSResearchAbsoluteFrame(sequence, axes, [command[@"parameterByte"] unsignedIntegerValue]);
    return RSResearchRateFrame(sequence, axes, NO);
}
- (void)sendExperimentalCommand:(NSDictionary *)command {
    if (!self.ready || self.busy) { [self status:@"当前操作未结束，请先停止"]; return; }
    if (![command isKindOfClass:NSDictionary.class] || ![@[@"rs3", @"rs3mini"] containsObject:command[@"profile"]]) { [self status:@"实验指令必须明确选择 rs3 或 rs3mini 研究配置"]; return; }
    NSString *kind = [command[@"command"] copy];
    NSDictionary *specific = @{@"observe": @[], @"query": @[@"kind", @"timeoutMs"], @"sleep": @[@"asleep"], @"absolute": @[@"pan", @"tilt", @"roll", @"parameterByte", @"observeMs"], @"rate": @[@"pan", @"tilt", @"roll", @"durationMs"]};
    if (![kind isKindOfClass:NSString.class] || !specific[kind]) { [self status:@"不支持此实验指令"]; return; }
    NSMutableArray *allowed = [specific[kind] mutableCopy]; [allowed addObjectsFromArray:@[@"profile", @"command"]];
    for (NSString *key in command) if (![allowed containsObject:key]) { [self status:@"实验指令包含未知字段"]; return; }
    if (([kind isEqualToString:@"absolute"] || [kind isEqualToString:@"rate"]) && ![command[@"profile"] isEqualToString:@"rs3"]) { [self status:@"原生角度/速率仅有 rs3 研究配置"]; return; }
    NSMutableDictionary *job = [command mutableCopy];
    NSString *timeKey = [kind isEqualToString:@"query"] ? @"timeoutMs" : ([kind isEqualToString:@"rate"] ? @"durationMs" : @"observeMs");
    if ([kind isEqualToString:@"query"] || [kind isEqualToString:@"absolute"] || [kind isEqualToString:@"rate"]) {
        id milliseconds = job[timeKey] ?: ([kind isEqualToString:@"rate"] ? nil : @3000);
        if (![milliseconds isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)milliseconds) == CFBooleanGetTypeID() || !isfinite([milliseconds doubleValue]) || [milliseconds doubleValue] < 0 || [milliseconds doubleValue] > 60000 || ([kind isEqualToString:@"query"] && [milliseconds doubleValue] == 0)) { [self status:@"实验时段必须在 0 到 60000 ms 内，查询须大于零"]; return; }
        job[timeKey] = @([milliseconds doubleValue]);
    }
    if ([kind isEqualToString:@"absolute"]) {
        id parameter = job[@"parameterByte"];
        if (![parameter isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)parameter) == CFBooleanGetTypeID() || !isfinite([parameter doubleValue]) || [parameter doubleValue] < 0 || [parameter doubleValue] > 255 || floor([parameter doubleValue]) != [parameter doubleValue]) { [self status:@"必须提供原始末参数字节 parameterByte（0 到 255）"]; return; }
    }
    if ([kind isEqualToString:@"sleep"] && (!job[@"asleep"] || CFGetTypeID((__bridge CFTypeRef)job[@"asleep"]) != CFBooleanGetTypeID())) { [self status:@"asleep 必须为布尔值"]; return; }
    if (![kind isEqualToString:@"observe"] && ![self researchFrame:job sequence:0]) { [self status:@"实验角度、速率或查询种类无效"]; return; }
    self.researchProfile = [command[@"profile"] copy]; self.researchStatus = nil;
    if ([kind isEqualToString:@"observe"]) { [self status:@"已选择研究配置，仅观察被动状态，本机映射未验证"]; return; }
    self.experimentalJob = [job copy]; self.experimentalSent = NO;
    __weak typeof(self) weak = self;
    [self beginStop:^{
        if (!weak.experimentalJob) return;
        weak.experimentalSequence = weak.sequence++;
        weak.experimentalSent = YES;
        weak.experimentalDeadline = Clock() + [weak.experimentalJob[timeKey] doubleValue] / 1000;
        if ([kind isEqualToString:@"sleep"]) weak.experimentalDeadline = Clock() + 3;
        if ([kind isEqualToString:@"rate"]) weak.nativeRateActive = YES;
        if (![kind isEqualToString:@"rate"] || [weak.experimentalJob[@"durationMs"] doubleValue] > 0)
            [weak writeFrame:[weak researchFrame:weak.experimentalJob sequence:weak.experimentalSequence]];
        [weak status:@"实验命令已排队；本机物理执行未验证"]; [weak ensureTimer];
    } message:nil];
}
@end
