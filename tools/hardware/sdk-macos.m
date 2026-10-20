// Headless real-device test: public device SDK only, no AppKit or RSGimbal.
#import <Foundation/Foundation.h>
#import "RSBleDevice.h"
static NSMutableArray *rows;
static BOOL Wait(BOOL (^condition)(void), double seconds) {
    NSTimeInterval end=NSProcessInfo.processInfo.systemUptime+seconds;
    while(!condition() && NSProcessInfo.processInfo.systemUptime<end)
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:.02]];
    return condition();
}
static void Row(NSString *name, BOOL ok, id value) {
    NSMutableDictionary *r=[@{@"name":name,@"ok":@(ok)} mutableCopy];
    if(value)r[@"value"]=value;[rows addObject:r];
}
static NSDictionary *Check(NSString *name, void (^start)(RSAppCompletion)) {
    __block BOOL done=NO;__block NSError *failure=nil;__block NSDictionary *result=nil;
    start(^(NSDictionary *r,NSError *e){result=r;failure=e;done=YES;});
    BOOL completed=Wait(^BOOL{return done;},7);
    NSMutableDictionary *safe=[NSMutableDictionary dictionary];
    for(NSString *key in @[@"rawValue",@"mode",@"sourceMode",@"sourceProfile",@"sourceWorkMode",@"inputSource",@"values",@"settings"])
        if(result[key])safe[key]=result[key];
    if(failure)safe[@"code"]=failure.userInfo[@"code"]?:failure.domain;
    if(!completed)safe[@"code"]=@"HARNESS_DEADLINE";
    Row(name,completed&&!failure&&result!=nil,safe);
    return completed&&!failure?result:nil;
}
int main(int argc,const char *argv[]) {
 @autoreleasepool {
    if(argc>1 && strcmp(argv[1],"--help")==0){puts("RS4MINI_SDK_TEST=yes tools/hardware/sdk-macos.sh --run");return 0;}
    if(![NSProcessInfo.processInfo.environment[@"RS4MINI_SDK_TEST"] isEqual:@"yes"]){fputs("Explicit SDK test opt-in required\n",stderr);return 2;}
    rows=[NSMutableArray array];__block BOOL powered=NO;__block NSUInteger samples=0;__block NSDictionary *sample=nil;__block BOOL degree=NO;
    RSBleDevice *g=[[RSBleDevice alloc] initWithStatus:^(NSString *text,BOOL ready){if([text containsString:@"蓝牙就绪"])powered=YES;}];
    g.telemetryHandler=^(NSDictionary *s){if(s[@"jointAngles"]){samples++;sample=s;}};
    g.messageHandler=^(NSDictionary *m){if([m[@"sender"] intValue]==4&&[m[@"receiver"] intValue]==2&&[m[@"commandSet"] intValue]==4&&[m[@"commandId"] intValue]==30&&([m[@"flags"] intValue]&128))degree=YES;};
    Row(@"deviceLayerOnly",NSClassFromString(@"RSGimbal")==nil&&![g respondsToSelector:NSSelectorFromString(@"moveTo:")],nil);
    BOOL power=Wait(^BOOL{return powered;},10);Row(@"bluetoothReady",power,nil);
    if(power){[g connect];BOOL linked=Wait(^BOOL{return g.ready;},32);Row(@"connect",linked,nil);
     if(linked){
      BOOL fresh=Wait(^BOOL{return samples>=2;},5);Row(@"attitude",fresh&&sample[@"attitude"]!=nil,sample[@"attitude"]);Row(@"joints",fresh&&sample[@"jointAngles"]!=nil,sample[@"jointAngles"]);
      Row(@"profile",[g useAppProfile:@"ronin-2.2.2"],nil);
      NSDictionary *sensitivity=Check(@"getFollowSensitivity",^(RSAppCompletion c){[g getFollowSensitivityWithTimeoutMs:3000 completion:c];});
      Check(@"getMotorSettings",^(RSAppCompletion c){[g getMotorSettingsWithTimeoutMs:3000 completion:c];});
      Check(@"getCustomFollowSettings",^(RSAppCompletion c){[g getCustomFollowSettingsWithTimeoutMs:3000 completion:c];});
      Check(@"getAxisMode",^(RSAppCompletion c){[g getAxisModeWithTimeoutMs:3000 completion:c];});
      Check(@"getUserProfile",^(RSAppCompletion c){[g getUserProfileWithTimeoutMs:3000 completion:c];});
      Check(@"getWorkMode",^(RSAppCompletion c){[g getWorkModeWithTimeoutMs:3000 completion:c];});
      Check(@"getSmoothTrackAxes",^(RSAppCompletion c){[g getSmoothTrackAxes:@{} timeoutMs:3000 completion:c];});
      Check(@"getFollowTuning",^(RSAppCompletion c){[g getFollowTuning:@{} timeoutMs:3000 completion:c];});
      Check(@"getRcTuning",^(RSAppCompletion c){[g getRcTuning:@{} timeoutMs:3000 completion:c];});
      Check(@"getStandaloneTuning",^(RSAppCompletion c){[g getStandaloneTuning:@{} timeoutMs:3000 completion:c];});
      if([NSProcessInfo.processInfo.environment[@"RS4MINI_SDK_WRITEBACK"] isEqual:@"yes"]){
       NSNumber *mode=sensitivity[@"rawValue"];
       if(mode && (mode.intValue==0||mode.intValue==1)){
        Check(@"sensitivity.sameValueWrite",^(RSAppCompletion c){[g setFollowSensitivity:mode timeoutMs:3000 completion:c];});
        Check(@"sensitivity.sameValueReadback",^(RSAppCompletion c){[g getFollowSensitivityWithTimeoutMs:3000 completion:^(NSDictionary *r,NSError *e){
          if(!e&&![r[@"rawValue"] isEqual:mode])e=[NSError errorWithDomain:@"SDK_TEST_READBACK_MISMATCH" code:1 userInfo:nil];c(r,e);
        }];});
       }else Row(@"sensitivity.sameValueWrite",NO,@"No valid baseline; no write sent");
      }
      Check(@"follow.speed",^(RSAppCompletion c){[g getFollowSettings:@"speed" timeoutMs:3000 completion:c];});
      Check(@"rc.speed",^(RSAppCompletion c){[g getRcSettings:@"speed" timeoutMs:3000 completion:c];});
      Check(@"motor.single",^(RSAppCompletion c){[g getMotorTuning:@{@"axis":@"pitch",@"parameter":@"stiffness"} timeoutMs:3000 completion:c];});
      Check(@"motor.bulk",^(RSAppCompletion c){[g getMotorTuning:@{} timeoutMs:3000 completion:c];});
      Check(@"handle",^(RSAppCompletion c){[g getHandleSettingsWithTimeoutMs:3000 completion:c];});
      Check(@"calibration.query",^(RSAppCompletion c){[g queryCalibrationStatusWithTimeoutMs:3000 completion:c];});
      [g requestDegreeInfo];Row(@"degreeInfo",Wait(^BOOL{return degree&&!g.busy;},5),nil);
      [g stop];Row(@"stop",Wait(^BOOL{return !g.busy;},5),nil);
     }
    }
    [g disconnect];Row(@"disconnect",Wait(^BOOL{return !g.ready&&!g.connecting&&!g.busy;},5),nil);
    NSDictionary *report=@{@"port":@"macos",@"entry":@"RSBleDevice",@"rows":rows};
    NSData *data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil];
    fwrite(data.bytes,1,data.length,stdout);puts("");
    for(NSDictionary *r in rows)if(![r[@"ok"] boolValue])return 1;return 0;
 }
}
