#import <AppKit/AppKit.h>

@interface RSHoldButton : NSButton
@property(nonatomic, copy) void (^onPress)(void);
@property(nonatomic, copy) void (^onRelease)(void);
- (NSRect)titleDrawingRect;
@end

// Local keyboard state only; never owns a Bluetooth connection.
@interface RSArrowKeys : NSObject
@property(nonatomic, copy) void (^drive)(double pan, double tilt);
@property(nonatomic, copy) void (^stop)(void);
@property(nonatomic, readonly) BOOL active;
- (BOOL)keyCode:(unsigned short)code down:(BOOL)down repeat:(BOOL)repeat allowed:(BOOL)allowed;
- (void)reset;
@end
BOOL RSArrowFocusAllowsControl(NSResponder *responder);
