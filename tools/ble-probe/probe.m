#import <CoreBluetooth/CoreBluetooth.h>
#import <Foundation/Foundation.h>

@interface RSProbe : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@property(nonatomic, strong) CBCentralManager *central;
@property(nonatomic, strong) CBPeripheral *selected;
@property(nonatomic, strong) CBCharacteristic *notifyCharacteristic;
@property(nonatomic, strong) CBCharacteristic *writeCharacteristic;
@property(nonatomic, copy) NSArray<NSString *> *nameFragments;
@property(nonatomic) BOOL shouldConnect;
@property(nonatomic) BOOL telemetryCapture;
@property(nonatomic) NSTimeInterval captureDuration;
@property(nonatomic, copy) NSString *axisCapture;
@property(nonatomic) NSInteger calibrationStage;
@property(nonatomic) NSInteger calibrationFramesRemaining;
@property(nonatomic) BOOL queryPosition;
@property(nonatomic) BOOL queryDegreeInfo;
@property(nonatomic) NSInteger controlTest; // 0=none, 1=neutral, 2/3=small pan, 4/5=large pan
@property(nonatomic) BOOL controlTestStarted;
@property(nonatomic) NSInteger movementFramesRemaining;
@property(nonatomic) NSInteger stopFramesRemaining;
@property(nonatomic) uint16_t sequence;
@property(nonatomic) NSInteger pendingServices;
@property(nonatomic) NSInteger characteristicCount;
@property(nonatomic) NSTimeInterval timeout;
- (instancetype)initWithArguments:(NSArray<NSString *> *)arguments;
- (void)start;
@end

static NSString *HexString(NSData *data) {
    if (!data) return @"-";
    const unsigned char *bytes = data.bytes;
    NSMutableString *result = [NSMutableString stringWithCapacity:data.length * 2];
    for (NSUInteger i = 0; i < data.length; i++) [result appendFormat:@"%02x", bytes[i]];
    return result;
}

static NSString *PropertyLabels(CBCharacteristicProperties properties) {
    NSMutableArray<NSString *> *labels = [NSMutableArray array];
    if (properties & CBCharacteristicPropertyBroadcast) [labels addObject:@"broadcast"];
    if (properties & CBCharacteristicPropertyRead) [labels addObject:@"read"];
    if (properties & CBCharacteristicPropertyWriteWithoutResponse) [labels addObject:@"writeWithoutResponse"];
    if (properties & CBCharacteristicPropertyWrite) [labels addObject:@"write"];
    if (properties & CBCharacteristicPropertyNotify) [labels addObject:@"notify"];
    if (properties & CBCharacteristicPropertyIndicate) [labels addObject:@"indicate"];
    if (properties & CBCharacteristicPropertyAuthenticatedSignedWrites) [labels addObject:@"authenticatedSignedWrites"];
    if (properties & CBCharacteristicPropertyExtendedProperties) [labels addObject:@"extendedProperties"];
    if (properties & CBCharacteristicPropertyNotifyEncryptionRequired) [labels addObject:@"notifyEncryptionRequired"];
    if (properties & CBCharacteristicPropertyIndicateEncryptionRequired) [labels addObject:@"indicateEncryptionRequired"];
    return [labels componentsJoinedByString:@","];
}

static NSString *ManagerStateLabel(CBManagerState state) {
    switch (state) {
        case CBManagerStateUnknown: return @"unknown";
        case CBManagerStateResetting: return @"resetting";
        case CBManagerStateUnsupported: return @"unsupported";
        case CBManagerStateUnauthorized: return @"unauthorized";
        case CBManagerStatePoweredOff: return @"poweredOff";
        case CBManagerStatePoweredOn: return @"poweredOn";
    }
    return @"invalid";
}

static NSString *AuthorizationLabel(CBManagerAuthorization authorization) {
    switch (authorization) {
        case CBManagerAuthorizationNotDetermined: return @"notDetermined";
        case CBManagerAuthorizationRestricted: return @"restricted";
        case CBManagerAuthorizationDenied: return @"denied";
        case CBManagerAuthorizationAllowedAlways: return @"allowedAlways";
    }
    return @"invalid";
}

static uint8_t DJI_CRC8(const uint8_t *bytes, NSUInteger length) {
    uint8_t crc = 0x77;
    for (NSUInteger index = 0; index < length; index++) {
        crc ^= bytes[index];
        for (NSInteger bit = 0; bit < 8; bit++) {
            crc = (crc & 1) ? (uint8_t)((crc >> 1) ^ 0x8c) : (uint8_t)(crc >> 1);
        }
    }
    return crc;
}

static uint16_t DJI_CRC16(const uint8_t *bytes, NSUInteger length) {
    uint16_t crc = 0x3692;
    for (NSUInteger index = 0; index < length; index++) {
        crc ^= bytes[index];
        for (NSInteger bit = 0; bit < 8; bit++) {
            crc = (crc & 1) ? (uint16_t)((crc >> 1) ^ 0x8408) : (uint16_t)(crc >> 1);
        }
    }
    return crc;
}

@implementation RSProbe

- (instancetype)initWithArguments:(NSArray<NSString *> *)arguments {
    self = [super init];
    if (!self) return nil;
    _nameFragments = @[@"RS4", @"RS 4", @"RONIN", @"DJI"];
    _timeout = 15;
    _captureDuration = 10;
    _sequence = 0x0100;

    for (NSUInteger index = 1; index < arguments.count; index++) {
        NSString *argument = arguments[index];
        if ([argument isEqualToString:@"--connect"]) {
            _shouldConnect = YES;
        } else if ([argument isEqualToString:@"--telemetry-capture"]) {
            _shouldConnect = YES;
            _telemetryCapture = YES;
        } else if ([argument isEqualToString:@"--capture-seconds"] && index + 1 < arguments.count) {
            _captureDuration = [arguments[++index] doubleValue];
        } else if ([argument isEqualToString:@"--axis-capture"] && index + 1 < arguments.count) {
            _shouldConnect = YES;
            _axisCapture = [arguments[++index] lowercaseString];
            if (![@[@"pan", @"tilt", @"roll"] containsObject:_axisCapture]) {
                fprintf(stderr, "--axis-capture must be pan, tilt, or roll\n");
                exit(EXIT_FAILURE);
            }
        } else if ([argument isEqualToString:@"--query-position"]) {
            _shouldConnect = YES;
            _queryPosition = YES;
        } else if ([argument isEqualToString:@"--query-degree-info"]) {
            _shouldConnect = YES;
            _queryDegreeInfo = YES;
        } else if ([argument isEqualToString:@"--neutral-test"]) {
            _shouldConnect = YES;
            _controlTest = 1;
        } else if ([argument isEqualToString:@"--pan-test-right"]) {
            _shouldConnect = YES;
            _controlTest = 2;
        } else if ([argument isEqualToString:@"--pan-test-left"]) {
            _shouldConnect = YES;
            _controlTest = 3;
        } else if ([argument isEqualToString:@"--pan-test-right-large"]) {
            _shouldConnect = YES;
            _controlTest = 4;
        } else if ([argument isEqualToString:@"--pan-test-left-large"]) {
            _shouldConnect = YES;
            _controlTest = 5;
        } else if ([argument isEqualToString:@"--timeout"] && index + 1 < arguments.count) {
            _timeout = [arguments[++index] doubleValue];
        } else if ([argument isEqualToString:@"--name"] && index + 1 < arguments.count) {
            _nameFragments = @[arguments[++index]];
        } else if ([argument isEqualToString:@"--output"] && index + 1 < arguments.count) {
            index += 1; // stdout is redirected in main before the probe starts.
        } else if ([argument isEqualToString:@"--help"] || [argument isEqualToString:@"-h"]) {
            printf("Usage: rs4mini-probe [--timeout SECONDS] [--name TEXT] [--connect] [--output FILE]\n");
            printf("                       [--telemetry-capture] [--capture-seconds SECONDS]\n");
            printf("                       [--axis-capture pan|tilt|roll]\n");
            printf("                       [--query-position]\n");
            printf("                       [--query-degree-info]\n");
            printf("                       [--neutral-test | --pan-test-right | --pan-test-left]\n");
            printf("                       [--pan-test-right-large | --pan-test-left-large]\n\n");
            printf("Default mode only scans. --connect only enumerates GATT services and characteristics.\n");
            printf("Explicit motion test modes write bounded control/stop sequences.\n");
            exit(EXIT_SUCCESS);
        } else {
            fprintf(stderr, "Unknown argument: %s\n", argument.UTF8String);
            exit(EXIT_FAILURE);
        }
    }
    return self;
}

- (void)start {
    self.central = [[CBCentralManager alloc] initWithDelegate:self queue:dispatch_get_main_queue()];
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(self.timeout * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
        [self finish:@"Timed out" code:EXIT_SUCCESS];
    });
}

- (void)centralManagerDidUpdateState:(CBCentralManager *)central {
    printf("CoreBluetooth state=%s authorization=%s\n",
           ManagerStateLabel(central.state).UTF8String,
           AuthorizationLabel(CBManager.authorization).UTF8String);
    fflush(stdout);
    if (central.state == CBManagerStateUnauthorized) {
        [self finish:@"Bluetooth permission denied. Allow access in System Settings." code:EXIT_FAILURE];
        return;
    }
    if (central.state != CBManagerStatePoweredOn) return;
    NSMutableDictionary<NSUUID *, CBPeripheral *> *connected = [NSMutableDictionary dictionary];
    for (CBUUID *service in @[[CBUUID UUIDWithString:@"FFF0"], [CBUUID UUIDWithString:@"1812"]]) {
        for (CBPeripheral *peripheral in [central retrieveConnectedPeripheralsWithServices:@[service]]) {
            connected[peripheral.identifier] = peripheral;
        }
    }
    for (CBPeripheral *peripheral in connected.allValues) {
        printf("system-connected name=\"%s\" id=%s state=%ld\n",
               (peripheral.name ?: @"<unnamed>").UTF8String,
               peripheral.identifier.UUIDString.UTF8String,
               (long)peripheral.state);
    }
    if (self.shouldConnect && connected.count) {
        CBPeripheral *peripheral = connected.allValues.firstObject;
        self.selected = peripheral;
        peripheral.delegate = self;
        printf("Connecting read-only to system-connected %s…\n",
               (peripheral.name ?: @"<unnamed>").UTF8String);
        fflush(stdout);
        [central connectPeripheral:peripheral options:nil];
        return;
    }
    printf("Bluetooth ready; scanning for BLE advertisements…\n");
    [central scanForPeripheralsWithServices:nil
                                    options:@{CBCentralManagerScanOptionAllowDuplicatesKey: @NO}];
}

- (void)centralManager:(CBCentralManager *)central
 didDiscoverPeripheral:(CBPeripheral *)peripheral
     advertisementData:(NSDictionary<NSString *, id> *)advertisementData
                  RSSI:(NSNumber *)RSSI {
    NSString *name = advertisementData[CBAdvertisementDataLocalNameKey] ?: peripheral.name ?: @"<unnamed>";
    BOOL matches = NO;
    for (NSString *fragment in self.nameFragments) {
        if ([name rangeOfString:fragment options:NSCaseInsensitiveSearch].location != NSNotFound) {
            matches = YES;
            break;
        }
    }
    if (!matches) return;

    NSArray<CBUUID *> *serviceUUIDs = advertisementData[CBAdvertisementDataServiceUUIDsKey];
    NSMutableArray<NSString *> *serviceNames = [NSMutableArray array];
    for (CBUUID *UUID in serviceUUIDs ?: @[]) [serviceNames addObject:UUID.UUIDString];
    NSString *manufacturer = HexString(advertisementData[CBAdvertisementDataManufacturerDataKey]);
    printf("device name=\"%s\" id=%s rssi=%s services=%s manufacturer=%s\n",
           name.UTF8String,
           peripheral.identifier.UUIDString.UTF8String,
           RSSI.stringValue.UTF8String,
           (serviceNames.count ? [serviceNames componentsJoinedByString:@","] : @"-").UTF8String,
           manufacturer.UTF8String);
    fflush(stdout);

    if (!self.shouldConnect || self.selected) return;
    self.selected = peripheral;
    peripheral.delegate = self;
    [central stopScan];
    printf("Connecting read-only to %s…\n", name.UTF8String);
    [central connectPeripheral:peripheral options:nil];
}

- (void)centralManager:(CBCentralManager *)central didConnectPeripheral:(CBPeripheral *)peripheral {
    printf("Connected; discovering services…\n");
    [peripheral discoverServices:nil];
}

- (void)centralManager:(CBCentralManager *)central
didFailToConnectPeripheral:(CBPeripheral *)peripheral
                  error:(NSError *)error {
    [self finish:[NSString stringWithFormat:@"Connection failed: %@", error.localizedDescription ?: @"unknown error"]
              code:EXIT_FAILURE];
}

- (void)peripheral:(CBPeripheral *)peripheral didDiscoverServices:(NSError *)error {
    if (error) {
        [self finish:[NSString stringWithFormat:@"Service discovery failed: %@", error.localizedDescription]
                  code:EXIT_FAILURE];
        return;
    }
    self.pendingServices = peripheral.services.count;
    if (!self.pendingServices) {
        [self finish:@"Connected, but no services were exposed." code:EXIT_FAILURE];
        return;
    }
    for (CBService *service in peripheral.services) {
        printf("service %s\n", service.UUID.UUIDString.UTF8String);
        [peripheral discoverCharacteristics:nil forService:service];
    }
}

- (void)peripheral:(CBPeripheral *)peripheral
didDiscoverCharacteristicsForService:(CBService *)service
             error:(NSError *)error {
    if (error) {
        printf("  error %s\n", error.localizedDescription.UTF8String);
    } else {
        for (CBCharacteristic *characteristic in service.characteristics) {
            self.characteristicCount += 1;
            if ([characteristic.UUID.UUIDString caseInsensitiveCompare:@"FFF4"] == NSOrderedSame) {
                self.notifyCharacteristic = characteristic;
            }
            if ([characteristic.UUID.UUIDString caseInsensitiveCompare:@"FFF5"] == NSOrderedSame) {
                self.writeCharacteristic = characteristic;
            }
            printf("  characteristic %s properties=%s\n",
                   characteristic.UUID.UUIDString.UTF8String,
                   PropertyLabels(characteristic.properties).UTF8String);
        }
    }
    self.pendingServices -= 1;
    if (!self.pendingServices) {
        if (self.controlTest || self.telemetryCapture || self.axisCapture || self.queryPosition || self.queryDegreeInfo) {
            if (!self.notifyCharacteristic || !self.writeCharacteristic) {
                [self finish:@"FFF4/FFF5 channel incomplete; no writes performed." code:EXIT_FAILURE];
                return;
            }
            printf("Subscribing to FFF4%s…\n", self.telemetryCapture ? " read-only" : " before the labeled test");
            fflush(stdout);
            [peripheral setNotifyValue:YES forCharacteristic:self.notifyCharacteristic];
            if (!self.telemetryCapture) {
                dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.0 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
                    if (self.queryPosition || self.queryDegreeInfo) {
                        uint8_t commandId = self.queryDegreeInfo ? 0x1e : 0x02;
                        printf("query=04:%02x payload=<empty>\n", commandId); fflush(stdout);
                        [self writeFrame:[self queryFrameCommandSet:0x04 commandId:commandId]];
                        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(3.0 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
                            [self finish:@"Position query capture complete; no motion command sent." code:EXIT_SUCCESS];
                        });
                    } else if (self.axisCapture) {
                        printf("phase=baseline axis=%s\n", self.axisCapture.UTF8String);
                        fflush(stdout);
                        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.0 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
                            [self beginCalibrationStage:1];
                        });
                    } else {
                        [self startControlTest];
                    }
                });
            }
            return;
        }
        [self finish:[NSString stringWithFormat:@"Discovery complete: %ld characteristics; no writes performed.",
                      (long)self.characteristicCount]
                  code:EXIT_SUCCESS];
    }
}

- (NSData *)queryFrameCommandSet:(uint8_t)commandSet commandId:(uint8_t)commandId {
    enum { total = 13 };
    uint8_t frame[total]; memset(frame, 0, sizeof(frame));
    frame[0] = 0x55; frame[1] = total; frame[2] = 0x04; frame[3] = DJI_CRC8(frame, 3);
    frame[4] = 0x02; frame[5] = 0x04;
    frame[6] = self.sequence & 0xff; frame[7] = self.sequence >> 8; self.sequence++;
    frame[8] = 0x40; frame[9] = commandSet; frame[10] = commandId;
    uint16_t crc = DJI_CRC16(frame, total - 2);
    frame[11] = crc & 0xff; frame[12] = crc >> 8;
    return [NSData dataWithBytes:frame length:total];
}

- (void)peripheral:(CBPeripheral *)peripheral
didUpdateNotificationStateForCharacteristic:(CBCharacteristic *)characteristic
             error:(NSError *)error {
    if (error) {
        printf("Notification subscription warning: %s\n", error.localizedDescription.UTF8String);
    } else {
        printf("Notifications %s on %s\n",
               characteristic.isNotifying ? "enabled" : "disabled",
               characteristic.UUID.UUIDString.UTF8String);
    }
    fflush(stdout);
    if (self.telemetryCapture && characteristic.isNotifying && !error) {
        printf("Capturing FFF4 notifications for %.1f seconds; no writes will be performed.\n", self.captureDuration);
        fflush(stdout);
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(self.captureDuration * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [self finish:@"Telemetry capture complete; no writes performed." code:EXIT_SUCCESS];
        });
    }
}

- (void)peripheral:(CBPeripheral *)peripheral
didUpdateValueForCharacteristic:(CBCharacteristic *)characteristic
             error:(NSError *)error {
    if (error) {
        printf("rx-error=%s\n", error.localizedDescription.UTF8String);
    } else if ([characteristic.UUID.UUIDString caseInsensitiveCompare:@"FFF4"] == NSOrderedSame) {
        printf("rx=%.6f %s\n", NSDate.date.timeIntervalSince1970, HexString(characteristic.value).UTF8String);
    }
    fflush(stdout);
}

- (NSData *)velocityFrameWithPan:(double)panNormalized tilt:(double)tiltNormalized roll:(double)rollNormalized {
    enum { total = 22 };
    uint8_t frame[total];
    memset(frame, 0, sizeof(frame));
    frame[0] = 0x55;
    frame[1] = total;
    frame[2] = 0x04;
    frame[3] = DJI_CRC8(frame, 3);
    frame[4] = 0x02; // app
    frame[5] = 0x04; // gimbal motor controller
    frame[6] = self.sequence & 0xff;
    frame[7] = (self.sequence >> 8) & 0xff;
    self.sequence = (uint16_t)(self.sequence + 1);
    frame[8] = 0x00; // fire-and-forget velocity frame
    frame[9] = 0x04;
    frame[10] = 0x01;

    int16_t tilt = (int16_t)lrint(1024.0 + fmax(-1.0, fmin(1.0, tiltNormalized)) * 660.0);
    int16_t roll = (int16_t)lrint(1024.0 + fmax(-1.0, fmin(1.0, rollNormalized)) * 660.0);
    int16_t pan = (int16_t)lrint(1024.0 + fmax(-1.0, fmin(1.0, panNormalized)) * 660.0);
    frame[11] = tilt & 0xff; frame[12] = (tilt >> 8) & 0xff;
    frame[13] = roll & 0xff; frame[14] = (roll >> 8) & 0xff;
    frame[15] = pan & 0xff;    frame[16] = (pan >> 8) & 0xff;
    frame[17] = 0x00; frame[18] = 0x00;
    frame[19] = 0x02; // virtual joystick source
    uint16_t crc = DJI_CRC16(frame, total - 2);
    frame[20] = crc & 0xff;
    frame[21] = (crc >> 8) & 0xff;
    return [NSData dataWithBytes:frame length:total];
}

- (NSData *)velocityFrameWithPan:(double)panNormalized {
    return [self velocityFrameWithPan:panNormalized tilt:0 roll:0];
}

- (void)beginCalibrationStage:(NSInteger)stage {
    self.calibrationStage = stage;
    if (stage == 1 || stage == 4) {
        self.calibrationFramesRemaining = 30;
        printf("phase=%s axis=%s\n", stage == 1 ? "positive" : "negative", self.axisCapture.UTF8String);
    } else {
        self.calibrationFramesRemaining = 3;
        printf("phase=stop axis=%s\n", self.axisCapture.UTF8String);
    }
    fflush(stdout);
    [self sendCalibrationTick];
}

- (void)sendCalibrationTick {
    BOOL moving = self.calibrationStage == 1 || self.calibrationStage == 4;
    double sign = self.calibrationStage == 1 ? 1.0 : -1.0;
    double pan = 0, tilt = 0, roll = 0;
    if (moving) {
        if ([self.axisCapture isEqualToString:@"pan"]) pan = 0.25 * sign;
        if ([self.axisCapture isEqualToString:@"tilt"]) tilt = 0.25 * sign;
        if ([self.axisCapture isEqualToString:@"roll"]) roll = 0.15 * sign;
    }
    [self writeFrame:[self velocityFrameWithPan:pan tilt:tilt roll:roll]];
    self.calibrationFramesRemaining -= 1;
    if (self.calibrationFramesRemaining > 0) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.067 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [self sendCalibrationTick];
        });
        return;
    }
    if (self.calibrationStage == 1) {
        [self beginCalibrationStage:2];
    } else if (self.calibrationStage == 2) {
        printf("phase=midpoint axis=%s\n", self.axisCapture.UTF8String); fflush(stdout);
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.0 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [self beginCalibrationStage:4];
        });
    } else if (self.calibrationStage == 4) {
        [self beginCalibrationStage:5];
    } else {
        printf("phase=settle axis=%s\n", self.axisCapture.UTF8String); fflush(stdout);
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2.0 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [self finish:@"Axis telemetry capture complete; stop sequence complete." code:EXIT_SUCCESS];
        });
    }
}

- (void)writeFrame:(NSData *)frame {
    printf("tx=%s\n", HexString(frame).UTF8String);
    fflush(stdout);
    const NSUInteger chunkSize = 20;
    for (NSUInteger offset = 0; offset < frame.length; offset += chunkSize) {
        NSRange range = NSMakeRange(offset, MIN(chunkSize, frame.length - offset));
        [self.selected writeValue:[frame subdataWithRange:range]
                forCharacteristic:self.writeCharacteristic
                             type:CBCharacteristicWriteWithoutResponse];
    }
}

- (void)startControlTest {
    if (self.controlTestStarted) return;
    self.controlTestStarted = YES;
    BOOL large = self.controlTest == 4 || self.controlTest == 5;
    self.movementFramesRemaining = self.controlTest == 1 ? 0 : (large ? 15 : 6);
    self.stopFramesRemaining = 3;
    const char *label = self.controlTest == 1 ? "neutral-only" :
                        self.controlTest == 2 ? "pan-right ~1.2 degrees" :
                        self.controlTest == 3 ? "pan-left ~1.2 degrees" :
                        self.controlTest == 4 ? "pan-right ~10 degrees" : "pan-left ~10 degrees";
    printf("Starting %s test; 3 stop frames are mandatory.\n", label);
    fflush(stdout);
    [self sendControlTick];
}

- (void)sendControlTick {
    if (self.selected.state != CBPeripheralStateConnected) {
        [self finish:@"BLE link dropped before stop frames completed." code:EXIT_FAILURE];
        return;
    }
    double pan = 0.0;
    if (self.movementFramesRemaining > 0) {
        BOOL large = self.controlTest == 4 || self.controlTest == 5;
        // Small: 3 deg/s; large: 10 deg/s. Full-scale pan is about 37.5 deg/s.
        double magnitude = large ? (10.0 / 37.5) : (3.0 / 37.5);
        BOOL right = self.controlTest == 2 || self.controlTest == 4;
        pan = right ? magnitude : -magnitude;
        self.movementFramesRemaining -= 1;
    } else if (self.stopFramesRemaining > 0) {
        self.stopFramesRemaining -= 1;
    }
    [self writeFrame:[self velocityFrameWithPan:pan]];

    if (self.movementFramesRemaining > 0 || self.stopFramesRemaining > 0) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.067 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [self sendControlTick];
        });
    } else {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.25 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            NSString *result = self.controlTest == 1
                ? @"Neutral control frames sent; stop sequence complete."
                : @"Low-speed pan test sent; stop sequence complete.";
            [self finish:result code:EXIT_SUCCESS];
        });
    }
}

- (void)finish:(NSString *)message code:(int)code {
    [self.central stopScan];
    if (self.selected.state == CBPeripheralStateConnected) {
        [self.central cancelPeripheralConnection:self.selected];
    }
    printf("%s\n", message.UTF8String);
    fflush(stdout);
    exit(code);
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        for (int index = 1; index + 1 < argc; index++) {
            if (strcmp(argv[index], "--output") == 0) {
                if (!freopen(argv[index + 1], "w", stdout)) return EXIT_FAILURE;
                if (!freopen(argv[index + 1], "a", stderr)) return EXIT_FAILURE;
                break;
            }
        }
        RSProbe *probe = [[RSProbe alloc] initWithArguments:NSProcessInfo.processInfo.arguments];
        [probe start];
        [[NSRunLoop mainRunLoop] run];
    }
    return EXIT_SUCCESS;
}
