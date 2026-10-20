#import "RSSDKActions.h"
#import "RSDeviceProtocol.h"
#import <math.h>
// A recording proxy, never a CBCentralManager or real RSGimbal instance.
@interface RecordingGimbal : NSProxy
@property(nonatomic) BOOL ready;
@property(nonatomic) BOOL busy;
@property(nonatomic,copy) NSString *appProfile;
@property(nonatomic,strong) NSMutableArray *calls;
@end
@implementation RecordingGimbal
- (NSMethodSignature *)methodSignatureForSelector:(SEL)selector { return [RSGimbal instanceMethodSignatureForSelector:selector]; }
- (void)forwardInvocation:(NSInvocation *)invocation {
    [self.calls addObject:NSStringFromSelector(invocation.selector)];
    for(NSUInteger i=2;i<invocation.methodSignature.numberOfArguments;i++)if(strcmp([invocation.methodSignature getArgumentTypeAtIndex:i],"@?")==0){
        __unsafe_unretained RSAppCompletion block;[invocation getArgument:&block atIndex:i];if(block)block(@{@"acknowledged":@YES,@"deviceVerified":@NO},nil);
    }
    if(invocation.methodSignature.methodReturnLength){void *zero=calloc(1,invocation.methodSignature.methodReturnLength);[invocation setReturnValue:zero];free(zero);}
}
@end
static NSUInteger assertions;
static void Check(BOOL yes,NSString *s){assertions++;if(!yes){fprintf(stderr,"FAIL: %s\n",s.UTF8String);exit(1);}}
static NSMutableDictionary *Samples(NSDictionary *op){NSMutableDictionary *d=[NSMutableDictionary dictionary];for(NSDictionary *f in op[@"fields"])d[f[@"key"]]=f[@"sample"]?:[f[@"choices"] firstObject]?:@"false";return d;}
int main(void){@autoreleasepool{
    RecordingGimbal *fake=[RecordingGimbal alloc];fake.ready=YES;fake.appProfile=@"ronin-2.2.2";fake.calls=[NSMutableArray array];
    NSMutableSet *ids=[NSMutableSet set],*selectors=[NSMutableSet set];
    for(NSDictionary *op in RSSDKOperations()){
        NSString *identifier=op[@"id"];Check(![ids containsObject:identifier],@"operation IDs unique");[ids addObject:identifier];
        NSError *err=nil;NSDictionary *form=RSSDKParseForm(identifier,Samples(op),&err);Check(form!=nil,[NSString stringWithFormat:@"%@ form: %@",identifier,err]);
        NSUInteger before=fake.calls.count;__block BOOL completed=NO;
        RSSDKDispatch((RSGimbal *)fake,identifier,Samples(op),3000,^(NSDictionary *reply,NSError *error){Check(!error&&[reply[@"acknowledged"] boolValue],@"dispatch returns actual completion");completed=YES;});
        Check(completed&&fake.calls.count==before+1,[identifier stringByAppendingString:@" invokes exactly one public SDK method"]);[selectors addObject:fake.calls.lastObject];
        NSMutableDictionary *bad=Samples(op);bad[@"arbitraryFrame"]=@"55";Check(!RSSDKParseForm(identifier,bad,nil),@"no arbitrary GUI command fields");
        if([op[@"fields"] count]){NSDictionary *field=[op[@"fields"] firstObject];bad=Samples(op);bad[field[@"key"]]=@"NaN / unknown";Check(!RSSDKParseForm(identifier,bad,nil),@"malformed GUI fields rejected");}
    }
    Check(ids.count==32&&selectors.count==32,@"32 GUI actions map to 32 distinct public methods");
    NSDictionary *bools=RSSDKParseForm(@"smooth.write",@{@"axes.yaw":@"false"},nil);Check(CFGetTypeID((__bridge CFTypeRef)bools[@"axes"][@"yaw"])==CFBooleanGetTypeID(),@"false is genuine boolean, preserved in nested axis patch");
    Check([bools[@"axes"] count]==1,@"unspecified axes omitted");
    Check(!RSSDKParseForm(@"smooth.write",@{},nil),@"empty patch rejected before SDK");
    Check(!RSSDKParseForm(@"Motor.write",@{},nil),@"empty motor patch rejected");
    Check(!RSSDKParseForm(@"rc.tuning.write",@{@"axis":@"pitch",@"parameter":@"smoothing",@"value":@"31"},nil),@"source parameter-specific limits reused");
    Check(!RSSDKParseForm(@"follow.tuning.write",@{@"axis":@"pitch",@"parameter":@"speed",@"value":@"0"},nil),@"source speed minimum reused");
    Check(!RSSDKParseForm(@"motorTuning.write",@{@"axis":@"pitch",@"parameter":@"stiffness",@"value":@"4"},nil),@"source motor minimum reused");
    Check(!RSSDKParseForm(@"motorTuning.read",@{},nil),@"GUI motor form retains explicit selectors; SDK batch available programmatically");
    Check(!RSSDKParseForm(@"motorTuning.read",@{@"axis":@"pitch"},nil),@"motor read requires both source selectors");
    Check(RSSDKParseForm(@"motorTuning.read",@{@"axis":@"pitch",@"parameter":@"stiffness"},nil)!=nil,@"single motor read remains available through public SDK");
    Check(!RSSDKParseForm(@"parameter.subscribe",@{@"keys":@"MotorEnabled,MotorEnabled"},nil),@"duplicate subscriptions rejected");
    Check(!RSSDKParseForm(@"parameter.subscribe",@{@"keys":@"NotAKnownKey"},nil),@"unknown subscription key rejected");
    Check(!RSSDKParseForm(@"raw.read",@{@"index":@"1.2",@"size":@"1"},nil),@"fractional integer rejected");
    Check(!RSSDKParseForm(@"fine.write",@{@"axis":@"roll",@"adjustmentDegrees":@"nan"},nil),@"nonfinite rejected");
    for(NSString *mode in @[@"disconnected",@"busy",@"profile"]){fake.ready=![mode isEqual:@"disconnected"];fake.busy=[mode isEqual:@"busy"];fake.appProfile=[mode isEqual:@"profile"]?nil:@"ronin-2.2.2";NSUInteger before=fake.calls.count;__block BOOL failed=NO;RSSDKDispatch((id)fake,@"sensitivity.read",@{},3000,^(NSDictionary *reply,NSError *err){failed=err!=nil;});Check(failed&&fake.calls.count==before,@"lifecycle/source gate prevents SDK invocation");}
    fake.ready=YES;fake.busy=NO;fake.appProfile=@"ronin-2.2.2";
    for(NSNumber *timeout in @[@0,@60001,@(NAN)]){NSUInteger before=fake.calls.count;__block BOOL failed=NO;RSSDKDispatch((id)fake,@"handle.read",@{},timeout.doubleValue,^(NSDictionary *reply,NSError *error){failed=error!=nil;});Check(failed&&fake.calls.count==before,@"invalid timeout does not call SDK");}
    __block BOOL rejected=NO;NSUInteger before=fake.calls.count;RSSDKDispatch((id)fake,@"not-allowed",@{},3000,^(NSDictionary *reply,NSError *error){rejected=error!=nil;});Check(rejected&&fake.calls.count==before,@"unknown operation never dispatches");
    NSDictionary *snapshot=RSSDKStatusSnapshot((id)fake);Check(snapshot.count==4&&snapshot[@"sensorCalibration"]==NSNull.null,@"missing passive states remain null, not zero or success");
    NSString *json=RSSDKDisplay(@{@"body":[NSData dataWithBytes:(uint8_t[]){0,255} length:2],@"verified":@NO});Check([json containsString:@"00ff"]&&[json containsString:@"false"],@"binary response and evidence flags preserved for display");
    printf("Native SDK GUI adapter: %lu checks passed (no UI, no Bluetooth manager)\n",(unsigned long)assertions);
}return 0;}
