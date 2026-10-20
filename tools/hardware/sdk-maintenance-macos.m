// Explicit real-device maintenance runner: Foundation/CoreBluetooth/device SDK only.
#import <Foundation/Foundation.h>
#import "RSBleDevice.h"
static NSMutableArray *rows;
static NSFileHandle *capture;
static id Safe(id value) {
 if([value isKindOfClass:NSData.class])return [value base64EncodedStringWithOptions:0];
 if([value isKindOfClass:NSDictionary.class]){NSMutableDictionary *d=[NSMutableDictionary dictionary];for(id key in value)d[[key description]]=Safe(value[key]);return d;}
 if([value isKindOfClass:NSArray.class]){NSMutableArray *a=[NSMutableArray array];for(id item in value)[a addObject:Safe(item)];return a;}
 return value?:NSNull.null;
}
static void Log(NSString *kind,id data){NSDictionary *r=@{@"at":@(NSDate.date.timeIntervalSince1970),@"kind":kind,@"data":Safe(data)};NSData *b=[NSJSONSerialization dataWithJSONObject:r options:0 error:nil];if(b){[capture writeData:b];[capture writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];}}
static BOOL Wait(BOOL (^condition)(void),double seconds){double end=NSProcessInfo.processInfo.systemUptime+seconds;while(!condition()&&NSProcessInfo.processInfo.systemUptime<end)[[NSRunLoop currentRunLoop]runUntilDate:[NSDate dateWithTimeIntervalSinceNow:.02]];return condition();}
static void MaintenancePause(double seconds){Wait(^BOOL{return NO;},seconds);}
static void Row(NSString *name,BOOL ok,id value){NSMutableDictionary *r=[@{@"name":name,@"ok":@(ok)} mutableCopy];if(value)r[@"value"]=Safe(value);[rows addObject:r];Log(@"check",r);}
static NSDictionary *Check(NSString *name,void (^start)(RSAppCompletion)){
 __block BOOL done=NO;__block NSDictionary *result=nil;__block NSError *error=nil;
 start(^(NSDictionary *r,NSError *e){result=r;error=e;done=YES;});BOOL finished=Wait(^BOOL{return done;},7);
 Log(name,result?:@{@"errorCode":error.userInfo[@"code"]?:@"HARNESS_DEADLINE"});
 Row(name,finished&&!error&&result!=nil,error?@{@"errorCode":error.userInfo[@"code"]?:error.domain}:@{@"callbackCompleted":@(finished)});return finished&&!error?result:nil;
}
int main(int argc,const char *argv[]){@autoreleasepool{
 if(argc>1&&!strcmp(argv[1],"--help")){puts("RS4MINI_SDK_TEST=yes RS4MINI_SDK_MAINTENANCE=fine-tune|autotune|horizontal|acceleration-echo tools/hardware/sdk-maintenance-macos.sh --run");return 0;}
 NSDictionary *env=NSProcessInfo.processInfo.environment;NSString *action=env[@"RS4MINI_SDK_MAINTENANCE"];
 if(![env[@"RS4MINI_SDK_TEST"]isEqual:@"yes"]||![@[@"fine-tune",@"autotune",@"horizontal",@"acceleration-echo"]containsObject:action]){fputs("Explicit test opt-in and named maintenance case required\n",stderr);return 2;}
 NSString *directory=env[@"RS4MINI_CAPTURE_DIR"];if(!directory.length){fputs("Local ignored capture directory required\n",stderr);return 2;}
 NSString *path=[directory stringByAppendingPathComponent:[NSString stringWithFormat:@"sdk-macos-%@-%.0f.jsonl",action,NSDate.date.timeIntervalSince1970*1000]];
 if(![[NSFileManager defaultManager]createFileAtPath:path contents:nil attributes:nil])return 2;capture=[NSFileHandle fileHandleForWritingAtPath:path];rows=[NSMutableArray array];
 __block BOOL powered=NO;__block NSUInteger samples=0;__block NSDictionary *sample=nil;
 RSBleDevice *g=[[RSBleDevice alloc]initWithStatus:^(NSString *text,BOOL ready){if([text containsString:@"蓝牙就绪"])powered=YES;}];
 g.telemetryHandler=^(NSDictionary *s){if(s[@"jointAngles"]){samples++;sample=s;}Log(@"telemetry",s);};g.messageHandler=^(NSDictionary *m){Log(@"raw",m);};
 g.appStatusHandler=^(NSDictionary *s){Log(@"status",s);if([@[@"calibration",@"sensorCalibration"]containsObject:s[@"kind"]]){NSString *state=s[@"state"]?:s[@"sourceStatus"];NSNumber *progress=s[@"percent"]?:s[@"rawProgressValue"];printf("PROGRESS %s %d\n",state.UTF8String,progress.intValue);fflush(stdout);}};
 @try{
  Row(@"deviceLayerOnly",NSClassFromString(@"RSGimbal")==nil,nil);
  BOOL power=Wait(^BOOL{return powered;},10);Row(@"bluetoothReady",power,nil);
  if(power){[g connect];BOOL linked=Wait(^BOOL{return g.ready;},32);Row(@"connect",linked,nil);
   if(linked){Row(@"profile",[g useAppProfile:@"ronin-2.2.2"],nil);NSDictionary *motor=Check(@"motorPreflight",^(RSAppCompletion c){[g getMotorSettingsWithTimeoutMs:3000 completion:c];});BOOL enabled=[motor[@"settings"][@"enabled"]boolValue];Row(@"motorAlreadyEnabled",enabled,nil);
    if(enabled){puts("PREPARE_5_SECONDS");fflush(stdout);MaintenancePause(5);
     if([action isEqual:@"fine-tune"]){for(NSString *axis in @[@"pitch",@"roll"]){NSUInteger seen=samples;BOOL fresh=Wait(^BOOL{return samples>seen;},3);NSDictionary *before=sample[@"jointAngles"];Row([axis stringByAppendingString:@".beforeFresh"],fresh,nil);
      NSDictionary *plus=Check([axis stringByAppendingString:@".plus"],^(RSAppCompletion c){[g sendFineTuneRequest:@{@"axis":axis,@"adjustmentDegrees":@1}timeoutMs:5000 completion:c];});MaintenancePause(4);seen=samples;fresh=Wait(^BOOL{return samples>seen;},3);NSDictionary *afterPlus=sample[@"jointAngles"];Row([axis stringByAppendingString:@".plusFresh"],fresh,nil);
      NSDictionary *minus=Check([axis stringByAppendingString:@".minus"],^(RSAppCompletion c){[g sendFineTuneRequest:@{@"axis":axis,@"adjustmentDegrees":@-1}timeoutMs:5000 completion:c];});MaintenancePause(4);seen=samples;fresh=Wait(^BOOL{return samples>seen;},3);NSDictionary *afterMinus=sample[@"jointAngles"];Row([axis stringByAppendingString:@".minusFresh"],fresh,nil);
      double b=[before[axis]doubleValue],p=[afterPlus[axis]doubleValue],m=[afterMinus[axis]doubleValue];NSDictionary *effect=@{@"before":@(b),@"afterPlus":@(p),@"afterMinus":@(m)};
      Row([axis stringByAppendingString:@".measuredDirection"],plus&&minus&&before[axis]&&afterPlus[axis]&&afterMinus[axis]&&p-b>.2&&m-p<-.2,effect);printf("EFFECT %s %.2f %.2f %.2f\n",axis.UTF8String,b,p,m);fflush(stdout);
     }}else if([action isEqual:@"acceleration-echo"]){
      NSDictionary *before=Check(@"acceleration.before",^(RSAppCompletion c){[g getFollowTuning:@{@"parameter":@"acceleration"} timeoutMs:5000 completion:c];});
      NSDictionary *levels=Check(@"acceleration.levelsBefore",^(RSAppCompletion c){[g getFollowSettings:@"acceleration" timeoutMs:5000 completion:c];});
      BOOL allowed=[before[@"values"]count]==3&&[levels[@"settings"]count]==3;for(NSDictionary *r in before[@"values"])allowed&=[r[@"rawValue"]intValue]==1;for(NSString *v in [levels[@"settings"]allValues])allowed&=[v isEqual:@"low"];
      Row(@"acceleration.authorizedBaseline",allowed,nil);if(allowed){for(NSString *axis in @[@"pitch",@"roll",@"yaw"])Check([@"acceleration.echo." stringByAppendingString:axis],^(RSAppCompletion c){[g setFollowTuning:@{@"axis":axis,@"parameter":@"acceleration",@"value":@1} timeoutMs:5000 completion:c];});
       NSDictionary *after=Check(@"acceleration.after",^(RSAppCompletion c){[g getFollowTuning:@{@"parameter":@"acceleration"} timeoutMs:5000 completion:c];});
       NSDictionary *afterLevels=Check(@"acceleration.levelsAfter",^(RSAppCompletion c){[g getFollowSettings:@"acceleration" timeoutMs:5000 completion:c];});
       BOOL same=[after[@"values"]count]==3;NSMutableArray *values=[NSMutableArray array];for(NSDictionary *r in after[@"values"]){same&=[r[@"rawValue"]intValue]==1;[values addObject:@{@"axis":r[@"axis"],@"rawValue":r[@"rawValue"]}];}
       Row(@"acceleration.allOne",same,values);Row(@"acceleration.levelsUnchanged",[levels[@"settings"]isEqual:afterLevels[@"settings"]],afterLevels[@"settings"]);
      }
}else if([action isEqual:@"horizontal"]){NSDictionary *request=Check(@"horizontal.request",^(RSAppCompletion c){[g sendComponentCalibrationRequest:@{@"sourcePart":@"AUTO"}timeoutMs:5000 completion:c];});BOOL terminal=NO;if(request)terminal=Wait(^BOOL{return [@[@"COMPLETE",@"FAIL"]containsObject:g.appSensorCalibrationStatus[@"sourceStatus"]];},65);Row(@"horizontal.terminal",terminal&&[g.appSensorCalibrationStatus[@"sourceStatus"]isEqual:@"COMPLETE"],g.appSensorCalibrationStatus);
     }else{Check(@"motor.before",^(RSAppCompletion c){[g getMotorTuning:@{}timeoutMs:5000 completion:c];});NSDictionary *request=Check(@"autotune.start",^(RSAppCompletion c){[g sendAutoTuneRequest:@YES completion:c];});BOOL terminal=NO;if(request)terminal=Wait(^BOOL{return [@[@"Complete",@"Failure"]containsObject:g.appCalibrationStatus[@"state"]];},45);Row(@"autotune.terminal",terminal&&[g.appCalibrationStatus[@"state"]isEqual:@"Complete"],g.appCalibrationStatus);Check(@"motor.after",^(RSAppCompletion c){[g getMotorTuning:@{}timeoutMs:5000 completion:c];});}
    }
   }
  }
 }@finally{[g disconnect];Row(@"disconnect",Wait(^BOOL{return !g.ready&&!g.connecting&&!g.busy;},5),nil);g.telemetryHandler=nil;g.messageHandler=nil;g.appStatusHandler=nil;}
 NSDictionary *report=@{@"port":@"macos",@"entry":@"RSBleDevice",@"action":action,@"physicalObservedByUser":NSNull.null,@"rows":rows};Log(@"summary",report);[capture closeFile];NSData *data=[NSJSONSerialization dataWithJSONObject:report options:0 error:nil];fwrite(data.bytes,1,data.length,stdout);puts("");for(NSDictionary *r in rows)if(![r[@"ok"]boolValue])return 1;return 0;
}}
