#import <AppKit/AppKit.h>
#import <CoreBluetooth/CoreBluetooth.h>

#import "RSGimbal.h"
#import "RSSDKPanel.h"

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

@interface AppDelegate : NSObject <NSApplicationDelegate, NSWindowDelegate>
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) RSSDKPanel *sdkPanel;
@property(nonatomic, strong) NSTimer *sdkRefresh;
@property(nonatomic, strong) RSGimbal *gimbal;
@property(nonatomic, strong) NSTextField *status;
@property(nonatomic, strong) NSButton *connectButton;
@property(nonatomic, strong) NSSlider *speedSlider;
@property(nonatomic, strong) NSTextField *speedLabel;
@property(nonatomic, strong) NSArray<NSButton *> *motionButtons;
@property(nonatomic, strong) NSTextField *telemetryLabel;
@property(nonatomic, strong) NSArray<NSTextField *> *targetFields;
@property(nonatomic, strong) NSArray<NSButton *> *targetChecks;
@property(nonatomic, strong) NSButton *moveButton;
@property(nonatomic, strong) NSButton *currentButton;
@property(nonatomic, strong) NSDictionary *latestJoints;
@property(nonatomic, strong) NSButton *autoReconnect;
@property(nonatomic, strong) NSButton *saveHomeButton;
@property(nonatomic, strong) NSButton *returnHomeButton;
@property(nonatomic, strong) NSPopUpButton *scriptType;
@property(nonatomic, strong) NSButton *runScriptButton;
@property(nonatomic, strong) NSTextField *scriptLabel;
@property(nonatomic, strong) NSDictionary *loadedScript;
@property(nonatomic, strong) NSPopUpButton *quaternionOrder;
@property(nonatomic, strong) NSButton *quaternionConjugate;
@property(nonatomic, strong) NSTextField *orientationLabel;
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
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 1080, MIN(820,NSScreen.mainScreen.visibleFrame.size.height-50))
                                              styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable)
                                                backing:NSBackingStoreBuffered defer:NO];
    self.window.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];
    self.window.title = @"RS 4 Mini Control";
    self.window.delegate = self;
    self.window.backgroundColor = [NSColor colorWithWhite:0.075 alpha:1];
    [self.window center];
    [self.window makeKeyAndOrderFront:nil];

    NSScrollView *scroll = [[NSScrollView alloc] initWithFrame:NSMakeRect(0,0,420,self.window.contentView.bounds.size.height)];
    scroll.autoresizingMask = NSViewHeightSizable; scroll.hasVerticalScroller = YES;
    scroll.autohidesScrollers = YES; scroll.drawsBackground = NO;
    NSView *v = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 420, 1120)];
    scroll.documentView = v; [self.window.contentView addSubview:scroll];
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

    // Preserve the original hold controls above the telemetry and position form.
    for (NSView *item in v.subviews) { NSRect frame = item.frame; frame.origin.y += 220; item.frame = frame; }
    self.telemetryLabel = Label(@"姿态 / 机械关节：等待反馈", 12, NSFontWeightRegular);
    self.telemetryLabel.frame = NSMakeRect(30, 202, 360, 46);
    self.telemetryLabel.maximumNumberOfLines = 2; [v addSubview:self.telemetryLabel];
    NSMutableArray *fields = [NSMutableArray array], *checks = [NSMutableArray array];
    NSArray *names = @[@"Pan / Yaw", @"Tilt / Pitch", @"Roll"];
    for (NSUInteger i = 0; i < 3; i++) {
        double y = 154 - i * 40;
        NSButton *check = [NSButton checkboxWithTitle:names[i] target:nil action:nil];
        check.state = i == 0 ? NSControlStateValueOn : NSControlStateValueOff;
        check.frame = NSMakeRect(40, y, 110, 28); [v addSubview:check]; [checks addObject:check];
        NSTextField *field = [[NSTextField alloc] initWithFrame:NSMakeRect(165, y, 200, 28)];
        field.placeholderString = @"机械目标角度（度）";
        [v addSubview:field]; [fields addObject:field];
    }
    self.targetFields = fields; self.targetChecks = checks;
    self.currentButton = [NSButton buttonWithTitle:@"填入当前角度" target:self action:@selector(useCurrent:)];
    self.currentButton.frame = NSMakeRect(40, 22, 160, 34); self.currentButton.enabled = NO; [v addSubview:self.currentButton];
    self.moveButton = [NSButton buttonWithTitle:@"低速移动到选中目标" target:self action:@selector(moveTapped:)];
    self.moveButton.frame = NSMakeRect(210, 22, 180, 34); self.moveButton.enabled = NO; [v addSubview:self.moveButton];

    for (NSView *item in v.subviews) { NSRect frame = item.frame; frame.origin.y += 300; item.frame = frame; }
    self.autoReconnect = [NSButton checkboxWithTitle:@"意外断线自动重连（最多 5 次，不恢复运动）" target:self action:@selector(autoReconnectChanged:)];
    self.autoReconnect.frame = NSMakeRect(35, 274, 360, 28); [v addSubview:self.autoReconnect];
    self.saveHomeButton = [NSButton buttonWithTitle:@"保存当前位置" target:self action:@selector(saveHome:)];
    self.saveHomeButton.frame = NSMakeRect(40, 232, 160, 32); [v addSubview:self.saveHomeButton];
    self.returnHomeButton = [NSButton buttonWithTitle:@"选中轴返回保存位置" target:self action:@selector(returnHome:)];
    self.returnHomeButton.frame = NSMakeRect(210, 232, 180, 32); [v addSubview:self.returnHomeButton];
    self.scriptType = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(40, 186, 150, 30) pullsDown:NO];
    [self.scriptType addItemsWithTitles:@[@"速度关键帧", @"关节路点", @"实验指令（未验证）"]]; [v addSubview:self.scriptType];
    NSButton *load = [NSButton buttonWithTitle:@"载入 JSON" target:self action:@selector(loadScript:)];
    load.frame = NSMakeRect(200, 186, 90, 30); [v addSubview:load];
    self.runScriptButton = [NSButton buttonWithTitle:@"执行" target:self action:@selector(runScript:)];
    self.runScriptButton.frame = NSMakeRect(300, 186, 90, 30); [v addSubview:self.runScriptButton];
    self.scriptLabel = Label(@"尚未载入 · 载入后需点击执行", 11, NSFontWeightRegular);
    self.scriptLabel.frame = NSMakeRect(30, 150, 360, 28); self.scriptLabel.maximumNumberOfLines = 2; [v addSubview:self.scriptLabel];
    self.quaternionOrder = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(40, 104, 180, 28) pullsDown:NO];
    [self.quaternionOrder addItemsWithTitles:@[@"四元数顺序（未确认）", @"wxyz", @"xyzw"]]; [v addSubview:self.quaternionOrder];
    self.quaternionConjugate = [NSButton checkboxWithTitle:@"共轭" target:nil action:nil];
    self.quaternionConjugate.frame = NSMakeRect(240, 104, 120, 28); [v addSubview:self.quaternionConjugate];
    NSButton *convert = [NSButton buttonWithTitle:@"按所选约定换算" target:self action:@selector(convertOrientation:)];
    convert.frame = NSMakeRect(40, 62, 150, 30); [v addSubview:convert];
    self.orientationLabel = Label(@"仅数学转换\n不用于定位控制", 10, NSFontWeightRegular);
    self.orientationLabel.frame = NSMakeRect(200, 54, 190, 44); self.orientationLabel.maximumNumberOfLines = 2; [v addSubview:self.orientationLabel];
    NSTextField *note = Label(@"速度轨迹为开环；实验协议不代表 RS 4 Mini 已支持。", 10, NSFontWeightRegular);
    note.frame = NSMakeRect(25, 14, 370, 28); [v addSubview:note];
    [scroll.contentView scrollToPoint:NSMakePoint(0, 1120 - scroll.contentSize.height)]; [scroll reflectScrolledClipView:scroll.contentView];

    __weak typeof(self) weakSelf = self;
    self.gimbal = [[RSGimbal alloc] initWithStatus:^(NSString *text, BOOL ready) {
        weakSelf.status.stringValue = text;
        weakSelf.status.textColor = ready ? NSColor.systemGreenColor : NSColor.secondaryLabelColor;
        weakSelf.connectButton.title = ready ? @"断开稳定器" : (weakSelf.gimbal.connecting ? @"取消连接" : @"连接稳定器");
        weakSelf.connectButton.enabled = YES;
        for (NSButton *button in weakSelf.motionButtons) button.enabled = ready && !weakSelf.gimbal.busy;
        weakSelf.moveButton.enabled = weakSelf.currentButton.enabled = ready && !weakSelf.gimbal.busy && weakSelf.latestJoints != nil;
        [weakSelf refreshExpansion];
    }];
    self.gimbal.telemetryHandler = ^(NSDictionary *sample) {
        NSDictionary *attitude = sample[@"attitude"], *joints = sample[@"jointAngles"];
        BOOL first = weakSelf.latestJoints == nil;
        weakSelf.latestJoints = joints;
        if (joints) {
            weakSelf.telemetryLabel.stringValue = [NSString stringWithFormat:@"姿态 P %.1f°  R %.1f°  Y %.1f°\n关节 Pan %.2f°  Tilt %.1f°  Roll %.1f°", [attitude[@"pitch"] doubleValue], [attitude[@"roll"] doubleValue], [attitude[@"yaw"] doubleValue], [joints[@"yaw"] doubleValue], [joints[@"pitch"] doubleValue], [joints[@"roll"] doubleValue]];
            if (first) [weakSelf useCurrent:nil];
        } else weakSelf.telemetryLabel.stringValue = @"姿态 / 机械关节：等待反馈";
        weakSelf.moveButton.enabled = weakSelf.currentButton.enabled = weakSelf.gimbal.ready && !weakSelf.gimbal.busy && joints != nil;
        [weakSelf refreshExpansion];
    };
    self.gimbal.experimentalStatusHandler = ^(NSDictionary *sample) {
        weakSelf.scriptLabel.stringValue = [@"实验状态（未验证）：" stringByAppendingString:sample.description];
    };
    self.sdkPanel=[[RSSDKPanel alloc]initWithFrame:NSMakeRect(430,0,650,820) gimbal:self.gimbal];
    NSScrollView *sdkScroll=[[NSScrollView alloc]initWithFrame:NSMakeRect(430,0,650,self.window.contentView.bounds.size.height)];
    sdkScroll.hasVerticalScroller=YES;sdkScroll.autohidesScrollers=YES;sdkScroll.scrollerStyle=NSScrollerStyleOverlay;sdkScroll.drawsBackground=NO;
    sdkScroll.documentView=self.sdkPanel;[self.window.contentView addSubview:sdkScroll];
    [sdkScroll.contentView scrollToPoint:NSMakePoint(0,MAX(0,820-sdkScroll.contentSize.height))];[sdkScroll reflectScrolledClipView:sdkScroll.contentView];
    self.gimbal.appStatusHandler=^(NSDictionary *sample){[weakSelf.sdkPanel receiveStatus:sample];};
    self.gimbal.messageHandler=^(NSDictionary *message){[weakSelf.sdkPanel receiveMessage:message];};
    self.sdkRefresh=[NSTimer timerWithTimeInterval:0.2 repeats:YES block:^(NSTimer *timer){[weakSelf.sdkPanel refresh];}];
    [[NSRunLoop mainRunLoop]addTimer:self.sdkRefresh forMode:NSRunLoopCommonModes];
    [self refreshExpansion];
}

- (void)refreshExpansion {
    BOOL ready = self.gimbal.ready && !self.gimbal.busy;
    self.saveHomeButton.enabled = ready && self.latestJoints != nil;
    self.returnHomeButton.enabled = ready && self.gimbal.home != nil;
    self.runScriptButton.enabled = ready && self.loadedScript != nil;
    self.autoReconnect.state = self.gimbal.autoReconnectEnabled ? NSControlStateValueOn : NSControlStateValueOff;
}
- (void)autoReconnectChanged:(NSButton *)button { self.gimbal.autoReconnectEnabled = button.state == NSControlStateValueOn; }
- (void)saveHome:(id)sender { [self.gimbal captureHome]; [self refreshExpansion]; }
- (void)returnHome:(id)sender {
    NSMutableArray *axes = [NSMutableArray array]; NSArray *names = @[@"pan", @"tilt", @"roll"];
    for (NSUInteger i = 0; i < 3; i++) if (self.targetChecks[i].state == NSControlStateValueOn) [axes addObject:names[i]];
    [self.gimbal moveHomeAxes:axes];
}
- (void)loadScript:(id)sender {
    NSOpenPanel *panel = [NSOpenPanel openPanel]; panel.canChooseDirectories = NO; panel.allowsMultipleSelection = NO;
    NSInteger kind = self.scriptType.indexOfSelectedItem;
    [panel beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse response) {
        if (response != NSModalResponseOK) return;
        NSError *error; NSData *data = [NSData dataWithContentsOfURL:panel.URL options:0 error:&error];
        id value = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:&error] : nil;
        if (!value || (kind < 2 ? ![value isKindOfClass:NSArray.class] : ![value isKindOfClass:NSDictionary.class])) { self.status.stringValue = error.localizedDescription ?: @"轨迹/路点需 JSON 数组，实验指令需 JSON 对象"; return; }
        self.loadedScript = @{@"kind": @(kind), @"payload": value};
        self.scriptLabel.stringValue = [NSString stringWithFormat:@"已载入 %@：%@ · 尚未执行", @[@"速度关键帧", @"关节路点", @"实验指令"][kind], panel.URL.lastPathComponent];
        [self refreshExpansion];
    }];
}
- (void)runScript:(id)sender {
    if (!self.loadedScript || self.gimbal.busy || !self.gimbal.ready) return;
    NSInteger kind = [self.loadedScript[@"kind"] integerValue]; id value = self.loadedScript[@"payload"];
    if (kind == 0) [self.gimbal runTrajectory:value interpolation:@"smoothstep"];
    else if (kind == 1) [self.gimbal moveThrough:value];
    else [self.gimbal sendExperimentalCommand:value];
    [self refreshExpansion];
}
- (void)convertOrientation:(id)sender {
    if (self.quaternionOrder.indexOfSelectedItem == 0) { self.orientationLabel.stringValue = @"请显式选择分量顺序\n设备约定仍未确认"; return; }
    NSDictionary *value = [self.gimbal orientationWithOrder:self.quaternionOrder.titleOfSelectedItem conjugate:self.quaternionConjugate.state == NSControlStateValueOn];
    if (!value) { self.orientationLabel.stringValue = @"暂无有效单位四元数"; return; }
    NSDictionary *euler = value[@"euler"];
    self.orientationLabel.stringValue = [NSString stringWithFormat:@"ZYX P %.1f R %.1f Y %.1f\n设备坐标未验证", [euler[@"pitch"] doubleValue], [euler[@"roll"] doubleValue], [euler[@"yaw"] doubleValue]];
}

- (void)useCurrent:(id)sender {
    if (!self.latestJoints) return;
    NSArray *keys = @[@"yaw", @"pitch", @"roll"];
    for (NSUInteger i = 0; i < 3; i++) self.targetFields[i].stringValue = [NSString stringWithFormat:@"%.2f", [self.latestJoints[keys[i]] doubleValue]];
}
- (void)moveTapped:(id)sender {
    NSMutableDictionary *targets = [NSMutableDictionary dictionary]; NSArray *keys = @[@"pan", @"tilt", @"roll"];
    for (NSUInteger i = 0; i < 3; i++) if (self.targetChecks[i].state == NSControlStateValueOn) {
        NSScanner *scanner = [NSScanner scannerWithString:self.targetFields[i].stringValue]; double value;
        if (![scanner scanDouble:&value] || !scanner.isAtEnd || !isfinite(value) || fabs(value) > 180) { self.status.stringValue = @"请输入 -180 到 180 的有限角度"; return; }
        targets[keys[i]] = @(value);
    }
    [self.gimbal moveTo:targets];
}
- (void)applicationWillResignActive:(NSNotification *)notification { [self.gimbal stop]; }
- (void)windowDidResignKey:(NSNotification *)notification { [self.gimbal stop]; }

- (void)connectTapped:(id)sender {
    if (self.gimbal.ready || self.gimbal.connecting) [self.gimbal disconnect];
    else { self.connectButton.enabled = NO; [self.gimbal connect]; }
}

- (void)speedChanged:(NSSlider *)sender {
    self.speedLabel.stringValue = [NSString stringWithFormat:@"摇杆驱动力 %.0f%%", sender.doubleValue];
}
- (void)stopTapped:(id)sender { [self.gimbal stop]; }
- (void)centerTapped:(id)sender { [self.gimbal recenter]; }
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender { return YES; }
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    self.gimbal.autoReconnectEnabled = NO;
    if (self.gimbal.connecting) { [self.gimbal disconnect]; return NSTerminateNow; }
    if (!self.gimbal.ready) return NSTerminateNow;
    [self.gimbal disconnect]; NSTimeInterval deadline = NSProcessInfo.processInfo.systemUptime + 5;
    NSTimer *timer = [NSTimer timerWithTimeInterval:0.1 repeats:YES block:^(NSTimer *poll) {
        if (!self.gimbal.ready || NSProcessInfo.processInfo.systemUptime >= deadline) { [poll invalidate]; [sender replyToApplicationShouldTerminate:YES]; }
    }];
    [[NSRunLoop mainRunLoop] addTimer:timer forMode:NSRunLoopCommonModes];
    return NSTerminateLater;
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
