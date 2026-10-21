#import "RSManualControls.h"
static NSUInteger checks;
static void Require(BOOL ok,NSString *why){checks++;if(!ok){fprintf(stderr,"FAIL: %s\n",why.UTF8String);exit(1);}}
int main(){@autoreleasepool{
    RSArrowKeys *keys=[RSArrowKeys new];__block double pan=0,tilt=0;__block NSUInteger drives=0,stops=0;
    keys.drive=^(double p,double t){pan=p;tilt=t;drives++;};keys.stop=^{pan=tilt=0;stops++;};
    NSArray *codes=@[@123,@124,@125,@126];NSArray *pans=@[@-1,@1,@0,@0],*tilts=@[@0,@0,@-1,@1];
    for(NSUInteger i=0;i<codes.count;i++){
        unsigned short code=[codes[i] unsignedShortValue];
        Require([keys keyCode:code down:YES repeat:NO allowed:YES],@"arrow keydown consumed");
        Require(pan==[pans[i] doubleValue]&&tilt==[tilts[i] doubleValue]&&keys.active,@"correct pan/tilt sign");
        NSUInteger previous=drives;
        Require([keys keyCode:code down:YES repeat:YES allowed:YES]&&drives==previous,@"repeat does not resend or restart");
        Require([keys keyCode:code down:NO repeat:NO allowed:YES]&&!keys.active&&pan==0&&tilt==0,@"keyup stops");
        Require(![keys keyCode:code down:NO repeat:NO allowed:YES],@"unowned keyup passes through");
    }
    [keys keyCode:126 down:YES repeat:NO allowed:YES];[keys keyCode:124 down:YES repeat:NO allowed:YES];
    Require(pan==1&&tilt==1,@"two axes can be held together");
    [keys keyCode:126 down:NO repeat:NO allowed:YES];Require(pan==1&&tilt==0,@"release one axis preserves remaining held direction");
    [keys keyCode:123 down:YES repeat:NO allowed:YES];Require(pan==0&&tilt==0,@"opposite directions cancel");
    [keys keyCode:123 down:NO repeat:NO allowed:YES];Require(pan==1&&tilt==0,@"opposite release recomputes remaining direction");
    NSUInteger previous=stops;[keys reset];Require(!keys.active&&stops==previous+1,@"focus/stop/disconnect clears held keys and stops");
    [keys reset];Require(stops==previous+1,@"idle reset does not emit extra stops");
    previous=drives;[keys keyCode:124 down:YES repeat:YES allowed:YES];Require(!keys.active&&drives==previous,@"held repeat cannot restart after reset/reconnect");
    Require(![keys keyCode:126 down:YES repeat:NO allowed:NO]&&!keys.active,@"editing/unready/busy keydown passes through");
    [keys keyCode:126 down:YES repeat:NO allowed:YES];previous=stops;
    Require([keys keyCode:126 down:NO repeat:NO allowed:NO]&&!keys.active&&stops==previous+1,@"keyup during context change clears ownership and stops");
    Require(![keys keyCode:0 down:YES repeat:NO allowed:YES],@"unrelated key passes through");
    Require(RSArrowFocusAllowsControl(nil),@"no editor allows control");
    printf("Native manual keyboard controls: %lu checks passed (no UI or Bluetooth manager).\n",(unsigned long)checks);
}return 0;}
