#import <Foundation/Foundation.h>
#import <CoreBluetooth/CoreBluetooth.h>
typedef void (^StatusHandler)(NSString *text, BOOL ready);
typedef void (^TelemetryHandler)(NSDictionary *sample);
@interface RSGimbal : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@property(nonatomic, readonly) BOOL ready;
@property(nonatomic, readonly) BOOL connecting;
@property(nonatomic, readonly) BOOL busy;
@property(nonatomic, copy) TelemetryHandler telemetryHandler;
@property(nonatomic) BOOL autoReconnectEnabled;
@property(nonatomic, readonly) NSUInteger reconnectAttempt;
@property(nonatomic, readonly) NSDictionary *home;
@property(nonatomic, readonly) NSDictionary *experimentalStatus;
@property(nonatomic, copy) TelemetryHandler experimentalStatusHandler;
- (instancetype)initWithStatus:(StatusHandler)handler;
// Dependency injection for offline lifecycle tests. nil uses CoreBluetooth.
- (instancetype)initWithStatus:(StatusHandler)handler central:(CBCentralManager *)central;
- (void)connect;
- (void)disconnect;
- (void)drivePan:(double)pan tilt:(double)tilt roll:(double)roll;
- (void)moveTo:(NSDictionary *)targets;
- (void)runTrajectory:(NSArray *)keyframes interpolation:(NSString *)interpolation;
- (void)moveThrough:(NSArray *)waypoints;
- (void)captureHome;
- (void)moveHomeAxes:(NSArray<NSString *> *)axes;
- (NSDictionary *)orientationWithOrder:(NSString *)order conjugate:(BOOL)conjugate;
// Explicit other-model research profile in the command dictionary; never auto-enabled.
- (void)sendExperimentalCommand:(NSDictionary *)command;
- (void)stop;
- (void)recenter;
@end
