// Optional offscreen AppKit layout check; never creates a Bluetooth manager.
#import <AppKit/AppKit.h>
#import "RSSDKPanel.h"
@interface RSSDKPanel (LayoutTest)
- (void)groupChanged:(id)sender;
- (void)operationChanged:(id)sender;
@end
@interface OfflineGimbal : NSProxy
@end
@implementation OfflineGimbal
- (BOOL)ready{return NO;}- (BOOL)busy{return NO;}- (NSString *)appProfile{return nil;}
- (NSMethodSignature *)methodSignatureForSelector:(SEL)s{return [RSGimbal instanceMethodSignatureForSelector:s];}
- (void)forwardInvocation:(NSInvocation *)i {if(i.methodSignature.methodReturnLength){void *z=calloc(1,i.methodSignature.methodReturnLength);[i setReturnValue:z];free(z);}}
@end
int main(){@autoreleasepool{[NSApplication sharedApplication];OfflineGimbal *g=[OfflineGimbal alloc];RSSDKPanel *p=[[RSSDKPanel alloc]initWithFrame:NSMakeRect(0,0,650,820) gimbal:(id)g];NSWindow *w=[[NSWindow alloc]initWithContentRect:p.frame styleMask:0 backing:NSBackingStoreBuffered defer:NO];w.contentView=p;NSPopUpButton *groups=[p valueForKey:@"group"],*operations=[p valueForKey:@"operation"];NSUInteger checked=0;for(NSInteger i=0;i<groups.numberOfItems;i++){[groups selectItemAtIndex:i];[p groupChanged:nil];for(NSInteger j=0;j<operations.numberOfItems;j++){[operations selectItemAtIndex:j];[p operationChanged:nil];[p layoutSubtreeIfNeeded];NSView *form=[p valueForKey:@"form"],*tabs=[p valueForKey:@"tabs"];NSRect fr=[form convertRect:form.bounds toView:p],tr=[tabs convertRect:tabs.bounds toView:p];if(NSMinY(tr)<0||NSMaxY(fr)>820||NSHeight(tr)<140){fprintf(stderr,"Layout overflow: %s\n",operations.titleOfSelectedItem.UTF8String);return 1;}checked++;}}printf("Offline AppKit form layout: %lu operations fit 650x820; no Bluetooth manager.\n",(unsigned long)checked);}return 0;}
