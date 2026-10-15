#import "RSBleDevice.h"
@interface OfflineCentral : NSObject
@property(nonatomic) CBManagerState state;
@end
@implementation OfflineCentral
- (void)stopScan {}
@end
int main(void) {
    @autoreleasepool {
        OfflineCentral *central = [OfflineCentral new]; central.state = CBManagerStatePoweredOff;
        __block BOOL statusReceived = NO;
        RSBleDevice *device = [[RSBleDevice alloc] initWithStatus:^(NSString *text, BOOL ready) { statusReceived = text.length > 0 && !ready; } central:(id)central];
        if (NSClassFromString(@"RSGimbal") || NSClassFromString(@"RSPositionLoop") || NSClassFromString(@"RSTrajectoryLoop")) return 1;
        if ([device respondsToSelector:NSSelectorFromString(@"moveTo:")]) return 2;
        [device connect];
        if (device.ready || device.connecting || !statusReceived) return 3;
        [device stop]; [device disconnect];
        puts("Native standalone BLE SDK: 3 checks passed (no motion linked, no Bluetooth manager created)");
    }
    return 0;
}
