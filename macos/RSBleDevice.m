#import "RSBleDevice_Internal.h"
#include <math.h>
static NSTimeInterval Clock(void) { return NSProcessInfo.processInfo.systemUptime; }
static BOOL Matches(NSString *name) {
    NSString *source = (name ?: @"").uppercaseString;
    NSString *normalized = [[source componentsSeparatedByCharactersInSet:NSCharacterSet.whitespaceCharacterSet] componentsJoinedByString:@""];
    return [normalized containsString:@"DJIRS4MINI"];
}
@implementation RSBleDevice
- (BOOL)busy { return self.stopping || self.disconnecting || self.awaitingDeviceQuery || self.appCompletion != nil; }
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
        _outgoing = [RSFrameQueue new]; _decoder = [RSFrameDecoder new];
        _central = central ?: [[CBCentralManager alloc] initWithDelegate:self queue:dispatch_get_main_queue()];
    }
    return self;
}

- (void)status:(NSString *)text { if (self.statusHandler) self.statusHandler(text, self.ready); }

- (void)resetLink:(NSString *)message {
    [self finishApp:nil error:RSAppError(@"RS4MINI_DISCONNECTED", message ?: @"Disconnected", nil)];
    self.awaitingDeviceQuery = NO; self.appCalibrationStatus = nil; self.appUserParameterStatus = nil; self.appHandheldStickStatus = nil; self.appAbnormalStatus = nil; self.appBatteryStatus = nil; self.appProgramStatus = nil; self.appPeripheralStatus = nil; self.appExternalDeviceStatus = nil;
    BOOL recover = self.autoReconnectEnabled && (self.ready || self.retrying) && !self.disconnecting;
    [self.central stopScan]; [self.connectionTimer invalidate]; self.connectionTimer = nil;
    [self.tickTimer invalidate]; self.tickTimer = nil; [self cancelComposedMotion];
    self.latestJoints = nil;
    self.nativeRateActive = NO; self.researchStatus = nil; self.latestSample = nil;
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
        if (self.appCompletion && self.awaitingDeviceQuery && [message[@"sender"] intValue] == 4 && [message[@"receiver"] intValue] == 2 &&
            ([message[@"flags"] intValue] & 0x80) && [message[@"commandSet"] intValue] == 4 && [message[@"commandId"] intValue] == self.appCommandId &&
            [message[@"sequence"] unsignedShortValue] == self.deviceQuerySequence) {
            NSError *appError = nil;
            NSDictionary *result = nil;
            if(self.appCommandId==0x6b && ([message[@"flags"] intValue]&7)) appError=RSAppError(@"RS4MINI_PROTOCOL_ERROR",@"Unencrypted App response required",nil);
            else result = self.appCommandId == 0x6e ? RSDecodeAppCalibrationReply(message, &appError) : RSDecodeAppReply(message, self.appCommandId, self.appParameters, &appError);
            if (appError) [self failApp:appError];
            else if (self.appSettingsPatch && self.appCommandId == 0x10) {
                NSDictionary *before = RSDecodeAppSettings(result, self.appSettingsKind);
                NSData *candidate = RSAppSettingsFrame(0, self.appSettingsKind, self.appSettingsPatch, before[@"rawValue"]);
                if (!candidate) [self failApp:RSAppError(@"RS4MINI_UNSUPPORTED_VALUE", @"Current settings exceed source setter range; no write sent", nil)];
                else if (Clock() >= self.deviceQueryDeadline) [self failApp:RSAppError(@"RS4MINI_RESPONSE_TIMEOUT", @"Settings transaction deadline expired", nil)];
                else {
                    self.appSettingsBefore = before[@"rawValue"];
                    self.appSettingsRequested = @(((const uint8_t *)candidate.bytes)[13]);
                    self.appCommandId = 0x0f; self.appParameters = nil;
                    self.deviceQuerySequence = [self reserveSequence];
                    [self writeFrame:RSAppSettingsFrame(self.deviceQuerySequence, self.appSettingsKind, self.appSettingsPatch, self.appSettingsBefore)];
                }
            } else {
                if (self.appSettingsPatch) {
                    NSMutableDictionary *ack = [result mutableCopy];
                    ack[@"previousRawValue"] = self.appSettingsBefore; ack[@"requestedRawValue"] = self.appSettingsRequested;
                    ack[@"requestedSettings"] = self.appSettingsPatch; result = [ack copy];
                }
                [self finishApp:result error:nil];
            }
        }
        if (self.awaitingDeviceQuery && [self matchesResearchResponse:message sequence:self.deviceQuerySequence kind:@"degreeInfo"]) {
            self.awaitingDeviceQuery = NO;
            [self status:@"已收到 degree-info 原始响应，不代表反馈频率提高"];
        }
        if (self.appProfile) {
            NSDictionary *external=RSDecodeAppExternalDeviceNotification(message);
            if(external){self.appExternalDeviceStatus=external;
                @try{if(self.appStatusHandler)self.appStatusHandler(external);}
                @catch(NSException *exception){NSLog(@"App status observer exception: %@",exception.name);}}
            NSDictionary *peripheralStatus=RSDecodeAppPeripheralNotification(message);
            if(peripheralStatus){self.appPeripheralStatus=peripheralStatus;
                @try{if(self.appStatusHandler)self.appStatusHandler(peripheralStatus);}
                @catch(NSException *exception){NSLog(@"App status observer exception: %@",exception.name);}}
            NSDictionary *program=RSDecodeAppProgramStatusNotification(message);
            if(program) {self.appProgramStatus=program;
                @try {if(self.appStatusHandler)self.appStatusHandler(program);}
                @catch(NSException *exception){NSLog(@"App status observer exception: %@",exception.name);}}
            NSDictionary *source=RSDecodeAppSourceStatusNotification(message);
            if(source) {if([source[@"kind"] isEqualToString:@"abnormal"])self.appAbnormalStatus=source;else self.appBatteryStatus=source;
                @try {if(self.appStatusHandler)self.appStatusHandler(source);}
                @catch(NSException *exception){NSLog(@"App status observer exception: %@",exception.name);}}
            NSDictionary *stick=RSDecodeAppHandheldStickNotification(message);
            if(stick) {self.appHandheldStickStatus=stick;
                @try {if(self.appStatusHandler)self.appStatusHandler(stick);}
                @catch(NSException *exception){NSLog(@"App status observer exception: %@",exception.name);}}
            NSDictionary *parameters=RSDecodeAppUserParameterNotification(message);
            if(parameters) {self.appUserParameterStatus=parameters;
                @try {if(self.appStatusHandler)self.appStatusHandler(parameters);}
                @catch(NSException *exception){NSLog(@"App status observer exception: %@",exception.name);}}
            NSDictionary *appStatus = RSDecodeAppCalibrationNotification(message);
            if (appStatus) {
                self.appCalibrationStatus = appStatus;
                @try { if (self.appStatusHandler) self.appStatusHandler(appStatus); }
                @catch (NSException *exception) { NSLog(@"App status observer exception: %@", exception.name); }
            }
        }
        if (self.messageHandler) self.messageHandler(message);
        [self didReceiveMessage:message];
        if ([message[@"commandSet"] intValue] != 4 || [message[@"commandId"] intValue] != 5) continue;
        NSDictionary *sample = RSDecodeTelemetry(message[@"payload"]);
        if (!sample) continue;
        self.latestSample = sample;
        if (sample[@"jointAngles"]) {
            self.latestJoints = sample[@"jointAngles"]; self.latestJointAt = Clock();

        }
        [self didReceiveTelemetry:sample];
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
    if (self.appCompletion) {
        NSUInteger token = self.appToken; __weak typeof(self) weak = self;
        [self beginStopKeepingApp:^{
            if (weak.appToken == token) [weak finishApp:nil error:RSAppError(@"RS4MINI_OPERATION_CANCELLED", @"App transaction cancelled by stop", nil)];
            if (after) after();
        } message:message];
    } else [self beginStopKeepingApp:after message:message];
}
- (void)beginStopKeepingApp:(void (^)(void))after message:(NSString *)message {
    self.awaitingDeviceQuery = NO;
    self.pan = self.tilt = self.roll = 0; [self cancelPosition];
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
    [self checkComposedBackpressure];
    if (self.stopping) {
        if (self.pendingStops > 0 && self.outgoing.empty) { self.pendingStops--; [self writeFrame:RSVelocityFrame(self.sequence++, 0, 0, 0)]; }
        if (!self.pendingStops && self.outgoing.empty) {
            self.stopping = NO; void (^after)(void) = self.afterStop; self.afterStop = nil;
            if (self.stopMessage) [self status:self.stopMessage];
            if (after) after();
        }
    } else if (self.appNoAckPending) {
        if (self.outgoing.empty) {
            NSMutableDictionary *sent=[@{@"profile":@"ronin-2.2.2",@"sent":@YES,@"acknowledgementRequested":@NO,@"acknowledged":@NO,@"deviceVerified":@NO,@"physicalCompletionVerified":@NO} mutableCopy];
            if(self.appCommandId==0x6a)sent[@"requestedStart"]=self.appRequestedStart;
            [self finishApp:[sent copy] error:nil];
        }
        else if (Clock() >= self.deviceQueryDeadline) [self failApp:RSAppError(@"RS4MINI_IO_TIMEOUT", self.appCommandId==18?@"Parameter subscription write timed out":@"Auto-tune request write timed out", nil)];
    } else if (self.awaitingDeviceQuery) {
        if (Clock() >= self.deviceQueryDeadline) {
            if (self.appCompletion) [self failApp:RSAppError(@"RS4MINI_RESPONSE_TIMEOUT", @"App transaction response timed out", nil)];
            else { self.awaitingDeviceQuery = NO; [self status:@"degree-info 查询超时"]; }
        }
    } else if ([self advanceComposedMotion]) {
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

- (void)stop {
    if (self.disconnecting) return;
    [self cancelComposedMotion];
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
    [self cancelComposedMotion];
    [self beginStop:^{ [weak resetLink:@"已断开"]; } message:nil];
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
- (NSDictionary *)prepareResearchCommand:(NSDictionary *)command {
    if (!self.ready || self.busy) { [self status:@"当前操作未结束，请先停止"]; return nil; }
    if (![command isKindOfClass:NSDictionary.class] || ![@[@"rs3", @"rs3mini"] containsObject:command[@"profile"]]) { [self status:@"实验指令必须明确选择 rs3 或 rs3mini 研究配置"]; return nil; }
    NSString *kind = [command[@"command"] copy];
    NSDictionary *specific = @{@"observe": @[], @"query": @[@"kind", @"timeoutMs"], @"sleep": @[@"asleep"], @"absolute": @[@"pan", @"tilt", @"roll", @"parameterByte", @"observeMs"], @"rate": @[@"pan", @"tilt", @"roll", @"durationMs"]};
    if (![kind isKindOfClass:NSString.class] || !specific[kind]) { [self status:@"不支持此实验指令"]; return nil; }
    NSMutableArray *allowed = [specific[kind] mutableCopy]; [allowed addObjectsFromArray:@[@"profile", @"command"]];
    for (NSString *key in command) if (![allowed containsObject:key]) { [self status:@"实验指令包含未知字段"]; return nil; }
    if (([kind isEqualToString:@"absolute"] || [kind isEqualToString:@"rate"]) && ![command[@"profile"] isEqualToString:@"rs3"]) { [self status:@"原生角度/速率仅有 rs3 研究配置"]; return nil; }
    NSMutableDictionary *job = [command mutableCopy];
    NSString *timeKey = [kind isEqualToString:@"query"] ? @"timeoutMs" : ([kind isEqualToString:@"rate"] ? @"durationMs" : @"observeMs");
    if ([kind isEqualToString:@"query"] || [kind isEqualToString:@"absolute"] || [kind isEqualToString:@"rate"]) {
        id milliseconds = job[timeKey] ?: ([kind isEqualToString:@"rate"] ? nil : @3000);
        if (![milliseconds isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)milliseconds) == CFBooleanGetTypeID() || !isfinite([milliseconds doubleValue]) || [milliseconds doubleValue] < 0 || [milliseconds doubleValue] > 60000 || ([kind isEqualToString:@"query"] && [milliseconds doubleValue] == 0)) { [self status:@"实验时段必须在 0 到 60000 ms 内，查询须大于零"]; return nil; }
        job[timeKey] = @([milliseconds doubleValue]);
    }
    if ([kind isEqualToString:@"absolute"]) {
        id parameter = job[@"parameterByte"];
        if (![parameter isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)parameter) == CFBooleanGetTypeID() || !isfinite([parameter doubleValue]) || [parameter doubleValue] < 0 || [parameter doubleValue] > 255 || floor([parameter doubleValue]) != [parameter doubleValue]) { [self status:@"必须提供原始末参数字节 parameterByte（0 到 255）"]; return nil; }
    }
    if ([kind isEqualToString:@"sleep"] && (!job[@"asleep"] || CFGetTypeID((__bridge CFTypeRef)job[@"asleep"]) != CFBooleanGetTypeID())) { [self status:@"asleep 必须为布尔值"]; return nil; }
    if (![kind isEqualToString:@"observe"] && ![self researchFrame:job sequence:0]) { [self status:@"实验角度、速率或查询种类无效"]; return nil; }
    self.appProfile = nil; self.appCalibrationStatus = nil; self.appUserParameterStatus = nil; self.appHandheldStickStatus = nil; self.appAbnormalStatus = nil; self.appBatteryStatus = nil; self.appProgramStatus = nil; self.appPeripheralStatus = nil; self.appExternalDeviceStatus = nil;
    return [job copy];
}

- (void)requestDegreeInfo {
    if (!self.ready || self.busy) { [self status:@"当前操作未结束，请先停止"]; return; }
    __weak typeof(self) weak = self;
    [self beginStop:^{
        weak.deviceQuerySequence = [weak reserveSequence];
        weak.deviceQueryDeadline = Clock() + 3; weak.awaitingDeviceQuery = YES;
        [weak writeResearchCommand:@{@"command": @"query", @"kind": @"degreeInfo"} sequence:weak.deviceQuerySequence];
        [weak ensureTimer];
    } message:nil];
}
- (BOOL)useAppProfile:(NSString *)profile {
    if (![profile isEqualToString:@"ronin-2.2.2"] || self.busy) { [self status:@"必须在空闲时明确选择 ronin-2.2.2 协议来源"]; return NO; }
    self.researchProfile = nil; self.researchStatus = nil; self.appProfile = [profile copy]; self.appCalibrationStatus = nil; self.appUserParameterStatus = nil; self.appHandheldStickStatus = nil; self.appAbnormalStatus = nil; self.appBatteryStatus = nil; self.appProgramStatus = nil; self.appPeripheralStatus = nil; self.appExternalDeviceStatus = nil; return YES;
}
- (void)finishApp:(NSDictionary *)result error:(NSError *)error {
    RSAppCompletion completion = self.appCompletion;
    if (!completion) return;
    self.appCompletion = nil; self.appParameters = nil; self.awaitingDeviceQuery = NO;
    self.appNoAckPending = NO; self.appRequestedStart = nil;
    self.appSettingsKind = nil; self.appSettingsPatch = nil; self.appSettingsBefore = nil; self.appSettingsRequested = nil;
    dispatch_async(dispatch_get_main_queue(), ^{ completion(result, error); });
}
- (void)failApp:(NSError *)error {
    if (!self.appCompletion) return;
    NSUInteger token = self.appToken; __weak typeof(self) weak = self;
    [self beginStopKeepingApp:^{ if (weak.appToken == token) [weak finishApp:nil error:error]; } message:nil];
}
- (NSData *)appCommandFrame:(uint8_t)command sequence:(uint16_t)sequence context:(NSArray *)context mode:(id)mode {
    switch (command) {
        case 0x10: return RSAppParameterRequestFrame(sequence, context);
        case 0x0f:
            if (context) {
                if (mode && context.count==1 && [@[@0,@62] containsObject:context[0][@"index"]]) return RSAppProfileValueWriteFrame(sequence,context,mode);
                if (mode && context.count>0 && [context[0][@"index"] intValue]>=17 && [context[0][@"index"] intValue]<=19) return RSAppSmoothTrackWriteFrame(sequence,context,mode);
                if (mode && context.count==1 && [context[0][@"index"] intValue]==34) return RSAppAxisModeWriteFrame(sequence,context,mode);
                if (mode) return context.count==2 ? RSAppStandaloneWriteFrame(sequence,context,mode) : RSAppTuningWriteFrame(sequence,context,mode);
                if (context.count!=1 || [context[0][@"size"] intValue]!=1) return nil;
                if ([context[0][@"index"] intValue]==37) return RSAppBalanceStartFrame(sequence);
                if ([context[0][@"index"] intValue]==36) return RSAppSystemCalibrationStartFrame(sequence);
                return nil;
            }
            return RSAppSensitivityFrame(sequence, mode);
        case 18: return context ? nil : RSAppParameterSubscriptionFrame(sequence,mode);
        case 0x6a: return RSAppAutoTuneFrame(sequence, mode);
        case 7: return RSAppFineTuneFrame(sequence,context,mode);
        case 0x13: return context || mode ? nil : RSAppFactoryResetFrame(sequence,@"HG724");
        case 0x35: return RSAppHandleWriteFrame(sequence,context,mode);
        case 0x36: return context || mode ? nil : RSAppHandleQueryFrame(sequence);
        case 0x6e: return RSAppCalibrationQueryFrame(sequence);
        case 0x6b: return context ? nil : [mode isKindOfClass:NSDictionary.class] ? RSAppProgramStatusSubscriptionFrame(sequence,mode) : RSAppProgramStatusRequestFrame(sequence,mode);
        case 0x31: return RSAppMotorWriteFrame(sequence,context,mode);
        case 0x32: return RSAppMotorReadFrame(sequence,context);
        default: return nil;
    }
}
- (void)getAutoCalibrationStatusWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self readAppParameters:@[@{@"index":@36,@"size":@1}] timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if (completion) completion(error?nil:RSDecodeAppSystemCalibrationReply(reply),error);
    }];
}
- (void)sendAutoCalibrationRequestWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self startAppCommand:0x0f parameters:@[@{@"index":@36,@"size":@1}] mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if (result) result[@"requestedValue"]=@1;
        if (completion) completion(result?[result copy]:nil,error);
    }];
}
- (void)getBalanceTestStatusWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self readAppParameters:@[@{@"index":@37,@"size":@1}] timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if (completion) completion(error?nil:RSDecodeAppBalanceReply(reply),error);
    }];
}
- (void)sendBalanceTestRequestWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self startAppCommand:0x0f parameters:@[@{@"index":@37,@"size":@1}] mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy]; if (result) result[@"requestedValue"]=@64;
        if (completion) completion(result?[result copy]:nil,error);
    }];
}
- (void)sendFineTuneRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *request=RSAppFineTuneSpec(spec);
    if(!request){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Fine tune requires pitch/roll and finite adjustmentDegrees -2..2",nil));});return;}
    [self startAppCommand:7 parameters:@[@{@"index":request[@"axisWire"],@"size":@1}] mode:request[@"encodedTenths"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if(result){NSMutableDictionary *metadata=[request mutableCopy];[metadata removeObjectForKey:@"axisWire"];[result addEntriesFromDictionary:metadata];result[@"stabilizationStateVerified"]=@NO;}
        if(completion)completion(result?[result copy]:nil,error);
    }];
}
- (void)getUserProfileWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {[self getProfileValue:@"userProfile" timeoutMs:timeoutMs completion:completion];}
- (void)getWorkModeWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {[self getProfileValue:@"workMode" timeoutMs:timeoutMs completion:completion];}
- (void)getProfileValue:(NSString *)kind timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self readAppParameters:RSAppProfileValueContext(kind) timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if(error){if(completion)completion(nil,error);return;}NSError *decodeError=nil;NSDictionary *result=RSDecodeAppProfileValueReply(reply[@"message"],kind,&decodeError);if(completion)completion(result,decodeError);
    }];
}
- (void)sendUserProfileRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {[self sendProfileValue:@"userProfile" spec:spec timeoutMs:timeoutMs completion:completion];}
- (void)sendWorkModeRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {[self sendProfileValue:@"workMode" spec:spec timeoutMs:timeoutMs completion:completion];}
- (void)sendProfileValue:(NSString *)kind spec:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *request=RSAppProfileValueSpec(kind,spec);
    if(!request){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Named source profile/work-mode value required",nil));});return;}
    [self startAppCommand:0x0f parameters:RSAppProfileValueContext(kind) mode:request[@"requestedRawValue"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if(result){[result addEntriesFromDictionary:request];result[@"activePresetVerified"]=@NO;result[@"persistenceVerified"]=@NO;}
        if(completion)completion(result?[result copy]:nil,error);
    }];
}
- (void)getSmoothTrackAxes:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSArray *context=RSAppSmoothTrackSelection(filters);
    if(!context){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Named smooth track selection required",nil));});return;}
    [self readAppParameters:context timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if(error){if(completion)completion(nil,error);return;}NSError *decodeError=nil;NSDictionary *result=RSDecodeAppSmoothTrackReply(reply[@"message"],context,&decodeError);if(completion)completion(result,decodeError);
    }];
}
- (void)sendSmoothTrackAxesRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *request=RSAppSmoothTrackSpec(spec);
    if(!request){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Named boolean smooth track axes required",nil));});return;}
    [self startAppCommand:0x0f parameters:request[@"context"] mode:request[@"bits"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if(result){result[@"requestedAxes"]=request[@"requestedAxes"];result[@"activePresetVerified"]=@NO;result[@"atomicApplicationVerified"]=@NO;result[@"persistenceVerified"]=@NO;}
        if(completion)completion(result?[result copy]:nil,error);
    }];
}
- (void)getAxisModeWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self readAppParameters:@[@{@"index":@34,@"size":@1}] timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if(error){if(completion)completion(nil,error);return;}NSError *decodeError=nil;NSDictionary *result=RSDecodeAppAxisModeReply(reply[@"message"],&decodeError);if(completion)completion(result,decodeError);
    }];
}
- (void)sendAxisModeRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *request=RSAppAxisModeSpec(spec);
    if(!request){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Named source axis mode required",nil));});return;}
    [self startAppCommand:0x0f parameters:@[@{@"index":@34,@"size":@1}] mode:request[@"requestedRawValue"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if(result){[result addEntriesFromDictionary:request];result[@"activePresetVerified"]=@NO;result[@"otherBitsPreservationVerified"]=@NO;result[@"persistenceVerified"]=@NO;}
        if(completion)completion(result?[result copy]:nil,error);
    }];
}
- (void)sendFactorySettingsResetRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *request=RSAppFactoryResetSpec(spec);
    if(!request){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Explicit sourcePlatform HG724 required",nil));});return;}
    [self startAppCommand:0x13 parameters:nil mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if(result){result[@"requestedSourcePlatform"]=request[@"requestedSourcePlatform"];result[@"targetResetScopeVerified"]=@NO;result[@"persistenceVerified"]=@NO;}
        if(completion)completion(result?[result copy]:nil,error);
    }];
}
- (void)sendHandleSettingRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *request=RSAppHandleWriteSpec(spec);
    if(!request){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Named handle setting and integer value0/1 required",nil));});return;}
    [self startAppCommand:0x35 parameters:@[@{@"index":request[@"offset"],@"size":@1}] mode:request[@"requestedValue"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if(result){result[@"setting"]=request[@"setting"];result[@"requestedValue"]=request[@"requestedValue"];result[@"unspecifiedByteSemanticsVerified"]=@NO;result[@"readbackVerified"]=@NO;result[@"persistenceVerified"]=@NO;}
        if(completion)completion(result?[result copy]:nil,error);
    }];
}
- (void)getHandleSettingsWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self startAppCommand:0x36 parameters:nil mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if(error){if(completion)completion(nil,error);return;}NSError *decodeError=nil;
        NSDictionary *result=RSDecodeAppHandleReply(reply[@"message"],&decodeError);if(completion)completion(result,decodeError);
    }];
}
- (void)getStandaloneTuning:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSArray *selection=RSAppStandaloneSelection(filters);
    if(!selection){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Invalid standalone selection",nil));});return;}
    NSMutableArray *context=[NSMutableArray arrayWithObject:@{@"index":@72,@"size":@1}];for(NSDictionary *row in selection)[context addObject:@{@"index":row[@"index"],@"size":@2}];
    [self startAppCommand:0x10 parameters:context mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if(error){if(completion)completion(nil,error);return;}NSError *decodeError=nil;
        NSDictionary *result=RSDecodeAppStandaloneReply(reply[@"message"],selection,&decodeError);if(completion)completion(result,decodeError);
    }];
}
- (void)setStandaloneTuning:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *row=RSAppStandaloneWriteSpec(spec);
    if(!row){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Standalone write requires explicit inputSource2 and a named value",nil));});return;}
    [self startAppCommand:0x0f parameters:@[@{@"index":@72,@"size":@1},@{@"index":row[@"index"],@"size":@2}] mode:row[@"value"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if(result)[result addEntriesFromDictionary:@{@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"requestedValue":row[@"value"],@"requestedInputSource":@2,@"activePresetVerified":@NO}];
        if(completion)completion(result?[result copy]:nil,error);
    }];
}
- (void)getFollowTuning:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self getNumericTuning:@"follow" filters:filters timeoutMs:timeoutMs completion:completion];
}
- (void)setFollowTuning:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self setNumericTuning:@"follow" spec:spec timeoutMs:timeoutMs completion:completion];
}
- (void)getRcTuning:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self getNumericTuning:@"rc" filters:filters timeoutMs:timeoutMs completion:completion];
}
- (void)setRcTuning:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self setNumericTuning:@"rc" spec:spec timeoutMs:timeoutMs completion:completion];
}
- (void)getNumericTuning:(NSString *)domain filters:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSArray *selection=RSAppTuningSelection(domain,filters);
    if (!selection) { if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Invalid numeric tuning selection",nil));});return; }
    NSMutableArray *context=[NSMutableArray array];for(NSDictionary *row in selection)[context addObject:@{@"index":row[@"index"],@"size":row[@"size"]}];
    [self startAppCommand:0x10 parameters:context mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if(error){if(completion)completion(nil,error);return;}
        NSError *decodeError=nil;NSDictionary *result=RSDecodeAppTuningReply(reply[@"message"],selection,&decodeError);if(completion)completion(result,decodeError);
    }];
}
- (void)setNumericTuning:(NSString *)domain spec:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *row=RSAppTuningWriteSpec(domain,spec);
    if(!row){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Invalid named numeric tuning value",nil));});return;}
    [self startAppCommand:0x0f parameters:@[@{@"index":row[@"index"],@"size":row[@"size"]}] mode:row[@"value"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        NSMutableDictionary *result=[reply mutableCopy];if(result)[result addEntriesFromDictionary:@{@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"requestedValue":row[@"value"],@"activePresetVerified":@NO}];
        if(completion)completion(result?[result copy]:nil,error);
    }];
}
- (void)getMotorTuning:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSArray *selection=RSAppMotorSelection(filters);
    if (!selection) { if (completion) dispatch_async(dispatch_get_main_queue(), ^{ completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Invalid motor selection",nil)); }); return; }
    NSMutableArray *context=[NSMutableArray array];
    for (NSDictionary *row in selection) [context addObject:@{@"index":row[@"index"],@"size":@1}];
    [self startAppCommand:0x32 parameters:context mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if (error) { if (completion) completion(nil,error); return; }
        NSError *decodeError=nil; NSDictionary *result=RSDecodeAppMotorReply(reply[@"message"],selection,&decodeError);
        if (completion) completion(result,decodeError);
    }];
}
- (void)setMotorTuning:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *row=RSAppMotorWriteSpec(spec);
    if (!row) { if (completion) dispatch_async(dispatch_get_main_queue(), ^{ completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Invalid named motor value",nil)); }); return; }
    NSArray *context=@[@{@"index":row[@"index"],@"size":@1}];
    [self startAppCommand:0x31 parameters:context mode:row[@"value"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error) {
        if (error) { if (completion) completion(nil,error); return; }
        NSMutableDictionary *result=[reply mutableCopy];
        [result addEntriesFromDictionary:@{@"axis":row[@"axis"],@"parameter":row[@"parameter"],@"requestedValue":row[@"value"]}];
        if (completion) completion([result copy],nil);
    }];
}

- (NSArray *)appParameterSubscriptionKeys{return RSAppParameterSubscriptionKeys();}
- (void)sendParameterSubscriptionRequest:(NSDictionary *)spec completion:(RSAppCompletion)completion{
    NSDictionary *selection=RSAppParameterSubscriptionSpec(spec);
    if(!selection){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Nonempty known subscription keys required",nil));});return;}
    NSDictionary *snapshot=@{@"keys":selection[@"requestedKeys"]};
    [self startAppCommand:18 parameters:nil mode:snapshot settingsKind:nil settingsPatch:nil timeoutMs:3000 completion:^(NSDictionary *reply,NSError *error){if(completion)completion(error?nil:RSAppParameterSubscriptionSent(selection),error);}];
}
- (void)sendProgramStatusSubscriptionRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *selection=RSAppProgramStatusSubscriptionSelection(spec);
    if(!selection){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Named program and boolean enabled required",nil));});return;}
    NSDictionary *snapshot=@{@"program":selection[@"requestedProgram"],@"enabled":selection[@"requestedEnabled"]};
    [self startAppCommand:0x6b parameters:nil mode:snapshot settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error){
        if(error){if(completion)completion(nil,error);return;}
        NSMutableDictionary *result=[reply mutableCopy];[result addEntriesFromDictionary:selection];
        [result addEntriesFromDictionary:@{@"freshStatusVerified":@NO,@"programCorrelationVerified":@NO,@"modelLayoutVerified":@NO,@"notificationStreamVerified":@NO,@"remoteSubscriptionStateVerified":@NO}];
        if(completion)completion([result copy],nil);
    }];
}
- (void)sendProgramStatusRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *selection=RSAppProgramStatusSelection(spec);
    if(!selection){if(completion)dispatch_async(dispatch_get_main_queue(), ^{completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"program must be track, timelapse or panorama",nil));});return;}
    [self startAppCommand:0x6b parameters:nil mode:selection[@"requestedProgramCommandId"] settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *reply,NSError *error){
        if(error){if(completion)completion(nil,error);return;}
        NSMutableDictionary *result=[reply mutableCopy];[result addEntriesFromDictionary:selection];
        [result addEntriesFromDictionary:@{@"requestType":@"RequestSinglePush",@"freshStatusVerified":@NO,@"programCorrelationVerified":@NO,@"modelLayoutVerified":@NO}];
        if(completion)completion([result copy],nil);
    }];
}
- (void)queryCalibrationStatusWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self startAppCommand:0x6e parameters:nil mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:completion];
}
- (void)sendAutoTuneRequest:(NSNumber *)start completion:(RSAppCompletion)completion {
    [self startAppCommand:0x6a parameters:nil mode:[start copy] settingsKind:nil settingsPatch:nil timeoutMs:3000 completion:completion];
}
- (void)startAppCommand:(uint8_t)command parameters:(NSArray *)parameters mode:(id)mode settingsKind:(NSString *)settingsKind settingsPatch:(NSDictionary *)settingsPatch timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSError *error = nil;
    if (![self.appProfile isEqualToString:@"ronin-2.2.2"]) error = RSAppError(@"RS4MINI_PROFILE_REQUIRED", @"Select explicit ronin-2.2.2 source profile", nil);
    else if (!self.ready) error = RSAppError(@"RS4MINI_DISCONNECTED", @"Device is not connected", nil);
    else if (self.busy) error = RSAppError(@"RS4MINI_BUSY", @"Device operation is active", nil);
    else if (!isfinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60000) error = RSAppError(@"RS4MINI_INVALID_ARGUMENT", @"timeoutMs must be >0..60000", nil);
    NSArray *context = parameters ? RSAppParameterContext(parameters) : nil;
    if (!error && ![self appCommandFrame:command sequence:0 context:context mode:mode])
        error = RSAppError(@"RS4MINI_INVALID_ARGUMENT", @"Invalid App command arguments", nil);
    if (error) { if (completion) dispatch_async(dispatch_get_main_queue(), ^{ completion(nil, error); }); return; }
    self.appSettingsKind = settingsKind; self.appSettingsPatch = settingsPatch;
    self.appParameters = (command == 0x10 || command == 0x32) ? context : nil; self.appCommandId = command; self.appCompletion = completion ?: ^(NSDictionary *result, NSError *error) {};
    NSUInteger token = ++self.appToken; __weak typeof(self) weak = self;
    [self beginStopKeepingApp:^{
        if (!weak.ready || !weak.appCompletion || weak.appToken != token) return;
        weak.deviceQuerySequence = [weak reserveSequence]; weak.deviceQueryDeadline = Clock() + timeoutMs / 1000;
        weak.awaitingDeviceQuery = command != 0x6a && command != 18;
        weak.appNoAckPending = command == 0x6a || command == 18; weak.appRequestedStart = command == 0x6a ? mode : nil;
        NSData *packet = [weak appCommandFrame:command sequence:weak.deviceQuerySequence context:context mode:mode];
        [weak writeFrame:packet]; [weak ensureTimer];
    } message:nil];
}
- (void)getAppSettings:(NSString *)kind timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self readAppParameters:@[@{@"index": RSAppSettingsSchema(kind)[@"index"], @"size": @1}] timeoutMs:timeoutMs completion:^(NSDictionary *reply, NSError *error) {
        if (completion) completion(error ? nil : RSDecodeAppSettings(reply, kind), error);
    }];
}
- (void)getFollowSettings:(NSString *)parameter timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSString *kind=RSAppModeKind(@"follow",parameter);
    if (!kind) { if (completion) dispatch_async(dispatch_get_main_queue(), ^{ completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Unknown named follow/RC parameter",nil)); });return; }
    [self getAppSettings:kind timeoutMs:timeoutMs completion:completion];
}
- (void)setFollowSettings:(NSString *)parameter settings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self setAppSettings:RSAppModeKind(@"follow",parameter) settings:settings timeoutMs:timeoutMs completion:completion];
}
- (void)getRcSettings:(NSString *)parameter timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSString *kind=RSAppModeKind(@"rc",parameter);
    if (!kind) { if (completion) dispatch_async(dispatch_get_main_queue(), ^{ completion(nil,RSAppError(@"RS4MINI_INVALID_ARGUMENT",@"Unknown named follow/RC parameter",nil)); });return; }
    [self getAppSettings:kind timeoutMs:timeoutMs completion:completion];
}
- (void)setRcSettings:(NSString *)parameter settings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self setAppSettings:RSAppModeKind(@"rc",parameter) settings:settings timeoutMs:timeoutMs completion:completion];
}
- (void)getCustomFollowSettingsWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self getAppSettings:@"customFollow" timeoutMs:timeoutMs completion:completion];
}
- (void)getMotorSettingsWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self getAppSettings:@"motor" timeoutMs:timeoutMs completion:completion];
}
- (void)setAppSettings:(NSString *)kind settings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSDictionary *patch = RSAppSettingsPatch(kind, settings);
    if (!patch) {
        if (completion) dispatch_async(dispatch_get_main_queue(), ^{ completion(nil, RSAppError(@"RS4MINI_INVALID_ARGUMENT", @"Settings require valid named fields", nil)); }); return;
    }
    NSArray *context = @[@{@"index": RSAppSettingsSchema(kind)[@"index"], @"size": @1}];
    [self startAppCommand:0x10 parameters:context mode:nil settingsKind:kind settingsPatch:patch timeoutMs:timeoutMs completion:completion];
}
- (void)setCustomFollowSettings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self setAppSettings:@"customFollow" settings:settings timeoutMs:timeoutMs completion:completion];
}
- (void)setMotorSettings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self setAppSettings:@"motor" settings:settings timeoutMs:timeoutMs completion:completion];
}
- (void)readAppParameters:(NSArray<NSDictionary *> *)parameters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self startAppCommand:0x10 parameters:parameters mode:nil settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:completion];
}
- (void)getFollowSensitivityWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    [self readAppParameters:@[@{@"index": @150, @"size": @1}] timeoutMs:timeoutMs completion:^(NSDictionary *result, NSError *error) {
        if (!completion) return;
        if (error) { completion(nil, error); return; }
        unsigned int raw = 0; [[NSScanner scannerWithString:result[@"parameters"][0][@"rawHex"]] scanHexInt:&raw];
        NSMutableDictionary *reading = [result mutableCopy]; reading[@"rawValue"] = @(raw); reading[@"mode"] = raw <= 1 ? @(raw) : NSNull.null;
        completion([reading copy], nil);
    }];
}
- (void)setFollowSensitivity:(NSNumber *)mode timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion {
    NSNumber *snapshot = [mode copy];
    [self startAppCommand:0x0f parameters:nil mode:snapshot settingsKind:nil settingsPatch:nil timeoutMs:timeoutMs completion:^(NSDictionary *result, NSError *error) {
        if (!completion) return;
        if (error) { completion(nil, error); return; }
        NSMutableDictionary *value = [result mutableCopy]; value[@"requestedMode"] = snapshot;
        completion([value copy], nil);
    }];
}
- (void)cancelPosition {}
- (void)cancelComposedMotion {}
- (void)checkComposedBackpressure {}
- (BOOL)advanceComposedMotion { return NO; }
- (void)didReceiveMessage:(NSDictionary *)message {}
- (void)didReceiveTelemetry:(NSDictionary *)sample {}
- (void)beginResearchRate { self.nativeRateActive = YES; }
- (uint16_t)reserveSequence { return self.sequence++; }
- (void)writeVelocityPan:(double)pan tilt:(double)tilt roll:(double)roll { [self writeFrame:RSVelocityFrame(self.sequence++, pan, tilt, roll)]; }
- (void)writeResearchCommand:(NSDictionary *)command sequence:(uint16_t)sequence { [self writeFrame:[self researchFrame:command sequence:sequence]]; }
- (BOOL)matchesResearchResponse:(NSDictionary *)message sequence:(uint16_t)sequence kind:(NSString *)kind {
    RSFrameDecoder *decoder = [RSFrameDecoder new];
    NSDictionary *expected = [decoder push:RSResearchQueryFrame(sequence, kind)].firstObject;
    return [message[@"sender"] intValue] == 4 && [message[@"receiver"] intValue] == 2 &&
        ([message[@"flags"] intValue] & 0x80) && [message[@"sequence"] unsignedShortValue] == sequence &&
        [message[@"commandSet"] isEqual:expected[@"commandSet"]] && [message[@"commandId"] isEqual:expected[@"commandId"]];
}
@end
