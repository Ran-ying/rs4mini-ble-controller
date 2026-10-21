// Optional offscreen AppKit layout check; never creates a Bluetooth manager.
#import <AppKit/AppKit.h>
#import "RSSDKPanel.h"
#import "RSManualControls.h"
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
static void RequireViewport(NSScrollView *scroll, NSString *phase) {
    NSView *panel=scroll.documentView;
    NSRect visible=[panel convertRect:panel.bounds toView:scroll.contentView];
    NSRect clip=scroll.contentView.bounds;
    if(fabs(NSMinX(panel.frame))>0.5 || fabs(NSMinX(visible)-NSMinX(clip))>0.5 || fabs(NSWidth(visible)-NSWidth(clip))>0.5) {
        fprintf(stderr,"Horizontal viewport overflow (%s): document %s, visible %s, clip %s\n",phase.UTF8String,NSStringFromRect(panel.frame).UTF8String,NSStringFromRect(visible).UTF8String,NSStringFromRect(clip).UTF8String);exit(1);
    }
}
int main(){@autoreleasepool{
    [NSApplication sharedApplication];
    for(NSString *title in @[@"↑",@"↓",@"←",@"→",@"↺ Roll",@"Roll ↻"]) {
        RSHoldButton *button=[[RSHoldButton alloc]initWithFrame:NSMakeRect(0,0,[title containsString:@"Roll"]?120:80,[title containsString:@"Roll"]?46:54)];
        button.title=title;button.font=[NSFont systemFontOfSize:[title containsString:@"Roll"]?15:25 weight:NSFontWeightSemibold];
        NSRect text=[button titleDrawingRect];
        if(!NSContainsRect(NSInsetRect(button.bounds,1,1),text)){fprintf(stderr,"Direction title outside border\n");return 1;}
        [button cacheDisplayInRect:button.bounds toBitmapImageRep:[button bitmapImageRepForCachingDisplayInRect:button.bounds]];
    }
    if(RSArrowFocusAllowsControl([NSTextView new])||RSArrowFocusAllowsControl([NSTextField new])||RSArrowFocusAllowsControl([NSPopUpButton new])||RSArrowFocusAllowsControl([NSSlider new])||!RSArrowFocusAllowsControl([NSButton new])){fprintf(stderr,"Keyboard editor/control focus gate failed\n");return 1;}
    OfflineGimbal *g=[OfflineGimbal alloc];NSUInteger checked=0;
    for(NSNumber *height in @[@820,@600]) {
        NSWindow *w=[[NSWindow alloc]initWithContentRect:NSMakeRect(0,0,1080,height.doubleValue) styleMask:0 backing:NSBackingStoreBuffered defer:NO];
        NSScrollView *scroll=[RSSDKPanel scrollViewWithFrame:NSMakeRect(430,0,650,height.doubleValue) gimbal:(id)g];
        [w.contentView addSubview:scroll];
        // Check the production host before any user scrolling or event-loop correction.
        RequireViewport(scroll,@"initial attachment");
        RSSDKPanel *p=(RSSDKPanel *)scroll.documentView;
        NSPopUpButton *groups=[p valueForKey:@"group"],*operations=[p valueForKey:@"operation"];
        for(NSInteger i=0;i<groups.numberOfItems;i++) {
            [groups selectItemAtIndex:i];[p groupChanged:nil];
            for(NSInteger j=0;j<operations.numberOfItems;j++) {
                [operations selectItemAtIndex:j];[p operationChanged:nil];[p layoutSubtreeIfNeeded];
                NSView *form=[p valueForKey:@"form"],*tabs=[p valueForKey:@"tabs"];
                NSRect fr=[form convertRect:form.bounds toView:p],tr=[tabs convertRect:tabs.bounds toView:p];
                if(NSMinY(tr)<0||NSMaxY(fr)>820||NSHeight(tr)<140){fprintf(stderr,"Layout overflow: %s\n",operations.titleOfSelectedItem.UTF8String);return 1;}
                for(NSView *item in ((NSStackView *)p.subviews.firstObject).arrangedSubviews) {
                    NSRect itemRect=[item convertRect:item.bounds toView:p];
                    if(NSMinX(itemRect)<-0.5||NSMaxX(itemRect)>NSWidth(p.bounds)+0.5){fprintf(stderr,"Horizontal control overflow: %s\n",operations.titleOfSelectedItem.UTF8String);return 1;}
                }
                RequireViewport(scroll,@"operation selection");checked++;
            }
        }
        [scroll.contentView scrollToPoint:NSZeroPoint];[scroll reflectScrolledClipView:scroll.contentView];RequireViewport(scroll,@"scrolled bottom");
        [scroll.contentView scrollToPoint:NSMakePoint(0,MAX(0,820-scroll.contentSize.height))];[scroll reflectScrolledClipView:scroll.contentView];RequireViewport(scroll,@"scrolled top");
    }
    printf("Offline AppKit layout: %lu operation/viewport combinations; initial attachment and scrolling fit; no Bluetooth manager.\n",(unsigned long)checked);
}return 0;}
