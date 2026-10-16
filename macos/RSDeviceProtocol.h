#import <Foundation/Foundation.h>

NSData *RSVelocityFrame(uint16_t sequence, double pan, double tilt, double roll);
NSData *RSRecenterFrame(uint16_t sequence);
NSDictionary *RSDecodeTelemetry(NSData *payload);
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

// Current-App parameter codecs; source-proven, hardware unverified.
NSArray<NSDictionary *> *RSAppParameterContext(NSArray *parameters);
NSData *RSAppParameterRequestFrame(uint16_t sequence, NSArray *parameters);
NSData *RSAppSensitivityFrame(uint16_t sequence, NSNumber *mode);
NSError *RSAppError(NSString *code, NSString *message, NSNumber *statusCode);
NSDictionary *RSDecodeAppReply(NSDictionary *message, uint8_t command, NSArray *parameters, NSError **error);
// Named current-App settings; only these groups/boolean fields may be written.
NSDictionary *RSAppSettingsSchema(NSString *kind);
NSDictionary *RSAppSettingsPatch(NSString *kind, NSDictionary *patch);
NSDictionary *RSDecodeAppSettings(NSDictionary *reply, NSString *kind);
NSData *RSAppSettingsFrame(uint16_t sequence, NSString *kind, NSDictionary *patch, NSNumber *currentValue);
NSData *RSAppAutoTuneFrame(uint16_t sequence, NSNumber *start);
NSData *RSAppCalibrationQueryFrame(uint16_t sequence);
NSDictionary *RSDecodeAppCalibrationRecords(NSData *body);
NSDictionary *RSDecodeAppCalibrationReply(NSDictionary *message, NSError **error);
NSDictionary *RSDecodeAppCalibrationNotification(NSDictionary *message);
NSArray<NSDictionary *> *RSAppMotorSelection(NSDictionary *filters);
NSDictionary *RSAppMotorWriteSpec(NSDictionary *spec);
NSData *RSAppMotorReadFrame(uint16_t sequence, NSArray *context);
NSData *RSAppMotorWriteFrame(uint16_t sequence, NSArray *context, NSNumber *value);
NSDictionary *RSDecodeAppMotorReply(NSDictionary *message, NSArray *selection, NSError **error);

NSData *RSAppBalanceStartFrame(uint16_t sequence);
NSDictionary *RSAppBalanceFields(uint8_t rawValue);
NSDictionary *RSDecodeAppBalanceReply(NSDictionary *reply);

NSData *RSAppSystemCalibrationStartFrame(uint16_t sequence);
NSDictionary *RSAppSystemCalibrationFields(uint8_t rawValue);
NSDictionary *RSDecodeAppSystemCalibrationReply(NSDictionary *reply);

NSString *RSAppModeKind(NSString *domain, NSString *parameter);
