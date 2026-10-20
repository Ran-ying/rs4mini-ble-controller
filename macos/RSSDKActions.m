#import "RSSDKActions.h"
#import "RSDeviceProtocol.h"
#import <math.h>
static NSError *FormError(NSString *message) { return [NSError errorWithDomain:@"RS4MiniSDKPanel" code:1 userInfo:@{NSLocalizedDescriptionKey:message}]; }
static void MutableRemove(NSMutableDictionary *p, NSString *key) { [p removeObjectForKey:key]; }
NSArray *RSSDKOperations(void) { return @[@{@"id":@"sensitivity.read",@"title":@"读取跟随灵敏度",@"group":@"读取与状态",@"fields":@[],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"sensitivity.write",@"title":@"设置跟随灵敏度",@"group":@"跟随与模式",@"fields":@[@{@"key":@"mode",@"label":@"源模式值",@"kind":@"enum",@"required":@YES,@"choices":@[@"0",@"1"],@"sample":@"0"}],@"write":@YES,@"confirm":@NO,@"detail":@"仅发送请求；ACK 不代表生效、持久化或物理完成。"},
@{@"id":@"follow.levels.read",@"title":@"读取跟随档位",@"group":@"跟随与模式",@"fields":@[@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"speed",@"acceleration",@"deadZone"],@"sample":@"speed"}],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"follow.levels.write",@"title":@"设置跟随档位",@"group":@"跟随与模式",@"fields":@[@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"speed",@"acceleration",@"deadZone"],@"sample":@"speed"},@{@"key":@"pitch",@"label":@"pitch 档位",@"kind":@"enum",@"required":@NO,@"choices":@[@"custom",@"low",@"middle",@"high"],@"sample":@"low"},@{@"key":@"roll",@"label":@"roll 档位",@"kind":@"enum",@"required":@NO,@"choices":@[@"custom",@"low",@"middle",@"high"],@"sample":@"low"},@{@"key":@"yaw",@"label":@"yaw 档位",@"kind":@"enum",@"required":@NO,@"choices":@[@"custom",@"low",@"middle",@"high"],@"sample":@"low"}],@"write":@YES,@"confirm":@NO,@"detail":@"只修改选定轴；留空轴保持当前值。至少选择一轴。"},
@{@"id":@"follow.tuning.read",@"title":@"读取跟随数值",@"group":@"数值参数",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@NO,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"},@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@NO,@"choices":@[@"speed",@"acceleration",@"deadZone"],@"sample":@"speed"}],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"follow.tuning.write",@"title":@"设置跟随数值",@"group":@"数值参数",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@YES,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"},@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"speed",@"acceleration",@"deadZone"],@"sample":@"speed"},@{@"key":@"value",@"label":@"源整数值",@"kind":@"integer",@"required":@YES,@"min":@0,@"max":@100,@"sample":@"20"}],@"write":@YES,@"confirm":@NO,@"detail":@"源整数单位；范围由 SDK 按参数校验，不是物理速度。"},
@{@"id":@"rc.levels.read",@"title":@"读取摇杆档位",@"group":@"跟随与模式",@"fields":@[@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"speed",@"deadZone",@"smoothing"],@"sample":@"speed"}],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"rc.levels.write",@"title":@"设置摇杆档位",@"group":@"跟随与模式",@"fields":@[@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"speed",@"deadZone",@"smoothing"],@"sample":@"speed"},@{@"key":@"pitch",@"label":@"pitch 档位",@"kind":@"enum",@"required":@NO,@"choices":@[@"custom",@"low",@"middle",@"high"],@"sample":@"low"},@{@"key":@"roll",@"label":@"roll 档位",@"kind":@"enum",@"required":@NO,@"choices":@[@"custom",@"low",@"middle",@"high"],@"sample":@"low"},@{@"key":@"yaw",@"label":@"yaw 档位",@"kind":@"enum",@"required":@NO,@"choices":@[@"custom",@"low",@"middle",@"high"],@"sample":@"low"}],@"write":@YES,@"confirm":@NO,@"detail":@"只修改选定轴；留空轴保持当前值。至少选择一轴。"},
@{@"id":@"rc.tuning.read",@"title":@"读取摇杆数值",@"group":@"数值参数",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@NO,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"},@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@NO,@"choices":@[@"speed",@"deadZone",@"smoothing"],@"sample":@"speed"}],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"rc.tuning.write",@"title":@"设置摇杆数值",@"group":@"数值参数",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@YES,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"},@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"speed",@"deadZone",@"smoothing"],@"sample":@"speed"},@{@"key":@"value",@"label":@"源整数值",@"kind":@"integer",@"required":@YES,@"min":@0,@"max":@100,@"sample":@"20"}],@"write":@YES,@"confirm":@NO,@"detail":@"源整数单位；范围由 SDK 按参数校验，不是物理速度。"},
@{@"id":@"CustomFollow.read",@"title":@"读取自定义跟随",@"group":@"跟随与模式",@"fields":@[],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"CustomFollow.write",@"title":@"设置自定义跟随",@"group":@"跟随与模式",@"fields":@[@{@"key":@"enabled",@"label":@"enabled",@"kind":@"bool",@"required":@NO,@"sample":@"false"},@{@"key":@"pitch",@"label":@"pitch",@"kind":@"bool",@"required":@NO,@"sample":@"false"},@{@"key":@"roll",@"label":@"roll",@"kind":@"bool",@"required":@NO,@"sample":@"false"},@{@"key":@"yaw",@"label":@"yaw",@"kind":@"bool",@"required":@NO,@"sample":@"false"}],@"write":@YES,@"confirm":@NO,@"detail":@"至少指定一个字段；未指定位由 SDK 新鲜读取后保留。电机设置可能改变机构状态。"},
@{@"id":@"Motor.read",@"title":@"读取电机开关",@"group":@"跟随与模式",@"fields":@[],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"Motor.write",@"title":@"设置电机开关",@"group":@"跟随与模式",@"fields":@[@{@"key":@"enabled",@"label":@"enabled",@"kind":@"bool",@"required":@NO,@"sample":@"false"},@{@"key":@"forbidSelfie",@"label":@"forbidSelfie",@"kind":@"bool",@"required":@NO,@"sample":@"false"},@{@"key":@"forbidVertical",@"label":@"forbidVertical",@"kind":@"bool",@"required":@NO,@"sample":@"false"},@{@"key":@"roll360",@"label":@"roll360",@"kind":@"bool",@"required":@NO,@"sample":@"false"}],@"write":@YES,@"confirm":@YES,@"detail":@"至少指定一个字段；未指定位由 SDK 新鲜读取后保留。电机设置可能改变机构状态。"},
@{@"id":@"axisMode.read",@"title":@"读取轴模式",@"group":@"跟随与模式",@"fields":@[],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"axisMode.write",@"title":@"设置轴模式",@"group":@"跟随与模式",@"fields":@[@{@"key":@"sourceMode",@"label":@"源轴模式",@"kind":@"enum",@"required":@YES,@"choices":@[@"ThreeAxis",@"TwoAxis",@"Roll360",@"ThreeDRoll360"],@"sample":@"ThreeAxis"}],@"write":@YES,@"confirm":@NO,@"detail":@"源字段操作，不能当作完整 PF/PTF/FPV 模式切换。"},
@{@"id":@"profile.read",@"title":@"读取用户配置",@"group":@"跟随与模式",@"fields":@[],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"profile.write",@"title":@"设置用户配置",@"group":@"跟随与模式",@"fields":@[@{@"key":@"sourceProfileValue",@"label":@"源配置值（0–5）",@"kind":@"integer",@"required":@YES,@"min":@0,@"max":@5,@"sample":@"0"}],@"write":@YES,@"confirm":@NO,@"detail":@"源字段操作，不能当作完整 PF/PTF/FPV 模式切换。"},
@{@"id":@"workMode.read",@"title":@"读取工作模式",@"group":@"跟随与模式",@"fields":@[],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"workMode.write",@"title":@"设置工作模式",@"group":@"跟随与模式",@"fields":@[@{@"key":@"sourceMode",@"label":@"源工作模式",@"kind":@"enum",@"required":@YES,@"choices":@[@"Free",@"Flower",@"Fpv",@"Center"],@"sample":@"Free"}],@"write":@YES,@"confirm":@NO,@"detail":@"源字段操作，不能当作完整 PF/PTF/FPV 模式切换。"},
@{@"id":@"smooth.read",@"title":@"读取跟随轴开关",@"group":@"跟随与模式",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@NO,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"}],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"smooth.write",@"title":@"设置跟随轴开关",@"group":@"跟随与模式",@"fields":@[@{@"key":@"axes.pitch",@"label":@"pitch",@"kind":@"bool",@"required":@NO,@"sample":@"false"},@{@"key":@"axes.roll",@"label":@"roll",@"kind":@"bool",@"required":@NO,@"sample":@"false"},@{@"key":@"axes.yaw",@"label":@"yaw",@"kind":@"bool",@"required":@NO,@"sample":@"false"}],@"write":@YES,@"confirm":@NO,@"detail":@"至少选择一轴，其余轴不写入。"},
@{@"id":@"motorTuning.read",@"title":@"读取电机数值",@"group":@"数值参数",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@YES,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"},@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"stiffness",@"strength",@"gyroFiltering",@"preControl"],@"sample":@"stiffness"}],@"write":@NO,@"confirm":@NO,@"detail":@"按轴和参数读取；SDK逐项查询并汇总，非原子快照。"},
@{@"id":@"motorTuning.write",@"title":@"设置电机数值",@"group":@"数值参数",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@YES,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"},@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"stiffness",@"strength",@"gyroFiltering",@"preControl"],@"sample":@"stiffness"},@{@"key":@"value",@"label":@"源整数值",@"kind":@"integer",@"required":@YES,@"min":@0,@"max":@100,@"sample":@"5"}],@"write":@YES,@"confirm":@YES,@"detail":@"源范围由 SDK 校验；写入电机参数的效果尚未实机验收。"},
@{@"id":@"standalone.read",@"title":@"读取独立配置",@"group":@"数值参数",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@NO,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"},@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@NO,@"choices":@[@"speed",@"smoothing"],@"sample":@"speed"}],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"standalone.write",@"title":@"设置独立配置（输入源2）",@"group":@"数值参数",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@YES,@"choices":@[@"pitch",@"roll",@"yaw"],@"sample":@"pitch"},@{@"key":@"parameter",@"label":@"参数",@"kind":@"enum",@"required":@YES,@"choices":@[@"speed",@"smoothing"],@"sample":@"speed"},@{@"key":@"value",@"label":@"源整数值",@"kind":@"integer",@"required":@YES,@"min":@0,@"max":@100,@"sample":@"20"},@{@"key":@"inputSource",@"label":@"输入源（显式）",@"kind":@"enum",@"required":@YES,@"choices":@[@"2"],@"sample":@"2"}],@"write":@YES,@"confirm":@NO,@"detail":@"输入源2与数值同包写入；不自动恢复输入源，不代表活动预设确认。"},
@{@"id":@"fine.write",@"title":@"Pitch / Roll 微调",@"group":@"手柄与微调",@"fields":@[@{@"key":@"axis",@"label":@"轴",@"kind":@"enum",@"required":@YES,@"choices":@[@"pitch",@"roll"],@"sample":@"pitch"},@{@"key":@"adjustmentDegrees",@"label":@"调整量（度，-2..2）",@"kind":@"number",@"required":@YES,@"min":@-2,@"max":@2,@"sample":@"0.1"}],@"write":@YES,@"confirm":@NO,@"detail":@"这是源微调请求；SDK不自动暂停稳定器或回滚。"},
@{@"id":@"system.read",@"title":@"读取系统校准候选状态",@"group":@"校准与维护",@"fields":@[],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"balance.read",@"title":@"读取平衡测试状态",@"group":@"校准与维护",@"fields":@[],@"write":@NO,@"confirm":@NO,@"detail":@"显式查询；本机响应与字段布局仍待验收。"},
@{@"id":@"tune.write",@"title":@"自动调参开始 / 取消请求",@"group":@"校准与维护",@"fields":@[@{@"key":@"start",@"label":@"开始（false 为取消请求）",@"kind":@"bool",@"required":@YES,@"sample":@"false"}],@"write":@YES,@"confirm":@YES,@"detail":@"此请求无 ACK。false 不是已验证的物理中止。"},
@{@"id":@"system.write",@"title":@"系统校准候选（未通过）",@"group":@"校准与维护",@"fields":@[],@"write":@YES,@"confirm":@YES,@"detail":@"与 AUTO 部件校准不同；型号/UI关系与完成、中止仍待验。"},
@{@"id":@"component.write",@"title":@"水平校准（AUTO）",@"group":@"校准与维护",@"fields":@[@{@"key":@"sourcePart",@"label":@"源部件",@"kind":@"enum",@"required":@YES,@"choices":@[@"AUTO"],@"sample":@"AUTO"}],@"write":@YES,@"confirm":@YES,@"detail":@"本机屏幕称水平校准。SDK先读取电机门槛；ACK不代表完成，完成提示仍需手动确认。"},
@{@"id":@"balance.write",@"title":@"启动平衡测试请求",@"group":@"校准与维护",@"fields":@[],@"write":@YES,@"confirm":@YES,@"detail":@"使用参数 balance_test，不是04:40旧平衡调整。"},
@{@"id":@"center.read",@"title":@"CENTER 只读信息",@"group":@"读取与状态",@"fields":@[@{@"key":@"sourceVersion",@"label":@"显式源版本",@"kind":@"enum",@"required":@YES,@"choices":@[@"Ver1_0",@"Ver1_1",@"Ver1_3",@"Ver13"],@"sample":@"Ver1_0"}],@"write":@NO,@"confirm":@NO,@"detail":@"只读GET；需要显式格式版本，不协商、不激活、不绑定。"},
@{@"id":@"raw.read",@"title":@"原始参数读取",@"group":@"读取与状态",@"fields":@[@{@"key":@"index",@"label":@"源参数索引（0–255）",@"kind":@"integer",@"required":@YES,@"min":@0,@"max":@255,@"sample":@"35"},@{@"key":@"size",@"label":@"已知响应宽度",@"kind":@"enum",@"required":@YES,@"choices":@[@"1",@"2",@"4",@"8"],@"sample":@"1"}],@"write":@NO,@"confirm":@NO,@"detail":@"仅当已知索引及宽度时使用；不猜测参数名称，不提供原始写入。"},
@{@"id":@"program.read",@"title":@"单次程序状态请求",@"group":@"订阅与状态",@"fields":@[@{@"key":@"program",@"label":@"程序",@"kind":@"enum",@"required":@YES,@"choices":@[@"track",@"timelapse",@"panorama"],@"sample":@"track"}],@"write":@NO,@"confirm":@NO,@"detail":@"仅状态请求，不执行程序；ACK不保证收到新状态。"}]; }
NSDictionary *RSSDKOperation(NSString *identifier) { for (NSDictionary *row in RSSDKOperations()) if ([row[@"id"] isEqual:identifier]) return row; return nil; }
NSDictionary *RSSDKParseForm(NSString *identifier, NSDictionary *strings, NSError **error) {
    NSDictionary *op=RSSDKOperation(identifier);
    if (!op || ![strings isKindOfClass:NSDictionary.class]) { if(error)*error=FormError(@"未知操作或表单"); return nil; }
    NSMutableSet *known=[NSMutableSet set]; for (NSDictionary *f in op[@"fields"]) [known addObject:f[@"key"]];
    for (id key in strings) if (![known containsObject:key]) { if(error)*error=FormError(@"表单含未知字段"); return nil; }
    NSMutableDictionary *result=[NSMutableDictionary dictionary];
    for (NSDictionary *f in op[@"fields"]) {
        id input=strings[f[@"key"]];
        if (input && ![input isKindOfClass:NSString.class]) { if(error)*error=FormError(@"表单必须为文本输入"); return nil; }
        NSString *text=[(input?:@"") stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
        if (!text.length) { if([f[@"required"] boolValue]) { if(error)*error=FormError([@"请填写：" stringByAppendingString:f[@"label"]]); return nil; } continue; }
        id value=nil; NSString *kind=f[@"kind"];
        if ([kind isEqual:@"enum"]) { if ([f[@"choices"] containsObject:text]) value=[text copy]; }
        else if ([kind isEqual:@"bool"]) { if([text isEqual:@"true"])value=@YES;else if([text isEqual:@"false"])value=@NO; }
        else if ([kind isEqual:@"keys"]) {
            NSMutableArray *keys=[NSMutableArray array]; for(NSString *part in [text componentsSeparatedByString:@","]) { NSString *key=[part stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet]; if(!key.length || [keys containsObject:key]) { if(error)*error=FormError(@"订阅键不能为空或重复");return nil; } [keys addObject:key]; } value=[keys copy];
        } else {
            NSScanner *scan=[NSScanner scannerWithString:text];scan.locale=[NSLocale localeWithLocaleIdentifier:@"en_US_POSIX"];scan.charactersToBeSkipped=nil;double n;
            if([scan scanDouble:&n]&&scan.isAtEnd&&isfinite(n)&&n>=[f[@"min"] doubleValue]&&n<=[f[@"max"] doubleValue]&&(![kind isEqual:@"integer"]||floor(n)==n))value=@(n);
        }
        if(!value){if(error)*error=FormError([@"字段值无效：" stringByAppendingString:f[@"label"]]);return nil;}
        NSArray *path=[f[@"key"] componentsSeparatedByString:@"."];
        if(path.count==2){NSMutableDictionary *nested=result[path[0]];if(!nested){nested=[NSMutableDictionary dictionary];result[path[0]]=nested;}nested[path[1]]=value;}else result[f[@"key"]]=value;
    }
    BOOL valid=YES;
    if([identifier isEqual:@"standalone.write"])result[@"inputSource"]=@2;
    if([identifier hasSuffix:@".levels.write"]){NSString *domain=[identifier hasPrefix:@"follow"]?@"follow":@"rc";NSMutableDictionary *patch=[result mutableCopy];[patch removeObjectForKey:@"parameter"];valid=RSAppSettingsPatch(RSAppModeKind(domain,result[@"parameter"]),patch)!=nil;}
    else if([identifier isEqual:@"CustomFollow.write"]||[identifier isEqual:@"Motor.write"])valid=RSAppSettingsPatch([identifier hasPrefix:@"Custom"]?@"customFollow":@"motor",result)!=nil;
    else if([identifier isEqual:@"follow.tuning.write"]||[identifier isEqual:@"rc.tuning.write"])valid=RSAppTuningWriteSpec([identifier hasPrefix:@"follow"]?@"follow":@"rc",result)!=nil;
    else if([identifier isEqual:@"standalone.write"])valid=RSAppStandaloneWriteSpec(result)!=nil;
    else if([identifier isEqual:@"motorTuning.write"])valid=RSAppMotorWriteSpec(result)!=nil;
    else if([identifier isEqual:@"smooth.write"])valid=RSAppSmoothTrackSpec(result)!=nil;
    else if([identifier isEqual:@"fine.write"])valid=RSAppFineTuneSpec(result)!=nil;
    else if([identifier isEqual:@"axisMode.write"])valid=RSAppAxisModeSpec(result)!=nil;
    else if([identifier isEqual:@"profile.write"])valid=RSAppProfileValueSpec(@"userProfile",result)!=nil;
    else if([identifier isEqual:@"workMode.write"])valid=RSAppProfileValueSpec(@"workMode",result)!=nil;
    if(!valid){if(error)*error=FormError(@"输入不符合SDK的命名参数/范围要求；至少指定一个要修改的字段。");return nil;}
    return [result copy];
}
void RSSDKDispatch(RSGimbal *gimbal, NSString *identifier, NSDictionary *strings, double timeoutMs, RSAppCompletion completion) {
    NSError *error=nil; NSDictionary *spec=RSSDKParseForm(identifier,strings,&error);
    if(!spec || !isfinite(timeoutMs)||timeoutMs<=0||timeoutMs>60000){if(completion)completion(nil,error?:FormError(@"超时需大于0且不超过60000毫秒"));return;}
    if(!gimbal.ready || gimbal.busy){if(completion)completion(nil,FormError(@"请先连接并等待设备空闲"));return;}
    if(![gimbal.appProfile isEqual:@"ronin-2.2.2"]){if(completion)completion(nil,FormError(@"请显式启用当前App协议来源"));return;}
    NSMutableDictionary *p=[spec mutableCopy];
    if ([identifier isEqual:@"sensitivity.read"]) { [gimbal getFollowSensitivityWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"sensitivity.write"]) { [gimbal setFollowSensitivity:@([p[@"mode"] intValue]) timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"follow.levels.read"]) { [gimbal getFollowSettings:p[@"parameter"] timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"follow.levels.write"]) { NSString *parameter=p[@"parameter"]; MutableRemove(p,@"parameter"); [gimbal setFollowSettings:parameter settings:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"follow.tuning.read"]) { [gimbal getFollowTuning:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"follow.tuning.write"]) { [gimbal setFollowTuning:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"rc.levels.read"]) { [gimbal getRcSettings:p[@"parameter"] timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"rc.levels.write"]) { NSString *parameter=p[@"parameter"]; MutableRemove(p,@"parameter"); [gimbal setRcSettings:parameter settings:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"rc.tuning.read"]) { [gimbal getRcTuning:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"rc.tuning.write"]) { [gimbal setRcTuning:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"CustomFollow.read"]) { [gimbal getCustomFollowSettingsWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"CustomFollow.write"]) { [gimbal setCustomFollowSettings:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"Motor.read"]) { [gimbal getMotorSettingsWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"Motor.write"]) { [gimbal setMotorSettings:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"axisMode.read"]) { [gimbal getAxisModeWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"axisMode.write"]) { [gimbal sendAxisModeRequest:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"profile.read"]) { [gimbal getUserProfileWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"profile.write"]) { [gimbal sendUserProfileRequest:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"workMode.read"]) { [gimbal getWorkModeWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"workMode.write"]) { [gimbal sendWorkModeRequest:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"smooth.read"]) { [gimbal getSmoothTrackAxes:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"smooth.write"]) { [gimbal sendSmoothTrackAxesRequest:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"motorTuning.read"]) { [gimbal getMotorTuning:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"motorTuning.write"]) { [gimbal setMotorTuning:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"standalone.read"]) { [gimbal getStandaloneTuning:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"standalone.write"]) { p[@"inputSource"]=@2; [gimbal setStandaloneTuning:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"fine.write"]) { [gimbal sendFineTuneRequest:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"system.read"]) { [gimbal getAutoCalibrationStatusWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"balance.read"]) { [gimbal getBalanceTestStatusWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"tune.write"]) { [gimbal sendAutoTuneRequest:p[@"start"] completion:completion]; }
    else if ([identifier isEqual:@"system.write"]) { [gimbal sendAutoCalibrationRequestWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"component.write"]) { [gimbal sendComponentCalibrationRequest:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"balance.write"]) { [gimbal sendBalanceTestRequestWithTimeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"center.read"]) { [gimbal getCenterActivationInfo:p timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"raw.read"]) { [gimbal readAppParameters:@[@{@"index":p[@"index"],@"size":@([p[@"size"] intValue])}] timeoutMs:timeoutMs completion:completion]; }
    else if ([identifier isEqual:@"program.read"]) { [gimbal sendProgramStatusRequest:p timeoutMs:timeoutMs completion:completion]; }
}
NSDictionary *RSSDKStatusSnapshot(RSGimbal *g) { return @{@"calibration":g.appCalibrationStatus?:NSNull.null,@"userParameters":g.appUserParameterStatus?:NSNull.null,@"handheldStick":g.appHandheldStickStatus?:NSNull.null,@"abnormal":g.appAbnormalStatus?:NSNull.null,@"battery":g.appBatteryStatus?:NSNull.null,@"program":g.appProgramStatus?:NSNull.null,@"peripheral":g.appPeripheralStatus?:NSNull.null,@"externalDevice":g.appExternalDeviceStatus?:NSNull.null,@"sensorCalibration":g.appSensorCalibrationStatus?:NSNull.null,@"tutorial":g.appTutorialStatus?:NSNull.null}; }
static id DisplayValue(id v) {
    if([v isKindOfClass:NSData.class]){NSMutableString *hex=[NSMutableString string];for(NSUInteger i=0;i<[v length];i++)[hex appendFormat:@"%02x",((const uint8_t *)[v bytes])[i]];return hex;}
    if([v isKindOfClass:NSDictionary.class]){NSMutableDictionary *d=[NSMutableDictionary dictionary];for(id k in v)d[[k description]]=DisplayValue(v[k]);return d;}
    if([v isKindOfClass:NSArray.class]){NSMutableArray *a=[NSMutableArray array];for(id x in v)[a addObject:DisplayValue(x)];return a;}
    return v?:NSNull.null;
}
NSString *RSSDKDisplay(id v){id value=DisplayValue(v);NSData *data=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted|NSJSONWritingSortedKeys|NSJSONWritingFragmentsAllowed error:nil];return data?[[NSString alloc]initWithData:data encoding:NSUTF8StringEncoding]:[value description];}
