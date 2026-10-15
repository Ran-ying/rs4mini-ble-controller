#import "RSGimbal.h"
#import "RSBleDevice_Internal.h"
#import "RSMotionCore.h"
#include <math.h>
static NSTimeInterval Clock(void) { return NSProcessInfo.processInfo.systemUptime; }
@interface RSGimbal ()
@property(nonatomic, strong) RSPositionLoop *position;
@property(nonatomic, strong) RSTrajectoryLoop *trajectory;
@property(nonatomic, strong) NSDictionary *home;
@property(nonatomic, strong) NSUUID *homeIdentifier;
@property(nonatomic, strong) NSArray *waypoints;
@property(nonatomic) NSUInteger waypointIndex;
@property(nonatomic) NSTimeInterval waypointDeadline;
@property(nonatomic, strong) NSDictionary *experimentalJob;
@property(nonatomic) NSTimeInterval experimentalDeadline;
@property(nonatomic) uint16_t experimentalSequence;
@property(nonatomic) BOOL experimentalSent;
@end
@implementation RSGimbal
- (instancetype)initWithStatus:(StatusHandler)handler central:(CBCentralManager *)central {
    if ((self = [super initWithStatus:handler central:central])) {
        _position = [RSPositionLoop new]; _trajectory = [RSTrajectoryLoop new];
    }
    return self;
}
- (void)cancelPosition { [self.position cancel]; }
- (void)cancelComposedMotion {
    [self.position cancel]; [self.trajectory cancel]; self.waypoints = nil; self.waypointDeadline = 0; self.experimentalJob = nil;
}
- (void)didReceiveTelemetry:(NSDictionary *)sample {
    if (sample[@"jointAngles"]) [self.position feedback:sample[@"jointAngles"] at:self.latestJointAt];
}
- (void)didReceiveMessage:(NSDictionary *)message {
    if (self.experimentalSent && [self.experimentalJob[@"command"] isEqualToString:@"query"] &&
        [self matchesResearchResponse:message sequence:self.experimentalSequence kind:self.experimentalJob[@"kind"]]) {
        self.experimentalJob = nil;
        [self status:[NSString stringWithFormat:@"已收到关联实验查询响应（%lu 字节）", (unsigned long)[message[@"payload"] length]]];
        if (self.experimentalStatusHandler) self.experimentalStatusHandler(@{@"kind": @"query-response", @"message": message, @"deviceVerified": @NO});
    }
}
- (void)checkComposedBackpressure {
    if (self.trajectory.active && !self.outgoing.empty && Clock() - self.lastWriteProgress > .5) {
        [self.trajectory cancel]; [self beginStop:nil message:@"轨迹链路延误超过 500 ms，已取消并尝试停止"];
    }
}
- (BOOL)advanceComposedMotion {
    if (self.experimentalJob) {
        NSString *kind = self.experimentalJob[@"command"];
        if ([kind isEqualToString:@"sleep"] && self.outgoing.empty) { self.experimentalJob = nil; [self status:@"实验休眠/唤醒写入已完成，设备效果未验证"]; }
        else if (Clock() >= self.experimentalDeadline) {
            self.experimentalJob = nil;
            if ([kind isEqualToString:@"query"]) [self status:@"实验查询超时，未收到关联响应"];
            else [self beginStop:nil message:@"实验观察/速率时段已结束并尝试停止，不代表物理到位"];
        } else if ([kind isEqualToString:@"rate"] && self.outgoing.empty) {
            [self writeResearchCommand:self.experimentalJob sequence:[self reserveSequence]];
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
            [self writeVelocityPan:[v[@"pan"] doubleValue] tilt:[v[@"tilt"] doubleValue] roll:[v[@"roll"] doubleValue]];
        }
    } else if (self.trajectory.active) {
        if (self.outgoing.empty) {
            NSString *state = [self.trajectory step:Clock()]; NSDictionary *v = self.trajectory.velocity;
            if ([state isEqualToString:@"moving"]) [self writeVelocityPan:[v[@"pan"] doubleValue] tilt:[v[@"tilt"] doubleValue] roll:[v[@"roll"] doubleValue]];
            else [self beginStop:nil message:[state isEqualToString:@"done"] ? @"速度轨迹结束，已发送停止指令" : @"轨迹调度延误，已取消并停止"];
        }
    } else if (self.waypoints) {
        if (self.waypointDeadline && Clock() >= self.waypointDeadline) {
            self.waypointDeadline = 0; self.waypointIndex++;
            if (self.waypointIndex >= self.waypoints.count) { self.waypoints = nil; [self status:@"所有路点已完成"]; }
            else [self startWaypoint];
        }
    } else return NO;
    return YES;
}

- (BOOL)busy { return [super busy] || self.position.active || self.trajectory.active || self.waypoints != nil || self.experimentalJob != nil; }

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

- (void)sendExperimentalCommand:(NSDictionary *)command {
    NSDictionary *job = [self prepareResearchCommand:command]; if (!job) return;
    NSString *kind = job[@"command"];
    NSString *timeKey = [kind isEqualToString:@"query"] ? @"timeoutMs" : ([kind isEqualToString:@"rate"] ? @"durationMs" : @"observeMs");
    self.researchProfile = [command[@"profile"] copy]; self.researchStatus = nil;
    if ([kind isEqualToString:@"observe"]) { [self status:@"已选择研究配置，仅观察被动状态，本机映射未验证"]; return; }
    self.experimentalJob = [job copy]; self.experimentalSent = NO;
    __weak typeof(self) weak = self;
    [self beginStop:^{
        if (!weak.experimentalJob) return;
        weak.experimentalSequence = [weak reserveSequence];
        weak.experimentalSent = YES;
        weak.experimentalDeadline = Clock() + [weak.experimentalJob[timeKey] doubleValue] / 1000;
        if ([kind isEqualToString:@"sleep"]) weak.experimentalDeadline = Clock() + 3;
        if ([kind isEqualToString:@"rate"]) [weak beginResearchRate];
        if (![kind isEqualToString:@"rate"] || [weak.experimentalJob[@"durationMs"] doubleValue] > 0)
            [weak writeResearchCommand:weak.experimentalJob sequence:weak.experimentalSequence];
        [weak status:@"实验命令已排队；本机物理执行未验证"]; [weak ensureTimer];
    } message:nil];
}
@end
