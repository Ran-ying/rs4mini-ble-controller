#import <AppKit/AppKit.h>
#import <CoreBluetooth/CoreBluetooth.h>

static uint8_t DJI_CRC8(const uint8_t *bytes, NSUInteger length) {
    uint8_t crc = 0x77;
    for (NSUInteger i = 0; i < length; i++) {
        crc ^= bytes[i];
        for (NSInteger bit = 0; bit < 8; bit++)
            crc = (crc & 1) ? (uint8_t)((crc >> 1) ^ 0x8c) : (uint8_t)(crc >> 1);
    }
    return crc;
}

static uint16_t DJI_CRC16(const uint8_t *bytes, NSUInteger length) {
    uint16_t crc = 0x3692;
    for (NSUInteger i = 0; i < length; i++) {
        crc ^= bytes[i];
        for (NSInteger bit = 0; bit < 8; bit++)
            crc = (crc & 1) ? (uint16_t)((crc >> 1) ^ 0x8408) : (uint16_t)(crc >> 1);
    }
    return crc;
}

@interface HoldButton : NSButton
@property(nonatomic, copy) void (^onPress)(void);
@property(nonatomic, copy) void (^onRelease)(void);
@end

@implementation HoldButton
- (void)mouseDown:(NSEvent *)event {
    if (!self.enabled) return;
    if (self.onPress) self.onPress();
    [super mouseDown:event];
    if (self.onRelease) self.onRelease();
}
@end

typedef void (^StatusHandler)(NSString *text, BOOL ready);

@interface RSGimbal : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@property(nonatomic, strong) CBCentralManager *central;
@property(nonatomic, strong) CBPeripheral *peripheral;
@property(nonatomic, strong) CBCharacteristic *rx;
@property(nonatomic, strong) CBCharacteristic *tx;
@property(nonatomic, strong) NSTimer *velocityTimer;
@property(nonatomic) uint16_t sequence;
@property(nonatomic) double pan;
@property(nonatomic) double tilt;
@property(nonatomic) double roll;
@property(nonatomic) NSInteger pendingStops;
@property(nonatomic) BOOL ready;
@property(nonatomic, copy) StatusHandler statusHandler;
- (instancetype)initWithStatus:(StatusHandler)handler;
- (void)connect;
- (void)disconnect;
- (void)drivePan:(double)pan tilt:(double)tilt roll:(double)roll;
- (void)stop;
- (void)recenter;
@end

@implementation RSGimbal

- (instancetype)initWithStatus:(StatusHandler)handler {
    if ((self = [super init])) {
        _statusHandler = [handler copy];
        _sequence = 0x0100;
        _central = [[CBCentralManager alloc] initWithDelegate:self queue:dispatch_get_main_queue()];
    }
    return self;
}

- (void)setStatus:(NSString *)text ready:(BOOL)ready {
    if (self.statusHandler) self.statusHandler(text, ready);
}

- (void)connect {
    if (self.ready || self.peripheral.state == CBPeripheralStateConnected) return;
    if (self.central.state != CBManagerStatePoweredOn) {
        [self setStatus:@"等待 Mac 蓝牙可用…" ready:NO];
        return;
    }
    [self setStatus:@"正在寻找 DJI RS 4 Mini…" ready:NO];
    NSMutableDictionary<NSUUID *, CBPeripheral *> *known = [NSMutableDictionary dictionary];
    for (CBUUID *service in @[[CBUUID UUIDWithString:@"FFF0"], [CBUUID UUIDWithString:@"1812"]]) {
        for (CBPeripheral *candidate in [self.central retrieveConnectedPeripheralsWithServices:@[service]])
            known[candidate.identifier] = candidate;
    }
    for (CBPeripheral *candidate in known.allValues) {
        NSString *name = candidate.name ?: @"";
        if ([name rangeOfString:@"DJI RS4 MINI" options:NSCaseInsensitiveSearch].location == NSNotFound &&
            [name rangeOfString:@"DJI RS 4 MINI" options:NSCaseInsensitiveSearch].location == NSNotFound) continue;
        self.peripheral = candidate;
        candidate.delegate = self;
        [self setStatus:[NSString stringWithFormat:@"正在连接 %@…", name] ready:NO];
        [self.central connectPeripheral:candidate options:nil];
        return;
    }
    [self.central scanForPeripheralsWithServices:nil
                                         options:@{CBCentralManagerScanOptionAllowDuplicatesKey: @NO}];
}

- (void)disconnect {
    [self stop];
    CBPeripheral *p = self.peripheral;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.28 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        if (p) [self.central cancelPeripheralConnection:p];
        self.ready = NO;
        [self setStatus:@"已断开" ready:NO];
    });
}

- (void)centralManagerDidUpdateState:(CBCentralManager *)central {
    if (central.state == CBManagerStatePoweredOn) {
        [self setStatus:@"蓝牙就绪，点击连接" ready:NO];
    } else if (central.state == CBManagerStateUnauthorized) {
        [self setStatus:@"请在系统设置中允许蓝牙权限" ready:NO];
    } else if (central.state == CBManagerStatePoweredOff) {
        [self setStatus:@"Mac 蓝牙已关闭" ready:NO];
    } else {
        [self setStatus:@"正在初始化蓝牙…" ready:NO];
    }
}

- (void)centralManager:(CBCentralManager *)central
 didDiscoverPeripheral:(CBPeripheral *)peripheral
     advertisementData:(NSDictionary<NSString *, id> *)advertisementData
                  RSSI:(NSNumber *)RSSI {
    NSString *name = advertisementData[CBAdvertisementDataLocalNameKey] ?: peripheral.name ?: @"";
    if ([name rangeOfString:@"DJI RS4 MINI" options:NSCaseInsensitiveSearch].location == NSNotFound &&
        [name rangeOfString:@"DJI RS 4 MINI" options:NSCaseInsensitiveSearch].location == NSNotFound) return;
    [central stopScan];
    self.peripheral = peripheral;
    peripheral.delegate = self;
    [self setStatus:[NSString stringWithFormat:@"正在连接 %@…", name] ready:NO];
    [central connectPeripheral:peripheral options:nil];
}

- (void)centralManager:(CBCentralManager *)central didConnectPeripheral:(CBPeripheral *)peripheral {
    [self setStatus:@"已连接，正在读取控制通道…" ready:NO];
    [peripheral discoverServices:@[[CBUUID UUIDWithString:@"FFF0"]]];
}

- (void)centralManager:(CBCentralManager *)central
didFailToConnectPeripheral:(CBPeripheral *)peripheral
                  error:(NSError *)error {
    [self setStatus:[NSString stringWithFormat:@"连接失败：%@", error.localizedDescription] ready:NO];
}

- (void)centralManager:(CBCentralManager *)central
didDisconnectPeripheral:(CBPeripheral *)peripheral
              timestamp:(CFAbsoluteTime)timestamp
                 isReconnecting:(BOOL)isReconnecting
                  error:(NSError *)error API_AVAILABLE(macos(13.0)) {
    self.ready = NO;
    self.rx = nil;
    self.tx = nil;
    [self.velocityTimer invalidate];
    self.velocityTimer = nil;
    [self setStatus:error ? @"连接已中断，点击重新连接" : @"已断开" ready:NO];
}

- (void)centralManager:(CBCentralManager *)central
didDisconnectPeripheral:(CBPeripheral *)peripheral
                  error:(NSError *)error {
    self.ready = NO;
    self.rx = nil;
    self.tx = nil;
    [self.velocityTimer invalidate];
    self.velocityTimer = nil;
    [self setStatus:error ? @"连接已中断，点击重新连接" : @"已断开" ready:NO];
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverServices:(NSError *)error {
    if (error || peripheral.services.count == 0) {
        [self setStatus:@"没有找到 FFF0 控制服务" ready:NO];
        return;
    }
    for (CBService *service in peripheral.services)
        [peripheral discoverCharacteristics:nil forService:service];
}

- (void)peripheral:(CBPeripheral *)peripheral
didDiscoverCharacteristicsForService:(CBService *)service
             error:(NSError *)error {
    if (error) {
        [self setStatus:@"读取控制通道失败" ready:NO];
        return;
    }
    for (CBCharacteristic *c in service.characteristics) {
        if ([c.UUID.UUIDString caseInsensitiveCompare:@"FFF4"] == NSOrderedSame) self.rx = c;
        if ([c.UUID.UUIDString caseInsensitiveCompare:@"FFF5"] == NSOrderedSame) self.tx = c;
    }
    if (!self.rx || !self.tx) {
        [self setStatus:@"控制通道不完整" ready:NO];
        return;
    }
    [peripheral setNotifyValue:YES forCharacteristic:self.rx];
}

- (void)peripheral:(CBPeripheral *)peripheral
didUpdateNotificationStateForCharacteristic:(CBCharacteristic *)characteristic
             error:(NSError *)error {
    if (error || !characteristic.isNotifying) {
        [self setStatus:@"无法启用云台通知" ready:NO];
        return;
    }
    self.ready = YES;
    [self setStatus:[NSString stringWithFormat:@"已连接 · %@", peripheral.name ?: @"RS 4 Mini"] ready:YES];
}

- (NSData *)velocityFramePan:(double)pan tilt:(double)tilt roll:(double)roll {
    enum { total = 22 };
    uint8_t f[total]; memset(f, 0, sizeof(f));
    f[0] = 0x55; f[1] = total; f[2] = 0x04; f[3] = DJI_CRC8(f, 3);
    f[4] = 0x02; f[5] = 0x04;
    f[6] = self.sequence & 0xff; f[7] = self.sequence >> 8; self.sequence++;
    f[8] = 0x00; f[9] = 0x04; f[10] = 0x01;
    int16_t t = (int16_t)lrint(1024.0 + fmax(-1, fmin(1, tilt)) * 660.0);
    int16_t r = (int16_t)lrint(1024.0 + fmax(-1, fmin(1, roll)) * 660.0);
    int16_t p = (int16_t)lrint(1024.0 + fmax(-1, fmin(1, pan)) * 660.0);
    f[11] = t & 0xff; f[12] = t >> 8;
    f[13] = r & 0xff; f[14] = r >> 8;
    f[15] = p & 0xff; f[16] = p >> 8;
    f[17] = 0; f[18] = 0; f[19] = 0x02;
    uint16_t crc = DJI_CRC16(f, total - 2); f[20] = crc & 0xff; f[21] = crc >> 8;
    return [NSData dataWithBytes:f length:total];
}

- (NSData *)recenterFrame {
    enum { total = 15 };
    uint8_t f[total]; memset(f, 0, sizeof(f));
    f[0] = 0x55; f[1] = total; f[2] = 0x04; f[3] = DJI_CRC8(f, 3);
    f[4] = 0x02; f[5] = 0x04;
    f[6] = self.sequence & 0xff; f[7] = self.sequence >> 8; self.sequence++;
    f[8] = 0x40; f[9] = 0x04; f[10] = 0x4c; f[11] = 0xfe; f[12] = 0x01;
    uint16_t crc = DJI_CRC16(f, total - 2); f[13] = crc & 0xff; f[14] = crc >> 8;
    return [NSData dataWithBytes:f length:total];
}

- (void)writeFrame:(NSData *)frame {
    if (!self.ready || !self.tx || self.peripheral.state != CBPeripheralStateConnected) return;
    for (NSUInteger off = 0; off < frame.length; off += 20) {
        NSRange range = NSMakeRange(off, MIN((NSUInteger)20, frame.length - off));
        [self.peripheral writeValue:[frame subdataWithRange:range]
                  forCharacteristic:self.tx
                               type:CBCharacteristicWriteWithoutResponse];
    }
}

- (void)ensureVelocityTimer {
    if (self.velocityTimer) return;
    self.velocityTimer = [NSTimer scheduledTimerWithTimeInterval:(1.0 / 15.0)
                                                          target:self
                                                        selector:@selector(velocityTick:)
                                                        userInfo:nil
                                                         repeats:YES];
    [[NSRunLoop mainRunLoop] addTimer:self.velocityTimer forMode:NSRunLoopCommonModes];
}

- (void)velocityTick:(NSTimer *)timer {
    BOOL moving = self.pan != 0 || self.tilt != 0 || self.roll != 0;
    if (!moving && self.pendingStops <= 0) {
        [timer invalidate]; self.velocityTimer = nil; return;
    }
    if (!moving) self.pendingStops--;
    [self writeFrame:[self velocityFramePan:self.pan tilt:self.tilt roll:self.roll]];
}

- (void)drivePan:(double)pan tilt:(double)tilt roll:(double)roll {
    if (!self.ready) return;
    self.pan = fmax(-1, fmin(1, pan));
    self.tilt = fmax(-1, fmin(1, tilt));
    self.roll = fmax(-1, fmin(1, roll));
    self.pendingStops = 0;
    [self ensureVelocityTimer];
    [self writeFrame:[self velocityFramePan:self.pan tilt:self.tilt roll:self.roll]];
}

- (void)stop {
    BOOL wasMoving = self.pan != 0 || self.tilt != 0 || self.roll != 0;
    self.pan = 0; self.tilt = 0; self.roll = 0;
    if (self.ready) {
        self.pendingStops = MAX(self.pendingStops, wasMoving ? 3 : 1);
        [self ensureVelocityTimer];
    }
}

- (void)recenter {
    [self stop];
    if (!self.ready) return;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.22 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        [self writeFrame:[self recenterFrame]];
    });
}
@end

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) RSGimbal *gimbal;
@property(nonatomic, strong) NSTextField *status;
@property(nonatomic, strong) NSButton *connectButton;
@property(nonatomic, strong) NSSlider *speedSlider;
@property(nonatomic, strong) NSTextField *speedLabel;
@property(nonatomic, strong) NSArray<NSButton *> *motionButtons;
@end

@implementation AppDelegate

static NSTextField *Label(NSString *text, CGFloat size, NSFontWeight weight) {
    NSTextField *label = [NSTextField labelWithString:text];
    label.font = [NSFont systemFontOfSize:size weight:weight];
    label.textColor = NSColor.labelColor;
    label.alignment = NSTextAlignmentCenter;
    return label;
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 420, 600)
                                              styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable)
                                                backing:NSBackingStoreBuffered defer:NO];
    self.window.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];
    self.window.title = @"RS 4 Mini Control";
    self.window.backgroundColor = [NSColor colorWithWhite:0.075 alpha:1];
    [self.window center];
    [self.window makeKeyAndOrderFront:nil];

    NSView *v = self.window.contentView;
    NSTextField *title = Label(@"RS 4 MINI", 26, NSFontWeightBold);
    title.frame = NSMakeRect(40, 536, 340, 36); [v addSubview:title];
    NSTextField *subtitle = Label(@"DIRECT BLUETOOTH CONTROL", 11, NSFontWeightMedium);
    subtitle.textColor = NSColor.secondaryLabelColor;
    subtitle.frame = NSMakeRect(40, 512, 340, 20); [v addSubview:subtitle];

    self.status = Label(@"正在初始化蓝牙…", 13, NSFontWeightRegular);
    self.status.frame = NSMakeRect(35, 470, 350, 24); [v addSubview:self.status];

    self.connectButton = [NSButton buttonWithTitle:@"连接稳定器" target:self action:@selector(connectTapped:)];
    self.connectButton.bezelStyle = NSBezelStyleRounded;
    self.connectButton.frame = NSMakeRect(115, 428, 190, 36); [v addSubview:self.connectButton];

    self.speedLabel = Label(@"摇杆驱动力 20%", 13, NSFontWeightMedium);
    self.speedLabel.frame = NSMakeRect(80, 381, 260, 24); [v addSubview:self.speedLabel];
    self.speedSlider = [NSSlider sliderWithValue:20 minValue:3 maxValue:100 target:self action:@selector(speedChanged:)];
    self.speedSlider.frame = NSMakeRect(75, 354, 270, 26); [v addSubview:self.speedSlider];

    HoldButton *(^makeHold)(NSString *, NSRect, double, double, double) = ^HoldButton *(NSString *text, NSRect frame, double pan, double tilt, double roll) {
        HoldButton *b = [[HoldButton alloc] initWithFrame:frame];
        b.title = text; b.font = [NSFont systemFontOfSize:25 weight:NSFontWeightSemibold];
        b.bezelStyle = NSBezelStyleTexturedRounded; b.enabled = NO;
        __weak typeof(self) weakSelf = self;
        b.onPress = ^{ double s = weakSelf.speedSlider.doubleValue / 100.0; [weakSelf.gimbal drivePan:pan * s tilt:tilt * s roll:roll * s]; };
        b.onRelease = ^{ [weakSelf.gimbal stop]; };
        [v addSubview:b]; return b;
    };
    HoldButton *up = makeHold(@"↑", NSMakeRect(170, 284, 80, 54), 0, 1, 0);
    HoldButton *left = makeHold(@"←", NSMakeRect(82, 224, 80, 54), -1, 0, 0);
    HoldButton *right = makeHold(@"→", NSMakeRect(258, 224, 80, 54), 1, 0, 0);
    HoldButton *down = makeHold(@"↓", NSMakeRect(170, 164, 80, 54), 0, -1, 0);
    HoldButton *rollLeft = makeHold(@"↺ Roll", NSMakeRect(82, 100, 120, 46), 0, 0, -1);
    HoldButton *rollRight = makeHold(@"Roll ↻", NSMakeRect(218, 100, 120, 46), 0, 0, 1);
    rollLeft.font = rollRight.font = [NSFont systemFontOfSize:15 weight:NSFontWeightSemibold];
    self.motionButtons = @[up, left, right, down, rollLeft, rollRight];

    NSButton *stop = [NSButton buttonWithTitle:@"停止" target:self action:@selector(stopTapped:)];
    stop.frame = NSMakeRect(170, 224, 80, 54); stop.bezelStyle = NSBezelStyleRounded;
    [v addSubview:stop];
    NSButton *center = [NSButton buttonWithTitle:@"回中" target:self action:@selector(centerTapped:)];
    center.frame = NSMakeRect(130, 40, 160, 36); center.bezelStyle = NSBezelStyleRounded;
    [v addSubview:center];

    __weak typeof(self) weakSelf = self;
    self.gimbal = [[RSGimbal alloc] initWithStatus:^(NSString *text, BOOL ready) {
        weakSelf.status.stringValue = text;
        weakSelf.status.textColor = ready ? NSColor.systemGreenColor : NSColor.secondaryLabelColor;
        weakSelf.connectButton.title = ready ? @"断开稳定器" : @"连接稳定器";
        weakSelf.connectButton.enabled = YES;
        for (NSButton *button in weakSelf.motionButtons) button.enabled = ready;
    }];
}

- (void)connectTapped:(id)sender {
    if (self.gimbal.ready) [self.gimbal disconnect];
    else { self.connectButton.enabled = NO; [self.gimbal connect]; }
}

- (void)speedChanged:(NSSlider *)sender {
    self.speedLabel.stringValue = [NSString stringWithFormat:@"摇杆驱动力 %.0f%%", sender.doubleValue];
}
- (void)stopTapped:(id)sender { [self.gimbal stop]; }
- (void)centerTapped:(id)sender { [self.gimbal recenter]; }
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender { return YES; }
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    if (self.gimbal.ready) {
        [self.gimbal stop];
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.28 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [sender replyToApplicationShouldTerminate:YES];
        });
        return NSTerminateLater;
    }
    return NSTerminateNow;
}
@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = NSApplication.sharedApplication;
        AppDelegate *delegate = [AppDelegate new];
        app.delegate = delegate;
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        [app activateIgnoringOtherApps:YES];
        [app run];
    }
    return 0;
}
