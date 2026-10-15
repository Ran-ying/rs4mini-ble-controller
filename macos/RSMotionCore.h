#import <Foundation/Foundation.h>
NSDictionary *RSOrientation(NSArray *components, NSString *order, BOOL conjugate);

@interface RSPositionLoop : NSObject
@property(nonatomic, readonly) BOOL active;
@property(nonatomic, readonly) NSDictionary *velocity;
@property(nonatomic, readonly) NSDictionary *current;
- (BOOL)begin:(NSDictionary *)targets at:(NSTimeInterval)now error:(NSError **)error;
- (void)feedback:(NSDictionary *)joints at:(NSTimeInterval)now;
// waiting, moving, arrived, timeout, telemetryTimeout, idle
- (NSString *)step:(NSTimeInterval)now;
- (void)cancel;
@end

@interface RSTrajectoryLoop : NSObject
@property(nonatomic, readonly) BOOL active;
@property(nonatomic, readonly) NSDictionary *velocity;
- (BOOL)begin:(NSArray *)keyframes interpolation:(NSString *)interpolation at:(NSTimeInterval)now error:(NSError **)error;
// moving, done, overrun, idle; default scheduler lag bound 500 ms.
- (NSString *)step:(NSTimeInterval)now;
- (void)cancel;
@end
