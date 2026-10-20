#import "RSGimbal.h"
// Named GUI adapter only: calls the public application facade, never encodes packets.
NSArray<NSDictionary *> *RSSDKOperations(void);
NSDictionary *RSSDKOperation(NSString *identifier);
NSDictionary *RSSDKParseForm(NSString *identifier, NSDictionary<NSString *, NSString *> *strings, NSError **error);
void RSSDKDispatch(RSGimbal *gimbal, NSString *identifier, NSDictionary *strings, double timeoutMs, RSAppCompletion completion);
NSDictionary *RSSDKStatusSnapshot(RSGimbal *gimbal);
NSString *RSSDKDisplay(id value);
