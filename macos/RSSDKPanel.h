#import <AppKit/AppKit.h>
#import "RSGimbal.h"
@interface RSSDKPanel : NSView
- (instancetype)initWithFrame:(NSRect)frame gimbal:(RSGimbal *)gimbal;
- (void)refresh;
- (void)receiveMessage:(NSDictionary *)message;
- (void)receiveStatus:(NSDictionary *)status;
@end
