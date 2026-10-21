#import <AppKit/AppKit.h>
#import "RSGimbal.h"
@interface RSSDKPanel : NSView
+ (NSScrollView *)scrollViewWithFrame:(NSRect)frame gimbal:(RSGimbal *)gimbal;
- (instancetype)initWithFrame:(NSRect)frame gimbal:(RSGimbal *)gimbal;
- (void)refresh;
- (void)receiveMessage:(NSDictionary *)message;
- (void)receiveStatus:(NSDictionary *)status;
@end
