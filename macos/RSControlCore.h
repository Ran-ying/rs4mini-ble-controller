#import <Foundation/Foundation.h>

NSData *RSVelocityFrame(uint16_t sequence, double pan, double tilt, double roll);
NSData *RSRecenterFrame(uint16_t sequence);
NSDictionary *RSDecodeTelemetry(NSData *payload);
NSDictionary *RSOrientation(NSArray *components, NSString *order, BOOL conjugate);
NSData *RSResearchAbsoluteFrame(uint16_t sequence, NSDictionary *targets, NSUInteger parameter);
NSData *RSResearchRateFrame(uint16_t sequence, NSDictionary *rates, BOOL release);
NSData *RSResearchSleepFrame(uint16_t sequence, NSString *profile, BOOL asleep);
NSData *RSResearchQueryFrame(uint16_t sequence, NSString *kind);
NSDictionary *RSDecodeResearchStatus(NSDictionary *message, NSString *profile);

@interface RSFrameDecoder : NSObject
@property(nonatomic, readonly) NSUInteger invalidFrames;
@property(nonatomic, readonly) NSUInteger discardedBytes;
- (NSArray<NSDictionary *> *)push:(NSData *)data;
- (void)reset;
@end

// A frame already started is completed before stop frames; queued motion is discarded.
@interface RSFrameQueue : NSObject
@property(nonatomic, readonly) BOOL empty;
- (void)enqueue:(NSData *)frame;
- (NSData *)nextChunk;
- (void)discardPending;
- (void)reset;
@end

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
