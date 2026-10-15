#import "RSBleDevice.h"
// Single application entry.
@interface RSGimbal : RSBleDevice
@property(nonatomic, readonly) NSDictionary *home;
- (void)moveTo:(NSDictionary *)targets;
- (void)runTrajectory:(NSArray *)keyframes interpolation:(NSString *)interpolation;
- (void)moveThrough:(NSArray *)waypoints;
- (void)captureHome;
- (void)moveHomeAxes:(NSArray<NSString *> *)axes;
- (NSDictionary *)orientationWithOrder:(NSString *)order conjugate:(BOOL)conjugate;
// Explicit other-model research profile in the command dictionary; never auto-enabled.
- (void)sendExperimentalCommand:(NSDictionary *)command;
@end
