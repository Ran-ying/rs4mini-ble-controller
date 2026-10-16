#import <Foundation/Foundation.h>
#import <CoreBluetooth/CoreBluetooth.h>
typedef void (^StatusHandler)(NSString *text, BOOL ready);
typedef void (^TelemetryHandler)(NSDictionary *sample);
typedef void (^RSAppCompletion)(NSDictionary *result, NSError *error);
// Device layer: independent of RSGimbal and composed motion.
@interface RSBleDevice : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@property(nonatomic, readonly) BOOL ready;
@property(nonatomic, readonly) BOOL connecting;
@property(nonatomic, readonly) BOOL busy;
@property(nonatomic, copy) TelemetryHandler telemetryHandler;
@property(nonatomic) BOOL autoReconnectEnabled;
@property(nonatomic, readonly) NSUInteger reconnectAttempt;
@property(nonatomic, readonly) NSDictionary *experimentalStatus;
@property(nonatomic, copy) TelemetryHandler experimentalStatusHandler;
- (instancetype)initWithStatus:(StatusHandler)handler;
- (instancetype)initWithStatus:(StatusHandler)handler central:(CBCentralManager *)central;
- (void)requestDegreeInfo;
@property(nonatomic, readonly, copy) NSString *appProfile;
- (BOOL)useAppProfile:(NSString *)profile;
- (void)readAppParameters:(NSArray<NSDictionary *> *)parameters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getFollowSensitivityWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setFollowSensitivity:(NSNumber *)mode timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
@property(nonatomic, copy) TelemetryHandler messageHandler;
- (void)connect;
- (void)disconnect;
- (void)drivePan:(double)pan tilt:(double)tilt roll:(double)roll;
- (void)stop;
- (void)recenter;
@end
