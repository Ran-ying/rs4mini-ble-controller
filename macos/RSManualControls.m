#import "RSManualControls.h"

@implementation RSHoldButton
- (NSRect)titleDrawingRect { return NSInsetRect(self.bounds,8,6); }
- (void)drawRect:(NSRect)dirtyRect {
    NSRect border=NSInsetRect(self.bounds,1,1);
    NSBezierPath *path=[NSBezierPath bezierPathWithRoundedRect:border xRadius:8 yRadius:8];
    [(self.highlighted?NSColor.controlAccentColor:NSColor.controlBackgroundColor) setFill];[path fill];
    [NSColor.separatorColor setStroke];path.lineWidth=1;[path stroke];
    NSRect inner=[self titleDrawingRect];NSFont *font=self.font?:[NSFont systemFontOfSize:22];
    NSMutableDictionary *attributes=[@{NSFontAttributeName:font,NSForegroundColorAttributeName:self.enabled?NSColor.labelColor:NSColor.disabledControlTextColor} mutableCopy];
    NSSize size=[self.title sizeWithAttributes:attributes];
    while((size.width>inner.size.width||size.height>inner.size.height)&&font.pointSize>8){font=[NSFont systemFontOfSize:font.pointSize-1 weight:NSFontWeightSemibold];attributes[NSFontAttributeName]=font;size=[self.title sizeWithAttributes:attributes];}
    NSRect rect=NSMakeRect(NSMidX(inner)-size.width/2,NSMidY(inner)-size.height/2,size.width,size.height);
    [NSGraphicsContext saveGraphicsState];NSRectClip(inner);[self.title drawInRect:rect withAttributes:attributes];[NSGraphicsContext restoreGraphicsState];
}
- (void)mouseDown:(NSEvent *)event {
    if(!self.enabled)return;
    if(self.onPress)self.onPress();
    @try { [super mouseDown:event]; } @finally { if(self.onRelease)self.onRelease(); }
}
@end

@interface RSArrowKeys ()
@property(nonatomic,strong) NSMutableIndexSet *pressed;
@end
@implementation RSArrowKeys
- (instancetype)init { if((self=[super init]))_pressed=[NSMutableIndexSet indexSet];return self; }
- (BOOL)active { return self.pressed.count>0; }
- (void)reset { BOOL wasActive=self.active;[self.pressed removeAllIndexes];if(wasActive&&self.stop)self.stop(); }
- (BOOL)keyCode:(unsigned short)code down:(BOOL)down repeat:(BOOL)repeat allowed:(BOOL)allowed {
    if(code<123||code>126)return NO;
    BOOL held=[self.pressed containsIndex:code];
    if(!allowed){[self reset];return held;}
    if(down){
        // A held key must be released and pressed again after stop/focus/connection loss.
        if(repeat||held)return held||repeat;
        [self.pressed addIndex:code];
    }else{
        if(!held)return NO;
        [self.pressed removeIndex:code];
    }
    double pan=([self.pressed containsIndex:124]?1:0)-([self.pressed containsIndex:123]?1:0);
    double tilt=([self.pressed containsIndex:126]?1:0)-([self.pressed containsIndex:125]?1:0);
    if(pan==0&&tilt==0){if(self.stop)self.stop();}
    else if(self.drive)self.drive(pan,tilt);
    return YES;
}
@end
BOOL RSArrowFocusAllowsControl(NSResponder *responder) {
    return ![responder isKindOfClass:NSTextView.class]&&![responder isKindOfClass:NSTextField.class]&&![responder isKindOfClass:NSPopUpButton.class]&&![responder isKindOfClass:NSSlider.class]&&![responder isKindOfClass:NSStepper.class];
}
